# Tasks

## WS-A — Limit removal (REQ-UNB-01..05)
- [ ] A.1 `hooks/pipeline-completion-audit.py`: delete `ITERATION_CEILING` + `_audit_iteration_ceiling` + its call; reframe BLOCKED message as worklist; keep other audits.
- [ ] A.2 `common-pipeline-conventions/SKILL.md`: add `## Unbounded solving discipline`.
- [ ] A.3 `architect-team-pipeline` / `bug-fix-pipeline` / `mini-architect-team-pipeline` / `ux-test-builder`: remove ceiling/oscillation-abort/exhaustion-stop prose; reference the canonical section; reframe escalation to required-input-only.
- [ ] A.4 sub-loop skills (diagnostic-research-team, editability/interaction-completeness, expensive-verification-debugging, intake-and-mapping, cartographer-team, api-design-from-frontend, data-engineering-exploration): caps → convergence.
- [ ] A.5 tests: rewrite ceiling/oscillation/escalation tests to assert no-halt-worklist; add a high-`dev_loop_iterations`-passes test.

## WS-B — P6 worktree polish (REQ-CDL-11)
- [ ] B.1 `worktree_lifecycle.py`: squash-merge detection (no false-positive) + task-aware worktree heuristic.
- [ ] B.2 real-git tests for both.

## WS-C — P0 + P0.5 (REQ-CDL-01, REQ-CDL-02)
- [ ] C.1 `bug-fix-pipeline`: scope-isolation + EXECUTED light FE/API discriminant before deep diagnosis (reorder).
- [ ] C.2 metric instrumentation + frozen-benchmark protocol; structural test.

## WS-D — P1 CDLG core (REQ-CDL-03..06)
- [ ] D.1 NEW `skills/endpoint-trace-mapping/SKILL.md` + `agents/endpoint-tracer.md` (registered, frontmatter-valid).
- [ ] D.2 NEW stdlib lineage modules: graph schema+validator, `func://`/`asset://` ID nomenclature (rename-stable), witness-reconciliation (recall/hallucination + threshold), freshness/cost helpers — unit-tested.
- [ ] D.3 two-layer extraction + cost/freshness CONTRACTS documented.

## WS-E — P2–P5 consumers (REQ-CDL-07..10)
- [ ] E.1 `diagnostic-research-team`: consume the CDLG (call-map gate).
- [ ] E.2 NEW `skills/data-lineage-mapping/SKILL.md` (+ agent if warranted) with Reuse Decision vs data-eng.
- [ ] E.3 overlap detection (CDLG-based) in `hooks/locks.py` + `team-spawning-and-review-gates`; canonical front→back traversal.
- [ ] E.4 `mempalace-integration`: function-level records + nomenclature.
- [ ] E.5 structural tests for E.1–E.4.

## WS-F — Release
- [ ] F.1 bump plugin.json + marketplace.json → 3.8.0; CHANGELOG v3.8.0.
- [ ] F.2 README + CLAUDE currency.
- [ ] F.3 full `python -m pytest` green; keep on branch (no auto-merge).
