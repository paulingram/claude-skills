## ADDED Requirements

### Requirement: Structured bug-isolation reorder (P0)

`bug-fix-pipeline` SHALL, after replication, freeze a scope-isolation artifact (involved pages → the exact endpoint set) and run an EXECUTED light FE/API discriminant (a real authenticated call against the live dev environment, evidence-backed — never a code-read verdict) BEFORE deep diagnosis, in the order replicate → scope-isolate → light-discriminant → call-map → diagnose.

#### Scenario: cheap checks precede deep analysis

- **WHEN** the bug-fix pipeline runs
- **THEN** a scope-isolation artifact (pages + endpoint set) and an executed FE/API discriminant verdict are recorded before any deep-diagnosis step
- **AND** the discriminant verdict is backed by a captured request/response, not a code read

### Requirement: Run-metric instrumentation (P0.5)

The pipeline SHALL record, per run, the success metrics named in the lineage doc §6 — `dev_loop_iterations`, first-pass-fix outcome, oscillation / `bug-still-present` / `fix-regression` counts, the FE/API discriminant verdict vs the layer actually fixed, and (when present) the REQ-DOC-06 recall/hallucination numbers — to a queryable location (run ledger + MemPalace run-history). A frozen-benchmark protocol SHALL be documented.

#### Scenario: metrics are recorded per run

- **WHEN** a bug-fix run completes
- **THEN** the named metrics are written to the run ledger in a queryable form

### Requirement: Endpoint trace mapping skill + agent (P1)

The plugin SHALL provide a registered, frontmatter-valid `endpoint-trace-mapping` skill and an `endpoint-tracer` agent that produce `ENDPOINT_TRACE_MAP.md` (markdown + depth/size-capped mermaid + datestamp) and the `lineage-graph.json` machine sidecar, via a documented two-layer extraction contract (intra-service LSP-first static seed + LLM-refine; inter-service route/contract matching reusing INTEGRATION_MAP + INTERACTION_INTUITION_MAP).

#### Scenario: the skill and agent exist and validate

- **WHEN** the plugin's skills and agents are enumerated
- **THEN** `endpoint-trace-mapping` skill and `endpoint-tracer` agent are present with valid frontmatter and are referenced by the pipeline

### Requirement: Lineage graph schema, ID nomenclature, and witness verification (P1)

The plugin SHALL provide a stdlib `lineage-graph.json` schema + validator; a `func://`/`asset://` identity module with documented overload/closure/anonymous handling and a rename-stability fallback (AST-path or content-hash); and a runtime-witness reconciliation routine (REQ-DOC-06) that, given a CDLG subset and a `code-path-witness.json`, computes edge recall and hallucination rate and gates consumption on a configurable threshold. These SHALL be unit-tested.

#### Scenario: ID stability across a rename

- **WHEN** a function is renamed but its body is unchanged
- **THEN** the identity module's rename-stability fallback yields a stable join key (a round-trip test demonstrates this)

#### Scenario: witness reconciliation computes recall and hallucination

- **WHEN** the reconciliation routine is given a subset graph and a witness
- **THEN** it returns edge recall and hallucination-rate numbers and a pass/fail against the configured threshold

### Requirement: Cost ceiling and transitive freshness for traces (P1)

Trace construction SHALL run under a hard token/time budget with marked depth-truncation (never silent drop), and freshness SHALL be transitive — a node is stale if any node reachable in its subtree changed since `last_mapped`. These contracts SHALL be documented and the freshness/cost helpers unit-tested where deterministic.

#### Scenario: transitive staleness

- **WHEN** a deep callee changed but the endpoint's own file did not
- **THEN** the freshness helper marks the endpoint's trace stale

### Requirement: Diagnosis consumes the CDLG (P2)

`diagnostic-research-team` SHALL consume the verified CDLG (call-map gate) rather than re-tracing, and the data-source existence check SHALL cite the `asset://` node.

#### Scenario: diagnosis reads the CDLG

- **WHEN** the diagnostic-research-team skill is read
- **THEN** it documents consuming the verified CDLG / endpoint trace as its call-map input

### Requirement: Data lineage skill (P3)

The plugin SHALL provide a `data-lineage-mapping` skill producing `DATA_LINEAGE_MAP.md` + the asset edges (`reads`/`writes`/`modifies`/`originates`) in `lineage-graph.json`, with a Reuse Decision vs `data-engineering-exploration` Stage 2/6.

#### Scenario: the data-lineage skill exists with a reuse decision

- **WHEN** the plugin's skills are enumerated
- **THEN** `data-lineage-mapping` is present and its body records a reuse-first decision vs the data-eng skill

### Requirement: Call-graph overlap + canonical traversal (P4)

CDLG-based overlap detection SHALL feed the parallel-execution graph + `hooks/locks.py` (shared-callee overlap, not just file paths), and a single validated UI-element → endpoint → function → data_asset traversal SHALL be defined for the bug subset.

#### Scenario: overlap considers shared callees

- **WHEN** two work-items edit different files but share a hot callee
- **THEN** the documented overlap rule flags them as overlapping

### Requirement: MemPalace function-level lineage (P5)

MemPalace SHALL store function-level lineage records (a `func://` lookup returns callers / callees / data-sources), bounded to the mapped subset, using the stable nomenclature.

#### Scenario: a function lookup returns lineage

- **WHEN** the mempalace-integration body is read
- **THEN** it documents function-level lineage records keyed by `func://` IDs

### Requirement: Worktree polish — squash-merge detection + task-aware heuristic (P6)

`scripts/setup/worktree_lifecycle.py` SHALL detect a squash-merged branch as merged (without a false-positive that deletes unmerged work) and SHALL support a task-aware worktree heuristic (the auto-worktree default may vary by task scope/size; `--no-worktree` still honored). Both SHALL have real-git tests.

#### Scenario: a squash-merged branch is recognized as merged

- **WHEN** a branch was squash-merged into main
- **THEN** the squash-merge detection recognizes it as merged
- **AND** an unmerged branch is never falsely flagged as merged
