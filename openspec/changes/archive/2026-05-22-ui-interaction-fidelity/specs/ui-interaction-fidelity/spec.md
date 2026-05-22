## ADDED Requirements

### Requirement: Interaction-completeness verification skill

The system SHALL provide an `interaction-completeness` skill at `skills/interaction-completeness/SKILL.md` that defines a judgment-heavy verification discipline for UI/UX work: for every slice with interactive surface it independently enumerates every interactive element AND every page / screen / route, classifies each element by how it is wired and each page as `live` / `placeholder` / `confirmed-stub`, verifies every non-stub element has a genuine user-driven Playwright test, and traces each element to its endpoint or client-only behavior. The skill SHALL mandate a three-reviewer parallel-then-converge loop with a `system-architect` Round-3 robustness review and a bounded multi-pass outer loop, modeled on the `editability-completeness` skill.

#### Scenario: Skill file exists and is well-formed

- **WHEN** `skills/interaction-completeness/SKILL.md` is parsed
- **THEN** it has valid frontmatter with a `name` of `interaction-completeness` and a quoted `description`
- **AND** it is registered in `tests/test_skills.py`'s `EXPECTED_SKILLS`

#### Scenario: Skill mandates the three-reviewer converging structure

- **WHEN** the `interaction-completeness` skill body is read
- **THEN** it mandates three `interaction-reviewer` agents spawned in parallel for independent analysis
- **AND** a round-robin convergence step, a `system-architect` Round-3 robustness review, and a bounded multi-pass outer loop
- **AND** it states that gaps become solution requirements

#### Scenario: Skill covers both interactive elements and pages

- **WHEN** the skill's scope and classification rubric are read
- **THEN** it defines an element wiring rubric with an `endpoint-backed` class, a `client-only` class, a `confirmed-stub` class, and an `ambiguous` class that escalates to the human
- **AND** it defines a page-classification rubric with `live`, `placeholder`, and `confirmed-stub` classes

### Requirement: Interaction-reviewer agent

The system SHALL provide an `interaction-reviewer` agent at `agents/interaction-reviewer.md`, spawned three times in parallel, that independently enumerates interactive elements and pages, classifies element wiring and page genuineness, traces each element to its endpoint, audits Playwright test authenticity, detects placeholder pages and hardcoded-should-be-dynamic values, and is analysis-only — it has no `Edit` access to feature code and produces verdicts, not fixes.

#### Scenario: Agent file exists with valid frontmatter

- **WHEN** `agents/interaction-reviewer.md` is parsed
- **THEN** it has the five required frontmatter keys (`name`, `description`, `tools`, `model`, `color`)
- **AND** `model` is `opus` and every entry in `tools` is from the valid tool set
- **AND** it is registered in `tests/test_agents.py`'s `EXPECTED_AGENTS`

#### Scenario: Agent is analysis-only

- **WHEN** the `interaction-reviewer` agent's `tools` list is inspected
- **THEN** it does not include `Edit` — the agent classifies, traces, and writes verdict / SR artifacts but never edits feature code

### Requirement: Confirmed-stub mechanism

An interactive element OR a page that is intentionally inert or a placeholder SHALL be classifiable as `confirmed-stub` ONLY with explicit user confirmation. An `interaction-reviewer` that encounters an inert element or a placeholder page SHALL escalate a structured question to the human via the orchestrator rather than guess; once confirmed, the stub SHALL be recorded durably; an unconfirmed inert control or unconfirmed placeholder page SHALL be reported as a gap, never silently passed.

#### Scenario: Unconfirmed inert control is a gap

- **GIVEN** an interactive element that drives no endpoint and no client behavior, with no user confirmation that it is an intentional stub
- **WHEN** the interaction-completeness review runs
- **THEN** the element is reported as a gap (an `unwired-control`) and a solution requirement is written

#### Scenario: Confirmed stub is accepted without a user-flow test

- **GIVEN** an inert interactive element or a placeholder page that the user has explicitly confirmed is intentional
- **WHEN** the interaction-completeness review runs
- **THEN** it is classified `confirmed-stub`, recorded in the converged interaction map and in the change's `coverage-map.json` `confirmed_stubs[]` list
- **AND** it is not reported as a gap and does not require a user-flow test

