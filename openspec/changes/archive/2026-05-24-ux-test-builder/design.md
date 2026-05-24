# Design — ux-test-builder

## Context

The plugin's existing Playwright disciplines all operate on *the system being built*. `playwright-user-flows` defines authoring discipline; `interaction-intuition` (Phase −1D) predicts wiring before implementation; `interaction-completeness` (Phase 5) verifies wiring after implementation. None of these answer the new question: *"given a persona + an objective + a target site, does the site work for this person — including the adjacent things they'd realistically need?"*

That question is the `ux-test-builder` capability. It's reached via a new explicit command (`/architect-team:ux-test`), uses the existing site-mapping disciplines to know what's there, drafts a literal flow matching the user's request, expands the flow set via three independent agents that find adjacent capabilities the literal description missed, distills to a unique set, executes every flow in parallel via three executor agents against the live target, resolves disagreements via the standard 3-cycle bounded convergence, documents bugs, and routes them through the existing `bug-fix-pipeline`.

## Architecture

### Phases U0 → U9

| Phase | Step | Output |
|---|---|---|
| **U0** | Intake | `.architect-team/ux-tests/<slug>/intake.json` |
| **U1** | Site mapping (reuses `intake-and-mapping`, freshness-checked) | `<codebase>/docs/CODEBASE_MAP.md` + `ROUTE_MAP.md` + `INTERACTION_INTUITION_MAP.md` |
| **U2** | Literal flow draft | `.architect-team/ux-tests/<slug>/literal-flow.spec.ts` + `.json` |
| **U3** | Flow expansion (3 `flow-explorer` agents in parallel) | `.architect-team/ux-tests/<slug>/expansions/explorer-<N>-<ts>.json` (×3) |
| **U4** | Distillation (orchestrator-serialized) | `.architect-team/ux-tests/<slug>/distilled-flows.json` |
| **U5** | Playwright authoring per distilled flow | `.architect-team/ux-tests/<slug>/playwright/<flow-N>.spec.ts` |
| **U6** | Parallel execution (3 `flow-executor` agents) | `.architect-team/ux-tests/<slug>/executions/executor-<N>/<flow-N>.json` (×3 per flow) |
| **U7** | Consensus on disagreements (3-cycle bounded convergence) | `.architect-team/ux-tests/<slug>/consensus/<flow-N>.json` |
| **U8** | Bug documentation + auto-route to `bug-fix-pipeline` | `.architect-team/ux-tests/<slug>/bugs/<bug-N>.json` + bug-fix-pipeline SR with `origin.kind: "ux-flow-failure"` |
| **U9** | Final report | `<cwd>/.architect-team/runs/ux-test-<slug>-<ts>.md` |

### bug-fix-pipeline Phase B6b — Logical Sensibility Check (the second new structural piece in v0.9.29)

Inserted between Phase B6 (QA replay) and Phase B7 (Archive + Report) in `skills/bug-fix-pipeline/SKILL.md`. Closes a real-world gap surfaced by user feedback: the QA-replayer at B6 confirms the originating symptom is gone end-to-end, but the fix may have touched (directly or transitively) UI components / routes / API endpoints / dependent pages that the originating symptom check doesn't exercise. The example case: a fix correctly routed "Sign Back In" to `/login`, but `/login` was itself broken in the deployed bundle (`auth-unavailable` because `VITE_*` env vars weren't baked). The QA-replayer's contract (*"original symptom gone end-to-end"*) was met — the click went to `/login` — but the destination was broken.

**Why a new phase, not an enhancement to B6:** B6's `qa-replayer` agent runs the SPECIFIC reproduction artifact from B2 (the Playwright flow that originally failed). Its scope is intentionally narrow — "is the specific symptom the user reported gone?" Widening B6's scope to "and also is every adjacent flow logical?" would muddy the QA-replayer's contract. Adding B6b as a separate phase with a separate agent (the `fix-sensibility-checker`) keeps each role's responsibility crisp: B6 = symptom check, B6b = sensibility-of-the-impact-set check.

**Process:**

