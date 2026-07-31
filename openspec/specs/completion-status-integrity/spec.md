# completion-status-integrity Specification

## Purpose
TBD - created by archiving change harden-evidence-integrity. Update Purpose after archive.
## Requirements
### Requirement: Unmanifested-task completion is blocked during an active run
`hooks/review-gate-task.py` SHALL block a `TaskUpdate(completed)` (subagents shape) or `TaskCompleted` (teams shape) for a task mentioned in NO teammate manifest — not in any manifest's `expected_review_evidence`, `shared_task_id`, or `task_ids` — WHEN ALL of: (a) `.architect-team/active-run.json` reports an active CT6 run, (b) the completing session is the RUN's recorded session (in the default Agent-Teams dispatch mode the Lead and every teammate share one session id, so this test scopes the gate to the run's actors rather than distinguishing among them; REGISTRATION, not actor identity, is the discriminator — the same session basis the completion audit uses), and (c) the kill-switch env var is not set. The block message SHALL name the remediation: register the task in a teammate manifest (`expected_review_evidence`) or complete it through the evidence flow. Registration SHALL NOT weaken the evidence gate: evidence enforcement remains scoped by `expected_review_evidence` exactly as before.

#### Scenario: Unregistered task completion mid-run is blocked
- **WHEN** the active run's session flips a task to completed and no manifest mentions that task id anywhere
- **THEN** the hook blocks (exit 2) with the manifest-registration remediation in its message

#### Scenario: Registered board task completes without weakening evidence
- **WHEN** a task id recorded as a manifest's `shared_task_id` (or in its `task_ids`) is flipped to completed by the run's session
- **THEN** the gate stands down, and the evidence requirement for ids in `expected_review_evidence` remains enforced unchanged

#### Scenario: Manifested task with valid evidence completes
- **WHEN** a task listed in a manifest completes with a valid v7 evidence file including a passing independent review
- **THEN** the hook allows the completion exactly as before

### Requirement: The gate is scoped fail-open outside active CT6 runs
The unmanifested-task gate SHALL NOT fire when there is no active run marker, when the marker's session is not the completing session, when the task id is mentioned in any teammate manifest (registration stand-down), when the task id cannot be extracted, or when the kill-switch env var (`CT6_TASK_GATE_DISABLED` or equivalent documented name) is set — preserving the existing scoping rationale that foreign workflows and user task tracking are left alone.

#### Scenario: No active run
- **WHEN** a task completes and no active-run marker exists
- **THEN** the hook applies only the pre-existing manifest-scoped behavior (unmanifested tasks allowed)

#### Scenario: Kill-switch honored
- **WHEN** the kill-switch env var is set and an active run's orchestrator completes an unmanifested task
- **THEN** the hook allows it

### Requirement: The run marker records the run session for the gate's session test
The run-continuity marker (`.architect-team/active-run.json`) SHALL carry the run's session identifier while a run is active, populated at engagement (resolved from an explicit argument or the harness environment, with `CLAUDE_CODE_SESSION_ID` the primary documented name), so the completion-status gate and the completion audit share one session-matching basis.

#### Scenario: Marker carries session id during a run
- **WHEN** a pipeline run is engaged and the marker is read
- **THEN** its session identifier field is non-null and matches the run's session

