# interaction-intuition-discovery Specification

## Purpose

Define the discovery-phase enforcement layer that — for every frontend codebase in scope at Phase −1D — cross-walks `ROUTE_MAP.md` × `DESIGN_MAP.md` × `INTEGRATION_MAP.md` to produce an explicit per-element intuition of "what action does this control take and which endpoint will it call" with confidence (`high` / `medium` / `low` / `unknown`) + evidence + (for everything below `high`) a precise ambiguity question; then gate the transition from Phase −1 to Phase 0 on a bulk user-verification (single numbered list; reply `all correct` / a list of incorrect indices / `all incorrect`) with a targeted drill-down resolving only the flagged subset. The confirmed intuition map is a binding input to Phase 0 spec authoring and Phase 1 coverage criteria. The Phase −1D bulk-verify gate is a *domain gate* (not a process gate) — it fires whenever the gathered low-confidence union is non-empty, regardless of `--proposal-first`.

## Requirements

### Requirement: interaction-intuition skill

The system SHALL provide an `interaction-intuition` skill at `skills/interaction-intuition/SKILL.md` that defines a discovery-phase enforcement layer for every frontend codebase in scope: it cross-walks `ROUTE_MAP.md` × `DESIGN_MAP.md` × `INTEGRATION_MAP.md` and produces an explicit per-element intuition of "what action does this control take and which endpoint will it call" with explicit confidence, evidence, and (for low-confidence items) a precise ambiguity question. The skill SHALL define inputs, outputs, the confidence rubric, the per-element intuition process, the artifact schema, the escalate-don't-guess rule, and the domain-gate carve-out relative to the v0.9.20 gates-opt-in rule.

#### Scenario: Skill file exists and is well-formed

- **WHEN** `skills/interaction-intuition/SKILL.md` is parsed
- **THEN** it has valid frontmatter with a `name` of `interaction-intuition` and a quoted `description`
- **AND** it is registered in `tests/test_skills.py`'s `EXPECTED_SKILLS`

#### Scenario: Skill defines the required sections

- **WHEN** the `interaction-intuition` skill body is read
- **THEN** it has a `## Inputs` section naming `ROUTE_MAP.md`, `DESIGN_MAP.md`, and `INTEGRATION_MAP.md` as the three required input artifacts
- **AND** a `## Outputs` section naming `<codebase>/docs/INTERACTION_INTUITION_MAP.md` as the per-codebase artifact
- **AND** a `## Confidence rubric` section defining `high` / `medium` / `low` / `unknown`
- **AND** a `## Per-element intuition` section defining the deterministic process
- **AND** a `## Artifact schema` section documenting every required frontmatter and per-element field
- **AND** a `## Escalate-don't-guess` section stating that ambiguity becomes `unknown` with a precise question, never an invented action
- **AND** a `## Domain-gate carve-out` section referencing the v0.9.20 gates-opt-in rule and naming the Phase −1D bulk-verify as a domain gate

### Requirement: interaction-intuiter agent

The system SHALL provide an `interaction-intuiter` agent at `agents/interaction-intuiter.md`, spawned per frontend codebase during Phase −1B after `route-mapper`, that reads the route + design + integration maps for that codebase, enumerates every interactive-by-design element, classifies each action and candidate endpoint(s), assigns a confidence, and writes the per-codebase `INTERACTION_INTUITION_MAP.md`. The agent SHALL be analysis-only with respect to feature code: it is permitted `Write` access only for the intuition map and must NOT have `Edit` in its tools allowlist.

#### Scenario: Agent file exists with valid frontmatter

- **WHEN** `agents/interaction-intuiter.md` is parsed
- **THEN** it has valid frontmatter with the five required keys (`name`, `description`, `model`, `tools`, `color`)
- **AND** `model` is `opus`
- **AND** the tools allowlist contains `Read`, `Glob`, `Grep`, `LS`, `Bash`, `Write`, and `TodoWrite`
- **AND** the tools allowlist does NOT contain `Edit`
- **AND** it is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`

#### Scenario: Agent body documents the required sections

- **WHEN** the agent body is parsed
- **THEN** it contains `## Inputs`, `## Process`, `## Output schema`, `## Escalate-don't-guess`, and `## What this agent does NOT do` sections
- **AND** the `## What this agent does NOT do` section states explicitly that `Write` is permitted only for the intuition map

