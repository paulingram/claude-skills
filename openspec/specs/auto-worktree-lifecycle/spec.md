# auto-worktree-lifecycle Specification

## Purpose
TBD - created by archiving change auto-worktree-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Worktree lifecycle helper

The plugin SHALL ship a `scripts/setup/worktree_lifecycle.py` helper exposing four stdlib-only functions for managing architect-team-run worktrees: `create_run_worktree(slug, base_branch="main", parent_dir=None) -> Path`, `cleanup_run_worktree(worktree_path, remove_branch=False) -> None`, `current_worktree_is_run() -> bool`, `current_run_slug() -> str | None`.

#### Scenario: create_run_worktree builds the expected layout

- **WHEN** `create_run_worktree(slug="add-billing")` is called from `/Users/foo/projects/myapp/` (a clean git repo on `main`)
- **THEN** a new worktree is created at `/Users/foo/projects/myapp-add-billing/`
- **AND** the worktree is checked out on a new branch `architect-team/add-billing`
- **AND** the function returns the absolute path to the new worktree

#### Scenario: collision handling appends suffix

- **WHEN** `create_run_worktree(slug="add-billing")` is called and `architect-team/add-billing` already exists as a branch (active or stale)
- **THEN** the helper appends `-2` (then `-3`, etc.) to find an available name
- **AND** the resulting branch is `architect-team/add-billing-2`
- **AND** the resulting worktree directory uses the same suffixed name

#### Scenario: current_worktree_is_run detects branch pattern

- **WHEN** `current_worktree_is_run()` is called from a checkout whose `HEAD` resolves to `architect-team/<anything>`
- **THEN** it returns `True`
- **AND** when called from `main` or any other branch, it returns `False`

#### Scenario: current_run_slug extracts the slug

- **WHEN** `current_run_slug()` is called from a checkout on branch `architect-team/add-billing`
- **THEN** it returns `"add-billing"`
- **AND** when called from `main`, it returns `None`

#### Scenario: cleanup_run_worktree removes the worktree

- **WHEN** `cleanup_run_worktree(worktree_path)` is called against an existing worktree
- **THEN** `git worktree remove <path>` is invoked
- **AND** the worktree directory is gone afterward
- **AND** with `remove_branch=True`, the branch is also deleted

#### Scenario: helper is stdlib-only

- **WHEN** the module is imported
- **THEN** it depends only on `subprocess`, `pathlib`, `re`, `typing` from the standard library

### Requirement: Slash commands auto-create a worktree by default

Each of `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` SHALL document an auto-worktree step that fires AFTER argument parsing + refinement and BEFORE skill invocation. The step SHALL be skipped when ANY of: `--no-worktree` flag passed, or already inside an `architect-team/*` run worktree.

#### Scenario: default invocation creates a worktree

- **WHEN** `/architect-team <prose>` is invoked from the main checkout (on any branch) without `--no-worktree`
- **THEN** the command flow creates a worktree at `<parent>/<repo-name>-<slug>/` on `architect-team/<slug>` branch
- **AND** the orchestrator chdirs into the new worktree
- **AND** the pipeline skill is invoked with the new worktree as cwd

#### Scenario: --no-worktree opt-out skips creation

- **WHEN** `/architect-team <prose> --no-worktree` is invoked
- **THEN** no worktree is created
- **AND** the pipeline runs in the current checkout (v1.1.0 behavior)

#### Scenario: re-entry detection skips creation

- **WHEN** `/architect-team <prose>` is invoked from inside a worktree on branch `architect-team/some-prior-run`
- **THEN** the auto-worktree step detects re-entry via `current_worktree_is_run()`
- **AND** no nested worktree is created
- **AND** the pipeline runs in the current (existing run) worktree

#### Scenario: natural-language opt-out recognized

- **WHEN** the user types `/architect-team add billing, no worktree`
- **THEN** the argument parser treats `"no worktree"` as the `--no-worktree` flag
- **AND** the prose `"add billing"` becomes the requirement

#### Scenario: bug-fix and mini commands follow the same rule

- **WHEN** `/architect-team:bug-fix` or `/architect-team:mini` is invoked without `--no-worktree`
- **THEN** an `architect-team/<slug>` worktree is auto-created (same convention as `/architect-team`)

### Requirement: common-pipeline-conventions documents the auto-worktree lifecycle

`skills/common-pipeline-conventions/SKILL.md` SHALL gain a `## Auto-worktree lifecycle` section documenting: when the auto-worktree fires, the re-entry detection, the `--no-worktree` opt-out, the path + branch convention, and the cleanup semantics (default: keep on success; explicit cleanup via helper).

#### Scenario: section exists and explains the trigger

- **WHEN** the skill body is parsed
- **THEN** it contains `## Auto-worktree lifecycle` exactly once
- **AND** the section names that auto-worktree fires by default on every `/architect-team` family invocation
- **AND** the section names the `--no-worktree` opt-out

#### Scenario: section documents the path + branch convention

- **WHEN** the section body is read
- **THEN** it names the branch pattern `architect-team/<slug>`
- **AND** it names the path pattern `<parent-of-repo>/<repo-name>-<slug>/`
- **AND** it documents collision-handling (appends `-2`, `-3`, ...)

#### Scenario: section documents cleanup semantics

- **WHEN** the section body is read
- **THEN** it states that cleanup is NOT automatic
- **AND** it gives the cleanup command (`git worktree remove <path> && git branch -d architect-team/<slug>`)

### Requirement: Version bumped to 1.2.0

The version string `1.2.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, the top of `CHANGELOG.md`, the README banner + version badge, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.2.0

- **WHEN** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are read
- **THEN** both have `"version": "1.2.0"`

#### Scenario: CHANGELOG carries the v1.2.0 entry

- **WHEN** `CHANGELOG.md` is read
- **THEN** the first `## [` entry is `## [1.2.0]`
- **AND** the previous v1.1.0 entry is preserved unchanged below it

#### Scenario: README banner + badge at 1.2.0

- **WHEN** `README.md` is parsed
- **THEN** the banner area shows `v 1 . 2 . 0`
- **AND** the version badge reads `1.2.0`

#### Scenario: CLAUDE.md overview names v1.2.0

- **WHEN** `CLAUDE.md`'s overview paragraph is parsed
- **THEN** it names v1.2.0 as the current version
- **AND** it mentions auto-worktree-by-default as the v1.2.0 capability