#### Scenario: Reviewer escalates rather than guessing

- **GIVEN** an interactive element or a page whose intended behavior cannot be determined from the requirements, design, or code
- **WHEN** an `interaction-reviewer` evaluates it
- **THEN** the reviewer escalates a structured question to the human and does not classify it as a stub or a gap on its own

### Requirement: ui_interaction_review review-gate field

The review-gate evidence schema in `hooks/review_evidence_schema.py` SHALL be bumped to version 6 with a new required field `ui_interaction_review` taking the values `pass`, `n/a`, or `fail`. `validate_evidence()` SHALL block `fail`, SHALL require a non-empty `ui_interaction_review_note` when the value is `n/a`, and the field SHALL be enforced by both the `review-gate-task.py` and `teammate-idle-check.py` hooks through the shared schema module.

#### Scenario: Evidence missing the field is blocked

- **GIVEN** a review-gate evidence file with no `ui_interaction_review` field
- **WHEN** `validate_evidence()` runs
- **THEN** it returns a gap naming the missing `ui_interaction_review` field

#### Scenario: A fail value is blocked

- **GIVEN** a review-gate evidence file with `ui_interaction_review` set to `fail`
- **WHEN** `validate_evidence()` runs
- **THEN** it returns a gap — an unwired control, an unconfirmed placeholder page, or a hardcoded-dynamic-value must be escalated via a solution requirement, not marked complete

#### Scenario: An n/a value requires a note

- **GIVEN** a review-gate evidence file with `ui_interaction_review` set to `n/a` and no `ui_interaction_review_note`
- **WHEN** `validate_evidence()` runs
- **THEN** it returns a gap requiring a non-empty `ui_interaction_review_note`

#### Scenario: A pass value with the field present validates

- **GIVEN** an otherwise-valid review-gate evidence file with `ui_interaction_review` set to `pass`
- **WHEN** `validate_evidence()` runs
- **THEN** the field contributes no gap
- **AND** `SCHEMA_VERSION` is 6 and both evidence hooks import the shared schema module

### Requirement: Strengthened test-completeness-verifier Playwright audit

The `test-completeness-verifier` agent SHALL additionally flag a Playwright test that claims to be a user-flow test but performs no or near-zero genuine user interaction (no `page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles`), and SHALL cross-check the evidence-listed Playwright test IDs against the interactivity inventory so an interactive element with no covering test is flagged.

#### Scenario: A navigate-and-assert test masquerading as a flow is flagged

- **GIVEN** a Playwright test file in the evidence whose body contains `page.goto` and assertions but no genuine user-interaction calls
- **WHEN** the `test-completeness-verifier` audits the Playwright tests
- **THEN** it records the test as a vacuous-flow finding in its verdict JSON

#### Scenario: An inventory element with no covering test is flagged

- **GIVEN** an interactivity inventory listing an interactive element and a set of evidence-listed Playwright tests, none of which exercises that element
- **WHEN** the `test-completeness-verifier` cross-checks the inventory against the tests
- **THEN** it records the uncovered element as a finding

### Requirement: Pipeline and discipline wiring

The `architect-team-pipeline` skill SHALL invoke the interaction-completeness team at Phase 3 and Phase 5 for any slice with UI/UX surface, and the `playwright-user-flows`, `frontend`, `integration`, and `team-spawning-and-review-gates` skills/agents SHALL reference the `ui_interaction_review` field, the confirmed-stub mechanism, placeholder-page detection, and the `interaction-completeness` skill.

#### Scenario: Pipeline skill invokes the interaction-completeness team

- **WHEN** `skills/architect-team-pipeline/SKILL.md` is read
- **THEN** Phase 5 invokes the `interaction-completeness` team for any in-scope frontend slice
- **AND** the `ui_interaction_review` field is named in the Phase 3 review-gate description

#### Scenario: The v6 evidence schema is documented

- **WHEN** `skills/team-spawning-and-review-gates/SKILL.md` is read
- **THEN** the review-gate evidence schema section documents `ui_interaction_review` as a v6 field with its `pass`/`n/a`/`fail` semantics

#### Scenario: Frontend and integration agents emit the field

