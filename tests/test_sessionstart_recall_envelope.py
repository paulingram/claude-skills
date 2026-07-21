"""Tests for the recall envelope wired into hooks/sessionstart-run-continuity.py.

The resume directive recalls the active-run marker's recorded state into the
session context; that recalled state MUST be wrapped in the recall-hygiene
data-not-instructions envelope (REQ-002). The wrapping is fail-open: any engine
error injects the recalled state UNWRAPPED rather than crashing the hook, and
every existing directive behavior is preserved.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.helpers.module_loader import load_module

from hooks import run_continuity as rc

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "sessionstart-run-continuity.py"


def _load_module():
    return load_module(HOOK, "sessionstart_run_continuity")


def _run(payload: dict) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop(rc.DISABLE_ENV, None)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True, capture_output=True, cwd=str(REPO_ROOT), env=env,
    )


def test_recalled_state_is_enveloped(tmp_path: Path) -> None:
    mod = _load_module()
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.update_marker(tmp_path, slug="my-feature", phase="Phase 5")
    out = mod.build_directive({"cwd": str(tmp_path), "source": "resume"})
    # the recalled marker state is wrapped, marked as non-instruction data
    assert '<recalled-data source="active-run-marker" instructions="false">' in out
    assert "</recalled-data>" in out
    # the recalled facts themselves survive inside the envelope
    assert "my-feature" in out and "Phase 5" in out
    # existing directive behavior preserved verbatim
    assert "[CT6 run-continuity]" in out
    assert 'Skill(skill="architect-team-pipeline")' in out
    assert "--stand-down" in out
    assert "CT6-TEAMMATE" in out


def test_subprocess_stdout_carries_the_envelope(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.update_marker(tmp_path, slug="e2e-slug", phase="Phase 1")
    r = _run({"cwd": str(tmp_path), "source": "resume"})
    assert r.returncode == 0
    assert "<recalled-data" in r.stdout
    assert "instructions=\"false\"" in r.stdout
    assert "e2e-slug" in r.stdout


def test_fail_open_when_engine_unavailable(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "_load_recall_engine", lambda: None)
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.update_marker(tmp_path, slug="ff-slug", phase="Phase 2")
    out = mod.build_directive({"cwd": str(tmp_path), "source": "resume"})
    # unwrapped, but the directive + recalled facts are still emitted
    assert "<recalled-data" not in out
    assert "ff-slug" in out and "Phase 2" in out
    assert 'Skill(skill="architect-team-pipeline")' in out


def test_fail_open_when_engine_raises(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()

    class _Boom:
        def envelope(self, *args, **kwargs):
            raise RuntimeError("engine exploded")

    monkeypatch.setattr(mod, "_load_recall_engine", lambda: _Boom())
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.update_marker(tmp_path, slug="zz-slug", phase="Phase 3")
    out = mod.build_directive({"cwd": str(tmp_path), "source": "resume"})
    assert "<recalled-data" not in out
    assert "zz-slug" in out and "Phase 3" in out
    assert "[CT6 run-continuity]" in out


def test_wrap_recalled_helper_fail_open(monkeypatch) -> None:
    mod = _load_module()
    # None engine => raw text back
    monkeypatch.setattr(mod, "_load_recall_engine", lambda: None)
    assert mod._wrap_recalled("raw text", source="x") == "raw text"


def test_no_marker_still_silent(tmp_path: Path) -> None:
    # the envelope wiring must not perturb the no-marker silent path
    r = _run({"cwd": str(tmp_path), "source": "startup"})
    assert r.returncode == 0 and r.stdout.strip() == ""
