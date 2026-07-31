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
import os
import sys
from pathlib import Path
from typing import Any

from review_evidence_schema import _detect_trigger_mode, safe_id, validate_evidence

# v3.47.0 — the run-continuity substrate backs the completion-status gate below
# (active-run marker + the shared session basis). MODULE-object import with the
# house dual-form fallback; unavailable => the gate is inert and this hook
# behaves exactly as pre-v3.47.0 (fail open).
try:  # pragma: no cover - exercised by both import paths
    from hooks import run_continuity as _rc
except ImportError:  # pragma: no cover - bare-module fallback
    try:
        import run_continuity as _rc  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - substrate unavailable
        _rc = None  # type: ignore[assignment]

# The kill-switch for the unmanifested-task gate. This hook fires for EVERY
# TaskUpdate in every workflow, so the one enforcement arm that can block a task
# no manifest claims ships with an off switch a human can set without touching
# the plugin.
TASK_GATE_DISABLE_ENV = "CT6_TASK_GATE_DISABLED"


def _read_stdin_utf8() -> str:
    """Read the hook payload from stdin as UTF-8 (A8 review-remediation).

    Decodes the raw stdin bytes as `utf-8` with `errors="replace"` instead of
    the locale codec so a UTF-8 payload (e.g. an emoji in a task title) cannot
    raise `UnicodeDecodeError` under cp1252 and silently no-op the gate. Falls
    back to the text stream when `sys.stdin.buffer` is unavailable."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


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


def _is_registered_task(task_id: str, cwd: Path) -> bool:
    """True if ANY teammate manifest mentions ``task_id`` in any of its id fields.

    Deliberately WIDER than `_is_teammate_task`, and used for a different
    question. `_is_teammate_task` asks "does this task owe an evidence file?" and
    reads only `expected_review_evidence`. This asks "has the run registered this
    task to somebody at all?" and also reads `shared_task_id` (the Agent-Teams
    board id) and `task_ids` (the tasks.md ids) — the two fields a CT6 manifest
    uses to record the SAME work under different id spaces.

    Only the completion-status gate consults it, and only to stand down: the
    postmortem hole is an arbitrary board item flipped to `completed` that no
    manifest mentions anywhere, not a teammate closing the board task its own
    manifest names. Widening here cannot weaken the evidence gate, which is
    still scoped by `_is_teammate_task` alone.
    """
    teammates_dir = cwd / ".architect-team" / "teammates"
    if not teammates_dir.is_dir():
        return False
    for manifest_path in teammates_dir.glob("*.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # already surfaced by _is_teammate_task's warning
        if not isinstance(manifest, dict):
            continue
        for field in ("expected_review_evidence", "task_ids"):
            values = manifest.get(field)
            if isinstance(values, list) and any(str(v) == task_id for v in values):
                return True
        shared = manifest.get("shared_task_id")
        if shared is not None and str(shared) == task_id:
            return True
    return False


def _task_gate_disabled() -> bool:
    """True when CT6_TASK_GATE_DISABLED is set truthy (same truthiness rule as
    the run-continuity kill-switch: anything but unset / 0 / false / no)."""
    v = os.environ.get(TASK_GATE_DISABLE_ENV, "").strip().lower()
    return v not in ("", "0", "false", "no")


def _unmanifested_task_block(task_id: str, cwd: Path, payload: dict[str, Any]) -> str | None:
    """The block message for an orchestrator completing an UNMANIFESTED task
    during an active run — or None to allow.

    v3.47.0 (postmortem rule R3 — never accept a completion status from the
    producer). `_is_teammate_task` scopes the evidence gate to tasks a manifest
    claims; everything else was allowed, so an orchestrator could flip its own
    board items to `completed` mid-run with no evidence anywhere and then relay
    those statuses to the user as fact. This arm closes that, and ONLY that:

      (a) an ACTIVE, non-stale run marker exists (`.architect-team/active-run.json`),
      (b) the completing session belongs to the run — the same
          `run_continuity.is_orchestrator_session` basis the Stop audit uses,
      (c) NO teammate manifest registers the task id in any of its id fields
          (`expected_review_evidence` / `shared_task_id` / `task_ids`),
      (d) neither kill-switch (`CT6_TASK_GATE_DISABLED`,
          `CT6_RUN_CONTINUITY_DISABLED`) is set.

    Every other direction fails OPEN — no marker, an inactive or stale marker, a
    null marker session (pre-upgrade markers), a payload with no session, an
    unreadable marker, or a missing substrate. Foreign workflows and plain user
    task tracking are left exactly as they were.

    ON `Path.cwd()`. The sibling `hooks/pretool_skill_gate.py` deliberately
    refuses to fall back to the hook process's own cwd, because ambient state
    must not gate an unrelated payload. This hook resolves state from cwd
    because that is how it has always scoped itself — `_is_teammate_task` reads
    the same directory — and because the session test narrows the blast radius
    to the run's own actors: a completion from any other session is allowed
    regardless of what state happens to sit in cwd. Consistent within this hook,
    deliberately different from its sibling (adversarial-review observation).

    WHY (c) EXISTS. The requirement was written expecting condition (b) to
    separate the orchestrator from its teammates. In CT6's DEFAULT dispatch mode
    (Agent Teams) it does not: the Lead and every teammate run under ONE
    `CLAUDE_CODE_SESSION_ID` and one transcript, so (b) is true for all of them.
    Verified in a live run — the marker's recorded session equalled the session
    of a teammate completing its own board task, and the gate blocked it. On (b)
    alone every teammate's completion is blocked and the run wedges at the exact
    moment each group finishes. (c) restores the intended target: what still
    blocks is a task NO manifest mentions anywhere — the arbitrary board item
    flipped to `completed`, which is what the postmortem actually described.
    """
    if _rc is None:
        return None
    try:
        if _task_gate_disabled() or _rc.continuity_disabled():
            return None
        if _is_registered_task(task_id, cwd):
            return None  # the run assigned this task to somebody; not the hole
        marker = _rc.read_marker(cwd)
        if not isinstance(marker, dict) or marker.get("status") != "active":
            return None
        if _rc.marker_is_stale(marker):
            return None  # an abandoned run must not tax the workspace forever
        session_id = payload.get("session_id") or payload.get("sessionId")
        if not _rc.is_orchestrator_session(marker, session_id if isinstance(session_id, str) else None):
            return None
    except Exception:
        return None  # a gate bug must never wedge an unrelated workflow

    slug = marker.get("slug") or marker.get("run_id") or "(unnamed)"
    return (
        f"review-gate-task: blocking task completion (task_id={task_id}): the "
        f"architect-team run '{slug}' is ACTIVE, this completion comes from the "
        f"run's own session, and NO teammate manifest mentions {task_id!r} "
        f"anywhere — not in expected_review_evidence, not as a shared_task_id, "
        f"not in task_ids. A completion status inside a run is a claim until "
        f"evidence backs it — the producer's own 'done' is an input to "
        f"verification, not a substitute for it.\n"
        f"Resolve it one of three ways:\n"
        f"  1. Register the task to the teammate who owns the work: add "
        f"{task_id!r} to that manifest's expected_review_evidence "
        f"(.architect-team/teammates/<name>.json) and complete it through the "
        f"evidence flow (.architect-team/reviews/{task_id}.json) — or, if the "
        f"work is already tracked under another id, record it as that "
        f"manifest's shared_task_id / task_ids entry.\n"
        f"  2. If this id is a stray board item that duplicates work tracked "
        f"elsewhere, delete it rather than marking it done — an unregistered "
        f"'completed' is exactly the status the run cannot verify.\n"
        f"  3. If this task is genuinely outside the run's evidence contract, "
        f"set {TASK_GATE_DISABLE_ENV}=1 for the workflow that needs it (the "
        f"documented kill-switch) — a deliberate, visible opt-out rather than a "
        f"silent one."
    )


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
        raw = _read_stdin_utf8()
        payload = json.loads(raw) if raw.strip() else {}
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
        # v3.47.0 — except when the run's own orchestrator is completing it
        # mid-run, which is the unmanifested-task hole (see the helper's
        # docstring for the three preconditions and the fail-open directions).
        block = _unmanifested_task_block(str(task_id), Path.cwd(), payload)
        if block:
            print(block, file=sys.stderr)
            return 2
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
    except OSError as e:
        # (A9 review-remediation) A Windows sharing-violation (the evidence file
        # open in another process) raises OSError on read_text. Previously this
        # propagated -> exit 1 -> the gate was silently skipped. A gate that
        # cannot READ its evidence must FAIL CLOSED — treat it identically to
        # the missing-file branch (blocking gap, exit 2), never skip.
        print(
            f"review-gate-task: blocking task {task_id}: evidence at {evidence_path} "
            f"could not be read ({e}). A gate that cannot read its evidence fails closed.",
            file=sys.stderr,
        )
        return 2

    if not isinstance(evidence, dict):
        # Valid JSON, wrong shape (a top-level array / string / number). The
        # validator assumes a mapping; without this the shape error surfaced as
        # an AttributeError below.
        print(
            f"review-gate-task: blocking task {task_id}: evidence at {evidence_path} "
            f"is a JSON {type(evidence).__name__}, not an object. The review-evidence "
            f"contract is a single JSON object; a gate that cannot evaluate its "
            f"evidence fails closed.",
            file=sys.stderr,
        )
        return 2

    try:
        gaps = validate_evidence(evidence)
    except Exception as e:
        # (B1, v3.47.0 adversarial remediation) The A9 promise above covers a
        # gate that cannot READ its evidence; this extends it to one that cannot
        # EVALUATE it. An exception used to escape main(), exit the hook 1, and
        # Claude Code treats exit 1 as a non-blocking error — so one malformed
        # field silently skipped the gate entirely. Fail CLOSED instead: an
        # evidence file that breaks the validator is not evidence.
        print(
            f"review-gate-task: blocking task {task_id}: validating the evidence at "
            f"{evidence_path} raised {type(e).__name__}: {e}. A gate that cannot "
            f"evaluate its evidence fails closed — repair the evidence file (this "
            f"is a bug worth reporting if the file looks well-formed).",
            file=sys.stderr,
        )
        return 2

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
