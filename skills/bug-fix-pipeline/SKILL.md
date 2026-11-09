---
name: bug-fix-pipeline
description: Use when a bug needs fixing end-to-end faster than the full architect-team-pipeline, with the same rigor where it matters. Sibling lane, Phases B-1 to B8 -- replicate, reproduce-test, propose, fix, QA-replay against live dev (production opt-in). Takes a requirements folder or plain prose like /architect-team.
user-invocable: false
---

# bug-fix-pipeline

The `architect-team-pipeline` is excellent for greenfield features and substantial new capability work. For a known-bug-with-a-clear-symptom — *"the row-action menu's Delete button doesn't actually delete; clicking it just closes the menu"* — its 100%-coverage planning gate, parallel team spawn, six Phase 5 review teams, and master-review audit are weight a 30-line fix doesn't need. The `bug-fix-pipeline` keeps the discipline that matters (maps must be fresh; the proposal must be real; the fix must be generalized; testing must be against the live system) and replaces what doesn't apply to a bug fix with the discipline specific to one.

You are the **Team Lead** for the bug-fix variant. Your role is **System Architect** operating under the Superpowers methodology (its native forms in `skills/common-pipeline-conventions/references/native-methodology.md` when that CONDITIONAL plugin is absent). You coordinate a tight loop that takes a bug — a folder of artifacts OR a plain-language description typed directly — and drives it to a verified resolution against the live dev environment.

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

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/plugin-prerequisites.md` and execute it in full. Do not work from memory.

`superpowers` and `cartographer` are CONDITIONAL plugins: the pre-flight check runs first and resolves availability, and an absent plugin degrades to the native forms in `skills/common-pipeline-conventions/references/native-methodology.md` instead of aborting the run.

## Five non-negotiable disciplines

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/five-non-negotiable-disciplines.md` and execute it in full. Do not work from memory.

Replicate first; the reproduction IS the regression test; generalize, never symptom-patch; QA replay against live dev; live-dev-by-default with production as an explicit opt-in.

## Inputs

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/inputs.md` and execute it in full. Do not work from memory.

`$REQ_DIR` is the bug in ONE of two first-class forms -- a requirements folder OR plain-language prose -- and prose is never refused, never read as a path, and never traded for a folder; the chapter also names the flags this lane reads.

## Dispatch mode

Per `common-pipeline-conventions` `## Dispatch mode (v1.0.0)`, the selection (env `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` + `claude --version >= 2.1.32` + `--no-teams` flag, also readable from `~/.claude/settings.json`) is computed ONCE — for the bug-fix pipeline, at the top of Phase B−1 — and persisted as `dispatch_mode: "teams"` or `dispatch_mode: "subagents"` to `<workspace>/.architect-team/intake-state.json` (the bug-fix pipeline reuses the main pipeline's `intake-state.json`); every later phase reads it to branch between teams mode and subagents mode. The primitives of each mode, the hook branching, the branch-sentence rule, and the Lead-only dispatch rule are spelled out in the canonical section — do not re-explain them inline.

## Default mode of operation

Same as `architect-team-pipeline` v0.9.20: **drive end-to-end, gates are opt-in for *process* gates, fire for *domain* gates** (per the v0.9.21 carve-out). The bug-fix pipeline's domain gates — fire regardless of `--proposal-first`:

- **Phase B1 ambiguity-escalation question** — when the bug description is genuinely incomplete (no screen named, no steps named, no expected-vs-actual). The agent does NOT guess; it asks. This is part of the deliverable.
- **`needs-clarification` verdict in any phase** — a structured ask to the user is the right move when the work cannot proceed responsibly.
- **`--environment production` escalation** — production deploys are user decisions.

Process gates (proposal-first pause, "do you want me to proceed?", obvious-answer clarifying questions) follow the same opt-in rule as the main pipeline.

## Appearance-change policy (v3.14.0)

A bug-fix run is `strict` by nature: the mandate is the named symptom, and restoring the intended behavior/appearance the bug broke (spec restoration) is in scope — restyling beyond it is not. The fix MUST NOT bundle visual "polish", layout tweaks, or new UI surface the bug report never named; improvement ideas surfaced during the fix are recorded to `<workspace>/.architect-team/appearance-proposals/<run-id>.json` (status `recorded`) and listed read-only in the Phase B7 report — imperative, never interrogative. The `--appearance` flag can widen a run explicitly (`propose` / `innovate`); `appearance_mode` is bound at the top of Phase B−1 into `intake-state.json` alongside the dispatch-mode selection and carried in every spawn brief. Canonical home: `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`.

