## 1. REQ-001: interaction-intuition skill

- [ ] 1.1 Create `skills/interaction-intuition/SKILL.md` with valid frontmatter (`name: interaction-intuition`, quoted `description`).
- [ ] 1.2 Author `## Inputs`: name `ROUTE_MAP.md`, `DESIGN_MAP.md` (when present), `INTEGRATION_MAP.md`.
- [ ] 1.3 Author `## Outputs`: name `<codebase>/docs/INTERACTION_INTUITION_MAP.md` as the per-codebase artifact.
- [ ] 1.4 Author `## Confidence rubric` with `high` / `medium` / `low` / `unknown` per REQ-004; state the rule "every `low` and `unknown` element MUST surface to the Phase −1D gate".
- [ ] 1.5 Author `## Per-element intuition`: deterministic process — per-screen enumeration → action intuition → candidate-endpoint matching → confidence assignment → ambiguity-question authoring.
- [ ] 1.6 Author `## Artifact schema`: every required frontmatter field + every required per-element field, with brief semantics.
- [ ] 1.7 Author `## Escalate-don't-guess`: the rule that ambiguous → `unknown` with a precise question, never invent an action.
- [ ] 1.8 Author `## Domain-gate carve-out`: cite the v0.9.20 gates-opt-in rule and clarify that the Phase −1D gate is a domain gate (fires regardless of `--proposal-first`).

## 2. REQ-002: interaction-intuiter agent

- [ ] 2.1 Create `agents/interaction-intuiter.md` with valid frontmatter — five required keys, `model: opus`, color.
- [ ] 2.2 Set tools allowlist: `Read, Glob, Grep, LS, Bash, Write, TodoWrite`. NO `Edit`.
- [ ] 2.3 Author `## Inputs`, `## Process`, `## Output schema`, `## Escalate-don't-guess`, `## What this agent does NOT do` sections.
- [ ] 2.4 In `## What this agent does NOT do`, state explicitly that `Write` is permitted only for the intuition map; no source-code writes.

## 3. REQ-003: INTERACTION_INTUITION_MAP.md schema

- [ ] 3.1 In the skill body's `## Artifact schema`, document the YAML frontmatter fields: `last_intuited`, `confirmed`, `confirmed_at`, `producer`, `inputs`, `covers_screens`, `covers_elements`, `confidence_summary`.
- [ ] 3.2 Document the per-element fields: `element_id`, `route`, `element_label`, `element_kind`, `design_source`, `intuited_action`, `candidate_endpoints[]` (each with `method`, `path`, `source`, `match_kind`), `confidence`, `evidence[]`, `ambiguity_question`, `user_verdict`, `correction_note`, `confirmed_action`, `confirmed_endpoint`, `superseded_by`.
- [ ] 3.3 Document the `match_kind` taxonomy: `exact-by-label`, `exact-by-action-noun`, `plausible-by-design-intent`, `inferred-from-similar-route`.

## 4. REQ-004: confidence rubric

- [ ] 4.1 Author the four labels in `## Confidence rubric` with explicit criteria (matching the spec REQ-004 definitions).
- [ ] 4.2 State that `low` and `unknown` MUST surface; `medium` surfaces only with a non-null `ambiguity_question`.
- [ ] 4.3 State the bias-toward-`high`-when-supported rule (the rubric should not produce hundreds of `low` items for an exact-match heavy design).

## 5. REQ-005: Phase −1D bulk-verify gate

- [ ] 5.1 In `skills/architect-team-pipeline/SKILL.md`, add a `## Phase −1D — Interaction-intuition bulk-verify gate` section between Phase −1C and Phase 0.
- [ ] 5.2 Define the trigger condition: gate fires when union of all maps has at least one `low`/`unknown`/flagged-`medium`; no-op otherwise.
- [ ] 5.3 Define the presentation format: single numbered list with index, route, element label, intuited action, top candidate, confidence, ambiguity question.
- [ ] 5.4 Define the response parser: three reply formats (`all correct`, integer list, `all incorrect`); anything else re-prompts.
- [ ] 5.5 Define auto-confirmation: unflagged items get `user_verdict: confirmed`, `confirmed_action: <intuited>`, `confirmed_endpoint: <top candidate>`.

## 6. REQ-006: drill-down follow-up

- [ ] 6.1 In the same Phase −1D section, define the drill-down round: one targeted question per flagged item.
- [ ] 6.2 Specify the preferred channel: `AskUserQuestion` (max 4 options, max 4 questions per message — batching allowed); free-form when candidates exceed 4 or the question needs prose.
- [ ] 6.3 Define the update rule: each answer writes `user_verdict`, `confirmed_action`, `confirmed_endpoint`, optional `correction_note` to the corresponding entry.
- [ ] 6.4 Define the gate exit: `confirmed: true` + `confirmed_at: <ISO>` flips ONLY after every flagged item across every map has a non-null `user_verdict`. Re-mine to MemPalace `--room interaction-intuitions`.

## 7. REQ-007: binding-input rule for Phase 0 + Phase 1

