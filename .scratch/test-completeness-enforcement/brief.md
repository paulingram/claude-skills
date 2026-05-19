# Test Completeness Enforcement

## Problem statement

The pipeline mandates unit + integration + Playwright user-flow testing across multiple skills, but the discipline is documentation only. In practice:

1. A teammate can claim "tests pass" while having only run unit tests, skipping integration and / or Playwright entirely. The review-gate hook validates `tests.added ≥ 1` and `tests.passing == tests.added` but does NOT validate the KIND of tests (unit vs integration vs e2e).
2. The "Playwright user-flow tests" language across `playwright-user-flows`, `dev-api-integration-testing`, `frontend` agent, and `integration` agent describes the discipline (simulate a real human via `page.click` / `page.fill` / `page.waitFor` and assert visible state) but a teammate could technically write a "Playwright test" that uses `page.evaluate(() => fetch(...))` to hit API endpoints directly — bypassing the entire user-simulation point. The skill includes anti-patterns against this but the enforcement is documentation-only.

The user wants:
- Language audit + tightening so "Playwright test" unambiguously = real-user simulation.
- A new post-analysis test-completeness-verifier agent that confirms unit + integration + Playwright all ran AND meet spec acceptance criteria.
- The verifier loops until all three pass (or explicit per-kind n/a is justified).
- On any failure, SR auto-spawn (per v0.7.0) routes back to the originating team's dev loop.

## Requirements

### REQ-001 — Language audit and enforcement around Playwright user-flow tests

- Audit every reference to "Playwright tests" / "user-flow tests" in `skills/playwright-user-flows/`, `skills/dev-api-integration-testing/`, `skills/frontend-route-mapping/`, `skills/visual-fidelity-reconciliation/`, `agents/frontend.md`, `agents/integration.md`, `agents/backend.md`, `commands/architect-team.md`, `commands/visual-qa.md`.
- Every reference must be unambiguous: tests simulate a real human via `page.goto` / `page.click` / `page.fill` / `page.selectOption` / `page.setInputFiles` / `page.waitFor` / `expect(locator).toBeVisible()` and assert visible state. Direct API calls (`page.evaluate(() => fetch(...))`, `page.request.get(...)`, `axios.post(...)` from inside a Playwright test) in place of user clicks are forbidden EXCEPT for `page.route` (to mock specific error paths) and asset-resolution verification.
- Anti-pattern table in `playwright-user-flows` and the test-author hard rules in `frontend` / `integration` agents explicitly reject the "I'll just hit the endpoint in the Playwright test" rationalization, naming `page.evaluate(() => fetch())` and `page.request.*` as the specific anti-pattern.
- Acceptance: grep audit of the listed files confirms no remaining ambiguous language; explicit new anti-patterns + hard rules present.

### REQ-002 — New `test-completeness-verifier` agent

- Create `agents/test-completeness-verifier.md` with frontmatter (name, description, tools, model, color) per the existing agent conventions.
- The agent is READ-ONLY: tools are `Read, Glob, Grep, LS, Bash, TodoWrite` only (no Edit / Write — it produces a verdict, not edits).
- Model: `sonnet` (similar role to `codebase-map-reviewer`).
- Color: `red` (matches reviewer-class agents).
- The agent runs at the end of Phase 3 (per-team review gate) AND end of Phase 5 (cross-layer integration) to verify the work shipped has:
  - **Unit tests** ran (count > 0 from `tests.unit` in review evidence) OR justified as `unit_n/a_note: "<why no unit-testable surface>"`.
  - **Integration tests** ran (count > 0 from `tests.integration`) — for backend slices this means against the live dev API per `dev-api-integration-testing`; OR justified as `integration_n/a_note`.
  - **Playwright tests** ran (count > 0 from `tests.e2e` or `tests.playwright`) — for frontend slices this means real-user simulation per `playwright-user-flows` (the verifier grep-audits the test source for `page.evaluate(() => fetch(...))` / `page.request.*` / `axios.*` anti-patterns and fails if found); OR justified as `playwright_n/a_note`.
  - All three categories satisfy the acceptance criteria from `openspec/changes/<change-name>/coverage-map.json` for the teammate's slice.
