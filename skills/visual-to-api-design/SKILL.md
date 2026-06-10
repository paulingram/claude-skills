---
name: visual-to-api-design
description: Use when the architect-team is invoked against a visual codebase (UI present, requirements absent OR partially specified) and must DERIVE the API design from what the screens reveal — the Phase 0 "review this codebase / design the API for this visual" case. Runs the Exploration Pipeline, a scope-gated 7-stage flow with 3-reviewer convergence per stage (each convergence wrapped in a ralph-loop whose completion-promise is total reviewer agreement) and per-stage checklists that gate the next stage's freeze. The body documents every stage, the checklists, the ralph-loop governance, the openspec-skill conversion, and the original 4-stage flow that remains valid as a strict subset.
---

# Visual-to-API Design Pipeline (the Exploration Pipeline)

When the architect-team is given a visual codebase (a UI repo, a Figma export, a deployed site URL) but no explicit requirements OR only partial requirements, this skill produces the API design — and, when frontend is in scope, the persona research, page/element catalog, reusable-component architecture, per-page REST returns, and consolidated API design — that the visual code implies. This is the **Exploration Pipeline**: a scope-gated **7-stage** flow, each stage frozen before the next begins, each stage reviewed by 3 independent agents in convergence (the v0.9.19 pattern) **inside a `ralph-loop:ralph-loop`** whose completion-promise is total reviewer agreement, each stage's output the explicit checklist the next stage must satisfy.

**The original 4-stage flow is a strict SUBSET of the 7-stage pipeline** (see `## The 4 stages (the original subset)` below): Stage 1 (context discovery) is a subset of Exploration Stage 1, Stage 2 (per-persona research) of Exploration Stage 2, Stage 3 (page catalog) of Exploration Stage 3a, and Stage 4 (backend design from frontend) of Exploration Stages 5+6+7. The 4-stage subset and the `/architect-team:visual-to-api` command remain valid and unchanged.

## The Exploration Pipeline — 7 stages

The Exploration Pipeline runs 7 stages. Frontend stages (1–6) run only when frontend is in scope; the backend stage (7) runs only when backend is in scope; Stage 0 always runs and decides the branch. Each stage produces a frozen JSON artifact at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json` AND (for the stages that own a standardized doc) one of the five canonical `*_MAP.md` documents in `<codebase>/docs/`. Each stage runs the v0.9.19 3-reviewer convergence protocol (Round 1 independent → Round 2 round-robin → Round 3 architect) **inside a `ralph-loop:ralph-loop`**, and reads the prior stage's frozen artifact as its CHECKLIST.

### Governance — every stage's convergence runs inside a ralph-loop

Every stage's 3-reviewer doc-passing convergence is wrapped in the `ralph-loop:ralph-loop` skill (the `/ralph-loop` command). The loop body is the 3-reviewer convergence; the loop's `--completion-promise` is **total agreement across all reviewers that the stage document meets every required step (100% fidelity)**. The loop exits ONLY when all three reviewers AND the Round-3 architect agree the stage doc satisfies every checklist item; the loop runs until that completion-promise is satisfied — there is **no iteration cap** (per `common-pipeline-conventions` `## Unbounded solving discipline`). Each stage below names its own promise string. The canonical invocation shape (matching `intake-and-mapping`):

```bash
/ralph-loop "<stage convergence prompt>" --completion-promise "<STAGE-N PROMISE>"
```

When the convergence reaches total agreement, the loop body emits the stage's exact promise line, which trips the completion-promise and exits the loop. The loop never halts on iteration count and never freezes a half-agreed artifact — it keeps converging. If a stage genuinely cannot converge because the requirement is unsettleable from the available inputs (a product decision only the owner can make), it routes an `api-design-stage-incomplete` SR surfacing that specific required owner input — loudly, while the run continues working everything else — rather than stopping.

### Run-time inputs — `language`, `component_libraries`, `ancillary_docs`

The target `language`, the `component_libraries`, and the `ancillary_docs` are read from the **requirements-brief frontmatter** or a **project config** (`<codebase>/.architect-team.config` / brief frontmatter). They are NEVER guessed. When frontend/component work is in scope and any of these inputs is absent, the skill **escalates via a domain gate** (an `AskUserQuestion`-style prompt, consistent with `common-pipeline-conventions` `## Scope discipline`) — it does not invent a language or a component library. `ancillary_docs` (product briefs, brand guidelines, market research, competitor docs) are a **first-class Stage 1 input**, read alongside the codebase.

### The five standardized documentation artifacts

The Exploration Pipeline emits five fixed-name documents into `<codebase>/docs/`. Their names, paths, and frontmatter schemas are **canonicalized in `common-pipeline-conventions`** (the `## Standardized documentation naming` standard — another teammate owns that section); this skill REFERENCES that standard rather than duplicating it. The five docs and their producing stage:

