# live-data-wiring-discipline Specification

## Purpose
TBD - created by archiving change live-data-wiring-discipline. Update Purpose after archive.
## Requirements
### Requirement: common-pipeline-conventions documents the live-data wiring discipline

`skills/common-pipeline-conventions/SKILL.md` SHALL gain a new top-level section `## Live-data wiring discipline (v2.6.0)` as the canonical home of the rules.

#### Scenario: section exists exactly once

- **WHEN** the canonical skill body is parsed
- **THEN** it contains the heading `## Live-data wiring discipline (v2.6.0)` exactly once

#### Scenario: 5 severities are named verbatim

- **WHEN** the section is read
- **THEN** it names `mock-state-residue` as a severity
- **AND** it names `live-response-not-rendered` as a severity
- **AND** it names `mock-fallback-uncovered` as a severity
- **AND** it names `network-not-intercepted` as a severity
- **AND** it names `async-status-not-surfaced` as a severity

#### Scenario: 2-pass verification workflow is documented

- **WHEN** the section is read
- **THEN** it documents the Playwright pass (capture network response + assert rendered value matches + tamper test)
- **AND** it documents the code-side audit (grep diff + touched files for mock-state residue)

#### Scenario: wiring_mandate annotation is documented

- **WHEN** the section is read
- **THEN** it names the `wiring_mandate` annotation
- **AND** it names at least 3 canonical mandate phrases (e.g., "wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend")

#### Scenario: 3-reviewer Phase 5 swarm extension is documented

- **WHEN** the section is read
- **THEN** it references the existing v0.9.19 `interaction-completeness` 3-reviewer pattern AS the swarm mechanism

#### Scenario: async-status surface rule is documented

- **WHEN** the section is read
- **THEN** it documents the rule that backends emitting async states (loading / processing / done / error / empty) require corresponding UI surfaces

### Requirement: verify_live_data_wiring is the 9th Layer 3 tool

`hooks/vao_tools.py` SHALL expose `verify_live_data_wiring(verification_artifact, wiring_mandate, out_path=None) -> dict` as a deterministic verification function AND a `verify-live-data-wiring` CLI subcommand.

#### Scenario: function exists with the right signature

- **WHEN** `hooks/vao_tools.py` is loaded
- **THEN** `verify_live_data_wiring` is a callable
- **AND** the function accepts `verification_artifact`, `wiring_mandate`, and an optional `out_path`

#### Scenario: returns the standard verdict shape

- **WHEN** `verify_live_data_wiring` is invoked
- **THEN** the returned dict has keys `tool`, `valid`, `gaps`, `verdict_at`
- **AND** the `tool` value is `"verify-live-data-wiring"`

#### Scenario: empty inputs trivially pass

- **WHEN** invoked with empty verification artifact AND no wiring mandate
- **THEN** `valid: True`
- **AND** `gaps: []`

#### Scenario: mock-state-residue detected

- **WHEN** the artifact's diff_files contains an added line referencing `from "msw"` OR `setupWorker(` OR `useMockBackend` OR similar mock signature
- **THEN** `valid: False`
- **AND** a gap has `severity: "mock-state-residue"`

#### Scenario: live-response-not-rendered detected

- **WHEN** `playwright_trace_summary.captured_network_requests[]` includes a response with value V AND `ui_text_after_render` does not contain V
- **THEN** a gap has `severity: "live-response-not-rendered"`

#### Scenario: mock-fallback-uncovered detected

- **WHEN** the artifact's diff_files contains a `?? mockData` OR `|| MOCK_DEFAULT` fallback pattern
- **THEN** a gap has `severity: "mock-fallback-uncovered"`

#### Scenario: network-not-intercepted detected

- **WHEN** `wiring_mandate.endpoints[]` includes `/api/documents` AND `playwright_trace_summary.captured_network_requests[]` has no request to `/api/documents`
- **THEN** a gap has `severity: "network-not-intercepted"`

#### Scenario: async-status-not-surfaced detected

- **WHEN** `wiring_mandate.async_states_expected[]` includes `"processing"` AND `playwright_trace_summary.ui_text_after_render` has no element naming the processing state
- **THEN** a gap has `severity: "async-status-not-surfaced"`

#### Scenario: deterministic output

- **WHEN** the function is invoked twice with byte-identical inputs
- **THEN** the JSON output is byte-identical (modulo `verdict_at`)

### Requirement: _MOCK_STATE_SIGNATURES constant lists canonical signatures

