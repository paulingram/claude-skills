# Spec: external-state-assertion-discipline capability

## ADDED Requirements

### Requirement: common-pipeline-conventions documents External-state assertion (v2.4.0)

`skills/common-pipeline-conventions/SKILL.md` `## Verified-live discipline (v2.2.0)` section SHALL gain a new sub-section `### External-state assertion (v2.4.0)` documenting the rule that any feature interacting with an external system MUST assert against the external system's own observable downstream state, not against any internal proxy field.

#### Scenario: sub-section exists exactly once

- **WHEN** the canonical skill body is parsed
- **THEN** it contains the heading `### External-state assertion (v2.4.0)` exactly once

#### Scenario: 6 canonical external-system kinds are named

- **WHEN** the sub-section is read
- **THEN** it names `email` as a canonical external-system kind
- **AND** it names `payment` as a canonical external-system kind
- **AND** it names `push` as a canonical external-system kind
- **AND** it names `webhook-outbound` as a canonical external-system kind
- **AND** it names `oauth` as a canonical external-system kind
- **AND** it names `blob-storage` as a canonical external-system kind

#### Scenario: forbidden anti-patterns are named

- **WHEN** the sub-section is read
- **THEN** it forbids asserting against a backend response body field
- **AND** it forbids asserting against the third-party API's acknowledgement of receipt
- **AND** it forbids asserting against UI display text claiming success

### Requirement: common-pipeline-conventions documents Evidence-artifact citation (v2.4.0)

`skills/common-pipeline-conventions/SKILL.md` `## Verified-live discipline (v2.2.0)` section SHALL gain a new sub-section `### Evidence-artifact citation (v2.4.0)` documenting the rule that every verified-live claim MUST include an `evidence_artifact_path` pointing to a concrete on-disk artifact.

#### Scenario: sub-section exists exactly once

- **WHEN** the canonical skill body is parsed
- **THEN** it contains the heading `### Evidence-artifact citation (v2.4.0)` exactly once

#### Scenario: accepted artifact formats are named

- **WHEN** the sub-section is read
- **THEN** it names Playwright trace ZIP as an accepted artifact format
- **AND** it names network log JSON / HAR as an accepted artifact format
- **AND** it names screenshot as an accepted artifact format
- **AND** it names external-API response dump JSON as an accepted artifact format

#### Scenario: structural requirements are named

- **WHEN** the sub-section is read
- **THEN** it requires the path to exist on disk
- **AND** it requires the file to be greater than 0 bytes
- **AND** it requires the artifact to be a file (not a directory)

### Requirement: verify_live_verification_claim detects external-state-not-asserted

`hooks/vao_tools.py::verify_live_verification_claim` SHALL detect verification artifacts whose `feature_kind` is in the documented external-system list AND whose `external_state_assertion` block is missing OR whose `passes` field is not `true`, and emit a gap entry with severity `external-state-not-asserted`.

#### Scenario: email feature without external_state_assertion is caught

- **WHEN** `verify_live_verification_claim` is invoked against an artifact where `feature_kind == "email"` AND `external_state_assertion` is missing
- **THEN** the returned verdict has `valid: False`
- **AND** at least one gap has `severity: "external-state-not-asserted"`

#### Scenario: payment feature with external_state_assertion.passes=false is caught

- **WHEN** the artifact's `feature_kind == "payment"` AND `external_state_assertion.passes == false`
- **THEN** the returned verdict has `valid: False`
- **AND** at least one gap has `severity: "external-state-not-asserted"`

#### Scenario: email feature with valid external_state_assertion passes

- **WHEN** the artifact's `feature_kind == "email"` AND `external_state_assertion.passes == true` AND `external_state_assertion.observed_state.event == "delivered"`
- **THEN** no `external-state-not-asserted` severity fires

#### Scenario: non-external-system features are not affected

- **WHEN** the artifact carries no `feature_kind` OR `feature_kind` is a non-external value
- **THEN** no `external-state-not-asserted` severity fires regardless of `external_state_assertion` presence

#### Scenario: assertion against a forbidden proxy field fires the severity

- **WHEN** `feature_kind == "email"` AND the artifact's `assertions[]` array references the string `"email_dispatch_status"` AND `external_state_assertion` is missing
- **THEN** at least one gap has `severity: "external-state-not-asserted"`
- **AND** the gap's `evidence` field names the forbidden proxy substring

### Requirement: verify_live_verification_claim detects missing-evidence-artifact

`hooks/vao_tools.py::verify_live_verification_claim` SHALL detect verification artifacts whose `evidence_artifact_path` is missing, points to a nonexistent path, points to a directory, or points to a zero-byte file, and emit a gap entry with severity `missing-evidence-artifact`.

