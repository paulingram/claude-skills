# Spec: verified-agent-output capability

## ADDED Requirements

### Requirement: A canonical verified-agent-output skill exists

`skills/verified-agent-output/SKILL.md` SHALL exist as the canonical home of the VAO framework, documenting the five layers, the failure-shape taxonomy, the per-shape adversarial-reviewer pairings, the four tool-mediated verification outputs, the run-history shape-detection mechanism, and the composition rules with existing review patterns.

#### Scenario: skill file exists

- **WHEN** the plugin's `skills/` directory is enumerated
- **THEN** `skills/verified-agent-output/SKILL.md` is present
- **AND** it has valid YAML frontmatter with `name: verified-agent-output` and a non-empty `description`

#### Scenario: skill names the five layers

- **WHEN** the skill body is parsed
- **THEN** it explicitly names Layer 1 as the oracle-derivation gate
- **AND** it names Layer 2 as the adversarial-reviewer pairing
- **AND** it names Layer 3 as the tool-mediated execution proof
- **AND** it names Layer 4 as the run-history shape detection
- **AND** it names Layer 5 as the structural test enforcement

#### Scenario: skill enumerates the failure-shape taxonomy

- **WHEN** the skill body is parsed
- **THEN** it names the `parity-verb` task shape
- **AND** it names the `backend-dep` task shape
- **AND** it names the `shared-tree` task shape
- **AND** it names the `dynamic-value` task shape
- **AND** it names the `default` task shape

#### Scenario: skill documents the per-shape adversarial-reviewer pairings

- **WHEN** the skill body is parsed
- **THEN** it pairs `parity-verb` with `oracle-divergence-hunter`
- **AND** it pairs `backend-dep` with `fake-data-hunter`
- **AND** it pairs `shared-tree` with `git-discipline-hunter`
- **AND** it pairs `dynamic-value` with `hardcoded-literal-hunter`
- **AND** it pairs `default` with `general-anti-pattern-hunter`

### Requirement: An oracle-deriver agent exists

`agents/oracle-deriver.md` SHALL exist as a new opus agent with read-only tooling, dispatched at the new Phase 0.5 to walk the named oracle artifact (codebase, design mockup, reference URL, schema) and produce the frozen structural spec the rest of the run measures against.

#### Scenario: agent file exists with valid frontmatter

- **WHEN** `agents/oracle-deriver.md` is loaded
- **THEN** it has YAML frontmatter with `name: oracle-deriver`
- **AND** the frontmatter sets `model: opus`
- **AND** the frontmatter sets a non-empty `description`
- **AND** the frontmatter's `tools` allowlist excludes `Edit` and `Write` to source files (read-only on source; Write is permitted only to `<workspace>/.architect-team/oracle-spec/`)

#### Scenario: agent documents the spec-shape categories

- **WHEN** the agent body is parsed
- **THEN** it names `component-tree` as a `spec_shape` value
- **AND** it names `design-map` as a `spec_shape` value
- **AND** it names `api-contract` as a `spec_shape` value
- **AND** it names `data-model` as a `spec_shape` value
- **AND** it names `hybrid` as a `spec_shape` value

#### Scenario: agent writes the frozen spec to the conventional path

- **WHEN** the agent's output contract is described in its body
- **THEN** it writes to `<workspace>/.architect-team/oracle-spec/<change-name>.json`
- **AND** the spec includes `_human_review_required: true` until the user accepts

### Requirement: An adversarial-reviewer agent exists

`agents/adversarial-reviewer.md` SHALL exist as a new opus agent dispatched alongside every Phase 3 teammate. Its role is shape-paired: the orchestrator's spawn brief names which of the five shapes the adversarial-reviewer is hunting for, and the agent runs the matching `vao_tools.py` tool against the teammate's diff + tool-call log.

#### Scenario: agent file exists with valid frontmatter

- **WHEN** `agents/adversarial-reviewer.md` is loaded
- **THEN** it has YAML frontmatter with `name: adversarial-reviewer`
- **AND** the frontmatter sets `model: opus`
- **AND** the frontmatter sets a non-empty `description`
- **AND** the frontmatter's `tools` allowlist permits Bash (to invoke vao tools) and Read (to inspect the teammate's tool-call log)

