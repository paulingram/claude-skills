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

# Evidence schema v6 (v0.9.19 added the required `ui_interaction_review` field —
# a hook-enforced gate confirming every interactive element is genuinely
# UI-tested, every page is the real live page rather than a placeholder, and
# every displayed value is correctly static or dynamically bound — or a
# user-confirmed stub; the same path `visual_fidelity_review` (v0.5.0),
# `test_completeness_review` (v0.9.0) and `integration_testing_review` (v0.9.5)
# each took via a SCHEMA_VERSION bump. v5 (v0.9.13) added the required
# `independent_review` block — the verdict of an independent `task-reviewer`
# agent, so the Phase 3 gate structurally cannot pass on the teammate's
# self-attestation). The 12 fields below are the teammate's OWN self-review and
# remain REQUIRED in every .architect-team/reviews/<task-id>.json evidence file.
SCHEMA_VERSION = 6

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
    "ui_interaction_review",
}

VALID_VISUAL_FIDELITY_VALUES = {"pass", "n/a", "fail"}
VALID_TEST_COMPLETENESS_VALUES = {"pass", "n/a", "fail"}
VALID_INTEGRATION_TESTING_VALUES = {"pass", "n/a", "fail"}
VALID_UI_INTERACTION_VALUES = {"pass", "n/a", "fail"}

# v5 (v0.9.13). The `independent_review` block is written by an independent
# `task-reviewer` agent — NOT the teammate. Its sub-fields below are all
# REQUIRED, and `reviewer` MUST NOT equal the top-level `teammate` field: the
# producer cannot be its own checker.
REQUIRED_INDEPENDENT_REVIEW_FIELDS = {
    "reviewer",
    "verdict",
    "spec_review",
    "quality_review",
    "real_not_stubbed",
    "reuse_compliance",
    "reviewed_at",
}


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
    carry allowed values. It cannot, at hook time, verify the teammate's own
    self-review CLAIMS are true; that is exactly why the v5 schema requires an
    `independent_review` block written by a separate `task-reviewer` agent that
    read the same task's diff — and why this validator enforces
    `independent_review.reviewer != teammate`: the producer cannot be its own
    checker. The deeper end-of-run cross-checks live in
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

    uir = evidence.get("ui_interaction_review")
    if uir not in VALID_UI_INTERACTION_VALUES:
        gaps.append(
            f"ui_interaction_review={uir!r} must be one of "
            f"{sorted(VALID_UI_INTERACTION_VALUES)}"
        )
    elif uir == "fail":
        gaps.append(
            "ui_interaction_review='fail' — the interaction-completeness review "
            "found an unwired control, an unconfirmed placeholder page, or a "
            "hardcoded value that context shows should be dynamically bound. An "
            "interactive element must be genuinely user-flow-tested or a "
            "user-confirmed stub; a route must reach the real live page, not a "
            "placeholder; a dynamic value must be bound to its data source. Such "
            "a gap MUST be escalated via a solution requirement (origin.kind "
            "'unwired-control' / 'placeholder-page' / 'hardcoded-dynamic-value'), "
            "not marked complete. Re-run the interaction-completeness team after "
            "the routed fix lands and only mark complete when the verdict is 'pass'."
        )
    elif uir == "n/a":
        note = evidence.get("ui_interaction_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "ui_interaction_review='n/a' requires a non-empty "
                "ui_interaction_review_note explaining why (this slice has no "
                "UI/frontend interactive surface — no interactive elements, no "
                "pages / screens / routes — e.g., a backend-only or pure-infra "
                "slice)"
            )

    gaps += _validate_independent_review(evidence)

    return gaps


def _validate_independent_review(evidence: dict[str, Any]) -> list[str]:
    """Return gap descriptions for the `independent_review` block.

    The 12 top-level fields are the TEAMMATE's self-review. They are a cheap
    first pass — a teammate can write a perfectly-conformant self-review that
    lies, and shape validation cannot tell. The `independent_review` block is
    the verdict of an independent `task-reviewer` agent that read the same
    task's diff: it is REQUIRED, and its `reviewer` MUST NOT equal the
    top-level `teammate` field, so the Phase 3 gate cannot open on
    self-attestation — the producer cannot be its own checker.
    """
    gaps: list[str] = []
    review = evidence.get("independent_review")
    if review is None:
        gaps.append(
            "missing the required 'independent_review' block — the Phase 3 gate "
            "cannot open on the teammate's self-review alone; an independent "
            "task-reviewer agent must review the task's diff and write this block"
        )
        return gaps
    if not isinstance(review, dict):
        gaps.append("independent_review must be an object")
        return gaps

    missing = REQUIRED_INDEPENDENT_REVIEW_FIELDS - review.keys()
    if missing:
        gaps.append(f"independent_review is missing fields: {sorted(missing)}")
        return gaps

    # The `reviewer != teammate` check below is the headline anti-self-attestation
    # guarantee — but it can only run if the evidence carries a usable `teammate`.
    # `teammate` is NOT in REQUIRED_EVIDENCE_FIELDS, so an evidence file could omit
    # it and silently no-op the check. Because `independent_review` is always
    # required in v5, requiring `teammate` here makes it mandatory by design: the
    # producer-cannot-be-its-own-checker rule has no meaning without it.
    teammate = evidence.get("teammate")
    teammate_ok = isinstance(teammate, str) and bool(teammate.strip())
    if not teammate_ok:
        gaps.append(
            "evidence must carry a non-empty 'teammate' field — the "
            "independent_review.reviewer != teammate check cannot run without it"
        )

    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        gaps.append("independent_review.reviewer must be a non-empty string")
    elif teammate_ok and reviewer.strip() == teammate.strip():
        gaps.append(
            f"independent_review.reviewer ({reviewer!r}) equals the teammate "
            f"({teammate!r}) — the producer cannot be its own checker; the "
            f"independent review must be written by a different agent"
        )

    if review.get("verdict") != "pass":
        gaps.append(
            f"independent_review.verdict={review.get('verdict')!r} (need 'pass') — "
            f"a non-pass verdict means the task-reviewer found the task incomplete; "
            f"the teammate must re-engage on the reviewer's per-gap notes"
        )

    if review.get("spec_review") != "pass":
        gaps.append(
            f"independent_review.spec_review={review.get('spec_review')!r} (need 'pass')"
        )
    if review.get("quality_review") != "pass":
        gaps.append(
            f"independent_review.quality_review={review.get('quality_review')!r} "
            f"(need 'pass')"
        )
    if review.get("real_not_stubbed") is not True:
        gaps.append("independent_review.real_not_stubbed must be true")
    if review.get("reuse_compliance") != "ok":
        gaps.append(
            f"independent_review.reuse_compliance={review.get('reuse_compliance')!r} "
            f"(need 'ok')"
        )

    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        gaps.append("independent_review.reviewed_at must be a non-empty string")

    return gaps
