# Exploration documentation standard (v3.2.0)

The Exploration Pipeline — the 7-stage extension of `visual-to-api-design` (Stage 0 scope-gate + the reused Stage 1/2/3/4 bodies + the net-new reusable-component-architecture Stage 3c + the API Stages 5/6 + the data-architecture Stage 7) — produces a fixed, named set of FIVE `*_MAP.md` documents under each project's `<codebase>/docs/` directory. These are the structured exploration artifacts the implementation pipeline (Phase 2-8 of architect-team) then builds against. This section is the canonical home of their names, paths, frontmatter, and bodies, so the producer skill body and any downstream consumer reference one schema rather than re-describing it.

These five docs follow the EXISTING `*_MAP.md` convention already used across the plugin — `CODEBASE_MAP.md` (`docs/CODEBASE_MAP.md`), `ROUTE_MAP.md` (`frontend-route-mapping`), `DESIGN_MAP.md` (`design-fidelity-mapping`), `INTEGRATION_MAP.md` (`docs/INTEGRATION_MAP.md`), and `INTERACTION_INTUITION_MAP.md` (`interaction-intuition`): a fixed, greppable filename; a `<codebase>/docs/` location; required YAML frontmatter carrying a `generated_at` timestamp plus per-doc counts/metadata; and a Markdown body following the schema. The names are stable and exact so structural tests and consuming agents can assert their presence the same way they assert `ROUTE_MAP.md` / `DESIGN_MAP.md`.

### The five standardized docs

| Doc | Path | Produced by (stage) | Required frontmatter | Body — one line |
|---|---|---|---|---|
| `PERSONA_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 2 | `{generated_at, personas_count, source_ancillary_docs[]}` | One objective section per persona — who they are, what they need, the screens/flows that serve them. |
| `COMPONENT_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 3c | `{generated_at, language, component_libraries[], elements_total, components_total, coverage}` (`coverage: "100%"`) | The proposed reusable components, each component's per-page placement, and the payload each component consumes. |
| `API_RETURNS_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 5 | `{generated_at, pages_count, returns_count}` | Per-page REST return shapes — the response payload each page needs, with the over-fetch budget held to zero unconsumed top-level fields. |
| `API_DESIGN_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 6 | `{generated_at, endpoints_count, user_types[]}` | The consolidated API — every endpoint, its CRUD operations, and the return shape served per user type. |
| `DATA_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | `visual-to-api-design` Stage 7 | `{generated_at, db_types[], phenotypes_used[], openspec_change}` | The extensible data schema + database choice(s) + which `phenotypes` (user-management / ai-management / config-management) the design draws on. |

Every frontmatter block carries `generated_at` (an ISO-8601 timestamp of the generation, matching the `last_routed` / `last_designed` timestamp convention of the existing `*_MAP.md` docs) plus the per-doc fields above. The body of each doc follows the one-line schema in the table; the producer skill (`visual-to-api-design`) owns the full per-section body schema for each, stage by stage.

### When the docs are produced

- **AUTO-GENERATED** — when the Exploration Pipeline runs against a project (the normal case), all five docs are produced as the natural output of Stages 2, 3c, 5, 6, and 7. The Stage 0 scope-gate degrades the set when a layer is out of scope: the frontend-facing docs (`PERSONA_MAP.md`, `COMPONENT_ARCHITECTURE_MAP.md`) are produced only when a frontend is in scope, and `DATA_ARCHITECTURE_MAP.md` only when a backend is in scope. The pipeline never blocks on a missing input; it degrades the doc set to what the project's scope supports.
- **CREATED-ON-ASK** — in standalone mode (a user invoking `visual-to-api-design` directly, outside a full pipeline run), the docs are produced on request rather than unconditionally, the same way `DESIGN_MAP.md` is created-on-ask when design inputs are present rather than forced onto every codebase.

### Cross-references

- `skills/visual-to-api-design/SKILL.md` is the PRODUCER — its 7 stages emit these five docs; it owns the full per-section body schema for each. This section is the canonical name/path/frontmatter registry the producer references.
- The existing `*_MAP.md` siblings whose convention these five match: `docs/CODEBASE_MAP.md`, `frontend-route-mapping` (`ROUTE_MAP.md`), `design-fidelity-mapping` (`DESIGN_MAP.md`), `docs/INTEGRATION_MAP.md`, and `interaction-intuition` (`INTERACTION_INTUITION_MAP.md`).
- `openspec/changes/exploration-pipeline/design.md` `## Standardized documentation schema` is the design source these five docs were specified in.
