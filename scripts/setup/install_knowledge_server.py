#!/usr/bin/env python3
"""install_knowledge_server.py — the full-lifecycle installer for the CT6
knowledge server (`services/knowledge_server/`).

Run from `/architect-team:knowledge-install`. Stdlib-only, deterministic — the
knowledge server carries NO LLM and NO network, so there is nothing to
`pip install` and no key to resolve. Mirrors the `install_librarian.py` template
(a step-summary printer, `--json`, `--check-only`, `status`, `uninstall --purge`),
but the knowledge server is an MCP *stdio* server the user's MCP client (Claude
Code, etc.) spawns on demand — so instead of a boot descriptor this installer
GENERATES and PRINTS the MCP registration snippet the user pastes into their own
MCP client config, and NEVER auto-edits that config.

The server is launched with the PORTABLE `--repo-root <repo>` flag (the KS-1
contract — `services/knowledge_server/server.py`): the server auto-discovers the
conventional CT6 sidecars under that root (`docs/data-dictionary.json`,
`lineage-graph.json`, `docs/data-annotations/`, `docs/*_MAP.md`), so the emitted
registration carries NO brittle hardcoded absolute paths. The `--repo-root` is the
TARGET repo whose knowledge gets served; it is resolved from `--repo-root` >
the recorded config > the git repo root of the install context, and recorded in
`config.json` so the registration is reproducible. When none resolves, the
installer falls back to the bundled fixture as a clearly-labelled DEMO/probe
default (never a shipped fake catalog).

PROBE == SHIP: the printed registration argv and confirm_serving's probe argv are
derived from ONE function (`_server_argv`), so a green confirm can never be a
false-green against a different argv than the registration prints.

Subcommands:
  install (default)  Provision the state layout (`config.json` + `cache/`),
                     resolve + record the target repo-root, and GENERATE + PRINT
                     the MCP registration snippet. With `--confirm`, also run the
                     live serving round-trip (below).
  status             Report provisioned / target repo-root / registration.
  print-registration Re-print the MCP registration snippet (JSON + the
                     `claude mcp add` convenience form).
  confirm-serving    START the server as a subprocess and perform a real
                     `initialize` + `tools/list` + `tools/call` JSON-RPC
                     round-trip over stdio; print "serving on this machine" ONLY
                     when a status tool returns a live freshness verdict (the
                     `confirm_gateway_serving` bar).
  uninstall          Remove the provisioning markers. With `--purge`, also remove
                     the whole state dir. Never errors if absent.

Flags:
  --base-dir PATH    The knowledge state dir (default: $CT6_KNOWLEDGE_HOME, else
                     ~/.architect-team/knowledge/). No hardcoded home in the core.
  --repo-root DIR    The TARGET repo whose conventional sidecars get served
                     (default: the git repo root of the install context).
  --server-name NAME The MCP server name in the registration (default ct6-knowledge).
  --confirm          (install) run the live serving round-trip after provisioning.
  --check-only       Report intent only; do not provision.
  --json             Emit a machine-readable JSON status report.
  --purge            (uninstall) also remove the state dir.
  --timeout SECONDS  The serving round-trip timeout (default 15).

Exit codes:
  0  success (install / status / print-registration / uninstall; a confirmed
     serving round-trip).
  1  a real failure, OR the standalone `confirm-serving` diagnostic reporting NOT
     serving.

HONEST BOUNDARY: this provisions state + GENERATES + PRINTS the MCP registration —
it NEVER writes/edits the user's MCP client config, NEVER installs third-party
packages, and NEVER prints "serving" without a real live `tools/call` round-trip.
The result is described as "serving on this machine", never "deployed".
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]

ENV_HOME = "CT6_KNOWLEDGE_HOME"
CONFIG_NAME = "config.json"
CACHE_DIRNAME = "cache"
DEFAULT_SERVER_NAME = "ct6-knowledge"
CONFIRM_TIMEOUT = 15.0

# The knowledge server's stdio entry point (KS-1) + the bundled fixture used as a
# labelled DEMO/probe default when no target repo-root resolves. `--repo-root` at
# the flat fixture dir auto-discovers its root-level lineage-graph.json (a map
# source), so the probe still gets a live round-trip.
_SERVER_PATH = _REPO_ROOT / "services" / "knowledge_server" / "server.py"
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "knowledge_server"

# The status tools the probe tries (one per source family); whichever the server
# discovered under --repo-root answers with a live freshness verdict.
_STATUS_TOOLS = ("get_dictionary_status", "get_map_status")
# The probe sends initialize + tools/list + one tools/call per status tool.
_PROBE_MESSAGES = 1 + 1 + len(_STATUS_TOOLS)

# The freshness verdicts a live status tool may return (ks-server's contract:
# a live probe = tools/call result.isError is False AND
# structuredContent.freshness.verdict in this set).
VALID_FRESHNESS_VERDICTS = frozenset({"current", "stale", "unknowable"})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# base-dir resolution (no hardcoded home in the testable core)
# --------------------------------------------------------------------------- #

def resolve_base_dir(explicit: Optional[str], env: Optional[dict[str, str]] = None) -> Path:
    """Resolve the state base dir: explicit `--base-dir` > `$CT6_KNOWLEDGE_HOME` >
    `~/.architect-team/knowledge/`. The home default is only reached when neither
    override is set — tests always inject one of the first two."""
    env = os.environ if env is None else env
    if explicit:
        return Path(explicit)
    from_env = env.get(ENV_HOME)
    if from_env:
        return Path(from_env)
    return Path.home() / ".architect-team" / "knowledge"


# --------------------------------------------------------------------------- #
# target repo-root resolution + the SINGLE-SOURCE server argv
# --------------------------------------------------------------------------- #

def _git_repo_root(start: Optional[str | Path] = None) -> Optional[str]:
    """The git repo root of `start` (default CWD), or None when not in a git repo
    / git is unavailable. Never raises."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(start or Path.cwd()), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    top = (proc.stdout or "").strip()
    return top or None


