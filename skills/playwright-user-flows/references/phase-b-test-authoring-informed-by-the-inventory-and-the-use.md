# Phase B — Test authoring (informed by the inventory AND the user-journey map)

**Choose the venue before authoring against it (v3.66.0).** Apply the `verification-planning` skill first: enumerate local run / dev environment / replay / seeded fixture / production for the claims these flows verify, prove which venue each depends on, and record the `verification_plan`. The real-backend rule below stands — for a `both`-layer feature the deployed dev environment IS the faithful venue for front-to-back claims, and the plan records why; the cheaper venues still settle first every claim they can (the handler logic locally, the failing input by replay, the empty-state by a seeded fixture), and a live environment the flows need is the run's to PROVIDE (`references/local-dev-test-discipline.md`), never a reason to wait.

**Tests are organized by user journey, not by inventory entry.** Each entry in `journeys[]` becomes a top-level test whose name reflects the user achievement, not the widget being clicked. For each journey AND each entry in `conditional_ui`, author a Playwright test. Mandates:

### Test naming reflects user intent

Names describe what the user accomplishes (or fails to accomplish), not the UI mechanism:

- **Yes:** `test_first_time_visitor_completes_first_login`
- **Yes:** `test_returning_user_resumes_session_to_intended_route`
- **Yes:** `test_user_sees_clear_error_when_password_wrong`
- **No:** `test_submit_button_works`
- **No:** `test_email_input_accepts_text`
- **No:** `test_handles_401`

`test_handles_401` describes the test's mechanic; `test_user_sees_clear_error_when_password_wrong` describes the user-facing outcome the test is protecting. Only the latter survives a refactor that renames the submit endpoint or restructures the error component — and only the latter is something a PM or product reviewer can read and confirm matches their intent.

#### State-guard tests (disabled buttons, loading spinners, empty states) — same rule applies

The temptation is strongest here. "The submit button is disabled when the form is invalid" sounds like a behavior fact, not a widget assertion. That is the trap. Name these tests by what the **user** experiences, not by what the developer wired up:

- **Yes:** `test_user_cannot_submit_until_credentials_entered`
- **Yes:** `test_user_sees_loading_indicator_during_submit`
- **Yes:** `test_user_cannot_double_submit_during_an_in_flight_request`
- **Yes:** `test_user_sees_empty_state_when_no_inventory_matches_filter`
- **No:** `test_sign_in_button_disabled_when_form_invalid`
- **No:** `test_submit_button_disabled_during_submission`
- **No:** `test_loading_spinner_renders_during_submit`
- **No:** `test_empty_state_shows_when_filter_returns_zero_rows`

The "No" names describe what the developer wired up (a `disabled` attribute, a spinner element, an empty-state block). The "Yes" names describe what the user discovers (they cannot submit yet, they know their request is in flight, they understand why the list is empty). If a refactor renames the spinner component or moves the disabled logic into a hook, the "No" names rot; the "Yes" names still apply because the user experience has not changed.

### Real-user simulation

A Playwright test simulates a real human via `page.goto` / `page.click` / `page.fill` / `page.selectOption` / `page.setInputFiles` / `page.waitFor` / `expect(locator).toBeVisible()` and asserts visible state. Direct API calls inside a Playwright test — `page.evaluate(() => fetch(...))`, `page.request.get/post/...`, `axios.*` from inside the test body — are FORBIDDEN substitutes for user-click paths. The only allowed direct-API uses are: `page.route(...)` to mock specific error paths (401 / 429 / 500), and `page.request.*` to verify asset resolution (e.g., logo SVG returns 200 with the registered SHA-256).

- `page.goto` → `page.click` / `page.fill` / `page.selectOption` / `page.setInputFiles` → `page.waitForSelector` or `expect(locator).toBeVisible()`.
- NEVER hit the API directly in place of a user click.
- NEVER call internal app methods (e.g., `window.app.submitLogin()`).

### Real backend by default (front-to-back integration is the default, not opt-in)

Real-user simulation (clicking through the UI) and real-backend testing (the UI talking to a real server) are TWO different disciplines, and a test can satisfy the first while violating the second. A test that clicks every button correctly but whose every API response is a canned mock has proven the frontend renders fake data nicely — it has proven NOTHING about whether the frontend and backend actually integrate. On a greenfield build where the frontend and backend are written in parallel, this is the dominant failure mode: each layer is built, the frontend mocks the backend, "Playwright passes", and the two layers are never once exercised together.

