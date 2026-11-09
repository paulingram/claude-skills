---
name: team-spawning-and-review-gates
description: Use when the orchestrator is dispatching teammates in Phase 2 or capturing review-gate evidence in Phase 3. Defines non-overlapping file-scope rules, plan-approval-mode triggers, direct teammate-to-teammate messaging conventions, the review-gate evidence file schema (v7 — the teammate's 17-field self-review including the 5 Verified Agent Output fields, plus an independent task-reviewer verdict), the independent task-reviewer dispatch, the teammate manifest format the SubagentStop hook reads, and escalation policy on repeated hook rejection.
user-invocable: false
---

# Team Spawning & Review Gates

The orchestrator's parallelism only works if every teammate has crisp boundaries and the review gates have evidence to enforce. This skill defines both.

## Operating context (v1.0.0) — for teammate agents

This section is the canonical long-lived-teammate framing every teammate agent in the architect-team pipeline references. Each `agents/*.md` body carries a one-line pointer here rather than re-stating the paragraph; this file is the single source of truth, so wording changes ship in one place.

You are a long-lived teammate in an architect-team run — not a one-shot subagent. The Lead spawns you and assigns work via the shared task list (teams mode) or dispatches you per-task (subagents mode); either way, you stay in your role across multiple tasks within this run and your 1M context window accumulates the run's prior decisions, maps, and review evidence. You receive tasks from the Lead; if your work surfaces a follow-up that needs a different agent type, you write a solution requirement and return to the Lead — you do NOT spawn other agents or teams yourself. Internal short-lived `Agent` subagents for sub-research within your task are permitted (per Claude Code's standard semantics) and are NOT a nested team.

## Non-overlapping file scopes

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/non-overlapping-file-scopes.md` and execute it in full. Do not work from memory.

Two teammates MUST NEVER edit the same file. Period.

## CDLG overlap — shared callees, not just shared files (lineage roadmap P4 — REQ-CDL-09 / REQ-PARA-01)

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/cdlg-overlap-shared-callees-not-just-shared-files-lineage-ro.md` and execute it in full. Do not work from memory.

File-path scoping (above) catches the case where two teammates edit the SAME
file. It does NOT catch the more subtle case the lineage roadmap surfaced: two
work-items edit DIFFERENT files but **share a hot callee** — item A's function
transitively calls a function that item B's slice also touches. Dispatching those
two in parallel is a hidden overlap: a change A makes to the shared callee's
behavior can break B even though their `files_owned` sets are disjoint.

## Canonical front→back traversal (lineage roadmap P4 — REQ-CDL-09 / REQ-PARA-02)

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/canonical-front-back-traversal-lineage-roadmap-p4-req-cdl-09.md` and execute it in full. Do not work from memory.

The CDLG also enables a single navigable traversal that chains the whole stack:

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

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/direct-teammate-to-teammate-messaging.md` and execute it in full. Do not work from memory.

When two teammates need to coordinate (e.g., backend defines a contract, frontend consumes it):

## Reading teammate state

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/reading-teammate-state.md` and execute it in full. Do not work from memory.

An orchestrator coordinating parallel teammates is constantly tempted to convert *absence of a report* into *a finding about the teammate*. It is not one. A teammate is in exactly one of three KNOWABLE states, and only two of them support a conclusion:

## Review-gate evidence file

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/review-gate-evidence-file.md` and execute it in full. Do not work from memory.

Path: `<cwd>/.architect-team/reviews/<task-id>.json`.

The Phase 3 task gate is a **tier-2** gate (`## Review tiers (v4.0.0)` below): the producer's 17-field self-review plus ONE paired independent verdict — the `task-reviewer`'s `independent_review` block, with `test-completeness-verifier` on the mechanical side — and a third independent verdict only when the two disagree. Three parallel reviewers are reserved for tier-3 gates (architecture approval, master review, map convergence). Schema v7 carries 17 required fields and 6 optional tool-mediated fields (`interactions_honored_review`, `live_verification_review`, `appearance_scope_review`, `check_integrity_review`, `claim_instrument_binding_review`, `principles_review`).

## Red-first — a new guard is not evidence until it has been shown to fail

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/red-first-a-new-guard-is-not-evidence-until-it-has-been-show.md` and execute it in full. Do not work from memory.

`tests.added` and `tests.passing` say a test exists and is green. Neither says the test can ever be anything else. A test that asserts something already true, targets a path the runner never collects, or exercises a code path the change did not touch is green on day one and green after the feature is deleted — it is a green light wired to nothing. This is the same rule the bug-fix pipeline has always enforced (the reproduction artifact must reproduce BEFORE it regresses); it applies to every NEW test in every pipeline, not only to bug reproductions.

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

## Baseline SHA capture

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/baseline-sha-capture.md` and execute it in full. Do not work from memory.

The orchestrator captures a single immutable SHA reference at run start and includes it in every teammate's spawn brief. Teammates use it to diff their own work against the run's baseline WITHOUT touching shared git state — no `git stash`, no `git reset`, no race.

## Solution Requirements — auto-spawn the dev loop on any surfaced issue

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/solution-requirements-auto-spawn-the-dev-loop-on-any-surface.md` and execute it in full. Do not work from memory.

Whenever an agent surfaces an issue during testing — a Playwright failure, an integration test failure, a live-dev-API regression, a visual-fidelity drift, an RCA product-bug verdict — the agent does NOT just write a handoff and wait. It ALSO writes a structured **solution requirement** that the orchestrator automatically picks up and feeds back into Phase 2 of the dev loop. The loop is closed: issue → solution requirement → fix team spawned → fix flows through Phase 2 → Phase 5 → original test re-runs → verdict pass → originating teammate's task unblocks.

## Hook-rejection escalation policy

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/hook-rejection-escalation-policy.md` and execute it in full. Do not work from memory.

