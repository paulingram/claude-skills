#!/usr/bin/env python3
"""Agent dispatch result-wrapping + resume helper for the architect-team plugin (v1.8.0).

Real-world failure motivating this helper: a background `dv-attorney` agent ran
68 tool-calls of real work; the final report message was lost to a stream
timeout (harness-level rate limiting). The orchestrator saw an empty result and
treated the agent as failed; the user had to manually `redispatch and continue`
the agent, which then produced its verdict from its already-loaded context. The
work was on disk the whole time — only the REPORT was lost.

This module ships three stdlib-only functions that automate the recovery:

  is_truncated(result) -> bool
      Heuristic detector for empty / rate-limited / report-marker-less
      Agent-dispatch results.

  wrap_agent_result(result, agent_id, send_message=None, max_attempts=2) -> dict
      Detects truncation; if found, dependency-injected `send_message` is
      invoked to ask the SAME agent for its final verdict. Up to
      `max_attempts` resume attempts. Returns a merged result with
      `resumed`, `attempts`, and `resumed_failed` flags. Never raises.

  read_checkpoint(agent_id, checkpoints_dir=None) -> dict | None
      Reads `.architect-team/agent-checkpoints/<agent_id>.json` if present.
      Returns None for absent / unreadable / malformed files. Never raises.

The helper is dependency-injection-friendly: `wrap_agent_result` takes the
`SendMessage`-equivalent as a parameter so the helper does not couple to the
Claude Code harness's tool primitives and tests can pass a mock callable. The
orchestrator binds the harness's real SendMessage at call time.

Reuse Decision: RD-1 (build-new — no existing module wraps Agent dispatch
results). Stdlib only per the convention used by `scripts/setup/teams_mode.py`
(v1.0.0) and `scripts/setup/worktree_paths.py` (v1.1.0). The
`shared_state_dir()` resolver from `worktree_paths.py` is imported lazily
inside `read_checkpoint` — matching the v1.1.0 / v1.2.0 / v1.3.0 lazy-import
pattern so sys.path quirks at module-load time can't break the import graph.

References:
  - openspec/changes/agent-resume-discipline/proposal.md
  - openspec/changes/agent-resume-discipline/design.md
  - openspec/changes/agent-resume-discipline/specs/agent-resume-discipline/spec.md
  - skills/common-pipeline-conventions/SKILL.md `## Background-agent resume discipline`
  - skills/common-pipeline-conventions/SKILL.md `## Agent checkpoint discipline`
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


# ---- Constants ---------------------------------------------------------------

# Minimum output character length for a result to be considered "real".
# Anything shorter is almost certainly a truncated stream or an empty report.
_MIN_OUTPUT_CHARS = 50

# Harness-emitted rate-limit + timeout markers. Matched case-insensitively
# anywhere in the output. The first two are the literal substrings observed
# in the real `dv-attorney` failure that motivated v1.8.0; the others cover
# common variants.
_RATE_LIMIT_MARKERS = (
    "server is temporarily limiting requests",
    "rate limit",
    "rate limited",
    "rate-limited",
    "rate_limited",
    "request limit",
    "stream timeout",
    "stream timed out",
)

# Standard report-format markers a well-formed dispatch report should carry.
# Matched case-insensitively. If output contains NONE of these AND is non-empty,
# the agent likely stopped mid-thought before reaching the report section.
_REPORT_MARKERS = (
    "status:",
    "done",
    "blocked",
    "needs_context",
    "needs context",
)

# The follow-up prompt sent on resume. Asks the agent to report its final
# verdict in the standard report format and to cite any on-disk artifacts.
# Multi-line, intentionally explicit about what was lost so the resumed
# agent doesn't re-do its work.
DEFAULT_RESUME_PROMPT = (
    "Your previous report message was lost to a stream timeout, but your "
    "work is on disk. Please report your final verdict now in the standard "
    "report format:\n"
    "- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT\n"
    "- Commit SHAs (if any)\n"
    "- Files touched\n"
    "- Concerns / blocker description\n"
    "- Cite any artifacts on disk by absolute path\n"
    "Do NOT re-do completed work — read your own checkpoint at "
    ".architect-team/agent-checkpoints/<your-agent-id>.json first if one "
    "exists, and report from your already-loaded context."
)


# ---- Public API --------------------------------------------------------------


def is_truncated(result: dict | None) -> bool:
    """Return True iff the Agent dispatch result looks truncated or lost.

    Three heuristics, evaluated in order:

      1. Missing / non-dict / no `output` field, or output that is empty or
         shorter than `_MIN_OUTPUT_CHARS`.
      2. Output contains any of the documented harness rate-limit / stream-
         timeout markers (case-insensitive substring match).
      3. Output is non-empty but contains NONE of the standard report-format
         markers (`Status:`, `DONE`, `BLOCKED`, `NEEDS_CONTEXT`).

    Returns True on ANY of the three. Never raises — a malformed input
    (None, non-dict, missing field) returns True since "we can't tell what
    this is" should err on the side of resuming.
    """
    if not isinstance(result, dict):
        return True

    output = result.get("output", "")
    if not isinstance(output, str):
        return True

    if len(output.strip()) < _MIN_OUTPUT_CHARS:
        return True

    output_lower = output.lower()

    for marker in _RATE_LIMIT_MARKERS:
        if marker in output_lower:
            return True

    # If output is substantial but lacks every report-format marker, treat
    # as truncated — the agent likely stopped before its closing report.
    if not any(marker in output_lower for marker in _REPORT_MARKERS):
        return True

    return False


def wrap_agent_result(
    result: dict | None,
    agent_id: str,
    send_message: Callable[..., Any] | None = None,
    max_attempts: int = 2,
    resume_prompt: str = DEFAULT_RESUME_PROMPT,
) -> dict:
    """Wrap an Agent dispatch result, auto-resuming on truncation.

    The orchestrator MUST route every background Agent dispatch result
    through this helper before treating the work as complete. The helper:

      1. If `is_truncated(result)` is False, returns the result with
         `resumed=False, attempts=1, resumed_failed=False`.
      2. If truncated AND `send_message` is None (test / no-harness mode),
         returns the result with `resumed=False, attempts=1` so callers
         can still inspect truncation status.
      3. If truncated AND `send_message` is callable, invokes
         `send_message(to=agent_id, prompt=resume_prompt)` to ask the
         SAME agent for its final verdict. The resumed output is merged
         into the original. If still truncated, retries up to
         `max_attempts` total resume attempts.
      4. If all `max_attempts` resume attempts return truncated output,
         returns the last merged result with `resumed_failed=True` so the
         orchestrator can surface the failure to the user without losing
         visibility into what is on disk.

    Never raises. A `send_message` callable that itself raises is caught;
    the exception is recorded under `resume_error` on the returned dict
    and the attempt counts toward the cap.

    Args:
        result: the raw Agent dispatch result dict. May be None / malformed —
            the helper tolerates either.
        agent_id: the Agent identifier to address resume messages to.
            Passed through to `send_message(to=agent_id, prompt=...)`.
        send_message: a callable with signature
            `send_message(to: str, prompt: str) -> dict` returning a result
            in the same shape as the original `result`. Dependency-
            injected for testability. If None, no resume is attempted.
        max_attempts: maximum number of resume attempts before surfacing
            `resumed_failed=True`. Default 2 per the design.
        resume_prompt: the follow-up prompt sent on resume. Default is
            `DEFAULT_RESUME_PROMPT`.

    Returns:
        A dict carrying the (possibly resumed) output plus metadata:
            `output`: str — the merged or original output text
            `resumed`: bool — True iff at least one resume was attempted
                AND produced new output
            `attempts`: int — 1 + number of resume attempts made
            `resumed_failed`: bool — True iff max_attempts exhausted and
                the final result is still truncated
            `resume_error`: str | None — exception text if send_message
                raised on any attempt; None otherwise
            Any other keys from the original `result` are preserved.
    """
    # Normalize input to a dict so downstream merges are safe.
    base: dict[str, Any] = {}
    if isinstance(result, dict):
        base.update(result)
    output = base.get("output", "")
    if not isinstance(output, str):
        output = ""

    # Fast-path: not truncated. Return as-is with metadata.
    if not is_truncated(base):
        base["output"] = output
        base["resumed"] = False
        base["attempts"] = 1
        base["resumed_failed"] = False
        base.setdefault("resume_error", None)
        return base

    # Truncated but no send_message — caller wants detection only.
    if send_message is None:
        base["output"] = output
        base["resumed"] = False
        base["attempts"] = 1
        base["resumed_failed"] = False
        base.setdefault("resume_error", None)
        return base

    # Truncated AND we have a send_message — resume up to max_attempts.
    attempts = 1
    resumed = False
    resume_error: str | None = None
    current_output = output

    while attempts < (1 + max_attempts):
        try:
            resumed_result = send_message(to=agent_id, prompt=resume_prompt)
        except Exception as exc:  # noqa: BLE001 — caller-side errors are reported, not raised
            resume_error = f"{type(exc).__name__}: {exc}"
            attempts += 1
            continue

        attempts += 1
        new_output = ""
        if isinstance(resumed_result, dict):
            candidate = resumed_result.get("output", "")
            if isinstance(candidate, str):
                new_output = candidate

        if new_output:
            resumed = True
            # Merge: append resumed output to the original (separated by a
            # marker so downstream readers can tell the seam). Original
            # output may be empty; that's fine.
            if current_output:
                current_output = (
                    current_output.rstrip()
                    + "\n\n--- [resumed via wrap_agent_result] ---\n\n"
                    + new_output
                )
            else:
                current_output = new_output

        merged = dict(base)
        merged["output"] = current_output
        if not is_truncated(merged):
            merged["resumed"] = resumed
            merged["attempts"] = attempts
            merged["resumed_failed"] = False
            merged["resume_error"] = resume_error
            return merged

    # Max attempts exhausted. Surface failure for orchestrator to escalate.
    base["output"] = current_output
    base["resumed"] = resumed
    base["attempts"] = attempts
    base["resumed_failed"] = True
    base["resume_error"] = resume_error
    return base


def read_checkpoint(
    agent_id: str,
    checkpoints_dir: Path | None = None,
) -> dict | None:
    """Read `.architect-team/agent-checkpoints/<agent_id>.json` if present.

    Used by long-running agents on resume: the agent reads its OWN checkpoint
    first to learn which steps already completed, then skips already-done
    work. The checkpoint shape is documented in
    `common-pipeline-conventions ## Agent checkpoint discipline`:

        {
            "agent_id": "<id>",
            "task_id": "<task>",
            "schema_version": 1,
            "last_completed_step": "<human-readable>",
            "files_touched": ["<path>", ...],
            "in_progress": "<human-readable>",
            "ts": "<ISO-8601 UTC>"
        }

    Args:
        agent_id: the checkpoint owner's agent identifier. Used as the
            filename stem (`<agent_id>.json`).
        checkpoints_dir: directory holding checkpoints. When None, resolves
            via `scripts.setup.worktree_paths.shared_state_dir() /
            'agent-checkpoints'` so checkpoints are visible across worktrees
            during the same architect-team run. The lazy import matches the
            v1.1.0 / v1.2.0 / v1.3.0 pattern — avoids sys.path issues at
            module import time.

    Returns:
        The parsed checkpoint dict when present and well-formed JSON;
        None when the file is absent, unreadable, or malformed.
        Never raises.
    """
    if checkpoints_dir is None:
        try:
            # Lazy import to avoid sys.path coupling at module load.
            from worktree_paths import shared_state_dir  # type: ignore
        except ImportError:
            try:
                from scripts.setup.worktree_paths import shared_state_dir  # type: ignore
            except ImportError:
                # Fall back: degenerate cwd-relative location. The caller
                # gets None because the file won't exist there anyway in
                # any normal run, which is the correct conservative answer.
                shared_state_dir = lambda: Path.cwd() / ".architect-team"  # noqa: E731
        try:
            checkpoints_dir = shared_state_dir() / "agent-checkpoints"
        except Exception:  # noqa: BLE001 — never raise from a checkpoint read
            return None

    path = Path(checkpoints_dir) / f"{agent_id}.json"
    try:
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    return data
