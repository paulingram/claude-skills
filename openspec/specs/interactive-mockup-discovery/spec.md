# interactive-mockup-discovery Specification

## Purpose
TBD - created by archiving change interactive-mockup-discovery. Update Purpose after archive.
## Requirements
### Requirement: A canonical interactive-mockup-discovery skill exists

`skills/interactive-mockup-discovery/SKILL.md` SHALL exist as the canonical home of the framework's interactive-mockup oracle handling, documenting the two-pass mechanism (observation + intent inference), the interactions[] schema, the action_kind taxonomy, the interaction_intent_gap surfacing protocol, and the verify-interactions-honored verdict contract.

#### Scenario: skill file exists with valid frontmatter

- **WHEN** `skills/interactive-mockup-discovery/SKILL.md` is loaded
- **THEN** it has YAML frontmatter with `name: interactive-mockup-discovery`
- **AND** the frontmatter sets a non-empty `description`

#### Scenario: skill names the two passes

- **WHEN** the skill body is parsed
- **THEN** it explicitly names Pass 1 as the observation pass
- **AND** it names Pass 2 as the intent-inference pass

#### Scenario: skill names all seven action_kind values

- **WHEN** the skill body is parsed
- **THEN** it names `navigate` as an `action_kind` value
- **AND** it names `open-drawer` as an `action_kind` value
- **AND** it names `open-modal` as an `action_kind` value
- **AND** it names `submit` as an `action_kind` value
- **AND** it names `input-text` as an `action_kind` value
- **AND** it names `reveal` as an `action_kind` value
- **AND** it names `no-op` as an `action_kind` value

### Requirement: An interaction-observer agent exists

`agents/interaction-observer.md` SHALL exist as a new opus agent dispatched by `oracle-deriver` when `spec_shape` detects an interactive HTML mockup. The agent observes the mockup's actual runtime behavior — element-by-element click/focus/input simulation — and writes the resulting interactions[] array to the oracle spec.

#### Scenario: agent file exists with valid frontmatter

- **WHEN** `agents/interaction-observer.md` is loaded
- **THEN** it has YAML frontmatter with `name: interaction-observer`
- **AND** the frontmatter sets `model: opus`
- **AND** the frontmatter sets a non-empty `description`
- **AND** the frontmatter sets a `color`

#### Scenario: agent carries the uniform discipline sections

- **WHEN** the agent body is parsed
- **THEN** it contains a `## Operating context` section
- **AND** it contains a `## Forbidden git operations` section
- **AND** it contains a `## Checkpoint discipline` section

#### Scenario: agent documents the four-step observe protocol

- **WHEN** the agent body is parsed
- **THEN** it documents running the mockup
- **AND** it documents enumerating every interactive element
- **AND** it documents simulating each interaction
- **AND** it documents recording the observed effect

### Requirement: oracle-deriver recognizes interactive-mockup as a spec_shape

`agents/oracle-deriver.md` SHALL extend its spec_shape vocabulary to name `interactive-mockup` as a 6th category alongside the existing five (component-tree, design-map, api-contract, data-model, hybrid).

#### Scenario: oracle-deriver names the new spec_shape

- **WHEN** the oracle-deriver agent body is parsed
- **THEN** it names `interactive-mockup` as a `spec_shape` value

#### Scenario: oracle-deriver documents the dispatch contract

- **WHEN** the oracle-deriver agent body is parsed
- **THEN** it documents dispatching the `interaction-observer` agent when `spec_shape: interactive-mockup` triggers

### Requirement: interaction-intuiter gains intent-inference mode

`agents/interaction-intuiter.md` SHALL document a new INTENT-INFERENCE mode that reads the oracle spec's interactions[] array, compares semantic_label vs observed_effect, and emits interaction_intent_gap entries for the Phase −1D bulk-verify gate when mismatches are detected.

#### Scenario: agent body documents the new mode

- **WHEN** the interaction-intuiter agent body is parsed
- **THEN** it contains a section naming "INTENT-INFERENCE" (or "intent inference") as a documented mode
- **AND** it names `interaction_intent_gap` as the entry kind it emits

### Requirement: verify-interactions-honored is the 6th Layer 3 tool

`hooks/vao_tools.py` SHALL expose `verify_interactions_honored(built_components, oracle_spec) -> dict` as a deterministic verification function AND a `verify-interactions-honored` CLI subcommand. The tool walks every interactions[] entry whose `resolved_intent` is populated (the user confirmed an intent gap) OR whose `action_kind` is non-trivial, and asserts the built code's handler matches the resolved intent.

#### Scenario: function exists with the right signature

- **WHEN** `hooks/vao_tools.py` is loaded
- **THEN** `verify_interactions_honored` is a callable
- **AND** the function accepts `built_components`, `oracle_spec`, and an optional `out_path`

#### Scenario: function returns the verdict shape

- **WHEN** `verify_interactions_honored` is invoked
- **THEN** the returned dict has the keys `tool`, `matched`, `gaps`, `honored_count`, `total_count`, `verdict_at`
- **AND** the `tool` value is `"verify-interactions-honored"`

