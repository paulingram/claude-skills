# Phase 0b — Backend dispatch check (v3.4.0)

Runs ONLY when Phase 0a was a no-op AND the run is backend-shaped — i.e., the bug-classifier at Phase −2 returned `kind: feature` AND the Phase −1A classification surfaces a `backend` / `library` / `infra` / `data-pipeline` codebase (with or without a frontend in scope). Per `common-pipeline-conventions/SKILL.md` `## Backend-from-frontend dispatch + analysis modularization (v3.4.0)`:

1. **Branch A — Existing API extension.** An existing backend codebase is in scope AND the request adds endpoints to it (extending, not designing from scratch). Detected by: the bug-classifier verdict OR the request prose ("add endpoint X to Y" / "extend the existing API") OR the Phase 0 normalization preview classifying as `openspec` against an existing change folder. **NO dispatch.** Phase 0 proceeds with its normal classification + normalization; Phase 1 enforces dev-API-integration-testing criteria primary.

2. **Branch B — Greenfield API + frontend codebase referenceable.** A frontend codebase is in scope OR named in `$REQ_DIR` AS A REFERENCE (not as a refactor target). Detected by: Phase −1A surfaced a frontend codebase classification AND the request prose explicitly says *"design the backend from this frontend"* / *"read-only reference"* / *"derive the API from this UI"*, OR the brief's frontmatter sets `reference_codebases: [...]` with codebases that are not `$REQ_DIR`'s primary work target. **Dispatch ladder:**
   - Set `intake-state.json::frontend_read_only = true` and `frontend_reference_codebase = <absolute-path>`.
   - Dispatch `cartographer-team` with `inputs.frontend_read_only = true` and `inputs.output_path = <workspace>/.architect-team/frontend-reference/<codebase-slug>/CODEBASE_MAP.md` (+ ROUTE_MAP.md for frontends).
   - Dispatch `domain-research-team` with `inputs.frontend_read_only = true` and `inputs.output_path = <workspace>/.architect-team/frontend-reference/<codebase-slug>/PERSONA_MAP.md`. The skill MUST perform the outside-research mandate regardless of input completeness (per its body's Phase R2).
   - Dispatch `api-design-from-frontend` with `inputs.persona_map_path = <workspace>/.architect-team/frontend-reference/<codebase-slug>/PERSONA_MAP.md` + `inputs.frontend_reference_path = <absolute-path>` + `inputs.output_dir = <workspace>/.architect-team/frontend-reference/<codebase-slug>/`. The 3-stage flow (Stages 5+6+7) produces `API_RETURNS_MAP.md` + `API_DESIGN_MAP.md` + `DATA_ARCHITECTURE_MAP.md` + an openspec change via `openspec-propose`.

3. **Branch C — Greenfield API + documentation referenceable (no frontend codebase).** No frontend codebase is in scope, BUT `$REQ_DIR` cites documentation (PDFs / markdown / API specs / product briefs / brand docs) OR the brief's frontmatter sets `reference_docs: [...]`. **Dispatch ladder:**
   - Dispatch `domain-research-team` with `inputs.doc_inputs = [<paths>]` and `inputs.output_path = <workspace>/.architect-team/doc-reference/PERSONA_MAP.md`. The skill MUST perform outside research (the doc-only path makes the outside-research mandate even more critical — docs frame the problem; outside research grounds the personas + objectives in industry reality).
   - Dispatch `api-design-from-frontend` with `inputs.persona_map_path = <workspace>/.architect-team/doc-reference/PERSONA_MAP.md` + `inputs.doc_inputs = [<paths>]` + `inputs.output_dir = <workspace>/.architect-team/doc-reference/`. The 3-stage flow produces the same 3 maps + openspec change.

4. **Branch D — Pure greenfield, no reference at all.** No frontend codebase, no docs. **NO dispatch.** Phase 0 proceeds with its normal `plain` branch authoring.

### Frontend-read-only enforcement (non-negotiable)

When Branch B fires, `frontend_read_only: true` is set in `intake-state.json` for the rest of the run. This affects:

- The 3 dispatched skills (`cartographer-team`, `domain-research-team`, `api-design-from-frontend`) — each MUST honor the flag and route output to the alternate `<workspace>/.architect-team/frontend-reference/<codebase-slug>/` path instead of `<frontend-codebase>/docs/`. Each skill body documents this explicitly.
- The frontend's working tree is NEVER modified. Any `Write` / `Edit` targeting a path under `frontend_reference_codebase` during this run is a v3.0.0 unilateral-override violation that the PreToolUse guardrail should catch.
- The frontend's `.architect-team/intake-state.json` (if it exists separately) is NEVER touched.

### How Phase 0 reacts

When Branch B or C fires AND completes successfully:

- **Skip the `plain` branch's `openspec init` + artifact-authoring loop** in Phase 0 step 3 below — the OpenSpec change already exists, authored by the openspec skill via `api-design-from-frontend` Stage A3.
- **Phase 0 still runs** to (a) classify the now-existing OpenSpec change (it will classify as `openspec`), and (b) treat the produced maps as binding inputs (the same pattern as Phase 0a).
- **Phase 1's planning validation loop** then operates on the openspec change at the same bar as any other openspec input. The `dev-api-integration-testing` criteria are primary; Playwright criteria remain N/A (no frontend was refactored — the frontend was a read-only reference).

When Branch A or D applies (no dispatch), Phase 0 proceeds unchanged.

This step is the explicit pre-action half of the Phase 0b contract; the post-action half (Stages 5+6+7 output binding into Phase 1) is enforced by Phase 1's standard validation against the produced openspec change.
