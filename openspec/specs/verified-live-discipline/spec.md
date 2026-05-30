# verified-live-discipline Specification

## Purpose
TBD - created by archiving change verified-live-discipline. Update Purpose after archive.
## Requirements
### Requirement: common-pipeline-conventions documents the verified-live discipline

`skills/common-pipeline-conventions/SKILL.md` SHALL contain a new `## Verified-live discipline (v2.2.0)` section as the canonical home of the rules.

#### Scenario: section exists exactly once

- **WHEN** the skill body is parsed
- **THEN** it contains the `## Verified-live discipline (v2.2.0)` heading exactly once

#### Scenario: section names the 3 failure modes verbatim

- **WHEN** the section is read
- **THEN** it names `gesture substitution` (or `gesture-substitution`) as a failure mode
- **AND** it names `self-verification loop` (or `self-verification-loop`) as a failure mode
- **AND** it names `prefill masking` (or `prefill-masking`) as a failure mode

#### Scenario: section names the 4 required attestations

- **WHEN** the section is read
- **THEN** it names "deployed-URL invocation" as a required attestation
- **AND** it names "literal user gesture" as a required attestation
- **AND** it names "semantic behavior assertion" as a required attestation
- **AND** it names "captured screenshot" as a required attestation

#### Scenario: section forbids the 3 anti-patterns

- **WHEN** the section is read
- **THEN** it forbids corner-clicks / empty-region-clicks instead of user-gesture targets
- **AND** it forbids self-authored unit tests asserting own fix
- **AND** it forbids tests on pre-populated demo state that masks the bug-exposable state

### Requirement: verify_live_verification_claim is the 7th Layer 3 tool

`hooks/vao_tools.py` SHALL expose `verify_live_verification_claim(verification_artifact, bug_description, out_path=None) -> dict` as a deterministic verification function AND a `verify-live-verification-claim` CLI subcommand.

#### Scenario: function exists with the right signature

- **WHEN** `hooks/vao_tools.py` is loaded
- **THEN** `verify_live_verification_claim` is a callable
- **AND** the function accepts `verification_artifact`, `bug_description`, and an optional `out_path`

#### Scenario: function returns the verdict shape

- **WHEN** `verify_live_verification_claim` is invoked
- **THEN** the returned dict has the keys `tool`, `valid`, `gaps`, `verdict_at`
- **AND** the `tool` value is `"verify-live-verification-claim"`

#### Scenario: empty artifact + empty bug description trivially passes

- **WHEN** `verify_live_verification_claim` is invoked with an empty artifact and empty bug description
- **THEN** the verdict has `valid: True`
- **AND** `gaps` is empty

#### Scenario: gesture-substitution is detected

- **WHEN** `verify_live_verification_claim` is invoked against an artifact whose `click_targets[]` includes coordinate `(8, 8)` or `(0, 0)` AND the bug description names a dropdown / menu / popup gesture
- **THEN** the verdict has `valid: False`
- **AND** `gaps` contains an entry with `severity: "gesture-substitution"`

#### Scenario: self-verification-loop is detected

- **WHEN** `verify_live_verification_claim` is invoked against an artifact whose test source was created within the current fix session AND whose assertion contains a substring from the fix's git diff
- **THEN** the verdict has `valid: False`
- **AND** `gaps` contains an entry with `severity: "self-verification-loop"`

#### Scenario: prefill-masking is detected

- **WHEN** `verify_live_verification_claim` is invoked against an artifact whose setup loads a pre-populated demo matter AND the bug requires a blank/empty state to manifest
- **THEN** the verdict has `valid: False`
- **AND** `gaps` contains an entry with `severity: "prefill-masking"`

#### Scenario: missing-screenshot is detected

- **WHEN** `verify_live_verification_claim` is invoked against an artifact whose `screenshot_path` is null
- **THEN** the verdict has `valid: False`
- **AND** `gaps` contains an entry with `severity: "missing-screenshot"`

#### Scenario: missing-deployed-url is detected

- **WHEN** `verify_live_verification_claim` is invoked against an artifact whose `target_url` is missing or points to localhost
- **THEN** the verdict has `valid: False`
- **AND** `gaps` contains an entry with `severity: "missing-deployed-url"`

#### Scenario: missing-semantic-assertion is detected

- **WHEN** `verify_live_verification_claim` is invoked against an artifact whose `assertions[]` is empty
- **THEN** the verdict has `valid: False`
- **AND** `gaps` contains an entry with `severity: "missing-semantic-assertion"`

#### Scenario: CLI subcommand exposes the tool

- **WHEN** `python3 hooks/vao_tools.py verify-live-verification-claim --artifact A --bug B --out OUT` runs against an empty artifact
- **THEN** the process exits 0

#### Scenario: deterministic output

- **WHEN** `verify_live_verification_claim` is invoked twice with the same inputs
- **THEN** both invocations produce byte-identical JSON output (modulo `verdict_at`)

### Requirement: qa-replayer gains Verification-Claim Audit

`agents/qa-replayer.md` SHALL gain a `## Verification-Claim Audit (v2.2.0)` section documenting the 3 self-checks (gesture / independence / state) and the new `bug-resolved-verification-suspect` verdict.

#### Scenario: section exists

- **WHEN** the agent body is parsed
- **THEN** it contains the `## Verification-Claim Audit (v2.2.0)` heading

#### Scenario: section names the 3 self-checks

- **WHEN** the section is read
- **THEN** it documents the gesture audit
- **AND** it documents the independence audit
- **AND** it documents the state audit

#### Scenario: new verdict is documented

- **WHEN** the agent body is parsed
- **THEN** it names `bug-resolved-verification-suspect` as a verdict value