def _resolve_repo_root(explicit: Optional[str], base: Optional[Path]
                       ) -> tuple[str, bool]:
    """Resolve the TARGET repo-root and whether it is the labelled fixture default.
    Precedence: explicit `--repo-root` > the recorded config > the git repo root of
    the install context > the bundled fixture (labelled DEMO/probe default)."""
    if explicit:
        return str(explicit), False
    if base is not None:
        cfg = _read_config(base)
        recorded = cfg.get("repo_root")
        if isinstance(recorded, str) and recorded:
            return recorded, bool(cfg.get("using_fixture"))
    git_root = _git_repo_root()
    if git_root:
        return git_root, False
    return str(_FIXTURE_DIR), True


def _server_argv(repo_root: str | Path) -> list[str]:
    """THE ONE function that produces the server launch argv: `<python> <abs
    server.py> --repo-root <repo>`. A path script (services/ has no __init__.py —
    NOT `python -m`). build_registration AND the confirm probe both derive from
    this, so the printed registration and the probed argv can never diverge."""
    py = sys.executable or "python3"
    return [py, str(_SERVER_PATH), "--repo-root", str(repo_root)]


def _probe_argv(repo_root: str | Path) -> list[str]:
    """The confirm-serving probe argv — EXACTLY the registration argv (`_server_argv`)
    plus a hard --max-messages bound (belt-and-suspenders alongside the
    communicate() clean exit). The source portion is identical to what ships."""
    return _server_argv(repo_root) + ["--max-messages", str(_PROBE_MESSAGES)]


# --------------------------------------------------------------------------- #
# live serving confirmation — a real initialize + tools/list + tools/call
# round-trip (the confirm_gateway_serving mold: no "serving" without a real probe)
# --------------------------------------------------------------------------- #

