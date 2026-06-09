## ADDED Requirements

### Requirement: README documents the v3.8.0 capabilities

`README.md` SHALL contain a v3.8.0 capability section (in the house bitmap style) describing unbounded solving (no iteration ceiling; loop until success; audit-as-worklist; oscillation continues from a different angle; sub-loops converge) AND the CDLG lineage foundation (the `endpoint-trace-mapping` + `data-lineage-mapping` skills, the `endpoint-tracer` agent, `hooks/lineage_graph.py`, `hooks/run_metrics.py`, the bug-isolation reorder, squash-merge detection + task-aware worktree, `cdlg_overlap`), with the honest boundary that live polyglot extraction is the agent's runtime job. Version/counts SHALL remain correct (3.8.0 / 40 / 34 / 19 / 3870).

#### Scenario: README names the v3.8.0 capabilities

- **WHEN** `README.md` is read
- **THEN** it describes unbounded solving AND the CDLG lineage foundation, naming the new skills, agent, and modules
- **AND** the version banner is 3.8.0 and the styling/count structural tests pass

### Requirement: CLAUDE.md version-history covers v3.8.0

`CLAUDE.md` SHALL carry a v3.8.0 summary in its version-history paragraph (unbounded solving + CDLG), consistent with the v3.3–3.7 summary style; counts current (40/34/19).

#### Scenario: CLAUDE.md history names v3.8.0

- **WHEN** `CLAUDE.md` is read
- **THEN** the version-history paragraph contains a v3.8.0 entry summarizing unbounded solving + the CDLG foundation

### Requirement: CODEBASE_MAP documents the v3.8.0 modules

`docs/CODEBASE_MAP.md` SHALL document the new v3.8.0 modules/skills/agents — `hooks/lineage_graph.py`, `hooks/run_metrics.py`, `hooks/locks.py::cdlg_overlap`, the `worktree_lifecycle.py` squash-merge + task-aware additions, the `pipeline-completion-audit.py` limit-removal, the `endpoint-trace-mapping` + `data-lineage-mapping` skills, and the `endpoint-tracer` agent — with accurate counts and a refreshed `last_mapped`.

#### Scenario: CODEBASE_MAP names the new modules

- **WHEN** `docs/CODEBASE_MAP.md` is read
- **THEN** `lineage_graph.py`, `run_metrics.py`, the two new skills, and the new agent are documented
- **AND** the skill/agent counts and `last_mapped` are current

### Requirement: INTEGRATION_MAP and phenotypes README are current

`docs/INTEGRATION_MAP.md` SHALL reflect the lineage integration points (or be confirmed already-accurate) and `phenotypes/README.md` SHALL carry no stale version/count reference.

#### Scenario: secondary docs are current

- **WHEN** `docs/INTEGRATION_MAP.md` and `phenotypes/README.md` are read
- **THEN** neither contains a stale fact contradicting the v3.8.0 state
