# Tasks: worktree-state-resolution

Single implementer slice — bounded scope, ~12 files. No parallel decomposition needed.

## Files owned

- Create: `scripts/setup/worktree_paths.py`
- Create: `tests/test_worktree_state_resolution.py`
- Modify: `hooks/locks.py` (use shared resolution by default)
- Modify: `skills/common-pipeline-conventions/SKILL.md` (new `## Running in parallel sessions` section)
- Modify: `skills/mempalace-integration/SKILL.md` (shared resolution note)
- Modify: `tests/test_locks.py` (one new test for shared-resolution default if needed; or leave unchanged if backwards-compat tests already cover it)
- Modify: `.claude-plugin/plugin.json` (version 1.1.0)
- Modify: `.claude-plugin/marketplace.json` (version 1.1.0)
- Modify: `CHANGELOG.md` (prepend v1.1.0 entry)
- Modify: `CLAUDE.md` (overview + counts)
- Modify: `README.md` (banner, badge, NEW IN v1.1.0 row, Requirements section if it changes)
- Modify: `docs/CODEBASE_MAP.md` (new helper to inventory + count bump)
- Modify: `docs/INTEGRATION_MAP.md` (worktree-aware state resolution under runtime dependencies)

## Tasks

- [TASK-1] Author `scripts/setup/worktree_paths.py`:
  - `is_worktree() -> bool` — subprocess `git rev-parse --git-dir` + `git rev-parse --git-common-dir`; compare resolved absolute paths
  - `shared_state_dir() -> Path` — main worktree's `.architect-team/` (parent of `git --git-common-dir` + `.architect-team`)
  - `run_state_dir() -> Path` — `Path.cwd() / '.architect-team'`
  - All three handle non-git directories gracefully (fallback to cwd)
  - Stdlib only

- [TASK-2] Update `hooks/locks.py`:
  - Import `from scripts.setup.worktree_paths import shared_state_dir` (or duplicate the function locally to avoid cross-dir imports — pick whichever is cleaner; the v1.0.0 plugin convention is stdlib-only helpers with explicit imports)
  - In `_resolve_locks_dir(locks_dir)`: if `locks_dir is None`, return `shared_state_dir() / 'locks'`
  - Preserve the existing `locks_dir=` parameter behavior exactly

- [TASK-3] Author `tests/test_worktree_state_resolution.py`:
  - 2 tests for `is_worktree()`: True from a worktree (created via subprocess), False from main checkout
  - 2 tests for `shared_state_dir()`: same path from main + from worktree (both resolve to main's `.architect-team/`)
  - 1 test for `run_state_dir()`: different paths between main and worktree
  - 1 test for cross-worktree lock coordination: acquire from worktree A, attempt to acquire intersecting scope from worktree B (or simulated equivalent) → blocked
  - Use `tmp_path` + subprocess for worktree setup; clean up after each test

- [TASK-4] Extend `skills/common-pipeline-conventions/SKILL.md`:
  - Add `## Running in parallel sessions` section near the end (before any trailing operating-rules block)
  - Cover: the 3-layer model, the shared-vs-run split, pointer to `superpowers:using-git-worktrees`
  - ~30-50 lines

- [TASK-5] Update `skills/mempalace-integration/SKILL.md`:
  - One sentence in the wake-up section noting the palace path resolves via `shared_state_dir()` for worktree-aware coordination

- [TASK-6] Version bumps:
  - `plugin.json` + `marketplace.json` → "1.1.0"

- [TASK-7] Docs:
  - `CHANGELOG.md` — prepend v1.1.0 entry (Added / Changed / Migration sub-sections per the existing house style)
  - `CLAUDE.md` — replace the v1.0.0 lead paragraph with v1.1.0 lead naming the worktree-aware state resolution; bump test count to ~1694
  - `README.md` — banner v1.1.0, version badge, tests badge ~1694, new NEW IN row, update Requirements section (worktrees are optional but document them)
  - `docs/CODEBASE_MAP.md` — `last_mapped` 2026-05-28; add `scripts/setup/worktree_paths.py` to inventory + the new test file; test count ~1694, file count 73
  - `docs/INTEGRATION_MAP.md` — `last_synthesized` 2026-05-28; add a sub-section about worktree-aware state resolution under runtime dependencies

## Acceptance

All 7 acceptance criteria from `proposal.md`'s QA Guidance section. Full test suite: 1688 → ~1694, zero failures.