| Doc | Path | Produced by | Frontmatter (per the canonical standard) |
|---|---|---|---|
| `PERSONA_MAP.md` | `<codebase>/docs/` | Stage 2 | `{generated_at, personas_count, source_ancillary_docs[]}` |
| `COMPONENT_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | Stage 3c | `{generated_at, language, component_libraries[], elements_total, components_total, coverage}` |
| `API_RETURNS_MAP.md` | `<codebase>/docs/` | Stage 5 | `{generated_at, pages_count, returns_count}` |
| `API_DESIGN_MAP.md` | `<codebase>/docs/` | Stage 6 | `{generated_at, endpoints_count, user_types[]}` |
| `DATA_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | Stage 7 | `{generated_at, db_types[], phenotypes_used[], openspec_change}` |

These are auto-generated whenever the Exploration Pipeline runs against a project (frontend docs only when frontend is in scope; `DATA_ARCHITECTURE_MAP.md` only when backend is in scope), created-on-ask in standalone mode, and follow the existing `*_MAP.md` convention.

### Stage 0 — Scope detection

**Goal:** classify the run and branch the downstream stages. Stage 0 ALWAYS runs.

**What it does:** surfaces the existing `intake-and-mapping` classification and classifies the run as exactly one of three scope outcomes:

- **`frontend-only`** — UI present, no backend to design; run Stages 1–6, skip Stage 7.
- **`backend-only`** — backend/data work with no UI to catalog; skip the frontend stages (1–6), run Stage 7.
- **`both`** — full Exploration; run Stages 1–7.

**Branching rule (stated explicitly):** **the frontend stages (1–6) run if and only if frontend is in scope; the backend stage (7) runs if and only if backend is in scope.** A `both` run executes all seven; a `frontend-only` run stops after Stage 6; a `backend-only` run runs Stage 7 directly against whatever API/data requirements exist.

**Required output** (`stage-0-scope.json`): `{stage: 0, name: "scope-detection", scope: "frontend-only" | "backend-only" | "both", frontend_in_scope: bool, backend_in_scope: bool, classification_source: "intake-and-mapping", frozen_at, _human_review_required}`.

**ralph-loop:** the 3-reviewer scope-classification convergence is wrapped in `/ralph-loop "classify run scope (frontend-only | backend-only | both) from the intake-and-mapping output; all reviewers agree on the branch" --completion-promise "STAGE-0 SCOPE COMPLETE — all reviewers agree on scope + branch"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 1 — Personas + application classification

**v3.4.0 — delegation to `domain-research-team`.** Stages 1 and 2 are encapsulated in the `domain-research-team` skill (`skills/domain-research-team/SKILL.md`), which carries the mandatory outside-research enrichment v3.4.0 adds. visual-to-api-design invokes the skill once with `output_kind: persona-map`, the frontend codebase + configured `ancillary_docs` as inputs, and the `<codebase>/docs/PERSONA_MAP.md` output path. The persona enumeration + per-persona objectives come back as one final map; visual-to-api-design proceeds to Stage 3 with that map as the binding input.

**Goal:** when frontend is in scope, catalog ALL personas (user types) and classify the whole application. **Reuses Exploration Stage 1 (context discovery)** — see `### Stage 1 — Context discovery` in the subset section below for the exact `stage-1-context.json` shape; Stage 1 of the Exploration Pipeline extends it by reading the configured `ancillary_docs` as a first-class input.

**What it does:** enumerates every distinct persona/user-type AND produces the application classification (`application_purpose` / `industry` / `use_case_summary`), reading the frontend PLUS the configured `ancillary_docs`. The persona enumeration is the seed for Stage 2's per-persona objective document.

**Required output:** the existing `stage-1-context.json` (see subset section) with `ancillary_docs_read: [...]` added — the list of ancillary docs consumed.

**ralph-loop:** wrapped in `/ralph-loop "discover personas + application classification from the frontend + ancillary_docs; all reviewers agree the persona list + classification are complete" --completion-promise "STAGE-1 CONTEXT COMPLETE — all reviewers agree personas + classification are complete"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 2 — Per-persona objectives → `PERSONA_MAP.md`

**Goal:** for each persona, write an objective document describing what that persona wants to achieve in this industry while using this product. **Reuses Exploration Stage 2 (per-persona research)** — see `### Stage 2 — Per-persona research` in the subset section for the `stage-2-personas.json` shape.

**Output doc:** `<codebase>/docs/PERSONA_MAP.md` — **one objective section per persona**, each section carrying: the persona's **role**, the **industry context**, and the **objectives** they want to achieve with the product. Frontmatter `{generated_at, personas_count, source_ancillary_docs[]}` per the canonical naming standard.

**Stage-2 CHECKLIST against Stage 1:** every persona in Stage 1's persona list MUST appear as a `PERSONA_MAP.md` section; the count MUST match.

**ralph-loop:** wrapped in `/ralph-loop "write one PERSONA_MAP.md objective section per persona (role + industry context + product objectives); all reviewers agree every persona is covered" --completion-promise "STAGE-2 PERSONA_MAP COMPLETE — all reviewers agree every persona has an objective section"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 3a — Page/element catalog

**Goal:** list every page, then every element on each page, capturing for each element its `type`, its `html_attributes`, and a `value_class: dynamic | static` classification. **Reuses Exploration Stage 3 (page catalog) + `design-fidelity-mapping` (DESIGN_MAP).** See `### Stage 3 — Page catalog` in the subset section for the per-element shape this extends.

**Per-element capture (stated explicitly):**

