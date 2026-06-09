---
name: data-lineage-mapping
description: Use when a diagnostic or feature trace reaches data and the asset-lineage layer of the Code & Data Lineage Graph (CDLG) must be produced or consulted — the bug/feature-flow-facing per-asset lineage that records which functions read / write / modify / originate each data asset, and how each asset is populated. Produces DATA_LINEAGE_MAP.md (human view) + the asset edges (reads / writes / modifies / originates) in lineage-graph.json, keyed by the asset:// nomenclature, joined to func:// nodes. Makes data-model decomposition available in the bug-fix and feature flows (not only Phase 0c). The deterministic graph pieces live in hooks/lineage_graph.py; this skill is the asset-lineage contract that layers on top of endpoint-trace-mapping. A reuse-first layer over data-engineering-exploration Stage 2/6 — the warehouse-design layer — not a duplicate of it.
---

# Data Lineage Mapping (the CDLG asset-lineage layer)

When a diagnostic trace (or a feature build) reaches **data**, the question stops
being "which function ran" and becomes "does the data live at source, who
populated it, and which functions read / write / modify it." This skill produces
the **asset half** of the Code & Data Lineage Graph (CDLG): per-asset lineage —
`reads` / `writes` / `modifies` / `originates` edges between `func://` nodes and
`asset://` nodes — plus a human-readable `DATA_LINEAGE_MAP.md` that records, for
each data asset, its schema/contents summary and the functions that populate it.

It is the data-plane counterpart to `endpoint-trace-mapping`: that skill builds
the call-hierarchy (functions ↔ endpoints); this one extends the SAME graph with
the data-asset nodes and edges so a trace can backtrack a function + its
parameters into the table/store and answer the data-source existence check
(REQ-DIAG-04). It makes the data-model decomposition — historically available
only in the Phase 0c `data-engineering-exploration` path — **available in the
bug-fix and feature flows**.

Source of truth for the graph schema, the `func://` / `asset://` identity
nomenclature, witness reconciliation, transitive freshness, and the cost ceiling:
**`hooks/lineage_graph.py`** (stdlib-only, deterministic, unit-tested). This skill
is the *contract*; that module is the *machine* — do not re-implement the
deterministic pieces in prose, call the module. Requirements:
`docs/LINEAGE_UPGRADE_REQUIREMENTS.md` §4 (CDLG) + REQ-DATA-01/02/03/04,
REQ-DIAG-04, REQ-MEM-02, REQ-SAFE-01.

## Reuse Decision — vs `data-engineering-exploration` Stage 2/6 (MANDATORY, REQ-DATA-04)

CT6's `reuse-first-design` discipline applies to this skill itself: before
building anything, the existing `data-engineering-exploration` skill already does
data-model and lineage work, so this skill must **extend / reuse rather than
duplicate** it. The reuse-first decision is explicit and load-bearing — the two
skills occupy DIFFERENT layers and the boundary is deliberate:

| Axis | `data-engineering-exploration` Stage 2/6 (the warehouse-design layer) | `data-lineage-mapping` (this skill — the bug/feature-flow-facing asset-lineage layer) |
|---|---|---|
| When it runs | Phase 0c only — a 7-stage exploration pipeline for data-engineering *asks* (dbt / Airflow / Snowflake / Kafka / lakehouse design) | The bug-fix and feature flows — whenever a diagnostic or feature trace reaches data and needs per-asset lineage on the fly |
| What Stage 2 produces | `CONCEPTUAL_DATA_MODEL.md` — entities + relationships + business rules + SCD strategy for a warehouse being *designed* | The asset's schema/contents *as it exists in the running system*, summarized for a trace — not a designed conceptual model |
| What Stage 6 produces | `DATA_VALIDATION_LINEAGE_MAP.md` — per-transformation validation rules + OpenLineage / Marquez / DataHub emission for a *warehouse pipeline's* table/column lineage | `DATA_LINEAGE_MAP.md` — per-asset `reads` / `writes` / `modifies` / `originates` edges in `lineage-graph.json`, keyed by the `func://` functions in the live codebase that touch the asset |
| Granularity | Warehouse entities + transformations (dbt models, DAG tasks, stream processors) | Source-code functions ↔ data assets (the CDLG join), reconciled against the runtime witness |
| Lineage substrate | External frameworks (OpenLineage / Marquez / DataHub / dbt-manifest) for a data platform | The CT6-native CDLG (`lineage-graph.json`) for an application codebase |

**Decision: extend, do not duplicate.** This skill REUSES — and does not
re-implement:

