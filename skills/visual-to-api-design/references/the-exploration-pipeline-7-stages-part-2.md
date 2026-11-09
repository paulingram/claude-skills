# The exploration pipeline (7 stages) (part 2)

### Stage 3b — Route<->persona map

**Goal:** construct the route inventory and cross-map every route to the personas it impacts. **Reuses `frontend-route-mapping` (ROUTE_MAP).**

**What it does:** builds the ROUTE_MAP via `frontend-route-mapping`, then annotates **each route with the personas it impacts** (drawn from the Stage 2 `PERSONA_MAP.md`). Every route in the ROUTE_MAP carries an `impacted_personas: [...]` annotation.

**Required output** (`stage-3b-route-persona-map.json`): the ROUTE_MAP with each route annotated `{route, ..., impacted_personas: [persona_id, ...]}`.

**Stage-3b CHECKLIST:** every route in the ROUTE_MAP has at least one impacted persona OR an explicit `impacted_personas: []` with a justification (e.g., a public/unauthenticated route); every persona in `PERSONA_MAP.md` is referenced by at least one route.

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-3B ROUTE-PERSONA COMPLETE — all reviewers agree every route is annotated with impacted personas". The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 3c — Reusable-component architecture → `COMPONENT_ARCHITECTURE_MAP.md` (NET-NEW)

**Goal (the single net-new stage):** propose a reusable-component architecture in the configured `language` + `component_libraries`, map every catalogued element 1:1 to a proposed component (100% coverage), record the exact per-page placement of each component, and declare each component's expected payload consumption. This is a **multi-agent (>=3) doc-passing task.**

**What it does:**

- **Proposes components in the configured `language` + `component_libraries`** (read from the brief/config per `### Run-time inputs`; absence escalates via a domain gate, never guessed).
- **Maps every catalogued element (from Stage 3a) to a proposed component — 100% coverage**, verified via a **`verify-every-element`-style check** (`hooks/vao_tools.py::verify-every-element` pattern, reused per RD-9): every element_id in the Stage 3a catalog appears in exactly one component's `covers_element_ids`. An uncovered element fails the stage.
- **Records the exact per-page placement of each component.** When design inputs exist (a DESIGN_MAP is present), placement is **pixel-perfect** (per-screen coordinates / asset placement). Otherwise it degrades to a **structural-placement** mode recording which page/region each component occupies (no pixel coordinates). The placement mode never blocks; it degrades.
- **Declares each component's expected payload consumption** — the data shape the component expects to render (which feeds Stage 5's per-page returns).

**Output doc:** `<codebase>/docs/COMPONENT_ARCHITECTURE_MAP.md`. Frontmatter `{generated_at, language, component_libraries[], elements_total, components_total, coverage}` per the canonical naming standard.

**Stage-3c CHECKLIST against Stage 3a:** the UNION of every component's `covers_element_ids` MUST equal the full set of element_ids in the Stage 3a catalog (100% coverage). Every component declares a `placement` (pixel-perfect or structural) and an `expected_payload`.

**ct6-converge workflow:** the >=3-agent doc-passing convergence is wrapped in the `ct6-converge` workflow with completion promise "STAGE-3C COMPONENT-ARCHITECTURE COMPLETE — all reviewers agree 100% element coverage + placement + payload". The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 4 — Conversion → OpenSpec via the openspec skill

**Goal:** convert the component-architecture conversion plan (Stages 3a–3c) into OpenSpec documents **using the openspec skill** — `openspec-propose` / `opsx:propose` — NOT hand-written JSON. >=3 agents in parallel; validate 100% conversion.

**What it does (stated explicitly):**

- **Invokes the openspec skill** (`openspec-propose` / `opsx:propose`) to author the conversion OpenSpec. The skill body NAMES the openspec skill explicitly; this stage does NOT hand-write OpenSpec JSON or spec files.
- **>=3 agents in parallel** each draft a slice of the conversion; they converge.
- **Validates 100% conversion** — a coverage check confirms 100% of the conversion plan (every page, every route, every component from Stages 3a/3b/3c) is represented in the produced OpenSpec artifacts. A plan item with no OpenSpec representation fails the stage.

**Required output** (`stage-4-openspec-conversion.json`): the openspec change name produced + a coverage manifest mapping every conversion-plan item → its OpenSpec requirement/spec. (The OpenSpec documents themselves live wherever the openspec skill writes them.)

**Stage-4 CHECKLIST:** 100% of the conversion plan is represented in the OpenSpec; the OpenSpec was authored via the openspec skill (not hand-written).

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-4 OPENSPEC-CONVERSION COMPLETE — all reviewers agree 100% of the plan is converted via the openspec skill". The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 5 — Per-page REST returns → `API_RETURNS_MAP.md`

