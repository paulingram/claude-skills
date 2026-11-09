# Phase −1D — Interaction intuition (per-frontend-codebase production + bulk-verify gate)

> **Nomenclature note.** In this skill, Phase −1D is presented as its own H2 section (the focus here is the per-codebase mapping flow's late steps). In `architect-team-pipeline/SKILL.md`'s `## Phase −1 — Intake & Mapping` super-section, Phase −1D appears as sub-section D under that single H2 (the focus there is the entire pipeline). Both refer to the same orchestration step with the identical canonical name "Phase −1D"; the structural-level difference is an aesthetic choice (focus follows nesting). Tests assert the identifier "Phase −1D" appears in both files; the H2/H3 distinction is intentional.


After every codebase has a complete map AND `INTEGRATION_MAP.md` is synthesized (next section), Phase −1D runs once per frontend codebase to cross-walk routes × design × integration into an explicit per-element intuition of "what action does this control take and which endpoint does it call". When no frontend codebase exists in scope, Phase −1D is a silent no-op.

Per the `interaction-intuition` skill:

1. **Per-frontend-codebase intuiter dispatch.** For each codebase that produced a `ROUTE_MAP.md` in the per-codebase ct6-converge workflow above, dispatch the `interaction-intuiter` agent. It reads that codebase's `ROUTE_MAP.md`, its `DESIGN_MAP.md` (when present), `<workspace>/docs/INTEGRATION_MAP.md`, and `$REQ_DIR` — and writes `<codebase>/docs/INTERACTION_INTUITION_MAP.md` with `confirmed: false`. The per-codebase intuiter dispatches run in parallel.
2. **Auto-mine the intuition maps** to MemPalace.
3. **Bulk-verify gate.** The orchestrator gathers across every map every element with `confidence ∈ {low, unknown}` OR (`confidence == medium` AND `ambiguity_question != null`). If the gathered set is non-empty, present it to the user as a single numbered list and parse the reply per one of three formats (`all correct` / a list of incorrect item-number integers / `all incorrect`). Items the user did NOT flag are auto-`confirmed`.
4. **Drill-down round.** One targeted follow-up per flagged item — `AskUserQuestion` (4 options × 4 questions per message) when the candidate set fits; free-form otherwise. Each answer writes `user_verdict`, `confirmed_action`, `confirmed_endpoint`, and (when applicable) `correction_note` to the matching entry (keyed on `element_id`).
5. **Close.** Once every flagged item has a non-null `user_verdict`, flip each map's frontmatter to `confirmed: true` and `confirmed_at: <ISO 8601 UTC>`, re-mine each, and Phase −1D closes.

Phase −1D is a domain gate, not a process gate — it fires whenever the gathered low-confidence union is non-empty, regardless of `--proposal-first`.
