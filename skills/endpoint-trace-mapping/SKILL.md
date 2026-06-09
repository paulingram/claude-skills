---
name: endpoint-trace-mapping
description: Use when the endpoint-tracer agent is producing a per-endpoint internal call-trace for an in-scope endpoint subset, or when any phase needs to consult or build the Code & Data Lineage Graph (CDLG). Defines ENDPOINT_TRACE_MAP.md + lineage-graph.json, the two-layer extraction contract (intra-service LSP-first static seed + LLM-refine on ambiguity; inter-service route/contract matching reusing INTEGRATION_MAP + INTERACTION_INTUITION_MAP), the func:// / asset:// identity nomenclature, runtime-witness verification against code-path-witness.json (the trust gate), subset-on-demand + transitive freshness + the cost ceiling. The deterministic pieces live in hooks/lineage_graph.py.
---

# Endpoint Trace Mapping (the CDLG foundation)

CT6 reliably **finds and replicates** bugs but is weaker at **logically isolating**
them: diagnosis discovers the relevant code path *while theorizing* rather than
laying out the call/data structure first and reasoning against a known map. This
skill closes that gap. It produces, for an in-scope endpoint subset, a nested
internal call-trace (endpoint → functions → sub-functions, recursively) plus a
machine-readable graph sidecar — the **Code & Data Lineage Graph (CDLG)** — and
**grounds every consumed subgraph against executed reality** before diagnosis is
allowed to trust it.

Source of truth for the schema, the identity nomenclature, witness
reconciliation, transitive freshness, and the cost ceiling: **`hooks/lineage_graph.py`**
(stdlib-only, deterministic, unit-tested). This skill is the *contract*; that
module is the *machine*. Requirements: `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`
§4 (CDLG) + REQ-DOC-01/03/04/05/06/07/08, REQ-DIAG-03, REQ-MEM-02, REQ-SAFE-01.

## The honest boundary — what is deterministic vs what is the agent's runtime job

This is a two-part deliverable, and the split is deliberate (not hand-waved):

- **Deterministic, in `hooks/lineage_graph.py` (testable, no LLM):** the graph
  schema + `validate_lineage_graph`, the `func://` / `asset://` ID
  make/parse/fingerprint helpers, `reconcile_with_witness` + `witness_gate`,
  `transitive_stale_nodes` / `is_node_stale`, `truncate_to_budget` and the
  `MERMAID_MAX_NODES` / `MERMAID_MAX_DEPTH` constants.
- **The agent's runtime job (live, polyglot, not unit-testable here):** the
  actual extraction — running the per-language LSP, reading code, refining
  ambiguous edges with an LLM, matching FE call-sites to routes. The
  `endpoint-tracer` agent does this against the live target codebase and emits a
  graph that conforms to the module's schema.

Do not pretend the live extraction is deterministic, and do not re-implement the
deterministic pieces in prose — call the module.

## Artifacts

### `ENDPOINT_TRACE_MAP.md` (the human view)

Path: `<codebase>/docs/ENDPOINT_TRACE_MAP.md`. YAML frontmatter (required):

```yaml
---
last_traced: 2026-06-08T10:30:00Z   # ISO 8601 UTC, set at write time (in-file datestamp)
codebase: /abs/path/to/service
scope_subset: ["GET /api/users", "POST /api/matters"]   # the in-scope endpoint set
witness_verified: true              # did the consumed subset pass the REQ-DOC-06 gate?
---
```

Body — per in-scope endpoint:

- A prose summary of the endpoint's internal recursive function-call pattern.
- A **depth/size-capped mermaid** call-tree (within `MERMAID_MAX_NODES` /
  `MERMAID_MAX_DEPTH` — see the cost ceiling below). Truncated subtrees are
  marked `... (truncated: N more)`, never silently dropped.
- The greppable `func://` ids for each node so a reader can join to
  `lineage-graph.json`.
- The runtime-verification line: edge recall + hallucination rate vs the witness,
  and the pass/fail gate verdict.

Full machine detail lives in the JSON; the mermaid stays legible (REQ-DOC-05).

### `lineage-graph.json` (the machine sidecar)

The CDLG itself, conforming to the `hooks/lineage_graph.py` schema
(`schema_version: 1`):

- **Nodes** — `kind` ∈ {`function`, `endpoint`, `data_asset`}, each with an `id`
  (the `func://` / `asset://` / `endpoint://` nomenclature), and `path` / `name`.
- **Edges** — `kind` ∈ {`calls`, `reads`, `writes`, `modifies`, `serves`,
  `originates`, `serves_route`}, each optionally carrying `executed`,
  `match_basis`, `confidence`.
- Every produced graph MUST pass `validate_lineage_graph(graph) == []` before it
  is written. `serves_route` edges (the FE→BE seam) MUST carry a `match_basis`.

Write-ownership (REQ-SAFE-01): `lineage-graph.json` is shared mutable state — it
is written **only by the orchestrator** between subagent dispatches, OR sharded
per-subset with unique paths. Parallel teammates NEVER write the same graph file
concurrently (the same rule as `coverage-map.json` / `intake-state.json`).

## The two-layer extraction contract (REQ-DOC-07)

The hard part is split, not glossed over. An HTTP call is **not** a function
edge, so the two layers use different techniques with different reliability and
are **reported separately**:

### Intra-service (within one language/service)

- **LSP-first static seed (reuse-first):** prefer a per-language LSP
  `callHierarchy` / `references` query; fall back to tree-sitter / ctags where no
  LSP exists. This cheaply seeds `calls` / `serves` edges.
