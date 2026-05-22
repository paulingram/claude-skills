## 1. REQ-001: interaction-completeness skill

- [ ] 1.1 Create `skills/interaction-completeness/SKILL.md` with valid frontmatter (`name: interaction-completeness`, a quoted `description`).
- [ ] 1.2 Define the verification structure — three `interaction-reviewer` agents spawned in parallel for independent analysis, a round-robin convergence step, a `system-architect` Round-3 robustness review, and a bounded multi-pass outer loop — modeled on `editability-completeness`.
- [ ] 1.3 Define the element wiring-classification rubric: `endpoint-backed` (drives an API call), `client-only` (pure client behavior — navigation / state / overlay), `confirmed-stub` (intentionally inert, user-confirmed), `ambiguous` (escalate to the human).
- [ ] 1.4 Define the element→endpoint trace and the test-authenticity audit — every non-stub interactive element must have a genuine user-driven Playwright test (real `page.click` / `page.fill` etc.), not a direct API call and not a vacuous navigate-and-assert.
- [ ] 1.5 Define the scope as covering every interactive element AND every page / screen / route, and define the converged interaction-map artifact schema plus the rule that every gap becomes a solution requirement.

## 2. REQ-002: interaction-reviewer agent

- [ ] 2.1 Create `agents/interaction-reviewer.md` with the five required frontmatter keys; `model: opus`; an analysis-only tool set (no `Edit`; no `Write` of feature code).
- [ ] 2.2 Author the agent body: independent enumeration of interactive elements AND pages, element wiring classification, page `live`/`placeholder`/`confirmed-stub` classification, element→endpoint trace, Playwright test-authenticity audit, hardcoded-dynamic-value detection, round-robin convergence, and writing the converged map + solution requirements.

## 3. REQ-003: confirmed-stub mechanism

- [ ] 3.1 In `skills/interaction-completeness/SKILL.md`, define `confirmed-stub` — an intentionally-inert element OR an intentional placeholder page — as REQUIRING explicit user confirmation, with the structured escalation question a reviewer raises instead of guessing.
- [ ] 3.2 Define the durable record: a confirmed stub is recorded in the converged interaction map AND a `confirmed_stubs[]` list in the active change's `coverage-map.json`.
- [ ] 3.3 Define that an inert control with no confirmation is an `unwired-control` gap and an unconfirmed placeholder page is a `placeholder-page` gap — both routed as solution requirements, never a silent pass.

## 4. REQ-004: ui_interaction_review evidence field (schema v5 to v6)

- [ ] 4.1 Edit `hooks/review_evidence_schema.py`: bump `SCHEMA_VERSION` to 6; add `ui_interaction_review` to `REQUIRED_EVIDENCE_FIELDS`; add a `VALID_UI_INTERACTION_VALUES` set (`pass` / `n/a` / `fail`).
- [ ] 4.2 Extend `validate_evidence()`: `ui_interaction_review` must be one of the valid values; `fail` returns a gap (escalate via SR, do not mark complete); `n/a` requires a non-empty `ui_interaction_review_note`.
- [ ] 4.3 Confirm both `hooks/review-gate-task.py` and `hooks/teammate-idle-check.py` enforce the new field purely via the shared `review_evidence_schema` import (no drifted per-hook copy).

## 5. REQ-005: strengthen the test-completeness-verifier Playwright audit

- [ ] 5.1 Edit `agents/test-completeness-verifier.md`: add vacuous-flow-test detection — flag a Playwright test that contains `page.goto` + assertions but no genuine user-interaction calls (`page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles`).
- [ ] 5.2 Add the interactivity-inventory cross-check — flag any inventory element with no covering evidence-listed Playwright test.
- [ ] 5.3 Update the verifier's verdict-JSON schema in the agent doc to record the vacuous-flow and uncovered-element findings.

## 6. REQ-006: pipeline and discipline wiring

- [ ] 6.1 Edit `skills/architect-team-pipeline/SKILL.md`: Phase 3 review gate names `ui_interaction_review`; Phase 5 invokes the `interaction-completeness` team for any in-scope frontend slice.
- [ ] 6.2 Edit `skills/playwright-user-flows/SKILL.md`: reference the `ui_interaction_review` field, the confirmed-stub mechanism, placeholder-page detection, and the `interaction-completeness` verification team.
- [ ] 6.3 Edit `skills/team-spawning-and-review-gates/SKILL.md`: document the v6 evidence schema and `ui_interaction_review` (`pass`/`n/a`/`fail` semantics + the `n/a` note rule).
- [ ] 6.4 Edit `agents/frontend.md` and `agents/integration.md`: instruct each to set `ui_interaction_review` in its review-gate evidence and to honor the confirmed-stub mechanism and the no-unconfirmed-placeholder-pages rule.

## 7. REQ-007: test coverage

