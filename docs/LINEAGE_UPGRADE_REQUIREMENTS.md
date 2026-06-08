---
created: 2026-06-08
updated: 2026-06-08
revision: 2
status: draft
doc_type: requirements
title: CT6 Lineage & Logical Bug-Isolation Upgrade
source: "/Users/axe/Documents/AI Agent System Mapping and Automated Bug Diagnosis Strategy_transcript.txt"
note: "Formalizes the source transcript into enumerated requirements, a current-state scorecard vs CT6, a unifying architectural proposal (CDLG), success metrics, and a phased roadmap. Revision 2 strengthens graph trustworthiness (runtime-witness grounding), the FE→BE extraction seam, kill-gated phasing, correctness-based acceptance criteria, transitive freshness, concurrency/cost discipline, ID stability, and adds measurable success metrics. Awaiting owner decisions in §9 before implementation."
---

# CT6 Lineage & Logical Bug-Isolation Upgrade — Requirements

## Document control

| Field | Value |
|---|---|
| Status | Draft (revision 2) — awaiting owner decisions (§9) |
| Created | 2026-06-08 |
| Source | `AI Agent System Mapping and Automated Bug Diagnosis Strategy_transcript.txt` (dictated design notes) |
| Scope | New/extended CT6 **skills + agents + artifacts** that the pipeline produces *inside target codebases* |
| Related | `skills/bug-fix-pipeline`, `skills/diagnostic-research-team`, `skills/documentation-currency`, `skills/mempalace-integration`, `skills/common-pipeline-conventions`, `skills/reuse-first-design`, `agents/qa-replayer.md` + the v0.9.31/0.9.32 **code-path execution witness** (`code-path-witness.json`), `scripts/setup/worktree_lifecycle.py` |

### Revision 2 — what changed vs revision 1

The architecture (CDLG-as-shared-primitive) and phasing instinct were sound. Revision 1's blind spot: it treated the generated graph as **trustworthy by construction** — the exact failure mode CT6 was built to refuse (VAO, producer/checker, "testing must be EXECUTED, not described"). Revision 2 closes that and seven adjacent gaps:

1. **Graph trust** — the CDLG is now grounded against the **runtime execution witness** CT6 already captures during replication (new REQ-DOC-06; the highest-value change).
2. **FE→BE seam** — inter-service edges are resolved by route/contract matching, not call-graph traversal, as a distinct sub-problem (new REQ-DOC-07).
3. **Kill-gated phasing** — P1 (the High-risk foundation feeding all of P2–P5) gets an explicit proof-of-value spike with abandon criteria; P0 is guaranteed standalone value.
4. **Correctness-based ACs** — "an artifact exists" → "exists AND is validated" across §5.
5. **Transitive freshness** — staleness via graph reachability (subtree invalidation), not per-endpoint git-mtime (REQ-DOC-04).
6. **Concurrency + cost discipline** — `lineage-graph.json` write-ownership and a hard per-trace budget (new REQ-SAFE-01, REQ-DOC-08).
7. **ID stability** — overload/closure/anonymous handling + rename stability for the function-ID join key (REQ-MEM-02 expanded).
8. **Reuse-first applied to itself** + **measurable success metrics** (new §6).

---

## 1. Background & problem statement

CT6 reliably **finds and replicates** bugs (Playwright user-flows against a live dev environment, mandatory in `bug-fix-pipeline` Phase B1). It is weaker at **logically isolating** them: diagnosis discovers the relevant code path *while theorizing* rather than laying out the call/data structure first and reasoning against a known map.

