---
name: playwright-user-flows
description: Use when authoring or running Playwright tests for any feature with a frontend component, especially during Phase 5 integration. Mandates a workflow that first establishes who the users are and what they are trying to achieve (escalating to the user via structured questions when intent cannot be derived from product docs/requirements), then exhaustively enumerates every link, button, form input, modal trigger, keyboard shortcut, drag target, and conditional render gate plus the API contracts each touches, then authors tests organized around user journeys (page.goto / click / fill / waitFor) that assert visible state. Rejects endpoint-only testing as a substitute for user-flow testing. Coverage verification proves every user objective, every interactive element, and every error response is exercised.
---

# Playwright User Flows — White-Box, Real-User

Frontend tests fail in production when they test what the developer remembered, not what the user can actually do — and what the user can actually do is shaped by **who** the user is and **what they are trying to achieve**, not just which elements the developer made interactive. This skill enforces three disciplines:

1. **Know the user, know the goal.** Before reading code, establish who the user base is and what each persona is trying to accomplish. If the product docs / requirements / OpenSpec proposal do not make this clear, **ask the user** — do not guess.
2. **Read the code exhaustively.** Enumerate every interactive element (link, button, form input of every type, modal trigger, drag target, keyboard shortcut, conditional render gate) and every API call the feature touches, from the actual source. No exceptions, no "the obvious ones".
3. **Test as the user, test the user's goals.** Every test simulates a real human — `page.click`, `page.fill`, `page.waitFor` — and is named after a user achievement, not a widget. Tests are organized by user journey: the sequence a real user follows to accomplish a real goal. Direct API calls are never a substitute for user-flow tests.

## Phase A — Examination (mandatory, before any test code)

For each feature/flow under test:

### Step 0: Identify users and objectives (mandatory, BEFORE reading any code)

Before opening a single source file, answer four questions:

1. **Who uses this feature?** Enumerate every distinct user persona (e.g., "first-time visitor", "returning shopper", "admin operator", "API consumer through the UI"). Roles defined in code (RBAC tables, auth scopes) are a STARTING point — but a single code-role often serves multiple journeys (a returning vs. first-time shopper share one role).
2. **What is each persona trying to achieve?** For each persona, list the concrete goals this feature exists to serve. Goals are user-facing outcomes ("complete a purchase", "recover a forgotten password", "compare two products"), not verbs the UI exposes ("click submit").
3. **What is their starting context?** Where are they coming from (URL, referrer, email link, deep link)? What state are they in (logged in, logged out, mid-checkout, error recovery)? What do they already know?
4. **What does success look like — visibly?** For each goal, the literal visible state that signals "the user got what they came for" (a confirmation page, a row appearing in a list, an item disappearing, a number incrementing).

#### Where to look first

In priority order:
1. `$REQ_DIR/proposal.md`, `design.md`, `tasks.md` (OpenSpec).
2. `<codebase>/README.md`, `docs/`, any product / UX brief in the repo.
3. Analytics, feature-flag definitions, route popularity hints — if available.
4. The route names themselves (`/checkout`, `/admin/users` strongly hint at persona).
5. Issue tracker / commit history referenced from the feature.

#### PROCEED test — do you actually have high confidence?

After answering the four questions from your sources, run this check **for each persona and each goal you have drafted**:

1. **Persona quote test.** For each persona name on your list, can you quote a phrase from a source artifact (brief / proposal / README / OpenSpec doc / ticket) that NAMES this persona, or names a clear synonym? Write the quote AND the source file/section beside the persona. If you cannot produce a quote, you are inferring — not knowing.
2. **Goal quote test.** For each goal, can you quote a phrase from a source artifact that names this goal or describes the user-facing outcome it produces? Same rule: cite the source, or admit you inferred it.
3. **Success-visible quote test.** For each `success_visible` assertion, did the source describe what success looks like, or did you make it up? "The dashboard renders" is not in the brief unless the brief says so.

