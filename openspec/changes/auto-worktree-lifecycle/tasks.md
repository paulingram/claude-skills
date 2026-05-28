# Tasks: auto-worktree-lifecycle

Single implementer slice — bounded scope.

## Files owned

- Create: `scripts/setup/worktree_lifecycle.py`
- Create: `tests/test_worktree_lifecycle.py`
- Modify: `commands/architect-team.md` (add auto-worktree step + --no-worktree flag)
- Modify: `commands/bug-fix.md` (same)
- Modify: `commands/mini.md` (same)
- Modify: `skills/common-pipeline-conventions/SKILL.md` (new `## Auto-worktree lifecycle` section)
- Modify: `.claude-plugin/plugin.json` (version 1.2.0)
- Modify: `.claude-plugin/marketplace.json` (version 1.2.0)
- Modify: `CHANGELOG.md` (prepend v1.2.0 entry)
- Modify: `CLAUDE.md` (v1.2.0 lead + counts)
- Modify: `README.md` (banner, badges, NEW IN v1.2.0 row)
- Modify: `docs/CODEBASE_MAP.md` (new helper + new test file + counts)
- Modify: `docs/INTEGRATION_MAP.md` (note auto-worktree default)

## Tasks

- [TASK-1] Author `scripts/setup/worktree_lifecycle.py`:
  - `create_run_worktree(slug, base_branch="main", parent_dir=None) -> Path`
  - `cleanup_run_worktree(worktree_path, remove_branch=False) -> None`
  - `current_worktree_is_run() -> bool` (uses `git rev-parse --abbrev-ref HEAD`, checks startswith `architect-team/`)
  - `current_run_slug() -> str | None`
  - Collision handling: append `-2`, `-3`, etc.
  - Stdlib only

- [TASK-2] Author `tests/test_worktree_lifecycle.py` (8 tests):
  - 1 test for `create_run_worktree` happy path
  - 1 test for collision handling
  - 2 tests for `current_worktree_is_run` (True from run worktree, False from main)
  - 1 test for `current_run_slug` extraction
  - 1 test for `cleanup_run_worktree` removes worktree
  - 1 test for `cleanup_run_worktree` with `remove_branch=True` removes branch too
  - 1 integration test exercising create + chdir + cleanup end-to-end

- [TASK-3] Update `commands/architect-team.md`:
  - Add `--no-worktree` to flag list with natural-language phrasings
  - Add a new step "Auto-worktree creation (v1.2.0)" between refinement and skill invocation
  - Document re-entry detection + opt-out behavior

- [TASK-4] Update `commands/bug-fix.md` (same as architect-team)

- [TASK-5] Update `commands/mini.md` (same)

- [TASK-6] Extend `skills/common-pipeline-conventions/SKILL.md`:
  - Add `## Auto-worktree lifecycle` section near `## Running in parallel sessions`
  - Cover: when it fires, re-entry detection, --no-worktree opt-out, path + branch convention, cleanup semantics

- [TASK-7] Version bumps in `plugin.json` + `marketplace.json` to `1.2.0`

- [TASK-8] Docs:
  - CHANGELOG: prepend v1.2.0 entry (Added / Changed / Migration sub-sections)
  - CLAUDE.md: replace v1.1.0 lead with v1.2.0 lead naming the auto-worktree default + counts ~1702
  - README: banner / badges / NEW IN v1.2.0 row / status timeline bumped
  - CODEBASE_MAP: last_mapped 2026-05-28; add `worktree_lifecycle.py` to inventory + new test file; counts ~1702 / 74
  - INTEGRATION_MAP: last_synthesized 2026-05-28; note auto-worktree default

- [TASK-9] Commits (4 fine):
  - 1: helper + tests
  - 2: 3 slash commands updated
  - 3: skill body update
  - 4: version bump + docs

- [TASK-10] Write Phase 3 review-evidence at `.architect-team/reviews/v1.2.0-auto-worktree-lifecycle.json` per v6 schema. teammate = "v1.2.0-implementer". Do NOT write `independent_review`.

- [TASK-11] Final verification:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: 1702 passed / 1 skipped.

## Acceptance

All 8 acceptance criteria from `proposal.md`'s QA Guidance section. Full test suite green with +8 net new tests.