This document converts the source transcript into a concrete, prioritized requirements set, grounded in a verified assessment of what CT6 does today **and in CT6's own anti-hallucination discipline** — every generated artifact must be verifiable against executed reality, not trusted because it was produced.

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
| C2.c Freshness check (doc vs code recency) | 🟡 | `cartographer-team`/`intake-and-mapping` compare `last_mapped` vs `git log` | coarse — one timestamp per codebase; no transitive (callee) invalidation |
| C2.d Build-map-if-missing before proceeding | 🟡 | intake builds `CODEBASE_MAP` if absent | doesn't extend to endpoint-trace depth |
| C2.e markdown + mermaid + in-file datestamp + cache | 🟡 | frontmatter timestamps; mermaid only in `CODEBASE_MAP.md` | API maps lack call-flow mermaid |
| **Graph trustworthiness (cross-cutting)** | ❌ | **the v0.9.31/0.9.32 `code-path-witness.json` proves which handlers actually executed** — but only for fix verification, not for grounding a map | no generated call/lineage map is reconciled against executed reality |
| C3.a Data-model decomposition in the diagnostic flow | 🟡 | `data-engineering-exploration` Stage 2 | only in Phase 0c; never in bug-fix/feature flows |
| C3.b/c Per-asset population + read/write/modify/origin graph | ❌ | Stage 6 names external tools (OpenLineage/dbt) | no CT6-native asset graph |
| C3.d Dedicated per-asset tracking skill | ❌ | — | doesn't exist |
| C4.a MemPalace function-level lineage | ❌ | record/room granularity is whole-artifact (route-maps, design-maps, diagnostic-plans, rca-artifacts, …) | nothing function-level / queryable |
| C4.b Function-naming nomenclature | ❌ | conventional names only, undocumented | no standard exists; no rename/overload stability story |
| C5.a Overlap detection for parallel work | 🟡 | `hooks/locks.py` + non-overlapping `files_owned` + `reconciler` | file-path based, not call-graph based |
| C5.b Canonical front→back map (FE→BE seam) | 🟡 | `INTEGRATION_MAP` + `INTERACTION_INTUITION_MAP` | stops at endpoint boundary; the `fetch()`→handler edge is never resolved to a function |
| C6.a Worktree vs in-place | ✅* | v1.2.0 auto-worktree default + `--no-worktree` + re-entry detect | *fixed default, not a task-aware heuristic |
| C6.b Always merge to main / no loose branches | ✅ | **v3.7.0 auto-merge + v1.3.0 cleanup + startup reconciliation** | only squash-merges not auto-detected (safe default) |
| C7 Supervisory lifecycle agent | ❌ | orchestrator + phases; `test-run-monitor` is passive | no dedicated lifecycle/PM agent (author: future) |

**Already shipped — do not rebuild:** the C6 worktree/merge discipline (transcript lines ~223–244) is implemented at v3.7.0 + v1.3.0; C1.a (Playwright replication) is fully operational. **Reuse, don't reinvent:** the `code-path-witness.json` mechanism (executed-handler capture) already exists and is the cornerstone of REQ-DOC-06.

---

## 4. Guiding architectural proposal — the Code & Data Lineage Graph (CDLG)

Clusters **C1, C2, C3, C4, C5 are the same primitive** wearing different hats: a persisted, queryable graph of `functions ↔ endpoints ↔ data assets`. Build it once; the rest become thin consumers.

- **Nodes:** `function`, `endpoint`, `data_asset`.
- **Edges:** `calls` / `called_by`, `reads` / `writes` / `modifies`, `serves` (endpoint→function), `originates` (asset genesis), `serves_route` (FE call-site → endpoint, the inter-service seam).
- **Built on-demand, subset-first** — the bug's pages→APIs define the trace subset (cost control); persist and reuse.
- **Two-layer extraction (the hard part is split, not hand-waved):**
  - **Intra-service** (within one language/service): cheap static seeding — **prefer a per-language LSP `callHierarchy` / `references` query, or tree-sitter/ctags where no LSP exists** (reuse-first; see §9.2) — refined by an LLM tracer only where static resolution is ambiguous (dynamic dispatch, DI, reflection, ORM lazy-loading).
  - **Inter-service** (FE → BE, service → service, producer → queue → consumer): this is **route/contract matching, NOT call-graph traversal** — an HTTP call is not a function edge. Resolve `fetch('/api/x')` → the route handler by matching against the route table, reusing `INTEGRATION_MAP` + `INTERACTION_INTUITION_MAP` (already confirmed by the user at Phase −1D) as priors. Distinct technique, distinct reliability, reported separately. (REQ-DOC-07)
