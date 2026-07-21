# skill-boilerplate-compile — delta (quality-upgrades-v3-42)

## ADDED Requirements

### Requirement: Single-source compiled skill boilerplate

Shared skill boilerplate SHALL be defined in exactly one canonical source and compiled into marker-fenced blocks in the five pipeline-driving skills by a deterministic stdlib tool with byte-stable output and a `--check` freshness mode wired into the suite.

#### Scenario: compile is deterministic and checked

- **WHEN** the compile tool runs twice against an unchanged source
- **THEN** the outputs are byte-identical
- **AND** a hand-edit inside a generated block fails `--check` (and the suite pin)

#### Scenario: boilerplate is single-source

- **WHEN** the canonical source changes and the compile re-runs
- **THEN** every consuming skill's fenced block updates identically
- **AND** the instruction-compliance lint remains green over the compiled files

### Requirement: On-demand reference sections for the largest skills

Rarely-fired heavy blocks in the largest skills SHALL be extracted into per-skill `references/` files with read-on-demand pointers at the original call sites, WHERE conservative extraction is possible — gates, disciplines, and test-pinned wiring stay inline in the authoritative body, and a skill whose substantial blocks are all load-bearing is recorded as no-safe-extraction rather than force-reduced. Every pointer SHALL resolve (lint-enforced) and the bodies SHALL shrink measurably where extraction occurred.

#### Scenario: extraction shrinks bodies and pointers resolve

- **WHEN** the extraction lands
- **THEN** each skill where conservative extraction was possible has its SKILL.md byte count reduced versus the pre-change baseline (recorded in the review evidence)
- **AND** each skill with no safely-extractable block is recorded as no-safe-extraction with the blocking pins named
- **AND** every reference pointer resolves to an existing file (lint / test enforced)
