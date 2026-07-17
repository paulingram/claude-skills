#!/usr/bin/env python3
"""install_gateway.py — the full-lifecycle installer for the CT6 external-LLM gateway.

Run from `/architect-team:architect-team-setup --external-llm` (or standalone).
Stdlib-only. Mirrors the `install_librarian.py` pattern: a step-summary printer,
`--json`, `--check-only`, and the same "never auto-register / never auto-enable
without a key" safety posture.

WHAT THIS INSTALLS: a local LiteLLM proxy (MIT-licensed, `pip install
"litellm[proxy]"`) configured so the secondary role split (v3.35.0; provider
registry v3.40.0) has a real backend — the neutral `ct6-secondary` alias
routes to the CHOSEN provider from the lever's SECONDARY_PROVIDERS registry
(OpenAI Codex 5.6 / Z.ai GLM), while Anthropic models either pass through the
same gateway (api-key mode) or keep Claude Code's native sign-in auth
(subscription mode).

PROVIDER SELECTION (v3.40.0): the secondary provider resolves through a
ladder — the `--secondary` flag > `$CT6_SECONDARY_PROVIDER` > the recorded
`gateway.json` choice > the v3.39 grandfather (an `openai_model`-only state
reads as openai) > the interactive prompt > the openai default. An unknown
name FAILS the run (it never falls through to a different provider);
`--re-ask-provider` suppresses the recorded/grandfathered choice so the
question is asked again. EVERY install — with or without `--activate` —
migrates an on-disk LEGACY split alias (`codex-5.6-sol`) to the neutral alias
the just-regenerated config routes, and CARRIES a prior activated/split state
forward: a plain re-install never silently deactivates a machine (uninstall
is the only downgrade path).

AUTH MODES (resolved, never probed against a live API):
  * ``api-key``       — an `ANTHROPIC_API_KEY` resolves (process env, gateway env
                        file, or `--anthropic-key`). The gateway fronts BOTH
                        providers: explicit Anthropic routes + a catch-all, plus
                        the `ct6-secondary` → chosen-provider route. `--activate`
                        may then point Claude Code at the gateway
                        (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` in
                        `~/.claude/settings.json`, consent-gated) and apply the
                        secondary role split via `set_default_model.py`.
  * ``subscription``  — NO Anthropic key anywhere. Fable (and every Anthropic
                        model) keeps Claude Code's native subscription sign-in —
                        `ANTHROPIC_BASE_URL` is deliberately NEVER written, since
                        rerouting subscription OAuth traffic through a local proxy
                        is not supported by the harness. The gateway still runs,
                        secondary-provider-only, for the service tier and direct
                        callers. The secondary role split stays OFF (the harness
                        cannot split-route only secondary traffic); the printed
                        remediation is to add an `ANTHROPIC_API_KEY` and re-run
                        with `--activate`.

SECRETS: keys live ONLY in `<state>/gateway.env` (chmod 0600 best-effort) and are
masked to their last 4 chars in every report. The generated `config.yaml` carries
`os.environ/...` references, never raw keys. Nothing under the repo is touched.

KEY PROMPTS (v3.38.0, ask-then-apply): an INTERACTIVE install prompts for a
missing key instead of punting to a printed remediation — hidden (getpass)
entry, degrading to visible input with a one-line warning ONLY when hidden
entry is unachievable (getpass's non-console fallback), never on an import
check. Interactivity is the `--interactive-prompts` flag, set only by
interactive callers: `main()` on a real TTY without `--json`/`--check-only`,
or `setup_entry(assume_yes=False, check_only=False)` on a TTY. A blank entry
skips (today's absent-key path runs verbatim) and records the slot in
`<state>/key-declines.json` (via=prompt-skip); the `decline` subcommand is the
wrapper flow's deterministic record channel (via=wrapper). A recorded decline
suppresses the PROMPT on re-runs — never the `status` truth — auto-resets the
moment that slot's key resolves on any path, and `--re-ask-keys` clears it so
prompts fire again. Non-interactive, non-TTY, `--check-only`, and `--json`
runs never prompt, never block, never invent a key.

Subcommands:
  install (default)  Provision state + config + env file + launcher + the per-OS
                     boot descriptor, install `litellm[proxy]` through setup.py's
                     PEP-668-aware ladder, and (v3.37.0) REGISTER + START the
                     gateway itself — user-level (schtasks onlogon / `systemctl
                     --user` / LaunchAgents), never sudo/admin; `--no-register`
                     opts back to the printed hint. Enabled ONLY when the chosen
                     secondary provider's key resolves; otherwise
                     install-but-disabled (registration deferred) with an
                     explicit remediation.
  status             Report auth mode / provider / keys (masked) / litellm
                     presence / file layout / registration / activation + the
                     agents' model policy state. With `--live`, probe the
                     RUNNING gateway for the STATE-RECORDED alias
                     (`secondary_alias`, falling back to the legacy
                     `codex_alias`) — a working legacy v3.39 install probes
                     green.
  uninstall          Deactivate (remove OUR settings.json env keys, restore the
                     uniform-fable model state if the secondary split is
                     applied), stop + UNREGISTER the gateway, remove the boot
                     descriptor. With `--purge`, remove state too (incl.
                     key-declines.json).
  decline            Record (or `--clear`) a per-key decline —
                     `decline <anthropic|openai|zai>` — the wrapper flow's
                     deterministic channel for an explicit "don't ask again".

Flags:
  --base-dir PATH     State dir (default: $CT6_GATEWAY_HOME, else
                      ~/.architect-team/gateway/).
  --secondary NAME    Secondary provider from the SECONDARY_PROVIDERS registry
                      (openai|zai); see the resolution ladder above.
  --secondary-model ID  Upstream model id override for the chosen provider
                      (default: the registry entry's model, e.g. gpt-5.6-sol).
  --<provider>-key KEY  One flag per registry provider (--openai-key /
                      --zai-key): store that provider's key in gateway.env
                      (else its key_env in the process env, else an existing
                      gateway.env entry).
  --anthropic-key KEY Store an Anthropic key in gateway.env (opts into api-key mode).
  --openai-model ID   Deprecated synonym for `--secondary-model` with
                      `--secondary openai`.
  --port N            Gateway port (default: 4000).
  --activate          api-key mode only: write the Claude Code env block to
                      settings.json AND apply the secondary role split. In
                      subscription mode this degrades to an honest note.
  --settings-path P   Claude settings.json location (tests inject a tmp path).
  --agents-dir P      agents/ dir for the model split (tests inject a tmp dir).
  --no-install        Skip the pip install (state-only provisioning).
  --no-register       Skip the automatic boot registration (print the hint).
  --interactive-prompts  Allow the interactive missing-key prompt (set only by
                      interactive callers; never under --check-only/--json).
  --re-ask-keys       Clear the recorded key declines so prompts fire again.
  --re-ask-provider   Ignore the recorded/grandfathered provider choice and
                      resolve it again.
  --check-only        Report intent only; provision nothing.
  --live              (status) probe the RUNNING gateway's /v1/models and
                      confirm it serves what the mode needs.
  --json              Machine-readable JSON report.
  --purge             (uninstall) also remove the state dir.

Exit codes: 0 success; 1 a real failure (actionable message).

HONEST BOUNDARY: registration is EXECUTED by default (v3.37.0 owner directive —
the enable signal is the consent; user-level only, never sudo/admin; a failure
degrades to a fail step + the manual hint). Model availability stays an INPUT
(the resolve_model convention): activation applies the split because YOU
asserted the backend exists by enabling external-LLM usage — nothing here
probes a live API to DECIDE anything. v3.39.0 adds the post-install live
CONFIRMATION (the step the v3.38.1 field bug proved necessary): after a
registered install the installer polls the LOCAL gateway's /v1/models and
asserts the split's ids are actually served — verifying what was just
installed, never deciding policy from a probe. The split targets the
INSTALLED plugin copy (the agents Claude Code actually runs), falling back to
the repo agents/ when none exists; `~/.architect-team/gateway/gateway.json`
records the desired policy AND the served alias (`secondary_alias`, legacy
`codex_alias`) so the SessionStart self-heal survives plugin updates and
re-applies the alias the recorded gateway config actually routes
(heal-to-recorded-alias — never an alias the running gateway would 404).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]

ENV_HOME = "CT6_GATEWAY_HOME"
# Tri-state enable signal read by setup.py (truthy=enable, set-falsy=disable,
# absent=no signal) — the same convention as CT6_CODEX_56_AVAILABLE.
ENV_SIGNAL = "CT6_EXTERNAL_LLM"
ENV_SECONDARY_PROVIDER = "CT6_SECONDARY_PROVIDER"
SERVICE_NAME = "ct6-llm-gateway"
DEFAULT_PORT = 4000

# Anthropic model ids given EXPLICIT gateway routes in api-key mode (v3.38.1).
# The '*' catch-all alone was observed non-functional on a real LiteLLM
# install (SR-gateway-wildcard-route); these are the ids a real key listed via
# /v1/models on 2026-07-16, fable first (the plugin default), opus-4-8 second
# (the implemented fallback). Extend here when Anthropic ships new ids — the
# catch-all remains as a best-effort tail for anything unlisted.
ANTHROPIC_EXPLICIT_MODELS = (
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
)

CONFIG_NAME = "config.yaml"
ENV_FILE_NAME = "gateway.env"
STATE_NAME = "gateway.json"
DECLINES_NAME = "key-declines.json"
DESCRIPTOR_DIRNAME = "descriptor"
MASTER_KEY_VAR = "CT6_GATEWAY_MASTER_KEY"

# Provider-independent key slot, followed by the chosen secondary provider's slot.
ANTHROPIC_SLOT = ("anthropic", "ANTHROPIC_API_KEY")

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

SECONDARY_ALIAS = _lever.SECONDARY_ALIAS
SECONDARY_PROVIDERS = _lever.SECONDARY_PROVIDERS
# Deprecated external-reader name. New code uses SECONDARY_ALIAS; CODEX_ALIAS
# intentionally remains the historical upstream model id for one transition.
CODEX_ALIAS = _lever.CODEX_MODEL
DEFAULT_OPENAI_MODEL = str(SECONDARY_PROVIDERS["openai"]["model"])

# Model-policy strings — single-sourced from the lever (ADV3-5): the gateway
# never spells these literals itself, so they cannot drift from the emitter.
POLICY_SECONDARY_SPLIT = _lever.POLICY_SECONDARY_SPLIT
POLICY_UNIFORM_FABLE = _lever.POLICY_UNIFORM_FABLE
LEGACY_POLICY_CODEX_SPLIT = _lever.LEGACY_POLICY_CODEX_SPLIT


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


def provider_key_slots(secondary_provider: str) -> tuple[tuple[str, str], ...]:
    """Promptable key slots for a provider: chosen secondary first, Anthropic second."""
    entry = SECONDARY_PROVIDERS[secondary_provider]
    return ((secondary_provider, str(entry["key_env"])), ANTHROPIC_SLOT)


def preserved_env_keys() -> tuple[str, ...]:
    """gateway.env keys an install rewrite must never drop (ADV3-2): EVERY
    registry provider's key slot — switching --secondary must not delete the
    other provider's stored key — plus the Anthropic slot and the master key."""
    return tuple(str(SECONDARY_PROVIDERS[name]["key_env"])
                 for name in sorted(SECONDARY_PROVIDERS)) + (
        "ANTHROPIC_API_KEY", MASTER_KEY_VAR)


