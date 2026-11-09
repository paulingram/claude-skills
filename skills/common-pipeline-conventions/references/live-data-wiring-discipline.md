# Live-data wiring discipline (v2.6.0)

A user-reported recurring failure: when a requirement explicitly says "wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend", the agent satisfies the requirement's POSITIVE half (adds the live wiring) but leaves the NEGATIVE half (removes the mock wiring) silently unaddressed. The UI continues to render mock fallbacks because the mock-state code path is still reachable.

**Failure shape** (verbatim heirship-app-v3 case in CHANGELOG v2.6.0): the backend extracted 71 facts + 13 persons but the client workspace stayed mock-wired — never showed extraction status, never fetched the live document list, never surfaced the extracted people. The user's directive: swarm the testing so that when something is mandated live, every still-hardcoded area is caught — use Playwright to assess, then look at the code.

Concrete heirship-app-v3 case:
- **Backend side:** the extractor ran, persisted 71 facts + 13 persons to the live database, returned the extracted records via the live API.
- **Frontend side:** the client workspace component still imports the mock fixture data + still uses MSW handlers + still falls back to hardcoded values when the live response is null/loading + never wires the document-list query to the live endpoint + never renders the async extraction-status states (`pending` / `processing` / `done-with-facts`).
- **Surface symptom:** the UI looks "the same" — but the data it shows is the mock, not the live extracted records. The user sees the same hardcoded list; the 71 newly-extracted facts never appear.

### Why the existing framework misses this

v2.0.0's `verify_no_fake_data` catches fake data IN ADDED lines of the diff — i.e., "agent ADDED fake data in NEW code." It does NOT catch the inverse: pre-existing mock wiring left in place after live wiring was added. The agent satisfies `verify_no_fake_data` (nothing fake in the diff) and the UI still renders mock data (because the old mock path wasn't removed).

### The `wiring_mandate` annotation

When the requirement carries one of the canonical phrases — *"wire to live data"*, *"remove mocks"*, *"stop using fixtures"*, *"use real backend"*, *"replace the mock"*, *"unmock"*, *"actual data"*, *"real API"*, *"go live"* — the slice is annotated `wiring_mandate: "live"` in the architect's brief. The annotation triggers the v2.6.0 verification.

### The 2-pass verification workflow

The user's verbatim ask: *"they need to use playwright to asses, then look at code."* The discipline IS that order:

**Pass 1 — Playwright assess (drives the UI, captures network response, asserts UI rendered value matches captured response).**
1. Drive the UI to the bug-exposing state.
2. Intercept network requests for every endpoint in `wiring_mandate.endpoints[]`. Capture response bodies.
3. Assert the UI's rendered text/state CONTAINS the live values (allowing for formatting transforms — date strings, locale, etc.).
4. **Tamper test** — modify the captured network response (e.g., change `count: 71` → `count: 999` via Playwright `page.route` for a SECOND run); assert the UI updates. If the UI doesn't update, the data path is mock-cached, not live.
5. Capture an `evidence_artifact_path` per the v2.4.0 discipline.

**Pass 2 — Code-side audit (walk the diff + touched files for mock-state residue).**
1. For every file in the slice's `files_changed[]`, walk the file content for the `_MOCK_STATE_SIGNATURES` patterns (see Layer 3 below).
2. Specifically check for FALLBACK patterns (`?? mockData`, `|| MOCK_DEFAULT`, `?? FIXTURE_`) that would silently render mock when live data is null.
3. Check for MOCK FLAGS (`useMockBackend`, `VITE_USE_MOCK`, `enableMocking`, `MOCK_API`) that would conditionally route to mock.
4. Check for MOCK IMPORTS (`from "msw"`, faker, fixture files, `__mocks__/`) reachable from production component code paths.
5. If ANY residue is reachable from the touched feature's code path, the live wiring is incomplete.

Both passes must agree. A passing Playwright assessment WITH residual mock imports = incomplete; the imports may be unreachable today but will silently re-activate the mock path on the next change.

### The 5 named severities

| Severity | What it catches |
|---|---|
| `mock-state-residue` | Diff or touched-file contents contain ANY canonical mock-state signature (MSW / Mirage / faker / fixture import / mock flag / mock-symbol name) |
| `live-response-not-rendered` | Playwright captured a network response value V; the UI's rendered text does NOT contain V |
| `mock-fallback-uncovered` | Diff contains `?? MOCK_*` / `\|\| MOCK_*` / `?? FIXTURE_*` patterns that silently render mock if live data is null |
| `network-not-intercepted` | `wiring_mandate.endpoints[]` includes endpoint E; Playwright captured requests do NOT include a request to E — UI sourced data elsewhere (cached mock / hardcoded constant / local fixture) |
| `async-status-not-surfaced` | `wiring_mandate.async_states_expected[]` includes state S; Playwright UI text has no element naming the state — user sees nothing when work is in progress |

### The 3-reviewer Phase 5 swarm extension

The user explicitly asked: *"maybe we swarm the testing."* The existing v0.9.19 `interaction-completeness` Phase 5 protocol ALREADY dispatches 3 `interaction-reviewer` agents in parallel and converges. THAT IS THE SWARM. v2.6.0 extends each of the 3 reviewers' mandate — when the slice carries `wiring_mandate: "live"`, each reviewer independently:

1. Runs the 2-pass workflow (Playwright assess + code-side audit).
2. Writes `live_data_wiring_findings[]` to its convergence report.
3. The round-1 convergence requires all 3 reviewers to report ZERO findings; disagreements go to round 2; the round-3 architect robustness review checks the converged findings + the deterministic `verify_live_data_wiring` tool verdict (both must agree).

