---
created: 2026-06-08
status: draft
doc_type: requirements
title: CT6 Lineage & Logical Bug-Isolation Upgrade
source: "/Users/axe/Documents/AI Agent System Mapping and Automated Bug Diagnosis Strategy_transcript.txt"
note: "Formalizes the source transcript into enumerated requirements, a current-state scorecard vs CT6, a unifying architectural proposal (CDLG), and a phased roadmap. Awaiting owner decisions in §8 before implementation."
---

# CT6 Lineage & Logical Bug-Isolation Upgrade — Requirements

## Document control

| Field | Value |
|---|---|
| Status | Draft — awaiting owner decisions (§8) |
| Created | 2026-06-08 |
| Source | `AI Agent System Mapping and Automated Bug Diagnosis Strategy_transcript.txt` (dictated design notes) |
| Scope | New/extended CT6 **skills + agents + artifacts** that the pipeline produces *inside target codebases* |
| Related | `skills/bug-fix-pipeline`, `skills/diagnostic-research-team`, `skills/documentation-currency`, `skills/mempalace-integration`, `skills/common-pipeline-conventions`, `scripts/setup/worktree_lifecycle.py` |

---

## 1. Background & problem statement

CT6 reliably **finds and replicates** bugs (Playwright user-flows against a live dev environment, mandatory in `bug-fix-pipeline` Phase B1). It is weaker at **logically isolating** them: diagnosis discovers the relevant code path *while theorizing* rather than laying out the call/data structure first and reasoning against a known map.

This document converts the source transcript into a concrete, prioritized requirements set, grounded in a verified assessment of what CT6 does today.

---

## 2. Source material — distilled concepts

Seven concept clusters from the transcript:

| # | Cluster |
|---|---|
| C1 | **Structured bug-isolation methodology** — replicate → subset pages→APIs → recursive call-hierarchy → light API discriminant first → backtrack to data source |
| C2 | **Per-endpoint deep documentation** built post-deploy, freshness-checked, mandated by a skill, markdown + mermaid + in-file datestamp, cached |
| C3 | **Data-model decomposition + per-asset lineage** — schemas/contents, how each asset is populated and by which functions |
| C4 | **MemPalace function-level graph** — look up a function → upstream / downstream / data sources; a function-naming nomenclature |
| C5 | **Parallelism via overlap detection** + a canonical front→back map |
| C6 | **Worktree-vs-in-place heuristics + always-merge-to-main / no loose branches** |
| C7 | **Supervisory agent / project-lifecycle management** (flagged by the author as future) |

---

## 3. Current-state assessment vs CT6 (✅ done · 🟡 partial · ❌ missing)

