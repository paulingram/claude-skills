---
name: root-cause-test-failures
description: Use when running, debugging, or triaging any Playwright user-flow test or live dev-API integration test. Triggers - any test failure, a flaky test, you are about to retry a test without diagnosing it, you are about to propose a fix without an evidence trail, or you find yourself reaching for "probably" / "must be" / "seems like" / "obviously" to explain why something deviated from expected. Also use before every test run to write the per-step expectation that the failure-mode analysis will measure against. Mandatory whenever the architect-team Phase 3 review gate or Phase 5 integration loop runs tests.
---

# Root-Cause Test Failures — Predict, Trace, Loop Three Times

When a test fails, the product code is wrong, or the test is wrong. Until evidence says which, EVERY proposed cause is a guess. This skill makes guessing structurally hard.

Three disciplines:

1. **Predict before you test.** For every Playwright user-flow test and every dev-API integration test, write down what each step should produce — DOM state, URL, API response shape, DB / queue side-effect — BEFORE the test runs. Without a prediction, you cannot detect deviation; you can only detect "red".
2. **Refuse to rationalize.** When a test deviates from prediction, "the most likely cause" is not allowed without evidence. Every candidate cause must be supported by a log line, a captured payload, a stack frame, a screenshot, a diff against a known-good run, or a reproduction recipe.
3. **Three passes, minimum.** Run the root-cause loop three times before claiming you understand the failure. Pass 1 traces data forward; Pass 2 traces calls backward; Pass 3 falsifies. If the three passes converge on the same root cause, you have it. If they diverge, run a fourth pass against the strongest remaining candidate.

This skill builds on `superpowers:systematic-debugging` and operationalizes its principles inside the architect-team review-gate and escalation conventions.

## Phase A — Predict expected behavior BEFORE running the test

For every test (Playwright or integration), write the per-step expectation to `<test-output-dir>/expectations/<test-id>.json` **before** the test executes. The expectation file is mandatory; the review-gate evidence file (per `team-spawning-and-review-gates`) MUST reference its path.

### Schema

```json
{
  "test_id": "test_first_time_visitor_completes_first_login",
  "test_kind": "playwright" | "integration" | "live-dev",
  "feature": "login-flow",
  "predicted_at": "<ISO 8601 UTC>",
  "steps": [
    {
      "step": 1,
      "action": "page.goto('/login')",
      "expected": {
        "url": "/login",
        "visible_anchor": "role=heading[name=\"Sign in\"]",
        "absent": ["role=alert", "role=progressbar"]
      }
    },
    {
      "step": 2,
      "action": "page.fill('email', 'test@example.com')",
      "expected": {
        "form_state": { "email": "test@example.com", "submit_disabled": true }
      }
    },
    {
      "step": 3,
      "action": "page.click('Sign in')",
      "expected": {
        "api_request": { "method": "POST", "url": "/api/auth/login", "body_includes": ["email", "password"] },
        "api_response": { "status": 200, "body_shape": { "token": "string", "user": "object" } },
        "side_effect": { "cookie_set": "session=*", "audit_log_event": "user_login" },
        "url_after": "/dashboard?welcome=1",
        "visible_anchor_after": "role=banner >> text=Welcome, test@example.com"
      }
    }
  ]
}
```

For dev-API integration tests, the per-step `expected` block adds: `request_payload`, `response_assertions` (status, headers, body shape, body values), `side_effect_assertions` (DB rows, queue messages, file artifacts), `audit_log_assertions` (event name, fields, actor).

### Where the expectations come from

