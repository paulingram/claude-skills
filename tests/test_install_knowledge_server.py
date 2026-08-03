"""Tests for the knowledge-server installer + command (KS-8, KS-9).

Covers:
  - `scripts/setup/install_knowledge_server.py` — the stdlib-only installer CLI
    (install / status / print-registration / confirm-serving / uninstall +
    --check-only / --json / --purge / --confirm), on the `install_librarian.py`
    template. Provisions `~/.architect-team/knowledge/`, resolves the TARGET repo
    root, and GENERATES + PRINTS a PORTABLE MCP registration snippet whose argv
    launches the KS-1 server with `--repo-root <repo>` (the server auto-discovers
    the conventional sidecars docs/data-dictionary.json + lineage-graph.json +
    docs/*_MAP.md under it — no brittle hardcoded absolute paths), never
    auto-editing the user's MCP config, and live-confirms serving via a real
    initialize + tools/list + tools/call round-trip over stdio (KS-8).
  - `commands/knowledge-install.md` — the polyglot slash-command entry + the
    canonical-command registration (23 -> 24) (KS-9).

SINGLE-SOURCE ARGV (probe == ship): build_registration AND confirm_serving derive
the launch argv from ONE function (_server_argv), so a green confirm can never be
a false-green against a different argv than the printed registration.

The confirm-serving LOGIC is proven three ways:
  (1) an injected `round_trip` seam (succeeds -> serving; fails/unstartable ->
      NOT serving),
  (2) the REAL `_stdio_round_trip` driven as a genuine subprocess against a tiny
      in-test fake stdio server that mirrors the KS-1 contract (its argparse
      rejects unknown args exactly as the real server does — a future argv drift
      goes RED),
  (3) THE LOAD-BEARING co-exercise: confirm_serving() run through the REAL
      _server_argv() against ks-server's ACTUAL services/knowledge_server/server.py
      (a subprocess, NOT the fake, NOT the entry_argv= bypass) over a repo with
      real sidecars -> serving, and over a repo with NO sidecars -> honest
      NOT-serving. This is the 'entry point exercised by a test' that stops the
      launch-dead-server class recurring.

Everything runs OFFLINE + stdlib-only. Module-load style mirrors
`tests/test_install_librarian.py` (services/ has no `__init__.py`).
"""
from __future__ import annotations

import importlib.util
import io
import json
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "knowledge_server"
_REAL_SERVER = REPO_ROOT / "services" / "knowledge_server" / "server.py"
_HAVE_REAL = _REAL_SERVER.exists() and (_FIXTURE_DIR / "data-dictionary.json").exists()


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# The system under test.
inst = _load("install_knowledge_server", "scripts/setup/install_knowledge_server.py")