When the `PostToolUse(TaskUpdate)` hook rejects a teammate's attempt to mark a task complete (exits 2), the teammate MUST follow this procedure:

## Independent review — the task-reviewer

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/independent-review-the-task-reviewer.md` and execute it in full. Do not work from memory.

The 17 top-level evidence fields are the teammate's **self-review**. A self-review is a producer checking its own work — the last producer-is-own-checker gap in the pipeline. The `PostToolUse(TaskUpdate)` hook does shape validation: it can confirm the evidence file is well-formed JSON with `"pass"` values; it cannot confirm those values are *true*. A teammate could write a perfectly-conformant evidence file that lies, and on shape validation alone the gate would open.

## Review evidence — what each field means in practice

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/review-evidence-what-each-field-means-in-practice.md` and execute it in full. Do not work from memory.

- `spec_review: "pass"` — teammate has self-reviewed against the acceptance criteria in the coverage map and confirms each criterion is met by their code.
- `quality_review: "pass"` — teammate has run linters, type checkers, and any project quality tools, all green.
- `real_not_stubbed: true` — teammate has grep'd its diff for `TODO`, `pass`, `NotImplementedError`, mock returns outside test fixtures, and confirms none exist.
- `reuse_compliance: "ok"` — every new file in `files_changed` corresponds to a Reuse Decision in `design.md`.
- `independent_review` — the verdict of the independent `task-reviewer` agent (NOT the teammate); see "## Independent review — the task-reviewer" above. Its `reviewer` must differ from `teammate`.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "I'll write the evidence file after I mark complete" | The hook fires on the TaskUpdate. Evidence must exist BEFORE. |
| "I can share a file with another teammate this once" | No. Hand off via direct messaging and a contract file owned by one side. |
| "Plan-approval mode is slowing me down" | It exists for the triggers above for a reason. Auth/schemas/contracts are where silent breakage costs most. |
| "I'll skip the manifest — the SubagentStop hook is paranoid" | The hook is exactly what keeps idle subagents from leaving work undone. Write the manifest. |
| "My self-review all says pass — I'll write the `independent_review` block myself and mark complete" | The producer cannot be its own checker. `independent_review.reviewer` must differ from `teammate`; an independent `task-reviewer` agent writes that block after reading your diff. A teammate filling it in itself is the exact self-attestation the hook rejects. |

## Review tiers (v4.0.0)

> **STOP.** Before dispatching reviewers for any gate, Read `skills/team-spawning-and-review-gates/references/review-tiers.md` and record the gate's tier in the brief.

Tier 3 (three independent reviewers + synthesis, Fable 5.1) is reserved for architecture approval, the master review, and map convergence; tier 2 (producer + one paired adversarial reviewer, mechanical verifiers on Sonnet 5.5) is the default for every Phase 3 task gate; tier 1 (one verifier, often a Layer-3 tool or a `prompt` hook, Haiku 5.5 or no model) covers classification and shape checks. The producer is never its own checker at any tier.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Non-overlapping file scopes` | `skills/team-spawning-and-review-gates/references/non-overlapping-file-scopes.md` | on demand |
| `CDLG overlap — shared callees, not just shared files (lineage roadmap P4 — REQ-CDL-09 / REQ-PARA-01)` | `skills/team-spawning-and-review-gates/references/cdlg-overlap-shared-callees-not-just-shared-files-lineage-ro.md` | on demand |
| `Canonical front→back traversal (lineage roadmap P4 — REQ-CDL-09 / REQ-PARA-02)` | `skills/team-spawning-and-review-gates/references/canonical-front-back-traversal-lineage-roadmap-p4-req-cdl-09.md` | on demand |
| `Direct teammate-to-teammate messaging` | `skills/team-spawning-and-review-gates/references/direct-teammate-to-teammate-messaging.md` | on demand |
| `Reading teammate state` | `skills/team-spawning-and-review-gates/references/reading-teammate-state.md` | on demand |
| `Review-gate evidence file` | `skills/team-spawning-and-review-gates/references/review-gate-evidence-file.md` | on demand |
| `Red-first — a new guard is not evidence until it has been shown to fail` | `skills/team-spawning-and-review-gates/references/red-first-a-new-guard-is-not-evidence-until-it-has-been-show.md` | on demand |
| `Baseline SHA capture` | `skills/team-spawning-and-review-gates/references/baseline-sha-capture.md` | on demand |
| `Solution Requirements — auto-spawn the dev loop on any surfaced issue` | `skills/team-spawning-and-review-gates/references/solution-requirements-auto-spawn-the-dev-loop-on-any-surface.md` | on demand |
| `Hook-rejection escalation policy` | `skills/team-spawning-and-review-gates/references/hook-rejection-escalation-policy.md` | on demand |
| `Independent review — the task-reviewer` | `skills/team-spawning-and-review-gates/references/independent-review-the-task-reviewer.md` | on demand |
| `Review evidence — what each field means in practice` | `skills/team-spawning-and-review-gates/references/review-evidence-what-each-field-means-in-practice.md` | on demand |
| `Review tiers (v4.0.0)` | `skills/team-spawning-and-review-gates/references/review-tiers.md` | on demand |
