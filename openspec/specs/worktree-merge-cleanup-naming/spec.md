# worktree-merge-cleanup-naming Specification

## Purpose
TBD - created by archiving change worktree-merge-cleanup-naming. Update Purpose after archive.
## Requirements
### Requirement: End-of-run worktree disposition

The system SHALL provide `finalize_run_worktree(worktree_path=None, against="origin/main", branch=None) -> dict` in `scripts/setup/worktree_lifecycle.py`. When invoked at the end of a pipeline run against a worktree on an `architect-team/<slug>` branch, it SHALL remove the worktree and its branch when the branch is merged into `<against>`, and otherwise leave the worktree in place and return an explicit persistence warning. It SHALL never remove a worktree whose branch is not merged. It SHALL be best-effort: any subprocess failure surfaces in the returned dict rather than raising.

#### Scenario: merged branch is removed at end of run

- **WHEN** `finalize_run_worktree` runs against a worktree whose `architect-team/<slug>` branch is merged into `origin/main`
- **THEN** the worktree directory is removed from disk
- **AND** the `architect-team/<slug>` branch is deleted
- **AND** the returned dict has `removed: true`, `merged: true`, and `warning: null`

#### Scenario: unmerged branch is left with a warning

- **WHEN** `finalize_run_worktree` runs against a worktree whose branch is NOT merged into `origin/main`
- **THEN** the worktree directory is left intact on disk
- **AND** the returned dict has `removed: false`, `merged: false`
- **AND** `warning` is a non-empty string naming the worktree path, stating the folder persists until the branch is merged, and giving the manual `git worktree remove <path> && git branch -d architect-team/<slug>` command

#### Scenario: non-run worktree is a no-op

- **WHEN** `finalize_run_worktree` runs against a directory whose branch does NOT start with `architect-team/`
- **THEN** nothing is removed
- **AND** the returned dict has `removed: false` and a `reason` indicating it is not a run worktree

### Requirement: Hidden per-project worktree container layout

`create_run_worktree` SHALL create the run worktree at `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` (a hidden per-project container directory, created if absent) on branch `architect-team/<slug>`. Collision handling SHALL append `-2`, `-3`, … to the slug within the container until both the path and the branch are free. The branch naming convention SHALL be unchanged.

#### Scenario: worktree is created inside the hidden container

- **WHEN** `create_run_worktree("add-billing")` runs in a repo at `<parent>/myapp`
- **THEN** the worktree is created at `<parent>/.myapp-worktrees/add-billing/`
- **AND** the container directory `<parent>/.myapp-worktrees/` exists
- **AND** the worktree is checked out on branch `architect-team/add-billing`

#### Scenario: collision bumps the slug inside the container

- **WHEN** `create_run_worktree("add-billing")` runs AND branch `architect-team/add-billing` already exists
- **THEN** the worktree is created at `<parent>/.myapp-worktrees/add-billing-2/` on branch `architect-team/add-billing-2`

### Requirement: Backward-compatible dual-layout cleanup

The v1.3.0 sweep helpers (`list_merged_architect_team_worktrees`, `cleanup_merged_worktrees`) and the slug-derivation helper SHALL recognize worktrees created under BOTH the old flat `<repo>-<slug>` layout AND the new `.<repo>-worktrees/<slug>` layout. A merged worktree under either layout SHALL be swept; a slug SHALL be derivable under either layout for branch cleanup.

#### Scenario: sweep removes merged worktrees under both layouts

- **WHEN** one merged worktree exists under the old flat `<repo>-<slug>` layout AND another merged worktree exists under the new `.<repo>-worktrees/<slug>` layout
- **THEN** `cleanup_merged_worktrees()` removes BOTH

#### Scenario: slug derivation handles both layouts

- **WHEN** the slug is derived from a worktree path under the new `.<repo>-worktrees/<slug>` layout
- **THEN** it returns `<slug>`
- **AND** when derived from a path under the old `<repo>-<slug>` layout it still returns `<slug>`

### Requirement: Explicit end-of-run cleanup messaging

The Phase 8 (full), B8 (bug-fix), and M7 (mini) success paths SHALL emit an explicit end-of-run worktree statement derived from `finalize_run_worktree`: a "cleaned" note when the worktree was removed, or a can't-miss warning when it persists. The canonical convention prose, the three command bodies, and the `cleanup-worktrees` command SHALL document the hidden-container layout and the dual-layout recognition.

#### Scenario: convention documents the new layout and end-of-run behavior

- **WHEN** `skills/common-pipeline-conventions/SKILL.md` `## Auto-worktree lifecycle` is read
- **THEN** the path convention names `<parent-of-repo>/.<repo-name>-worktrees/<slug>/`
- **AND** the cleanup-semantics describe the end-of-run merge-check (remove-if-merged, warn-if-not) and the dual-layout backward-compatibility

#### Scenario: no stale flat-layout default remains documented

- **WHEN** the auto-worktree convention, the three pipeline command bodies, and the `cleanup-worktrees` command are read
- **THEN** none of them documents `<parent>/<repo>-<slug>/` as the current default layout