def resolve_secondary_provider(
    explicit: Optional[str],
    base: Path,
    *,
    env: Optional[dict[str, str]] = None,
    re_ask: bool = False,
    interactive: bool = False,
    prompt_fn=None,
    isatty_fn=None,
) -> tuple[Optional[str], str, Optional[str]]:
    """Resolve provider by flag > env > state > grandfather > ask > openai.

    Returns ``(provider, source, error)``. Unknown inputs never fall through to a
    different provider; callers surface the error and perform no state write.
    ``--re-ask-provider`` suppresses both recorded and grandfathered choices.
    """
    env = os.environ if env is None else env
    state = _read_state(base)
    candidate: Optional[str] = None
    source = ""
    if explicit is not None:
        candidate, source = str(explicit).strip().lower(), "flag"
    elif ENV_SECONDARY_PROVIDER in env:
        candidate = str(env.get(ENV_SECONDARY_PROVIDER, "")).strip().lower()
        source = "env"
    elif not re_ask and state.get("secondary_provider"):
        candidate = str(state["secondary_provider"]).strip().lower()
        source = "recorded"
    elif not re_ask and "openai_model" in state and "secondary_provider" not in state:
        candidate, source = "openai", "grandfather"
    elif interactive:
        candidate = _prompt_for_provider(prompt_fn=prompt_fn, isatty_fn=isatty_fn)
        source = "interactive"
    else:
        candidate, source = "openai", "default"
    if candidate not in SECONDARY_PROVIDERS:
        valid = ", ".join(sorted(SECONDARY_PROVIDERS))
        return None, source, (
            f"unknown secondary provider {candidate!r} from {source}; valid: {valid}")
    return candidate, source, None


def resolve_keys(
    base: Path,
    openai_arg: Optional[str] = None,
    anthropic_arg: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    *,
    secondary_provider: str = "openai",
    provider_args: Optional[dict[str, Optional[str]]] = None,
) -> dict[str, str]:
    """Resolve Anthropic + the chosen provider: args > process env > gateway.env."""
    env = os.environ if env is None else env
    existing = read_env_file(base / ENV_FILE_NAME)
    provider_args = dict(provider_args or {})
    if openai_arg is not None:
        provider_args["openai"] = openai_arg
    entry = SECONDARY_PROVIDERS[secondary_provider]
    provider_env = str(entry["key_env"])
    provider_key = (provider_args.get(secondary_provider) or env.get(provider_env)
                    or existing.get(provider_env))
    anthropic = (anthropic_arg or env.get("ANTHROPIC_API_KEY")
                 or existing.get("ANTHROPIC_API_KEY"))
    master = existing.get(MASTER_KEY_VAR)
    out: dict[str, str] = {}
    if provider_key:
        out[provider_env] = provider_key
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
# interactive key prompt + per-key decline record (v3.38.0)
# --------------------------------------------------------------------------- #
#
# Ask-then-apply: an interactive TTY install PROMPTS for a missing key (hidden
# getpass entry) instead of punting to a printed remediation. A blank entry
# skips and records the slot in key-declines.json (via=prompt-skip); the
# wrapper flow's AskUserQuestion decline is recorded via the `decline`
# subcommand (via=wrapper). A recorded decline suppresses the PROMPT on
# re-runs, never the `status` truth; it auto-resets the moment the slot's key
# resolves on any path, and --re-ask-keys clears it so prompts fire again.


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z")


def _read_declines(base: Path) -> dict[str, Any]:
    """Read <state>/key-declines.json — slot → {declined_at, via}. Missing or
    malformed reads as no declines (fail open: worst case we ask again)."""
    path = base / DECLINES_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_declines(base: Path, declines: dict[str, Any]) -> None:
    """Persist the decline record. An emptied record removes the file, so a
    fully-cleared state dir and a fresh one look identical."""
    path = base / DECLINES_NAME
    if not declines:
        try:
            path.unlink()
        except OSError:
            pass
        return
    base.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(declines, indent=2, sort_keys=True),
                    encoding="utf-8")


def _record_decline(base: Path, slot: str, via: str) -> None:
    """Record a slot decline. `via` is 'wrapper' (the decline subcommand — the
    slash-command flow's deterministic channel) or 'prompt-skip' (a blank entry
    at the installer prompt)."""
    declines = _read_declines(base)
    declines[slot] = {"declined_at": _utc_now_iso(), "via": via}
    _write_declines(base, declines)


