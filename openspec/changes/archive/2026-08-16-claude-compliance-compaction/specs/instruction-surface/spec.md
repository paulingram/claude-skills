# instruction-surface — delta for claude-compliance-compaction (v3.61.1)

## ADDED Requirements

### Requirement: The README tests badge mirrors the published suite count

The suite SHALL pin the README's shields.io tests badge to the passing count
stated by the CHANGELOG top entry's suite-total line, so the most visible
count in the repo cannot drift from the (measurement-backed) published
number.

#### Scenario: badge matches the publication

- **GIVEN** a CHANGELOG top entry publishing `N passing`
- **AND** a README tests badge saying `N passing`
- **WHEN** the pin runs
- **THEN** it passes

#### Scenario: badge drift is refused

- **GIVEN** a CHANGELOG top entry publishing `N passing`
- **AND** a README tests badge saying any other count
- **WHEN** the pin runs
- **THEN** it fails naming both numbers

### Requirement: CLAUDE.md stays pointer-shaped toward the canonical docs

CLAUDE.md SHALL carry the operative conventions, the three-release digest
convention, and pointers to the canonical depth surfaces
(`docs/CODEBASE_MAP.md`, `docs/CAPABILITY_INDEX.md`, `CHANGELOG.md`,
`docs/RELEASE_HISTORY.md`, `docs/ETHOS.md`) rather than duplicating their
content inline.

#### Scenario: the capability-index pointer survives

- **GIVEN** the compacted CLAUDE.md
- **WHEN** `test_claude_md_references_the_index` runs
- **THEN** it passes (the pointer block names `docs/CAPABILITY_INDEX.md`)

#### Scenario: the compliance lint stays clean

- **GIVEN** the compacted CLAUDE.md
- **WHEN** `instruction_compliance.py` assesses the repo
- **THEN** it reports zero findings across all in-scope files
