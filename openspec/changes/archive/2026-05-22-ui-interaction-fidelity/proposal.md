## Why

The `architect-team` pipeline keeps shipping frontend work that is not what it claims to be — and the verification does not catch it. Three failure modes, one root cause:

1. **Playwright "user-flow" tests pass without driving the UI.** The `playwright-user-flows` skill exhaustively mandates real-user simulation — "Direct API calls are never a substitute for user-flow tests" — but the discipline is trust-based Markdown, and the one hook-enforced gate field (`integration_testing_review`) verifies *real-backend-vs-mock*, NOT *real-UI-interaction-vs-direct-API-call*. A test that hits the real backend via `page.request.post('/api/...')` — or that merely navigates and asserts static content while calling itself a "flow" — passes every gate today.
2. **Placeholder pages ship in place of the live pages they should be.** A route can be wired to a placeholder / "coming soon" / skeleton / mock page instead of the real page, and nothing flags it — the user reported exactly this: a run shipped pages wired to placeholders rather than the live pages they should have been. A Playwright test clicks happily through a placeholder and passes.
3. **Hardcoded values ship where a dynamic, data-bound value belongs.** A design mockup is full of sample data — a name, a date, a dollar amount. A literal implementation hardcodes `"John Smith"` where the context makes clear it is the logged-in user's name. The architect authoring the spec, the developer implementing it, and the evaluator reviewing it never systematically ask "is this a fixed label, or sample data standing in for a dynamic field?" — so the UI ships showing one person's sample data to everyone.

