---
change: test-completeness-enforcement
status: in_progress
---

# Tasks

## T-001 — REQ-001 language audit + tighten

- Grep-audit: `skills/playwright-user-flows/`, `skills/dev-api-integration-testing/`, `skills/frontend-route-mapping/`, `skills/visual-fidelity-reconciliation/`, `agents/frontend.md`, `agents/integration.md`, `agents/backend.md`, `commands/architect-team.md`, `commands/visual-qa.md`.
- Identify any reference to "Playwright test" / "user-flow test" / "e2e test" that does NOT explicitly state real-user simulation.
- Tighten: add the unambiguous language ("simulates a real human via `page.goto` / `page.click` / `page.fill` / `page.waitFor`; asserts visible state; direct API calls via `page.evaluate(() => fetch())` / `page.request.*` / `axios.*` from inside a Playwright test are FORBIDDEN except for `page.route` mocking specific error paths and asset-resolution verification") to:
  - `skills/playwright-user-flows/SKILL.md` Phase B "Real-user simulation" (already strong; add the `page.evaluate(fetch)` / `page.request.*` explicit rejection).
  - `skills/playwright-user-flows/SKILL.md` anti-patterns table (add the specific anti-pattern row).
  - `agents/frontend.md` hard rules (add the explicit forbidden patterns).
  - `agents/integration.md` hard rules.
  - `agents/backend.md` (only if it references Playwright — likely doesn't, but check).
- `files_owned`: the 9 files above.

## T-002 — REQ-002 new `test-completeness-verifier` agent

- Create `agents/test-completeness-verifier.md` with:
  - Frontmatter: `name`, `description`, `tools: Read, Glob, Grep, LS, Bash, TodoWrite` (READ-ONLY), `model: sonnet`, `color: red`.
  - Body: inputs (`task_id`, review evidence path, coverage-map slice); process (check each kind: unit/integration/Playwright + grep-audit Playwright source for the forbidden API-direct-call anti-patterns); output schema (`<cwd>/.architect-team/test-completeness/<task-id>-<ts>.json`); escalation (write SR with `origin.kind: "test-completeness-failure"`); hard rules (read-only; never edits; never silently passes).
- `files_owned`: `agents/test-completeness-verifier.md`.

## T-003 — REQ-003 hook field enforcement

- Edit `hooks/review-gate-task.py`:
  - Add `"test_completeness_review"` to `REQUIRED_EVIDENCE_FIELDS`.
  - Add `VALID_TEST_COMPLETENESS_VALUES = {"pass", "n/a", "fail"}`.
  - In `_validate()`, add the parallel branch to the existing `visual_fidelity_review` check: invalid value → block; `"fail"` → block with escalation message; `"n/a"` → require non-empty `test_completeness_review_note`.
- `files_owned`: `hooks/review-gate-task.py`.

## T-004 — REQ-004 + REQ-005 wire SR loop + tests

- Update `skills/team-spawning-and-review-gates/SKILL.md` `## Solution Requirements`: add `"test-completeness-failure"` to the `origin.kind` enum; update schema example.
- Update `skills/team-spawning-and-review-gates/SKILL.md` review-evidence schema: bump v2 → v3; add `test_completeness_review` field documentation.
- Update `tests/test_review_gate_task.py`:
  - Update `_valid_evidence()` helper: bump `schema_version` to 3; add `test_completeness_review: "n/a"` + `test_completeness_review_note: "..."`.
  - Add new test cases (mirror the existing v0.5.0 visual-fidelity tests): pass / fail-blocks / missing-blocks / invalid-value-blocks (parametrized) / n/a-without-note-blocks (parametrized).
- Update `tests/test_agents.py` `EXPECTED_AGENTS`: add `test-completeness-verifier`.
- `files_owned`: `skills/team-spawning-and-review-gates/SKILL.md`, `tests/test_review_gate_task.py`, `tests/test_agents.py`.

## T-005 — REQ-006 docs + version bump

- `CHANGELOG.md`: prepend v0.9.0 entry covering REQ-001..005.
- `README.md`: update banner version `v0.8.1` → `v0.9.0`; update "What you get" agent count `10` → `11`; add Loop 4d to "The Loops"; update status timeline.
- `docs/CODEBASE_MAP.md`: targeted refresh — agent table adds `test-completeness-verifier` row; tests count updated; system overview mentions test-completeness enforcement; mermaid adds the node + edge.
- `.claude-plugin/plugin.json` + `marketplace.json`: version `0.8.1` → `0.9.0`.
- `files_owned`: `CHANGELOG.md`, `README.md`, `docs/CODEBASE_MAP.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.

## T-006 — Integration verification

- Run `python -m pytest -v`. Expect total ≥ 96 (90 baseline + ≥ 6 new for `test_completeness_review`). All pass.
- Grep audit for REQ-001 acceptance: confirm the forbidden-pattern language is present in the named files.
- Confirm `agents/test-completeness-verifier.md` parses cleanly (frontmatter valid).
