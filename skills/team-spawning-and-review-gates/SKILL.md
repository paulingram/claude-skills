---
name: team-spawning-and-review-gates
description: Use when the orchestrator dispatches teammates in Phase 2 or captures review-gate evidence in Phase 3. File-scope rules, plan-approval-mode triggers, evidence schema v7 (self-review, Verified Agent Output fields, task-reviewer verdict), the SubagentStop teammate manifest, escalation on repeated hook rejection.
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
file.

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

An orchestrator coordinating parallel teammates is constantly tempted to convert *absence of a report* into *a finding about the teammate*.

## Review-gate evidence file

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/review-gate-evidence-file.md` and execute it in full. Do not work from memory.

Path: `<cwd>/.architect-team/reviews/<task-id>.json` -- the schema v7 file (17 required self-review fields, 6 optional tool-mediated fields, and the `task-reviewer`'s `independent_review` verdict) that the Phase 3 tier-2 task gate reads before a task may complete.

## Red-first — a new guard is not evidence until it has been shown to fail

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/red-first-a-new-guard-is-not-evidence-until-it-has-been-show.md` and execute it in full. Do not work from memory.

`tests.added` and `tests.passing` say a test exists and is green.

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

The orchestrator captures a single immutable SHA reference at run start and includes it in every teammate's spawn brief.

## Solution Requirements — auto-spawn the dev loop on any surfaced issue

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/solution-requirements-auto-spawn-the-dev-loop-on-any-surface.md` and execute it in full. Do not work from memory.

Whenever an agent surfaces an issue during testing it ALSO writes a structured **solution requirement** that the orchestrator feeds back into Phase 2, closing the loop: issue -> solution requirement -> fix team -> Phase 2 -> Phase 5 -> re-run -> the originating task unblocks.

## Hook-rejection escalation policy

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/hook-rejection-escalation-policy.md` and execute it in full. Do not work from memory.

When the `PostToolUse(TaskUpdate)` hook rejects a teammate's attempt to mark a task complete (exits 2), the teammate MUST follow this procedure:

## Independent review — the task-reviewer

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/independent-review-the-task-reviewer.md` and execute it in full. Do not work from memory.

The 17 top-level evidence fields are the teammate's **self-review**.

## Review evidence — what each field means in practice

> **STOP.** Before acting under this section, Read `skills/team-spawning-and-review-gates/references/review-evidence-what-each-field-means-in-practice.md` and execute it in full. Do not work from memory.

Each of the 17 self-review fields has a concrete meaning (`spec_review`, `quality_review`, `real_not_stubbed`, `reuse_compliance`, ...), and `independent_review` is the `task-reviewer`'s verdict, whose `reviewer` must differ from `teammate`.

## Anti-patterns to reject

> **STOP.** Before accepting any rationalization that bends a scope, evidence or review rule, Read `skills/team-spawning-and-review-gates/references/anti-patterns-to-reject.md` and execute it in full.

Every rationalization for a shared file, a late evidence file, a skipped manifest, skipped plan-approval or a self-written `independent_review` block is rejected; the chapter carries each with its rebuttal.

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
| `Anti-patterns to reject` | `skills/team-spawning-and-review-gates/references/anti-patterns-to-reject.md` | on demand |
| `Review tiers (v4.0.0)` | `skills/team-spawning-and-review-gates/references/review-tiers.md` | on demand |
