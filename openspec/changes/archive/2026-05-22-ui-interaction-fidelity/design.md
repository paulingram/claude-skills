## Context

The `architect-team` plugin (v0.9.18) drives a spec-to-production pipeline. For frontend work it relies on the `playwright-user-flows` skill, which is one of the most detailed skills in the plugin — it mandates a four-discipline workflow (know the user, enumerate interactive elements exhaustively, test as the user with `page.click`/`fill`/`waitFor`, test against the real backend) and an extensive anti-pattern table that explicitly forbids `page.request.*`, `page.evaluate(()=>fetch())`, and `axios` calls as substitutes for user-click paths.

Despite that, the user reports a recurring failure: Playwright tests "pass" without genuinely driving the UI — they call the API directly. A careful walk of the existing process shows **the discipline is written but under-enforced**:

1. **`playwright-user-flows` is trust-based Markdown.** Nothing structurally checks that an agent followed it. The CODEBASE_MAP itself records the inherent limit: "every phase discipline is trust-based Markdown."
2. **The one hook-enforced gate field, `integration_testing_review`, checks the wrong axis.** It verifies *real-backend-vs-mock*. A test can hit the **real** backend via `page.request.post('/api/...')` — fully satisfying `integration_testing_review: "pass"` — while never issuing a single `page.click`. Real-backend and real-user-interaction are two different axes; only the first is gated.
3. **The `test-completeness-verifier`'s Playwright audit is a grep.** It searches the *evidence-listed* test files for `page.request.*` / `axios` / `page.evaluate(fetch)`. A grep finds *present* forbidden patterns. It cannot find: (a) an interactive element that was never tested at all; (b) a "user-flow test" that navigates and asserts static content with zero `page.click` (no forbidden pattern, no real interaction either); (c) a direct-API test in a file the evidence simply did not list; (d) whether each element is correctly wired to its endpoint.
4. **There is no first-class "confirmed stub" concept.** When an element is intentionally inert (a placeholder button), the test author either tests it (and it fails) or skips it (silently, violating coverage). A genuine coverage gap and an accepted stub are indistinguishable.
5. **Placeholder pages ship undetected.** A route can be wired to a placeholder / "coming soon" / skeleton / mock page instead of the real page it should reach, and nothing in the pipeline flags it. The user reported exactly this: a run shipped pages wired to placeholders rather than the live pages they should have been. The `frontend` agent's "no placeholder data" rule, like the rest of the discipline, is unenforced Markdown — and a Playwright test can click happily through a placeholder page and pass.
6. **Hardcoded values ship where a dynamic, data-bound value belongs.** A design mockup is full of sample data — a name, a date, a dollar amount. A literal implementation hardcodes `"John Smith"` where the context makes clear it is the logged-in user's name (a dynamic, data-bound field). Nothing in the pipeline — not the architect authoring the spec, not the developer implementing it, not the evaluator reviewing it — systematically asks "is this a fixed label, or sample data standing in for a dynamic field?" The UI then shows one person's sample data to everyone.

The `editability-completeness` skill already solved a structurally identical problem at a different granularity: "the existing gates do not catch this ... this skill closes the gap at the level it actually occurs — the individual attribute." It runs three independent reviewer agents that argue to convergence, a `system-architect` Round-3 robustness review, and a bounded multi-pass loop, routing gaps as solution requirements. The same shape fits interactive-element-and-test-authenticity verification exactly.

## Goals / Non-Goals

**Goals:**

