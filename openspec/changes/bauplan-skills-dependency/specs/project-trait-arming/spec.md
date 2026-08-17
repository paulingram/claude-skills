## ADDED Requirements

### Requirement: A project trait arms a capability deterministically and recursively

A capability MAY declare a project-level marker file as its applicability trait. Detection SHALL search the target repository recursively, so a marker in a subdirectory of a monorepo arms the capability, and SHALL skip the conventional excluded directories already used by the codebase-trait detectors. Detection SHALL return both a boolean and evidence naming the marker and the path that matched.

#### Scenario: a top-level marker arms the capability

- **WHEN** the marker file is present at the repository root
- **THEN** detection returns true with evidence naming the matched path

#### Scenario: a monorepo subdirectory marker arms the capability

- **WHEN** the marker file exists only in a nested subdirectory of the repository
- **THEN** detection returns true with evidence naming that nested path

#### Scenario: excluded directories do not arm the capability

- **WHEN** the only marker-shaped file lies inside a conventionally-excluded directory such as a dependency or VCS directory
- **THEN** detection returns false

#### Scenario: no marker means not armed

- **WHEN** the repository contains no marker file
- **THEN** detection returns false with evidence stating no trait was detected

### Requirement: Deterministic signals arm silently and inferred signals require one confirmation

Arming SHALL be asymmetric by signal certainty. A detected project marker SHALL arm the capability with no user interaction. Stated intent in the request — the inferred signal, which is the only signal available before a project exists — SHALL surface exactly one confirmation before the first capability-specific dispatch, and SHALL arm only on an affirmative answer. That confirmation is a domain gate: it SHALL fire regardless of any process-gate opt-out, because the user's answer determines what is built.

#### Scenario: marker arms without asking

- **WHEN** the project marker is detected
- **THEN** the capability arms and no confirmation is surfaced

#### Scenario: stated intent asks exactly once

- **WHEN** no marker exists but the request states intent to target the capability's platform
- **THEN** exactly one confirmation is surfaced before the first capability-specific dispatch

#### Scenario: greenfield remains reachable

- **WHEN** the request asks to create a project for the capability's platform from scratch, so no marker can yet exist
- **THEN** the confirmation path is available and, on confirmation, the capability's project-creation skill is reachable

#### Scenario: the confirmation is not skippable as process ceremony

- **WHEN** the run is operating under a process-gate opt-out
- **THEN** the arming confirmation still fires

### Requirement: A declined or unarmed run records its disposition

When the arming confirmation is declined, the run SHALL proceed with generic behavior and SHALL record the declined arming in the run report. When neither a marker nor stated intent is present, the run SHALL dispatch none of the capability's skills.

#### Scenario: decline degrades and is recorded

- **WHEN** the user declines the arming confirmation
- **THEN** the run proceeds with generic behavior
- **AND** the run report records that arming was offered and declined

#### Scenario: no signal means no dispatch

- **WHEN** a run's target has neither the marker nor stated intent
- **THEN** zero capability-specific skills are dispatched
