---
name: ux-test-builder
description: "A persona-driven UX-test orchestrator. Takes a persona description + objectives + target site (URL or `--dev` for the project's dev environment) + credentials (env-var reference, never the secret). Maps the site (fresh or freshness-checked via `intake-and-mapping`), drafts a literal Playwright flow matching the user's request, dispatches `flow-explorer` agents per the review tier (one by default, three only at tier 3) to propose 10-15 adjacent flows each, distills to a unique set, authors one `.spec.ts` per flow, dispatches `flow-executor` agents per the review tier (one runs every flow against the live target, a second re-runs disputed flows), resolves verdict disagreements via loop-until-converged convergence (no fixed cycle cap), documents bugs, and auto-routes them through the existing `bug-fix-pipeline` (v0.9.22). The capability is the structural bridge between 'human describes a persona's UX concern' and 'the bug-fix-pipeline has the work queued.' Reached via `/architect-team:ux-test`."
user-invocable: false
---

# ux-test-builder

The plugin's existing Playwright disciplines (`playwright-user-flows`, `interaction-intuition`, `interaction-completeness`) all operate on *the system being built*. The `ux-test-builder` capability answers a different question: *given a persona + an objective + a target site, does the site let the person do what they need AND the adjacent things they'd realistically need, without breaking?*

You are the **Team Lead** for the UX-test variant. Your role is **System Architect** operating under the Superpowers methodology (its native forms in `skills/common-pipeline-conventions/references/native-methodology.md` when that CONDITIONAL plugin is absent). You coordinate a 10-phase loop (U0 → U9) that takes a UX concern, expands it via independent agents to discover adjacent capability, runs the whole flow set against a live target, and feeds bugs into the bug-fix-pipeline.

<!-- ct6:block:principles:begin -->
## Operating principles

CT6 work is governed by eight load-bearing principles. The full statements — each with its named anti-pattern — live in `docs/ETHOS.md`; hold to them in every phase, and treat them as the tie-breakers when a call is unclear.

- **Reuse before build.** Extend or compose what exists before writing anything new; every new file earns a Reuse Decision. Anti-pattern: the greenfield reflex.
- **The producer is never its own checker.** Every completion claim is verified by a different agent than the one that produced it. Anti-pattern: self-attestation.
- **Honest boundary.** Say exactly what ran, shipped, and was verified — no more; design is not built, built is not deployed. Anti-pattern: the overclaim.
- **Unbounded solving.** Loop until the gate is green; never hand back a half-finished run on an iteration count. Anti-pattern: the arbitrary stop.
- **Default to action.** Gates are opt-in; on reversible work, pick the sensible default and proceed. Anti-pattern: permission-seeking.
- **Documentation currency.** Docs ship current or the run does not ship. Anti-pattern: the stale grid.
- **Evidence before assertion.** State a result only after running the check and reading its output. Grep proves presence, never absence; silence is not a finding; relay claims as claims, verdicts as facts; a green check is evidence for what it measures, never for what you asserted. Anti-pattern: the unverified "should work".
- **Understand before acting.** Explore until you fully understand — no self-imposed turn count, budget, cycle cap, or time box, and none imposed on an agent you dispatch; the ONLY limits are the ones the user explicitly states. Anti-pattern: the self-rationed investigation.

See `docs/ETHOS.md` for the full text.
<!-- ct6:block:principles:end -->

## Plugin prerequisites (v3.9.0)

**superpowers is a CONDITIONAL plugin (v4.0.0; it was a hard dependency from v3.9.0 to v3.67.0).** A pre-flight check still runs as the very first action of this pipeline and resolves availability either way: (a) `~/.claude/plugins/installed_plugins.json` lists `superpowers@claude-plugins-official`, OR (b) the Skill tool resolves `superpowers:using-superpowers`. When it is present the lane uses the superpowers skills named below. When it is absent the lane does NOT abort: it prints one line naming the gap and the install remediation (`/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`), records `methodology: native` in `intake-state.json`, and runs the same disciplines in their native form per `skills/common-pipeline-conventions/references/native-methodology.md`. The same rule covers `cartographer` (native mapping fallback in that chapter) and the retired `ralph-loop`, whose job the `ct6-converge` workflow does (`skills/common-pipeline-conventions/references/converge-workflows.md`). The canonical source of truth is `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)`.

