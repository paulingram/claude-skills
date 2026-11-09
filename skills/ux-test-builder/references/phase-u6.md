# Phase U6 — Execution (`flow-executor` agents per the review tier)

This phase is the pipeline's `superpowers:verification-before-completion` gate — each flow's pass/fail verdict rests on captured evidence (trace + screenshots + per-step expectation deltas + the flow-effect witness), never an unverified assertion, per `## Plugin prerequisites (v3.9.0)`.

The orchestrator dispatches `flow-executor` agents per the review tier (`skills/team-spawning-and-review-gates/references/review-tiers.md`; the agent brief `agents/flow-executor.md` says the same) — **review tier 2 by default**: ONE executor runs every distilled flow (the authored flow with its `expected_user_effect` is the producer side; the executor is the paired independent verdict), a SECOND executor re-runs only the flows the first DISPUTES (a `fail`, a `flaky`, an `env-failure`, or a split between the Playwright assertion and the flow-effect witness), and a panel of three runs every flow in PARALLEL only when the user or a project principle raises the gate to tier 3. Each executor receives:

1. The full distilled-flow set + the Playwright `.spec.ts` files.
2. The target URL / dev environment URL.
3. The credentials env-var NAME (the secret is read from `os.environ[<name>]` at agent runtime).
4. The directive: *"Run every Playwright flow against the live target (the second executor: the disputed flows the Lead names). Document each flow's outcome with the captured trace + screenshot(s) + per-step expectation deltas. Each flow runs ONCE per executor; you are one of <1 | 2 | 3> Lead-dispatched executors and you do not consult the others."*

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

N executions by default plus one re-run per disputed flow (3N only on a tier-3 panel). The redundancy — a second independent run of every disputed flow, three of every flow at tier 3 — IS the consensus mechanism: flakiness, intermittent UI states, race conditions, and environment dependencies surface as DISAGREEMENTS between executors rather than silently passing, and a clean `pass` with a `pass` witness from the paired executor is the producer and the checker agreeing.

Bracket each dispatch with the v3.34.0 dispatch-wait pair per `## Notifications` — emit `waiting_on_agents` (`--agents "flow-executor-1 — run all N flows"`, then `"flow-executor-2 — re-run the <K> disputed flows"`, or all three on a tier-3 panel, + `--details "<N flows against <target>; tier <2|3>>"`) as the dispatch goes out, and `agents_complete` (per-executor pass/fail/flaky/env-failure tallies) when the executors have persisted every flow result. The same pair brackets each U7 re-examination round.

**Flow-effect witness (v0.9.32) — MANDATORY per flow.** Each executor runs Step 3.5 of `agents/flow-executor.md`: for every flow with an `expected_user_effect` block (authored at U5), the executor verifies the declared effects actually occurred — by scanning the captured trace's network log + DOM snapshot + console log + final URL. A flow's Playwright assertion can pass via a wrong code path (a selector that grabbed a sibling button labeled "Upload" but pointing at a different endpoint; a redirect that landed on a similar-looking page) while the persona's actual user-effect never happened. The witness catches that. A `flow_effect_witness: { verdict: "fail" }` forces the flow's overall verdict to `fail` with `failure_reason: "flow-effect-not-witnessed"` — even if Playwright reported pass. U8 bug-routing reads `failure_reason` and writes the SR with `origin.kind: "flow-effect-gap"` so the receiving bug-fix run knows the flow's path was wrong, not just that "something didn't work." Parallel discipline to Phase B6's `test-did-not-exercise-fix` (v0.9.31) and Phase 5's `feature-tests-did-not-exercise-implementation` (v0.9.32) — same underlying failure mode, adapted to the UX domain where there's no fix-diff or feature-commit but there IS a persona's declared intent.
