# exploration-pipeline Specification

## Purpose
TBD - created by archiving change exploration-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Stage 0 — scope detection

The extended `visual-to-api-design` skill SHALL begin with an explicit scope-detection stage that classifies the run as `frontend-only`, `backend-only`, or `both`, surfacing the existing `intake-and-mapping` classification, and branches the downstream stages accordingly.

#### Scenario: scope is classified and branches the flow

- **WHEN** the skill body is read
- **THEN** Stage 0 names the three scope outcomes (`frontend-only` / `backend-only` / `both`)
- **AND** it states that the frontend stages (1-6) run only when frontend is in scope and the backend stage (7) runs only when backend is in scope

### Requirement: Stage 1 — persona catalog + application classification

When frontend is in scope, the skill SHALL catalog ALL personas (user types) by reading the frontend plus the configured ancillary documents, and classify the whole application — reusing `visual-to-api-design` Stage 1 (context discovery).

#### Scenario: personas and classification are produced

- **WHEN** Stage 1 runs with frontend in scope
- **THEN** it enumerates every distinct persona/user-type and an application classification (purpose / industry / use-case)
- **AND** it reads the configured `ancillary_docs` as a first-class input

### Requirement: Stage 2 — per-persona objective document (PERSONA_MAP.md)

For each persona, the skill SHALL write an objective document describing what that persona wants to achieve in this industry while using this product, emitted as the standardized `PERSONA_MAP.md` (one objective section per persona).

#### Scenario: PERSONA_MAP.md carries one objective section per persona

- **WHEN** Stage 2 completes
- **THEN** `<codebase>/docs/PERSONA_MAP.md` exists with a section per persona containing the persona's role, industry context, and the objectives they want to achieve with the product

### Requirement: Stage 3a — page/element catalog with attributes and dynamic/static

The skill SHALL list every page, then every element on each page, capturing for each element its type, its HTML attributes, and a `dynamic` vs `static` classification — reusing `visual-to-api-design` Stage 3 + `design-fidelity-mapping`, with raw-HTML-attribute capture performed unconditionally.

#### Scenario: every element is catalogued with attributes + classification

- **WHEN** Stage 3a completes
- **THEN** the catalog lists every page and, per page, every element with `{type, html_attributes, value_class: dynamic|static}`
- **AND** the dynamic/static classification follows `dynamic-value-discovery` (classify from context, never from the literal)

### Requirement: Stage 3b — route maps mapped to impacted personas

The skill SHALL construct route maps (reusing `frontend-route-mapping` ROUTE_MAP) and produce a route↔persona cross-map identifying, for every route, which personas it impacts.

#### Scenario: every route maps to its impacted personas

- **WHEN** Stage 3b completes
- **THEN** each route in the ROUTE_MAP is annotated with the personas it impacts (drawn from the PERSONA_MAP)

### Requirement: Stage 3c — reusable-component architecture (COMPONENT_ARCHITECTURE_MAP.md)

The skill SHALL propose a reusable-component architecture in the configured language + component libraries, map every proposed component against the full element list for 100% coverage, record the exact per-page placement of each component (pixel-perfect when design inputs exist; structural placement otherwise), and declare each component's expected payload consumption — emitted as `COMPONENT_ARCHITECTURE_MAP.md`. This is a multi-agent (≥3) doc-passing task.

#### Scenario: components cover 100% of elements with placement + payload

- **WHEN** Stage 3c completes
- **THEN** `COMPONENT_ARCHITECTURE_MAP.md` maps every catalogued element to a proposed component (100% coverage, verifiable via a `verify-every-element`-style check)
- **AND** each component records the exact pages it is placed on and its expected payload consumption
- **AND** the proposed components use the configured language + component libraries

### Requirement: Stage 4 — conversion to OpenSpec via the openspec skill

The skill SHALL convert the component-architecture conversion plan into OpenSpec documents using the openspec skill (`openspec-propose` / `opsx:propose`), with ≥3 agents in parallel, validating that 100% of the plan is converted.

#### Scenario: OpenSpec is produced via the openspec skill and covers 100%

- **WHEN** Stage 4 completes
- **THEN** the skill body invokes the openspec skill (not hand-written JSON) to author the conversion OpenSpec
- **AND** a coverage check confirms 100% of the conversion plan is represented in the OpenSpec artifacts

### Requirement: Stage 5 — per-page REST returns (API_RETURNS_MAP.md)

The skill SHALL specify, per page, the most efficient REST/API returns powering that page — the data needed and its shape — such that every element's data source is identified and 100% of data-bearing elements are covered, emitted as `API_RETURNS_MAP.md`. "Most efficient" is defined measurably as: no returned field is unconsumed by any element on the page (over-fetch budget = 0 unconsumed top-level fields), and pages sharing data reuse the same return shape.

