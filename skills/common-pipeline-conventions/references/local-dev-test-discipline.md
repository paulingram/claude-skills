# Local -> dev -> test-on-dev (v3.57.0)

Read-on-demand detail for the pointer in `SKILL.md`.

**A gate that requires a live environment obliges the run to PROVIDE one.** The v3.55.0 frontend-E2E loop-exit gate requires a Playwright flow executed against a running environment. Requiring that while never deploying is a contradiction the run cannot resolve by asking: *"the route doesn't exist on dev until it's deployed, and dev has zero campaigns so the screen has nothing to render."* Both halves are the pipeline's to fix, and neither is a decision the user should be handed.

**The sequence is fixed and automatic: work locally -> deploy to dev -> test on dev.** When a run touches a frontend slice, Phase 5 MUST, before it declares the E2E unsatisfiable:

1. **Bring the environment up.** Start the local dev server, or run `prod_deploy.deploy_command` from `.architect-team-deploy.json` when the target is a shared dev environment. A route that does not exist on dev *yet* is not a blocker — it is the deploy step, not run. Emit the `deploy` notification when it comes up.
2. **Seed the data the flow needs.** An empty dev database is a fixture problem, not an untestable screen. Create the records the flow renders through the application's own surface — the real create endpoint or the real UI — so the seed exercises the same path a user would. Never assert against a screen you seeded by writing directly to the database behind the app's back; that verifies the renderer and nothing else.
3. **Then run the flow, and write the verdict.** Only after 1 and 2. A verdict artifact written without them is the described-not-executed escape the genuineness tool exists to catch.
4. **Only a genuine external blocker escalates** — no credentials, no reachable dev host, a deploy that fails for a reason the run cannot fix. That is an SR (`origin.kind: "deploy-mandate-not-satisfied"`) or, if only the owner can supply the missing input, the required-input marker. *"How do you want to proceed?"* with a recommended option attached is **not** an escalation; it is the run asking permission to do its own job, and the answer was always the recommended option.

**Inherited debt is never this run's to satisfy.** `.architect-team/reviews/` is cumulative, so a run-level gate reading it sees every slice every previous run wrote. `_audit_frontend_e2e` scopes to the current run — a slice claimed by a teammate manifest, OR written after the active-run marker's `started_at` — and prints how many it excluded. Twenty-five inherited slices blocking a two-slice run is the gate misfiring, not the run failing. When a gate is newly introduced, the debt it reveals is a backlog to schedule, never a wall in front of the next commit.

**Corollary, general.** When a gate cannot be satisfied, the first question is whether the run failed to do something it could have done. Deploying, seeding, and re-running are all inside the pipeline's authority. Ask the user only for what genuinely requires them.

