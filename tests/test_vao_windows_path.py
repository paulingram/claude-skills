"""A3 (review-remediation): hooks/vao_tools.py verify_no_pipeline_bypass must
count a review-evidence write whose ledger path uses Windows backslashes.

The ledger-scanner previously tested the forward-slash `/reviews/` substring
against the RAW path, so a Windows path like
`C:\\ws\\.architect-team\\reviews\\T-1.json` never matched and the gate emitted
a false `independent-review-bypassed`. The fix normalizes backslashes ->
forward slashes (and lowercases) BEFORE the membership test, mirroring the
openspec check immediately below it.
"""
from __future__ import annotations

from pathlib import Path

from hooks.vao_tools import (
    _scan_ledger_for_pipeline_elements,
    verify_no_pipeline_bypass,
)


def _ledger_with_backslash_review() -> list[dict]:
    """A minimal ledger: a Skill invocation, an Agent dispatch, an openspec
    bash call, and a review-evidence Write whose path uses BACKSLASHES."""
    return [
        {"tool": "Skill", "input": {"name": "architect-team-pipeline"}},
        {"tool": "Agent", "input": {"subagent_type": "backend"}},
        {"tool": "Bash", "input": {"command": "openspec validate --all --strict"}},
        {
            "tool": "Write",
            "input": {
                # Windows-style backslash path — the exact A3 regression shape.
                "file_path": r"C:\workspace\.architect-team\reviews\T-1.json",
                "content": "{}",
            },
        },
    ]


def test_scanner_counts_backslash_review_path() -> None:
    counts = _scan_ledger_for_pipeline_elements(_ledger_with_backslash_review())
    assert counts["review_evidence_files"] >= 1, (
        "a backslash .architect-team\\reviews\\*.json write was not counted as "
        "review evidence (A3 path-normalization regression)"
    )


def test_scanner_counts_loose_backslash_reviews_dir() -> None:
    """The loose `/reviews/` form (not under .architect-team) also normalizes."""
    ledger = [
        {"tool": "Skill", "input": {"name": "architect-team-pipeline"}},
        {
            "tool": "Write",
            "input": {"file_path": r"D:\proj\reviews\BD-1.json", "content": "{}"},
        },
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["review_evidence_files"] >= 1


def test_no_false_independent_review_bypassed_for_backslash_path() -> None:
    """End-to-end: a pipeline run whose ONLY review evidence is a backslash
    path must NOT emit `independent-review-bypassed`."""
    verdict = verify_no_pipeline_bypass(
        user_prompt="/architect-team build the dashboard",
        toolcall_ledger=_ledger_with_backslash_review(),
        final_report="Done. Review evidence written.",
    )
    severities = {g["severity"] for g in verdict["gaps"]}
    assert "independent-review-bypassed" not in severities, (
        f"false independent-review-bypassed emitted for a backslash review "
        f"path; gaps={verdict['gaps']!r}"
    )


def test_forward_slash_path_still_counts_unchanged() -> None:
    """Regression guard: the forward-slash path that already worked still
    counts (the fix is additive, not a behavior swap)."""
    ledger = [
        {"tool": "Skill", "input": {"name": "architect-team-pipeline"}},
        {
            "tool": "Write",
            "input": {
                "file_path": "/home/u/ws/.architect-team/reviews/T-2.json",
                "content": "{}",
            },
        },
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["review_evidence_files"] >= 1


def test_non_json_review_path_still_not_counted() -> None:
    """A non-.json write under reviews/ is still NOT evidence (the parens-fix
    contract is preserved under normalization)."""
    ledger = [
        {"tool": "Skill", "input": {"name": "architect-team-pipeline"}},
        {
            "tool": "Write",
            "input": {
                "file_path": r"C:\ws\.architect-team\reviews\notes.txt",
                "content": "scratch",
            },
        },
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["review_evidence_files"] == 0
