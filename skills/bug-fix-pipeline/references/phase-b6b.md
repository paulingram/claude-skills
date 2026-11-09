# Phase B6b — Logical Sensibility Check (v0.9.29)

After Phase B6 returns `bug-resolved` and BEFORE Phase B7's archive, the orchestrator runs a logical sensibility check on the impact set of the fix. Closes a real-world gap surfaced by user feedback:

> *"Why am I seeing 'Sign-in is unavailable — the authentication service is not configured for this build' when it clearly is? How did this make it out of your fix module and why didn't you catch this. The fix correctly routes Sign Back In to /login, but the deployed bundle is hermetic (no VITE_* baked), so the LoginScreen shows 'auth-unavailable.' There needs to be a post deployment check for sensibility on all elements touched."*

B6's QA-replay verifies the ORIGINAL symptom is gone (clicking Sign Back In routes to `/login` — necessary). The user's experience was still broken because `/login` itself rendered "auth-unavailable" — the fix didn't break the route, but the route's destination was broken independently and the QA-replay's narrow scope didn't catch it. B6b widens the verification: the agent reads the fix's git diff, computes the **impact set** (changed files + their importers + nav destinations + endpoints), and runs minimal Playwright sensibility flows on each impact-set item against the deployed dev environment.

**Why a new phase, not an enhancement to B6:** B6's `qa-replayer` runs the SPECIFIC reproduction artifact from B2. Its scope is intentionally narrow — "is the user's reported symptom gone?" Widening B6 would muddy that contract. B6b adds a separate phase + a separate agent (`fix-sensibility-checker`) so each role's responsibility stays crisp.

### Process

1. **Compute the impact set.** The orchestrator (or the dispatched `fix-sensibility-checker` agent — the canonical impact-set computation is in the agent body's `## Impact-set computation` section) reads `git diff <merge-base>..<fix-commit-sha> --name-only` and classifies each changed file (UI component / page / API endpoint / style / config). For each changed file, the agent expands to importers (one level — `git grep` for the file's import paths) + nav destinations (for changed pages — `<Link to=` / `router.push(` / `navigate(` patterns) + endpoints (for changed API handlers).
2. **The Lead creates a `fix-sensibility-checker` task in the shared list (teams mode) OR dispatches the `fix-sensibility-checker` subagent (subagents mode)** with the impact set + the deployed dev URL + the credentials env-var.
3. **The agent authors minimal Playwright sensibility flows per impact-set item.** Each flow is small (5-10 lines): navigate to the page / load the component / call the endpoint, and assert it renders without an error banner ("auth-unavailable", "service-unavailable", "configuration-missing", "could not load", "500", "404"), without console errors, without broken auth surfaces, without missing-data placeholders.
4. **The agent runs the sensibility flows against the deployed dev environment** (per `playwright-user-flows` — same real-running-app discipline as B6).
5. **Per-item verdict:** one of `sensible` / `nonsensical` / `env-failure` / `not-reachable`. Persisted in the agent's verdict file at `<cwd>/.architect-team/sensibility/<bug-slug>/checker-<ts>.json`.
6. **The orchestrator pools the verdicts:**
   - **All `sensible`** → B6b passes; proceed to B7.
   - **Any `nonsensical`** → the orchestrator writes a FRESH solution requirement for each `nonsensical` item with `origin.kind: "fix-regression"`, the failing impact-set item as the symptom, the captured trace + screenshots as evidence. The new SR routes back through the bug-fix-pipeline (recursive — a new B−1 → B8 loop on the new bug). The CURRENT fix is NOT marked complete; the new SR resolves first, then B6 + B6b re-run on the new state. Repeated `fix-regression` SRs on one run are an observability signal, never a count that escalates: the orchestrator continues from a different angle (re-routes through `diagnostic-research-team`, broadens the fix scope) per the loop-until-resolved subsection below and `docs/ETHOS.md` principle 8.
   - **Any `env-failure`** → routes to the implementing team for env diagnosis (parity with B6's `env-failure` handling).
   - **Any `not-reachable`** → logged in the verdict file as an audit-trail item; no SR generated (the item being not-reachable means the fix can't have broken it from the user's view).

### Unbounded recursion (loop until resolved)

The fix-regression loop runs until the bug is resolved end-to-end — there is NO iteration ceiling, per `architect-team-pipeline`'s `## Run-state: unbounded solving, concurrency, required-input gates`. Keep DETECTING recurrence: when the SAME fix-regression recurs (the original bug likely has a deeper architectural issue), do NOT stop — continue from a DIFFERENT angle: re-route through `diagnostic-research-team` for a deeper root-cause pass, broaden the fix scope, or try an alternate strategy, and surface the recurrence loudly. Track the fix-regression-cycle counter in the SR ledger purely as an observability signal. Only a genuine need for owner input (a deeper design decision only the owner can make) becomes a required-input pause via the marker — never a give-up.

### The --no-deploy skip

If the user invoked the bug-fix run with `--no-deploy` (the dev environment is hand-managed), B6b is SKIPPED with a note in the final report: *"Logical Sensibility Check (Phase B6b) was skipped because `--no-deploy` was set. The QA-replay at Phase B6 verified the original symptom is gone, but the impact set was NOT independently sensibility-checked. Consider re-running the bug-fix without `--no-deploy` for the full verification."* Phase B7 then runs without B6b's verdict.

### SR origin kinds the bug-fix-pipeline now recognizes

The SR-intake behavior inherited from the main pipeline's Phase 3b (when a bug-fix run is itself spawned by an SR, vs. directly via `/architect-team:bug-fix`) recognizes these SR origin kinds:

| `origin.kind` | Source phase | Routing |
|---|---|---|
| `ux-flow-failure` | `ux-test-builder` Phase U8 (v0.9.29) | Normal bug-fix-pipeline flow B−1 → B8, with the failing flow as the regression-test contract |
| `fix-regression` | bug-fix-pipeline Phase B6b (v0.9.29) | Same as above — recursive on the original bug-fix run |
| (other existing kinds — `rca-product-bug`, `playwright-failure`, etc.) | Various (v0.9.22 and prior) | Same |

### Target-element verification gate (v2.21.0)

After the qa-replayer's verdict but BEFORE proceeding to Phase B6b sensibility check, invoke the 19th Layer 3 tool against the qa-replayer's verification artifact:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-target-element-measured --artifact "<workspace>/.architect-team/qa-replays/<bug-slug>.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-target-element.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-target-element-measured --artifact "<workspace>/.architect-team/qa-replays/<bug-slug>.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-target-element.json"
```

If any of the 3 severities fires (`proxy-element-substituted` / `unreachable-state-not-escalated` / `semantic-target-mismatch`), the qa-replayer's `bug-resolved` verdict is OVERRIDDEN to `bug-still-present` with the gap as the explicit failure reason. The orchestrator routes an SR with `origin.kind: target-state-unreachable-needs-seed-data` so the responsible team seeds the missing target state. See `common-pipeline-conventions/SKILL.md` `## No proxy-element verification discipline (v2.21.0)` for the canonical home.