**v3.4.0 — delegation to `api-design-from-frontend`.** Stages 5, 6, and 7 are extracted into the `api-design-from-frontend` skill (`skills/api-design-from-frontend/SKILL.md`) for reuse by the `architect-team-pipeline` Phase 0b backend dispatch. This Exploration Pipeline still drives the same 3 stages; it does so by invoking `api-design-from-frontend` once with the Stage 3+4 artifacts as inputs and the `<codebase>/docs/` paths as the output directory. The stage descriptions below remain as the canonical contract documentation.

```json
// invoked at the start of Stage 5 by visual-to-api-design
{
  "persona_map_path": "<codebase>/docs/PERSONA_MAP.md",
  "component_architecture_map_path": "<codebase>/docs/COMPONENT_ARCHITECTURE_MAP.md",
  "page_catalog_path": "<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-3-pages.json",
  "frontend_reference_path": "<codebase-absolute-path>",
  "doc_inputs": [],
  "output_dir": "<codebase>/docs",
  "openspec_change_name": "<change-slug>",
  "frontend_read_only": false,
  "completion_promise": "API DESIGN COMPLETE"
}
```

`api-design-from-frontend` produces all 3 output maps (Stages A1+A2+A3) under one orchestration; visual-to-api-design no longer drives each Stage 5/6/7 ct6-converge workflow directly. Behavior preserved bit-for-bit.

**Goal (Stage 5 contract):** specify, per page, the **most efficient** REST/API returns powering that page — the data needed and its shape — such that every element's data source is identified and 100% of data-bearing elements are covered.

**"Most efficient" — the measurable definition (the strict ct6-converge workflow exit predicate):**

- **Over-fetch budget = 0 unconsumed top-level fields** — no returned top-level field may be consumed by zero elements on the page. The over-fetch check FLAGS any return field consumed by no element.
- **Shared pages reuse one return shape** — pages sharing the same data reuse a single return shape rather than redefining it.

**What it does:** for each page, lists the API return shape(s) powering it and **maps every dynamic element (from Stage 3a `value_class: dynamic`) to a field in a return.** Every data-bearing element has an identified return source.

**Output doc:** `<codebase>/docs/API_RETURNS_MAP.md`. Frontmatter `{generated_at, pages_count, returns_count}` per the canonical naming standard.

**Stage-5 CHECKLIST against Stage 3a + Stage 3c:** every `value_class: dynamic` element maps to a return field; the over-fetch check returns 0 unconsumed top-level fields per page; shared-data pages reuse one shape.

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-5 API_RETURNS COMPLETE — all reviewers agree 100% of dynamic elements have an efficient return source (0 over-fetch)". The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 6 — Consolidated API design + play-test → `API_DESIGN_MAP.md`

**Goal:** holistically propose a target API structure that **maximizes endpoint reusability**, provides **CRUD operations where the data model requires them**, and **shapes returns by user-type**; then **design-time play-test (desk-trace)** each page against the proposed API.

**"Max reusability" — the measurable definition (the strict ct6-converge workflow exit predicate):**

- **Every page's needs are satisfiable from the consolidated endpoint set** — no page requires a return the consolidated set can't produce.
- **No two endpoints serve identical element sets** — duplicate-coverage endpoints are consolidated.

**The play-test is a design-time DESK-TRACE, not a running server** (per resolved design decision 1). For each page, document the trace: **every component (from Stage 3c) → the proposed endpoint call (or the consolidated return field) that satisfies its payload consumption.** A running mock-server-from-OpenSpec contract test is explicitly DEFERRED to the implementation pipeline (architect-team Phases 2–8), since the API is not built during exploration. The desk-trace's exit criterion is **100% of components on 100% of pages satisfied** by an endpoint call or a consolidated return.

**What it does:** defines the consolidated endpoint set with CRUD coverage and per-user-type response shaping; documents a play-test trace for **every page (100%)** showing each component is satisfied by an endpoint call or a consolidated return.

**Output doc:** `<codebase>/docs/API_DESIGN_MAP.md`. Frontmatter `{generated_at, endpoints_count, user_types[]}` per the canonical naming standard.

**Stage-6 CHECKLIST against Stage 5 + Stage 3c:** every page satisfiable from the consolidated set; no two endpoints serve identical element sets; 100% of pages carry a play-test desk-trace; CRUD present where the data model needs it; returns shaped by user-type.

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-6 API_DESIGN COMPLETE — all reviewers agree the consolidated API satisfies 100% of pages (desk-traced) with max reuse". The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 7 — Backend data architecture + phenotype gates → `DATA_ARCHITECTURE_MAP.md`

