---
name: playwright-user-flows
description: Use when authoring or running Playwright tests for any feature with a frontend component, especially during Phase 5 integration. Mandates a workflow that first establishes who the users are and what they are trying to achieve (escalating to the user via structured questions when intent cannot be derived from product docs/requirements), then exhaustively enumerates every link, button, form input, modal trigger, keyboard shortcut, drag target, and conditional render gate plus the API contracts each touches, then authors tests organized around user journeys (page.goto / click / fill / waitFor) that assert visible state. Rejects endpoint-only testing as a substitute for user-flow testing. Coverage verification proves every user objective, every interactive element, and every error response is exercised.
user-invocable: false
---

# Playwright User Flows — White-Box, Real-User

Frontend tests fail in production when they test what the developer remembered, not what the user can actually do — and what the user can actually do is shaped by **who** the user is and **what they are trying to achieve**, not just which elements the developer made interactive. This skill enforces four disciplines:

1. **Know the user, know the goal.** Before reading code, establish who the user base is and what each persona is trying to accomplish. If the product docs / requirements / OpenSpec proposal do not make this clear, **ask the user** — do not guess.
2. **Read the code exhaustively.** Enumerate every interactive element (link, button, form input of every type, modal trigger, drag target, keyboard shortcut, conditional render gate) and every API call the feature touches, from the actual source. No exceptions, no "the obvious ones".
3. **Test as the user, test the user's goals.** Every test simulates a real human — `page.click`, `page.fill`, `page.waitFor` — and is named after a user achievement, not a widget. Tests are organized by user journey: the sequence a real user follows to accomplish a real goal. Direct API calls are never a substitute for user-flow tests.
4. **Test against the real backend, not fake data.** For any feature that spans both a frontend and a backend, the user-flow tests MUST exercise the **real running backend** with real data flow front-to-back — the frontend's HTTP calls hit a real server, real DB / queue / cache, real responses. A Playwright test that clicks through the UI correctly but talks to a mocked backend (canned `page.route` happy-path responses, MSW handlers, an in-memory fake API server, or hardcoded response fixtures) has verified nothing about whether the two layers actually work together. This discipline is the DEFAULT — it applies unless the requirements *explicitly* authorize isolated / mock-backed testing for a named requirement. See Phase B → "Real backend by default".

## Phase A — Examination (mandatory, before any test code)

> **STOP.** Before acting under this section, Read `skills/playwright-user-flows/references/phase-a-examination-mandatory-before-any-test-code.md` and execute it in full. Do not work from memory.

For each feature/flow under test:

## Phase B — Test authoring (informed by the inventory AND the user-journey map)

> **STOP.** Before acting under this section, Read `skills/playwright-user-flows/references/phase-b-test-authoring-informed-by-the-inventory-and-the-use.md` and execute it in full. Do not work from memory.

**Choose the venue before authoring against it (v3.66.0).** Apply the `verification-planning` skill first: enumerate local run / dev environment / replay / seeded fixture / production for the claims these flows verify, prove which venue each depends on, and record the `verification_plan`. The real-backend rule below stands — for a `both`-layer feature the deployed dev environment IS the faithful venue for front-to-back claims, and the plan records why; the cheaper venues still settle first every claim they can (the handler logic locally, the failing input by replay, the empty-state by a seeded fixture), and a live environment the flows need is the run's to PROVIDE (`references/local-dev-test-discipline.md`), never a reason to wait.

## Phase C — Coverage verification (before submitting tests)

> **STOP.** Before acting under this section, Read `skills/playwright-user-flows/references/phase-c-coverage-verification-before-submitting-tests.md` and execute it in full. Do not work from memory.

Run an automated coverage check across two layers — user-intent first, then mechanics. User-intent gaps are blocking even if every mechanical gap is closed.

## Anti-pattern rationalizations to reject

> **STOP.** Before acting under this section, Read `skills/playwright-user-flows/references/anti-pattern-rationalizations-to-reject.md` and execute it in full. Do not work from memory.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Phase A — Examination (mandatory, before any test code)` | `skills/playwright-user-flows/references/phase-a-examination-mandatory-before-any-test-code.md` | on demand |
| `Phase B — Test authoring (informed by the inventory AND the user-journey map)` | `skills/playwright-user-flows/references/phase-b-test-authoring-informed-by-the-inventory-and-the-use.md` | on demand |
| `Phase C — Coverage verification (before submitting tests)` | `skills/playwright-user-flows/references/phase-c-coverage-verification-before-submitting-tests.md` | on demand |
| `Anti-pattern rationalizations to reject` | `skills/playwright-user-flows/references/anti-pattern-rationalizations-to-reject.md` | on demand |
