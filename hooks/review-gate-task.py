#!/usr/bin/env python3
"""PostToolUse(TaskUpdate) hook for the architect-team plugin.

Blocks TaskUpdate from setting status to 'completed' when the review-gate
evidence file at .architect-team/reviews/<taskId>.json is missing or invalid.

Exit codes:
- 0: allow
- 2: block (writes a structured error to stderr describing the gap)

Reads the hook payload from stdin (JSON).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


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
}

VALID_VISUAL_FIDELITY_VALUES = {"pass", "n/a", "fail"}
VALID_TEST_COMPLETENESS_VALUES = {"pass", "n/a", "fail"}


def _safe_id(value: str) -> str | None:
    """Return value if safe for use in a filesystem path component, else None.

    Rejects empty strings, values containing '/' or '\\', values starting with
    '.', and the exact string '..'.  These cover every path-traversal vector
    for the controlled identifier sets (task IDs like 'T-1', 'REQ-001') that
    the hooks handle.
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


def _is_teammate_task(task_id: str, cwd: Path) -> bool:
    """Return True if task_id appears in any teammate manifest's expected_review_evidence.

    This scopes the hook: it only enforces the review gate on tasks that an
    architect-team orchestrator has explicitly assigned to a teammate via a
    manifest at .architect-team/teammates/<name>.json. Orchestrator-internal
    and user task tracking (TaskCreate/TaskUpdate outside the architect-team
    pipeline) is left alone.
    """
    teammates_dir = cwd / ".architect-team" / "teammates"
    if not teammates_dir.is_dir():
        return False
    for manifest_path in teammates_dir.glob("*.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        expected = manifest.get("expected_review_evidence") or []
        if isinstance(expected, list) and task_id in expected:
            return True
    return False


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as e:
        print(f"review-gate-task: malformed hook payload: {e}", file=sys.stderr)
        return 0  # don't block on hook-side decode errors

    if payload.get("tool_name") != "TaskUpdate":
        return 0

    tool_input = payload.get("tool_input") or {}
    task_id = tool_input.get("taskId")
    status = tool_input.get("status")

    if status != "completed":
        return 0
    if not task_id:
        # No taskId on a completed TaskUpdate — can't look up a manifest, so
        # we cannot tell whether this is a teammate task. Default to allow
        # rather than block: false positives would break every other plugin /
        # workflow that uses TaskUpdate without architect-team semantics.
        return 0

    if _safe_id(str(task_id)) is None:
        print(
            f"review-gate-task: blocking TaskUpdate: task_id {task_id!r} contains "
            f"path-traversal characters and was rejected.",
            file=sys.stderr,
        )
        return 2

    # Scope: only enforce on tasks an architect-team orchestrator has assigned.
    if not _is_teammate_task(str(task_id), Path.cwd()):
        return 0

    evidence_path = Path.cwd() / ".architect-team" / "reviews" / f"{task_id}.json"
    if not evidence_path.exists():
        print(
            f"review-gate-task: blocking TaskUpdate(task_id={task_id}, status=completed): "
            f"missing review evidence at {evidence_path}. "
            f"Write the evidence file before marking complete.",
            file=sys.stderr,
        )
        return 2

    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(
            f"review-gate-task: blocking task {task_id}: evidence at {evidence_path} is not valid JSON: {e}",
            file=sys.stderr,
        )
        return 2

    gaps = _validate(evidence)
    if gaps:
        print(
            f"review-gate-task: blocking task {task_id}: review evidence has gaps: "
            + "; ".join(gaps),
            file=sys.stderr,
        )
        return 2

    return 0


def _validate(evidence: dict[str, Any]) -> list[str]:
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
                gaps.append("tests.added must be ≥ 1")
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

    return gaps


if __name__ == "__main__":
    sys.exit(main())
