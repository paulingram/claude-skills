## Why

v3.8.0 (unbounded solving + the Code & Data Lineage Graph foundation) is merged to main, but the reader-facing documentation does not yet fully describe the new capabilities. The v3.8.0 build updated version/counts and the CHANGELOG, but `README.md` lacks a v3.8.0 capability section, `CLAUDE.md` lacks a v3.8.0 version-history entry, and `docs/CODEBASE_MAP.md` does not document the new modules (`lineage_graph.py`, `run_metrics.py`), the two new skills, the new agent, `cdlg_overlap`, or the worktree additions. A stale README ships a lie; a stale CODEBASE_MAP breaks the next run's reuse-first design.

## What Changes

- **Update** `README.md` — add a v3.8.0 capability section (house bitmap style) describing unbounded solving + the CDLG lineage foundation (new skills, agent, modules); version/counts already current. (REQ-001)
- **Update** `CLAUDE.md` — add a v3.8.0 version-history summary consistent with the v3.3–3.7 entries. (REQ-002)
- **Update** `docs/CODEBASE_MAP.md` — document `hooks/lineage_graph.py`, `hooks/run_metrics.py`, `hooks/locks.py::cdlg_overlap`, the `worktree_lifecycle.py` squash-merge + task-aware additions, the `pipeline-completion-audit.py` limit-removal, the `endpoint-trace-mapping` + `data-lineage-mapping` skills, the `endpoint-tracer` agent; refresh counts + `last_mapped`. (REQ-003)
- **Verify/refresh** `docs/INTEGRATION_MAP.md` (lineage integration points) + `phenotypes/README.md` (no stale refs). (REQ-004)

Documentation-only; no version bump (stays 3.8.0); no CHANGELOG edit (already current); no source/test changes.

## Capabilities

### New Capabilities

- `documentation-currency-v380`: a guarantee that README, CLAUDE.md, and CODEBASE_MAP fully reflect the v3.8.0 capabilities (unbounded solving + CDLG lineage foundation) — every new skill/agent/module documented, counts accurate, version current.

### Modified Capabilities

None.

## Impact

**Affected files:** `README.md`, `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `phenotypes/README.md`. No code, no version-source-of-truth, no CHANGELOG.
