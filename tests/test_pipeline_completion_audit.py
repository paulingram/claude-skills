"""Unit tests for hooks/pipeline-completion-audit.py (v0.9.9).

The Stop hook gates the orchestrator's TERMINAL state: it blocks a session from
ending while an architect-team run is demonstrably incomplete. It is also
runnable standalone (`--check`) as a Phase 8 pre-commit gate.

We invoke the script as a subprocess: `--check` mode (no stdin) and Stop-hook
mode (JSON payload on stdin), against crafted `.architect-team/` workspaces.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def _run_check(script: Path, workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--check"],
        text=True, capture_output=True, cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _run_stop(script: Path, workspace: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True, capture_output=True, cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _at(workspace: Path) -> Path:
    d = workspace / ".architect-team"
    d.mkdir(exist_ok=True)
    return d


def _write_sr(workspace: Path, sr_id: str, status: str, *, origin_kind: str = "visual-fidelity-drift",
              diagnostic_plan_path: str | None = None) -> None:
    sr_dir = _at(workspace) / "solution-requirements"
    sr_dir.mkdir(exist_ok=True)
    body = {"solution_id": sr_id, "status": status, "origin": {"kind": origin_kind}}
    if diagnostic_plan_path is not None:
        body["diagnostic_plan_path"] = diagnostic_plan_path
    (sr_dir / f"{sr_id}.json").write_text(json.dumps(body), encoding="utf-8")


# --- not an architect-team run => always allow -----------------------------

def test_no_architect_team_dir_allows(script: Path, workspace: Path) -> None:
    assert _run_check(script, workspace).returncode == 0
    assert _run_stop(script, workspace, {}).returncode == 0


def test_empty_architect_team_dir_allows(script: Path, workspace: Path) -> None:
    _at(workspace)  # exists but holds no run state
    assert _run_check(script, workspace).returncode == 0
    assert _run_stop(script, workspace, {}).returncode == 0


# --- clean run => allow -----------------------------------------------------

def test_clean_run_allows(script: Path, workspace: Path) -> None:
    _write_sr(workspace, "SR-1", "resolved")
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"dev_loop_iterations": 4}), encoding="utf-8"
    )
    assert _run_check(script, workspace).returncode == 0, _run_check(script, workspace).stderr
    assert _run_stop(script, workspace, {}).returncode == 0


# --- open / in-progress SRs => block ---------------------------------------

@pytest.mark.parametrize("status", ["open", "in_progress"])
def test_unresolved_sr_blocks(script: Path, workspace: Path, status: str) -> None:
    _write_sr(workspace, "SR-1", status)
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"a {status!r} SR must block; stderr={r.stderr!r}"
    assert "SR-1" in r.stderr
    assert _run_stop(script, workspace, {}).returncode == 2


# --- test-failure SR without a diagnostic plan => block --------------------

def test_test_failure_sr_without_diagnostic_plan_blocks(script: Path, workspace: Path) -> None:
    _write_sr(workspace, "SR-2", "resolved", origin_kind="rca-product-bug")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "diagnostic" in r.stderr.lower()


def test_test_failure_sr_with_missing_plan_file_blocks(script: Path, workspace: Path) -> None:
    _write_sr(workspace, "SR-3", "resolved", origin_kind="integration-testing-failure",
              diagnostic_plan_path=".architect-team/diagnostic-research/x/plan.md")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "diagnostic_plan_path" in r.stderr


def test_test_failure_sr_with_present_plan_allows(script: Path, workspace: Path) -> None:
    plan_rel = ".architect-team/diagnostic-research/x/plan.md"
    plan = workspace / plan_rel
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("the plan", encoding="utf-8")
    _write_sr(workspace, "SR-4", "resolved", origin_kind="rca-product-bug",
              diagnostic_plan_path=plan_rel)
    assert _run_check(script, workspace).returncode == 0


# --- editability not satisfied => block ------------------------------------

def test_unsatisfied_editability_blocks(script: Path, workspace: Path) -> None:
    feat = _at(workspace) / "editability" / "projects"
    feat.mkdir(parents=True)
    (feat / "converged-map-pass1-ts.json").write_text(
        json.dumps({"feature": "projects", "satisfied": False, "gaps": [{"x": 1}]}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "editability" in r.stderr.lower()


def test_satisfied_editability_allows(script: Path, workspace: Path) -> None:
    feat = _at(workspace) / "editability" / "projects"
    feat.mkdir(parents=True)
    (feat / "converged-map-pass2-ts.json").write_text(
        json.dumps({"feature": "projects", "satisfied": True, "gaps": []}),
        encoding="utf-8",
    )
    assert _run_check(script, workspace).returncode == 0


def test_editability_drafts_without_converged_map_blocks(script: Path, workspace: Path) -> None:
    feat = _at(workspace) / "editability" / "orders"
    feat.mkdir(parents=True)
    (feat / "reviewer-1-pass1-ts.json").write_text(json.dumps({"draft": True}), encoding="utf-8")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "converge" in r.stderr.lower()


# --- test-completeness debt => block ---------------------------------------

def test_test_completeness_fail_blocks(script: Path, workspace: Path) -> None:
    tc = _at(workspace) / "test-completeness"
    tc.mkdir()
    (tc / "T-1-ts.json").write_text(
        json.dumps({"task_id": "T-1", "verified_at": "2026-05-20T10:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "test-completeness" in r.stderr.lower()


def test_phase_5_integration_debt_blocks(script: Path, workspace: Path) -> None:
    tc = _at(workspace) / "test-completeness"
    tc.mkdir()
    (tc / "T-2-ts.json").write_text(
        json.dumps({"task_id": "T-2", "verified_at": "2026-05-20T10:00:00Z",
                    "overall": "pass", "phase_5_integration_debt": True}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "debt" in r.stderr.lower()


def test_latest_verdict_wins(script: Path, workspace: Path) -> None:
    """A later passing verdict supersedes an earlier failing one for the same task."""
    tc = _at(workspace) / "test-completeness"
    tc.mkdir()
    (tc / "T-3-early.json").write_text(
        json.dumps({"task_id": "T-3", "verified_at": "2026-05-20T09:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    (tc / "T-3-late.json").write_text(
        json.dumps({"task_id": "T-3", "verified_at": "2026-05-20T12:00:00Z", "overall": "pass"}),
        encoding="utf-8",
    )
    assert _run_check(script, workspace).returncode == 0


# --- iteration ceiling => block --------------------------------------------

def test_iteration_ceiling_exceeded_blocks(script: Path, workspace: Path) -> None:
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"dev_loop_iterations": 21}), encoding="utf-8"
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "ceiling" in r.stderr.lower()


# --- escalation marker => allow even with violations -----------------------

def test_escalation_marker_allows_despite_violations(script: Path, workspace: Path) -> None:
    _write_sr(workspace, "SR-1", "open")
    (_at(workspace) / "escalation-pending.md").write_text(
        "Waiting on the human to decide X.", encoding="utf-8"
    )
    assert _run_check(script, workspace).returncode == 0
    assert _run_stop(script, workspace, {}).returncode == 0


# --- stop_hook_active => never loop ----------------------------------------

def test_stop_hook_active_allows(script: Path, workspace: Path) -> None:
    """When the Stop hook has already fired this stop, it must not block again."""
    _write_sr(workspace, "SR-1", "open")
    r = _run_stop(script, workspace, {"stop_hook_active": True})
    assert r.returncode == 0, f"stop_hook_active must prevent a re-block; stderr={r.stderr!r}"


# --- fail open --------------------------------------------------------------

def test_malformed_stop_payload_fails_open(script: Path, workspace: Path) -> None:
    _write_sr(workspace, "SR-1", "open")
    r = subprocess.run(
        [sys.executable, str(script)],
        input="{not json",
        text=True, capture_output=True, cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert r.returncode == 0, "a malformed hook payload must fail open (exit 0)"


def test_corrupt_sr_is_reported_not_crashed(script: Path, workspace: Path) -> None:
    sr_dir = _at(workspace) / "solution-requirements"
    sr_dir.mkdir()
    (sr_dir / "SR-bad.json").write_text("{ not json", encoding="utf-8")
    r = _run_check(script, workspace)
    # A corrupt SR is a real violation, but the hook must not crash.
    assert r.returncode == 2
    assert "SR-bad" in r.stderr
