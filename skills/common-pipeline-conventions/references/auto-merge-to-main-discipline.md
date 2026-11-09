# Auto-merge-to-main discipline (v3.7.0)

This is the canonical home of the auto-merge-to-main rules; the three slash command bodies and the three pipeline skill bodies reference it rather than re-explaining. The user asked for autonomous runs to be self-tidying — a clean run should land on `main` and clean up after itself, not leave a growing pile of feature branches + worktrees behind a manual PR step.

### The rule — `AUTO_MERGE_MAIN` defaults to true

`AUTO_MERGE_MAIN` is **true by default**. On a clean Phase 8 / B8 / M7 pass (the completion audit passes AND the commit landed on `architect-team/<change-name>`), the pipeline merges that branch into `main`, pushes `main`, deletes the branch (local + remote), and removes the run worktree — **but ONLY when the branch merges cleanly**. This supersedes the prior default (feature-branch + recommend-a-PR + persistence-warning) for the merge destination.

### The clean-merge flow

After the completion audit passes + the commit lands on `architect-team/<change-name>`:

1. Probe clean-mergeability with `_branch_cleanly_mergeable(toplevel, branch, "main")` (uses `git merge-tree --write-tree main <branch>` — a pure in-memory merge that NEVER mutates the working tree).
2. If `AUTO_MERGE_MAIN` and the branch is cleanly mergeable → call `merge_branch_to_main_and_prune(branch, worktree_path, push=AUTO_PUSH)` (the orchestrator chdir's to the MAIN checkout first, since the merge runs `git checkout main` there). Report `merged + pruned`.
3. The helper: `git checkout main` → `git merge --no-ff <branch>` → `git push origin main` → remove the worktree → `git branch -d <branch>` (local) + `git push origin --delete <branch>` (remote).

### Safety — conflicts skipped, branch protection always wins, never force

- **Conflict** → the helper changes NOTHING and returns `{merged: False, conflict: True, reason: "conflict"}` (or `"conflict-on-merge"` if an unexpected conflict surfaces during the real merge, in which case it runs `git merge --abort`). The run falls back to today's feature-branch + PR-recommend + persistence-warning behavior. Conflicts are **never** force-resolved.
- **Push rejected** (branch protection on `main`, non-fast-forward, hook rejection) → the helper STOPS pruning, leaves the branch + worktree on disk (recoverable), and returns `{merged: True, pushed: False, reason: "push-rejected"}`. It **never** adds `--force`. The orchestrator reports the rejection and stops; the work is preserved for a manual PR. Branch protection always wins.
- **Best-effort** → `merge_branch_to_main_and_prune` never raises; every outcome is reflected in its returned dict (`{merged, pushed, branch_deleted, worktree_removed, conflict, reason, branch, worktree_path}`).

### Opt-out — `--no-auto-merge`

The `--no-auto-merge` flag (sets `AUTO_MERGE_MAIN=false`) restores today's feature-branch + PR behavior verbatim: push `architect-team/<change-name>`, recommend a PR, emit the v3.6.0 `finalize_run_worktree` persistence warning, and leave the branch + worktree for manual merge. Natural-language equivalents recognized at parse time: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. Use it whenever the user wants the human-review-via-PR gate before anything lands on `main`.

### Startup branch reconciliation

After the v1.3.0 merged-worktree sweep at the start of every `/architect-team` family invocation, the command enumerates stray `architect-team/*` branches via `list_run_branches()` and, when any exist, presents ONE `AskUserQuestion` with three options:

- **merge-all-clean + prune** → for each cleanly-mergeable stray branch, call `merge_branch_to_main_and_prune(branch, worktree_path)`; report any conflicts (left untouched).
- **prune-without-merge** → `cleanup_run_worktree(path, remove_branch=True)` per branch (discard the work).
- **leave** → no-op.

Only `architect-team/*` branches are ever considered — the user's own branches and the command's OWN run branch are NEVER touched. Silent no-op when there are no stray branches. The v1.3.0 sweep already removed the merged-worktree branches, so the reconcile prompt focuses on the unmerged / orphaned strays.

### Reconciliation with `--allow-push-to-default` (D6)

`AUTO_MERGE_MAIN=true` is the new default and **supersedes** the old guard's "feature-branch unless `--allow-push-to-default`" default for the merge destination — a clean run lands on `main` by merging the run branch, not by pushing directly to `main`. `--no-auto-merge` restores the prior feature-branch + PR path, which still honors `--allow-push-to-default` exactly as before. `--allow-push-to-default` remains valid and unchanged for that opt-out path.

### Helpers (v3.7.0)

The two new public functions in `scripts/setup/worktree_lifecycle.py` (stdlib only):

- `list_run_branches(against="main", remote="origin") -> list[dict]` — one descriptor per local `architect-team/*` branch: `{branch, worktree_path, merged_into_main, cleanly_mergeable}`. Non-`architect-team/*` branches are NEVER included. Best-effort → `[]`.
- `merge_branch_to_main_and_prune(branch, worktree_path=None, against="main", remote="origin", push=True) -> dict` — merge a cleanly-mergeable run branch into `main`, push, delete the branch (local + remote), remove the worktree. Always returns `{merged, pushed, branch_deleted, worktree_removed, conflict, reason, branch, worktree_path}`. Never raises; never `--force`.

The internal `_branch_cleanly_mergeable(toplevel, branch, against="main") -> bool` probes via `git merge-tree --write-tree` with a legacy 3-arg fallback; it never mutates the working tree.

### Cross-references

- The 3 pipeline slash command bodies (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) each document the `--no-auto-merge` flag, a `## Startup branch reconciliation (v3.7.0)` section, and the Phase 8 / B8 / M7 auto-merge branch in their default-git-behavior section.
- The 3 pipeline skill bodies (`skills/architect-team-pipeline/SKILL.md` Phase 8, `skills/bug-fix-pipeline/SKILL.md` B8, `skills/mini-architect-team-pipeline/SKILL.md` M7) wire the auto-merge step, gated on `AUTO_MERGE_MAIN` + clean-mergeability + audit-clean.
- `tests/test_auto_merge_main.py` exercises the two helpers against real `git init` + self-remote `origin/main` + `git worktree add` fixtures (no mocks): `list_run_branches` merge-state reporting + non-architect-team exclusion; the clean merge + prune path; the conflict path (main unchanged, branch + worktree intact); the non-run-branch guard.