**Result rule (binary, no middle ground):**
- Every persona, goal, and success-visible has a citation → you have high confidence. Proceed past Step 0.
- ANY ONE is inferred (no citation) → you do NOT have high confidence. **Escalate to the user before writing the user-intent map**, per the next subsection.

#### Tell-tale signs you are inferring, not knowing

Watch for these red flags in your own draft. Any single one means STOP and escalate — do not rationalize past them:

- **Generic role labels not in the source.** You wrote "Inventory Manager" / "Fulfillment Operator" / "Power User" / "Admin Operator" / "Site Editor" / "Customer Support Agent" / "Engineer" when the source said only "any authenticated user" or "logged-in user".
- **"Most likely" interpretation of an ambiguous noun.** The source says "users can edit stock"; you decide "users = warehouse staff". The brief did not say warehouse staff.
- **UI-shaped goal labels.** Your goal is "manage inventory" or "use the dashboard" — these are framings of what the UI offers, not what a real human is trying to accomplish in their day.
- **Multiple plausible interpretations exist and you picked the one that is "obviously right".** If it were obviously right, the others would not be plausible.
- **You can describe a persona in detail but cannot quote a single sentence from any source that justifies its existence.**
- **You are about to write a user-intent map with more invented detail than was given to you.** If your map is richer than the brief, the extra detail came from your imagination.

The pattern: **plausibility ≠ confirmation.** A persona you can defend is not the same as a persona the user told you about. The whole point of Step 0 is to refuse to guess — even when guessing would be reasonable.

#### When to escalate to the user (REQUIRED, not optional)

If after reading the sources above you cannot answer all four questions with **high confidence**, stop and ask the user. Surface specific, structured questions — never a vague "tell me about the users". A good question template:

~~~
Before I write Playwright tests for <feature>, I need to confirm user intent:

1. Who are the primary personas using this feature? I see <persona-A> and
   <persona-B> in the code / docs — are there others (e.g., admin operators,
   external integrators, API-consumers-via-UI)?
2. For <persona-A>, what are the top 2-3 goals they are trying to accomplish
   with this feature? I inferred <goal-1>, <goal-2> — is that right?
3. For <goal-1>, what does "done, success" look like to the user — a
   confirmation page, an item in a list, an email sent? I want to assert
   against that exact visible state.
4. Are there persona × goal combinations that are explicitly NOT in scope for
   this release (so I do not write tests for them)?
~~~

If the skill is being applied from a subagent context (e.g., the architect-team `integration` or `frontend` agent), write the question to `<cwd>/.architect-team/handoffs/<self>-to-orchestrator-userintent-<feature>-<ts>.md` and signal idle so the orchestrator surfaces it to the user. Do NOT proceed past Step 0 until the answers land.

Asking is cheap; writing tests against wrong assumptions costs an order of magnitude more. **A test author who proceeds without confident answers to these four questions is testing what they imagine, not what the user does.**

#### Write the user-intent map

Persist `<test-output-dir>/user-intent/<feature>.json`:

```json
{
  "feature": "login-flow",
  "personas": [
    {
      "id": "first-time-visitor",
      "description": "Someone who has never logged in before, clicking 'Sign in' from a marketing page.",
      "starting_context": { "route_in": "/", "auth": "logged_out", "referrer": "marketing_email" },
      "goals": [
        {
          "id": "complete-first-login",
          "intent": "Get into the dashboard so I can use the product I just signed up for.",
          "success_visible": "Dashboard renders with my user name in the header.",
          "failure_modes_user_cares_about": ["wrong password", "rate-limited", "service down"]
        }
      ]
    },
    {
      "id": "returning-user-with-expired-session",
      "description": "Has logged in before, session cookie expired, wants to resume what they were doing.",
      "starting_context": { "route_in": "/orders/42", "auth": "session_expired" },
      "goals": [
        {
          "id": "resume-to-intended-route",
          "intent": "Get back to what I was doing, not bounced to the dashboard root.",
          "success_visible": "Order #42 detail page renders after login.",
          "failure_modes_user_cares_about": ["forgot password", "account locked"]
        }
      ]
    }
  ],
  "out_of_scope": ["password-reset-via-SMS (deferred to next release)"]
}
```

