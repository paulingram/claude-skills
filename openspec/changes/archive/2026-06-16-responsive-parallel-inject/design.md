## Context

`/architect-team:inject` writes to a per-run JSONL inbox (`hooks/inflight_inbox.py`) that the orchestrator polled only at phase boundaries, and the v2.5.0 discipline forbade spawning parallel teams for injected work. This change makes inject responsive + parallel WITHIN the harness's constraints.

## Goals / Non-Goals

- **Goal:** a separable injected problem opens a concurrent in-run lane (background team + disjoint lock), and the inbox is drained promptly (every wake), not only at phase boundaries.
- **Non-Goal:** true async push / preemption. The Lead is a single model-driven agent; this is aggressive polling, not an interrupt.
- **Non-Goal:** a new lock primitive — lane isolation reuses the existing `hooks/locks.py`.
- **Non-Goal:** wiring `cdlg_overlap` (call-graph overlap) into `acquire_lock` — out of scope; the residual is documented honestly instead.

## Reuse Decision Log

| Proposed unit | Decision | Rationale |
|---|---|---|
| Lane file-scope isolation | **REUSE** `hooks/locks.py::acquire_lock` / `globs_intersect` | The v1.0.0 lock layer already serializes overlapping scopes (`## Running in parallel sessions`); a lane is an intra-run lock holder. No new lock code. |
| Background dispatch + resume | **REUSE** `run_in_background: true` + `wrap_agent_result()` (`scripts/setup/agent_resume.py`) | The existing teams-mode dispatch + Background-agent resume discipline. |
| Convergence of lane output | **REUSE** Phase 4 reconciliation | Lanes converge exactly as parallel Phase 2 teammates do. |
| Verifier acceptance of `parallel-problem` | **REUSE** `verify_inflight_clarifications_processed` | It gates on `processed_at`, so a marked `parallel-problem` message counts automatically; only the remediation prose updated. |
| `parallel-problem` + `lane_id` | **EXTEND** `hooks/inflight_inbox.py` | Additive classification + field; preserves existing schema/locking/read-tolerance. |

## Key Decisions

- **Lane linkage is enforced in code:** `mark_processed` raises if `parallel-problem` has no `lane_id`, making "a lane actually opened" auditable on disk.
- **Sole-writer invariant preserved:** lanes are teammates that write unique-path artifacts and return requests; the orchestrator stays the single writer of `coverage-map.json` / `intake-state.json`, so background lanes create no shared-state write conflict.
- **Honest residuals (adversarial-review-driven):** polling-not-push; file-glob/advisory isolation (`cdlg_overlap` not wired in — keep lane scopes coarse; Phase 4 backstops); subagents-mode degrades lanes to sequential; failed lane spawn downgrades the classification.

## Risks / Mitigations

- **Risk: two file-disjoint lanes collide on a shared hot callee.** Mitigation: documented residual + "keep lane scopes coarse + prefer folding when independence is uncertain" + Phase 4 reconciliation backstop.
- **Risk: overclaiming concurrency in subagents-mode.** Mitigation: explicit dispatch-mode caveat (degrades to sequential).
