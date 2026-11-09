---
name: common-pipeline-conventions
description: "Use as the canonical home for cross-cutting conventions shared by every architect-team pipeline (architect-team-pipeline, bug-fix-pipeline, mini-architect-team-pipeline). Consolidates the polyglot Python invocation rule, dispatch-mode selection (teams vs subagents) and persistence, the project-email notifier discipline (the 10 event types, the opt-in best-effort rule, the phase-boundary wiring rule), and the MemPalace wake-up precondition reference. Each pipeline skill references the canonical sections here rather than re-explaining the rule, so a single edit propagates."
user-invocable: false
---

# Common Pipeline Conventions

The three pipeline skills (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) share a growing set of cross-cutting disciplines (this file is the canonical home for every one of them — the founding four below and the 40+ added since; the RANKED binding set is the `Read this first` section). Without a canonical home, each pipeline re-explained the rule in its own body — three places to update on every change, three places to drift. This skill is the single source of truth. Each pipeline body references the section it needs and stays slim.

The founding conventions (procedure; the behavioral rules that bind every agent are ranked in the `Read this first` section):

1. **Cross-platform Python invocation** — every plugin-script call uses the polyglot `python3 X || python X` pattern so the same invocation works on Linux / macOS and on default Windows python.org installs.
2. **Dispatch mode selection (v1.0.0)** — teams vs subagents, decided once at pipeline entry, persisted to `intake-state.json`, with the teams-mode and subagents-mode dispatch primitives spelled out.
3. **Project-email notifications** — opt-in, best-effort, the 10 event types, the phase-boundary wiring rule.
4. **MemPalace wake-up precondition** — the wake-up runs before any subagent dispatch; the canonical rule lives in `mempalace-integration` (this skill points there).

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

## Read this first — the binding behavioral rules, in priority order (v3.66.0)

This file carries 50+ disciplines; since v4.0.0 only their headings, STOP pointers and first paragraphs live here, and the full chapters live under `references/`. Before each phase starts, open `skills/common-pipeline-conventions/references/INDEX.md` and Read every chapter it lists for that phase (and for `always`). These are the ones that bind every agent on every turn, RANKED — when two rules seem to conflict, the higher one wins. Each points at its canonical section; everything else in this file is procedure for carrying these out, read on demand from its STOP pointer, never from memory.

1. **Evidence before assertion** — state a result only after running the check and reading its output; a cause is a hypothesis until it survives an executed falsification (`docs/ETHOS.md` principle 7 + its section "A cause is a hypothesis until it survives an executed falsification").
2. **No self-imposed limits** — explore until you fully understand; no self-imposed turn count, budget, cycle cap, or time box; only the user sets a limit, explicitly (the "No self-imposed limits discipline" section below; `docs/ETHOS.md` principle 8).
3. **Unbounded solving** — loop until the gate is green; the only pause is a named missing input the owner alone holds (the "Unbounded solving discipline" section).
4. **Verification is a choice, not a lookup** — before verifying, enumerate local run / dev environment / replay / seeded fixture / production, pick the cheapest faithful venue, and record the plan (the `verification-planning` skill); a gate that needs a live environment obliges the run to PROVIDE one, never to ask (`references/local-dev-test-discipline.md`).
5. **The producer is never its own checker** (`team-spawning-and-review-gates`; `docs/ETHOS.md` principle 2).
6. **Honest boundary; relay claims as claims, verdicts as facts** (`docs/ETHOS.md` principle 3 + its "Evidence integrity" section).
7. **Fidelity to human-configured policy** — never edit, disable, or skip a human's configuration (the "Deploy mandate discipline" section; `hooks/deploy_config.py`).
8. **Scope discipline** — never silently narrow the prompt (the "Scope discipline" section).
9. **Teammate git discipline** — no destructive git operations (the "Teammate git discipline" section).
10. **Documentation currency** — docs ship current or the run does not ship (`documentation-currency`).

## No self-imposed limits discipline (v3.66.0)