The root cause is the same: the discipline is written (`playwright-user-flows`, the `frontend` agent's "no placeholder data" rule) but **under-enforced**, and the pipeline has no shared, deliberate practice for telling a genuine static literal from sample-data-for-a-dynamic-value. The `test-completeness-verifier` greps the evidence-listed Playwright files for some forbidden patterns, but a grep finds *present* bad patterns — not a button that was never genuinely tested, a vacuous "flow" test, a route wired to a placeholder, or a hardcoded value that should be dynamic. And nothing distinguishes a real coverage gap from an intentional, accepted stub.

## What Changes

- **Add** the `interaction-completeness` skill — a judgment-heavy verification discipline modeled on the proven `editability-completeness` skill. For any slice with UI/UX surface it independently (re-)enumerates every interactive element **and every page / screen / route**, classifies each element by how it is wired and each page as `live` / `placeholder` / `confirmed-stub`, verifies every non-stub element has a genuine user-driven Playwright test that exercises the real UI path, and traces each element to the endpoint (or client behavior) it drives. It runs as a three-reviewer parallel-then-converge loop with a `system-architect` Round-3 robustness review and a bounded multi-pass outer loop. (REQ-001)
- **Add** the `interaction-reviewer` agent — spawned ×3 in parallel, independent; enumerates interactive elements and pages, classifies element wiring and page genuineness, traces element→endpoint, audits Playwright test authenticity, detects placeholder pages and hardcoded-should-be-dynamic values; converges with the other two; gaps become solution requirements. Analysis-only. Mirrors `editability-reviewer`. (REQ-002)
- **Add** a first-class **confirmed-stub mechanism** — an interactive element OR a page that is intentionally inert / a placeholder MUST be classified `confirmed-stub`, which REQUIRES explicit user confirmation: the reviewer escalates a structured question, the user confirms, and the confirmed stub is recorded. An unconfirmed inert control or unconfirmed placeholder page is a gap, never a silent pass. (REQ-003)
- **Add** the `ui_interaction_review` review-gate evidence field (evidence schema v5 → v6) — hook-enforced (`pass` / `n/a` / `fail`), so "every interactive element is genuinely UI-tested, every page is live, and every displayed value is correctly static or dynamically bound — or a confirmed stub" becomes a structural gate, exactly as `visual_fidelity_review` made visual drift structural. (REQ-004)
- **Modify** the `test-completeness-verifier` agent — its Playwright audit additionally flags a "user-flow test" with no / near-zero genuine user interaction (a navigate-and-assert masquerading as a flow), and cross-checks the evidence-listed Playwright tests against the interactivity inventory. (REQ-005)
- **Modify** the pipeline + discipline wiring — `architect-team-pipeline` SKILL.md (Phase 3 + Phase 5 invoke the interaction-completeness team); `playwright-user-flows`, `frontend`, `integration`, and `team-spawning-and-review-gates` reference the v6 field, the new skill, and the stub mechanism. (REQ-006)
- **Add** pytest structural coverage — the new skills + agent register correctly, the v6 schema validates, both hooks enforce the new field, the strengthened verifier behaves as documented. (REQ-007)
- **Document & release** as v0.9.19 — README, CHANGELOG, CODEBASE_MAP (20 skills, 17 agents, evidence schema v6), INTEGRATION_MAP, CLAUDE.md, version bump. (REQ-008)
- **Add** placeholder-page detection (REQ-009) — the `interaction-completeness` verification enumerates every page / screen / route and classifies each `live`, `placeholder`, or `confirmed-stub`. A route wired to a stub / "coming soon" / skeleton / mock page where the design or requirements specify a real live page is reported as a gap (`placeholder-page`) and routed as a solution requirement. The skill carries a placeholder-signal rubric and cross-checks every page against the design / requirements / `ROUTE_MAP.md`. (REQ-009)
- **Add** the `dynamic-value-discovery` skill (REQ-010) — a cross-role discipline for telling a genuine static literal from sample data standing in for a dynamic, data-bound value. It defines how to classify a displayed value `static` vs. `dynamic` FROM CONTEXT (a name beside an avatar is the user's name; a nav label is fixed — the value alone never decides), mandates that every dynamic value is bound to a named data source, and requires escalation when a value's classification is genuinely ambiguous. (REQ-010)
- **Wire** dynamic-value discovery into the developer, architect, and evaluator (REQ-011) — the `frontend` / `backend` agents (bind dynamic values, never hardcode design sample data); the `system-architect` agent and the `design-fidelity-mapping` skill (the DESIGN_MAP classifies each value `static`/`dynamic` and names its data source; spec acceptance criteria require the bindings); and the `interaction-reviewer` agent / `interaction-completeness` skill (flag a hardcoded value the context shows should be dynamic as a `hardcoded-dynamic-value` gap). (REQ-011)

No breaking change to a target project. The new gate applies to slices with UI/UX surface; `n/a` (with a note) covers slices with no frontend.

## Capabilities

### New Capabilities

- `ui-interaction-fidelity`: an enforcement layer guaranteeing that when UI/UX ships, the shipped UI is *genuine* — every interactive element is independently verified to be real-user-flow-tested (real clicks, real UI path, not a direct API call and not a vacuous navigate-and-assert) and correctly wired, every page is the real live page rather than a placeholder, and every displayed value is correctly a static literal or a dynamic data-binding rather than hardcoded sample data — or an explicit, user-confirmed stub. Delivered via a new judgment-heavy reviewer team (`interaction-completeness` skill + `interaction-reviewer` agent), a new cross-role discipline (`dynamic-value-discovery` skill) wired into the developer / architect / evaluator, a new hook-enforced review-gate field (`ui_interaction_review`), and a strengthened mechanical verifier.

### Modified Capabilities

None. No existing spec's requirements change. The change strengthens enforcement around the existing `playwright-user-flows` discipline and complements the existing `editability-completeness` skill, but does not alter any requirement of the `pipeline-polish-v023`, `python3-portability`, or `project-email-notifications` capabilities.

## Impact

**Affected files:**

- `skills/interaction-completeness/SKILL.md` — NEW. The verification discipline — interactive-element wiring + test authenticity + placeholder-page detection.
- `skills/dynamic-value-discovery/SKILL.md` — NEW. The cross-role static-vs-dynamic-value discipline.
- `agents/interaction-reviewer.md` — NEW. The ×3 independent reviewer agent (elements + pages + hardcoded-value detection).
- `hooks/review_evidence_schema.py` — MODIFIED. Schema v5 → v6: add `ui_interaction_review` to `REQUIRED_EVIDENCE_FIELDS`, add its `VALID_*` value set, extend `validate_evidence()`.
- `agents/test-completeness-verifier.md` — MODIFIED. Vacuous-flow-test detection + interactivity-inventory cross-check.
- `agents/frontend.md`, `agents/backend.md`, `agents/integration.md` — MODIFIED. Emit `ui_interaction_review`; honor the confirmed-stub mechanism; bind dynamic values per `dynamic-value-discovery`.
- `agents/system-architect.md` — MODIFIED. Consult `dynamic-value-discovery` when reviewing specs/designs.
- `skills/architect-team-pipeline/SKILL.md` — MODIFIED. Phase 3 + Phase 5 invoke the interaction-completeness team.
- `skills/playwright-user-flows/SKILL.md` — MODIFIED. Reference the v6 field, the confirmed-stub mechanism, placeholder-page detection, and the new verification team.
- `skills/team-spawning-and-review-gates/SKILL.md` — MODIFIED. Document the v6 evidence schema + the new field.
- `skills/design-fidelity-mapping/SKILL.md` — MODIFIED. The DESIGN_MAP classifies each per-screen value `static` / `dynamic` and names the data source.
- `tests/test_interaction_completeness.py`, `tests/test_ui_interaction_review.py`, `tests/test_dynamic_value_discovery.py` — NEW. Structural coverage.
- `tests/test_skills.py`, `tests/test_agents.py`, `tests/test_review_gate_task.py`, `tests/test_teammate_idle_check.py`, `tests/test_cross_consistency.py` — MODIFIED. Register the new skills/agent; update evidence-schema helpers for v6.
- `README.md`, `CHANGELOG.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `CLAUDE.md` — MODIFIED. Documentation.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — MODIFIED. Version `0.9.19`.

**Affected APIs / dependencies:** none — no new third-party dependency. The change is Markdown skills/agents + the Python evidence-schema module + pytest self-tests.

**Affected systems:** future pipeline runs (after the plugin updates to v0.9.19) gate UI/UX slices on the new `ui_interaction_review` field, run the interaction-completeness team — including placeholder-page detection — at Phase 5, and apply `dynamic-value-discovery` at planning, implementation, and review.

**Reuse-first decision summary:** The discipline `playwright-user-flows` already exists and is exhaustive — it is EXTENDED (referenced), not rewritten. The enforcement gaps are genuinely new: no existing component independently verifies interactive-element coverage, test authenticity, placeholder-vs-live pages, or hardcoded-vs-dynamic values. `test-completeness-verifier` is the wrong *kind* of component (a mechanical sonnet grep) for judgment-heavy work; `editability-completeness` is the right *pattern* but the wrong *granularity*. So `interaction-completeness` + `interaction-reviewer` are a justified build-new that REUSES the `editability-completeness` pattern wholesale. The `dynamic-value-discovery` skill is a justified build-new cross-role discipline modeled on `reuse-first-design` (a principle-skill every role consults) — wired into existing developer / architect / evaluator agents, NO new agent. The v6 field EXTENDS the existing shared `hooks/review_evidence_schema.py` exactly as three prior review fields were added. Every other change extends an existing file. The full Reuse Decision Log is in `design.md`.
