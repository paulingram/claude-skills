---
name: common-pipeline-conventions
description: "Use as the canonical home for cross-cutting conventions shared by every architect-team pipeline (architect-team-pipeline, bug-fix-pipeline, mini-architect-team-pipeline). Consolidates the polyglot Python invocation rule, dispatch-mode selection (teams vs subagents) and persistence, the project-email notifier discipline (the 5 event types, the opt-in best-effort rule, the phase-boundary wiring rule), and the MemPalace wake-up precondition reference. Each pipeline skill references the canonical sections here rather than re-explaining the rule, so a single edit propagates."
user-invocable: false
---

# Common Pipeline Conventions

The three pipeline skills (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) share a growing set of cross-cutting disciplines (this file is the canonical home for every one of them — the founding four below and the 40+ added since; the RANKED binding set is the `Read this first` section). Without a canonical home, each pipeline re-explained the rule in its own body — three places to update on every change, three places to drift. This skill is the single source of truth. Each pipeline body references the section it needs and stays slim.

The founding conventions (procedure; the behavioral rules that bind every agent are ranked in the `Read this first` section):

1. **Cross-platform Python invocation** — every plugin-script call uses the polyglot `python3 X || python X` pattern so the same invocation works on Linux / macOS and on default Windows python.org installs.
2. **Dispatch mode selection (v1.0.0)** — teams vs subagents, decided once at pipeline entry, persisted to `intake-state.json`, with the teams-mode and subagents-mode dispatch primitives spelled out.
3. **Project-email notifications** — opt-in, best-effort, the 5 event types, the phase-boundary wiring rule.
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

A pipeline run is a long, mostly-unattended sequence of phases. The plugin ships an **opt-in per-project email notifier** so a configured list of stakeholders is kept informed as a run progresses. Every pipeline wires it at the canonical event points below.
## MemPalace wake-up precondition

The wake-up is a precondition every pipeline depends on; it runs before any subagent dispatch. The canonical wake-up rule (the unscoped initial wake-up + the wing-scoped second pass + the `mempalace`-not-on-PATH surface note + the install-prompt sentence) lives in `mempalace-integration`'s `## Phase A — Wake-up at pipeline start` section. Each pipeline body cites that section and names the pipeline-specific entry condition (Phase −2 prelude for the main pipeline; Phase B−1 prelude for the bug-fix pipeline when invoked directly, no-op when reached via the main pipeline's Phase −2 routing; Phase M0 for the mini pipeline).

The wake-up is not numbered as a phase — it is a precondition the rest of the run depends on. Each pipeline body's reference to this section is the right shape; the rule itself is not re-explained.

## Running in parallel sessions

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/running-in-parallel-sessions.md` and execute it in full. Do not work from memory.

When two `/architect-team` invocations need to run **at the same time on the same project on the same machine** — the typical case is one developer driving two concurrent feature slices against independent file scopes — the right primitive is **git worktrees**. Each session opens its own worktree (its own working tree on its own branch), so neither can clobber the other's index, working files, or branch head. v1.1.0 adds the state-resolution layer that lets worktree-based sessions ALSO share the architect-team coordination layers they need to share.
## Auto-worktree lifecycle

> **STOP.** Before creating, cleaning up, or merging a run worktree, Read `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md` and execute it in full. Do not work from memory.

## Auto-merge-to-main discipline (v3.7.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md` and execute it in full. Do not work from memory.

This is the canonical home of the auto-merge-to-main rules; the three slash command bodies and the three pipeline skill bodies reference it rather than re-explaining. The user asked for autonomous runs to be self-tidying — a clean run should land on `main` and clean up after itself, not leave a growing pile of feature branches + worktrees behind a manual PR step.
## Scope-fidelity discipline family (v3.10.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/scope-fidelity-discipline-family.md` and execute it in full. Do not work from memory.

Five disciplines enforce ONE root principle — **the agent does the mandated work; it never unilaterally narrows the scope or defers the work, and never frames the narrowing/deferral as acceptable** — at five distinct moments in a run's timeline. They share marker lists, severities, the Layer 3 verification surface, and (above all) the **3-disposition model**. This section is the canonical family home; the five member sections below carry each discipline's RULE (markers, severities, paths) and reference this table for the firing-moment distinctions and the disposition model.
## Scope discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/scope-discipline.md` and execute it in full. Do not work from memory.

