# Proposal: live-data-wiring-discipline (v2.6.0)

## Why

A user-reported failure pattern that the existing framework doesn't catch. Verbatim from the user:

> "got an issue liek 'So: the backend extracted 71 facts + 13 persons (confirmed), but the client workspace is still mock-wired for documents/facts — it never shows extraction status (no pending/processing/done-with-facts), never fetches the live document list, and the sidebar never surfaces the extracted people. That's a real wiring gap, exactly matching what you saw.' and we simply cant have this. we need our front end agents to truly catch all of this. maybe we swarm the testing, ensuring when somehting is mandated live, we catch any areas where something is still hardcoded. they need to use playwright to asses, then look at code. this is a case where we wanted things removed from mock state"

### The failure shape

When a requirement explicitly says "wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend", an agent can satisfy the requirement's POSITIVE half (add the live wiring) and leave the NEGATIVE half (remove the mock wiring) silently unaddressed. The UI continues to render mock fallbacks because the mock-state code path is still reachable.

Specifically — the heirship-app-v3 case the user surfaced:
- **Backend side:** the extractor ran, persisted 71 facts + 13 persons to the live database, returned the extracted records via the live API.
- **Frontend side:** the client workspace component still imports the mock fixture data + still uses MSW handlers + still falls back to hardcoded values when the live response is null/loading + never wires the document-list query to the live endpoint + never renders the async extraction-status states (`pending` / `processing` / `done-with-facts`).
- **Surface symptom:** the UI looks "the same" — but the data it shows is the mock, not the live extracted records. The user sees "documents/facts" exactly as before; the 71 newly-extracted facts never appear.

### Why the existing framework misses this

The v2.0.0 `verify_no_fake_data` Layer-3 tool catches design-literals + MSW handlers + page.route fulfill + hardcoded JSON IN ADDED DIFFS. It catches "agent added fake data in the new code." It does NOT catch:

| Existing tool | What it catches | What it misses |
|---|---|---|
| `verify_no_fake_data` (v2.0.0) | Fake data in ADDED lines of the diff | Pre-existing mock wiring left in place; `?? mockValue` fallback patterns; conditional `useMockBackend` flags; mock imports the agent forgot to delete |
| `verify_interactions_honored` (v2.1.0) | Mockup-vs-built interaction mismatches | The UI's rendered VALUES coming from a stale mock data source |
| `verify_live_verification_claim` (v2.2.0) | Proxy assertions / fabricated tables | Live-vs-mock data routing — the test could pass against mock and the agent claims live |
| `verify_interactions_honored` again | Element wiring | Async status states (loading / processing / error / empty) that should surface but don't |

The user's verbatim diagnosis: *"the client workspace is still mock-wired for documents/facts — it never shows extraction status, never fetches the live document list, and the sidebar never surfaces the extracted people."* Three distinct sub-failures all rooted in the same shape: **the mock data path wasn't removed when the live data path was added.**

### The right discipline

For ANY slice with a "wire to live" / "remove mock" mandate, verification MUST include both passes (Playwright assess + code-side audit) and BOTH must agree:

1. **Playwright pass** — drive the UI, intercept the network response for the mandated endpoint, capture the live response's actual values, then assert the UI's rendered text/state contains those EXACT values (not a transformation, not a fallback, not a stale snapshot). **Tamper test:** modify the captured network response (e.g., change a count from 71 → 999), assert the UI updates. If the UI doesn't update, the data path is mock.
2. **Code-side pass** — walk the diff + the touched files for mock-state residue: MSW imports, faker, fixture imports, mock flags (`useMockBackend` / `VITE_USE_MOCK` / etc.), fallback patterns (`?? mockValue` / `|| MOCK_DATA`), Mirage/Pretender/etc. server setup, page.route fulfill in production code. If ANY residue is reachable from the touched feature's code path, the live wiring is incomplete.

The user explicitly asked for "swarm the testing" — multiple agents independently verifying. The existing v0.9.19 Phase 5 `interaction-completeness` 3-reviewer pattern IS the swarm. v2.6.0 extends each of the 3 reviewers' mandate to include the live-data-wiring assessment.

## What changes

Three enforcement layers (same shape as v2.0.0 / v2.2.0 / v2.4.0 / v2.5.0). Plus the existing 3-reviewer Phase 5 swarm gets its mandate extended.

### Layer 1 — `## Live-data wiring discipline (v2.6.0)` canonical section

New section in `skills/common-pipeline-conventions/SKILL.md`. Documents:

