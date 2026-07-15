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