#### Scenario: empty oracle interactions trivially passes

- **WHEN** `verify_interactions_honored` is invoked with an oracle spec carrying no interactions[]
- **THEN** the verdict has `matched: True`
- **AND** `gaps` is empty

#### Scenario: resolved-intent mismatch is a gap

- **WHEN** `verify_interactions_honored` is invoked with an oracle spec where one entry has `resolved_intent: navigate:/sign-in` AND the built code's matching handler navigates to `/dashboard`
- **THEN** the verdict has `matched: False`
- **AND** `gaps` contains an entry naming the trigger_selector + expected_intent + actual_handler

#### Scenario: CLI subcommand exposes the tool

- **WHEN** `python3 hooks/vao_tools.py verify-interactions-honored --components C --oracle O --out OUT` runs against an oracle spec with empty interactions[]
- **THEN** the process exits 0

### Requirement: Schema v7 includes optional interactions_honored_review

`hooks/review_evidence_schema.py` schema v7 SHALL define `interactions_honored_review` as an OPTIONAL evidence field — required only when the run's oracle spec carries a non-empty interactions[] array, n/a otherwise. The validation logic accepts the same `pass | n/a | fail` string-shape OR `{verdict, verdict_path}` dict-shape as the other v7 fields.

#### Scenario: optional field is recognized by the validator

- **WHEN** an evidence file omits `interactions_honored_review` (n/a — no interactive-mockup oracle in scope)
- **THEN** `validate_evidence` does NOT report a gap for that field

#### Scenario: present field validates pass/n/a/fail

- **WHEN** an evidence file carries `interactions_honored_review: "pass"`
- **THEN** `validate_evidence` does not report a gap on that field

#### Scenario: present field blocks on fail

- **WHEN** an evidence file carries `interactions_honored_review: "fail"`
- **THEN** `validate_evidence` reports a gap citing the field

#### Scenario: present field accepts the dict-shape with verdict_path

- **WHEN** an evidence file carries `interactions_honored_review: {verdict: "pass", verdict_path: ".architect-team/vao-verdicts/T-1-interactions-honored.json"}`
- **THEN** `validate_evidence` does not report a gap on that field

### Requirement: interactive-mockup-logout-misroute synthetic fixture exists

`tests/fixtures/vao/interactive-mockup-logout-misroute.json` SHALL exist as the canonical synthetic fixture reproducing the heirship-style "mockup lies" case: a Logout button whose observed_effect is `navigate to /dashboard`, the intent inference flags the mismatch, the user-resolved intent is `navigate to /sign-in`, and a built tree that still routes to `/dashboard` produces a verify-interactions-honored verdict of `matched: false`.

#### Scenario: fixture exists with the failure shape

- **WHEN** `tests/fixtures/vao/interactive-mockup-logout-misroute.json` is loaded
- **THEN** it is valid JSON
- **AND** it contains an `oracle_spec.interactions[]` array
- **AND** at least one entry has `semantic_label: "Logout"`, `observed_effect` referencing `/dashboard`, and `resolved_intent` referencing `/sign-in`

#### Scenario: tool catches the fixture

- **WHEN** `verify_interactions_honored` is invoked against the fixture's `built_components` + `oracle_spec`
- **THEN** the verdict has `matched: False`
- **AND** at least one gap names the Logout trigger_selector

### Requirement: Version is bumped to 2.1.0

The plugin's version SHALL be bumped to `2.1.0` consistently across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top-of-CHANGELOG.md, the README banner, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 2.1.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "2.1.0"`

#### Scenario: CHANGELOG documents the additive release

- **WHEN** `CHANGELOG.md` is read at the top entry
- **THEN** the v2.1.0 entry is present
- **AND** it names the two-pass mechanism (observation + intent inference)
- **AND** it confirms backwards compatibility (the new schema field is optional)

### Requirement: Structural tests assert the v2.1.0 framework is wired

`tests/test_vao_interactions_honored.py` SHALL exist with ≥ 20 tests covering the 6th tool's positive + negative + determinism contracts and the synthetic fixture round-trip. `tests/test_interactive_mockup_discovery.py` SHALL exist with ≥ 20 tests covering the skill body, agent frontmatter, and oracle-deriver / interaction-intuiter extensions.

#### Scenario: tool-test file exists with ≥ 20 tests

- **WHEN** `python3 -m pytest tests/test_vao_interactions_honored.py --collect-only` runs
- **THEN** it collects at least 20 tests
- **AND** every collected test passes

#### Scenario: skill-test file exists with ≥ 20 tests

- **WHEN** `python3 -m pytest tests/test_interactive_mockup_discovery.py --collect-only` runs
- **THEN** it collects at least 20 tests
- **AND** every collected test passes

#### Scenario: existing 2255-test baseline still passes

- **WHEN** `python3 -m pytest -q` runs against the v2.1.0 branch
- **THEN** the prior v2.0.0 baseline of 2255 passing + 1 skipped tests remains green
- **AND** the new tests add to the count (target ~2300 + 1 skipped)

