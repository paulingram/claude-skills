---
name: verification-planning
description: Use BEFORE verifying any claim — a fix, a feature, a deploy, a diagnosis — to choose HOW to verify it. Enumerates the verification venues (local run, dev environment, replay of captured artifacts, seeded fixture, production read-only checks), states what each uniquely provides, proves whether the claim depends on it, picks the cheapest faithful venue, and records the choice as a verification_plan artifact. Adds the cheaper-faithful-method-found counterpart to the stuck verdicts (cannot-verify-without-deploy / env-failure / blocked) so "I need to wait for prod" is never the reflex when a faithful cheaper method exists, and a gate that needs a live environment obliges the run to PROVIDE one rather than ask.
user-invocable: false
---

# Verification Planning — verification is a choice, never a lookup

Across 120 instruction files, roughly ten CT6 rules name a *mandatory venue* for one gate — "the real running dev environment", "LOCAL first, LIVE DEV last", "Phase 0 is a hard precondition: the live app must be running" — and, before v3.66.0, exactly zero asked the agent to ENUMERATE the ways a claim could be verified and choose among them. So at verify-time the agent's question was "which venue does this gate demand?", never "what is the cheapest faithful way to learn whether this is true?" — and the system shipped five ready-made labels meaning "I am stuck until the environment changes" (`cannot-verify-without-deploy`, `env-failure`, `target-state-unreachable-needs-seed-data`, `blocked`, `escalation-pending.md`) with no counterpart meaning "I found a cheaper faithful method". The field symptom: *"I need to wait before deploying to prod"* while a local run, a replay, or a seeded fixture would have settled the claim in a minute.

This skill is the missing primitive. It fires BEFORE verifying anything, it costs one small artifact, and it makes "I considered N venues and chose this one because the others cannot exhibit the claim" a recorded, auditable fact.

## The venue menu

| Venue | What it uniquely provides | Faithful for | Cost |
|---|---|---|---|
| **Local run** (unit / integration / a scratch script / a local build or container) | the code path, the built artifact, deterministic inputs | logic, contracts, build/bundle/config, most regressions | seconds |
| **Replay** (captured traces, request logs, recorded fixtures, a saved failing input) | the exact production-shaped input that failed, without production | reproductions, diagnoses, "does the fix change the captured outcome" | seconds–minutes |
| **Seeded fixture** (a dev database or store seeded through the application's own create path) | the target STATE a flow needs (the empty-list case, the expired session, the archived row) | flows whose precondition is a data state | minutes |
| **Stratified sample** (a seeded, stratified subset of the real table with its edge rows and the reported rows, materialized in a warehouse sandbox — `scripts/data_dictionary/sampling.py`) | real data at a fraction of the volume: the claim's own predicate stratified, NULLs / boundaries / duplicates / the named rows included, whole groups kept for aggregate-level changes | data transformations, data defects, "does this change alter these strata" | seconds–minutes |
| **Dev environment** (the deployed dev instance, real backend, real DB / queue / cache) | the deployed topology — real networking, auth proxy, secrets, cross-service calls | front-to-back integration, deploy-time behaviour, anything the deployed topology alone produces | minutes per cycle |
| **Production (read-only checks)** | real users' data shape, real traffic, real third parties | a `@prod-safe` smoke check of a shipped change — and NOTHING that mutates (`test-prod-safety-classifier`) | a user decision, never automatic |

A **stratified sample** is the cheapest faithful venue for a data claim whenever the full transformation takes minutes and the dictionary shows the table is large: it exhibits the claim's failure on real rows (the reported ones included) in seconds, and the full run stays the gate it confirms (`data-eng-pipeline` `## Sample-first iteration (v4.0.0)`; the rule in full is `skills/data-eng-pipeline/references/sample-first.md`).

Production is never a superior oracle. Nothing in CT6 states that production verifies something dev cannot; it verifies the same things later, at more risk, with fewer levers. It is the LAST venue, entered only on the user's explicit decision, and only for read-only checks.

## The four steps (do them in order, write them down)

1. **Enumerate.** List every venue above against the claim. Do not skip one because it "obviously" does not apply — write the one-line reason it does not.
2. **Prove dependence.** For each venue, name what it UNIQUELY provides, then answer: *does this claim depend on that?* A bundling bug does not depend on the deployed load balancer; a 401 produced by the auth proxy does. Per `expensive-verification-debugging` Phase 1, "the remote environment rarely adds diagnostic information a local artifact lacks" — prove it rather than assume it, in either direction.
3. **Choose the cheapest faithful venue.** Faithful means the venue can EXHIBIT the claim being false — the check could fail *because* the claim is wrong (`docs/ETHOS.md` `### A green check proves what it measured`). Among faithful venues, choose the cheapest. A gate that MANDATES a venue (the frontend-E2E loop-exit gate mandates a live environment for a frontend slice) is honoured as a gate — the plan then records that the venue is gate-mandated, and the cheaper venues still run FIRST for every claim they can settle.
4. **Record the plan.** Write the `verification_plan` artifact (below) into the verification evidence you are producing — the review-gate evidence, the QA-replayer verdict, the E2E verdict, the diagnostic-plan sidecar. A verdict that says "stuck" without a plan is refused (see the counterpart verdict).

## The `verification_plan` artifact

```json
{
  "claim": "the archive button removes the row and the row stays gone after reload",
  "venues_considered": [
    {"venue": "local run", "unique_provides": "the component + handler code path", "faithful": true, "why_not": null},
    {"venue": "replay", "unique_provides": "the captured failing request", "faithful": false, "why_not": "no capture exists for this flow"},
    {"venue": "seeded fixture", "unique_provides": "an archivable row in dev", "faithful": true, "why_not": null},
    {"venue": "dev environment", "unique_provides": "the deployed auth proxy + real DB", "faithful": true, "why_not": "gate-mandated for the frontend slice - runs AFTER the local + seeded checks"},
    {"venue": "production", "unique_provides": "real users' data", "faithful": false, "why_not": "mutating flow - never in prod"}
  ],
  "chosen_venue": "local run, then seeded fixture on dev (gate-mandated live run last)",
  "why_cheaper_venues_cannot_exhibit": "none - the local run is faithful for the handler; the live run is the gate, not the only oracle",
  "recorded_at": "<ISO 8601 UTC>"
}
```

`venues_considered` MUST carry at least two entries with a `venue` — one venue enumerated is a lookup, not a choice — and `chosen_venue` MUST be non-empty. `why_cheaper_venues_cannot_exhibit` is the sentence a reviewer reads first: it must name the specific thing the claim depends on that the cheaper venues lack.

## Stuck verdicts and the counterpart

- `cannot-verify-without-deploy` (and its siblings `env-failure`, `blocked`, `target-state-unreachable-needs-seed-data`) is legitimate ONLY when the artifact carries a `verification_plan` whose `venues_considered` shows every cheaper venue is not faithful for this claim. The 24th-tool family enforces it: `verify-target-element-measured` returns `stuck-without-verification-plan` for a `cannot-verify-without-deploy` verdict with no such plan (`hooks/vao/live_verification.py`). A stuck verdict without a plan is the reflex this skill exists to remove.
- **`cheaper-faithful-method-found`** is the counterpart verdict. When the plan shows a cheaper venue IS faithful, the agent records this verdict, runs the cheaper method, and cites its captured output — it does not wait. This verdict is never a reason to skip a gate-mandated venue; it is the reason the gate-mandated run is the confirmation rather than the first and only test.

## Providing the venue is the run's job

A gate that requires a live environment obliges the run to PROVIDE one — bring the local dev server up, run `prod_deploy.deploy_command`, seed the records the flow needs through the application's own create path, then run the flow. *"The route doesn't exist on dev until it's deployed"* is the deploy step, not a blocker; *"dev has zero campaigns so the screen has nothing to render"* is a fixture problem, not an untestable screen. Read and execute `skills/common-pipeline-conventions/references/local-dev-test-discipline.md` (the v3.57.0 discipline) before escalating anything environment-shaped. Waiting is not a verification method: *"How do you want to proceed?"* with a recommended option attached is the run asking permission to do its own job, and the answer was always the recommended option. Only a genuine external blocker escalates — a credential the run does not have, a production deploy (always the user's decision), a design decision only the owner can make — and it escalates naming the input, while every other venue's checks continue.