No new agent dispatches. Zero net cost in the existing protocol's dispatch budget; richer assessment from the existing swarm.

### The async-status surface rule

Backends that emit async states (loading / pending / processing / done / error / empty / partial) REQUIRE corresponding UI surfaces. The canonical states + required UI elements:

| State | UI element required |
|---|---|
| `loading` / `pending` | A spinner / skeleton / "loading..." text element |
| `processing` | A progress indicator / "processing N items" text element |
| `done` / `done-with-facts` / `success` | The actual rendered live data |
| `error` | An error UI with retry affordance |
| `empty` | An empty-state UI ("No documents yet") distinct from loading |

For each state in `wiring_mandate.async_states_expected[]`, the Playwright `ui_text_after_render` MUST contain a state-named element. Missing = `async-status-not-surfaced` severity.

### Pattern propagation mandate (v2.7.0)

When an agent fixes ONE mock-state instance under a `wiring_mandate`, it MUST sweep the codebase for the SAME shared source and fix ALL consumers in the same change — not announce one fix and offer the sweep as a follow-up. The follow-up offer is itself the bug this section closes.

**Verbatim user prose driving the rule:**

> "One honest caveat for later: the other client walkthrough screens (intake steps, review) read from the same one-time-seeded WtData copy, so they may show similarly stale data in live mode. I fixed the Workspace (what you reported) and noted the pattern; say the word if you want me to sweep the rest of the client app for the same gap. like its dumb that the agents are not actively like, hey its fake data and you said none so I will fix it all"

**Canonical failure shape — the heirship walkthrough case:**

- `Workspace.tsx` reads `useWalkthroughData()` → was originally seeded ONCE into a local `WtData` copy → workspace renders stale data
- `IntakeSteps.tsx` reads the SAME `useWalkthroughData()` → same one-time seed, same staleness
- `ReviewPanel.tsx` reads the SAME `useWalkthroughData()` → same one-time seed, same staleness
- Agent fixes `Workspace.tsx` to refetch on focus, leaves `IntakeSteps.tsx` and `ReviewPanel.tsx` untouched, and announces the gap as "say the word if you want me to sweep"
- The user said "no mock data" — that mandate covers EVERY consumer of the shared source. A partial fix is a discipline failure.

**The mandate (non-negotiable):**

1. **Trace the source.** When an agent finds a mock-state instance, it identifies WHAT the source is: a shared fixture import (`import { WtData } from '../fixtures/wt-data'`), a shared hook (`useWalkthroughData`), a shared seed function (`seedWtData`), a shared context value, a shared store slice.
2. **Enumerate consumers.** Grep the codebase for ALL files that import or call the same source. The list is the consumer set.
3. **Fix every consumer in the same change.** Every consumer in the enumerated set MUST land in the same diff. Partial fixes are forbidden.
4. **Surface the sweep, never offer it.** The post-fix report names every consumer the sweep touched and the verification that each now reads live. The phrase *"say the word if you want me to sweep the rest"* is FORBIDDEN — the sweep happens automatically.

**6th severity — `shared-mock-source-not-swept`** (added to `verify_live_data_wiring` in v2.7.0):

- Triggers when `wiring_mandate.shared_mock_sources[]` (or the artifact's `codebase_scan.consumer_files{}` map) names a source S with N consumer files, AND the diff modified strictly fewer than N consumers, AND any unfixed consumer file still contains a mock-state signature referencing S.
- Evidence carries the source identifier, the unfixed consumer file paths, and the verbatim signature line that survives.

**3 canonical shared-source signatures:**

| Signature class | Examples |
|---|---|
| **Shared fixture import** | `import { WtData } from '../fixtures/wt-data'` / `import seedData from './seed-data.json'` |
| **Shared hook** | `useWalkthroughData()` / `useMockBackend()` / `useSeedData()` |
| **Shared seed function** | `seedWtData()` / `bootstrapMockState()` / `initOneTimeSeed()` |

When the `wiring_mandate` does NOT carry a `shared_mock_sources` field, the v2.7.0 detector is a no-op — backwards-compatible.

### Cross-references

- `hooks/vao_tools.py::verify_live_data_wiring` — the deterministic Layer 3 tool (9th in the VAO module; 6 severities in v2.7.0).
- `hooks/vao_tools.py::_MOCK_STATE_SIGNATURES` — the canonical pattern list ≥ 12 entries.
- `skills/interaction-completeness/SKILL.md` `## Live-data wiring axis (v2.6.0)` — the 3-reviewer swarm extension.
- `agents/interaction-reviewer.md` `## Live-data wiring audit (v2.6.0)` — the per-reviewer audit protocol (extended in v2.7.0 with the sweep step).
- `agents/frontend.md` `## Pattern propagation mandate (v2.7.0)` — the implementer-side discipline.
- `tests/fixtures/vao/live-data-mock-residue.json` — v2.6.0 canonical case (verbatim heirship-app-v3).
- `tests/fixtures/vao/shared-mock-source-not-swept.json` — v2.7.0 canonical case (walkthrough WtData partial sweep).
- `tests/test_vao_live_data_wiring.py` + `tests/test_live_data_wiring_discipline.py` + `tests/test_pattern_propagation_discipline.py` — structural tests.
- Companion to v2.0.0 `verify_no_fake_data` (catches NEW fake data) + v2.2.0 verified-live + v2.4.0 external-state + evidence-artifact disciplines.
