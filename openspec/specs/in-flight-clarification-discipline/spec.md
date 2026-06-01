# in-flight-clarification-discipline Specification

## Purpose
TBD - created by archiving change in-flight-clarification-discipline. Update Purpose after archive.
## Requirements
### Requirement: common-pipeline-conventions documents the in-flight clarification discipline

`skills/common-pipeline-conventions/SKILL.md` SHALL gain a new top-level section `## In-flight clarification discipline (v2.5.0)` as the canonical home of the rules.

#### Scenario: section exists exactly once

- **WHEN** the canonical skill body is parsed
- **THEN** it contains the heading `## In-flight clarification discipline (v2.5.0)` exactly once

#### Scenario: 3 detection signals are named

- **WHEN** the section is read
- **THEN** it names `intake-state.json` as a detection signal
- **AND** it names `escalation-pending.md` as a detection signal
- **AND** it names unresolved teammate manifests (`teammates/*.json` without matching review-evidence) as a detection signal

#### Scenario: 4 forbidden anti-patterns are named

- **WHEN** the section is read
- **THEN** it names "solve-with-tools-directly" (or equivalent description) as a forbidden anti-pattern
- **AND** it names "answer-conversationally" (or equivalent) as a forbidden anti-pattern
- **AND** it names "spawn-sibling-invocation" (or equivalent — spawning a fresh `/architect-team` invocation as a sibling) as a forbidden anti-pattern
- **AND** it names "silently-ignore" (or equivalent) as a forbidden anti-pattern

#### Scenario: cancellation channel is documented

- **WHEN** the section is read
- **THEN** it names "cancel" as a canonical cancel phrase
- **AND** it names "stop" as a canonical cancel phrase
- **AND** it names "abort" as a canonical cancel phrase
- **AND** it documents that the default leans toward fold-into-pipeline, not toward cancel

#### Scenario: per-run clarifications log path is documented

- **WHEN** the section is read
- **THEN** it names `.architect-team/clarifications/` as the directory where mid-run clarifications are appended

### Requirement: 3 pipeline-driving SKILL.md bodies cross-reference the new canonical section

`skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, and `skills/mini-architect-team-pipeline/SKILL.md` SHALL each gain a one-paragraph reference to the new canonical section, located in or near each body's `## Default mode of operation` (or equivalent) sub-section.

#### Scenario: each pipeline body references the canonical section

- **WHEN** each pipeline body is parsed
- **THEN** it contains the substring "In-flight clarification" referring to the new canonical section in `common-pipeline-conventions`

### Requirement: 3 pipeline-driving slash command bodies cross-reference the new canonical section

`commands/architect-team.md`, `commands/bug-fix.md`, and `commands/mini.md` SHALL each gain a brief reference to the new canonical section.

#### Scenario: each command body references the canonical section

- **WHEN** each of the 3 command bodies is parsed
- **THEN** it contains the substring "In-flight clarification" referring to the canonical section

### Requirement: Structural tests assert the v2.5.0 framework is wired

`tests/test_in_flight_clarification_discipline.py` SHALL exist with ≥ 20 tests covering all of the above requirements.

#### Scenario: test file collects ≥ 20 tests

- **WHEN** `python3 -m pytest tests/test_in_flight_clarification_discipline.py --collect-only` runs
- **THEN** it collects at least 20 tests
- **AND** every collected test passes

#### Scenario: existing 2482-test baseline still passes

- **WHEN** `python3 -m pytest -q` runs against the v2.5.0 branch
- **THEN** the prior v2.4.0 baseline of 2482 passing + 1 skipped tests remains green
- **AND** the new tests add to the count (target ~2505 + 1 skipped)

### Requirement: Version is bumped to 2.5.0

The plugin's version SHALL be bumped to `2.5.0` consistently across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top-of-CHANGELOG.md, the README banner, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 2.5.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "2.5.0"`

#### Scenario: CHANGELOG documents the additive release

- **WHEN** `CHANGELOG.md` is read at the top entry
- **THEN** the v2.5.0 entry is present
- **AND** it names the canonical section
- **AND** it confirms backwards compatibility

