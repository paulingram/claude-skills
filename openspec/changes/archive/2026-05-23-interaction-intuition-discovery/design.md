# Design — interaction-intuition-discovery

## Context

The pipeline produces `ROUTE_MAP.md` (every route + every interactive element in code) and `DESIGN_MAP.md` (per-screen visual specs from the design source) at Phase −1B. It produces `INTEGRATION_MAP.md` at Phase −1C (every cross-codebase contract + endpoint). Three rich artifacts. None of them answers: *for the work that is about to be scoped — for each element on each designed screen — what action does this element take and which endpoint will it call?*

That question is the whole point of Phase 5's `interaction-completeness` team — but Phase 5 runs against a live built app, so it answers the question *after* the team has already paid for the answer in code. The cost of being wrong scales with how late the answer arrives. The pipeline has no upstream answer-finding step.

This change adds it.

## Architecture

### The artifact: `INTERACTION_INTUITION_MAP.md`

One per frontend codebase, written to `<codebase>/docs/INTERACTION_INTUITION_MAP.md` — sibling to `ROUTE_MAP.md` and `DESIGN_MAP.md`. YAML frontmatter + a markdown body. Frontmatter:

```yaml
---
last_intuited: 2026-05-22T19:00:00Z
confirmed: false
confirmed_at: null
producer: interaction-intuiter
inputs:
  - docs/ROUTE_MAP.md
  - docs/DESIGN_MAP.md
  - ../docs/INTEGRATION_MAP.md
covers_screens: 12
covers_elements: 47
confidence_summary:
  high: 28
  medium: 11
  low: 5
  unknown: 3
---
```

Body is a per-route section enumerating every interactive-by-design element with a stable `element_id` (kebab-cased route + ordinal-within-route is enough; the agent assigns these deterministically from the design-spec reading order). Each element entry:

```yaml
- element_id: dashboard__row-actions__delete
  route: /dashboard
  element_label: "Delete"
  element_kind: button | link | form-input | modal-trigger | drag-target | keyboard-shortcut | conditional-render-gate
  design_source: DESIGN_MAP.md#dashboard-row-actions
  intuited_action: "Delete the row this control sits inside; remove it from the displayed list"
  candidate_endpoints:
    - method: DELETE
      path: /api/items/{id}
      source: INTEGRATION_MAP.md#items-api
      match_kind: exact-by-label
    - method: PATCH
      path: /api/items/{id}/status
      source: INTEGRATION_MAP.md#items-api
      match_kind: plausible-by-design-intent
  confidence: high | medium | low | unknown
  evidence:
    - "DESIGN_MAP.md classifies the row as a list item with row-level mutation controls"
    - "INTEGRATION_MAP.md has DELETE /api/items/{id} matching the label verbatim"
    - "ROUTE_MAP.md shows /dashboard already imports a useItems() hook returning delete-capable methods"
  ambiguity_question: null   # populated when confidence < high
  user_verdict: null         # populated after the Phase −1D gate
  correction_note: null
  confirmed_action: null
  confirmed_endpoint: null
  superseded_by: null
```

The body is YAML-encoded markdown blocks (one per element) so it is both human-readable and machine-parsable for downstream consumption.

### The producer: `interaction-intuiter` agent

A new agent definition in `agents/interaction-intuiter.md`. Spawned per frontend codebase, **after** `route-mapper` finishes producing `ROUTE_MAP.md` (+ `DESIGN_MAP.md` when design inputs are present) for that codebase. Tools: `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write` (the only file it writes is `INTERACTION_INTUITION_MAP.md`), `TodoWrite`. Analysis-only with respect to feature code — it never edits source.

Model: `opus`. Agent body specifies:

1. **Inputs** — `ROUTE_MAP.md`, `DESIGN_MAP.md` (when present), the workspace's `INTEGRATION_MAP.md`, and read-only access to source code for verification.
2. **Per-screen enumeration** — for every screen the design source describes, walk every interactive element in the design's reading order; assign a stable `element_id`; resolve `element_kind` from the design-spec's element classification.
3. **Action intuition** — derive `intuited_action` from the element label + the screen's purpose + the surrounding controls (a "Delete" button beside a row item deletes that item; a "Save" button on a form submits the form; a "+" button in a list-header creates a new item).
4. **Candidate-endpoint matching** — for each intuited action, walk `INTEGRATION_MAP.md` and collect endpoints whose `method + path + summary` plausibly match. Each match carries a `match_kind`: `exact-by-label` (the endpoint path or summary contains the element's label verbatim), `exact-by-action-noun` (action keyword aligns: delete/remove/destroy, create/add/new, edit/update/patch), `plausible-by-design-intent` (the design's described data flow points at this endpoint), `inferred-from-similar-route` (no exact match; analogous route does X, so this likely does X', adjusted for context).
5. **Confidence assignment** — per the REQ-004 rubric:
   - `high` — clear label + an `exact-by-*` endpoint match + design context aligns.
   - `medium` — clear label OR exact match (not both), OR multiple plausible candidates.
   - `low` — unclear label OR no obvious candidate OR conflicting signals across the maps.
   - `unknown` — the element is in the design but neither the route table nor the API surface points to an action; the intuiter cannot guess responsibly.
6. **Ambiguity-question authoring** — for any element with `confidence` in `{low, unknown}`, the agent writes a specific, focused `ambiguity_question` ("Should the row-level 'Archive' button call `POST /api/items/{id}/archive` (preserves the row, sets `archived=true`) or `DELETE /api/items/{id}` (removes the row entirely)?"). Vague questions are forbidden — the question MUST present the concrete candidates and the user-visible behavioral difference between them.
7. **Escalate-don't-guess** — the same discipline as `interaction-completeness` and `editability-completeness`: when the maps + label + design cannot responsibly answer the question, assign `unknown` with a precise `ambiguity_question`, never invent an action. The Phase −1D gate exists exactly to handle these cases.

### The orchestration: Phase −1B and Phase −1D

**Phase −1B insertion.** After `route-mapper` produces `ROUTE_MAP.md` (+ `DESIGN_MAP.md` if applicable) and the 3-reviewer codebase-map review loop emits `CODEBASE MAP COMPLETE` for that codebase, the orchestrator dispatches `interaction-intuiter` against the same codebase. The intuiter writes the per-codebase intuition map and exits. The map is mined to MemPalace `--room interaction-intuitions`. Per-codebase intuition production is independent across codebases and runs in parallel when multiple frontends are in scope.

**Phase −1D bulk-verify gate.** At the end of Phase −1 (after `INTEGRATION MAP COMPLETE`), the orchestrator gathers across every frontend codebase's intuition map every element where `confidence ∈ {low, unknown}` PLUS any `medium` elements whose entry contains a non-null `ambiguity_question`. If the gathered set is empty, the gate is a no-op and Phase −1 closes normally. Otherwise:

1. **Present the bulk list** — emit a single numbered list to the user. Each item shows: index, route, element label, intuited action, top candidate endpoint (if any), confidence, and the agent's specific `ambiguity_question`. Tell the user the response format: reply with "all correct" to auto-confirm everything, OR a comma- / space-separated list of the item numbers that are NOT correct, OR "all incorrect" to drill down on every item.
2. **Parse the reply** — items the user did NOT include in their incorrect list are auto-`confirmed`. Items the user flagged are `flagged-for-drilldown`. ("all correct" → empty flagged set; "all incorrect" → every item flagged.)
3. **Drill-down round** — for each flagged item, the orchestrator asks ONE targeted follow-up. Preferred channel: `AskUserQuestion` with up to 4 options when the candidate-endpoint set is small (typically: each candidate endpoint, plus "none of these — confirm-stub", plus "skip — defer to implementation team"). For items with more than 4 candidates or that need free-form clarification, the orchestrator emits a focused free-form question. The user's answer updates the entry's `user_verdict`, `confirmed_action`, `confirmed_endpoint`, and (if applicable) `correction_note`. Multiple flagged items can be batched into a single message (4 questions per message, the `AskUserQuestion` maximum), so a 10-item drill-down takes 3 user-turns, not 10.
4. **Persist** — once every flagged item has a `user_verdict`, the orchestrator updates each intuition map's frontmatter to `confirmed: true` with `confirmed_at: <ISO 8601 UTC>`, re-mines to MemPalace, and Phase −1 closes.

**Phase 0 binding-input.** The confirmed intuition map becomes a binding input to OpenSpec spec authoring. Concretely: the proposal authoring step reads every `confirmed_action` / `confirmed_endpoint` and ensures the proposal text reflects them; the spec authoring step adds an acceptance criterion per confirmed element. Any spec that contradicts a confirmed intuition without an explicit override (`superseded_by: REQ-XXX` in the entry, recorded only when the user explicitly overrides their earlier verdict in a Phase 0+ message) is a Phase 1 gate failure.

**Phase 1 coverage-map enrichment.** Each `frontend` or `both`-layer requirement that touches a designed screen MUST include every confirmed element-action-endpoint triple from the relevant screen as an acceptance criterion. The Phase 5 `interaction-completeness` team then verifies them all.

### Domain gate vs. process gate

The v0.9.20 "gates are opt-in" rule applies to **pipeline-process gates** — `AskUserQuestion` calls that ask whether the user wants to proceed, "should I fix this bug" prompts where the answer is obvious, `--proposal-first` pauses. The Phase −1D bulk-verify is a **domain gate** — it is the user-confirmation step that IS the feature, exactly like the `editability-completeness` team's `ambiguous` attribute escalation. It fires whenever the gathered low-confidence set is non-empty, regardless of `--proposal-first`. The skill body's `## Default mode of operation` section is amended to make this distinction explicit so the two rules do not appear to contradict each other.

## Reuse Decisions

| Decision | Choice | Justification |
|---|---|---|
| Verification skill structure | **reuse** the `interaction-completeness` 3-reviewer / converge / Round-3 / multi-pass pattern | Already proven (v0.9.19 dogfood). The intuition skill is a single-agent per-codebase producer rather than a 3-reviewer converger because Phase −1B work is enumeration-driven, not judgment-converging — the user IS the converger via the Phase −1D gate. Adopt the structure where it fits (escalation-not-guessing, gap → SR / user-question), adapt where it does not. |
| Per-codebase artifact | **extend** the existing `<codebase>/docs/<MAP>.md` convention | `ROUTE_MAP.md`, `DESIGN_MAP.md`, `INTEGRATION_MAP.md` all live in `<codebase>/docs/`. `INTERACTION_INTUITION_MAP.md` slots in as a sibling. No new directory layout. |
| Producer agent | **build-new** `interaction-intuiter` rather than extending `route-mapper` | `route-mapper`'s scope is *enumeration from code* — facts already exist on disk. The intuiter's scope is *judgment about not-yet-existing code* — different cognitive workload + different tools allowlist + different model selection. Mixing them would burden `route-mapper` with intuition responsibilities it does not need when no design or API map is present. Keeping them separate also lets the intuiter spawn only when at least one of `DESIGN_MAP.md` or `INTEGRATION_MAP.md` exists for the codebase — a clean precondition that `route-mapper` does not enforce. |
| Bulk-verify UI | **extend** the existing `AskUserQuestion` pattern, batched | `AskUserQuestion` caps options at 4 per question, and 4 questions per message. The drill-down round packs flagged items 4-per-message; the bulk-present step uses a numbered text list (not `AskUserQuestion` — the user replies in free form because the list can be arbitrarily long). The text-list pattern is already used by other escalations; no new UI primitive. |
| MemPalace room | **extend** the existing `--room <name>` mining convention | New room name `interaction-intuitions`. No schema change to MemPalace. |
| Documentation-currency gate | **reuse** the existing v0.9.15 mechanism | CODEBASE_MAP / INTEGRATION_MAP / README / CHANGELOG / CLAUDE.md all swept at Phase 8 by the existing audit + `documentation-currency` skill. No new gate. |
| Test framework | **reuse** the existing pytest structural-test pattern | New tests follow `tests/test_interaction_completeness.py`'s shape. `EXPECTED_SKILLS` / `EXPECTED_AGENTS` in the central test files are appended. |
| Domain-gate carve-out | **modify** the existing `## Default mode of operation` section in the pipeline skill | The v0.9.20 rule is already in place; this change clarifies (in the same section, not a new one) that domain gates are distinct from process gates. One additional paragraph, not a rewrite. |

No new third-party dependency. No new file outside `<codebase>/docs/`, `skills/`, `agents/`, `tests/`, `commands/`, `.claude-plugin/`, and the top-level docs.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The intuiter produces hundreds of `low` / `unknown` items for a complex design, drowning the user in the bulk-verify gate | The intuiter MUST set `confidence: high` whenever the maps responsibly support it; the rubric explicitly biases toward `high` when an exact endpoint match exists. For initial-run designs that ARE that ambiguous, the gate's existence is the correct signal — the user wanted to see them. A future enhancement could chunk the bulk-verify list into per-route sections; not needed for v0.9.21. |
| The user's bulk-reply parser misinterprets "1, 4, 7" vs. "all correct" vs. "all incorrect" | The orchestrator's reply-parsing logic uses three deterministic heuristics in order: (1) exact match `all correct` or `all incorrect` (case-insensitive, leading/trailing whitespace trimmed); (2) any comma- or whitespace-separated list of integers within the valid range — those integers are the flagged set; (3) anything else → re-prompt with the format reminder. The skill body documents the heuristics. |
| The Phase −1D gate makes a no-frontend run pause unnecessarily | The gate fires ONLY when at least one frontend codebase has produced an intuition map with at least one `low`/`unknown`/flagged-`medium` element. For non-frontend runs (e.g., this v0.9.21 self-mod) the gate is a silent no-op. |
| The `--proposal-first` flag and the Phase −1D gate appear to contradict each other (one says "don't pause", the other says "pause") | The domain-gate carve-out paragraph in `## Default mode of operation` resolves this explicitly: process gates are opt-in; domain gates are part of the deliverable. The skill body and the command file both cite this. |
| Future skill drift — someone removes the intuiter from Phase −1B and the pipeline silently skips intuition | The pipeline-wiring tests assert the intuiter is named in both `architect-team-pipeline/SKILL.md`'s Phase −1B section AND `intake-and-mapping/SKILL.md`'s per-codebase mapping section. A drift breaks the test suite. |
