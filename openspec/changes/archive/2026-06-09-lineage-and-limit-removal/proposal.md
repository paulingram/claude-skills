## Why

Two owner directives, on one reviewable branch: (1) **remove all run/iteration limits** so the dev-loop never halts until success — the owner chose the hard-literal reading, reconciled to "nothing can BLOCK/halt the run; the completeness checks become a worklist that keeps the loop going until everything is green"; and (2) **execute the `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` roadmap P0–P6** — building the Code & Data Lineage Graph (CDLG) and its consumers as CT6 plugin artifacts, with P1's research-grade polyglot extraction shipped as real contracts + structural tests + buildable stdlib pieces (live extraction NOT claimed proven; kill-gated per the doc).

## What Changes

- **Remove the global iteration ceiling (20)** + oscillation→abort + exhaustion→escalate-and-stop; convert bounded sub-loops to loop-until-converged; convert the completion-audit from a halting gate into a non-halting worklist; keep the concurrency model, the 3-pass RCA rigor floor, and the executed-not-described disciplines. New canonical `## Unbounded solving discipline` in `common-pipeline-conventions`. (REQ-UNB-01..05)
- **P0** diagnosis reorder in `bug-fix-pipeline` (scope-isolation + EXECUTED light FE/API discriminant before deep diagnosis). (REQ-CDL-01)
- **P0.5** per-run metric instrumentation (REQ-SAFE-02) + frozen-benchmark protocol. (REQ-CDL-02)
- **P1** `endpoint-trace-mapping` skill + `endpoint-tracer` agent; `lineage_graph` schema + validator, `func://`/`asset://` ID nomenclature (overload/closure/rename-stable), runtime-witness reconciliation (REQ-DOC-06), two-layer extraction + cost/freshness contracts. (REQ-CDL-03..06)
- **P2** `diagnostic-research-team` consumes the CDLG. (REQ-CDL-07)
- **P3** `data-lineage-mapping` skill (reuse-first vs data-eng). (REQ-CDL-08)
- **P4** CDLG-based overlap detection + canonical front→back traversal. (REQ-CDL-09)
- **P5** MemPalace function-level records + nomenclature. (REQ-CDL-10)
- **P6** squash-merge detection + task-aware worktree heuristic in `worktree_lifecycle.py`. (REQ-CDL-11)
- **Release** v3.8.0; full pytest suite green; one branch kept for review (no auto-merge).

## Capabilities

### New Capabilities

- `unbounded-solving`: the pipeline has no iteration ceiling and never halts on incomplete work; it loops until every gate is green (success), surfacing genuinely-external blockers without stopping.
- `code-data-lineage`: a persisted, runtime-verified graph of functions↔endpoints↔data-assets (CDLG) plus its consumers — structured bug-isolation, per-endpoint trace docs, data lineage, call-graph overlap detection, and MemPalace function-level records.

### Modified Capabilities

None removed. Existing disciplines (concurrency, RCA rigor, executed-testing, domain gates) are preserved; only the halting/limit character is removed.

## Impact

**Affected files:** `hooks/pipeline-completion-audit.py`; `skills/common-pipeline-conventions/SKILL.md`, `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md`, `skills/ux-test-builder/SKILL.md`, `skills/diagnostic-research-team/SKILL.md`, `skills/editability-completeness/SKILL.md`, `skills/interaction-completeness/SKILL.md`, `skills/expensive-verification-debugging/SKILL.md`, `skills/intake-and-mapping/SKILL.md`, `skills/cartographer-team/SKILL.md`, `skills/api-design-from-frontend/SKILL.md`, `skills/data-engineering-exploration/SKILL.md`, `skills/mempalace-integration/SKILL.md`, `skills/team-spawning-and-review-gates/SKILL.md`; NEW `skills/endpoint-trace-mapping/`, `skills/data-lineage-mapping/`, `agents/endpoint-tracer.md`; NEW lineage stdlib modules under `hooks/` or `scripts/setup/`; `hooks/locks.py`; `scripts/setup/worktree_lifecycle.py`; `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` (present on branch); `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`; + tests.
