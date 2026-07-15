#!/usr/bin/env python3
"""install_gateway.py — the full-lifecycle installer for the CT6 external-LLM gateway.

Run from `/architect-team:architect-team-setup --external-llm` (or standalone).
Stdlib-only. Mirrors the `install_librarian.py` pattern: a step-summary printer,
`--json`, `--check-only`, and the same "never auto-register / never auto-enable
without a key" safety posture.

WHAT THIS INSTALLS: a local LiteLLM proxy (MIT-licensed, `pip install
"litellm[proxy]"`) configured so the v3.35.0 Codex 5.6 role split has a real
backend — the `codex-5.6-sol` model id routes to OpenAI, while Anthropic models
either pass through the same gateway (api-key mode) or keep Claude Code's native
sign-in auth (subscription mode).

AUTH MODES (resolved, never probed against a live API):
  * ``api-key``       — an `ANTHROPIC_API_KEY` resolves (process env, gateway env
                        file, or `--anthropic-key`). The gateway fronts BOTH
                        providers: a catch-all Anthropic route + the codex →
                        OpenAI route. `--activate` may then point Claude Code at
                        the gateway (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`
                        in `~/.claude/settings.json`, consent-gated) and apply the
                        codex role split via `set_default_model.py`.
  * ``subscription``  — NO Anthropic key anywhere. Fable (and every Anthropic
                        model) keeps Claude Code's native subscription sign-in —
                        `ANTHROPIC_BASE_URL` is deliberately NEVER written, since
                        rerouting subscription OAuth traffic through a local proxy
                        is not supported by the harness. The gateway still runs,
                        OpenAI-only, for the service tier and direct callers. The
                        codex role split stays OFF (the harness cannot split-route
                        only codex traffic); the printed remediation is to add an
                        `ANTHROPIC_API_KEY` and re-run with `--activate`.

SECRETS: keys live ONLY in `<state>/gateway.env` (chmod 0600 best-effort) and are
masked to their last 4 chars in every report. The generated `config.yaml` carries
`os.environ/...` references, never raw keys. Nothing under the repo is touched.

Subcommands:
  install (default)  Provision state + config + env file + launcher + the per-OS
                     boot descriptor (printed register hint, NEVER loaded). Installs
                     `litellm[proxy]` through setup.py's PEP-668-aware ladder.
                     Enabled ONLY when an OpenAI key resolves; otherwise install-
                     but-disabled with an explicit remediation.
  status             Report auth mode / keys (masked) / litellm presence / file
                     layout / activation + the agents' model policy state.
  uninstall          Deactivate (remove OUR settings.json env keys, restore the
                     uniform-fable model state if the codex split is applied),
                     remove the boot descriptor. With `--purge`, remove state too.

Flags:
  --base-dir PATH     State dir (default: $CT6_GATEWAY_HOME, else
                      ~/.architect-team/gateway/).
  --openai-key KEY    Store the OpenAI key in gateway.env (else env OPENAI_API_KEY,
                      else an existing gateway.env entry).
  --anthropic-key KEY Store an Anthropic key in gateway.env (opts into api-key mode).
  --openai-model ID   The OpenAI-side model id the codex alias maps to
                      (default: gpt-5.6-sol; written as openai/<id>).
  --port N            Gateway port (default: 4000).
  --activate          api-key mode only: write the Claude Code env block to
                      settings.json AND apply the codex role split. In
                      subscription mode this degrades to an honest note.
  --settings-path P   Claude settings.json location (tests inject a tmp path).
  --agents-dir P      agents/ dir for the model split (tests inject a tmp dir).
  --no-install        Skip the pip install (state-only provisioning).
  --check-only        Report intent only; provision nothing.
  --json              Machine-readable JSON report.
  --purge             (uninstall) also remove the state dir.

Exit codes: 0 success; 1 a real failure (actionable message).

HONEST BOUNDARY: this provisions + configures; it never registers the boot
descriptor, never starts the gateway for you, and never claims the gateway is
"running". Model availability stays an INPUT (the resolve_model convention):
activation applies the split because YOU asserted the backend exists by enabling
external-LLM usage — nothing here probes a live API.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import secrets
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]

ENV_HOME = "CT6_GATEWAY_HOME"
# Tri-state enable signal read by setup.py (truthy=enable, set-falsy=disable,
# absent=no signal) — the same convention as CT6_CODEX_56_AVAILABLE.
ENV_SIGNAL = "CT6_EXTERNAL_LLM"
SERVICE_NAME = "ct6-llm-gateway"
DEFAULT_PORT = 4000
# The OpenAI-side model id the codex alias maps to — the id OpenAI's live
# /v1/models registry serves Codex 5.6 (sol) under (verified 2026-07-15; the
# standalone -codex line stops at gpt-5.3-codex, the 5.6 generation ships as
# gpt-5.6-sol/terra/luna). NOT validated at install time (model availability is
# not probe-able from stdlib); override with --openai-model if it moves.
DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"

CONFIG_NAME = "config.yaml"
ENV_FILE_NAME = "gateway.env"
STATE_NAME = "gateway.json"
DESCRIPTOR_DIRNAME = "descriptor"
MASTER_KEY_VAR = "CT6_GATEWAY_MASTER_KEY"

AUTH_MODE_API_KEY = "api-key"
AUTH_MODE_SUBSCRIPTION = "subscription"

LITELLM_PACKAGE = "litellm[proxy]"
# Force a binary wheel for litellm itself: its sdist grew a Rust component
# (litellm-rust python-bridge) whose build needs a full MSVC/cargo toolchain —
# observed failing on a real Windows install ("linker `link.exe` not found").
# With --only-binary the resolver backtracks to the newest version that ships
# a compatible wheel instead of attempting a source build.
LITELLM_INSTALL_ARGS = ["--only-binary", "litellm", LITELLM_PACKAGE]


def _load(name: str, rel: str):
    """Load an in-repo sibling module by file path (mirrors install_librarian.py)."""
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / rel)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {name} from {rel}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Reused substrate: the model lever (codex alias + split), the bg-runtime
# descriptor generator, and setup.py's PEP-668-aware pip ladder.
_lever = _load("ct6_model_lever", "scripts/setup/set_default_model.py")
_bg = _load("ct6_bg_runtime", "services/common/bg_runtime.py")
_setup = _load("ct6_setup_module", "scripts/setup/setup.py")

CODEX_ALIAS = _lever.CODEX_MODEL  # "codex-5.6-sol" — the id agents/*.md carry


# --------------------------------------------------------------------------- #
# base-dir / auth-mode / key resolution
# --------------------------------------------------------------------------- #

def resolve_base_dir(explicit: Optional[str], env: Optional[dict[str, str]] = None) -> Path:
    """Resolve the state base dir: explicit `--base-dir` > `$CT6_GATEWAY_HOME` >
    `~/.architect-team/gateway/`."""
    env = os.environ if env is None else env
    if explicit:
        return Path(explicit)
    from_env = env.get(ENV_HOME)
    if from_env:
        return Path(from_env)
    return Path.home() / ".architect-team" / "gateway"


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE env file (comments + blank lines ignored; first `=` splits)."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    except OSError:
        return {}
    return out


def write_env_file(path: Path, values: dict[str, str]) -> None:
    """Write the gateway env file (sorted KEY=VALUE) and chmod 0600 best-effort.
    This file is the ONLY place a raw key is persisted — outside the repo."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}={v}" for k, v in sorted(values.items()) if v) + "\n"
    path.write_text(body, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform-dependent best-effort
        pass


def resolve_keys(
    base: Path,
    openai_arg: Optional[str] = None,
    anthropic_arg: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Resolve the gateway's secret set: explicit args > process env > the existing
    gateway.env. Returns only the keys that resolved (values are RAW — callers must
    mask before any display)."""
    env = os.environ if env is None else env
    existing = read_env_file(base / ENV_FILE_NAME)
    out: dict[str, str] = {}
    openai = openai_arg or env.get("OPENAI_API_KEY") or existing.get("OPENAI_API_KEY")
    anthropic = (anthropic_arg or env.get("ANTHROPIC_API_KEY")
                 or existing.get("ANTHROPIC_API_KEY"))
    master = existing.get(MASTER_KEY_VAR)
    if openai:
        out["OPENAI_API_KEY"] = openai
    if anthropic:
        out["ANTHROPIC_API_KEY"] = anthropic
    out[MASTER_KEY_VAR] = master or ("sk-ct6-" + secrets.token_urlsafe(24))
    return out


def resolve_auth_mode(keys: dict[str, str]) -> str:
    """``api-key`` when an Anthropic key resolved; else ``subscription`` — the mode
    where fable is used via Claude Code's native sign-in and the gateway serves
    OpenAI only. This is a KEY-PRESENCE check, never a live-API probe."""
    return AUTH_MODE_API_KEY if keys.get("ANTHROPIC_API_KEY") else AUTH_MODE_SUBSCRIPTION


def _mask(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    return ("…" + secret[-4:]) if len(secret) >= 4 else "set"


# --------------------------------------------------------------------------- #
# generated artifacts: config.yaml / launcher / claude env block
# --------------------------------------------------------------------------- #

def build_gateway_config(
    auth_mode: str,
    codex_alias: str = CODEX_ALIAS,
    openai_model: str = DEFAULT_OPENAI_MODEL,
) -> str:
    """The LiteLLM proxy config. Deterministic text (no yaml dep); secrets are
    `os.environ/...` references resolved from gateway.env by the launcher —
    NEVER raw values.

    * Always: the codex alias → OpenAI route (the v3.35.0 role-split backend).
    * api-key mode only: a catch-all route sending every other model id to
      Anthropic, so ANTHROPIC_BASE_URL can front the whole harness.
    * Always: a master key, so the local proxy never runs unauthenticated.
    """
    lines = [
        "# CT6 external-LLM gateway (LiteLLM) — GENERATED by",
        "# scripts/setup/install_gateway.py; edit by re-running the installer.",
        "model_list:",
        f"  - model_name: {codex_alias}",
        "    litellm_params:",
        f"      model: openai/{openai_model}",
        "      api_key: os.environ/OPENAI_API_KEY",
    ]
    if auth_mode == AUTH_MODE_API_KEY:
        lines += [
            '  - model_name: "*"',
            "    litellm_params:",
            '      model: "anthropic/*"',
            "      api_key: os.environ/ANTHROPIC_API_KEY",
        ]
    lines += [
        "general_settings:",
        f"  master_key: os.environ/{MASTER_KEY_VAR}",
        "",
    ]
    return "\n".join(lines)


def _litellm_command() -> str:
    """The command the launcher runs: the resolved `litellm` console script when
    present, else the bare name (resolved again at launch time via PATH)."""
    return shutil.which("litellm") or "litellm"


def build_launcher(platform_key: str, base: Path, port: int) -> tuple[str, str]:
    """Return (filename, content) of the gateway launcher for `platform_key`.
    The launcher loads gateway.env into the process env and execs the proxy —
    so a boot-descriptor-started gateway sees its keys without them living in
    the descriptor or the shell profile."""
    cmd = _litellm_command()
    if platform_key == "windows":
        # joined with "\n": the text-mode write translates to CRLF on Windows
        # (a literal "\r\n" here would double to "\r\r\n" through that layer)
        content = "\n".join([
            "@echo off",
            "REM CT6 external-LLM gateway launcher — GENERATED by install_gateway.py",
            "REM PYTHONUTF8: litellm's startup banner is not cp1252-encodable and",
            "REM crashes app startup on a legacy-codepage Windows console without it.",
            'set "PYTHONUTF8=1"',
            f'for /f "usebackq eol=# tokens=1,* delims==" %%a in ("{base / ENV_FILE_NAME}") do set "%%a=%%b"',
            f'"{cmd}" --config "{base / CONFIG_NAME}" --port {port}',
            "",
        ])
        return "run_gateway.bat", content
    content = "\n".join([
        "#!/bin/sh",
        "# CT6 external-LLM gateway launcher — GENERATED by install_gateway.py",
        "PYTHONUTF8=1",
        "export PYTHONUTF8",
        "set -a",
        f'. "{base / ENV_FILE_NAME}"',
        "set +a",
        f'exec "{cmd}" --config "{base / CONFIG_NAME}" --port {port}',
        "",
    ])
    return "run_gateway.sh", content


def gateway_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def build_claude_env_block(port: int, master_key: str) -> dict[str, str]:
    """The settings.json `env` entries that point Claude Code at the gateway.
    Written ONLY in api-key mode and only on explicit --activate — in
    subscription mode rerouting native sign-in auth is unsupported."""
    return {
        "ANTHROPIC_BASE_URL": gateway_url(port),
        "ANTHROPIC_AUTH_TOKEN": master_key,
    }


# --------------------------------------------------------------------------- #
# settings.json activation (merge-preserving, mirrors setup.py's flag write)
# --------------------------------------------------------------------------- #

def _read_settings(settings_path: Path) -> dict[str, Any]:
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def apply_claude_env(settings_path: Path, port: int, master_key: str) -> None:
    """Merge the gateway env block into settings.json (idempotent; every other
    key preserved — the same merge posture as setup.py's teams-mode write)."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_settings(settings_path)
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        env_block = {}
    env_block.update(build_claude_env_block(port, master_key))
    data["env"] = env_block
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remove_claude_env(settings_path: Path, port: int) -> bool:
    """Remove OUR env entries from settings.json — only when ANTHROPIC_BASE_URL
    still points at THIS gateway's URL (a user-customized value is never
    clobbered). Returns True when something was removed."""
    data = _read_settings(settings_path)
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        return False
    if env_block.get("ANTHROPIC_BASE_URL") != gateway_url(port):
        return False
    env_block.pop("ANTHROPIC_BASE_URL", None)
    env_block.pop("ANTHROPIC_AUTH_TOKEN", None)
    data["env"] = env_block
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def claude_env_applied(settings_path: Path, port: int) -> bool:
    env_block = _read_settings(settings_path).get("env")
    return isinstance(env_block, dict) and env_block.get(
        "ANTHROPIC_BASE_URL") == gateway_url(port)


# --------------------------------------------------------------------------- #
# litellm install (through setup.py's PEP-668-aware ladder)
# --------------------------------------------------------------------------- #

def litellm_installed() -> bool:
    try:
        return importlib.util.find_spec("litellm") is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False


def install_litellm(installer=None) -> tuple[bool, Optional[str]]:
    """Install `litellm[proxy]` via setup.py's `_install_packages` ladder
    (uv → pip --user → --break-system-packages), forcing a binary wheel for
    litellm (see LITELLM_INSTALL_ARGS — the ladder appends the args verbatim
    after `install`, so the flag rides along on every rung). `installer` is
    injectable so tests never touch pip for real."""
    installer = installer or _setup._install_packages
    return installer(LITELLM_INSTALL_ARGS)


# --------------------------------------------------------------------------- #
# step / report scaffolding (mirrors install_librarian.py)
# --------------------------------------------------------------------------- #

@dataclass
class StepResult:
    name: str
    status: str  # "ok" | "skipped" | "fail"
    detail: str = ""


@dataclass
class Report:
    action: str = "install"
    base_dir: str = ""
    auth_mode: str = AUTH_MODE_SUBSCRIPTION
    openai_key_present: bool = False
    anthropic_key_present: bool = False
    litellm_present: bool = False
    enabled: bool = False
    activated: bool = False
    split_applied: bool = False
    descriptor_path: Optional[str] = None
    register_hint: Optional[str] = None
    remediation: Optional[str] = None
    check_only: bool = False
    steps: list[StepResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.steps.append(StepResult(name=name, status=status, detail=detail))


def _platform_key() -> str:
    return {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}.get(
        platform.system(), "linux")


def _write_state(base: Path, payload: dict[str, Any]) -> None:
    """Persist the non-secret installer state (gateway.json). NEVER a raw key."""
    base.mkdir(parents=True, exist_ok=True)
    (base / STATE_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_state(base: Path) -> dict[str, Any]:
    path = base / STATE_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _default_agents_dir() -> Path:
    return _REPO_ROOT / "agents"


SUBSCRIPTION_MODE_NOTE = (
    "subscription mode — no ANTHROPIC_API_KEY resolved, so Anthropic models "
    "(fable) keep Claude Code's native sign-in auth: ANTHROPIC_BASE_URL is NOT "
    "written and the codex role split stays OFF (the harness cannot route only "
    "codex traffic through the gateway while sign-in auth handles the rest). "
    "The gateway still serves OpenAI models to direct callers. For the full "
    "gateway + the codex split: set ANTHROPIC_API_KEY and re-run install "
    "--activate."
)


# --------------------------------------------------------------------------- #
# subcommand handlers
# --------------------------------------------------------------------------- #

def _cmd_install(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="install", base_dir=str(base),
                    check_only=bool(args.check_only))
    keys = resolve_keys(base, args.openai_key, args.anthropic_key)
    report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
    report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
    report.auth_mode = resolve_auth_mode(keys)
    report.litellm_present = litellm_installed()

    if args.check_only:
        would = "api-key (full gateway)" if report.auth_mode == AUTH_MODE_API_KEY \
            else "subscription (fable via sign-in; gateway OpenAI-only)"
        report.add("check-only", "skipped",
                   f"would install in {would} mode; no state provisioned")
        return report

    # 1. litellm through the setup.py install ladder.
    if report.litellm_present and not args.force_reinstall:
        report.add("litellm", "ok", "already installed")
    elif args.no_install:
        report.add("litellm", "skipped", "--no-install (state-only provisioning)")
    else:
        ok, detail = install_litellm()
        report.litellm_present = ok
        if ok:
            report.add("litellm", "ok",
                       f"pip install \"{LITELLM_PACKAGE}\""
                       + (f" — {detail}" if detail else ""))
        else:
            report.add("litellm", "fail",
                       f"install failed: {detail}. Remediation: "
                       f"pip install \"{LITELLM_PACKAGE}\" then re-run.")

    # 2. secrets → gateway.env (the only raw-key location; chmod 0600).
    write_env_file(base / ENV_FILE_NAME, keys)
    report.add("secrets", "ok",
               f"gateway.env written (OPENAI_API_KEY: {_mask(keys.get('OPENAI_API_KEY')) or 'ABSENT'}, "
               f"ANTHROPIC_API_KEY: {_mask(keys.get('ANTHROPIC_API_KEY')) or 'absent — subscription mode'})")

    # 3. config + launcher + state.
    (base / CONFIG_NAME).write_text(
        build_gateway_config(report.auth_mode, CODEX_ALIAS, args.openai_model),
        encoding="utf-8")
    launcher_name, launcher_body = build_launcher(_platform_key(), base, args.port)
    (base / launcher_name).write_text(launcher_body, encoding="utf-8")
    if not launcher_name.endswith(".bat"):
        try:
            os.chmod(base / launcher_name, 0o755)
        except OSError:  # pragma: no cover
            pass
    report.add("config", "ok",
               f"{CONFIG_NAME} ({report.auth_mode} mode) + {launcher_name} written")

    # 4. boot descriptor (written + hint printed; NEVER registered for you).
    desc_dir = base / DESCRIPTOR_DIRNAME
    desc_dir.mkdir(parents=True, exist_ok=True)
    descriptor = _bg.install_descriptor(
        _platform_key(), SERVICE_NAME, str(base / launcher_name))
    desc_path = desc_dir / descriptor["filename"]
    desc_path.write_text(descriptor["content"], encoding="utf-8")
    report.descriptor_path = str(desc_path)
    report.register_hint = descriptor["register_hint"]
    report.add("descriptor", "ok",
               f"{descriptor['kind']} descriptor written to {desc_path}")

    # 5. enablement (honest: no OpenAI key => provisioned but NOT enabled).
    report.enabled = report.openai_key_present
    if not report.enabled:
        report.remediation = (
            f"set OPENAI_API_KEY (env) or re-run with --openai-key …; state dir: {base}")
        report.add("enable", "skipped",
                   "no OpenAI key resolved; provisioned but NOT enabled")
    else:
        report.add("enable", "ok",
                   "gateway enabled; register the printed descriptor (or run the "
                   "launcher directly) to start it")

    # 6. activation (api-key mode only; consent came from the explicit flag).
    if args.activate:
        if report.auth_mode == AUTH_MODE_API_KEY and report.enabled:
            settings_path = Path(args.settings_path) if args.settings_path \
                else _setup.DEFAULT_USER_SETTINGS_PATH
            apply_claude_env(settings_path, args.port, keys[MASTER_KEY_VAR])
            report.activated = True
            report.add("activate", "ok",
                       f"ANTHROPIC_BASE_URL={gateway_url(args.port)} + auth token "
                       f"written to {settings_path}")
            agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
            if agents_dir.is_dir():
                changed = _lever.apply_split(agents_dir, CODEX_ALIAS)
                report.split_applied = True
                report.add("codex-split", "ok",
                           f"role split applied ({len(changed)} file(s) rewritten; "
                           f"dev/checking/testing agents → {CODEX_ALIAS})")
            else:
                report.add("codex-split", "skipped",
                           f"agents dir not found at {agents_dir}; apply manually: "
                           f"python scripts/setup/set_default_model.py --split codex")
        elif report.auth_mode == AUTH_MODE_SUBSCRIPTION:
            report.add("activate", "skipped", SUBSCRIPTION_MODE_NOTE)
        else:
            report.add("activate", "skipped",
                       "cannot activate: no OpenAI key (see enable remediation)")
    elif report.auth_mode == AUTH_MODE_SUBSCRIPTION:
        report.add("mode", "ok", SUBSCRIPTION_MODE_NOTE)

    _write_state(base, {
        "auth_mode": report.auth_mode,
        "port": args.port,
        "codex_alias": CODEX_ALIAS,
        "openai_model": args.openai_model,
        "activated": report.activated,
        "enabled": report.enabled,
    })
    return report


def _cmd_status(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="status", base_dir=str(base))
    state = _read_state(base)
    keys = read_env_file(base / ENV_FILE_NAME)
    port = int(state.get("port", args.port))
    report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
    report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
    report.auth_mode = state.get("auth_mode", resolve_auth_mode(keys))
    report.litellm_present = litellm_installed()
    report.enabled = report.openai_key_present and (base / CONFIG_NAME).is_file()
    settings_path = Path(args.settings_path) if args.settings_path \
        else _setup.DEFAULT_USER_SETTINGS_PATH
    report.activated = claude_env_applied(settings_path, port)
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    report.descriptor_path = str(descs[0]) if descs else None
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    policy = _lever.policy_state(agents_dir) if agents_dir.is_dir() else "unknown"
    report.split_applied = policy == "codex-split"
    if not report.openai_key_present:
        report.remediation = "set OPENAI_API_KEY or re-run install --openai-key …"
    report.add("status", "ok",
               f"mode={report.auth_mode}; enabled={report.enabled}; "
               f"activated={report.activated}; litellm={report.litellm_present}; "
               f"model-policy={policy}; "
               f"OPENAI_API_KEY={_mask(keys.get('OPENAI_API_KEY')) or 'absent'}; "
               f"ANTHROPIC_API_KEY={_mask(keys.get('ANTHROPIC_API_KEY')) or 'absent'}")
    return report


def _cmd_uninstall(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="uninstall", base_dir=str(base),
                    check_only=bool(args.check_only))
    state = _read_state(base)
    port = int(state.get("port", args.port))

    if args.check_only:
        report.add("check-only", "skipped",
                   "would deactivate settings.json, restore uniform fable if the "
                   "codex split is applied, and remove the boot descriptor; "
                   "nothing touched")
        return report

    # 1. deactivate settings.json (only OUR values are ever removed).
    settings_path = Path(args.settings_path) if args.settings_path \
        else _setup.DEFAULT_USER_SETTINGS_PATH
    if remove_claude_env(settings_path, port):
        report.add("deactivate", "ok",
                   f"gateway env entries removed from {settings_path}")
    else:
        report.add("deactivate", "skipped",
                   "no gateway env entries in settings.json (no-op)")

    # 2. restore the model state ONLY when the codex split is what's applied.
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    if agents_dir.is_dir() and _lever.policy_state(agents_dir) == "codex-split":
        changed = _lever.set_model(agents_dir, "fable")
        report.add("model-restore", "ok",
                   f"uniform fable restored ({len(changed)} file(s) rewritten)")
    else:
        report.add("model-restore", "skipped",
                   "model state is not codex-split (left untouched)")

    # 3. descriptor removal + unregister hint (never executed for you).
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    if descs:
        kind = _platform_key()
        report.register_hint = {
            "linux": f"sudo systemctl disable --now {SERVICE_NAME}",
            "darwin": f"launchctl unload -w ~/Library/LaunchAgents/{SERVICE_NAME}.plist",
            "windows": f'schtasks /delete /tn "{SERVICE_NAME}" /f',
        }[kind]
        for d in descs:
            try:
                d.unlink()
            except OSError:  # pragma: no cover
                pass
        report.add("descriptor", "ok",
                   "boot descriptor removed; run the printed unregister hint")
    else:
        report.add("descriptor", "skipped", "no boot descriptor present (no-op)")

    if args.purge:
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
            report.add("purge", "ok", f"removed state dir {base}")
        else:
            report.add("purge", "skipped", "state dir already absent (no-op)")
    return report


_HANDLERS = {
    "install": _cmd_install,
    "status": _cmd_status,
    "uninstall": _cmd_uninstall,
}


# --------------------------------------------------------------------------- #
# setup.py integration
# --------------------------------------------------------------------------- #

def resolve_external_llm_signal(
    enable_flag: bool, disable_flag: bool, env: Optional[dict[str, str]] = None,
) -> Optional[bool]:
    """Tri-state enable signal for setup.py: True (--external-llm or truthy
    CT6_EXTERNAL_LLM), False (--no-external-llm — the flag overrides the env —
    or a SET-but-falsy env var), None (no signal: leave everything untouched)."""
    if disable_flag:
        return False
    if enable_flag:
        return True
    env = os.environ if env is None else env
    if ENV_SIGNAL not in env:
        return None
    return str(env.get(ENV_SIGNAL, "")).strip().lower() in {"1", "true", "yes"}


def setup_entry(
    enable: bool,
    check_only: bool,
    assume_yes: bool,
    base_dir: Optional[str] = None,
    settings_path: Optional[str] = None,
    agents_dir: Optional[str] = None,
) -> tuple[str, str, Optional[str]]:
    """The setup.py hook: run install (enable=True) or uninstall (enable=False)
    and fold the result into one (name, status, detail) report row. NEVER raises
    and never gates setup — any failure degrades to a 'warn' row with the manual
    remediation (the same posture as apply_model_policy)."""
    name = "external-llm (LiteLLM gateway)"
    manual = "python scripts/setup/install_gateway.py install --activate"
    try:
        base = resolve_base_dir(base_dir)
        argv = ["install" if enable else "uninstall", "--base-dir", str(base)]
        if check_only:
            argv.append("--check-only")
        if enable and assume_yes:
            # --activate writes settings.json + the model split; consent came
            # from --yes / CT6_SETUP_ASSUME_YES (the setup consent convention).
            argv.append("--activate")
        if settings_path:
            argv += ["--settings-path", settings_path]
        if agents_dir:
            argv += ["--agents-dir", agents_dir]
        parser = _build_parser()
        args = parser.parse_args(argv)
        handler = _HANDLERS[args.command or "install"]
        report = handler(args, base)
        failed = [s for s in report.steps if s.status == "fail"]
        if failed:
            return name, "warn", (
                f"{failed[0].name}: {failed[0].detail} — finish manually: {manual}")
        if check_only:
            return name, "note", "; ".join(
                f"{s.name}: {s.detail}" for s in report.steps) or "check-only"
        if not enable:
            return name, "applied", "gateway deactivated + descriptor removed"
        summary = (
            f"mode={report.auth_mode}; enabled={report.enabled}; "
            f"activated={report.activated}"
            + ("; codex split applied" if report.split_applied else "")
            + (f"; NOT enabled — {report.remediation}" if report.remediation else "")
        )
        if report.auth_mode == AUTH_MODE_SUBSCRIPTION:
            summary += " (fable via Claude sign-in; gateway serves OpenAI only)"
        elif report.enabled and not report.activated:
            summary += (
                " (activation needs consent: rerun with --yes, or run manually: "
                + manual + ")"
            )
        return name, "applied", summary
    except Exception as exc:  # never gate setup on the gateway installer
        return name, "warn", f"external-llm setup not applied ({exc}); run manually: {manual}"


def check_external_llm_option() -> tuple[str, str, Optional[str]]:
    """Informational row shown by setup.py when NO external-llm signal is present."""
    name = "external-llm (LiteLLM gateway — not requested)"
    detail = (
        "no external-LLM signal — nothing installed. To enable out-of-the-box "
        "OpenAI/Codex usage rerun setup with --external-llm (or set "
        f"{ENV_SIGNAL}=1); --no-external-llm uninstalls. Fable keeps working "
        "either via your Claude sign-in (no key) or via ANTHROPIC_API_KEY."
    )
    return name, "note", detail


# --------------------------------------------------------------------------- #
# argparse + emit
# --------------------------------------------------------------------------- #

def _add_shared_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-dir", default=None,
                        help=f"state dir (default ${ENV_HOME} or ~/.architect-team/gateway)")
    parser.add_argument("--openai-key", default=None,
                        help="OpenAI API key to store in gateway.env")
    parser.add_argument("--anthropic-key", default=None,
                        help="Anthropic API key to store in gateway.env (api-key mode)")
    parser.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL,
                        help=f"OpenAI-side model id for the codex alias (default: {DEFAULT_OPENAI_MODEL})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"gateway port (default: {DEFAULT_PORT})")
    parser.add_argument("--activate", action="store_true",
                        help="api-key mode: write the Claude Code env block + apply the codex split")
    parser.add_argument("--settings-path", default=None,
                        help="Claude settings.json path (default: ~/.claude/settings.json)")
    parser.add_argument("--agents-dir", default=None,
                        help="agents/ dir for the model split (default: the repo's agents/)")
    parser.add_argument("--no-install", action="store_true",
                        help="skip the pip install (state-only provisioning)")
    parser.add_argument("--force-reinstall", action="store_true",
                        help="reinstall litellm even when already importable")
    parser.add_argument("--check-only", action="store_true",
                        help="report intent only; provision nothing")
    parser.add_argument("--json", action="store_true",
                        help="emit a machine-readable JSON report")
    parser.add_argument("--purge", action="store_true",
                        help="(uninstall) also remove the state dir")


def _build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    _add_shared_flags(shared)
    parser = argparse.ArgumentParser(
        prog="install_gateway.py", parents=[shared],
        description="Install / manage the CT6 external-LLM gateway (LiteLLM).")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("install", parents=[shared], add_help=False)
    sub.add_parser("status", parents=[shared], add_help=False)
    sub.add_parser("uninstall", parents=[shared], add_help=False)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    # Ensure Unicode output works on Windows consoles (cp1252 default) — the
    # masked-key ellipsis and pip's own output are not cp1252-encodable
    # (the same guard as setup.py's main()).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - console-dependent best-effort
            pass
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    command = args.command or "install"
    base = resolve_base_dir(args.base_dir)
    handler = _HANDLERS[command]
    try:
        report = handler(args, base)
    except Exception as exc:
        msg = f"{command} failed: {exc!r}"
        if getattr(args, "json", False):
            print(json.dumps({"action": command, "error": msg}, indent=2))
        else:
            print(f"\n[x] {msg}\n")
        return 1
    return _emit(report, getattr(args, "json", False))


def _emit(report: Report, as_json: bool) -> int:
    if as_json:
        payload = {
            "action": report.action,
            "base_dir": report.base_dir,
            "auth_mode": report.auth_mode,
            "openai_key_present": report.openai_key_present,
            "anthropic_key_present": report.anthropic_key_present,
            "litellm_present": report.litellm_present,
            "enabled": report.enabled,
            "activated": report.activated,
            "split_applied": report.split_applied,
            "descriptor_path": report.descriptor_path,
            "register_hint": report.register_hint,
            "remediation": report.remediation,
            "check_only": report.check_only,
            "steps": [{"name": s.name, "status": s.status, "detail": s.detail}
                      for s in report.steps],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print()
    print("=" * 64)
    print(f"  CT6 external-LLM gateway {report.action} -- summary")
    print("=" * 64)
    for step in report.steps:
        marker = {"ok": "[+]", "skipped": "[-]", "fail": "[x]"}.get(step.status, "[?]")
        print(f"  {marker} {step.name:<14} {step.detail}")
    print("=" * 64)
    print(f"  State dir:   {report.base_dir}")
    print(f"  Auth mode:   {report.auth_mode}"
          + ("  (fable via Claude sign-in)" if report.auth_mode == AUTH_MODE_SUBSCRIPTION else ""))
    print(f"  Gateway:     {'enabled' if report.enabled else 'provisioned but NOT enabled'}"
          f"; Claude Code activation: {'applied' if report.activated else 'not applied'}")
    if report.register_hint:
        print("  Register the boot descriptor yourself (NOT run for you):")
        print(f"    {report.register_hint}")
    if report.remediation:
        print(f"  Remediation: {report.remediation}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
