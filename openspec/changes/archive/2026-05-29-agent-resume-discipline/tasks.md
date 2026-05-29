# Tasks: agent-resume-discipline

Single implementer slice.

## Files owned

- Create: `scripts/setup/agent_resume.py` (3 functions, stdlib only)
- Create: `tests/test_agent_resume_discipline.py` (≥ 10 tests)
- Modify: `skills/common-pipeline-conventions/SKILL.md` (2 new sections)
- Modify: `skills/architect-team-pipeline/SKILL.md` (wrap_agent_result reference)
- Modify: `skills/bug-fix-pipeline/SKILL.md` (same)
- Modify: `skills/mini-architect-team-pipeline/SKILL.md` (same)
- Modify: all 27 `agents/*.md` files (uniform `## Checkpoint discipline` section)
- Modify: `tests/test_dispatch_banner.py::test_plugin_metadata_at_1_5_0` — bump assertion to 1.8.0
- Modify: `.claude-plugin/plugin.json` (1.8.0)
- Modify: `.claude-plugin/marketplace.json` (1.8.0)
- Modify: `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`

## Tasks

- [TASK-1] Author `scripts/setup/agent_resume.py`:
  - `is_truncated(result: dict) -> bool` — heuristics per `design.md`
  - `wrap_agent_result(result, agent_id, send_message=None, max_attempts=2, resume_prompt=DEFAULT_RESUME_PROMPT) -> dict` — dependency-injected SendMessage
  - `read_checkpoint(agent_id, checkpoints_dir=None) -> dict | None` — defaults to `worktree_paths.shared_state_dir() / 'agent-checkpoints'`
  - `DEFAULT_RESUME_PROMPT` constant
  - Stdlib only

- [TASK-2] Author `tests/test_agent_resume_discipline.py` (≥ 10 tests):
  - 4 tests for `is_truncated` (empty, rate-limit, missing markers, well-formed)
  - 3 tests for `wrap_agent_result` (not-truncated passes through, truncated invokes send_message + merged, max_attempts cap)
  - 2 tests for `read_checkpoint` (absent → None, present → parsed)
  - 2 structural tests (canonical sections exist; 27 agents have checkpoint section; 3 pipelines reference wrap_agent_result)

- [TASK-3] Add `## Background-agent resume discipline` section to `common-pipeline-conventions/SKILL.md`. Cover: orchestrator MUST wrap; truncation detection criteria; 2-attempt cap; user-surfacing on failure; pointer to `scripts/setup/agent_resume.py`.

- [TASK-4] Add `## Agent checkpoint discipline` section to `common-pipeline-conventions/SKILL.md`. Cover: when to checkpoint (>20 tool calls expected), where (`.architect-team/agent-checkpoints/<agent-id>.json`), the schema, the cadence (~every 10 tool calls), how resume uses it.

- [TASK-5] In each of the 3 pipeline SKILL.md bodies, add a sentence to the relevant dispatch section pointing at `common-pipeline-conventions ## Background-agent resume discipline`. Brief — 1 line per pipeline.

- [TASK-6] For each of the 27 `agents/*.md` files, INSERT a `## Checkpoint discipline` section. Uniform 3-5 line block:

```markdown
## Checkpoint discipline

When your work is expected to exceed ~20 tool calls, write a checkpoint to `.architect-team/agent-checkpoints/<your-agent-id>.json` every ~10 calls (or after each logical step) per `common-pipeline-conventions ## Agent checkpoint discipline`. On resume after a stream timeout, read your own checkpoint FIRST and skip already-completed steps. The checkpoint schema: `{agent_id, task_id, last_completed_step, files_touched, in_progress, ts}`.
```

  Frontmatter unchanged. Use a small Python helper for the 27-file insertion (loop with Edit tool calls OR a one-shot script).

- [TASK-7] Bump the v1.5.0 test-pinning assertion in `tests/test_dispatch_banner.py::test_plugin_metadata_at_1_5_0` to `1.8.0` (per the precedent established in v1.6.0/v1.7.0).

- [TASK-8] Version bumps: `plugin.json` + `marketplace.json` → `1.8.0`.

- [TASK-9] Docs:
  - CHANGELOG: prepend v1.8.0 entry (Added: agent_resume.py helper + 2 canonical sections + 27-agent checkpoint sections + tests; Migration: backwards-compatible)
  - CLAUDE.md: replace v1.7.0 lead with v1.8.0 lead naming the resume discipline; bump test count
  - README: banner v1.8.0, badges, NEW IN v1.8.0 row, status timeline
  - CODEBASE_MAP: last_mapped 2026-05-29T03:00:00Z; add new helper + new test file; bump counts
  - INTEGRATION_MAP: last_synthesized 2026-05-29T03:00:00Z; note the resume discipline

- [TASK-10] Commits (4 logical groups):
  1. `agent_resume.py` helper + `tests/test_agent_resume_discipline.py`
  2. `common-pipeline-conventions` 2 new sections + 3 pipeline references
  3. 27 agents/*.md uniform Checkpoint discipline section
  4. Version bump + docs + v1.5.0-test pinning fix

- [TASK-11] Phase 3 review-evidence at `.architect-team/reviews/v1.8.0-agent-resume-discipline.json` per v6. teammate = "v1.8.0-implementer", task_id = "v1.8.0-agent-resume-discipline". No `independent_review`.

- [TASK-12] Final test:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: ~2080+ / 1 skipped (2056 baseline + 10-20 new from `test_agent_resume_discipline.py` + parametrize amplification).

## Acceptance

All 9 acceptance criteria from `proposal.md` `## QA Guidance`.
