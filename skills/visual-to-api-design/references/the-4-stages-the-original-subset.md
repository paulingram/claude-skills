# The 4 stages (the original subset)

The original 4-stage flow is the canonical SUBSET of the Exploration Pipeline (see `## The Exploration Pipeline — 7 stages` above) and remains valid and unchanged — invoked directly by the `/architect-team:visual-to-api` command. Each stage produces a frozen JSON artifact stored at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json`. Each stage runs the v0.9.19 3-reviewer convergence protocol (3 independent reviewer agents → round-robin Round 2 → architect Round 3) before its artifact is frozen; in the full Exploration Pipeline that convergence is additionally wrapped in a `ct6-converge` workflow (see governance above), but the 4-stage subset's convergence semantics are unchanged. Each subsequent stage reads the prior stage's frozen artifact as its CHECKLIST.

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
