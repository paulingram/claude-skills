---
name: api-design-from-frontend
description: "Extracts the \"backend logic from frontend\" portion (Stages 5+6+7) of visual-to-api-design as a standalone reusable skill. Stage 5 per-page REST returns → API_RETURNS_MAP.md. Stage 6 consolidated API design + desk-trace play-test → API_DESIGN_MAP.md. Stage 7 backend data architecture → DATA_ARCHITECTURE_MAP.md + openspec change via openspec-propose. Each stage's 3-reviewer convergence wraps in a ralph-loop with total-agreement completion-promise. Inputs: PERSONA_MAP.md + page catalog + COMPONENT_ARCHITECTURE_MAP.md (or equivalent frontend artifacts). Callers: visual-to-api-design (refactors to delegate Stage 5+ here), architect-team-pipeline Phase 0b (backend dispatch when frontend or docs are referenceable). v3.4.0."
---

# API Design from Frontend

You are the **API Design from Frontend orchestrator**. Drive the 3-stage backend-logic flow that converts a frontend-derived structural model into a complete backend API + data architecture + OpenSpec change. The 3 stages are a strict subset of `visual-to-api-design`'s Stages 5+6+7, extracted here so they can be called standalone for backend-only requests with a frontend OR documentation reference.

## When this skill runs

Two callers as of v3.4.0:

1. **`visual-to-api-design` Stage 5 onward** — the 7-stage Exploration Pipeline delegates Stages 5+6+7 to this skill. The visual-to-api-design body's Stages 5+6+7 sections become thin pointers to this skill rather than carrying the implementation. Behavior preserved.

2. **`architect-team-pipeline` Phase 0b (B and C branches)** — backend-shaped request with a frontend codebase reference (read-only) OR documentation reference. After `cartographer-team` (B only) + `domain-research-team` produce the upstream artifacts, this skill runs Stages 5+6+7 directly to produce the API design + data architecture + OpenSpec change.

## Inputs

The caller passes a structured `inputs` object:

```json
{
  "persona_map_path": "<absolute-path-to-PERSONA_MAP.md>",
  "component_architecture_map_path": "<absolute-path-or-null>",
  "page_catalog_path": "<absolute-path-or-null>",
  "frontend_reference_path": "<absolute-path-or-null>",
  "doc_inputs": ["<absolute-path-to-doc>", ...],
  "output_dir": "<absolute-path-to-output-directory>",
  "openspec_change_name": "<kebab-case-change-name>",
  "frontend_read_only": true | false,
  "completion_promise": "API DESIGN COMPLETE"
}
```

`persona_map_path` is required. At least one of `component_architecture_map_path` / `page_catalog_path` / `frontend_reference_path` / `doc_inputs` MUST be non-empty (otherwise there's no frontend signal to design the API from).

## Phase A1 — Stage 5: per-page REST returns

For every page (or analogous unit — modal / widget / dashboard panel) in the input artifacts, derive the REST returns the page needs. Apply the v0.9.19 3-reviewer convergence pattern wrapped in `/ralph-loop "<stage-5 review prompt>" --completion-promise "API RETURNS MAP COMPLETE"`. The loop runs until the completion-promise is satisfied (total reviewer agreement); no iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`).

For each page entry:

```json
{
  "page_id": "<route or screen name>",
  "consumer_persona_ids": ["<persona-id>", ...],
  "returns": [
    {
      "endpoint_role": "primary" | "secondary" | "polling" | "long-running",
      "shape": "<JSON schema or one-line shape description>",
      "trace_to_elements": ["<element-id-or-component-id>", ...]
    }
  ]
}
```

Output: `<output_dir>/API_RETURNS_MAP.md` with frontmatter `{generated_at, pages_count, returns_count}`.

**3-reviewer convergence:** 3 reviewers independently check every page is covered, every return traces to ≥ 1 element on the page, and no two returns are duplicates of each other. Iterates until all 3 say `ok`.

## Phase A2 — Stage 6: consolidated API design + desk-trace play-test

Convert the per-page returns into a consolidated endpoint catalog optimized for reuse — every endpoint serves the maximum union of pages it can serve, with CRUD coverage where the data model needs it, and return-shape variants per user-type when persona-relevant.

For each endpoint:

```json
{
  "endpoint_id": "<HTTP_METHOD-path>",
  "http_method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  "path": "<route pattern>",
  "request_shape": "<JSON schema>",
  "response_shape_by_user_type": {
    "<persona-id>": "<JSON schema for that persona's view>",
    "_default": "<JSON schema>"
  },
  "side_effects": ["<creates X, updates Y, sends Z>", ...],
  "auth_requirement": "<auth scheme + required role>",
  "satisfies_pages": ["<page-id>", ...]
}
```

**Desk-trace play-test (mandatory):** for every page in `API_RETURNS_MAP.md`, the reviewers manually trace through which endpoint(s) the page would call, in what order, with what payloads. Every page MUST be fully satisfiable. Failures iterate.

**Stage-6 checklist (matches visual-to-api-design):**

- Every page satisfiable from the consolidated endpoint set.
- No two endpoints serve identical element sets.
- 100% of pages carry a play-test desk-trace.
- CRUD present where the data model needs it.
- Returns shaped by user-type where persona-relevant.

Output: `<output_dir>/API_DESIGN_MAP.md` with frontmatter `{generated_at, endpoints_count, user_types[]}`.

3-reviewer convergence wrapped in `/ralph-loop "<stage-6 review prompt>" --completion-promise "API DESIGN MAP COMPLETE"`. The loop runs until the completion-promise is satisfied (total reviewer agreement); no iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`).

