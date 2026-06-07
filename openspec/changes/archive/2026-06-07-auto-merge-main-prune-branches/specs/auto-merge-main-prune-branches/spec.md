## ADDED Requirements

### Requirement: Auto-merge-to-main is the default at Phase 8

When a run reaches a clean Phase 8 (completion audit exits 0) AND `AUTO_MERGE_MAIN` is true (the default), the orchestrator SHALL merge the run's `architect-team/<change-name>` branch into `main` with `--no-ff`, push `main` when `AUTO_PUSH` is true, delete the branch (local, and remote when pushed), and remove the run worktree. The merge SHALL proceed ONLY when the branch merges cleanly into `main`. The orchestrator SHALL NEVER force-push and SHALL NEVER bypass branch protection.

#### Scenario: clean run auto-merges and prunes

- **WHEN** a run finishes a clean Phase 8 with `AUTO_MERGE_MAIN` true and the branch merges cleanly into `main`
- **THEN** the branch is merged `--no-ff` into `main`
- **AND** `main` is pushed (when `AUTO_PUSH`), the branch is deleted (local + remote), and the run worktree is removed
- **AND** no stray branch or worktree remains for that run

#### Scenario: branch-protection rejection stops without forcing

- **WHEN** the push to `main` is rejected (branch protection / non-fast-forward / auth)
- **THEN** the orchestrator surfaces the rejection and STOPS
- **AND** never escalates to a force-push

#### Scenario: conflict is skipped, not forced

- **WHEN** the run branch does NOT merge cleanly into `main`
- **THEN** it is NOT merged
- **AND** the branch + worktree are left intact and the conflict is reported
- **AND** the run falls back to recommending a manual PR

### Requirement: Per-workstream opt-out via --no-auto-merge

The system SHALL provide a `--no-auto-merge` flag (with natural-language equivalents *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*) on `/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini`. When set, `AUTO_MERGE_MAIN` SHALL be false and the run SHALL use the prior behavior: commit on `architect-team/<change-name>`, push it, recommend a PR, and emit the worktree-persistence warning.

#### Scenario: opt-out preserves feature-branch + PR behavior

- **WHEN** `--no-auto-merge` (or a natural-language equivalent) is passed
- **THEN** the run commits on its `architect-team/<change-name>` branch, pushes it, recommends a PR, and does NOT merge into `main` or delete the branch/worktree

### Requirement: Auto-merge fires only after the completion audit passes

Auto-merge SHALL fire ONLY after the Phase 8 completion audit exits 0. A non-clean audit SHALL block the merge exactly as it blocks the commit today.

#### Scenario: failing audit blocks auto-merge

- **WHEN** the completion audit exits non-zero
- **THEN** the run does NOT commit AND does NOT auto-merge to `main`

### Requirement: Startup branch reconciliation prompt

At activation, after the v1.3.0 merged-worktree sweep and before the new run's work, the command SHALL enumerate stray local `architect-team/*` branches. When at least one exists, it SHALL present one prompt offering: (a) merge every cleanly-mergeable stray branch into `main` and prune its branch + worktree, (b) prune without merging, or (c) leave everything. On (a) it SHALL merge only cleanly-mergeable branches and report any that conflict. It SHALL NEVER consider non-`architect-team/*` branches. With zero stray branches it SHALL be a silent no-op.

#### Scenario: stray branches trigger the reconcile prompt

- **WHEN** stray `architect-team/*` branches exist at activation
- **THEN** one prompt offers merge-all-clean+prune / prune-without-merge / leave
- **AND** on merge-all only cleanly-mergeable branches are merged and pruned; conflicting ones are reported and left

#### Scenario: own branches are never touched

- **WHEN** the reconcile step runs
- **THEN** branches NOT starting with `architect-team/` are never enumerated, merged, or pruned

#### Scenario: no stray branches is a silent no-op

- **WHEN** there are zero stray `architect-team/*` branches at activation
- **THEN** the reconcile step prints nothing and proceeds

### Requirement: Branch-reconciliation helpers

`scripts/setup/worktree_lifecycle.py` SHALL provide `list_run_branches(against="main", remote="origin") -> list[dict]` returning every local `architect-team/*` branch with `{branch, worktree_path, merged_into_main, cleanly_mergeable}`, and `merge_branch_to_main_and_prune(branch, worktree_path=None, against="main", remote="origin", push=True) -> dict` that merges a cleanly-mergeable branch into `main`, pushes (when `push`), deletes the branch, and removes the worktree — aborting cleanly and changing nothing on conflict. Both SHALL be best-effort (failures reflected in the return value, never raised) and SHALL never consider non-`architect-team/*` branches.

#### Scenario: list_run_branches reports merge status per branch

- **WHEN** `list_run_branches` runs with one merged and one unmerged `architect-team/*` branch present
- **THEN** each entry carries the correct `merged_into_main` and `cleanly_mergeable` flags
- **AND** no non-`architect-team/*` branch appears in the result

#### Scenario: merge helper aborts cleanly on conflict

- **WHEN** `merge_branch_to_main_and_prune` is called for a branch that conflicts with `main`
- **THEN** it returns `conflict: true`, does not merge, leaves the branch + worktree intact, and changes nothing on `main`
