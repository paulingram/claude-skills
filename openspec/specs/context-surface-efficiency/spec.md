# context-surface-efficiency Specification

## Purpose
TBD - created by archiving change context-token-optimization. Update Purpose after archive.
## Requirements
### Requirement: Measured census and ranked findings report

Every efficiency review of CT6's AI-facing instruction surfaces SHALL measure every in-scope surface class (skills/*/SKILL.md bodies, agents/*.md, commands/*.md, project CLAUDE.md, frontmatter descriptions) and SHALL produce a ranked findings report where each finding names the surface, the inefficiency class (cross-file duplication / duplication with another doc / oversized always-loaded surface / boilerplate replication / verbosity without instruction value), an estimated token saving with the estimation method recorded (bytes/4 heuristic), and a concrete remediation. The report SHALL state which existing engines (claude_md_efficiency / token_compression / instruction_compliance) were reused versus fresh analysis.

#### Scenario: Census covers every surface class

- **WHEN** the efficiency review run completes its measurement phase
- **THEN** the findings artifact records a byte total and per-file ranking for each of the five surface classes, and every finding carries an estimated token saving computed as bytes/4 with the method named in the artifact

#### Scenario: Findings are ranked by estimated saving

- **WHEN** the findings report is emitted
- **THEN** findings are ordered by estimated token saving weighted by load frequency (always-loaded > per-invoke > per-spawn), and each finding names its inefficiency class and concrete remediation

### Requirement: Bounded always-loaded CLAUDE.md

The project CLAUDE.md SHALL NOT duplicate the CHANGELOG's release narrative beyond a bounded recent-release window of at most three entries, each a short paragraph, with `CHANGELOG.md` cited as the canonical per-version history. The repo-summary prose SHALL describe the CURRENT state rather than accreting per-release history inline.

#### Scenario: Recent-releases section is bounded

- **WHEN** CLAUDE.md is inspected after the remediation
- **THEN** its `## Recent releases` section contains at most three release entries plus an explicit pointer to `CHANGELOG.md` for the full narrative, and no removed content is lost from the repository (the full narrative remains in `CHANGELOG.md`)

#### Scenario: Current-state framing preserved under the doc-currency gate

- **WHEN** the documentation-currency audit walks CLAUDE.md after the trim
- **THEN** every count and capability statement in CLAUDE.md remains accurate for the shipped version (the trim removes duplication, never currency)

### Requirement: Exact-duplication single-sourcing trims

A low-risk duplication trim SHALL remove only content that is exactly redundant — a block restating a rule verbatim (or near-verbatim) where the canonical `common-pipeline-conventions` section (or another canonical home) is already cited in the same file — and SHALL record a before/after byte count per edited file. A trim that would change what an agent reading the file in isolation is instructed to do is NOT low-risk and SHALL be deferred to the higher-risk list instead.

#### Scenario: Trim removes only cited-canonical restatements

- **WHEN** a duplication trim is applied to an instruction file
- **THEN** the file still cites the canonical section for every rule whose restatement was removed, and the run's evidence records the file's before and after byte counts

#### Scenario: Doubtful trims are deferred

- **WHEN** an analyst cannot show a candidate block is exactly redundant with an already-cited canonical home
- **THEN** the block is left unedited and the candidate appears on the higher-risk deferral list with its estimated saving

### Requirement: Suite and lint invariants for efficiency remediations

Every implemented remediation SHALL keep the full pytest suite green with the same pass/skip totals (or a CHANGELOG-recorded delta), SHALL keep the instruction-compliance lint at zero findings, and SHALL update any touched test pin only via its sanctioned lever. No enforcement gate, skill, agent, or command SHALL be deleted, and the 48/39/23 surface counts SHALL be unchanged.

#### Scenario: Suite green after remediations

- **WHEN** `python -m pytest` runs after all remediations land
- **THEN** the suite passes with the same pass/skip totals as the pre-run baseline, or the delta is recorded in the CHANGELOG entry for the release

#### Scenario: Instruction-compliance lint stays clean

- **WHEN** the instruction-compliance assessment runs over the edited instruction files
- **THEN** it reports zero findings

### Requirement: Higher-risk deferral list

Remediations that could change behavior — pointer-form CLAUDE.md conversion, canonical-skill restructures or splits, trigger-affecting frontmatter-description rewrites, agent-boilerplate slimming, command-wrapper dedup against skill bodies — SHALL NOT be implemented by an efficiency review run; they SHALL be enumerated in the findings report with a per-item estimated token saving and an explicit remediation sketch for item-by-item user decision.

#### Scenario: Deferred items are enumerated, not implemented

- **WHEN** the run's final report is emitted
- **THEN** each higher-risk item appears with its estimated saving and remediation sketch, and the run's git diff contains no edit implementing any deferred item

