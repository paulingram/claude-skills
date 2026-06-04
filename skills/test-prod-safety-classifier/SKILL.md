---
name: test-prod-safety-classifier
description: Evaluate every Playwright / QA test file in a codebase and classify it `@prod-safe` (only reads — safe against ANY deployed environment including production) or `@not-prod-safe` (contains mutations — POST/PUT/PATCH/DELETE / form submits / file uploads / DB writes / external side effects). Two modes — MASS-CLASSIFY scans every test under a glob, produces a per-file report, and (with `--write-annotations`) injects the top-of-file annotation into each file; AUTO-CLASSIFY runs on every new test file written at Phase 3 review gate, gates the slice on a missing annotation, and emits a `prod-safety-classification-required` SR when ambiguous. Both modes feed the 15th Layer 3 tool `verify_test_prod_safety_classification` which gates Phase 5 — a `@not-prod-safe` test scheduled against a production URL is `prod-deployment-runs-unsafe-test`, a CRITICAL safety violation.
---

# Test Prod-Safety Classifier

When deploying to production, NO test may mutate data. Every Playwright and QA test MUST be classified `@prod-safe` (only reads) or `@not-prod-safe` (contains mutations); production environments may only run `@prod-safe` tests. This skill provides the evaluation + classification + annotation injection for every existing test in the codebase, and the auto-classify gate for every new test on a go-forward basis.

## The failure shape this closes

> "update such that any form of playright and QA testing knows that when deploying to production, any testing must be non-destructive and perform no mutations to any data / no changes. So we will want to ensure this. also we will want every test written to be properly classified into prod safe or not. give us a skill to evaluate the current tests and mass classify them and then auto classify on go forward basis"

Existing playwright-user-flows discipline tests against live dev backends. Existing v2.4.0 verified-live discipline mandates a deployed URL. Neither distinguishes "dev/staging deployed URL" from "production deployed URL." A test that creates a matter, sends an invite email, uploads a document — perfectly valid against dev — would corrupt production data if accidentally pointed at the prod URL. v2.17.0 makes this structurally impossible.

## Two modes

### Mode 1 — Mass-classify (on-demand)

Invoked via `/architect-team:classify-test-prod-safety [<glob>] [--write-annotations] [--dry-run]`. Default is `--dry-run` (report only); `--write-annotations` modifies test files in-place to inject the annotation.

**Per-file algorithm:**

1. **Read the file.** Strip BOM, normalize line endings.
2. **Check for existing annotation.** Scan the first 20 lines for any of `_PROD_SAFE_ANNOTATIONS` or `_NOT_PROD_SAFE_ANNOTATIONS` (case-insensitive substring match). If present, record the annotation; skip injection.
3. **Auto-classify** by scanning the file body for `_MUTATION_PATTERNS` and `_READ_ONLY_PATTERNS`:
   - **`not-prod-safe`** — any mutation hit (POST/PUT/PATCH/DELETE / form submit / file upload / DB write / cloud storage put / sendgrid send / etc.)
   - **`prod-safe`** — no mutation hits AND at least one read-only hit (`page.goto`, `page.locator`, `expect()`, GET, etc.)
   - **`ambiguous`** — no mutation hits AND no read-only hits (the file might call a helper function that mutates; runtime dispatch through a switch; etc.)
