# auto-cleanup-merged-worktrees Specification

## Purpose
TBD - created by archiving change auto-cleanup-merged-worktrees. Update Purpose after archive.
## Requirements
### Requirement: Auto-cleanup helper functions

`scripts/setup/worktree_lifecycle.py` SHALL gain two stdlib-only functions: `list_merged_architect_team_worktrees(against="origin/main", exclude_current=True) -> list[Path]` and `cleanup_merged_worktrees(against="origin/main", dry_run=False) -> list[Path]`. Both SHALL only consider worktrees whose branch starts with `architect-team/` — non-architect-team worktrees are never touched.

#### Scenario: list_merged identifies merged architect-team branches

- **WHEN** two worktrees exist on `architect-team/foo` and `architect-team/bar`, with `bar` merged into `origin/main` and `foo` un-merged
- **THEN** `list_merged_architect_team_worktrees()` returns `[<path-to-bar-worktree>]`
- **AND** the un-merged worktree is NOT in the list

#### Scenario: exclude_current safeguard

- **WHEN** invoked from inside a worktree on `architect-team/current`, and that branch IS merged into origin/main
- **THEN** `list_merged_architect_team_worktrees(exclude_current=True)` does NOT include the current worktree
- **AND** with `exclude_current=False`, the current worktree IS included

#### Scenario: non-architect-team branches are ignored

- **WHEN** a worktree exists on a branch like `feature/foo` or `bugfix/baz` (not `architect-team/*`)
- **THEN** that worktree is NEVER included in `list_merged_architect_team_worktrees()` regardless of merge state

#### Scenario: cleanup_merged_worktrees removes the right set

- **WHEN** `cleanup_merged_worktrees()` is called and `list_merged_architect_team_worktrees()` would return `[X, Y]`
- **THEN** worktrees X and Y are removed from the filesystem
- **AND** the function returns `[X, Y]` (the paths cleaned)
- **AND** the corresponding branches are deleted as part of `git worktree remove`

#### Scenario: dry_run preview

- **WHEN** `cleanup_merged_worktrees(dry_run=True)` is called
- **THEN** the function returns the list of paths that WOULD be cleaned
- **AND** no worktree is actually removed
- **AND** no filesystem change is made

#### Scenario: helper is stdlib-only

- **WHEN** the new helpers are imported
- **THEN** they depend only on `subprocess`, `pathlib`, `typing` from the standard library

### Requirement: Slash commands auto-cleanup as first step

Each of `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` SHALL document an auto-cleanup step as the FIRST action of the command flow (before argument parsing, before refinement, before auto-worktree creation). The step is BEST-EFFORT — cleanup failure surfaces a one-line note but does NOT block the new run.

#### Scenario: cleanup is documented as first step in each command

- **WHEN** each of the 3 slash command bodies is parsed
- **THEN** the first action documented is the auto-cleanup step (or a step that includes the auto-cleanup invocation)
- **AND** the step explicitly references `cleanup_merged_worktrees()` or the equivalent helper invocation

#### Scenario: best-effort discipline documented

- **WHEN** the auto-cleanup step body is read
- **THEN** it explicitly states the step is best-effort and a failure does NOT block the new run
- **AND** it says a failure surfaces a one-line note to the user

#### Scenario: pre-cleanup fetch documented

- **WHEN** the auto-cleanup step body is read
- **THEN** it documents the `git fetch origin main` pre-fetch (so `origin/main` is current before merge-detection runs)
- **AND** the fetch itself is best-effort (a network failure does not block the run)

### Requirement: Explicit cleanup command

The plugin SHALL ship a `/architect-team:cleanup-worktrees` command at `commands/cleanup-worktrees.md`. The command SHALL support `--dry-run` to preview cleanup without filesystem changes and `--against <ref>` to override the default `origin/main` comparison.

#### Scenario: command file exists with valid frontmatter

- **WHEN** `commands/cleanup-worktrees.md` is parsed
- **THEN** it has a valid frontmatter with `description` ≥ 30 chars
- **AND** the body documents the `--dry-run` and `--against` flags

#### Scenario: --dry-run preview output

- **WHEN** the user invokes `/architect-team:cleanup-worktrees --dry-run`
- **THEN** the command reports the paths that WOULD be cleaned
- **AND** no filesystem change occurs

### Requirement: Mini Phase M7 cleans its own worktree after green merge

`skills/mini-architect-team-pipeline/SKILL.md`'s Phase M7 (auto-merge to main on green QA) SHALL end with a `cleanup_run_worktree(<current-worktree-path>, remove_branch=False)` invocation, removing the worktree as the final post-merge step. (The branch is already deleted as part of M7's existing branch-delete step; setting `remove_branch=False` here avoids the double-delete.)

#### Scenario: M7 ends with worktree cleanup

- **WHEN** Phase M7 of `mini-architect-team-pipeline` is parsed
- **THEN** the body contains an explicit cleanup step at the end (after the existing branch-delete + compact-prompt)
- **AND** the step references `cleanup_run_worktree` or the equivalent helper

### Requirement: common-pipeline-conventions documents the auto-cleanup

`skills/common-pipeline-conventions/SKILL.md`'s `## Auto-worktree lifecycle` section (added in v1.2.0) SHALL gain a sub-section documenting:
- The two auto-cleanup trigger points (start of every run + mini's M7)
- The `exclude_current` safeguard
- The `--dry-run` capability via the explicit command
- The merged-branch detection mechanism (`git merge-base --is-ancestor`)
- The squash-merge limitation (not auto-detected)

#### Scenario: section has the auto-cleanup sub-section

- **WHEN** the skill body is parsed
- **THEN** the `## Auto-worktree lifecycle` section contains a sub-section heading naming auto-cleanup (e.g., `### Auto-cleanup` or `### Auto-cleanup (v1.3.0)`)

#### Scenario: section names both trigger points

- **WHEN** the sub-section is read
- **THEN** it names "start of every /architect-team family invocation" as trigger 1
- **AND** it names "after mini-pipeline Phase M7 green merge" as trigger 2

### Requirement: Version bumped to 1.3.0

The version string `1.3.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, the top of `CHANGELOG.md`, the README banner + version badge, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.3.0

- **WHEN** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are read
- **THEN** both have `"version": "1.3.0"`

#### Scenario: CHANGELOG carries v1.3.0 entry

- **WHEN** `CHANGELOG.md` is read
- **THEN** the first `## [` entry is `## [1.3.0]`
- **AND** the previous v1.2.0 entry is preserved unchanged below it

