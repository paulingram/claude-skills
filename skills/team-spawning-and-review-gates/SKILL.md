---
name: team-spawning-and-review-gates
description: Use when the orchestrator is dispatching teammates in Phase 2 or capturing review-gate evidence in Phase 3. Defines non-overlapping file-scope rules, plan-approval-mode triggers, direct teammate-to-teammate messaging conventions, the review-gate evidence file schema, and the teammate manifest format the SubagentStop hook reads.
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
- Direct messages use the harness's teammate-messaging mechanism (e.g., `SendMessage` if the harness exposes one). The orchestrator does NOT proxy.
- Every cross-team message is also written to `.architect-team/handoffs/<from>-to-<to>-<timestamp>.md` for audit.

## Review-gate evidence file

Path: `<cwd>/.architect-team/reviews/<task-id>.json`.

The teammate writes this BEFORE its `TaskUpdate` flips the task to `completed`. The `PostToolUse(TaskUpdate)` hook reads it and exits 2 (blocks completion) if it's missing or any field is invalid.

Schema:

```json
{
  "schema_version": 1,
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
  "reuse_compliance": "ok"
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