- **The CDLG graph machinery** from `hooks/lineage_graph.py` (the asset edges,
  the `asset://` nomenclature, `validate_lineage_graph`, the witness gate, the
  reachability/freshness walk, the cost ceiling). It does NOT define a second
  graph format.
- **The call-hierarchy** from `endpoint-trace-mapping` — the `func://` nodes this
  skill attaches asset edges to are the same nodes that skill already produced.
  This skill ADDS `data_asset` nodes + `reads` / `writes` / `modifies` /
  `originates` edges to the existing graph; it does not build a parallel one.
- **Stage 2's conceptual-decomposition technique** (schema summary, identifier
  semantics, join/merge analysis) is reused *as a method* when this skill
  decomposes an asset reached in a trace — but applied to the live store, in the
  bug/feature flow, at the moment a trace needs it, rather than as a Phase 0c
  warehouse-design deliverable.

When a run is genuinely a data-engineering *design* ask (a new warehouse, a dbt
project, a streaming topology), it routes to `data-engineering-exploration` at
Phase 0c — NOT here. When a bug-fix or feature trace reaches an existing data
asset and needs to know who populates it and whether the data is present, it
routes HERE. The reuse-first check is what keeps these from converging into one
bloated skill.

## Artifacts

### `DATA_LINEAGE_MAP.md` (the human view)

Path: `<codebase>/docs/DATA_LINEAGE_MAP.md`. YAML frontmatter (required):

```yaml
---
last_traced: 2026-06-08T10:30:00Z   # ISO 8601 UTC, set at write time (in-file datestamp)
codebase: /abs/path/to/service
asset_subset: ["asset://postgres/public/matters", "asset://postgres/public/persons"]
witness_verified: true              # did the consumed asset edges pass the REQ-DOC-06 gate?
---
```

Body — per in-scope data asset:

- The asset's `asset://<store>/<schema>/<table>` id (greppable, joins to
  `lineage-graph.json`).
- A **schema + contents summary** (columns / types / a contents sketch;
  joins/merges in or out of the store the asset participates in) — the data-model
  decomposition reached in the trace (REQ-DATA-01).
- **Per-asset population tracking (REQ-DATA-02):** the explicit list of `func://`
  functions that populate the asset (write / modify / originate it), each
  traceable to a node in `lineage-graph.json`. "Who fills this table, and from
  where" is answerable directly from this section.
- The reader/writer breakdown: which `func://` functions `reads` it, which
  `writes` it, which `modifies` it, and how it `originates`.
- The runtime-verification line for any asset edges that the replication
  exercised: edge recall + hallucination rate vs the witness + the gate verdict.

Full machine detail lives in the JSON; the human view stays legible (REQ-DOC-05).

### `lineage-graph.json` (the machine sidecar — the SAME CDLG)

This skill writes into the SAME `lineage-graph.json` the `endpoint-trace-mapping`
skill produces — it does not create a second file. It contributes:

- **`data_asset` nodes** — `kind: "data_asset"`, `id` is the
  `asset://<store>/<schema>/<table>` nomenclature (built with
  `make_asset_id(...)`, parsed with `parse_asset_id(...)`).
