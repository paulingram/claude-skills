## ADDED Requirements

### Requirement: A guidance block may be gated on a detected project trait

A guidance block's capability check MAY key on a project trait detected in the target repository rather than on the presence of an installed capability. When a block is trait-keyed, it SHALL be added whenever the trait is detected and the opt-in CLAUDE.md flag is supplied — including when the capability the guidance describes is unavailable — and SHALL be removed when the trait is absent. This exists so that safety-critical guidance survives the degraded path, where guidance is most needed precisely because the tooling that would otherwise enforce it is missing.

#### Scenario: trait present and capability absent still yields the block

- **WHEN** the target project exhibits the trait, the capability itself is not installed, and `--claude-md` is supplied
- **THEN** the trait-keyed guidance block is present in the target project's CLAUDE.md

#### Scenario: trait absent removes the block

- **WHEN** the target project no longer exhibits the trait and the installer runs with `--claude-md`
- **THEN** exactly the fenced block is removed and all other CLAUDE.md content is byte-preserved

#### Scenario: the opt-in flag still governs

- **WHEN** an installer path runs without `--claude-md`, whatever the trait state
- **THEN** no CLAUDE.md is created or modified

#### Scenario: trait-keyed blocks remain idempotent

- **WHEN** an installer with a trait-keyed block runs twice against a project that exhibits the trait
- **THEN** the block is present exactly once
