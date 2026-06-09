---
name: expensive-verification-debugging
description: Use when debugging a failure whose verification cycle is expensive — a container rebuild, an ECS / Kubernetes / Cloud Run rolling deploy, a slow CI run, a long compile, any feedback loop with a multi-minute turnaround — or when you notice you have already burned two or more deploy / rebuild cycles fixing one bug at a time. Triggers — "I'll fix this one and redeploy to see", whack-a-mole config debugging, a greenfield Docker / Vite / build / CI pipeline that has never run end-to-end, an env var or asset that is not reaching the production bundle, sequential one-fix-per-deploy loops, "the deploy is rolling, waiting to verify". Establishes that when verification is expensive you audit the entire failure pathway and batch every fix before spending a cycle, rather than hunting one root cause at a time.
---

# Expensive-Verification Debugging — Audit the Whole Pathway, Batch the Fixes

When a verify cycle is cheap (re-run a unit test, ~1 second), debugging one hypothesis at a time is fine — a wrong guess costs a second. When a verify cycle is expensive (a Docker rebuild + ECS rolling deploy, ~3-4 minutes), the SAME one-hypothesis-at-a-time habit becomes catastrophic: every incomplete diagnosis burns a full cycle, and a symptom with three independent causes costs three cycles plus the debugging time between them.

The fix is not "debug faster." It is to change strategy when the loop is expensive: **stop hunting a single root cause, audit every stage of the failure pathway statically, find every defect, fix them all in one batch, confirm against the cheapest local artifact, and spend the expensive cycle once.**

Four disciplines:

1. **Price the loop first.** Before debugging, name the cost of one verification cycle out loud. A 1-second test re-run and a 4-minute deploy demand different strategies. If the cycle is expensive, the cost of an incomplete diagnosis is multiplied by every wasted cycle — so the diagnosis must be complete before the first cycle.
2. **Audit the pathway, do not hunt the root cause.** A symptom at the end of a multi-stage pathway can be broken at ANY stage — and on a never-before-run (greenfield) pathway, multiple stages broken at once is the EXPECTED case, not bad luck. Enumerate every stage; check every one statically; find every defect. "I found the bug" is wrong framing — you found *a* bug.
3. **Find the cheapest faithful artifact.** The expensive remote environment rarely adds diagnostic information a local artifact lacks. Identify the cheapest artifact that still exhibits the symptom — a locally-built bundle, a locally-built image, a locally-run container — and debug against THAT. Spend the expensive cycle only on what genuinely requires the remote environment.
4. **Batch the fixes; spend the expensive cycle once.** Fix every defect the pathway audit surfaced, confirm the batch against the cheap artifact, and only then run the expensive cycle — once.

This skill is the cost-aware companion to `root-cause-test-failures`. RCA's 3-pass loop converges on *the* root cause and assumes a cheap re-run; this skill handles the case where the loop is expensive AND the symptom may have several independent causes. Apply both: RCA for the per-stage analysis, this skill for the strategy.

## When this skill fires

- You are about to verify a fix by means of a deploy, a container rebuild, a rolling rollout, a slow CI run, a long compile — anything with a multi-minute turnaround.
- You have already run 2+ such cycles for the SAME symptom. (This is a hard STRATEGY-SWITCH signal — stop the one-bug-per-cycle whack-a-mole and pivot to the pathway-audit + batch-all-fixes strategy; see "Strategy switch" below. The run keeps going — only the inefficient approach stops.)
- You are standing up a NEW expensive pathway — a first Dockerfile, a first CI workflow, a first Vite/build config — that has never run end-to-end. Apply this skill **proactively, before the first cycle** (the proactive form below).
- A symptom is "downstream": an env var, asset, secret, or config value is not reaching a built/deployed artifact, and the chain from source to artifact has several stages.

This skill does NOT fire for cheap-loop debugging (sub-second test re-runs, hot-reload). There, normal RCA is enough.

## Phase 1 — Price the loop and name the cheapest faithful artifact

Before touching any fix:

