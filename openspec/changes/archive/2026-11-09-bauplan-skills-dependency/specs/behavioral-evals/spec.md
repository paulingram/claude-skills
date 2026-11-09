## ADDED Requirements

### Requirement: Arming behavior is covered by the opt-in eval tier

The opt-in behavioral eval tier SHALL include evals asserting the arming behavior of a trait-armed conditional capability, exercised against a fixture repository carrying the capability's project marker. These evals SHALL remain behind the tier's existing opt-in environment flag, and the default suite SHALL stay key-free and deterministic.

#### Scenario: marker fixture arms and dispatches

- **WHEN** the eval tier runs under its opt-in flag against a fixture repository containing the project marker
- **THEN** the run dispatches at least one of the capability's skills
- **AND** the dispatch is recorded in the run-state artifact the eval asserts against

#### Scenario: bare fixture arms nothing

- **WHEN** the eval tier runs under its opt-in flag against a fixture repository with no marker and no stated intent
- **THEN** zero of the capability's skills are dispatched

#### Scenario: greenfield intent reaches the project-creation skill

- **WHEN** the eval tier runs under its opt-in flag against a fixture with no marker but a request stating intent to target the capability's platform, and the arming confirmation is answered affirmatively
- **THEN** the capability's project-creation skill is reachable

#### Scenario: the default suite is unaffected

- **WHEN** the default suite runs without the opt-in flag or any API key
- **THEN** none of these evals execute and the suite's determinism is unchanged
