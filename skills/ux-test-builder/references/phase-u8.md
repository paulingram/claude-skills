# Phase U8 — Bug routing to bug-fix-pipeline

Each routed bug carries its diagnosis downstream: the `bug-fix-pipeline` applies `superpowers:systematic-debugging` to replicate + root-cause every `ux-flow-failure` SR before any fix is proposed (per `## Plugin prerequisites (v3.9.0)`).

For every flow with consensus verdict `fail`:

1. The orchestrator writes a structured bug artifact at `<cwd>/.architect-team/ux-tests/<persona-slug>/bugs/<bug-N>.json`:

```json
{
  "bug_slug": "<persona-slug>--<flow-slug>",
  "flow_id": "<flow-N>",
  "persona_description": "<from intake>",
  "objectives": "<from intake>",
  "target_site": "<URL>",
  "literal_vs_actual": "<what the persona expected vs. what happened>",
  "playwright_spec_path": "<...>/playwright/<flow-N>-<slug>.spec.ts",
  "trace_paths": [<from all 3 executors>],
  "screenshot_paths": [<from all 3 executors>],
  "consensus_pass_count": <P>,
  "created_at": "<ISO 8601 UTC>"
}
```

2. The orchestrator creates a solution requirement at `<cwd>/.architect-team/solution-requirements/SR-ux-<bug-slug>-<ts>.json` with `origin.kind: "ux-flow-failure"` + `origin.source: <path to bug artifact>` + `acceptance_criteria: [<the Playwright flow path — the regression-test contract>]`. **Emit an `issue_discovered` notification** per routed SR (best-effort, per `## Notifications`) — invoke from the target project's root and proceed immediately regardless of outcome:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the flow's literal_vs_actual one-liner>" --details "<flow id + consensus verdict + the SR path it was routed as>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the flow's literal_vs_actual one-liner>" --details "<flow id + consensus verdict + the SR path it was routed as>"
   ```
3. The SR auto-routes through `bug-fix-pipeline` per the existing v0.9.22 dispatch — the orchestrator invokes `/architect-team:bug-fix` against each SR. The bug-fix pipeline's replicate → reproduce-test → propose → fix → QA-replay → sensibility-check → archive loop applies.

The UX test builder does NOT block on bug fixes. The bugs are queued; the final report at U9 includes the bug-fix dispatch references (SR paths + bug-fix branch names if Phase B8 commits landed during the session).

For flows with verdict `flaky` (the consensus-on-intermittence verdict — reached when the executors converge on the observation that the flow consistently fails some runs and passes others, NOT a cap reached by exhausting a cycle count), the SR is still written but carries `flakiness: true` — the bug-fix-pipeline's replicate step surfaces the flakiness rather than treating it as a deterministic bug.
