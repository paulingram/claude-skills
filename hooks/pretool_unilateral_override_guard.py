#!/usr/bin/env python3
"""v3.0.0 PreToolUse runtime guardrail.

Fires BEFORE Edit / Write / NotebookEdit tool calls when:

  1. An active pipeline run is in flight (workspace's `.architect-team/
     intake-state.json` exists with `status: in_progress` and `phase < 8`).
  2. The about-to-fire tool targets a source file (NOT under
     `.architect-team/` / `.mempalace/` / `openspec/changes/`).
  3. No `Skill(architect-team-pipeline)` (or sibling pipeline skill)
     invocation appears in the run's toolcall ledger yet.

When all three conditions hold, exit 2 to block the tool call. The stderr
message names the violation + the disclosure-required alternative.

Use:
  Registered in hooks/hooks.json as PreToolUse[Edit|Write|NotebookEdit].
  Payload is read from stdin as JSON.

Backwards-compat: when no active pipeline state is detected, the hook is a
silent no-op (exit 0). Stdlib-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


_PIPELINE_SKILL_NAMES = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
    "ux-test-builder",
    "architect-team",  # plugin-prefixed slug
)


_BYPASS_ALLOWED_PATH_FRAGMENTS = (
    "/.architect-team/",
    "/.mempalace/",
    "/openspec/changes/",
    "\\.architect-team\\",
    "\\.mempalace\\",
    "\\openspec\\changes\\",
)


def _find_workspace(start: Path) -> Path | None:
    """Walk up from `start` looking for a directory containing `.architect-team/`.

    Returns the workspace root or None if no such ancestor exists. The bare
    filesystem root (drive anchor on Windows, `/` on POSIX) is never treated
    as a workspace: a stray `C:\\.architect-team` / `/.architect-team` must not
    capture an unrelated subtree. The walk terminates at the root and returns
    None when no real marker is found.
    """
    start = start.resolve()
    root = Path(start.anchor)
    for candidate in (start, *start.parents):
        if candidate == root:
            continue
        if (candidate / ".architect-team").is_dir():
            return candidate
    return None


def _read_intake_state(workspace: Path) -> dict[str, Any] | None:
    intake_path = workspace / ".architect-team" / "intake-state.json"
    if not intake_path.exists():
        return None
    try:
        return json.loads(intake_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _ledger_has_pipeline_skill_invocation(workspace: Path, run_id: str | None) -> bool:
    """True iff the toolcall ledger contains a Skill call for a pipeline-driving skill."""
    if not run_id:
        return False
    ledger_path = workspace / ".architect-team" / "run-history" / f"{run_id}-toolcalls.jsonl"
    if not ledger_path.exists():
        return False
    try:
        text = ledger_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        tool = (entry.get("tool") or entry.get("tool_name") or "").strip()
        if tool != "Skill":
            continue
        inp = entry.get("tool_input") or entry.get("input") or entry.get("args") or {}
        if not isinstance(inp, dict):
            continue
        skill_name = (inp.get("skill") or inp.get("skill_name") or "").strip().lower()
        if any(p in skill_name for p in _PIPELINE_SKILL_NAMES):
            return True
    return False


def _is_allowed_path(file_path: str) -> bool:
    """True iff writing this path does NOT count as a source-code bypass.

    Writes under `.architect-team/` / `.mempalace/` / `openspec/changes/`
    are pipeline-managed state and never trigger the guardrail.
    """
    if not isinstance(file_path, str) or not file_path:
        return True
    lower = file_path.lower().replace("\\", "/")
    return any(frag.replace("\\", "/") in lower for frag in _BYPASS_ALLOWED_PATH_FRAGMENTS)


def check_payload(payload: dict[str, Any]) -> tuple[int, str]:
    """Inspect a PreToolUse payload and return (exit_code, stderr_message).

    Pure function — safe to call from tests with any payload shape.
    """
    tool = (payload.get("tool_name") or payload.get("tool") or "").strip()
    if tool not in ("Edit", "Write", "NotebookEdit"):
        return 0, ""

    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("args") or {}
    if not isinstance(tool_input, dict):
        return 0, ""

    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("notebook_path")
        or ""
    )
    if not file_path:
        return 0, ""
    if _is_allowed_path(file_path):
        return 0, ""

    # Resolve workspace. Prefer payload-provided workspace; fall back to cwd
    # and walk up looking for `.architect-team/`.
    workspace_hint = payload.get("workspace") or payload.get("cwd")
    start = Path(workspace_hint) if workspace_hint else Path.cwd()
    workspace = _find_workspace(start)
    if workspace is None:
        return 0, ""

    intake = _read_intake_state(workspace)
    if intake is None:
        return 0, ""

    status = (intake.get("status") or "").strip().lower()
    phase = intake.get("phase")
    try:
        phase_int = int(phase) if phase is not None else 99
    except (TypeError, ValueError):
        phase_int = 99

    if status != "in_progress":
        return 0, ""
    if phase_int >= 8:
        return 0, ""

    run_id = intake.get("run_id") or intake.get("runId")
    if _ledger_has_pipeline_skill_invocation(workspace, run_id):
        return 0, ""  # Pipeline IS invoked; the edit is part of the pipeline's work

    # Active pipeline + no Skill invocation + source-file edit = unilateral bypass
    message = (
        "CT6 v3.0.0 PreToolUse guardrail BLOCKED — pipeline-bypass detected.\n"
        "\n"
        f"  - active pipeline run: {run_id!r}\n"
        f"  - current phase: {phase!r}\n"
        f"  - tool about to fire: {tool}\n"
        f"  - target file: {file_path}\n"
        f"  - no Skill(pipeline) invocation found in toolcall ledger\n"
        "\n"
        "REQUIRED ACTION — choose one:\n"
        "\n"
        "  (a) Invoke the pipeline Skill first:\n"
        "      Skill(skill='architect-team-pipeline')  [or bug-fix-pipeline / "
        "mini-architect-team-pipeline / ux-test-builder]\n"
        "\n"
        "  (b) Explicitly disclose the bypass to the user BEFORE editing:\n"
        "      'I am not invoking the pipeline because [verbatim user "
        "authorization]. Want the full pipeline? Reply \"use the pipeline\".'\n"
        "\n"
        "Silent bypass is forbidden under v2.22.0 + v3.0.0 unilateral-override "
        "discipline. The post-hoc virtuous confession ('I owe you a straight "
        "answer', 'I should be straight about that', 'the honest framing is') "
        "is NOT an acceptable substitute for pre-action disclosure."
    )
    return 2, message


def main(argv: list[str] | None = None) -> int:
    """Read PreToolUse payload from stdin, run the check, write any stderr,
    return the exit code."""
    try:
        if not sys.stdin.isatty():
            stdin_text = sys.stdin.read()
        else:
            stdin_text = ""
    except (OSError, ValueError):
        stdin_text = ""

    payload: dict[str, Any] = {}
    if stdin_text.strip():
        try:
            parsed = json.loads(stdin_text)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            pass

    exit_code, message = check_payload(payload)
    if message:
        print(message, file=sys.stderr)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