def _capture(monkeypatch, argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    try:
        rc = inst.main(argv)
    finally:
        monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    return rc, out.getvalue()


def _make_repo_fixture(tmp_path: Path) -> Path:
    """Build a repo-shaped fixture with the CT6 conventional sidecar layout so
    `--repo-root <repo>` auto-discovery mounts BOTH sources — copied from the flat
    tests/fixtures/knowledge_server/ files into docs/ + root."""
    repo = tmp_path / "repo"
    (repo / "docs" / "data-annotations").mkdir(parents=True)
    shutil.copy(_FIXTURE_DIR / "data-dictionary.json", repo / "docs" / "data-dictionary.json")
    shutil.copy(_FIXTURE_DIR / "lineage-graph.json", repo / "lineage-graph.json")
    shutil.copy(_FIXTURE_DIR / "ENDPOINT_TRACE_MAP.md", repo / "docs" / "ENDPOINT_TRACE_MAP.md")
    shutil.copy(_FIXTURE_DIR / "data-annotations" / "analyst.json",
                repo / "docs" / "data-annotations" / "analyst.json")
    return repo


# A tiny newline-delimited JSON-RPC 2.0 MCP stdio server MIRRORING the KS-1
# contract. Its argparse ACCEPTS exactly the real server's flags (--repo-root /
# --dictionary / --graph / --map / --annotations / --max-messages) and REJECTS
# unknown args just as the real server does — so a stale --base-dir argv makes it
# exit nonzero, and argv drift is caught. Reads stdin lines until EOF (communicate
# closes stdin), responds one JSON object per line. Mounts both *_status tools so
# the probe (which tries get_dictionary_status AND get_map_status) resolves.
#   --mode normal        -> live tools/call results
#   --mode tool-error    -> tools/call result.isError=true (NOT live)
#   --mode bad-freshness -> tools/call result has no freshness verdict (NOT live)
#   --mode no-tools      -> tools/list returns [] (NOT serving)
#   --mode crash         -> exit(1) immediately (unstartable -> NOT serving)
_FAKE_SERVER = textwrap.dedent(
    """
    import sys, json, argparse
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root"); p.add_argument("--dictionary"); p.add_argument("--graph")
    p.add_argument("--annotations"); p.add_argument("--map", action="append", default=[])
    p.add_argument("--max-messages", type=int, default=None)
    p.add_argument("--mode", default="normal")
    a = p.parse_args()
    if a.mode == "crash":
        sys.exit(1)
    tools = [] if a.mode == "no-tools" else ["get_dictionary_status", "get_map_status"]

    def send(o):
        sys.stdout.write(json.dumps(o) + "\\n"); sys.stdout.flush()

    n = 0
    for line in sys.stdin:
        if a.max_messages is not None and n >= a.max_messages:
            break
        line = line.strip()
        if not line:
            continue
        n += 1
        try:
            req = json.loads(line)
        except Exception:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse"}}); continue
        mid = req.get("id"); method = req.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "fake-knowledge-server", "version": "0"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                {"name": t, "description": "status", "inputSchema": {"type": "object"}} for t in tools]}})
        elif method == "tools/call":
            name = (req.get("params") or {}).get("name")
            if name not in tools:
                send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown tool: " + str(name)}})
            elif a.mode == "tool-error":
                send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": "boom"}], "isError": True}})
            elif a.mode == "bad-freshness":
                send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": "{}"}], "structuredContent": {"rows": []}, "isError": False}})
            else:
                payload = {"source": name, "freshness": {"verdict": "unknowable", "basis": ["fake"]}}
                send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(payload)}], "structuredContent": payload, "isError": False}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}})
    """
)


def _write_fake_server(tmp_path: Path) -> Path:
    p = tmp_path / "fake_mcp_server.py"
    p.write_text(_FAKE_SERVER, encoding="utf-8")
    return p


def _fake_argv(fake: Path, mode: str = "normal") -> list[str]:
    return [sys.executable, str(fake), "--repo-root", "dummy-repo",
            "--mode", mode, "--max-messages", "4"]


# --------------------------------------------------------------------------- #
# KS-9 — the command exists + is registered (23 -> 24 in lockstep)
# --------------------------------------------------------------------------- #

def test_command_file_exists_and_is_polyglot() -> None:
    cmd_path = REPO_ROOT / "commands" / "knowledge-install.md"
    assert cmd_path.exists(), "commands/knowledge-install.md must exist (KS-9)"
    cmd = cmd_path.read_text(encoding="utf-8")
    assert "install_knowledge_server.py" in cmd
    assert "python3 " in cmd and "|| python " in cmd
    assert "After the script runs, summarize" in cmd
    assert "Safety rules" in cmd
    assert cmd.lstrip().startswith("---")
    assert "description:" in cmd
    assert cmd.count("```!") == 1


def test_command_doc_uses_repo_root_not_base_dir_contract() -> None:
    """Doc currency — the command doc must describe the --repo-root server
    contract, not a stale --base-dir/--dictionary server contract."""
    cmd = (REPO_ROOT / "commands" / "knowledge-install.md").read_text(encoding="utf-8")
    assert "--repo-root" in cmd
    # the server is launched with --repo-root; the doc must not claim the server
    # takes --base-dir (that flag is the installer's STATE dir, not a server flag).
    assert "server.py --base-dir" not in cmd
    assert "--dictionary <data-dictionary.json>" not in cmd


def test_command_frontmatter_has_no_colon_space_in_description() -> None:
    cmd = (REPO_ROOT / "commands" / "knowledge-install.md").read_text(encoding="utf-8")
    assert cmd.lstrip().startswith("---")
    fm = cmd.lstrip()[3:].split("---", 1)[0]
    desc_lines = [ln for ln in fm.splitlines() if ln.startswith("description:")]
    assert desc_lines
    value = desc_lines[0][len("description:"):].strip()
    if not (value.startswith("'") or value.startswith('"')):
        assert ": " not in value
        assert " #" not in value


def test_command_registered_in_audit_module() -> None:
    audit = _load("skill_invocation_audit_ks", "hooks/skill_invocation_audit.py")
    assert "knowledge-install" in audit.CANONICAL_COMMANDS
    assert audit.COMMAND_TO_SKILLS["knowledge-install"] == ("knowledge-install",)


# --------------------------------------------------------------------------- #
# KS-8 — installer CLI dispatch + stdlib-only import
# --------------------------------------------------------------------------- #

def test_subcommands_dispatch(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    common = ["--base-dir", str(base)]
    assert inst.main(["install", *common, "--json"]) == 0
    assert inst.main(["status", *common, "--json"]) == 0
    assert inst.main(["print-registration", *common, "--json"]) == 0
    monkeypatch.setattr(inst, "_default_round_trip",
                        lambda argv, timeout=None: {"ok": True, "detail": "round-trip OK", "tool": "get_dictionary_status"})
    assert inst.main(["confirm-serving", *common, "--json"]) == 0
    assert inst.main(["uninstall", *common]) == 0


def test_stdlib_only_import() -> None:
    import builtins

    real_import = builtins.__import__
    blocked = {"anthropic", "litellm", "yaml", "requests"}

    def guard(name, *a, **k):
        root = name.split(".")[0]
        if root in blocked:
            raise ImportError(f"{root} is blocked for the stdlib-only import test")
        return real_import(name, *a, **k)

    builtins.__import__ = guard
    try:
        _load("install_knowledge_server_stdlib", "scripts/setup/install_knowledge_server.py")
    finally:
        builtins.__import__ = real_import


# --------------------------------------------------------------------------- #
# KS-8 — provisioning + base-dir resolution
# --------------------------------------------------------------------------- #

def test_install_provisions_state(tmp_path: Path) -> None:
    base = tmp_path / "kn"
    assert inst.main(["install", "--base-dir", str(base), "--json"]) == 0
    assert (base / "config.json").exists()
    assert (base / "cache").is_dir()


def test_base_dir_env_override(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "env-home"
    monkeypatch.setenv("CT6_KNOWLEDGE_HOME", str(base))
    assert inst.main(["install", "--json"]) == 0
    assert (base / "config.json").exists()


def test_resolve_base_dir_no_hardcoded_home(monkeypatch) -> None:
    monkeypatch.setenv("CT6_KNOWLEDGE_HOME", "/tmp/ct6-kn-test-home")
    assert inst.resolve_base_dir(None) == Path("/tmp/ct6-kn-test-home")
    assert inst.resolve_base_dir("/explicit/path") == Path("/explicit/path")


def test_check_only_reports_without_provisioning(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    rc, text = _capture(monkeypatch, ["install", "--check-only", "--base-dir", str(base), "--json"])
    payload = json.loads(text)
    assert rc == 0
    assert payload["check_only"] is True
    assert not (base / "config.json").exists()


# --------------------------------------------------------------------------- #
# KS-8 — the PORTABLE --repo-root registration (single-source argv)
# --------------------------------------------------------------------------- #

def test_registration_argv_is_repo_root_not_source_flags(tmp_path: Path, monkeypatch) -> None:
    """The registration launches the KS-1 server with the PORTABLE `--repo-root
    <repo>` (the server auto-discovers sidecars) — NOT hardcoded --dictionary/
    --graph absolute paths, and NOT the installer's own --base-dir state flag."""
    base = tmp_path / "kn"
    repo = _make_repo_fixture(tmp_path)
    rc, text = _capture(monkeypatch, [
        "install", "--base-dir", str(base), "--repo-root", str(repo), "--json"])
    payload = json.loads(text)
    assert rc == 0
    argv = payload["registration"]["argv"]
    assert "--repo-root" in argv and str(repo) in argv
    assert "--base-dir" not in argv         # installer STATE, not a server flag
    assert "--dictionary" not in argv       # portability: no hardcoded sidecar paths
    assert "--graph" not in argv
    assert any(a.endswith("server.py") for a in argv)


def test_probe_and_registration_share_argv() -> None:
    """PROBE == SHIP — the confirm probe launches EXACTLY the registration argv
    (plus a test-only --max-messages bound). One function sources both, so a green
    confirm can never be a false-green against a divergent argv."""
    rr = str(Path("/some/target/repo"))
    reg_argv = inst.build_registration(rr, "ct6-knowledge")["argv"]
    probe_argv = inst._probe_argv(rr)
    assert probe_argv[:len(reg_argv)] == reg_argv
    assert "--repo-root" in reg_argv and rr in reg_argv
    # both derive from the ONE argv function
    assert inst._server_argv(rr) == reg_argv


def test_repo_root_recorded_in_config(tmp_path: Path) -> None:
    base = tmp_path / "kn"
    repo = _make_repo_fixture(tmp_path)
    inst.main(["install", "--base-dir", str(base), "--repo-root", str(repo), "--json"])
    cfg = json.loads((base / "config.json").read_text(encoding="utf-8"))
    assert cfg["repo_root"] == str(repo)


def test_git_repo_root_of_cwd_resolves() -> None:
    """_git_repo_root returns a real toplevel from inside a git repo (this repo)."""
    top = inst._git_repo_root(REPO_ROOT)
    assert top is not None
    assert Path(top) == REPO_ROOT or REPO_ROOT.samefile(top)


def test_resolve_repo_root_precedence(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    # explicit flag wins
    rr, fx = inst._resolve_repo_root("/explicit/repo", base)
    assert rr == "/explicit/repo" and fx is False
    # no explicit + no config + no git root -> bundled fixture (labeled)
    monkeypatch.setattr(inst, "_git_repo_root", lambda *a, **k: None)
    rr2, fx2 = inst._resolve_repo_root(None, base)
    assert fx2 is True and Path(rr2) == _FIXTURE_DIR


def test_fixture_fallback_when_no_repo_root(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    monkeypatch.setattr(inst, "_git_repo_root", lambda *a, **k: None)
    rc, text = _capture(monkeypatch, ["install", "--base-dir", str(base), "--json"])
    payload = json.loads(text)
    assert rc == 0
    assert payload["using_fixture"] is True
    argv = payload["registration"]["argv"]
    assert "--repo-root" in argv and str(_FIXTURE_DIR) in argv


def test_install_prints_mcp_registration(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    rc, text = _capture(monkeypatch, ["install", "--base-dir", str(base)])
    assert rc == 0
    assert "mcpServers" in text
    assert "ct6-knowledge" in text
    assert "claude mcp add" in text
    assert "--repo-root" in text


def test_registration_in_json_payload(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    rc, text = _capture(monkeypatch, ["install", "--base-dir", str(base), "--json"])
    payload = json.loads(text)
    assert rc == 0
    reg = payload["registration"]
    assert reg["server_name"] == "ct6-knowledge"
    entry = reg["snippet"]["mcpServers"]["ct6-knowledge"]
    assert entry["command"]
    assert isinstance(entry["args"], list) and entry["args"]


def test_never_auto_edits_user_mcp_config(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    user_cfg = tmp_path / "claude_desktop_config.json"
    user_cfg.write_text('{"mcpServers": {"other": {}}}', encoding="utf-8")
    before = user_cfg.read_text(encoding="utf-8")
    rc, text = _capture(monkeypatch, ["install", "--base-dir", str(base)])
    assert rc == 0
    assert user_cfg.read_text(encoding="utf-8") == before  # untouched — no auto-edit
    assert "mcpServers" in text  # printed, not written
    created_outside = [p.name for p in tmp_path.iterdir() if p != base and p != user_cfg]
    assert created_outside == [], f"installer wrote outside base-dir: {created_outside}"


def test_custom_server_name(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    rc, text = _capture(
        monkeypatch,
        ["install", "--base-dir", str(base), "--server-name", "my-knowledge", "--json"])
    payload = json.loads(text)
    assert rc == 0
    assert payload["registration"]["server_name"] == "my-knowledge"
    assert "my-knowledge" in payload["registration"]["snippet"]["mcpServers"]


# --------------------------------------------------------------------------- #
# KS-8 — status / uninstall --purge parity
# --------------------------------------------------------------------------- #

def test_status_report(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    repo = _make_repo_fixture(tmp_path)
    inst.main(["install", "--base-dir", str(base), "--repo-root", str(repo), "--json"])
    rc, text = _capture(monkeypatch, ["status", "--base-dir", str(base), "--json"])
    payload = json.loads(text)
    assert rc == 0
    assert payload["provisioned"] is True
    assert payload["registration"]["server_name"] == "ct6-knowledge"
    assert payload["repo_root"] == str(repo)


def test_status_before_install_reports_not_provisioned(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    rc, text = _capture(monkeypatch, ["status", "--base-dir", str(base), "--json"])
    payload = json.loads(text)
    assert rc == 0
    assert payload["provisioned"] is False


def test_uninstall_purge(tmp_path: Path) -> None:
    base = tmp_path / "kn"
    common = ["--base-dir", str(base)]
    inst.main(["install", *common, "--json"])
    assert (base / "config.json").exists()
    assert inst.main(["uninstall", *common]) == 0
    assert not (base / "config.json").exists()
    assert base.exists()
    assert inst.main(["uninstall", "--purge", *common]) == 0
    assert not base.exists()
    assert inst.main(["uninstall", "--purge", *common]) == 0


# --------------------------------------------------------------------------- #
# KS-8 — honest boundary: no "deployed" / "in production" wording
# --------------------------------------------------------------------------- #

def test_honest_boundary_no_deployed_wording(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    rc, text = _capture(monkeypatch, ["install", "--base-dir", str(base)])
    assert rc == 0
    low = text.lower()
    assert "deployed" not in low
    assert "in production" not in low


# --------------------------------------------------------------------------- #
# KS-8 — the live-result helpers (the isError + freshness gate)
# --------------------------------------------------------------------------- #

def test_tool_call_live_accepts_valid_freshness() -> None:
    for verdict in ("current", "stale", "unknowable"):
        ok, _ = inst._tool_call_live({"result": {
            "isError": False, "structuredContent": {"freshness": {"verdict": verdict}}}})
        assert ok is True


def test_tool_call_live_rejects_iserror() -> None:
    ok, why = inst._tool_call_live({"result": {"isError": True, "content": []}})
    assert ok is False and "isError" in why


def test_tool_call_live_rejects_missing_freshness() -> None:
    ok, _ = inst._tool_call_live({"result": {"isError": False, "structuredContent": {"rows": []}}})
    assert ok is False


def test_tool_call_live_rejects_jsonrpc_error() -> None:
    ok, why = inst._tool_call_live({"error": {"code": -32602, "message": "unknown tool"}})
    assert ok is False and "error" in why.lower()


# --------------------------------------------------------------------------- #
# KS-8 — confirm_serving LOGIC via the injected round_trip seam
# --------------------------------------------------------------------------- #

def test_confirm_serving_true_on_successful_round_trip() -> None:
    ok, detail = inst.confirm_serving(
        "/some/repo",
        round_trip=lambda argv, timeout=None: {
            "ok": True, "detail": "round-trip OK via get_dictionary_status", "tool": "get_dictionary_status"})
    assert ok is True
    assert "serving on this machine" in detail
    assert "deployed" not in detail.lower()


def test_confirm_serving_false_on_failed_round_trip() -> None:
    ok, detail = inst.confirm_serving(
        "/some/repo",
        round_trip=lambda argv, timeout=None: {
            "ok": False, "detail": "neither status tool returned a live result", "tool": None})
    assert ok is False
    assert "serving on this machine" not in detail
    assert "NOT serving" in detail


def test_confirm_serving_false_when_unstartable() -> None:
    def boom(argv, timeout=None):
        raise RuntimeError("cannot spawn server executable")

    ok, detail = inst.confirm_serving("/some/repo", round_trip=boom)
    assert ok is False
    assert "serving on this machine" not in detail


def test_confirm_serving_subcommand_serving(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    inst.main(["install", "--base-dir", str(base), "--json"])
    monkeypatch.setattr(inst, "_default_round_trip",
                        lambda argv, timeout=None: {"ok": True, "detail": "round-trip OK", "tool": "get_map_status"})
    rc, text = _capture(monkeypatch, ["confirm-serving", "--base-dir", str(base)])
    assert rc == 0
    assert "serving on this machine" in text


def test_confirm_serving_subcommand_not_serving_exits_1(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    inst.main(["install", "--base-dir", str(base), "--json"])
    monkeypatch.setattr(inst, "_default_round_trip",
                        lambda argv, timeout=None: {"ok": False, "detail": "round-trip failed", "tool": None})
    rc, text = _capture(monkeypatch, ["confirm-serving", "--base-dir", str(base), "--json"])
    assert rc == 1
    payload = json.loads(text)
    assert payload["serving"] is False


def test_install_confirm_does_not_gate_provisioning(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "kn"
    monkeypatch.setattr(inst, "_default_round_trip",
                        lambda argv, timeout=None: {"ok": False, "detail": "server not reachable", "tool": None})
    rc, text = _capture(monkeypatch, ["install", "--confirm", "--base-dir", str(base)])
    assert rc == 0
    assert (base / "config.json").exists()
    assert "NOT serving" in text


# --------------------------------------------------------------------------- #
# KS-8 — the REAL _stdio_round_trip driven against a fake KS-1 stdio server
# --------------------------------------------------------------------------- #

def test_real_stdio_round_trip_serving(tmp_path: Path) -> None:
    fake = _write_fake_server(tmp_path)
    outcome = inst._stdio_round_trip(_fake_argv(fake, "normal"), timeout=15.0)
    assert outcome["ok"] is True
    ok, detail = inst.confirm_serving(entry_argv=_fake_argv(fake, "normal"), timeout=15.0)
    assert ok is True
    assert "serving on this machine" in detail


def test_real_stdio_round_trip_tool_error_is_not_serving(tmp_path: Path) -> None:
    fake = _write_fake_server(tmp_path)
    outcome = inst._stdio_round_trip(_fake_argv(fake, "tool-error"), timeout=15.0)
    assert outcome["ok"] is False


def test_real_stdio_round_trip_bad_freshness_is_not_serving(tmp_path: Path) -> None:
    fake = _write_fake_server(tmp_path)
    outcome = inst._stdio_round_trip(_fake_argv(fake, "bad-freshness"), timeout=15.0)
    assert outcome["ok"] is False


def test_real_stdio_round_trip_no_tools_is_not_serving(tmp_path: Path) -> None:
    fake = _write_fake_server(tmp_path)
    outcome = inst._stdio_round_trip(_fake_argv(fake, "no-tools"), timeout=15.0)
    assert outcome["ok"] is False


def test_real_stdio_round_trip_crash_is_not_serving(tmp_path: Path) -> None:
    fake = _write_fake_server(tmp_path)
    ok, detail = inst.confirm_serving(entry_argv=_fake_argv(fake, "crash"), timeout=15.0)
    assert ok is False
    assert "serving on this machine" not in detail


def test_fake_server_rejects_unknown_args(tmp_path: Path) -> None:
    """Test fidelity — the fake's argparse rejects a stale --base-dir just as the
    real server does, so an argv drift back to --base-dir goes RED."""
    fake = _write_fake_server(tmp_path)
    argv = [sys.executable, str(fake), "--base-dir", "x", "--max-messages", "4"]
    outcome = inst._stdio_round_trip(argv, timeout=15.0)
    assert outcome["ok"] is False


def test_real_stdio_round_trip_unspawnable_is_not_serving(tmp_path: Path) -> None:
    argv = [sys.executable, str(tmp_path / "does-not-exist.py")]
    ok, detail = inst.confirm_serving(entry_argv=argv, timeout=15.0)
    assert ok is False
    assert "serving on this machine" not in detail


# --------------------------------------------------------------------------- #
# KS-8 — THE LOAD-BEARING co-exercise: confirm_serving() through the REAL
#         _server_argv() against ks-server's ACTUAL server (NOT the fake, NOT the
#         entry_argv bypass). This is the 'entry point exercised by a test' that
#         stops the launch-dead-server class recurring.
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not _HAVE_REAL, reason="the real knowledge server / fixture is absent")
def test_real_server_repo_root_serves(tmp_path: Path) -> None:
    """A repo with the conventional sidecars -> confirm_serving(repo_root) drives
    the REAL server via the REAL _server_argv (--repo-root auto-discovery) and
    gets 'serving on this machine'."""
    repo = _make_repo_fixture(tmp_path)
    ok, detail = inst.confirm_serving(str(repo), timeout=30.0)
    assert ok is True, detail
    assert "serving on this machine" in detail
    assert "freshness verdict" in detail


@pytest.mark.skipif(not _HAVE_REAL, reason="the real knowledge server / fixture is absent")
def test_real_server_no_sidecars_is_not_serving(tmp_path: Path) -> None:
    """A repo with NO conventional sidecars -> the real server exits 'no source'
    -> honest NOT-serving (the failure the guard must be able to report)."""
    empty = tmp_path / "empty-repo"
    empty.mkdir()
    ok, detail = inst.confirm_serving(str(empty), timeout=30.0)
    assert ok is False
    assert "serving on this machine" not in detail


@pytest.mark.skipif(not _HAVE_REAL, reason="the real knowledge server / fixture is absent")
def test_real_server_via_full_default_path(tmp_path: Path, monkeypatch) -> None:
    """Exercise the FULL default path end-to-end against the real server: resolve
    repo-root (here monkeypatched to a real-sidecar repo) -> _probe_argv ->
    _stdio_round_trip -> REAL server -> serving. No repo_root arg, no entry_argv
    bypass — the same wiring the confirm-serving subcommand uses."""
    repo = _make_repo_fixture(tmp_path)
    monkeypatch.setattr(inst, "_git_repo_root", lambda *a, **k: str(repo))
    ok, detail = inst.confirm_serving(timeout=30.0)
    assert ok is True, detail
    assert "serving on this machine" in detail
