# Design: live-data-wiring-discipline (v2.6.0)

## Reference

Full WHY + WHAT + ACs in `proposal.md`. This file is the architectural deep-dive.

## Why this is v2.6.0 (MINOR), not v3.0.0

- **MINOR (additive)** — one new canonical section + one new Layer 3 tool + extensions to existing Phase 5 swarm. No removed behavior, no schema break.
- **No code change to existing tools** — `verify_no_fake_data`, `verify_interactions_honored`, etc. are unchanged. v2.6.0 ships alongside.
- **No new agent** — extends the existing 3-reviewer `interaction-completeness` swarm rather than adding a 4th role.
- **Backwards-compat is unconditional** — artifacts without `wiring_mandate` don't fire the v2.6.0 tool; pre-v2.6.0 evidence files validate unchanged.

## Reuse Decision Log

### RD-1: EXTEND `skills/common-pipeline-conventions/SKILL.md`

**Decision:** Extend (new top-level section).
**Justification:** Same pattern as v1.4 / v1.6 / v1.7 / v1.8 / v2.0 / v2.2 / v2.4 / v2.5 sections.

### RD-2: EXTEND `hooks/vao_tools.py`

**Decision:** Extend (add 9th deterministic tool).
**Justification:** The 8 existing tools live in this module; the 9th is the same module-not-hook pattern.

### RD-3: EXTEND existing Phase 5 `interaction-completeness` 3-reviewer swarm

**Decision:** Extend mandate, NOT add a new agent role.
**Justification:** The user's verbatim ask was "maybe we swarm the testing." The existing v0.9.19 Phase 5 protocol ALREADY dispatches 3 `interaction-reviewer` agents in parallel with convergence — that IS the swarm. Adding a NEW 3-agent team for live-data-wiring would dispatch 3 MORE agents per Phase 5 (total: 6 reviewers per slice). The cost is high and the assessment overlaps with what `interaction-reviewer` already does (UI element wiring). The right scope: extend the existing 3-reviewer mandate to ALSO assess live-data-wiring when the slice has `wiring_mandate: "live"`. Zero new agent dispatches; richer assessment from the existing swarm.

### RD-4: NO new agent role

**Decision:** Decline.
**Justification:** See RD-3. The existing `interaction-reviewer` agent body gains a `## Live-data wiring audit (v2.6.0)` section. Same agent, extended mandate.

### RD-5: NO schema change

**Decision:** Decline.
**Justification:** v2.2.0 `live_verification_review` (in schema v7's `OPTIONAL_VAO_FIELDS`) already covers the gating. The new tool's verdict cites via the existing `verdict_path` field.

### RD-6: NEW canonical fixture

**Decision:** Build new.
**Justification:** Same pattern as every prior verified-live extension. Each new failure mode gets a canonical positive case the framework MUST catch.

### RD-7: EXTEND existing test files vs. NEW dedicated files

**Decision:** Build new (`tests/test_vao_live_data_wiring.py` + `tests/test_live_data_wiring_discipline.py`).
**Justification:** The 9th tool gets its own test file (same pattern as v2.1.0 `test_vao_interactions_honored.py` and v2.2.0 `test_vao_live_verification_claim.py`). Discipline-side assertions live in their own file.

### RD-8: DEFERRED — live tamper-test execution

**Decision:** Deferred to v2.6.x.
**Justification:** v2.6.0 documents the tamper-test pattern (Playwright intercepts response, modifies, asserts UI updates) and READS the agent's tamper-test results. Actually executing the Playwright tamper in the runtime is a follow-on that requires the Playwright adapter + MCP plumbing. The discipline + fixture format ship now; runtime execution catches up in v2.6.x.

### RD-9: DEFERRED — AST-based mock-residue detection

**Decision:** Deferred to v2.6.x.
**Justification:** v2.6.0's `_MOCK_STATE_SIGNATURES` uses substring + simple regex. False-positives possible (e.g., `mockData` as a variable name in a test file that's correctly scoped). v2.6.x can add AST-aware traversal with TypeScript/JS parser.

## The 5 severities — why these

Each maps to a concrete failure observation. The vocabulary is closed at 5 for v2.6.0; each new mock-vs-live failure shape that surfaces in production adds a new severity in v2.6.x.

| Severity | What the agent did wrong | What surfaces to the user |
|---|---|---|
| `mock-state-residue` | Added live wiring; forgot to remove mock imports / flags / handlers | UI silently renders mock data because the mock path is still reachable |
| `live-response-not-rendered` | Live wiring connects; UI doesn't actually display the live values | UI shows stale snapshot / fallback / hardcoded value despite live data being available |
| `mock-fallback-uncovered` | `?? MOCK_DATA` / `\|\| MOCK_DEFAULT` left in place | UI silently uses mock when live data is null/loading — masking real failures |
| `network-not-intercepted` | UI never fetched the live endpoint | UI sourced data from cached mock / hardcoded constant / local fixture |
| `async-status-not-surfaced` | Backend emits states (loading / pending / processing / done / error); UI lacks UI for them | User sees "nothing happening" when work is actually in progress — heirship-app-v3 case verbatim |

## The `_MOCK_STATE_SIGNATURES` taxonomy

Greppable patterns for substring + regex detection. v2.6.0 ships these 14 canonical signatures (with case-insensitive matching where appropriate):

