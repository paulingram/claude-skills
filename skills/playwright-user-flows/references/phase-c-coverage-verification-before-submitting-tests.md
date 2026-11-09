# Phase C — Coverage verification (before submitting tests)

Run an automated coverage check across two layers — user-intent first, then mechanics. User-intent gaps are blocking even if every mechanical gap is closed.

**User-intent coverage (highest priority):**
- Every `(persona, goal)` pair in `user-intent/<feature>.json` must have at least one journey in `journeys/<feature>.json`.
- Every journey in `journeys/<feature>.json` must have at least one test in the test source whose name references the journey ID (or persona+goal).
- Every `failure_branches[]` entry inside a journey must have at least one test that triggers the branch and asserts the expected user-visible state.

**Mechanical coverage:**
- Every `id` in `interactivity[]` must appear in the test source (grep by selector or by inventory id used as a test-name suffix) in at least one test.
- Every `id` in `conditional_ui[]` must appear in at least one test.
- Every endpoint in the inventory's `fires_api` set must be exercised by at least one test (real call for happy paths, `page.route` for error paths).
- Every navigation edge must be traversed by at least one test.

**Gap policy:** An interactivity ID with no journey reference is a gap of one of two kinds — either (a) it is genuinely out-of-scope for this test pass (declare it explicitly in `out_of_scope[]` with rationale) or (b) the user-intent map is missing a goal (escalate to the user to confirm). Silent gaps are forbidden.

Write `<test-output-dir>/playwright-coverage.json`:

```json
{
  "feature": "login-flow",
  "coverage": {
    "user_intent": {
      "personas_covered": ["first-time-visitor", "returning-user-with-expired-session"],
      "goals_covered": {
        "first-time-visitor:complete-first-login": ["test_first_time_visitor_completes_first_login"],
        "returning-user-with-expired-session:resume-to-intended-route": ["test_returning_user_resumes_session_to_intended_route"]
      },
      "failure_branches_covered": {
        "first-time-visitor:complete-first-login:401": ["test_user_sees_clear_error_when_password_wrong"],
        "first-time-visitor:complete-first-login:429": ["test_user_sees_rate_limit_message"]
      }
    },
    "interactivity": {
      "email-input": ["test_first_time_visitor_completes_first_login"],
      "submit": ["test_first_time_visitor_completes_first_login", "test_user_sees_clear_error_when_password_wrong", "test_user_sees_rate_limit_message"],
      "forgot-password": ["test_user_recovers_forgotten_password_via_email_link"]
    },
    "conditional_ui": {
      "error-banner": ["test_user_sees_clear_error_when_password_wrong"],
      "loading-spinner": ["test_user_sees_loading_indicator_during_submit"]
    },
    "endpoints_exercised": ["POST /api/auth/login"],
    "navigations_traversed": ["/login → /dashboard", "/login → /forgot-password"]
  },
  "gaps": [],
  "out_of_scope": []
}
```

If `gaps` is non-empty, add tests (or escalate to the user for missing goals) until it is empty. Then this file goes into the review-gate evidence.

**Register the authored flows in the suite manifest.** When the codebase carries `<e2e-dir>/suite-manifest.json`, register the flows this pass authored there per `playwright-suite-builder` — file, test names, persona, kind, and the `covers_elements[]` this coverage check just computed — so the suite's registry of "which tests are written" stays true after this pass ends. Absent a suite manifest, behavior is unchanged.

### Emit the integration_testing_review verdict

When this skill is applied inside the architect-team pipeline, the teammate (or the integration agent) MUST set `integration_testing_review` in the review-gate evidence per `team-spawning-and-review-gates`:

- `"pass"` — the happy-path user-flow tests exercised the real running backend (real server process, real DB / queue / cache, real responses). The demo artifact references the backend start command / `webServer` config that proves a real backend was in the loop.
- `"n/a"` — ONE of: (1) the slice has no cross-layer surface (pure static frontend with no backend, OR backend-only slice with no frontend); (2) Phase 3 per-team gate and the counterpart layer is not yet integrated — note says DEFERRED TO PHASE 5; (3) the requirements explicitly authorize isolated / mock-backed testing for this requirement — note quotes the authorization. Requires `integration_testing_review_note`.
- `"fail"` — a `both`-layer feature whose happy-path tests ran against a mocked / fake backend with no explicit authorization. The hook blocks this; re-author against the real backend or escalate via an SR with `origin.kind: "integration-testing-failure"`.

### Independent interaction verification — the `interaction-completeness` team and the `ui_interaction_review` field

This skill is the test-AUTHORING discipline. It is trust-based Markdown — nothing here structurally proves the author actually followed it. A "user-flow test" can hit the real backend through `page.request.post('/api/...')` and never issue a single `page.click`; a route can be wired to a placeholder page that a navigate-and-assert test clicks happily through; a value can ship hardcoded as the design's sample literal where the context says it is a per-user dynamic value. So a separate, INDEPENDENT verification gate checks that this discipline was genuinely followed — the same division of labor `editability-completeness` has with this skill.

