# principles-injection — delta (quality-upgrades-v3-42)

## ADDED Requirements

### Requirement: Single principles source

A single `docs/ETHOS.md` SHALL state the plugin's load-bearing operating principles (at minimum: reuse-first, producer≠checker, honest-boundary, unbounded solving, default-to-action), each with a one-line statement and its named anti-pattern.

#### Scenario: principles doc exists and is complete

- **WHEN** `docs/ETHOS.md` is read
- **THEN** it contains at least five principles, each with a statement and an anti-pattern
- **AND** it is listed in the documentation-currency inventory

### Requirement: Enforced presence in agent and skill surfaces

A marker-fenced principles block (or a lint-verified pointer to `docs/ETHOS.md`) SHALL be present in all 39 agent definitions and in the five pipeline-driving skills, maintained by the boilerplate-sync mechanism so it cannot drift silently.

#### Scenario: every agent carries the block

- **WHEN** the sync mechanism's check mode runs over `agents/*.md`
- **THEN** every agent file contains the current principles block
- **AND** a hand-edited or missing block fails the suite's pin test

#### Scenario: pipeline-driving skills carry the block

- **WHEN** the compile/check mechanism runs over the five pipeline-driving skills
- **THEN** each contains the current principles block or pointer
- **AND** the instruction-compliance lint remains green over the updated files
