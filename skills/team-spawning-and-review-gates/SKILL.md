---
name: team-spawning-and-review-gates
description: Use when the orchestrator is dispatching teammates in Phase 2 or capturing review-gate evidence in Phase 3. Defines non-overlapping file-scope rules, plan-approval-mode triggers, direct teammate-to-teammate messaging conventions, the review-gate evidence file schema, the teammate manifest format the SubagentStop hook reads, and escalation policy on repeated hook rejection.
---

# Team Spawning & Review Gates

The orchestrator's parallelism only works if every teammate has crisp boundaries and the review gates have evidence to enforce. This skill defines both.

## Non-overlapping file scopes

Two teammates MUST NEVER edit the same file. Period.

### How to assign scopes

1. Read `tasks.md` and the coverage map.
2. For each task, list every file it will create or modify (use the design.md's Reuse Decisions as the canonical list).
3. Group tasks by overlapping file sets. Each non-overlapping group becomes one teammate's scope.
4. If a single task forces overlap (e.g., a contract file that backend writes and frontend consumes), assign the task to ONE owner and have the other consume the result — see "Direct messaging" below.

### What to put in the teammate's brief

- `task_ids`: the exact task IDs from `tasks.md` it owns.
- `files_owned`: the explicit list of files it may write. Anything not in this list is read-only for this teammate.
- `files_consumed`: files it reads but does not write (with the owning teammate's name where relevant).
- `acceptance_criteria`: verbatim from the coverage map.
- `relevant_codebase_map_sections`: paths into CODEBASE_MAP.md.
- `reuse_decisions`: the relevant entries from `design.md`'s Reuse Decisions section.
- `plan_approval_mode`: `true` if any of the triggers below apply.

## Plan-approval-mode triggers (any one)

If a teammate's scope touches ANY of:

- Authentication / authorization code.
- DB schema (migrations, model changes).
- API contracts (OpenAPI / GraphQL SDL / gRPC proto / RPC schemas).
- Cross-service contracts (queue message schemas, shared event types).
- External integrations (third-party APIs, webhooks).
- Secrets / config / env-var schemas.

→ spawn the teammate in plan-approval mode. The orchestrator reviews and explicitly approves the plan before any tool calls run.

## Direct teammate-to-teammate messaging

When two teammates need to coordinate (e.g., backend defines a contract, frontend consumes it):

- The owning teammate publishes its result to a known path (e.g., the contract file, plus a brief in `.architect-team/handoffs/<owner>-to-<consumer>.md`).
- The consuming teammate is told in its brief: "Wait for the handoff from `<owner>` at `<path>` before starting tasks T-X, T-Y."
- Every cross-team message MUST be written to `.architect-team/handoffs/<from>-to-<to>-<timestamp>.md` — this is the primary coordination primitive and survives across sessions.
- If the harness exposes a teammate-messaging mechanism (e.g., `SendMessage`), use it as an optional shortcut in ADDITION to (not in place of) the handoff file. The orchestrator does NOT proxy.

## Review-gate evidence file

Path: `<cwd>/.architect-team/reviews/<task-id>.json`.

The teammate writes this BEFORE its `TaskUpdate` flips the task to `completed`. The `PostToolUse(TaskUpdate)` hook reads it and exits 2 (blocks completion) if it's missing or any field is invalid.

Schema (v4 — v0.9.5 added `integration_testing_review` + optional `integration_testing_review_note`; v0.9.0 added `test_completeness_review` + optional `test_completeness_review_note`; v0.5.0 added `visual_fidelity_review` + optional `visual_fidelity_review_note`):

```json
{
  "schema_version": 4,
  "task_id": "T-12",
  "teammate": "backend-auth",
  "completed_at": "<ISO 8601 UTC>",
  "spec_review": "pass",
  "quality_review": "pass",
  "real_not_stubbed": true,
  "tests": {
    "added": 8,
    "passing": 8,
    "unit": ["tests/auth/test_login.py::test_happy", "..."],
    "integration": ["tests/integration/test_login_dev_api.py::test_login_against_dev"],
    "e2e": []
  },
  "demo_artifact": "curl -X POST http://dev.local/api/auth/login -d '{\"email\":\"t@t.com\",\"password\":\"...\"}'",
  "files_changed": ["src/auth/login.py", "src/auth/__init__.py", "tests/auth/test_login.py"],
  "reuse_compliance": "ok",
  "visual_fidelity_review": "n/a",
  "visual_fidelity_review_note": "backend-only slice; no frontend files touched",
  "test_completeness_review": "n/a",
  "test_completeness_review_note": "backend-only slice; integration tests count as the qualifying kind for this slice",
  "integration_testing_review": "n/a",
  "integration_testing_review_note": "backend-only slice with no frontend; no cross-layer surface to integration-test front-to-back"
}
```

Required field validity:

- `spec_review` and `quality_review` must be `"pass"`.
- `real_not_stubbed` must be `true`.
- `tests.added` must equal `tests.passing`.
- `tests.added` must be ≥ 1.
- `demo_artifact` must be a non-empty string.
- `files_changed` must be a non-empty array.
- `reuse_compliance` must be `"ok"`.
- `visual_fidelity_review` must be one of `"pass"` / `"n/a"` / `"fail"`. The hook BLOCKS `"fail"` — drift / gaps detected by `visual-fidelity-reconciliation` MUST be escalated via handoff, not marked complete. Re-run reconciliation after the architect-routed fix and only mark complete when verdict is `"pass"`.
- `visual_fidelity_review_note` is required (non-empty string) WHEN `visual_fidelity_review == "n/a"`. It must explain which branch applies (no frontend touched, OR no DESIGN_MAP.md exists for the codebase). Not required when value is `"pass"` (the reconciliation JSON paths carry the evidence).
- `test_completeness_review` must be one of `"pass"` / `"n/a"` / `"fail"`. The hook BLOCKS `"fail"` — test-kind completeness gaps detected by `test-completeness-verifier` MUST be escalated via the SR auto-spawn (`origin.kind: "test-completeness-failure"`), not marked complete. The verifier writes the SR automatically; wait for the orchestrator to re-spawn the fix loop, then re-run the verifier to reach `"pass"`.
- `test_completeness_review_note` is required (non-empty string) WHEN `test_completeness_review == "n/a"`. It must explain which kind(s) are inapplicable and why (e.g., backend-only slice so Playwright is n/a, OR no testable pure-logic surface for unit tests). Not required when value is `"pass"` (the verifier verdict JSON carries the evidence).
- `integration_testing_review` must be one of `"pass"` / `"n/a"` / `"fail"`. The hook BLOCKS `"fail"` — a `both`-layer feature whose happy-path user-flow tests ran against a mocked / fake backend (`page.route` happy-path stubs, MSW, an in-memory fake API server, hardcoded fixtures) instead of the real running backend MUST be re-authored against the real backend, or escalated via the SR auto-spawn (`origin.kind: "integration-testing-failure"`), not marked complete. Front-to-back integration testing is the DEFAULT for every `both`-layer feature per `playwright-user-flows`'s "Real backend by default" discipline — it is overridden only by an explicit authorization in the requirements folder.
- `integration_testing_review_note` is required (non-empty string) WHEN `integration_testing_review == "n/a"`. It must give ONE of three legitimate reasons: (1) the slice has no cross-layer surface (pure static frontend with no backend, OR backend-only slice with no frontend); (2) Phase 3 per-team gate where the counterpart layer is not yet integrated — the note says the integration test is DEFERRED TO PHASE 5 (a debt Phase 5 must settle against the real backend; `n/a` is never valid for a `both`-layer slice at Phase 5); (3) the requirements folder explicitly authorizes isolated / mock-backed testing for this requirement — the note quotes the authorization. Not required when value is `"pass"` (the verifier verdict JSON + the demo artifact's real-backend reference carry the evidence).

Any missing or failing field → hook blocks. Re-engage on the failing item, fix, update evidence, retry.

## Teammate manifest

Path: `<cwd>/.architect-team/teammates/<teammate-name>.json`.

The orchestrator writes this when spawning. The `SubagentStop` hook reads it on subagent stop to validate the teammate didn't go idle with uncompleted work.

Schema:

```json
{
  "schema_version": 1,
  "teammate": "backend-auth",
  "spawned_at": "<ISO 8601 UTC>",
  "task_ids": ["T-10", "T-11", "T-12"],
  "files_owned": ["src/auth/login.py", "tests/auth/test_login.py", "..."],
  "expected_review_evidence": ["T-10", "T-11", "T-12"]
}
```

The hook checks that for every `task_id` in `expected_review_evidence`, there's a valid review-evidence file. If not → exit 2 with a structured error naming the gaps. The harness re-engages the teammate.

## Solution Requirements — auto-spawn the dev loop on any surfaced issue

Whenever an agent surfaces an issue during testing — a Playwright failure, an integration test failure, a live-dev-API regression, a visual-fidelity drift, an RCA product-bug verdict — the agent does NOT just write a handoff and wait. It ALSO writes a structured **solution requirement** that the orchestrator automatically picks up and feeds back into Phase 2 of the dev loop. The loop is closed: issue → solution requirement → fix team spawned → fix flows through Phase 2 → Phase 5 → original test re-runs → verdict pass → originating teammate's task unblocks.

This converts "alert the user" into "fix the system." Alerts that don't trigger remediation are process failures; the discipline is to spawn the remediation, not log the alert.

### File location

```
<cwd>/.architect-team/solution-requirements/SR-<short-id>-<ISO-8601-UTC>.json
```

where `<short-id>` is derived from the originating test ID, drifted screen+element, or affected requirement. Use `_safe_id()`-compatible characters only (no `/`, `\`, leading `.`, or `..`).

### Schema

```json
{
  "schema_version": 1,
  "solution_id": "SR-test_user_completes_first_login-2026-05-18T15:00:00Z",
  "created_at": "<ISO 8601 UTC>",
  "origin": {
    "kind": "playwright-failure" | "integration-test-failure" | "live-dev-regression" | "visual-fidelity-drift" | "rca-product-bug" | "visual-qa-audit" | "test-completeness-failure" | "integration-testing-failure" | "editability-gap",
    "discovered_in": "Phase 3" | "Phase 5" | "/architect-team:visual-qa" | "ad-hoc",
    "discovered_by": "<teammate-name or 'integration' or 'visual-qa'>",
    "test_id": "<failing test ID, if applicable>",
    "rca_artifact": "<path to rca/<test-id>-<ts>.json, if applicable>",
    "reconciliation_artifact": "<path to visual-fidelity/<screen>-<viewport>-<ts>.json, if applicable>",
    "handoff_artifact": "<path to .architect-team/handoffs/<from>-to-<to>-<ts>.md if also written>"
  },
  "problem_summary": "<one-paragraph user-facing description: what the user sees that they should not, in product terms not implementation terms>",
  "expected_behavior": "<one-paragraph spec citation: what DESIGN_MAP / coverage-map / proposal.md says SHOULD happen>",
  "evidence": [
    "<path to log excerpt / screenshot / captured payload>",
    "<file:line citation>",
    "..."
  ],
  "affected_requirements": ["REQ-012", "REQ-019"],
  "affected_screens": ["/login", "/dashboard"],
  "scope": {
    "files_to_change": ["src/auth/login.py", "src/auth/__init__.py"],
    "files_to_test": ["tests/integration/test_login_dev_api.py", "tests/playwright/test_login.spec.ts"]
  },
  "acceptance_criteria": [
    "POST /api/auth/login with a soft-deleted account returns 410 Gone with body {error: 'account_deactivated'}",
    "POST /api/auth/login with a valid account returns 200 with body.user.name as a non-null string matching the DB row's name column",
    "Existing test_user_completes_first_login passes against the live dev API",
    "Visual-fidelity reconciliation for /dashboard's user-name banner reaches verdict perfect"
  ],
  "suggested_team": "backend-auth",
  "blast_radius": "single endpoint; no schema changes; safe to deploy with the existing release window",
  "priority": "critical" | "high" | "medium" | "low",
  "status": "open"
}
```

### Required field validity

- `solution_id` must be unique and `_safe_id()`-compatible.
- `origin.kind` must be one of the enumerated values (`playwright-failure`, `integration-test-failure`, `live-dev-regression`, `visual-fidelity-drift`, `rca-product-bug`, `visual-qa-audit`, `test-completeness-failure`, `integration-testing-failure`, `editability-gap`); agents MUST NOT invent new kinds.
- `editability-gap` SRs spawn a fix team DIRECTLY — they do NOT route through `diagnostic-research-team`. The `editability-completeness` team's converged map already names the exact attribute, the exact trace stage that breaks, and the exact file; the diagnosis is complete, so no diagnostic research is needed. (The test-failure origins — `rca-product-bug`, `playwright-failure`, `integration-failure`, `integration-testing-failure`, `test-completeness-failure`, `visual-fidelity-cascade` — DO route through `diagnostic-research-team` first; `editability-gap` does not.)
- `problem_summary` and `expected_behavior` are non-empty strings.
- `evidence` is a non-empty array; an SR without evidence is an alert dressed as a requirement.
- `affected_requirements` may be empty if the problem is in territory not yet covered by the coverage map — but then `affected_screens` (for visual) or `scope.files_to_change` MUST be non-empty so the orchestrator can attribute the fix.
- `acceptance_criteria` MUST include the original failing test as one of its criteria. The fix is only complete when the test that surfaced the issue passes.
- `suggested_team` is a hint; the orchestrator may route differently based on file ownership.
- `priority` defaults to `"high"` for any RCA product-bug, `"critical"` for any visual-fidelity drift blocking a designed user journey, and per-case judgment otherwise.

### Orchestrator pickup (architect-team-pipeline behavior)

When the orchestrator resumes (after any subagent signals idle), it MUST:

1. Walk `.architect-team/solution-requirements/*.json`.
2. For each SR with `status: "open"`:
   - If `affected_requirements` is non-empty → append entries to the active change's `coverage-map.json` referencing the SR ID; mark each entry `status: "in_progress"` once the fix team is spawned.
   - If `affected_requirements` is empty → write a new coverage-map entry derived from `acceptance_criteria` + `affected_screens` + `scope`.
   - Spawn a Phase 2 team per `team-spawning-and-review-gates` rules. The teammate's brief includes the SR ID, the SR file path, the acceptance criteria copied verbatim, the files_owned from `scope.files_to_change`, and a pointer to the original failing test that becomes the team's review-gate verification.
   - Update SR `status: "in_progress"` and record the spawned teammate name in a new `spawned_teammate` field.
3. The fix team works through Phase 3 (review gate) → Phase 4 (reconciliation if shared boundary) → Phase 5 (the original failing test re-runs as part of integration).
4. When the originating test reaches verdict `pass`, the orchestrator marks the SR `status: "resolved"` with a `resolved_at` timestamp and a `resolved_by` commit SHA, then unblocks the ORIGINATING teammate's task. The originating teammate re-runs whatever they were waiting on (visual-fidelity reconciliation, RCA, etc.) and that loop now converges to pass.
5. Master review (Phase 7) walks every SR and confirms each is `resolved` AND its acceptance criteria are reflected in a passing test in the coverage map.

### What this prevents

- Alerts that sit in a handoff file forever until someone manually triages them.
- Failures that surface, get logged, and don't translate into a code change.
- Teammates that mark their task `visual_fidelity_review: "fail"` and leave the fix to the user.
- Phase 5 failures that route back to a team in name only, with no concrete acceptance criteria attached.
- Process drift where "we'll fix it next sprint" silently re-enters the backlog instead of the active loop.

### Mandatory consumers (these skills write SRs on every applicable trigger)

- `root-cause-test-failures` Phase C — every `product-bug` RCA verdict writes an SR alongside the handoff. The handoff is for human readability; the SR is for orchestrator action.
- `visual-fidelity-reconciliation` Phase E — every escalation (out-of-scope file, implementation-extras, spec-ambiguity, cascade-blast-radius) writes an SR. Drift that gets autonomously fixed-to-spec does NOT need an SR (the fix happened in-loop).
- `playwright-user-flows` — when a Playwright test fails AND the RCA verdict is product-bug, the SR is written by RCA (don't duplicate). When a test reveals a UI contract that the implementation never honored (gap in the original spec), write an SR with `origin.kind: "playwright-failure"`.
- `dev-api-integration-testing` — when an integration test fails against the live dev API with a backend regression (RCA verdict product-bug), the SR is written by RCA. When the failure is in test-author error or env / fixture / race, fix in-loop without an SR (per root-cause-test-failures Phase C).
- `test-completeness-verifier` agent — every `overall: fail` writes an SR with `origin.kind: "test-completeness-failure"` so the orchestrator re-spawns the originating team with concrete missing-test acceptance criteria. The originating team re-enters Phase 2 to author the missing tests, passes Phase 3, and the verifier re-runs in Phase 5 to confirm. When the failure is specifically a `both`-layer feature whose happy-path user-flow tests ran against a mocked / fake backend (the `backend_integration_audit` is `mock_backed` with no explicit requirements authorization), the verifier instead uses `origin.kind: "integration-testing-failure"` — the orchestrator routes this through `diagnostic-research-team` (it is a test-failure origin) before spawning the fix team, and the `acceptance_criteria` mandate re-authoring the happy path against the real running backend.
- `editability-completeness` team — every gap in the converged editable-surface map (an attribute a user should be able to control whose end-to-end trace breaks: a `missing-control`, `dead-control`, `orphan-field`, `no-readback`, or `schema-mismatch`) becomes an SR with `origin.kind: "editability-gap"`. The `acceptance_criteria` are end-to-end and concrete: the create/edit flow has a working control for the attribute, the value reaches the database, the read-back returns it, and a real-backend integration test covers the round-trip. The fix team is spawned directly. After the fixes land, the three `editability-reviewer` agents re-spawn and re-review until the converged map has zero gaps.
- `visual-verification-team` (the `system-architect` Visual Gap Synthesis role) — spawned in Phase 5 (and by `/architect-team:visual-qa`). After the team's `visual-capture` agents render the LIVE app and its `visual-analyzer` agents produce per-screen gap lists, the synthesis clusters the gaps into root causes and writes one SR per gap cluster with `origin.kind: "visual-fidelity-drift"`. The `acceptance_criteria` mandate that the live app match the DESIGN_MAP Oracle for every screen in the cluster, re-verified by the team against the running app. A team `blocked` verdict (the live app would not run) or `incomplete` (the sweep did not cover every screen) escalates to the human, not a fix team — an unrunnable app or an incomplete sweep is a prerequisite defect, not a fix-team task.

### Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "The handoff is enough — the orchestrator can read it" | The handoff is markdown for humans. The SR is JSON for machine action. Without the SR, the orchestrator has nothing structured to spawn a team from. |
| "I'll write a brief SR and let the fix team figure out the details" | Then the fix team negotiates the spec instead of executing it, and the acceptance criteria drift. Write the full SR with concrete acceptance criteria — the originating test MUST be among them. |
| "I'll skip the SR if the fix is obvious" | "Obvious" fixes still need acceptance criteria, evidence, and a loop entry. Otherwise the master review (Phase 7) has nothing to walk. |
| "I'll wait for the orchestrator to ask before writing the SR" | The orchestrator picks up SRs from disk; it does not poll teammates for status. If you don't write the SR, the loop does not re-enter. |
| "The fix touches files outside my scope; I'll let the user spawn the next team" | That is the scope-out-of-bounds escalation — write the SR with `suggested_team` set to the owning team. The orchestrator routes; the user does not need to be in the loop unless the SR has a spec-ambiguity. |
| "I'll set priority to medium to be neutral" | RCA product-bugs blocking a documented user journey are critical or high. The priority drives queue ordering at Phase 2 spawn time. Be honest, not modest. |

## Hook-rejection escalation policy

When the `PostToolUse(TaskUpdate)` hook rejects a teammate's attempt to mark a task complete (exits 2), the teammate MUST follow this procedure:

**Threshold:** after **3 consecutive hook rejections on the same `task_id`**, the teammate STOPS attempting to mark the task complete and escalates instead.

**Step 1 — Stop retrying.** Do not attempt a fourth `TaskUpdate(status=completed)` for the same `task_id`. Further attempts will keep failing and waste context.

**Step 2 — Write an escalation handoff.** Create a file at:

```
<cwd>/.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<timestamp>.md
```

The file MUST contain:
- The task ID.
- The exact stderr output the hook reported for each of the 3 rejections (copy verbatim).
- What was tried to close each reported gap and why each attempt failed.
- The specific clarification or action the teammate needs from the orchestrator (e.g., a schema correction, a scope reassignment, an evidence-field waiver with justification).

**Step 3 — Wait.** Do not proceed with other tasks that depend on the stuck task. Signal idle. The orchestrator will inspect the handoff, either resolve the blocker (correct the task, update the manifest, or explicitly waive a field) and re-engage, or reassign the task to a different teammate.

**Note:** this policy is currently enforced by documentation (the teammate's own discipline). Code-level enforcement (counting consecutive rejections in the hook) is a v0.3.0 candidate if real-world data shows teammates ignoring the 3-rejection threshold.

## Review evidence — what each field means in practice

- `spec_review: "pass"` — teammate has self-reviewed against the acceptance criteria in the coverage map and confirms each criterion is met by their code.
- `quality_review: "pass"` — teammate has run linters, type checkers, and any project quality tools, all green.
- `real_not_stubbed: true` — teammate has grep'd its diff for `TODO`, `pass`, `NotImplementedError`, mock returns outside test fixtures, and confirms none exist.
- `reuse_compliance: "ok"` — every new file in `files_changed` corresponds to a Reuse Decision in `design.md`.

If any of these can't be honestly asserted, the teammate goes back to work — it does not falsify the evidence file. The hook does shape validation; honesty is enforced by the teammate's own discipline + by the orchestrator's spot checks.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "I'll write the evidence file after I mark complete" | The hook fires on the TaskUpdate. Evidence must exist BEFORE. |
| "I can share a file with another teammate this once" | No. Hand off via direct messaging and a contract file owned by one side. |
| "Plan-approval mode is slowing me down" | It exists for the triggers above for a reason. Auth/schemas/contracts are where silent breakage costs most. |
| "I'll skip the manifest — the SubagentStop hook is paranoid" | The hook is exactly what keeps idle subagents from leaving work undone. Write the manifest. |