This file is consulted by every subsequent step. The interactivity inventory traces FROM these goals. Tests in Phase B are named FROM these goals. Coverage in Phase C is measured AGAINST these goals.

### Step 1: Consult the route map

Read `<codebase>/docs/ROUTE_MAP.md` for every route the flow traverses. If `last_routed` is older than the codebase's latest commit, request re-mapping via the intake skill before continuing — tests built on stale assumptions are worse than no tests.

### Step 2: Enumerate interactive elements (exhaustive)

Read the actual component code for each route's component tree. List EVERY interactive element — no exceptions, no "I'll just cover the obvious ones":

- **Every link** — `<a>`, framework `Link` / `NavLink` (`next/link`, `react-router-dom`, etc.), programmatic `router.push` / `navigate` / `Linking.openURL`. Include footer, header, contextual in-content, breadcrumb, and pagination links.
- **Every button** — `<button>`, `role=button` divs/spans, icon-only buttons (test their accessible name), buttons with disabled-when conditions (test both states).
- **Every form input** — text, password, email, number, tel, url, search, checkbox, radio, select/dropdown (native AND custom), combobox, file, date, time, datetime-local, month, week, color, range, textarea, contenteditable, hidden (if it affects submission), uncontrolled inputs via `ref`.
- **Every overlay trigger** — modal/dialog open buttons, drawer/sidebar toggles, popovers with click-through actions, tooltips with interactive content, command palettes (`cmd+k`), context-menu triggers, toast actions.
- **Every drag/touch interaction** — drag-and-drop sources and targets, swipe gestures, long-press, pinch/zoom where the feature uses them.
- **Every keyboard shortcut** — `onKeyDown` / `onKeyUp` handlers, hotkey libraries (`react-hotkeys`, `mousetrap`, `tinykeys`), document-level listeners, framework command palettes.
- **Every conditional render gate** — `if` / `&&` / ternary in JSX (or v-if / *ngIf / `{#if}`) that determines what shows when, and the predicate that gates each. Loading, empty, error, permission-gated, feature-flag-gated, A/B variants.
- **Every implicit interaction** — auto-focus on mount, auto-redirect on certain states, auto-submit (e.g., search-as-you-type after debounce), scroll-position-triggered loading, hover-triggered prefetch.

**Heuristic for "is this interactive?":** if removing it would change what the user can do, see, or get — it is interactive. When in doubt, include it.

**Cross-reference back to user intent:** for every element you enumerate, tag it with the `(persona, goal)` combinations from Step 0 that it participates in. An element that participates in zero user goals is one of two things — either (a) genuinely out-of-scope for this test pass (declare it in `out_of_scope[]`) or (b) a missing goal in the user-intent map (escalate to the user to confirm). Silent "I'll just skip it" is forbidden.

### Step 3: Trace each interaction

For every interactive element, trace what happens on interaction:

- DOM/state change (target selector + expected visible result).
- API call(s) fired (method + endpoint + payload shape).
- Navigation change (which route).
- Error states it can surface.

### Step 4: Read the API contract

For each API call, read the corresponding backend code (use the backend CODEBASE_MAP.md if mapped; otherwise read the route handler directly):

- Request schema (validate against what the frontend sends).
- Success response shape.
- EVERY error response and HTTP status it can return.

### Step 5: Write the interactivity inventory

Write `<test-output-dir>/interactivity/<feature>.json`:

