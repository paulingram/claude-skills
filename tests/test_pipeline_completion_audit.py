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
from tests.helpers.module_loader import load_module


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


# Default origin kind for the "a clean resolved SR" background fixtures: a
# NON-test-failure origin (`editability-gap` routes a fix team directly and does
# NOT require a diagnostic_plan_path). SR-sr-catalog-spelling-reconcile flipped
# the runtime constant to the canonical `visual-fidelity-drift`, which (correctly)
# IS a test-failure origin demanding a plan — so the prior default
# (`visual-fidelity-drift`) made every "clean resolved SR" background fixture
# require a plan it was never meant to carry. Tests whose intent IS a
# test-failure SR pass `origin_kind=` explicitly (rca-product-bug /
# integration-testing-failure below), so they are unaffected.
def _write_sr(workspace: Path, sr_id: str, status: str, *, origin_kind: str = "editability-gap",
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


# --- v3.8.0 unbounded solving: NO iteration ceiling ------------------------

def test_high_iteration_count_does_not_block(script: Path, workspace: Path) -> None:
    """v3.8.0: the global iteration ceiling was removed — the dev-loop runs
    until success and NEVER aborts on iteration count. A workspace with a very
    high dev_loop_iterations and no real incomplete work must NOT block."""
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"dev_loop_iterations": 999}), encoding="utf-8"
    )
    r = _run_check(script, workspace)
    assert r.returncode == 0, (
        f"a high dev_loop_iterations must NOT block (no ceiling); stderr={r.stderr!r}"
    )
    assert _run_stop(script, workspace, {}).returncode == 0


def test_iteration_ceiling_symbols_removed(script: Path) -> None:
    """v3.8.0: ITERATION_CEILING and _audit_iteration_ceiling no longer exist."""
    import importlib.util

    mod = load_module(script, "pipeline_completion_audit_sym")
    assert not hasattr(mod, "ITERATION_CEILING")
    assert getattr(mod, "_audit_iteration_ceiling", None) is None


def test_high_iteration_count_with_open_sr_still_blocks(script: Path, workspace: Path) -> None:
    """The worklist still works: a high iteration count does NOT excuse real
    incomplete work — an open SR still blocks regardless of iteration count."""
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"dev_loop_iterations": 999}), encoding="utf-8"
    )
    _write_sr(workspace, "SR-1", "open")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"an open SR must still block; stderr={r.stderr!r}"
    assert "SR-1" in r.stderr


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


# ---- openspec validate --all --strict wired into the master-review gate ----


def _load_audit_module(script: Path):
    import importlib.util

    mod = load_module(script, "pca_openspec_gate")
    return mod


def _write_master_review_verdict(workspace: Path, overall: str = "pass") -> None:
    mr = workspace / ".architect-team" / "master-review"
    mr.mkdir(parents=True, exist_ok=True)
    # Colon-free filename — Windows rejects ':' in paths; the hook globs
    # audit-*.json so the exact stamp format does not matter for the match.
    (mr / "audit-2026-06-10T000000Z.json").write_text(
        json.dumps({"overall": overall, "verified_at": "2026-06-10T00:00:00Z"}),
        encoding="utf-8",
    )


def _fake_run(stdout: str, returncode: int = 0):
    def _run(cmd, **kwargs):  # noqa: ANN001 - mirrors subprocess.run loosely
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return _run


def _patch_openspec(monkeypatch, mod, *, which, run=None) -> None:
    """Patch the module's shutil.which / subprocess.run via monkeypatch so they
    are RESTORED after the test. NOTE: mod.shutil / mod.subprocess are the global
    module singletons — a bare assignment would leak the fake across the whole
    test process (breaking every later test that shells out); monkeypatch.setattr
    undoes it on teardown."""
    monkeypatch.setattr(mod.shutil, "which", which)
    if run is not None:
        monkeypatch.setattr(mod.subprocess, "run", run)