- **Trust by grounding, not by construction:** every extracted subgraph is **reconciled against the runtime execution witness** (`code-path-witness.json`) captured during replication — the static graph's claimed-executed edges must match what actually fired; missed or hallucinated edges in the bug subset are graph defects to resolve **before diagnosis trusts the graph.** (REQ-DOC-06)
- **Storage** — human view (`ENDPOINT_TRACE_MAP.md`, `DATA_LINEAGE_MAP.md`: markdown + **depth/size-capped** mermaid call-trees + in-file datestamp) **plus** a machine sidecar (`lineage-graph.json`). Full machine detail lives in the JSON; mermaid stays legible.
- **Identity nomenclature** — `func://<codebase>/<path>#<qualified_name>` and `asset://<store>/<schema>/<table>`, with explicit rules for overloads, methods-vs-free-functions, closures/anonymous functions, and a **rename-stability fallback** (AST-path or content-hash) so the join key survives refactors. (REQ-MEM-02)
- **Freshness — transitive, not per-file:** a node is stale if **any node reachable in its subtree** changed since `last_mapped` (graph reachability over `git log`), not just the endpoint's own file. Refresh under the Phase 8 `documentation-currency` gate. (REQ-DOC-04)
- **Concurrency:** `lineage-graph.json` is shared mutable state — written **only by the orchestrator** (like `coverage-map.json` / `intake-state.json`) OR sharded per-subset with unique paths; never written concurrently by parallel teammates. (REQ-SAFE-01)
- **Cost:** every trace runs under a **hard token/time budget** with graceful depth-truncation (truncated subtrees marked, not silently dropped). (REQ-DOC-08)

Consumers: diagnosis walks the graph (C1); endpoint docs render it (C2); data lineage is its asset edges (C3); MemPalace lookup queries it at function granularity (C4); overlap detection asks "do two work-items share a subtree" (C5).

---

## 5. Requirements

Priority: **P1** must-have · **P2** should-have · **P3** nice-to-have. Status is relative to current CT6 (§3). **Acceptance criteria assert correctness, not mere existence** — an artifact that exists but is unvalidated does NOT satisfy its AC.

### 5.1 Bug-isolation methodology (REQ-DIAG)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-DIAG-01 | P1 | extend | **Scope-isolation gate.** After replication, enumerate the involved pages and subset to the exact endpoints used on them; freeze as the diagnosis scope. *AC:* a scope artifact lists pages + endpoint set; every later diagnostic step is bounded to it AND any step touching code outside the set is rejected. |
| REQ-DIAG-02 | P1 | extend | **Light diagnostic discriminant, run first — EXECUTED, not reasoned.** Before deep code analysis, make a **real authenticated call against the live dev environment** (same discipline as B1/B2) and assert whether data is returned; branch FE-bug vs API-bug. *AC:* a discriminant step precedes deep analysis and records an FE/API verdict backed by a captured request/response (a code-read verdict does NOT satisfy this — that is the "verified by reading the code" anti-pattern). |
| REQ-DIAG-03 | P1 | new | **Pre-diagnosis call-hierarchy.** Produce a nested call-pattern map (endpoint → functions → sub-functions, recursively) before hypothesis formation. *AC:* a call-tree artifact exists, is **reconciled against the runtime witness for the executed slice** (REQ-DOC-06), carries zero unresolved/hallucinated edges in the bug subset, and is cited by the diagnostic step. |
| REQ-DIAG-04 | P1 | reuse+extend | **Data-source existence check.** Backtrack the function + parameters into the table/store and verify whether the data lives at source. *AC:* diagnosis cites the specific data-layer node (`asset://…`) and a present/absent verdict **with the query/evidence that produced it** (consumes REQ-DIAG-03). |
| REQ-DIAG-05 | P1 | new | **Reordered pipeline.** `bug-fix-pipeline` order becomes: replicate → scope-isolate → light-discriminant → call-map → diagnose. *AC:* the run ledger shows the cheap checks (scope, discriminant) completed and recorded BEFORE any deep-analysis subagent dispatch; out-of-order execution is a gate failure. |