| Concept | Status | What exists today | Gap |
|---|---|---|---|
| C1.a Playwright replication | ✅ | `bug-fix-pipeline` B1 + `agents/bug-replicator.md` | none |
| C1.b Subset pages → APIs before diagnosis | 🟡 | replicator identifies failing path from ROUTE/INTEGRATION maps | no explicit "freeze the endpoint set as scope" gate |
| C1.c Recursive call-hierarchy *before* diagnosing | ❌ | `diagnostic-researcher` traces the executed path inline | no pre-built nested call-tree artifact |
| C1.d Light API discriminant *first* | 🟡 | B2 backend diagnostic performs the check | bundled into replication; not a distinct early FE-vs-API gate |
| C1.e Backtrack params → "does data live at source" | ✅ | `diagnostic-research-team` traces file:line to DB | depends on C1.c being laid out first |
| C2.a Per-endpoint internal call-pattern docs | ❌ | `API_DESIGN_MAP.md` stops at the HTTP contract | nothing documents an endpoint's internal function chain |
| C2.b Built post-deploy, skill-mandated | 🟡 | `documentation-currency` runs at Phase 8 | refreshes maps, not endpoint internals |
| C2.c Freshness check (doc vs code recency) | 🟡 | `cartographer-team`/`intake-and-mapping` compare `last_mapped` vs `git log` | coarse — one timestamp per codebase |
| C2.d Build-map-if-missing before proceeding | 🟡 | intake builds `CODEBASE_MAP` if absent | doesn't extend to endpoint-trace depth |
| C2.e markdown + mermaid + in-file datestamp + cache | 🟡 | frontmatter timestamps; mermaid only in `CODEBASE_MAP.md` | API maps lack call-flow mermaid |
| C3.a Data-model decomposition in the diagnostic flow | 🟡 | `data-engineering-exploration` Stage 2 | only in Phase 0c; never in bug-fix/feature flows |
| C3.b/c Per-asset population + read/write/modify/origin graph | ❌ | Stage 6 names external tools (OpenLineage/dbt) | no CT6-native asset graph |
| C3.d Dedicated per-asset tracking skill | ❌ | — | doesn't exist |
| C4.a MemPalace function-level lineage | ❌ | 14 record types, all whole-artifact granularity | nothing function-level / queryable |
| C4.b Function-naming nomenclature | ❌ | conventional names only, undocumented | no standard exists |
| C5.a Overlap detection for parallel work | 🟡 | `hooks/locks.py` + non-overlapping `files_owned` + `reconciler` | file-path based, not call-graph based |
| C5.b Canonical front→back map | 🟡 | `INTEGRATION_MAP` + `INTERACTION_INTUITION_MAP` | stops at endpoint boundary |
| C6.a Worktree vs in-place | ✅* | v1.2.0 auto-worktree default + `--no-worktree` + re-entry detect | *fixed default, not a task-aware heuristic |
| C6.b Always merge to main / no loose branches | ✅ | **v3.7.0 auto-merge + v1.3.0 cleanup + startup reconciliation** | only squash-merges not auto-detected (safe default) |
| C7 Supervisory lifecycle agent | ❌ | orchestrator + phases; `test-run-monitor` is passive | no dedicated lifecycle/PM agent (author: future) |

**Already shipped — do not rebuild:** the C6 worktree/merge discipline (transcript lines ~223–244) is implemented at v3.7.0 + v1.3.0; C1.a (Playwright replication) is fully operational.

---

## 4. Guiding architectural proposal — the Code & Data Lineage Graph (CDLG)

Clusters **C1, C2, C3, C4, C5 are the same primitive** wearing different hats: a persisted, queryable graph of `functions ↔ endpoints ↔ data assets`. Build it once; the rest become thin consumers.

