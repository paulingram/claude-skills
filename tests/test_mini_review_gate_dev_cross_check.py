"""Backstop: the existing v6 review-evidence schema accepts the mini-pipeline's
dev↔dev cross-review pattern unmodified.

The full pipeline spawns a dedicated `task-reviewer` agent in Phase 3 and the
hook enforces `independent_review.reviewer != teammate` so the producer cannot
be its own checker. The mini variant skips the dedicated reviewer and instead
has the two dev teammates cross-review each other — the frontend dev signs off
backend's evidence and vice versa.

That cross-review pattern already satisfies the schema's only structural
producer-checker rule (`reviewer != teammate`): the reviewer of record is the
OTHER dev, never the teammate itself. This test pins that invariant so a future
schema tweak cannot silently break the mini variant — and also pins the
negative case so self-review (reviewer == teammate) remains rejected.

The function under test is `hooks/review_evidence_schema.py::validate_evidence`
(returns a list of human-readable gap descriptions; empty list = valid). The
payload shape mirrors `tests/test_independent_review.py::_valid_v5_evidence`
which is the in-tree canonical valid-v6 evidence example.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _import_schema(plugin_root: Path):
    """Import hooks/review_evidence_schema.py as a module — mirrors the loader
    pattern used by `tests/test_independent_review.py` so this test stays
    structurally aligned with the rest of the schema suite."""
    path = plugin_root / "hooks" / "review_evidence_schema.py"
    spec = importlib.util.spec_from_file_location(
        "review_evidence_schema_mini_t", path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_cross_review_evidence(teammate: str, reviewer: str) -> dict:
    """A structurally-valid v6 review-evidence dict parameterised by the
    teammate (producer) and the independent reviewer's identifier.

    The non-cross-review fields mirror the canonical valid-evidence helper in
    `test_independent_review.py` (`_valid_v5_evidence`) — keeping this test
    payload in lock-step with the rest of the schema test suite means it is
    the cross-review pairing alone that this test is asserting on.
    """
    return {
        "schema_version": 6,
        "task_id": "M4-T1",
        "teammate": teammate,
        "completed_at": "2026-05-26T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {
            "added": 2,
            "passing": 2,
            "unit": ["a", "b"],
            "integration": [],
            "e2e": [],
        },
        "demo_artifact": "curl http://dev.local/api",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": (
            "mini-variant slice; cross-review backstop test; no frontend "
            "files touched in this payload"
        ),
        "test_completeness_review": "n/a",
        "test_completeness_review_note": (
            "mini-variant slice; integration is the qualifying kind for this slice"
        ),
        "integration_testing_review": "n/a",
        "integration_testing_review_note": (
            "mini-variant slice with no cross-layer surface in this payload"
        ),
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": (
            "mini-variant slice; no UI/frontend interactive surface in this payload"
        ),
        # v7 VAO fields — all 'n/a' for the mini-variant cross-review fixture
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "mini-variant fixture; no oracle artifact in scope",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "mini-variant fixture; no real teammate tool-call log",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "mini-variant fixture; no production-code diff in scope",
        "adversarial_review": "n/a",
        "adversarial_review_note": "mini-variant fixture; mini collapses adversarial pairing to mini-qa",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "mini-variant fixture; no session transcript / ledger in scope",
        "independent_review": {
            "reviewer": reviewer,
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-05-26T11:00:00Z",
        },
    }


# --- positive cases: dev↔dev cross-review is accepted ----------------------


def test_frontend_reviews_backend_accepted(plugin_root: Path) -> None:
    """The mini variant's pattern: the frontend dev signs off the backend
    teammate's evidence. `reviewer != teammate` holds (frontend ≠ backend), so
    the existing v6 schema must accept it without modification."""
    module = _import_schema(plugin_root)
    payload = _valid_cross_review_evidence(teammate="backend", reviewer="frontend")
    gaps = module.validate_evidence(payload)
    assert gaps == [], (
        f"frontend reviewing backend (mini cross-review) must be accepted; "
        f"gaps={gaps}"
    )


def test_backend_reviews_frontend_accepted(plugin_root: Path) -> None:
    """The mirror: the backend dev signs off the frontend teammate's evidence.
    Same invariant, opposite direction; the schema must accept both."""
    module = _import_schema(plugin_root)
    payload = _valid_cross_review_evidence(teammate="frontend", reviewer="backend")
    gaps = module.validate_evidence(payload)
    assert gaps == [], (
        f"backend reviewing frontend (mini cross-review) must be accepted; "
        f"gaps={gaps}"
    )


# --- negative case: the reviewer != teammate invariant still holds ---------


def test_self_review_still_rejected(plugin_root: Path) -> None:
    """The mini variant must NOT collapse the producer-checker rule into a
    no-op. With `reviewer == teammate` the hook must still reject the evidence;
    only a cross-review (where the reviewer is the OTHER dev) opens the gate."""
    module = _import_schema(plugin_root)
    payload = _valid_cross_review_evidence(teammate="backend", reviewer="backend")
    gaps = module.validate_evidence(payload)
    assert gaps, (
        "self-review (reviewer == teammate) must still be rejected even in the "
        "mini variant — the producer cannot be its own checker"
    )
    joined = " ".join(gaps).lower()
    assert "reviewer" in joined and "teammate" in joined, gaps