- The failure shape verbatim (with the heirship-app-v3 "71 facts + 13 persons" worked example).
- **The `wiring_mandate` annotation**: when a requirement carries `wiring_mandate: "live"` (or equivalent prose phrases — "wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend"), the slice is subject to the v2.6.0 discipline.
- **The 5 named severities** (see Layer 3 below).
- **The 2-pass verification workflow** — Playwright assess FIRST (drive the UI, capture network response, assert rendered value matches captured response, tamper-test that modifying the response updates the UI), code-side audit SECOND (grep the diff + touched files for mock-state residue).
- **The 3-reviewer Phase 5 swarm extension** — each of the 3 `interaction-reviewer` agents independently runs both passes against the `wiring_mandate` slice; convergence per the existing v0.9.19 protocol.
- **The async-status surface rule** — for any backend that emits async states (loading / pending / processing / done / error / empty / partial), the UI MUST render distinct states; missing state UI is silent failure.

### Layer 2 — New `verify_live_data_wiring` Layer 3 tool (the 9th)

`hooks/vao_tools.py::verify_live_data_wiring(verification_artifact, wiring_mandate)` — deterministic, stdlib-only, bit-stable output.

**Inputs:**
- `verification_artifact`: dict carrying `diff_files[]` (each `{path, added_lines[], removed_lines[]}`), `touched_file_contents` (dict of path → file content for files the agent claims are now live-wired), `playwright_trace_summary` (`captured_network_requests[]` + `ui_text_after_render` + `tamper_test_results`), and the v2.4.0 `evidence_artifact_path`.
- `wiring_mandate`: dict carrying `mandate_kind` ("live-data-wiring" / "remove-mock" / etc.), `endpoints[]` that should be live-wired, `async_states_expected[]` (e.g., `["pending", "processing", "done-with-facts"]`).

**5 named severities:**

| Severity | Detection |
|---|---|
| `mock-state-residue` | Diff `added_lines` OR `touched_file_contents` contain ANY of the canonical mock-state signatures (MSW imports / Mirage / faker / fixture imports / mock flags / fallback patterns / page.route fulfill in production). |
| `live-response-not-rendered` | Playwright captured a network response with value V; the UI's rendered text does NOT contain V (allowing for formatting transforms — date strings, locale, etc. — via the artifact's `transform_hints`). |
| `mock-fallback-uncovered` | Diff contains `?? MOCK_*` / `\|\| MOCK_*` / `?? FIXTURE_*` patterns that would silently render mock if live data is null/undefined. |
| `network-not-intercepted` | The mandate's `endpoints[]` includes endpoint E; Playwright `captured_network_requests[]` does NOT include a request to E. The UI sourced its data elsewhere (cached mock, hardcoded constant, local fixture). |
| `async-status-not-surfaced` | The mandate's `async_states_expected[]` includes state S; Playwright `ui_text_after_render` does NOT contain a state-named element for S. The UI silently fails to inform the user that work is pending. |

**Output:** `{tool, valid, gaps[severity/evidence/remediation], verdict_at}`. Deterministic. CLI subcommand `verify-live-data-wiring`.

### Layer 3 — Extend the existing Phase 5 `interaction-completeness` 3-reviewer swarm

`skills/interaction-completeness/SKILL.md` gains a `## Live-data wiring axis (v2.6.0)` sub-section. For any slice the architect annotated with `wiring_mandate: "live"`, EACH of the 3 `interaction-reviewer` agents (already dispatched in parallel per the existing v0.9.19 protocol) independently:

1. Reads the mandate's `endpoints[]` + `async_states_expected[]`.
2. Runs the Playwright pass — captures network response, asserts UI rendered value matches.
3. Runs the code-side pass — greps the diff + touched files for mock-state residue.
4. Writes findings into the existing convergence protocol's `live_data_wiring_findings` block.

The architect's Round-3 robustness review verdict requires zero `mock-state-residue` / `live-response-not-rendered` / `mock-fallback-uncovered` / `network-not-intercepted` / `async-status-not-surfaced` findings.

`agents/interaction-reviewer.md` gains a `## Live-data wiring audit (v2.6.0)` section documenting the per-reviewer audit protocol.

### Schema v7 — No changes

`live_verification_review` (v2.2.0) already covers the gating. The `verify_live_data_wiring` verdict can be cited via the existing optional `live_verification_review` field's `verdict_path`.

### Canonical synthetic fixture