### 5.2 Endpoint documentation & graph extraction (REQ-DOC)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-DOC-01 | P1 | new | **Per-endpoint deep docs.** Document each in-scope endpoint's internal recursive function-call pattern. *AC:* `ENDPOINT_TRACE_MAP.md` per codebase with per-endpoint call trees, each **runtime-verified** (REQ-DOC-06) for the slice that the replication exercised. |
| REQ-DOC-02 | P2 | extend | **Mandated post-deploy construction.** At the end of every dev+deploy cycle, (re)build endpoint docs for touched endpoints; enforced by a dedicated skill at the Phase 8 `documentation-currency` gate. *AC:* the Phase 8 gate refreshes endpoint docs for every changed endpoint; a stale touched-endpoint doc blocks the commit (same shape as the existing doc-currency audit). |
| REQ-DOC-03 | P1 | extend | **Build-if-missing gate.** If the endpoint depth-map is absent, build it before bug-fix deep diagnosis proceeds. *AC:* the pipeline blocks deep diagnosis until the relevant endpoint map exists AND passes its runtime-verification threshold. |
| REQ-DOC-04 | P2 | extend | **Transitive freshness.** A node is stale if any node reachable in its subtree changed since the map's `last_mapped` (graph reachability over `git log`), not only the endpoint's own file. *AC:* a callee-only change three levels down marks the endpoint's trace stale and triggers a targeted re-trace of the affected subtree. |
| REQ-DOC-05 | P2 | extend | **Storage standard.** markdown + depth/size-capped mermaid call-trees + in-file datestamp + stable greppable `func://` names; cached and incrementally updated. *AC:* artifacts contain mermaid (within the REQ-DOC-08 size cap) + in-file timestamp; re-runs reuse cache; full detail is recoverable from `lineage-graph.json`. |
| REQ-DOC-06 | **P1** | **new** | **Runtime-grounded graph verification (the trust gate).** Reconcile the extracted CDLG subset against the `code-path-witness.json` captured during replication: every edge the static/LLM trace claims executed must appear in the witness, and every witnessed handler must appear in the graph. *AC:* a verification report records **edge recall** (witnessed edges present in the graph) and **hallucination rate** (graph edges asserting execution that the witness did not fire); diagnosis MUST NOT consume a subgraph below the configured recall threshold or above the hallucination ceiling — it re-traces or escalates instead. This is also the P1 spike's kill-gate metric (§6, §7). |
| REQ-DOC-07 | **P1** | **new** | **Inter-service edge resolution (the FE→BE seam).** Resolve cross-service edges (FE `fetch`/client call → route handler; service→service; producer→queue→consumer) by route/contract matching — explicitly NOT call-graph traversal — reusing `INTEGRATION_MAP` + the user-confirmed `INTERACTION_INTUITION_MAP` as priors. *AC:* `serves_route` edges are produced with their match basis (route pattern / contract) and a confidence; unresolved seams are surfaced (never silently bridged), and their reliability is reported separately from intra-service edges. |
| REQ-DOC-08 | P2 | new | **Cost ceiling + graceful degradation.** Every trace runs under a hard token/time budget; on exhaustion the tree is depth-truncated with explicit `truncated: true` markers (never silently dropped), and mermaid renders are node/depth-capped. *AC:* a trace that would exceed budget terminates with a partial, clearly-marked graph + a recorded budget-exhaustion note — mirroring the existing global iteration-ceiling discipline. |

### 5.3 Data lineage (REQ-DATA)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-DATA-01 | P1 | extend | **Data-model decomposition in the diagnostic flow.** When a trace reaches data, pull schemas/contents, summarize, examine joins/merges (in/out of DB). *AC:* available outside the Phase 0c data-eng path (bug-fix + feature flows), with the decomposition cited by the data-source check (REQ-DIAG-04). |
| REQ-DATA-02 | P2 | new | **Per-asset population tracking.** Record how each data asset is populated and by which functions. *AC:* `DATA_LINEAGE_MAP.md` records population sources per asset, each traceable to a `func://` node in `lineage-graph.json`. |
| REQ-DATA-03 | P1 | new | **Data-asset graph.** Per asset: which functions read / write / modify it, and how it originates. *AC:* `reads`/`writes`/`modifies`/`originates` edges present in `lineage-graph.json`, with edges to executed code reconciled against the runtime witness where the replication exercised them (REQ-DOC-06). |
| REQ-DATA-04 | P2 | new | **Dedicated skill.** A `data-lineage-mapping` skill maintains the above, after a reuse-first check against `data-engineering-exploration` Stage 2/6 (extend rather than duplicate where possible). *AC:* skill exists, is invoked by the relevant phases, and its design.md carries a Reuse Decision vs the existing data-eng skill. |

