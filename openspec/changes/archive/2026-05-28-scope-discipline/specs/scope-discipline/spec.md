# Spec: scope-discipline capability

## ADDED Requirements

### Requirement: common-pipeline-conventions has a scope-discipline section

`skills/common-pipeline-conventions/SKILL.md` SHALL gain a `## Scope discipline` section naming the anti-pattern (silently narrowing the prompt's scope), the parity-verb list, the domain-gate rule, the surfacing pattern, and the explicit forbidden patterns.

#### Scenario: section exists exactly once

- **WHEN** the skill body is parsed
- **THEN** it contains `## Scope discipline` exactly once

#### Scenario: section names the anti-pattern explicitly

- **WHEN** the section body is read
- **THEN** it explicitly names "silently narrowing" as the anti-pattern
- **AND** it contrasts the anti-pattern with the v0.9.36 anti-deferral discipline (same shape, different timeline)

#### Scenario: section lists parity-implying verbs

- **WHEN** the section body is read
- **THEN** it lists at least these 6 parity-implying verbs: `match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`
- **AND** for each verb, the section indicates that the implied scope is visual + structural + behavioral parity

#### Scenario: section defines the surfacing pattern

- **WHEN** the section body is read
- **THEN** it states that scope-narrowing IS a domain gate
- **AND** it instructs the agent to surface the scope question via `AskUserQuestion` BEFORE starting work
- **AND** it includes an example question wording

#### Scenario: section forbids documented-deferral patterns

- **WHEN** the section body is read
- **THEN** it explicitly forbids patterns like "documenting work as queued for next runs without explicit user authorization"
- **AND** it explicitly forbids "interpreting parity-implying verbs as partial-match plus follow-ups"
- **AND** it explicitly forbids "unilaterally splitting the user's ask into 'this run' and 'future runs'"

### Requirement: Three pipeline bodies reference the scope-discipline section

Each of `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md` SHALL contain an anti-pattern entry pointing at `common-pipeline-conventions` `## Scope discipline`.

#### Scenario: architect-team-pipeline references the section

- **WHEN** `skills/architect-team-pipeline/SKILL.md` is parsed
- **THEN** it contains a reference to `common-pipeline-conventions` `## Scope discipline` (either by literal string or via the canonical pattern of "per `common-pipeline-conventions` `## Scope discipline`")

#### Scenario: bug-fix-pipeline references the section

- **WHEN** `skills/bug-fix-pipeline/SKILL.md` is parsed
- **THEN** it contains the same reference pattern

#### Scenario: mini-architect-team-pipeline references the section

- **WHEN** `skills/mini-architect-team-pipeline/SKILL.md` is parsed
- **THEN** it contains the same reference pattern

### Requirement: prompt-refiner agent documents the 6th grading axis

`agents/prompt-refiner.md` SHALL be updated to document a 6th grading axis named `scope-fidelity` measuring whether the refined prompt scopes narrower than the original prose reasonably implies.

#### Scenario: agent body names the 6th axis

- **WHEN** `agents/prompt-refiner.md` is parsed
- **THEN** the body contains the substring `scope-fidelity`
- **AND** the grade-schema JSON example in the body includes the axis

#### Scenario: agent body documents what the axis measures

- **WHEN** the agent body is read
- **THEN** it describes the axis as measuring whether the refined prompt scopes narrower than the original prose
- **AND** it states that a flagged `scope-fidelity` is a domain gate (the user MUST be asked to confirm the scope before proceeding)

### Requirement: proposal-refiner skill documents the 6th axis

`skills/proposal-refiner/SKILL.md` SHALL be updated so its Phase R2 grade-schema example includes the `scope-fidelity` axis.

#### Scenario: skill body shows the 6th axis in the grade schema

- **WHEN** `skills/proposal-refiner/SKILL.md` `### Phase R2 — Initial clarity audit + grade` section is parsed
- **THEN** the schema example JSON contains the `scope-fidelity` axis

### Requirement: bug-classifier documents action-verb interpretation

`agents/bug-classifier.md` SHALL be updated with a section on action-verb interpretation: when the prompt contains parity-implying verbs (`match`, `rebuild`, etc.), the classifier MUST surface the scope question (via the `unclear` verdict + an ambiguity question) rather than scoping to a narrower interpretation.

#### Scenario: agent body has the action-verb section

- **WHEN** `agents/bug-classifier.md` is parsed
- **THEN** the body contains language about parity-implying verbs
- **AND** the body instructs the agent to NOT scope narrower than the verb implies
- **AND** the body documents that a parity-verb prompt with narrower-than-literal interpretation should trigger an `unclear` verdict with a scope-clarifying question

### Requirement: system-architect audit modes flag scope-narrowing

`agents/system-architect.md`'s Master Review Audit mode (Phase 7) AND its Phase 2 architect brief sections SHALL include a scope-narrowing check: flag any plan whose scope is narrower than the original prompt without explicit user authorization recorded somewhere in the change folder.

#### Scenario: Master Review Audit names the check

- **WHEN** the Master Review Audit mode section in `agents/system-architect.md` is parsed
- **THEN** the body contains language about checking whether the run's scope matches the original prompt's literal meaning
- **AND** it instructs the audit to flag silent narrowings as a verdict-failure condition

#### Scenario: Phase 2 architect brief names the check

- **WHEN** the Phase 2 architect brief section in `agents/system-architect.md` is parsed
- **THEN** it contains language about confirming the proposed plan's scope matches the original prompt
- **AND** it instructs the architect to surface a scope-clarification question if the proposed plan scopes narrower than the prompt literally implies

### Requirement: Structural tests assert the discipline is documented

The plugin SHALL ship `tests/test_scope_discipline.py` containing grep-audit tests that assert each of the structural requirements above. At least 8 tests.

#### Scenario: test file exists and is discovered

- **WHEN** `python3 -m pytest tests/test_scope_discipline.py --collect-only` runs
- **THEN** it collects ≥ 8 test cases
- **AND** all test cases pass when the structural assertions hold

### Requirement: Version bumped to 1.4.0

`1.4.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top of `CHANGELOG.md`, README banner + version badge, CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.4.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "1.4.0"`

#### Scenario: CHANGELOG carries v1.4.0 entry

- **WHEN** `CHANGELOG.md` is read
- **THEN** the first `## [` entry is `## [1.4.0]`
- **AND** the previous v1.3.0 entry is preserved unchanged below it
