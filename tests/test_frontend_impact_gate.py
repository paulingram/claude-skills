# -*- coding: utf-8 -*-
"""Tests for the v3.44.0 frontend-impact end-to-end gate in validate_evidence.

The owner directive: a change with frontend impact can NEVER be marked "done" on
a unit test alone — a real-frontend end-to-end verdict is mandatory. This encodes
that as a hard, structural gate: when `files_changed` contains frontend files,
`frontend_impact_e2e_review` is REQUIRED and must be 'pass'. Backward-compatible:
a backend-only change (the common case, and CT6's own only case) is unaffected.
"""
from __future__ import annotations

from hooks.review_evidence_schema import validate_evidence


def _base_evidence() -> dict:
    """A structurally-valid backend-only review-evidence dict (no frontend impact)."""
    return {
        "schema_version": 7,
        "task_id": "T-1",
        "teammate": "backend-auth",
        "completed_at": "2026-07-24T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 2, "passing": 2, "unit": ["a", "b"], "integration": [], "e2e": []},
        "demo_artifact": "curl http://dev.local/api",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "backend-only slice; no frontend files touched",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "backend-only slice; integration is the qualifying kind",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "backend-only slice with no frontend; no cross-layer surface",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "backend-only slice; no UI/frontend interactive surface",
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "synthetic test fixture; no oracle artifact in scope",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "synthetic test fixture; no real teammate tool-call log",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "synthetic test fixture; no production-code diff in scope",
        "adversarial_review": "n/a",
        "adversarial_review_note": "synthetic test fixture; no Phase 3 adversarial dispatch in scope",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "synthetic test fixture; no session transcript / ledger in scope",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-07-24T11:00:00Z",
        },
    }


def _gaps_mentioning(gaps: list[str], needle: str) -> list[str]:
    return [g for g in gaps if needle in g]


# --------------------------------------------------------------------------- #
# no frontend impact — backward-compatible (the field is optional)
# --------------------------------------------------------------------------- #

def test_backend_only_evidence_without_the_field_passes() -> None:
    ev = _base_evidence()
    assert "frontend_impact_e2e_review" not in ev
    assert validate_evidence(ev) == []


def test_backend_only_with_bad_field_shape_still_validated() -> None:
    ev = _base_evidence()
    ev["frontend_impact_e2e_review"] = "fail"  # no impact, but a present 'fail' still blocks
    assert _gaps_mentioning(validate_evidence(ev), "frontend_impact_e2e_review")


# --------------------------------------------------------------------------- #
# frontend impact — the hard gate
# --------------------------------------------------------------------------- #

def test_frontend_change_with_only_a_unit_test_is_blocked() -> None:
    """THE grievance, encoded: frontend files changed, evidence carries a passing
    unit test but NO end-to-end verdict → the gate blocks 'done'."""
    ev = _base_evidence()
    ev["files_changed"] = ["src/Dashboard.tsx", "src/api_client.py"]
    # (unit tests present, but no frontend_impact_e2e_review)
    gaps = validate_evidence(ev)
    assert _gaps_mentioning(gaps, "frontend impact detected"), gaps


def test_frontend_change_with_passing_e2e_verdict_opens_the_gate() -> None:
    ev = _base_evidence()
    ev["files_changed"] = ["src/Dashboard.tsx"]
    ev["frontend_impact_e2e_review"] = "pass"
    assert validate_evidence(ev) == []


def test_frontend_change_with_failing_e2e_verdict_is_blocked() -> None:
    ev = _base_evidence()
    ev["files_changed"] = ["src/Dashboard.tsx"]
    ev["frontend_impact_e2e_review"] = "fail"
    assert _gaps_mentioning(validate_evidence(ev), "frontend_impact_e2e_review")


def test_frontend_change_na_without_note_is_blocked() -> None:
    ev = _base_evidence()
    ev["files_changed"] = ["theme.css"]
    ev["frontend_impact_e2e_review"] = "n/a"  # no authorization note
    assert _gaps_mentioning(validate_evidence(ev), "frontend_impact_e2e_review")


def test_frontend_change_na_with_authorization_note_passes() -> None:
    ev = _base_evidence()
    ev["files_changed"] = ["theme.css"]
    ev["frontend_impact_e2e_review"] = "n/a"
    ev["frontend_impact_e2e_review_note"] = "comment-only CSS change; no rendered behavior affected"
    assert validate_evidence(ev) == []


def test_frontend_change_with_dict_shape_pass_requires_verdict_path() -> None:
    ev = _base_evidence()
    ev["files_changed"] = ["src/Dashboard.tsx"]
    # dict-shape 'pass' without a verdict_path citation is rejected (the pass must
    # cite the real e2e verdict JSON — a bare claim can't open the gate)
    ev["frontend_impact_e2e_review"] = {"verdict": "pass"}
    assert _gaps_mentioning(validate_evidence(ev), "verdict_path")
    # with the citation it opens
    ev["frontend_impact_e2e_review"] = {
        "verdict": "pass",
        "verdict_path": ".architect-team/vao-verdicts/run-1-fe-e2e.json",
    }
    assert validate_evidence(ev) == []