## No self-imposed limits on the search

The search for the cheapest faithful venue is investigation, and `docs/ETHOS.md` principle 8 governs it: enumerate every venue, prove dependence for each, and never truncate the enumeration on a turn count, a budget, or an "obvious" shortcut you set yourself. The only limits are the ones the user explicitly states.

## Where this skill fires

- `playwright-user-flows` Phase B — before authoring flows against a venue (the real-backend rule stands; the plan records WHY the real backend is the faithful venue for a `both`-layer feature, and which claims the cheaper venues settled first).
- `dev-api-integration-testing` — before the local-then-live sequence.
- `agents/integration.md` Phase 5 — before the reconciliation sweep's live-app precondition is treated as a blocker.
- `agents/qa-replayer.md` Phase B6 — a `cannot-verify-without-deploy` verdict carries the plan or is refused.
- `bug-fix-pipeline` Phases B5–B6 — the dev deploy is the default end-to-end venue, never a substitute for the cheapest faithful check of each claim along the way.
- `expensive-verification-debugging` Phase 1 — this skill generalises its "price the loop, find the cheapest faithful artifact" step from *an already-expensive failing loop* to *every verification, at planning time, before the first cycle*.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "I need the real environment to test this." | Name what the real environment UNIQUELY provides and prove the claim depends on it. Most build / config / logic / contract claims do not; the artifact is identical locally. |
| "Deploying IS the test." | Deploying is the most expensive possible test. Find the cheapest faithful venue, settle what it can settle, and reserve the deploy for the confirmation the gate mandates. |
| "The gate needs a live env, so I'll wait for someone to bring it up." | The gate obliges the RUN to provide the environment. Bring it up, seed it, run the flow — per `local-dev-test-discipline.md`. |
| "Static analysis is not a substitute for the live run, so there is nothing cheaper." | Static analysis is one venue; a local run, a replay, and a seeded fixture are three others. The live run stays the gate; it stops being the only oracle. |
| "Production will tell us for sure." | Production tells you the same thing later, with real users bearing the risk. It is a read-only smoke venue on the user's explicit decision, never the oracle of first resort. |
| "Enumerating five venues every time is overhead." | It is one small artifact, and it is the difference between a verification you chose and a wait you defaulted into. |

## Hard rules (non-negotiable)

- Every verification carries a `verification_plan` with ≥ 2 venues considered and a chosen venue; a stuck verdict without one is refused.
- The cheapest faithful venue runs FIRST; a gate-mandated venue runs as the confirmation, never as the first and only test.
- Production is entered only on the user's explicit decision, and only for `@prod-safe` read-only checks.
- A gate that needs a live environment obliges the run to provide it; asking is not a verification method.
- No self-imposed limits on the venue search (`docs/ETHOS.md` principle 8).