- Output: a structured verdict JSON at `<cwd>/.architect-team/test-completeness/<task-id>-<ts>.json` with fields per kind (`status`: `pass` / `n/a` / `fail`; `evidence`: test IDs + counts + commit refs; `note`: required when status is `n/a`).
- On any kind failing OR ambiguous: writes a solution requirement (`origin.kind: "test-completeness-failure"`) per v0.7.0 SR auto-spawn so the orchestrator re-spawns the originating team's loop.
- Acceptance: `agents/test-completeness-verifier.md` exists with valid frontmatter; presence test added to `tests/test_agents.py` `EXPECTED_AGENTS`; agent body documents the read-only posture and the verdict JSON schema.

### REQ-003 — Hook enforcement of test-kind completeness

- Add a new evidence field `test_completeness_review` to the review-gate hook (`hooks/review-gate-task.py`) with values `"pass"` / `"n/a"` / `"fail"`.
- The hook BLOCKS `"fail"` (mirror of v0.5.0's `visual_fidelity_review` enforcement).
- `"n/a"` requires a non-empty `test_completeness_review_note` justifying which kind(s) are inapplicable and why.
- `"pass"` allows completion.
- Add `test_completeness_review` to `REQUIRED_EVIDENCE_FIELDS`. Add `VALID_TEST_COMPLETENESS_VALUES = {"pass", "n/a", "fail"}` constant.
- Schema-version implication: review-gate evidence schema v2 → v3 (documented in `team-spawning-and-review-gates`).
- Acceptance: hook validates the new field per the rules above; hook tests cover every branch (pass, fail-blocks, missing-blocks, invalid-value-blocks, n/a-without-note-blocks).

### REQ-004 — Loop discipline (re-uses v0.7.0 SR auto-spawn)

- The test-completeness-verifier loops by writing SRs that the orchestrator picks up and re-spawns the dev loop for. No new orchestrator code needed — v0.7.0 already implements the SR pickup loop.
- Add `test-completeness-failure` to the `origin.kind` enum in `team-spawning-and-review-gates`'s `## Solution Requirements` section.
- Acceptance: documented in `team-spawning-and-review-gates`; verifier agent body references the SR spawn behavior; an end-to-end scenario in the new skill explains the closed loop.

### REQ-005 — Tests for the new hook field and new agent

- Hook tests in `tests/test_review_gate_task.py`: new test cases for `test_completeness_review` covering pass / fail-blocks / missing-blocks / invalid-value-blocks (parametrized) / n/a-without-note-blocks (parametrized).
- Agent presence test in `tests/test_agents.py`: add `test-completeness-verifier` to `EXPECTED_AGENTS`; existing parametrized frontmatter validation covers the new agent automatically.
- Update `_valid_evidence` helper to include the new field with default `"n/a"` + note so existing tests stay valid.
- Acceptance: full pytest suite passes; total tests ≥ 96 (90 baseline + ≥ 6 new).

### REQ-006 — Documentation refresh

- `CHANGELOG.md` entry for v0.9.0 covering REQ-001 through REQ-005.
- `README.md` updates: skill / agent / hook counts; new-in-v0.9.0 callout for test-completeness enforcement; loops section gets a new sub-loop entry (Loop 4d — Test-completeness verification).
- `docs/CODEBASE_MAP.md` targeted refresh: agent table adds test-completeness-verifier row; tests row updated; system overview mentions the new enforcement; mermaid adds a node + edge for the new agent.
- Version bump `0.8.1` → `0.9.0` in `plugin.json` and `marketplace.json`.

## Out of scope

- A separate skill file for test-completeness-verification. The agent's body documents the discipline; a separate skill would be premature factoring. Revisit if the body grows beyond ~150 lines.
- Modifying the existing `tests.added` / `tests.passing` fields in review evidence — those stay as-is. The new field is additive.
- Changing the structure of `tests` (unit / integration / e2e arrays). The verifier consumes them as-is.

## Acceptance — the change is complete when

- All 6 requirements above are met.
- Full pytest suite passes (target: 96+ tests).
- v0.9.0 is committed and pushed to origin/main per v0.8.0 auto-commit + push discipline.
- Coverage map for `test-completeness-enforcement` is fully green at Phase 7 master review.
- Final report cites: REQ-001 grep audit results, REQ-002 agent file path, REQ-003 hook test pass count, REQ-005 test count delta.
