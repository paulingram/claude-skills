# Spec: teammate-git-discipline capability

## ADDED Requirements

### Requirement: common-pipeline-conventions has a teammate-git-discipline section

`skills/common-pipeline-conventions/SKILL.md` SHALL gain a `## Teammate git discipline` section naming the 6+ forbidden destructive git operations, the right pattern (orchestrator captures baseline SHA; teammates diff against it), and the worked example from the heirship-app-v2 reflog evidence.

#### Scenario: section exists exactly once

- **WHEN** the skill body is parsed
- **THEN** it contains `## Teammate git discipline` exactly once

#### Scenario: section names the forbidden operations

- **WHEN** the section body is read
- **THEN** it explicitly names `git stash` (and `git stash pop`) as forbidden
- **AND** it names `git reset --hard` as forbidden
- **AND** it names `git rebase` as forbidden
- **AND** it names `git commit --amend` as forbidden
- **AND** it names `git checkout` (to other branches) as forbidden
- **AND** it names `git clean -f` as forbidden

#### Scenario: section documents the baseline-SHA pattern

- **WHEN** the section is read
- **THEN** it states that the orchestrator captures `git rev-parse HEAD` as `$BASELINE_SHA` at run start
- **AND** it states teammates diff against `<baseline>..` instead of using `git stash`

#### Scenario: section names the worked-example failure mode

- **WHEN** the section is read
- **THEN** it references the failure mode: concurrent teammates running `git stash` clobbering each other's work
- **AND** it includes the reflog signature `reset: moving to HEAD` repeated as a diagnostic marker

### Requirement: Three pipeline bodies reference the teammate-git-discipline section

Each of `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md` SHALL contain an anti-pattern entry pointing at `common-pipeline-conventions` `## Teammate git discipline`.

#### Scenario: architect-team-pipeline references the section

- **WHEN** `skills/architect-team-pipeline/SKILL.md` is parsed
- **THEN** it contains a reference to `common-pipeline-conventions` `## Teammate git discipline`

#### Scenario: bug-fix-pipeline references the section

- **WHEN** `skills/bug-fix-pipeline/SKILL.md` is parsed
- **THEN** it contains a reference to `common-pipeline-conventions` `## Teammate git discipline`

#### Scenario: mini-architect-team-pipeline references the section

- **WHEN** `skills/mini-architect-team-pipeline/SKILL.md` is parsed
- **THEN** it contains a reference to `common-pipeline-conventions` `## Teammate git discipline`

### Requirement: All 27 agents document forbidden git operations

Every `agents/*.md` file SHALL contain a `## Forbidden git operations` section listing the forbidden operations + cross-referencing the canonical section in `common-pipeline-conventions`.

#### Scenario: every agent has the section

- **WHEN** `grep -L '^## Forbidden git operations' agents/*.md` runs
- **THEN** zero output (every agent has the section)

#### Scenario: no agent body claims to run forbidden operations

- **WHEN** an audit grep for `git stash`, `git reset --hard`, `git rebase`, `git commit --amend`, `git clean -f` runs against each `agents/*.md` body OUTSIDE the `## Forbidden git operations` section
- **THEN** zero matches indicating the agent runs those operations as its own action

### Requirement: team-spawning-and-review-gates documents the baseline-SHA capture

`skills/team-spawning-and-review-gates/SKILL.md` SHALL gain a `## Baseline SHA capture` sub-section documenting: the orchestrator captures `$BASELINE_SHA = git rev-parse HEAD` at run start; passes it to every teammate's spawn brief; teammates diff against it for verification.

#### Scenario: section exists with required content

- **WHEN** the skill body is parsed
- **THEN** it contains `## Baseline SHA capture` (or equivalent canonical sub-heading)
- **AND** it names `git rev-parse HEAD` as the capture command
- **AND** it names `$BASELINE_SHA` (or a similar named variable) as the captured value
- **AND** it states teammates receive the value in their spawn brief

### Requirement: Structural tests assert the discipline is documented

The plugin SHALL ship `tests/test_teammate_git_discipline.py` with ≥ 8 tests covering the discipline assertions above.

#### Scenario: ≥ 8 tests collected and passing

- **WHEN** `python3 -m pytest tests/test_teammate_git_discipline.py --collect-only` runs
- **THEN** it collects ≥ 8 tests (likely more via parametrize)
- **AND** all collected tests pass

### Requirement: Version bumped to 1.6.0

`1.6.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top of `CHANGELOG.md`, README banner + version badge, CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.6.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "1.6.0"`