def _init_result_ok(msg: Any) -> bool:
    """A valid initialize response — a result carrying serverInfo.name and a
    protocolVersion (ks-server's recognition rule)."""
    if not isinstance(msg, dict):
        return False
    res = msg.get("result")
    if not isinstance(res, dict) or not res.get("protocolVersion"):
        return False
    info = res.get("serverInfo")
    return isinstance(info, dict) and bool(info.get("name"))


def _tool_call_live(msg: Any) -> tuple[bool, str]:
    """Decide whether a tools/call response is a LIVE status result: result.isError
    is False AND structuredContent.freshness.verdict is one of the valid verdicts
    (ks-server's live-probe definition). A top-level JSON-RPC error (unknown tool /
    bad method) or an isError result is NOT live."""
    if not isinstance(msg, dict):
        return False, "no response to tools/call"
    if msg.get("error"):
        return False, f"JSON-RPC error {msg['error']}"
    res = msg.get("result")
    if not isinstance(res, dict):
        return False, "tools/call carried no result"
    if res.get("isError") is not False:
        return False, f"result.isError={res.get('isError')!r} (a tool-execution error, not a live result)"
    sc = res.get("structuredContent")
    verdict = sc.get("freshness", {}).get("verdict") if isinstance(sc, dict) else None
    if verdict not in VALID_FRESHNESS_VERDICTS:
        return False, (f"structuredContent.freshness.verdict={verdict!r} is not one of "
                       f"{sorted(VALID_FRESHNESS_VERDICTS)}")
    return True, f"freshness verdict={verdict}"


def _short(msg: Any) -> str:
    try:
        return json.dumps(msg)[:160]
    except Exception:
        return repr(msg)[:160]


def _kill(proc: "subprocess.Popen[str]") -> None:
    try:
        proc.kill()
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.communicate(timeout=3)
    except Exception:
        pass