- **`type`** — the element classification (form-input-text, submit-button, file-upload, data-row, etc.).
- **`html_attributes`** — the element's tag + salient HTML attributes, **captured UNCONDITIONALLY from source for every element, regardless of design inputs.** Computed-style attributes are added ONLY when design inputs exist (reusing DESIGN_MAP's per-element computed-style capture). Raw-HTML-attribute capture never blocks; it degrades to tag+attributes when no DESIGN_MAP is present.
- **`value_class: dynamic | static`** — classified per **`dynamic-value-discovery`**: classify from CONTEXT (is this a per-user / per-record / per-state value?), **never from the literal** on the screen. A name field showing "John Smith" is `dynamic` even though the mockup shows a constant.

**Required output** (`stage-3a-page-element-catalog.json`): per page, every element with `{type, html_attributes, value_class}` plus the existing subset fields (`element_id`, `classification`, `blurb`, `is_dynamic`, `needs_backend`, `backend_endpoint_hint`).

**ralph-loop:** wrapped in `/ralph-loop "catalog every page → every element with {type, html_attributes captured unconditionally, value_class dynamic|static via dynamic-value-discovery}; all reviewers agree every element on every page is catalogued" --completion-promise "STAGE-3A CATALOG COMPLETE — all reviewers agree every element is captured with attributes + value_class"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 3b — Route<->persona map

**Goal:** construct the route inventory and cross-map every route to the personas it impacts. **Reuses `frontend-route-mapping` (ROUTE_MAP).**

**What it does:** builds the ROUTE_MAP via `frontend-route-mapping`, then annotates **each route with the personas it impacts** (drawn from the Stage 2 `PERSONA_MAP.md`). Every route in the ROUTE_MAP carries an `impacted_personas: [...]` annotation.

**Required output** (`stage-3b-route-persona-map.json`): the ROUTE_MAP with each route annotated `{route, ..., impacted_personas: [persona_id, ...]}`.

**Stage-3b CHECKLIST:** every route in the ROUTE_MAP has at least one impacted persona OR an explicit `impacted_personas: []` with a justification (e.g., a public/unauthenticated route); every persona in `PERSONA_MAP.md` is referenced by at least one route.

**ralph-loop:** wrapped in `/ralph-loop "build the ROUTE_MAP and annotate every route with impacted personas from PERSONA_MAP; all reviewers agree every route maps to its personas" --completion-promise "STAGE-3B ROUTE-PERSONA COMPLETE — all reviewers agree every route is annotated with impacted personas"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 3c — Reusable-component architecture → `COMPONENT_ARCHITECTURE_MAP.md` (NET-NEW)

**Goal (the single net-new stage):** propose a reusable-component architecture in the configured `language` + `component_libraries`, map every catalogued element 1:1 to a proposed component (100% coverage), record the exact per-page placement of each component, and declare each component's expected payload consumption. This is a **multi-agent (>=3) doc-passing task.**

**What it does:**

- **Proposes components in the configured `language` + `component_libraries`** (read from the brief/config per `### Run-time inputs`; absence escalates via a domain gate, never guessed).
- **Maps every catalogued element (from Stage 3a) to a proposed component — 100% coverage**, verified via a **`verify-every-element`-style check** (`hooks/vao_tools.py::verify-every-element` pattern, reused per RD-9): every element_id in the Stage 3a catalog appears in exactly one component's `covers_element_ids`. An uncovered element fails the stage.
- **Records the exact per-page placement of each component.** When design inputs exist (a DESIGN_MAP is present), placement is **pixel-perfect** (per-screen coordinates / asset placement). Otherwise it degrades to a **structural-placement** mode recording which page/region each component occupies (no pixel coordinates). The placement mode never blocks; it degrades.
- **Declares each component's expected payload consumption** — the data shape the component expects to render (which feeds Stage 5's per-page returns).

**Output doc:** `<codebase>/docs/COMPONENT_ARCHITECTURE_MAP.md`. Frontmatter `{generated_at, language, component_libraries[], elements_total, components_total, coverage}` per the canonical naming standard.

**Stage-3c CHECKLIST against Stage 3a:** the UNION of every component's `covers_element_ids` MUST equal the full set of element_ids in the Stage 3a catalog (100% coverage). Every component declares a `placement` (pixel-perfect or structural) and an `expected_payload`.

