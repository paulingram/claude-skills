# Proposal: auto-cleanup-merged-worktrees (v1.3.0)

## Why

v1.2.0 makes worktree creation automatic but explicitly does NOT auto-clean up — the pipeline emits a recommendation, the user decides when to remove. As `/architect-team` runs pile up, the user's filesystem fills with worktrees from past runs whose branches were merged to `main` long ago. The user's follow-up: *"we need auto cleanup so we resolve trees when branches are merged in."*

Without auto-cleanup, each run produces residue. After 10 runs the user has 10 worktrees on disk, 9 of which are merged-and-forgotten. That's filesystem pollution and cognitive load (`git worktree list` becomes unreadable).

v1.3.0 adds two auto-cleanup trigger points:
1. **At the start of every `/architect-team` family invocation** — sweep all `architect-team/*` worktrees, remove any whose branch is merged into `origin/main`. (Excludes the current worktree if invoked from inside one; that's re-entry, handled by v1.2.0.)
2. **At the end of mini-pipeline's M7 green merge** — the mini pipeline just merged its own branch to main, so it immediately cleans up its own worktree.

Combined: `mini` runs always auto-clean themselves; `architect-team` + `bug-fix` runs auto-clean any LEFTOVER merged worktrees from prior runs at the start of the next run.

## What changes

1. **Two new helpers in `scripts/setup/worktree_lifecycle.py`** (extending the v1.2.0 module):
   - `list_merged_architect_team_worktrees(against: str = "origin/main", exclude_current: bool = True) -> list[Path]` — returns paths of `architect-team/*` worktrees whose branch is merged into `<against>`. Excludes the current worktree by default (so the slash command can call this from inside a run worktree safely).
   - `cleanup_merged_worktrees(against: str = "origin/main", dry_run: bool = False) -> list[Path]` — calls `list_merged_architect_team_worktrees()`, removes each, returns the paths cleaned. Honors `dry_run=True` for preview without side effects.
2. **Three slash commands updated** (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) — add an auto-cleanup step as the FIRST action (before refinement, before auto-worktree creation). Best-effort: cleanup failure NEVER blocks the new run.
3. **`commands/cleanup-worktrees.md`** (NEW) — explicit `/architect-team:cleanup-worktrees` command for on-demand invocation; supports `--dry-run` to preview.
4. **Mini-pipeline Phase M7 updated** — after a successful green merge, the orchestrator removes the run worktree + branch via `cleanup_run_worktree(<path>, remove_branch=True)`. This is the IN-RUN cleanup (the mini pipeline knows it just merged itself).
5. **`common-pipeline-conventions/SKILL.md`'s `## Auto-worktree lifecycle` section updated** to document the new auto-cleanup behavior.
6. **6 new tests** covering: merged-branch detection, current-worktree exclusion, cleanup_merged_worktrees with dry_run, the explicit cleanup command structure, mini's M7 cleanup integration assertion.
7. **Version bump to v1.3.0** in plugin.json + marketplace.json + CHANGELOG + CLAUDE.md + README + maps.

## QA Guidance

### Acceptance Criteria

- [AC-1] `scripts/setup/worktree_lifecycle.py` gains `list_merged_architect_team_worktrees` + `cleanup_merged_worktrees`; both stdlib only; both honor `exclude_current=True` / `dry_run=True` respectively.
- [AC-2] The 3 pipeline-driving slash commands auto-fire `cleanup_merged_worktrees()` as their FIRST step (before refinement). The step is BEST-EFFORT — failure surfaces a one-line note + continues; never blocks the new run.
- [AC-3] `/architect-team:cleanup-worktrees` is invocable; supports `--dry-run` for preview; reports each path cleaned (or would-be-cleaned in dry-run).
- [AC-4] Mini-pipeline Phase M7 (the auto-merge step) now ends with `cleanup_run_worktree(<path>, remove_branch=True)` — the mini run's own worktree is removed after successful merge.
- [AC-5] The current worktree is NEVER auto-removed even if its branch happens to be marked merged. The `exclude_current=True` default in `list_merged_architect_team_worktrees()` enforces this.
- [AC-6] `common-pipeline-conventions/SKILL.md` `## Auto-worktree lifecycle` section documents the two auto-cleanup trigger points.
- [AC-7] All existing tests pass (1702 baseline) + 6 new tests. Target: 1708 / 1 skipped.
- [AC-8] Version `1.3.0` consistent across plugin.json, marketplace.json, CHANGELOG, README, CLAUDE.md.

### Unit Test Targets

- `worktree_lifecycle.py:list_merged_architect_team_worktrees`: returns the right set of paths; excludes current; respects the `against` parameter
- `worktree_lifecycle.py:cleanup_merged_worktrees`: removes the right worktrees; `dry_run=True` doesn't touch the filesystem; idempotent
- The 3 slash command bodies: each contains an `## Auto-cleanup` step as the FIRST action; each lists the cleanup helper invocation

### Integration Test Targets

- End-to-end: create two worktrees on `architect-team/a` and `architect-team/b`, merge `b` to main, call `cleanup_merged_worktrees()`; assert only `b` was removed and `a` is intact.

### Playwright Flows

- N/A.

### Out of Scope

- **Auto-cleanup of NON-architect-team worktrees.** The helper only touches worktrees whose branch starts with `architect-team/`. The user's own worktrees stay untouched.
- **Auto-cleanup based on age.** "Worktree older than N days, remove" is a different policy; v1.3.0 only cleans MERGED branches. Old-but-unmerged stays.
- **Squash-merge detection.** `git branch --merged` doesn't detect squash-merged branches (different SHA). Out of scope for v1.3.0; user runs `--dry-run` to verify, or uses the explicit cleanup command to force-remove a known-squash-merged branch.
- **Splitting the 7-mode `system-architect`** (SR-audit-eff-002) — still deferred.

## Impact

- **Modified:** `scripts/setup/worktree_lifecycle.py` (+2 functions), 3 slash commands, `skills/mini-architect-team-pipeline/SKILL.md` (M7 cleanup), `skills/common-pipeline-conventions/SKILL.md`, plugin.json, marketplace.json, CHANGELOG, CLAUDE.md, README, CODEBASE_MAP, INTEGRATION_MAP.
- **New:** `commands/cleanup-worktrees.md`, `tests/test_worktree_auto_cleanup.py`, 1 openspec change folder.
- **Test count:** 1702 → ~1708.
- **Version:** v1.2.0 → **v1.3.0**.
- **Backwards-compatible:** existing v1.2.0 users see no behavior change for the worktree-creation flow. The auto-cleanup is additive and best-effort.