A pipeline run starts with a user prompt. The first thing the run does — before refinement, before triage, before any teammate dispatches — is *read that prompt*. The user's prose IS the contract. Reframing the prompt's scope to fit what the agent thinks is reasonable, what fits the available time, what the agent already knows how to do, or what the agent has been hoping to defer, is **not** the same as answering an obvious clarifying question. It is a domain decision the user hasn't authorized. The plugin treats it as a domain gate and makes the agent surface it explicitly.
## Teammate git discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/teammate-git-discipline.md` and execute it in full. Do not work from memory.

Teammates work on their owned file scope. They MUST NOT manipulate shared git state. Even with the v1.2.0 per-run worktree (each `/architect-team` invocation gets its own working tree), the teammates WITHIN a single run share that worktree — the index, the working tree, the stash stack, the reflog, the branch HEAD are all one shared piece of state. A teammate that runs a destructive git command against that shared state is touching the work of every other teammate dispatched into the same run.
## Contract-first parallelism (v3.48.0 — the canonical statement)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/contract-first-parallelism.md` and execute it in full. Do not work from memory.

When a run needs BOTH backend surface work AND a frontend that visualizes that data, the architect settles the INTERFACE first and makes it real immediately, so both sides build at once. The frontend never needed the backend's implementation — only its interface, and those become available at very different times.
## Frontend missing-API discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/frontend-missing-api-discipline.md` and execute it in full. Do not work from memory.

When the frontend agent builds a UI element (a button, a form field, a list, a status display, an avatar) that needs a backend API which **does not yet exist** and no contract-first protocol is running for it, the agent must NOT improvise. The four improvisations are all defects in the costume of progress — each ships visibly-broken work that downstream gates catch only after wasted round trips. v1.7.0 names the explicit alternative: surface the missing API as a structured solution requirement, pause that element's work, continue on other elements, and return to wire up when the backend ships the endpoint.
## Background-agent resume discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/background-agent-resume-discipline.md` and execute it in full. Do not work from memory.

When the orchestrator dispatches a long-running background agent, the harness-level stream delivering the agent's final report can be lost to a rate-limit cutoff / network blip even when the work succeeded end-to-end (motivating case in CHANGELOG: a `dv-attorney` agent did 68 tool-calls of real work, finished, then its report stream was cut — the orchestrator saw an empty result and treated it as failed though the work was on disk the whole time; only the REPORT was lost).
## Agent checkpoint discipline

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/agent-checkpoint-discipline.md` and execute it in full. Do not work from memory.

A long-running agent (one whose work is expected to exceed ~20 tool calls — system-architect drafting, backend implementing a multi-endpoint slice, master-synthesizer auditing, integration testing) MUST write a lightweight checkpoint to disk every ~10 tool calls (or after each logical step, whichever comes first). The checkpoint exists for one purpose: when an agent is resumed after a stream timeout, it reads its OWN checkpoint FIRST and skips already-completed steps, avoiding 68 tool-calls of re-work.
## Skill-invocation discipline (v2.0.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/skill-invocation-discipline.md` and execute it in full. Do not work from memory.

Layer 6 of the Verified Agent Output (VAO) framework — the gate that ensures the OTHER FIVE LAYERS get a chance to fire at all. The heirship-app-v2 session that triggered this discipline: a user typed `/architect-team:architect-team review the excel list`, but earlier in the same session an `architect-team` Skill had already been invoked. The harness's system reminder said *"this skill has been invoked earlier in this session"*. The agent interpreted that as a SESSION-WIDE ban on re-invocation and "applied the methodology by hand" — read files, edited code, ran tests, made commits — all WITHOUT calling the Skill tool. None of Layers 1-5 fired because the framework was never reinvoked. The user's explicit instruction got the work, but none of the structural verification.
## Verified-live discipline (v2.2.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/verified-live-discipline.md` and execute it in full. Do not work from memory.

The class of failure: **an agent claims "verified live GREEN on the deployed URL" while the verification never actually drove the bug-exposing gesture.** The VAO Layer 3 tools take agent CLAIMS as input but assume the verification was AGAINST THE RIGHT THING; v2.2.0 closes the gap one rung up — was the VERIFICATION CLAIM ITSELF valid?
## In-flight clarification discipline (v2.5.0)

> **STOP.** Before reacting to ANY user message that arrives while a pipeline is in-flight, Read `skills/common-pipeline-conventions/references/in-flight-clarification-discipline.md` and execute it in full. Do not work from memory.