def _stdio_round_trip(
    argv: list[str],
    *,
    timeout: float = CONFIRM_TIMEOUT,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Start the server subprocess and perform a real `initialize` -> `tools/list`
    -> `tools/call` round-trip over stdio (newline-delimited JSON, the MCP stdio
    transport). Because the server discovers its sources from `--repo-root`, the
    probe cannot know a-priori which status tool exists, so it calls BOTH
    (get_dictionary_status + get_map_status) in one communicate() batch — whichever
    the server mounted answers live. Uses the communicate() pattern ks-server
    recommends (all requests written up front, stdin closed, clean EOF exit; no
    blocking-read hang). `ok` is True only when initialize returned a valid result,
    tools/list returned a non-empty tool set, AND at least one status tools/call
    returned a LIVE result (isError False + a valid freshness verdict). Never
    leaves the process running."""
    requests: list[dict[str, Any]] = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    call_ids: dict[int, str] = {}
    for offset, tool in enumerate(_STATUS_TOOLS):
        rid = 3 + offset
        call_ids[rid] = tool
        requests.append({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                         "params": {"name": tool, "arguments": {}}})
    payload = "".join(json.dumps(r) + "\n" for r in requests)

    try:
        proc = subprocess.Popen(
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            env=env,
        )
    except (OSError, ValueError) as exc:
        return {"ok": False, "detail": f"could not spawn the server ({exc})", "tool": None}

    try:
        out, _ = proc.communicate(input=payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(proc)
        return {"ok": False,
                "detail": f"round-trip timed out after {timeout}s (server did not respond)",
                "tool": None}
    except Exception as exc:
        _kill(proc)
        return {"ok": False, "detail": f"stdio exchange failed ({exc})", "tool": None}

    responses: dict[Any, dict] = {}
    for line in (out or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and "id" in obj:
            responses[obj["id"]] = obj

    if not _init_result_ok(responses.get(1)):
        return {"ok": False, "detail": f"initialize did not return a valid result ({_short(responses.get(1))})",
                "tool": None}
    listed = responses.get(2)
    tools = (listed.get("result") or {}).get("tools") if isinstance(listed, dict) else None
    if not tools:
        return {"ok": False, "detail": f"tools/list returned no tools ({_short(listed)})",
                "tool": None}
    for rid, tool in call_ids.items():
        live, why = _tool_call_live(responses.get(rid))
        if live:
            return {"ok": True,
                    "detail": (f"initialize + tools/list ({len(tools)} tool(s)) + "
                               f"tools/call('{tool}') round-trip OK; {why}"),
                    "tool": tool}
    return {"ok": False,
            "detail": (f"tools/list had {len(tools)} tool(s) but neither "
                       f"{' nor '.join(_STATUS_TOOLS)} returned a live result"),
            "tool": None}


# Injectable seam — tests monkeypatch this to prove confirm_serving's decision
# logic without a real subprocess (the confirm_gateway_serving prober discipline).
_default_round_trip: Callable[..., dict[str, Any]] = _stdio_round_trip


def confirm_serving(
    repo_root: Optional[str | Path] = None,
    *,
    entry_argv: Optional[list[str]] = None,
    round_trip: Optional[Callable[..., dict[str, Any]]] = None,
    timeout: Optional[float] = None,
) -> tuple[bool, str]:
    """Confirm the knowledge server is serving ON THIS MACHINE via a real stdio
    round-trip. Returns `(serving, detail)`; never raises. `serving` is True ONLY
    after a successful initialize + tools/list + status tools/call round-trip whose
    status result is live — an unstartable / unanswering / no-source server always
    returns False, and the detail then names why. The success detail is phrased
    "serving on this machine", NEVER "deployed". The probe argv is `_probe_argv`,
    which shares `_server_argv` with the printed registration (probe == ship)."""
    round_trip = round_trip if round_trip is not None else _default_round_trip
    timeout = CONFIRM_TIMEOUT if timeout is None else timeout
    if entry_argv is not None:
        argv = list(entry_argv)
    else:
        rr = repo_root if repo_root is not None else _resolve_repo_root(None, None)[0]
        argv = _probe_argv(rr)
    try:
        outcome = round_trip(argv, timeout=timeout)
    except Exception as exc:
        return False, (f"NOT serving — the knowledge server could not be started for "
                       f"a serving check ({exc})")
    if not isinstance(outcome, dict) or not outcome.get("ok"):
        detail = outcome.get("detail") if isinstance(outcome, dict) else "round-trip returned no verdict"
        return False, (f"NOT serving — {detail} (an unstartable or unanswering server "
                       f"never prints serving)")
    return True, f"serving on this machine — {outcome.get('detail', 'round-trip OK')}"


# --------------------------------------------------------------------------- #
# MCP registration (GENERATED + PRINTED — never auto-applied)
# --------------------------------------------------------------------------- #

def build_registration(
    repo_root: str | Path,
    server_name: str = DEFAULT_SERVER_NAME,
    argv: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build the MCP registration the user applies themselves — the `mcpServers`
    JSON snippet they paste into their MCP client config, plus a `claude mcp add`
    convenience form. The argv launches the server with the PORTABLE `--repo-root`
    flag (KS-1), derived from `_server_argv` (the SAME function the confirm probe
    uses). This function only BUILDS the registration; nothing here (or anywhere
    in this installer) writes it to the user's config."""
    argv = list(argv) if argv is not None else _server_argv(repo_root)
    command, args = argv[0], argv[1:]
    snippet = {"mcpServers": {server_name: {"command": command, "args": args}}}
    add_cmd = ("claude mcp add " + server_name + " -- "
               + " ".join(shlex.quote(a) for a in argv))
    return {
        "server_name": server_name,
        "snippet": snippet,
        "claude_mcp_add": add_cmd,
        "argv": argv,
        "repo_root": str(repo_root),
    }


# --------------------------------------------------------------------------- #
# step / report scaffolding (mirrors install_librarian.py)
# --------------------------------------------------------------------------- #

@dataclass
class StepResult:
    name: str
    status: str  # "ok" | "skipped" | "warn" | "fail"
    detail: str = ""


@dataclass
class Report:
    action: str = "install"
    base_dir: str = ""
    provisioned: bool = False
    check_only: bool = False
    repo_root: Optional[str] = None
    using_fixture: bool = False
    registration: Optional[dict[str, Any]] = None
    serving: Optional[bool] = None
    serving_detail: Optional[str] = None
    remediation: Optional[str] = None
    steps: list[StepResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.steps.append(StepResult(name=name, status=status, detail=detail))


# --------------------------------------------------------------------------- #
# provisioning
# --------------------------------------------------------------------------- #

def _config_payload(base: Path, server_name: str, repo_root: str,
                    using_fixture: bool) -> dict[str, Any]:
    return {
        "server_name": server_name,
        "repo_root": repo_root,
        "using_fixture": using_fixture,
        "server_entry": str(_SERVER_PATH),
        "llm": None,  # the knowledge server is deterministic — no LLM
        "provisioned_at": _utc_now_iso(),
        "paths": {"cache": str(base / CACHE_DIRNAME)},
    }


def _provision_state(base: Path, server_name: str, repo_root: str,
                     using_fixture: bool, report: Report) -> None:
    """Create the state layout under `base` (idempotent) and record the config."""
    base.mkdir(parents=True, exist_ok=True)
    (base / CACHE_DIRNAME).mkdir(parents=True, exist_ok=True)
    (base / CONFIG_NAME).write_text(
        json.dumps(_config_payload(base, server_name, repo_root, using_fixture),
                   indent=2, sort_keys=True),
        encoding="utf-8")
    report.add("provision", "ok", f"state layout created under {base}")


def _read_config(base: Path) -> dict[str, Any]:
    cfg = base / CONFIG_NAME
    if not cfg.exists():
        return {}
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_server_name(base: Path, fallback: str = DEFAULT_SERVER_NAME) -> str:
    name = _read_config(base).get("server_name")
    return name if isinstance(name, str) and name else fallback


# --------------------------------------------------------------------------- #
# subcommand handlers
# --------------------------------------------------------------------------- #

def _cmd_install(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="install", base_dir=str(base), check_only=bool(args.check_only))
    server_name = getattr(args, "server_name", None) or DEFAULT_SERVER_NAME
    repo_root, using_fixture = _resolve_repo_root(getattr(args, "repo_root", None), base)
    report.repo_root = repo_root
    report.using_fixture = using_fixture

    if using_fixture:
        report.add("repo-root", "warn",
                   "no target repo-root resolved — defaulting to the bundled fixture "
                   f"({_FIXTURE_DIR}) as a labelled DEMO/probe default; pass --repo-root "
                   "<repo> to serve your repo's sidecars")
    else:
        report.add("repo-root", "ok", f"target repo-root: {repo_root}")

    if args.check_only:
        report.add("check-only", "skipped", "reporting intent only; no state provisioned")
        report.registration = build_registration(repo_root, server_name)
        report.add("registration", "ok",
                   f"would register MCP server '{server_name}' (PRINTED, never auto-applied)")
        return report

    _provision_state(base, server_name, repo_root, using_fixture, report)
    report.provisioned = True
    report.registration = build_registration(repo_root, server_name)
    report.add("registration", "ok",
               f"MCP registration generated for '{server_name}' — PRINT it and apply it "
               f"yourself (never auto-edited into your MCP config)")

    if getattr(args, "confirm", False):
        ok, detail = confirm_serving(repo_root, timeout=getattr(args, "timeout", None))
        report.serving = ok
        report.serving_detail = detail
        # a failed serving check is informational — it NEVER gates the install
        # (provision + registration already succeeded); mark it warn, not fail.
        report.add("confirm-serving", "ok" if ok else "warn", detail)
    return report


def _cmd_status(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="status", base_dir=str(base))
    report.provisioned = (base / CONFIG_NAME).exists()
    server_name = _read_server_name(base)
    repo_root, using_fixture = _resolve_repo_root(getattr(args, "repo_root", None), base)
    report.repo_root = repo_root
    report.using_fixture = using_fixture
    report.registration = build_registration(repo_root, server_name)
    cache_state = "present" if (base / CACHE_DIRNAME).is_dir() else "absent"
    state = "provisioned" if report.provisioned else "not provisioned"
    report.add("status", "ok",
               f"{state}; MCP server '{server_name}'; repo-root={repo_root}"
               f"{' (bundled fixture)' if using_fixture else ''}; cache={cache_state}")
    if not report.provisioned:
        report.remediation = (
            f"python3 \"${{CLAUDE_PLUGIN_ROOT}}/scripts/setup/install_knowledge_server.py\" "
            f"install --base-dir {base} --repo-root <target-repo>")
    return report


def _cmd_print_registration(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="print-registration", base_dir=str(base))
    server_name = getattr(args, "server_name", None) or _read_server_name(base)
    report.provisioned = (base / CONFIG_NAME).exists()
    repo_root, using_fixture = _resolve_repo_root(getattr(args, "repo_root", None), base)
    report.repo_root = repo_root
    report.using_fixture = using_fixture
    report.registration = build_registration(repo_root, server_name)
    report.add("print-registration", "ok",
               f"MCP registration for '{server_name}' (repo-root={repo_root}) — apply it yourself")
    return report


def _cmd_confirm_serving(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="confirm-serving", base_dir=str(base))
    report.provisioned = (base / CONFIG_NAME).exists()
    if not report.provisioned:
        report.serving = False
        report.serving_detail = f"NOT serving — not provisioned at {base}; run install first"
        report.add("confirm-serving", "skipped", report.serving_detail)
        return report
    repo_root, using_fixture = _resolve_repo_root(getattr(args, "repo_root", None), base)
    report.repo_root = repo_root
    report.using_fixture = using_fixture
    ok, detail = confirm_serving(repo_root, timeout=getattr(args, "timeout", None))
    report.serving = ok
    report.serving_detail = detail
    report.add("confirm-serving", "ok" if ok else "fail", detail)
    return report


def _cmd_uninstall(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="uninstall", base_dir=str(base))
    cfg = base / CONFIG_NAME
    if cfg.exists():
        try:
            cfg.unlink()
            report.add("uninstall", "ok",
                       "provisioning removed (config.json). If you registered the MCP "
                       "server with your client, remove it there yourself.")
        except OSError as exc:
            report.add("uninstall", "fail", f"could not remove {cfg}: {exc}")
    else:
        report.add("uninstall", "skipped", "no provisioning present (no-op)")
    report.provisioned = False

    if getattr(args, "purge", False):
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
            report.add("purge", "ok", f"removed state dir {base}")
        else:
            report.add("purge", "skipped", "state dir already absent (no-op)")
    return report


_HANDLERS: dict[str, Callable[[argparse.Namespace, Path], Report]] = {
    "install": _cmd_install,
    "status": _cmd_status,
    "print-registration": _cmd_print_registration,
    "confirm-serving": _cmd_confirm_serving,
    "uninstall": _cmd_uninstall,
}


# --------------------------------------------------------------------------- #
# argparse + emit
# --------------------------------------------------------------------------- #

def _add_shared_flags(parser: argparse.ArgumentParser) -> None:
    """Flags accepted in EITHER position (before OR after the subcommand): a
    parent-parser shape so `install --base-dir X` and `--base-dir X install` both
    parse (the install_librarian.py convention)."""
    parser.add_argument("--base-dir", default=None,
                        help=f"state dir (default ${ENV_HOME} or ~/.architect-team/knowledge)")
    parser.add_argument("--repo-root", default=None,
                        help="the TARGET repo whose conventional sidecars get served "
                             "(default: the git repo root of the install context)")
    parser.add_argument("--server-name", default=None,
                        help=f"the MCP server name in the registration (default {DEFAULT_SERVER_NAME})")
    parser.add_argument("--confirm", action="store_true",
                        help="(install) run the live serving round-trip after provisioning")
    parser.add_argument("--check-only", action="store_true",
                        help="report intent only; do not provision")
    parser.add_argument("--json", action="store_true",
                        help="emit a machine-readable JSON status report")
    parser.add_argument("--purge", action="store_true",
                        help="(uninstall) also remove the state dir")
    parser.add_argument("--timeout", type=float, default=None,
                        help=f"the serving round-trip timeout in seconds (default {CONFIRM_TIMEOUT})")


def _build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    _add_shared_flags(shared)

    parser = argparse.ArgumentParser(
        prog="install_knowledge_server.py", parents=[shared],
        description="Install / manage the CT6 knowledge server (MCP stdio service).")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("install", parents=[shared], add_help=False)
    sub.add_parser("status", parents=[shared], add_help=False)
    sub.add_parser("print-registration", parents=[shared], add_help=False)
    sub.add_parser("confirm-serving", parents=[shared], add_help=False)
    sub.add_parser("uninstall", parents=[shared], add_help=False)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    command = args.command or "install"  # default subcommand

    base = resolve_base_dir(args.base_dir)
    handler = _HANDLERS[command]
    try:
        report = handler(args, base)
    except Exception as exc:  # surface real failures with an actionable message
        msg = f"{command} failed: {exc!r}"
        if getattr(args, "json", False):
            print(json.dumps({"action": command, "error": msg}, indent=2))
        else:
            print(f"\n[x] {msg}\n")
        return 1

    exit_code = 0
    # the standalone serving diagnostic exits non-zero when NOT serving.
    if command == "confirm-serving" and report.serving is not True:
        exit_code = 1
    return _emit(report, getattr(args, "json", False), exit_code)


def _emit(report: Report, as_json: bool, exit_code: int) -> int:
    if as_json:
        payload = {
            "action": report.action,
            "base_dir": report.base_dir,
            "provisioned": report.provisioned,
            "check_only": report.check_only,
            "repo_root": report.repo_root,
            "using_fixture": report.using_fixture,
            "registration": report.registration,
            "serving": report.serving,
            "serving_detail": report.serving_detail,
            "remediation": report.remediation,
            "steps": [{"name": s.name, "status": s.status, "detail": s.detail}
                      for s in report.steps],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return exit_code

    print()
    print("=" * 64)
    print(f"  CT6 knowledge server {report.action} -- summary")
    print("=" * 64)
    for step in report.steps:
        marker = {"ok": "[+]", "skipped": "[-]", "warn": "[!]", "fail": "[x]"}.get(
            step.status, "[?]")
        print(f"  {marker} {step.name:<18} {step.detail}")
    print("=" * 64)
    print(f"  State dir:   {report.base_dir}")
    print(f"  Provisioned: {report.provisioned}")
    if report.repo_root is not None:
        print(f"  Repo-root:   {report.repo_root}"
              f"{'  (bundled fixture — demo/probe default)' if report.using_fixture else ''}")
    if report.serving is not None:
        print(f"  Serving:     {report.serving_detail}")
    if report.registration:
        print("  Register the knowledge server with your MCP client yourself")
        print("  (this installer NEVER edits your MCP config):")
        print("    MCP config snippet -- paste into your MCP client config:")
        for line in json.dumps(report.registration["snippet"], indent=2).splitlines():
            print(f"      {line}")
        print("    Or, with the Claude Code CLI:")
        print(f"      {report.registration['claude_mcp_add']}")
        if report.using_fixture:
            print("    NOTE: serving the bundled fixture (demo/probe default). Re-run")
            print("      install with --repo-root <your-repo> to serve your repo's sidecars.")
    if report.remediation:
        print("  To provision, run:")
        print(f"    {report.remediation}")
    print("=" * 64)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