#### Scenario: missing evidence_artifact_path field is caught

- **WHEN** `verify_live_verification_claim` is invoked against an artifact whose `evidence_artifact_path` is missing
- **THEN** the returned verdict has `valid: False`
- **AND** at least one gap has `severity: "missing-evidence-artifact"`

#### Scenario: nonexistent path is caught

- **WHEN** the artifact's `evidence_artifact_path` is a string pointing to a file that does not exist on disk
- **THEN** the returned verdict has `valid: False`
- **AND** the gap's `evidence` field references "does not exist" or similar

#### Scenario: zero-byte file is caught

- **WHEN** the artifact's `evidence_artifact_path` resolves to a file but the file is 0 bytes
- **THEN** the returned verdict has `valid: False`
- **AND** the gap's `evidence` references "empty" or "0 bytes"

#### Scenario: valid evidence artifact passes

- **WHEN** the artifact's `evidence_artifact_path` resolves to an existing file > 0 bytes
- **THEN** no `missing-evidence-artifact` severity fires

### Requirement: external-state-not-asserted-email-invite synthetic fixture exists

`tests/fixtures/vao/external-state-not-asserted-email-invite.json` SHALL exist as a synthetic verification artifact reproducing the verbatim heirship Failure B (assertion was `email_dispatch_status === "sent"` on backend response; should have been SendGrid Activity API event=delivered).

#### Scenario: fixture exists with the failure shape

- **WHEN** the fixture is loaded
- **THEN** it is valid JSON
- **AND** `verification_artifact.feature_kind == "email"`
- **AND** `verification_artifact.external_state_assertion` is missing OR `passes != true`
- **AND** `verification_artifact.assertions[]` references the forbidden proxy field `email_dispatch_status`

#### Scenario: fixture is caught by the tool

- **WHEN** `verify_live_verification_claim` is invoked against the fixture
- **THEN** the verdict has `valid: False`
- **AND** at least one gap has `severity: "external-state-not-asserted"`

#### Scenario: fixture's _corrected_verification_artifact passes

- **WHEN** `verify_live_verification_claim` is invoked against the fixture's `_corrected_verification_artifact`
- **THEN** the verdict has `valid: True`

### Requirement: fabricated-verification-table synthetic fixture exists

`tests/fixtures/vao/fabricated-verification-table.json` SHALL exist as a synthetic verification artifact reproducing the verbatim heirship Failure A (3 ✅ "sent" results claimed but no Playwright trace captured them; no `evidence_artifact_path` cited).

#### Scenario: fixture exists with the failure shape

- **WHEN** the fixture is loaded
- **THEN** `verification_artifact.evidence_artifact_path` is missing OR points to a nonexistent path

#### Scenario: fixture is caught by the tool

- **WHEN** `verify_live_verification_claim` is invoked against the fixture
- **THEN** the verdict has `valid: False`
- **AND** at least one gap has `severity: "missing-evidence-artifact"`

### Requirement: Structural tests assert the v2.4.0 framework is wired

`tests/test_vao_live_verification_claim.py` SHALL gain ≥ 20 new tests covering the 2 new severities + the 2 fixture round-trips + the per-feature-kind forbidden-proxy-field detection. `tests/test_verified_live_discipline.py` SHALL gain ≥ 10 new tests asserting the 2 new sub-sections + the canonical external-system table + the forbidden anti-patterns.

#### Scenario: test files collect the new tests

- **WHEN** `python3 -m pytest tests/test_vao_live_verification_claim.py tests/test_verified_live_discipline.py --collect-only` runs
- **THEN** the total collected count is ≥ 30 higher than the v2.3.0 baseline of 76

#### Scenario: existing 2432-test baseline still passes

- **WHEN** `python3 -m pytest -q` runs against the v2.4.0 branch
- **THEN** the prior v2.3.0 baseline of 2432 passing + 1 skipped tests remains green
- **AND** the new tests add to the count (target ~2470 + 1 skipped)

### Requirement: Version is bumped to 2.4.0

The plugin's version SHALL be bumped to `2.4.0` consistently across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top-of-CHANGELOG.md, the README banner, and the CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 2.4.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "2.4.0"`

#### Scenario: CHANGELOG documents the additive release

- **WHEN** `CHANGELOG.md` is read at the top entry
- **THEN** the v2.4.0 entry is present
- **AND** it names the 2 new severities
- **AND** it names the 2 new sub-sections
- **AND** it confirms backwards compatibility
