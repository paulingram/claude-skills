#!/usr/bin/env python3
"""PostToolUse(TaskUpdate) hook for the architect-team plugin.

Blocks TaskUpdate from setting status to 'completed' when the review-gate
evidence file at .architect-team/reviews/<taskId>.json is missing or invalid.

The evidence schema + validation logic live in `review_evidence_schema.py`
(a sibling module) so this hook and `teammate-idle-check.py` cannot drift.

Exit codes:
- 0: allow
- 2: block (writes a structured error to stderr describing the gap)

Reads the hook payload from stdin (JSON).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from review_evidence_schema import safe_id, validate_evidence


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
            # A corrupt manifest cannot be used to recognise ownership; surface
            # it so the orchestrator notices, but keep scanning the others.
            print(
                f"review-gate-task: warning: manifest {manifest_path} is unreadable/"
                f"invalid JSON and was skipped while resolving task ownership.",
                file=sys.stderr,
            )
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

    if safe_id(str(task_id)) is None:
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

    gaps = validate_evidence(evidence)
    if gaps:
        print(
            f"review-gate-task: blocking task {task_id}: review evidence has gaps: "
            + "; ".join(gaps),
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
