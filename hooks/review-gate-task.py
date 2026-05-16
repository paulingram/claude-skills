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
}


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
        print("review-gate-task: TaskUpdate→completed without taskId; blocking", file=sys.stderr)
        return 2

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

    return gaps


if __name__ == "__main__":
    sys.exit(main())
