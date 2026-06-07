## Context

Extends `scripts/setup/worktree_lifecycle.py` (the canonical home for worktree/branch git subprocesses) and the Phase 8 git-behavior docs. Reuse Decision: **RD-EXTEND** the lifecycle helper + compose `finalize_run_worktree` (v3.6.0) and `_branch_is_merged_into`. No new module.

## Key decisions

### D1 — Clean-mergeability probe without mutating the working tree

`cleanly_mergeable` is decided with `git merge-tree --write-tree <main> <branch>` (git ≥ 2.38): exit 0 + no `CONFLICT` markers → clean. Fallback for older git: a throwaway probe in a detached temp index, or treat "merged_into_main already true" as clean and otherwise attempt-and-abort. The probe NEVER leaves the working tree dirty.

### D2 — `merge_branch_to_main_and_prune`

```
merge_branch_to_main_and_prune(branch, worktree_path=None, against="main", remote="origin", push=True) -> dict
```
- Guard: `branch` must start with `architect-team/` (else `{merged: False, reason: "not-a-run-branch"}`).
- Probe clean-mergeability (D1). If not clean → `{merged: False, conflict: True, reason: "conflict", ...}` — change nothing.
- From the MAIN worktree: `git checkout main`, `git merge --no-ff <branch>`. If the merge unexpectedly conflicts, `git merge --abort` and return `conflict: True`.
- Push `main` when `push` (and detect rejection → `{pushed: False, reason: "push-rejected", ...}`, no force).
- Delete branch: `git branch -d <branch>` (local) + `git push origin --delete <branch>` when pushed.
- Remove worktree: `finalize_run_worktree(worktree_path, ...)` or `cleanup_run_worktree(worktree_path, remove_branch=False)` (branch already deleted).
- Return `{merged, pushed, branch_deleted, worktree_removed, conflict, reason, branch, worktree_path}`. Best-effort — never raises.

### D3 — `list_run_branches`

Enumerate local branches via `git branch --list 'architect-team/*'`; for each, find its worktree (from `git worktree list --porcelain`), compute `merged_into_main` (`_branch_is_merged_into`) and `cleanly_mergeable` (D1). Non-`architect-team/*` branches are never included. Best-effort → `[]` on failure.

### D4 — Phase 8 wiring (orchestrator-side, documented in skill + command bodies)

After the completion audit passes + the commit lands on `architect-team/<change-name>`:
- If `AUTO_MERGE_MAIN` and the branch is cleanly mergeable → `merge_branch_to_main_and_prune(branch, worktree_path, push=AUTO_PUSH)`; report merged + pruned.
- Else (`--no-auto-merge`, or conflict) → today's behavior: push the feature branch, recommend a PR, emit the v3.6.0 persistence warning.
- Branch-protection rejection → stop + report, never force.

### D5 — Startup reconcile (command-body, domain gate)

After the v1.3.0 sweep: `stray = [b for b in list_run_branches() if not b.merged_into_main]` (merged ones were already swept). If non-empty, `AskUserQuestion` (merge-all-clean+prune / prune-without-merge / leave). On merge-all → `merge_branch_to_main_and_prune` each cleanly-mergeable; report conflicts. On prune-without-merge → `cleanup_run_worktree(remove_branch=True)` per branch (discard). Only `architect-team/*` considered.

### D6 — Reconciliation with `--allow-push-to-default`

`AUTO_MERGE_MAIN=true` is the new default and supersedes the old guard's "feature-branch unless `--allow-push-to-default`" default for the merge destination. `--no-auto-merge` restores the prior feature-branch+PR path (which still honors `--allow-push-to-default` as before). `--allow-push-to-default` remains valid and unchanged for the opt-out path.

## Reuse Decision Log

| Item | Decision | Rationale |
|---|---|---|
| Merge + prune | RD-EXTEND `worktree_lifecycle.py` | Composes `_branch_is_merged_into` + `finalize_run_worktree`. |
| Clean-mergeability probe | RD-NEW internal helper | `git merge-tree --write-tree`; no existing equivalent. |
| Branch listing | RD-EXTEND | Builds on `_parse_worktree_list_porcelain`. |
| Phase 8 / startup wiring | RD-MODIFY docs | Command + skill bodies; no new code path beyond the two helpers. |

## Risks

- **Removing the cwd worktree** on the per-run merge: the merge runs from the MAIN worktree (`git checkout main` there), not from inside the run worktree, so `finalize`/`cleanup` can remove the run worktree safely. The orchestrator chdir's to the main checkout before the merge step.
- **Squash-merge limitation** (inherited): `cleanly_mergeable`/`merged_into_main` use `--is-ancestor`/`merge-tree`; squash-merged branches read as unmerged (safe false-negative).
- **Reversal of the safety default**: explicitly user-requested; `--no-auto-merge` is the opt-out; branch protection still wins; conflicts never forced.