```json
{
  "feature": "login-flow",
  "routes_in_flow": ["/login", "/dashboard"],
  "interactivity": [
    {
      "id": "email-input",
      "selector": "role=textbox[name=\"Email\"]",
      "type": "input",
      "validation": "client-side email regex",
      "binds_to": "state.loginForm.email"
    },
    {
      "id": "submit",
      "selector": "role=button[name=\"Sign in\"]",
      "type": "button",
      "disabled_when": "form invalid OR loading",
      "on_click": {
        "fires_api": "POST /api/auth/login",
        "payload": { "email": "string", "password": "string" },
        "success_200": { "token": "string", "user": "User" },
        "errors": [
          { "status": 401, "shape": { "error": "invalid_credentials" } },
          { "status": 429, "shape": { "error": "rate_limited" } },
          { "status": 500 }
        ]
      }
    },
    {
      "id": "forgot-password",
      "selector": "role=link[name=\"Forgot password?\"]",
      "type": "link",
      "navigates_to": "/forgot-password"
    }
  ],
  "conditional_ui": [
    { "id": "error-banner", "selector": "role=alert", "renders_when": "API 401" },
    { "id": "loading-spinner", "selector": "role=progressbar", "renders_when": "submit in flight" }
  ]
}
```

This file is the source of truth for what mechanics get tested. Step 6 turns it into journeys.

### Step 6: Build the user-journey map (bridge from inventory to tests)

For each `(persona, goal)` combination in the user-intent map, write the sequence of inventory IDs the persona will touch to accomplish the goal. This is the bridge from "what's interactive" (mechanics) to "what tests get written" (user achievements).

Persist `<test-output-dir>/journeys/<feature>.json`:

```json
{
  "feature": "login-flow",
  "journeys": [
    {
      "id": "first-time-visitor-completes-first-login",
      "persona": "first-time-visitor",
      "goal": "complete-first-login",
      "preconditions": { "auth": "logged_out", "route": "/login" },
      "steps": [
        { "action": "fill", "inventory_id": "email-input", "value": "<seeded test email>" },
        { "action": "fill", "inventory_id": "password-input", "value": "<seeded test password>" },
        { "action": "click", "inventory_id": "submit" },
        { "action": "wait", "for": "navigation to /dashboard" },
        { "action": "assert", "visible": "user name in header" }
      ],
      "failure_branches": [
        { "trigger": "401 on submit", "expected_user_visible": "error-banner reading 'Invalid credentials'" },
        { "trigger": "429 on submit", "expected_user_visible": "error-banner reading 'Too many attempts, try again in N seconds'" }
      ]
    },
    {
      "id": "returning-user-resumes-to-intended-route",
      "persona": "returning-user-with-expired-session",
      "goal": "resume-to-intended-route",
      "preconditions": { "auth": "session_expired", "route_attempted": "/orders/42" },
      "steps": [
        { "action": "wait", "for": "redirect to /login?next=/orders/42" },
        { "action": "fill", "inventory_id": "email-input", "value": "<seeded test email>" },
        { "action": "fill", "inventory_id": "password-input", "value": "<seeded test password>" },
        { "action": "click", "inventory_id": "submit" },
        { "action": "wait", "for": "navigation to /orders/42" },
        { "action": "assert", "visible": "order #42 detail page" }
      ]
    }
  ]
}
```

Each journey becomes a Phase B test. Inventory IDs not referenced by any journey are flagged in Phase C as either out-of-scope-for-this-pass OR as a missing journey (escalate to user).

## Phase B — Test authoring (informed by the inventory AND the user-journey map)

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

- `page.goto` → `page.click` / `page.fill` / `page.selectOption` / `page.setInputFiles` → `page.waitForSelector` or `expect(locator).toBeVisible()`.
- NEVER hit the API directly in place of a user click.
- NEVER call internal app methods (e.g., `window.app.submitLogin()`).

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

For every Playwright test authored here, write a per-step expectation file BEFORE running the test, per `root-cause-test-failures`. The expectation file (`<test-output-dir>/expectations/<test-id>.json`) is the contract Phase B's root-cause loop measures against. On any test failure, do NOT propose a fix until the 3-pass root-cause loop from `root-cause-test-failures` has completed and produced an `rca/<test-id>-<ts>.json` artifact with evidence-backed root cause. Symptom patches, blind retries, and "probably-flaky" rationalizations are forbidden — escalate via the RCA handoff if a product bug is found.

