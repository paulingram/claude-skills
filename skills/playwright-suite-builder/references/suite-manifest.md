# The suite manifest — the durable registry

One manifest per frontend codebase, at `<e2e-dir>/suite-manifest.json`,
**committed in the target repo**. It is the single artifact answering "which
tests are written", it binds each test to the intuition-map elements it covers,
and it is what a full-integration run enumerates.

Top-level fields — `schema_version`, `e2e_dir`, `personas[]`, `last_built`,
`prod_exceptions[]`, and **`tests[]`**, the array the per-test entries below live
in. All six are REQUIRED; a manifest missing any one of them is a blocking
validation finding, and `tests[]` is the one most easily forgotten because the
table describes its contents rather than the array. Per-test entries:

| Field | Meaning |
|---|---|
| `file` | path to the spec, relative to the repo root |
| `test_names[]` | the test titles inside that file |
| `persona` | which persona slug this test is for |
| `kind` | `journey`, `debug-flow`, or `prod-check` |
| `source` | `user-flow`, `explorer`, `gap-fill`, `bug-path`, or `pre-existing` |
| `covers_elements[]` | intuition-map `element_id`s this test exercises |
| `covers_routes[]` | routes this test traverses |
| `safety` | `dev` or `prod` — the classifier verdict, bound per test |
| `mutates_data` | bool — the classifier's mutation finding |
| `origin_ref` | SR path / bug slug, or `null` |

**These fields are STRINGS, not merely present.** Every per-test field except
`mutates_data` (a real boolean) and `origin_ref` (a string or `null`) must be a
non-blank string. A falsy non-string value — `false`, `0`, `[]` — is treated as
**ABSENT**, not as a value, and blocks.

That distinction is not pedantry. A `teardown: false` once passed the
present-not-blank check, because `false` is neither `None` nor `""`, and it
authorized a production-mutating test. The JSON looks like it says something; the
validator read it as saying nothing. Write the string.

The schema, its validation, and the `verify-suite-manifest` ship check are
implemented by the stdlib-only engine at
`scripts/playwright_suite/manifest.py`. The skill is the contract; the engine is
the mechanism.