### 5.4 MemPalace function lineage (REQ-MEM)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-MEM-01 | P1 | new | **Function-level lineage records.** Store the CDLG so a function lookup returns upstream callers, downstream callees, and data sources. *AC:* query a `func://` ID → callers / callees / data-sources; records are bounded to the mapped subset (no whole-repo explosion). |
| REQ-MEM-02 | P1 | new | **Stable identity nomenclature (the join key).** A documented function/asset ID convention (`func://…`, `asset://…`) that is load-bearing for MemPalace dedup AND graph diffing. *AC:* the spec defines handling for overloads, methods vs free functions, generics/templates, and closures/anonymous functions, AND a **rename-stability strategy** (AST-path or content-hash fallback) so a refactor that renames a function does not orphan its history or accumulate duplicate records. A round-trip test demonstrates ID stability across a rename + a move. |

### 5.5 Parallelism & overlap (REQ-PARA)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-PARA-01 | P2 | extend | **Call-graph overlap detection.** Derive work-item overlap from the CDLG (shared callees/subtrees), not only file paths; feed the parallel-execution graph + `hooks/locks.py`. *AC:* the overlap verdict considers shared `func://` nodes, not just `files_owned`; two items that edit different files but share a hot callee are flagged as overlapping. |
| REQ-PARA-02 | P2 | extend | **Canonical front→back traversal.** Chain UI element → endpoint → function tree → data asset into one navigable traversal, built on the REQ-DOC-07 inter-service resolution. *AC:* a single validated traversal from a UI control (an `INTERACTION_INTUITION_MAP` element) to a `data_asset` exists for at least the bug subset, with the FE→BE hop carrying its match basis + confidence. |

### 5.6 Cross-cutting safety, cost & measurement (REQ-SAFE)

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-SAFE-01 | **P1** | **new** | **Graph write-ownership.** `lineage-graph.json` and the trace maps follow CT6's shared-state model: written only by the orchestrator between subagent dispatches, OR sharded per-subset with unique paths, never concurrently mutated by parallel teammates. *AC:* no code path lets two teammates write the same graph file; concurrent runs against the same subset are serialized or shard-isolated (parallels the existing `coverage-map.json` rule). |
| REQ-SAFE-02 | **P1** | **new** | **Success-metric instrumentation.** The pipeline records the §6 metrics per bug-fix run so before/after is measurable. *AC:* each run emits `dev_loop_iterations`, first-pass-fix outcome, oscillation/`bug-still-present`/`fix-regression` counts, the FE/API discriminant verdict vs the layer actually fixed, and the REQ-DOC-06 recall/hallucination numbers — to a queryable location (MemPalace run-history + the run ledger). |

### 5.7 Worktree & merge discipline (REQ-WT) — largely already implemented

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-WT-01 | P1 | ✅ done | **Always merge to main / no loose branches.** *AC:* satisfied by v3.7.0 auto-merge + v1.3.0 cleanup; the benchmark run (§6) verifies no regression. |
| REQ-WT-02 | P3 | polish | **Task-aware worktree heuristic** (vs fixed always-on default). *AC:* worktree choice can vary by task scope/size with a documented rule + `--no-worktree` still honored. |
| REQ-WT-03 | P3 | polish | **Squash-merge detection** in cleanup. *AC:* squash-merged branches are recognized as merged (closes the documented v1.3.0 false-negative) without introducing a false-positive that deletes unmerged work. |

### 5.8 Supervisory lifecycle (REQ-SUP) — future

| ID | Priority | Status | Requirement & acceptance criteria |
|---|---|---|---|
| REQ-SUP-01 | P3 | future | **Supervisory agent for project lifecycle / PM techniques.** *AC:* TBD; out of immediate scope. |

---

## 6. Success metrics

The upgrade is a High-risk, multi-phase investment; it MUST be justified by measured outcomes, not faith. All metrics use counters CT6 already records (REQ-SAFE-02 wires them).

**Enabler — the frozen bug benchmark.** Assemble a fixed corpus of **N reproducible bugs** (replayed from CT6 run-history already mined to MemPalace). Run the baseline (current CT6) once; re-run after each phase. Without a frozen corpus, before/after is noise.