**ralph-loop:** the >=3-agent doc-passing convergence is wrapped in `/ralph-loop "propose reusable components in the configured language + component_libraries; map every element 1:1 (100% coverage, verify-every-element-style); record exact per-page placement (pixel-perfect when DESIGN_MAP exists, structural otherwise); declare each component's expected payload; all reviewers agree on 100% coverage + placement + payload" --completion-promise "STAGE-3C COMPONENT-ARCHITECTURE COMPLETE — all reviewers agree 100% element coverage + placement + payload"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 4 — Conversion → OpenSpec via the openspec skill

**Goal:** convert the component-architecture conversion plan (Stages 3a–3c) into OpenSpec documents **using the openspec skill** — `openspec-propose` / `opsx:propose` — NOT hand-written JSON. >=3 agents in parallel; validate 100% conversion.

**What it does (stated explicitly):**

- **Invokes the openspec skill** (`openspec-propose` / `opsx:propose`) to author the conversion OpenSpec. The skill body NAMES the openspec skill explicitly; this stage does NOT hand-write OpenSpec JSON or spec files.
- **>=3 agents in parallel** each draft a slice of the conversion; they converge.
- **Validates 100% conversion** — a coverage check confirms 100% of the conversion plan (every page, every route, every component from Stages 3a/3b/3c) is represented in the produced OpenSpec artifacts. A plan item with no OpenSpec representation fails the stage.

**Required output** (`stage-4-openspec-conversion.json`): the openspec change name produced + a coverage manifest mapping every conversion-plan item → its OpenSpec requirement/spec. (The OpenSpec documents themselves live wherever the openspec skill writes them.)

**Stage-4 CHECKLIST:** 100% of the conversion plan is represented in the OpenSpec; the OpenSpec was authored via the openspec skill (not hand-written).

**ralph-loop:** wrapped in `/ralph-loop "convert the component-architecture plan to OpenSpec via the openspec skill (openspec-propose / opsx:propose), >=3 agents; validate 100% of the plan is converted; all reviewers agree conversion is complete" --completion-promise "STAGE-4 OPENSPEC-CONVERSION COMPLETE — all reviewers agree 100% of the plan is converted via the openspec skill"`. The loop runs until the completion-promise is satisfied (no iteration cap).

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

`api-design-from-frontend` produces all 3 output maps (Stages A1+A2+A3) under one orchestration; visual-to-api-design no longer drives each Stage 5/6/7 ralph-loop directly. Behavior preserved bit-for-bit.

**Goal (Stage 5 contract):** specify, per page, the **most efficient** REST/API returns powering that page — the data needed and its shape — such that every element's data source is identified and 100% of data-bearing elements are covered.

**"Most efficient" — the measurable definition (the strict ralph-loop exit predicate):**

- **Over-fetch budget = 0 unconsumed top-level fields** — no returned top-level field may be consumed by zero elements on the page. The over-fetch check FLAGS any return field consumed by no element.
- **Shared pages reuse one return shape** — pages sharing the same data reuse a single return shape rather than redefining it.

**What it does:** for each page, lists the API return shape(s) powering it and **maps every dynamic element (from Stage 3a `value_class: dynamic`) to a field in a return.** Every data-bearing element has an identified return source.

**Output doc:** `<codebase>/docs/API_RETURNS_MAP.md`. Frontmatter `{generated_at, pages_count, returns_count}` per the canonical naming standard.

**Stage-5 CHECKLIST against Stage 3a + Stage 3c:** every `value_class: dynamic` element maps to a return field; the over-fetch check returns 0 unconsumed top-level fields per page; shared-data pages reuse one shape.

**ralph-loop:** wrapped in `/ralph-loop "specify per-page REST returns; map every dynamic element to a return field; enforce over-fetch budget = 0 unconsumed top-level fields and shared-page shape reuse; all reviewers agree every data-bearing element has an efficient return source" --completion-promise "STAGE-5 API_RETURNS COMPLETE — all reviewers agree 100% of dynamic elements have an efficient return source (0 over-fetch)"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Stage 6 — Consolidated API design + play-test → `API_DESIGN_MAP.md`

**Goal:** holistically propose a target API structure that **maximizes endpoint reusability**, provides **CRUD operations where the data model requires them**, and **shapes returns by user-type**; then **design-time play-test (desk-trace)** each page against the proposed API.

**"Max reusability" — the measurable definition (the strict ralph-loop exit predicate):**

- **Every page's needs are satisfiable from the consolidated endpoint set** — no page requires a return the consolidated set can't produce.
- **No two endpoints serve identical element sets** — duplicate-coverage endpoints are consolidated.

**The play-test is a design-time DESK-TRACE, not a running server** (per resolved design decision 1). For each page, document the trace: **every component (from Stage 3c) → the proposed endpoint call (or the consolidated return field) that satisfies its payload consumption.** A running mock-server-from-OpenSpec contract test is explicitly DEFERRED to the implementation pipeline (architect-team Phases 2–8), since the API is not built during exploration. The desk-trace's exit criterion is **100% of components on 100% of pages satisfied** by an endpoint call or a consolidated return.

**What it does:** defines the consolidated endpoint set with CRUD coverage and per-user-type response shaping; documents a play-test trace for **every page (100%)** showing each component is satisfied by an endpoint call or a consolidated return.

**Output doc:** `<codebase>/docs/API_DESIGN_MAP.md`. Frontmatter `{generated_at, endpoints_count, user_types[]}` per the canonical naming standard.

**Stage-6 CHECKLIST against Stage 5 + Stage 3c:** every page satisfiable from the consolidated set; no two endpoints serve identical element sets; 100% of pages carry a play-test desk-trace; CRUD present where the data model needs it; returns shaped by user-type.

**ralph-loop:** wrapped in `/ralph-loop "consolidate the API for max reusability (every page satisfiable, no two endpoints serve identical element sets), CRUD where the data model needs it, return-by-user-type; desk-trace play-test every page (100%) showing each component calls an endpoint or consumes a consolidated return; all reviewers agree" --completion-promise "STAGE-6 API_DESIGN COMPLETE — all reviewers agree the consolidated API satisfies 100% of pages (desk-traced) with max reuse"`. The loop runs until the completion-promise is satisfied (no iteration cap).

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