An agent explores until it fully understands the problem, and it never rations that understanding. Concretely, no agent may impose on its own work — or on any agent it dispatches — a **turn** count, a token or cost **budget**, a **cycle** or round cap, a **time** box, a sampling cap standing in for a full walk, or a "good enough after N" cutoff. The only limits are the ones the user explicitly states — "spend only X", "only do this much", a `--max-iterations` the user passed, a `<budget-seconds>` the user passed — and a limit the user did not state is not a limit. Exhaustion, impatience, and the urge to summarise are not stopping conditions. The one sanctioned pause is a NAMED missing input that only the owner can supply, and it pauses only that thread while everything else continues.

Corollaries, so the rule is not misread: a bounded retry of an EXTERNAL flaky resource (a rate-limit backoff, a lock retry, the 2-attempt harness-truncation resume) is mechanics, not a limit on understanding; a write-scope bound ("Write only to `<path>`") is not a limit; a spawn-recursion depth bound is not a limit; a user-invoked flag (`--proposal-first`, `--max-iterations`, `<budget-seconds>`) is the user's limit and is honoured exactly. `tests/test_no_self_imposed_limits.py` sweeps `agents/`, `skills/`, `commands/` and `docs/ETHOS.md` for the forbidden shapes and forbids their return; `docs/ETHOS.md` principle 8 names the anti-pattern — *the self-rationed investigation*.

## Cross-platform Python invocation (polyglot pattern)

Every plugin-script call in any pipeline skill (and in `hooks/hooks.json`) uses the polyglot pattern:

```bash
python3 X.py args || python X.py args
```

The `python3` form is the Unix idiom (Linux / macOS). The `|| python ...` fallback handles default Windows python.org installs where only `python` is on PATH and `python3` triggers the Microsoft Store shim. On systems where `python3` is callable the shell short-circuits and the fallback never fires; on systems where it isn't, the second attempt runs with `python` and the script still succeeds.

**Binding convention.** When you copy a `python3 ...` invocation from a skill body into a Bash call (a notifier call, a hook command, a completion-audit invocation, anything else that points at a plugin script), copy the `|| python ...` fallback with it. The two halves are a unit — a bare `python3` invocation in a pipeline body is the failure mode this rule exists to prevent.

The same convention is asserted structurally by `tests/test_cross_consistency.py` (every `python3 X` plugin-script invocation in a pipeline skill body is paired with a `|| python X` fallback in the same shell command).

## Dispatch mode (v1.0.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/dispatch-mode.md` and execute it in full. Do not work from memory.

The pipelines support two dispatch primitives — **teams mode** (Claude Code's experimental Agent Teams: long-lived named teammates with their own 1M contexts, a shared task list, and direct `SendMessage`) and **subagents mode** (the v0.9.36 behavior — ephemeral `Agent`-tool dispatches, fresh context per call). The Lead decides which once, at startup, and the decision is the same for the entire run.
## Notifications wiring convention (per-project email events — opt-in, best-effort)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/notifications-wiring-convention.md` and execute it in full. Do not work from memory.

Governs the opt-in, best-effort per-project email notifier (`scripts/notify/notify.py`): its event types and the phase-boundary points every pipeline wires.

## MemPalace wake-up precondition

The wake-up is a precondition every pipeline depends on; it runs before any subagent dispatch. The canonical wake-up rule (the unscoped initial wake-up + the wing-scoped second pass + the `mempalace`-not-on-PATH surface note + the install-prompt sentence) lives in `mempalace-integration`'s `## Phase A — Wake-up at pipeline start` section. Each pipeline body cites that section and names the pipeline-specific entry condition (Phase −2 prelude for the main pipeline; Phase B−1 prelude for the bug-fix pipeline when invoked directly, no-op when reached via the main pipeline's Phase −2 routing; Phase M0 for the mini pipeline).

The wake-up is not numbered as a phase — it is a precondition the rest of the run depends on. Each pipeline body's reference to this section is the right shape; the rule itself is not re-explained.

## Running in parallel sessions

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/running-in-parallel-sessions.md` and execute it in full. Do not work from memory.

Governs concurrent `/architect-team` sessions on one project: one git worktree each, with the shared coordination state resolved through `scripts/setup/worktree_paths.py`.

## Auto-worktree lifecycle

> **STOP.** Before creating, cleaning up, or merging a run worktree, Read `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md` and execute it in full. Do not work from memory.

## Auto-merge-to-main discipline (v3.7.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md` and execute it in full. Do not work from memory.