4. **Reconcile.** If the file has an existing annotation AND it disagrees with the auto-classification, emit a `classification-mismatch` warning. The skill defers to the annotation (it's a human decision), but flags the gap.
5. **Inject (when `--write-annotations`).** Add the annotation as a top-of-file comment in the file's primary comment syntax:
   - JavaScript/TypeScript: `// @prod-safe` or `// @not-prod-safe`
   - Python: `# @prod-safe` or `# @not-prod-safe`
   - Ruby: `# @prod-safe` or `# @not-prod-safe`
   The annotation is inserted as the FIRST non-shebang, non-blank line.
6. **Escalate ambiguous tests.** Ambiguous files do NOT get auto-annotated; instead, they're surfaced in the report with a structured question for the user.

**Output artifact** (`<workspace>/.architect-team/test-prod-safety/classification-report-<ts>.json`):

```json
{
  "ran_at": "<ISO 8601>",
  "glob_or_path": "<the input pattern>",
  "total_files_scanned": 42,
  "classifications": {
    "prod-safe": 12,
    "not-prod-safe": 23,
    "ambiguous": 7
  },
  "annotations_written": 35,
  "files": [
    {
      "path": "tests/auth/login.spec.ts",
      "existing_annotation": null,
      "auto_classification": "prod-safe",
      "mutation_hits": [],
      "readonly_hits": ["page-goto", "to-have-url", "to-be-visible"],
      "annotation_written": "@prod-safe",
      "_ambiguity_reason": null
    },
    {
      "path": "tests/matter/create.spec.ts",
      "existing_annotation": null,
      "auto_classification": "not-prod-safe",
      "mutation_hits": ["page-request-post", "set-input-files"],
      "readonly_hits": ["page-goto", "expect-call"],
      "annotation_written": "@not-prod-safe",
      "_ambiguity_reason": null
    },
    {
      "path": "tests/dashboard/helpers/setup.spec.ts",
      "existing_annotation": null,
      "auto_classification": "ambiguous",
      "mutation_hits": [],
      "readonly_hits": [],
      "annotation_written": null,
      "_ambiguity_reason": "no mutation OR read-only patterns detected; file may call helper that mutates — needs human review"
    }
  ]
}
```

### Mode 2 — Auto-classify (Phase 3 gate)

Runs on every test file written or modified during a pipeline run. Gates the slice's Phase 3 review-evidence write.

**Per-file algorithm:**

1. **Read the file** (same as Mode 1).
2. **Check for annotation.** If missing → emit gap with `severity: "unclassified-test"`; suggest the auto-classification in `suggested_annotation`. The implementer agent MUST add the annotation before marking the slice complete.
3. **If annotation present**, run the v2.17.0 Layer 3 tool `verify_test_prod_safety_classification` to detect classification-mismatch / mutation-in-prod-safe-test / unclassified-test.
4. **If ambiguous** AND no annotation present → emit SR with `origin.kind: "prod-safety-classification-required"` so the user reviews + decides.

The auto-classifier is invoked from the Phase 3 review-gate hook. A slice cannot mark complete with an unclassified test.

## Cross-references

- `skills/common-pipeline-conventions/SKILL.md` `## Prod-safe test classification discipline (v2.17.0)` — the canonical home of the rule + the 4 severities + the SR origin kind + the annotation contract.
- `hooks/vao_tools.py::verify_test_prod_safety_classification` — the 15th Layer 3 tool (Mode 2's gate).
- `hooks/vao_tools.py::_MUTATION_PATTERNS` + `_READ_ONLY_PATTERNS` + `_PROD_URL_EXCLUSIONS` + `_PROD_SAFE_ANNOTATIONS` + `_NOT_PROD_SAFE_ANNOTATIONS` — the canonical pattern allowlists this skill scans against.
- `commands/classify-test-prod-safety.md` — the slash command entry point for Mode 1.
- `agents/frontend.md` + `agents/backend.md` `## Prod-safe test classification discipline (v2.17.0)` — every authored test carries the annotation.
- `agents/qa-replayer.md` `## Prod-safe test classification discipline (v2.17.0)` — re-replays against prod-labeled URL filter to `@prod-safe` only.
- `agents/bug-replicator.md` `## Prod-safe test classification discipline (v2.17.0)` — repro tests carry the annotation per their mutation profile.
- New SR origin kind `prod-safety-classification-required` joins the canonical catalog.

## When this skill runs

The skill is invoked:

1. **On-demand** via `/architect-team:classify-test-prod-safety <glob>` — Mode 1 mass-classify.
2. **At Phase 3 review gate** — Mode 2 auto-classify; every new test file is checked.
3. **At Phase 5 cross-layer integration** — Mode 2 verification; gates the run on a properly classified, environment-appropriate test suite.
4. **At Phase B6 qa-replayer re-replay** — when the deployed dev URL is a production URL (`!_is_local_env_url(url) AND !any(p in url for p in _PROD_URL_EXCLUSIONS)`), the re-replay filters to `@prod-safe` tests only.

## Operating rules (non-negotiable)

1. **Every test file MUST be annotated.** No exceptions; unclassified tests do not ship.
2. **`@prod-safe` tests cannot contain mutation patterns.** The classifier scans the file body, not just the annotation.
3. **`@not-prod-safe` tests cannot run against production URLs.** The Phase 5 gate enforces this.
4. **Ambiguous classifications escalate to the user.** The skill never silently guesses for an unclear file.
5. **Mode 1 is `--dry-run` by default.** `--write-annotations` is opt-in so the user can review the report before files are modified.
6. **The annotation is the SOURCE OF TRUTH.** When annotation and auto-classifier disagree, the annotation wins (it's a human decision) BUT the mismatch is reported.
7. **Read-only on source by default.** Modifications happen ONLY in Mode 1's `--write-annotations` path or at Phase 3 auto-annotate (with user consent).