The rule in one paragraph (the failure shape, the detection-signal table, the fold procedure, the anti-pattern rationales, the cancellation table and the clarifications-log schema are in the reference file): a pipeline is **in-flight** when ANY of the 3 detection signals holds — `<workspace>/.architect-team/intake-state.json` present with `completed_at` null / `phase` < 8 / status `in_progress`; `<workspace>/.architect-team/escalation-pending.md` present; or an unresolved `<workspace>/.architect-team/teammates/*.json` manifest with no matching `reviews/<task-id>.json`. A user message that arrives then and does NOT explicitly cancel the run is an amendment to THIS run: the orchestrator MUST **append** it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, **re-evaluate** the in-flight phase (`clarification` → fold into the next phase's inputs; `scope-amendment` → re-run Phase 0 → 1 with the amended brief; `parallel-problem` → open a sanctioned in-run lane per `### Parallel lanes (v3.16.0)` below), and **continue** the run. The 4 forbidden anti-patterns — **solve-with-tools-directly**, **answer-conversationally**, **spawn-sibling-invocation**, **silently-ignore** — each act outside the pipeline and bypass every discipline; a sanctioned in-run lane is NOT a sibling and is NOT this anti-pattern. The ONLY mid-run release is the cancellation channel: an explicit `/architect-team cancel` / `/architect-team stop` / `/architect-team:cancel` / `/architect-team:stop`, a new explicit `/architect-team:<other-command>`, or plain-prose "cancel the run" / "stop the pipeline" / "abort"; the default leans heavily toward "fold into pipeline" — ambiguous prose is a clarification, not a cancel. Symmetric with v2.0.0 Layer 6 (`hooks/skill_invocation_audit.py`, which catches the inverse case): together they close both directions of "the agent should not operate outside the framework."

### Parallel lanes (v3.16.0)

The v2.5.0 dispositions above (`clarification` / `scope-amendment`) FOLD an injected message into the single sequential flow. That is right when the message depends on the in-flight work. It is WRONG when the user injects a SEPARABLE, independent problem and wants it worked NOW, in parallel — the verbatim driver: *"inject just sits there passively … I need it to spawn more teams so we can have multiple problems worked on in parallel."* v3.16.0 adds the `parallel-problem` disposition + a sanctioned concurrent **lane**.

**When to classify `parallel-problem`** (all three must hold): the injected problem (a) does NOT depend on the in-flight work's outputs, (b) touches a file scope DISJOINT from every active lane's scope, and (c) is a real unit of work (not a clarification of existing work). If scope overlaps an active lane, it is NOT parallel — fold it (or queue it behind that lane). When unsure, prefer `clarification`/`scope-amendment` (folding is always safe; a wrong parallel-spawn risks two lanes colliding).

**Lane mechanics:**
1. **Acquire a disjoint file-scope lock FIRST.** Before spawning, the Lead calls `hooks/locks.py::acquire_lock(scope_glob, ttl, run_id)` for the lane's file scope. If it returns `blocked` (the scope intersects an active lane — `acquire_lock` uses `globs_intersect`), the lane does NOT spawn in parallel — it queues until the holding lane releases, OR it is folded. Disjoint glob → the lock is granted. This is the SAME lock layer that already serializes parallel `/architect-team` sessions (`## Running in parallel sessions`); a lane is just an intra-run lock holder.
   - **Isolation residual — be honest about what the lock does NOT catch.** `acquire_lock` is FILE-GLOB-level and ADVISORY (not a mutex; and NOT call-graph-aware — `cdlg_overlap` exists in `hooks/locks.py` but is a separate helper that is NOT wired into `acquire_lock`). So two lanes with file-disjoint globs that both reach a shared HOT CALLEE, or a lane that edits a file OUTSIDE its declared glob, are NOT prevented from colliding. Mitigation: keep lane scopes COARSE and genuinely independent (whole subsystems / top-level directories), declare the glob to cover everything the lane will actually touch, and prefer FOLDING whenever independence is uncertain (per the safe default above). Phase 4 reconciliation is the backstop if two lanes do touch a shared boundary.
2. **Spawn the lane as a BACKGROUND team.** The Lead dispatches the lane's team with `run_in_background: true` (per the `Background-agent resume discipline` section, routing the result through `wrap_agent_result()`), so the Lead's turn is NOT blocked and it can keep draining the inbox + servicing other lanes. The lane runs the normal Phase 2 → 3 → 5 gates + writes its own review-gate evidence; it is one coherent run with multiple lanes, NOT a sibling invocation. **If the lane FAILS to spawn** — `acquire_lock` returned `blocked`, or the background dispatch returns `resumed_failed` (per the resume discipline) — do NOT mark the message `parallel-problem` (that classification REQUIRES a live `lane_id` and `mark_processed` raises without one); instead downgrade it to `clarification` / `scope-amendment` (fold) or queue it, and mark it processed under that classification. A failed lane must never leave the message unprocessed at Phase 8.
3. **Record the linkage.** The Lead marks the inbox message processed with `classification="parallel-problem"` and `lane_id=<the spawned lane id>` (`hooks/inflight_inbox.py::mark_processed(..., lane_id=...)` — which REQUIRES a non-empty `lane_id` for this classification). This makes "did a lane actually open for this problem?" auditable on disk.
4. **Converge via Phase 4.** When the lane completes, its work reconciles into the run through the existing Phase 4 reconciliation (shared-boundary diff), exactly as parallel Phase 2 teammates do. The lane's commits attribute to the one run's coverage map.

**Responsiveness protocol (poll on every wake, not just phase boundaries).** Because lanes run in the background, the Lead's turn returns between dispatch completions. The orchestrator MUST drain the inbox (`unprocessed_messages`) at **every phase boundary AND after every background-dispatch return / wake** — not only at phase boundaries. This is what makes an inject get serviced promptly instead of waiting for the next phase ("the listener is caught up with other stuff" was the symptom of polling only at boundaries while blocked on a synchronous teammate).

**Honest harness constraint — do NOT overclaim.** The Lead is a single model-driven agent; there is no async push/listener thread that wakes the orchestrator the instant a message lands. "Responsive" here means: dispatch in the background so the Lead is not blocked, and poll the inbox aggressively on every wake/return so the message is drained at the next opportunity — typically the next dispatch boundary, not an interrupt. A message injected while the Lead is mid-tool-call is serviced when that call returns, not preemptively. The win is real (background + every-wake polling drains in seconds-to-one-dispatch instead of waiting a whole phase), but it is polling, not preemption.

**Dispatch-mode caveat (v3.16.0).** Background lanes + every-wake polling are **teams-mode** primitives — `run_in_background: true` is what frees the Lead's turn (see `## Dispatch mode`). In the **subagents-mode fallback** the harness blocks the Lead's turn until each dispatch RETURNS, so a lane CANNOT run truly concurrently: it degrades to SEQUENTIAL (queued behind the current dispatch) and the every-wake poll collapses to the phase-boundary poll. The classification + disjoint-lock + Phase-4 convergence machinery still applies; only the concurrency degrades. The orchestrator knows which mode is active from `intake-state.json::dispatch_mode` and must not promise concurrency it cannot deliver in subagents mode.

## Live-data wiring discipline (v2.6.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/live-data-wiring-discipline.md` and execute it in full. Do not work from memory.

A user-reported recurring failure: when a requirement explicitly says "wire to live data" / "remove mocks" / "stop using fixtures" / "use real backend", the agent satisfies the requirement's POSITIVE half (adds the live wiring) but leaves the NEGATIVE half (removes the mock wiring) silently unaddressed. The UI continues to render mock fallbacks because the mock-state code path is still reachable.
## No standing-red discipline (v2.8.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-standing-red-discipline.md` and execute it in full. Do not work from memory.

Agents MUST NOT commit a failing test as documentation of a known bug. When a regression is diagnosed — including cross-layer cases where the agent proves one layer is correct and the other is broken — the agent's only valid endings are: (a) fix every layer the diagnosis names in this change, OR (b) route the unfixed layer via a solution requirement so the orchestrator dispatches the right team, OR (c) escalate for an explicit confirmed-stub decision. **Committing a failing test that "will go green when fixed" is none of these.** It's a discipline failure that ships visible red CI signal as a substitute for routing the fix.
## Unilateral-override discipline (v3.0.0) — META

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/unilateral-override-discipline.md` and execute it in full. Do not work from memory.

The v2.10.0 / v2.14.0 / v2.20.0 / v2.21.0 / v2.22.0 disciplines below all catch surface manifestations of ONE underlying pattern: the agent makes a unilateral judgment call against the user's explicit choice, then post-hoc confesses with virtue-framed language. v3.0.0 ships the meta-discipline that detects this pattern at its root.
## Backend-from-frontend dispatch + analysis modularization (v3.4.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/backend-from-frontend-dispatch-and-analysis-modularization.md` and execute it in full. Do not work from memory.

v3.4.0 extracts the analysis primitives previously inline in `intake-and-mapping` and `visual-to-api-design` into 3 standalone reusable skills, AND adds `Phase 0b — Backend dispatch check` for backend-shaped requests with optional frontend OR documentation references. Three orthogonal jobs that were entangled:
## Data engineering exploration discipline (v3.5.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/data-engineering-exploration-discipline.md` and execute it in full. Do not work from memory.

v3.5.0 ships a structured exploration pipeline for data engineering / data architecture asks — the analog of `visual-to-api-design` for the data plane. Dispatched by a new `Phase 0c — Data-engineering dispatch check` in `architect-team-pipeline`. Closes the gap surfaced in v3.4.0's honest assessment: pure data-engineering work (dbt projects / Airflow DAGs / Snowflake warehouses / Kafka streaming / lakehouses / data meshes) was hitting `Phase 0b Branch D` (no structured exploration, fell through to plain-branch authoring) when the structured analysis stages it would benefit from are different from the REST-API ones.
## Phenotype convergence rules (v3.5.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/phenotype-convergence-rules.md` and execute it in full. Do not work from memory.

The 3 production phenotypes (`user-management` / `ai-management` / `config-management`) have implicit pairing + dependency relationships the dispatch points (`api-design-from-frontend` Stage A3, `visual-to-api-design` Stage 7, `data-engineering-exploration` Stage 3 + Stage 7) must consult; v3.5.0 codifies them.
## Test-run monitor discipline (v3.3.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/test-run-monitor-discipline.md` and execute it in full. Do not work from memory.

A passive observer team that watches when testing is happening and produces a per-run report. Strictly log-only: no mid-run interrupts, no auto-SR filing, no pipeline gating. The monitor team is the answer to *"I want to know what's going on across my test runs without paying attention to each one."*
## No end-of-run deferral discipline (v2.10.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-end-of-run-deferral-discipline.md` and execute it in full. Do not work from memory.

Agents MUST NOT end a run by cataloguing in-scope work as "Deferred" and bouncing the unfixed items back to the user as a "Want me to continue?" decision question. Every in-scope item discovered during the run has exactly one valid disposition by run-end: **(a)** fixed in this change, **(b)** routed via a solution requirement (the v1.7.0 `missing-api-for-frontend-element` or v2.8.0 `cross-layer-backend-required` / `cross-layer-frontend-required` origin kinds — or any other documented SR origin), OR **(c)** explicit confirmed-stub with a user-citation recorded in `coverage-map.json` `confirmed_stubs[]`. Anything else — particularly a clustered "I'd take them cluster-by-cluster (A → B → C → D), each gated + redeployed + Playwright-verified the same way" follow-up offer — is the failure mode this discipline closes.
## Multi-persona path-coverage discipline (v2.11.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/multi-persona-path-coverage-discipline.md` and execute it in full. Do not work from memory.

Features that serve more than one user persona (a client receiving an email invite; an attorney monitoring a dashboard; a title-agency assistant entering intake data on behalf of a client; a family member completing their own intake; etc.) MUST be tested from EVERY persona's path before any fix on the feature is claimed complete. Testing one persona's golden path and declaring the fix shipped — when the OTHER personas' views still don't render, still don't persist, or still don't sync — is the failure mode this discipline closes.
## Dynamic affordance discovery discipline (v2.13.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/dynamic-affordance-discovery-discipline.md` and execute it in full. Do not work from memory.

When the pipeline is given a codebase (either to review/audit or to build into), the intake phase MUST scan the codebase for **affordance signatures** — UI elements, libraries, and backend code paths that signal a user-facing capability (file upload, file download, real-time updates, notifications, etc.). Any affordance class that is **present in the code** but **not addressed in the run's requirements inventory** is a discipline failure: the run will silently leave the affordance unsupported and the user will hit it in production.
## UX-test environment sequencing discipline (v2.13.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/ux-test-environment-sequencing-discipline.md` and execute it in full. Do not work from memory.

UX tests MUST run in BOTH environments — **LOCAL first, LIVE DEV last** — in that order. The local pass is fast feedback (debugger, hot-reload, breakpoints); the live-dev pass is real-world verification (the deployed bundle, real env vars, the same URL the user hits). Running tests only locally silently never verifies the deployed code. Running tests only against the live dev URL loses the fast-feedback loop and burns deploy time per iteration.
## No implementation-time scope cut discipline (v2.14.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-implementation-time-scope-cut-discipline.md` and execute it in full. Do not work from memory.

When the user's prompt names a **full-build mandate** ("implement everything in full", "build the whole thing", "implement it all", "do everything"), agents MUST NOT unilaterally implement a foundation/scaffold subset and announce the cut as virtuous. The agent's final report cannot use "Honest scope statement" / ⚠️ + "scope statement" headers, cannot describe what was NOT built as "milestones M1–M7", cannot self-justify with "I stopped at the M_N boundary deliberately rather than half-land" framing, and cannot frame partial work as "shippable-and-true today" when the explicit mandate was full build.
## Prod-safe test classification discipline (v2.17.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/prod-safe-test-classification-discipline.md` and execute it in full. Do not work from memory.

Every Playwright and QA test MUST carry a top-of-file classification annotation — `@prod-safe` (only reads; safe to run against ANY deployed environment including production) or `@not-prod-safe` (contains mutations — POST/PUT/PATCH/DELETE, form submits, DB writes, file uploads, email sends, etc.). When a test run targets a production-labeled URL, ONLY `@prod-safe` tests may execute. Unclassified tests are a discipline failure; running `@not-prod-safe` tests against production is a critical safety failure.
## Codebase discipline registry (v2.18.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/codebase-discipline-registry.md` and execute it in full. Do not work from memory.

CT6 disciplines that mutate the target codebase (annotation insertion, fixture authoring, mock removal, persona inventory build) need a per-codebase **discipline registry** so the orchestrator knows whether each discipline has already been applied. When the orchestrator detects an un-applied discipline at pipeline start, the registry mechanism **auto-executes** the discipline's update routine before the user's actual run continues.
## In-flight clarification injection mechanism (v2.19.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/in-flight-clarification-injection-mechanism.md` and execute it in full. Do not work from memory.

The v2.5.0 in-flight clarification discipline above documents WHAT the orchestrator does when the user injects a mid-run message. v2.19.0 ships HOW the injection happens: a persistent per-run inbox JSONL, an explicit `/architect-team:inject <message>` slash command, a phase-boundary check protocol the orchestrator runs at every numbered phase, and a 17th Layer 3 tool that gates Phase 8 against any silently-ignored clarification.
## Deploy mandate discipline (v2.20.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/deploy-mandate-discipline.md` and execute it in full. Do not work from memory.

When the user's prompt contains an explicit **deploy verb** + **completeness modifier**, the orchestrator MUST treat the request as a **HARD MANDATE** with a single success criterion: every user-facing surface is hooked to live data from a real deployed backend at a real deployed URL the user can log into. Anything less is failure. The orchestrator MUST NOT:
## No proxy-element verification discipline (v2.21.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-proxy-element-verification-discipline.md` and execute it in full. Do not work from memory.

When a verification step cannot reach the target state OR cannot locate the target element, the agent MUST escalate. Substituting a nearby measurable element ("the screen-reader label in the coverage badge" instead of "the no-patients-monitored empty state") and reporting PASS off that proxy is a verification fraud. The rule: **the element being measured MUST be the SAME element named in the spec/test**. Not "a related element". Not "the closest measurable thing". The same element.
## No pipeline-bypass discipline (v2.22.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/no-pipeline-bypass-discipline.md` and execute it in full. Do not work from memory.

When the user invokes `/architect-team` (or any pipeline-driving slash command), the orchestrator MUST follow the pipeline. "Follow" means actually executing the multi-agent dispatch, the OpenSpec ceremony, the worktree isolation, the independent review gates, and the completion audit — NOT applying the methodology by hand because the orchestrator decided the prior session's mapping was sufficient.
## Exploration documentation standard (v3.2.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/exploration-documentation-standard.md` and execute it in full. Do not work from memory.

The Exploration Pipeline — the 7-stage extension of `visual-to-api-design` (Stage 0 scope-gate + the reused Stage 1/2/3/4 bodies + the net-new reusable-component-architecture Stage 3c + the API Stages 5/6 + the data-architecture Stage 7) — produces a fixed, named set of FIVE `*_MAP.md` documents under each project's `<codebase>/docs/` directory. These are the structured exploration artifacts the implementation pipeline (Phase 2-8 of architect-team) then builds against. This section is the canonical home of their names, paths, frontmatter, and bodies, so the producer skill body and any downstream consumer reference one schema rather than re-describing it.
## Unbounded solving discipline (v3.8.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/unbounded-solving-discipline.md` and execute it in full. Do not work from memory.

The dev-loop runs until **SUCCESS** and never halts on iteration count or oscillation. There is **NO iteration ceiling**. The pipeline never aborts because it has looped "too many" times, and it **never stops on incomplete work**. The only two things that ever interrupt the loop are (1) reaching success — every coverage-map requirement green, every gate passed, every solution requirement resolved — or (2) a deliberate pause to collect genuinely-required owner input the run cannot synthesize itself.
## Run continuity discipline (v3.30.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/run-continuity-discipline.md` and execute it in full. Do not work from memory.

The Unbounded solving discipline above says the loop never halts on incomplete work; run continuity is its ENFORCEMENT substrate plus the resume half: **once a pipeline run starts, it is driven through the pipeline to completion — across turn ends, context compactions, and session restarts — and the pipeline machinery stays mandatory until the run completes or the USER explicitly stands it down.** Two real-world failure modes taught it: (1) the orchestrator ending a turn mid-run with *"we've done a lot — say continue if you want me to keep going"* (an arbitrary checkpoint that silently converts an autonomous run into a babysat one), and (2) a resumed session "continuing" the run by hand without re-loading the pipeline skill, because the resume prompt ("continue") is not a pipeline command.
## Run metrics + success measurement (v3.8.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/run-metrics-and-success-measurement.md` and execute it in full. Do not work from memory.

Canonical home of the bug-fix run-metric discipline (REQ-CDL-02 / REQ-SAFE-02; `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` §6). The multi-phase upgrade MUST be justified by **measured** outcomes — without per-run metrics in a queryable location, before/after is noise. Each bug-fix run records the §6 metrics so the structured-bug-isolation reorder (and later the CDLG) can be proven to help.
## Uniform plugin usage (v3.9.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/uniform-plugin-usage.md` and execute it in full. Do not work from memory.

This is the single source of truth for HOW every CT6 pipeline invokes its orchestration and methodology dependencies — the native `ct6-converge` workflow (declared before, recorded after), the CONDITIONAL superpowers plugin with its native fallback (not a hard dependency since v4.0.0), and the OpenSpec CLI/skills. The point is **predictable behavior regardless of which pipeline runs**: the full (`architect-team-pipeline`), bug-fix (`bug-fix-pipeline`), mini (`mini-architect-team-pipeline`), and ux-test (`ux-test-builder`) bodies all reference THIS section rather than re-describing the invocation form locally, so a single edit propagates. A pipeline body MUST NOT re-spell these invocations inline.
## Layer 3 gate invocation table (v3.10.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/layer-3-gate-invocation-table.md` and execute it in full. Do not work from memory.

This is the single parameterized home for the Layer 3 / discipline gate invocations the pipeline bodies used to re-spell inline (the v2.18.0 / v2.19.0 / v2.20.0 / v3.0.0 polyglot `python3 … || python …` blocks). Each pipeline body references THIS table by gate name + cites the gate's per-phase placement; it does NOT re-spell the bash. Every invocation uses the detect-once polyglot form from `## Cross-platform Python invocation` and is **best-effort unless the gate's own discipline says it blocks** (the deploy-mandate and unilateral-override gates block; the discipline-registry and inflight checks are best-effort / non-gating).
## Appearance-change policy discipline (v3.14.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/appearance-change-policy-discipline.md` and execute it in full. Do not work from memory.

Agents MUST NOT make unsolicited changes to frontend APPEARANCE. When the user asks for an update, an improvement, or a fix, the mandate covers the named work — it does not authorize restyling, layout tweaks, new visible elements, or "polish" the user never asked for. Backend changes needed to deliver the mandate are unrestricted by this policy ("do what you need to on the backend"); what a user SEES changes only when the user asked for it, approved it, or explicitly granted free rein.
## Declared-gates discipline (v3.47.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/declared-gates-discipline.md` and execute it in full. Do not work from memory.

**A gate you name is a gate you record.** The moment the orchestrator states a condition that gates ship, deploy, merge, or completion — in a plan, in a phase decision, in a progress report, in user-facing prose ("we don't ship until the full Playwright suite passes against the live URL", "this merges after the type-check is clean") — it has made a promise the user is now relying on. An unrecorded gate is a claim, and an unverified claim about a gate is exactly what the rest of this stack forbids. Recording it costs one JSON append; forgetting it is how a run ships past its own stated bar and reports success.
## Spec currency discipline (mid-run) (v3.47.0)

> **STOP.** Before acting under this section, Read `skills/common-pipeline-conventions/references/spec-currency-discipline-mid-run.md` and execute it in full. Do not work from memory.

**The orchestrator owns spec currency WHILE agents read it.** `openspec/changes/<slug>/` is not a private drafting space once Phase 2 has dispatched — it is the contract several teammates are actively building against, and every edit to it silently re-points a document someone else already read. Two teammates implementing two readings of one amended line produce a defect no test names and no reviewer can attribute; the fix costs a phase, and the cause is invisible in every diff.
## Local -> dev -> test-on-dev is the pipeline's job, not the user's (v3.57.0)

> **STOP.** Before escalating a gate that needs a live environment, Read `skills/common-pipeline-conventions/references/local-dev-test-discipline.md` and execute it in full. Do not work from memory.

## Augment-never-replace discipline (v3.63.0)

> **STOP.** Before arming, dispatching, or gating on an optional third-party capability, Read `skills/common-pipeline-conventions/references/augment-never-replace.md` and execute it in full. Do not work from memory.

## Git commit identity discipline (v3.67.0)

> **STOP.** Before the first commit-authoring git command of a run (`commit` / `merge` / `revert`), Read `skills/common-pipeline-conventions/references/git-commit-identity.md` and execute it in full. Do not work from memory.

The rule: a run commits as the PERSON driving it, and the tool never decides who that is. The front door resolves it once per checkout (`hooks/git_identity.py resolve`): a recorded `<main-worktree>/.architect-team/git-identity.json` is used silently; a candidate from local/global git config is CONFIRMED with the user first; nothing found means the user is ASKED for name + email — a domain gate, never a hardcoded default, never the user's git config rewritten. Every commit-authoring command then carries the record explicitly (the `git_identity.py git --` wrapper or `-c user.name=… -c user.email=…`), and `pretool_skill_gate.py` Arm 4 refuses one that lacks or contradicts it during an active run (`CT6_GIT_IDENTITY_GATE_DISABLED` is the human's lever).