**The rule:** for any feature whose coverage-map `layer` is `both` (spans frontend AND backend), the happy-path user-flow tests MUST run against the **real running backend** — a real server process, real DB / queue / cache, real responses produced by the actual backend code. This is the DEFAULT. It is overridden ONLY when the requirements folder *explicitly* authorizes isolated / mock-backed testing for a named requirement (and that authorization is quoted in the review-gate evidence's `integration_testing_review_note`).

**Forbidden as a substitute for real-backend testing of the happy path:**

- `page.route('**/api/**', route => route.fulfill({ status: 200, body: <canned JSON> }))` — intercepting the happy-path API and returning hand-written JSON. (Forcing a *specific error* — 401 / 429 / 500 — via `page.route` remains allowed; that is error-path injection, not happy-path faking.)
- **MSW** (`msw`, `setupServer`, `setupWorker`, `rest.*`, `http.*` request handlers) standing in for the backend during the Playwright run.
- An **in-memory / fake / stub API server** (`json-server`, a hand-rolled Express stub, `miragejs`, `nock`, a "mock backend" fixture) started instead of the real backend.
- **Hardcoded response fixtures** imported into the frontend (`fixtures/loginResponse.json`, `__mocks__/api.ts`) and returned by a build-time flag or a test-only code path.
- A real backend pointed at a **fake / seeded-only datastore that the backend code itself does not own** (e.g., the frontend reads from a static JSON file the backend never writes).

**Allowed:**

- `page.route` to force a *specific error response* (401 / 429 / 500 / network failure) that is hard to trigger naturally — error-path coverage, not happy-path faking.
- A real backend running against a **dev database seeded with dev fixtures** per `dev-api-integration-testing` — the backend code still produces every response; the seed is just the starting data.
- Mocking a genuinely external third-party dependency (a payment processor, an email provider) per `dev-api-integration-testing`'s "mock only what's truly external" rule.

**Phase 3 vs Phase 5.** On a greenfield parallel build the frontend teammate may legitimately reach its Phase 3 review gate before the backend is integrated. In that case the frontend teammate sets `integration_testing_review: "n/a"` with a note that says *exactly* "counterpart backend not yet integrated; front-to-back integration testing DEFERRED TO PHASE 5". That `n/a` is a DEBT, not a pass — Phase 5 cross-layer integration MUST settle it by running the user-flow tests against the real backend. A `both`-layer feature that is still `n/a` at the end of Phase 5 is a failure, not a completion.

#### Tell-tale signs the tests are running on fake data

Any one of these means STOP — the happy path is not really integration-tested:

- The Playwright suite passes with **no backend process running** (no `npm run dev:api`, no server in the test's `webServer` config, no docker compose up). If killing the backend doesn't break the happy-path tests, the happy path never touched the backend.
- A `page.route('**/api/**', ...)` (or `'*/api/*'`, or the feature's specific endpoints) whose `fulfill` body is a hand-written success payload.
- An `msw` / `setupServer` / `miragejs` / `json-server` import anywhere in the frontend test setup, `playwright.config`, global-setup, or a test fixture.
- The test data appears verbatim as a string literal in a frontend file or a `fixtures/` JSON, and the same shape is asserted in the test — the test is checking that a constant equals itself.
- The backend team's endpoints have integration tests, the frontend team's UI has Playwright tests, and NO test loads the frontend in a browser AND hits the real backend in the same run.
- The review-gate evidence claims "tested with Playwright" but `integration_testing_review` is `pass` while no real backend is referenced anywhere in the test config or the demo artifact.

### Shared-state hygiene (flows against the shared dev environment)

The dev environment's data is SHARED — with the other flows in this suite, with the other teammates on this run, and with the previous run of this same test. A mutating flow that does not think about that is a flow that can pass without doing anything. This section imports the `dev-api-integration-testing` fixture discipline into the Playwright layer, where it has been missing.

**Every mutating flow uses per-test unique values OR restores what it changed.** Pick one:

- **Unique values (preferred).** Derive the value the test writes from a run-unique suffix — `` `QA Flow ${testInfo.testId}-${Date.now()}` ``, a uuid fragment, the `it-<test-name>-<uuid>` prefix convention from `dev-api-integration-testing`. Nothing the test writes can collide with anything already there.
- **Teardown restore.** Capture the pre-existing value in the setup step and put it back in `afterEach` / a cleanup step, so the environment ends the run in the state it started.

**Every flow is runnable twice in a row without failing on the second run.** This is the same non-negotiable as the backend idempotency rule, and it is the cheapest way to find the defect: run the flow, run it again immediately, and watch. A flow that only passes against a clean fixture is a flow that has already broken itself for the next run — and for the next teammate.

**Never assert a hardcoded literal the test itself wrote.** Assert on a value DERIVED from the test's own unique input:

```typescript
// NO — a residue of run N satisfies run N+1; the Edit never had to work
await page.getByTestId('display-name').fill('Updated Name');
await page.getByRole('button', { name: 'Save' }).click();
await expect(page.getByTestId('display-name')).toHaveValue('Updated Name');

// YES — only THIS run's write can satisfy THIS run's assertion
const unique = `Updated Name ${testInfo.testId}-${Date.now()}`;
await page.getByTestId('display-name').fill(unique);
await page.getByRole('button', { name: 'Save' }).click();
await page.reload();
await expect(page.getByTestId('display-name')).toHaveValue(unique);
```

The failure this closes is silent and total: run 1 genuinely saves `Updated Name`; run 2 opens a field that ALREADY reads `Updated Name`, fills it with the same string, fires no change event, sends no request — and the assertion passes. The test is now green forever and verifies nothing. Reload (or re-navigate) before the assertion too, so the value being read came back from the server rather than from the input you just typed into.

`test-completeness-verifier` Step 3g audits this mechanically — a `fill(<literal>)` paired with an assertion of the SAME literal in one file, and mutation actions on non-unique literals with no teardown or unique-value signal, land in `fixture_hygiene_findings[]` and make the playwright kind `fail`.

### Selector hierarchy (use the highest available)

1. `page.getByRole(...)` — accessible role + name.
2. `page.getByTestId(...)` — `data-testid` attribute.
3. `page.getByText(...)` — visible text.
4. CSS selectors — last resort. If you reach for CSS, ask whether you should add a `data-testid` to the component instead.

### Cover every error response

For each error in the inventory's `on_click.errors[]`: use `page.route('**/api/...', route => route.fulfill({ status: ..., body: ... }))` to force the failure and assert the user-visible error UI.

### Cover every conditional render

For each entry in `conditional_ui[]`: write at least one test that triggers the `renders_when` condition and asserts the element appears.

### Cover the navigation web

For each `navigates_to` and each `on_click` that ends in a route change: write a test that triggers the navigation the user's way and asserts the new route plus the new page's identifying element.

### Auth state

Use Playwright storage state files (`page.context().storageState({ path })`). Never re-login at the top of every test.

### Trace capture

Configure `trace: 'retain-on-failure'`. Failure traces go into the review-gate evidence file as artifact paths.

### Visual-fidelity tests (when DESIGN_MAP.md exists)

If `<codebase>/docs/DESIGN_MAP.md` exists, author a parallel layer of **visual-fidelity tests** alongside the user-journey tests. These tests assert that every interactive element's COMPUTED STYLE, BOUNDING BOX, and ASSET REFERENCE matches the per-screen visual specs in the design map. Naming follows the user-intent convention — describe what the user perceives, not the assertion mechanic.

#### Computed-style assertions

For each row in DESIGN_MAP.md's `## Per-Screen Visual Specs` table, assert the spec via `element.evaluate`:

```typescript
test('user_sees_brand_primary_button_on_login_page', async ({ page }) => {
  await page.goto('/login');
  const submit = page.getByRole('button', { name: 'Sign in' });
  const styles = await submit.evaluate(el => {
    const cs = window.getComputedStyle(el);
    return {
      fontFamily: cs.fontFamily,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      color: cs.color,
      backgroundColor: cs.backgroundColor,
      paddingTop: cs.paddingTop,
      paddingRight: cs.paddingRight,
      paddingBottom: cs.paddingBottom,
      paddingLeft: cs.paddingLeft,
      borderRadius: cs.borderRadius,
      boxShadow: cs.boxShadow,
    };
  });
  expect(styles.fontFamily).toContain('Inter');
  expect(styles.fontSize).toBe('14px');
  expect(styles.fontWeight).toBe('600');
  expect(styles.color).toBe('rgb(255, 255, 255)');
  expect(styles.backgroundColor).toBe('rgb(37, 99, 235)'); // brand.primary.500 = #2563EB
  expect(styles.borderRadius).toBe('6px');
});
```

Browser color values normalize to `rgb()` (or `rgba()`); convert hex from DESIGN_MAP.md to rgb for the assertion. Maintain a single helper that does the conversion (`hexToRgb('#2563EB') → 'rgb(37, 99, 235)'`) so tests stay readable.

#### Bounding-box assertions (zero-tolerance default)

```typescript
const box = await submit.boundingBox();
expect(box?.width).toBe(240); // EXACT — DESIGN_MAP spec width 240
expect(box?.height).toBe(40);
```

**Default tolerance is 0px (EXACT match).** Per-element overrides require an explicit `tolerance:` clause in DESIGN_MAP.md for that element with a recorded rationale (e.g., `tolerance: { width: 1px, rationale: "sub-pixel rounding observed across browser engines; not user-perceivable" }`). Silent slop is forbidden — see `visual-fidelity-reconciliation` for the strict-QA contract enforced at the review gate. Set viewport explicitly with `page.setViewportSize(...)` to match the viewport declared in DESIGN_MAP.md's frontmatter, otherwise different CI hosts produce different bounding boxes (which IS the bug, not a flake).

#### Asset reference assertions

For every `<img>` / `<svg use href>` / `background-image` referenced in DESIGN_MAP.md's Asset Registry:

```typescript
test('user_sees_brand_logo_top_left_on_login_page', async ({ page }) => {
  await page.goto('/login');
  const logo = page.getByRole('img', { name: /acme|brand/i });
  await expect(logo).toBeVisible();
  const src = await logo.getAttribute('src');
  expect(src).toBe('/images/logo.svg'); // matches Asset Registry path
  const response = await page.request.get(new URL(src!, page.url()).toString());
  expect(response.status()).toBe(200);
  // Optional SHA-256 verification:
  // const buf = await response.body();
  // expect(crypto.createHash('sha256').update(buf).digest('hex')).toBe('a3f1...');
});
```

If DESIGN_MAP.md records a SHA-256 hash for the asset, the test SHOULD verify it. Hash mismatches detect accidental asset overwrites that visual snapshots might miss.

#### Snapshot regression (primary viewport only)

Use sparingly and with explicit masks for time-sensitive UI:

```typescript
test('user_sees_login_page_layout_as_designed', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/login');
  await expect(page).toHaveScreenshot('login-empty-1440.png', {
    maxDiffPixelRatio: 0.01,
    mask: [page.getByTestId('current-time'), page.getByTestId('cookie-banner')],
  });
});
```

One snapshot per primary viewport declared in DESIGN_MAP.md is sufficient. Don't snapshot every responsive breakpoint — computed-style assertions cover the breakpoint-specific values precisely. Snapshots regress on layout / pixel; computed styles regress on intentional values. Both signals matter and aren't redundant.

#### Drift handling

If DESIGN_MAP.md's `## Detected Drift` flags a known disagreement between design and implementation, the visual-fidelity test should assert against whichever value the team decided to ship — captured in the Phase 1 spec validation as either "fix the code" (test asserts the DESIGN value) or "fix the design / accept the drift" (test asserts the IMPLEMENTATION value, with a `// drift: see DESIGN_MAP.md#detected-drift row N` comment).

Never assert against both values, and never write a test against an undeclared drift — that hides the decision instead of forcing it.

#### Strict QA at the review gate

The tests authored here are the test-authoring discipline. The strict POST-DEVELOPMENT QA discipline — zero-tolerance comparison of every (screen, element, state, viewport) tuple against DESIGN_MAP.md with per-state screenshots, code-first analysis, and architect-team escalation on any drift — is enforced separately by `visual-fidelity-reconciliation`. That skill is hook-enforced (the `visual_fidelity_review` field in review-gate evidence) and is what runs before any frontend task can be marked complete when DESIGN_MAP.md exists. On-demand audits use the `/architect-team:visual-qa` command.

### Per-test expectations & failure handling

For every Playwright test authored here, write a per-step expectation file BEFORE running the test, per `root-cause-test-failures`. The expectation file (`<test-output-dir>/expectations/<test-id>.json`) is the contract Phase B's root-cause loop measures against. On any test failure, do NOT propose a fix until the 3-pass root-cause loop from `root-cause-test-failures` has completed and produced an `rca/<test-id>-<ts>.json` artifact with evidence-backed root cause. Symptom patches, blind retries, and "probably-flaky" rationalizations are forbidden.

When the RCA verdict is `product-bug`, the failure-handler does NOT just escalate via a handoff — it ALSO writes a solution requirement to `<cwd>/.architect-team/solution-requirements/SR-<test-id>-<ts>.json` per `team-spawning-and-review-gates`'s `## Solution Requirements` section. The orchestrator picks the SR up automatically and spawns a fix team; the loop re-enters Phase 2 with the failing test as the convergence check. No alert sits idle.