In priority order:
1. The Phase 1 acceptance criteria for the requirement under test (the coverage map's `acceptance_criteria` field).
2. The journey map's `steps[]` and `failure_branches[]` (per `playwright-user-flows` Step 6).
3. The dev-API integration test plan's response + side-effect assertions (per `dev-api-integration-testing`).
4. The interactivity inventory's `success_visible` and `errors[]` blocks.

If any expectation cannot be derived from these sources, the test author is inventing it — return to the relevant skill and fix the upstream artifact first. A prediction grounded only in the test author's intuition is not a prediction; it is a guess dressed as a contract.

### When the test passes

Each expectation is verified by the test author confirming the actual matches the expected for every step. The expectation file is referenced from the review-gate evidence; the verification is part of `spec_review: "pass"`.

### When the test fails

The expectation file is the FIRST artifact the root-cause loop reads. Phase B begins immediately.

## Phase B — The 3-pass root-cause loop (mandatory on every failure)

A failure means one (or more) of: the prediction was wrong, the code under test diverged from prediction, the environment differed, a dependency degraded, a timing/race surfaced, or a fixture was stale.

**DO NOT propose a cause without running the full loop.** Three passes minimum, regardless of how confident you feel after pass 1. The point of multiple passes is to falsify your first instinct.

### Pass 1 — Forward data-flow trace (input → user-visible result)

Start from the test's input. Trace the data forward through every component, function, request, queue, service, and DB call until it arrives at the user-visible (or API-visible) result. At each hop, capture the ACTUAL value and compare it against the EXPECTED value from Phase A.

Instrumentation:
- Playwright: `page.on('request' | 'response' | 'console' | 'pageerror')`, `--trace on`, screenshots at each `expect` boundary, structured logs at every component render.
- Integration: capture full request/response bodies, query the DB at every checkpoint where a side-effect was predicted, tail the audit log.
- Live-dev: include the dev-API's request ID in every log line so the failure can be cross-referenced against server-side traces.

Output: a numbered list of every hop where actual ≠ expected, with the captured evidence at that hop. **No hop is "obviously fine" — verify each.** If pass 1 ends without a divergence found, the failing assertion itself is the divergence and pass 2 begins from there.

### Pass 2 — Backward call-flow trace (result → input)

Start from the failing assertion. Walk backward up the call stack and the code paths the test traversed. At each frame ask: "What had to be true for this line to execute? Was it true? Where was that condition computed?"

- Playwright: which component rendered the failing element? What props/state did it receive? Which hook fed those? Which API response populated the hook? Use React DevTools / Vue DevTools traces; for SSR-rendered failures, capture the server-rendered HTML and compare to the hydrated result.
- Integration: which handler returned the failing response? Which middleware decorated it? Which DB query produced its input? Which migration last touched the schema? When did that migration land vs the test fixture's seed time?

Output: an annotated call graph from failing assertion back to test input, with the source location (`file:line`) of every divergence and a captured value at each node.

### Pass 3 — Alternative-hypotheses sweep (try to falsify the leading theory)

Pass 1 + Pass 2 will usually produce a leading hypothesis. Pass 3 EXPLICITLY tries to falsify it. Consider all of these, even if some feel irrelevant:

- **Race conditions** — does the failure reproduce only when X completes before Y? Run the same test 10 times back-to-back; if pass rate is < 100%, you have a race, not a deterministic bug.
- **Environment differences** — was this test run against the same dev API as the last green run? Compare env files, feature flags, secrets, build SHA, schema-migration head.
- **Fixture / test data drift** — was the seeded dataset different? Re-seed and re-run. Was a prior test's mutation not rolled back?
- **Caching / stale state** — browser cache, CDN cache, query cache (react-query / SWR / Apollo), DB read-replica lag, CDN-edge stale content.
- **Time / locale / timezone** — the test asserts a date format; the dev API is in a different timezone; DST boundary; a `now()` call rounded across midnight.
- **Concurrency** — a sibling test ran in parallel and mutated shared state (a global feature flag, a user record, a queue).
- **Browser / runtime differences** — chromium vs the user's browser, JS engine version, Playwright version diff against the prior green run.
- **Test-author error** — the Phase A prediction was actually wrong. The expected behavior was misread from the spec, or the spec changed and the prediction did not. This is a valid finding and the fix is to the prediction file, not the product.
- **Multiple simultaneous causes** — the symptom has MORE THAN ONE independent root cause. A failure on a multi-stage pathway (a value travelling source → build → bundle → deploy → runtime) can be broken at several stages at once; finding one cause does not mean you found them all. This is the EXPECTED case on a never-before-run (greenfield) pathway, where no stage is proven. When Pass 1 or Pass 2 finds a defect, do not stop — keep tracing the rest of the pathway; a found defect raises, not lowers, the prior that sibling defects exist. If the verify loop for this failure is expensive (a deploy, a rebuild, a slow CI run), STOP and apply `expensive-verification-debugging` — audit the whole pathway and batch every fix before spending a cycle, rather than confirming one cause per expensive cycle.

If Pass 3 confirms the Pass 1+2 hypothesis (you can falsify every alternative; you cannot falsify the leading hypothesis) → root cause identified. If Pass 3 surfaces a stronger candidate → run a fourth pass against it. Loop until the strongest surviving hypothesis is supported by evidence from at least two of the three passes. If Pass 3 surfaces ADDITIONAL independent causes (not a stronger single candidate but genuine siblings), every one of them is a root cause — record them all; a fix that resolves only one leaves the symptom live.

### Output — the RCA artifact

Persist `<test-output-dir>/rca/<test-id>-<timestamp>.json`:

```json
{
  "schema_version": 1,
  "test_id": "test_first_time_visitor_completes_first_login",
  "failed_at": "<ISO 8601 UTC>",
  "failure_summary": "user-name banner never rendered; URL did reach /dashboard?welcome=1",
  "expectation_at_failure_step": "<reference to step N in expectations/<test-id>.json>",
  "actual_at_failure_step": "<observed value + evidence path>",
  "passes": [
    {
      "pass": 1,
      "kind": "forward-data-flow",
      "hops_checked": ["LoginForm.submit", "useAuth.login", "fetch", "POST /api/auth/login", "AuthContext.setUser", "Banner render"],
      "first_divergence": "AuthContext received user.name=null from POST /api/auth/login response",
      "evidence": ["captures/response-login-200.json", "logs/auth-context-debug.log:42"]
    },
    {
      "pass": 2,
      "kind": "backward-call-flow",
      "call_graph_root": "Banner.tsx:42",
      "divergences": [
        { "frame": "Banner.tsx:42", "expected": "user.name string", "actual": "null", "source": "AuthContext.user" },
        { "frame": "auth/login.py:118", "expected": "user.name from DB row", "actual": "row.full_name is null for soft-deleted accounts" }
      ]
    },
    {
      "pass": 3,
      "kind": "alternative-hypotheses",
      "considered": ["race", "env-diff", "fixture-drift", "cache", "timezone", "concurrency", "browser-diff", "test-author-error"],
      "falsified": [
        { "hypothesis": "race", "evidence": "10 consecutive runs all fail at same step" },
        { "hypothesis": "fixture-drift", "evidence": "re-seeded and re-ran; same result" },
        { "hypothesis": "test-author-error", "evidence": "spec line 47 requires user.name in header" }
      ],
      "remaining_hypothesis": "product-bug: soft-deleted account path returns user.name=null"
    }
  ],
  "root_cause": {
    "category": "product-bug",
    "summary": "POST /api/auth/login returns user.name=null when the matched account row is soft-deleted (deleted_at IS NOT NULL); the login handler does not filter soft-deleted accounts before constructing the response.",
    "evidence": [
      "auth/login.py:118 — query lacks WHERE deleted_at IS NULL",
      "captures/response-login-200.json — body.user.name == null",
      "fixtures/seed.sql:204 — test account has deleted_at set"
    ]
  },
  "fix_owner": "architect-team",
  "fix_strategy": "Route to architect; not a teammate-local fix because the soft-delete semantics are referenced in 4 other coverage-map entries (REQ-012, REQ-019, REQ-031, REQ-044) and need a unified treatment."
}
```

Every field is required; missing fields = the loop is not done.

## Phase C — Escalation when a real product bug is identified

If the RCA category is `product-bug` (the code under test is wrong, not the test):

1. The teammate or integration agent does **NOT propose a fix itself**. The fix routes through the architect's team-spawn cycle.
2. Write an escalation handoff to:

   ```
   <cwd>/.architect-team/handoffs/<team>-to-architect-rca-<test-id>-<timestamp>.md
   ```

   Contents (MUST include all):
   - The test ID and a link to the RCA artifact JSON.
   - A one-paragraph summary of the bug in **product terms** (what users experience), not implementation terms ("logged-in users see no name in the header after login because POST /api/auth/login returns null in user.name when the email matches a soft-deleted account").
   - A reproduction recipe: exact dev-API state, exact Playwright steps (or curl invocation), exact env / build SHA, exact fixture seed used.
   - Affected requirements: list every entry from `coverage-map.json` this breaks (so the architect can scope the fix correctly).
   - **Suggested area of investigation only — NOT a proposed fix.** The architect convenes the team to design the fix per the standard Phase 2 → Phase 5 dev loops.

3. **Write a solution requirement** (mandatory, not optional) per `team-spawning-and-review-gates`'s `## Solution Requirements` section to:

   ```
   <cwd>/.architect-team/solution-requirements/SR-<test-id>-<timestamp>.json
   ```

   This is the structured-JSON twin of the markdown handoff — same content, machine-readable. The orchestrator picks the SR up on its next pickup pass and routes it through `diagnostic-research-team` (three parallel `diagnostic-researcher` agents + system-architect review) BEFORE spawning the Phase 2 fix team. Your originating RCA is one input among several that the three researchers will independently verify, falsify, or extend. The fix team is then spawned with the consolidated diagnostic plan as a required input.

   `origin.kind` is `"rca-product-bug"`. `evidence` includes the RCA artifact path. `acceptance_criteria` lists the test that surfaced the bug plus any related coverage-map requirements the fix must restore.

4. Signal idle. The orchestrator picks up the SR (and the handoff for human context), invokes `diagnostic-research-team` to produce a consolidated diagnostic plan, then spawns the fix team automatically with the plan as a required input. The fix is routed through Phase 2 → Phase 5 with the full review-gate cycle. The failing test is re-run as part of Phase 5; when it passes, the SR is marked `resolved` and the ORIGINATING teammate's task unblocks. Your RCA is not discarded — it is the seed input the three researchers verify against; if the consolidated plan promotes a different root cause, that promotion is backed by independent cross-draft evidence, not a silent override.

If the RCA category is `test-author-error`:

1. Update the Phase A expectation file with the corrected prediction.
2. Document **why the original expectation was wrong** in a short note inside the expectation file's frontmatter or sidecar (often: misread of the spec, stale ROUTE_MAP entry, journey map referenced an inventory ID that was renamed, etc.).
3. Re-run the test. If it now passes, attach the corrected expectation file path to the review-gate evidence and proceed.

If the RCA category is `environment` / `fixture-drift` / `race` / `cache`:

1. Document the trigger (specifically: which env var / which fixture / which race window / which cache layer).
2. Document the fix (env update, fixture re-seed, retry policy with explicit backoff, cache invalidation).
3. Document the **prevention strategy** (a test, a check, a CI guard) so the same class of failure does not recur silently.
4. Re-run.

## Where this skill plugs into the pipeline

- **Phase 3 — Team review gate.** Every test in the teammate's slice MUST have a corresponding `expectations/<test-id>.json`. The review-gate evidence (per `team-spawning-and-review-gates`) references it. A failed test in the teammate's slice triggers Phase B before the teammate may attempt to fix anything.
- **Phase 5 — Cross-layer integration.** The integration agent applies this skill to every dev-API integration test and every Playwright user-flow test it runs. On failure, the integration agent does NOT silently retry; it runs the 3-pass loop and either fixes the expectation (test-author error), the env (env category), or escalates (product bug).
- **Phase 7 — Master review.** Every RCA artifact produced during the build is indexed; the master review checks that each `product-bug` finding has a corresponding closed task in the coverage map.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "I know what this is — it's just X" | "I know" without an evidence trail = a guess. Run the 3-pass loop and let the evidence either confirm or refute X. The evidence trail is also what the architect needs to scope the fix. |
| "Pass 1 told me everything; passes 2 and 3 are overkill" | Pass 1 is the most common source of premature certainty. Pass 2 and Pass 3 exist to falsify the Pass 1 conclusion. Skip them and you ship the wrong fix. |
| "We're under deadline pressure" | Wrong fixes ship the same bug back to users a week later. The 3-pass loop is 15–30 minutes; a wrong-cause patch routinely burns a day re-debugging. The pressure argument is exactly when the discipline matters most. |
| "I'll just retry the test — it's probably flaky" | "Probably flaky" without an RCA is the dominant cause of silent regressions. Either identify the race / fixture / env trigger and document it, or escalate. Retry-until-green is an anti-discipline. |
| "I can write the prediction after running the test" | Then the prediction is contaminated by the actual result — you have no baseline against which to detect deviation. Predictions are written before. |
| "I'll skip the RCA artifact and just tell the team verbally" | The artifact is the audit trail AND the structuring tool. You cannot half-fill the JSON without noticing your reasoning has a gap. A verbal hand-off lets the gap survive. |
| "The bug is obvious; we do not need to involve the architect" | Bug-obvious-to-developer ≠ root-cause-clear-to-architect. The architect's job is to route the fix through the dev loops with proper spec attribution and coverage updates. Skipping that step breaks the audit chain and the master-review will flag it later. |
| "I'll just add a null-check / try-catch / fallback to make the test pass" | That is a symptom patch, not a fix. Phase B Pass 2 exists specifically to find the upstream cause (why is it null in the first place?). If you patch the symptom, the upstream cause stays and breaks the next test that hits the same code path. |
| "The expectation file is overhead for a small test" | A small test has a small expectation file (one or two steps). Either way, the expectation file is the input to Phase B — without it, RCA has nothing to compare against. |
| "I'll loop twice and call it done" | Two passes is one short of the minimum. The third pass exists to falsify, not to confirm. Two-pass discipline produces confirmation bias dressed as analysis. |

## Red flags — STOP and re-run the loop

These are the symptoms that you are about to skip the discipline. Each means: stop, complete the missing pass, produce the missing artifact, then re-evaluate.

- You used the words "probably", "must be", "seems like", "obviously", "I think" without an evidence citation.
- You ran fewer than 3 passes.
- Your candidate root cause is supported by intuition or pattern-matching, not by a captured payload / log / stack frame / file:line reference.
- Your fix proposal addresses a symptom (e.g., "add a null check", "wrap in try/catch", "add a retry") rather than the upstream cause.
- You skipped Phase A (no expectation file exists for this test).
- You proposed a fix without writing the RCA artifact.
- You retried the test without recording why the prior run failed.
- The RCA artifact's `passes[]` array has fewer than 3 entries.
- The RCA artifact's `evidence[]` arrays are empty or contain only prose.