Governs how a clean run's branch lands on `main` (`--no-ff`) and prunes its worktree, so autonomous runs are self-tidying.

## Scope-fidelity discipline family (v3.10.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/scope-fidelity-discipline-family.md` and execute it in full. Do not work from memory.

Governs the five scope-fidelity disciplines behind one root principle -- do the mandated work, never narrow or defer it unilaterally -- and their shared 3-disposition model.

## Scope discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/scope-discipline.md` and execute it in full. Do not work from memory.

Governs the user's prompt as the contract: reframing its scope to what the agent finds reasonable or convenient is an unauthorized domain decision, surfaced as a domain gate.

## Teammate git discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/teammate-git-discipline.md` and execute it in full. Do not work from memory.

Governs the run worktree's shared git state: a teammate works only in its owned file scope and never runs a destructive git command against the shared index, tree or HEAD.

## Contract-first parallelism (v3.48.0 — the canonical statement)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/contract-first-parallelism.md` and execute it in full. Do not work from memory.

Governs runs needing both a backend surface and a frontend over it: the architect settles the interface first so both sides build at once (the `contract-first-parallelism` skill).

## Frontend missing-API discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/frontend-missing-api-discipline.md` and execute it in full. Do not work from memory.

Governs a frontend element whose backend API does not exist and no contract-first protocol is running for it: never fake, mock, hardcode or stub -- file a solution requirement, pause, return when it ships.

## Background-agent resume discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/background-agent-resume-discipline.md` and execute it in full. Do not work from memory.

Governs a background agent whose report stream is lost after the work succeeded: resume from on-disk state (`scripts/setup/agent_resume.py`), never treat the empty result as failure.

## Agent checkpoint discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/agent-checkpoint-discipline.md` and execute it in full. Do not work from memory.

Governs long-running agents (over ~20 tool calls): write a lightweight checkpoint every ~10 tool calls, and on resume read it first to skip completed steps.

## Skill-invocation discipline (v2.0.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/skill-invocation-discipline.md` and execute it in full. Do not work from memory.

Governs VAO Layer 6: a pipeline-driving command is driven through the Skill tool, never applied by hand; `hooks/skill_invocation_audit.py` catches the bypass.

## Verified-live discipline (v2.2.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/verified-live-discipline.md` and execute it in full. Do not work from memory.

Governs the claim "verified live GREEN on the deployed URL": the verification must drive the bug-exposing gesture against the right target, or the claim itself is invalid.

## In-flight clarification discipline (v2.5.0)

> **STOP.** Before reacting to ANY user message that arrives while a pipeline is in-flight, Read `skills/common-pipeline-conventions/references/in-flight-clarification-discipline.md` and execute it in full. Do not work from memory.

Governs a user message arriving mid-run (`intake-state.json` open, `escalation-pending.md` present, or an unresolved `teammates/*.json` manifest): fold it into THIS run or open a sanctioned parallel lane; only an explicit cancel releases it.

## Live-data wiring discipline (v2.6.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/live-data-wiring-discipline.md` and execute it in full. Do not work from memory.

Governs "wire to live data" / "remove mocks" asks: adding the live wiring AND removing the mock path are both mandatory; no mock fallback stays reachable.

## No standing-red discipline (v2.8.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-standing-red-discipline.md` and execute it in full. Do not work from memory.

Governs a diagnosed regression: fix every named layer, route the rest via a solution requirement, or escalate for a confirmed stub -- never commit a failing test as documentation.

## Unilateral-override discipline (v3.0.0) — META

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/unilateral-override-discipline.md` and execute it in full. Do not work from memory.

Governs the root pattern beneath the v2.10.0 / v2.14.0 / v2.20.0 / v2.21.0 / v2.22.0 disciplines: a unilateral call against the user's explicit choice, confessed afterwards in virtue-framed language (`hooks/pretool_unilateral_override_guard.py`).

## Backend-from-frontend dispatch + analysis modularization (v3.4.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/backend-from-frontend-dispatch-and-analysis-modularization.md` and execute it in full. Do not work from memory.

