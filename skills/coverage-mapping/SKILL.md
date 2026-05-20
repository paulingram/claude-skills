---
name: coverage-mapping
description: Use when building the Phase 1 coverage map, when verifying a team's slice in Phase 3, or when running the Phase 7 master review. Defines the coverage-map.json schema, how to populate it from OpenSpec specs and source requirements, how to detect uncovered requirements, and how to attribute commits to requirements for the final report.
---

# Coverage Mapping

The coverage map is the spine the entire pipeline hangs on. It translates source requirements into spec requirements, into scenarios, into acceptance criteria, into layers — and ultimately into commits and tests. If the coverage map is wrong or incomplete, Phase 7 will silently miss gaps.

## File location and format

`openspec/changes/<change-name>/coverage-map.json`:

```json
{
  "schema_version": 1,
  "change": "<change-name>",
  "generated_at": "<ISO 8601 UTC>",
  "entries": [
    {
      "source_requirement_id": "REQ-001",
      "source_excerpt": "<short verbatim quote from $REQ_DIR>",
      "spec_requirement_id": "spec.api.auth.login",
      "scenarios": ["spec.api.auth.login.happy", "spec.api.auth.login.invalid"],
      "acceptance_criteria": [
        "POST /auth/login with valid creds returns 200 with token",
        "POST /auth/login with invalid creds returns 401"
      ],
      "layer": "backend",
      "implementing_commits": [],
      "tests": { "unit": [], "integration": [], "e2e": [] },
      "demo_artifact": null,
      "status": "pending"
    }
  ]
}
```

### Field definitions

- `source_requirement_id` — stable ID assigned to each requirement in `$REQ_DIR`. If the source doesn't number them, the orchestrator assigns `REQ-001`, `REQ-002`, etc., in order of appearance.
- `source_excerpt` — verbatim short quote (max ~200 chars) so reviewers can confirm the mapping without opening `$REQ_DIR`.
- `spec_requirement_id` — the OpenSpec spec requirement that covers it. Run `openspec show <change> --json` to enumerate spec requirements.
- `scenarios` — list of scenario IDs under the spec requirement. At least one is required.
- `acceptance_criteria` — measurable. Reject "works correctly" / "is performant" / "is secure" without specifics.
- `layer` — `backend` / `frontend` / `both` / `infra`.
- `implementing_commits` — filled incrementally as commits land (Phases 2-5); reconciled in Phase 6.
- `tests.unit / integration / e2e` — test IDs (filename::test_name) added as they're written.
- `demo_artifact` — curl example for backend, Playwright trace path for frontend.
- `status` — `pending` / `in_progress` / `done` / `blocked`.

## Building the map

### Step 1: Enumerate source requirements

Read every file in `$REQ_DIR`. Extract requirements. If they're explicitly numbered, use those IDs. Otherwise, walk in document order and assign `REQ-NNN`.

### Step 2: Map to spec requirements

For each source requirement, run `openspec show <change> --json` and identify the spec requirement(s) that cover it. If you cannot find one, the coverage map has a gap — the spec needs another requirement before Phase 1 can exit.

### Step 3: Enumerate scenarios

For each spec requirement, list its scenarios. Scenarios that don't cleanly trace to a measurable acceptance criterion need refinement in the spec.

### Step 4: Classify layer

- Touches code in a frontend codebase → `frontend` or `both`.
- Touches code only in a backend codebase → `backend`.
- Touches code in multiple codebases or spans the boundary → `both`.
- Touches deployment / infra config only → `infra`.

### Step 4b: Add the default front-to-back integration criterion for every `both`-layer entry

For EVERY entry with `layer == "both"`, the `acceptance_criteria` array MUST contain an explicit front-to-back integration criterion — a criterion stating that the happy-path user-flow test runs against the **real running backend** (real server, real DB / queue / cache, real responses), NOT mocked / fake data, per `playwright-user-flows`'s "Real backend by default" discipline. This is the DEFAULT — add it whenever you classify an entry as `both`; do not wait to be told.

The ONLY way a `both`-layer entry legitimately lacks this criterion is an explicit statement in `$REQ_DIR` (proposal / design / source brief) authorizing isolated / mock-backed testing for that requirement. When such an authorization exists, record it verbatim in a `mock_testing_authorized` field on the entry (`{ "mock_testing_authorized": "<quoted authorization text + source file>" }`) so the test-completeness-verifier and the review-gate evidence can cite it. Absent that field, the integration criterion is mandatory and Phase 1 will not exit without it.

## Using the map

### Phase 1 (planning validation)

The loop continues if any entry has:
- No `spec_requirement_id`.
- Empty `scenarios`.
- Empty / vague `acceptance_criteria`.
- Wrong/missing `layer`.

For `layer == "frontend"` or `"both"` entries: the spec must include the Playwright user-flow specification per `playwright-user-flows`. For `"backend"` or `"both"`: the spec must include dev-API integration criteria per `dev-api-integration-testing`. For `layer == "both"` entries specifically: the loop ALSO continues if the entry lacks the front-to-back integration criterion from Step 4b (real-backend happy-path testing) AND lacks a `mock_testing_authorized` field — front-to-back integration testing against the real backend is the default for full-stack requirements and Phase 1 will not exit without it.

### Phase 3 (per-team review gate)

For a teammate's slice (the entries whose tasks they own): every entry's `tests` must have ≥1 passing test of the appropriate kind, every entry has a `demo_artifact`, and `status == "done"`.

### Phase 7 (master review)

Walk every entry. Any entry with `status != "done"` → re-spawn the appropriate team. Re-validate via `openspec validate --all --strict --json`. Then attribute every commit produced during the build to ≥1 entry via `implementing_commits`.

### Phase 8 (final report)

The coverage map IS the final report's spine: walk each entry, render its `source_requirement_id` → `implementing_commits` → `tests` → `demo_artifact`. Any entry without all four is a Phase-7 failure that should have been caught.

## Updating the map

The map is append-only structurally (entries don't disappear) but fields update as work proceeds:

- New commit → append SHA to `implementing_commits`.
- New test passes → append test ID to the appropriate `tests` array.
- Status changes → update `status` (and timestamp the change in a sidecar log if the orchestrator wants an audit trail).

Use atomic writes (write to `.tmp`, fsync, rename) so a crashed orchestrator doesn't leave a corrupt map.

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "I'll skip the coverage map for a small change" | Then Phase 7 has no spine to walk. Even a one-requirement change gets a one-entry map. |
| "Acceptance criteria like 'works correctly' are good enough" | Non-measurable criteria silently let bugs through. Rewrite them in terms of specific observable behavior. |
| "I'll fill in tests later" | Then you'll forget. The map drives Phase 3 — empty `tests` arrays are gate failures. |
| "One scenario per requirement is enough" | Often happy + failure + edge are three scenarios. The spec validation loop catches under-coverage. |
