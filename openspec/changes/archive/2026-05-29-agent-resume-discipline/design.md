# Design: agent-resume-discipline

## Reference

Full ACs + WHY + WHAT in `proposal.md`. This file holds the architectural anchors.

## The failure mode

A background agent runs for many tool calls (real case: 68). Near the end, the report stream times out due to harness-level rate limiting or transient network issues. The work IS on disk — the agent successfully invoked all its tools — but the final report message never reaches the orchestrator. The orchestrator sees an empty/truncated result and treats the agent as failed or just hung.

The user's correct manual recovery: read the agent's transcript file, observe what got done, manually `SendMessage` to resume the agent with "report your final verdict + cite any work artifacts on disk." The agent then produces the verdict in a fresh response, leveraging its already-loaded context.

v1.8.0 automates this recovery.

## Architecture — helper + discipline

### The helper: `scripts/setup/agent_resume.py`

Pure Python, stdlib only. Three functions:

```python
def is_truncated(result: dict) -> bool:
    """Heuristic: does this Agent dispatch result look like a truncated/timeout failure?"""
    # 1. Empty output / output field missing
    # 2. Contains known rate-limit markers
    # 3. Has output but lacks any standard report-format markers (Status:, DONE, BLOCKED, NEEDS_CONTEXT)

def wrap_agent_result(
    result: dict,
    agent_id: str,
    send_message: Callable | None = None,
    max_attempts: int = 2,
    resume_prompt: str = DEFAULT_RESUME_PROMPT,
) -> dict:
    """Wrap an Agent dispatch result; auto-resume on truncation.
    
    Returns the merged result with metadata:
        result['resumed'] -> bool
        result['attempts'] -> int (1 + number of resumes)
        result['resumed_failed'] -> bool (True if max_attempts exhausted)
    """
    # If not truncated → return as-is
    # If truncated → call send_message(to=agent_id, prompt=resume_prompt)
    # Merge the resumed result with the original
    # If resumed result is also truncated, retry (up to max_attempts)
    # If max_attempts exhausted, return with resumed_failed=True (don't raise — let orchestrator decide)

def read_checkpoint(
    agent_id: str,
    checkpoints_dir: Path | None = None,
) -> dict | None:
    """Read .architect-team/agent-checkpoints/<agent_id>.json if present."""
    # Default checkpoints_dir: scripts.setup.worktree_paths.shared_state_dir() / 'agent-checkpoints'
    # Returns None if file absent or malformed; never raises
```

`DEFAULT_RESUME_PROMPT`:
```
Your previous report message was lost to a stream timeout, but your work is on disk.
Please report your final verdict now in the standard report format:
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- Commit SHAs (if any)
- Files touched
- Concerns / blocker description
- Cite any artifacts on disk by absolute path
```

### Send_message dependency injection

`wrap_agent_result` takes `send_message` as a parameter so it's mockable in tests AND so the helper doesn't have to depend on the Claude Code harness's `SendMessage` tool directly. The orchestrator passes its own `SendMessage`-equivalent at call time:

```python
# In the orchestrator skill body / a hook:
from scripts.setup.agent_resume import wrap_agent_result

def my_send_message(to: str, prompt: str) -> dict:
    # Invoke harness SendMessage tool
    ...

result = wrap_agent_result(agent_result, agent_id, send_message=my_send_message)
```

This keeps the helper testable without harness coupling.

### The discipline

`common-pipeline-conventions/SKILL.md` gains two new sections:

1. **`## Background-agent resume discipline`** — orchestrator MUST wrap every background result; truncated → auto-resume; cap=2; surface to user on failure.
2. **`## Agent checkpoint discipline`** — long-running agents (>20 tool calls expected) write checkpoints every ~10 tool calls; resume reads checkpoint state.

Plus a brief `## Checkpoint discipline` section in every `agents/*.md` (3-5 lines, cross-referencing canonical).

## Checkpoint shape

```json
{
  "agent_id": "a33aa940e3004e157",
  "task_id": "deployed-verify-attorney-retry",
  "schema_version": 1,
  "last_completed_step": "verification phase 3 of 5",
  "files_touched": ["src/features/v2-title-agency/TAReview.tsx", "..."],
  "in_progress": "running verification phase 4 (deployed-asset hash check)",
  "ts": "2026-05-29T03:14:00Z"
}
```

The schema is intentionally minimal — agents write it; resume reads it. Future versions can extend.

## Reuse Decision Log

### RD-1: NEW `scripts/setup/agent_resume.py`

**Decision:** Build new.
**Anchor:** No existing module handles Agent dispatch result wrapping. v1.1.0 has `teams_mode.py` (mode detection), v1.2.0/v1.3.0 have `worktree_lifecycle.py` (worktree ops), v1.5.0 extends `teams_mode.py` for banner formatting. The resume helper is a distinct concern.

### RD-2: Extend `common-pipeline-conventions/SKILL.md`

**Decision:** Extend (the canonical home pattern).

### RD-3: Extend 3 pipeline SKILL.md bodies

**Decision:** Extend in place.

### RD-4: Extend 27 `agents/*.md` files with `## Checkpoint discipline`

**Decision:** Edit in place. Brief section (3-5 lines), cross-references canonical.
**Pattern matches v1.6.0:** every agent body carries the discipline inline for visibility (same trade-off accepted — duplication for safety).

### RD-5: NEW `tests/test_agent_resume_discipline.py`

**Decision:** New file.

### RD-6: NO harness-level Stop-hook

**Decision:** Out of scope.
**Reason:** Strongest fix would be a hook that fires on Agent completion with empty output, but that requires Claude Code harness extensions the plugin can't make. v1.8.0 ships the orchestrator-side discipline; harness-level hooks remain a future possibility.

## Migration / backwards compatibility

- **v1.7.0 → v1.8.0:** Purely additive. Runs that don't hit stream timeouts see no behavior change. Runs that DO hit timeouts automatically resume instead of silently failing.
- **No flag.** The discipline + helper are always on.
- **No behavior change for the runtime** beyond the auto-resume behavior on truncated results.

## Orthogonality with v2.0.0 VAO

v2.0.0 is on a separate branch (`architect-team/v2.0.0-verified-agent-output`) awaiting user decision. v1.8.0 ships independently. If v2.0.0 is later approved:

- v2.0.0's Layer 3 tool dispatches (each `verify-*` tool's invocation is itself an Agent call) benefit from v1.8.0's `wrap_agent_result()`
- v2.0.0's adversarial-reviewer agents are long-running and benefit from v1.8.0's checkpoint discipline
- No conflict; v1.8.0 layers cleanly underneath v2.0.0

## Trade-offs accepted

- **Documentation + helper discipline, not harness-level enforcement.** The agent has to follow the checkpoint discipline; the orchestrator has to call `wrap_agent_result()`. Both are documented and tested but not hook-enforced. The strongest fix would require harness changes the plugin can't make.
- **Checkpoint schema is informal v1.** Tightening to a strict schema with hook validation is a future v1.x.
- **2-attempt resume cap.** Picked as a sensible default. A failed third attempt surfaces to the user with cited on-disk artifacts. The cap can be configured per-call if needed.

## Version

v1.8.0 — minor bump (additive helper + discipline + checkpoint, no breaking change).
