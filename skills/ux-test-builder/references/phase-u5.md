# Phase U5 — Playwright authoring per distilled flow

One `.spec.ts` per distilled flow at `<cwd>/.architect-team/ux-tests/<persona-slug>/playwright/<flow-N>-<slug>.spec.ts` — test authoring applies `superpowers:test-driven-development` (the flow's assertions + `expected_user_effect` are written as the verification contract before the executors run them, per `## Plugin prerequisites (v3.9.0)`). Per `playwright-user-flows`:
- Real interaction calls.
- Real login.
- Per-step expectation files at `<cwd>/.architect-team/ux-tests/<persona-slug>/playwright/expectations/<flow-N>-<step-N>.json`, per `root-cause-test-failures`.
- **Selector witness assertions (v0.9.32) — MANDATORY for every action-call selector** (`.toBeVisible()` + `.toBeEnabled()` + a disambiguating role / attribute check). Same authoring discipline as the bug-replicator's `agents/bug-replicator.md` Step 2.
- **`expected_user_effect` block (v0.9.32) — MANDATORY per flow.** The U5 orchestrator emits an `expected_user_effect` field on every flow's spec (placed in a `<flow-N>-<slug>.effect.json` companion file at the same path) describing the concrete observable outcome the persona accomplishes by running this flow. The field is the input to U6's **flow-effect witness** (a flow that passes Playwright's assertion but didn't actually achieve the persona's intent is the failure mode the witness closes). Each effect is one of `dom_state_change` (an element appears/disappears/changes), `network_request` (a specific endpoint was called with a specific status), `url_change` (the URL landed at a specific route), or `console_sentinel` (a sentinel logged). Examples:

  ```json
  {
    "flow_id": "flow-3",
    "expected_user_effects": [
      { "kind": "network_request", "value": "POST /api/files/upload returned 2xx" },
      { "kind": "dom_state_change", "value": "file 'invoice-2024.pdf' appears in #uploaded-files-list" }
    ]
  }
  ```

The literal flow at U2 is already authored; this phase authors flows #2-N from the distilled set. Re-author the literal at U2 to add its `expected_user_effect` block too (it inherits the same v0.9.32 witness discipline).

**Email-aware flow authoring (v0.9.34).** When a distilled flow involves an email-triggered action (e.g., *"invitee signs up via the email link"*, *"user resets password via the reset email"*), the U5 orchestrator applies Phase E1 of the `email-testing` skill discipline. If `email_surface_detected: true`, the `.spec.ts` for that flow MUST include Mailpit provisioning (E2 in `beforeAll`/`afterAll`), `waitForEmail()` polling (E3), link extraction + classification (E3), and Playwright navigation to every extracted link with purpose-specific flow completion (E4). The email capture + link-follow steps are PART of the flow's `.spec.ts`, not a separate test — the flow executor at U6 runs them as written. The `expected_user_effect` block for an email-involving flow should include `{ kind: "network_request", value: "email captured by Mailpit" }` plus the effect of the link follow (e.g., `{ kind: "url_change", value: "post-signup URL matches /dashboard" }`).

**Grow the intuition map per authored flow.** Same duty as U2, once per distilled flow: call the `intuition-map-lifecycle` skill's `grow` verb with the flow's elements — upserted as `user_verdict: confirmed` entries carrying `source: user-flow`. A distilled flow survived U4 because it serves the persona and objectives the user gave at U0, so it carries the same authority as the literal, and BOTH of U2's ask-instead-of-upsert cases apply unchanged. A clash with an existing confirmed entry asks a targeted question; it never overwrites silently. And the caller duty is if anything heavier here than at U2 — these flows were distilled from explorer proposals rather than written by the user, so their selector-to-`element_id` extraction is a further inference — you mark any element you are unsure of `ambiguous: true` (or `extraction_confidence: low`/`unknown`) exactly as at U2. A marked element is never upserted; it routes to an `ambiguous-extraction` question instead. An unmarked element is taken as certain, so an unsure extraction left unmarked is a silent wrong entry, not an error you will see.
