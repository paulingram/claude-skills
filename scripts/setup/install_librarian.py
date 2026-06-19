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

Flags:
  --base-dir PATH    The librarian state dir (default: $CT6_LIBRARIAN_HOME, else
                     ~/.architect-team/librarian/). No hardcoded home in the core.
  --enable           (re)enable the daemon after a key is added (re-write + hint).
  --check-only       Report intent only; do not provision.
  --json             Emit a machine-readable JSON status report.

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
import importlib.util
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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
    if not report.key_present:
        report.remediation = (
            f"export ANTHROPIC_API_KEY=… ; librarian-install --enable "
            f"--base-dir {base}")
    state = "enabled" if report.enabled else "degraded (no key)" if not config.has_key \
        else "provisioned"
    report.add("status", "ok",
               f"{state}; descriptor_installed={report.descriptor_installed}; "
               f"{len(report.topics)} topic(s)")
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
    return report


_HANDLERS = {
    "install": _cmd_install,
    "add-topic": _cmd_add_topic,
    "remove-topic": _cmd_remove_topic,
    "list-topics": _cmd_list_topics,
    "run-once": _cmd_run_once,
    "status": _cmd_status,
    "uninstall": _cmd_uninstall,
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