Governs the three standalone analysis skills extracted from `intake-and-mapping` and `visual-to-api-design`, and Phase 0b, the backend dispatch check for backend-shaped requests.

## Data engineering exploration discipline (v3.5.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/data-engineering-exploration-discipline.md` and execute it in full. Do not work from memory.

Governs the structured exploration pipeline for data-engineering asks (dbt, Airflow, warehouses, streaming, lakehouses), dispatched by Phase 0c so such work never falls through to plain authoring.

## Phenotype convergence rules (v3.5.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/phenotype-convergence-rules.md` and execute it in full. Do not work from memory.

Governs the pairing and dependency relationships among the three production phenotypes (`user-management` / `ai-management` / `config-management`) every dispatch point must consult.

## Test-run monitor discipline (v3.3.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/test-run-monitor-discipline.md` and execute it in full. Do not work from memory.

Governs the passive observer team that watches test runs and writes a per-run report: log-only, no interrupts, no auto-SR filing, no gating.

## No end-of-run deferral discipline (v2.10.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-end-of-run-deferral-discipline.md` and execute it in full. Do not work from memory.

Governs run-end dispositions: every in-scope item is fixed, routed via a solution requirement, or an explicit confirmed stub in `coverage-map.json` -- never "Deferred" behind a "Want me to continue?" question.

## Multi-persona path-coverage discipline (v2.11.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/multi-persona-path-coverage-discipline.md` and execute it in full. Do not work from memory.

Governs multi-persona features: a fix is complete only when tested from EVERY persona's path, never one golden path.

## Dynamic affordance discovery discipline (v2.13.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/dynamic-affordance-discovery-discipline.md` and execute it in full. Do not work from memory.

Governs intake over a codebase: scan for affordance signatures (upload, download, real-time, notifications) and treat one present in code but absent from the requirements inventory as a failure.

## UX-test environment sequencing discipline (v2.13.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/ux-test-environment-sequencing-discipline.md` and execute it in full. Do not work from memory.

