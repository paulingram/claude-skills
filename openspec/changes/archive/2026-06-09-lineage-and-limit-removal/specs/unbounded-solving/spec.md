## ADDED Requirements

### Requirement: No global iteration ceiling

The pipeline SHALL NOT enforce a global dev-loop iteration ceiling. `hooks/pipeline-completion-audit.py` SHALL contain no `ITERATION_CEILING` constant and no `_audit_iteration_ceiling` check, and an arbitrarily large `dev_loop_iterations` SHALL NOT cause the audit to report a violation.

#### Scenario: a high iteration count does not block

- **WHEN** a workspace's `intake-state.json` has `dev_loop_iterations` set to a large value (e.g. 999)
- **THEN** the completion audit reports no iteration-ceiling violation
- **AND** no `ITERATION_CEILING` symbol exists in the audit module

### Requirement: Completion checks are a non-halting worklist

The completion-audit's completeness checks (open SRs, editability, test-completeness, visual-fidelity, master-review, documentation-currency, bug-fix-testing) SHALL still run and enumerate remaining work, but SHALL be framed as the worklist the loop closes until empty — they exist to drive continued solving until success, never to permit a stop on incomplete work.

#### Scenario: incomplete work keeps the loop going

- **WHEN** the audit finds remaining work (e.g. an open SR)
- **THEN** the remaining items are reported as the worklist to close
- **AND** the canonical `## Unbounded solving discipline` documents that the run continues until the worklist is empty (success)

### Requirement: Oscillation continues with a new angle

Recurrence detection SHALL be retained, but on a recurring solution-requirement the pipeline SHALL NOT abort/escalate-and-stop; it SHALL continue from a different angle (re-route through diagnostic-research, broaden scope, or an alternative strategy) and surface the recurrence without halting.

#### Scenario: a recurring SR does not stop the run

- **WHEN** the same requirement recurs
- **THEN** the pipeline continues with a different approach and surfaces the recurrence
- **AND** no rule instructs the run to stop/escalate-and-halt on oscillation

### Requirement: Sub-loops converge rather than cap

Bounded sub-loops that previously gave up at a fixed count (diagnostic-research 3-cycle, editability/interaction 3-pass, expensive-verification 2-cycle-stop, mapping ralph `--max-iterations N`) SHALL loop until converged / until the completion-promise fires, with no numeric give-up.

#### Scenario: a review loop runs until zero gaps

- **WHEN** a review or diagnostic loop has not yet converged
- **THEN** it continues iterating until convergence rather than stopping at a fixed pass count

### Requirement: Canonical unbounded-solving discipline

`common-pipeline-conventions/SKILL.md` SHALL carry a canonical `## Unbounded solving discipline` section stating there is no iteration ceiling, the dev-loop runs until success, the pipeline never aborts on iteration count or oscillation and never stops on incomplete work, and a genuinely-external blocker is surfaced-and-kept-working rather than halted. The 3 pipeline bodies + `ux-test-builder` SHALL reference it and SHALL NOT retain ceiling / oscillation-abort / exhaustion-stop prose.

#### Scenario: the discipline is canonical and referenced

- **WHEN** `common-pipeline-conventions/SKILL.md` is read
- **THEN** it contains `## Unbounded solving discipline`
- **AND** the architect-team-pipeline, bug-fix-pipeline, mini-architect-team-pipeline, and ux-test-builder bodies no longer document a numeric iteration ceiling as a halt condition