## Deletion discipline (v4.0.0)

> **STOP.** Before deleting, trashing or pruning any file, directory or run artifact, Read `skills/common-pipeline-conventions/references/deletion-discipline.md` and execute it in full. Do not work from memory.

Deletion is a decision about recoverability, and the agent does not make it from memory. Soft delete is the default — the `trash` verb of `hooks/deletion_guard.py` moves the content into the run's trash with a restore manifest — and a hard delete proceeds only when the guard's classifier (a PreToolUse hook on `Bash`) proves the content survives elsewhere: temp / gitignored / tracked-and-clean targets are allowed with the restore command, tracked-and-dirty / untracked / outside-a-repo / unparsable targets ASK, and the shared-state git operations are denied during an active run. `CT6_DELETION_GUARD_DISABLED` is the human's lever.

## Test selection discipline (v4.0.0)

> **STOP.** Before any phase runs a test suite, Read `skills/common-pipeline-conventions/references/test-selection.md` and select through `scripts/test_index/cli.py`. Do not run "the whole suite" from habit.

Every gate runs the tests SELECTED for its change set — Phase 3 per slice (`select --phase 3`), Phase 5 the selected integration tests plus the impacted flows (`select --phase 5`) — plus the human-owned pins (`.architect-team-deploy.json` `tests.always_run`) and every unknown-mapping test; the full suite runs ONCE, at Phase 8 before the merge (`select --phase 8` is not narrowable), which REVERSES the v3.65.0 "ENTIRE dev suite at Phase 5" rule on purpose. Every selection writes a `test-selection-<ts>.json` record the evidence file cites; an agent never lowers a pin. The B / M / D / U / P lanes apply the same three tiers at their own merge boundaries.

