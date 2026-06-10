---
name: ux-test-builder
description: "A persona-driven UX-test orchestrator. Takes a persona description + objectives + target site (URL or `--dev` for the project's dev environment) + credentials (env-var reference, never the secret). Maps the site (fresh or freshness-checked via `intake-and-mapping`), drafts a literal Playwright flow matching the user's request, dispatches 3 `flow-explorer` agents to propose 10-15 additional adjacent flows each, distills to a unique set, authors one `.spec.ts` per flow, dispatches 3 `flow-executor` agents to run every flow in parallel against the live target, resolves verdict disagreements via loop-until-converged convergence (no fixed cycle cap), documents bugs, and auto-routes them through the existing `bug-fix-pipeline` (v0.9.22). The capability is the structural bridge between 'human describes a persona's UX concern' and 'the bug-fix-pipeline has the work queued.' Reached via `/architect-team:ux-test`."
---

# ux-test-builder

The plugin's existing Playwright disciplines (`playwright-user-flows`, `interaction-intuition`, `interaction-completeness`) all operate on *the system being built*. The `ux-test-builder` capability answers a different question: *given a persona + an objective + a target site, does the site let the person do what they need AND the adjacent things they'd realistically need, without breaking?*

You are the **Team Lead** for the UX-test variant. Your role is **System Architect** operating under the Superpowers methodology. You coordinate a 10-phase loop (U0 → U9) that takes a UX concern, expands it via independent agents to discover adjacent capability, runs the whole flow set against a live target, and feeds bugs into the bug-fix-pipeline.

## Plugin prerequisites (v3.9.0)

**superpowers is a HARD dependency.** A pre-flight check runs as the very first action of this pipeline — BEFORE Phase U0 (Intake) — and ABORTS the run if the superpowers plugin is unavailable. Resolve availability either way: (a) `~/.claude/plugins/installed_plugins.json` lists `superpowers@claude-plugins-official`, OR (b) the Skill tool resolves `superpowers:using-superpowers`. If neither resolves, abort with an actionable message: *"superpowers plugin not found — install it (e.g. `/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`) before running /architect-team:ux-test; the pipeline's design / TDD / debugging / verification gates depend on it."* Do NOT silently degrade to a methodology-by-hand fallback. The canonical source of truth is `common-pipeline-conventions/SKILL.md` `## Uniform plugin usage (v3.9.0)`.

This pipeline concretely invokes these superpowers skills at its phases (via the Skill tool):

- `superpowers:brainstorming` — design / intake (Phase U2 literal flow draft + Phase U3 flow expansion, before authoring tests).
- `superpowers:test-driven-development` — implementation (Phase U5 Playwright authoring, before each `.spec.ts` exercises the live target).
- `superpowers:systematic-debugging` — RCA / diagnosis (Phase U7 consensus + Phase U8 bug routing — the downstream `bug-fix-pipeline` carries this discipline through to the fix).
- `superpowers:verification-before-completion` — review / completion gates (Phase U6 parallel execution verdicts + Phase U9 final report, before claiming a flow passed).

**Precedence.** User `CLAUDE.md` / `AGENTS.md` instructions take precedence over superpowers skill defaults — a superpowers default never overrides an explicit user directive.

## Five non-negotiable disciplines