## Phase C — Coverage verification (before submitting tests)

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

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "I can figure out who the users are from the code" | Code shows mechanics (RBAC scopes, route names); it does NOT show intent (first-time vs returning, error-recovery vs primary flow, ops vs end-user). When the four Step-0 questions are not answerable with high confidence, ASK the user. The user-intent map is non-optional. |
| "I can plausibly infer the personas from route names / component names / business context" | Inference is not confirmation. If the persona names you produce are not quote-citable from a source artifact (per the PROCEED test in Step 0), you are guessing. Plausibility is not high confidence. The whole point of Step 0 is to refuse to guess — even when guessing would be reasonable. Run the PROCEED test; if any persona or goal is inferred, escalate. |
| "The brief is detailed enough; I'll just label the personas with role names and move on" | If your persona labels are not in the brief, you are inventing them. "Inventory Manager" and "Fulfillment Operator" are common-sense labels, but if the brief said "any authenticated user", the user has not told you those personas exist. Escalate to confirm before committing the user-intent map to disk. |
| "Asking the user slows things down" | One clarification costs minutes. A test suite built on a wrong persona assumption costs hours to identify and rewrite — and worse, may pass green while leaving the actual user goal untested. The escalation cost is always lower than the rework cost. |
| "There's only one user role, so I don't need personas" | Even one role serves multiple personas across journeys: first-time vs returning, mobile vs desktop, error-recovery vs happy-path. A single role with a single persona is rare; default to enumerating, and let the user confirm collapse only if intent truly is uniform. |
| "I'll name tests after the function under test" | Test names that describe widgets (`test_submit_button`) document the developer's mental model. Test names that describe user achievements (`test_user_can_sign_in`) document the contract with the user. Only the latter survives refactors and only the latter is auditable by a non-developer. |
| "Disabled-button / loading-spinner / empty-state tests are UI behaviors, so widget-style names are fine here" | No — state-guard tests have a user-visible meaning ("they cannot submit yet", "they know the request is in flight", "they understand why the list is empty"). Name them by that meaning. `test_submit_button_disabled_when_form_invalid` rots when the button is refactored into a hook; `test_user_cannot_submit_until_credentials_entered` still applies. See the "State-guard tests" subsection in Phase B. |
| "I'll cover the buttons but skip keyboard shortcuts / drag handlers / hover prefetch" | A power user reaches for `cmd+k` before the mouse. A keyboard-only user has no other option. Skipping any interaction class ships a regression-blind spot for the exact users who notice fastest. Exhaustive means exhaustive. |
| "The inventory's missing IDs are obviously out of scope" | "Obviously" is the rationalization. Either declare them out-of-scope in `out_of_scope[]` with a written rationale, or escalate to the user. Silent gaps in the inventory become silent gaps in production. |
| "I'll just hit the API endpoint to test the same logic" | NO. The user doesn't interact with the API. Untested click paths break in production with frontend regressions. The Phase A inventory exists specifically to prevent this shortcut. |
| "I'll mock the entire backend in Playwright" | Mock specific error paths only (`page.route` for 401/429/500). Happy-path runs against the real dev API per `dev-api-integration-testing`. |
| "The interactivity inventory is overkill for a small feature" | If it's small, the inventory is small. Either way, you cannot author tests without it. |
| "I'll skip the conditional_ui ones — they're rare" | Conditional UI is exactly what breaks silently. Test it. |
| "Selectors are too brittle" | That's why the hierarchy goes role → testid → text → css. If you're reaching for CSS, the answer is usually to ADD a testid to the component. |
| "The route-map / CODEBASE_MAP isn't current, so I'll skip reading it" | Then trigger a re-mapping. Tests built on stale assumptions are worse than no tests. |
| "I'll write the test first and figure out interactivity later" | The inventory IS the test design. Skipping it produces happy-path-only tests that miss the failure modes that actually break in production. |
| "The user-intent map is documentation overhead — I'll keep it in my head" | The inventory and journey files are mechanically grep'd in Phase C. There is no Phase C pass without them on disk. Holding intent "in your head" makes the coverage check unauditable. |
