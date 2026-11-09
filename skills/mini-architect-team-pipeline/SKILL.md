---
name: mini-architect-team-pipeline
description: Use when a feature change (5 or fewer acceptance criteria) needs driving end-to-end faster than /architect-team, auto-merge to main on green QA. M0-M8 -- one system-architect, two cross-reviewing devs, one mini-qa agent running unit, integration and 1-3 Playwright flows on live dev; red hands off to the full lane.
user-invocable: false
---

# mini-architect-team-pipeline

The `/architect-team` pipeline is correct-by-construction at 8 phases, 39 agents, and tier-3 reviewer convergence at its map, architecture and master-review gates (`skills/team-spawning-and-review-gates/references/review-tiers.md`). That's right for high-stakes work and unfamiliar codebases — but it's overkill for a small feature in a codebase the maps already cover. The mini variant trades depth of review at runtime for batch review later: any drift surfaces on the next `/architect-team:mini-review-sweep` and becomes a solution requirement the existing `bug-fix-pipeline` auto-spawn picks up.

You are the **Team Lead** for the mini variant. Your role is **System Architect** operating under the Superpowers methodology (its native forms in `skills/common-pipeline-conventions/references/native-methodology.md` when that CONDITIONAL plugin is absent). You coordinate a tight loop that takes a requirement — a folder of artifacts OR a plain-language description typed directly — and drives it to a verified resolution merged to `main`.

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

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/plugin-prerequisites.md` and execute it in full. Do not work from memory.

`superpowers` and `cartographer` are CONDITIONAL plugins: the pre-flight check runs first and resolves availability, and an absent plugin degrades to the native forms in `skills/common-pipeline-conventions/references/native-methodology.md` instead of aborting the run.

## Inputs

`$REQ_DIR` (bound by `/architect-team:mini` from the user's argument) is the **requirement**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to the main `/architect-team`:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding requirement artifacts, screenshots, prior notes, or an OpenSpec brief.
2. **A plain-language requirement** — prose typed directly as the argument. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — **never refuse plain-language prose**, **do NOT treat the first word of a sentence as a path**, **do NOT ask the user for a folder when prose was given**. Ask only when `$REQ_DIR` is genuinely empty. The codebase the requirement applies to is the cwd (a git repo) unless the prose explicitly names another path.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

## Dispatch mode

Per `common-pipeline-conventions` `## Dispatch mode (v1.0.0)`, the selection (env `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` + `claude --version >= 2.1.32` + `--no-teams` flag, also readable from `~/.claude/settings.json`) is computed ONCE — for the mini pipeline, at the top of Phase M0 — and persisted as `dispatch_mode: "teams"` or `dispatch_mode: "subagents"` to `<workspace>/.architect-team/intake-state.json` (the mini pipeline shares the main pipeline's `intake-state.json` location); every later phase reads it to branch between teams mode and subagents mode. The primitives of each mode and the hook branching are spelled out in the canonical section — do not re-explain them inline.

**Mini-specific behavior.** In teams mode the mini variant runs four named teammates — `architect`, `backend-dev`, `frontend-dev`, `mini-qa` — and uses `SendMessage` specifically for the M4 cross-review (each dev sends its `self_review` evidence to the other for the `independent_review` block). In subagents mode the M4 backend + frontend parallel dispatch is the canonical batched-parallel pattern — a single Agent-tool call carrying both invocations. Wherever this skill body says *"the Lead creates a `<role>` task (teams mode) OR dispatches the `<role>` subagent (subagents mode)"*, the branch is decided by `dispatch_mode`; both halves of the sentence are real, the orchestrator picks one at execution time. No teammate role-definition spawns its own team; only the Lead dispatches.

## Appearance-change policy (v3.14.0)

The mini pipeline honors the same appearance constraint as the full pipeline: `appearance_mode` (`strict` DEFAULT / `propose` / `innovate`, from the `--appearance` flag or its natural-language equivalents) is bound at the top of Phase M0 into `intake-state.json` and carried in both dev briefs. Under `strict`, the devs make NO appearance-affecting change beyond the bundle's explicit acceptance criteria (plus spec restoration and the mandated-capability minimum); improvement ideas are recorded to `<workspace>/.architect-team/appearance-proposals/<run-id>.json` (status `recorded`) and listed read-only in the M7 report — imperative, never interrogative. The M4 cross-review and the mini-qa pass check that every visual delta in the diff traces to a mandate. Canonical home: `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`.

## Notifications (per-project email events — opt-in, best-effort)

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md` and execute it in full. Do not work from memory.

The mini pipeline emits the ten recognized notifier events via `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`, opt-in on `.architect-team-notify.json` and strictly best-effort.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` and execute it in full. Do not work from memory.

The unscoped `mempalace wake-up` runs as the earliest action of Phase M0, before any subagent dispatch, and run artifacts are persisted to the palace as the run progresses.

## What this skill does NOT do

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/what-this-skill-does-not-do.md` and execute it in full. Do not work from memory.

The mini variant drops the proposal-refiner loop, Phase -2 triage, tier-3 convergence (except the M1 integration-map refresh), `task-reviewer`, `test-completeness-verifier`, runtime visual / editability / interaction reviewers, `reconciler` and the producer/checker doc split; `/architect-team:mini-review-sweep` catches drift later.

## Phase M0.1 — Discipline freshness check (v2.18.0)

Same shape as the main pipeline's Phase 0.1 — invoke `verify-discipline-registry-current` (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the Discipline-freshness row), auto-apply safe disciplines, route the rest as SRs. See `common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)`. Runs AFTER the MemPalace wake-up and BEFORE Phase M0 intake. Best-effort — a failure of the verify-tool never blocks the mini loop; surface a one-line note and proceed.

## Phase-boundary inbox check (v2.19.0)

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-boundary-inbox-check.md` and execute it in full. Do not work from memory.