1. **State the verify cost.** Write it down: "one verification cycle = `docker build` + `docker push` + ECS rolling deploy ≈ 3-4 min." If you do not know the cost, measure one cycle, then proceed with the discipline.
2. **Name the cheapest faithful artifact.** Ask: what is the *cheapest* thing I can produce locally that still exhibits this symptom? For a bundling / env-inlining / asset bug, the locally-built bundle (`npm run build` → `dist/`) is faithful and free. For a Docker COPY / layer bug, a local `docker build` + `docker run` is faithful and ~10× cheaper than a remote rollout. For a CI-script bug, running the job's commands locally (or in the same container image) is faithful.
3. **Prove the remote environment is actually needed — or prove it is not.** List exactly what the expensive remote environment uniquely provides: real secrets manager, real networking / DNS, real load balancer, real production data. Then ask: *does this bug depend on any of those?* A build-time bug (env var not inlined, asset not copied, layer missing) does NOT — the built artifact is identical locally and remotely. If the bug does not depend on anything the remote environment uniquely provides, the remote environment has ZERO diagnostic value for it; debug locally.

If a faithful local artifact exists, you debug against it for the entire pathway audit. The expensive cycle is reserved for the *one* final confirmation, plus anything that genuinely depends on the remote environment.

## Phase 2 — Audit the entire failure pathway (the pathway-audit artifact)

Do not look for "the bug." Map the **pathway**: the ordered sequence of stages a value / asset / request must pass through to go from its origin to the observable point where the symptom appears. Each stage is an independent potential break.

For every stage, run a STATIC check (read the file, grep the config, inspect the local artifact) — no expensive cycle. Record the verdict and any defect.

Persist `<cwd>/.architect-team/failure-pathway/<symptom-slug>-<ISO-8601-UTC>.json`:

```json
{
  "schema_version": 1,
  "symptom": "<the observable failure, concretely — e.g. 'VITE_API_URL is undefined in the deployed app'>",
  "audited_at": "<ISO 8601 UTC>",
  "verification_cost": {
    "cycle": "<what one verify cycle is — e.g. docker build + ECS rolling deploy>",
    "duration": "<~3-4 min>",
    "cheapest_faithful_artifact": "<cheapest local artifact that exhibits the symptom — e.g. local `npm run build` output in dist/>",
    "remote_env_uniquely_provides": ["<things only the remote env has>"],
    "bug_depends_on_remote_env": false
  },
  "pathway": [
    {
      "stage": "<name of the stage>",
      "location": "<file / config the stage lives in>",
      "static_check": "<the check you ran statically, with no expensive cycle>",
      "verdict": "ok | broken",
      "defect": "<null, or the concrete defect — file:line + what is wrong>"
    }
  ],
  "defects_found": ["<every defect, enumerated — there may be more than one>"],
  "fix_batch": ["<every fix, to be applied together before the next verify>"],
  "cheap_verification": "<how the fix batch was confirmed against the cheap artifact, with the command + the observed result>",
  "expensive_cycles_spent": 0,
  "escalated": false
}
```

You cannot fill `pathway` honestly without checking every stage, and you cannot fill `defects_found` without surfacing every break. The artifact IS the discipline — it makes "I found the bug" (singular) impossible to write down.

**Rule: audit every stage even after you find a break.** Discovering a defect at stage 2 RAISES the prior that stages 3 and 4 are also broken (same author, same untested pathway, same greenfield). It never lowers it. Keep going to the end of the pathway.

## Phase 3 — Batch every fix, verify cheap, then spend the expensive cycle once

1. Apply every fix in `fix_batch` — all of them, together.
2. **Confirm against the cheapest faithful artifact.** Rebuild the bundle locally and grep it for the expected literal value. Rebuild the image locally and run the container. Do whatever the cheap artifact allows. Record the command and the observed result in `cheap_verification`.
3. Only when the cheap artifact shows the symptom resolved do you spend ONE expensive cycle for the final, environment-dependent confirmation.
4. If the expensive cycle still shows the symptom: a stage was missed, OR a defect genuinely depends on the remote environment. Re-audit — extend the pathway, do not revert. **Never revert a fix you statically proved was a defect just because the symptom persisted** — a proven defect (the `.dockerignore` literally listed `.env`) stays fixed; persistence means there are MORE defects, not that the proven one was wrong. Reverting proven fixes is how a 3-cycle bug becomes a 10-cycle bug.

## Proactive form — audit a greenfield pathway before its first cycle

The strongest application: do not wait for the first failure. When you stand up a NEW expensive pathway (a first Dockerfile, a first deploy workflow, a first build config), NO stage has ever been exercised — assume every stage is broken until statically proven otherwise. Run the Phase 2 pathway audit BEFORE the first deploy. The first expensive cycle of a greenfield pipeline should be a confirmation, not a discovery.

