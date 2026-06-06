## ADDED Requirements

### Requirement: Shared rule-constants module

The system SHALL provide `hooks/shared_rule_constants.py`, a stdlib-only module with no import side effects, exporting the rule enumerations that were previously duplicated as literals across the plugin: `FORBIDDEN_GIT_OPERATIONS`, `ACTION_KIND_VALUES`, `TEST_FAILURE_ORIGINS`, and `PARITY_VERBS`.

#### Scenario: module imports cleanly and exposes the four names

- **WHEN** `hooks/shared_rule_constants.py` is imported
- **THEN** it exposes `FORBIDDEN_GIT_OPERATIONS`, `ACTION_KIND_VALUES`, `TEST_FAILURE_ORIGINS`, and `PARITY_VERBS`
- **AND** the import has no side effects (no file writes, no network, no process spawn)

#### Scenario: the constants carry the documented values

- **WHEN** the constants are read
- **THEN** `PARITY_VERBS` contains exactly `match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`
- **AND** `FORBIDDEN_GIT_OPERATIONS` covers `git stash`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>`, `git clean -f`
- **AND** `ACTION_KIND_VALUES` contains exactly `navigate`, `open-drawer`, `open-modal`, `submit`, `input-text`, `reveal`, `no-op`

### Requirement: VAO tooling consumes the shared constants

`hooks/vao_tools.py` and `hooks/pipeline-completion-audit.py` SHALL derive their forbidden-git-operation and test-failure-origin sets from `hooks/shared_rule_constants.py` rather than re-declaring local literals. The observable behavior of every affected tool SHALL be unchanged.

#### Scenario: vao_tools derives the forbidden-git list from the shared module

- **WHEN** `hooks/vao_tools.py` is read
- **THEN** its forbidden-git-operation detection sources its operation set from `shared_rule_constants.FORBIDDEN_GIT_OPERATIONS` (no independently maintained duplicate list)

#### Scenario: pipeline-completion-audit derives test-failure origins from the shared module

- **WHEN** `hooks/pipeline-completion-audit.py` is read
- **THEN** its `TEST_FAILURE_ORIGINS` set is the shared `shared_rule_constants.TEST_FAILURE_ORIGINS` (imported, not re-listed)

#### Scenario: behavior is unchanged

- **WHEN** the full pytest suite runs after the change
- **THEN** every pre-existing test of `vao_tools.py` and `pipeline-completion-audit.py` passes unchanged

### Requirement: Scope-discipline parity-verb single source

The parity-verb list SHALL have a single authoritative source: the `PARITY_VERBS` constant for code, and the canonical prose in `common-pipeline-conventions` `## Scope discipline` for narrative. Each agent file that restates the parity rule (`prompt-refiner`, `bug-classifier`, `system-architect`, `oracle-deriver`) SHALL carry a source-of-truth header comment naming the canonical section; the inline restatement text is otherwise unchanged. A consistency test SHALL assert each inline verb list agrees with `PARITY_VERBS`.

#### Scenario: agent files cite the canonical source

- **WHEN** each of `agents/prompt-refiner.md`, `agents/bug-classifier.md`, `agents/system-architect.md`, `agents/oracle-deriver.md` is read
- **THEN** it contains a source-of-truth comment referencing `common-pipeline-conventions` `## Scope discipline`

#### Scenario: a consistency test pins the inline lists to the constant

- **WHEN** the parity-verb consistency test runs
- **THEN** it asserts every parity verb in `PARITY_VERBS` appears in each of the four agent files
- **AND** the canonical `## Scope discipline` prose in `common-pipeline-conventions` is unchanged

### Requirement: Canonical agent-boilerplate source and sync regenerator

The three byte-identical agent boilerplate blocks — `## Forbidden git operations`, `## Checkpoint discipline`, `## Operating context (v1.0.0)` — SHALL have a single canonical source, and `scripts/setup/sync_agent_boilerplate.py` SHALL be an idempotent regenerator that writes the canonical block text into each standard agent file. The inline blocks remain present in every agent file (load-bearing for dispatched subagents).

#### Scenario: a canonical source exists for the three blocks

- **WHEN** the sync tooling is read
- **THEN** the canonical text of each of the three blocks is defined in exactly one place

#### Scenario: the sync regenerator is idempotent

- **WHEN** `scripts/setup/sync_agent_boilerplate.py` is run against a tree whose agent blocks already match canonical
- **THEN** it makes no changes (no file is modified) and reports zero drift

### Requirement: Agent-boilerplate drift guard

The system SHALL ship `tests/test_agent_boilerplate_sync.py` asserting that every standard agent file's copy of each shared block is byte-identical to the canonical source, with the documented role-specific variants (`adversarial-reviewer`, `oracle-deriver`, `interaction-observer`) explicitly allowlisted as approved variants.

#### Scenario: the drift guard passes on the synced tree

- **WHEN** `python -m pytest tests/test_agent_boilerplate_sync.py` runs on the consolidated tree
- **THEN** it collects at least one test per shared block and all pass

#### Scenario: the drift guard fails on injected drift

- **WHEN** any standard agent's shared block is mutated away from canonical
- **THEN** the drift-guard test fails, naming the offending file and block

### Requirement: Zero behavior change with a green suite

The consolidation SHALL NOT change any runtime behavior or any discipline's enforcement semantics. The full pytest suite SHALL pass — at least the pre-change baseline (2394 passed + 1 skipped) plus the newly added tests — with any pre-existing duplication-asserting test updated only insofar as it now asserts the single-source/sync structure.

#### Scenario: the suite is green after consolidation

- **WHEN** `python -m pytest` runs from the repo root after the change
- **THEN** there are zero failures
- **AND** the passed count is at least the pre-change baseline plus the new tests

### Requirement: Version bump and documentation currency

`3.1.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and the top `CHANGELOG.md` entry; `README.md`, `CLAUDE.md`, and `docs/CODEBASE_MAP.md` SHALL reflect the new module, sync script, and tests.

#### Scenario: plugin metadata at 3.1.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "3.1.0"`

#### Scenario: CHANGELOG carries the v3.1.0 entry

- **WHEN** `CHANGELOG.md` is read
- **THEN** the first `## [` entry is `## [3.1.0]`
- **AND** the previous entry is preserved unchanged below it