def _clear_declines(base: Path, slot: Optional[str] = None) -> bool:
    """Clear one slot's decline, or ALL of them with slot=None (the
    --re-ask-keys path). Returns True when something was actually cleared."""
    declines = _read_declines(base)
    if not declines:
        return False
    if slot is None:
        _write_declines(base, {})
        return True
    if slot in declines:
        declines.pop(slot)
        _write_declines(base, declines)
        return True
    return False


def _stdin_isatty() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except Exception:  # pragma: no cover - a closed/replaced stdin is non-TTY
        return False


def _hidden_prompt(message: str) -> str:
    """Hidden (getpass) key entry. Degrades to visible input() with a one-line
    warning ONLY when hidden entry is unachievable — getpass's non-console
    fallback path, surfaced as GetPassWarning — never on an import check
    (getpass always imports)."""
    import getpass
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass(message)
    except getpass.GetPassWarning:
        print("[!] hidden entry is not available on this console -- "
              "the key will be VISIBLE as you type")
        return input(message)


_default_prompt_fn = _hidden_prompt   # injectable seam — tests stub this
_default_isatty_fn = _stdin_isatty    # injectable seam — tests stub this
_default_provider_prompt_fn = input    # visible provider-choice seam


def _prompt_for_provider(*, prompt_fn=None, isatty_fn=None) -> str:
    """Visible provider choice prompt. Blank selects OpenAI; non-TTY also defaults."""
    prompt_fn = prompt_fn or _default_provider_prompt_fn
    isatty_fn = isatty_fn or _default_isatty_fn
    if not isatty_fn():
        return "openai"
    choices = ", ".join(
        f"{name} ({entry['label']})" for name, entry in SECONDARY_PROVIDERS.items())
    try:
        entered = prompt_fn(
            f"Secondary provider [{choices}] (blank for openai): ")
    except (EOFError, KeyboardInterrupt):
        print()
        return "openai"
    return (entered or "").strip().lower() or "openai"


def _prompt_for_key(slot: str, *, prompt_fn=None, isatty_fn=None) -> Optional[str]:
    """Prompt for one slot's key on an interactive TTY. Returns the entered key
    (stripped) or None (blank entry, or stdin is not a TTY). The caller gates
    on --interactive-prompts / --check-only / --json and the decline record;
    this seam owns the TTY check and the hidden entry. The entered value is
    NEVER echoed — every report line masks via _mask."""
    prompt_fn = prompt_fn or _default_prompt_fn
    isatty_fn = isatty_fn or _default_isatty_fn
    if not isatty_fn():
        return None
    if slot == "anthropic":
        env_key = "ANTHROPIC_API_KEY"
    else:
        env_key = str(SECONDARY_PROVIDERS[slot]["key_env"])
    try:
        entered = prompt_fn(f"{env_key} for the CT6 gateway (blank to skip): ")
    except (EOFError, KeyboardInterrupt):
        # Ctrl-C / Ctrl-D at the prompt is a SKIP, not an abort — the same
        # semantics as the setup.py _prompt_user_consent house pattern (an
        # interrupt reads as a "no") and the librarian seam: the absent-key
        # path runs verbatim and a setup run never dies at a key prompt.
        print()
        return None
    entered = (entered or "").strip()
    return entered or None


# --------------------------------------------------------------------------- #
# generated artifacts: config.yaml / launcher / claude env block
# --------------------------------------------------------------------------- #

def _secondary_route_model(entry: dict[str, Optional[str]], model: str) -> str:
    prefix = str(entry["route_model"]).rsplit("/", 1)[0]
    return f"{prefix}/{model}"


def build_gateway_config(
    auth_mode: str,
    secondary_alias: str = SECONDARY_ALIAS,
    secondary_model: Optional[str] = None,
    secondary_provider: str = "openai",
) -> str:
    """The LiteLLM proxy config. Deterministic text (no yaml dep); secrets are
    `os.environ/...` references resolved from gateway.env by the launcher —
    NEVER raw values.

    * Always: the codex alias → OpenAI route (the v3.35.0 role-split backend).
    * api-key mode only: an EXPLICIT route per known Anthropic model id
      (ANTHROPIC_EXPLICIT_MODELS — fable first) plus a catch-all tail, so
      ANTHROPIC_BASE_URL can front the whole harness. Explicit routes are
      REQUIRED, not decorative: the catch-all alone was field-observed broken
      (v3.38.1, SR-gateway-wildcard-route).
    * Always: a master key, so the local proxy never runs unauthenticated.
    """
    entry = SECONDARY_PROVIDERS[secondary_provider]
    model = secondary_model or str(entry["model"])
    lines = [
        "# CT6 external-LLM gateway (LiteLLM) — GENERATED by",
        "# scripts/setup/install_gateway.py; edit by re-running the installer.",
        "model_list:",
        f"  - model_name: {secondary_alias}",
        "    litellm_params:",
        f"      model: {_secondary_route_model(entry, model)}",
        f"      api_key: os.environ/{entry['key_env']}",
    ]
    if entry.get("api_base"):
        lines.append(f"      api_base: {entry['api_base']}")
    if auth_mode == AUTH_MODE_API_KEY:
        # v3.38.1 (SR-gateway-wildcard-route, field-verified 2026-07-16): a
        # config that relies ONLY on the '*' catch-all was observed broken on a
        # real Windows LiteLLM install — the proxy exposed just the codex alias
        # and rejected every Anthropic id with "Invalid model name ... Call
        # /v1/models". Explicit per-model routes fixed it live (fable + opus
        # verified through the gateway). Each known Anthropic id therefore gets
        # its own route, emitted BEFORE the catch-all; the catch-all stays as a
        # best-effort tail for ids that ship after this list was written.
        for anthropic_id in ANTHROPIC_EXPLICIT_MODELS:
            lines += [
                f"  - model_name: {anthropic_id}",
                "    litellm_params:",
                f"      model: anthropic/{anthropic_id}",
                "      api_key: os.environ/ANTHROPIC_API_KEY",
            ]
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
# auto-registration (v3.37.0 — the installer EXECUTES the registration)
# --------------------------------------------------------------------------- #
#
# Owner directive: enabling external-LLM usage must be one command, so the
# installer registers + starts the gateway itself (opt-out: --no-register).
# This deliberately extends the older print-the-hint posture; the enable signal
# is the consent, registration stays user-level (never sudo / admin), and a
# registration failure degrades to a fail step + the manual hint — never a crash.

_default_runner = subprocess.run     # injectable seam — tests stub this
_default_spawner = subprocess.Popen  # injectable seam — the detached start-now


def _run(cmd: list[str], runner=None):
    runner = runner or _default_runner
    return runner(cmd, capture_output=True, text=True, encoding="utf-8",
                  errors="replace")


def _spawn_detached(cmd: list[str], spawner=None) -> bool:
    """Start a long-running process WITHOUT inheriting our pipes and WITHOUT
    waiting (a captured-pipe `subprocess.run` would block until the gateway
    itself exits — observed hanging a real install for its full timeout).
    Windows gets its own minimized console so the daemon survives us."""
    spawner = spawner or _default_spawner
    kwargs: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    if os.name == "nt":  # pragma: no cover - exercised on the real install
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7  # SW_SHOWMINNOACTIVE
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        kwargs["startupinfo"] = si
    try:
        spawner(cmd, **kwargs)
        return True
    except OSError:
        return False


