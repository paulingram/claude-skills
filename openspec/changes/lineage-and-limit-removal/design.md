## Context

A CT6-plugin self-change (this repo IS the plugin). Two deliverables on one branch. Reuse-first: extend existing skills/hooks/modules; new skills/agents only where no equivalent exists. The runtime execution witness (`code-path-witness.json`, v0.9.31/0.9.32) already exists and is REUSED as the CDLG ground-truth (REQ-DOC-06) — not rebuilt.

## Key decisions

### D1 — Limit removal reconciled to "no-halt worklist"
The owner chose hard-literal "remove everything." Removing the completeness gate outright would let a run finish incomplete — the opposite of the primary goal "cannot stop until success." Reconciliation: remove every numeric LIMIT (ceiling, oscillation-abort, exhaustion-stop, sub-loop caps); convert the completion-audit from a halting gate into the worklist that keeps the loop running until empty (success); surface-and-continue for required input. The `ITERATION_CEILING` is the only true numeric limit in the hook → deleted. The other audit checks remain (they define "not yet success"). The escalation marker remains ONLY for required user input, not give-up.

### D2 — CDLG as one primitive, shipped as contracts + buildable stdlib
P1's polyglot extraction is research-grade + kill-gated. Build the deterministic, testable pieces for real: the `lineage-graph.json` schema + validator, the `func://`/`asset://` ID module (rename-stable), the witness-reconciliation (recall/hallucination over provided graph+witness), freshness/cost helpers. Ship the skill/agent + two-layer-extraction contract as documentation + structural tests. Do NOT claim live polyglot extraction proven.

### D3 — Sequential workstreams on one branch (no parallel teammates)
Many deliverables touch the same skill files (bug-fix-pipeline, diagnostic-research-team, common-pipeline-conventions, plugin.json, CHANGELOG, README, CLAUDE, registration tests) → true parallel teammates would collide on the "two teammates never edit the same file" rule. Execute as ordered, individually-tested workstreams, checkpoint-committed on the one branch: (A) limit-removal → (B) P6 worktree → (C) P0+P0.5 → (D) P1 CDLG core → (E) P2–P5 consumers → (F) version+docs.

## Reuse Decision Log

| Item | Decision | Rationale |
|---|---|---|
| Runtime witness for graph trust | RD-REUSE `code-path-witness.json` | Already captures executed handlers; reused as ground truth (REQ-DOC-06). |
| Limit removal | RD-MODIFY `pipeline-completion-audit.py` + skills | Delete the ceiling; reframe checks as worklist. |
| P6 squash-merge / task-aware | RD-EXTEND `worktree_lifecycle.py` | Composes existing merge/cleanup helpers. |
| data-lineage-mapping | RD-EXTEND vs `data-engineering-exploration` | Reuse Stage 2/6 decomposition where possible (Reuse Decision in its body). |
| endpoint-trace-mapping skill/agent | RD-NEW | No existing endpoint-internal call-trace capability. |
| Lineage stdlib (schema/ID/witness) | RD-NEW stdlib modules | No existing equivalent; stdlib-only like the other hooks. |

## Risks

- **Scope size** — mitigated by sequential checkpoint-committed workstreams; the limit-removal (highest priority) lands first.
- **Overclaiming P1** — mitigated by the honest contracts-plus-structural-tests boundary; live extraction explicitly not claimed.
- **Test breakage from limit-removal** — the ceiling/oscillation tests are REWRITTEN (not deleted) to assert the new no-halt behavior.