#### Scenario: agent writes its verdict to the shared review-evidence file

- **WHEN** the agent's output contract is described in its body
- **THEN** it writes the `adversarial_review` block into the SAME `<cwd>/.architect-team/reviews/<task-id>.json` the teammate wrote
- **AND** the block contains `reviewer`, `shape`, `verdict`, `tool_invoked`, `tool_verdict_path`, `findings`, `reviewed_at` fields

### Requirement: A vao_tools.py module ships the four verification tools

`hooks/vao_tools.py` SHALL exist as a Python module exposing four deterministic verification tools — `verify-oracle-match`, `verify-baseline-clean`, `verify-no-fake-data`, `verify-every-element` — each producing JSON verdict output to `<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json`.

#### Scenario: module file exists

- **WHEN** `hooks/vao_tools.py` is loaded
- **THEN** it is a valid Python module
- **AND** it exposes the four tool functions as callable entry points
- **AND** it exposes a `__main__` CLI dispatching by subcommand name

#### Scenario: verify-oracle-match produces a deterministic verdict

- **WHEN** `verify_oracle_match` is invoked with the same built-path + oracle-spec inputs twice
- **THEN** both invocations produce byte-identical JSON output
- **AND** the JSON includes `matched: bool`, `divergences: [...]`, `match_pct: float`

#### Scenario: verify-baseline-clean detects forbidden git ops

- **WHEN** `verify_baseline_clean` is invoked against a tool-call log containing a `git stash` invocation
- **THEN** the output is `{clean: false, violations: [...]}`
- **AND** the violation record includes `op`, `args`, `line`, `ts`

#### Scenario: verify-no-fake-data detects design-literal hits

- **WHEN** `verify_no_fake_data` is invoked against a diff containing the string `"John Smith"` in production code AND `"John Smith"` is named in the oracle spec's `dynamic_values[]`
- **THEN** the output is `{clean: false, hits: [...]}`
- **AND** each hit record includes `file`, `line`, `match`, `category`

#### Scenario: verify-every-element returns coverage stats

- **WHEN** `verify_every_element` is invoked against a component path + the oracle spec's `elements[]`
- **THEN** the output is `{coverage: float, missing: [...], stub: [...], untested: [...]}`
- **AND** `coverage` is in the closed interval [0.0, 1.0]

### Requirement: Review-evidence schema is bumped to v7

`hooks/review_evidence_schema.py` SHALL bump `SCHEMA_VERSION` from 6 to 7 and add four required fields to `REQUIRED_EVIDENCE_FIELDS` — `oracle_match_review`, `baseline_clean_review`, `no_fake_data_review`, `adversarial_review`. The hook MUST block any evidence file missing any of the new fields or whose `adversarial_review.verdict != "pass"`.

#### Scenario: SCHEMA_VERSION constant equals 7

- **WHEN** `hooks/review_evidence_schema.py` is imported
- **THEN** `SCHEMA_VERSION == 7`

#### Scenario: REQUIRED_EVIDENCE_FIELDS includes the four new fields

- **WHEN** `REQUIRED_EVIDENCE_FIELDS` is inspected
- **THEN** the set includes `oracle_match_review`
- **AND** the set includes `baseline_clean_review`
- **AND** the set includes `no_fake_data_review`
- **AND** the set includes `adversarial_review`

#### Scenario: validate_evidence blocks a v6-shaped evidence file

- **WHEN** `validate_evidence` is called on a v6-shaped evidence dict (missing the four new fields)
- **THEN** the returned gap list is non-empty
- **AND** it names the four missing fields

#### Scenario: validate_evidence blocks adversarial_review with verdict != pass

- **WHEN** `validate_evidence` is called on a v7 evidence dict whose `adversarial_review.verdict == "fail"`
- **THEN** the returned gap list is non-empty
- **AND** it cites the failing adversarial verdict

### Requirement: All three pipeline skills document Phase 0.5 oracle-derivation

`skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, and `skills/mini-architect-team-pipeline/SKILL.md` SHALL each document the oracle-derivation gate at the canonical insertion point (Phase 0.5 in the main pipeline, the analogous insertion in the bug-fix and mini pipelines).

#### Scenario: architect-team-pipeline has a Phase 0.5 section

- **WHEN** the skill body is parsed
- **THEN** it contains a `## Phase 0.5` heading (or equivalent canonical naming)
- **AND** it dispatches the `oracle-deriver` agent
- **AND** it describes the user-confirmation gate
- **AND** it freezes the spec to `<workspace>/.architect-team/oracle-spec/<change-name>.json`

#### Scenario: bug-fix-pipeline documents the analogous insertion

- **WHEN** the bug-fix pipeline body is parsed
- **THEN** it documents the oracle-derivation step at the relevant phase (B0 or B0.5)
- **AND** it references the same `oracle-deriver` agent

#### Scenario: mini-architect-team-pipeline documents the analogous insertion

- **WHEN** the mini pipeline body is parsed
- **THEN** it documents the oracle-derivation step at the relevant phase (M0 or M0.5)
- **AND** it references the same `oracle-deriver` agent

### Requirement: team-spawning-and-review-gates documents Layer 2 adversarial-pairing

`skills/team-spawning-and-review-gates/SKILL.md` SHALL document the Layer 2 adversarial-pairing rule, the teammate manifest schema bump to v2 (adding `vao_task_shape` and `vao_adversarial_role` fields), and the dispatch concurrency rule (teammate + adversarial-reviewer dispatched in the SAME Phase 2 batch).

#### Scenario: skill names the five task shapes

- **WHEN** the skill body is parsed
- **THEN** it names all five task shapes: `parity-verb`, `backend-dep`, `shared-tree`, `dynamic-value`, `default`

#### Scenario: skill documents the manifest v2 schema bump

- **WHEN** the skill body is parsed
- **THEN** it names `vao_task_shape` as a required manifest v2 field
- **AND** it names `vao_adversarial_role` as a required manifest v2 field
- **AND** the manifest schema example JSON shows both fields

### Requirement: common-pipeline-conventions documents Layer 4 run-history shape detection

`skills/common-pipeline-conventions/SKILL.md` SHALL gain a `## Run-history shape detection (v2.0.0)` section documenting the shape-fingerprint format, the `vao detect-shape` tool, the Phase −2 invocation point, the user-confirmation flow, and the schema of the `.architect-team/run-history/` JSON files.

#### Scenario: section exists exactly once

- **WHEN** the skill body is parsed
- **THEN** it contains the `## Run-history shape detection (v2.0.0)` heading exactly once

#### Scenario: section documents the shape-fingerprint fields

- **WHEN** the section is read
- **THEN** it names `requirement_shape.parity_verbs`
- **AND** it names `requirement_shape.oracle_referenced`
- **AND** it names `requirement_shape.layers_touched`
- **AND** it names `requirement_shape.failure_modes_caught`
- **AND** it names `requirement_shape.failure_modes_missed`

#### Scenario: section documents the user-confirmation surface

- **WHEN** the section is read
- **THEN** it describes the orchestrator-emitted confirmation question that fires when a prior run with `verdict: red-escalation` matches the current shape

### Requirement: The pipeline-completion-audit hook enforces VAO verdicts

`hooks/pipeline-completion-audit.py` SHALL be extended so that on Stop (or `--check`) it blocks the run when ANY coverage-map entry is missing a VAO verdict file at `<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json` for each applicable layer.

#### Scenario: audit blocks on missing oracle-match verdict for parity-verb task

- **WHEN** the audit walks a coverage-map entry whose task-shape is `parity-verb` and no `<task-id>-oracle-match.json` verdict file exists
- **THEN** the audit exits with non-zero status
- **AND** the finding names the missing VAO verdict path

#### Scenario: audit allows when all required verdicts exist with positive results

- **WHEN** the audit walks a coverage-map entry and the matching VAO verdict files all exist with positive (`matched: true` / `clean: true`) results
- **THEN** the audit does not surface this entry as a finding

### Requirement: Synthetic-fixture suite asserts each known failure is blocked

`tests/fixtures/vao/` SHALL contain four synthetic-fixture files reproducing the four known failure cases — `scope-narrowing.json`, `git-stash-clobber.json`, `frontend-fake-data.json`, `oracle-structure-mismatch.json` — and `tests/test_verified_agent_output.py` SHALL assert that the v2.0.0 framework detects and blocks each fixture.