| Tier | Metric | Target / direction | Source |
|---|---|---|---|
| **Primary** | Median `dev_loop_iterations` (Phase 2→5 loops) per **verified** bug fix | **≥ 30% reduction** vs baseline | `intake-state.json` counter |
| **Guard (must hold or improve)** | First-pass fix rate — 1st proposed fix reaches `bug-resolved` at qa-replay | ↑ or unchanged | qa-replayer verdicts |
| **Guard** | `oscillation` trips + `bug-still-present` + `fix-regression` counts | ↓ or unchanged | hooks + qa-replayer |
| **Guard** | Wrong-layer rate — discriminant said FE but fix was API (or vice-versa) | ↓ | REQ-DIAG-02 verdict vs layer fixed |
| **Leading** | CDLG subset fidelity — edge recall ↑ / hallucination rate ↓ vs the runtime witness | meets the REQ-DOC-06 threshold | `code-path-witness.json` reconciliation |
| **Leading** | Cost per trace within budget; cache-hit rate on repeat traces | within REQ-DOC-08 budget | trace budget accounting |

**Headline number:** *median Phase 2→5 iterations per verified bug fix, on the frozen benchmark, with first-pass-correct rate held or improved.* The guards exist so the primary cannot be won by shipping faster wrong fixes. The primary target (≥30%) is a starting proposal — confirm in §9.

---

## 7. Phased roadmap

| Phase | Deliverable | Consumes → Produces | Effort | Risk | Depends on | Requirements |
|---|---|---|---|---|---|---|
| **P0 — Quick wins (standalone value)** | Reorder `bug-fix-pipeline`: scope-isolation + EXECUTED light-discriminant gates (orchestration only, existing maps). **Ships value even if P1 is abandoned.** | ROUTE/INTEGRATION maps → tighter, layer-correct diagnosis | S | Low | — | DIAG-01, DIAG-02, DIAG-05 |
| **P0.5 — Benchmark baseline** | Assemble the frozen N-bug corpus; wire REQ-SAFE-02 instrumentation; record the pre-CDLG baseline for §6 | run-history → baseline metrics | S | Low | — | SAFE-02 |
| **P1 — CDLG foundation (KILL-GATED SPIKE)** | New skill `endpoint-trace-mapping` + agent `endpoint-tracer`; `ENDPOINT_TRACE_MAP.md` + `lineage-graph.json`; two-layer extraction; runtime-witness verification; subset+cache+transitive-freshness; budget. **Spike first on 2 real polyglot targets; proceed only if the kill-gate passes (§7.1).** | code subset → runtime-verified call graph | L | **High** | P0, P0.5 | DOC-01/03/04/05/06/07/08, DIAG-03, MEM-02, SAFE-01 |
| **P2 — Diagnosis rewire** | Call-map gate; `diagnostic-research-team` reads the verified CDLG instead of re-tracing | verified CDLG → ranked hypotheses | M | Med | P1 | DIAG-03, DIAG-04 |
| **P3 — Data lineage** | `data-lineage-mapping` skill + agent (reuse-first vs data-eng Stage 2/6); asset edges; data decomposition in the bug flow | CDLG + schemas → `DATA_LINEAGE_MAP.md` | M | Med | P1 | DATA-01/02/03/04 |
| **P4 — Overlap + canonical map** | Extend parallel-execution-graph + `team-spawning-and-review-gates` + `hooks/locks.py` to consult the CDLG | CDLG → overlap verdicts | M | Med | P1 | PARA-01, PARA-02 |
| **P5 — MemPalace granularity** | New record type + stable function-ID nomenclature; mine `lineage-graph.json` | CDLG → MemPalace records | M | Med | P1 | MEM-01, MEM-02 |
| **P6 — Polish C6** | Task-aware worktree heuristic; squash-merge detection | — | S | Low | — | WT-02, WT-03 |
| **P7 — Supervisory lifecycle** (future) | Lifecycle/PM agent over runs | — | L | — | later | SUP-01 |

