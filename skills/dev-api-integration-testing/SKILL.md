---
name: dev-api-integration-testing
description: Use when authoring or running integration tests against a backend slice, especially during Phase 5 when verifying against a live dev API. Defines payload conventions, side-effect verification (DB / queue / file), dev-data fixture hygiene, idempotency, and the rule that the system under test runs against real dependencies — mock only what's truly external or non-deterministic.
---

# Dev-API Integration Testing

Backend tests that pass against mocks and fail against the live system are the most expensive bugs to discover. This skill enforces the discipline that integration tests run against the real dev API with real dev data, and verify real side effects.

## Where connection details live

The OpenSpec `design.md` for the change must include a `## Dev Environment` section with:

- Base URL of the dev API.
- Auth strategy (test user creds, service token, signed JWT).
- Database connection (read-only? read-write? which schema?).
- Queue / cache / object store endpoints.
- Cleanup strategy (test data prefix, transactional rollback, scheduled sweep).

Tests read these from the design artifact — never hard-code in test files.

## What "integration" means here

- The system under test (the backend service / module) runs against its REAL dependencies in the dev environment: real DB, real queues, real cache, real auth.
- Mock ONLY:
  - Truly external third parties (payment processors, email providers) — and only when the dev env doesn't have a sandbox.
  - Non-deterministic inputs (time, randomness, cloud-region routing) when assertion would otherwise flake.
- Everything else is real.

## Test structure

### Setup phase

- Create dev data with a per-test prefix (e.g., `it-<test_name>-<uuid>`) to make cleanup automatic and prevent cross-test contamination.
- Authenticate using the dev environment's test-user mechanism (NOT the production auth flow).

### Action phase

- One HTTP request per assertion when possible. Use `httpx` (or the project's existing async client).
- Capture the full request (method, URL, headers minus secrets, body) and response (status, headers, body) on failure for debug.

### Assertion phase

Three layers, all required for any state-changing endpoint:

1. **Response shape.** Status code + response body matches the schema in the design artifact. Use a schema validator (pydantic, marshmallow, zod-equivalent) — don't assert one field at a time.
2. **Side-effect verification.** The action actually changed the system:
   - DB row exists / updated / deleted (query directly).
   - Queue message published (consume from the queue or query the broker's API).
   - File written (read from the object store).
   - Cache entry set/invalidated.
3. **Audit/log effect** where applicable (audit trail row, log line, metric increment).

### Teardown phase

- Clean up the per-test prefix.
- If the test wrote to an external service that doesn't honor prefixes, register the resource with the cleanup registry so a periodic sweep removes it.

## Idempotency

Every test must be runnable twice in a row without failing on the second run. If the first run created data, the second run's setup must either reuse-or-recreate, or the teardown must have removed it.

This is non-negotiable — flaky tests rot the whole suite.

## Per-test expectations & failure handling

For every integration test (local OR live-dev), write a per-step expectation file BEFORE running the test, per `root-cause-test-failures`. The expectation file (`<test-output-dir>/expectations/<test-id>.json`) captures the request payload, response assertions (status / shape / values), side-effect assertions (DB rows, queue messages, files), and audit-log assertions — all of which are mandated above. On any failure, do NOT propose a fix until the 3-pass root-cause loop has run and produced an evidence-backed `rca/<test-id>-<ts>.json` artifact. "It's probably flaky" is forbidden — either identify the race / fixture / env trigger with evidence, or escalate via the RCA handoff if a product bug is found.

## Test naming

- Pattern: `test_<endpoint>_<scenario>` (e.g., `test_post_projects_creates_with_owner`, `test_post_projects_401_when_unauthenticated`).
- One scenario per test. Don't bundle happy-path and error cases in one function.

## Error path coverage

Cover EVERY error response the endpoint can return, drawn from the OpenSpec design artifact's response catalog:

- 400 / 422 validation errors (one test per failing validation rule).
- 401 unauthenticated.
- 403 unauthorized (right user, wrong role / missing permission).
- 404 not-found.
- 409 conflict.
- 429 rate-limited.
- 5xx via fault injection where possible.

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "I'll mock the DB to make the test fast" | Mocking the DB tests your assumptions about the ORM, not your code. Use the real DB in dev. |
| "The error responses are obvious — happy path is enough" | Error paths break production. Coverage of every documented error response is the bar. |
| "I'll skip side-effect verification — the 200 is enough" | A 200 with no side effect is a silent data-loss bug. Verify the row, the message, the file. |
| "Test data leaks are fine — dev gets reset" | Cross-test contamination causes flaky tests. Use the prefix discipline. |
| "I'll hard-code the dev URL" | The design artifact is the source. Read from it, so changing environments doesn't require a code edit. |