- **WHEN** `agents/frontend.md` and `agents/integration.md` are read
- **THEN** each instructs the agent to set `ui_interaction_review` in its review-gate evidence and to honor the confirmed-stub mechanism and the no-unconfirmed-placeholder-pages rule

### Requirement: Test coverage for the interaction-fidelity change

The pytest suite SHALL cover the new skills and agent registration, the v6 schema validation behavior of `ui_interaction_review`, both hooks' enforcement of the new field, the placeholder-detection and dynamic-value-discovery rubrics' presence in the skills, and the strengthened verifier's documented behavior — and the full suite SHALL pass with no regression.

#### Scenario: New test files exist and pass

- **WHEN** `python -m pytest tests/test_interaction_completeness.py tests/test_ui_interaction_review.py tests/test_dynamic_value_discovery.py -v` runs
- **THEN** every test passes
- **AND** the tests cover skill/agent registration, the page-and-element classification rubrics, the dynamic-value-discovery rubric, the v6 field's required/valid/n-a-note behavior, and hook enforcement

#### Scenario: Full suite passes with no regression

- **WHEN** `python -m pytest -v` runs from the repository root
- **THEN** every test passes, including the new interaction-fidelity tests and the updated cross-consistency and evidence-hook tests, with no regression in the pre-existing suite

### Requirement: Documentation and release

The change SHALL be documented and released as v0.9.19: a README section covering the new gate, the confirmed-stub mechanism, placeholder-page detection, and dynamic-value discovery; a `CHANGELOG.md` `## [0.9.19]` entry; refreshed `docs/CODEBASE_MAP.md` (20 skills, 17 agents, evidence schema v6), `docs/INTEGRATION_MAP.md`, and `CLAUDE.md`; and a version bump to `0.9.19` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

#### Scenario: README documents the new gate

- **WHEN** the updated `README.md` is read
- **THEN** it documents the `interaction-completeness` verification gate, the `ui_interaction_review` field, the confirmed-stub mechanism, placeholder-page detection, and dynamic-value discovery

#### Scenario: CHANGELOG and version are consistent

- **WHEN** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `CHANGELOG.md` are inspected
- **THEN** both JSON files report version `0.9.19`
- **AND** `CHANGELOG.md` has a `## [0.9.19]` entry referencing the `ui-interaction-fidelity` requirements

#### Scenario: Maps reflect the new skills and agent

- **WHEN** `docs/CODEBASE_MAP.md` is read
- **THEN** it documents 20 skills (including `interaction-completeness` and `dynamic-value-discovery`), 17 agents (including `interaction-reviewer`), and the evidence schema at version 6

### Requirement: Placeholder-vs-live-page detection

The `interaction-completeness` skill and `interaction-reviewer` agent SHALL, for every slice with UI/UX surface, enumerate every page / screen / route and classify each as `live` (the real functional page — real components, real data fetching where the design requires it, the genuine interactive surface), `placeholder` (a stub / skeleton / "coming soon" / mock page shipped where a live page should be — a gap), or `confirmed-stub` (a placeholder the user has explicitly confirmed is intentional for this release). The skill SHALL define a placeholder-signal rubric, and the verification SHALL cross-check each page against what the design / requirements / `ROUTE_MAP.md` say that page should be. An unconfirmed `placeholder` page SHALL be reported as a gap and routed as a solution requirement.

#### Scenario: A route wired to a placeholder where a live page is specified is a gap

- **GIVEN** a route whose component is a placeholder / "coming soon" / skeleton / mock page, while the design or requirements specify a real live page for that route
- **WHEN** the interaction-completeness review runs
- **THEN** the page is classified `placeholder`, reported as a `placeholder-page` gap, and a solution requirement is written

#### Scenario: A user-confirmed placeholder page is accepted

- **GIVEN** a placeholder page that the user has explicitly confirmed is an intentional placeholder for this release
- **WHEN** the interaction-completeness review runs
- **THEN** the page is classified `confirmed-stub`, recorded in the converged interaction map and the `confirmed_stubs[]` list, and is not reported as a gap

#### Scenario: The skill defines a placeholder-signal rubric