## Augment-never-replace precedence (v3.63.0)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/augment-never-replace-precedence.md` and execute it in full. Do not work from memory.

When a run arms an optional third-party capability (Bauplan is the first), the armed skill operates INSIDE this lane's mandates; the arming verdict is resolved at the top of Phase B-1 and an unarmed run reads no Bauplan instruction at all.

## Notifications (per-project email events — opt-in, best-effort)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md` and execute it in full. Do not work from memory.

This pipeline emits the ten recognized notifier events via `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`, opt-in on `.architect-team-notify.json` and strictly best-effort.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` and execute it in full. Do not work from memory.

When invoked DIRECTLY via `/architect-team:bug-fix`, the unscoped `mempalace wake-up` runs as the earliest action of this pipeline, before any subagent dispatch, and its output is kept verbatim.

## Phase B0.1 — Discipline freshness check (v2.18.0)

Same shape as the main pipeline's Phase 0.1 — invoke `verify-discipline-registry-current` (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the Discipline-freshness row), auto-apply safe disciplines, route the rest as SRs. See `common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)`. Runs AFTER the MemPalace wake-up + entry-condition checks above and BEFORE Phase B−1. Best-effort — a failure of the verify-tool never blocks the bug-fix loop; surface a one-line note and proceed.

## Phase-boundary inbox check (v2.19.0)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-boundary-inbox-check.md` and execute it in full. Do not work from memory.

At the start of every bug-fix phase AND after every background-dispatch return, read the in-flight inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` and process every new message before proceeding.

## Phase B−1 — Intake & Mapping (REQUIRED, runs before Phase B0)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b-1.md` and execute it in full. Do not work from memory.

Follow the `intake-and-mapping` skill verbatim: the same codebase discovery, the same tier-3 `ct6-converge` map convergence (declared before, recorded after), the same freshness rules, the same MemPalace wake-up + mining.

## Phase B0 — Detection & Normalization

Same as `architect-team-pipeline` Phase 0 — `plain` / `openspec` / `superpowers` classification, openspec init if needed, kebab `<bug-slug>` derived from the description.

For `plain` (the common case for a bug report), pick a `<bug-slug>` that names the symptom plainly: `fix-row-delete-button`, `fix-analysis-totals-zero`, `fix-login-redirect-loop`. Avoid generic names (`bugfix`, `quickfix`). The slug names the OpenSpec change AND the eventual feature branch.

The change-name convention: bug-fix changes get the same `architect-team/<bug-slug>` feature-branch pattern; the OpenSpec change lives at `openspec/changes/<bug-slug>/`.

## Phase B1 — Bug Replication

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b1.md` and execute it in full. Do not work from memory.

The Lead dispatches one `bug-replicator` per affected codebase, bracketed by the dispatch-wait notification pair, to reproduce the symptom against the live dev environment.

## Structured bug-isolation (v3.8.0)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/structured-bug-isolation.md` and execute it in full. Do not work from memory.

A structured pre-diagnosis sequence makes the cheap, decisive checks (frozen endpoint scope, an executed discriminant call) precede any deep analysis (REQ-DIAG-01 / 02 / 05).

## Phase B2 — Reproduction-artifact promotion + backend diagnostic

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b2.md` and execute it in full. Do not work from memory.

The B1 replication artifact IS the regression test: promote it to its permanent location and pair it with the backend diagnostic the QA replayer runs at B6.

## Phase B3 — OpenSpec proposal authoring

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b3.md` and execute it in full. Do not work from memory.

Author a slim OpenSpec change at `openspec/changes/<bug-slug>/` with the same artifact chain as a feature change, grounded in the replication and the root cause.

## Phase B4 — Bug-Fix Generalization Audit

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b4.md` and execute it in full. Do not work from memory.

The `system-architect` runs the Bug-Fix Generalization Audit on the proposal; its verdict gates B5.

## Phase B5 — Implement + deploy to dev

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b5.md` and execute it in full. Do not work from memory.

ONE focused fix-team agent implements the fix, runs the selected tests, and deploys to the dev environment before B6.

## Phase B6 — QA replay against live dev

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b6.md` and execute it in full. Do not work from memory.

The `qa-replayer` re-runs the replication artifacts verbatim against the deployed dev fix; only symptom-gone-end-to-end plus the code-path execution witness closes the loop.

## Phase B6b — Logical Sensibility Check (v0.9.29)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b6b.md` and execute it in full. Do not work from memory.

After `bug-resolved` and BEFORE B7 archives, the orchestrator runs a logical sensibility check on the fix's impact set.

