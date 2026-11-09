# Backend-from-frontend dispatch + analysis modularization (v3.4.0)

v3.4.0 extracts the analysis primitives previously inline in `intake-and-mapping` and `visual-to-api-design` into 3 standalone reusable skills, AND adds `Phase 0b — Backend dispatch check` for backend-shaped requests with optional frontend OR documentation references. Three orthogonal jobs that were entangled:

| Job | Old home (inline) | New home (skill) |
|---|---|---|
| Run cartographer + 3-reviewer convergence + targeted re-mapping | `intake-and-mapping` step B (inline block) | `cartographer-team` skill |
| Run 3-researcher convergence with codebase + outside research | `intake-and-mapping` step C (inline); `visual-to-api-design` Stages 1+2 (inline) | `domain-research-team` skill |
| Per-page returns + consolidated API design + backend data architecture (the "backend logic from frontend" portion of the Exploration Pipeline) | `visual-to-api-design` Stages 5+6+7 (inline) | `api-design-from-frontend` skill |

Existing pipelines refactor to DELEGATE to the new skills (behavior preserved; inline-in-skill-body → dispatch-the-skill), so the analysis capabilities are callable from any pipeline and a backend-only request with a frontend reference can run the analysis stages without the visual-to-api-design wrapper.

### Phase 0b decision tree

Inserted into `architect-team-pipeline/SKILL.md` between Phase 0a (Visual-to-API dispatch, v3.3.1) and Phase 0 (Detection & Normalization). Fires when Phase 0a was a no-op AND the run is backend-shaped; the first matching branch wins:

- **A. Existing API extension** — an existing backend codebase is in scope AND the request adds endpoints to it → NO dispatch; proceed to Phase 0 with `dev-api-integration-testing` criteria primary.
- **B. Greenfield API + frontend codebase** referenceable — a frontend codebase is in scope or named in the brief AS A REFERENCE → dispatch `cartographer-team` (frontend, READ-ONLY) for `CODEBASE_MAP.md` + `ROUTE_MAP.md`, `domain-research-team` (frontend + outside-research mandate) for `PERSONA_MAP.md` + objectives, then `api-design-from-frontend` for `API_RETURNS_MAP.md` + `API_DESIGN_MAP.md` + `DATA_ARCHITECTURE_MAP.md` + openspec change.
- **C. Greenfield API + documentation** referenceable — no frontend codebase but the brief cites docs (PDFs / markdown / API specs / brand docs) → dispatch `domain-research-team` (docs + MANDATORY outside research) then `api-design-from-frontend` using the docs-derived personas.
- **D. Pure greenfield**, no reference at all → NO dispatch; proceed to Phase 0 plain-branch authoring.

### Frontend-read-only enforcement (non-negotiable)

When Phase 0b dispatches against a frontend codebase as a REFERENCE (not a refactor target), the orchestrator:

1. Sets `frontend_read_only: true` in `<workspace>/.architect-team/intake-state.json`.
2. Sets `frontend_reference_codebase: <absolute-path>` to identify which codebase is the reference.
3. Routes ALL analysis-skill output to `<workspace>/.architect-team/frontend-reference/<codebase-slug>/` INSTEAD of `<frontend-codebase>/docs/`.
4. The dispatched skills (`cartographer-team`, `domain-research-team`) MUST honor the flag: any `Write` / `Edit` targeting a path under `frontend_reference_codebase` is a discipline violation.
5. The v3.0.0 PreToolUse guardrail's allow-list extends to include `.architect-team/frontend-reference/` (which is already covered by the `.architect-team/` allow-prefix).

The intent: the frontend codebase is examined as evidence; it is never modified. The analysis-derived artifacts live in a separate location so the frontend project's working tree stays untouched.

### domain-research-team's mandatory outside research

The `domain-research-team` skill REQUIRES every researcher to perform outside research (industry / market / competitors / related products), **regardless of whether docs or a frontend codebase are provided as inputs** (driver in CHANGELOG v3.4.0: *"it must … actually perform outside research … even if docs are provided"*). Concrete implementation:

- The new `domain-researcher` agent (opus, color amber) carries `WebFetch` + `WebSearch` in its tool allowlist (in addition to the standard read/glob/grep/bash/write set).
- Phase R2 of `domain-research-team` is the "Outside research" phase — every researcher independently runs queries against the industry / market / competitor surface relevant to the inputs.
- The skill's completion-promise (`DOMAIN RESEARCH COMPLETE`) requires that every researcher's output JSON include a non-empty `outside_research` block (with at least 1 industry query, 1 market context query, 1 competitor product cited).
- If a researcher returns an empty `outside_research` block, the ct6-converge workflow iterates with the deficiency surfaced.

### Cross-references

- `skills/cartographer-team/SKILL.md` — the new cartographer + 3-reviewer skill body.
- `skills/domain-research-team/SKILL.md` — the new 3-researcher + master-synthesizer skill body with outside-research mandate.
- `skills/api-design-from-frontend/SKILL.md` — the new Stages 5+6+7 extraction.
- `agents/domain-researcher.md` — the new researcher agent (WebFetch + WebSearch enabled).
- `skills/architect-team-pipeline/SKILL.md` `## Phase 0b — Backend dispatch check (v3.4.0)` — the orchestrator-side wiring.
- `skills/intake-and-mapping/SKILL.md` — refactored: step B delegates to `cartographer-team`, step C delegates to `domain-research-team`. Behavior preserved.
- `skills/visual-to-api-design/SKILL.md` — refactored: Stages 1+2 delegate to `domain-research-team`, Stages 5+6+7 delegate to `api-design-from-frontend`. The 7-stage flow is preserved structurally; the internal implementation now delegates.
- `tests/test_phase_0b_backend_dispatch.py` — symmetry test (parallel to v3.3.1's Phase 0a symmetry) asserting both the main pipeline body and each dispatched skill document the same contract.
- Companion to v3.3.1 visual-to-api dispatch symmetry — same architectural principle (modular, reusable skills with explicit dispatch contracts on both sides) applied to the backend-from-frontend surface.