| Signature | Pattern |
|---|---|
| MSW import | `from "msw"`, `from 'msw'`, `setupWorker(`, `setupServer(`, `rest.get(`, `rest.post(`, `http.get(`, `http.post(` |
| Mirage import | `from "miragejs"`, `from 'miragejs'`, `createServer(`, `mirage.` |
| Faker import | `from "@faker-js/faker"`, `faker.` |
| Fixture imports | regex `from\s+['"][^'"]*(?:fixtures?|mocks?|fake[_-]?data)[^'"]*['"]` |
| Mock-state symbol names | regex `(?:^\|\s)(?:mockData\|MOCK_DATA\|FIXTURE_\|fakeData)` |
| Mock-flag env vars | `VITE_USE_MOCK`, `NEXT_PUBLIC_MOCK`, `REACT_APP_USE_MOCK`, `useMockBackend`, `enableMocking`, `MOCK_API` |
| Fallback to mock | regex `\?\?\s*MOCK_\|\?\?\s*mockData\|\|\|\s*MOCK_\|\|\|\s*FIXTURE_` |
| Page-route fulfill (production) | `page.route(...fulfill` IF the file is not a test/spec file |
| Mirage Pretender setup | `new Pretender(`, `Pretender.prototype` |
| Conditional mock | regex `if\s*\([^)]*(?:USE_MOCK\|useMockBackend\|MOCK_API)` |
| `__mocks__` directory imports | regex `from\s+['"][^'"]*__mocks__[^'"]*['"]` |
| Hardcoded JSON body | regex `body:\s*JSON\.stringify\(\{[^}]+\}\)` IF the value is a known mock object |
| Storybook story import as data source | regex `from\s+['"][^'"]*\.stories\.[jt]sx?['"]` |
| Test fixture variable in production | `import.*fixture` from a non-test file |

The detection is intentionally permissive — false-positives surface as gap entries the human can dismiss; false-negatives let the failure mode through.

## Test-file exclusion

The check skips files matching `_is_test_path()` (already defined in `hooks/vao_tools.py` from v2.0.0's `verify_no_fake_data`). MSW handlers in `src/mocks/handlers.ts` that's only imported from test setup are legitimate; MSW handlers imported from production component code are not.

## Async-status surface rule

The discipline names the canonical async states a backend can emit:

| State | UI element required |
|---|---|
| `loading` / `pending` | A spinner / skeleton / "loading..." text element |
| `processing` | A progress indicator / "processing N items" text element |
| `done` / `done-with-facts` / `success` | The actual rendered live data |
| `error` | An error UI with retry affordance |
| `empty` | An empty-state UI ("No documents yet") distinct from loading |

For each state in the requirement's `async_states_expected[]`, the Playwright `ui_text_after_render` MUST contain a state-named element matching one of these surfaces. Missing = `async-status-not-surfaced` severity.

## How the 3-reviewer swarm extension works

The existing Phase 5 protocol already dispatches 3 `interaction-reviewer` agents in parallel + convergence. v2.6.0 adds to each reviewer's mandate:

1. **Each reviewer reads** the slice's `wiring_mandate` annotation (if present in the architect's brief).
2. **Each reviewer independently runs** the Playwright pass + the code-side audit against the slice's frontend files.
3. **Each reviewer writes** `live_data_wiring_findings[]` to its convergence report.
4. **Round 1 convergence** — if all 3 reviewers report zero findings, the axis passes.
5. **Round 2** — disagreements among the 3 reviewers go to round 2 (per the existing v0.9.19 protocol). The 3 reviewers exchange evidence; majority rules.
6. **Round 3** (architect robustness) — the `system-architect` Round 3 review (already in the protocol) explicitly checks the converged live-data-wiring findings + the deterministic `verify_live_data_wiring` tool verdict. Both must agree.

The swarm IS the existing 3-reviewer pattern. v2.6.0 extends what each reviewer measures.

## Failure-mode mapping

| Failure | Caught at | How |
|---|---|---|
| Mock import left in production code | Layer 3 `mock-state-residue` | `_MOCK_STATE_SIGNATURES` substring/regex grep |
| Backend wired but UI shows stale snapshot | Layer 3 `live-response-not-rendered` | Playwright UI text doesn't contain captured network response value |
| `?? mockValue` fallback silently rendering mock | Layer 3 `mock-fallback-uncovered` | Fallback-pattern regex |
| UI never fetched the live endpoint | Layer 3 `network-not-intercepted` | Mandate endpoints[] not in captured network requests |
| Backend emits processing state; UI never shows it | Layer 3 `async-status-not-surfaced` | Mandate async_states_expected[] not in UI text |
| Heirship-app-v3 verbatim: 71 facts extracted, never surface | All 5 severities concurrently | Canonical fixture demonstrates the convergence |

## Costs accepted

1. **One additional check per Phase 3/5 dispatch** — sub-millisecond for the deterministic tool.
2. **Existing 3 interaction-reviewer agents do slightly more work** — modest token cost; no new dispatches.
3. **Agents must capture network responses + UI text** — non-trivial when wiring_mandate is set. But that's the point — verify-live requires the artifact.
4. **1 new fixture + ~35 new tests** — modest growth (2514 → ~2550).

## Migration / backwards compatibility

- **v2.5.0 → v2.6.0:** ADDITIVE. No schema break.
- **Migration path.** Pre-v2.6.0 artifacts without `wiring_mandate` continue to validate; v2.6.0 fires only when the field is present.
- **Opt-out.** No opt-out — the discipline is always-on, but only fires when the requirement explicitly mandates live wiring.

## Version

**v2.6.0** — MINOR bump. Purely additive; backwards-compatible.
