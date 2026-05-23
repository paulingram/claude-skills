# doc-updater-agent Specification

## Purpose

Define a dedicated `doc-updater` agent (opus, bounded `Write` only to the documentation-currency inventory paths — NO `Edit`, NO source-code writes, NO version-source-of-truth writes) that performs the Phase 8 documentation-currency update step automatically, replacing the prior "the orchestrator performs the updates" sentence. The existing `system-architect` Documentation Currency Audit mode (unchanged from v0.9.15) independently verifies; the audit verdict — not the agent's self-report — gates the commit (producer/checker discipline per v0.9.13). Wired into BOTH the main `architect-team-pipeline` (Phase 8) AND the `bug-fix-pipeline` (Phase B8) so doc currency is automatic for both feature work and bug fixes.

## Requirements

### Requirement: doc-updater agent

The system SHALL provide a `doc-updater` agent at `agents/doc-updater.md`. The agent SHALL be `model: opus`, with a tools allowlist of `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write`, `TodoWrite`. `Edit` MUST NOT be in the tools allowlist (the agent uses whole-file rewrites via Write, not surgical edits). The agent body SHALL document its inputs, process, output report schema, bounded Write scope (explicit list of allowed inventory paths), what it does NOT do (negative-space section), and hard rules.

#### Scenario: agent file exists with valid frontmatter

