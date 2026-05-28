# Design: auto-cleanup-merged-worktrees

## Reference

Full ACs + WHY + WHAT in `proposal.md`. This file holds the architectural anchors.

## Trigger points (2)

### Trigger 1 — Start of every `/architect-team` family invocation

Inserts at the very start of each slash command's flow, BEFORE refinement and BEFORE auto-worktree creation:

```
0. Auto-cleanup merged worktrees (NEW in v1.3.0)
   - Best-effort: failure surfaces a one-line note + continues
   - Excludes the current worktree if invoked from inside a run worktree (re-entry case)
   - Calls cleanup_merged_worktrees() with default args (against=origin/main, dry_run=False)
1. Parse arguments + flags
2. Bind $REQ_DIR
3. Refinement (when applicable)
3.5. Auto-worktree creation (v1.2.0)
4. Invoke skill
```

This is the "sweep stale worktrees on each new run" trigger. Solo user running `/architect-team` weekly: each new run cleans up the previous merged-and-forgotten ones.

### Trigger 2 — End of mini-pipeline Phase M7 (after green merge)

The mini pipeline auto-merges to main on green QA (existing v0.10.0 behavior). After the merge succeeds, the run's own worktree is mergeable; the next action is cleanup:

```
M7. Auto-merge to main on green
    1. Commit + push branch
    2. Fast-forward main + push
    3. Branch delete (existing v0.10.0 behavior)
    4. NEW: cleanup_run_worktree(<this-worktree-path>, remove_branch=False)  
       — branch is already deleted in step 3
    5. Emit /compact prompt
```

The "in-run cleanup" handles the just-merged mini case immediately; trigger 1 handles everything else on subsequent runs.

## The `exclude_current` safeguard

When the slash command's trigger 1 fires from inside a run worktree (re-entry case after a long-running pipeline that creates new worktrees on its own), the auto-cleanup MUST NOT remove the current worktree even if its branch is already merged. The default `exclude_current=True` enforces this:

```python
def list_merged_architect_team_worktrees(against="origin/main", exclude_current=True) -> list[Path]:
    # 1. Get current worktree path (if any) via git rev-parse --show-toplevel
    # 2. List all worktrees: git worktree list --porcelain
    # 3. For each non-current worktree on an architect-team/* branch:
    #    - Check git merge-base --is-ancestor <branch> <against>
    #    - If True, include in the result
    # 4. Return the list
```

The slash command can override this with `exclude_current=False` only via explicit user invocation of `/architect-team:cleanup-worktrees --include-current` (a hidden flag for force-cleanup; not exposed in the natural-language equivalent set). For now, v1.3.0 doesn't ship that override — it's a future v1.x option.

## Merged-branch detection

Use `git merge-base --is-ancestor <branch> origin/main`:
- **Returns 0:** branch tip is reachable from origin/main → branch is fully merged (fast-forward or merge-commit). Safe to clean.
- **Returns 1:** branch tip is NOT reachable → either un-merged, or merged via squash (squash produces a different SHA on main). Leave alone.

Squash-merge detection is intentionally out of scope per the proposal. `--is-ancestor` is the safe-side check: false negatives (squash-merged branches not auto-cleaned) are better than false positives (un-merged work auto-deleted).

The `against` parameter defaults to `origin/main`. The slash command refreshes `origin/main` via `git fetch origin main` before invoking the cleanup; the helper itself does NOT auto-fetch (to keep it side-effect-free except for the cleanup itself).

## The explicit cleanup command

`/architect-team:cleanup-worktrees [--dry-run] [--against <ref>]`

- `--dry-run`: print the list of worktrees that WOULD be cleaned; no filesystem changes.
- `--against <ref>`: override the default `origin/main` (e.g., for branch-specific workflows).

The command body is minimal — just a Bash invocation of the helper. The command exists so users can clean explicitly without running a full pipeline.

## Reuse Decision Log

### RD-1: Extend `scripts/setup/worktree_lifecycle.py`

**Decision:** Extend in place.
**Anchor:** v1.2.0's `worktree_lifecycle.py` already houses the create/cleanup/detection trio. The auto-cleanup helpers are the natural completion of that lifecycle.
**Anti-pattern avoided:** A new `scripts/setup/worktree_cleanup.py` would split lifecycle responsibility.

### RD-2: Extend 3 slash command bodies with the auto-cleanup step

**Decision:** Extend in place.
**Anchor:** Same pattern as v1.2.0 added the auto-worktree step. The auto-cleanup is the symmetric counterpart at the start of the flow.

### RD-3: NEW `commands/cleanup-worktrees.md`

**Decision:** New command.
**Anchor:** v1.2.0 has 11 commands; v1.3.0 adds the 12th (`cleanup-worktrees`). The explicit cleanup capability is a distinct user-facing surface — bundling it into an existing command would confuse the surface area.

### RD-4: Extend `mini-architect-team-pipeline/SKILL.md` Phase M7

**Decision:** Extend in place — add step 4 (cleanup) to the existing M7 sequence.
**Anchor:** M7 already does the merge + branch delete. Adding worktree cleanup is the natural completion of the post-merge cleanup chain.

### RD-5: Extend `common-pipeline-conventions/SKILL.md` `## Auto-worktree lifecycle`

**Decision:** Extend the existing section (added in v1.2.0). New sub-section: `### Auto-cleanup (v1.3.0)`.

### RD-6: Tests in a new file `tests/test_worktree_auto_cleanup.py`

**Decision:** New file, NOT extending `test_worktree_lifecycle.py`.
**Reason:** v1.2.0's lifecycle tests cover the create/cleanup/detection trio. The v1.3.0 auto-cleanup is a higher-level behavior (sweep merged ones, exclude current) — separate file for clean separation.

### RD-7: NO change to `worktree_paths.py`

**Decision:** Unchanged (v1.1.0).

## Migration / backwards compatibility

- **v1.2.0 → v1.3.0:** Existing users get auto-cleanup of merged worktrees on their next `/architect-team` invocation. The cleanup is BEST-EFFORT — if it fails (filesystem permission, git error), a one-line note surfaces but the new run proceeds.
- **No flag required.** The behavior is on by default. To opt out per-invocation, the user runs the slash command with `--no-cleanup` (or natural-language equivalents); to opt out globally, no mechanism is provided (the cleanup is desirable).

## Trade-offs accepted

- **Best-effort failure on cleanup** — if a worktree fails to clean (e.g., it has uncommitted changes the user forgot), the next run continues. The user sees the warning but doesn't get blocked. Acceptable: the alternative (block the new run until manual cleanup) is hostile.
- **Squash-merged branches not detected** — see proposal Out of Scope.
- **Subprocess overhead** — each cleanup pass runs ~3-5 git commands. Negligible.
- **Network call for `git fetch origin main`** — the slash command's pre-cleanup fetch adds ~1s. Worth it for correctness (otherwise the local `origin/main` ref might be stale and merged branches go undetected).

## Version

v1.3.0 — minor bump (additive feature, no breaking changes).
