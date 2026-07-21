#!/usr/bin/env python3
"""install_librarian.py — the full-lifecycle installer for the CT6 Librarian.

Run from `/architect-team:librarian-install`. Stdlib-only (the `anthropic` SDK
stays a LAZY import behind `services/common/service_config.py`). Mirrors the
`install_mempalace.py` pattern: a step-summary printer, `--json`, `--check-only`,
and the same "never auto-register / never auto-enable without a key" safety
posture.

Subcommands:
  install (default)  Provision the state layout + config + topic registry + the
                     boot descriptor. Enable the daemon ONLY when an Anthropic key
                     resolves (or `--enable` is passed); otherwise install-but-
                     disabled with the explicit `--enable` remediation.
  status             Report descriptor-installed / key-present / enabled-or-degraded
                     / registered topics (+ per-topic last-run when available).
  add-topic NAME URL...   Add a topic -> URL(s) to the registry (idempotent).
  remove-topic NAME       Remove a topic from the registry (idempotent).
  list-topics             List the registered topics.
  run-once           ONE synchronous fetch->extract->index->metadata cycle over all
                     topics, foreground (no daemon). Reports per-topic counts.
  uninstall          Remove the boot descriptor (print the unregister hint). With
                     `--purge`, also remove the state dir. Never errors if absent.
  decline            Record an explicit decline of the Anthropic key prompt (the
                     wrapper's AskUserQuestion channel, v3.38.0); `--clear` clears
                     the recorded decline instead.

Flags:
  --base-dir PATH    The librarian state dir (default: $CT6_LIBRARIAN_HOME, else
                     ~/.architect-team/librarian/). No hardcoded home in the core.
  --enable           (re)enable the daemon after a key is added (re-write + hint).
  --check-only       Report intent only; do not provision.
  --json             Emit a machine-readable JSON status report.
  --interactive-prompts  Allow the hidden stdin key prompt on an interactive TTY
                     (v3.38.0; auto-set for a direct TTY `install` run without
                     --json/--check-only).
  --re-ask-keys      Clear the key-declines.json record so the prompt fires again.

Exit codes:
  0  success.
  1  a real failure (with an actionable message).

HONEST BOUNDARY: this provisions state + GENERATES the per-OS boot descriptor and
PRINTS the register hint — it NEVER loads/registers the descriptor and NEVER
`pip install anthropic`. With no key it provisions but does NOT enable; nothing is
ever described as "running" / "deployed" / "in production".
"""
from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    """Load an in-repo module by file path (services/ has no __init__.py, so this
    keeps the installer stdlib-only + robust when run from the slash command)."""
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / rel)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {name} from {rel}")
    mod = importlib.util.module_from_spec(spec)
    # Register before executing (the normal loader contract) so any module that
    # uses @dataclass resolves field types via sys.modules.get(__module__).
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Reused substrate (deterministic, stdlib-only; anthropic stays lazy inside).
_service_config = _load("service_config", "services/common/service_config.py")
_bg = _load("bg_runtime", "services/common/bg_runtime.py")
_library_index = _load("library_index", "services/librarian/library_index.py")
_librarian = _load("librarian", "services/librarian/librarian.py")
_daemon = _load("librarian_daemon", "services/librarian/daemon.py")
# The capability-gated CLAUDE.md guidance-block helper (stdlib-only sibling).
_guidance = _load("ct6_guidance_blocks", "scripts/setup/guidance_blocks.py")

# Layout constants are owned by the daemon module so the two agree.
CONFIG_NAME = _daemon.CONFIG_NAME
TOPICS_NAME = _daemon.TOPICS_NAME
INDEX_NAME = _daemon.INDEX_NAME
BODIES_DIR = _daemon.BODIES_DIR
METADATA_DIR = _daemon.METADATA_DIR
LOG_NAME = _daemon.LOG_NAME

ENV_HOME = "CT6_LIBRARIAN_HOME"
DESCRIPTOR_DIRNAME = "descriptor"
SERVICE_NAME = "ct6-librarian"
DEFAULT_INTERVAL_SECONDS = _daemon.DEFAULT_INTERVAL_SECONDS
DECLINES_NAME = "key-declines.json"  # v3.38.0 — the per-key decline record (D2)