def _windows_startup_dir(home: Optional[Path] = None) -> Path:
    """The current user's Startup folder — a plain-file autostart mechanism
    that needs NO privilege at all (observed: `schtasks /create` is denied
    from a non-elevated shell on a real Windows 11 box)."""
    if home is not None:
        return (Path(home) / "AppData" / "Roaming" / "Microsoft" / "Windows"
                / "Start Menu" / "Programs" / "Startup")
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def register_gateway(
    platform_key: str,
    launcher_path: Path,
    name: str = SERVICE_NAME,
    home: Optional[Path] = None,
    runner=None,
) -> tuple[bool, str]:
    """Register the gateway to start automatically AND start it now. User-level
    on every OS (schtasks onlogon / Startup-folder shim / `systemctl --user` /
    LaunchAgents) — no admin/sudo, matching a per-user gateway. Returns
    (ok, detail)."""
    if platform_key == "windows":
        # First choice: a direct /tr onlogon registration (NOT the XML
        # descriptor: its boot trigger needs admin). schtasks task creation is
        # itself denied from a non-elevated shell on some boxes, so on failure
        # fall back to a Startup-folder shim — a plain file write that always
        # works and runs the launcher minimized at logon.
        res = _run(["schtasks", "/create", "/tn", name,
                    "/tr", f'"{launcher_path}"', "/sc", "onlogon", "/f"], runner)
        if res.returncode == 0:
            started = _run(["schtasks", "/run", "/tn", name], runner).returncode == 0
            return True, ("scheduled task registered (onlogon)"
                          + (" + started" if started
                             else f' — start it: schtasks /run /tn "{name}"'))
        err = (res.stderr or res.stdout or "").strip() or "schtasks /create failed"
        startup_dir = _windows_startup_dir(home)
        try:
            startup_dir.mkdir(parents=True, exist_ok=True)
            shim = startup_dir / f"{name}.cmd"
            shim.write_text(
                f'@start "" /min "{launcher_path}"\n', encoding="utf-8")
        except OSError as exc:
            return False, f"{err}; startup-folder fallback also failed: {exc}"
        started = _spawn_detached(["cmd", "/c", str(launcher_path)])
        return True, (f"startup-folder shim registered at {shim} "
                      f"(schtasks denied: {err})"
                      + (" + started" if started else " — start it by running the launcher"))
    home = Path(home) if home else Path.home()
    if platform_key == "linux":
        unit_dir = home / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit = _bg.systemd_unit(name, str(launcher_path)).replace(
            "WantedBy=multi-user.target", "WantedBy=default.target")
        unit_path = unit_dir / f"{name}.service"
        unit_path.write_text(unit, encoding="utf-8")
        for cmd in (["systemctl", "--user", "daemon-reload"],
                    ["systemctl", "--user", "enable", "--now", name]):
            res = _run(cmd, runner)
            if res.returncode != 0:
                return False, (res.stderr or "").strip() or f"{' '.join(cmd)} failed"
        return True, f"user systemd unit enabled + started ({unit_path})"
    if platform_key == "darwin":
        agents_dir = home / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        plist_path = agents_dir / f"{name}.plist"
        plist_path.write_text(_bg.launchd_plist(name, [str(launcher_path)]),
                              encoding="utf-8")
        res = _run(["launchctl", "load", "-w", str(plist_path)], runner)
        if res.returncode != 0:
            return False, (res.stderr or "").strip() or "launchctl load failed"
        return True, f"launchd agent loaded ({plist_path})"
    return False, f"unsupported platform {platform_key!r}"


def unregister_gateway(
    platform_key: str,
    name: str = SERVICE_NAME,
    home: Optional[Path] = None,
    runner=None,
) -> tuple[bool, str]:
    """Stop + unregister the gateway (an absent registration is a no-op)."""
    if platform_key == "windows":
        _run(["schtasks", "/end", "/tn", name], runner)  # stop if running
        res = _run(["schtasks", "/delete", "/tn", name, "/f"], runner)
        shim = _windows_startup_dir(home) / f"{name}.cmd"
        shim_removed = False
        if shim.exists():
            try:
                shim.unlink()
                shim_removed = True
            except OSError:  # pragma: no cover
                pass
        if res.returncode == 0 and shim_removed:
            return True, "scheduled task + startup-folder shim removed"
        if res.returncode == 0:
            return True, "scheduled task stopped + removed"
        if shim_removed:
            return True, "startup-folder shim removed"
        return True, "not registered (no-op)"
    home = Path(home) if home else Path.home()
    if platform_key == "linux":
        _run(["systemctl", "--user", "disable", "--now", name], runner)
        unit_path = home / ".config" / "systemd" / "user" / f"{name}.service"
        if unit_path.exists():
            try:
                unit_path.unlink()
            except OSError:  # pragma: no cover
                pass
            _run(["systemctl", "--user", "daemon-reload"], runner)
            return True, "user systemd unit disabled + removed"
        return True, "not registered (no-op)"
    if platform_key == "darwin":
        plist_path = home / "Library" / "LaunchAgents" / f"{name}.plist"
        if plist_path.exists():
            _run(["launchctl", "unload", "-w", str(plist_path)], runner)
            try:
                plist_path.unlink()
            except OSError:  # pragma: no cover
                pass
            return True, "launchd agent unloaded + removed"
        return True, "not registered (no-op)"
    return False, f"unsupported platform {platform_key!r}"


def is_gateway_registered(
    platform_key: str,
    name: str = SERVICE_NAME,
    home: Optional[Path] = None,
    runner=None,
) -> bool:
    if platform_key == "windows":
        if _run(["schtasks", "/query", "/tn", name], runner).returncode == 0:
            return True
        return (_windows_startup_dir(home) / f"{name}.cmd").exists()
    home = Path(home) if home else Path.home()
    if platform_key == "linux":
        return (home / ".config" / "systemd" / "user" / f"{name}.service").exists()
    if platform_key == "darwin":
        return (home / "Library" / "LaunchAgents" / f"{name}.plist").exists()
    return False


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
    secondary_provider: str = "openai"
    secondary_model: str = DEFAULT_OPENAI_MODEL
    secondary_key_present: bool = False
    openai_key_present: bool = False
    anthropic_key_present: bool = False
    litellm_present: bool = False
    enabled: bool = False
    activated: bool = False
    # v3.40.0 ADV3C-1: a plain re-install carries a prior activation forward
    # (state honesty) — this flag lets the wording say so without claiming
    # THIS run performed an activation.
    activation_carried: bool = False
    registered: bool = False
    split_applied: bool = False
    # v3.40.0 ADV3C-1: the on-disk agents policy IS the split (e.g. carried
    # from a prior activation) even though THIS run did not apply it.
    split_on_disk: bool = False
    split_confirmed: Optional[bool] = None  # v3.39.0: live /v1/models verdict
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


