# Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)

**Contract-first parallelism (v3.48.0) — before the dispatch.** If the slice needs backend surfaces the frontend must visualize (a new endpoint, or new attributes on an existing one), engage `contract-first-parallelism` first: the two agents co-design the inbound surface contract, the Lead approves it (the mini variant's Lead absorbs the `system-architect` `## Interface Contract Approval` role), and the backend provisions the endpoint AT ITS REAL PATH with a contract-conforming provisional payload registered in `<workspace>/.architect-team/contracts/ledger.json` and its retirement gate registered with `... declare-gate --json <contract.json> --registry "<workspace>/.architect-team/declared-gates.json"`. The frontend then builds its complete integration against the live surface instead of waiting on the backend's internals. The mock-retirement gate runs at M7 — see there.

The Lead creates `backend` + `frontend` tasks **in parallel** in the shared list (teams mode) OR dispatches the `backend` and `frontend` subagents **in parallel** via a single Agent-tool call carrying multiple invocations (subagents mode) — mirrors `architect-team-pipeline` Phase 2. Bracket the dispatch with the v3.34.0 dispatch-wait pair per `## Notifications` — emit `waiting_on_agents` (`--agents "backend-dev — <backend slice>; frontend-dev — <frontend slice>"`) as the parallel dispatch goes out, and `agents_complete` (per-dev outcomes incl. the cross-review verdicts) when both devs have returned. The same pair brackets the Phase M5 `mini-qa` dispatch. Each dev applies `superpowers:test-driven-development` — write the failing test before the implementation code, per `## Plugin prerequisites (v3.9.0)`. Each receives:

- `tasks.md` from M2/M3 — with the file-scope partition.
- `coverage-map.json` — including the `qa_guidance` block.
- The cached maps from M1.

Per `team-spawning-and-review-gates`, the file scopes MUST NOT overlap. If the architect's `tasks.md` accidentally overlaps scopes, this is an M3 failure — return to M3 with the conflict noted (does not consume an M8 cycle).

### Cross-review (no `task-reviewer` agent)

Instead of dispatching a separate `task-reviewer` agent, the **two devs cross-review each other's diffs**:

- After `backend` writes its `self_review` block in the review-evidence file (v7), the orchestrator dispatches `frontend` with the additional task of writing the `independent_review` block for `backend`'s evidence file (and vice versa).
- The v7 schema's existing `reviewer != teammate` invariant is satisfied: `frontend` reviewing `backend`'s task has `teammate: backend, reviewer: frontend`, which is not the self-review forbidden pattern.
- The cross-review is **lightweight** — verify the diff matches the task's acceptance criteria, run the linters/type-checkers the diff touches, grep the diff for `TODO`, `NotImplementedError`, mock-return placeholders, and the new-file Reuse Decision.

The trade-off: weaker independence than a dedicated reviewer. Mitigation: `mini-qa`'s coverage check at M5 catches missing test coverage; the `/architect-team:mini-review-sweep` command catches the rest in batch.

On review-evidence write, the existing `hooks/review-gate-task.py` runs unchanged — the dev↔dev cross-review case satisfies the existing schema invariants and needs no hook change (verified by `tests/test_mini_review_gate_dev_cross_check.py`).
