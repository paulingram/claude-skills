# Phase A — Examination (mandatory, before any test code)

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

**Ensure and consult the interaction-intuition map.** `<codebase>/docs/INTERACTION_INTUITION_MAP.md` is the per-element record of what each control does and which endpoint it calls — exactly the selectors and endpoints Steps 2-4 would otherwise re-derive by hand, and it exists only when a pipeline run's Phase −1D produced it. So do not assume it: ensure it via the `intuition-map-lifecycle` skill's `ensure` verb, then consult it alongside `ROUTE_MAP.md` for every element the flow touches. **A map's mere PRESENCE does not satisfy the precondition.** The verb reports what is still owed in `action_required`, and ensure is complete only when that reads `none` — a present map that will not parse reports `repair-map`, and a present, schema-valid map carrying zero elements reports `populate`, so a freshly written scaffold still owes you its elements. Treat any value other than `none` as work to do before authoring, and read `intuition-map-lifecycle` for the full verdict set rather than re-deriving it here. An entry carrying `user_verdict: confirmed` is a settled fact about that element's action and endpoint — author to it rather than re-guessing. An unconfirmed, low-confidence, or `unknown` entry is a candidate to verify while tracing, never a fact to assert.

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