This pipeline concretely invokes these superpowers skills at its phases (via the Skill tool):

- `superpowers:brainstorming` — design / intake (Phase U2 literal flow draft + Phase U3 flow expansion, before authoring tests).
- `superpowers:test-driven-development` — implementation (Phase U5 Playwright authoring, before each `.spec.ts` exercises the live target).
- `superpowers:systematic-debugging` — RCA / diagnosis (Phase U7 consensus + Phase U8 bug routing — the downstream `bug-fix-pipeline` carries this discipline through to the fix).
- `superpowers:verification-before-completion` — review / completion gates (Phase U6 parallel execution verdicts + Phase U9 final report, before claiming a flow passed).

**Precedence.** User `CLAUDE.md` / `AGENTS.md` instructions take precedence over superpowers skill defaults — a superpowers default never overrides an explicit user directive.

## Five non-negotiable disciplines

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/five-non-negotiable-disciplines.md` and execute it in full. Do not work from memory.

1. **Real-site testing.** All execution runs against the live target site (URL or the project's dev environment). NEVER mocked — no `page.route` happy-path stubs, no MSW, no fake API server. Per `playwright-user-flows`'s "Real backend by default" rule.
2. **Convergence by review tier at both expansion and execution (3-agent convergence only on a tier-3 panel).** `flow-explorer` agents are dispatched at U3 per `skills/team-spawning-and-review-gates/references/review-tiers.md` — ONE by default, a panel of three only when the user or a project principle raises the gate to tier 3 — and each independently proposes adjacencies; `flow-executor` agents are dispatched at U6 the same way — ONE runs every flow by default (review tier 2: the authored flow's expected effect is the producer side, the executor the paired independent verdict), a SECOND re-runs only the flows the first disputes, a panel of three only at tier 3; disagreements at U7 resolve via the same loop-until-converged pattern used in `editability-completeness` / `interaction-completeness` (no fixed cycle cap).
3. **Literal-first-then-expand.** Phase U2 authors ONE literal Playwright flow matching the user's described task verbatim BEFORE the explorers expand. The literal is flow #1 in the eventual distilled set; the explorers add flows #2-N. NEVER skip the literal — the user asked for that specific flow.
4. **Bug-route-not-just-document.** Every flow with consensus verdict `fail` becomes a solution requirement with `origin.kind: "ux-flow-failure"` and auto-routes through the existing `bug-fix-pipeline`. Documenting bugs without routing them is the failure mode this skill prevents.
5. **Explorer-expansion-is-context-aware.** The `flow-explorer` agents (one, or the tier-3 panel) are explicitly prompted to discover ADJACENT capabilities the literal description missed (additional entry points for the same action, alternate flows to the same outcome, related pages where the same data surfaces, settings the persona would adjust, multi-step workflows). They MUST NOT rephrase the literal flow — that's flow #1 already.

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

## Notifications (per-project email events — opt-in, best-effort)

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/notifications-per-project-email-events-opt-in-best-effort.md` and execute it in full. Do not work from memory.

