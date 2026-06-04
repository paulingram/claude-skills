---
name: visual-to-api-design
description: Use when the architect-team is invoked against a visual codebase (UI present, requirements absent OR partially specified) and must DERIVE the API design from what the screens reveal. Runs a 4-stage pipeline — context-discovery → per-persona research → page catalog → backend-from-frontend design — with 3-reviewer convergence per stage and per-stage checklists that gate the next stage. Each stage's output is a frozen structured artifact; the next stage uses the prior artifact as its checklist. Stage 4 (backend design) is checked against Stage 3 (page catalog) for completeness — every element on every page MUST trace to a data point in the API mock; every API endpoint MUST trace to a service that delivers the data. The pipeline is invoked at Phase 0 when the requirement is "review this codebase / design the API for this visual."
---

# Visual-to-API Design Pipeline

When the architect-team is given a visual codebase (a UI repo, a Figma export, a deployed site URL) but no explicit requirements OR only partial requirements, this skill produces the API design that the visual code implies. The pipeline runs in 4 stages, each stage frozen before the next begins, each stage reviewed by 3 independent agents in convergence (the v0.9.19 pattern), each stage's output the explicit checklist the next stage must satisfy.

## The failure shape this closes (verbatim from the user)

> "lets optimize how we analyze viaul codebases for API desing. the first thin our agents should do is 1) discover the overall context and document. what is the purpose of the application, how many pages, how many user persons. What industry is it in, what use case does it appear to address etc. 2) then it must, for ecah persona, research what they woudl be using the platform for, reading documentation and internet searches. this must be recorded 3) then a complete catalog of each page must be made. first we identify all the pages, then for ecah page, identify every element on it. For ecah element, you will review it, classify it, make a blurb about it, and idnetify if it needs a backend built or if it needs to be dynamic etc.. such as a name field that must be a dynamic variable etc... 4) finally, once that is done, you will take all this context and devise a bakcend that solves for the front end use case, starting by defining the data needed to be returned or adsorbed, then defining the services needed such as database services etc...then the schema - for each return mock, you need to consolidate and come up with a data schema that properly solves all cases. Then finally, define the API layer - what are the endpoints, how do these map to the tables or services etc...you will use each prior step as a checklist. For example - when enurmeating the api, you will pass that by making sure the API layer accesses all the data. The data and schema layer will rely on solving the prior step - can it provide the data. Then the data return layer mocks must check list against every element identified on the page etc... you will do this with 3 agents who review each others work at each stage for completeness. Review this and optimize accordingly but ensure each step is inforprated"

Existing reviews of visual codebases jumped straight to "what does this UI do?" without first establishing context, persona research, exhaustive page catalog, OR a checklist-driven backend design. The result was an API design that *mostly* covered what was on screen but missed entire affordances (the v2.13.0 file-upload case) AND missed per-element data needs (a name field that should be dynamic but was treated as static). v2.13.0 ships the structured pipeline that makes both gaps structurally impossible.

## The 4 stages

Each stage produces a frozen JSON artifact stored at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json`. Each stage runs the v0.9.19 3-reviewer convergence protocol (3 independent reviewer agents → round-robin Round 2 → architect Round 3) before its artifact is frozen. Each subsequent stage reads the prior stage's frozen artifact as its CHECKLIST.

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

The skill is invoked at Phase 0 (Detection & Normalization) when:

1. `/architect-team` is given a visual codebase URL or path AND no explicit requirements folder.
2. OR an existing requirements folder is partial (carries some specs but the user explicitly asks to derive the API from the UI).
3. OR the user invokes `/architect-team` with prose like "review this codebase and design the API."

For pure-feature pipelines with full upfront requirements, this skill is a no-op (the requirements ARE the checklist, not the visual code).

## Cross-references

- `skills/interaction-completeness/SKILL.md` — the v0.9.19 3-reviewer convergence pattern this skill reuses per stage.
- `skills/intake-and-mapping/SKILL.md` — produces the codebase scan that Stage 1 reads.
- `hooks/vao_tools.py::verify_affordance_coverage` — the 13th Layer 3 tool that catches the file-upload-style affordance gap Stage 3 element classifications must address.
- `agents/system-architect.md` `Visual-to-API Design Audit` mode (NEW v2.13.0) — runs Round 3 of every stage.
- `agents/codebase-map-reviewer.md` — the existing reviewer pattern this skill's per-stage reviewers extend.
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
