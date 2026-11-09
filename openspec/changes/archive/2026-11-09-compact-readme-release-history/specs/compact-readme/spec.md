# compact-readme

## ADDED Requirements

### Requirement: The release history lives complete in docs/RELEASE_HISTORY.md
A new `docs/RELEASE_HISTORY.md` SHALL hold the COMPLETE release history including the current release: every region of the line-anchored move-set (the six historical NEW-IN spotlight blocks, the `### v` sections through v3.9.0, and the dense digest tail through ~v2.3.0 — everything between the durable REQUIREMENTS block and the inventory grid except the retained current spotlight) SHALL appear BYTE-IDENTICAL to its pre-move README bytes, and the current (v3.47.0) release section SHALL appear there too (duplicating the README spotlight). A brief header MAY introduce the file; moved bytes are never edited, reordered, or summarized.

#### Scenario: Byte-identical move verified mechanically
- **WHEN** the moved regions extracted from the pre-move README are diffed against their occurrences in docs/RELEASE_HISTORY.md
- **THEN** every region matches byte-for-byte, and the verification artifact (region list + hashes + diff result) is captured on disk

#### Scenario: Complete history including current
- **WHEN** docs/RELEASE_HISTORY.md is read after the change
- **THEN** it contains the current v3.47.0 section AND every prior release the README carried, and no release present before the move is absent after it

### Requirement: The README is compact with exactly one release section and a pointer
README.md SHALL contain exactly ONE release section (the current release's spotlight), a clearly-visible pointer to `docs/RELEASE_HISTORY.md` for the full history (placed where the history previously began), and ALL durable content (feature guides, setup, config schemas, troubleshooting — including the durable gateway troubleshooting embedded in the v3.41.0 section, which moves WITH its section per the user-ratified option A). The moved regions SHALL be gone from README.md.

#### Scenario: One release section plus pointer
- **WHEN** README.md is read after the change
- **THEN** the only release-narrative section is the current spotlight, the pointer to docs/RELEASE_HISTORY.md is present and visible near the top, and the durable content below the old narrative position is intact

### Requirement: The README banner is current and every pin family stays green
The README banner version SHALL read the current plugin.json version (fixing the inherited RED `test_readme_banner_version_matches_plugin_json`), and every existing README pin family SHALL pass: the spaced banner version + version badge, the SKILLS/AGENTS/COMMANDS inventory grid, the styling elements (block banner, gradient dividers, LOGIC MAP + ▣, theme marker), the derived "Plus 4 OPTIONAL VAO fields" pin with all four names, the python3 prerequisite, and the Agent-Teams requirement mentions. Any pin that references moved content SHALL be retargeted explicitly with the change flagged in the evidence — never silently.

#### Scenario: Banner pin flips from red to green
- **WHEN** the README rewrite lands and test_readme_styling.py runs
- **THEN** test_readme_banner_version_matches_plugin_json passes (it was red on the pre-change checkout — the captured red is the inherited state)

#### Scenario: All pin families pass
- **WHEN** the full suite runs after the change
- **THEN** zero failures, including every README pin family

### Requirement: The compact convention is structurally enforced
A new structural test file SHALL pin the convention so it cannot silently regress: README contains exactly one release section (mechanically countable — e.g. NEW-IN spotlight blocks or release-section markers), the pointer to docs/RELEASE_HISTORY.md exists in README, docs/RELEASE_HISTORY.md exists and contains the current release's version string and the earliest retained release's marker. The new tests SHALL be shown red first (against the pre-change tree or by scratch-mutation) with captured reds, and a verify-check-can-fail verdict SHALL cover this run's added test file per the v3.47.0 check-integrity gate.

#### Scenario: Convention pin bites
- **WHEN** a future edit adds a second release section to README or removes the pointer or the history file
- **THEN** the structural test fails naming the violated convention element

### Requirement: Cross-references and the palace are updated
CLAUDE.md's docs enumeration and docs/CODEBASE_MAP.md's doc inventory SHALL name docs/RELEASE_HISTORY.md; CHANGELOG.md SHALL be untouched; the restructured docs (README.md + docs/RELEASE_HISTORY.md at minimum) SHALL be mined into the MemPalace palace with the mine output captured.

#### Scenario: Docs lists name the new file
- **WHEN** CLAUDE.md and docs/CODEBASE_MAP.md are read after the change
- **THEN** each names docs/RELEASE_HISTORY.md in its docs enumeration

#### Scenario: Palace mined
- **WHEN** the run's evidence is inspected
- **THEN** it cites the executed mine commands and their output for the restructured docs
