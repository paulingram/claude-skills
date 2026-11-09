# Prod-safe test classification discipline (v2.17.0)

Every Playwright and QA test MUST carry a top-of-file classification annotation — `@prod-safe` (only reads; safe to run against ANY deployed environment including production) or `@not-prod-safe` (contains mutations — POST/PUT/PATCH/DELETE, form submits, DB writes, file uploads, email sends, etc.). When a test run targets a production-labeled URL, ONLY `@prod-safe` tests may execute. Unclassified tests are a discipline failure; running `@not-prod-safe` tests against production is a critical safety failure.

**Failure shape** (verbatim case in CHANGELOG v2.17.0): *"when deploying to production, any testing must be non-destructive and perform no mutations to any data / no changes … every test written to be properly classified into prod safe or not … a skill to evaluate the current tests and mass classify them and then auto classify"*. The prior disciplines mandate the live dev backend / deployed URL but none distinguishes a dev URL from a production URL — a test that creates a matter or sends an invite email is valid against dev but would corrupt production data if pointed at the prod URL. v2.17.0 makes that structurally impossible.

### The 3 classifications

| Classification | Meaning | Safe-against |
|---|---|---|
| `@prod-safe` | Only read operations (page.goto / page.locator / expect / GET) | Any deployed environment including production |
| `@not-prod-safe` | Contains mutation patterns (POST/PUT/PATCH/DELETE / form submit / file upload / DB writes / email sends / etc.) | Dev / staging / local ONLY |
| `ambiguous` | Cannot be determined automatically (calls a helper function that might mutate; runtime dispatch through a switch; etc.) | Requires human review before classification |

### The annotation contract

Every test file MUST carry a top-of-file classification annotation as a comment in the file's primary comment syntax:

| Language | Annotation form |
|---|---|
| JavaScript / TypeScript | `// @prod-safe` or `// @not-prod-safe` (single-line) or `/** @prod-safe */` (block) |
| Python | `# @prod-safe` or `# @not-prod-safe` |
| Ruby | `# @prod-safe` or `# @not-prod-safe` |

The annotation MUST appear within the first 20 lines of the file (typically immediately after the imports). Anything below line 20 is not considered — the annotation is a top-of-file contract.

### The execution rule

When a test run's `run_target.url` matches a `_PROD_URL_PATTERNS` value (substring indicating production — `prod.`, `production.`, `.app`, `www.`, or simply any URL NOT matching the dev/staging/local exclusion list), the test runner MUST filter to `@prod-safe` tests only. Running `@not-prod-safe` tests against production fires `prod-deployment-runs-unsafe-test` — a critical safety violation.

### 4 named severities

| Severity | Trigger |
|---|---|
| `unclassified-test` | Test file has no `@prod-safe` AND no `@not-prod-safe` annotation in its first 20 lines |
| `prod-deployment-runs-unsafe-test` | A test annotated `@not-prod-safe` (or unclassified) was scheduled against a production URL (matches `_PROD_URL_PATTERNS`) |
| `mutation-in-prod-safe-test` | A test annotated `@prod-safe` contains a mutation pattern from `_MUTATION_PATTERNS` |
| `classification-mismatch` | Automatic classification (from scanning the file for mutation/read-only patterns) disagrees with the annotation |

### Canonical mutation signatures (`_MUTATION_PATTERNS`)

| Class | Patterns |
|---|---|
| **HTTP POST/PUT/PATCH/DELETE** | `page.request.post(`, `page.request.put(`, `page.request.patch(`, `page.request.delete(`, `axios.post(`, `axios.put(`, `axios.patch(`, `axios.delete(`, `fetch(... method: 'POST'`, `fetch(... method: 'PUT'`, `fetch(... method: 'DELETE'`, `fetch(... method: 'PATCH'` |
| **Form / button submission** | `page.click(...) // submit button`, `form.submit()`, `page.locator('button[type=submit]').click()`, `await form.submit()` |
| **File upload to live storage** | `page.setInputFiles`, multipart-form encoded uploads |
| **Direct DB writes** | `prisma.X.create(`, `prisma.X.update(`, `prisma.X.delete(`, `knex.insert(`, `knex.update(`, `knex.delete(`, `db.insert(`, `db.update(`, `db.delete(`, `INSERT INTO`, `UPDATE `, `DELETE FROM` |
| **Cloud storage mutations** | `PutObject`, `DeleteObject`, `bucket.upload`, `uploader.upload(`, `BlobClient.upload` |
| **External side effects** | `sendgrid.send`, `client.messages.create` (Twilio), `mailgun.send`, `stripe.charges.create`, `stripe.PaymentIntent.create` |

### Canonical read-only signatures (`_READ_ONLY_PATTERNS`)

`page.goto`, `page.locator`, `page.textContent`, `page.title`, `page.url`, `expect(`, `toHaveText`, `toBeVisible`, `toContain`, `toEqual`, `toHaveURL`, `await fetch( ... method: 'GET'` (default), `axios.get(`, `prisma.X.findUnique`, `prisma.X.findMany`, `knex.select`

### New SR origin kind

`prod-safety-classification-required` — fires from the `test-prod-safety-classifier` skill when a test file lacks an annotation OR has an ambiguous classification.

### Cross-references

- `hooks/vao_tools.py::verify_test_prod_safety_classification` — the 15th Layer 3 tool.
- `hooks/vao/prod_safety.py::_MUTATION_PATTERNS` + `_READ_ONLY_PATTERNS` + `_PROD_URL_EXCLUSIONS` + `_PROD_SAFE_ANNOTATIONS` + `_NOT_PROD_SAFE_ANNOTATIONS` (re-exported by `hooks/vao_tools.py`) — the canonical pattern allowlists.
- `skills/test-prod-safety-classifier/SKILL.md` (NEW v2.17.0) — the 31st skill; mass-classify mode (scan + annotate) and auto-classify mode (Phase 3 gate).
- `commands/classify-test-prod-safety.md` (NEW v2.17.0) — the 16th slash command; entry point for mass-classify mode.
- `agents/frontend.md` + `agents/backend.md` `## Prod-safe test classification discipline (v2.17.0)` — every authored test carries the annotation.
- `agents/qa-replayer.md` `## Prod-safe test classification discipline (v2.17.0)` — re-replays against prod-labeled URL filter to `@prod-safe` only.
- `agents/bug-replicator.md` `## Prod-safe test classification discipline (v2.17.0)` — repro tests carry the annotation per their mutation profile.
- `tests/fixtures/vao/prod-safe-test-classification-required.json` — verbatim canonical case (4 test files exercising each of the 4 severities).
- Companion to v2.6.0 live-data wiring (catches mock-state on the tested path) + v2.11.0 multi-persona path-coverage (verifies persona breadth) + v2.13.0 UX-test env sequencing (local-first then live-dev) — different axis, same root principle: tests must do the right thing in the right environment.
