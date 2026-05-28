#!/usr/bin/env python3
"""Review-gate hook for the architect-team plugin.

Blocks task completion when the review-gate evidence file at
`.architect-team/reviews/<task-id>.json` is missing or invalid.

This hook serves TWO trigger shapes (one source of enforcement, two
dispatch points):

- **Subagents mode** (the v0.9.x dispatch shape): wired to `PostToolUse` on
  `TaskUpdate`. The payload carries `tool_name: "TaskUpdate"` and
  `tool_input: {taskId, status}`. The hook fires when a teammate calls
  `TaskUpdate(taskId=..., status="completed")`.
- **Teams mode** (the v1.0.0 agent-teams shape): wired to `TaskCompleted`.
  The payload carries `hook_event_name: "TaskCompleted"` and a task
  identifier under `task.id` (per https://code.claude.com/docs/en/hooks).
  The hook fires when a teammate marks a shared-task-list item complete.

In BOTH modes the enforcement is identical: read
`.architect-team/reviews/<task-id>.json`, validate the v6 schema, exit 2
with the same structured feedback if anything is wrong.

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
from typing import Any

from review_evidence_schema import _detect_trigger_mode, safe_id, validate_evidence


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


def _extract_task_id_and_status(
    payload: dict[str, Any], mode: str
) -> tuple[str | None, str | None]:
    """Return (task_id, status) from a hook payload, branching by trigger mode.

    Subagents mode (PostToolUse + TaskUpdate): `tool_input.taskId` + `tool_input.status`.
    Only fires when `tool_name == "TaskUpdate"`.

    Teams mode (TaskCompleted): the task identifier lives at `task.id` per the
    agent-teams hook docs; the event firing IS the "completed" signal — there is
    no separate status field — so we synthesize `status="completed"` to route
    through the same enforcement code path. Some harness emissions may put the
    id at `taskId` directly on the payload; we accept that too.
    """
    if mode == "teams":
        # TaskCompleted payload — by definition the task just transitioned to
        # completed; the event firing IS the status signal.
        task_obj = payload.get("task")
        task_id: Any = None
        if isinstance(task_obj, dict):
            task_id = task_obj.get("id") or task_obj.get("taskId")
        if not task_id:
            # Tolerate flatter payload shapes some harnesses may emit.
            task_id = payload.get("task_id") or payload.get("taskId")
        return (str(task_id) if task_id else None, "completed")

    # subagents mode — PostToolUse(TaskUpdate) shape.
    if payload.get("tool_name") != "TaskUpdate":
        return (None, None)
    tool_input = payload.get("tool_input") or {}
    return (tool_input.get("taskId"), tool_input.get("status"))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as e:
        print(f"review-gate-task: malformed hook payload: {e}", file=sys.stderr)
        return 0  # don't block on hook-side decode errors

    mode = _detect_trigger_mode(payload)
    task_id, status = _extract_task_id_and_status(payload, mode)

    # Subagents mode: a PostToolUse hook fires on every TaskUpdate of every
    # tool; ignore anything that isn't a TaskUpdate-with-completed-status.
    # Teams mode: TaskCompleted fires only on completion, so status is always
    # synthesized "completed" — but we still skip if we couldn't find a task_id.
    if status != "completed":
        return 0
    if not task_id:
        # No task_id on a completed event — can't look up a manifest, so we
        # cannot tell whether this is a teammate task. Default to allow rather
        # than block: false positives would break every other plugin / workflow
        # that uses the trigger without architect-team semantics.
        return 0

    if safe_id(str(task_id)) is None:
        print(
            f"review-gate-task: blocking task completion: task_id {task_id!r} contains "
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
            f"review-gate-task: blocking task completion (task_id={task_id}): "
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