- **WHEN** `agents/doc-updater.md` is parsed
- **THEN** it has the 5 required frontmatter keys (`name`, `description`, `tools`, `model`, `color`)
- **AND** `model` is `opus`
- **AND** the tools allowlist contains `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write`, `TodoWrite`
- **AND** the tools allowlist does NOT contain `Edit`
- **AND** the agent is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`

#### Scenario: agent body documents the required sections

- **WHEN** the agent body is parsed
- **THEN** it contains `## Inputs`, `## Process`, `## Output schema`, `## Bounded Write scope`, `## What this agent does NOT do`, and `## Hard rules` sections
- **AND** the `## Bounded Write scope` section enumerates the allowed inventory paths
- **AND** the `## What this agent does NOT do` section explicitly forbids writes to source code, tests, openspec/*, and the version-source-of-truth files (`plugin.json`, `marketplace.json`)

### Requirement: doc-updater agent process (read sources → identify stale → edit in place)

The `doc-updater` agent body's `## Process` section SHALL document a five-step process: (1) inventory walk — read every inventory doc's current state; (2) diff scan — read the run's `git diff` against the merge base; (3) staleness identification — for each diff-invalidated invariant, record a stale-section entry with required fields `{doc_path, section_anchor, current_value, expected_value, justification}`; (4) update in place — whole-file rewrites via Write (not surgical Edit); (5) report — write a structured JSON to `<cwd>/.architect-team/documentation-currency/updates-<ts>.json` enumerating every file touched and every section updated with its triggering justification.

#### Scenario: process steps documented

- **WHEN** the structural test parses the agent body's `## Process` section
- **THEN** it finds each of the five process steps named (inventory walk, diff scan, staleness identification, update in place, report)
- **AND** the stale-section entry fields are enumerated (`doc_path`, `section_anchor`, `current_value`, `expected_value`, `justification`)
- **AND** the report path pattern `documentation-currency/updates-` is named

#### Scenario: whole-file rewrite strategy stated

- **WHEN** the agent body is parsed
- **THEN** the body explicitly states that updates are whole-file rewrites (via Write), NOT surgical edits (Edit is not in the allowlist)
- **AND** the body explains the rationale (avoids partial-update inconsistency across same-file invariants)

### Requirement: documentation-currency skill references the doc-updater agent

The `skills/documentation-currency/SKILL.md` body SHALL be updated to name the `doc-updater` agent as the update mechanism. The skill SHALL document the producer/checker discipline: the `doc-updater` agent updates the inventory docs; the `system-architect` Documentation Currency Audit mode (unchanged from v0.9.15) independently verifies; the audit verdict — not the agent's self-report — gates the commit.

#### Scenario: documentation-currency skill names the doc-updater agent

- **WHEN** the structural test parses `skills/documentation-currency/SKILL.md`
- **THEN** it finds an explicit reference to the `doc-updater` agent as the update mechanism
- **AND** it finds language describing the producer/checker pairing (doc-updater produces; system-architect audits)
- **AND** it cites v0.9.13's producer/checker discipline (or v0.9.15's documentation-currency gate; either reference acceptable)

### Requirement: architect-team-pipeline Phase 8 dispatches doc-updater

The `skills/architect-team-pipeline/SKILL.md` body's `### Documentation-currency gate` block SHALL be modified so step 1 (Update) dispatches the `doc-updater` agent instead of stating "the orchestrator performs the updates." Step 2 (Audit, via `system-architect` in Documentation Currency Audit mode) and step 3 (Gate) SHALL remain structurally unchanged.

#### Scenario: Phase 8 doc-currency block dispatches doc-updater

- **WHEN** the structural test parses the Phase 8 documentation-currency block of `skills/architect-team-pipeline/SKILL.md`
- **THEN** step 1 (Update) names the `doc-updater` agent as the dispatch
- **AND** step 2 still names the `system-architect` Documentation Currency Audit mode
- **AND** step 3 (Gate) still states that `pipeline-completion-audit.py` enforces the verdict

### Requirement: bug-fix-pipeline Phase B8 dispatches doc-updater

The `skills/bug-fix-pipeline/SKILL.md` body's Phase B8 (or its inherited documentation-currency reference) SHALL be modified to name the `doc-updater` agent dispatch — replacing the current inherited language that defers to "the orchestrator updates." The bug-fix pipeline MUST run the same dispatch, audit, and gate as the main pipeline.

#### Scenario: bug-fix-pipeline Phase B8 names doc-updater dispatch

- **WHEN** the structural test parses the Phase B8 section (or the documentation-currency reference) of `skills/bug-fix-pipeline/SKILL.md`
- **THEN** it finds an explicit reference to the `doc-updater` agent dispatch
- **AND** the language confirms the same dispatch / audit / gate flow as the main pipeline

### Requirement: pytest structural coverage for v0.9.23

The system SHALL include pytest structural-test files:

- `tests/test_doc_updater_agent.py` — frontmatter; `model: opus`; tools allowlist exact (Read/Glob/Grep/LS/Bash/Write/TodoWrite); Edit not in allowlist; body sections present; bounded Write scope documented; what-this-agent-does-NOT-do section forbids source-code / test / openspec / version-json writes.
- `tests/test_doc_updater_wiring.py` — documentation-currency skill names the agent; architect-team-pipeline Phase 8 dispatches the agent; bug-fix-pipeline Phase B8 dispatches the agent.

Existing tests SHALL be updated: `tests/test_agents.py` `EXPECTED_AGENTS` += `doc-updater`.

#### Scenario: full suite passes at v0.9.23

- **WHEN** `python -m pytest -q` runs from the repo root
- **THEN** the suite exits 0
- **AND** the total passing-test count is strictly greater than 824 (the v0.9.22 baseline)
- **AND** no pre-existing test regresses

### Requirement: Documentation + release v0.9.23

The plugin SHALL be released as `v0.9.23`:

- `README.md` banner shows `v 0 . 9 . 23`; version badge `0.9.23`; tests badge reflects the new total; NEW IN panel header bumped to `v0.9.23`; a new v0.9.23 row at the top of the panel; timeline `(current)` marker moved to v0.9.23; inventory grid shows `SKILLS (22)` / `AGENTS (22)` (+ `doc-updater`) / `COMMANDS (7)`.
- `CHANGELOG.md` carries a prepended `## [0.9.23] — 2026-05-23` entry covering REQ-001..006 with the user's verbatim directive as the WHY.
- `docs/CODEBASE_MAP.md` — `last_mapped` bumped; agent count 21 → 22; new section for `agents/doc-updater.md` in §3/§4; §1 references v0.9.23.
- `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; note v0.9.23 adds the doc-updater dispatch (no new external integration).
- `CLAUDE.md` — frontmatter counts updated (22 agents); brief mention of doc-updater + the dispatch in both pipelines.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — `version: "0.9.23"`.

**Meta-poetic outcome:** the v0.9.23 release runs through its OWN Phase 8 doc-currency gate, which dispatches the brand-new `doc-updater` agent against the v0.9.23 diff. The agent eats its first meal on the way out — including any v0.9.22 doc-staleness still lingering. (If the v0.9.22 ship was already doc-current, the agent's report shows `updates: []` for that subset and only the v0.9.23-introduced sections get touched. Either way, the gate runs.)

#### Scenario: README banner and version assertions pass at v0.9.23

- **WHEN** `python -m pytest -q tests/test_readme_styling.py` runs
- **THEN** the banner / version-badge / inventory-count assertions pass at v0.9.23