**Goal (runs IFF backend is in scope):** derive the data architecture from the components + API requirements — reading the personas + platform use case — design an **extensibility-first schema for anticipated AND examined potential use cases**, select database types, fire the `phenotypes` domain gates, and THEN emit execution-ready OpenSpec requirements via the openspec skill.

**What it does:**

- **Reads the personas (`PERSONA_MAP.md`) + the platform use case** (Stage 1 classification) as the design inputs.
- **Designs an extensibility-first schema** for the anticipated use cases AND the examined potential use cases (it records which potential use cases were considered).
- **Selects the database type(s)** (relational / document / graph / key-value / time-series) with the selection rationale.
- **Fires the `phenotypes` domain gates** (per RD-8; these are `AskUserQuestion`-style domain gates, never silent application):
  - **user-management** — "Does this need a user-management layer? I can base it on the `phenotypes/user-management` phenotype, or follow new guidance." 
  - **AI-management** — "Does this need an AI-management layer? I can base it on the `phenotypes/ai-management` phenotype, or follow new guidance."
  - **config-management (deploy)** — "Does OpenTofu (or an equivalent IaC) already exist for deploy? If not, I can use the `phenotypes/config-management` phenotype (ships OpenTofu `.tf.tmpl`)."
- **Emits execution-ready OpenSpec requirements via the openspec skill** (`openspec-propose` / `opsx:propose`) — the final data-architecture requirements are OpenSpec, authored via the openspec skill, NOT hand-written.

**Output doc:** `<codebase>/docs/DATA_ARCHITECTURE_MAP.md` — records the extensible schema, the DB-type selection, and the anticipated/potential use cases considered. Frontmatter `{generated_at, db_types[], phenotypes_used[], openspec_change}` per the canonical naming standard.

**Stage-7 CHECKLIST against Stage 6 + Stage 1:** the schema covers every data point implied by the consolidated API (Stage 6) and every persona need (Stage 1/2); the three phenotype domain gates fired; the final requirements are OpenSpec authored via the openspec skill.

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-7 DATA_ARCHITECTURE COMPLETE — all reviewers agree the schema is extensible, DB types selected, phenotype gates fired, OpenSpec emitted via the openspec skill". The loop runs until the completion-promise is satisfied (no iteration cap).

### Exploration Pipeline — stage→doc→ct6-converge workflow→checklist summary

| Stage | Scope gate | Reuses | Output doc | OpenSpec skill | ct6-converge workflow completion-promise (abbrev.) |
|---|---|---|---|---|---|
| 0 — Scope detection | always | `intake-and-mapping` | `stage-0-scope.json` | — | STAGE-0 SCOPE COMPLETE |
| 1 — Personas + classification | frontend | Exploration Stage 1 (context discovery) | `stage-1-context.json` (+ `ancillary_docs_read`) | — | STAGE-1 CONTEXT COMPLETE |
| 2 — Per-persona objectives | frontend | Exploration Stage 2 (per-persona research) | `PERSONA_MAP.md` | — | STAGE-2 PERSONA_MAP COMPLETE |
| 3a — Page/element catalog | frontend | Exploration Stage 3 + `design-fidelity-mapping` | `stage-3a-...json` | — | STAGE-3A CATALOG COMPLETE |
| 3b — Route<->persona map | frontend | `frontend-route-mapping` (ROUTE_MAP) | `stage-3b-...json` | — | STAGE-3B ROUTE-PERSONA COMPLETE |
| 3c — Reusable-component architecture (NET-NEW) | frontend | `verify-every-element` (coverage) | `COMPONENT_ARCHITECTURE_MAP.md` | — | STAGE-3C COMPONENT-ARCHITECTURE COMPLETE |
| 4 — Conversion → OpenSpec | frontend | `openspec-propose` / `opsx:propose` | `stage-4-...json` | **yes** | STAGE-4 OPENSPEC-CONVERSION COMPLETE |
| 5 — Per-page REST returns | frontend | `dynamic-value-discovery` | `API_RETURNS_MAP.md` | — | STAGE-5 API_RETURNS COMPLETE |
| 6 — Consolidated API design + play-test | frontend | Exploration Stage 4 (api layer) | `API_DESIGN_MAP.md` | — | STAGE-6 API_DESIGN COMPLETE |
| 7 — Backend data architecture + phenotype gates | backend | `phenotypes` (user/ai/config-management) + openspec skill | `DATA_ARCHITECTURE_MAP.md` | **yes** | STAGE-7 DATA_ARCHITECTURE COMPLETE |

The OpenSpec-producing stages are **Stage 4** and **Stage 7** — both call the openspec skill (`openspec-propose` / `opsx:propose`), never hand-written JSON.
