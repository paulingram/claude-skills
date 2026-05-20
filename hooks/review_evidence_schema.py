#!/usr/bin/env python3
"""Shared review-gate evidence schema for the architect-team hooks.

SINGLE SOURCE OF TRUTH for the evidence-file contract enforced by BOTH
`review-gate-task.py` (PostToolUse / TaskUpdate) and `teammate-idle-check.py`
(SubagentStop). Before v0.9.9 the two hooks each carried their own copy of the
schema and drifted: the idle hook validated 8 fields while the task hook
validated 11. Centralising the schema here makes that drift structurally
impossible — both hooks import this module.

This module is NOT a hook itself; it is never wired in hooks.json. The hook
scripts import it because, when a script is run as `python3 <hooks-dir>/x.py`,
the script's own directory is `sys.path[0]`, so a sibling module resolves.
"""
from __future__ import annotations

from typing import Any

# Evidence schema v4 (v0.9.5). Every field below is REQUIRED in a
# .architect-team/reviews/<task-id>.json evidence file.
REQUIRED_EVIDENCE_FIELDS = {
    "task_id",
    "spec_review",
    "quality_review",
    "real_not_stubbed",
    "tests",
    "demo_artifact",
    "files_changed",
    "reuse_compliance",
    "visual_fidelity_review",
    "test_completeness_review",
    "integration_testing_review",
}

VALID_VISUAL_FIDELITY_VALUES = {"pass", "n/a", "fail"}
VALID_TEST_COMPLETENESS_VALUES = {"pass", "n/a", "fail"}
VALID_INTEGRATION_TESTING_VALUES = {"pass", "n/a", "fail"}


def safe_id(value: str) -> str | None:
    """Return value if safe for use in a filesystem path component, else None.

    Rejects empty strings, values containing '/' or '\\', values starting with
    '.', and the exact string '..'. These cover every path-traversal vector for
    the controlled identifier sets (task IDs like 'T-1', subagent names like
    'backend-auth') that the hooks handle.
    """
    if not value:
        return None
    if "/" in value or "\\" in value:
        return None
    if value.startswith("."):
        return None
    if value == "..":
        return None
    return value


def validate_evidence(evidence: dict[str, Any]) -> list[str]:
    """Return a list of human-readable gap descriptions for a review-evidence
    dict. An empty list means the evidence is structurally valid.

    This is a STRUCTURAL validator — it confirms the fields are present and
    carry allowed values. It does NOT (and cannot, at hook time) verify that
    the claims are true; the deeper end-of-run cross-checks live in
    `pipeline-completion-audit.py`.
    """
    gaps: list[str] = []
    missing = REQUIRED_EVIDENCE_FIELDS - evidence.keys()
    if missing:
        gaps.append(f"missing fields: {sorted(missing)}")
        return gaps

    if evidence.get("spec_review") != "pass":
        gaps.append(f"spec_review={evidence.get('spec_review')!r} (need 'pass')")
    if evidence.get("quality_review") != "pass":
        gaps.append(f"quality_review={evidence.get('quality_review')!r} (need 'pass')")
    if evidence.get("real_not_stubbed") is not True:
        gaps.append("real_not_stubbed must be true")
    if evidence.get("reuse_compliance") != "ok":
        gaps.append(f"reuse_compliance={evidence.get('reuse_compliance')!r} (need 'ok')")

    tests = evidence.get("tests")
    if not isinstance(tests, dict):
        gaps.append("tests must be an object")
    else:
        added = tests.get("added")
        passing = tests.get("passing")
        if not isinstance(added, int) or not isinstance(passing, int):
            gaps.append("tests.added and tests.passing must be integers")
        else:
            if added < 1:
                gaps.append("tests.added must be >= 1")
            if added != passing:
                gaps.append(f"tests.added ({added}) != tests.passing ({passing})")

    demo = evidence.get("demo_artifact")
    if not isinstance(demo, str) or not demo.strip():
        gaps.append("demo_artifact must be a non-empty string")

    files = evidence.get("files_changed")
    if not isinstance(files, list) or not files:
        gaps.append("files_changed must be a non-empty array")

    vfr = evidence.get("visual_fidelity_review")
    if vfr not in VALID_VISUAL_FIDELITY_VALUES:
        gaps.append(
            f"visual_fidelity_review={vfr!r} must be one of "
            f"{sorted(VALID_VISUAL_FIDELITY_VALUES)}"
        )
    elif vfr == "fail":
        gaps.append(
            "visual_fidelity_review='fail' — drift or gaps detected by "
            "visual-fidelity-reconciliation MUST be escalated via handoff to the "
            "architect-team, not marked complete. Re-run reconciliation after the "
            "architect-routed fix lands and only mark complete when verdict is 'pass'."
        )
    elif vfr == "n/a":
        note = evidence.get("visual_fidelity_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "visual_fidelity_review='n/a' requires a non-empty "
                "visual_fidelity_review_note explaining why (no frontend files "
                "touched, OR no DESIGN_MAP.md exists for the codebase)"
            )

    tcr = evidence.get("test_completeness_review")
    if tcr not in VALID_TEST_COMPLETENESS_VALUES:
        gaps.append(
            f"test_completeness_review={tcr!r} must be one of "
            f"{sorted(VALID_TEST_COMPLETENESS_VALUES)}"
        )
    elif tcr == "fail":
        gaps.append(
            "test_completeness_review='fail' — test-kind completeness gaps detected by "
            "the test-completeness-verifier MUST be escalated via the SR auto-spawn "
            "(origin.kind: 'test-completeness-failure'), not marked complete. "
            "The verifier writes the SR automatically; wait for the orchestrator to "
            "re-spawn the fix loop, then re-run the verifier to reach 'pass'."
        )
    elif tcr == "n/a":
        note = evidence.get("test_completeness_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "test_completeness_review='n/a' requires a non-empty "
                "test_completeness_review_note explaining which kind(s) are "
                "inapplicable and why (e.g., backend-only slice with no testable "
                "pure-logic surface for unit tests, OR no frontend touched so "
                "Playwright is n/a)"
            )

    itr = evidence.get("integration_testing_review")
    if itr not in VALID_INTEGRATION_TESTING_VALUES:
        gaps.append(
            f"integration_testing_review={itr!r} must be one of "
            f"{sorted(VALID_INTEGRATION_TESTING_VALUES)}"
        )
    elif itr == "fail":
        gaps.append(
            "integration_testing_review='fail' — this slice's user-flow / "
            "integration tests ran against a MOCKED or FAKE backend (page.route "
            "happy-path stubs, MSW handlers, an in-memory fake API server, or "
            "hardcoded response fixtures) instead of the real running backend. "
            "For any feature spanning both frontend and backend, the tests MUST "
            "exercise the real backend with real data flow front-to-back unless "
            "the requirements explicitly authorize isolated testing. Re-author the "
            "tests against the real backend (or escalate via SR origin.kind "
            "'integration-testing-failure'); do not mark complete."
        )
    elif itr == "n/a":
        note = evidence.get("integration_testing_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "integration_testing_review='n/a' requires a non-empty "
                "integration_testing_review_note giving ONE of the three "
                "legitimate reasons: (1) this slice has no cross-layer surface "
                "(pure static frontend with no backend, OR backend-only slice "
                "with no frontend); (2) Phase 3 per-team gate where the "
                "counterpart layer is not yet integrated and front-to-back "
                "testing is explicitly DEFERRED TO PHASE 5 integration; (3) the "
                "requirements folder explicitly authorizes isolated / mock-backed "
                "testing for this requirement — quote the authorization."
            )

    return gaps
