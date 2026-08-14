# forcing-gates — delta for optimize-forcing-gates (v3.61.0)

## ADDED Requirements

### Requirement: A release run cannot end its turn while its published count is unbacked

The completion audit SHALL refuse to end the turn of an ACTIVE run that
changed `.claude-plugin/plugin.json` since its baseline while
`changelog_check.py --require-measurements` refuses the published count —
once the CHANGELOG top entry names the manifest version. The arm SHALL stay silent during the authoring window (top entry not
yet naming the manifest version), for non-release runs, and in workspaces that
do not carry the convention. Kill-switch `CT6_RELEASE_BACKING_GATE_DISABLED`.

#### Scenario: aligned, published, unbacked

- **GIVEN** an active run whose diff bumped `.claude-plugin/plugin.json`
- **AND** the CHANGELOG top entry names the bumped version with a suite line
- **AND** no recorded measurement backs that count
- **WHEN** the completion audit runs
- **THEN** the run is blocked, quoting the checker's findings and naming the kill-switch

#### Scenario: the authoring window is never blocked

- **GIVEN** an active run whose diff bumped the manifest
- **AND** the CHANGELOG top entry still names the PREVIOUS version
- **WHEN** the completion audit runs
- **THEN** the arm contributes no violation

#### Scenario: a non-release run is never taxed

- **GIVEN** an active run whose diff did not touch the manifest
- **WHEN** the completion audit runs
- **THEN** the arm contributes no violation

### Requirement: Task deletion is refused while a run is active

`TaskUpdate` with `status: "deleted"` SHALL be refused at PreToolUse while the
payload workspace carries an ACTIVE, non-stale run marker. The decision SHALL
use payload-only evidence (a missing transcript does not disarm it), and
`escalation-pending.md` SHALL NOT stand the arm down. `status: "completed"`
SHALL remain unaffected. Kill-switch `CT6_TASK_DELETE_GATE_DISABLED`, which no
other switch substitutes for.

#### Scenario: deletion during an active run

- **GIVEN** an active, non-stale run marker in the payload's cwd
- **WHEN** `TaskUpdate(status="deleted")` is attempted
- **THEN** the call is refused with a message naming `completed` as the path and the kill-switch

#### Scenario: completion is untouched

- **GIVEN** the same active marker
- **WHEN** `TaskUpdate(status="completed")` is attempted
- **THEN** the call is allowed (subject only to the pre-existing arms)

#### Scenario: no marker, no gate

- **GIVEN** a workspace with no active run marker
- **WHEN** `TaskUpdate(status="deleted")` is attempted
- **THEN** the call is allowed

### Requirement: Measurement artifacts are immutable to agent editing tools

The ground-truth guard SHALL refuse agent `Edit`/`Write`/`NotebookEdit`
targeting any path under a `docs/measurements/` directory, creation included. The
measurement engine's own io writes SHALL be unaffected. The refusal message
SHALL state the Bash residual rather than implying completeness.

#### Scenario: hand-writing an artifact

- **GIVEN** any workspace
- **WHEN** `Write` targets `docs/measurements/<anything>.json`
- **THEN** the call is refused, directing to `scripts/measure/suite_measurement.py`

#### Scenario: ordinary docs are untouched

- **GIVEN** any workspace
- **WHEN** `Write` targets `docs/notes.md` or `src/measurements/data.json`
- **THEN** the call is not refused by this rule