- **WHEN** the `interaction-completeness` skill body is read
- **THEN** it defines placeholder signals — component / file naming (e.g. `Placeholder`, `ComingSoon`, `Stub`, `Mock`), "coming soon" / "under construction" / lorem-ipsum content, a data-driven page that makes no API calls, a near-empty route shell, and a route-table entry pointing at a placeholder while the real component is specified-but-unwired

#### Scenario: An ambiguous page escalates rather than being guessed

- **GIVEN** a page whose intended state (live vs. intentional placeholder) cannot be determined from the requirements, design, or `ROUTE_MAP.md`
- **WHEN** an `interaction-reviewer` evaluates it
- **THEN** the reviewer escalates a structured question to the human and does not classify the page on its own

### Requirement: Dynamic-value-discovery skill

The system SHALL provide a `dynamic-value-discovery` skill at `skills/dynamic-value-discovery/SKILL.md` that defines a cross-role discipline for distinguishing genuine static literals from sample data standing in for dynamic, data-bound values. The skill SHALL define how to classify a displayed value `static` or `dynamic` from CONTEXT — position, the value's nature, and the requirements / design language — rather than from the literal itself, SHALL mandate that every value classified `dynamic` is bound to a named data source, and SHALL require escalation to the human when a value's classification is genuinely ambiguous.

#### Scenario: Skill file exists and is well-formed

- **WHEN** `skills/dynamic-value-discovery/SKILL.md` is parsed
- **THEN** it has valid frontmatter with a `name` of `dynamic-value-discovery` and a quoted `description`
- **AND** it is registered in `tests/test_skills.py`'s `EXPECTED_SKILLS`

#### Scenario: The skill classifies from context, not from the literal

- **WHEN** the skill's classification rubric is read
- **THEN** it states that the same literal can be static in one place and dynamic in another and the classification is made from context — position, the value's nature, the requirements / design language — not from the value itself
- **AND** it lists dynamic signals (person names, dates, currency amounts, counts, statuses, a value in a record-detail view or a repeating list row, a greeting with a name) and static signals (nav labels, button text, section headings, fixed helper text, brand strings)

#### Scenario: Dynamic values must be bound to a data source

- **WHEN** the skill body is read
- **THEN** it mandates that every value classified `dynamic` is bound to a named data source — never shipped as the design's hardcoded sample literal

#### Scenario: An ambiguous value escalates rather than being guessed

- **GIVEN** a displayed value whose static-vs-dynamic classification cannot be determined from the requirements, design, or code
- **WHEN** the dynamic-value-discovery discipline is applied
- **THEN** the classification is escalated to the human as a structured question rather than guessed

### Requirement: Dynamic-value discovery wired into developer, architect, and evaluator

The `dynamic-value-discovery` skill SHALL be referenced by the developer agents (`frontend`, `backend`), by the architect (`system-architect` agent and the `design-fidelity-mapping` skill), and by the evaluator (`interaction-reviewer` agent and the `interaction-completeness` skill). The `interaction-completeness` verification SHALL flag a hardcoded value that context indicates should be dynamically bound as a `hardcoded-dynamic-value` gap, routed as a solution requirement.

#### Scenario: Developer agents bind dynamic values

- **WHEN** `agents/frontend.md` and `agents/backend.md` are read
- **THEN** each instructs the agent to apply `dynamic-value-discovery` — bind every dynamic value to its data source and never hardcode design sample data

#### Scenario: Architect classifies values at planning

- **WHEN** `agents/system-architect.md` and `skills/design-fidelity-mapping/SKILL.md` are read
- **THEN** the `system-architect` consults `dynamic-value-discovery` when reviewing specs and designs
- **AND** the DESIGN_MAP's per-screen visual specs classify each value `static` or `dynamic` and name the data source for each dynamic value

#### Scenario: Evaluator flags hardcoded dynamic values

- **WHEN** `agents/interaction-reviewer.md` and `skills/interaction-completeness/SKILL.md` are read
- **THEN** the `interaction-reviewer` applies `dynamic-value-discovery` and reports a hardcoded value the context shows should be dynamic as a `hardcoded-dynamic-value` gap
- **AND** such a gap is routed as a solution requirement and surfaces through the `ui_interaction_review` field