- **Nodes:** `function`, `endpoint`, `data_asset`.
- **Edges:** `calls` / `called_by`, `reads` / `writes` / `modifies`, `serves` (endpoint→function), `originates` (asset genesis).
- **Built on-demand, subset-first** — the bug's pages→APIs define the trace subset (cost control); persist and reuse.
- **Hybrid extraction** — cheap static seeding per language (tree-sitter / LSP / ctags) refined by an LLM tracer within the subset (handles CT6's polyglot targets).
- **Storage** — human view (`ENDPOINT_TRACE_MAP.md`, `DATA_LINEAGE_MAP.md`: markdown + mermaid call-trees + in-file datestamp) **plus** a machine sidecar (`lineage-graph.json`).
- **Identity nomenclature** — `func://<codebase>/<path>#<qualified_name>`, `asset://<store>/<schema>/<table>`.
- **Freshness** — reuse `last_mapped`-vs-`git log`, per endpoint; refresh under the Phase 8 `documentation-currency` gate.

Consumers: diagnosis walks the graph (C1); endpoint docs render it (C2); data lineage is its asset edges (C3); MemPalace lookup queries it at function granularity (C4); overlap detection asks "do two work-items share a subtree" (C5).

---

## 5. Requirements

Priority: **P1** must-have · **P2** should-have · **P3** nice-to-have. Status is relative to current CT6 (§3).

### 5.1 Bug-isolation methodology (REQ-DIAG)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-DIAG-01 | P1 | extend | **Scope-isolation gate.** After replication, enumerate the involved pages and subset to the exact endpoints used on them; freeze as the diagnosis scope. *AC:* a scope artifact lists pages + endpoint set; diagnosis is bounded to it. |
| REQ-DIAG-02 | P1 | extend | **Light diagnostic discriminant, run first.** Before deep code analysis, call the API layer as the authenticated user and assert whether data is returned; branch FE-bug vs API-bug. *AC:* a discriminant step precedes deep analysis and records an FE/API verdict with evidence. |
| REQ-DIAG-03 | P1 | new | **Pre-diagnosis call-hierarchy.** Produce a nested call-pattern map (endpoint → functions → sub-functions, recursively) before hypothesis formation. *AC:* a call-tree artifact exists and is cited by the diagnostic step. |
| REQ-DIAG-04 | P1 | reuse+extend | **Data-source existence check.** Backtrack the function + parameters into the table/store and verify whether the data lives at source. *AC:* diagnosis cites the data-layer node and a present/absent verdict (consumes REQ-DIAG-03). |
| REQ-DIAG-05 | P1 | new | **Reordered pipeline.** `bug-fix-pipeline` order becomes: replicate → scope-isolate → light-discriminant → call-map → diagnose. *AC:* cheap checks demonstrably precede deep analysis. |

### 5.2 Endpoint documentation (REQ-DOC)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-DOC-01 | P1 | new | **Per-endpoint deep docs.** Document each in-scope endpoint's internal recursive function-call pattern. *AC:* `ENDPOINT_TRACE_MAP.md` per codebase with per-endpoint call trees. |
| REQ-DOC-02 | P2 | extend | **Mandated post-deploy construction.** At the end of every dev+deploy cycle, (re)build endpoint docs for touched endpoints; enforced by a dedicated skill. *AC:* Phase 8 gate refreshes endpoint docs for changed endpoints. |
| REQ-DOC-03 | P1 | extend | **Build-if-missing gate.** If the endpoint depth-map is absent, build it before bug-fix deep diagnosis proceeds. *AC:* pipeline blocks deep diagnosis until the relevant endpoint map exists. |
| REQ-DOC-04 | P2 | extend | **Per-endpoint freshness.** Verify the endpoint doc's datestamp is newer than the last change to that endpoint/page; refresh if stale. *AC:* freshness compared at endpoint granularity. |
| REQ-DOC-05 | P2 | extend | **Storage standard.** markdown + mermaid call-trees + in-file datestamp + stable greppable names; cached and incrementally updated. *AC:* artifacts contain mermaid + in-file timestamp; re-runs reuse cache. |

### 5.3 Data lineage (REQ-DATA)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-DATA-01 | P1 | extend | **Data-model decomposition in the diagnostic flow.** When a trace reaches data, pull schemas/contents, summarize, examine joins/merges (in/out of DB). *AC:* available outside the Phase 0c data-eng path. |
| REQ-DATA-02 | P2 | new | **Per-asset population tracking.** Record how each data asset is populated and by which functions. *AC:* `DATA_LINEAGE_MAP.md` records population sources per asset. |
| REQ-DATA-03 | P1 | new | **Data-asset graph.** Per asset: which functions read / write / modify it, and how it originates. *AC:* read/write/modify/origin edges present in `lineage-graph.json`. |
| REQ-DATA-04 | P2 | new | **Dedicated skill.** A `data-lineage-mapping` skill maintains the above. *AC:* skill exists and is invoked by the relevant phases. |

### 5.4 MemPalace function lineage (REQ-MEM)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-MEM-01 | P1 | new | **Function-level lineage records.** Store the CDLG so a function lookup returns upstream callers, downstream callees, and data sources. *AC:* query a function ID → callers / callees / data-sources. |
| REQ-MEM-02 | P1 | new | **Identity nomenclature.** A stable function/asset ID convention (`func://…`, `asset://…`). *AC:* documented nomenclature used across artifacts + MemPalace records. |

### 5.5 Parallelism & overlap (REQ-PARA)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-PARA-01 | P2 | extend | **Call-graph overlap detection.** Derive work-item overlap from the CDLG (shared callees/subtrees), not only file paths; feed the parallel-execution graph + locks. *AC:* overlap verdict considers shared functions, not just files. |
| REQ-PARA-02 | P2 | extend | **Canonical front→back map.** Chain UI element → endpoint → function tree → data asset into one navigable traversal. *AC:* a single traversal from a UI control to a data asset exists. |

### 5.6 Worktree & merge discipline (REQ-WT) — largely already implemented

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-WT-01 | P1 | ✅ done | **Always merge to main / no loose branches.** *AC:* satisfied by v3.7.0 auto-merge + v1.3.0 cleanup; verify no regression. |
| REQ-WT-02 | P3 | polish | **Task-aware worktree heuristic** (vs fixed always-on default). *AC:* worktree choice can vary by task scope/size. |
| REQ-WT-03 | P3 | polish | **Squash-merge detection** in cleanup. *AC:* squash-merged branches are recognized as merged. |

### 5.7 Supervisory lifecycle (REQ-SUP) — future

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-SUP-01 | P3 | future | **Supervisory agent for project lifecycle / PM techniques.** *AC:* TBD; out of immediate scope. |

---

## 6. Phased roadmap

| Phase | Deliverable | Consumes → Produces | Effort | Risk | Depends on | Requirements |
|---|---|---|---|---|---|---|
| **P0 — Quick wins** | Reorder `bug-fix-pipeline`: add scope-isolation + light-discriminant gates (orchestration only, uses existing maps) | ROUTE/INTEGRATION maps → tighter diagnosis | S | Low | — | DIAG-01, DIAG-02, DIAG-05 |
| **P1 — CDLG foundation** | New skill `endpoint-trace-mapping` + agent `endpoint-tracer`; `ENDPOINT_TRACE_MAP.md` + `lineage-graph.json`; hybrid extraction; subset+cache+freshness | code subset → call graph | L | **High** | P0 | DOC-01/03/04/05, DIAG-03, MEM-02 |
| **P2 — Diagnosis rewire** | Call-map gate; `diagnostic-research-team` reads CDLG instead of re-tracing | CDLG → ranked hypotheses | M | Med | P1 | DIAG-03, DIAG-04 |
| **P3 — Data lineage** | `data-lineage-mapping` skill + agent; asset edges; data decomposition in the bug flow | CDLG + schemas → `DATA_LINEAGE_MAP.md` | M | Med | P1 | DATA-01/02/03/04 |
| **P4 — Overlap + canonical map** | Extend parallel-execution-graph + `team-spawning-and-review-gates` to consult the CDLG | CDLG → overlap verdicts | M | Med | P1 | PARA-01, PARA-02 |
| **P5 — MemPalace granularity** | New record type + function-ID nomenclature; mine `lineage-graph.json` | CDLG → MemPalace records | M | Med | P1 | MEM-01, MEM-02 |
| **P6 — Polish C6** | Task-aware worktree heuristic; squash-merge detection | — | S | Low | — | WT-02, WT-03 |
| **P7 — Supervisory lifecycle** (future) | Lifecycle/PM agent over runs | — | L | — | later | SUP-01 |

**Critical path:** P0 (ship now) → P1 (foundation) → P2–P5 (parallelizable). P6 is independent and tiny.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Polyglot call-graph extraction** (make-or-break) | Hybrid static-seed + LLM-refine, strictly bounded to the bug's subset, persisted (paid once per page-cluster). |
| **Cost / scale of full graphs** | Subset-on-demand + cache + incremental update on changed files only. |
| **Staleness** | Graph is a documentation-currency artifact; Phase 8 refreshes it like any other map. |
| **MemPalace record explosion** | Bound function-level records to the mapped subset; function-ID nomenclature keeps them diffable/dedupable. |

---

## 8. Open decisions (owner input required before implementation)

1. **Locus** — confirm these are CT6 skills/agents that *produce artifacts inside target codebases* (assumed), not changes to a single application.
2. **Extraction strategy** — hybrid static+LLM (recommended) vs pure-LLM vs static-only.
3. **Sequencing** — ship P0 quick-wins first (recommended) while speccing P1, vs foundation-first.
4. **Mechanization** — promote this document to an OpenSpec change (`openspec/changes/<name>/`) and drive P0 through `/architect-team:mini`?

---

## 9. Out of scope / already implemented

- **C6 worktree + merge discipline** — implemented (v3.7.0 auto-merge-and-prune, v1.3.0 merged-worktree sweep, startup branch reconciliation). Only optional polish remains (REQ-WT-02/03).
- **C1.a Playwright replication** — fully operational today.
- **C7 supervisory lifecycle** — deferred (author flagged as future).