#### Scenario: every data-bearing element has an identified return source

- **WHEN** Stage 5 completes
- **THEN** `API_RETURNS_MAP.md` lists, per page, the API return shape(s) powering it and maps every dynamic element to a field in a return
- **AND** the over-fetch check flags any return field consumed by no element

### Requirement: Stage 6 — consolidated API design with play-test (API_DESIGN_MAP.md)

The skill SHALL holistically propose a target API structure that maximizes endpoint reusability, provides CRUD operations where the data model requires them, and shapes returns by user-type; it SHALL design-time play-test each page against the proposed API, documenting how every component calls the API or consumes a consolidated return — emitted as `API_DESIGN_MAP.md`. "Max reusability" is defined measurably as: every page's needs are satisfiable from the consolidated endpoint set, and no two endpoints serve identical element sets.

#### Scenario: consolidated API covers every page and is play-tested

- **WHEN** Stage 6 completes
- **THEN** `API_DESIGN_MAP.md` defines the consolidated endpoint set with CRUD coverage and per-user-type response shaping
- **AND** every page has a documented play-test trace showing each component is satisfied by an endpoint call or a consolidated return (100% of pages)

### Requirement: Stage 7 — backend data architecture + phenotype gates (DATA_ARCHITECTURE_MAP.md)

When backend is in scope, the skill SHALL derive the data architecture from the components + API requirements — reading the personas + platform use case, designing an extensibility-first schema for anticipated and examined potential use cases, selecting database types — and SHALL fire `phenotypes` domain-gates asking whether a user-management layer and an AI-management layer are needed (use phenotype or new guidance) and whether OpenTofu (or equivalent) exists for deploy (else use the config-management phenotype). It SHALL then turn the architecture into execution-ready OpenSpec requirements via the openspec skill. Output: `DATA_ARCHITECTURE_MAP.md`.

#### Scenario: data architecture is derived and phenotype gates fire

- **WHEN** Stage 7 runs with backend in scope
- **THEN** `DATA_ARCHITECTURE_MAP.md` records the extensible schema, the DB-type selection, and the anticipated/potential use cases considered
- **AND** the skill fires the phenotype domain-gate for user-management, AI-management, and (OpenTofu) config-management
- **AND** the final data-architecture requirements are emitted as OpenSpec via the openspec skill

### Requirement: Every stage is ralph-loop governed

Every stage's 3-reviewer doc-passing convergence SHALL run inside a `ralph-loop:ralph-loop` whose completion-promise is total agreement across all reviewers that the stage document meets every required step.

#### Scenario: each stage names its ralph-loop wrapping + exit criterion

- **WHEN** the skill body is read
- **THEN** each of the 7 stages states that its convergence runs inside the ralph-loop skill
- **AND** each names an explicit exit criterion (all reviewers agree the stage doc meets every step / 100% fidelity)

### Requirement: Standardized documentation naming scheme

The skill SHALL define and canonicalize the 5 standardized documentation artifacts with fixed names and `<codebase>/docs/` paths — `PERSONA_MAP.md`, `COMPONENT_ARCHITECTURE_MAP.md`, `API_RETURNS_MAP.md`, `API_DESIGN_MAP.md`, `DATA_ARCHITECTURE_MAP.md` — each with a documented frontmatter schema, generated for every project the pipeline runs against (created-on-ask in standalone mode), matching the existing `*_MAP.md` convention.

#### Scenario: the naming standard is canonical and documented

- **WHEN** `common-pipeline-conventions` (or the skill) is read
- **THEN** the 5 doc names + paths + frontmatter schemas are documented as the standard
- **AND** the auto-generation trigger (every pipeline run vs created-on-ask standalone) is stated

### Requirement: Run-time inputs declared in the brief/config

The target `language`, `component_libraries`, and `ancillary_docs` SHALL be read from the requirements brief frontmatter or a project config; their absence when frontend/component work is in scope SHALL be escalated to the user, not silently guessed.

#### Scenario: inputs are read from the brief, absence escalates

- **WHEN** Stage 3c needs the language + component libraries
- **THEN** the skill reads them from the brief/config
- **AND** if they are absent it escalates via a domain-gate rather than guessing

### Requirement: Structural tests, subset preservation, and release

The plugin SHALL ship structural tests asserting the 7 stages, the ralph-loop-per-stage wrapping, the openspec-skill binding, the 5 doc schemas, and the phenotype gates; the existing 4-stage `visual-to-api-design` subset and its command SHALL still validate; the version SHALL be bumped and docs brought current.

#### Scenario: tests pass and the subset is preserved

- **WHEN** `python -m pytest` runs after the change
- **THEN** the new exploration-pipeline structural tests pass
- **AND** the pre-existing `visual-to-api-design` 4-stage tests + its command still pass

