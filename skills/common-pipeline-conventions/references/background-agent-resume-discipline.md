# Background-agent resume discipline

When the orchestrator dispatches a long-running background agent, the harness-level stream delivering the agent's final report can be lost to a rate-limit cutoff / network blip even when the work succeeded end-to-end (motivating case in CHANGELOG: a `dv-attorney` agent did 68 tool-calls of real work, finished, then its report stream was cut — the orchestrator saw an empty result and treated it as failed though the work was on disk the whole time; only the REPORT was lost).

The orchestrator MUST route EVERY background Agent dispatch result through `wrap_agent_result()` from `scripts/setup/agent_resume.py` BEFORE treating the work as complete or failed. The helper handles the recovery automatically.

### The wrap-call rule

```python
from scripts.setup.agent_resume import wrap_agent_result

# After every background Agent dispatch:
raw = invoke_agent(agent_id, brief)   # or the harness equivalent
result = wrap_agent_result(raw, agent_id, send_message=send_message_fn)

if result.get("resumed_failed"):
    # Surface to user with on-disk artifacts cited; do NOT treat as silent failure.
    ...
elif result.get("resumed"):
    # Resume succeeded — agent's verdict is in result["output"].
    ...
else:
    # Original result was well-formed.
    ...
```

The `send_message` parameter is dependency-injected so the helper itself does not couple to the Claude Code harness's `SendMessage` tool. The orchestrator binds the harness's real SendMessage at call time; tests pass a mock.

### Truncation-detection criteria

`is_truncated()` returns True on ANY of:
1. Result is missing, non-dict, missing `output` field, OR `output` is empty / shorter than 50 chars.
2. `output` contains a known harness rate-limit / stream-timeout marker (case-insensitive): "Server is temporarily limiting requests", "rate limit", "rate limited", "stream timeout", and close variants.
3. `output` is non-empty but contains NONE of the standard report-format markers `Status:`, `DONE`, `BLOCKED`, `NEEDS_CONTEXT` (case-insensitive).

### The 2-attempt cap + user-surfacing

`wrap_agent_result` caps resume attempts at `max_attempts=2` by default. After 2 failed resume attempts (the agent still returns truncated output, OR the `send_message` callable itself raises), the helper returns the merged result with `resumed_failed=True` and `resume_error` populated. The orchestrator MUST surface this to the user with the cited on-disk artifact paths (checkpoints, partial commits, .architect-team/reviews/* files) rather than treating it as a silent failure. A surfaced failure with on-disk pointers is recoverable; a silent failure loses the visibility that lets the user finish the run.

### Cross-references

- `scripts/setup/agent_resume.py` is the helper module. Stdlib only; mirrors the discipline used by `scripts/setup/teams_mode.py` and `scripts/setup/worktree_paths.py`.
- `tests/test_agent_resume_discipline.py` asserts the truncation heuristics + the resume behavior + the structural surfaces.
- `architect-team-pipeline/SKILL.md`, `bug-fix-pipeline/SKILL.md`, `mini-architect-team-pipeline/SKILL.md` reference this section at every background-Agent dispatch point.
