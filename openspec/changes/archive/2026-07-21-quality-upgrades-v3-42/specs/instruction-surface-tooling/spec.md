# instruction-surface-tooling — delta (quality-upgrades-v3-42)

## ADDED Requirements

### Requirement: Generated capability index

A machine-generated `docs/CAPABILITY_INDEX.md` SHALL list every skill, command, and agent with a one-line description, produced by a deterministic stdlib generator from the repo inventory, with a regenerate-and-diff freshness test and a CLAUDE.md reference.

#### Scenario: index is generated and fresh

- **WHEN** the generator runs twice against an unchanged repo
- **THEN** the output is byte-identical, matches the committed file, and covers every skill, command, and agent
- **AND** a hand-edit to the committed index fails the freshness test

### Requirement: Recorded non-goals

`docs/CODEBASE_MAP.md` SHALL carry a "What's intentionally NOT here" section with at least four deliberate omissions, each stating the omission, the rationale, and the revisit-trigger.

#### Scenario: non-goals section present

- **WHEN** the section is read
- **THEN** it contains at least four entries each with rationale and revisit-trigger

### Requirement: Enforced changelog rubric

A written `docs/CHANGELOG_RUBRIC.md` SHALL codify the CHANGELOG entry shape, and its deterministic subset — the top entry's version equals the plugin version source-of-truth, and the top entry states the current suite totals — SHALL be enforced by a suite-run deterministic check.

#### Scenario: rubric subset enforced

- **WHEN** the deterministic check runs against a CHANGELOG whose top entry's version mismatches plugin.json or lacks the suite-total line
- **THEN** the check fails naming the violation
- **AND** it passes against the shipped CHANGELOG