#### Scenario: scope-narrowing fixture is blocked at Layer 1

- **WHEN** `tests/fixtures/vao/scope-narrowing.json` is fed through the Layer 1 oracle-derivation flow synthetically
- **THEN** the test asserts the oracle-derivation surfaces the divergence
- **AND** the test asserts the user-confirmation gate fires before Phase 2 dispatch

#### Scenario: git-stash-clobber fixture is blocked at Layer 2/3

- **WHEN** `tests/fixtures/vao/git-stash-clobber.json` (a synthetic teammate tool-call log containing `git stash`) is passed to `verify_baseline_clean`
- **THEN** the tool returns `{clean: false, violations: [...]}`
- **AND** the test asserts the violation record names the `git stash` invocation

#### Scenario: frontend-fake-data fixture is blocked at Layer 2/3

- **WHEN** `tests/fixtures/vao/frontend-fake-data.json` (a synthetic frontend diff with `"John Smith"` in production code) is passed to `verify_no_fake_data` with the oracle spec naming `"John Smith"` as a dynamic value
- **THEN** the tool returns `{clean: false, hits: [...]}`
- **AND** the test asserts the hit record cites the file and line

#### Scenario: oracle-structure-mismatch fixture is blocked at Layer 1/2/3

- **WHEN** `tests/fixtures/vao/oracle-structure-mismatch.json` (a synthetic built-path + frozen oracle spec with divergence) is passed to `verify_oracle_match`
- **THEN** the tool returns `{matched: false, divergences: [...]}`
- **AND** the test asserts each divergence record has `path`, `expected`, `actual`, `severity`

### Requirement: A --no-vao escape hatch is documented

The three pipeline-driving slash commands (`/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`) SHALL accept a `--no-vao` flag that disables Layers 1, 2, 4, 5 (Layer 3 tools remain available for ad-hoc CLI invocation). The flag's trade-off — re-opening the v1.x failure modes the framework structurally prevents — SHALL be documented explicitly in the command body.

#### Scenario: --no-vao flag is documented in each command body

- **WHEN** the command bodies are parsed
- **THEN** each names the `--no-vao` flag
- **AND** each documents the explicit trade-off (the v1.x failure modes re-open)

### Requirement: Structural tests assert the v2.0.0 framework is wired

`tests/test_verified_agent_output.py` SHALL exist with ≥ 40 tests covering: oracle-deriver agent structure (frontmatter + spec-shape vocabulary), adversarial-reviewer agent structure, the four vao_tools functions (positive + negative synthetic-fixture round-trips), Phase 0.5 invocation in each of the 3 pipelines, the manifest v2 schema bump, Layer 4 run-history-shape-detection structural assertions, schema v7 validation positive + negative cases, the `--no-vao` flag presence in each command body.

#### Scenario: test file exists and collects ≥ 40 tests

- **WHEN** `python3 -m pytest tests/test_verified_agent_output.py --collect-only` runs
- **THEN** it collects at least 40 tests (likely more via parametrize over the four tools × shapes × pipelines)
- **AND** every collected test passes

#### Scenario: existing 2056-test baseline still passes

- **WHEN** `python3 -m pytest -q` runs against the v2.0.0 branch
- **THEN** the prior v1.7.0 baseline of 2056 passing + 1 skipped tests remains green
- **AND** the new tests add to the count (target ~2110 + 1 skipped)

### Requirement: Version is bumped to 2.0.0

The plugin's version SHALL be bumped to `2.0.0` consistently across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top-of-CHANGELOG.md, the README banner, the CLAUDE.md overview paragraph, and the CODEBASE_MAP.md / INTEGRATION_MAP.md frontmatter.

#### Scenario: plugin metadata at 2.0.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "2.0.0"`

#### Scenario: CHANGELOG documents the breaking change

- **WHEN** `CHANGELOG.md` is read at the top entry
- **THEN** the v2.0.0 entry is present
- **AND** it documents the review-evidence schema v6 → v7 break
- **AND** it documents the migration path for runs in flight at the upgrade