def test_openspec_gate_noop_without_master_review_verdict(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deterministic openspec check is scoped to the master-review gate: with
    no Phase 7 verdict it is a no-op even if an openspec/ workspace + CLI exist."""
    mod = _load_audit_module(script)
    (workspace / "openspec").mkdir()
    invalid = json.dumps({"items": [{"id": "x", "valid": False}]})
    _patch_openspec(monkeypatch, mod, which=lambda name: "/usr/bin/openspec", run=_fake_run(invalid))
    assert mod._audit_openspec_validation(workspace, workspace / ".architect-team") == []


def test_openspec_gate_noop_without_openspec_dir(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_audit_module(script)
    _write_master_review_verdict(workspace)
    invalid = json.dumps({"items": [{"id": "x", "valid": False}]})
    _patch_openspec(monkeypatch, mod, which=lambda name: "/usr/bin/openspec", run=_fake_run(invalid))
    assert mod._audit_openspec_validation(workspace, workspace / ".architect-team") == []


def test_openspec_gate_noop_when_cli_absent(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Best-effort: a missing openspec CLI never wedges the session."""
    mod = _load_audit_module(script)
    _write_master_review_verdict(workspace)
    (workspace / "openspec").mkdir()
    _patch_openspec(monkeypatch, mod, which=lambda name: None)
    assert mod._audit_openspec_validation(workspace, workspace / ".architect-team") == []


def test_openspec_gate_passes_when_all_valid(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_audit_module(script)
    _write_master_review_verdict(workspace)
    (workspace / "openspec").mkdir()
    valid = json.dumps({"items": [{"id": "a", "valid": True}, {"id": "b", "valid": True}]})
    _patch_openspec(monkeypatch, mod, which=lambda name: "/usr/bin/openspec", run=_fake_run(valid))
    assert mod._audit_openspec_validation(workspace, workspace / ".architect-team") == []


def test_openspec_gate_blocks_on_invalid_change(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_audit_module(script)
    _write_master_review_verdict(workspace)
    (workspace / "openspec").mkdir()
    out = json.dumps({"items": [
        {"id": "good-change", "valid": True},
        {"id": "orphan-one", "valid": False},
        {"id": "orphan-two", "valid": False},
    ]})
    _patch_openspec(monkeypatch, mod, which=lambda name: "/usr/bin/openspec", run=_fake_run(out, returncode=1))
    violations = mod._audit_openspec_validation(workspace, workspace / ".architect-team")
    assert len(violations) == 1
    assert "2 invalid change(s)" in violations[0]
    assert "orphan-one" in violations[0] and "orphan-two" in violations[0]
    assert "good-change" not in violations[0]


def test_openspec_gate_noop_on_subprocess_error(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_audit_module(script)
    _write_master_review_verdict(workspace)
    (workspace / "openspec").mkdir()

    def _boom(cmd, **kwargs):  # noqa: ANN001
        raise OSError("openspec exploded")

    _patch_openspec(monkeypatch, mod, which=lambda name: "/usr/bin/openspec", run=_boom)
    assert mod._audit_openspec_validation(workspace, workspace / ".architect-team") == []


def test_openspec_gate_blocks_on_nonzero_unparseable_output(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_audit_module(script)
    _write_master_review_verdict(workspace)
    (workspace / "openspec").mkdir()
    _patch_openspec(monkeypatch, mod, which=lambda name: "/usr/bin/openspec", run=_fake_run("not json at all", returncode=1))
    violations = mod._audit_openspec_validation(workspace, workspace / ".architect-team")
    assert len(violations) == 1
    assert "failed at the Phase 7" in violations[0]


# ===========================================================================
# v3.47.0 — `_audit_check_integrity` (rule R1b: a check is not evidence until
# it has been shown able to fail).
#
# The run's diff adding test files is the trigger the evidence file cannot see:
# `tests.added >= 1` is true for every slice, and `files_changed` cannot tell an
# added file from a modified one. The audit CAN see it — it diffs the working
# tree against the run's baseline SHA — so added test files demand a
# verify-check-can-fail verdict on disk, and that verdict must pass.
#
# Untracked files count as added. The audit runs BEFORE the Phase 8 auto-commit,
# which is exactly when a freshly-written test file is still untracked; keying on
# the tracked diff alone would leave the arm silent in the one situation it
# exists for.
# ===========================================================================


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True, capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _init_repo_with_baseline(workspace: Path) -> str:
    """A real git repo with one commit; returns the baseline SHA."""
    _git(workspace, "init", "--initial-branch=main")
    _git(workspace, "config", "user.email", "test@example.com")
    _git(workspace, "config", "user.name", "Test User")
    (workspace / "README.md").write_text("baseline\n", encoding="utf-8")
    (workspace / ".gitignore").write_text(".architect-team/\n", encoding="utf-8")
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-m", "baseline")
    return _git(workspace, "rev-parse", "HEAD").stdout.strip()


def _write_intake(workspace: Path, **fields) -> None:
    body = {"run_id": "r-1"}
    body.update(fields)
    (_at(workspace) / "intake-state.json").write_text(json.dumps(body), encoding="utf-8")


def _add_file(workspace: Path, relpath: str, *, commit: bool = False) -> Path:
    path = workspace / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    if commit:
        _git(workspace, "add", relpath)
        _git(workspace, "commit", "-m", f"add {relpath}")
    return path


def _write_check_verdict(workspace: Path, *, valid: bool = True,
                         name: str = "task-a-check-can-fail.json",
                         verdict_at: str = "2026-07-30T12:00:00Z",
                         body: dict | None = None) -> Path:
    vd = _at(workspace) / "vao-verdicts"
    vd.mkdir(parents=True, exist_ok=True)
    path = vd / name
    payload = body if body is not None else {
        "tool": "verify-check-can-fail",
        "valid": valid,
        "gaps": [] if valid else [{"severity": "vacuous-check"}],
        "verdict_at": verdict_at,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_added_test_file_without_a_verdict_blocks(script: Path, workspace: Path) -> None:
    """Scenario: added tests with no verdict block completion."""
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "tests/test_new_guard.py" in r.stderr.replace("\\", "/")
    assert "verify-check-can-fail" in r.stderr


def test_committed_added_test_file_also_counts(script: Path, workspace: Path) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_committed_guard.py", commit=True)
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "test_committed_guard.py" in r.stderr


def test_added_test_file_with_a_passing_verdict_allows(script: Path, workspace: Path) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    _write_check_verdict(workspace, valid=True)
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_added_test_file_with_a_failing_verdict_blocks(script: Path, workspace: Path) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    _write_check_verdict(workspace, valid=False)
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "check-can-fail" in r.stderr


# --- B4 (adversarial, medium): EVERY verdict must pass, not just the "latest".
#
# The original arm picked a latest verdict via `str(verdict_at or path.name)`,
# comparing ISO timestamps against filenames in one ordering — so a passing
# verdict dated 9999-12-31, or an undated one named "zz-…", outranked a real
# failure. Worse, the directory legitimately holds one verdict PER GROUP
# (hei-group1..4), so "latest wins" let a later group's pass hide an earlier
# group's failure. Requiring every verdict to pass removes the ordering
# heuristic entirely; a re-run overwrites its own --out path, so only a
# genuinely unresolved failure lingers.

def test_a_failing_verdict_is_not_buried_by_a_future_dated_passing_one(
    script: Path, workspace: Path
) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    _write_check_verdict(workspace, valid=False, name="a-check-can-fail.json",
                         verdict_at="2026-07-31T04:00:00Z")
    _write_check_verdict(workspace, valid=True, name="b-check-can-fail.json",
                         verdict_at="9999-12-31T23:59:59Z")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_a_failing_verdict_is_not_buried_by_an_undated_passing_one(
    script: Path, workspace: Path
) -> None:
    """'zz' sorts above '2026' when a filename is compared against a timestamp."""
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    _write_check_verdict(workspace, valid=False, name="a-check-can-fail.json",
                         verdict_at="2026-07-31T04:00:00Z")
    _write_check_verdict(workspace, name="zz-check-can-fail.json",
                         body={"tool": "verify-check-can-fail", "valid": True})
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_one_groups_failure_is_not_hidden_by_another_groups_pass(
    script: Path, workspace: Path
) -> None:
    """The real shape: one verdict per group in the same directory."""
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    _write_check_verdict(workspace, valid=False, name="hei-group3-check-can-fail.json",
                         verdict_at="2026-07-31T03:00:00Z")
    _write_check_verdict(workspace, valid=True, name="hei-group4-check-can-fail.json",
                         verdict_at="2026-07-31T05:00:00Z")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "hei-group3" in r.stderr


def test_all_passing_verdicts_allow(script: Path, workspace: Path) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    _write_check_verdict(workspace, valid=True, name="hei-group3-check-can-fail.json",
                         verdict_at="2026-07-31T03:00:00Z")
    _write_check_verdict(workspace, valid=True, name="hei-group4-check-can-fail.json",
                         verdict_at="2026-07-31T05:00:00Z")
    assert _run_check(script, workspace).returncode == 0


# --- B5 (adversarial, medium): the arm must bite the RUN's files, not a
# developer's pre-existing scratch. `git ls-files --others` is repo-wide, so an
# untracked tests/test_developer_scratch.py that predates the run blocked a run
# that never touched it. Untracked files now count only when they are newer than
# the run's start (the active-run marker's started_at, else the baseline commit).

def _age_file(path: Path, seconds_before: float) -> None:
    import time as _t
    stamp = _t.time() - seconds_before
    os.utime(path, (stamp, stamp))


def test_untracked_file_predating_the_run_does_not_arm_the_gate(
    script: Path, workspace: Path
) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    scratch = _add_file(workspace, "tests/test_developer_scratch.py")
    _age_file(scratch, 60 * 60 * 24 * 30)  # a month old — long before this run
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_untracked_file_written_during_the_run_still_arms_the_gate(
    script: Path, workspace: Path
) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")  # written now
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_marker_started_at_is_the_preferred_run_start(script: Path,
                                                      workspace: Path) -> None:
    """With a marker present, its started_at defines the run — an untracked file
    older than the marker is not this run's work even if it postdates the
    baseline commit."""
    import datetime as _dt
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    scratch = _add_file(workspace, "tests/test_older_than_the_run.py")
    _age_file(scratch, 3600)  # an hour old
    started = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=5)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    (_at(workspace) / "active-run.json").write_text(
        json.dumps({"schema": 1, "status": "active", "slug": "s",
                    "session_id": None, "started_at": started,
                    "updated_at": started}),
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_unreadable_check_verdict_blocks(script: Path, workspace: Path) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    vd = _at(workspace) / "vao-verdicts"
    vd.mkdir(parents=True, exist_ok=True)
    (vd / "task-a-check-can-fail.json").write_text("{not json", encoding="utf-8")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_check_verdict_of_unknown_shape_blocks(script: Path, workspace: Path) -> None:
    """A verdict whose passing-ness cannot be read is not a pass."""
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    _write_check_verdict(workspace, body={"tool": "verify-check-can-fail", "notes": "fine"})
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_no_added_test_files_is_fail_open(script: Path, workspace: Path) -> None:
    """Scenario: no added tests is fail-open."""
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "src/feature.py")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_modified_test_file_is_not_an_added_test_file(script: Path, workspace: Path) -> None:
    _init_repo_with_baseline(workspace)
    _add_file(workspace, "tests/test_existing.py", commit=True)
    sha = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    _write_intake(workspace, baseline_sha=sha)
    (workspace / "tests" / "test_existing.py").write_text(
        "def test_x():\n    assert 1 == 1\n", encoding="utf-8"
    )
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_no_baseline_sha_is_fail_open(script: Path, workspace: Path) -> None:
    _init_repo_with_baseline(workspace)
    _write_intake(workspace)  # no baseline_sha recorded
    _add_file(workspace, "tests/test_new_guard.py")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_unknown_baseline_sha_is_fail_open(script: Path, workspace: Path) -> None:
    _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha="0" * 40)
    _add_file(workspace, "tests/test_new_guard.py")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_not_a_git_repo_is_fail_open(script: Path, workspace: Path) -> None:
    _write_intake(workspace, baseline_sha="deadbeef")
    _add_file(workspace, "tests/test_new_guard.py")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_baseline_sha_falls_back_to_a_teammate_manifest(script: Path, workspace: Path) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace)  # intake has none
    teammates = _at(workspace) / "teammates"
    teammates.mkdir(parents=True, exist_ok=True)
    (teammates / "backend.json").write_text(
        json.dumps({"teammate": "backend", "baseline_sha": sha,
                    "expected_review_evidence": []}),
        encoding="utf-8",
    )
    _add_file(workspace, "tests/test_new_guard.py")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_gitignored_files_are_not_added_tests(script: Path, workspace: Path) -> None:
    """The `.architect-team/` fixtures a run writes for itself are not new guards."""
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, ".architect-team/fixtures/test_scratch.py")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_check_integrity_stop_mode_blocks_the_same_way(script: Path, workspace: Path) -> None:
    sha = _init_repo_with_baseline(workspace)
    _write_intake(workspace, baseline_sha=sha)
    _add_file(workspace, "tests/test_new_guard.py")
    r = _run_stop(script, workspace, {})
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "verify-check-can-fail" in r.stderr