Governs UX-test order: LOCAL first (fast feedback), LIVE DEV last (the deployed bundle at the user's URL) -- both, never only one.

## No implementation-time scope cut discipline (v2.14.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-implementation-time-scope-cut-discipline.md` and execute it in full. Do not work from memory.

Governs a full-build mandate: never implement a scaffold subset and announce the cut as virtuous, nor frame partial work as an honest scope statement or shippable milestone.

## Prod-safe test classification discipline (v2.17.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/prod-safe-test-classification-discipline.md` and execute it in full. Do not work from memory.

Governs the `@prod-safe` / `@not-prod-safe` annotation every Playwright and QA test carries: only `@prod-safe` tests run against a production URL; unclassified is a failure.

## Codebase discipline registry (v2.18.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/codebase-discipline-registry.md` and execute it in full. Do not work from memory.

Governs the per-codebase registry of applied CT6 disciplines: an un-applied discipline found at pipeline start is auto-executed before the user's run continues.

## In-flight clarification injection mechanism (v2.19.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/in-flight-clarification-injection-mechanism.md` and execute it in full. Do not work from memory.

Governs HOW a mid-run message is injected: the per-run inbox JSONL (`hooks/inflight_inbox.py`), `/architect-team:inject`, the phase-boundary check, and the Layer 3 tool gating Phase 8 on ignored clarifications.

## Deploy mandate discipline (v2.20.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/deploy-mandate-discipline.md` and execute it in full. Do not work from memory.

Governs an explicit deploy verb plus completeness modifier: a HARD MANDATE satisfied only when every surface runs on live data from a real deployed backend (`hooks/deploy_config.py` holds the human-owned policy).

## No proxy-element verification discipline (v2.21.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-proxy-element-verification-discipline.md` and execute it in full. Do not work from memory.

Governs verification that cannot reach the target state or element: escalate; never measure a nearby proxy and report PASS -- the element measured is the SAME element the spec names.

## No pipeline-bypass discipline (v2.22.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-pipeline-bypass-discipline.md` and execute it in full. Do not work from memory.

Governs any pipeline-driving command: actually execute the dispatch, OpenSpec ceremony, worktree isolation, review gates and completion audit -- never apply the methodology by hand.

## Exploration documentation standard (v3.2.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/exploration-documentation-standard.md` and execute it in full. Do not work from memory.

Governs the five `*_MAP.md` documents the Exploration Pipeline writes under `<codebase>/docs/`: names, paths, frontmatter and bodies, one schema for producer and consumers.

## Unbounded solving discipline (v3.8.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/unbounded-solving-discipline.md` and execute it in full. Do not work from memory.

Governs the dev-loop's stopping conditions: run until SUCCESS with NO iteration ceiling; only success or a deliberate pause for genuinely-required owner input interrupts it.

## Run continuity discipline (v3.30.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/run-continuity-discipline.md` and execute it in full. Do not work from memory.

Governs driving a started run to completion across turn ends, compactions and restarts: the pipeline stays mandatory until the run completes or the USER stands it down (`hooks/run_continuity.py`).

## Run metrics + success measurement (v3.8.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/run-metrics-and-success-measurement.md` and execute it in full. Do not work from memory.

Governs the bug-fix run metrics (REQ-CDL-02 / REQ-SAFE-02) that `hooks/run_metrics.py` records per run, so the structured-bug-isolation reorder is justified by measured outcomes.

## Uniform plugin usage (v3.9.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/uniform-plugin-usage.md` and execute it in full. Do not work from memory.

Governs how every pipeline invokes its orchestration dependencies -- the native `ct6-converge` workflow (declare, then record), the CONDITIONAL superpowers plugin with native fallback, the OpenSpec CLI/skills -- from this one home.

## Layer 3 gate invocation table (v3.10.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/layer-3-gate-invocation-table.md` and execute it in full. Do not work from memory.

Governs the single parameterized home of the Layer 3 gate invocations (`hooks/vao_tools.py`) each pipeline cites by gate name and phase; best-effort unless the gate's discipline says it blocks.

## Appearance-change policy discipline (v3.14.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/appearance-change-policy-discipline.md` and execute it in full. Do not work from memory.

Governs frontend APPEARANCE: what the user sees changes only when the user asked, approved, or granted free rein; backend changes are unrestricted.

## Declared-gates discipline (v3.47.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/declared-gates-discipline.md` and execute it in full. Do not work from memory.

Governs any gate named on ship, deploy, merge or completion: record it in `declared-gates.json` when stated; the Stop audit (`hooks/pipeline-completion-audit.py`) holds the run to it.

## Spec currency discipline (mid-run) (v3.47.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/spec-currency-discipline-mid-run.md` and execute it in full. Do not work from memory.

Governs edits to `openspec/changes/<slug>/` after Phase 2 dispatches: the orchestrator owns spec currency while teammates read it; a silent amendment re-points a contract already built against.

## Local -> dev -> test-on-dev is the pipeline's job, not the user's (v3.57.0)

> **STOP.** Before escalating a gate that needs a live environment, Read `skills/common-pipeline-conventions/references/local-dev-test-discipline.md` and execute it in full. Do not work from memory.

## Augment-never-replace discipline (v3.63.0)

> **STOP.** Before arming, dispatching, or gating on an optional third-party capability, Read `skills/common-pipeline-conventions/references/augment-never-replace.md` and execute it in full. Do not work from memory.

## Git commit identity discipline (v3.67.0)

> **STOP.** Before the first commit-authoring git command of a run (`commit` / `merge` / `revert`), Read `skills/common-pipeline-conventions/references/git-commit-identity.md` and execute it in full. Do not work from memory.

Governs who a run commits as -- the PERSON driving it, resolved once per checkout by `hooks/git_identity.py` (recorded, confirmed, or asked; never a hardcoded default) and refused by `hooks/pretool_skill_gate.py` Arm 4 when absent.

## Deletion discipline (v4.0.0)

> **STOP.** Before deleting, trashing or pruning any file, directory or run artifact, Read `skills/common-pipeline-conventions/references/deletion-discipline.md` and execute it in full. Do not work from memory.

Governs deleting, trashing or pruning: soft delete via the `trash` verb of `hooks/deletion_guard.py` is the default; a hard delete needs the guard (PreToolUse on `Bash`) to prove the content survives elsewhere.

## Test selection discipline (v4.0.0)

> **STOP.** Before any phase runs a test suite, Read `skills/common-pipeline-conventions/references/test-selection.md` and select through `scripts/test_index/cli.py`. Do not run "the whole suite" from habit.

Governs which tests each gate runs: those selected for the change set through `scripts/test_index/cli.py`, plus human-owned pins and unknown-mapping tests; the full suite runs once at Phase 8.

## Converge workflows (v4.0.0)

> **STOP.** Before running any "N reviewers loop until all ok" gate, Read `skills/common-pipeline-conventions/references/converge-workflows.md` and run the gate exactly as it says. Do not describe the loop in prose.

Governs every reviewer-convergence gate: DECLARE it, run `workflows/ct6-converge.js` (N blind reviewers, no round cap), RECORD, and satisfy it only when the record says converged with every reviewer `ok`.

## Native methodology (v4.0.0)

> **STOP.** When a lane's pre-flight finds `superpowers` or `cartographer` absent, Read `skills/common-pipeline-conventions/references/native-methodology.md` and run the lane with the native forms. Never abort for a missing optional plugin.

Governs a lane whose pre-flight finds `superpowers` or `cartographer` absent: both are CONDITIONAL; the lane records `methodology: native`, runs the native forms, never aborts.

## Completion-hold release (v4.1.0)

> **STOP.** When a turn is being held and you are deciding what to do about it, Read `skills/common-pipeline-conventions/references/completion-unlock.md` and act within it. Do not look for the exit.

Governs a held turn: open registered work holds it and nothing an agent writes releases it; finish the work or run the read-only `inspect` verb of `hooks/completion_unlock.py` and report -- release is the USER's `/architect-team:unlock`.

## Where this skill plugs in

- `architect-team-pipeline/SKILL.md` references this skill's four sections in place of re-explaining the rules.
- `bug-fix-pipeline/SKILL.md` references this skill's four sections.
- `mini-architect-team-pipeline/SKILL.md` references this skill's four sections (the mini pipeline's notifications wiring is included per the v1.0.0 decision to give mini-runs the same observability as the other two pipelines).
- `team-spawning-and-review-gates/SKILL.md` cross-references the dispatch-mode section for its teams-mode vs subagents-mode review-gate primitives.
- `mempalace-integration/SKILL.md` is the canonical home of the wake-up rule itself; this skill points there. v1.1.0 — the mempalace palace path resolves through `shared_state_dir()`, matching the shared-state split documented in `## Running in parallel sessions`.
- `superpowers:using-git-worktrees` is the upstream skill for worktree lifecycle mechanics (`add` / `remove` / branch hygiene) when the CONDITIONAL `superpowers` plugin is installed; `## Running in parallel sessions` references it rather than re-explaining, and `scripts/setup/worktree_lifecycle.py` is the native path that runs either way.
- `scripts/setup/worktree_paths.py` is the resolution primitive — `shared_state_dir()` / `run_state_dir()` / `is_worktree()` — used by the lock layer and the MemPalace integration.
- `scripts/setup/worktree_lifecycle.py` is the v1.2.0 lifecycle helper — `create_run_worktree()` / `cleanup_run_worktree()` / `current_worktree_is_run()` / `current_run_slug()` — used by the 3 pipeline slash commands' auto-worktree step.
- `tests/test_dispatch_mode_section.py` asserts the dispatch-mode contract against this skill body AND against every pipeline skill's reference-back.
- `tests/test_cross_consistency.py` asserts every `python3 ...` plugin-script invocation in a pipeline skill body is paired with a `|| python ...` fallback.
- `tests/test_worktree_state_resolution.py` (v1.1.0) asserts the worktree-aware resolution primitive against a real `git worktree add`-created worktree.
- `tests/test_worktree_lifecycle.py` (v1.2.0) asserts the lifecycle helper against real `git init` + `git worktree add` fixtures — happy path, collision handling, run-detection, slug extraction, cleanup with + without branch removal.