**Critical path:** P0 + P0.5 (ship now, independent) → P1 spike (kill-gated) → P2–P5 (parallelizable, ALL gated on P1 passing). P6 is independent and tiny. **P0 is deliberately decoupled** so the user gets a measurable win before committing to the High-risk foundation.

### 7.1 P1 kill-gate (abandon criteria)

Before building P2–P5 on the CDLG, the P1 spike must clear, on ≥ 2 real polyglot target repos from the benchmark:

- **Fidelity:** runtime-witness **edge recall ≥ R** and **hallucination rate ≤ H** on the bug subset (R, H set in §9 — proposed R ≥ 0.9, H ≤ 0.05).
- **Cost:** median trace within the REQ-DOC-08 budget, cache-hit ≥ C on repeat traces.
- **Seam:** REQ-DOC-07 resolves ≥ S% of FE→BE edges in the subset with stated confidence (unresolved surfaced, not bridged).

If the spike misses the gate, **stop at P0/P0.5** (which still deliver value) and revisit extraction strategy (§9.2) rather than pour effort into P2–P5 on an untrustworthy graph.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Untrustworthy graph → confidently-wrong diagnosis** (the core risk) | Ground every consumed subgraph against the runtime witness (REQ-DOC-06); diagnosis refuses a sub-threshold graph. This is what converts an LLM artifact into a verified one. |
| **FE→BE / inter-service seam** (an HTTP call is not a function edge) | Treat as a separate route/contract-matching sub-problem (REQ-DOC-07) reusing `INTEGRATION_MAP` + `INTERACTION_INTUITION_MAP`; report seam reliability separately; never silently bridge. |
| **Polyglot intra-service extraction** (make-or-break) | LSP-first static seed (reuse-first) + LLM-refine only on ambiguity, strictly bounded to the bug subset, persisted, kill-gated at P1 (§7.1). |
| **Cost / scale of full graphs** | Subset-on-demand + cache + incremental (changed-subtree) update + hard per-trace budget with marked truncation (REQ-DOC-08). |
| **Staleness (including transitive)** | Graph is a documentation-currency artifact refreshed at Phase 8; freshness is subtree-reachability based, not per-file (REQ-DOC-04). |
| **Concurrent corruption of the graph sidecar** | Orchestrator-serialized or per-subset-sharded writes (REQ-SAFE-01), matching the existing `coverage-map.json` rule. |
| **MemPalace record explosion / refactor churn** | Bound records to the mapped subset; stable, rename-resilient function-ID nomenclature keeps them diffable/dedupable (REQ-MEM-02). |
| **Investment unjustified** | §6 success metrics + the frozen benchmark make the payoff measurable before P2–P5 commitment. |

---

## 9. Open decisions (owner input required before implementation)

1. **Locus** — confirm these are CT6 skills/agents that *produce artifacts inside target codebases* (assumed), not changes to a single application.
2. **Extraction strategy (reuse-first lens)** — the recommended static layer is **per-language LSP `callHierarchy` first, tree-sitter/ctags fallback, LLM only on ambiguity**. Confirm this vs pure-LLM vs static-only. (CT6's own `reuse-first-design` argues for leaning on mature LSP tooling before building an LLM tracer.)
3. **Sequencing** — ship P0 + P0.5 quick-wins first (recommended) while speccing P1, vs foundation-first.
4. **Kill-gate thresholds** — confirm R (edge recall ≥ 0.9?), H (hallucination ≤ 0.05?), C (cache-hit), S (seam-resolution %), and the §6 primary target (≥ 30% iteration reduction?).
5. **Mechanization** — promote this document to an OpenSpec change (`openspec/changes/<name>/`) and drive P0 + P0.5 through `/architect-team:mini` (P0 touches the plugin's own `bug-fix-pipeline` skill body + needs the structural test suite green)?

---

## 10. Out of scope / already implemented

- **C6 worktree + merge discipline** — implemented (v3.7.0 auto-merge-and-prune, v1.3.0 merged-worktree sweep, startup branch reconciliation). Only optional polish remains (REQ-WT-02/03).
- **C1.a Playwright replication** — fully operational today.
- **The runtime execution witness** (`code-path-witness.json`) — already exists; REQ-DOC-06 *reuses* it for graph grounding rather than building new capture.
- **C7 supervisory lifecycle** — deferred (author flagged as future).
