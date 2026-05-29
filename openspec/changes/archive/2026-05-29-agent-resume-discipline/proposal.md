# Proposal: agent-resume-discipline (v1.8.0)

## Why

Real-world failure: a background agent (`dv-attorney`) ran 68 tool-calls of real work, then a stream timeout killed its final report. Work was on disk; orchestrator never saw the verdict; the user had to manually `redispatch and continue`. This is a reliability gap distinct from the v2.0.0 VAO framework — VAO addresses "agent doing the wrong thing"; v1.8.0 addresses "agent doing the right thing but losing visibility through harness-level failures."

Two failure modes from one root cause:
1. **Stream-timeout loss of report:** agent completed real work, but the report stream timed out; orchestrator sees empty/truncated result.
2. **Re-work on resume:** when manually resumed, the agent doesn't know what it already did; re-does 68 tool calls of work.

The fix layers a helper (`agent_resume.py`) + a checkpoint discipline + an orchestrator-side documented rule: never treat an empty/truncated background-agent result as completion; ALWAYS attempt `SendMessage` resume first.

## What changes

1. **New helper `scripts/setup/agent_resume.py`** exposes:
   - `wrap_agent_result(result: dict, agent_id: str) -> dict` — detects empty / truncated / timeout-marker output; auto-issues `SendMessage` to `agent_id` with a "report your final verdict + cite any work artifacts on disk" follow-up; returns the merged result with a `resumed: bool` flag
   - `is_truncated(result: dict) -> bool` — heuristic detection (empty output, "Server is temporarily limiting requests" markers, missing report-format markers like "Status:" or "DONE")
   - `read_checkpoint(agent_id: str) -> dict | None` — reads `.architect-team/agent-checkpoints/<agent-id>.json` if present
2. **New `## Background-agent resume discipline` section in `common-pipeline-conventions`** documenting:
   - The orchestrator MUST wrap every background Agent dispatch result through `wrap_agent_result()` before treating it as complete
   - Empty / truncated results trigger automatic `SendMessage` resume; max 2 resume attempts; on 3rd failure, surface to user with "agent <id> work-on-disk-pending: <paths>" + abort gracefully
3. **New `## Agent checkpoint discipline` section in `common-pipeline-conventions`** documenting:
   - Long-running agents (>20 tool calls expected) write a checkpoint to `.architect-team/agent-checkpoints/<agent-id>.json` every ~10 tool calls
   - Checkpoint shape: `{agent_id, last_completed_step, files_touched, in_progress: <description>, ts}`
   - On resume, the agent reads its own checkpoint FIRST and skips already-completed steps
4. **27 agents/*.md uniform update** — each gains a brief `## Checkpoint discipline` section (3-5 lines) instructing the agent to write checkpoints when its work is long; cross-reference to canonical section
5. **Three pipeline SKILL.md bodies updated** — each documents calling `wrap_agent_result()` after every background dispatch; cross-references the canonical sections
6. **New `tests/test_agent_resume_discipline.py`** with synthetic timeout fixtures asserting the discipline is documented + the helper functions detect/handle truncated results correctly
7. **Version bump to v1.8.0** in plugin.json + marketplace.json + CHANGELOG + CLAUDE.md + README + maps

## QA Guidance

### Acceptance Criteria

- [AC-1] `scripts/setup/agent_resume.py` exposes `wrap_agent_result`, `is_truncated`, `read_checkpoint`. Stdlib only.
- [AC-2] `is_truncated` returns True for: empty `result` field, results containing only rate-limit error strings, results missing required report-format markers (`Status:`, `DONE`, `BLOCKED`, `NEEDS_CONTEXT`).
- [AC-3] `wrap_agent_result` calls `SendMessage`-equivalent resume on truncated results, returns merged output with `resumed: bool` flag; caps at 2 resume attempts; surfaces to user on 3rd failure.
- [AC-4] `common-pipeline-conventions/SKILL.md` has both `## Background-agent resume discipline` and `## Agent checkpoint discipline` sections.
- [AC-5] All 27 `agents/*.md` files have a `## Checkpoint discipline` section.
- [AC-6] The 3 pipeline SKILL.md bodies (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) document calling `wrap_agent_result()` after every background dispatch.
- [AC-7] `tests/test_agent_resume_discipline.py` ≥ 10 tests covering the helper behaviors + structural assertions.
- [AC-8] All existing tests pass (2056 baseline post-v1.7.0) + new tests. Target: ~2080+ / 1 skipped.
- [AC-9] Version `1.8.0` consistent across plugin.json, marketplace.json, CHANGELOG, README, CLAUDE.md.

### Unit Test Targets

- `agent_resume.py:is_truncated`: positive cases (empty output, rate-limit message, missing Status: marker), negative cases (well-formed report)
- `agent_resume.py:wrap_agent_result`: synthetic Agent result + mocked SendMessage; assert resume invoked; assert merged result correct; assert 2-attempt cap
- `agent_resume.py:read_checkpoint`: returns None when file absent; returns parsed dict when present
- Structural grep audits on the 5 affected source files

### Integration Test Targets

- N/A — discipline + helper change; pytest suite IS the integration test.

### Playwright Flows

- N/A.

### Out of Scope

- **Harness-level Stop-hook for Agent completion** — the strongest structural fix (Option C from the analysis) requires Claude Code harness changes the plugin can't make. v1.8.0 is the orchestrator-side discipline + helper.
- **Auto-recovery from agent crashes mid-tool-call** — the resume pattern handles report-stream timeouts; a crashed agent mid-work requires deeper plumbing. Future v1.x.
- **Checkpoint replay verification** — when an agent reads its checkpoint on resume, v1.8.0 trusts the checkpoint's `last_completed_step` field. A future v1.x could add tool-call-log verification that the claimed steps actually completed.

## Impact

- **Modified:** `scripts/setup/agent_resume.py` (NEW), `skills/common-pipeline-conventions/SKILL.md` (2 new sections), 3 pipeline SKILL.md bodies, 27 `agents/*.md` files, CHANGELOG, CLAUDE.md, README, CODEBASE_MAP, INTEGRATION_MAP, plugin.json, marketplace.json.
- **New:** `tests/test_agent_resume_discipline.py`, 1 openspec change folder.
- **Test count:** 2056 → ~2080+.
- **Version:** v1.7.0 → **v1.8.0**.
- **Backwards-compatible:** purely additive — discipline + helper. Runs that don't hit stream timeouts see no behavior change.
- **Orthogonal to v2.0.0:** the VAO framework on `architect-team/v2.0.0-verified-agent-output` branch is unaffected. If v2.0.0 is later approved, the v1.8.0 resume helper layers cleanly underneath VAO's Layer 3 tool invocations.