`tests/fixtures/vao/live-data-mock-residue.json` reproduces the verbatim heirship-app-v3 failure:
- `mandate_kind: "live-data-wiring"`, `endpoints: ["/api/matters/{id}/documents", "/api/matters/{id}/facts", "/api/matters/{id}/persons"]`, `async_states_expected: ["pending", "processing", "done-with-facts"]`
- Touched file content includes residual `import { mockDocuments } from "../fixtures/documents-mock"` + `?? mockDocuments` fallback in the docs query + a `useMockBackend` flag + an MSW handler import
- Playwright network captures show NO request to `/api/matters/{id}/documents` (the UI never fetched live)
- Playwright UI text shows mock document names + no extraction-status indicator
- Tamper test shows modifying the live response doesn't change the UI

Each of the 5 severities fires on this fixture. The fixture's `_corrected_verification_artifact` shows the valid shape (mock imports removed, fallback patterns replaced with proper loading UI, all 3 endpoints in Playwright captures, async-state UI elements present, tamper-test UI updates).

## QA Guidance

### Acceptance Criteria

- [AC-1] `skills/common-pipeline-conventions/SKILL.md` gains `## Live-data wiring discipline (v2.6.0)` section appearing exactly once.
- [AC-2] Section names the 5 severities verbatim, the 2-pass verification workflow, the `wiring_mandate` annotation + 4+ canonical mandate phrases ("wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend").
- [AC-3] Section documents the 3-reviewer Phase 5 swarm extension + the async-status surface rule.
- [AC-4] `hooks/vao_tools.py` ships `verify_live_data_wiring(verification_artifact, wiring_mandate, out_path=None) -> dict` + CLI subcommand. Deterministic + bit-stable.
- [AC-5] 5 named severities recognized: `mock-state-residue` / `live-response-not-rendered` / `mock-fallback-uncovered` / `network-not-intercepted` / `async-status-not-surfaced`.
- [AC-6] `_MOCK_STATE_SIGNATURES` module-level constant lists at least 12 canonical signatures (MSW / Mirage / faker / fixture imports / mock flags / fallback patterns / page.route fulfill).
- [AC-7] `skills/interaction-completeness/SKILL.md` gains `## Live-data wiring axis (v2.6.0)` sub-section extending the 3-reviewer convergence.
- [AC-8] `agents/interaction-reviewer.md` gains `## Live-data wiring audit (v2.6.0)` section.
- [AC-9] `tests/fixtures/vao/live-data-mock-residue.json` exists, fires all 5 severities, AND `_corrected_verification_artifact` passes.
- [AC-10] `tests/test_vao_live_data_wiring.py` exists with ≥ 25 tests; `tests/test_live_data_wiring_discipline.py` exists with ≥ 10 tests.
- [AC-11] Version `2.6.0` consistent across plugin.json, marketplace.json, CHANGELOG, README banner, CLAUDE.md.
- [AC-12] All existing tests still pass + new tests. Target: 2514 → ~2550.
- [AC-13] Backwards-compatible — schema v7 unchanged; no new agent; v2.0.0 → v2.5.0 evidence files validate unchanged. Artifacts without `wiring_mandate` don't fire the v2.6.0 tool.

### Out of Scope

- **Live HTTPS probing** — same deferral as v2.2.0 / v2.4.0. The tool reads the evidence the agent provides; doesn't independently probe.
- **AST-based code analysis** — v2.6.0 uses substring + regex detection. AST analysis is v2.6.x.
- **Tamper-test execution** — v2.6.0 documents the tamper-test pattern + reads the agent's tamper-test results. Actually executing the Playwright tamper is v2.6.x runtime work.

## Impact

- **Modified skills:** `skills/common-pipeline-conventions/SKILL.md` (+ canonical section), `skills/interaction-completeness/SKILL.md` (+ live-data-wiring-axis sub-section).
- **Modified agents:** `agents/interaction-reviewer.md` (+ live-data-wiring-audit section).
- **Modified hooks:** `hooks/vao_tools.py` (+ 9th tool + new module constants + CLI subcommand).
- **New tests:** `tests/test_vao_live_data_wiring.py` (~25), `tests/test_live_data_wiring_discipline.py` (~10).
- **New fixtures:** `tests/fixtures/vao/live-data-mock-residue.json`.
- **Modified docs:** README.md, CHANGELOG.md, CLAUDE.md, plugin.json, marketplace.json. Docs CODEBASE_MAP + INTEGRATION_MAP timestamp bumps.
- **Test count:** 2514 → ~2550.
- **Version:** v2.5.0 → **v2.6.0** (MINOR — additive).
- **Backwards-compatible:** YES.