def _recorded_secondary_alias(state: dict[str, Any]) -> str:
    """The alias the RECORDED gateway config routes: `secondary_alias`, falling
    back to the legacy `codex_alias`, else the current SECONDARY_ALIAS. Each
    candidate is trimmed BEFORE the truthiness check (ADV3B-2) so a corrupt
    whitespace-only value reads as absent — it never masks the legacy key and
    never becomes a literal-whitespace probe expectation."""
    for key in ("secondary_alias", "codex_alias"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return SECONDARY_ALIAS


def _default_agents_dir() -> Path:
    """The agents/ dir the model split targets (v3.39.0: runtime-first).

    Claude Code runs the INSTALLED plugin cache copy, not the dev checkout —
    a split applied to the repo's agents/ never reaches the runtime and is
    reverted by the next git operation (ship state is uniform fable). Resolve
    the installed copy via the lever; fall back to the repo agents/ when no
    installed copy exists (a --plugin-dir dev install, or tests)."""
    return _lever.runtime_agents_dir()


# --------------------------------------------------------------------------- #
# live split confirmation + gateway restart (v3.39.0)
# --------------------------------------------------------------------------- #
#
# The v3.38.1 field bug proved a generated config can be broken while every
# install step reports ok. The confirm step closes that gap: after a
# registered install the installer polls the LIVE gateway's /v1/models and
# asserts the ids the split needs are actually SERVED — the neutral secondary
# alias always (install probes the alias the just-written config routes;
# status --live instead probes the STATE-RECORDED alias, so a working legacy
# v3.39 config still confirms green), claude-fable-5 additionally in api-key
# mode. An already-running gateway that predates a
# config regeneration serves the OLD config; on a failed confirm the installer
# restarts the gateway once (through the same user-level registration
# machinery) and re-probes before degrading to a warn. Never gates.
FABLE_MODEL = ANTHROPIC_EXPLICIT_MODELS[0]  # "claude-fable-5"
CONFIRM_ATTEMPTS = 15   # litellm cold-start on a real Windows box takes ~10-30s
CONFIRM_DELAY = 2.0


def _http_models_probe(port: int, master_key: str, timeout: float = 5.0) -> list[str]:
    """GET the live gateway's /v1/models and return the served model ids.
    Raises on any transport/shape failure (the caller retries)."""
    req = urllib.request.Request(
        gateway_url(port) + "/v1/models",
        headers={"Authorization": f"Bearer {master_key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - localhost
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data", []) if isinstance(payload, dict) else []
    return [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]


_default_models_prober = _http_models_probe  # injectable seam — tests stub this


def confirm_gateway_serving(
    port: int,
    master_key: str,
    expect: list[str],
    prober=None,
    attempts: Optional[int] = None,
    delay: Optional[float] = None,
    sleeper=time.sleep,
) -> tuple[bool, str]:
    """Poll the live gateway until every id in ``expect`` is served, or the
    attempts run out. Returns ``(ok, detail)`` — detail names what's missing
    or why the gateway was unreachable. Never raises. ``attempts``/``delay``
    default to the module constants AT CALL TIME (tests monkeypatch them)."""
    prober = prober or _default_models_prober
    attempts = CONFIRM_ATTEMPTS if attempts is None else attempts
    delay = CONFIRM_DELAY if delay is None else delay
    last = "no probe attempted"
    for i in range(max(1, attempts)):
        try:
            served = prober(port, master_key)
            missing = [m for m in expect if m not in served]
            if not missing:
                return True, (
                    f"gateway serving {len(served)} model(s) incl. "
                    + ", ".join(expect))
            last = (f"gateway up but NOT serving {', '.join(missing)} "
                    f"(served: {', '.join(served) or 'none'})")
        except Exception as exc:
            last = f"gateway unreachable at {gateway_url(port)} ({exc})"
        if i < attempts - 1:
            sleeper(delay)
    return False, last


def restart_gateway(
    platform_key: str,
    launcher_path: Path,
    name: str = SERVICE_NAME,
    runner=None,
) -> tuple[bool, str]:
    """Restart the gateway so a regenerated config takes effect. User-level on
    every OS (schtasks /end+/run, `systemctl --user restart`, `launchctl
    kickstart -k`) — never sudo/admin; the Startup-folder-shim case falls back
    to a detached launcher spawn. Returns (ok, detail)."""
    if platform_key == "windows":
        _run(["schtasks", "/end", "/tn", name], runner)  # stop if task-managed
        if _run(["schtasks", "/run", "/tn", name], runner).returncode == 0:
            return True, "scheduled task restarted"
        ok = _spawn_detached(["cmd", "/c", str(launcher_path)])
        return ok, ("launcher restarted (detached)" if ok
                    else "restart failed (no schtasks task; detached spawn failed)")
    if platform_key == "linux":
        res = _run(["systemctl", "--user", "restart", name], runner)
        if res.returncode == 0:
            return True, "user systemd unit restarted"
        return False, (res.stderr or "").strip() or "systemctl --user restart failed"
    if platform_key == "darwin":
        getuid = getattr(os, "getuid", None)
        uid = getuid() if getuid else 501
        res = _run(["launchctl", "kickstart", "-k", f"gui/{uid}/{name}"], runner)
        if res.returncode == 0:
            return True, "launchd agent restarted"
        return False, (res.stderr or "").strip() or "launchctl kickstart failed"
    return False, f"unsupported platform {platform_key!r}"


SUBSCRIPTION_MODE_NOTE = (
    "subscription mode — no ANTHROPIC_API_KEY resolved, so Anthropic models "
    "(fable) keep Claude Code's native sign-in auth: ANTHROPIC_BASE_URL is NOT "
    "written and the secondary role split stays OFF (the harness cannot route "
    "only secondary traffic through the gateway while sign-in auth handles the "
    "rest). The gateway still serves the chosen secondary provider to direct "
    "callers. For the full gateway + secondary split: set ANTHROPIC_API_KEY and "
    "re-run install --activate."
)


# --------------------------------------------------------------------------- #
# subcommand handlers
# --------------------------------------------------------------------------- #

def _cmd_install(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="install", base_dir=str(base),
                    check_only=bool(args.check_only))
    allow_provider_prompt = bool(
        getattr(args, "interactive_prompts", False)
        and not args.check_only and not getattr(args, "json", False))
    provider, provider_source, provider_error = resolve_secondary_provider(
        getattr(args, "secondary", None), base,
        re_ask=bool(getattr(args, "re_ask_provider", False)),
        interactive=allow_provider_prompt,
    )
    if provider_error or provider is None:
        report.add("secondary", "fail", provider_error or "provider resolution failed")
        return report
    report.secondary_provider = provider
    entry = SECONDARY_PROVIDERS[provider]
    if args.openai_model is not None:
        if provider != "openai":
            report.add(
                "secondary", "fail",
                "--openai-model is scoped to --secondary openai; use --secondary-model")
            return report
        print("NOTE: --openai-model is deprecated; use --secondary-model.", file=sys.stderr)
    report.secondary_model = (
        args.secondary_model or args.openai_model or str(entry["model"]))
    provider_args = {
        name: getattr(args, f"{name}_key", None)
        for name in SECONDARY_PROVIDERS
    }
    keys = resolve_keys(
        base, anthropic_arg=args.anthropic_key,
        secondary_provider=provider, provider_args=provider_args)
    provider_env = str(entry["key_env"])
    report.secondary_key_present = bool(keys.get(provider_env))
    report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
    report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
    report.auth_mode = resolve_auth_mode(keys)
    report.litellm_present = litellm_installed()

    if args.check_only:
        would = "api-key (full gateway)" if report.auth_mode == AUTH_MODE_API_KEY \
            else "subscription (fable via sign-in; gateway secondary-only)"
        report.add("check-only", "skipped",
                   f"would install in {would} mode; "
                   f"secondary={provider}/{report.secondary_model} ({provider_source}); "
                   "no state provisioned")
        return report

    # 0a. decline bookkeeping (v3.38.0): a slot's decline auto-resets whenever
    # that slot's key resolves on any path (args > env > gateway.env — checked
    # here, the resolve_keys caller, so resolution stays pure); --re-ask-keys
    # clears the whole record so prompts fire again.
    if getattr(args, "re_ask_keys", False):
        _clear_declines(base)
    for slot, env_key in provider_key_slots(provider):
        if keys.get(env_key):
            _clear_declines(base, slot)

    # 0b. interactive key prompt (v3.38.0 ask-then-apply): fires ONLY for an
    # interactive caller (--interactive-prompts) on a real TTY — never under
    # --check-only (already returned) or --json — and per slot only when
    # unresolved and not declined, openai then anthropic (D1 order). A captured
    # key folds into `keys` BEFORE write_env_file, so 0600 / masking /
    # config-reference behavior is inherited unchanged. Blank skips: today's
    # absent-key path runs verbatim and the decline is recorded.
    if (getattr(args, "interactive_prompts", False)
            and not getattr(args, "json", False) and _default_isatty_fn()):
        declines = _read_declines(base)
        for slot, env_key in provider_key_slots(provider):
            if keys.get(env_key):
                continue
            if slot in declines:
                report.add("prompt", "skipped",
                           f"{slot}: previously declined "
                           f"(via={declines[slot].get('via', 'unknown')}) -- not "
                           f"re-asking; pass --re-ask-keys to prompt again")
                continue
            entered = _prompt_for_key(slot)
            if entered:
                keys[env_key] = entered
                report.add("prompt", "ok",
                           f"{env_key} captured interactively "
                           f"({_mask(entered)}); raw value stored only in gateway.env")
            else:
                _record_decline(base, slot, via="prompt-skip")
                report.add("prompt", "skipped",
                           f"{slot}: blank entry -- skipped; decline recorded "
                           f"(via=prompt-skip; --re-ask-keys re-prompts)")
        report.secondary_key_present = bool(keys.get(provider_env))
        report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
        report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
        report.auth_mode = resolve_auth_mode(keys)

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
    # ADV3-2: merge, never replace — a provider switch must not delete the
    # OTHER provider's stored key. Every preserved slot (each registry
    # provider's key_env + Anthropic + master) carries forward; the freshly
    # resolved values win.
    existing_env = read_env_file(base / ENV_FILE_NAME)
    persisted = {k: v for k, v in existing_env.items()
                 if k in preserved_env_keys()}
    persisted.update(keys)
    write_env_file(base / ENV_FILE_NAME, persisted)
    # honesty: the report's openai flag reflects the FILE (a retained OpenAI
    # key on a zai run is still present), matching what status reports.
    report.openai_key_present = bool(persisted.get("OPENAI_API_KEY"))
    report.add("secrets", "ok",
               f"gateway.env written ({provider_env}: "
               f"{_mask(keys.get(provider_env)) or 'ABSENT'}, ANTHROPIC_API_KEY: "
               f"{_mask(keys.get('ANTHROPIC_API_KEY')) or 'absent — subscription mode'})")

    # 3. config + launcher + state.
    (base / CONFIG_NAME).write_text(
        build_gateway_config(
            report.auth_mode, SECONDARY_ALIAS, report.secondary_model, provider),
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

    # 3b. serving-side consistency (v3.40.0 ADV3B-1): the config just written
    # routes ONLY the neutral alias, so an on-disk LEGACY split would 404 the
    # moment that config is (re)loaded. Migrating it to the neutral alias in
    # the SAME run — with or without --activate — is consistency maintenance
    # of an already-activated machine, not a new activation.
    # migrate_legacy_split rewrites ONLY files carrying a legacy alias, so a
    # split-neutral machine (a fresh install, a manual lever state) never has
    # its agents touched. prior_state is read here, BEFORE this run's state
    # write, so a non-activate install can carry forward what it does not
    # change (only uninstall downgrades activated/model_policy).
    prior_state = _read_state(base)
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    migrated: list[str] = []
    if agents_dir.is_dir():
        migrated = _lever.migrate_legacy_split(agents_dir)
        if migrated:
            report.add("alias-migration", "ok",
                       f"{len(migrated)} agent file(s) migrated from a legacy "
                       f"secondary alias to {SECONDARY_ALIAS} in {agents_dir} "
                       f"(the regenerated {CONFIG_NAME} routes only the "
                       f"neutral alias)")
        # ADV3C-1: record whether the disk policy IS the split (e.g. carried
        # from a prior activation) so the confirm wording can be honest about
        # a split this run did not itself apply.
        report.split_on_disk = (
            _lever.policy_state(agents_dir) == POLICY_SECONDARY_SPLIT)
    elif not args.activate:
        # ADV3C-4: never skip step 3b silently — the --activate path already
        # surfaces a missing/typo'd agents dir (its secondary-split row); the
        # plain path gets the symmetric row.
        report.add("alias-migration", "skipped",
                   f"agents dir not found at {agents_dir} — legacy-alias "
                   f"migration not performed; check --agents-dir or apply the "
                   f"split manually: python scripts/setup/set_default_model.py "
                   f"--split secondary")

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

    # 5. enablement: only the chosen provider's key controls the secondary route.
    report.enabled = report.secondary_key_present
    if not report.enabled:
        provider_flag = f"--{provider}-key"
        report.remediation = (
            f"set {provider_env} (env) or re-run with {provider_flag} …; state dir: {base}")
        report.add("enable", "skipped",
                   f"no {provider} key resolved; provisioned but NOT enabled")
    else:
        report.add("enable", "ok", "gateway enabled")

    # 5b. auto-registration (v3.37.0): the installer registers + starts the
    # gateway itself (user-level; --no-register opts back to the printed hint).
    if args.no_register:
        report.add("register", "skipped",
                   "--no-register — register manually with the printed hint")
    elif not report.enabled:
        report.add("register", "skipped",
                   f"not enabled (no {provider_env}) — registration deferred")
    else:
        reg_ok, reg_detail = register_gateway(
            _platform_key(), base / launcher_name)
        report.registered = reg_ok
        if reg_ok:
            report.add("register", "ok", reg_detail)
        else:
            report.add("register", "fail",
                       f"{reg_detail} — register manually: {descriptor['register_hint']}")

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
            # legacy-alias files were already migrated at step 3b (the same-run
            # consistency pass); apply_split then repairs any remaining drift.
            if agents_dir.is_dir():
                changed = _lever.apply_split(agents_dir)
                report.split_applied = True
                report.add("secondary-split", "ok",
                           f"role split applied to {agents_dir} "
                           f"({len(changed)} policy rewrite(s), {len(migrated)} legacy "
                           f"alias migration(s); dev/checking/testing agents → "
                           f"{SECONDARY_ALIAS})")
            else:
                report.add("secondary-split", "skipped",
                           f"agents dir not found at {agents_dir}; apply manually: "
                           f"python scripts/setup/set_default_model.py --split secondary")
        elif report.auth_mode == AUTH_MODE_SUBSCRIPTION:
            report.add("activate", "skipped", SUBSCRIPTION_MODE_NOTE)
        else:
            report.add("activate", "skipped",
                       f"cannot activate: no {provider_env} (see enable remediation)")
    elif report.auth_mode == AUTH_MODE_SUBSCRIPTION:
        report.add("mode", "ok", SUBSCRIPTION_MODE_NOTE)
    elif prior_state.get("activated"):
        # ADV3C-1: this plain install neither activated nor deactivated —
        # the machine's prior activation carries forward (step 8 records it),
        # so the row must not read as "unactivated; needs consent".
        report.activation_carried = True
        report.add("activate", "ok",
                   "activation carried forward from the prior install "
                   "(settings.json untouched this run; uninstall is the only "
                   "downgrade path)")

    # 7. live confirmation (v3.39.0): assert the RUNNING gateway actually
    # serves the ids the split needs — the step the v3.38.1 field bug proved
    # necessary (a broken config passed every install step). Only when this
    # run registered/started the gateway (--no-register opts out of the
    # probe too — that pin means NO schtasks at all); a stale process serving
    # a pre-regeneration config gets ONE restart + re-probe before the honest
    # warn. Never gates.
    if report.enabled and report.registered:
        expect = [SECONDARY_ALIAS]
        if report.auth_mode == AUTH_MODE_API_KEY:
            expect.append(FABLE_MODEL)
        ok, detail = confirm_gateway_serving(
            args.port, keys[MASTER_KEY_VAR], expect)
        if not ok:
            restarted, r_detail = restart_gateway(
                _platform_key(), base / launcher_name)
            if restarted:
                ok, detail = confirm_gateway_serving(
                    args.port, keys[MASTER_KEY_VAR], expect)
                detail = f"{detail} (after restart: {r_detail})"
            else:
                detail = f"{detail}; restart attempt failed: {r_detail}"
        report.split_confirmed = ok
        if ok:
            # ADV3C-1: the split phrasing also applies when the disk policy is
            # a CARRIED split (this run confirmed it live without applying it).
            report.add("confirm", "ok",
                       ("CONFIRMED: CT6 runs the split — "
                        if report.split_applied or report.split_on_disk
                        else "CONFIRMED: ") + detail)
        else:
            report.add("confirm", "fail",
                       f"{detail} — verify keys in {base / ENV_FILE_NAME}, then "
                       f"restart the gateway and re-check: python "
                       f"scripts/setup/install_gateway.py status --live")
    elif report.enabled:
        report.add("confirm", "skipped",
                   "gateway not started this run (registration skipped or "
                   "failed) — start it, then verify: python "
                   "scripts/setup/install_gateway.py status --live")

    # 8. state (v3.40.0 ADV3B-1, carry-forward): a non-activate install
    # neither activated nor deactivated anything, so the prior `activated` and
    # a prior split `model_policy` carry FORWARD instead of downgrading —
    # uninstall (and a future explicit deactivate) is the ONLY downgrade path.
    # This keeps the SessionStart self-heal armed and `status --live` truthful
    # on an already-activated machine (and closes ADV3B-5, the modern-machine
    # heal-disarm on a plain re-install). The `{**prior_state}` merge carries
    # every key this run does not rewrite. `secondary_alias` records what the
    # just-regenerated config routes; step 3b migrated any on-disk legacy
    # split to that alias in the same run, so the record mirrors the disk.
    prior_split_desired = prior_state.get("model_policy") in (
        POLICY_SECONDARY_SPLIT, LEGACY_POLICY_CODEX_SPLIT)
    _write_state(base, {
        **prior_state,
        "auth_mode": report.auth_mode,
        "port": args.port,
        "secondary_provider": provider,
        "secondary_model": report.secondary_model,
        "secondary_alias": SECONDARY_ALIAS,
        "codex_alias": SECONDARY_ALIAS,
        # Preserve the grandfather marker for one transition version.
        "openai_model": report.secondary_model if provider == "openai" else None,
        "activated": bool(report.activated or prior_state.get("activated")),
        "enabled": report.enabled,
        "registered": report.registered,
        "model_policy": POLICY_SECONDARY_SPLIT
        if (report.split_applied or prior_split_desired)
        else POLICY_UNIFORM_FABLE,
    })
    return report


def _cmd_status(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="status", base_dir=str(base))
    state = _read_state(base)
    provider, _, error = resolve_secondary_provider(
        getattr(args, "secondary", None), base, re_ask=False, interactive=False)
    if error or provider is None:
        report.add("secondary", "fail", error or "provider resolution failed")
        return report
    entry = SECONDARY_PROVIDERS[provider]
    provider_env = str(entry["key_env"])
    report.secondary_provider = provider
    report.secondary_model = str(
        state.get("secondary_model") or state.get("openai_model") or entry["model"])
    keys = read_env_file(base / ENV_FILE_NAME)
    port = int(state.get("port", args.port))
    report.secondary_key_present = bool(keys.get(provider_env))
    report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
    report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
    report.auth_mode = state.get("auth_mode", resolve_auth_mode(keys))
    report.litellm_present = litellm_installed()
    report.enabled = report.secondary_key_present and (base / CONFIG_NAME).is_file()
    settings_path = Path(args.settings_path) if args.settings_path \
        else _setup.DEFAULT_USER_SETTINGS_PATH
    report.activated = claude_env_applied(settings_path, port)
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    report.descriptor_path = str(descs[0]) if descs else None
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    policy = _lever.policy_state(agents_dir) if agents_dir.is_dir() else "unknown"
    report.split_applied = policy == POLICY_SECONDARY_SPLIT
    report.registered = is_gateway_registered(_platform_key())
    if not report.secondary_key_present:
        report.remediation = (
            f"set {provider_env} or re-run install --{provider}-key …")
    summary = (
        f"mode={report.auth_mode}; secondary={provider}/{report.secondary_model}; "
        f"enabled={report.enabled}; activated={report.activated}; "
        f"registered={report.registered}; litellm={report.litellm_present}; "
        f"model-policy={policy}; {provider_env}="
        f"{_mask(keys.get(provider_env)) or 'absent'}; "
        f"ANTHROPIC_API_KEY={_mask(keys.get('ANTHROPIC_API_KEY')) or 'absent'}")
    # v3.38.0: report recorded declines — the decline suppresses the PROMPT,
    # never the truth (the absent-key fields above stay verbatim).
    declines = _read_declines(base)
    if declines:
        summary += f"; declined={','.join(sorted(declines))}"
    report.add("status", "ok", summary)
    report.add("agents", "ok", f"model policy read from {agents_dir}")
    # v3.39.0: --live probes the RUNNING gateway's /v1/models and reports
    # whether it serves what the current mode needs (one attempt burst, no
    # restart — status observes, install repairs).
    if getattr(args, "live", False):
        if report.enabled:
            # ADV3-3: expect the STATE-RECORDED alias — a working legacy
            # (v3.39) install whose config routes only codex-5.6-sol must
            # probe green; a hard-coded newest alias false-failed it.
            # ADV3B-2: whitespace-trimmed via _recorded_secondary_alias, so a
            # corrupt whitespace value never masks the legacy key.
            expect = [_recorded_secondary_alias(state)]
            if report.auth_mode == AUTH_MODE_API_KEY:
                expect.append(FABLE_MODEL)
            ok, detail = confirm_gateway_serving(
                port, keys.get(MASTER_KEY_VAR, ""), expect, attempts=3)
            report.split_confirmed = ok
            report.add("confirm", "ok" if ok else "fail",
                       (("CONFIRMED: CT6 runs the split — " if report.split_applied
                         else "CONFIRMED: ") + detail) if ok
                       else f"{detail} — restart the gateway or re-run install")
        else:
            report.add("confirm", "skipped",
                       "gateway not enabled — nothing to probe")
    return report


def _cmd_uninstall(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="uninstall", base_dir=str(base),
                    check_only=bool(args.check_only))
    state = _read_state(base)
    port = int(state.get("port", args.port))

    if args.check_only:
        report.add("check-only", "skipped",
                   "would deactivate settings.json, restore uniform fable if the "
                   "codex split is applied, stop + unregister the gateway, and "
                   "remove the boot descriptor; nothing touched")
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

    # 2. restore from current or legacy split state. policy_state recognizes a
    # complete legacy-alias split as secondary-split; the recorded legacy policy
    # is an additional mixed-version guard.
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    disk_policy = _lever.policy_state(agents_dir) if agents_dir.is_dir() else "unknown"
    recorded_policy = state.get("model_policy")
    wants_restore = disk_policy == POLICY_SECONDARY_SPLIT or recorded_policy in {
        POLICY_SECONDARY_SPLIT, LEGACY_POLICY_CODEX_SPLIT}
    if agents_dir.is_dir() and wants_restore:
        changed = _lever.set_model(agents_dir, "fable")
        report.add("model-restore", "ok",
                   f"uniform fable restored ({len(changed)} file(s) rewritten)")
    else:
        report.add("model-restore", "skipped",
                   "model state is not a secondary split (left untouched)")

    # 3. unregistration (v3.37.0: EXECUTED, symmetric with install) +
    #    descriptor removal.
    unreg_ok, unreg_detail = unregister_gateway(_platform_key())
    report.add("unregister", "ok" if unreg_ok else "fail", unreg_detail)
    if not unreg_ok:
        report.register_hint = {
            "linux": f"systemctl --user disable --now {SERVICE_NAME}",
            "darwin": f"launchctl unload -w ~/Library/LaunchAgents/{SERVICE_NAME}.plist",
            "windows": f'schtasks /delete /tn "{SERVICE_NAME}" /f',
        }[_platform_key()]
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    if descs:
        for d in descs:
            try:
                d.unlink()
            except OSError:  # pragma: no cover
                pass
        report.add("descriptor", "ok", "boot descriptor removed")
    else:
        report.add("descriptor", "skipped", "no boot descriptor present (no-op)")

    if args.purge:
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
            report.add("purge", "ok", f"removed state dir {base}")
        else:
            report.add("purge", "skipped", "state dir already absent (no-op)")
    elif state:
        # v3.39.0: record the deactivated state so the sessionstart self-heal
        # never re-applies a split the user uninstalled.
        _write_state(base, {**state, "activated": False,
                            "model_policy": POLICY_UNIFORM_FABLE})
    return report


def _cmd_decline(args: argparse.Namespace, base: Path) -> Report:
    """Record (or --clear) a wrapper-level key decline — the deterministic
    channel for the slash-command flow's AskUserQuestion decline disposition
    (v3.38.0 D3; the wrapper cannot type into a stdin prompt)."""
    report = Report(action="decline", base_dir=str(base))
    state = _read_state(base)
    report.auth_mode = state.get("auth_mode", report.auth_mode)
    report.enabled = bool(state.get("enabled", False))
    report.registered = bool(state.get("registered", False))
    slot = args.slot
    if getattr(args, "clear", False):
        if _clear_declines(base, slot):
            report.add("decline", "ok",
                       f"{slot}: decline cleared -- the installer may prompt again")
        else:
            report.add("decline", "skipped", f"{slot}: no decline recorded (no-op)")
        return report
    _record_decline(base, slot, via="wrapper")
    report.add("decline", "ok",
               f"{slot}: decline recorded (via=wrapper) -- the installer will not "
               f"prompt for this key; undo with `decline {slot} --clear` or "
               f"install --re-ask-keys")
    return report


_HANDLERS = {
    "install": _cmd_install,
    "status": _cmd_status,
    "uninstall": _cmd_uninstall,
    "decline": _cmd_decline,
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
    interactive: Optional[bool] = None,
    secondary: Optional[str] = None,
) -> tuple[str, str, Optional[str]]:
    """The setup.py hook: run install (enable=True) or uninstall (enable=False)
    and fold the result into one (name, status, detail) report row. NEVER raises
    and never gates setup — any failure (including a raising prompt seam)
    degrades to a 'warn' row with the manual remediation (the same posture as
    apply_model_policy).

    v3.38.0: passes interactivity through — `--interactive-prompts` is appended
    ONLY when NOT assume_yes AND NOT check_only AND stdin is a TTY. `interactive`
    is an explicit override for callers that already resolved it (setup.py
    forwards --no-prompt as False); the assume_yes/check_only guards are
    unconditional either way."""
    name = "external-llm (LiteLLM gateway)"
    manual = "python scripts/setup/install_gateway.py install --activate"
    try:
        base = resolve_base_dir(base_dir)
        argv = ["install" if enable else "uninstall", "--base-dir", str(base)]
        if secondary is not None:
            argv += ["--secondary", secondary]
        if check_only:
            argv.append("--check-only")
        if enable and assume_yes:
            # --activate writes settings.json + the model split; consent came
            # from --yes / CT6_SETUP_ASSUME_YES (the setup consent convention).
            argv.append("--activate")
        if enable and not assume_yes and not check_only:
            allow = interactive if interactive is not None else _default_isatty_fn()
            if allow:
                argv.append("--interactive-prompts")
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
        # ADV3C-1: a carried-forward activation must not read as "unactivated"
        # (the machine stays activated + split; this run just did not
        # RE-activate it — no activation is claimed for this run).
        activated_display = ("carried-forward"
                             if report.activation_carried and not report.activated
                             else report.activated)
        summary = (
            f"mode={report.auth_mode}; secondary={report.secondary_provider}/"
            f"{report.secondary_model}; enabled={report.enabled}; "
            f"activated={activated_display}"
            + ("; secondary split applied" if report.split_applied else "")
            + ("; CONFIRMED live — CT6 runs the split"
               if report.split_confirmed
               and (report.split_applied or report.split_on_disk)
               else "; CONFIRMED serving live" if report.split_confirmed
               else "; live confirmation FAILED (see confirm step)"
               if report.split_confirmed is False else "")
            + (f"; NOT enabled — {report.remediation}" if report.remediation else "")
        )
        if report.auth_mode == AUTH_MODE_SUBSCRIPTION:
            # Provider-neutral: the served-provider prose is single-sourced
            # from the lever registry entry (label carries provider + model),
            # never a hand-written per-provider string.
            entry = SECONDARY_PROVIDERS.get(report.secondary_provider, {})
            served = str(entry.get("label") or report.secondary_provider)
            summary += f" (fable via Claude sign-in; gateway serves {served} only)"
        elif (report.enabled and not report.activated
                and not report.activation_carried):
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
    provider_names = "|".join(sorted(SECONDARY_PROVIDERS))
    parser.add_argument("--secondary", default=None,
                        help=f"secondary provider name ({provider_names})")
    parser.add_argument("--secondary-model", default=None,
                        help="upstream model id override for the chosen secondary provider")
    for name, entry in SECONDARY_PROVIDERS.items():
        parser.add_argument(
            f"--{name}-key", default=None,
            help=f"{entry['label']} API key to store in gateway.env")
    parser.add_argument("--anthropic-key", default=None,
                        help="Anthropic API key to store in gateway.env (api-key mode)")
    parser.add_argument("--openai-model", default=None,
                        help="deprecated synonym for --secondary-model with --secondary openai")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"gateway port (default: {DEFAULT_PORT})")
    parser.add_argument("--activate", action="store_true",
                        help="api-key mode: write the Claude Code env block + "
                             "apply the secondary role split")
    parser.add_argument("--settings-path", default=None,
                        help="Claude settings.json path (default: ~/.claude/settings.json)")
    parser.add_argument("--agents-dir", default=None,
                        help="agents/ dir for the model split (default: the INSTALLED "
                             "plugin copy's agents/, else the repo's agents/)")
    parser.add_argument("--no-install", action="store_true",
                        help="skip the pip install (state-only provisioning)")
    parser.add_argument("--no-register", action="store_true",
                        help="skip the automatic boot registration (print the hint instead)")
    parser.add_argument("--interactive-prompts", action="store_true",
                        help="allow the interactive missing-key prompt (set only by "
                             "interactive callers: a TTY main() run or an interactive "
                             "setup run; never under --check-only/--json)")
    parser.add_argument("--re-ask-keys", action="store_true",
                        help="clear the recorded key declines so prompts fire again")
    parser.add_argument("--re-ask-provider", action="store_true",
                        help="ignore the recorded provider and ask/select it again")
    parser.add_argument("--force-reinstall", action="store_true",
                        help="reinstall litellm even when already importable")
    parser.add_argument("--check-only", action="store_true",
                        help="report intent only; provision nothing")
    parser.add_argument("--live", action="store_true",
                        help="(status) probe the RUNNING gateway's /v1/models and "
                             "confirm it serves what the mode needs")
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
    dec = sub.add_parser("decline", parents=[shared], add_help=False)
    dec.add_argument("slot", choices=("anthropic", *SECONDARY_PROVIDERS),
                     help="the key slot to decline (anthropic or a secondary provider)")
    dec.add_argument("--clear", action="store_true",
                     help="clear the recorded decline for the slot instead")
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
    # v3.38.0 (D1): a DIRECT terminal run is an interactive caller — main()
    # opts into prompting when stdin is a real TTY and neither --json nor
    # --check-only is present, so a direct install never stays punt-only.
    # setup_entry appends the flag itself; the handler never prompts without it.
    if (command == "install" and not args.interactive_prompts
            and not args.check_only and not getattr(args, "json", False)
            and _default_isatty_fn()):
        args.interactive_prompts = True
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
            "secondary_provider": report.secondary_provider,
            "secondary_model": report.secondary_model,
            "secondary_key_present": report.secondary_key_present,
            "openai_key_present": report.openai_key_present,
            "anthropic_key_present": report.anthropic_key_present,
            "litellm_present": report.litellm_present,
            "enabled": report.enabled,
            "activated": report.activated,
            "registered": report.registered,
            "split_applied": report.split_applied,
            "split_confirmed": report.split_confirmed,
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
    print(f"  Secondary:   {report.secondary_provider}/{report.secondary_model}")
    print(f"  Gateway:     {'enabled' if report.enabled else 'provisioned but NOT enabled'}"
          f"; auto-registered: {'yes' if report.registered else 'no'}"
          f"; Claude Code activation: "
          f"{'applied' if report.activated else 'carried forward (prior install)' if report.activation_carried else 'not applied'}")
    if report.register_hint and not report.registered:
        print("  Manual registration hint (auto-registration was skipped or failed):")
        print(f"    {report.register_hint}")
    if report.remediation:
        print(f"  Remediation: {report.remediation}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