- [ ] 7.1 Create `tests/test_interaction_completeness.py` — assert the skill + agent exist and are well-formed, the skill mandates the 3-reviewer/converge/Round-3/multi-pass structure, defines the element AND page classification rubrics, and the pipeline skill wires the team into Phase 3 + Phase 5.
- [ ] 7.2 Create `tests/test_ui_interaction_review.py` — assert `validate_evidence()` requires `ui_interaction_review`, accepts `pass`/`n/a`/`fail`, blocks `fail`, requires the note on `n/a`; `SCHEMA_VERSION == 6`.
- [ ] 7.3 Create `tests/test_dynamic_value_discovery.py` — assert the `dynamic-value-discovery` skill exists, is well-formed, defines the context-classification rubric, and is referenced by the developer / architect / evaluator agents and skills.
- [ ] 7.4 Update `tests/test_skills.py` `EXPECTED_SKILLS` (+`interaction-completeness`, +`dynamic-value-discovery`) and `tests/test_agents.py` `EXPECTED_AGENTS` (+`interaction-reviewer`).
- [ ] 7.5 Update the evidence-schema helpers/fixtures in `tests/test_review_gate_task.py` and `tests/test_teammate_idle_check.py` in lockstep for the v6 field.
- [ ] 7.6 Confirm `tests/test_cross_consistency.py` passes — the two evidence hooks still share one schema module; no unregistered skill/agent.
- [ ] 7.7 Run `python -m pytest -v` from the repo root — all pass, no regression against the pre-existing 496.

## 8. REQ-008: documentation and release v0.9.19

- [ ] 8.1 Add a README section documenting the `interaction-completeness` gate, the `ui_interaction_review` field, the confirmed-stub mechanism, placeholder-page detection, and dynamic-value discovery.
- [ ] 8.2 Prepend a `## [0.9.19]` entry to `CHANGELOG.md` referencing the `ui-interaction-fidelity` requirements REQ-001..011.
- [ ] 8.3 Update `docs/CODEBASE_MAP.md` — 20 skills, 17 agents, evidence schema v6; document `skills/interaction-completeness/`, `skills/dynamic-value-discovery/`, and `agents/interaction-reviewer.md` in §3/§4; bump `last_mapped`.
- [ ] 8.4 Update `docs/INTEGRATION_MAP.md` — note the evidence schema is v6; bump `last_synthesized`.
- [ ] 8.5 Update `CLAUDE.md` — skill/agent counts and the evidence-schema version.
- [ ] 8.6 Bump `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` `version` to `0.9.19`.
- [ ] 8.7 Run the full suite `python -m pytest -v` one final time — confirm all pass with no regression.

## 9. REQ-009: placeholder-vs-live-page detection

- [ ] 9.1 In `skills/interaction-completeness/SKILL.md`, define page / screen / route enumeration and the `live` / `placeholder` / `confirmed-stub` page-classification rubric.
- [ ] 9.2 Define the placeholder-signal rubric — component / file naming (`Placeholder`, `ComingSoon`, `Stub`, `Mock`, `Demo`, `WIP`), "coming soon" / "under construction" / lorem-ipsum content, a data-driven page that makes no API calls, a near-empty route shell, a route-table entry pointing at a placeholder while the real component is specified-but-unwired.
- [ ] 9.3 Define the cross-check of every page against the design / requirements / `ROUTE_MAP.md`, and the `placeholder-page` gap kind for an unconfirmed placeholder.
- [ ] 9.4 In `agents/interaction-reviewer.md`, add page enumeration + placeholder classification + the design/ROUTE_MAP cross-check to the reviewer's job.

## 10. REQ-010: dynamic-value-discovery skill

- [ ] 10.1 Create `skills/dynamic-value-discovery/SKILL.md` with valid frontmatter (`name: dynamic-value-discovery`, a quoted `description`).
- [ ] 10.2 Define the static-vs-dynamic classification discipline — every displayed value is classified FROM CONTEXT (position, the value's nature, the requirements / design language), never from the literal itself; the same literal can be static in one place and dynamic in another.
- [ ] 10.3 Define the dynamic-signal rubric (person names, dates / timestamps, currency, counts, statuses, IDs, a value in a record-detail view or a repeating list row, a greeting with a name) and the static-signal rubric (nav labels, button text, section headings, fixed helper text, brand strings).
- [ ] 10.4 Define the rule that every value classified `dynamic` is bound to a named data source — never the design's hardcoded sample literal — and the escalate-to-the-human rule for genuinely ambiguous values.

## 11. REQ-011: dynamic-value discovery wired into developer, architect, and evaluator

- [ ] 11.1 Edit `agents/frontend.md` and `agents/backend.md` (developer): apply `dynamic-value-discovery` — bind every dynamic value to its data source; never hardcode design sample data.
- [ ] 11.2 Edit `agents/system-architect.md` (architect): consult `dynamic-value-discovery` when reviewing specs and designs.
- [ ] 11.3 Edit `skills/design-fidelity-mapping/SKILL.md` (architect): the DESIGN_MAP's per-screen visual specs classify each value `static` or `dynamic` and name the data source for each dynamic value.
- [ ] 11.4 Edit `agents/interaction-reviewer.md` and `skills/interaction-completeness/SKILL.md` (evaluator): the `interaction-reviewer` applies `dynamic-value-discovery` and reports a hardcoded value the context shows should be dynamic as a `hardcoded-dynamic-value` gap routed as a solution requirement.

## 12. Archive

- [ ] 12.1 After every requirement is verified, run `openspec archive ui-interaction-fidelity` to merge the spec deltas into `openspec/specs/`.