**ralph-loop:** wrapped in `/ralph-loop "derive an extensibility-first data architecture (anticipated + potential use cases), select DB types, fire the user-management / ai-management / config-management phenotype domain gates, then emit execution-ready OpenSpec via the openspec skill; all reviewers agree the architecture is extensible + complete" --completion-promise "STAGE-7 DATA_ARCHITECTURE COMPLETE — all reviewers agree the schema is extensible, DB types selected, phenotype gates fired, OpenSpec emitted via the openspec skill"`. The loop runs until the completion-promise is satisfied (no iteration cap).

### Exploration Pipeline — stage→doc→ralph-loop→checklist summary

| Stage | Scope gate | Reuses | Output doc | OpenSpec skill | ralph-loop completion-promise (abbrev.) |
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

## The failure shape this closes (verbatim from the user)

> "lets optimize how we analyze viaul codebases for API desing. the first thin our agents should do is 1) discover the overall context and document. what is the purpose of the application, how many pages, how many user persons. What industry is it in, what use case does it appear to address etc. 2) then it must, for ecah persona, research what they woudl be using the platform for, reading documentation and internet searches. this must be recorded 3) then a complete catalog of each page must be made. first we identify all the pages, then for ecah page, identify every element on it. For ecah element, you will review it, classify it, make a blurb about it, and idnetify if it needs a backend built or if it needs to be dynamic etc.. such as a name field that must be a dynamic variable etc... 4) finally, once that is done, you will take all this context and devise a bakcend that solves for the front end use case, starting by defining the data needed to be returned or adsorbed, then defining the services needed such as database services etc...then the schema - for each return mock, you need to consolidate and come up with a data schema that properly solves all cases. Then finally, define the API layer - what are the endpoints, how do these map to the tables or services etc...you will use each prior step as a checklist. For example - when enurmeating the api, you will pass that by making sure the API layer accesses all the data. The data and schema layer will rely on solving the prior step - can it provide the data. Then the data return layer mocks must check list against every element identified on the page etc... you will do this with 3 agents who review each others work at each stage for completeness. Review this and optimize accordingly but ensure each step is inforprated"

Existing reviews of visual codebases jumped straight to "what does this UI do?" without first establishing context, persona research, exhaustive page catalog, OR a checklist-driven backend design. The result was an API design that *mostly* covered what was on screen but missed entire affordances (the v2.13.0 file-upload case) AND missed per-element data needs (a name field that should be dynamic but was treated as static). v2.13.0 ships the structured pipeline that makes both gaps structurally impossible.

## The 4 stages (the original subset)

