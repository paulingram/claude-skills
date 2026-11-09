# The Exploration Pipeline — 7 stages

The Exploration Pipeline runs 7 stages. Frontend stages (1–6) run only when frontend is in scope; the backend stage (7) runs only when backend is in scope; Stage 0 always runs and decides the branch. Each stage produces a frozen JSON artifact at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json` AND (for the stages that own a standardized doc) one of the five canonical `*_MAP.md` documents in `<codebase>/docs/`. Each stage runs the v0.9.19 3-reviewer convergence protocol (Round 1 independent → Round 2 round-robin → Round 3 architect) **inside a `ct6-converge` workflow**, and reads the prior stage's frozen artifact as its CHECKLIST.

### Governance — every stage's convergence runs inside a ct6-converge workflow, declared and recorded

Every stage's 3-reviewer doc-passing convergence is a tier-3 gate (each stage freezes a map) run as declare → the `ct6-converge` workflow → record per `skills/common-pipeline-conventions/references/converge-workflows.md`. The loop body is the 3-reviewer convergence; the workflow's `promise` is **total agreement across all reviewers that the stage document meets every required step (100% fidelity)** — the gate's LABEL, not its exit test. The loop exits ONLY when all three reviewers AND the Round-3 architect agree the stage doc satisfies every checklist item and the record says so (`converged: true`, three `ok` verdicts in the final round); there is **no iteration cap** (per `common-pipeline-conventions` `## Unbounded solving discipline`), and a human `maxRounds` pauses the gate rather than passing it. Each stage below names its own promise string. The canonical invocation shape (matching `intake-and-mapping`):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" declare --workspace <ws> --kind stage-<n> --promise "<STAGE-N PROMISE>" --reviewers 3
#   Workflow({ name: "ct6-converge", args: { kind: "stage-<n>", promise: "<STAGE-N PROMISE>", reviewers: 3, artifacts: ["<stage artifact>", "<stage *_MAP.md>"] } })   # the `ct6-converge` workflow with completion promise "<STAGE-N PROMISE>"
python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" record --workspace <ws> --kind stage-<n> --result '<the workflow JSON>'
```

When the convergence reaches total agreement, the workflow returns `converged: true` and the orchestrator records it, which satisfies the declared gate; typing the promise line changes nothing. The loop never halts on iteration count and never freezes a half-agreed artifact — it keeps converging. If a stage genuinely cannot converge because the requirement is unsettleable from the available inputs (a product decision only the owner can make), it routes an `api-design-stage-incomplete` SR surfacing that specific required owner input — loudly, while the run continues working everything else — rather than stopping.

### Run-time inputs — `language`, `component_libraries`, `ancillary_docs`

The target `language`, the `component_libraries`, and the `ancillary_docs` are read from the **requirements-brief frontmatter** or a **project config** (`<codebase>/.architect-team.config` / brief frontmatter). They are NEVER guessed. When frontend/component work is in scope and any of these inputs is absent, the skill **escalates via a domain gate** (an `AskUserQuestion`-style prompt, consistent with `common-pipeline-conventions` `## Scope discipline`) — it does not invent a language or a component library. `ancillary_docs` (product briefs, brand guidelines, market research, competitor docs) are a **first-class Stage 1 input**, read alongside the codebase.

### The five standardized documentation artifacts

The Exploration Pipeline emits five fixed-name documents into `<codebase>/docs/`. Their names, paths, and frontmatter schemas are **canonicalized in `common-pipeline-conventions`** (the `## Standardized documentation naming` standard — another teammate owns that section); this skill REFERENCES that standard rather than duplicating it. The five docs and their producing stage:

