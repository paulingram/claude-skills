# Phase U4 — Distillation (orchestrator-serialized)

The orchestrator reads every expansion (10-15 raw proposals from the default single explorer, 3 × 10-15 = 30-45 from a tier-3 panel, + the 1 literal) and deduplicates SEMANTICALLY — two flows that produce the same user-visible outcome via different selectors are duplicates; two flows that touch different upload entry points are NOT duplicates even if they look similar in code. The orchestrator uses the flows' `goal_one_line` + `steps[]` + `rationale` to judge.

Persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/distilled-flows.json` with the unique set (typically 8-15 flows after dedup from one explorer; 15-25 from a panel). Each entry carries `source_explorers: [<N>, ...]` crediting which explorer(s) proposed it; the literal flow's entry has `source_explorers: ["literal"]`.

**Run-start notification — the kickoff email carrying the test plan (v3.34.0, best-effort, per `## Notifications`).** The moment the distilled set is persisted — this run's test plan exists — the orchestrator emits `run_start` ONCE, embedding the plan itself so stakeholders receive the full flow catalog in ONE email. Pass `--details` with the persona, objectives, target, and the distilled-count breakdown:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_start --project <name> --run-id "ux-test-<persona-slug>" --details "<persona + objectives + target + N distilled flows (literal + explorer breakdown)>" --next-step "Phase U5 — Playwright authoring per distilled flow" --plan-file "<cwd>/.architect-team/ux-tests/<persona-slug>/distilled-flows.json" --plan-file "<cwd>/.architect-team/ux-tests/<persona-slug>/literal-flow.json" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_start --project <name> --run-id "ux-test-<persona-slug>" --details "<persona + objectives + target + N distilled flows (literal + explorer breakdown)>" --next-step "Phase U5 — Playwright authoring per distilled flow" --plan-file "<cwd>/.architect-team/ux-tests/<persona-slug>/distilled-flows.json" --plan-file "<cwd>/.architect-team/ux-tests/<persona-slug>/literal-flow.json"
```