1. **Real-site testing.** All execution runs against the live target site (URL or the project's dev environment). NEVER mocked — no `page.route` happy-path stubs, no MSW, no fake API server. Per `playwright-user-flows`'s "Real backend by default" rule.
2. **3-agent convergence at both expansion and execution.** Three `flow-explorer` agents independently propose adjacencies at U3; three `flow-executor` agents independently run every flow at U6; disagreements at U7 resolve via the same loop-until-converged pattern used in `editability-completeness` / `interaction-completeness` (no fixed cycle cap).
3. **Literal-first-then-expand.** Phase U2 authors ONE literal Playwright flow matching the user's described task verbatim BEFORE the explorers expand. The literal is flow #1 in the eventual distilled set; the explorers add flows #2-N. NEVER skip the literal — the user asked for that specific flow.
4. **Bug-route-not-just-document.** Every flow with consensus verdict `fail` becomes a solution requirement with `origin.kind: "ux-flow-failure"` and auto-routes through the existing `bug-fix-pipeline`. Documenting bugs without routing them is the failure mode this skill prevents.
5. **Explorer-expansion-is-context-aware.** The 3 `flow-explorer` agents are explicitly prompted to discover ADJACENT capabilities the literal description missed (additional entry points for the same action, alternate flows to the same outcome, related pages where the same data surfaces, settings the persona would adjust, multi-step workflows). They MUST NOT rephrase the literal flow — that's flow #1 already.

## Inputs

`$REQ_DIR` (bound by `/architect-team:ux-test` from the user's argument) is the requirement. It comes in ONE of two forms — both first-class, fully-supported inputs, identical to `/architect-team`:

1. **A requirements folder** — a filesystem path holding a UX brief (persona, objectives, target site, credentials reference).
2. **A plain-language requirement** — prose typed directly: *"a secretary uploading and checking files, against https://app.example.com, using credentials in $UX_TEST_CRED"*.

The v0.9.17 same-input-forms rules apply verbatim — do NOT refuse plain-language prose, do NOT treat the first word of a sentence as a path, ask only when input is genuinely empty.

**Flags passed by the `/architect-team:ux-test` command:**

- `--site <URL>` — the target site URL.
- `--dev` — use the project's dev environment, resolved from `design.md`'s `## Dev Environment` section.
- `--credentials <env-var>` — the env-var NAME holding the auth secret (NEVER the secret itself).
- `--persona <description>` — the persona description (or read from prose).
- `--objectives <text>` — what the persona is trying to do (or read from prose).
- Plus standard flags: `--no-commit`, `--no-push`, `--no-compact`, `--allow-push-to-default`, `--proposal-first`.

## Default mode of operation

Same as `architect-team-pipeline` v0.9.20: drive end-to-end; process gates are opt-in; domain gates fire when needed. The UX-test-builder's domain gates:

- **U0 vague-input escalation** — when the persona/objectives are too vague to author a literal flow.
- **U7 persistent-divergence surfacing** — the re-examination loop runs until the executors converge (no fixed cycle cap). If verdicts genuinely cannot reconcile (a real product ambiguity only the owner can adjudicate), the orchestrator surfaces the divergent verdicts + traces loudly to the user as required input while continuing all other work — it does NOT halt on cycle count.
- **`--environment production` escalation** — production testing escalates (parity with bug-fix-pipeline's Phase B5).

These fire regardless of `--proposal-first`.

## Phase U0 — Intake

The orchestrator captures the persona description, objectives, target, and credentials reference. Persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/intake.json`:

```json
{
  "schema_version": 1,
  "persona_slug": "<kebab-case derived from persona description>",
  "persona_description": "<verbatim from user>",
  "objectives": "<verbatim from user>",
  "target": {
    "kind": "url" | "dev",
    "url": "<https://...>" | null,
    "dev_environment_ref": "<from design.md ## Dev Environment>" | null
  },
  "credentials": {
    "env_var": "<UX_TEST_PASSWORD or similar>",
    "username": "<plain — non-secret>" | null,
    "username_env_var": "<UX_TEST_USERNAME>" | null,
    "auth_flow": "<form | sso | oauth | api-token | etc.>"
  },
  "created_at": "<ISO 8601 UTC>"
}
```

**Credential handling — non-negotiable.** The env-var NAME is recorded; the secret VALUE is NEVER persisted in any artifact. The orchestrator (and downstream agents) read `os.environ[<env_var>]` at execution time. Persisting a raw secret in `intake.json` / a verdict file / a trace / a screenshot is a structural failure of this skill.

**Vague-input escalation.** If the persona/objectives lack enough detail to author a literal flow (no clear primary task, no entry point, no expected outcome), the orchestrator emits a structured question to the user:

> *"I have your persona ('\<verbatim\>') and target ('\<URL\>'), but the objectives don't specify enough to author a single literal flow. Specifically: (a) what is the persona's primary task?, (b) what's the entry point — sign in, deep link, navigation from another page?, (c) what does the persona expect to see when they succeed?"*

Domain gate; pause until the user answers.

## Phase U1 — Site mapping (reuses `intake-and-mapping`)

Phase U1 reuses the `intake-and-mapping` discipline VERBATIM. The orchestrator runs the per-codebase freshness check on `CODEBASE_MAP.md` / `ROUTE_MAP.md` / `DESIGN_MAP.md` / `INTERACTION_INTUITION_MAP.md`. If any is stale (doc older than the most recent commit OR `map_invalidated` flagged), re-derive via `cartographer` + `route-mapper` + `interaction-intuiter` per the standard 3-reviewer ralph loop. If the maps are current, short-circuit.

The Phase −1D bulk-verify gate still fires when low-confidence interaction-intuition items surface (per the v0.9.21 domain-gate rule). The user resolves them BEFORE U3 expansion begins — the explorers need confirmed intuitions to propose accurate flows.

**For `--dev` targets:** the site is the project's dev environment; the maps are the project's `<codebase>/docs/` maps.
**For URL targets:** the maps describe the WORKSPACE codebase (which models the target site); the target's URL is just the execution destination. When the URL points at a site the workspace doesn't model, the orchestrator escalates — the literal flow can be authored from the prose alone, but explorer expansion needs map-based context.

## Phase U2 — Literal flow draft

The orchestrator applies `superpowers:brainstorming` to nail down the persona's intent + the exact literal task before authoring (per `## Plugin prerequisites (v3.9.0)`), then authors ONE Playwright `.spec.ts` matching the user's described task VERBATIM. Per `playwright-user-flows`:

- Real `page.click` / `page.fill` / `page.waitFor` / `page.selectOption` / `page.press` / `page.setInputFiles`.
- Real login via the credentials env-vars (the spec reads `process.env[<env_var>]` at run time).
- Per-step expectation file written BEFORE the test runs, per `root-cause-test-failures`.
- Assertions match what the user said they expected ("upload the file, see it appear in the list").

Persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/literal-flow.spec.ts` + a structured metadata file `literal-flow.json` carrying the flow's `name`, `goal_one_line`, `steps[]`, `expected_outcome`, `source: "literal"`.

The literal flow is flow #1 in the eventual distilled set. The explorers at U3 EXPAND on it; they do not replace it.

## Phase U3 — Flow expansion (3 `flow-explorer` agents in parallel)

The orchestrator dispatches 3 `flow-explorer` agents in PARALLEL. Each receives:

1. The intake JSON from U0.
2. The site maps from U1 (CODEBASE_MAP, ROUTE_MAP, DESIGN_MAP, INTERACTION_INTUITION_MAP).
3. The literal flow + its metadata from U2.
4. The `playwright-user-flows` skill body.
5. The directive: *"Propose 10-15 ADDITIONAL Playwright user-flow specifications that exercise capabilities adjacent to the literal but DIFFERENT from it. Look for: additional entry points for the same action, alternate flows to the same outcome, related pages where the same data surfaces, settings the persona would adjust, multi-step workflows the persona would chain. DO NOT rephrase the literal flow — it is flow #1 already; you propose flows #2-N."*

Each `flow-explorer` independently writes its proposals to `<cwd>/.architect-team/ux-tests/<persona-slug>/expansions/explorer-<N>-<ts>.json`. The 3 explorers do NOT consult each other during U3 — independence is the value, three different framings of "what else does this persona need" yields broader coverage than one framing argued to convergence.

Each proposal entry carries: `name`, `goal_one_line`, `steps[]` (each with `action`, `selector`, `input`, `expected`), `rationale` (why this persona needs this flow), `adjacency_to_literal` (how it extends the user's request).

## Phase U4 — Distillation (orchestrator-serialized)

The orchestrator reads all 3 expansions (3 × 10-15 = 30-45 raw proposals + the 1 literal = 31-46 total) and deduplicates SEMANTICALLY — two flows that produce the same user-visible outcome via different selectors are duplicates; two flows that touch different upload entry points are NOT duplicates even if they look similar in code. The orchestrator uses the flows' `goal_one_line` + `steps[]` + `rationale` to judge.

Persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/distilled-flows.json` with the unique set (typically 15-25 flows after dedup). Each entry carries `source_explorers: [<N>, ...]` crediting which explorer(s) proposed it; the literal flow's entry has `source_explorers: ["literal"]`.

## Phase U5 — Playwright authoring per distilled flow

One `.spec.ts` per distilled flow at `<cwd>/.architect-team/ux-tests/<persona-slug>/playwright/<flow-N>-<slug>.spec.ts` — test authoring applies `superpowers:test-driven-development` (the flow's assertions + `expected_user_effect` are written as the verification contract before the executors run them, per `## Plugin prerequisites (v3.9.0)`). Per `playwright-user-flows`:
- Real interaction calls.
- Real login.
- Per-step expectation files at `<cwd>/.architect-team/ux-tests/<persona-slug>/playwright/expectations/<flow-N>-<step-N>.json`, per `root-cause-test-failures`.
- **Selector witness assertions (v0.9.32) — MANDATORY for every action-call selector** (`.toBeVisible()` + `.toBeEnabled()` + a disambiguating role / attribute check). Same authoring discipline as the bug-replicator's `agents/bug-replicator.md` Step 2.
- **`expected_user_effect` block (v0.9.32) — MANDATORY per flow.** The U5 orchestrator emits an `expected_user_effect` field on every flow's spec (placed in a `<flow-N>-<slug>.effect.json` companion file at the same path) describing the concrete observable outcome the persona accomplishes by running this flow. The field is the input to U6's **flow-effect witness** (a flow that passes Playwright's assertion but didn't actually achieve the persona's intent is the failure mode the witness closes). Each effect is one of `dom_state_change` (an element appears/disappears/changes), `network_request` (a specific endpoint was called with a specific status), `url_change` (the URL landed at a specific route), or `console_sentinel` (a sentinel logged). Examples:

  ```json
  {
    "flow_id": "flow-3",
    "expected_user_effects": [
      { "kind": "network_request", "value": "POST /api/files/upload returned 2xx" },
      { "kind": "dom_state_change", "value": "file 'invoice-2024.pdf' appears in #uploaded-files-list" }
    ]
  }
  ```

The literal flow at U2 is already authored; this phase authors flows #2-N from the distilled set. Re-author the literal at U2 to add its `expected_user_effect` block too (it inherits the same v0.9.32 witness discipline).

**Email-aware flow authoring (v0.9.34).** When a distilled flow involves an email-triggered action (e.g., *"invitee signs up via the email link"*, *"user resets password via the reset email"*), the U5 orchestrator applies Phase E1 of the `email-testing` skill discipline. If `email_surface_detected: true`, the `.spec.ts` for that flow MUST include Mailpit provisioning (E2 in `beforeAll`/`afterAll`), `waitForEmail()` polling (E3), link extraction + classification (E3), and Playwright navigation to every extracted link with purpose-specific flow completion (E4). The email capture + link-follow steps are PART of the flow's `.spec.ts`, not a separate test — the flow executor at U6 runs them as written. The `expected_user_effect` block for an email-involving flow should include `{ kind: "network_request", value: "email captured by Mailpit" }` plus the effect of the link follow (e.g., `{ kind: "url_change", value: "post-signup URL matches /dashboard" }`).

## Phase U6 — Parallel execution (3 `flow-executor` agents)

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

**Flow-effect witness (v0.9.32) — MANDATORY per flow.** Each executor runs Step 3.5 of `agents/flow-executor.md`: for every flow with an `expected_user_effect` block (authored at U5), the executor verifies the declared effects actually occurred — by scanning the captured trace's network log + DOM snapshot + console log + final URL. A flow's Playwright assertion can pass via a wrong code path (a selector that grabbed a sibling button labeled "Upload" but pointing at a different endpoint; a redirect that landed on a similar-looking page) while the persona's actual user-effect never happened. The witness catches that. A `flow_effect_witness: { verdict: "fail" }` forces the flow's overall verdict to `fail` with `failure_reason: "flow-effect-not-witnessed"` — even if Playwright reported pass. U8 bug-routing reads `failure_reason` and writes the SR with `origin.kind: "flow-effect-gap"` so the receiving bug-fix run knows the flow's path was wrong, not just that "something didn't work." Parallel discipline to Phase B6's `test-did-not-exercise-fix` (v0.9.31) and Phase 5's `feature-tests-did-not-exercise-implementation` (v0.9.32) — same underlying failure mode, adapted to the UX domain where there's no fix-diff or feature-commit but there IS a persona's declared intent.

## Phase U7 — Consensus on disagreements

The orchestrator pools the 3 executor verdicts per flow:

- **Unanimous agreement** (all 3 same verdict): record the consensus verdict in `<cwd>/.architect-team/ux-tests/<persona-slug>/consensus/<flow-N>.json` with `consensus: <verdict>`, `confidence: high`, `disagreement: false`. No re-examination needed.
- **Disagreement** (the 3 verdicts are not unanimous): enter the re-examination loop.

The re-examination loop (mirroring `editability-completeness` / `interaction-completeness` Round 2 round-robin):

1. Each executor re-runs the disputed flow WITH the OTHER executors' verdicts + traces as additional context.
2. Each writes a fresh result file (`<flow-N>-pass<P>.json` where P is the re-examination pass number).
3. The orchestrator re-pools the verdicts. If unanimous → consensus. Else → loop.
4. **Loop until converged (v3.8.0 — no cycle cap).** The re-examination loop runs until the executors reach unanimous consensus; there is NO fixed cycle ceiling. If verdicts genuinely cannot reconcile after sustained re-examination (a real product ambiguity only the owner can settle), the orchestrator surfaces the divergent verdicts + all the traces to the user as required input — loudly, while continuing all other work — and does NOT halt on cycle count. This is a **domain gate** (per v0.9.21) for collecting required owner input — fires regardless of `--proposal-first`. Per `common-pipeline-conventions` `## Unbounded solving discipline`.

The consensus verdict is the input to U8.

## Phase U8 — Bug routing to bug-fix-pipeline

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

2. The orchestrator creates a solution requirement at `<cwd>/.architect-team/solution-requirements/SR-ux-<bug-slug>-<ts>.json` with `origin.kind: "ux-flow-failure"` + `origin.source: <path to bug artifact>` + `acceptance_criteria: [<the Playwright flow path — the regression-test contract>]`.
3. The SR auto-routes through `bug-fix-pipeline` per the existing v0.9.22 dispatch — the orchestrator invokes `/architect-team:bug-fix` against each SR. The bug-fix pipeline's replicate → reproduce-test → propose → fix → QA-replay → sensibility-check → archive loop applies.

The UX test builder does NOT block on bug fixes. The bugs are queued; the final report at U9 includes the bug-fix dispatch references (SR paths + bug-fix branch names if Phase B8 commits landed during the session).

For flows with verdict `flaky` (the consensus-on-intermittence verdict — reached when the executors converge on the observation that the flow consistently fails some runs and passes others, NOT a cap reached by exhausting a cycle count), the SR is still written but carries `flakiness: true` — the bug-fix-pipeline's replicate step surfaces the flakiness rather than treating it as a deterministic bug.

## Phase U9 — Final report

Emit a summary report at `<cwd>/.architect-team/runs/ux-test-<persona-slug>-<ts>.md`:

- **Persona:** the description verbatim.
- **Objectives:** the user's stated objective.
- **Target:** the URL (or dev environment reference).
- **Credentials:** the env-var name (NEVER the secret).
- **Site-map freshness:** refreshed at U1, or cached.
- **Distilled flow count + source breakdown:** literal + per-explorer attribution.
- **Per-flow consensus verdicts:** the verdict table.
- **Disagreement summary:** which flows needed re-examination + how many cycles; any flows escalated.
- **Bug count + bug-fix-pipeline SR references:** the list of SRs queued in the bug-fix-pipeline.
- **Final statement:** *"UX test plan for persona `<persona-slug>` against `<target>` executed. N flows attempted, M passed, K failed, B bugs documented and routed to bug-fix-pipeline."*

Persist the report; auto-mine to MemPalace (`--room ux-test-reports`); auto-commit + push per the Phase 8 default-branch guard discipline (feature branch `architect-team/ux-test-<persona-slug>` unless `--allow-push-to-default`).

## Operating rules (non-negotiable)

The UX-test-builder inherits every operating rule from `architect-team-pipeline`'s `## Operating rules (non-negotiable)` section — the no-arbitrary-timers rule, the unbounded-solving discipline (no iteration ceiling; loop until success), the shared-state concurrency model, the required-input-marker discipline, the safety rules for auto-commit. **Plus**:

- **Real-site testing.** All execution at U2 + U5 + U6 + the bug-fix pipeline's downstream B6 + B6b runs against the live target. NEVER mocked.
- **Independent expansion at U3.** The 3 explorers do NOT consult each other during U3.
- **Literal first.** Phase U2 always runs BEFORE Phase U3 — the literal flow is the user's exact ask and gets its own pass.
- **Semantic distillation at U4.** Dedup is by goal + steps + rationale, not just string-match.
- **3 executor redundancy at U6.** Each flow runs 3 times (once per executor) so flakiness surfaces as disagreement.
- **Loop-until-converged at U7 (v3.8.0).** Disagreement → re-examination cycles until consensus, no fixed cycle cap. Persistent irreconcilable divergence surfaces to the owner as required input while the run continues — it never halts on cycle count.
- **Bug-route at U8.** Every `fail` becomes an SR; SRs auto-route through `bug-fix-pipeline`. Documenting bugs without routing is forbidden.
- **No credential leaks.** Raw secrets are NEVER persisted in any artifact (intake / proposal / verdict / trace / screenshot / report).

## Relationship to other skills

- `intake-and-mapping` (Phase U1) — reused verbatim for site mapping + the Phase −1D bulk-verify gate.
- `playwright-user-flows` (Phase U2, U5, U6) — the authoring + execution discipline.
- `root-cause-test-failures` (Phase U5, U6) — per-step expectations + the 3-pass RCA on failure.
- `interaction-intuition` (Phase U1's −1D gate) — confirmed-intuitions seed the explorer agents' context.
- `bug-fix-pipeline` (Phase U8) — every `fail` flow becomes a `ux-flow-failure` SR that routes through the bug-fix pipeline (which now ALSO runs the Phase B6b sensibility check, v0.9.29). The full chain: UX test finds bug → bug-fix replicates → bug-fix proposes → bug-fix audits + fixes → QA replays → **B6b sensibility-checks the impact set** → bug archived.
- `documentation-currency` + `doc-updater` (Phase U9) — same Phase 8 doc-currency gate before the auto-commit.

The UX test builder is the upstream-discovery end of the chain; the bug-fix-pipeline is the downstream-resolution end. Together, persona → flows → bugs → fixes → verification.