`hooks/vao_tools.py` SHALL expose `_MOCK_STATE_SIGNATURES` as a module-level constant containing at least 12 canonical patterns (MSW imports / Mirage / faker / fixture imports / mock flag names / fallback patterns / page.route fulfill in production).

#### Scenario: constant exists and has ≥ 12 signatures

- **WHEN** the `vao_tools` module is imported
- **THEN** `_MOCK_STATE_SIGNATURES` is iterable
- **AND** `len(_MOCK_STATE_SIGNATURES) >= 12`

#### Scenario: signature classes are represented

- **WHEN** the constant is inspected
- **THEN** at least one signature references MSW (`"msw"` substring)
- **AND** at least one references faker (`"faker"` substring)
- **AND** at least one references fixture/mock imports
- **AND** at least one references a mock-flag env var (e.g., `VITE_USE_MOCK`)

### Requirement: interaction-completeness skill extends its 3-reviewer mandate

`skills/interaction-completeness/SKILL.md` SHALL gain a `## Live-data wiring axis (v2.6.0)` sub-section documenting that each of the 3 `interaction-reviewer` agents independently runs the v2.6.0 audit when the slice carries a `wiring_mandate`.

#### Scenario: sub-section exists exactly once

- **WHEN** the skill body is parsed
- **THEN** it contains `## Live-data wiring axis (v2.6.0)` exactly once

#### Scenario: 3-reviewer swarm reference

- **WHEN** the sub-section is read
- **THEN** it references the existing 3-reviewer convergence protocol
- **AND** it documents that each reviewer's `live_data_wiring_findings` block goes into the convergence report

### Requirement: interaction-reviewer agent body documents the live-data wiring audit

`agents/interaction-reviewer.md` SHALL gain a `## Live-data wiring audit (v2.6.0)` section.

#### Scenario: section exists exactly once

- **WHEN** the agent body is parsed
- **THEN** it contains `## Live-data wiring audit (v2.6.0)` exactly once

#### Scenario: per-reviewer audit protocol is documented

- **WHEN** the section is read
- **THEN** it documents the Playwright pass
- **AND** it documents the code-side audit
- **AND** it documents writing to `live_data_wiring_findings` in the convergence report

### Requirement: live-data-mock-residue synthetic fixture exists

`tests/fixtures/vao/live-data-mock-residue.json` SHALL exist as a synthetic verification artifact reproducing the verbatim heirship-app-v3 failure (backend extracted 71 facts + 13 persons; client workspace still mock-wired for documents/facts; never shows extraction status, never fetches live document list, sidebar never surfaces extracted people).

#### Scenario: fixture exists with the failure shape

- **WHEN** the fixture is loaded
- **THEN** it is valid JSON
- **AND** `wiring_mandate.endpoints[]` includes at least 3 endpoints
- **AND** `wiring_mandate.async_states_expected[]` includes a state name
- **AND** the verification artifact's diff or touched-file contents include mock-state signatures

#### Scenario: fires all 5 severities

- **WHEN** `verify_live_data_wiring` is invoked against the fixture
- **THEN** `valid: False`
- **AND** the gap severities include at least 4 distinct values from the 5-severity set

#### Scenario: _corrected_verification_artifact passes

- **WHEN** `verify_live_data_wiring` is invoked against the fixture's `_corrected_verification_artifact`
- **THEN** `valid: True`

### Requirement: Structural tests assert the v2.6.0 framework is wired

`tests/test_vao_live_data_wiring.py` SHALL exist with ≥ 25 tests covering the tool's 5 severities + determinism + CLI + fixture round-trip. `tests/test_live_data_wiring_discipline.py` SHALL exist with ≥ 10 tests covering the canonical section + interaction-completeness extension + interaction-reviewer extension.

#### Scenario: test files collect the expected count

- **WHEN** `python3 -m pytest tests/test_vao_live_data_wiring.py tests/test_live_data_wiring_discipline.py --collect-only` runs
- **THEN** the total collected count is ≥ 35

#### Scenario: existing 2514-test baseline still passes

- **WHEN** `python3 -m pytest -q` runs against the v2.6.0 branch
- **THEN** the prior v2.5.0 baseline of 2514 passing + 1 skipped tests remains green
- **AND** the new tests add to the count

### Requirement: Version is bumped to 2.6.0

The plugin's version SHALL be bumped to `2.6.0` consistently across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top-of-CHANGELOG.md, the README banner, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 2.6.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "2.6.0"`

#### Scenario: CHANGELOG documents the additive release

- **WHEN** `CHANGELOG.md` is read at the top entry
- **THEN** the v2.6.0 entry is present
- **AND** it names the 5 severities
- **AND** it confirms backwards compatibility