# Capability-gated CLAUDE.md guidance block: written to a target project's
# CLAUDE.md (via --claude-md) only when the capability is verified, and removed
# on uninstall / purge. The slug keys the fence pair.
GUIDANCE_CAPABILITY = "librarian"
GUIDANCE_ENABLED_BODY = (
    "## Librarian topics (CT6)\n"
    "The CT6 Librarian background research service is installed and enabled for\n"
    "this project. It curates per-topic reference material on a schedule. Use it:\n"
    "register topics with `librarian-install add-topic <name> <url>...`, list\n"
    "them with `list-topics`, and read the per-topic metadata the service writes\n"
    "for grounded, current context before researching a topic from scratch."
)
GUIDANCE_DISABLED_BODY = (
    "## Librarian topics (CT6 — provisioned, not enabled)\n"
    "The CT6 Librarian background research service is provisioned for this\n"
    "project but NOT enabled (no API key resolved), so curated topic research is\n"
    "not yet available. To enable it, set an API key and re-run the installer\n"
    "with `--enable` (see the installer's printed remediation)."
)


# --------------------------------------------------------------------------- #
# base-dir resolution (no hardcoded home in the testable core)
# --------------------------------------------------------------------------- #

def resolve_base_dir(explicit: Optional[str], env: Optional[dict[str, str]] = None) -> Path:
    """Resolve the state base dir: explicit `--base-dir` > `$CT6_LIBRARIAN_HOME` >
    `~/.architect-team/librarian/`. The home default is only reached when neither
    override is set — tests always inject one of the first two."""
    env = os.environ if env is None else env
    if explicit:
        return Path(explicit)
    from_env = env.get(ENV_HOME)
    if from_env:
        return Path(from_env)
    return Path.home() / ".architect-team" / "librarian"


def _platform_key() -> str:
    """Map the running platform to bg_runtime's descriptor platform key."""
    return {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}.get(
        platform.system(), "linux")


def _daemon_command(base: Path) -> str:
    """The program the boot descriptor runs: `<python> <abs daemon.py> --base-dir
    <state>`. A path script (services/ has no __init__.py — NOT `python -m`)."""
    py = sys.executable or "python3"
    daemon_path = _REPO_ROOT / "services" / "librarian" / "daemon.py"
    return f'{py} {daemon_path} --base-dir {base}'


# --------------------------------------------------------------------------- #
# key-declines record + interactive key prompt (v3.38.0 — setup-key-prompting)
# --------------------------------------------------------------------------- #

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _mask(secret: Optional[str]) -> Optional[str]:
    """Mask a secret to its last 4 chars for report lines (the same shape as
    scripts/setup/install_gateway.py — a raw key never appears in output)."""
    if not secret:
        return None
    return ("…" + secret[-4:]) if len(secret) >= 4 else "set"


def _read_declines(base: Path) -> dict[str, Any]:
    path = base / DECLINES_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_declines(base: Path, declines: dict[str, Any]) -> None:
    """Persist the decline record; an empty record removes the file (an absent
    file means no declines — the pre-v3.38.0 state, per the migration note)."""
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


def _record_decline(base: Path, slot: str = "anthropic",
                    via: str = "prompt-skip") -> None:
    declines = _read_declines(base)
    declines[slot] = {"declined_at": _utc_now_iso(), "via": via}
    _write_declines(base, declines)


def _clear_declines(base: Path, slot: Optional[str] = None) -> None:
    if slot is None:
        _write_declines(base, {})
        return
    declines = _read_declines(base)
    if slot in declines:
        del declines[slot]
        _write_declines(base, declines)


def _default_isatty() -> bool:
    """Module-level TTY probe so tests inject TTY-ness; never raises."""
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def _hidden_prompt(text: str) -> str:
    """Hidden (never-echoed) key entry via stdlib getpass. Module-level so tests
    inject it; raising here routes _prompt_for_key to the visible fallback."""
    return getpass.getpass(text)


def _visible_input(text: str) -> str:
    return input(text)