- Make "every interactive element is genuinely user-flow-tested or a confirmed stub" a structural, hook-enforced gate — not trust-based Markdown.
- Independently (re-)enumerate interactive elements, rather than trusting the test author's self-reported inventory.
- Verify the *authenticity* of each Playwright test — that it drives the UI with real user interaction, not a direct API call and not a vacuous navigate-and-assert.
- Review how each interactive element is wired to an endpoint (or to a client-only behavior).
- Detect placeholder pages — a route wired to a stub / "coming soon" / skeleton / mock page instead of the real live page — and flag every one unless the user has explicitly confirmed it.
- Distinguish genuine static literals from sample data standing in for dynamic, data-bound values — so a per-user / per-record / per-state value is never shipped hardcoded — and apply that discipline at planning (architect), implementation (developer), and review (evaluator).
- Give intentional stubs (an inert control OR a placeholder page) a first-class, user-confirmed status so a gap and an accepted stub are never conflated.
- Keep the existing `playwright-user-flows` authoring discipline intact — strengthen the *verification* around it, do not rewrite it.

**Non-Goals:**

- Not rewriting `playwright-user-flows`. It remains the test-authoring discipline; the new skill is the independent *verification* gate (the same division of labor as `playwright-user-flows` vs `editability-completeness`).
- Not building a Playwright test runner or a browser harness inside the plugin. The plugin verifies a target project's tests; it does not execute them itself.
- Not changing what `integration_testing_review` means. Real-backend-vs-mock stays its axis; the new `ui_interaction_review` field is the separate real-interaction axis.
- Not adding a new third-party dependency or a new harness hook.

## Decisions

### D1 — A new `interaction-completeness` skill, not an extension of `test-completeness-verifier`

The user's ask — "intuit the actual steps a user would take, test all steps and variants, confirm the experience is active as if they were a front-end user" — is a judgment-heavy task. `editability-completeness` states the principle directly: judgment-heavy verification "runs as a three-agent team that argues to convergence ... two cannot triangulate a judgment call; the third is the tie-break and the falsifier." `test-completeness-verifier` is a single mechanical sonnet agent whose Playwright check is a `grep`. Loading independent re-enumeration, wiring classification, and "is this a genuine user flow" judgment into a mechanical grep agent would both overload it and lose the independent-convergence rigor. So the verification discipline is a NEW skill that REUSES the `editability-completeness` structure wholesale.

*Alternatives considered:* fold everything into `test-completeness-verifier` (rejected — wrong kind of agent for judgment work; loses convergence rigor); a single new verifier agent with no convergence (rejected — `editability-completeness` already established that a single reviewer rationalizes past classification errors a three-way argument catches).

### D2 — A new `interaction-reviewer` agent, spawned ×3

Mirrors `editability-reviewer`: opus, analysis-only (Read/Glob/Grep/LS/Bash/TodoWrite — no `Edit`/`Write` of feature code), spawned three times in parallel for independent enumeration, then round-robin convergence. Each reviewer enumerates every interactive element from the actual source, classifies its wiring, traces element→endpoint, and audits whether each element's Playwright test genuinely drives the UI. The `system-architect` performs the Round-3 robustness review (shared-blind-spot check) before the converged map is final — identical to the editability and diagnostic-research patterns.

### D3 — A new hook-enforced field `ui_interaction_review` (evidence schema v5 → v6)

The evidence schema has been bumped before to add exactly this kind of gate: `visual_fidelity_review` (v0.5.0), `test_completeness_review` (v0.9.0), `integration_testing_review` (v0.9.5). Adding `ui_interaction_review` follows that established path. It is a separate field — not folded into `integration_testing_review` — because it gates a genuinely orthogonal axis (a test can be real-backend + fake-interaction, or mock-backend + real-interaction). Values: `pass` (every interactive element in the slice is genuinely UI-tested or a confirmed stub), `n/a` (the slice has no UI/frontend interactive surface — requires a `ui_interaction_review_note`), `fail` (blocked by the hook — drift routes through an SR). The field is defined once in the shared `hooks/review_evidence_schema.py`; both evidence hooks import that module, so the bump flows through without per-hook drift (the v0.9.9 single-source-of-truth design).

### D4 — The confirmed-stub mechanism