## Converge workflows (v4.0.0)

> **STOP.** Before running any "N reviewers loop until all ok" gate, Read `skills/common-pipeline-conventions/references/converge-workflows.md` and run the gate exactly as it says. Do not describe the loop in prose.

Every reviewer-convergence gate runs as DECLARE → `ct6-converge` workflow → RECORD: the gate `converge:<kind>` is declared into `declared-gates.json` first, `workflows/ct6-converge.js` dispatches N blind reviewers in parallel with one fixer per round and no self-imposed round cap, and the record script writes `.architect-team/converge/<kind>-<ts>.json` and satisfies the gate only when `converged` is true and the final round's `ok` count equals the reviewer count. The promise string is the gate's label, never the exit test; `ralph-loop` is retired. Reviewer counts follow `skills/team-spawning-and-review-gates/references/review-tiers.md` (three for a tier-3 gate, one paired reviewer for tier 2).

## Native methodology (v4.0.0)

> **STOP.** When a lane's pre-flight finds `superpowers` or `cartographer` absent, Read `skills/common-pipeline-conventions/references/native-methodology.md` and run the lane with the native forms. Never abort for a missing optional plugin.

`superpowers` and `cartographer` are CONDITIONAL plugins — preferred when installed, reported and remediated when absent, never gating. The lane records `methodology: native` and follows the chapter's native forms of brainstorming, test-driven development, systematic debugging, verification before completion and codebase mapping (a native map carries `source: native`); when a plugin is present the lane uses it.

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
- The five notifier events are an exclusive set. A pipeline body that needs a sixth event does NOT invent it inline — it adds the event to this skill's enumerated list first, then references the new event from the pipeline body.

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