- **Asset edges** — `kind` ∈ {`reads`, `writes`, `modifies`, `originates`},
  connecting `func://` nodes to `asset://` nodes:
  - `reads` — a function reads the asset (a SELECT / GET / load).
  - `writes` — a function writes new rows/records into the asset (an INSERT / PUT).
  - `modifies` — a function changes existing records (an UPDATE / PATCH / DELETE).
  - `originates` — the asset's genesis: the function/migration/seed that brings
    the asset into existence (the `originates` edge is the population's root).

Every produced graph MUST pass `validate_lineage_graph(graph) == []` before it is
written. (The validator already enforces that every edge's `src` / `dst` resolve
to declared nodes and every `kind` is one of the seven canonical kinds — the four
asset kinds above are in `EDGE_KINDS`.)

Write-ownership (REQ-SAFE-01): `lineage-graph.json` is shared mutable state —
written **only by the orchestrator** between subagent dispatches, OR sharded
per-subset with unique paths. Parallel teammates NEVER write the same graph file
concurrently (the same rule as `coverage-map.json` / `intake-state.json`).

## Per-asset population tracking (REQ-DATA-02)

For each data asset in scope, the skill records **how it is populated and by which
functions**. The population sources are the union of the asset's `writes` /
`modifies` / `originates` edges in `lineage-graph.json`; the `DATA_LINEAGE_MAP.md`
renders them as an explicit per-asset "populated by" list so a diagnostician can
answer "if this row is wrong/missing, which functions could have produced it"
without re-tracing. Every population source is a `func://` node — traceable, and
keyed by the stable nomenclature so MemPalace can dedup it across runs (REQ-MEM-02).

## Data-model decomposition in the bug-fix + feature flows (REQ-DATA-01)

When a trace reaches data, this skill pulls the asset's schema/contents, summarizes
it, and examines the joins/merges it participates in (in or out of the store).
Crucially this is **available outside the Phase 0c data-eng path** — it runs in
the bug-fix flow (a diagnostic-research trace that backtracks to a table) and in
the feature flow (a build that needs to know an asset's shape). The decomposition
is the evidence the data-source existence check (REQ-DIAG-04) cites: diagnosis
names the specific `asset://…` node and a present/absent verdict, and the schema
+ contents summary produced here is what backs that verdict.

## Runtime-witness verification (REQ-DOC-06) — the trust gate

Asset edges to executed code are **grounded against executed reality**, not
trusted by construction — the same discipline `endpoint-trace-mapping` applies to
call edges. Where the replication exercised a `func://` → `asset://` interaction,
the edge is reconciled against the runtime execution witness
(`code-path-witness.json`) via `reconcile_with_witness(...)` and gated with
`witness_gate(...)` from `hooks/lineage_graph.py`. A subset that fails the gate is
re-traced or surfaced — diagnosis does not consume an ungrounded asset edge. Asset
edges that the replication did not directly exercise are recorded without an
`executed` claim (the witness only grounds control-flow that actually fired).

## Identity nomenclature (REQ-MEM-02) — the load-bearing join key

The asset join key (load-bearing for MemPalace dedup AND graph diffing):

- **Data assets:** `asset://<store>/<schema>/<table>`. Build with
  `make_asset_id(store, schema, table)`, parse with `parse_asset_id(...)`
  (round-trips exactly).
- **Functions** (the other side of every asset edge): the same
  `func://<codebase>/<path>#<qualified_name>` nomenclature
  `endpoint-trace-mapping` uses, with the `stable_func_key(...)` rename-stability
  fallback — so a renamed-but-unchanged populating function keeps its asset-edge
  history instead of orphaning it.

## What "complete" means for review

A `DATA_LINEAGE_MAP.md` + `lineage-graph.json` asset layer is complete when:

1. `validate_lineage_graph(graph) == []` (schema valid; every asset edge's
   `src` / `dst` resolve to declared nodes).
2. Every in-scope asset in `asset_subset` has a schema/contents summary in
   `DATA_LINEAGE_MAP.md` and an `asset://` node in `lineage-graph.json`.
3. Each in-scope asset records its population sources (the `writes` / `modifies` /
   `originates` edges) and its readers (the `reads` edges), every edge endpoint a
   `func://` node (REQ-DATA-02 / REQ-DATA-03).
4. Asset edges the replication exercised pass `witness_gate` against
   `code-path-witness.json`, or the failing edges are surfaced for re-trace, and
   `witness_verified` reflects reality.
5. The Reuse Decision above is honored — this skill consumed the existing CDLG
   machinery + call-hierarchy and did NOT duplicate `data-engineering-exploration`.
6. `last_traced` is set at write time; full detail is recoverable from the JSON.

## Where this skill plugs into the pipeline

- **`bug-fix-pipeline` diagnosis** — when a `diagnostic-research-team` trace
  reaches data, this skill supplies the asset-lineage layer the data-source
  existence check (REQ-DIAG-04) cites; the researchers consult the `asset://`
  node + its `reads` / `writes` / `modifies` / `originates` edges rather than
  re-deriving which functions touch the asset.
- **Feature flows** — when a build needs an existing asset's shape + population
  sources, this skill makes the data-model decomposition available without the
  full Phase 0c `data-engineering-exploration` pipeline.
- **`endpoint-trace-mapping`** — the sibling skill that produces the call half of
  the CDLG; this skill extends the SAME `lineage-graph.json` with the data-asset
  half.
- **`mempalace-integration`** — the `func://` and `asset://` nodes this skill
  records are mined into MemPalace's function-level lineage records, keyed by the
  stable nomenclature.
- **`documentation-currency` (Phase 8)** — `DATA_LINEAGE_MAP.md` is a
  documentation-currency artifact; it is refreshed (transitive freshness) when a
  populating function's subtree changes.
