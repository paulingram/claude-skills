---
description: Explicit cleanup of merged architect-team/* worktrees. Walks `git worktree list`, identifies any whose branch is merged into `origin/main`, and removes them (worktree + branch). Excludes the current worktree from cleanup by default (safety). Supports `--dry-run` to preview without filesystem changes.
argument-hint: "[--dry-run] [--against <ref>]"
---

# /architect-team:cleanup-worktrees

Explicit cleanup utility. Run this on demand when you want to clean up merged
worktrees without invoking a full pipeline. The same cleanup also auto-fires at
the start of every `/architect-team` family invocation (v1.3.0); this command
is the manual version for when you want to clean now without starting a new
run.

Cleanup recognizes BOTH the old flat `<repo>-<slug>` layout and the new
`.<repo>-worktrees/<slug>` hidden-container layout (v3.6.0) — merge detection
is keyed off the branch, not the on-disk location, so both are swept
identically.

## Flags

- `--dry-run` -> print the paths that WOULD be cleaned; no filesystem changes.
- `--against <ref>` -> override the default `origin/main` comparison reference.

Natural-language equivalents: *"dry run"* / *"preview only"* / *"show me what
would be cleaned"* triggers `--dry-run`. *"compare against develop"* /
*"against staging"* etc. binds `--against` to the named ref.

## Invocation

Refresh origin first (best-effort — a network failure does not block):

```bash
git fetch origin main 2>/dev/null || true
```

Then invoke the helper via the polyglot Python pattern per
`common-pipeline-conventions` `## Cross-platform Python invocation`.

With `--dry-run`:

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; paths = cleanup_merged_worktrees(dry_run=True); print('\n'.join(str(p) for p in paths) or '(no merged worktrees to clean)')" || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; paths = cleanup_merged_worktrees(dry_run=True); print('\n'.join(str(p) for p in paths) or '(no merged worktrees to clean)')"
```

Without `--dry-run`:

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; cleaned = cleanup_merged_worktrees(); print(f'Cleaned {len(cleaned)} worktree(s).'); [print(f'  - {p}') for p in cleaned]" || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; cleaned = cleanup_merged_worktrees(); print(f'Cleaned {len(cleaned)} worktree(s).'); [print(f'  - {p}') for p in cleaned]"
```

When `--against <ref>` is passed, plumb the value through both `dry_run=True`
and the cleanup-mode invocations as the `against=` keyword argument to
`cleanup_merged_worktrees(against='<ref>', ...)`.

## Out of scope

- **Non-architect-team worktrees** — never touched, regardless of merge state.
  Only worktrees whose branch starts with `architect-team/` are candidates.
- **Squash-merged branches** — `git merge-base --is-ancestor` doesn't detect
  squash-merges (different SHA on main). Use `git worktree remove <path>`
  manually if you know the branch was squash-merged.
- **The current worktree** — excluded from auto-cleanup by default (safety:
  don't auto-remove the cwd you're working in). v1.3.0 does not expose an
  override; if you really want to clean the current worktree, `cd` out first
  and re-run.