An interactive element is `confirmed-stub` ONLY with explicit user confirmation. When an `interaction-reviewer` finds an element that is intentionally inert (no endpoint, no client behavior, a placeholder), it does NOT guess — it escalates a structured question to the human via the orchestrator (the same escalation channel `editability-completeness` uses for `ambiguous` attributes). Once the user confirms "yes, that is an intentional stub," the element is recorded as `confirmed-stub` in the converged interaction map AND in a `confirmed_stubs[]` list in the change's `coverage-map.json`, so it is durable and visible. A confirmed stub does not require a user-flow test (testing an intentionally-inert control is meaningless), but it IS tracked — the gate can report "3 confirmed stubs" rather than silently ignoring them. An inert element with NO confirmation is a gap (`unwired-control`), routed as a solution requirement.

### D5 — Strengthen `test-completeness-verifier` for the mechanical half

The judgment-heavy work is the new team's; the cheap mechanical wins stay with the verifier and are strengthened: (a) flag a Playwright test that claims to be a user-flow test but contains no / near-zero genuine interaction calls (`page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles`) — a navigate-and-assert masquerading as a flow; (b) cross-check the evidence-listed Playwright test IDs against the interactivity inventory so an element with no covering test is flagged mechanically before the judgment team even runs. The verifier and the interaction-completeness team are complementary — exactly as `test-completeness-verifier` and `editability-completeness` are today.

### D6 — Division of labor with the existing skills

- `playwright-user-flows` — the test-AUTHORING discipline. Unchanged in substance; gains references to the new field, the stub mechanism, and the verification team.
- `interaction-completeness` (new) — the independent VERIFICATION gate that the authoring discipline was followed. Same relationship `editability-completeness` has to `playwright-user-flows` today.
- `test-completeness-verifier` — the mechanical pre-screen (kinds present, forbidden-pattern grep, now also vacuous-flow + inventory cross-check).
- `visual-fidelity-reconciliation` / `visual-verification-team` — verify the UI *looks* right. `interaction-completeness` verifies the UI *behaves* right — every control genuinely works and is genuinely tested, and every page is the real live page, not a placeholder. Complementary, non-overlapping.
- `editability-completeness` — verifies every entity attribute a user should control is editable end-to-end. `interaction-completeness` is the sibling discipline for interactive elements and pages; the two run side by side at Phase 5 and do not overlap (attributes vs. controls/pages).

### D7 — Placeholder-page detection is part of the same verification

The `interaction-reviewer` enumerates not just interactive elements but every page / screen / route in the slice, and classifies each `live`, `placeholder`, or `confirmed-stub`. A `placeholder` — a route wired to a stub, "coming soon", skeleton, or mock where the design or requirements specify a real live page — is a gap, routed as a solution requirement, UNLESS the user has explicitly confirmed it is an intentional placeholder for this release (the D4 confirmed-stub mechanism, extended from elements to pages). The skill carries a placeholder-signal rubric — component / file naming (`Placeholder`, `ComingSoon`, `Stub`, `Mock`, `Demo`, `WIP`), "coming soon" / "under construction" / lorem-ipsum content, a data-driven page that makes no API calls, a near-empty route shell, a route-table entry pointing at a placeholder while the real component is specified-but-unwired — and cross-checks every page against the design / requirements / `ROUTE_MAP.md`. This is judgment-heavy (a skeleton can be a legitimate loading state; a sparse page can be genuinely minimal), which is exactly why the three-reviewer convergence and the escalate-don't-guess rule apply. Placeholder detection reuses the same skill, agent, reviewer team, confirmed-stub mechanism, and `ui_interaction_review` gate field — it adds a page-level dimension, not a new component.

### D8 — Dynamic-value discovery is a cross-role discipline, wired into developer, architect, and evaluator