| Doc | Path | Produced by | Frontmatter (per the canonical standard) |
|---|---|---|---|
| `PERSONA_MAP.md` | `<codebase>/docs/` | Stage 2 | `{generated_at, personas_count, source_ancillary_docs[]}` |
| `COMPONENT_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | Stage 3c | `{generated_at, language, component_libraries[], elements_total, components_total, coverage}` |
| `API_RETURNS_MAP.md` | `<codebase>/docs/` | Stage 5 | `{generated_at, pages_count, returns_count}` |
| `API_DESIGN_MAP.md` | `<codebase>/docs/` | Stage 6 | `{generated_at, endpoints_count, user_types[]}` |
| `DATA_ARCHITECTURE_MAP.md` | `<codebase>/docs/` | Stage 7 | `{generated_at, db_types[], phenotypes_used[], openspec_change}` |

These are auto-generated whenever the Exploration Pipeline runs against a project (frontend docs only when frontend is in scope; `DATA_ARCHITECTURE_MAP.md` only when backend is in scope), created-on-ask in standalone mode, and follow the existing `*_MAP.md` convention.

### Stage 0 — Scope detection

**Goal:** classify the run and branch the downstream stages. Stage 0 ALWAYS runs.

**What it does:** surfaces the existing `intake-and-mapping` classification and classifies the run as exactly one of three scope outcomes:

- **`frontend-only`** — UI present, no backend to design; run Stages 1–6, skip Stage 7.
- **`backend-only`** — backend/data work with no UI to catalog; skip the frontend stages (1–6), run Stage 7.
- **`both`** — full Exploration; run Stages 1–7.

**Branching rule (stated explicitly):** **the frontend stages (1–6) run if and only if frontend is in scope; the backend stage (7) runs if and only if backend is in scope.** A `both` run executes all seven; a `frontend-only` run stops after Stage 6; a `backend-only` run runs Stage 7 directly against whatever API/data requirements exist.

**Required output** (`stage-0-scope.json`): `{stage: 0, name: "scope-detection", scope: "frontend-only" | "backend-only" | "both", frontend_in_scope: bool, backend_in_scope: bool, classification_source: "intake-and-mapping", frozen_at, _human_review_required}`.

**ct6-converge workflow:** the 3-reviewer scope-classification convergence is wrapped in the `ct6-converge` workflow with completion promise "STAGE-0 SCOPE COMPLETE — all reviewers agree on scope + branch". The promise is the gate's label; the loop runs until the record says converged (no iteration cap).

### Stage 1 — Personas + application classification

**v3.4.0 — delegation to `domain-research-team`.** Stages 1 and 2 are encapsulated in the `domain-research-team` skill (`skills/domain-research-team/SKILL.md`), which carries the mandatory outside-research enrichment v3.4.0 adds. visual-to-api-design invokes the skill once with `output_kind: persona-map`, the frontend codebase + configured `ancillary_docs` as inputs, and the `<codebase>/docs/PERSONA_MAP.md` output path. The persona enumeration + per-persona objectives come back as one final map; visual-to-api-design proceeds to Stage 3 with that map as the binding input.

**Goal:** when frontend is in scope, catalog ALL personas (user types) and classify the whole application. **Reuses Exploration Stage 1 (context discovery)** — see `### Stage 1 — Context discovery` in the subset section below for the exact `stage-1-context.json` shape; Stage 1 of the Exploration Pipeline extends it by reading the configured `ancillary_docs` as a first-class input.

**What it does:** enumerates every distinct persona/user-type AND produces the application classification (`application_purpose` / `industry` / `use_case_summary`), reading the frontend PLUS the configured `ancillary_docs`. The persona enumeration is the seed for Stage 2's per-persona objective document.

**Required output:** the existing `stage-1-context.json` (see subset section) with `ancillary_docs_read: [...]` added — the list of ancillary docs consumed.

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-1 CONTEXT COMPLETE — all reviewers agree personas + classification are complete". The promise is the gate's label; the loop runs until the record says converged (no iteration cap).

### Stage 2 — Per-persona objectives → `PERSONA_MAP.md`

**Goal:** for each persona, write an objective document describing what that persona wants to achieve in this industry while using this product. **Reuses Exploration Stage 2 (per-persona research)** — see `### Stage 2 — Per-persona research` in the subset section for the `stage-2-personas.json` shape.

**Output doc:** `<codebase>/docs/PERSONA_MAP.md` — **one objective section per persona**, each section carrying: the persona's **role**, the **industry context**, and the **objectives** they want to achieve with the product. Frontmatter `{generated_at, personas_count, source_ancillary_docs[]}` per the canonical naming standard.

**Stage-2 CHECKLIST against Stage 1:** every persona in Stage 1's persona list MUST appear as a `PERSONA_MAP.md` section; the count MUST match.

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-2 PERSONA_MAP COMPLETE — all reviewers agree every persona has an objective section". The promise is the gate's label; the loop runs until the record says converged (no iteration cap).

### Stage 3a — Page/element catalog

**Goal:** list every page, then every element on each page, capturing for each element its `type`, its `html_attributes`, and a `value_class: dynamic | static` classification. **Reuses Exploration Stage 3 (page catalog) + `design-fidelity-mapping` (DESIGN_MAP).** See `### Stage 3 — Page catalog` in the subset section for the per-element shape this extends.

**Per-element capture (stated explicitly):**

- **`type`** — the element classification (form-input-text, submit-button, file-upload, data-row, etc.).
- **`html_attributes`** — the element's tag + salient HTML attributes, **captured UNCONDITIONALLY from source for every element, regardless of design inputs.** Computed-style attributes are added ONLY when design inputs exist (reusing DESIGN_MAP's per-element computed-style capture). Raw-HTML-attribute capture never blocks; it degrades to tag+attributes when no DESIGN_MAP is present.
- **`value_class: dynamic | static`** — classified per **`dynamic-value-discovery`**: classify from CONTEXT (is this a per-user / per-record / per-state value?), **never from the literal** on the screen. A name field showing "John Smith" is `dynamic` even though the mockup shows a constant.

**Required output** (`stage-3a-page-element-catalog.json`): per page, every element with `{type, html_attributes, value_class}` plus the existing subset fields (`element_id`, `classification`, `blurb`, `is_dynamic`, `needs_backend`, `backend_endpoint_hint`).

**ct6-converge workflow:** wrapped in the `ct6-converge` workflow with completion promise "STAGE-3A CATALOG COMPLETE — all reviewers agree every element is captured with attributes + value_class". The promise is the gate's label; the loop runs until the record says converged (no iteration cap).

> **STOP.** This chapter continues in `skills/visual-to-api-design/references/the-exploration-pipeline-7-stages-part-2.md`; Read it before acting on the later stages.
