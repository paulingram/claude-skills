# spec-currency-mid-run

## ADDED Requirements

### Requirement: A spec fingerprint helper exists
A stdlib helper (`hooks/spec_fingerprint.py`) SHALL compute a stable SHA-256 fingerprint over the sorted relative-path + content set of the active OpenSpec change directory (`openspec/changes/<active-slug>/`), returning identical values for identical content regardless of platform path separators, and a distinct value for any content change.

#### Scenario: Fingerprint is content-stable
- **WHEN** the fingerprint is computed twice over an unchanged change directory
- **THEN** the two values are identical

#### Scenario: Fingerprint moves on amendment
- **WHEN** any artifact in the change directory is edited
- **THEN** the recomputed fingerprint differs

### Requirement: Teammate manifests are stamped with the briefed spec state
The teammate manifest schema SHALL gain an additive `spec_fingerprint` field, written by the orchestrator at Phase 2 dispatch alongside `baseline_sha`, recording the spec state the teammate was briefed against. Pre-upgrade manifests without the field remain valid.

#### Scenario: Dispatch stamps the fingerprint
- **WHEN** the orchestrator writes a teammate manifest at dispatch during a run with an active OpenSpec change
- **THEN** the manifest carries the current spec fingerprint

### Requirement: The completion audit flags stale-briefed in-flight teammates
`hooks/pipeline-completion-audit.py` SHALL gain an `_audit_spec_currency` arm: for every teammate manifest whose expected work is not all complete, the manifest's `spec_fingerprint` MUST equal the currently computed fingerprint OR a re-brief record MUST exist (a re-brief handoff file plus the manifest's fingerprint updated). A mismatch with no re-brief is a violation naming the stale teammate. The arm SHALL fail-open when no openspec change dir exists or no manifest carries a fingerprint.

#### Scenario: Amended spec with un-rebriefed teammate blocks
- **WHEN** the orchestrator amends proposal.md after dispatch and a teammate manifest still carries the old fingerprint with no re-brief record
- **THEN** the audit reports a violation naming that teammate

#### Scenario: Pre-upgrade runs are fail-open
- **WHEN** no manifest carries a spec_fingerprint field
- **THEN** the arm reports no violation

### Requirement: A spec-drift SR origin kind exists
The SR origin catalog SHALL gain `spec-drift` — used when implementations disagree because the spec they read differed, or when code-vs-spec disagreement is discovered at review. `spec-drift` SRs dispatch a fix team DIRECTLY (the diagnosis — "the spec line changed" — is already complete) and `spec-drift` SHALL NOT be added to `TEST_FAILURE_ORIGINS` (no diagnostic-plan requirement attaches).

#### Scenario: spec-drift SR routes direct
- **WHEN** an SR with origin.kind spec-drift is picked up
- **THEN** the fix team is dispatched without a diagnostic-research-team invocation being required

### Requirement: The mid-run spec-currency discipline is documented
`skills/common-pipeline-conventions/SKILL.md` SHALL gain a spec-currency discipline section, referenced from the team-spawning skill: the orchestrator owns spec currency WHILE agents read it; any amendment to an openspec artifact after Phase 2 dispatch requires the fingerprint update plus a re-brief handoff to every teammate whose scope the amendment touches; where code and spec disagree at review time, the code wins and the spec is amended in the same phase — never "the readers misread."

#### Scenario: Discipline text present and cross-referenced
- **WHEN** the conventions skill and team-spawning skill are read
- **THEN** the spec-currency discipline exists with the re-brief obligation and the code-wins rule, and team-spawning references it
