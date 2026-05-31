# Phenotype Subsystem Specification

## Purpose

Define a labeled library of generalized, deployable application-architecture patterns
("phenotypes") that the architect-team pipeline can propose (reuse-first) or be told to use, plus the
stdlib engine that discovers, validates, matches, and emits them, and the first seed phenotype
(user-management).

## Requirements

### Requirement: Phenotype record structure
The system SHALL store each phenotype as `phenotypes/<label>/` containing `phenotype.json`,
`blueprint.md`, and a `scaffold/` directory.

#### Scenario: Well-formed record validates
- **WHEN** `validate_phenotype` runs against a record whose `label` equals its directory name and whose required keys are present and well-typed
- **THEN** it returns an empty error list.

#### Scenario: Label / directory mismatch is rejected
- **WHEN** a `phenotype.json` `label` differs from its containing directory name
- **THEN** `validate_phenotype` returns a non-empty error list naming the mismatch.

#### Scenario: Missing required key is rejected
- **WHEN** a `phenotype.json` omits a required key (e.g. `match`)
- **THEN** `validate_phenotype` returns a non-empty error list.

### Requirement: Deterministic discovery and matching
The system SHALL discover phenotypes by globbing `phenotypes/*/phenotype.json` and SHALL rank them
against a free-text request via deterministic, case-insensitive keyword + trigger-phrase scoring.

#### Scenario: A user-management request matches the user-management phenotype
- **WHEN** `match_phenotype("I want a user management system with login and roles")` runs
- **THEN** the `user-management` phenotype ranks first with a positive score and reports the matched keywords/phrases.

#### Scenario: An unrelated request does not match
- **WHEN** `match_phenotype("render a real-time 3D physics simulation")` runs
- **THEN** the `user-management` phenotype scores 0 and is not proposed.

### Requirement: Scaffold emission with parameter substitution
The system SHALL emit a phenotype's scaffold to a target directory, substituting `{{param}}`
placeholders in both file contents and destination paths, and SHALL support a non-writing dry-run.

#### Scenario: Dry-run lists files without writing
- **WHEN** `emit_scaffold("user-management", tmp, {"service_name": "acme"}, dry_run=True)` runs
- **THEN** it returns the list of would-be-written destination paths and writes nothing to disk.

#### Scenario: Missing required parameter errors
- **WHEN** `emit_scaffold` is called without a required parameter that has no default
- **THEN** it raises (CLI exits non-zero) with a message naming the missing parameter.

### Requirement: Explicit phenotype trigger
`/architect-team` SHALL accept `--phenotype <label>` (and the natural-language equivalents "use the
`<label>` phenotype" / "use phenotypes") and bind the selected phenotype as the run's starting point.

#### Scenario: Flag is parsed and bound
- **WHEN** `/architect-team --phenotype user-management "build accounts for my app"` is invoked
- **THEN** the pipeline loads the `user-management` phenotype and uses its scaffold as the starting point.

### Requirement: Reuse-first auto-suggest is never silent
`reuse-first-design` SHALL check the phenotype library before deciding to build new, and SHALL surface
a strong match to the user as a proposal — never applying a phenotype silently.

#### Scenario: A strong match is proposed, not imposed
- **WHEN** a request strongly matches a phenotype and no in-workspace extend/compose/reuse option exists
- **THEN** the pipeline asks the user whether to base the work on that phenotype before proceeding.

### Requirement: The user-management seed phenotype
The system SHALL ship a generalized `user-management` phenotype (blueprint + scaffold + metadata)
derived from the analyzed source, documenting how the parts interrelate and how they are deployed
(OpenTofu), containing no embedded secrets or account-specific values.

#### Scenario: Seed validates and is matchable
- **WHEN** the test suite runs
- **THEN** `phenotypes/user-management/phenotype.json` validates and `match_phenotype` ranks it first for a user-management request.

#### Scenario: Blueprint documents the user's explicit asks
- **WHEN** `phenotypes/user-management/blueprint.md` is read
- **THEN** it contains a `## How the parts interrelate` section and a `## Deployment` section.

### Requirement: Consumption preserves pipeline rigor
Using a phenotype SHALL emit and then customize the scaffold and drive it through the normal pipeline
phases; the emitted scaffold SHALL NOT be shipped unexamined, and the customizations required SHALL be
enumerated in the blueprint's `## Reuse-Decision hooks` and the scaffold's `post_emit_notes`.

### Requirement: Absorb capability is specified
The system SHALL document the design of an `absorb` capability (a `/architect-team:absorb-phenotype`
command wrapping a `skills/phenotype-absorption/` skill) that ingests an arbitrary codebase into a new
labeled phenotype. The build is deferred to a follow-up change.

#### Scenario: Design is recorded
- **WHEN** `design.md` and `skills/phenotypes/SKILL.md` are read
- **THEN** the absorb capability's command, skill, flow, and guardrails are documented.
