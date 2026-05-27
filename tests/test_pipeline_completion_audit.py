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


# --- visual-fidelity: reconciliation ran but no verifier verdict => block ---

def test_reconciliation_without_verifier_verdict_blocks(script: Path, workspace: Path) -> None:
    """v0.9.11: if visual-fidelity reconciliation ran, an independent
    visual-verification-team verdict must exist — a self-reported reconciliation
    that never rendered the live app does not gate the run."""
    at = _at(workspace)
    (at / "visual-fidelity-summary-ts.md").write_text("reconciliation ran", encoding="utf-8")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"reconciliation w/o a verification verdict must block; stderr={r.stderr!r}"
    assert "verification" in r.stderr.lower()


def test_failed_verifier_verdict_blocks(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    (at / "visual-fidelity-summary-ts.md").write_text("reconciliation ran", encoding="utf-8")
    vf = at / "visual-fidelity"
    vf.mkdir()
    (vf / "verification-verdict-web-ts.json").write_text(
        json.dumps({"codebase": "web", "verified_at": "2026-05-20T10:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "visual-verification-team" in r.stderr


def test_blocked_verifier_verdict_blocks(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    (at / "visual-fidelity-summary-ts.md").write_text("reconciliation ran", encoding="utf-8")
    vf = at / "visual-fidelity"
    vf.mkdir()
    (vf / "verification-verdict-web-ts.json").write_text(
        json.dumps({"codebase": "web", "verified_at": "2026-05-20T10:00:00Z", "overall": "blocked"}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2


def test_passing_verifier_verdict_allows(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    (at / "visual-fidelity-summary-ts.md").write_text("reconciliation ran", encoding="utf-8")
    vf = at / "visual-fidelity"
    vf.mkdir()
    (vf / "verification-verdict-web-ts.json").write_text(
        json.dumps({"codebase": "web", "verified_at": "2026-05-20T10:00:00Z", "overall": "pass"}),
        encoding="utf-8",
    )
    assert _run_check(script, workspace).returncode == 0


def test_latest_verifier_verdict_wins_per_codebase(script: Path, workspace: Path) -> None:
    """A later passing verifier verdict supersedes an earlier failing one."""
    at = _at(workspace)
    (at / "visual-fidelity-summary-ts.md").write_text("reconciliation ran", encoding="utf-8")
    vf = at / "visual-fidelity"
    vf.mkdir()
    (vf / "verification-verdict-web-early.json").write_text(
        json.dumps({"codebase": "web", "verified_at": "2026-05-20T09:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    (vf / "verification-verdict-web-late.json").write_text(
        json.dumps({"codebase": "web", "verified_at": "2026-05-20T12:00:00Z", "overall": "pass"}),
        encoding="utf-8",
    )
    assert _run_check(script, workspace).returncode == 0


# --- master-review audit verdict => gate -----------------------------------

def test_failed_master_review_audit_blocks(script: Path, workspace: Path) -> None:
    """v0.9.13: a Phase 7 master-review audit verdict of overall != pass blocks
    the run — the independent system-architect audit did not pass."""
    mr = _at(workspace) / "master-review"
    mr.mkdir()
    (mr / "audit-2026-05-21T10-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T10:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"a failing master-review audit must block; stderr={r.stderr!r}"
    assert "master-review" in r.stderr.lower()
    assert _run_stop(script, workspace, {}).returncode == 2


def test_passing_master_review_audit_allows(script: Path, workspace: Path) -> None:
    mr = _at(workspace) / "master-review"
    mr.mkdir()
    (mr / "audit-2026-05-21T10-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T10:00:00Z", "overall": "pass"}),
        encoding="utf-8",
    )
    assert _run_check(script, workspace).returncode == 0, _run_check(script, workspace).stderr
    assert _run_stop(script, workspace, {}).returncode == 0


def test_no_master_review_audit_files_allows(script: Path, workspace: Path) -> None:
    """No master-review audit verdict yet => no violation (conservative — the
    absence of the Phase 7 verdict is not itself a block)."""
    _write_sr(workspace, "SR-1", "resolved")
    assert _run_check(script, workspace).returncode == 0


def test_latest_master_review_audit_wins(script: Path, workspace: Path) -> None:
    """A later passing audit verdict supersedes an earlier failing one."""
    mr = _at(workspace) / "master-review"
    mr.mkdir()
    (mr / "audit-2026-05-21T09-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T09:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    (mr / "audit-2026-05-21T12-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T12:00:00Z", "overall": "pass"}),
        encoding="utf-8",
    )
    assert _run_check(script, workspace).returncode == 0


# --- documentation-currency audit verdict => gate --------------------------

def test_failed_documentation_currency_audit_blocks(script: Path, workspace: Path) -> None:
    """v0.9.15: a Phase 8 documentation-currency audit verdict of overall != pass
    blocks the run — the independent system-architect audit found stale docs."""
    dc = _at(workspace) / "documentation-currency"
    dc.mkdir()
    (dc / "audit-2026-05-21T10-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T10:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"a failing documentation-currency audit must block; stderr={r.stderr!r}"
    assert "documentation-currency" in r.stderr.lower()
    assert _run_stop(script, workspace, {}).returncode == 2


def test_passing_documentation_currency_audit_allows(script: Path, workspace: Path) -> None:
    dc = _at(workspace) / "documentation-currency"
    dc.mkdir()
    (dc / "audit-2026-05-21T10-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T10:00:00Z", "overall": "pass"}),
        encoding="utf-8",
    )
    assert _run_check(script, workspace).returncode == 0, _run_check(script, workspace).stderr
    assert _run_stop(script, workspace, {}).returncode == 0


def test_no_documentation_currency_audit_files_allows(script: Path, workspace: Path) -> None:
    """No documentation-currency audit verdict yet => no violation (conservative,
    mirroring the master-review check)."""
    _write_sr(workspace, "SR-1", "resolved")
    assert _run_check(script, workspace).returncode == 0


def test_latest_documentation_currency_audit_wins(script: Path, workspace: Path) -> None:
    """A later passing doc-currency audit supersedes an earlier failing one."""
    dc = _at(workspace) / "documentation-currency"
    dc.mkdir()
    (dc / "audit-2026-05-21T09-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T09:00:00Z", "overall": "fail"}),
        encoding="utf-8",
    )
    (dc / "audit-2026-05-21T12-00-00Z.json").write_text(
        json.dumps({"change": "x", "verified_at": "2026-05-21T12:00:00Z", "overall": "pass"}),
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


# --- v0.9.36: bug-fix testing verdict enforcement ---------------------------


def _write_bug_fix_b1(workspace: Path, slug: str, verdict: str = "reproduced",
                       artifact_executed: bool = True,
                       failing_output_captured: bool = True) -> None:
    bf_dir = _at(workspace) / "bug-fix" / slug
    bf_dir.mkdir(parents=True, exist_ok=True)
    (bf_dir / "b1-replication-verdict.json").write_text(json.dumps({
        "phase": "B1", "bug_slug": slug, "verdict": verdict,
        "artifact_paths": ["tests/e2e/bug-fix-test/flow.spec.ts"],
        "artifact_executed": artifact_executed,
        "failing_output_captured": failing_output_captured,
        "dev_environment_url": "https://dev.example.com",
        "timestamp": "2026-05-27T00:00:00Z",
    }), encoding="utf-8")


def _write_bug_fix_b6(workspace: Path, slug: str, verdict: str = "bug-resolved",
                       artifacts_executed: bool = True,
                       symptom_gone: bool = True,
                       witness_passed: bool = True) -> None:
    bf_dir = _at(workspace) / "bug-fix" / slug
    bf_dir.mkdir(parents=True, exist_ok=True)
    (bf_dir / "b6-qa-replay-verdict.json").write_text(json.dumps({
        "phase": "B6", "bug_slug": slug, "verdict": verdict,
        "artifacts_rerun": ["tests/e2e/bug-fix-test/flow.spec.ts"],
        "artifacts_executed_against_live_dev": artifacts_executed,
        "symptom_gone_end_to_end": symptom_gone,
        "code_path_witness_passed": witness_passed,
        "dev_environment_url": "https://dev.example.com",
        "iteration": 1, "timestamp": "2026-05-27T00:00:00Z",
    }), encoding="utf-8")


def test_bug_fix_no_b1_verdict_blocks(script: Path, workspace: Path) -> None:
    """A bug-fix slug directory without a B1 verdict file blocks."""
    bf_dir = _at(workspace) / "bug-fix" / "fix-broken-delete"
    bf_dir.mkdir(parents=True)
    _write_bug_fix_b6(workspace, "fix-broken-delete")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "b1-replication-verdict" in r.stderr


def test_bug_fix_no_b6_verdict_blocks(script: Path, workspace: Path) -> None:
    """A bug-fix slug directory without a B6 verdict file blocks."""
    _write_bug_fix_b1(workspace, "fix-broken-delete")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "b6-qa-replay-verdict" in r.stderr


def test_bug_fix_b1_not_executed_blocks(script: Path, workspace: Path) -> None:
    """B1 verdict with artifact_executed=false blocks even if verdict is reproduced."""
    _write_bug_fix_b1(workspace, "fix-broken-delete", artifact_executed=False)
    _write_bug_fix_b6(workspace, "fix-broken-delete")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "artifact_executed" in r.stderr


def test_bug_fix_b1_no_output_blocks(script: Path, workspace: Path) -> None:
    """B1 verdict with failing_output_captured=false blocks."""
    _write_bug_fix_b1(workspace, "fix-broken-delete", failing_output_captured=False)
    _write_bug_fix_b6(workspace, "fix-broken-delete")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "failing_output_captured" in r.stderr


def test_bug_fix_b6_not_executed_blocks(script: Path, workspace: Path) -> None:
    """B6 verdict with artifacts_executed_against_live_dev=false blocks."""
    _write_bug_fix_b1(workspace, "fix-broken-delete")
    _write_bug_fix_b6(workspace, "fix-broken-delete", artifacts_executed=False)
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "artifacts_executed_against_live_dev" in r.stderr


def test_bug_fix_b6_symptom_not_gone_blocks(script: Path, workspace: Path) -> None:
    """B6 verdict with symptom_gone_end_to_end=false blocks."""
    _write_bug_fix_b1(workspace, "fix-broken-delete")
    _write_bug_fix_b6(workspace, "fix-broken-delete", symptom_gone=False)
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "symptom_gone_end_to_end" in r.stderr


def test_bug_fix_b6_witness_not_passed_blocks(script: Path, workspace: Path) -> None:
    """B6 verdict with code_path_witness_passed=false blocks."""
    _write_bug_fix_b1(workspace, "fix-broken-delete")
    _write_bug_fix_b6(workspace, "fix-broken-delete", witness_passed=False)
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "code_path_witness_passed" in r.stderr


def test_bug_fix_clean_verdicts_allow(script: Path, workspace: Path) -> None:
    """Valid B1 + B6 verdicts with all fields true allows."""
    _write_bug_fix_b1(workspace, "fix-broken-delete")
    _write_bug_fix_b6(workspace, "fix-broken-delete")
    r = _run_check(script, workspace)
    assert r.returncode == 0


def test_bug_fix_could_not_reproduce_b1_does_not_block_on_execution(script: Path, workspace: Path) -> None:
    """A could-not-reproduce verdict doesn't check artifact_executed (the bug wasn't confirmed)."""
    _write_bug_fix_b1(workspace, "fix-broken-delete", verdict="could-not-reproduce",
                       artifact_executed=False)
    _write_bug_fix_b6(workspace, "fix-broken-delete")
    r = _run_check(script, workspace)
    assert r.returncode == 0
