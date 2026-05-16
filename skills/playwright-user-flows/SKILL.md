---
name: playwright-user-flows
description: Use when authoring or running Playwright tests for any feature with a frontend component, especially during Phase 5 integration. Mandates a two-phase workflow — first examine the frontend code to build an interactivity inventory and API expectation map, then author tests that simulate the real user (page.goto / click / fill / waitFor) and assert visible state. Rejects endpoint-only testing as a substitute for user-flow testing. Includes a coverage verification step that proves every interactive element and every error response is tested.
---

# Playwright User Flows — White-Box, Real-User

Frontend tests fail in production when they test what the developer remembered, not what the user can actually do. This skill enforces two disciplines:

1. **Read the code first.** Before authoring any test, enumerate every interactive element and every API call the feature touches, from the actual source.
2. **Test as the user.** Every test simulates a real human — `page.click`, `page.fill`, `page.waitFor` — and asserts visible state. Direct API calls are never a substitute for user-flow tests.

## Phase A — Examination (mandatory, before any test code)

For each feature/flow under test:

### Step 1: Consult the route map

Read `<codebase>/docs/ROUTE_MAP.md` for every route the flow traverses. If `last_routed` is older than the codebase's latest commit, request re-mapping via the intake skill before continuing — tests built on stale assumptions are worse than no tests.

### Step 2: Enumerate interactive elements

Read the actual component code for each route's component tree. List EVERY interactive element — no exceptions:

- Buttons, links.
- Form inputs of every type: text, password, email, number, checkbox, radio, select/dropdown, file, date, color, range, textarea.
- Modal/drawer triggers, popovers, tooltips that have click-through actions.
- Drag-and-drop targets.
- Keyboard shortcuts (`onKeyDown`, `onKeyUp`, hotkey libraries).
- Conditional render gates — `if` / `&&` / ternary in JSX that determine what shows when, and the predicate that gates each.

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

This file is the source of truth for what gets tested.

## Phase B — Test authoring (informed by the inventory)

For each entry in `interactivity` AND each entry in `conditional_ui`, author a Playwright test. Mandates:

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

## Phase C — Coverage verification (before submitting tests)

Run an automated coverage check:

- Every `id` in `interactivity[]` must appear in the test source (grep by selector or by inventory id used as a test-name suffix) in at least one test.
- Every `id` in `conditional_ui[]` must appear in at least one test.
- Every endpoint in the inventory's `fires_api` set must be exercised by at least one test (real call for happy paths, `page.route` for error paths).
- Every navigation edge must be traversed by at least one test.

Write `<test-output-dir>/playwright-coverage.json`:

```json
{
  "feature": "login-flow",
  "coverage": {
    "interactivity": { "email-input": ["test_login_happy_path"], "submit": ["test_login_happy_path", "test_login_401", "test_login_429"], "forgot-password": ["test_forgot_password_link_navigates"] },
    "conditional_ui": { "error-banner": ["test_login_401"], "loading-spinner": ["test_login_pending_state"] },
    "endpoints_exercised": ["POST /api/auth/login"],
    "navigations_traversed": ["/login → /dashboard", "/login → /forgot-password"]
  },
  "gaps": []
}
```

If `gaps` is non-empty, add tests until it is empty. Then this file goes into the review-gate evidence.

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "I'll just hit the API endpoint to test the same logic" | NO. The user doesn't interact with the API. Untested click paths break in production with frontend regressions. The Phase A inventory exists specifically to prevent this shortcut. |
| "I'll mock the entire backend in Playwright" | Mock specific error paths only (`page.route` for 401/429/500). Happy-path runs against the real dev API per `dev-api-integration-testing`. |
| "The interactivity inventory is overkill for a small feature" | If it's small, the inventory is small. Either way, you cannot author tests without it. |
| "I'll skip the conditional_ui ones — they're rare" | Conditional UI is exactly what breaks silently. Test it. |
| "Selectors are too brittle" | That's why the hierarchy goes role → testid → text → css. If you're reaching for CSS, the answer is usually to ADD a testid to the component. |
| "The route-map / CODEBASE_MAP isn't current, so I'll skip reading it" | Then trigger a re-mapping. Tests built on stale assumptions are worse than no tests. |
| "I'll write the test first and figure out interactivity later" | The inventory IS the test design. Skipping it produces happy-path-only tests that miss the failure modes that actually break in production. |