A hardcoded value that should be dynamic cannot be caught by a single gate — it has to be *prevented* at planning, *avoided* at implementation, and *caught* at review. So this is delivered as a discipline **skill** (`dynamic-value-discovery`), not a check buried in one agent — the same shape as `reuse-first-design`, which the architect and the implementers all consult. The skill defines how to classify a displayed value `static` vs. `dynamic` FROM CONTEXT — a person name beside an avatar, a value in a record-detail view, anything in a repeating list row, a greeting with a name, a currency amount, a date, a status, a count are dynamic; nav labels, button text, section headings, fixed helper text, brand strings are static — the rule being that the value alone never decides, the context does. It mandates that every dynamic value is bound to a named data source, and it requires escalation to the human when a classification is genuinely ambiguous.

It is wired into the three roles the user named:

- **Architect** — `system-architect` and the `design-fidelity-mapping` skill consult it: the DESIGN_MAP's per-screen specs classify each value `static` or `dynamic` and name the data source for each dynamic value; the Phase 1 spec's acceptance criteria then require the binding.
- **Developer** — `frontend` and `backend` consult it: bind every dynamic value to its data source; never hardcode design sample data.
- **Evaluator** — the new `interaction-reviewer`, guided by this skill, flags a hardcoded value the context shows should be dynamic as a `hardcoded-dynamic-value` gap, routed (like `unwired-control` and `placeholder-page`) through the `ui_interaction_review` field and a solution requirement.

No new agent — the `interaction-reviewer` is the evaluator, and the existing developer/architect agents gain a skill reference.

## Reuse Decisions

Per `reuse-first-design` (extend > compose > reuse > build-new), anchored in `docs/CODEBASE_MAP.md` and `docs/INTEGRATION_MAP.md`:

| Element | Decision | Rationale | Map anchor |
|---|---|---|---|
| Independent interaction-verification capability | build-new (skill `interaction-completeness`) | No existing component verifies interactive-element coverage + test authenticity. `test-completeness-verifier` is mechanical grep (wrong kind); `editability-completeness` is attribute-granularity (wrong granularity). Genuinely new capability. | CODEBASE_MAP §4 Skills; the gap is documented in `editability-completeness` ("the existing gates do not catch this") |
| The verification skill's STRUCTURE | reuse (pattern) | The 3-reviewer parallel → round-robin converge → `system-architect` Round-3 → bounded multi-pass → gaps-as-SRs structure is reused verbatim from `editability-completeness`. No new pattern invented. | CODEBASE_MAP §4 (`editability-completeness`, `editability-reviewer`) |
| `interaction-reviewer` agent | build-new | A judgment-heavy 3-reviewer team needs its own agent; mirrors `editability-reviewer` (opus, analysis-only, ×3). | CODEBASE_MAP §4 Agents (`editability-reviewer`) |
| `dynamic-value-discovery` skill | build-new | A cross-role discipline distinguishing static literals from sample-data-for-dynamic-values; no existing skill does this. Modeled on `reuse-first-design` as a principle-skill every role consults; wired into existing developer / architect / evaluator agents — no new agent. | CODEBASE_MAP §4 Skills (`reuse-first-design` — the cross-role discipline-skill precedent) |
| `ui_interaction_review` evidence field | extend | Added to the existing shared `hooks/review_evidence_schema.py` — the exact path `visual_fidelity_review`/`test_completeness_review`/`integration_testing_review` took. No new file; both hooks import the shared module. | CODEBASE_MAP §4 Hooks + §6 (evidence schema v5) |
| Verifier strengthening | extend | `agents/test-completeness-verifier.md` gains two checks; no new agent. | CODEBASE_MAP §4 Agents (`test-completeness-verifier`) |
| Pipeline + discipline wiring | extend | Notifier-style edits into existing `architect-team-pipeline`, `playwright-user-flows`, `team-spawning-and-review-gates` SKILLs and `frontend`/`integration` agents. | CODEBASE_MAP §4 Skills + Agents |
| Tests | extend | New `tests/test_interaction_completeness.py` + `tests/test_ui_interaction_review.py` follow the existing one-test-file-per-discipline convention; existing test files get the new skill/agent registered + v6 helper updates. | CODEBASE_MAP §8 navigation guide |

