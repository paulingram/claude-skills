---
name: bug-fix-pipeline
description: "Use when a bug needs to be fixed end-to-end faster than the full architect-team-pipeline can deliver, but with the same rigor where it matters. A sibling orchestrator playbook whose Phases B−1 through B8 mirror the main pipeline's structural points but replace the Phase 2-5 parallel-team-spawn / 6-team-review with a tight replicate → reproduce-test → propose → fix → QA-replay loop. The body documents the five non-negotiable disciplines (replicate first, reproduction IS the regression test, generalized fix not symptom patch, QA replay against the live dev environment, live-dev-by-default with production opt-in). Accepts the same two input forms as the main /architect-team — a requirements folder OR a plain-language requirement typed directly as prose."
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

**superpowers is a CONDITIONAL plugin (v4.0.0; it was a hard dependency from v3.9.0 to v3.67.0).** A pre-flight check still runs as the very first action of this pipeline and resolves availability either way: (a) `~/.claude/plugins/installed_plugins.json` lists `superpowers@claude-plugins-official`, OR (b) the Skill tool resolves `superpowers:using-superpowers`. When it is present the lane uses the superpowers skills named below. When it is absent the lane does NOT abort: it prints one line naming the gap and the install remediation (`/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`), records `methodology: native` in `intake-state.json`, and runs the same disciplines in their native form per `skills/common-pipeline-conventions/references/native-methodology.md`. The same rule covers `cartographer` (native mapping fallback in that chapter) and the retired `ralph-loop`, whose job the `ct6-converge` workflow does (`skills/common-pipeline-conventions/references/converge-workflows.md`). The canonical source of truth is `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)`.

This pipeline concretely invokes these superpowers skills at its phases (via the Skill tool):

- `superpowers:brainstorming` — design / intake (Phase B3 proposal authoring, before drafting the fix design).
- `superpowers:test-driven-development` — implementation (Phase B2 reproduction-as-regression-test + Phase B5 implement, before writing the fix code).
- `superpowers:systematic-debugging` — RCA / diagnosis (Phase B1 replication + Phase B3 diagnostic-research-team, before proposing any fix).
- `superpowers:verification-before-completion` — review / completion gates (Phase B6 QA replay + Phase B7 archive, before claiming the bug resolved).

**Precedence.** User `CLAUDE.md` / `AGENTS.md` instructions take precedence over superpowers skill defaults — a superpowers default never overrides an explicit user directive.

## Five non-negotiable disciplines

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/five-non-negotiable-disciplines.md` and execute it in full. Do not work from memory.

1. **Replicate first.** Phase B1 reproduces the symptom — a Playwright user-flow for frontend bugs, a backend script for backend bugs — against the live dev environment, BEFORE any fix is proposed. A fix without a replication is a guess and gets rejected at the architect review (Phase B4).
2. **Reproduction IS the regression test.** The Playwright flow / backend script that demonstrated the bug becomes the test the QA replay verifies against post-fix. No "now write a test" second step. For frontend bugs the agent ALSO writes a **backend diagnostic test** so the regression is covered on both sides of the contract.
3. **Generalize, never symptom-patch.** The `system-architect` Bug-Fix Generalization Audit at Phase B4 rejects fixes that special-case the failing input — a literal user-id in a conditional, a hard-coded category name in a switch. The override is explicit: the user has to say *"hard-code it"* / *"hotfix this one"* / equivalent. Silence is NOT authorization.
4. **QA replay against live dev.** Phase B6 dispatches the `qa-replayer` against the deployed fix, re-running the original replication artifacts verbatim. The pass criterion is *"the originating symptom is gone end-to-end"* — not "the test passes," but the original failure mode is no longer reproducible — AND *"the code-path execution witness confirms the fix's buggy handler was actually invoked by the test"* (v0.9.31). A test that passes via a different code path (selector misidentification, precondition skip, sibling-handler entry) is the failure mode v0.9.31's witness exists to catch; the new verdict `test-did-not-exercise-fix` routes back to **Phase B2** (re-author the test) instead of B3 (re-propose the fix), because the FIX may be correct and the TEST may be wrong — separate axes, separate recovery paths.
5. **Live-dev-environment-by-default.** Phase B5 ALWAYS deploys the fix to the dev environment (per the target project's `design.md` `## Dev Environment` section) before Phase B6 testing. Builds confirmed green first. Choosing HOW to verify each claim along the way is the `verification-planning` skill's enumerate-and-choose step — the dev deploy is the default venue for the end-to-end confirmation, never a substitute for the cheapest faithful check a local run, a replay, or a seeded fixture settles first. Production is an explicit opt-in exception (`--environment production`) that escalates a structured question to the user.

