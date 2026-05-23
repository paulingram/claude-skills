---
name: interaction-intuition
description: "Discovery-phase verification discipline that — for every frontend codebase in scope at Phase −1B — cross-walks ROUTE_MAP.md × DESIGN_MAP.md × INTEGRATION_MAP.md and produces an explicit per-element intuition of what action each control takes and which endpoint it likely calls, with confidence high / medium / low / unknown, evidence, and a precise ambiguity question for every low-confidence item. The end of Phase −1 fires a bulk-verify gate: every low-confidence and unknown element is presented to the user as a single numbered list (`all correct` / a list of incorrect indices / `all incorrect`), then a targeted drill-down resolves only the flagged items. The confirmed intuition map is a binding input to Phase 0 spec authoring and Phase 1 coverage criteria. The Phase −1D bulk-verify is a domain gate (the user-confirmation step IS the feature) and fires regardless of the v0.9.20 process-gates-opt-in rule."
---

# interaction-intuition

The pipeline's `interaction-completeness` team catches drift at Phase 5 — against a built, running app. By then the proposal is months old and a wiring gap costs a full cycle to find. The `interaction-intuition` skill answers the same question — *which design elements MUST be interactive, what does each one do, and which endpoint does each call?* — but at Phase −1B, against design + maps, BEFORE the OpenSpec proposal is scaffolded.

The shape is a per-frontend-codebase artifact, an agent that produces it, and a bulk-verify gate at the seam between Phase −1 and Phase 0 that resolves every low-confidence intuition with the user in a single round-trip — present the whole list, the user names the wrong ones, a targeted drill-down resolves only those.

## Inputs

The orchestrator gives the `interaction-intuiter` agent, per frontend codebase:

1. `<codebase>/docs/ROUTE_MAP.md` — every documented route + every interactive element the route table + components currently know about.
2. `<codebase>/docs/DESIGN_MAP.md` (when design inputs are present) — per-screen visual specs, the asset registry, the per-value `static`/`dynamic` classification.
3. `<workspace>/docs/INTEGRATION_MAP.md` — every cross-codebase API endpoint, contract, queue topic, and shared schema in scope.
4. The source-description from `$REQ_DIR` (the feature being scoped) — so screens / elements the design is silent about but the requirement asks for surface as `unknown`.

If `DESIGN_MAP.md` is absent for the codebase (no design inputs were detected), the intuiter runs against `ROUTE_MAP.md` + `INTEGRATION_MAP.md` only and infers screens from the route table. The output is more `medium` / `low`-heavy; that is expected and correct.

If `ROUTE_MAP.md` is absent (not a frontend codebase), the intuiter does NOT spawn for this codebase. The skill is a no-op there.

## Outputs

One per frontend codebase: `<codebase>/docs/INTERACTION_INTUITION_MAP.md`. Sibling to `ROUTE_MAP.md` and `DESIGN_MAP.md`. Auto-mined to MemPalace `--room interaction-intuitions` after the agent finishes, and again after the Phase −1D bulk-verify gate flips `confirmed: true`.

## Confidence rubric

Every per-element intuition carries one of four labels. The agent assigns the label deterministically from the criteria below:

- **`high`** — clear element label (an unambiguous action word: `Save`, `Delete`, `Submit`, `Edit`, `Add`, `Create`, `Cancel`, `Search`, `Filter`, `Export`, `Import`, `Login`, `Logout`, `Send`, etc.) AND at least one `exact-by-label` or `exact-by-action-noun` endpoint match in `INTEGRATION_MAP.md` AND design-spec context aligns (the screen's purpose, the surrounding controls, the data flow named in the design all point at this action).
- **`medium`** — exactly one of {clear label, exact endpoint match} but not both, OR multiple plausible candidate endpoints with no clear winner, OR design context is partial (the screen is described but the specific element's action is implied rather than stated).
- **`low`** — unclear label (`...`, `→`, a bare icon, an unnamed icon button), OR no obvious candidate endpoint in `INTEGRATION_MAP.md`, OR conflicting signals (the label says one thing, the route's existing API client imports suggest another).
- **`unknown`** — the element appears in the design source but neither the route table nor the API surface points to an action the intuiter can responsibly guess. The element exists; what it does is genuinely undetermined.

**Bias toward `high` when supported.** When the label, the endpoint match, and the design context all agree, the intuition IS `high` — do not downgrade it because "maybe the user wants something different." The Phase −1D gate exists for the genuinely uncertain cases. Producing hundreds of `low` items for an exact-match-heavy design wastes the user's bulk-verify pass and breaks the signal-to-noise of the gate.

**`low` and `unknown` MUST surface to the Phase −1D bulk-verify gate.** `medium` elements surface only when the agent has populated a non-null `ambiguity_question`. `high` items are auto-confirmed implicitly when the gate runs — they are not in the bulk-verify list.

## Per-element intuition

The intuiter walks every screen the design source (or the route table, when no design exists) describes, in design-reading order, and for each screen enumerates every interactive element. Element kinds the intuiter recognizes: `button`, `link`, `form-input`, `modal-trigger`, `drag-target`, `keyboard-shortcut`, `conditional-render-gate` (a UI element whose presence is gated on application state — a "delete" only available to admins, for example).

For each element, in order:

1. **Assign a stable `element_id`** — `<route-slug>__<region>__<label-slug>__<ordinal>`. Deterministic from the design's reading order, so the same map produced on two runs against unchanged inputs has the same IDs.
2. **Capture the `element_label`** — the literal label text from the design or the route component, normalized (whitespace collapsed; not lower-cased — preserve the design's casing).
3. **Resolve `element_kind`** from the design-spec classification or the component code.
4. **Intuit `intuited_action`** — what does this control do, in one sentence written in user-effect terms? "Delete the row this control sits inside; remove it from the displayed list." NOT "Calls DELETE /api/items/{id}." The action is what the USER experiences; the endpoint is the next field.
5. **Match `candidate_endpoints[]`** — walk `INTEGRATION_MAP.md` and collect endpoints whose `method + path + summary` plausibly serve the intuited action. Each match carries a `match_kind`:
   - `exact-by-label` — the endpoint path or summary contains the element's label verbatim (a "Delete" button → `DELETE /api/items/{id}` whose summary is "Delete an item").
   - `exact-by-action-noun` — action keyword aligns (delete/remove/destroy; create/add/new; edit/update/patch; search/filter; export/import).
   - `plausible-by-design-intent` — the design's described data flow points at this endpoint even if the label is generic.
   - `inferred-from-similar-route` — no exact match; a sibling route does something analogous and this likely does the same adjusted for context (use sparingly — this rarely meets the `high` threshold).
6. **Assign `confidence`** per the rubric.
7. **If `confidence < high`, author `ambiguity_question`** — a precise, focused question that names the concrete candidates and the user-visible behavioral difference between them. Examples:
   - GOOD: *"Should the row-level 'Archive' button call `POST /api/items/{id}/archive` (preserves the row, sets `archived=true`, the row remains queryable) or `DELETE /api/items/{id}` (removes the row entirely, it cannot be recovered)?"*
   - BAD: *"What does the Archive button do?"* (vague — no candidates, no behavioral diff).
   - BAD: *"Is the Archive button correct?"* (asks the wrong question — there's no intuition to be correct OR incorrect, just blank).
8. **Capture `evidence[]`** — every reasoning step cites a source: a `DESIGN_MAP.md#anchor`, an `INTEGRATION_MAP.md#endpoint-id`, a `ROUTE_MAP.md` line, or the source description from `$REQ_DIR`. An intuition with no citations is a guess and the orchestrator rejects it.

## Artifact schema

`<codebase>/docs/INTERACTION_INTUITION_MAP.md` carries YAML frontmatter + a markdown body. The body's elements are themselves YAML-blocks-in-markdown for machine-parsability.

### Frontmatter fields

- `last_intuited` — ISO 8601 UTC timestamp of the most recent intuiter run.
- `confirmed` — bool. `false` until the Phase −1D bulk-verify gate completes and every flagged item has a `user_verdict`.
- `confirmed_at` — ISO 8601 UTC timestamp, or `null` until confirmation.
- `producer` — string. Always `interaction-intuiter`.
- `inputs` — list of artifact paths the intuiter actually read.
- `covers_screens` — int. Count of distinct screens / routes the map covers.
- `covers_elements` — int. Count of distinct interactive elements the map covers.
- `confidence_summary` — object with `high`, `medium`, `low`, `unknown` int counts. The sum equals `covers_elements`.

### Per-element fields

- `element_id` — stable kebab-case id.
- `route` — the route path the element appears on (`/dashboard`, `/items/[id]/edit`).
- `element_label` — literal label string from the design or component.
- `element_kind` — one of `button`, `link`, `form-input`, `modal-trigger`, `drag-target`, `keyboard-shortcut`, `conditional-render-gate`.
- `design_source` — `<path>#<anchor>` into the source artifact that named the element (DESIGN_MAP or ROUTE_MAP).
- `intuited_action` — single-sentence user-effect description.
- `candidate_endpoints[]` — list of candidate endpoint objects, each `{method, path, source, match_kind}`. May be empty (`[]`) for `unknown` items.
- `confidence` — one of `high`, `medium`, `low`, `unknown`.
- `evidence[]` — list of citation strings.
- `ambiguity_question` — string or `null`. Null when `confidence: high`; non-null for every surfaced item.
- `user_verdict` — `null` before Phase −1D resolves the item; one of `confirmed`, `corrected`, `deferred-to-impl` afterward.
- `correction_note` — string or `null`. Populated only when the user's drill-down answer added prose context.
- `confirmed_action` — string or `null`. Filled by auto-confirmation OR by the drill-down user answer.
- `confirmed_endpoint` — endpoint object or `null`. Filled by auto-confirmation (from `candidate_endpoints[0]`) OR by the drill-down user answer.
- `superseded_by` — `null`, or a REQ-id when the user explicitly overrides this entry post-Phase 0.

## Escalate-don't-guess

When the maps + label + design source cannot responsibly resolve an element, the intuiter assigns `confidence: unknown` and authors a precise `ambiguity_question`. It does NOT invent an endpoint or an action. The Phase −1D bulk-verify gate exists exactly for these — surfacing them is the correct outcome.

A `low` or `unknown` classification is never a personal failure. It is signal: the design source plus the existing API surface do not, on their own, determine what this control should do. The user resolves it.

## Domain-gate carve-out

The v0.9.20 `## Default mode of operation` rule in `architect-team-pipeline/SKILL.md` says **gates are opt-in**: process gates (`--proposal-first`, "do you want me to proceed", clarifying questions whose answer is obvious) fire ONLY when the user explicitly requests them or a genuinely material fork exists where the answer is not obvious.

The Phase −1D bulk-verify is **not** a process gate. It is a **domain gate** — the user-confirmation step that IS the feature. It is structurally identical to the `editability-completeness` team's `ambiguous` attribute escalation and the `interaction-completeness` team's `ambiguous` element escalation: each fires whenever the deliverable cannot be produced without the user's specific factual input. They are part of the work, not interruptions to it.

The Phase −1D gate fires whenever the union of low-confidence intuitions is non-empty, **regardless** of `--proposal-first`. The pipeline skill's `## Default mode of operation` section names this distinction explicitly so the two rules do not appear to contradict each other.

## Hard rules (non-negotiable)

- **One intuition map per frontend codebase.** Never merge multiple codebases' intuitions into a single file. Each map lives at `<codebase>/docs/INTERACTION_INTUITION_MAP.md`.
- **Read-only on source code.** The intuiter may Read / Glob / Grep / LS / Bash / TodoWrite the codebase, and Write only `INTERACTION_INTUITION_MAP.md`. It may NOT Edit any source file and may NOT Write any other path.
- **Every intuition cites at least one source.** No citation = a guess = rejected by the orchestrator before the map is mined.
- **`low` and `unknown` MUST surface to the gate.** The agent never silently drops a low-confidence item to keep the bulk-verify list short.
- **`high` does not surface.** The gate is for genuinely uncertain items; auto-confirming `high` items in the gate output would burn the user's attention.
- **Ambiguity questions are concrete.** Vague questions ("what does this button do?") fail Round 1 of the orchestrator's pre-gate review and the agent re-authors them.
- **No deferred answers in the map itself.** Every element has a `confidence` and (for `confidence < high`) a non-empty `ambiguity_question`. "We'll figure it out later" is not a value.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "There's no exact endpoint match — mark it `unknown`." | Look first for `exact-by-action-noun` and `plausible-by-design-intent` matches. `unknown` is for elements where every match-kind comes up empty. |
| "The label is clear — that's `high` even with no endpoint match." | `high` requires BOTH a clear label AND an exact endpoint match AND aligned design context. A clear label with no endpoint match is `medium` or `low`. |
| "I'll skip this element — it's probably client-only." | Client-only elements (navigation, modal triggers, overlays, state toggles) are first-class. Classify them — `candidate_endpoints: []` is allowed; `intuited_action` is still required. |
| "There are 30 ambiguous elements — let me batch them all as one big question." | The gate already batches the bulk-verify presentation. The drill-down questions are one per flagged item — distinct items, distinct questions. AskUserQuestion's 4-questions-per-message limit handles the batching. |
| "The design doesn't show this element but the route table does." | That is signal, not noise. The element is in scope; intuit its action from the component code + the route's API client imports. Confidence is likely `medium` or `low`. |
| "I'll write the action as 'calls POST /api/items'." | The action is in user-effect terms ("creates a new item; the new item appears in the displayed list"). The endpoint is the next field. |
| "If the user did not answer my ambiguity question in the bulk reply, I'll just guess `confirmed-stub`." | Items the user did NOT flag are auto-`confirmed` per their `intuited_action` and top candidate. `confirmed-stub` is a different verdict, reserved for elements the user explicitly confirms are intentionally inert. |

## Relationship to other skills

- `interaction-completeness` (Phase 5) — verifies built code matches the confirmed intuitions. The two skills are bookends: this one promises an intuition; `interaction-completeness` checks the promise was kept. **`user_verdict: confirmed-stub` entries in `INTERACTION_INTUITION_MAP.md` flow downstream to Phase 5** — `interaction-completeness` reads the map before enumerating, pre-populates the converged map's `confirmed_stubs[]` and the active change's `coverage-map.json` `confirmed_stubs[]` for every pre-confirmed element (keyed on `element_id`), and does NOT re-escalate the same question to the user. The cross-reference is bidirectional with the v0.9.21 binding-input rule: `confirmed`-action entries flow to Phase 0 spec authoring + Phase 1 coverage criteria; `confirmed-stub` entries flow to Phase 5's interaction-completeness team. See v0.9.28 (cohesion-review issue #5).
- `frontend-route-mapping` + `design-fidelity-mapping` (Phase −1B) — produce the inputs (`ROUTE_MAP.md`, `DESIGN_MAP.md`). The intuiter consumes them.
- `intake-and-mapping` (Phase −1) — orchestrates the per-codebase pipeline including the intuiter dispatch.
- `dynamic-value-discovery` (cross-role) — the intuiter applies this discipline when reasoning about labels that might be dynamic data ("Account balance: $1,240.00" — the literal IS a dynamic-value-binding signal).
- `mempalace-integration` — the intuiter's output is mined to MemPalace `--room interaction-intuitions` for prior-context recall in future runs against the same project.
