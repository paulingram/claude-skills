# Phase M5 — mini-qa runs unit + integration + narrow Playwright

The Lead creates a `mini-qa` task in the shared list (teams mode) OR dispatches the `mini-qa` subagent (subagents mode) with:

- `proposal.md` (its `## QA Guidance` section is authoritative scope).
- `coverage-map.json` (the `qa_guidance` block mirrors the markdown; they MUST agree or the verdict is `red-with-evidence`).
- The git diff produced by M4.
- The dev-environment URL(s) from the target project's `design.md` `## Dev Environment` section.
- The slug.
- The current cycle number `<N>` (1 on first invocation; M8 increments on re-eval).

`mini-qa` runs per its agent spec: read QA Guidance, verify unit + integration coverage exists, run both suites, author ≤ 3 Playwright flows, deploy to dev, run Playwright against the live dev URL, emit verdict.

**Deploy notification (best-effort, per `## Notifications`).** When `mini-qa` brings the dev environment up for the Playwright run, the orchestrator emits a `deploy` event with `--layer <layer>`. Invoke from the target project's root and proceed immediately regardless of the notifier's outcome:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer>
```

This `deploy` invocation is best-effort and NEVER blocks, fails, or delays bringing the dev environment up — a notifier failure does not affect the deploy or the QA run.

Per `dev-api-integration-testing`, integration tests MUST hit the real dev API; mocks are reserved for truly external, non-deterministic dependencies. Per `playwright-user-flows`, every Playwright flow is genuine user-driven interaction (page.goto → click → fill → waitFor → assert visible state), not an endpoint call masquerading as a flow.

`mini-qa` writes `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json` per cycle.
