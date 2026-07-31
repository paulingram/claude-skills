# declared-gates-registry

## ADDED Requirements

### Requirement: A declared-gates registry file contract exists
The run state SHALL include a declared-gates registry at `<workspace>/.architect-team/declared-gates.json`: a JSON array of entries `{gate_id, declaration_text, check_command_or_artifact, declared_at}` appended whenever the orchestrator names a condition that gates ship, deploy, merge, or completion — in a plan, a report, a phase decision, or user-facing prose. Satisfying a gate SHALL append `{satisfied_at, evidence_path}` to its entry, where `evidence_path` cites the executed check's output or verdict file.

#### Scenario: Declaring a gate records it
- **WHEN** the orchestrator states that the release gates on the full Playwright suite against the live URL
- **THEN** a registry entry exists with that declaration text and a check command or artifact expectation before any ship step runs

### Requirement: The completion audit blocks on unsatisfied declared gates
`hooks/pipeline-completion-audit.py` SHALL gain an `_audit_declared_gates` arm in the worklist family: every registry entry MUST carry `satisfied_at` and an `evidence_path` that exists and is >0 bytes before the run may complete; an unsatisfied entry is a violation quoting the gate's own `declaration_text`. The arm SHALL fail-open when the registry file is absent (a run that declared nothing).

#### Scenario: Unsatisfied gate blocks completion
- **WHEN** the registry contains a gate with no `satisfied_at` and the Stop audit runs
- **THEN** the audit exits non-zero with a violation quoting the declaration text

#### Scenario: Absent registry is fail-open
- **WHEN** no declared-gates.json exists in the run state
- **THEN** the `_audit_declared_gates` arm reports no violation

#### Scenario: Satisfied gate passes
- **WHEN** every registry entry carries `satisfied_at` and an existing non-empty `evidence_path`
- **THEN** the arm reports no violation

### Requirement: The discipline text makes naming a gate recording a gate
`skills/common-pipeline-conventions/SKILL.md` SHALL gain a declared-gates discipline section, and the pipeline skills' ship-adjacent phase text SHALL reference it: a gate you name is a gate you record; an unrecorded gate is a claim, and unverified claims about gates are exactly what the discipline forbids. Deploy/ship steps SHALL check the registry before executing.

#### Scenario: Pipeline text references the registry before ship
- **WHEN** the architect-team pipeline's Phase 8 pre-commit text is read
- **THEN** it requires the declared-gates registry to be satisfied (via the completion audit) before the auto-commit proceeds
