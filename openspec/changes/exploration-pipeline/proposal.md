## Why

The plugin already has the pieces of a frontend→backend discovery flow, but they are scattered and under-orchestrated. `visual-to-api-design` runs a 4-stage context→personas→page-catalog→backend-design with its own 3-reviewer convergence — but it writes only stage JSON (zero OpenSpec), it does not propose a reusable-component architecture, it has no per-page REST-returns or consolidated-API-with-play-test stage, and its convergence is not the mandated `/ralph-loop`. The user wants ONE formalized, standardized "Exploration Pipeline" that takes a frontend (+ ancillary docs + a language/component-library config) and drives it through 7 ralph-loop-governed stages to a standardized documentation set and execution-ready OpenSpec — reusing everything that already exists and adding only what is genuinely missing.

A reconciliation sweep (read every overlapping skill) found: of the 7 stages' sub-steps, **6 already exist, 4 are partial, 2 are net-new**. The decision (user-confirmed) is to **EXTEND `visual-to-api-design` in place** from 4 → 7 stages — one skill, the current 4-stage entry point preserved as a subset — rather than create a second overlapping skill (the exact duplication just consolidated away in v3.1.0).

## What Changes

- **Extend** `skills/visual-to-api-design/SKILL.md` from 4 → 7 stages (the core change). The existing 4-stage subset + `/architect-team:visual-to-api` command keep working. (REQ-001…REQ-010)
- **Stage 0 — scope detection** (FE / BE / both) as an explicit branching gate, surfacing the existing `intake-and-mapping` classification. (REQ-001)
- **Stages 1-2 — personas + per-persona objective doc** — reuse `visual-to-api-design` Stage 1+2; formalize output as `PERSONA_MAP.md` (one objective section per persona: who, industry, what they want to achieve with this product); add `ancillary_docs` as a first-class input. (REQ-002, REQ-003)
- **Stage 3 — frontend maps** — reuse Stage 3 + `design-fidelity-mapping` + `frontend-route-mapping`; ADD unconditional per-element raw-HTML-attribute capture + an explicit page→element list form; ADD a route↔persona impact cross-map. (REQ-004, REQ-005)
- **Stage 3c — reusable-component architecture (NET-NEW)** — propose components in the configured language + component libraries, mapped 1:1 to 100% of catalogued elements, with exact per-page placement (pixel-perfect, DESIGN_MAP-gated) and per-component payload consumption → `COMPONENT_ARCHITECTURE_MAP.md`. (REQ-006)
- **Stage 4 — conversion → OpenSpec** via the **openspec skill** (`openspec-propose`/`opsx:propose`); ralph-loop-gated; 100% conversion. (REQ-007)
- **Stage 5 — per-page REST returns** → `API_RETURNS_MAP.md`; every element's data source identified; ralph-loop, strict exit. (REQ-008)
- **Stage 6 — consolidated API design** → `API_DESIGN_MAP.md`; maximize endpoint reuse, CRUD where needed, return-by-user-type; design-time play-test of each page against the proposed API. (REQ-009)
- **Stage 7 — backend data architecture** → `DATA_ARCHITECTURE_MAP.md`; extensibility-first schema; phenotype domain-gates for user-management / AI-management / (OpenTofu) config-management; DB-type selection; then OpenSpec requirements via the **openspec skill**. (REQ-010)
- **Cross-cutting** — every stage's 3-reviewer convergence runs INSIDE a `ralph-loop:ralph-loop` (REQ-011); the 5 standardized `*_MAP.md` docs are canonicalized with fixed names/paths/frontmatter + an auto-generation trigger (REQ-012); run-time inputs (`language`, `component_libraries`, `ancillary_docs`) are read from the brief/project config (REQ-013).
- **Tests + release** — structural tests for the 7 stages, the ralph-loop wrapping, the openspec-skill binding, the 5 doc schemas, the phenotype gates; the existing 4-stage subset still validates; version bump + docs. (REQ-014)

This produces DOCS + execution-ready OpenSpec REQUIREMENTS; the existing `architect-team-pipeline` Phase 2-8 builds the app from them. No discipline's behavior changes; no second overlapping skill is created.

## Capabilities

### New Capabilities

- `exploration-pipeline`: a standardized, ralph-loop-governed, 7-stage frontend→backend discovery pipeline (an in-place extension of `visual-to-api-design`) that turns a frontend + config into a fixed set of formalized maps (`PERSONA_MAP` / `COMPONENT_ARCHITECTURE_MAP` / `API_RETURNS_MAP` / `API_DESIGN_MAP` / `DATA_ARCHITECTURE_MAP`) and execution-ready OpenSpec requirements, reusing the existing mapping + phenotype + reuse-first machinery, with OpenSpec emitted via the openspec skill and every stage gated by the ralph-loop skill.

### Modified Capabilities

None of the existing capabilities' requirements change. `visual-to-api-design`'s 4-stage behavior is preserved as a subset; the mapping skills (`design-fidelity-mapping`, `frontend-route-mapping`, `interaction-intuition`), `phenotypes`, `reuse-first-design`, `coverage-mapping` are reused, not altered.

## Impact

**Affected files:**
- `skills/visual-to-api-design/SKILL.md` — MODIFIED. Extend 4 → 7 stages (core).
- `commands/visual-to-api.md` — MODIFIED. Note the extension; subset entry preserved.
- `skills/common-pipeline-conventions/SKILL.md` — MODIFIED. Canonicalize the 5-doc naming standard + the ralph-loop-per-stage + openspec-skill bindings.
- `agents/*.md` — possibly NEW reviewer role(s) for the net-new stages (component-architecture / api-design), only if existing reviewers cannot be reused (reuse-first).
- `skills/phenotypes/SKILL.md` + `phenotypes/{user-management,ai-management,config-management}/` — REUSED at Stage 7 (no change).
- `tests/test_exploration_pipeline.py` (+ related) — NEW structural coverage.
- `.claude-plugin/plugin.json` + `marketplace.json`, `CHANGELOG.md`, `docs/CODEBASE_MAP.md` — version + docs.

**Affected APIs / dependencies:** none new. Markdown skills/agents + pytest self-tests; binds to existing prerequisite plugins (`ralph-loop`, OpenSpec skills).

**Reuse-first decision summary:** EXTEND `visual-to-api-design` (not a new skill); REUSE `design-fidelity-mapping` / `frontend-route-mapping` / `interaction-intuition` / `phenotypes` / `reuse-first-design` / `coverage-mapping` / `verify-every-element`; BIND to `ralph-loop:ralph-loop` + `openspec-propose`/`opsx:propose`. Only stage 3c (reusable-component architecture) is substantially net-new. Full Reuse Decision Log in `design.md`.
