# Cross-references

- `skills/interaction-completeness/SKILL.md` — the v0.9.19 3-reviewer convergence pattern this skill reuses per stage (kept at tier 3 here because every stage freezes a map; `interaction-completeness` itself is tiered per gate since v4.0.0).
- `skills/intake-and-mapping/SKILL.md` — produces the codebase scan that Stage 1 reads.
- `hooks/vao_tools.py::verify_affordance_coverage` — the 13th Layer 3 tool that catches the file-upload-style affordance gap Stage 3 element classifications must address.
- `agents/system-architect.md` `Visual-to-API Design Audit` mode (NEW v2.13.0) — runs Round 3 of every stage.
- `agents/codebase-map-reviewer.md` — the existing reviewer pattern this skill's per-stage reviewers extend.
- the `ct6-converge` workflow (`workflows/ct6-converge.js`, declared before and recorded after per `skills/common-pipeline-conventions/references/converge-workflows.md`) — every Exploration Pipeline stage's 3-reviewer convergence runs INSIDE it with a total-agreement completion promise as the gate's label (same pattern as `intake-and-mapping`).
- The openspec skill — `openspec-propose` / `opsx:propose` — the OpenSpec authoring mechanism Stages 4 and 7 call (never hand-written JSON).
- `skills/design-fidelity-mapping/SKILL.md` (DESIGN_MAP) — Stage 3a reuses its per-element type/attribute/static-dynamic capture; unconditional raw-HTML-attribute capture is added on top.
- `skills/frontend-route-mapping/SKILL.md` (ROUTE_MAP) — Stage 3b reuses the route inventory and annotates each route with impacted personas.
- `skills/dynamic-value-discovery/SKILL.md` — Stage 3a's `value_class: dynamic | static` classification follows it (classify from context, never the literal); feeds Stage 5's per-page returns.
- `skills/phenotypes/SKILL.md` (`phenotypes/user-management`, `phenotypes/ai-management`, `phenotypes/config-management`) — Stage 7 fires the three phenotype domain gates (user-management / AI-management / OpenTofu config-management).
- `hooks/vao_tools.py::verify-every-element` — the 100%-coverage checker pattern Stages 3c and 5 reuse (every element mapped to a component / a return field).
- `common-pipeline-conventions` `## Standardized documentation naming` — the canonical home of the five `*_MAP.md` doc names + paths + frontmatter schemas (`PERSONA_MAP.md`, `COMPONENT_ARCHITECTURE_MAP.md`, `API_RETURNS_MAP.md`, `API_DESIGN_MAP.md`, `DATA_ARCHITECTURE_MAP.md`); this skill references that standard rather than duplicating it.
- New SR origin kind `api-design-stage-incomplete` — routes incomplete-stage findings back to the reviewer team.
- Companion to v2.6.0 live-data wiring (catches mock-state survival on the built feature) + v2.11.0 multi-persona path-coverage (verifies the built feature works per persona) — different axis, same root principle: **the structured-checklist pattern catches what ad-hoc review misses**. This skill provides the upstream structure; v2.6.0/v2.11.0/v2.13.0 affordance discovery provide the downstream verification.