## Phase B7 — Archive + Report

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b7.md` and execute it in full. Do not work from memory.

On `bug-resolved` at B6 (and the target-element gate passing), archive the change and report.

## Phase B8 — Commit + push

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b8.md` and execute it in full. Do not work from memory.

Phase B8 runs the full suite once, commits as the checkout's recorded identity, records the run's success metrics, pushes, and auto-merges a clean branch.

## Operating rules (non-negotiable)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/operating-rules.md` and execute it in full. Do not work from memory.

The bug-fix pipeline inherits every operating rule of `architect-team-pipeline` and adds its own: replicate before propose, reproduction is the regression test, generalize, QA replay against live dev, production escalates, unbounded solving, fix every bug found, execute every test.

## Anti-patterns to reject

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/anti-patterns-to-reject.md` and execute it in full. Do not work from memory.

## Relationship to other skills

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/relationship-to-other-skills.md` and execute it in full. Do not work from memory.

This lane reuses `intake-and-mapping`, `playwright-user-flows`, `dev-api-integration-testing`, `root-cause-test-failures`, `coverage-mapping` + `reuse-first-design` and `documentation-currency` at the phases the chapter names.

## Same input forms as architect-team-pipeline

This skill's input rules are IDENTICAL to `architect-team-pipeline`'s. The v0.9.17 same-input-forms rules apply verbatim:

- **Folder OR plain-language prose, both first-class.** Either form is a valid invocation.
- **Never refuse plain-language prose.** A sentence describing a bug is a fully-supported input. Do NOT tell the user the skill "needs a folder."
- **Never treat the first word of a sentence as a path.** `no`, `the`, `fix`, `delete`, `clicking` are not directories — the entire sentence is the requirement.
- **Ask only when input is genuinely empty.** Then ask: *"What bug should the bug-fix pipeline replicate and resolve?"* — NOT *"give me a requirements folder."*

When the input is plain-language prose, the codebase the bug applies to is the cwd (a git repo) unless the prose explicitly names another path.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Five non-negotiable disciplines` | `skills/bug-fix-pipeline/references/five-non-negotiable-disciplines.md` | on demand |
| `Augment-never-replace precedence (v3.63.0)` | `skills/bug-fix-pipeline/references/augment-never-replace-precedence.md` | on demand |
| `Notifications (per-project email events — opt-in, best-effort)` | `skills/bug-fix-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md` | on demand |
| `MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)` | `skills/bug-fix-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` | on demand |
| `Phase B−1 — Intake & Mapping (REQUIRED, runs before Phase B0)` | `skills/bug-fix-pipeline/references/phase-b-1.md` | on demand |
| `Phase B1 — Bug Replication` | `skills/bug-fix-pipeline/references/phase-b1.md` | on demand |
| `Structured bug-isolation (v3.8.0)` | `skills/bug-fix-pipeline/references/structured-bug-isolation.md` | on demand |
| `Phase B2 — Reproduction-artifact promotion + backend diagnostic` | `skills/bug-fix-pipeline/references/phase-b2.md` | on demand |
| `Phase B3 — OpenSpec proposal authoring` | `skills/bug-fix-pipeline/references/phase-b3.md` | on demand |
| `Phase B4 — Bug-Fix Generalization Audit` | `skills/bug-fix-pipeline/references/phase-b4.md` | on demand |
| `Phase B5 — Implement + deploy to dev` | `skills/bug-fix-pipeline/references/phase-b5.md` | on demand |
| `Phase B6 — QA replay against live dev` | `skills/bug-fix-pipeline/references/phase-b6.md` | on demand |
| `Phase B6b — Logical Sensibility Check (v0.9.29)` | `skills/bug-fix-pipeline/references/phase-b6b.md` | on demand |
| `Phase B7 — Archive + Report` | `skills/bug-fix-pipeline/references/phase-b7.md` | on demand |
| `Phase B8 — Commit + push` | `skills/bug-fix-pipeline/references/phase-b8.md` | on demand |
| `Anti-patterns to reject` | `skills/bug-fix-pipeline/references/anti-patterns-to-reject.md` | on demand |
| `Plugin prerequisites (v3.9.0)` | `skills/bug-fix-pipeline/references/plugin-prerequisites.md` | on demand |
| `Inputs` | `skills/bug-fix-pipeline/references/inputs.md` | on demand |
| `Phase-boundary inbox check (v2.19.0)` | `skills/bug-fix-pipeline/references/phase-boundary-inbox-check.md` | on demand |
| `Operating rules (non-negotiable)` | `skills/bug-fix-pipeline/references/operating-rules.md` | on demand |
| `Relationship to other skills` | `skills/bug-fix-pipeline/references/relationship-to-other-skills.md` | on demand |