## Strategy switch — after 2 expensive cycles, change approach (don't stop)

If you have spent **2 expensive cycles on the same symptom** without resolution, STOP THE WHACK-A-MOLE — but NOT the run. The dev-loop keeps solving; you change strategy from one-bug-per-expensive-cycle to pathway-audit-then-batch. There is no give-up cap here (per `common-pipeline-conventions` `## Unbounded solving discipline`) — two cycles is the signal that the inline one-at-a-time approach has taken over, so switch approaches rather than starting a third blind cycle. Instead:

1. Complete the Phase 2 pathway audit fully (you almost certainly skipped stages).
2. If the audit now shows a clear batch of defects → apply Phase 3 (cheap verify, batch ALL the fixes, then ONE cycle). Keep batching across further rounds as needed — the batch-all-fixes efficiency discipline never stops solving, it just avoids spending an expensive cycle per bug.
3. If the pathway audit is genuinely inconclusive → re-route for deeper diagnosis: write a solution requirement per `team-spawning-and-review-gates` with `origin.kind: "rca-product-bug"`, attach the pathway-audit artifact, and signal idle. The orchestrator routes it through `diagnostic-research-team` — three researchers map the full pathway independently. Three fresh perspectives on the whole pathway beats a fourth solo cycle. This is a CONTINUATION of solving (the diagnostic loop itself is unbounded), not a halt.

## Communicating cost (do not grind silently)

When the loop is expensive, the user is paying for every cycle in wall-clock time. Per the v0.9.2 pipeline-discipline rule, also:

- **State the plan and the expected cycle count up front:** "This needs a deploy to verify (~4 min/cycle). I have audited the pathway and found N defects; fixing all N, then one deploy." Do not narrate one bug at a time across N surprise cycles.
- **While an unavoidable expensive cycle runs, poll its status with a tight bounded loop** (e.g., poll the ECS service / health endpoint) — do NOT schedule a wall-clock wakeup, do NOT idle-monologue "waiting + verifying". Use the wait productively: re-audit remaining stages, prepare the cheap-verification grep, so a failed cycle has its next batch ready.
- If you have hit the 2-cycle strategy-switch threshold, **tell the user you are switching to the pathway-audit + batch strategy** rather than silently starting a third one-bug-at-a-time cycle. (You are not stopping — you are changing approach.)

## Worked example — env var not reaching a deployed Vite app

**Symptom:** `VITE_API_URL` is `undefined` in the app running on ECS.

**The whack-a-mole path (what burns cycles):** fix `.dockerignore`, deploy (4 min), still broken; fix the Dockerfile `COPY`, deploy (4 min), still broken; fix the code's `import.meta` access, deploy (4 min), works. Three cycles, ~12 min of deploys plus debugging between each.

**The pathway-audit path (one cycle):**

*Phase 1.* Verify cost = `docker build` + ECS rolling deploy ≈ 3-4 min. Cheapest faithful artifact = a local `npm run build` → `dist/` (~30 s), because Vite inlines `VITE_*` env vars at **build time** — the bundle is byte-identical locally and on ECS. ECS uniquely provides real SSM / ALB / DNS; the bug "env var not in the bundle" depends on NONE of those. So: debug entirely against the local bundle.

*Phase 2 — audit all four stages statically:*

| Stage | Location | Static check | Verdict |
|---|---|---|---|
| 1. env value defined | `.env` | does `.env` exist with `VITE_API_URL`? | ok |
| 2. survives the build context | `.dockerignore` | does `.dockerignore` exclude `.env`? | **broken** — `.dockerignore` lists `.env` |
| 3. COPYd into the build image | `Dockerfile` | is there a `COPY .env* ./` before the build step? | **broken** — no such line |
| 4. statically inlined by Vite | `src/**` | is `import.meta.env` accessed as a direct literal `import.meta.env.VITE_API_URL`? | **broken** — `src/config.ts` uses `(import.meta as Foo).env` — the cast defeats Vite's static text/AST replacement, so the value is never baked in |

`defects_found`: 3. (Three independent breaks, all on one pathway — exactly what a greenfield, never-run deploy pipeline produces.)