- [ ] 7.1 In the pipeline skill's Phase 0 section, state that the confirmed intuition map is a binding input to OpenSpec proposal / spec authoring.
- [ ] 7.2 Define the override mechanism: a `superseded_by: REQ-XXX` field on the entry, populated only when the user explicitly overrides post-Phase 0; otherwise a contradicting spec is a Phase 1 gate failure.
- [ ] 7.3 In the Phase 1 loop conditions, add: every `frontend` or `both`-layer requirement that touches a designed screen MUST include every confirmed element-action-endpoint triple as an acceptance criterion in the coverage map.

## 8. REQ-008: domain-gate carve-out

- [ ] 8.1 In `skills/architect-team-pipeline/SKILL.md`'s `## Default mode of operation` section (added v0.9.20), add a paragraph distinguishing process gates from domain gates.
- [ ] 8.2 Name the Phase −1D bulk-verify, the `editability-completeness` `ambiguous` escalation, and the `interaction-completeness` `ambiguous` escalation as domain gates.
- [ ] 8.3 In `commands/architect-team.md`, extend the `--proposal-first` flag bullet with a one-line clarification ("Domain gates — Phase −1D bulk-verify, ambiguous-attribute escalations — fire regardless of this flag.").

## 9. REQ-009: pipeline + discipline wiring

- [ ] 9.1 Edit `skills/architect-team-pipeline/SKILL.md` Phase −1B subsection: after the route-mapper invocation, name `interaction-intuiter` as the next agent dispatched against the same codebase.
- [ ] 9.2 Edit `skills/intake-and-mapping/SKILL.md` per-codebase mapping section: name the `interaction-intuiter` step + INTERACTION_INTUITION_MAP.md output.
- [ ] 9.3 Edit `skills/frontend-route-mapping/SKILL.md`: end-of-skill section names `interaction-intuition` as the consumer of `ROUTE_MAP.md`.
- [ ] 9.4 Edit `skills/design-fidelity-mapping/SKILL.md`: end-of-skill section names `interaction-intuition` as the consumer of `DESIGN_MAP.md`.
- [ ] 9.5 Edit `agents/route-mapper.md`: notes its output feeds `interaction-intuiter`.

## 10. REQ-010: test coverage

- [ ] 10.1 Create `tests/test_interaction_intuition_skill.py` — assert frontmatter, the required sections (`## Inputs`, `## Outputs`, `## Confidence rubric`, `## Per-element intuition`, `## Artifact schema`, `## Escalate-don't-guess`, `## Domain-gate carve-out`), the four confidence labels parametrized, the must-surface rule.
- [ ] 10.2 Create `tests/test_interaction_intuiter_agent.py` — assert frontmatter (5 keys, `model: opus`), tools allowlist (`Edit` NOT present; `Write` IS present), required body sections.
- [ ] 10.3 Create `tests/test_phase_minus_1d_bulk_verify_wiring.py` — assert the pipeline skill has Phase −1B intuiter reference + Phase −1D gate section + three reply formats + binding-input rule for Phase 0/1; assert intake-and-mapping has the matching per-codebase step.
- [ ] 10.4 Create `tests/test_interaction_intuition_map_schema.py` — parametrize every frontmatter field + every per-element field; assert each appears in the skill body's `## Artifact schema` section.
- [ ] 10.5 Update `tests/test_skills.py` `EXPECTED_SKILLS` — append `interaction-intuition`.
- [ ] 10.6 Update `tests/test_agents.py` `EXPECTED_AGENTS` — append `interaction-intuiter`.
- [ ] 10.7 Run `python -m pytest -q` from the repo root — all pass, no regression against the pre-v0.9.21 baseline of 649.

## 11. REQ-011: documentation + release v0.9.21

- [ ] 11.1 Add a README section (after the v0.9.20 NEW IN block) documenting interaction-intuition + the Phase −1D bulk-verify gate; update the Pipeline phases listing.
- [ ] 11.2 Prepend `## [0.9.21] — 2026-05-22` to `CHANGELOG.md` covering REQ-001..011, with the user's verbatim directive quoted as the WHY.
- [ ] 11.3 Update `docs/CODEBASE_MAP.md` — `last_mapped`, skill count 20 → 21, agent count 17 → 18, new sections for `skills/interaction-intuition/` + `agents/interaction-intuiter.md`, §1 references v0.9.21.
- [ ] 11.4 Update `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; new per-codebase artifact `INTERACTION_INTUITION_MAP.md` named.
- [ ] 11.5 Update `CLAUDE.md` — frontmatter counts.
- [ ] 11.6 Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` `version: "0.9.21"`.
- [ ] 11.7 Update `README.md` banner (`v 0 . 9 . 21`), version badge, tests badge, timeline current marker.
- [ ] 11.8 Run full pytest one final time — confirm all pass.

## 12. Archive

- [ ] 12.1 After every requirement is verified, run `openspec archive interaction-intuition-discovery` to merge the spec deltas into `openspec/specs/`.
