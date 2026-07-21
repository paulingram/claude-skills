# gstack-comparative-analysis — delta (gstack-profile-comparison)

## ADDED Requirements

### Requirement: Reference package staged outside the repo

The gstack reference package SHALL be unpacked at `~/Downloads/gstack-main/` (outside the CT6 repo tree), SHALL never be committed into the repo, and SHALL be read statically only — no gstack executable, tool, installer, or CI workflow is ever executed during the analysis.

#### Scenario: unpack location verified

- **WHEN** the analysis begins
- **THEN** `~/Downloads/gstack-main/` exists with the package contents
- **AND** no path under the CT6 repo tree contains gstack content

#### Scenario: static-read boundary held

- **WHEN** the profiling completes
- **THEN** no gstack binary, script, or workflow was executed (profilers used read-only file access)

### Requirement: Four-tier profile completeness

The gstack profile SHALL cover all four tiers — (a) the skill format tier (`SKILL.md` + `SKILL.md.tmpl` system), (b) the `bin/` tool tier, (c) the evals CI tier, (d) the architecture/ethos docs — each producing a findings artifact whose material claims carry gstack file citations.

#### Scenario: per-tier findings exist

- **WHEN** the profiling phase completes
- **THEN** a findings artifact exists for each of the four tiers under the run's `.architect-team/gstack-comparison/findings/`
- **AND** each material claim in each artifact cites at least one gstack file path

#### Scenario: oversized docs skimmed not read

- **WHEN** the docs-tier profiler processes `CHANGELOG.md` (912 KB) and `TODOS.md` (144 KB)
- **THEN** they are skimmed for recency/direction signals only and the findings say so

### Requirement: Two-sided cited comparison report

The comparison report SHALL contain a surface-by-surface matrix (at minimum: skill format, quality/verification tier, tooling tier, docs tier, memory/context tier, agent-model configuration) and narrative answers to all three questions — what gstack does better, where CT6 is better, which gstack ideas CT6 should adopt — with every material claim citing files on BOTH sides (gstack path + CT6 path).

#### Scenario: matrix + three questions answered

- **WHEN** the report is finalized
- **THEN** it contains the comparison matrix and all three narrative sections
- **AND** every material claim carries a gstack citation and a CT6 citation

#### Scenario: independent citation verification

- **WHEN** an independent reviewer (not the report's author) re-resolves the report's citations
- **THEN** every cited path exists in its respective tree
- **AND** claims the reviewer refutes are corrected or removed before the report is final

### Requirement: Prioritized adoption backlog

The adoption backlog SHALL exist alongside the report, SHALL be prioritized by value-vs-effort ratio, and each item SHALL be actionable as a future pipeline input (solution-requirement-style fields: title, why, acceptance criteria, scope, suggested route); the report SHALL record the backlog's path. No backlog item is implemented in this run.

#### Scenario: backlog exists and is consumable

- **WHEN** the run completes
- **THEN** the backlog file exists alongside the report with items ordered by value-vs-effort
- **AND** each item carries title, why, acceptance criteria, scope, and a suggested route
- **AND** the report records the backlog path

#### Scenario: no implementation this run

- **WHEN** the run completes
- **THEN** no backlog item has been implemented (no source/test/doc changes beyond the OpenSpec analysis record)

### Requirement: Repo hygiene and in-chat delivery

The run's tracked-file footprint SHALL be limited to the OpenSpec analysis record; the report and backlog SHALL live under `.architect-team/` (gitignored); and the full findings SHALL be presented to the user in-chat, not only on disk.

#### Scenario: working tree clean of analysis side-effects

- **WHEN** the run reaches its final report
- **THEN** `git status` in the run worktree shows only the OpenSpec change (and gitignored `.architect-team/` state)

#### Scenario: findings presented in-chat

- **WHEN** the final report is emitted
- **THEN** the user-facing message contains the comparison verdicts and backlog summary in full, with the on-disk paths cited
