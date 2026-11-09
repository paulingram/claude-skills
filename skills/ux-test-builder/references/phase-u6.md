# Phase U6 — Parallel execution (3 `flow-executor` agents)

This phase is the pipeline's `superpowers:verification-before-completion` gate — each flow's pass/fail verdict rests on captured evidence (trace + screenshots + per-step expectation deltas + the flow-effect witness), never an unverified assertion, per `## Plugin prerequisites (v3.9.0)`.

The orchestrator dispatches 3 `flow-executor` agents in PARALLEL. Each receives:

1. The full distilled-flow set + the Playwright `.spec.ts` files.
2. The target URL / dev environment URL.
3. The credentials env-var NAME (the secret is read from `os.environ[<name>]` at agent runtime).
4. The directive: *"Run every Playwright flow against the live target. Document each flow's outcome with the captured trace + screenshot(s) + per-step expectation deltas. Each flow runs ONCE per executor; you are one of three."*

Each executor persists per-flow results at `<cwd>/.architect-team/ux-tests/<persona-slug>/executions/executor-<N>/<flow-N>.json`:

```json
{
  "executor": <1|2|3>,
  "flow_id": "<flow-N>",
  "verdict": "pass" | "fail" | "flaky" | "env-failure",
  "trace_path": "<...>/traces/<flow-N>.zip",
  "screenshots": ["<path>", ...],
  "expectation_deltas": [{step, expected, actual, match: bool}, ...],
  "flow_effect_witness": {
    "verdict": "pass" | "fail" | "n/a",
    "expected_user_effects": [{kind, value, observed: bool}, ...],
    "gap_if_failed": "<for fail: which effects were not observed>"
  },
  "failure_reason": "flow-effect-not-witnessed" | "playwright-assertion-failed" | "env-failure" | null,
  "duration_ms": <int>,
  "executed_at": "<ISO 8601 UTC>",
  "notes": "<one-line summary>"
}
```

3 executors × N flows = 3N total executions. The redundancy IS the consensus mechanism — flakiness, intermittent UI states, race conditions, and environment dependencies surface as DISAGREEMENTS rather than silently passing.

Bracket the dispatch with the v3.34.0 dispatch-wait pair per `## Notifications` — emit `waiting_on_agents` (`--agents "flow-executor-1 — run all N flows; flow-executor-2 — run all N flows; flow-executor-3 — run all N flows"` + `--details "<N flows × 3 executors against <target>>"`) as the parallel dispatch goes out, and `agents_complete` (per-executor pass/fail/flaky/env-failure tallies) when all 3 executors have persisted every flow result. The same pair brackets each U7 re-examination round.

**Flow-effect witness (v0.9.32) — MANDATORY per flow.** Each executor runs Step 3.5 of `agents/flow-executor.md`: for every flow with an `expected_user_effect` block (authored at U5), the executor verifies the declared effects actually occurred — by scanning the captured trace's network log + DOM snapshot + console log + final URL. A flow's Playwright assertion can pass via a wrong code path (a selector that grabbed a sibling button labeled "Upload" but pointing at a different endpoint; a redirect that landed on a similar-looking page) while the persona's actual user-effect never happened. The witness catches that. A `flow_effect_witness: { verdict: "fail" }` forces the flow's overall verdict to `fail` with `failure_reason: "flow-effect-not-witnessed"` — even if Playwright reported pass. U8 bug-routing reads `failure_reason` and writes the SR with `origin.kind: "flow-effect-gap"` so the receiving bug-fix run knows the flow's path was wrong, not just that "something didn't work." Parallel discipline to Phase B6's `test-did-not-exercise-fix` (v0.9.31) and Phase 5's `feature-tests-did-not-exercise-implementation` (v0.9.32) — same underlying failure mode, adapted to the UX domain where there's no fix-diff or feature-commit but there IS a persona's declared intent.