## Inputs

`$REQ_DIR` (bound by `/architect-team:bug-fix` from the user's argument) is the **bug**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to the main `/architect-team`:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding bug-report artifacts, screenshots, prior diagnostic notes, or an OpenSpec brief.
2. **A plain-language requirement** — prose typed directly as the argument: a sentence or paragraph describing the symptom, the user's experience, expected vs. actual behavior. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — **do NOT refuse plain-language prose**, **do NOT treat the first word of a sentence as a path**, **do NOT ask the user for a folder when prose was given**. Ask only when `$REQ_DIR` is genuinely empty. The codebase the bug applies to is the cwd (a git repo) unless the prose explicitly names another path.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

**Flags the `/architect-team:bug-fix` command binds and this lane reads.** `--environment production` (B5 escalates before any production deploy), `--no-deploy` (B5 skips the dev deploy and B6b is skipped with a note in the report), `--force-bug` (B0 skips the classifier warning), `--proposal-first` (pause after B3), and — v4.0.0 — **`--full-data`**: sample-first iteration is OFF for the run. Absent the flag (the default), a data defect follows the stratified sample plan at B1 and B6 (`skills/data-eng-pipeline/references/sample-first.md`); with it, B1 replicates and B6 replays against the full table, no sample plan is produced or referenced, and the B7 report records the opt-out. A project principle that forbids sampling has the same effect and is named in the report.

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

When a run arms an optional third-party capability, the armed skill operates INSIDE this lane's mandates rather than in place of them — the rule itself, the skill-to-phase binding, the conflict record, and the narrow platform-safety carve-out all live in `common-pipeline-conventions` `## Augment-never-replace discipline (v3.63.0)`. Concretely for this lane: the arming verdict for the optional `bauplan` lakehouse capability is resolved at the top of Phase B−1, alongside the dispatch-mode and `appearance_mode` selections — a `bauplan_project.yml` anywhere in the target repo (`_has_bauplan_markers` in `hooks/discipline_registry.py`, recursive, so a monorepo subdirectory marker counts) arms it silently, while stated Bauplan intent with no marker surfaces exactly one confirmation owed BEFORE the first bauplan-specific dispatch — resolved through `resolve_bauplan_arming` in `scripts/bauplan/arming.py` and recorded as `{armed, signal, requires_confirmation, disposition}` at `<workspace>/.architect-team/bug-fix/<bug-slug>/bauplan-arming.json`. That confirmation joins this lane's domain gates above: it fires regardless of `--proposal-first`, because the user's answer determines what gets built. **Every Bauplan pointer in this body is gated on that verdict:** an unarmed run — the ordinary case — reads no Bauplan instruction at all, and B1 through B8 proceed exactly as they do today. An armed run whose `bauplan` plugin turns out to be absent warns and degrades (the generic path, with the missed capability and its remediation named in the B7 report); it never blocks.

## Notifications (per-project email events — opt-in, best-effort)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md` and execute it in full. Do not work from memory.

Per `common-pipeline-conventions` `## Notifications wiring convention`, this pipeline emits the ten recognized events (`run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, plus the tick-driven `heartbeat`) via the notifier CLI at `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`. The discipline is opt-in (gated on `.architect-team-notify.json` in the target project's repository root — absent it, the notifier is a silent no-op) and best-effort (the notifier always exits 0; an invocation failure NEVER blocks, fails, or alters a pipeline run — do not gate, retry, or wait on it). Every invocation uses the polyglot `python3 ... || python ...` form per `common-pipeline-conventions` `## Cross-platform Python invocation`.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` and execute it in full. Do not work from memory.

Per `common-pipeline-conventions` `## MemPalace wake-up precondition` (which points at the canonical rule in `mempalace-integration` `## Phase A — Wake-up at pipeline start`): when the bug-fix pipeline is invoked DIRECTLY via `/architect-team:bug-fix` (not routed in from the main pipeline's Phase −2), the unscoped wake-up runs as the earliest action of this pipeline — before any subagent dispatch, including the Phase B−1 intake-and-mapping flow. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback), then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. Include the wake-up output verbatim — the bug-fix loop benefits from prior-context recall (past bug-replications mined to `bug-replications`, past QA-replay verdicts mined to `qa-replays`, past architect generalization-audit verdicts mined to `bug-fix-audits`). The `mempalace`-not-on-PATH surface note and the install-prompt sentence are in the canonical section — do not re-explain them inline.

## Phase B0.1 — Discipline freshness check (v2.18.0)

Same shape as the main pipeline's Phase 0.1 — invoke `verify-discipline-registry-current` (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the Discipline-freshness row), auto-apply safe disciplines, route the rest as SRs. See `common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)`. Runs AFTER the MemPalace wake-up + entry-condition checks above and BEFORE Phase B−1. Best-effort — a failure of the verify-tool never blocks the bug-fix loop; surface a one-line note and proceed.

## Phase-boundary inbox check (v2.19.0)

Same shape as the main pipeline's `## Phase-boundary inbox check` — at the start of every numbered bug-fix phase (B−1 / B0 / B1 / B2 / B3 / B4 / B5 / B6 / B6b / B7 / B8) AND **after every background-dispatch return / wake** (v3.16.0 — dispatch teammates with `run_in_background: true` so the inbox drains promptly, not only at phase boundaries), read the in-flight inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` via `hooks.inflight_inbox.unprocessed_messages`, classify each new message per v2.5.0 (incl. `parallel-problem` → spawn a concurrent lane with a disjoint `hooks/locks.py` lock, recording `lane_id` via `mark_processed`), mark_processed. Phase B8 invokes the 17th Layer 3 tool `verify-inflight-clarifications-processed` to gate against silently-ignored messages (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the In-flight inbox row).

See `common-pipeline-conventions/SKILL.md` `## In-flight clarification injection mechanism (v2.19.0)` for the canonical home + `## In-flight clarification discipline (v2.5.0)` `### Parallel lanes (v3.16.0)` for the responsiveness + parallel-lane protocol.

## Phase B−1 — Intake & Mapping (REQUIRED, runs before Phase B0)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b-1.md` and execute it in full. Do not work from memory.

Follow the `intake-and-mapping` skill verbatim — same codebase discovery (read `$REQ_DIR/codebases.json` → frontmatter → cwd → ask user); same per-codebase `ct6-converge` workflow with cartographer + route-mapper + the tier-3 reviewer convergence (the `codebase-map` and `integration-map` presets, declared before and recorded after); same map-freshness rules (read `last_mapped` and compare against `git log -1 --format=%cI`; re-derive if stale or if `map_invalidated`); same integration mapping; same MemPalace wake-up + mining.

## Phase B0 — Detection & Normalization

Same as `architect-team-pipeline` Phase 0 — `plain` / `openspec` / `superpowers` classification, openspec init if needed, kebab `<bug-slug>` derived from the description.

For `plain` (the common case for a bug report), pick a `<bug-slug>` that names the symptom plainly: `fix-row-delete-button`, `fix-analysis-totals-zero`, `fix-login-redirect-loop`. Avoid generic names (`bugfix`, `quickfix`). The slug names the OpenSpec change AND the eventual feature branch.

The change-name convention: bug-fix changes get the same `architect-team/<bug-slug>` feature-branch pattern; the OpenSpec change lives at `openspec/changes/<bug-slug>/`.

## Phase B1 — Bug Replication

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b1.md` and execute it in full. Do not work from memory.

The Lead creates a `bug-replicator` task in the shared list (teams mode) OR dispatches the `bug-replicator` subagent (subagents mode), one per affected codebase (usually just one). Bracket the dispatch with the v3.34.0 dispatch-wait pair per `## Notifications` — emit `waiting_on_agents` (`--agents "bug-replicator-<codebase> — reproduce: <symptom one-liner>"`) as the dispatch goes out, and `agents_complete` (`--agents "bug-replicator-<codebase> — <verdict>"`) when every replicator has returned its verdict. Inputs to the agent:

## Structured bug-isolation (v3.8.0)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/structured-bug-isolation.md` and execute it in full. Do not work from memory.

Closes REQ-DIAG-01 / REQ-DIAG-02 / REQ-DIAG-05 (the P0 "quick wins" of the CT6 Lineage & Logical Bug-Isolation Upgrade — `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`). The historical failure: diagnosis discovered the relevant code path *while theorizing* — a deep-analysis subagent was dispatched before anyone had frozen the endpoint scope or established, with an executed call, whether the defect even lived on the API side. Cheap, decisive checks were skipped in favor of expensive reasoning. v3.8.0 inserts a **structured pre-diagnosis sequence** so the cheap checks always precede deep analysis.

## Phase B2 — Reproduction-artifact promotion + backend diagnostic

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b2.md` and execute it in full. Do not work from memory.

The replication artifact from B1 IS the regression test — this is `superpowers:test-driven-development` in its purest form (the failing test exists before the fix code is written, per `## Plugin prerequisites (v3.9.0)`). Move it to its permanent location in the target codebase's test directory if it isn't already there. The pair the QA replayer will run at B6:

## Phase B3 — OpenSpec proposal authoring

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b3.md` and execute it in full. Do not work from memory.

Author a slim OpenSpec change at `openspec/changes/<bug-slug>/`. Apply `superpowers:brainstorming` to settle the fix's design intent before drafting (per `## Plugin prerequisites (v3.9.0)`); when the root cause is unclear, the `diagnostic-research-team` dispatch carries `superpowers:systematic-debugging`. The artifact chain is the same as a feature change: `proposal.md`, `design.md`, `specs/<cap>/spec.md`, `tasks.md`, `coverage-map.json`. The proposal:

## Phase B4 — Bug-Fix Generalization Audit

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b4.md` and execute it in full. Do not work from memory.

The Lead creates a `system-architect` task in **Bug-Fix Generalization Audit** mode (teams mode) OR dispatches the `system-architect` subagent in that mode (subagents mode). Inputs:

## Phase B5 — Implement + deploy to dev

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b5.md` and execute it in full. Do not work from memory.

The Lead creates ONE focused fix-team task in the shared list (teams mode) OR dispatches ONE focused fix-team subagent (subagents mode) — a `frontend` or `backend` agent depending on layer; for `both`-layer bugs, the Lead sequences them or runs them in parallel with non-overlapping file scope per the main pipeline's Phase 2 rules — usually a bug fix is single-layer or has a clear primary. Brief includes:

## Phase B6 — QA replay against live dev

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b6.md` and execute it in full. Do not work from memory.

The QA replay is this pipeline's `superpowers:verification-before-completion` gate — evidence (the originating symptom is gone end-to-end against the live dev environment) before any claim that the bug is resolved, per `## Plugin prerequisites (v3.9.0)`.

## Phase B6b — Logical Sensibility Check (v0.9.29)

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b6b.md` and execute it in full. Do not work from memory.

After Phase B6 returns `bug-resolved` and BEFORE Phase B7's archive, the orchestrator runs a logical sensibility check on the impact set of the fix. Closes a real-world gap surfaced by user feedback:

## Phase B7 — Archive + Report

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b7.md` and execute it in full. Do not work from memory.

On `bug-resolved` at B6 (AND the v2.21.0 target-element gate passing):

## Phase B8 — Commit + push

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/phase-b8.md` and execute it in full. Do not work from memory.

As part of Phase B8, record the run's §6 success metrics via `hooks/run_metrics.record_run_metrics(workspace, run_id, metrics)` — `dev_loop_iterations`, `first_pass_fix`, `oscillation_count`, `bug_still_present_count`, `fix_regression_count`, `fe_api_verdict` (from `discriminant.json`), `layer_fixed`, the derived `wrong_layer`, and the REQ-DOC-06 `cdlg_edge_recall` / `cdlg_hallucination_rate` (None until the CDLG ships). The metrics land at `<workspace>/.architect-team/run-metrics/<run_id>.json` and are mined to MemPalace run-history. See `common-pipeline-conventions/SKILL.md` `## Run metrics + success measurement (v3.8.0)` for the canonical home + the frozen-bug-benchmark protocol.

## Operating rules (non-negotiable)

The bug-fix pipeline inherits every operating rule from `architect-team-pipeline`'s `## Operating rules (non-negotiable)` section — including the no-arbitrary-timers rule, the unbounded-solving discipline (no iteration ceiling; loop until resolved), the shared-state concurrency model, the required-input-marker discipline, the safety rules for the auto-commit step, and the documentation-currency gate. **Plus**:

- **Replicate before propose.** Phase B1 MUST return `reproduced` before B3 can run. A proposal authored on an un-reproduced bug is the failure mode this skill exists to prevent.
- **Reproduction is the regression test.** No "now write the test" second step. The replication artifact IS the test.
- **Frontend bugs MUST have a backend diagnostic.** Phase B2's backend-diagnostic mandate is non-negotiable for `frontend` and `both`-layer bug-fix runs. A regression that one layer catches and the other misses is the failure mode the dual artifact prevents.
- **Generalization is non-negotiable.** The Phase B4 audit's verdict gates B5. A `needs-generalization` or `needs-replacement` verdict returns the proposal to B3; the implementing team does NOT proceed until the architect's verdict is `pass`.
- **QA replay against live dev.** Phase B6 runs against the deployed dev environment, not against local code. The pass criterion is symptom-gone-end-to-end.
- **Production deploys escalate.** Phase B5 NEVER auto-deploys to production. The `--environment production` flag triggers an explicit user-confirmation question.
- **Unbounded solving (v3.8.0).** There is NO iteration bound or ceiling — the bug-fix loop runs until the symptom is gone end-to-end. Never abort on iteration count. On a recurring fix-regression, continue from a DIFFERENT angle (re-route through diagnostic-research, broaden scope, alternate strategy) and surface the recurrence loudly WITHOUT halting. The only interruptions are reaching resolution or pausing to collect required owner input (the required-input marker). Per `common-pipeline-conventions` `## Unbounded solving discipline`.
- **Don't silently narrow the prompt's scope (v1.4.0).** If the bug-fix pipeline's reading of the user's report is materially narrower than the prompt's literal meaning — particularly when the report contains a parity-implying verb (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) — surface the scope decision via `AskUserQuestion` BEFORE Phase B1 replication. The user's answer becomes the contract; silent reframing is the anti-pattern. Per `common-pipeline-conventions` `## Scope discipline`. Structurally the same shape as the v0.9.36 anti-deferral rule below, fired EARLIER in the timeline (intake instead of mid-run).
- **Teammates MUST NOT run destructive git operations (v1.6.0).** The bug-fix pipeline's `bug-replicator`, `backend`, `frontend`, `qa-replayer`, and `fix-sensibility-checker` teammates MUST NOT run `git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, or `git clean -f`. These manipulate state shared across teammates within the same run and caused the heirship-app-v2 reflog clobbering (concurrent stash + pop interleaving lost three of four teammates' work). For baseline verification, the orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` at the bug-fix Phase B−1 entry and includes it in every teammate's spawn brief; teammates run `git diff $BASELINE_SHA -- <my-files>` instead of stashing. Per `common-pipeline-conventions` `## Teammate git discipline`.
- **Fix every bug you identify — never defer to "separate runs" (v0.9.36).** When the pipeline identifies multiple bugs (from replication, from QA replay, from sensibility checks, or from the user's description listing several symptoms), it fixes ALL of them in the current run. The orchestrator does NOT cluster bugs and then decide some clusters "merit a focused `/architect-team:bug-fix` run" or "would suffer in depth if batched here." That is the pipeline refusing to do its job. If the user listed 5 bugs, fix 5 bugs. If QA replay surfaces a regression, fix it in-loop (that is what the B6→B3 cycle exists for). If sensibility checks find 3 broken pages, those become SRs that resolve in-run. The ONLY legitimate deferral is an explicit user instruction ("skip this one for now", "don't fix cluster D") — silence is NOT deferral authorization.
- **Testing must be EXECUTED, not described (v0.9.36).** The B1 replication artifact must be actually run against the live dev environment with its output captured. The B6 QA replay must actually re-run the artifacts against the deployed fix. "The test would pass" / "the fix addresses the root cause so the test should pass" / "I verified by reading the code" are NOT testing — they are guessing. The verdict files at `.architect-team/bug-fix/<bug-slug>/` are the structural proof; the `pipeline-completion-audit` hook blocks without them.

## Anti-patterns to reject

> **STOP.** Before acting under this section, Read `skills/bug-fix-pipeline/references/anti-patterns-to-reject.md` and execute it in full. Do not work from memory.

## Relationship to other skills

- `architect-team-pipeline` (sibling) — same orchestration discipline, different shape. Bug-fix pipeline is reached via `/architect-team:bug-fix` (explicit) or via the main pipeline's Phase −2 triage when the classifier returns `bug` (or in parallel for `mixed`).
- `intake-and-mapping` (Phase B−1) — reused verbatim. Same maps, same freshness rules.
- `playwright-user-flows` (Phase B1 frontend, B6 QA replay) — the bug-replicator drives Playwright per this skill; the QA replayer re-runs it the same way.
- `dev-api-integration-testing` (Phase B1 backend, B2 backend diagnostic, B6 QA replay) — same.
- `root-cause-test-failures` — applies when B1 returns `could-not-reproduce` or when B6 returns an unclear `bug-still-present` (the diagnostic loop runs through the orchestrator's normal channels).
- `coverage-mapping` + `reuse-first-design` (Phase B3) — same authoring disciplines as a feature proposal.
- `documentation-currency` (Phase B8) — the doc-currency gate runs before the auto-commit, same as the main pipeline. v0.9.23 promoted the update step to the dedicated `doc-updater` agent; the audit (system-architect Documentation Currency Audit mode) and the commit-blocking enforcement are unchanged.

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