The original 4-stage flow is the canonical SUBSET of the Exploration Pipeline (see `## The Exploration Pipeline — 7 stages` above) and remains valid and unchanged — invoked directly by the `/architect-team:visual-to-api` command. Each stage produces a frozen JSON artifact stored at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json`. Each stage runs the v0.9.19 3-reviewer convergence protocol (3 independent reviewer agents → round-robin Round 2 → architect Round 3) before its artifact is frozen; in the full Exploration Pipeline that convergence is additionally wrapped in a `ralph-loop:ralph-loop` (see governance above), but the 4-stage subset's convergence semantics are unchanged. Each subsequent stage reads the prior stage's frozen artifact as its CHECKLIST.

### Stage 1 — Context discovery

**Goal:** answer "what is this application?"

**Required output** (`stage-1-context.json`):

```json
{
  "stage": 1,
  "name": "context-discovery",
  "application_purpose": "Heir-apparent estate intake + matter management for title agencies, attorneys, and family members",
  "industry": "Legal / Real-estate title services",
  "use_case_summary": "Streamline matter creation, family-graph intake, and aggregate reporting for §25 estate cases",
  "pages_count": 14,
  "personas_count": 4,
  "tech_stack_hints": ["React/Vite", "FastAPI", "Neo4j", "AWS S3"],
  "deployment_environment_hint": "https://heirship-app-v3.example.com",
  "frozen_at": "<ISO 8601>",
  "_human_review_required": false
}
```

**Reviewer convergence:** 3 reviewers independently read the codebase + README + manifest files, propose context paragraphs, then converge in Round 2. Disputes resolve by re-reading evidence; Round 3 architect review is the final gate.

### Stage 2 — Per-persona research

**Goal:** for each persona named in Stage 1, document what they would USE the platform for.

**Required output** (`stage-2-personas.json`):

```json
{
  "stage": 2,
  "name": "per-persona-research",
  "based_on_stage_1": "<sha-of-stage-1-artifact>",
  "personas": [
    {
      "persona_id": "title-agency-operator",
      "role_description": "Title agency staff who creates the initial matter and enters basic property + decedent info on behalf of the client",
      "research_sources": ["industry-blog-1", "competitor-doc-x", "user-research-note-y"],
      "expected_workflows": [
        "Open new matter from property address",
        "Send invite to family members for intake",
        "Monitor matter status across the firm's portfolio"
      ],
      "expected_data_needs": ["matter list", "matter detail", "invite-status panel", "family-graph editor (limited)"],
      "expected_affordances": ["file-upload (property docs)", "search (matter list)", "export (matter list to CSV)"]
    }
  ],
  "frozen_at": "<ISO 8601>",
  "_human_review_required": false
}
```

**Stage-2 CHECKLIST against stage 1:** every persona in `stage-1-context.json::personas_count` MUST appear; total count MUST match.

**Reviewer convergence:** 3 reviewers each research their assigned persona independently (via documentation + internet searches when applicable; via deep code-reading otherwise), then converge in Round 2. A persona missing research sources, expected workflows, OR expected data needs is rejected in Round 3.

### Stage 3 — Page catalog

**Goal:** enumerate every page; for each page, enumerate every element with classification + blurb + dynamic-or-static + backend-need.

**Required output** (`stage-3-page-catalog.json`):

```json
{
  "stage": 3,
  "name": "page-catalog",
  "based_on_stage_2": "<sha-of-stage-2-artifact>",
  "pages": [
    {
      "page_id": "ta-new-matter",
      "route": "/ta/new",
      "title": "Title Agency · New Matter",
      "personas_using_this_page": ["title-agency-operator"],
      "elements": [
        {
          "element_id": "decedent-name-input",
          "classification": "form-input-text",
          "blurb": "Free-text input for the decedent's full legal name; bound to matter.decedent.full_name",
          "is_dynamic": true,
          "dynamic_data_source": "matter.decedent.full_name (user-entered)",
          "needs_backend": true,
          "backend_endpoint_hint": "POST /matters",
          "validation_hint": "required, max 200 chars"
        },
        {
          "element_id": "create-matter-button",
          "classification": "submit-button",
          "blurb": "Submits the new matter form; triggers POST to backend; shows loading state",
          "is_dynamic": false,
          "needs_backend": true,
          "backend_endpoint_hint": "POST /matters",
          "loading_state_required": true,
          "double_submit_guard_required": true
        },
        {
          "element_id": "upload-property-docs",
          "classification": "file-upload",
          "blurb": "Drag-drop zone for property documents; multipart upload to S3",
          "is_dynamic": false,
          "needs_backend": true,
          "backend_endpoint_hint": "POST /matters/{id}/documents (multipart)",
          "affordance_kind": "file-upload"
        }
      ]
    }
  ],
  "frozen_at": "<ISO 8601>",
  "_human_review_required": false
}
```

**Stage-3 CHECKLIST against stage 1+2:** total pages count MUST match `stage-1::pages_count`; every persona's `expected_workflows` from Stage 2 MUST be reachable from at least one page; every persona's `expected_affordances` (file-upload, search, export, etc.) MUST be reflected in element classifications.

**Reviewer convergence:** 3 reviewers each catalog ~1/3 of the pages independently, then converge in Round 2. Missing page → rejected; element on a page that one reviewer caught but two missed → escalated in Round 2; Round 3 architect verifies completeness against Stage 1 + 2 checklists.

### Stage 4 — Backend design from frontend

**Goal:** derive the backend (data → services → schema → API layer) from the frozen page catalog.

**Required output** (`stage-4-backend-design.json`) — a NESTED 4-layer artifact, each layer checking the prior:

```json
{
  "stage": 4,
  "name": "backend-design",
  "based_on_stage_3": "<sha-of-stage-3-artifact>",
  "layers": {
    "data": {
      "_purpose": "Define the data that must be returned or absorbed for every element classified `needs_backend: true` or `is_dynamic: true` in Stage 3.",
      "data_points": [
        {
          "data_point_id": "matter.decedent.full_name",
          "source_element_ids": ["decedent-name-input", "matter-list-row.decedent-name", "attorney-dashboard.matter-card.decedent"],
          "type": "string",
          "max_length": 200,
          "required": true
        }
      ],
      "checklist_verdict": "every element with `needs_backend: true` OR `is_dynamic: true` from Stage 3 has at least one data_point covering it"
    },
    "services": {
      "_purpose": "Define services needed (DB, queue, cache, object storage, third-party APIs) to provide the data layer.",
      "services": [
        {"service_id": "postgres", "purpose": "matters, persons, relationships tables"},
        {"service_id": "neo4j", "purpose": "family graph aggregate queries"},
        {"service_id": "s3", "purpose": "property document storage (file-upload affordance)"},
        {"service_id": "sendgrid", "purpose": "invite emails"}
      ],
      "checklist_verdict": "every data_point in the data layer has a service that can store/retrieve it"
    },
    "schema": {
      "_purpose": "Consolidate per-element data shapes into a normalized schema that solves all cases.",
      "tables": [
        {
          "table_id": "matters",
          "columns": [
            {"column": "id", "type": "uuid", "primary": true},
            {"column": "decedent_full_name", "type": "varchar(200)", "nullable": false, "covers_data_point": "matter.decedent.full_name"}
          ]
        }
      ],
      "checklist_verdict": "every data_point in the data layer maps to at least one column in the schema"
    },
    "api": {
      "_purpose": "Define endpoints + mappings to tables/services.",
      "endpoints": [
        {
          "endpoint_id": "create-matter",
          "method": "POST",
          "path": "/matters",
          "request_shape": {"decedent_full_name": "string"},
          "response_shape": {"id": "uuid"},
          "service_dependencies": ["postgres"],
          "covers_element_ids": ["decedent-name-input", "create-matter-button"]
        }
      ],
      "checklist_verdict": "every element with `needs_backend: true` from Stage 3 is covered by at least one endpoint; every endpoint's `service_dependencies` exist in the services layer; every endpoint's request/response shape's fields exist in the schema layer"
    }
  },
  "frozen_at": "<ISO 8601>",
  "_human_review_required": false
}
```

**Stage-4 CHECKLIST against stage 3:** the api layer's `covers_element_ids` UNION across all endpoints MUST equal the set of all element_ids in stage 3 with `needs_backend: true`. Any element not covered → fail.

**Reviewer convergence:** 3 reviewers each design one layer-pair independently (data+services, schema, api), then converge in Round 2. Round 3 architect verifies the cross-layer checklists (data → services → schema → api).

## Per-stage checklists are the gate

| Stage | Reads as checklist | Must satisfy |
|---|---|---|
| Stage 1 | (none — the seed) | All 6 fields populated; deployment_environment_hint present if codebase has any |
| Stage 2 | Stage 1's `personas_count` | Every persona has research_sources + expected_workflows + expected_data_needs + expected_affordances |
| Stage 3 | Stage 1's `pages_count` + Stage 2's `expected_workflows` + `expected_affordances` | Total pages count matches; every workflow reachable from a page; every affordance reflected in element classifications |
| Stage 4 data layer | Stage 3's elements with `needs_backend: true` OR `is_dynamic: true` | Every such element has a data_point |
| Stage 4 services layer | Stage 4 data layer | Every data_point has a service |
| Stage 4 schema layer | Stage 4 data layer | Every data_point maps to a schema column |
| Stage 4 api layer | Stage 3 elements with `needs_backend: true` + Stage 4 services + Stage 4 schema | Every element covered by an endpoint; every endpoint's deps exist |

A stage cannot freeze until its checklist returns `verdict: pass`. The orchestrator gates the next stage's dispatch on the prior stage's frozen artifact.

## 3-reviewer convergence per stage

Each stage dispatches 3 reviewer agents in parallel (same v0.9.19 pattern as `interaction-completeness`):

1. **Round 1 (independent):** each reviewer produces their own draft of the stage's required output.
2. **Round 2 (round-robin):** each reviewer reads the other two's drafts; disputes resolve by re-reading evidence; agreements crystallize.
3. **Round 3 (architect review):** the `system-architect` agent (in dedicated `Visual-to-API Design Audit` mode) reviews the converged draft for completeness against the stage's checklist; a populated finding is a verdict-failure condition.

Reviewers are **read-only on source code** — they don't edit the codebase; they produce the structured artifact. The artifact is the gate; the orchestrator dispatches the next stage's reviewers when the architect's Round 3 verdict is `pass`.

## New SR origin kind

`api-design-stage-incomplete` joins the canonical SR origin-kind list. Fires when:

- A stage's checklist returns `verdict: fail` (e.g., Stage 3 has only 12 pages but Stage 1 said 14).
- A stage's converged artifact is missing a required field.
- A cross-stage checklist fails (e.g., Stage 4 api layer has elements not covered by any endpoint).

The orchestrator routes the SR to the reviewer team to fix; the run does not progress to the next stage until the SR closes.

## When this skill runs

The skill is invoked at Phase 0 (Detection & Normalization) when ANY of the following holds:

1. **Explicit signal (v2.15.0 — canonical entry point).** `<workspace>/.architect-team/intake-state.json::intake_mode == "visual-to-api"`, set by the dedicated slash command `/architect-team:visual-to-api <codebase-path>`. This signal SHORT-CIRCUITS the heuristic detection — when present, the skill runs unconditionally even if a requirements folder is also present. Use this when you want the visual-to-API pipeline regardless of the input shape.
2. **Heuristic — codebase + no requirements.** `/architect-team` is given a visual codebase URL or path AND no explicit requirements folder.
3. **Heuristic — partial requirements + explicit derive ask.** An existing requirements folder is partial AND the user explicitly asks to derive the API from the UI.
4. **Heuristic — prose pattern.** The user invokes `/architect-team` with prose like *"review this codebase and design the API"* / *"derive the API from the UI"* / *"build out the backend for this frontend"*.

For pure-feature pipelines with full upfront requirements AND no explicit `intake_mode == "visual-to-api"` signal, this skill is a no-op (the requirements ARE the checklist, not the visual code).

### How the explicit signal is set

The `/architect-team:visual-to-api <codebase-path>` slash command writes `intake_mode: "visual-to-api"` to `<workspace>/.architect-team/intake-state.json` BEFORE invoking the `architect-team-pipeline` skill. The pipeline at Phase 0 reads the signal in this order:

1. **Check explicit signal first.** If `intake_mode == "visual-to-api"`, dispatch the `visual-to-api-design` skill unconditionally. Skip the heuristic detection.
2. **Fall back to heuristic detection.** If `intake_mode` is unset or has a different value, apply the path/prose heuristics above to decide whether to dispatch.

The explicit signal is the canonical way for users to FORCE this pipeline when they know they want the 4-stage workflow. The heuristic paths remain for backwards compatibility and for users who don't know about the dedicated command yet.

## Cross-references

- `skills/interaction-completeness/SKILL.md` — the v0.9.19 3-reviewer convergence pattern this skill reuses per stage.
- `skills/intake-and-mapping/SKILL.md` — produces the codebase scan that Stage 1 reads.
- `hooks/vao_tools.py::verify_affordance_coverage` — the 13th Layer 3 tool that catches the file-upload-style affordance gap Stage 3 element classifications must address.
- `agents/system-architect.md` `Visual-to-API Design Audit` mode (NEW v2.13.0) — runs Round 3 of every stage.
- `agents/codebase-map-reviewer.md` — the existing reviewer pattern this skill's per-stage reviewers extend.
- `ralph-loop:ralph-loop` (the `/ralph-loop` skill) — every Exploration Pipeline stage's 3-reviewer convergence runs INSIDE this loop with a total-agreement completion-promise (same pattern as `intake-and-mapping`).
- The openspec skill — `openspec-propose` / `opsx:propose` — the OpenSpec authoring mechanism Stages 4 and 7 call (never hand-written JSON).
- `skills/design-fidelity-mapping/SKILL.md` (DESIGN_MAP) — Stage 3a reuses its per-element type/attribute/static-dynamic capture; unconditional raw-HTML-attribute capture is added on top.
- `skills/frontend-route-mapping/SKILL.md` (ROUTE_MAP) — Stage 3b reuses the route inventory and annotates each route with impacted personas.
- `skills/dynamic-value-discovery/SKILL.md` — Stage 3a's `value_class: dynamic | static` classification follows it (classify from context, never the literal); feeds Stage 5's per-page returns.
- `skills/phenotypes/SKILL.md` (`phenotypes/user-management`, `phenotypes/ai-management`, `phenotypes/config-management`) — Stage 7 fires the three phenotype domain gates (user-management / AI-management / OpenTofu config-management).
- `hooks/vao_tools.py::verify-every-element` — the 100%-coverage checker pattern Stages 3c and 5 reuse (every element mapped to a component / a return field).
- `common-pipeline-conventions` `## Standardized documentation naming` — the canonical home of the five `*_MAP.md` doc names + paths + frontmatter schemas (`PERSONA_MAP.md`, `COMPONENT_ARCHITECTURE_MAP.md`, `API_RETURNS_MAP.md`, `API_DESIGN_MAP.md`, `DATA_ARCHITECTURE_MAP.md`); this skill references that standard rather than duplicating it.
- New SR origin kind `api-design-stage-incomplete` — routes incomplete-stage findings back to the reviewer team.
- Companion to v2.6.0 live-data wiring (catches mock-state survival on the built feature) + v2.11.0 multi-persona path-coverage (verifies the built feature works per persona) — different axis, same root principle: **the structured-checklist pattern catches what ad-hoc review misses**. This skill provides the upstream structure; v2.6.0/v2.11.0/v2.13.0 affordance discovery provide the downstream verification.