*Phase 3.* Fix all three: drop `.env` from `.dockerignore`; add `COPY .env* ./` to the Dockerfile; change the code to a direct `import.meta.env.VITE_API_URL` literal. Confirm cheap: `docker build` locally, then `grep -r "<expected API URL value>" dist/` (or inside the built image) — the literal is now baked in. THEN one ECS deploy to confirm in the real environment. **One expensive cycle instead of three.**

The agent in the real incident said afterward "I should have spotted #3 first by inspecting the bundle." Inspecting the bundle is Phase 1's cheapest-faithful-artifact step. This skill makes it the first move, not the retrospective regret.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "Let me fix this one and redeploy to see." | Each deploy is minutes. "Redeploy to see" makes the expensive cycle do the work a free static read should do. Audit the whole pathway first; deploy to *confirm*, not to *discover*. |
| "I found the bug." | You found *a* bug. A symptom at the end of a multi-stage pathway can be broken at several stages independently — and on a greenfield pathway that is the expected case. Finish the pathway audit. |
| "The fix didn't work, so my diagnosis was wrong — let me revert it." | Or your diagnosis was *incomplete*. A defect you statically proved (the `.dockerignore` literally excluded `.env`) is a real defect regardless of whether the symptom cleared. Reverting proven fixes turns a 3-cycle bug into a 10-cycle bug. Persistence means MORE defects downstream — keep auditing. |
| "I'll inspect the bundle / image after I deploy." | The bundle and the image are LOCAL artifacts. Build and inspect them before deploying. The remote environment almost never adds diagnostic information a local build lacks for a build-time bug. |
| "I need the real environment to test this." | Name exactly what the real environment uniquely provides (secrets, networking, data). Then prove the bug depends on one of those. Most build / config / bundling / COPY bugs do not — the artifact is identical locally. |
| "Deploying IS the test." | Deploying is the most expensive possible test. Find the cheapest faithful artifact that exhibits the symptom and test against that; reserve the deploy for environment-dependent confirmation. |
| "I'm close, just one more deploy." | "Close" after 2 expensive cycles is a sunk-cost signal, not a progress signal. Switch strategy at cycle 2: complete the pathway audit and batch the fixes, or re-route to `diagnostic-research-team`. (Keep solving — change the approach, don't stop the run.) |
| "It's a new pipeline, of course the first deploy fails — I'll fix as I go." | A greenfield pathway has correlated failure: every stage is unproven, so multiple stages are broken. "Fix as I go" = one expensive cycle per stage. Audit the whole new pathway statically before the first cycle. |
| "I'll just keep the user posted while I iterate." | Narrating one surprise cycle at a time is not keeping the user posted — it is grinding in public. State the cost, the defect count, and the plan up front; spend one cycle. |

## Red flags — switch strategy

Any one of these means stop the one-bug-per-cycle whack-a-mole and run the pathway audit (or re-route to `diagnostic-research-team`). The run keeps solving — only the inefficient approach stops:

- You have run 2+ deploy / rebuild / slow-CI cycles for the same symptom.
- You are about to start an expensive cycle to "see if it worked" without a local check first.
- Your diagnosis names exactly one cause and you have not inspected the other stages of the pathway.
- You reverted a fix because "the symptom persisted" without proving the fix was wrong.
- You are waiting on a remote cycle and have not built / run the artifact locally.
- You are standing up a brand-new Docker / CI / build pipeline and are about to run it for the first time without a static stage-by-stage audit.
- You are narrating "fixed bug N, deploying, waiting" for the Nth time.

## Where this skill plugs into the pipeline

- **Phase 5 — Cross-Layer Integration.** Deploy / rollout / dev-environment debugging is where expensive verify loops live. The `integration` agent applies this skill to every deploy- or rebuild-verified failure.
- **Phase 2 / 3 — Teammates doing build / infra / Docker / CI work.** The `frontend` agent (Vite / build config), the `backend` agent (Dockerfile / migrations / deploy config) apply this skill whenever verifying a fix needs a rebuild or deploy.
- **`root-cause-test-failures`.** When an RCA's verify loop is expensive, apply this skill's strategy on top of the 3-pass analysis: audit the whole pathway, batch the fixes.
- **`diagnostic-research-team`.** The 2-expensive-cycle strategy switch routes here — three researchers map the full pathway independently rather than a fourth solo cycle. This is a continuation of solving (that loop is unbounded), not a halt.
