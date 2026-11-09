# Phase P8 — Dev/prod classification

Invoke `skills/test-prod-safety-classifier` per test and bind its verdict INTO
the manifest — `safety` (`dev` / `prod`) and `mutates_data` (bool) are recorded
per entry. The classifier is the existing discipline and the existing annotation
contract; this phase is where its verdict stops being a report and becomes a
registry fact.

**The prod project is default-deny.** It contains `kind` `prod-check` tests only
— navigation and assertion, no mutation. A test with no recorded classification
lands dev-only and carries `safety` `dev`; unclassified never means "probably
fine".

A `mutates_data` true test enters the prod project ONLY through a
`prod_exceptions[]` entry carrying all three of:

1. **The user's recorded authorization** — who authorized it, when, and why. Not
   an agent's judgment that it seemed safe.
2. **A test-only data tag** per the `it-<prefix>` convention from
   `skills/dev-api-integration-testing`, so anything the test creates is
   identifiable as test data.
3. **Mandatory teardown** — declared in the exception and implemented in the
   test.

An exception missing any of the three is a blocking finding, not a warning.
Derive read-only `prod-check` variants of the smoke-worthy journeys here rather
than promoting mutating tests — a prod smoke suite is built from reads, not from
writes made careful.
