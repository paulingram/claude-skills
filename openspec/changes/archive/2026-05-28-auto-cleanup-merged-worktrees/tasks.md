# Tasks: auto-cleanup-merged-worktrees

Single implementer slice.

## Files owned

- Modify: `scripts/setup/worktree_lifecycle.py` (add 2 functions)
- Create: `tests/test_worktree_auto_cleanup.py` (6 tests)
- Modify: `commands/architect-team.md` (auto-cleanup as first step)
- Modify: `commands/bug-fix.md` (same)
- Modify: `commands/mini.md` (same)
- Create: `commands/cleanup-worktrees.md` (explicit cleanup command)
- Modify: `skills/mini-architect-team-pipeline/SKILL.md` (M7 worktree cleanup)
- Modify: `skills/common-pipeline-conventions/SKILL.md` (auto-cleanup sub-section)
- Modify: `tests/test_commands.py` (add `cleanup-worktrees` to EXPECTED_COMMANDS)
- Modify: `.claude-plugin/plugin.json` (1.3.0)
- Modify: `.claude-plugin/marketplace.json` (1.3.0)
- Modify: `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`

## Tasks

- [TASK-1] Add `list_merged_architect_team_worktrees(against, exclude_current) -> list[Path]` and `cleanup_merged_worktrees(against, dry_run) -> list[Path]` to `scripts/setup/worktree_lifecycle.py`. Stdlib only. Parse `git worktree list --porcelain`; for each `architect-team/*` branch, use `git merge-base --is-ancestor <branch> <against>`; collect & return / clean. Skip current worktree when `exclude_current=True`. Skip non-architect-team branches always.

- [TASK-2] Author `tests/test_worktree_auto_cleanup.py` (6 tests):
  - 2 worktrees, one merged → list returns only merged
  - exclude_current=True excludes current; False includes it
  - non-architect-team branches ignored regardless of merge state
  - cleanup_merged_worktrees actually removes (filesystem assertion)
  - cleanup_merged_worktrees with dry_run=True leaves filesystem untouched
  - end-to-end: create 2 worktrees, merge one, call cleanup, assert only merged is gone

- [TASK-3] Update `commands/architect-team.md` — add `## Auto-cleanup of merged worktrees (v1.3.0) — runs first` section at the TOP (before the existing Argument parsing section). Document the best-effort discipline + the `git fetch origin main` pre-fetch + the cleanup helper invocation via polyglot Bash pattern.

- [TASK-4] Same update for `commands/bug-fix.md`.

- [TASK-5] Same update for `commands/mini.md`.

- [TASK-6] Create `commands/cleanup-worktrees.md` — minimal command body invoking the helper via Bash; documents `--dry-run` and `--against <ref>` flags.

- [TASK-7] Update `skills/mini-architect-team-pipeline/SKILL.md` Phase M7 — add a final step after the existing branch-delete + compact-prompt that invokes `cleanup_run_worktree(<current-worktree-path>, remove_branch=False)`. Document the rationale (mini just merged itself → clean up immediately).

- [TASK-8] Extend `skills/common-pipeline-conventions/SKILL.md` `## Auto-worktree lifecycle` section — add `### Auto-cleanup (v1.3.0)` sub-section documenting the 2 trigger points, the `exclude_current` safeguard, `--dry-run` capability, merged-branch detection mechanism, squash-merge limitation.

- [TASK-9] Add `cleanup-worktrees` to `tests/test_commands.py`'s `EXPECTED_COMMANDS` set.

- [TASK-10] Version bumps: `plugin.json` + `marketplace.json` → 1.3.0.

- [TASK-11] Docs: CHANGELOG (v1.3.0 entry), CLAUDE.md (v1.3.0 lead + counts ~1708), README (banner + badges + NEW IN row + status timeline), CODEBASE_MAP (last_mapped 04:00, new test file + commands count 12, tests ~1708 / 75), INTEGRATION_MAP (last_synthesized 04:00, note auto-cleanup default).

- [TASK-12] Commits — 4 logical groups:
  1. Helper functions + tests
  2. 3 slash commands + new cleanup command + test_commands.py
  3. Skill body updates (mini M7 + common-pipeline-conventions)
  4. Version bump + docs

- [TASK-13] Phase 3 review-evidence at `.architect-team/reviews/v1.3.0-auto-cleanup-merged-worktrees.json` per v6 schema. teammate = "v1.3.0-implementer". No `independent_review` block.

- [TASK-14] Final test run:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: 1708 passed / 1 skipped.

## Acceptance

All 8 acceptance criteria from `proposal.md` `## QA Guidance`. Full suite +6 net new tests, zero failures.