### Requirement: bug-fix-pipeline Phase B6 wires the verdict through the tool

`skills/bug-fix-pipeline/SKILL.md` Phase B6 SHALL wire the qa-replayer's verdict through `verify-live-verification-claim` before `bug-resolved` is accepted.

#### Scenario: Phase B6 documents the tool invocation

- **WHEN** the bug-fix-pipeline skill body is parsed
- **THEN** Phase B6 documents the `verify-live-verification-claim` invocation after the qa-replayer's verdict

#### Scenario: Phase B6 documents the new verdict's routing

- **WHEN** the bug-fix-pipeline skill body is parsed
- **THEN** it names `bug-resolved-verification-suspect` and documents the routing for each severity

### Requirement: Schema v7 includes optional live_verification_review

`hooks/review_evidence_schema.py` schema v7 SHALL define `live_verification_review` as an OPTIONAL evidence field (added to `OPTIONAL_VAO_FIELDS`). Required ONLY when the evidence claims "verified live"; n/a otherwise.

#### Scenario: VALID_LIVE_VERIFICATION_VALUES exists

- **WHEN** the schema module is inspected
- **THEN** `VALID_LIVE_VERIFICATION_VALUES == {"pass", "n/a", "fail"}`

#### Scenario: field is in OPTIONAL_VAO_FIELDS

- **WHEN** the schema module is inspected
- **THEN** `"live_verification_review"` is in `OPTIONAL_VAO_FIELDS`

#### Scenario: field is NOT in REQUIRED_EVIDENCE_FIELDS

- **WHEN** the schema module is inspected
- **THEN** `"live_verification_review"` is NOT in `REQUIRED_EVIDENCE_FIELDS`
- **AND** the REQUIRED set still has 17 fields (unchanged from v2.0.0/v2.1.0)

#### Scenario: absent field does not block

- **WHEN** an evidence file omits `live_verification_review`
- **THEN** `validate_evidence` does NOT report a gap for that field

#### Scenario: pass field does not block

- **WHEN** an evidence file carries `live_verification_review: "pass"`
- **THEN** `validate_evidence` does not report a gap on that field

#### Scenario: fail field blocks

- **WHEN** an evidence file carries `live_verification_review: "fail"`
- **THEN** `validate_evidence` reports a gap citing the field

#### Scenario: dict-shape with verdict_path passes

- **WHEN** an evidence file carries `live_verification_review: {verdict: "pass", verdict_path: ".architect-team/vao-verdicts/T-1-live-verification.json"}`
- **THEN** `validate_evidence` does not report a gap on that field

### Requirement: 3 canonical synthetic fixtures exist

`tests/fixtures/vao/` SHALL contain three synthetic-fixture files reproducing the three failure modes. Each is a positive case the `verify_live_verification_claim` tool MUST catch.

#### Scenario: gesture-substitution-corner-click.json exists with the failure shape

- **WHEN** `tests/fixtures/vao/gesture-substitution-corner-click.json` is loaded
- **THEN** it is valid JSON
- **AND** it contains a `verification_artifact.click_targets[]` whose entries include coordinate `(8, 8)` or similar empty-region pixels
- **AND** the bug description references a gesture (dropdown / menu / popup close behavior)

#### Scenario: self-authored-unit-test-loop.json exists with the failure shape

- **WHEN** `tests/fixtures/vao/self-authored-unit-test-loop.json` is loaded
- **THEN** it contains a `verification_artifact.test_source_created_at` within the current fix session window
- **AND** the test's assertion references a string also present in the fix's git diff (provided in `verification_artifact.fix_diff_strings[]`)

#### Scenario: prefill-masking-demo-matter.json exists with the failure shape

- **WHEN** `tests/fixtures/vao/prefill-masking-demo-matter.json` is loaded
- **THEN** it contains a `verification_artifact.setup_actions[]` loading the Carter demo matter
- **AND** the bug description requires a blank/empty state to manifest
- **AND** the trace shows a saturated state (`N/N answered`)

### Requirement: Structural tests assert the v2.2.0 framework is wired

`tests/test_vao_live_verification_claim.py` SHALL exist with ≥ 30 tests covering the 7th tool's positive + negative + determinism contracts and the synthetic fixture round-trip. `tests/test_verified_live_discipline.py` SHALL exist with ≥ 20 tests covering the canonical-section assertions, qa-replayer extension, schema field, bug-fix-pipeline B6 wiring.

#### Scenario: tool-test file exists with ≥ 30 tests

- **WHEN** `python3 -m pytest tests/test_vao_live_verification_claim.py --collect-only` runs
- **THEN** it collects at least 30 tests
- **AND** every collected test passes

#### Scenario: discipline-test file exists with ≥ 20 tests

- **WHEN** `python3 -m pytest tests/test_verified_live_discipline.py --collect-only` runs
- **THEN** it collects at least 20 tests
- **AND** every collected test passes

#### Scenario: existing 2318-test baseline still passes

- **WHEN** `python3 -m pytest -q` runs against the v2.2.0 branch
- **THEN** the prior v2.1.0 baseline of 2318 passing + 1 skipped tests remains green
- **AND** the new tests add to the count (target ~2370 + 1 skipped)

### Requirement: Version is bumped to 2.2.0

The plugin's version SHALL be bumped to `2.2.0` consistently across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top-of-CHANGELOG.md, the README banner, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 2.2.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "2.2.0"`

#### Scenario: CHANGELOG documents the additive release

- **WHEN** `CHANGELOG.md` is read at the top entry
- **THEN** the v2.2.0 entry is present
- **AND** it names the 3 failure modes
- **AND** it confirms backwards compatibility