- **LLM-refine only on ambiguity:** dynamic dispatch, dependency injection,
  reflection, ORM lazy-loading — where static resolution is genuinely ambiguous,
  the tracer refines with an LLM read. Do not LLM-trace what the LSP already
  resolved.

### Inter-service (FE → BE, service → service, producer → queue → consumer)

This is **route/contract matching, NOT call-graph traversal.** Resolve
`fetch('/api/x')` → the route handler by matching against the route table,
reusing `INTEGRATION_MAP` + `INTERACTION_INTUITION_MAP` (already confirmed by the
user at Phase −1D) as priors. Each resolved edge is a `serves_route` edge
carrying its `match_basis` (route pattern / contract) and a `confidence`.
**Unresolved seams are surfaced, never silently bridged**, and their reliability
is reported separately from intra-service edges.

## Runtime-witness verification (REQ-DOC-06) — the trust gate

The CDLG is **not trusted by construction** — that is the exact failure mode CT6
was built to refuse (VAO / producer-checker / "testing must be EXECUTED, not
described"). Every extracted subgraph is reconciled against the runtime execution
witness CT6 already captures during replication.

- **Reuse, don't rebuild:** the `code-path-witness.json` mechanism (executed-
  handler capture, v0.9.31/0.9.32) ALREADY EXISTS. This skill *consumes* it; it
  does not build new capture.
- Call `reconcile_with_witness(graph, witness_executed_edges)` (from
  `hooks/lineage_graph.py`) where `witness_executed_edges` is the set of
  `(src, dst)` the witness observed firing. It returns `edge_recall`,
  `hallucination_rate`, `missing_edges`, `hallucinated_edges`, and the two
  counts.
- Gate with `witness_gate(reconciliation, recall_threshold=0.9,
  hallucination_ceiling=0.05)`. **Diagnosis MUST NOT consume a subgraph that
  fails the gate** — below the recall threshold or above the hallucination
  ceiling, the tracer re-traces the missed/hallucinated edges or escalates. It
  never trusts the graph anyway.
- This is also the P1 spike's kill-gate metric (`docs/LINEAGE_UPGRADE_REQUIREMENTS.md`
  §7.1): on ≥ 2 real polyglot targets, edge recall ≥ R and hallucination ≤ H, or
  the foundation is abandoned at P0/P0.5.

## Subset-on-demand, transitive freshness, and the cost ceiling

- **Subset-first (cost control):** the bug's pages → APIs define the trace
  subset. Do not trace the whole repo; trace the in-scope endpoint set, persist,
  and reuse. Build-if-missing (REQ-DOC-03): if the depth-map is absent, build it
  before deep diagnosis proceeds — and only consume it once it passes the
  witness gate.
- **Transitive freshness (REQ-DOC-04):** a node is stale if **any node reachable
  in its `calls` / `serves` subtree** changed since `last_traced` — not just the
  endpoint's own file. Use `transitive_stale_nodes(graph, changed_paths)` (where
  `changed_paths` comes from `git log` since `last_traced`). A callee-only change
  three levels down marks the endpoint's trace stale and triggers a targeted
  re-trace of the affected subtree, under the Phase 8 `documentation-currency`
  gate.
- **Cost ceiling (REQ-DOC-08):** every trace runs under a hard token/time budget.
  On exhaustion the tree is depth-truncated with explicit `truncated: true`
  markers — use `truncate_to_budget(node_ids, MERMAID_MAX_NODES)` which returns
  `(kept, truncated_flag)` and *marks* truncation rather than dropping silently.
  Mermaid renders are node/depth-capped (`MERMAID_MAX_NODES` /
  `MERMAID_MAX_DEPTH`).

## Identity nomenclature (REQ-MEM-02) — the load-bearing join key

The CDLG join key (load-bearing for MemPalace dedup AND graph diffing):

- **Functions:** `func://<codebase>/<path>#<qualified_name>` with an optional
  `~<disambiguator>` suffix for overloads / closures / anonymous functions. Build
  with `make_func_id(...)`, parse with `parse_func_id(...)` (round-trips
  exactly).
- **Data assets:** `asset://<store>/<schema>/<table>`. Build with
  `make_asset_id(...)`, parse with `parse_asset_id(...)`.
- **Rename-stability fallback:** `stable_func_key(qualified_name, source)` returns
  `fp:<content_fingerprint>` — a body-derived key that is INVARIANT under a
  rename (body unchanged → same key) but CHANGES when the body changes. This is
  the fallback that keeps a renamed-but-unchanged function's history and graph
  identity intact instead of orphaning it. `content_fingerprint(source)` is
  whitespace-invariant (two bodies differing only in surrounding whitespace
  fingerprint identically).

## What "complete" means for review

An `ENDPOINT_TRACE_MAP.md` + `lineage-graph.json` pair is complete when:

1. `validate_lineage_graph(graph) == []` (schema valid; `serves_route` edges
   carry a `match_basis`).
2. Every in-scope endpoint in `scope_subset` has a call-tree in both artifacts.
3. The consumed subset passes `witness_gate` against `code-path-witness.json`
   (recall ≥ threshold, hallucination ≤ ceiling) — or the failing edges are
   surfaced for re-trace, and `witness_verified` reflects reality.
4. Inter-service `serves_route` edges carry a `match_basis` + `confidence`;
   unresolved seams are surfaced, not bridged.
5. The mermaid render is within the size cap, with any truncation marked.
6. `last_traced` is set at write time; full detail is recoverable from the JSON.