- **The `interaction-completeness` skill** is that independent verification. For any slice with interactive surface it runs a three-`interaction-reviewer` parallel-then-converge team (with a `system-architect` Round-3 robustness review and a bounded multi-pass loop) that re-enumerates every interactive element AND every page from the actual source — not the author's self-reported inventory — classifies each element's wiring and each page as `live` / `placeholder` / `confirmed-stub`, traces each element to its endpoint, and audits whether each element's Playwright test genuinely drives the UI. It runs at Phase 5 alongside the editability-completeness team and the visual-fidelity sweep.
- **Test authenticity is the core audit.** A genuine user-flow test reaches the element with `page.click` / `page.fill` / `page.selectOption` / `page.check` / `page.press` / `page.setInputFiles`. A direct API call (`page.request.*`, `page.evaluate(() => fetch())`) is never a substitute, and a vacuous navigate-and-assert — a `page.goto` plus assertions with zero genuine interaction calls — is a flow test in name only. The interaction-completeness team flags both; this is exactly the gap a forbidden-pattern grep cannot see (a navigate-and-assert contains no forbidden pattern, and a never-tested button contains no test at all).
- **Placeholder-page detection.** The interaction-completeness team also classifies every page / screen / route `live`, `placeholder`, or `confirmed-stub`, cross-checking each against the design / requirements / `ROUTE_MAP.md`. The placeholder signals are both component naming (a component named or filed under `ComingSoon` / `Placeholder` / `Stub` / `Mock` / `Demo` / `WIP` / `Skeleton`) and page content ("coming soon" / "under construction" copy, lorem-ipsum body text, a data-driven page that issues no API call, a near-empty route shell). A route wired to such a placeholder where a real live page is specified is a `placeholder-page` gap — a Playwright test that clicks through a placeholder and passes has verified nothing.
- **The confirmed-stub mechanism.** An interactive element OR a page that is intentionally inert / a placeholder is classified `confirmed-stub` ONLY with explicit user confirmation — the reviewer escalates a structured question, the user confirms, and the confirmed stub is recorded in the converged interaction map and the change's `coverage-map.json` `confirmed_stubs[]`. A `confirmed-stub` does NOT require a user-flow test (testing an intentionally-inert control is meaningless) but is tracked, not silently ignored. An unconfirmed inert control or unconfirmed placeholder page is a gap (`unwired-control` / `placeholder-page`), never a silent pass.
- **The `ui_interaction_review` review-gate evidence field** (added at evidence schema v6; the current schema is v7) surfaces this verification, exactly as `integration_testing_review` surfaces the real-backend axis — and it gates a genuinely orthogonal axis: a test can be real-backend + fake-interaction, or mock-backed + real-interaction. Set it honestly: `"pass"` when every interactive element in the slice is genuinely UI-tested with a real user-interaction call and correctly wired, every page is the real live page, and every displayed value is correctly static or dynamically bound — or a confirmed stub; `"n/a"` (with a required `ui_interaction_review_note`) when the slice has no UI/frontend interactive surface; `"fail"` when an `unwired-control`, a `placeholder-page`, or a `hardcoded-dynamic-value` gap was found — the hook blocks `"fail"`, and the gap routes through a solution requirement, not a mark-complete.

### The frontend-E2E loop-exit verdict artifact — the deliverable of a frontend flow run (v3.55.0)

A frontend-impacting change is not done until a real user clicked through it against a live environment. So the deliverable of running this skill for a frontend slice is not just a green test log — it is a machine-checkable verdict artifact at `<workspace>/.architect-team/frontend-e2e/<slice>-verdict.json`, written when the flow runs against the live dev environment (Phase 5 step 3b of `architect-team-pipeline`). Its shape:

```json
{
  "slice": "<review-evidence filename stem>",
  "verdict": "passed",
  "executed_against_live_env": true,
  "live_url": "http://localhost:5173",
  "user_driven_actions": [{"action": "page.getByRole('button', { name: 'Sign in' }).click", "selector": "getByRole('button')"}],
  "trace_path": "traces/<slice>-trace.zip",
  "visible_state_assertions": ["expect(page.getByText('Welcome')).toBeVisible()", "expect(page).toHaveURL(/dashboard/)"],
  "test_files": ["e2e/login.spec.ts"]
}
```

The `trace_path` is the captured Playwright trace (`trace: 'on'`) and MUST name a file that exists. `user_driven_actions` are the real click/fill/getByRole/check/selectOption calls — never `page.request`/`fetch`. `visible_state_assertions` assert visible end-to-end state (`toBeVisible`/`toHaveText`/`toHaveURL`) — never a bare navigate-and-assert-title.

The 22nd Layer-3 tool `verify-frontend-e2e-loop-exit --artifact <verdict.json> --repo-root <workspace> --out <verdict>` checks this artifact is genuine, biting on four escape modes: `e2e-described-not-executed` (not run against a live env / no trace), `e2e-api-only-no-user-actions` (every action is a direct-API call), `e2e-vacuous-navigate-assert` (no assertion on visible state), and `e2e-trace-claimed-but-absent` (a trace path that names no file). The run-level `_audit_frontend_e2e` arm in `pipeline-completion-audit.py` is the loop-exit backstop: a frontend slice with no genuine passing verdict here BLOCKS the Phase 8 commit, and no per-task `frontend_impact_e2e_review` note escapes it.