## Operating rules (non-negotiable)

> These are AUTHORING rules for maintaining this file. The behavioral rules that bind every agent at run time are ranked in the "Read this first" section at the top of this file — read those; these govern how this file is edited.

- A change to any of the four conventions edits this skill ONCE. The pipeline skills' references stay one-line; the rule update propagates by reference.
- A pipeline skill MUST NOT re-explain any of the four conventions inline — replace it with a reference to this skill. Inline re-explanation is the drift-risk this skill exists to remove.
- A pipeline skill's per-phase notifier invocations (the actual `notify.py phase_start --phase "Phase 2 — ..."` calls at each phase boundary) STAY in the pipeline body — those are per-phase content, not cross-cutting. The per-phase invocations follow the polyglot pattern from this skill's `## Cross-platform Python invocation` section.
- The dispatch primitives (teams-mode vs subagents-mode) are spelled out in this skill ONCE. A pipeline body references them; it does not re-spell the primitives.
- The ten notifier events are an exclusive set. A pipeline body that needs an eleventh event does NOT invent it inline — it adds the event to this skill's enumerated list first, then references the new event from the pipeline body.

## Reference index

Heavy, rarely-fired procedure detail lives in this skill's `references/` folder and is pulled in on demand via the STOP pointers in the sections above. Each row is the canonical home of that block; work from the reference file, never from memory.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Dispatch mode (v1.0.0)` | `skills/common-pipeline-conventions/references/dispatch-mode.md` | on demand |
| `Notifications wiring convention (per-project email events — opt-in, best-effort)` | `skills/common-pipeline-conventions/references/notifications-wiring-convention.md` | on demand |
| `Running in parallel sessions` | `skills/common-pipeline-conventions/references/running-in-parallel-sessions.md` | on demand |
| `Auto-worktree lifecycle` | `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md` | on demand |
| `Auto-merge-to-main discipline (v3.7.0)` | `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md` | on demand |
| `Scope-fidelity discipline family (v3.10.0)` | `skills/common-pipeline-conventions/references/scope-fidelity-discipline-family.md` | on demand |
| `Scope discipline` | `skills/common-pipeline-conventions/references/scope-discipline.md` | on demand |
| `Teammate git discipline` | `skills/common-pipeline-conventions/references/teammate-git-discipline.md` | on demand |
| `Contract-first parallelism (v3.48.0 — the canonical statement)` | `skills/common-pipeline-conventions/references/contract-first-parallelism.md` | on demand |
| `Frontend missing-API discipline` | `skills/common-pipeline-conventions/references/frontend-missing-api-discipline.md` | on demand |
| `Background-agent resume discipline` | `skills/common-pipeline-conventions/references/background-agent-resume-discipline.md` | on demand |
| `Agent checkpoint discipline` | `skills/common-pipeline-conventions/references/agent-checkpoint-discipline.md` | on demand |
| `Skill-invocation discipline (v2.0.0)` | `skills/common-pipeline-conventions/references/skill-invocation-discipline.md` | on demand |
| `Verified-live discipline (v2.2.0)` | `skills/common-pipeline-conventions/references/verified-live-discipline.md` | on demand |
| `In-flight clarification discipline (v2.5.0)` | `skills/common-pipeline-conventions/references/in-flight-clarification-discipline.md` | on demand |
| `Live-data wiring discipline (v2.6.0)` | `skills/common-pipeline-conventions/references/live-data-wiring-discipline.md` | on demand |
| `No standing-red discipline (v2.8.0)` | `skills/common-pipeline-conventions/references/no-standing-red-discipline.md` | on demand |
| `Unilateral-override discipline (v3.0.0) — META` | `skills/common-pipeline-conventions/references/unilateral-override-discipline.md` | on demand |
| `Backend-from-frontend dispatch + analysis modularization (v3.4.0)` | `skills/common-pipeline-conventions/references/backend-from-frontend-dispatch-and-analysis-modularization.md` | on demand |
| `Data engineering exploration discipline (v3.5.0)` | `skills/common-pipeline-conventions/references/data-engineering-exploration-discipline.md` | on demand |
| `Phenotype convergence rules (v3.5.0)` | `skills/common-pipeline-conventions/references/phenotype-convergence-rules.md` | on demand |
| `Test-run monitor discipline (v3.3.0)` | `skills/common-pipeline-conventions/references/test-run-monitor-discipline.md` | on demand |
| `No end-of-run deferral discipline (v2.10.0)` | `skills/common-pipeline-conventions/references/no-end-of-run-deferral-discipline.md` | on demand |
| `Multi-persona path-coverage discipline (v2.11.0)` | `skills/common-pipeline-conventions/references/multi-persona-path-coverage-discipline.md` | on demand |
| `Dynamic affordance discovery discipline (v2.13.0)` | `skills/common-pipeline-conventions/references/dynamic-affordance-discovery-discipline.md` | on demand |
| `UX-test environment sequencing discipline (v2.13.0)` | `skills/common-pipeline-conventions/references/ux-test-environment-sequencing-discipline.md` | on demand |
| `No implementation-time scope cut discipline (v2.14.0)` | `skills/common-pipeline-conventions/references/no-implementation-time-scope-cut-discipline.md` | on demand |
| `Prod-safe test classification discipline (v2.17.0)` | `skills/common-pipeline-conventions/references/prod-safe-test-classification-discipline.md` | on demand |
| `Codebase discipline registry (v2.18.0)` | `skills/common-pipeline-conventions/references/codebase-discipline-registry.md` | on demand |
| `In-flight clarification injection mechanism (v2.19.0)` | `skills/common-pipeline-conventions/references/in-flight-clarification-injection-mechanism.md` | on demand |
| `Deploy mandate discipline (v2.20.0)` | `skills/common-pipeline-conventions/references/deploy-mandate-discipline.md` | on demand |
| `No proxy-element verification discipline (v2.21.0)` | `skills/common-pipeline-conventions/references/no-proxy-element-verification-discipline.md` | on demand |
| `No pipeline-bypass discipline (v2.22.0)` | `skills/common-pipeline-conventions/references/no-pipeline-bypass-discipline.md` | on demand |
| `Exploration documentation standard (v3.2.0)` | `skills/common-pipeline-conventions/references/exploration-documentation-standard.md` | on demand |
| `Unbounded solving discipline (v3.8.0)` | `skills/common-pipeline-conventions/references/unbounded-solving-discipline.md` | on demand |
| `Run continuity discipline (v3.30.0)` | `skills/common-pipeline-conventions/references/run-continuity-discipline.md` | on demand |
| `Run metrics + success measurement (v3.8.0)` | `skills/common-pipeline-conventions/references/run-metrics-and-success-measurement.md` | on demand |
| `Uniform plugin usage (v3.9.0)` | `skills/common-pipeline-conventions/references/uniform-plugin-usage.md` | on demand |
| `Layer 3 gate invocation table (v3.10.0)` | `skills/common-pipeline-conventions/references/layer-3-gate-invocation-table.md` | on demand |
| `Appearance-change policy discipline (v3.14.0)` | `skills/common-pipeline-conventions/references/appearance-change-policy-discipline.md` | on demand |
| `Declared-gates discipline (v3.47.0)` | `skills/common-pipeline-conventions/references/declared-gates-discipline.md` | on demand |
| `Spec currency discipline (mid-run) (v3.47.0)` | `skills/common-pipeline-conventions/references/spec-currency-discipline-mid-run.md` | on demand |
| `Local -> dev -> test-on-dev is the pipeline's job, not the user's (v3.57.0)` | `skills/common-pipeline-conventions/references/local-dev-test-discipline.md` | on demand |
| `Augment-never-replace discipline (v3.63.0)` | `skills/common-pipeline-conventions/references/augment-never-replace.md` | on demand |
| `Git commit identity discipline (v3.67.0)` | `skills/common-pipeline-conventions/references/git-commit-identity.md` | on demand |
| `Deletion discipline (v4.0.0)` | `skills/common-pipeline-conventions/references/deletion-discipline.md` | on demand |
| `Test selection discipline (v4.0.0)` | `skills/common-pipeline-conventions/references/test-selection.md` | on demand |
| `Converge workflows (v4.0.0)` | `skills/common-pipeline-conventions/references/converge-workflows.md` | on demand |
| `Native methodology (v4.0.0)` | `skills/common-pipeline-conventions/references/native-methodology.md` | on demand |
| `Completion-hold release (v4.1.0)` | `skills/common-pipeline-conventions/references/completion-unlock.md` | on demand |