## Phase A3 — Stage 7: backend data architecture + OpenSpec authoring

Derive the data architecture that serves the consolidated API design. Apply phenotype dispatch:

- If personas + auth requirements match the `user-management` phenotype's shape → propose seeding it.
- If the request involves multi-tenant LLM templates + budgets → propose `ai-management` phenotype.
- If the deployment surface (configured language + cloud) matches `config-management` → propose seeding its OpenTofu monorepo.

Each phenotype proposal goes through the v2.3.0 domain gate (user confirms via `AskUserQuestion`).

For the data architecture itself:

```json
{
  "entities": [
    {
      "entity_id": "<kebab-case>",
      "attributes": [{"name": "<attr>", "type": "<type>", "constraints": [...]}],
      "relationships": [{"to": "<entity-id>", "kind": "one-to-many" | "many-to-many" | "..."}]
    }
  ],
  "db_types_per_entity": {"<entity-id>": "postgres" | "redis" | "dynamodb" | "..."},
  "extensibility_choices": [
    {"choice": "<one-line decision>", "rationale": "<why>"}
  ],
  "phenotype_proposals": ["user-management" | "ai-management" | "config-management"]
}
```

Output: `<output_dir>/DATA_ARCHITECTURE_MAP.md` with frontmatter `{generated_at, db_types[], phenotypes_used[], openspec_change}`.

**OpenSpec authoring via the openspec skill (non-negotiable per visual-to-api-design Operating Rule #9):** Stage 7 calls the openspec skill (`openspec-propose` / `opsx:propose`) to produce the OpenSpec change at `openspec/changes/<openspec_change_name>/`. The change carries:

- `proposal.md` documenting the API design + data architecture.
- `specs/` capturing every endpoint as a REQ.
- `design.md` with reuse-first decisions (per `reuse-first-design`).
- `tasks.md` decomposing the implementation.

Hand-written OpenSpec JSON is forbidden.

3-reviewer convergence wrapped in `/ralph-loop "<stage-7 review prompt>" --completion-promise "DATA ARCHITECTURE MAP COMPLETE"`. The loop runs until the completion-promise is satisfied (total reviewer agreement); no iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`).

## Phase A4 — Return verdict

Return to the caller:

```json
{
  "api_returns_map_path": "<...>",
  "api_design_map_path": "<...>",
  "data_architecture_map_path": "<...>",
  "openspec_change_path": "<...>",
  "summary": {
    "pages_count": N,
    "endpoints_count": N,
    "entities_count": N,
    "phenotypes_used": [...]
  }
}
```

## Frontend-read-only mode

When `frontend_read_only: true`:

- All input artifacts are read-only — `persona_map_path` / `component_architecture_map_path` / `page_catalog_path` / `frontend_reference_path` are NEVER modified.
- Output goes to the caller-configured `output_dir`. The caller is responsible for choosing a path outside the frontend codebase (typically `<workspace>/.architect-team/frontend-reference/<codebase-slug>/`).
- The OpenSpec change still lands at `openspec/changes/<openspec_change_name>/` in the WORKSPACE — that's the backend project's own openspec dir, not the frontend reference's.

## Disciplines this skill respects

- v3.0.0 unilateral-override — no stage can be skipped; each stage's checklist + 3-reviewer convergence is non-negotiable.
- visual-to-api-design Operating Rules #1–12 — stages frozen in order, checklists gate freezes, 3-reviewer convergence per stage, read-only on source, cross-stage references by SHA, no deferral, Stage 6 covers every Stage 5 element, every stage in ralph-loop, OpenSpec via the openspec skill, scope-gated stages, run-time inputs read never guessed, 4-stage subset stays valid.
- v0.9.19 3-reviewer convergence — the canonical pattern per stage.

## What this skill is NOT

- Not a complete frontend-to-backend exploration — `visual-to-api-design` runs Stages 0–4 before invoking this skill (or Phase 0b runs `domain-research-team` + `cartographer-team` first).
- Not an implementer — produces the OpenSpec change (the planning layer); Phase 2 of the architect-team-pipeline implements it.
- Not a fix loop — gaps surface to the caller; this skill doesn't file SRs itself.
