# frontend-e2e-loop-exit-gate

## ADDED Requirements

### Requirement: A frontend-impacting run cannot complete without genuine passing E2E evidence
`hooks/pipeline-completion-audit.py` SHALL carry a `_audit_frontend_e2e` arm (registered in `audit()`) that determines the run's frontend impact by running `hooks/frontend_impact.py::changed_files_touch_frontend` over the union of `files_changed` across `.architect-team/reviews/*.json`. For a frontend-impacting run, the arm SHALL REQUIRE, per frontend slice, a genuine passing E2E verdict at `.architect-team/frontend-e2e/<slice>-verdict.json` (`verdict == "passed"`, `executed_against_live_env == true`, ≥1 `user_driven_actions`, a `trace_path` naming an existing file, ≥1 `visible_state_assertions`). A missing, non-passing, or incomplete verdict — OR a slice that touched a real frontend UI file but produced only a review-gate note — SHALL be a BLOCKING violation (the run does not complete/commit). The arm SHALL honor the `CT6_FRONTEND_E2E_GATE_DISABLED` kill-switch and SHALL be a no-op outside an active run and for a run that touched no frontend.

#### Scenario: A frontend run with no E2E verdict is blocked
- **WHEN** the completion audit runs on a run whose review evidence's `files_changed` touches a frontend UI file AND no passing `.architect-team/frontend-e2e/<slice>-verdict.json` exists
- **THEN** the audit returns a BLOCKING violation naming the frontend slice that lacks executed E2E evidence, and the run does not commit

#### Scenario: A run touching no frontend is unaffected
- **WHEN** the completion audit runs on a run whose changed files touch no frontend UI file
- **THEN** the `_audit_frontend_e2e` arm contributes zero violations (no-op)

### Requirement: A Layer-3 verifier validates that E2E evidence is genuine as-the-user testing
`hooks/vao/` SHALL provide `verify-frontend-e2e-loop-exit` (dispatched through the `hooks/vao_tools.py` facade — Layer-3 tool count 21 → 22). Given an E2E verdict artifact, it SHALL return `{valid, gaps[]}` and SHALL bite on four escape modes: `e2e-described-not-executed` (not executed against a live env / no trace), `e2e-api-only-no-user-actions` (no `page.click`/`fill`/`getByRole`/`check`/`selectOption` — only `page.request.*` / `fetch` / direct API), `e2e-vacuous-navigate-assert` (no assertion on visible end-to-end state), and `e2e-trace-claimed-but-absent` (`trace_path` set but the file does not exist). A genuine artifact (real user-driven actions + an existing trace + visible-state assertions) SHALL return `valid: true` with zero gaps.

#### Scenario: An API-only "E2E" test is flagged
- **WHEN** `verify-frontend-e2e-loop-exit` is run on an artifact whose only actions are `page.request.post(...)` calls with no click/fill
- **THEN** it returns `valid: false` with an `e2e-api-only-no-user-actions` gap

#### Scenario: A genuine click-driven E2E artifact passes
- **WHEN** the artifact has `page.click`/`page.fill` user actions, a `trace_path` that exists, and a `toBeVisible` assertion, executed against a live URL
- **THEN** the verifier returns `valid: true` with zero gaps

### Requirement: A frontend UI change cannot self-authorize away the E2E gate
`hooks/review_evidence_schema.py` SHALL keep `frontend_impact_e2e_review` conditionally required when `files_changed` touches frontend, and the run-level `_audit_frontend_e2e` arm SHALL be the backstop that a per-task `frontend_impact_e2e_review_note` cannot escape: a slice that touched a real frontend UI file requires the executed E2E verdict artifact at completion regardless of any note. The `n/a`/absent + note path SHALL be documented as legitimate ONLY for a frontend-adjacent change with no runnable UI surface.

#### Scenario: A note does not satisfy the run-level gate
- **WHEN** a slice sets `frontend_impact_e2e_review: "n/a"` with a note but its `files_changed` touched a real frontend UI file and no E2E verdict artifact exists
- **THEN** the completion audit blocks the run (the note is not a substitute for executed E2E evidence at the run level)
