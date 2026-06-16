## ADDED Requirements

### Requirement: REQ-001 — `parallel-problem` classification + auditable lane linkage

`hooks/inflight_inbox.py` SHALL add `parallel-problem` to `CLASSIFICATIONS`, add a `lane_id` field to the message schema (initialized null on append), and `mark_processed` SHALL require a non-empty `lane_id` when `classification == "parallel-problem"` (recording it on the message). Existing classifications SHALL continue to work without a `lane_id`. The module SHALL remain stdlib-only.

#### Scenario: parallel-problem records a lane and rejects a missing one

- **WHEN** `mark_processed(..., classification="parallel-problem", lane_id="lane-B")` runs
- **THEN** the message persists `classification == "parallel-problem"` and `lane_id == "lane-B"`
- **AND** calling it with `classification="parallel-problem"` and no `lane_id` raises `ValueError`

### Requirement: REQ-002 — Sanctioned concurrent in-run lanes (not forbidden siblings)

The canonical `## In-flight clarification discipline (v2.5.0)` SHALL document a `### Parallel lanes (v3.16.0)` mechanism: a separable, independent, disjoint-scope injected problem opens a concurrent in-run lane holding a disjoint `hooks/locks.py` file-scope lock, converging via Phase 4; the `spawn-sibling-invocation` anti-pattern SHALL be amended to distinguish a forbidden second `/architect-team` RUN from an allowed in-run LANE.

#### Scenario: lane isolation enforced by the lock layer

- **WHEN** an active lane holds a file-scope lock and a second lane requests a DISJOINT scope
- **THEN** the second lock is granted (true parallel)
- **AND** a request for an OVERLAPPING scope is `blocked` (must queue or fold)

### Requirement: REQ-003 — Responsiveness (poll on every wake)

The inbox-check protocol in `## In-flight clarification injection mechanism (v2.19.0)` and all 3 pipeline bodies SHALL drain the inbox at every phase boundary AND after every background-dispatch return / wake (not only at phase boundaries).

#### Scenario: protocol documents poll-on-every-wake

- **WHEN** the canonical protocol + the 3 pipeline bodies are read
- **THEN** each states the inbox is checked after every background-dispatch return / wake

### Requirement: REQ-004 — Honest harness limits documented

The doctrine SHALL honestly state: the responsiveness is polling, not async push/preemption; lane isolation is file-glob + advisory (`cdlg_overlap` is not wired into `acquire_lock`); background lanes degrade to sequential in subagents-mode; a failed lane spawn downgrades the classification rather than leaving the message unprocessed.

#### Scenario: honesty residuals present

- **WHEN** the `### Parallel lanes (v3.16.0)` section is read
- **THEN** it contains the isolation residual, the dispatch-mode caveat, and the spawn-failure downgrade

### Requirement: REQ-005 — Command + verifier + docs current

`commands/inject.md` SHALL describe the responsive + `parallel-problem` behavior; `verify_inflight_clarifications_processed` remediation text SHALL mention `parallel-problem` (contract unchanged); the documentation-currency inventory + the version (`.claude-plugin/plugin.json` + `marketplace.json` = 3.16.0) SHALL be brought current.

#### Scenario: surfaces updated

- **WHEN** the command, verifier, and version files are read
- **THEN** each reflects v3.16.0 and the parallel-problem mechanism

### Requirement: REQ-006 — Tests green both encodings

A new test file SHALL cover the classification + `lane_id` contract, the end-to-end inject mechanism (append → read → lock-isolated lane → processed → verified), the overlapping-scope block, and the doctrine pins; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings
- **THEN** zero failures with the new test file present and passing