### Requirement: INTERACTION_INTUITION_MAP.md artifact schema

The system SHALL document an artifact schema for `<codebase>/docs/INTERACTION_INTUITION_MAP.md` in the `interaction-intuition` skill body's `## Artifact schema` section. The schema SHALL include:

- YAML frontmatter fields: `last_intuited`, `confirmed`, `confirmed_at`, `producer`, `inputs`, `covers_screens`, `covers_elements`, `confidence_summary`.
- Per-element fields: `element_id`, `route`, `element_label`, `element_kind`, `design_source`, `intuited_action`, `candidate_endpoints[]` (with `method`, `path`, `source`, `match_kind`), `confidence`, `evidence[]`, `ambiguity_question`, `user_verdict`, `correction_note`, `confirmed_action`, `confirmed_endpoint`, `superseded_by`.
- A `match_kind` taxonomy: `exact-by-label`, `exact-by-action-noun`, `plausible-by-design-intent`, `inferred-from-similar-route`.

#### Scenario: Schema documentation contains every required field

- **WHEN** the structural test reads the `## Artifact schema` section of the skill body
- **THEN** it finds explicit mention of every frontmatter field name listed above
- **AND** every per-element field name listed above
- **AND** every `match_kind` value listed above

### Requirement: Confidence-classification rubric

The `interaction-intuition` skill body's `## Confidence rubric` section SHALL define the four labels with explicit criteria: `high` (clear label AND `exact-by-*` endpoint match AND design context aligns), `medium` (clear label OR exact match but not both, OR multiple plausible candidates), `low` (unclear label OR no obvious candidate OR conflicting signals), `unknown` (element exists in design but neither route nor API points to an action). The rubric SHALL state that every `low` and `unknown` element MUST surface to the Phase −1D gate, and that `medium` elements surface only when the agent has populated a non-null `ambiguity_question`.

#### Scenario: Rubric is parametrized in tests

- **WHEN** `tests/test_interaction_intuition_map_schema.py` runs
- **THEN** it asserts every confidence label (`high`, `medium`, `low`, `unknown`) is named in the skill body's `## Confidence rubric` section
- **AND** it asserts the rule "every `low` and `unknown` element MUST surface to the Phase −1D gate" is stated in the skill body

### Requirement: Phase −1D bulk-verify gate

The `architect-team-pipeline` skill body SHALL contain a `## Phase −1D — Interaction-intuition bulk-verify gate` section (or equivalent name containing both "Phase −1D" and "bulk-verify") that defines:

- The trigger condition: the gate fires at the end of Phase −1 (after Phase −1C's `INTEGRATION MAP COMPLETE`) when the union across every frontend codebase's `INTERACTION_INTUITION_MAP.md` contains at least one `low`/`unknown` element OR a `medium` element with a non-null `ambiguity_question`. If the union is empty, the gate is a silent no-op.
- The presentation: the orchestrator emits a single numbered list — each item showing index, route, element label, intuited action, top candidate endpoint, confidence, and the agent's specific ambiguity question.
- The response format: the user replies with `all correct`, a comma- or whitespace-separated list of item-number integers (the flagged set), or `all incorrect`. Anything else triggers a re-prompt with the format reminder.
- The auto-confirmation: unflagged items receive `user_verdict: confirmed`, `confirmed_action: <intuited_action>`, `confirmed_endpoint: <top candidate>` when a candidate exists.

#### Scenario: Pipeline skill names the gate and its parts

- **WHEN** the structural test parses `skills/architect-team-pipeline/SKILL.md`
- **THEN** it finds a section header containing both "Phase −1D" and "bulk-verify"
- **AND** that section names all three reply formats (`all correct`, the integer list, `all incorrect`)
- **AND** it states the no-op condition for an empty low-confidence union
- **AND** it states the auto-confirmation rule for unflagged items

### Requirement: Drill-down follow-up round

The Phase −1D section SHALL define a drill-down follow-up round that fires after the bulk-verify reply is parsed. For each item the user flagged, ONE targeted follow-up question SHALL be emitted using `AskUserQuestion` (up to 4 options per question, up to 4 questions per message, batched) when the candidate-endpoint set fits; otherwise a free-form question. The user's answer SHALL update the corresponding entry's `user_verdict`, `confirmed_action`, `confirmed_endpoint`, and (when applicable) `correction_note`. The map's frontmatter `confirmed` SHALL flip to `true` only after every flagged item across every map in scope has a non-null `user_verdict`, at which point the map is re-mined to MemPalace `--room interaction-intuitions`.

#### Scenario: Drill-down preserves item identity

- **WHEN** a flagged item is resolved during drill-down
- **THEN** the corresponding entry in the on-disk `INTERACTION_INTUITION_MAP.md` is updated in place (matched on `element_id`)
- **AND** `confirmed: true` flips only after every flagged item has a non-null `user_verdict`
- **AND** the updated map is re-mined to MemPalace `--room interaction-intuitions`

### Requirement: Binding-input rule for Phase 0 and Phase 1

The `architect-team-pipeline` skill body SHALL state two binding-input rules: (1) Phase 0 spec authoring reads the `confirmed: true` intuition map and the proposal / spec text MUST reflect every confirmed `confirmed_action` / `confirmed_endpoint` mapping; contradicting a confirmed intuition without an explicit override (`superseded_by: REQ-XXX` in the entry, recorded only on an explicit user override) is a Phase 1 gate failure. (2) Phase 1 coverage-map authoring MUST include every confirmed element-action-endpoint triple from the relevant screen as an acceptance criterion for each `frontend` or `both`-layer requirement that touches a designed screen.

#### Scenario: Pipeline skill states the binding rules

- **WHEN** the structural test parses the pipeline skill's Phase 0 and Phase 1 sections
- **THEN** Phase 0 mentions reading the confirmed intuition map as a binding input
- **AND** Phase 1's loop conditions name the confirmed wirings as required coverage-map content for in-scope frontend / both-layer requirements
- **AND** the `superseded_by: REQ-XXX` override mechanism is named

### Requirement: Domain-gate carve-out

The `architect-team-pipeline` skill's `## Default mode of operation` section (added in v0.9.20) SHALL be amended to distinguish process gates (opt-in: `--proposal-first`, "do you want me to proceed", obvious-answer clarifying questions) from domain gates (always fire when the deliverable requires user input: the Phase −1D bulk-verify, the `editability-completeness` `ambiguous` attribute escalation, the `interaction-completeness` `ambiguous` element escalation). The `commands/architect-team.md` file's `--proposal-first` flag bullet SHALL include a one-line clarification pointing at this distinction.

#### Scenario: Section explicitly distinguishes process vs. domain gates

- **WHEN** the structural test parses the pipeline skill's `## Default mode of operation` section
- **THEN** it finds explicit references to BOTH "process gate" and "domain gate" (or equivalent phrasing — the two distinct categories named)
- **AND** the Phase −1D bulk-verify is named as a domain gate
- **AND** `commands/architect-team.md`'s `--proposal-first` flag bullet contains a one-line clarification of the carve-out

### Requirement: Pipeline + discipline wiring

The system SHALL update existing files to wire the intuiter into the pipeline. The dispatch site is the new Phase −1D sub-section (production + bulk-verify gate together) added to `## Phase −1 — Intake & Mapping` between section C (integration mapping) and Phase 0. Phase −1D is the correct site because the intuiter requires `INTEGRATION_MAP.md` (a Phase −1C output) and runs once per frontend codebase in parallel:

- `skills/architect-team-pipeline/SKILL.md` MUST contain a Phase −1D sub-section (D within `## Phase −1 — Intake & Mapping`, header includes "Phase −1D" and "bulk-verify") that dispatches `interaction-intuiter` per frontend codebase and then fires the bulk-verify gate.
- `skills/intake-and-mapping/SKILL.md` MUST name `interaction-intuiter` and the `INTERACTION_INTUITION_MAP.md` artifact as a Phase −1D step.
- `skills/frontend-route-mapping/SKILL.md` MUST name `interaction-intuition` as a Phase −1D consumer of `ROUTE_MAP.md`.
- `skills/design-fidelity-mapping/SKILL.md` MUST name `interaction-intuition` as a Phase −1D consumer of `DESIGN_MAP.md`.
- `agents/route-mapper.md` MUST note that its output feeds `interaction-intuiter` at Phase −1D.

#### Scenario: Wiring is present in every named file

- **WHEN** the structural test parses each of the five files above
- **THEN** each file contains the expected reference to `interaction-intuiter` (or `interaction-intuition`) in the location described above
- **AND** the pipeline skill's Phase −1D sub-section is the dispatch site (not Phase −1B), reflecting the INTEGRATION_MAP dependency

### Requirement: Test coverage for v0.9.21

The plugin SHALL include the following new pytest files with structural coverage:

- `tests/test_interaction_intuition_skill.py` — frontmatter validity; required section presence (`## Inputs`, `## Outputs`, `## Confidence rubric`, `## Per-element intuition`, `## Artifact schema`, `## Escalate-don't-guess`, `## Domain-gate carve-out`); confidence labels parametrized; must-surface rule asserted.
- `tests/test_interaction_intuiter_agent.py` — frontmatter (5 keys, `model: opus`); tools allowlist (`Edit` not present; `Write` present); required body sections.
- `tests/test_phase_minus_1d_bulk_verify_wiring.py` — pipeline skill has Phase −1B intuiter dispatch + Phase −1D gate section + three reply formats + binding-input rule for Phase 0/1; intake-and-mapping has matching per-codebase step.
- `tests/test_interaction_intuition_map_schema.py` — every frontmatter field + every per-element field + every `match_kind` value + every confidence label parametrized and asserted present in the skill body.

Existing tests SHALL be updated: `tests/test_skills.py` `EXPECTED_SKILLS` includes `interaction-intuition`; `tests/test_agents.py` `EXPECTED_AGENTS` includes `interaction-intuiter`.

#### Scenario: All structural tests pass

- **WHEN** `python -m pytest -q` runs from the repo root
- **THEN** the suite exits 0
- **AND** the total passing-test count is strictly greater than 649 (the v0.9.20 baseline)
- **AND** no pre-existing test regresses

### Requirement: Release as v0.9.21

The plugin SHALL be released as `v0.9.21` with all documentation updated for currency:

- `README.md` banner shows `v 0 . 9 . 21`, version badge shows `0.9.21`, tests badge reflects the new total, the timeline `(current)` marker is on the v0.9.21 entry, a new section after the v0.9.20 panel documents interaction-intuition + the Phase −1D bulk-verify gate.
- `CHANGELOG.md` carries a prepended `## [0.9.21] — 2026-05-22` entry quoting the user's verbatim directive as the WHY and covering all requirements in this change.
- `docs/CODEBASE_MAP.md` — `last_mapped` bumped; skill count 20 → 21; agent count 17 → 18; new sections for `skills/interaction-intuition/` and `agents/interaction-intuiter.md`; §1 references v0.9.21.
- `docs/INTEGRATION_MAP.md` — `last_synthesized` bumped; new per-codebase artifact `INTERACTION_INTUITION_MAP.md` named.
- `CLAUDE.md` — frontmatter counts updated.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — `version: "0.9.21"`.

#### Scenario: Documentation-currency tests pass at v0.9.21

- **WHEN** `python -m pytest -q tests/test_readme_styling.py` runs (or equivalent doc-currency tests)
- **THEN** every banner / badge / version assertion passes at v0.9.21
- **AND** the Phase 8 documentation-currency audit returns exit-0