1. **Compute the impact set.** The orchestrator reads the fix's `git diff` (the commits the implementing team landed at B5) and extracts:
   - Every UI component file changed (`.tsx` / `.jsx` / `.vue` / `.svelte` / `.css` / `.scss`).
   - Every page / screen / route file changed.
   - Every API endpoint handler / controller / route handler changed.
   - For each changed file, the SET OF IMPORTERS (files that import it) — these are transitively affected.
   - For each touched route, the SET OF NAVIGATION DESTINATIONS (links / redirects within the route's components) — the example case's `/login` page would surface here even if the fix only changed the Sign-Back-In handler.
2. **Dispatch the `fix-sensibility-checker` agent** with the impact set + the deployed dev URL + the credentials env-var.
3. **The agent authors minimal Playwright sensibility flows per impact-set item.** Each flow is small: navigate to the page / load the component / call the endpoint, and assert the page renders without:
   - An error banner ("auth-unavailable", "service-unavailable", "configuration-missing", "could not load", "500", "404 — not found" where the page should exist).
   - Console errors (uncaught exceptions, network failures on critical resources).
   - Broken auth surfaces (a login form that says it can't authenticate when auth should work).
   - Missing-data placeholders where data should be present (a list page showing "no items" when items are known to exist in the dev DB).
4. **The agent runs the sensibility flows against the deployed dev environment** (per `playwright-user-flows`, same real-running-app discipline as B6).
5. **The agent documents each item's verdict**: `sensible | nonsensical | env-failure | not-reachable`. Persisted at `.architect-team/sensibility/<bug-slug>/checker-<ts>.json` with the full impact set + per-item verdict + the captured trace + the captured screenshot(s).
6. **The orchestrator pools the verdicts:**
   - All `sensible` → B6b passes; proceed to B7.
   - Any `nonsensical` → the orchestrator writes a fresh SR with `origin.kind: "fix-regression"`, the failing impact-set item as the symptom, the captured trace + screenshot as evidence. The new SR routes back through the bug-fix-pipeline (recursive — the new bug gets its own B-1 → B8 loop). The CURRENT fix is NOT marked complete; the SR resolves first, then B6 + B6b re-run on the new state.
   - Any `env-failure` → routes to the implementing team for env diagnosis (parity with B6's `env-failure` handling — env issues are not fix issues).
   - Any `not-reachable` → the impact-set computation may have mis-identified the item (e.g., a stale CODEBASE_MAP); the orchestrator notes this in the verdict file as an audit-trail item but does NOT route to bug-fix (the item being not-reachable means the fix can't have broken it from the user's view).
7. **Bounded recursion.** The fix-regression loop counts against the global 20-step iteration ceiling per `architect-team-pipeline`'s run-state rules. If 3 consecutive fix-regression bugs surface on the same bug-fix run, the orchestrator escalates to the user (the fix likely has a deeper architectural issue that needs human attention).

**Impact-set computation rules (the agent's discipline):**

Computed mechanically from the diff, NOT speculatively. The agent runs `git diff <merge-base>..HEAD --name-only` to get the changed-files list. Then for each changed file:

- If it's a UI component (`.tsx` / `.jsx` / `.vue` / `.svelte`): `git grep -l "from ['\"]\(\.\|@\)/.*<basename>['\"]"` to find importers (or the project's preferred dependency-resolution method).
- If it's a route file (matches `frontend-route-mapping`'s patterns): the route's component imports become the impact-set components; the navigation destinations within the route's body become the impact-set routes.
- If it's an API endpoint handler: the endpoint's path becomes an impact-set endpoint (the agent runs an integration-style request against it to verify it returns sensible responses).

The agent's `## Impact-set computation` section documents this exhaustively so the rules are auditable.

**The dev-environment precondition:** B6b runs against the DEPLOYED dev environment, NOT against local source code. The fix has already passed B6's QA-replay, which means B5 has already deployed; B6b's sensibility check uses that deployment. (If the user invoked the bug-fix run with `--no-deploy`, B6b is skipped with a note in the final report — the sensibility check requires a live deployment.)

### The persona-slug convention

`<persona-slug>` is derived from the persona description (e.g., *"a secretary uploading and checking files"* → `secretary-uploading-checking-files`). It's the run identifier — multiple runs against the same site with different personas don't collide.

### The intake schema (U0)

```json
{
  "schema_version": 1,
  "persona_slug": "<kebab-case>",
  "persona_description": "<verbatim from user>",
  "objectives": "<verbatim from user — what the persona is trying to do>",
  "target": {
    "kind": "url" | "dev",
    "url": "<https://app.example.com>" | null,
    "dev_environment_ref": "<design.md ## Dev Environment section content>" | null
  },
  "credentials": {
    "env_var": "<UX_TEST_PASSWORD or similar>",
    "username": "<plain — non-secret>" | null,
    "username_env_var": "<UX_TEST_USERNAME>" | null,
    "auth_flow": "<form | sso | api-token | etc.>"
  },
  "created_at": "<ISO 8601 UTC>"
}
```

**Credential handling:** the env-var NAME is recorded; the secret VALUE is NEVER persisted. The orchestrator reads `os.environ[<env_var>]` at execution time (U5 / U6). Usernames may be plain (non-secret) OR also env-var-referenced.

### The literal flow (U2)

The orchestrator authors ONE Playwright `.spec.ts` matching the user's described task verbatim. Per `playwright-user-flows`:
- Real `page.click` / `page.fill` / `page.waitFor` / `page.selectOption` / `page.press` / `page.setInputFiles`.
- Real login via the credentials env-vars.
- Per-step expectation file per `root-cause-test-failures`.

This is flow #1 in the eventual distilled set; the explorers EXPAND on it, they don't replace it.

### Flow expansion (U3) — 3 explorer agents

Each `flow-explorer` agent receives:
1. The intake JSON (persona, objectives, target, credentials reference).
2. The site maps from U1.
3. The literal flow from U2.
4. The `playwright-user-flows` skill body (the authoring discipline).
5. The directive: *"Propose 10-15 ADDITIONAL flows that exercise capabilities adjacent to the literal but DIFFERENT — additional entry points for the same action, alternate flows to the same outcome, related pages where the same data surfaces, settings the persona would adjust, multi-step workflows the persona would chain. DO NOT rephrase the literal flow. The literal is flow #1 already; you propose flows #2-N."*

Each agent independently writes its proposals as a structured JSON list — one entry per flow with `name`, `goal_one_line`, `steps[]` (each step has `action`, `selector`, `input`, `expected`), `rationale` (why this persona needs this flow), `adjacency_to_literal` (how it extends the user's request). Persisted at `.architect-team/ux-tests/<slug>/expansions/explorer-<N>-<ts>.json`.

Agents do NOT consult each other in U3. Independence is the value — three different framings of "what else does this persona need" produces broader coverage than one framing argued to convergence.

### Distillation (U4) — orchestrator-serialized

The orchestrator reads all 3 expansions (3 × 10-15 = 30-45 raw proposals + the 1 literal = 31-46 total). It deduplicates semantically — two flows that produce the same user-visible outcome via different selectors are duplicates; two flows that touch different upload entry points are NOT duplicates even if they look similar in code. The orchestrator uses the flows' `goal_one_line` + `steps[]` + `rationale` to judge. Typically the distilled set is 15-25 flows.

Each distilled entry carries `source_explorers: [<N>, ...]` crediting which explorer(s) proposed it. The literal flow is always entry #1 with `source_explorers: ["literal"]`.

### Playwright authoring (U5) — one .spec.ts per distilled flow

Per `playwright-user-flows`. Each flow becomes a complete, runnable test at `.architect-team/ux-tests/<slug>/playwright/<flow-N>-<slug>.spec.ts`. Per-step expectation files written at `.architect-team/ux-tests/<slug>/playwright/expectations/<flow-N>-<step-N>.json` per `root-cause-test-failures`.

### Parallel execution (U6) — 3 executor agents

Each `flow-executor` agent receives:
1. The full distilled-flow set + the Playwright `.spec.ts` files.
2. The target site URL / dev environment URL.
3. The credentials env-var name (the actual secret is read from the env at agent runtime).
4. The directive: *"Run every Playwright flow against the live target. Document each flow's outcome — `pass` / `fail` / `flaky` / `env-failure` — with the captured trace and screenshot(s) and the per-step expectation deltas. Each flow is run ONCE per executor; you (executor N) are one of three."*

Each executor persists per-flow results at `.architect-team/ux-tests/<slug>/executions/executor-<N>/<flow-N>.json`:

```json
{
  "executor": <1|2|3>,
  "flow_id": "<flow-N>",
  "verdict": "pass" | "fail" | "flaky" | "env-failure",
  "trace_path": ".architect-team/ux-tests/<slug>/executions/executor-<N>/traces/<flow-N>.zip",
  "screenshots": ["<path>", ...],
  "expectation_deltas": [{step, expected, actual, match: bool}, ...],
  "duration_ms": <int>,
  "executed_at": "<ISO 8601 UTC>",
  "notes": "<one-line summary>"
}
```

Three executors running every flow once = 3N flow executions total for N distilled flows. The redundancy is the consensus mechanism.

### Consensus on disagreements (U7)

For each flow, the orchestrator pools the 3 executor verdicts:

- **Unanimous agreement** (all 3 same verdict): record as the consensus verdict in `.architect-team/ux-tests/<slug>/consensus/<flow-N>.json` with `consensus: <verdict>`, `confidence: high`, `disagreement: false`.
- **Disagreement** (the 3 don't all agree): enter the re-examination loop.

The re-examination loop (mirroring editability-completeness / interaction-completeness Round 2):

1. Each executor re-runs the disputed flow with the OTHER executors' verdicts + traces as additional context.
2. Each writes a fresh result file (`<flow-N>-pass<P>.json` where P is the re-examination pass number).
3. The orchestrator re-pools the verdicts. If unanimous → consensus. Else → loop.
4. Bounded at **3 re-examination cycles** (parallel to the bounded-convergence pattern used elsewhere). After 3 cycles without consensus, the orchestrator escalates to the user with the divergent verdicts + traces as evidence (a domain gate per v0.9.21 — fires regardless of `--proposal-first`).

The consensus verdict is the input to U8.

### Bug routing (U8) — auto-dispatch to bug-fix-pipeline

For every flow with consensus verdict `fail`:

1. The orchestrator writes a structured bug artifact at `.architect-team/ux-tests/<slug>/bugs/<bug-N>.json`:

   ```json
   {
     "bug_slug": "<persona-slug>--<flow-slug>",
     "flow_id": "<flow-N>",
     "persona_description": "<verbatim from intake>",
     "objectives": "<verbatim from intake>",
     "target_site": "<URL>",
     "literal_vs_actual": "<one-paragraph: what the user expected to happen, what actually happened>",
     "playwright_spec_path": ".architect-team/ux-tests/<slug>/playwright/<flow-N>-<slug>.spec.ts",
     "trace_paths": [<from all 3 executors' traces>],
     "screenshot_paths": [<from all 3 executors' screenshots>],
     "consensus_pass_count": <P>,
     "created_at": "<ISO 8601 UTC>"
   }
   ```

2. The orchestrator creates a solution requirement at `.architect-team/solution-requirements/SR-ux-<bug-slug>-<ts>.json` with `origin.kind: "ux-flow-failure"` and `origin.source: <path to bug artifact>`.
3. The SR auto-routes through `bug-fix-pipeline` per the existing v0.9.22 dispatch (the orchestrator invokes `/architect-team:bug-fix` against each SR; the bug-fix pipeline's replicate-propose-fix-QA loop applies).

The UX test builder does NOT block on bug fixes. The bugs are queued; the final report at U9 includes the bug-fix-pipeline dispatch references (the SR paths + the bug-fix branch names if Phase B8 commits landed during the same session).

### Final report (U9)

Summary report at `<cwd>/.architect-team/runs/ux-test-<slug>-<ts>.md`:

- Persona, objectives, target site, credentials env-var name.
- Site-map freshness (refreshed at U1 or cached).
- Distilled flow count + source breakdown (literal + per-explorer attribution).
- Per-flow consensus verdicts.
- Disagreement summary (which flows needed re-examination + how many cycles).
- Bug count + the list of bug-fix-pipeline SR paths.
- Final statement: **"UX test plan for persona `<persona-slug>` against `<target>` executed. N flows attempted, M passed, K failed, B bugs documented and routed to bug-fix-pipeline."**
- Auto-commit + push per the same Phase 8 default-branch guard discipline (the work lands on `architect-team/ux-test-<slug>` unless `--allow-push-to-default`).

## Reuse Decisions

| Decision | Choice | Justification |
|---|---|---|
| Site mapping | **reuse** `intake-and-mapping` + `route-mapper` + `interaction-intuition` verbatim | The site-mapping discipline + freshness checks are solved; the U1 step IS the existing Phase −1B+−1C+−1D flow run against the target's codebase (when the target IS the project's dev environment) OR against a remote site (when the target is an external URL — in which case the existing mapping discipline still applies; cartographer runs against the project's source code, and route-mapper / interaction-intuiter operate on the rendered live site via Playwright reconnaissance). No new mapping code. |
| Playwright authoring | **reuse** `playwright-user-flows` verbatim | The real-interaction discipline (real `page.click`, never `page.request.*`, per-step expectations, etc.) is solved. The new U5 step IS the existing authoring discipline applied per-flow. |
| RCA on flow failure | **reuse** `root-cause-test-failures` verbatim | Per-step expectation files + the 3-pass RCA loop apply to UX test flows the same way they apply to integration tests. |
| 3-agent convergence pattern (U3 + U6 + U7) | **reuse** the existing pattern from `editability-completeness` / `interaction-completeness` / `integration-explorer` | Same shape: 3 agents in parallel → independent drafts → round-robin re-examination → bounded 3-cycle convergence → escalate to user on non-convergence. Battle-tested. |
| Bug-fix integration (U8) | **reuse** `bug-fix-pipeline` verbatim + a new SR origin kind | The bug-fix-pipeline's replicate-propose-fix-QA loop is the right downstream — the UX test builder's job is to FIND bugs; the bug-fix-pipeline's job is to FIX them. The only new API surface is the SR origin kind `ux-flow-failure`. |
| Credential handling | **reuse** the env-var-reference pattern from the existing `.architect-team-notify.json` config | Secrets are never persisted; only env-var NAMES are recorded. The orchestrator reads `os.environ[<name>]` at execution time. |
| Default-branch guard + commit + push at U9 | **reuse** the Phase 8 default-branch-guard discipline | Same flow: feature branch `architect-team/ux-test-<slug>` unless `--allow-push-to-default`; auto-commit; auto-push; recommend PR. |
| Documentation-currency gate at U9 | **reuse** the v0.9.23 `doc-updater` agent + system-architect Documentation Currency Audit | Same gate as Phase 8 / Phase B8 — the UX test builder's output IS a new artifact set that should be documented in the run report; the existing gate handles it. |
| New skill | **build-new** `ux-test-builder` | The orchestration shape (persona + literal + expand + distill + execute + arbitrate + route) is genuinely new — it doesn't fit into any existing skill's scope. |
| New agents (`flow-explorer`, `flow-executor`) | **build-new** | Each is a discrete role — propose flows / execute flows. The existing agents (`route-mapper`, `interaction-intuiter`, `editability-reviewer`, etc.) all operate on the WORKSPACE codebase; these two operate on a TARGET site. The role is different. |
| New agent (`fix-sensibility-checker`) | **build-new** | The role — compute the impact set from a git diff, author minimal Playwright sensibility flows, run them against deployed dev, route nonsensical items as fresh SRs — does not fit any existing agent. `qa-replayer` (v0.9.22) is the closest sibling but its scope is narrow (re-run the SPECIFIC reproduction artifact); `fix-sensibility-checker` is wider (synthesize new flows from the impact set). Cleaner as a separate role. |
| Phase B6b sensibility check | **build-new** in `skills/bug-fix-pipeline/SKILL.md` | Architectural addition to address a real-world gap (the `auth-unavailable` example). Inserted between B6 and B7 as a new phase so each phase's responsibility stays crisp (B6 = symptom check, B6b = impact-set sensibility check). |
| New command | **build-new** `/architect-team:ux-test` | Same shape as `/architect-team:bug-fix` (v0.9.22) — a sibling entry point with its own argument-parsing block + a different invocation target. |

No new third-party dependency. The capability uses the EXISTING Playwright + chromium stack (already a `setup.py` dependency for v0.9.5's "Real backend by default" discipline).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The 3 explorers propose flows that are technically distinct but practically redundant. | U4 (distillation) deduplicates semantically (by `goal_one_line` + `steps[]` + `rationale`, not just string-match). The orchestrator's distillation step is judgment-heavy; multiple explorers proposing the same flow is the expected case and the deduplication is the correct response. |
| The 3 executors return all-different verdicts on a genuinely flaky flow. | U7's re-examination loop is bounded at 3 cycles. If a flow remains flaky after 3 cycles, the consensus verdict becomes `flaky` (NOT `fail` — flakiness is a separate signal); the U8 bug-routing step writes it as a `bug` with `origin.kind: "ux-flow-failure"` but with `flakiness: true` in the artifact, and the bug-fix-pipeline's replicate step would surface the flakiness rather than a deterministic bug. |
| The target site requires complex auth (SSO, OAuth, multi-step login) that the credentials env-var pattern doesn't cover. | U0's `auth_flow` field admits `sso`, `oauth`, etc., and the literal flow at U2 + the explorer flows at U3 are authored with the auth flow's specifics. The credentials env-var stores the input (token / refresh-token / etc.) that completes the auth; the Playwright code performs the actual sequence. For genuinely complex auth not covered by the env-var pattern, U0 escalates to the user. |
| The site map is stale at U1 but the freshness check passes (e.g., the timestamps are fresh but the site changed externally). | The standard freshness rule applies — if a U3 explorer or a U6 executor discovers the map is materially wrong, they record the codebase in `intake-state.json`'s `map_invalidated` array per `intake-and-mapping`, forcing re-mapping on the next run. The current run does its best with the available map. |
| The bug-fix-pipeline gets flooded with low-priority UX-test bugs and can't keep up. | The bug-fix-pipeline runs against each SR independently (per the v0.9.22 design). The UX test builder enqueues SRs; the user can choose to run them sequentially, in parallel, or selectively (each SR is its own `/architect-team:bug-fix` invocation). The UX test builder does NOT auto-block on bug fixes — the bugs are documented + queued; resolution happens at the user's pace. |
| The Playwright execution itself fails for env reasons (browser binary missing, network unavailable) before any flow can run. | Each executor returns `env-failure` for affected flows. If all 3 executors return `env-failure` on the same flow, the orchestrator escalates immediately (not a flow bug — an env problem). Phase 0 of `visual-fidelity-reconciliation` (the live-app precondition pattern) applies. |
| The user's persona description is too vague for the literal flow at U2. | U0 escalates: structured question to the user — *"I have your persona ('<verbatim>') but the objectives don't specify enough to author a single literal flow. Specifically: (a) what is the persona's primary task?, (b) what's the entry point?, (c) what's the expected outcome?"*. Domain gate — fires regardless of `--proposal-first`. |
| (B6b) The impact-set computation produces FALSE POSITIVES — flags an importer that the fix didn't really break. | The agent's verdict on a false-positive item is `sensible` (the sensibility check passes because the item is fine), and no SR is generated. False positives in the impact-set don't produce false bugs; they produce extra runtime cost. Acceptable. |
| (B6b) The impact-set computation produces FALSE NEGATIVES — misses an importer the fix transitively broke. | This is the real-world case the entire feature exists to address (the `auth-unavailable` example). The agent's impact-set rules are mechanical (git-grep based) so they're auditable. The user can extend the rules via the impact-set section in `bug-fix-pipeline/SKILL.md` as new patterns surface. The agent body documents the heuristic + the limitation explicitly. |
| (B6b) The fix-regression loop infinitely recurses (each fix introduces a new regression). | Bounded by the global 20-step iteration ceiling from `architect-team-pipeline`'s run-state rules. The orchestrator also tracks a local fix-regression-cycle counter; after 3 consecutive fix-regression SRs on the same bug-fix run, the orchestrator escalates to the user — the original bug likely has a deeper architectural issue. |
| (B6b) The user invoked the bug-fix run with `--no-deploy` (the dev environment is hand-managed). | B6b requires a deployed dev environment to run against. If `--no-deploy` is set, B6b is SKIPPED with a note in the final report: *"Logical Sensibility Check (Phase B6b) was skipped because `--no-deploy` was set. The QA-replay at Phase B6 verified the original symptom is gone, but the impact set was NOT independently sensibility-checked. Consider re-running the bug-fix without `--no-deploy` for the full verification."* |