## Operating rules (non-negotiable)

1. **Stages are frozen in order.** Stage N+1 cannot start until Stage N's artifact is frozen + architect-pass.
2. **Checklists gate the freeze.** A stage's converged artifact cannot freeze until its checklist returns `verdict: pass`.
3. **3-reviewer convergence per stage** — never 2, never 1.
4. **Read-only on source.** Reviewers produce artifacts; they don't edit the codebase.
5. **Cross-stage references by SHA.** Each stage's artifact carries `based_on_stage_<N-1>: "<sha-of-prior-artifact>"` so downstream verification can prove the chain.
6. **No deferral.** Per v2.10.0 — every stage that finds a gap routes an SR (`api-design-stage-incomplete`); it does not catalogue the gaps as "deferred" at the end of the run.
7. **Stage 4's API layer MUST cover every Stage 3 element marked `needs_backend: true`.** No partial API designs; the v2.7.0 pattern-propagation discipline applies (no follow-up offers).
8. **Every stage runs inside a ralph-loop.** Each of the 7 Exploration Pipeline stages wraps its 3-reviewer convergence in `ralph-loop:ralph-loop` with an explicit `--completion-promise` = total reviewer agreement (100% fidelity). There is no iteration cap — the loop runs until convergence. A stage cannot freeze on partial agreement; a genuinely unsettleable requirement (needing an owner decision) routes an `api-design-stage-incomplete` SR for required owner input while the run continues.
9. **OpenSpec is authored via the openspec skill.** Stages 4 and 7 produce OpenSpec via `openspec-propose` / `opsx:propose` — NEVER hand-written OpenSpec JSON or spec files.
10. **Scope gates the frontend/backend stages.** Stage 0 classifies `frontend-only | backend-only | both`; the frontend stages (1–6) run iff frontend is in scope and the backend stage (7) runs iff backend is in scope.
11. **Run-time inputs are read, never guessed.** `language`, `component_libraries`, and `ancillary_docs` come from the brief frontmatter or project config; absence (when FE/component work is in scope) escalates via a domain gate.
12. **The 4-stage subset stays valid.** The original 4-stage flow + the `/architect-team:visual-to-api` command remain a valid, unchanged subset of the 7-stage Exploration Pipeline.