## Risks / Trade-offs

- **Schema v5 → v6 is a cross-cutting change** → Mitigation: the schema is the single source of truth in `hooks/review_evidence_schema.py`; both hooks import it; `tests/test_cross_consistency.py` already guards against the two hooks drifting. The bump is mechanical and well-precedented (three prior fields added the same way). Every existing evidence file in a *completed* run is historical; the new required field affects only evidence written *after* v0.9.19 is installed.
- **The new gate adds another Phase 5 review** → Mitigation: it runs only for slices with UI/UX surface; non-frontend slices set `ui_interaction_review: "n/a"` with a note (the same cheap path `visual_fidelity_review` already uses for backend slices). Phase 5's re-run-convergence rule already accounts for interdependent reviews.
- **Trust-based wiring of the new team into the pipeline** → Mitigation: same inherent limit as every phase discipline; `tests/test_interaction_completeness.py` asserts the pipeline skill references the new team and the v6 field. Structural tests prove presence, not execution — accepted, consistent with the plugin's architecture.
- **The plugin is verifying itself** → This change modifies the plugin's own enforcement. The running pipeline uses the installed (cached) plugin version, so editing the working repo's skills/hooks does not change in-flight behavior; the new gate goes live only after the plugin updates to v0.9.19.
- **Over-strict gate could block legitimate work** → Mitigation: the confirmed-stub mechanism is the pressure valve — anything intentionally inert is explicitly accepted via user confirmation, never force-tested.

## Migration Plan

Additive. Ships in v0.9.19. After the plugin updates, the next pipeline run with frontend surface runs the interaction-completeness team at Phase 5 and gates on `ui_interaction_review`. No migration of existing target projects. The evidence schema bump is backward-tolerant for *reading* historical evidence (completed runs are not re-validated); only evidence written under v0.9.19+ carries the new required field. Rollback is a plugin downgrade.

## Test Strategy

- **Structural (pytest)** — `tests/test_interaction_completeness.py`: the `interaction-completeness` skill exists with valid frontmatter and is registered; the `interaction-reviewer` agent exists with the 5 required frontmatter keys, a valid tool set, and `model: opus`; the skill mandates 3 reviewers + convergence + the `system-architect` Round-3 + multi-pass; the pipeline skill wires the team into Phase 3 + Phase 5. `tests/test_ui_interaction_review.py`: `validate_evidence()` requires `ui_interaction_review`, accepts `pass`/`n/a`/`fail`, blocks `fail`, requires `ui_interaction_review_note` on `n/a`; both hooks enforce it.
- **Evidence-schema regression** — `tests/test_review_gate_task.py` + `tests/test_teammate_idle_check.py` helpers updated in lockstep for v6; `tests/test_cross_consistency.py` confirms the two hooks still share one schema module.
- **Registry consistency** — `tests/test_skills.py` `EXPECTED_SKILLS` gains `interaction-completeness`; `tests/test_agents.py` `EXPECTED_AGENTS` gains `interaction-reviewer`; `test_cross_consistency.py`'s no-unregistered-skill/agent checks pass.
- **No Playwright / no dev-API tests for this codebase** — the `architect-team` plugin has zero frontend and zero HTTP API surface. The change itself is Markdown + the Python schema module; its test discipline is pytest structural, matching the archived `python3-portability` and `project-email-notifications` changes. (The change is *about* Playwright discipline in target projects — but this plugin is verified structurally.)
- **Full suite** — `python -m pytest -v` must pass with all new tests and no regression in the pre-existing 496.

## Open Questions

None blocking. The run mode (proposal-first, with a user-review pause after Phase 1) is itself the checkpoint for any scoping adjustment — the user reviews this proposal/design/specs/tasks package and may narrow scope (e.g., defer the schema v6 field, or the verifier strengthening) before Phase 2 implementation begins.
