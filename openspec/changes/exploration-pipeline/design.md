# Design — exploration-pipeline (extend visual-to-api-design 4 → 7 stages)

## Context

Reconciliation found 6 of the 7 stages' sub-steps already exist, 4 partial, 2 net-new. Decision (user-confirmed): EXTEND `visual-to-api-design` in place; bind every stage to `ralph-loop:ralph-loop`; emit OpenSpec via the openspec skill; standardize 5 `*_MAP.md` docs; read inputs from the brief/config.

## Resolved design decisions (the refinement's 4 open questions)

1. **Stage 6 "play-test against the PROPOSED API"** → a **design-time desk-trace**, not a running server. For each page, document the trace: every component → the proposed endpoint call (or the consolidated return field) that satisfies its payload consumption. A running mock-server-from-OpenSpec contract test is explicitly deferred to the implementation pipeline (Phase 2-8 of architect-team), since the API is not built during exploration. The desk-trace's exit criterion is 100% of components on 100% of pages satisfied.
2. **"Most efficient REST returns" / "max endpoint reusability"** → measurable definitions baked into the spec: over-fetch budget = 0 unconsumed top-level return fields per page; pages sharing data reuse one return shape; no two endpoints serve identical element sets; every page satisfiable from the consolidated endpoint set. These are the strict ralph-loop exit predicates for Stages 5/6.
3. **Stage 3c pixel-perfect placement** → **DESIGN_MAP-gated**: when design inputs exist (DESIGN_MAP present), placement is pixel-perfect (per-screen coordinates/asset placement); otherwise a **degraded structural-placement mode** records which page/region each component occupies without pixel coordinates. Never blocks; degrades.
4. **Raw-HTML-attribute capture (Stage 3a)** → **unconditional**: the element's tag + salient HTML attributes are captured from source for every element regardless of design inputs; computed-style attributes are added only when design inputs exist (reusing DESIGN_MAP's per-element computed-style capture).

## Key architecture — one skill, 7 stages, ralph-loop + openspec bound

`visual-to-api-design/SKILL.md` grows a Stage 0 + Stages 5/6 + a stronger Stage 3c + 7d, keeping its existing Stage 1/2/3/4 bodies as the reused early stages. Every stage = the existing 3-reviewer convergence (Round 1 independent → Round 2 round-robin → Round 3 architect) wrapped in `/ralph-loop "<stage prompt>" --completion-promise "<STAGE> COMPLETE — all reviewers agree"` (loops until the promise; no iteration cap per v3.8.0 unbounded solving). The OpenSpec-producing stages (4, 7d) call the openspec skill rather than writing JSON.

## Reuse Decision Log

| ID | Decision | Anchor / justification |
|---|---|---|
| RD-1 | extend `skills/visual-to-api-design/SKILL.md` | The closest existing component (4-stage pipeline with stage-gate + 3-reviewer convergence). Grow to 7 stages; subset preserved. NOT a new skill (avoids the duplication consolidated in v3.1.0). |
| RD-2 | reuse `design-fidelity-mapping` (DESIGN_MAP) | Per-element type/attrs/static-dynamic + asset registry + per-screen specs already exist — Stage 3a builds on it; add unconditional raw-attr capture. |
| RD-3 | reuse `frontend-route-mapping` (ROUTE_MAP) | Route inventory exists — Stage 3b annotates it with persona impact. |
| RD-4 | reuse `interaction-intuition` / `dynamic-value-discovery` | Element→endpoint intuition + static/dynamic classification feed Stages 3a/5. |
| RD-5 | build-new the reusable-component-architecture stage (3c) | No existing artifact proposes components, maps 100% coverage, records placement + payload. The single net-new stage. Output `COMPONENT_ARCHITECTURE_MAP.md`. |
| RD-6 | bind `ralph-loop:ralph-loop` | The user-mandated loop mechanism; wrap each stage's convergence. Already used in `intake-and-mapping`. |
| RD-7 | bind `openspec-propose` / `opsx:propose` (the openspec skill) | The user-mandated OpenSpec mechanism for Stages 4 + 7d; replaces hand-written JSON for OpenSpec output. |
| RD-8 | reuse `phenotypes` (user-management / ai-management / config-management) | Stage 7 domain-gates map exactly onto the existing phenotype proposal gate + the 3 seed phenotypes; config-management ships OpenTofu `.tf.tmpl`. No new phenotype. |
| RD-9 | reuse `coverage-mapping` + `hooks/vao_tools.py verify-every-element` | The 100%-coverage checker pattern for Stages 3c/5. |
| RD-10 | reuse existing reviewer agents where possible; build-new a reviewer role ONLY if the net-new stages need one | Reuse-first; a `component-architect`-style reviewer is added only if no existing reviewer fits Stage 3c/6. |

## Standardized documentation schema

| Doc | Path | Produced by | Frontmatter |
|---|---|---|---|
| `PERSONA_MAP.md` | `<codebase>/docs/` | Stage 2 | `{generated_at, personas_count, source_ancillary_docs[]}` |
| `COMPONENT_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | Stage 3c | `{generated_at, language, component_libraries[], elements_total, components_total, coverage: "100%"}` |
| `API_RETURNS_MAP.md` | `<codebase>/docs/` | Stage 5 | `{generated_at, pages_count, returns_count}` |
| `API_DESIGN_MAP.md` | `<codebase>/docs/` | Stage 6 | `{generated_at, endpoints_count, user_types[]}` |
| `DATA_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | Stage 7 | `{generated_at, db_types[], phenotypes_used[], openspec_change}` |

Auto-generated whenever the exploration pipeline runs against a project; created-on-ask in standalone mode. Canonicalized in `common-pipeline-conventions`.

## Risks / mitigations

- **Risk:** extending v2a balloons the SKILL.md and breaks its existing tests. **Mitigation:** keep Stage 1-4 bodies intact; ADD stages; the existing visual-to-api-design tests are the regression net; new structural tests assert the additions.
- **Risk:** "every project gets these docs" over-generates for backend-only or non-UI projects. **Mitigation:** Stage 0 scope gate — frontend docs only when frontend in scope; DATA_ARCHITECTURE only when backend in scope.
- **Risk:** the openspec skill / ralph-loop skill are external prerequisite plugins; absent them the bindings fail. **Mitigation:** they are already listed prerequisites (`architect-team-setup`); document the dependency.
