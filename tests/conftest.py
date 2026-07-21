"""Shared pytest fixtures."""
import hashlib
import json
import os
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# REQ-012 opt-in behavioral eval tier gate.
# --------------------------------------------------------------------------- #
#
# `tests/evals/` drives the live `claude` CLI (it costs money and needs auth),
# so the DEFAULT suite must never collect or execute it. `collect_ignore` is a
# pytest conftest hook: paths are resolved relative to this conftest's
# directory, and pytest skips collection under them entirely. Only when the
# operator opts in with `CT6_EVALS=1` is the directory collected. This does NOT
# affect the default-suite offline test (`tests/test_evals_offline.py`), which
# only READS captured fixture data under `tests/evals/` - reading files is
# unaffected by collection gating.
collect_ignore = []
if os.environ.get("CT6_EVALS") != "1":
    collect_ignore.append("evals")


# --------------------------------------------------------------------------- #
# REQ-004 real-machine-state tripwire (v3.41.1)
# --------------------------------------------------------------------------- #

#: The real, user-owned files no test may ever mutate. `settings.json` carries
#: the gateway activation env block; `gateway.json` records activation consent;
#: `gateway.env` holds the master + provider keys.
_PROTECTED_REAL_STATE = {
    "settings.json": Path.home() / ".claude" / "settings.json",
    "gateway.json": Path.home() / ".architect-team" / "gateway" / "gateway.json",
    "gateway.env": Path.home() / ".architect-team" / "gateway" / "gateway.env",
}


def _digest(path: Path) -> str | None:
    """Content digest, or None when the file does not exist."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, ValueError):
        return None


@pytest.fixture(scope="session", autouse=True)
def _real_state_tripwire() -> "object":
    """Fail the suite LOUDLY if any test mutates the developer's real machine
    state.

    History (v3.41.1): `tests/test_install_gateway.py` ran a real `uninstall`
    with `--base-dir`/`--agents-dir` sandboxed but no `--settings-path`.
    `_cmd_uninstall` resolved the DEFAULT `~/.claude/settings.json` and
    `remove_claude_env` stripped the gateway env block — so on an ACTIVATED
    machine EVERY full suite run silently deactivated the gateway while
    `gateway.json` still recorded `activated: true`. Both observed drift
    incidents trace to this. It went unnoticed for so long because on CI and on
    never-activated machines the strip is a no-op; only the one developer whose
    machine was actually activated ever paid for it, and the symptom (sessions
    quietly running direct-to-Anthropic with the secondary split off) is
    invisible from inside the suite.

    Per-module sandboxing fixes the known leak; this tripwire converts any
    FUTURE leak of the same class — in any test file, through any code path —
    into a named suite failure instead of silent damage to a real machine.

    Content digests, not mtimes: a rewrite with identical bytes is not a
    mutation, and a touch without a content change should not cry wolf.
    """
    before = {name: _digest(path) for name, path in _PROTECTED_REAL_STATE.items()}
    yield
    mutated = []
    for name, path in _PROTECTED_REAL_STATE.items():
        after = _digest(path)
        if after == before[name]:
            continue
        if before[name] is None:
            what = "CREATED (did not exist before the suite)"
        elif after is None:
            what = "DELETED"
        else:
            what = "MODIFIED"
        mutated.append(f"  - {name} {what}: {path}")

    if mutated:
        detail = "\n".join(mutated)
        raise AssertionError(
            "REQ-004 TRIPWIRE: the test suite mutated the developer's REAL "
            "machine state. No test may ever touch these files - sandbox the "
            "path (pass --settings-path / --base-dir / --agents-dir, or "
            "monkeypatch the module's DEFAULT_USER_SETTINGS_PATH).\n"
            f"{detail}\n"
            "If the gateway env block was stripped from settings.json, the "
            "machine is now DRIFTED: `gateway.json` still records "
            "activated=true while Claude Code runs direct-to-Anthropic with "
            "the secondary split off. Recover with `install --activate`, or "
            "start a new session (the SessionStart self-heal re-applies it)."
        )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Repo root, derived from this conftest's location."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def plugin_root(repo_root: Path) -> Path:
    """For this repo the plugin root IS the repo root."""
    return repo_root


@pytest.fixture(autouse=True)
def _scrub_plugin_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """v3.39.0 GLOBAL hermeticity: the runtime agents-dir resolver
    (set_default_model.installed_plugin_agents_dir) reads Claude Code's REAL
    per-user installed-plugin registry by default — an unscrubbed resolution
    would let any model-policy test rewrite the REAL installed plugin copy
    mid-suite (the v3.35.0 ambient-leak lesson, applied globally). Point every
    test at a nonexistent registry so the resolver falls back to the repo
    agents/ (the pre-v3.39.0 behavior); resolver tests pass ``registry_path``
    explicitly (the parameter beats the env var)."""
    monkeypatch.setenv("CT6_PLUGIN_REGISTRY", "__ct6-no-plugin-registry__.json")