def _prompt_for_key(
    slot: str = "anthropic",
    *,
    prompt_fn: Optional[Callable[[str], str]] = None,
    isatty_fn: Optional[Callable[[], bool]] = None,
    input_fn: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    """The v3.38.0 interactive key prompt — the librarian's single-slot parity
    with install_gateway.py's seam. The caller enforces the remaining fire
    conditions (--interactive-prompts set, key unresolved, slot not declined,
    not --check-only/--json); this seam enforces the TTY gate and the entry
    contract: hidden getpass entry, degrading to VISIBLE input with a one-line
    warning ONLY when hidden entry is unachievable (the non-console path
    raising — not an import check). A blank or interrupted entry returns None.
    The raw value is returned to the caller and never echoed."""
    tty = isatty_fn if isatty_fn is not None else _default_isatty
    if not tty():
        return None
    text = f"Anthropic API key for the CT6 Librarian ({slot} slot; blank to skip): "
    hidden = prompt_fn if prompt_fn is not None else _hidden_prompt
    try:
        raw = hidden(text)
    except (EOFError, KeyboardInterrupt):
        return None
    except Exception:
        print("[!] hidden key entry is unachievable on this stdin; "
              "input will be VISIBLE")
        visible = input_fn if input_fn is not None else _visible_input
        try:
            raw = visible(text)
        except (EOFError, KeyboardInterrupt):
            return None
    value = (raw or "").strip()
    return value or None


# --------------------------------------------------------------------------- #
# step / report scaffolding (mirrors install_mempalace.py)
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
    key_present: bool = False
    llm_mode: str = "fake"          # "anthropic" | "fake"
    enabled: bool = False
    descriptor_installed: bool = False
    descriptor_path: Optional[str] = None
    register_hint: Optional[str] = None
    remediation: Optional[str] = None
    check_only: bool = False
    topics: dict[str, Any] = field(default_factory=dict)
    declined: list[str] = field(default_factory=list)  # v3.38.0 — declined slots
    steps: list[StepResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.steps.append(StepResult(name=name, status=status, detail=detail))


# --------------------------------------------------------------------------- #
# config + topic registry persistence
# --------------------------------------------------------------------------- #

def _read_topics(base: Path) -> dict[str, list[str]]:
    path = base / TOPICS_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): list(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _write_topics(base: Path, topics: dict[str, list[str]]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / TOPICS_NAME).write_text(
        json.dumps(topics, indent=2, sort_keys=True), encoding="utf-8")


def _config_payload(config: "_service_config.ServiceConfig", base: Path) -> dict[str, Any]:
    """The persisted `config.json`. Stores model / interval / storage paths and a
    key-SOURCE reference — NEVER the raw key (the redacted view masks it). The
    daemon resolves the live key at runtime from the env or an operator-managed
    config, not from this file."""
    redacted = config.redacted()
    return {
        "llm_model": config.llm_model,
        "storage_mode": "file-folder",
        "key_source": "ANTHROPIC_API_KEY" if config.has_key else None,
        "anthropic_key_masked": redacted["anthropic_key"],
        "extra": {"interval_seconds": DEFAULT_INTERVAL_SECONDS},
        "paths": {
            "index": str(base / INDEX_NAME),
            "bodies": str(base / BODIES_DIR),
            "metadata": str(base / METADATA_DIR),
            "log": str(base / LOG_NAME),
        },
    }


def _write_config(base: Path, config: "_service_config.ServiceConfig") -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / CONFIG_NAME).write_text(
        json.dumps(_config_payload(config, base), indent=2, sort_keys=True),
        encoding="utf-8")


def _provision_state(base: Path, config: "_service_config.ServiceConfig", report: Report) -> None:
    """Create the full state layout under `base` (idempotent)."""
    base.mkdir(parents=True, exist_ok=True)
    (base / BODIES_DIR).mkdir(parents=True, exist_ok=True)
    (base / METADATA_DIR).mkdir(parents=True, exist_ok=True)
    _write_config(base, config)
    if not (base / TOPICS_NAME).exists():
        _write_topics(base, {})
    # initialize the sqlite index file (touched/created via LibraryIndex).
    idx = _library_index.LibraryIndex(str(base / INDEX_NAME))
    idx.close()
    report.add("provision", "ok", f"state layout created under {base}")


def _write_descriptor(base: Path, report: Report) -> None:
    """Generate + write the per-OS boot descriptor; record + (caller) print the
    register hint. The descriptor is WRITTEN, never loaded/executed."""
    desc_dir = base / DESCRIPTOR_DIRNAME
    desc_dir.mkdir(parents=True, exist_ok=True)
    descriptor = _bg.install_descriptor(
        _platform_key(), SERVICE_NAME, _daemon_command(base))
    desc_path = desc_dir / descriptor["filename"]
    desc_path.write_text(descriptor["content"], encoding="utf-8")
    report.descriptor_installed = True
    report.descriptor_path = str(desc_path)
    report.register_hint = descriptor["register_hint"]
    report.add("descriptor", "ok",
               f"{descriptor['kind']} descriptor written to {desc_path}")


# --------------------------------------------------------------------------- #
# LLM-mode resolution
# --------------------------------------------------------------------------- #

def _resolve_config_and_mode(base: Path, env: Optional[dict[str, str]] = None
                             ) -> "_service_config.ServiceConfig":
    """Load the ServiceConfig (config file + env), so `has_key` reflects the live
    key. Storage mode is forced to file-folder (the installable layout)."""
    config = _service_config.load_config(base / CONFIG_NAME, env=env)
    config.storage_mode = "file-folder"
    return config


# --------------------------------------------------------------------------- #
# run-once (foreground full cycle, injectable for offline tests)
# --------------------------------------------------------------------------- #

def run_once(
    base_dir: str | Path,
    *,
    source: Optional[Any] = None,
    llm: Optional[Any] = None,
    env: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """One synchronous fetch->extract->index->metadata cycle over every registered
    topic, foreground (no daemon). Reuses `daemon.build_daemon` so the wiring is
    identical to the scheduled path, then drives `research_topic` directly. Tests
    inject `source`/`llm` (StaticSource + FakeLLMClient) so it runs offline.
    Returns `{topics: {name: {fetched, indexed, skipped}}}`."""
    base = Path(base_dir)
    _scheduler, librarian = _daemon.build_daemon(base, source=source, llm=llm)
    result: dict[str, Any] = {"topics": {}}
    for topic in sorted(librarian.topics):
        summary = librarian.research_topic(topic)
        result["topics"][topic] = {
            "fetched": summary["fetched"],
            "indexed": len(summary["indexed"]),
            "skipped": len(summary["skipped"]),
        }
    librarian.index.close()
    return result


# --------------------------------------------------------------------------- #
# CLAUDE.md guidance block (capability-gated, self-removing)
# --------------------------------------------------------------------------- #

def _upsert_guidance(args: argparse.Namespace, report: Report) -> None:
    """On a verified install, write the guidance block to --claude-md (if given).
    Enabled installs get the usage block; provisioned-but-disabled installs get
    the honest disabled block naming the --enable remediation (the librarian's
    established honesty pattern). A no-op when --claude-md was not supplied."""
    target = getattr(args, "claude_md", None)
    if not target:
        return
    body = GUIDANCE_ENABLED_BODY if report.enabled else GUIDANCE_DISABLED_BODY
    _guidance.upsert_block(target, GUIDANCE_CAPABILITY, body, create=True)
    report.add("guidance-block", "ok",
               f"{'enabled' if report.enabled else 'disabled-state'} guidance "
               f"block written to {target}")


def _remove_guidance(args: argparse.Namespace, report: Report) -> None:
    """On uninstall / purge, remove exactly the guidance block from --claude-md
    (if given). A no-op when --claude-md was not supplied or no block exists."""
    target = getattr(args, "claude_md", None)
    if not target:
        return
    removed = _guidance.remove_block(target, GUIDANCE_CAPABILITY)
    report.add("guidance-block", "ok" if removed else "skipped",
               f"guidance block removed from {target}" if removed
               else f"no guidance block present in {target} (no-op)")


# --------------------------------------------------------------------------- #
# subcommand handlers
# --------------------------------------------------------------------------- #

def _cmd_install(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="install", base_dir=str(base), check_only=bool(args.check_only))
    config = _resolve_config_and_mode(base)
    report.key_present = config.has_key
    report.llm_mode = "anthropic" if config.has_key else "fake"

    if args.check_only:
        report.add("check-only", "skipped",
                   "reporting intent only; no state provisioned")
        return report

    # v3.38.0 setup-key-prompting: decline bookkeeping + the interactive prompt.
    if getattr(args, "re_ask_keys", False) and _read_declines(base):
        _clear_declines(base)
        report.add("key-declines", "ok", "decline record cleared (--re-ask-keys)")
    if config.has_key and "anthropic" in _read_declines(base):
        # auto-reset: a resolved key deletes the slot's stale decline record.
        _clear_declines(base, "anthropic")
        report.add("key-declines", "ok",
                   "anthropic key resolved; stale decline record cleared")
    if (not config.has_key
            and getattr(args, "interactive_prompts", False)
            and not getattr(args, "json", False)
            and _default_isatty()):
        if "anthropic" in _read_declines(base):
            report.add("key-prompt", "skipped",
                       "anthropic key previously declined; not re-asking "
                       "(pass --re-ask-keys to prompt again)")
        else:
            captured = _prompt_for_key("anthropic")
            if captured:
                # route through the EXISTING enable path exactly as a key in
                # the environment does; the raw value stays in-process
                # (config.json persists only the mask + key source).
                config.anthropic_key = captured
                report.key_present = True
                report.llm_mode = "anthropic"
                report.add("key-prompt", "ok",
                           f"Anthropic key captured at the hidden prompt "
                           f"({_mask(captured)}); enabling the daemon")
            else:
                _record_decline(base, "anthropic", via="prompt-skip")
                report.add("key-prompt", "skipped",
                           "blank entry at the key prompt; decline recorded "
                           "(via=prompt-skip) -- pass --re-ask-keys to prompt "
                           "again")

    _provision_state(base, config, report)

    enable = bool(args.enable) or config.has_key
    if enable:
        _write_descriptor(base, report)
        report.enabled = True
        report.add("enable", "ok",
                   "daemon enabled; run the printed register hint to load it")
    else:
        # honest no-key path: provision + write descriptor, but do NOT enable.
        _write_descriptor(base, report)
        report.enabled = False
        report.remediation = (
            f"export {ENV_HOME}={base} ; export ANTHROPIC_API_KEY=… ; "
            f"librarian-install --enable --base-dir {base}"
        )
        report.add("enable", "skipped",
                   "no Anthropic key resolved; provisioned but NOT enabled "
                   "(see remediation)")
    report.topics = _read_topics(base)
    report.declined = sorted(_read_declines(base))
    _upsert_guidance(args, report)
    return report


def _cmd_add_topic(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="add-topic", base_dir=str(base))
    topics = _read_topics(base)
    existing = topics.get(args.name, [])
    for url in args.urls:
        if url not in existing:
            existing.append(url)
    topics[args.name] = existing
    _write_topics(base, topics)
    report.topics = topics
    report.add("add-topic", "ok", f"{args.name} -> {existing}")
    return report


def _cmd_remove_topic(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="remove-topic", base_dir=str(base))
    topics = _read_topics(base)
    if args.name in topics:
        del topics[args.name]
        _write_topics(base, topics)
        report.add("remove-topic", "ok", f"removed {args.name}")
    else:
        report.add("remove-topic", "skipped", f"{args.name} not registered (no-op)")
    report.topics = topics
    return report


def _cmd_list_topics(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="list-topics", base_dir=str(base))
    report.topics = _read_topics(base)
    report.add("list-topics", "ok", f"{len(report.topics)} topic(s) registered")
    return report


def _cmd_run_once(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="run-once", base_dir=str(base))
    config = _resolve_config_and_mode(base)
    report.key_present = config.has_key
    report.llm_mode = "anthropic" if config.has_key else "fake"
    if config.has_key and "anthropic" in _read_declines(base):
        _clear_declines(base, "anthropic")  # v3.38.0 auto-reset on resolution
    topics = _read_topics(base)
    if not topics:
        report.add("run-once", "skipped", "no topics registered (nothing to do)")
        report.topics = {}
        return report
    # production run-once resolves the real source/llm via build_daemon; a bad URL
    # degrades gracefully (UrlSource logs + skips) so this still exits 0.
    result = run_once(base)
    report.topics = result["topics"]
    report.add("run-once", "ok", f"cycled {len(result['topics'])} topic(s)")
    return report


def _cmd_status(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="status", base_dir=str(base))
    config = _resolve_config_and_mode(base)
    report.key_present = config.has_key
    report.llm_mode = "anthropic" if config.has_key else "fake"
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    report.descriptor_installed = bool(descs)
    report.descriptor_path = str(descs[0]) if descs else None
    # enabled iff a descriptor is installed AND a key resolves (honest: a descriptor
    # written in the no-key path is provisioned-but-disabled).
    report.enabled = report.descriptor_installed and config.has_key
    report.topics = _read_topics(base)
    if config.has_key and "anthropic" in _read_declines(base):
        _clear_declines(base, "anthropic")  # v3.38.0 auto-reset on resolution
    report.declined = sorted(_read_declines(base))
    if not report.key_present:
        report.remediation = (
            f"export ANTHROPIC_API_KEY=… ; librarian-install --enable "
            f"--base-dir {base}")
    state = "enabled" if report.enabled else "degraded (no key)" if not config.has_key \
        else "provisioned"
    detail = (f"{state}; descriptor_installed={report.descriptor_installed}; "
              f"{len(report.topics)} topic(s)")
    if report.declined:
        # honesty: the decline suppresses the PROMPT, never the truth — the
        # absent key + remediation above stay reported alongside this.
        detail += f"; declined={','.join(report.declined)}"
    report.add("status", "ok", detail)
    return report


def _cmd_uninstall(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="uninstall", base_dir=str(base))
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    if descs:
        # the unregister hint for the user to run (we never execute it).
        kind = _platform_key()
        report.register_hint = {
            "linux": f"sudo systemctl disable --now {SERVICE_NAME}",
            "darwin": f"launchctl unload -w ~/Library/LaunchAgents/{SERVICE_NAME}.plist",
            "windows": f'schtasks /delete /tn "{SERVICE_NAME}" /f',
        }[kind]
        for d in descs:
            try:
                d.unlink()
            except OSError:
                pass
        report.add("uninstall", "ok",
                   "boot descriptor removed; run the printed unregister hint")
    else:
        report.add("uninstall", "skipped", "no boot descriptor present (no-op)")
    report.descriptor_installed = False

    if args.purge:
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
            report.add("purge", "ok", f"removed state dir {base}")
        else:
            report.add("purge", "skipped", "state dir already absent (no-op)")
    _remove_guidance(args, report)
    return report


def _cmd_decline(args: argparse.Namespace, base: Path) -> Report:
    """The wrapper's deterministic decline record/clear channel (v3.38.0, D3):
    the slash-command flow cannot type into a prompt, so an AskUserQuestion
    decline is recorded here (the librarian's single anthropic slot)."""
    report = Report(action="decline", base_dir=str(base))
    if getattr(args, "clear", False):
        if "anthropic" in _read_declines(base):
            _clear_declines(base, "anthropic")
            report.add("decline", "ok", "anthropic decline record cleared")
        else:
            report.add("decline", "skipped",
                       "no anthropic decline recorded (no-op)")
    else:
        _record_decline(base, "anthropic", via="wrapper")
        report.add("decline", "ok",
                   "anthropic key decline recorded (via=wrapper); install will "
                   "not prompt for it (clear with decline --clear or "
                   "--re-ask-keys)")
    report.declined = sorted(_read_declines(base))
    return report


_HANDLERS = {
    "install": _cmd_install,
    "add-topic": _cmd_add_topic,
    "remove-topic": _cmd_remove_topic,
    "list-topics": _cmd_list_topics,
    "run-once": _cmd_run_once,
    "status": _cmd_status,
    "uninstall": _cmd_uninstall,
    "decline": _cmd_decline,
}


# --------------------------------------------------------------------------- #
# argparse + emit
# --------------------------------------------------------------------------- #

def _add_shared_flags(parser: argparse.ArgumentParser) -> None:
    """The flags accepted in EITHER position (before OR after the subcommand): a
    parent-parser shape so `install --base-dir X` and `--base-dir X install` both
    parse. With subparsers, a top-level-only optional placed after the subcommand
    name would be 'unrecognized', so every subparser inherits these too."""
    parser.add_argument("--base-dir", default=None,
                        help=f"state dir (default ${ENV_HOME} or ~/.architect-team/librarian)")
    parser.add_argument("--enable", action="store_true",
                        help="(re)enable the daemon after a key is added")
    parser.add_argument("--check-only", action="store_true",
                        help="report intent only; do not provision")
    parser.add_argument("--json", action="store_true",
                        help="emit a machine-readable JSON status report")
    parser.add_argument("--purge", action="store_true",
                        help="(uninstall) also remove the state dir")
    parser.add_argument("--interactive-prompts", action="store_true",
                        help="allow the hidden stdin key prompt on an "
                             "interactive TTY (v3.38.0; auto-set for a direct "
                             "TTY install without --json/--check-only)")
    parser.add_argument("--re-ask-keys", action="store_true",
                        help="clear the key-declines.json record so the key "
                             "prompt fires again")
    parser.add_argument("--claude-md", default=None,
                        help="path to a target project's CLAUDE.md — a capability "
                             "guidance block is written there on a verified install "
                             "and removed on uninstall (omit to touch no CLAUDE.md)")


def _build_parser() -> argparse.ArgumentParser:
    # parent carries the shared flags so subparsers can inherit them (the flags
    # parse whether they appear before or after the subcommand name).
    shared = argparse.ArgumentParser(add_help=False)
    _add_shared_flags(shared)

    parser = argparse.ArgumentParser(
        prog="install_librarian.py", parents=[shared],
        description="Install / manage the CT6 Librarian background service.")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("install", parents=[shared], add_help=False)
    sub.add_parser("status", parents=[shared], add_help=False)
    sub.add_parser("list-topics", parents=[shared], add_help=False)
    sub.add_parser("run-once", parents=[shared], add_help=False)
    p_add = sub.add_parser("add-topic", parents=[shared], add_help=False)
    p_add.add_argument("name")
    p_add.add_argument("urls", nargs="+")
    p_rm = sub.add_parser("remove-topic", parents=[shared], add_help=False)
    p_rm.add_argument("name")
    sub.add_parser("uninstall", parents=[shared], add_help=False)
    p_dec = sub.add_parser("decline", parents=[shared], add_help=False)
    p_dec.add_argument("--clear", action="store_true",
                       help="clear the recorded decline instead of recording one")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    command = args.command or "install"  # default subcommand

    # v3.38.0 — a direct-terminal `install` on a real TTY is interactive by
    # default (D1 parity with install_gateway.py): the wrapper and tests pass
    # --interactive-prompts explicitly; --json/--check-only stay prompt-free.
    if (command == "install"
            and not getattr(args, "interactive_prompts", False)
            and not getattr(args, "json", False)
            and not getattr(args, "check_only", False)
            and _default_isatty()):
        args.interactive_prompts = True

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

    return _emit(report, getattr(args, "json", False))


def _emit(report: Report, as_json: bool) -> int:
    if as_json:
        payload = {
            "action": report.action,
            "base_dir": report.base_dir,
            "key_present": report.key_present,
            "llm_mode": report.llm_mode,
            "enabled": report.enabled,
            "descriptor_installed": report.descriptor_installed,
            "descriptor_path": report.descriptor_path,
            "register_hint": report.register_hint,
            "remediation": report.remediation,
            "check_only": report.check_only,
            "topics": report.topics,
            "declined": report.declined,
            "steps": [{"name": s.name, "status": s.status, "detail": s.detail}
                      for s in report.steps],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print()
    print("=" * 64)
    print(f"  CT6 Librarian {report.action} -- summary")
    print("=" * 64)
    for step in report.steps:
        marker = {"ok": "[+]", "skipped": "[-]", "fail": "[x]"}.get(step.status, "[?]")
        print(f"  {marker} {step.name:<14} {step.detail}")
    print("=" * 64)
    print(f"  State dir:   {report.base_dir}")
    print(f"  LLM mode:    {report.llm_mode}  (Anthropic key present: {report.key_present})")
    print(f"  Daemon:      {'enabled' if report.enabled else 'provisioned but NOT enabled'}")
    if report.topics:
        print(f"  Topics:      {sorted(report.topics)}")
    if report.declined:
        print(f"  Key prompts declined for: {', '.join(report.declined)} "
              f"(re-ask with --re-ask-keys)")
    if report.register_hint:
        print("  Register the boot descriptor yourself (NOT run for you):")
        print(f"    {report.register_hint}")
    if report.remediation:
        print("  To enable later, set a key and re-run --enable:")
        print(f"    {report.remediation}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