At the start of every mini phase AND after every background-dispatch return, read the in-flight inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` and process every new message before proceeding.

## Phase M0 — Intake

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m0.md` and execute it in full. Do not work from memory.

Detect the input form per `## Inputs` and resolve `$REQ_DIR` into the run's intake state.

## Phase M1 — Maps freshness check

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m1.md` and execute it in full. Do not work from memory.

The mini variant uses cached maps wherever possible, re-deriving per `intake-and-mapping` only when a map is stale.

## Phase M2 — Architect drafts the 5-artifact OpenSpec bundle

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m2.md` and execute it in full. Do not work from memory.

A single `system-architect` drafts the full 5-artifact OpenSpec bundle at `openspec/changes/<slug>/` in one pass, including the mandatory `## QA Guidance` section of `proposal.md`, whose contract follows:

## QA Guidance

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/qa-guidance.md` and execute it in full. Do not work from memory.

`coverage-map.json` mirrors the section as a top-level `qa_guidance` block; the validator is the structural check and M3's self-confirm pass MUST detect and repair a malformed contract.

## Phase M3 — Architect self-confirm loop

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m3.md` and execute it in full. Do not work from memory.

The same architect re-reads its own bundle against the source requirements and the cached maps and asks whether the bundle still makes sense, iterating to a fixed point.

## Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m4.md` and execute it in full. Do not work from memory.

Contract-first parallelism (v3.48.0) runs before the dispatch when the frontend must visualize a new backend surface; then the backend and frontend devs implement in parallel with non-overlapping file scope and cross-review each other at review tier 2.

## Phase M5 — mini-qa runs unit + integration + narrow Playwright

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m5.md` and execute it in full. Do not work from memory.

The Lead dispatches one `mini-qa` agent to run the selected unit + integration suites and 1-3 narrow Playwright flows against the live dev URL.

## Phase M6 — Verdict gate

Read `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json`:

- `verdict: green` → proceed to **Phase M7** (auto-merge).
- `verdict: red-with-evidence` → proceed to **Phase M8** (re-eval loop; increment cycle counter).
- `verdict: env-failure` → halt. Write `.architect-team/mini/<slug>/env-failure.md` summarizing the env issue and surface to user. Do NOT increment the M8 cycle counter — env failures are not the fix's fault.

## Phase M7 — Auto-merge to main

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m7.md` and execute it in full. Do not work from memory.

On green QA: run the mock-retirement gate (when M4 created a contract), the full suite once, the single-pass doc-currency update, then commit as the recorded identity and auto-merge to `main`.

## Phase M8 — Re-evaluation loop and escalation

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m8.md` and execute it in full. Do not work from memory.

On `verdict: red-with-evidence`, the Lead increments the cycle counter and has the architect re-evaluate the bundle against the verdict; recurrence hands the work off to the full `/architect-team` pipeline as a continuation, never a give-up.

## Operating rules (non-negotiable)

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/operating-rules.md` and execute it in full. Do not work from memory.

The mini pipeline inherits the cross-cutting disciplines of `common-pipeline-conventions` and adds its own: never narrow the prompt's scope silently, reframing is not a clarifying question, no destructive teammate git, unbounded solving with hand-off to the full pipeline on recurrence.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Notifications (per-project email events — opt-in, best-effort)` | `skills/mini-architect-team-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md` | on demand |
| `MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)` | `skills/mini-architect-team-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` | on demand |
| `What this skill does NOT do` | `skills/mini-architect-team-pipeline/references/what-this-skill-does-not-do.md` | on demand |
| `Phase M0 — Intake` | `skills/mini-architect-team-pipeline/references/phase-m0.md` | on demand |
| `Phase M1 — Maps freshness check` | `skills/mini-architect-team-pipeline/references/phase-m1.md` | on demand |
| `QA Guidance` | `skills/mini-architect-team-pipeline/references/qa-guidance.md` | on demand |
| `Phase M3 — Architect self-confirm loop` | `skills/mini-architect-team-pipeline/references/phase-m3.md` | on demand |
| `Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)` | `skills/mini-architect-team-pipeline/references/phase-m4.md` | on demand |
| `Phase M5 — mini-qa runs unit + integration + narrow Playwright` | `skills/mini-architect-team-pipeline/references/phase-m5.md` | on demand |
| `Phase M7 — Auto-merge to main` | `skills/mini-architect-team-pipeline/references/phase-m7.md` | on demand |
| `Phase M8 — Re-evaluation loop and escalation` | `skills/mini-architect-team-pipeline/references/phase-m8.md` | on demand |
| `Plugin prerequisites (v3.9.0)` | `skills/mini-architect-team-pipeline/references/plugin-prerequisites.md` | on demand |
| `Phase-boundary inbox check (v2.19.0)` | `skills/mini-architect-team-pipeline/references/phase-boundary-inbox-check.md` | on demand |
| `Phase M2 — Architect drafts the 5-artifact OpenSpec bundle` | `skills/mini-architect-team-pipeline/references/phase-m2.md` | on demand |
| `Operating rules (non-negotiable)` | `skills/mini-architect-team-pipeline/references/operating-rules.md` | on demand |