Per `common-pipeline-conventions` `## Notifications wiring convention`, this pipeline emits the ten recognized events (`run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, plus the tick-driven `heartbeat`) via the notifier CLI at `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py` — engaging ANY architect-team task emits its notifications, and the UX-test variant is no exception (v3.34.0 closes the gap where this pipeline had none). The discipline is opt-in (gated on `.architect-team-notify.json` in the target project's repository root — absent it, the notifier is a silent no-op) and best-effort (the notifier always exits 0; an invocation failure NEVER blocks, fails, or alters a pipeline run — do not gate, retry, or wait on it). Every invocation uses the polyglot `python3 ... || python ...` form per `common-pipeline-conventions` `## Cross-platform Python invocation`.

## Phase U0 — Intake

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u0.md` and execute it in full. Do not work from memory.

The orchestrator captures the persona description, objectives, target, and credentials reference. Persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/intake.json`:

## Phase U1 — Site mapping (reuses `intake-and-mapping`)

Phase U1 reuses the `intake-and-mapping` discipline VERBATIM. The orchestrator runs the per-codebase freshness check on `CODEBASE_MAP.md` / `ROUTE_MAP.md` / `DESIGN_MAP.md` / `INTERACTION_INTUITION_MAP.md`. If any is stale (doc older than the most recent commit OR `map_invalidated` flagged), re-derive via `cartographer` (or the native mapping form in `skills/common-pipeline-conventions/references/native-methodology.md` when that CONDITIONAL plugin is absent) + `route-mapper` + `interaction-intuiter` per the standard tier-3 `ct6-converge` map convergence — the `codebase-map` preset (`reviewers: 3`, promise `CODEBASE MAP COMPLETE`), DECLARED before the workflow runs and RECORDED after it per `skills/architect-team-pipeline/references/phase--1.md` `### Converge record protocol (v4.0.0)`; the recorded all-`ok` round is the exit, the promise only the label. If the maps are current, short-circuit.

**Project principles at intake (v4.0.0, per `project-principles`).** Once per project: when `<workspace>/.architect-team/principles.json` is absent, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" default-set --workspace <ws>` (proposed never binds); when the user provided a document, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" extract-candidates <file>`, `Read` it, and confirm the drafted statements in ONE `AskUserQuestion` (a domain gate; nothing becomes confirmed silently). Every explorer and executor brief carries the output of `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace <ws>` exactly as the intake record is carried.

**Homepage rebuild once the maps are current (v4.0.0, best-effort, never blocking).** After the freshness check (and any re-derive) has left the maps current (`project-homepage` `## Rebuild moments`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```

The Phase −1D bulk-verify gate still fires when low-confidence interaction-intuition items surface (per the v0.9.21 domain-gate rule). The user resolves them BEFORE U3 expansion begins — the explorers need confirmed intuitions to propose accurate flows.

**For `--dev` targets:** the site is the project's dev environment; the maps are the project's `<codebase>/docs/` maps.
**For URL targets:** the maps describe the WORKSPACE codebase (which models the target site); the target's URL is just the execution destination. When the URL points at a site the workspace doesn't model, the orchestrator escalates — the literal flow can be authored from the prose alone, but explorer expansion needs map-based context.

## Phase U2 — Literal flow draft

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u2.md` and execute it in full. Do not work from memory.

The orchestrator applies `superpowers:brainstorming` to nail down the persona's intent + the exact literal task before authoring (per `## Plugin prerequisites (v3.9.0)`), then authors ONE Playwright `.spec.ts` matching the user's described task VERBATIM. Per `playwright-user-flows`:

## Phase U3 — Flow expansion (`flow-explorer` agents per the review tier)

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u3.md` and execute it in full. Do not work from memory.

The orchestrator dispatches `flow-explorer` agents per the review tier (`skills/team-spawning-and-review-gates/references/review-tiers.md`): ONE by default, a panel of three in PARALLEL only when the user or a project principle raises the gate to tier 3. Each receives:

## Phase U4 — Distillation (orchestrator-serialized)

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u4.md` and execute it in full. Do not work from memory.

The orchestrator reads all 3 expansions (3 × 10-15 = 30-45 raw proposals + the 1 literal = 31-46 total) and deduplicates SEMANTICALLY — two flows that produce the same user-visible outcome via different selectors are duplicates; two flows that touch different upload entry points are NOT duplicates even if they look similar in code. The orchestrator uses the flows' `goal_one_line` + `steps[]` + `rationale` to judge.

## Phase U5 — Playwright authoring per distilled flow

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u5.md` and execute it in full. Do not work from memory.

One `.spec.ts` per distilled flow at `<cwd>/.architect-team/ux-tests/<persona-slug>/playwright/<flow-N>-<slug>.spec.ts` — test authoring applies `superpowers:test-driven-development` (the flow's assertions + `expected_user_effect` are written as the verification contract before the executors run them, per `## Plugin prerequisites (v3.9.0)`). Per `playwright-user-flows`:
- Real interaction calls.
- Real login.
- Per-step expectation files at `<cwd>/.architect-team/ux-tests/<persona-slug>/playwright/expectations/<flow-N>-<step-N>.json`, per `root-cause-test-failures`.
- **Selector witness assertions (v0.9.32) — MANDATORY for every action-call selector** (`.toBeVisible()` + `.toBeEnabled()` + a disambiguating role / attribute check). Same authoring discipline as the bug-replicator's `agents/bug-replicator.md` Step 2.
- **`expected_user_effect` block (v0.9.32) — MANDATORY per flow.** The U5 orchestrator emits an `expected_user_effect` field on every flow's spec (placed in a `<flow-N>-<slug>.effect.json` companion file at the same path) describing the concrete observable outcome the persona accomplishes by running this flow. The field is the input to U6's **flow-effect witness** (a flow that passes Playwright's assertion but didn't actually achieve the persona's intent is the failure mode the witness closes). Each effect is one of `dom_state_change` (an element appears/disappears/changes), `network_request` (a specific endpoint was called with a specific status), `url_change` (the URL landed at a specific route), or `console_sentinel` (a sentinel logged). Examples:

## Phase U6 — Execution (`flow-executor` agents per the review tier)

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u6.md` and execute it in full. Do not work from memory.

This phase is the pipeline's `superpowers:verification-before-completion` gate — each flow's pass/fail verdict rests on captured evidence (trace + screenshots + per-step expectation deltas + the flow-effect witness), never an unverified assertion, per `## Plugin prerequisites (v3.9.0)`.

## Phase U7 — Consensus on disagreements

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u7.md` and execute it in full. Do not work from memory.

The orchestrator pools the 3 executor verdicts per flow:

## Phase U8 — Bug routing to bug-fix-pipeline

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u8.md` and execute it in full. Do not work from memory.

Each routed bug carries its diagnosis downstream: the `bug-fix-pipeline` applies `superpowers:systematic-debugging` to replicate + root-cause every `ux-flow-failure` SR before any fix is proposed (per `## Plugin prerequisites (v3.9.0)`).

## Phase U9 — Final report

> **STOP.** Before acting under this section, Read `skills/ux-test-builder/references/phase-u9.md` and execute it in full. Do not work from memory.

Emit a summary report at `<cwd>/.architect-team/runs/ux-test-<persona-slug>-<ts>.md`:

## Operating rules (non-negotiable)

The UX-test-builder inherits every operating rule from `architect-team-pipeline`'s `## Operating rules (non-negotiable)` section — the no-arbitrary-timers rule, the unbounded-solving discipline (no iteration ceiling; loop until success), the shared-state concurrency model, the required-input-marker discipline, the safety rules for auto-commit. **Plus**:

- **Real-site testing.** All execution at U2 + U5 + U6 + the bug-fix pipeline's downstream B6 + B6b runs against the live target. NEVER mocked.
- **Independent expansion at U3.** The explorers (one by default; a panel of three at tier 3) do NOT consult each other during U3.
- **Literal first.** Phase U2 always runs BEFORE Phase U3 — the literal flow is the user's exact ask and gets its own pass.
- **Semantic distillation at U4.** Dedup is by goal + steps + rationale, not just string-match.
- **Tier-2 executor redundancy at U6.** Each flow runs once under the paired executor; a disputed flow runs again under a second executor, and three times only on a tier-3 panel — so flakiness surfaces as disagreement rather than as a silent pass.
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

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Five non-negotiable disciplines` | `skills/ux-test-builder/references/five-non-negotiable-disciplines.md` | on demand |
| `Notifications (per-project email events — opt-in, best-effort)` | `skills/ux-test-builder/references/notifications-per-project-email-events-opt-in-best-effort.md` | on demand |
| `Phase U0 — Intake` | `skills/ux-test-builder/references/phase-u0.md` | on demand |
| `Phase U2 — Literal flow draft` | `skills/ux-test-builder/references/phase-u2.md` | on demand |
| `Phase U3 — Flow expansion (`flow-explorer` agents per the review tier)` | `skills/ux-test-builder/references/phase-u3.md` | on demand |
| `Phase U4 — Distillation (orchestrator-serialized)` | `skills/ux-test-builder/references/phase-u4.md` | on demand |
| `Phase U5 — Playwright authoring per distilled flow` | `skills/ux-test-builder/references/phase-u5.md` | on demand |
| `Phase U6 — Execution (`flow-executor` agents per the review tier)` | `skills/ux-test-builder/references/phase-u6.md` | on demand |
| `Phase U7 — Consensus on disagreements` | `skills/ux-test-builder/references/phase-u7.md` | on demand |
| `Phase U8 — Bug routing to bug-fix-pipeline` | `skills/ux-test-builder/references/phase-u8.md` | on demand |
| `Phase U9 — Final report` | `skills/ux-test-builder/references/phase-u9.md` | on demand |
