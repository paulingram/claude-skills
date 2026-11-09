---
name: visual-to-api-design
description: Use when the architect-team is invoked against a visual codebase (UI present, requirements absent OR partially specified) and must DERIVE the API design from what the screens reveal — the Phase 0 "review this codebase / design the API for this visual" case. Runs the Exploration Pipeline, a scope-gated 7-stage flow with 3-reviewer convergence per stage (each convergence wrapped in a ct6-converge workflow whose completion-promise is total reviewer agreement) and per-stage checklists that gate the next stage's freeze. The body documents every stage, the checklists, the ct6-converge workflow governance, the openspec-skill conversion, and the original 4-stage flow that remains valid as a strict subset.
user-invocable: false
---

# Visual-to-API Design Pipeline (the Exploration Pipeline)

When the architect-team is given a visual codebase (a UI repo, a Figma export, a deployed site URL) but no explicit requirements OR only partial requirements, this skill produces the API design — and, when frontend is in scope, the persona research, page/element catalog, reusable-component architecture, per-page REST returns, and consolidated API design — that the visual code implies. This is the **Exploration Pipeline**: a scope-gated **7-stage** flow, each stage frozen before the next begins, each stage reviewed by 3 independent agents in convergence (the v0.9.19 pattern) **inside a `ct6-converge` workflow** whose completion-promise is total reviewer agreement, each stage's output the explicit checklist the next stage must satisfy.

**The original 4-stage flow is a strict SUBSET of the 7-stage pipeline** (see `## The 4 stages (the original subset)` below): Stage 1 (context discovery) is a subset of Exploration Stage 1, Stage 2 (per-persona research) of Exploration Stage 2, Stage 3 (page catalog) of Exploration Stage 3a, and Stage 4 (backend design from frontend) of Exploration Stages 5+6+7. The 4-stage subset and the `/architect-team:visual-to-api` command remain valid and unchanged.

## The Exploration Pipeline — 7 stages

> **STOP.** Before acting under this section, Read `skills/visual-to-api-design/references/the-exploration-pipeline-7-stages.md` and execute it in full. Do not work from memory.

The Exploration Pipeline runs 7 stages. Frontend stages (1–6) run only when frontend is in scope; the backend stage (7) runs only when backend is in scope; Stage 0 always runs and decides the branch. Each stage produces a frozen JSON artifact at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json` AND (for the stages that own a standardized doc) one of the five canonical `*_MAP.md` documents in `<codebase>/docs/`. Each stage runs the v0.9.19 3-reviewer convergence protocol (Round 1 independent → Round 2 round-robin → Round 3 architect) **inside a `ct6-converge` workflow**, and reads the prior stage's frozen artifact as its CHECKLIST.

## The failure shape this closes (verbatim from the user)

> **STOP.** Before acting under this section, Read `skills/visual-to-api-design/references/the-failure-shape-this-closes-verbatim-from-the-user.md` and execute it in full. Do not work from memory.

Existing reviews of visual codebases jumped straight to "what does this UI do?" without first establishing context, persona research, exhaustive page catalog, OR a checklist-driven backend design. The result was an API design that *mostly* covered what was on screen but missed entire affordances (the v2.13.0 file-upload case) AND missed per-element data needs (a name field that should be dynamic but was treated as static). v2.13.0 ships the structured pipeline that makes both gaps structurally impossible.

## The 4 stages (the original subset)

> **STOP.** Before acting under this section, Read `skills/visual-to-api-design/references/the-4-stages-the-original-subset.md` and execute it in full. Do not work from memory.

The original 4-stage flow is the canonical SUBSET of the Exploration Pipeline (see `## The Exploration Pipeline — 7 stages` above) and remains valid and unchanged — invoked directly by the `/architect-team:visual-to-api` command. Each stage produces a frozen JSON artifact stored at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json`. Each stage runs the v0.9.19 3-reviewer convergence protocol (3 independent reviewer agents → round-robin Round 2 → architect Round 3) before its artifact is frozen; in the full Exploration Pipeline that convergence is additionally wrapped in a `ct6-converge` workflow (see governance above), but the 4-stage subset's convergence semantics are unchanged. Each subsequent stage reads the prior stage's frozen artifact as its CHECKLIST.

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

> **STOP.** Before acting under this section, Read `skills/visual-to-api-design/references/when-this-skill-runs.md` and execute it in full. Do not work from memory.

The skill is invoked at Phase 0 (Detection & Normalization) when ANY of the following holds:

## Cross-references

> **STOP.** Before acting under this section, Read `skills/visual-to-api-design/references/cross-references.md` and execute it in full. Do not work from memory.

- `skills/interaction-completeness/SKILL.md` — the v0.9.19 3-reviewer convergence pattern this skill reuses per stage.
- `skills/intake-and-mapping/SKILL.md` — produces the codebase scan that Stage 1 reads.
- `hooks/vao_tools.py::verify_affordance_coverage` — the 13th Layer 3 tool that catches the file-upload-style affordance gap Stage 3 element classifications must address.
- `agents/system-architect.md` `Visual-to-API Design Audit` mode (NEW v2.13.0) — runs Round 3 of every stage.
- `agents/codebase-map-reviewer.md` — the existing reviewer pattern this skill's per-stage reviewers extend.
- `ct6-converge` workflow (the `ct6-converge` workflow skill) — every Exploration Pipeline stage's 3-reviewer convergence runs INSIDE this loop with a total-agreement completion-promise (same pattern as `intake-and-mapping`).
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
8. **Every stage runs inside a ct6-converge workflow.** Each of the 7 Exploration Pipeline stages wraps its 3-reviewer convergence in `ct6-converge` workflow with an explicit `--completion-promise` = total reviewer agreement (100% fidelity). There is no iteration cap — the loop runs until convergence. A stage cannot freeze on partial agreement; a genuinely unsettleable requirement (needing an owner decision) routes an `api-design-stage-incomplete` SR for required owner input while the run continues.
9. **OpenSpec is authored via the openspec skill.** Stages 4 and 7 produce OpenSpec via `openspec-propose` / `opsx:propose` — NEVER hand-written OpenSpec JSON or spec files.
10. **Scope gates the frontend/backend stages.** Stage 0 classifies `frontend-only | backend-only | both`; the frontend stages (1–6) run iff frontend is in scope and the backend stage (7) runs iff backend is in scope.
11. **Run-time inputs are read, never guessed.** `language`, `component_libraries`, and `ancillary_docs` come from the brief frontmatter or project config; absence (when FE/component work is in scope) escalates via a domain gate.
12. **The 4-stage subset stays valid.** The original 4-stage flow + the `/architect-team:visual-to-api` command remain a valid, unchanged subset of the 7-stage Exploration Pipeline.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `The exploration pipeline (7 stages) (part 2)` | `skills/visual-to-api-design/references/the-exploration-pipeline-7-stages-part-2.md` | on demand |
| `The Exploration Pipeline — 7 stages` | `skills/visual-to-api-design/references/the-exploration-pipeline-7-stages.md` | on demand |
| `The failure shape this closes (verbatim from the user)` | `skills/visual-to-api-design/references/the-failure-shape-this-closes-verbatim-from-the-user.md` | on demand |
| `The 4 stages (the original subset)` | `skills/visual-to-api-design/references/the-4-stages-the-original-subset.md` | on demand |
| `When this skill runs` | `skills/visual-to-api-design/references/when-this-skill-runs.md` | on demand |
| `Cross-references` | `skills/visual-to-api-design/references/cross-references.md` | on demand |
