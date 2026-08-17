## ADDED Requirements

### Requirement: Bauplan is a conditional dependency armed by its project marker

The `bauplan` plugin (marketplace `bauplan-skills`, source `BauplanLabs/bauplan-skills`) SHALL be declared a member of the conditional-dependency tier, and its applicability trait SHALL be the presence of `bauplan_project.yml` in the target repository. Its absence SHALL never gate setup or a run.

#### Scenario: a Bauplan repository arms the path

- **WHEN** a run targets a repository containing `bauplan_project.yml`
- **THEN** the Bauplan path is armed without user interaction

#### Scenario: a non-Bauplan repository dispatches no bauplan skills

- **WHEN** a run targets a repository with no `bauplan_project.yml` and the request states no Bauplan intent
- **THEN** zero `bauplan-*` skills are dispatched

#### Scenario: setup without the plugin still succeeds

- **WHEN** setup runs on a machine without the `bauplan` plugin installed
- **THEN** setup reports it absent and exits zero

### Requirement: Each bauplan skill is bound to the CT6 phase where it is the right tool

The integration SHALL record an explicit mapping from each of the six `bauplan-*` skills to the CT6 phase or phases at which it applies, and every injection point SHALL carry a stated justification. The mapping SHALL be derived from a review of the whole CT6 injection surface rather than assumed.

#### Scenario: every bauplan skill has a binding

- **WHEN** the integration's skill-to-phase mapping is read
- **THEN** each of `bauplan-explore-data`, `bauplan-data-assessment`, `bauplan-data-pipeline`, `bauplan-safe-ingestion`, `bauplan-data-quality-checks`, and `bauplan-debug-and-fix-pipeline` appears with at least one CT6 phase and a justification

#### Scenario: injection points are justified, not assumed

- **WHEN** an injection point is added to any CT6 surface
- **THEN** the change records why that surface is the right home for it

### Requirement: Bauplan skills augment CT6 invariants and never replace them

Where a CT6 phase mandates a verbatim dispatch or a review gate, that mandate SHALL continue to hold and the bauplan skill SHALL operate inside it. No part of this integration SHALL relax an existing CT6 gate. Where Bauplan's platform safety rules and a CT6 default conflict on a lakehouse operation, Bauplan's rules SHALL win and the conflict SHALL be recorded.

#### Scenario: the verbatim exploration dispatch survives

- **WHEN** the data-eng lane reaches the phase that dispatches `data-engineering-exploration` verbatim on an armed Bauplan run
- **THEN** that verbatim dispatch still occurs
- **AND** any bauplan skill enriches its inputs or execution rather than standing in for it

#### Scenario: no review gate is relaxed

- **WHEN** an armed Bauplan run passes through the paired review gate and the close-out gate
- **THEN** the evidence those gates require is unchanged from an unarmed run

#### Scenario: platform safety rules take precedence

- **WHEN** a Bauplan safety rule conflicts with a CT6 default on a lakehouse operation
- **THEN** the Bauplan rule governs and the conflict is recorded

### Requirement: Bauplan safety context is propagated on the marker, not on plugin presence

The Bauplan lakehouse safety context SHALL be propagated into a target project through the existing opt-in guidance-block mechanism, and its capability check SHALL key on the detected project marker rather than on whether the `bauplan` plugin is installed — so the safety rules remain present on the degraded path.

#### Scenario: safety context survives a missing plugin

- **WHEN** a target project has `bauplan_project.yml` but the `bauplan` plugin is not installed, and the guidance block is opted into
- **THEN** the Bauplan safety guidance block is present in the target project's CLAUDE.md

#### Scenario: no marker means no block

- **WHEN** a target project has no `bauplan_project.yml`
- **THEN** no Bauplan guidance block is added

#### Scenario: opt-in is still required

- **WHEN** the installer runs without the opt-in CLAUDE.md flag
- **THEN** no CLAUDE.md is created or modified

### Requirement: CT6 never handles Bauplan credentials

CT6 SHALL NOT prompt for, store, transmit, or otherwise handle a Bauplan API key or profile. Authentication SHALL remain entirely the plugin's own chain.

#### Scenario: no credential prompt

- **WHEN** any part of the Bauplan integration executes, including setup, arming, and dispatch
- **THEN** no Bauplan credential is requested from the user or written to CT6 state
