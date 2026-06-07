## Why

The auto-worktree lifecycle (v1.2.0 create + v1.3.0 next-run sweep) leaves two real pain points the user hit directly (they had to manually `git worktree remove` two merged-and-forgotten worktrees this session):

1. **Merged worktrees are only swept at the START of the next run.** There is no removal at the moment a run completes on an already-merged branch, and no clear end-of-run signal that an unmerged worktree folder will persist on disk. The user must remember the folder exists.
2. **The flat naming convention `<parent-of-repo>/<repo-name>-<slug>/` scatters worktrees as siblings of the repo,** cluttering the parent directory and making it hard to (a) see all of a project's worktrees in one place and (b) bulk-inspect or bulk-remove them.

The plugin cannot observe a GitHub PR merge live (full + bug-fix pipelines push a feature branch and recommend a PR; the merge lands later), so a git post-merge hook is explicitly out of scope (user choice). The fix is a non-invasive end-of-run merge-check plus a tidier folder layout.

## What Changes

- **Add** an end-of-run worktree disposition helper `finalize_run_worktree(...)` to `scripts/setup/worktree_lifecycle.py`: at Phase 8 / B8 success, if the run's `architect-team/<slug>` branch is already merged into `origin/main`, remove the worktree + branch immediately; otherwise leave it and return an explicit persistence warning. Complements (does not replace) the v1.3.0 next-run sweep. (REQ-001)
- **Change** the worktree directory naming convention from the flat `<parent>/<repo>-<slug>/` to a hidden per-project container `<parent>/.<repo>-worktrees/<slug>/`, so all of a project's run worktrees collect in one hidden folder. Branch naming `architect-team/<slug>` is unchanged. (REQ-002)
- **Guarantee** backward-compatible cleanup: the v1.3.0 sweep (`list_merged_architect_team_worktrees` / `cleanup_merged_worktrees`) and the slug-derivation helper recognize BOTH the old flat `<repo>-<slug>` worktrees AND the new `.<repo>-worktrees/<slug>` worktrees, so pre-existing worktrees are never orphaned. (REQ-003)
- **Upgrade** the Phase 8 / B8 / M7 cleanup messaging from a soft recommendation to an explicit end-of-run statement: when merged → "cleaned"; when not merged → a can't-miss warning naming the folder, why it persists, and the manual cleanup command. (REQ-004)
- **Document & release** as v3.6.0 — `common-pipeline-conventions` auto-worktree section, the three pipeline command bodies, the `cleanup-worktrees` command, the `worktree_lifecycle.py` docstring, README, CHANGELOG, CLAUDE.md, version bump. (REQ-005)

No breaking change to the public helper signatures already in use; `create_run_worktree` keeps its signature and only changes the directory it computes. Unmerged work is NEVER auto-deleted.

## Capabilities

### New Capabilities

- `worktree-merge-cleanup-naming`: the auto-worktree lifecycle removes a run's worktree automatically at end-of-run when its branch is already merged, warns explicitly when it is not, and groups all of a project's run worktrees under a single hidden per-project container folder — with the existing sweep recognizing both the old and new layouts.

### Modified Capabilities

None. The v1.2.0 create / v1.3.0 sweep enforcement semantics are preserved and extended; no existing spec's requirements change.

## Impact

**Affected files:**

- `scripts/setup/worktree_lifecycle.py` — MODIFIED. New `finalize_run_worktree`; new container-path computation in `create_run_worktree` + `_resolve_collision`; dual-layout `_slug_from_worktree_path`; updated module docstring.
- `skills/common-pipeline-conventions/SKILL.md` — MODIFIED. `## Auto-worktree lifecycle` path convention + cleanup-semantics + auto-cleanup subsections.
- `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` — MODIFIED. Auto-worktree path note + end-of-run finalize wiring.
- `commands/cleanup-worktrees.md` — MODIFIED. Dual-layout recognition note.
- `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md` — MODIFIED. Phase 8 / B8 / M7 finalize + warning messaging.
- `tests/test_worktree_lifecycle.py` — MODIFIED. New-layout create + collision paths.
- `tests/test_worktree_merge_finalize.py` — NEW. finalize merged-removal + unmerged-warning + dual-layout slug + dual-layout sweep.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `README.md`, `CLAUDE.md` — MODIFIED. v3.6.0 release docs.
