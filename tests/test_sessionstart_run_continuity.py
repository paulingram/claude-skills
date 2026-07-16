"""Tests for hooks/sessionstart-run-continuity.py (v3.30.0).

The SessionStart resume directive: an ACTIVE active-run.json marker injects
the resume-via-Skill directive into the session context; anything else prints
nothing. Always exit 0 — this hook never blocks.
"""
from tests.helpers.module_loader import load_module
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hooks import run_continuity as rc

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "sessionstart-run-continuity.py"


def _load_module():
    mod = load_module(HOOK, "sessionstart_run_continuity")
    return mod


def _run(payload: dict | str, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop(rc.DISABLE_ENV, None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        text=True, capture_output=True, cwd=str(REPO_ROOT), env=env,
    )


def test_wired_in_hooks_json() -> None:
    data = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    entries = data["hooks"].get("SessionStart", [])
    assert entries, "no SessionStart hooks defined"
    cmds = [h["command"] for entry in entries for h in entry["hooks"]]
    assert any("sessionstart-run-continuity.py" in c for c in cmds)


def test_silent_without_marker(tmp_path: Path) -> None:
    r = _run({"cwd": str(tmp_path), "source": "startup"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_active_marker_injects_directive(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.update_marker(tmp_path, slug="my-feature", phase="Phase 5")
    r = _run({"cwd": str(tmp_path), "source": "resume"})
    assert r.returncode == 0
    assert "[CT6 run-continuity]" in r.stdout
    assert 'Skill(skill="architect-team-pipeline")' in r.stdout
    assert "my-feature" in r.stdout and "Phase 5" in r.stdout
    assert "--stand-down" in r.stdout
    assert "CT6-TEAMMATE" in r.stdout, "teammate sessions are told to ignore the notice"


def test_compact_source_sharpens_the_note(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "bug-fix-pipeline")
    r = _run({"cwd": str(tmp_path), "source": "compact"})
    assert "COMPACTED" in r.stdout
    r2 = _run({"cwd": str(tmp_path), "source": "startup"})
    assert "COMPACTED" not in r2.stdout


def test_silent_for_complete_and_stood_down(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.mark_complete(tmp_path)
    assert _run({"cwd": str(tmp_path), "source": "startup"}).stdout.strip() == ""
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.stand_down(tmp_path, "user said no pipeline")
    assert _run({"cwd": str(tmp_path), "source": "startup"}).stdout.strip() == ""


def test_kill_switch_silences(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    r = _run({"cwd": str(tmp_path), "source": "startup"}, env_extra={rc.DISABLE_ENV: "1"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_fail_open_on_garbage(tmp_path: Path) -> None:
    assert _run("{not json").returncode == 0
    assert _run({}).returncode == 0
    p = rc.marker_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{broken", encoding="utf-8")
    r = _run({"cwd": str(tmp_path), "source": "startup"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_build_directive_pure_function(tmp_path: Path) -> None:
    mod = _load_module()
    assert mod.build_directive({}) == ""
    assert mod.build_directive({"cwd": ""}) == ""
    rc.engage_marker(tmp_path, "ux-test-builder")
    out = mod.build_directive({"cwd": str(tmp_path), "source": "resume"})
    assert 'Skill(skill="ux-test-builder")' in out


# --------------------------------------------------------------------------- #
# v3.39.0 — model-split self-heal
# --------------------------------------------------------------------------- #
#
# A plugin update ships uniform-fable agent files into a fresh cache dir,
# silently reverting an applied codex role split. When the gateway state says
# the split is desired AND the hook runs from an INSTALLED plugin copy whose
# agents/ drifted, the hook re-applies the split. A dev checkout is NEVER
# rewritten; every failure path returns "" (fail-open).

import shutil  # noqa: E402


def _fake_installed_plugin(tmp_path: Path, model: str = "fable") -> tuple[Path, Path]:
    """A fake installed plugin copy (under a fake plugins base) carrying the
    REAL model lever + a two-agent agents/ dir, plus the plugins base."""
    plugins_base = tmp_path / "plugins"
    root = plugins_base / "cache" / "architect-team-marketplace" / "architect-team" / "9.9.9"
    (root / "agents").mkdir(parents=True)
    for stem in ("backend", "system-architect"):
        (root / "agents" / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: {model}\n---\n\nbody\n", encoding="utf-8")
    (root / "scripts" / "setup").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "scripts" / "setup" / "set_default_model.py",
                root / "scripts" / "setup" / "set_default_model.py")
    return root, plugins_base


def _gateway_state(tmp_path: Path, **overrides) -> Path:
    state = {"activated": True, "auth_mode": "api-key",
             "model_policy": "codex-split", "codex_alias": "codex-5.6-sol"}
    state.update(overrides)
    path = tmp_path / "gateway.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def test_heal_reapplies_split_to_drifted_installed_copy(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)  # uniform fable = drifted
    note = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_gateway_state(tmp_path))
    assert "self-heal" in note and "re-applied" in note
    assert "model: codex-5.6-sol" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")
    assert "model: fable" in (
        root / "agents" / "system-architect.md").read_text(encoding="utf-8")


def test_heal_never_rewrites_a_dev_checkout(tmp_path: Path) -> None:
    """The root guard: a plugin root OUTSIDE the plugins base (a dev checkout,
    this repo itself) is never rewritten — even with a codex-split state."""
    mod = _load_module()
    root, _ = _fake_installed_plugin(tmp_path)
    note = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=tmp_path / "elsewhere",
        gateway_state_path=_gateway_state(tmp_path))
    assert note == ""
    assert "model: fable" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")


def test_heal_noop_when_state_does_not_want_the_split(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)
    for overrides in ({"model_policy": "uniform-fable"},
                      {"activated": False},
                      {"auth_mode": "subscription"}):
        note = mod.maybe_heal_model_split(
            plugin_root=root, plugins_base=plugins_base,
            gateway_state_path=_gateway_state(tmp_path, **overrides))
        assert note == "", overrides
    assert "model: fable" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")


def test_heal_noop_when_split_already_applied_or_state_missing(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)
    # missing state file => fail-open no-op
    assert mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=tmp_path / "absent.json") == ""
    # apply once, then the healed state is a silent no-op
    first = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_gateway_state(tmp_path))
    assert first != ""
    again = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_gateway_state(tmp_path))
    assert again == ""


def test_heal_fail_open_on_garbage_state(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)
    bad = tmp_path / "gateway.json"
    bad.write_text("{not json", encoding="utf-8")
    assert mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=bad) == ""
