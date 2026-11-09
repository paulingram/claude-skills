---
name: mini-architect-team-pipeline
description: "Use when a small-to-medium feature change (≤5 acceptance criteria) needs to be driven end-to-end faster than the full /architect-team can deliver, but with auto-merge to main on green QA. A sibling orchestrator playbook to architect-team-pipeline and bug-fix-pipeline; speed comes from dropping phases and parallel-review fan-out, not a weaker model. The body documents the M0-M8 phases: a single system-architect drafts the 5-artifact OpenSpec bundle with a mandatory ## QA Guidance section, two devs implement in parallel and cross-review each other, and one mini-qa agent runs unit + integration + 1-3 narrow Playwright flows against the live dev URL. On green it auto-merges to main with a Mini-Run: <slug> trailer; on persistent red it hands the work off to the unbounded full /architect-team pipeline as a continuation (no give-up cap). Accepts the same two input forms as /architect-team — a requirements folder OR plain-language prose."
user-invocable: false
---

# mini-architect-team-pipeline

The `/architect-team` pipeline is correct-by-construction at 8 phases, 26 agents, and ×3 reviewer convergence at multiple points. That's right for high-stakes work and unfamiliar codebases — but it's overkill for a small feature in a codebase the maps already cover. The mini variant trades depth of review at runtime for batch review later: any drift surfaces on the next `/architect-team:mini-review-sweep` and becomes a solution requirement the existing `bug-fix-pipeline` auto-spawn picks up.

You are the **Team Lead** for the mini variant. Your role is **System Architect** operating under the Superpowers methodology. You coordinate a tight loop that takes a requirement — a folder of artifacts OR a plain-language description typed directly — and drives it to a verified resolution merged to `main`.

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

- `superpowers:brainstorming` — design / intake (Phase M2 architect drafts the bundle, before authoring specs).
- `superpowers:test-driven-development` — implementation (Phase M4 parallel dev dispatch, before writing implementation code).
- `superpowers:systematic-debugging` — RCA / diagnosis (Phase M5 mini-qa red verdict + Phase M8 re-evaluation, before proposing any fix).
- `superpowers:verification-before-completion` — review / completion gates (Phase M6 verdict gate + Phase M7 auto-merge, before claiming the change ready for main).

**Precedence.** User `CLAUDE.md` / `AGENTS.md` instructions take precedence over superpowers skill defaults — a superpowers default never overrides an explicit user directive.

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

Per `common-pipeline-conventions` `## Notifications wiring convention`, the mini pipeline emits the ten recognized events (`run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, plus the tick-driven `heartbeat`) via the notifier CLI at `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`. The discipline is opt-in (gated on `.architect-team-notify.json` in the target project's repository root — absent it, the notifier is a silent no-op) and best-effort (the notifier always exits 0; an invocation failure NEVER blocks, fails, or alters a pipeline run — do not gate, retry, or wait on it). Every invocation uses the polyglot `python3 ... || python ...` form per `common-pipeline-conventions` `## Cross-platform Python invocation`.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` and execute it in full. Do not work from memory.

Per `common-pipeline-conventions` `## MemPalace wake-up precondition` (which points at the canonical rule in `mempalace-integration` `## Phase A — Wake-up at pipeline start`): the unscoped wake-up runs as the earliest action of Phase M0 — before any subagent dispatch. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback), then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. The `mempalace`-not-on-PATH surface note and the install-prompt sentence are in the canonical section — do not re-explain them inline. Per `mempalace-integration`, persist run artifacts (the OpenSpec bundle, the QA verdicts, the architect's M3 diffs) as the run progresses.

## What this skill does NOT do

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/what-this-skill-does-not-do.md` and execute it in full. Do not work from memory.

- **No proposal-refiner Q&A loop** — the architect grounds prose directly. If ambiguous, the architect surfaces ONE clarification batch before drafting; no iterative grading loop.
- **No Phase −2 bug-classifier triage** — feature work is assumed. (Bug fixes use `/architect-team:bug-fix`.)
- **No ×3 reviewer convergence anywhere** — single architect, two devs (cross-reviewing each other), one QA.
- **No `task-reviewer` agent at the review gate** — the devs cross-review each other's diffs; the v7 review-evidence schema's reviewer-is-the-other-dev pattern still satisfies the existing reviewer-≠-teammate hook check.
- **No `test-completeness-verifier` at gate time** — `mini-qa` does its own coverage check against `## QA Guidance`.
- **No visual / editability / interaction reviewers at runtime** — deferred to `/architect-team:mini-review-sweep`.
- **No `reconciler`** — non-overlapping file scope eliminates parallel-branch merges.
- **No `documentation-currency` producer/checker split at runtime** — runs single-pass at M7 before merge; the heavyweight sweep catches doc-drift later.

## Phase M0.1 — Discipline freshness check (v2.18.0)

Same shape as the main pipeline's Phase 0.1 — invoke `verify-discipline-registry-current` (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the Discipline-freshness row), auto-apply safe disciplines, route the rest as SRs. See `common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)`. Runs AFTER the MemPalace wake-up and BEFORE Phase M0 intake. Best-effort — a failure of the verify-tool never blocks the mini loop; surface a one-line note and proceed.

## Phase-boundary inbox check (v2.19.0)

Same shape as the main pipeline's `## Phase-boundary inbox check` — at the start of every mini phase (M0 / M1 / M2 / M3 / M4 / M5 / M6 / M7) AND **after every background-dispatch return / wake** (v3.16.0 — dispatch teammates with `run_in_background: true` so the inbox drains promptly, not only at phase boundaries), read the in-flight inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` via `hooks.inflight_inbox.unprocessed_messages`, classify each new message per v2.5.0 (incl. `parallel-problem` → spawn a concurrent lane with a disjoint `hooks/locks.py` lock, recording `lane_id` via `mark_processed`), mark_processed. Phase M7 invokes the 17th Layer 3 tool `verify-inflight-clarifications-processed` to gate against silently-ignored messages (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the In-flight inbox row).

See `common-pipeline-conventions/SKILL.md` `## In-flight clarification injection mechanism (v2.19.0)` for the canonical home + `## In-flight clarification discipline (v2.5.0)` `### Parallel lanes (v3.16.0)` for the responsiveness + parallel-lane protocol.

## Phase M0 — Intake

Detect the input form per `## Inputs`. Resolve `$REQ_DIR`:

- Folder form → `$REQ_DIR` is the resolved directory.
- Prose form → write the verbatim prose to `.architect-team/mini/<slug>/prompt.md`; `$REQ_DIR` is that file's directory.

Derive `<slug>` as `YYYY-MM-DD-<lowercase-kebab-of-the-prompt-or-folder-name>` (e.g., `2026-05-26-add-bulk-export`). The slug feeds the Mini-Run trailer at Phase M7.

Create a working branch off `main`:

```bash
git fetch origin
git checkout -b mini/<slug> origin/main
```

If the cwd is not on `main` already, this is fine — the mini variant always branches from the remote's `main` so the auto-merge at M7 has a known base.

**MemPalace wake-up.** Already run as the earliest action of Phase M0 per the `## MemPalace wake-up` section above (which references the canonical rule in `mempalace-integration` `## Phase A`). Per `mempalace-integration`, persist run artifacts (the OpenSpec bundle, the QA verdicts, the architect's M3 diffs) as the run progresses.

## Phase M1 — Maps freshness check

The mini variant uses **cached maps** wherever possible. Per `intake-and-mapping`, for each codebase the requirement touches:

1. Locate `<codebase>/docs/CODEBASE_MAP.md` and `<codebase>/docs/ROUTE_MAP.md` and the root `docs/INTEGRATION_MAP.md`.
2. Compare each map's `last_mapped` (or equivalent timestamp in its frontmatter) to the newest mtime of source files in its scope.
3. **Map fresh** (`last_mapped` ≥ newest src mtime) → use it as-is.
4. **Map stale or missing** → refresh **only the affected codebase**. Single-pass: dispatch `cartographer` for `CODEBASE_MAP.md` and `route-mapper` for `ROUTE_MAP.md`. **Do NOT** spawn ×3 reviewers; do NOT regenerate `INTEGRATION_MAP.md` unless the change crosses codebases. Single-pass refresh is the mini variant's whole-pipeline shape; trust the cartographer's first pass.

A stale `INTEGRATION_MAP.md` is the one case worth a ×3 escalation — but only when the change crosses codebases. For an in-codebase change, ignore stale integration-map sections.

Persist the maps (fresh or refreshed) into the working context for M2.

## Phase M2 — Architect drafts the 5-artifact OpenSpec bundle

The Lead creates a `system-architect` task in the shared list (teams mode) OR dispatches the `system-architect` subagent (subagents mode), with the prompt + the cached maps from M1. The architect produces the **full 5-artifact OpenSpec bundle** in one pass at `openspec/changes/<slug>/`:

- `proposal.md` — the WHY, the WHAT, and a mandatory `## QA Guidance` section (see contract below).
- `design.md` — architectural decisions.
- `specs/<capability>/spec.md` — capability-level requirements.
- `tasks.md` — the work breakdown with non-overlapping file scope for backend vs. frontend (per `team-spawning-and-review-gates`).
- `coverage-map.json` — per `coverage-mapping`, **plus** a top-level `qa_guidance` block mirroring the markdown section.

The mini variant produces all five so the OpenSpec archive looks identical to a full-pipeline change; no per-capability ×3 review.

### The ## QA Guidance contract

`proposal.md` MUST contain a `## QA Guidance` section with these four required sub-sections (and an optional `### Out of Scope`):

```markdown
## QA Guidance

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/qa-guidance.md` and execute it in full. Do not work from memory.

The `coverage-map.json` carries the same content as a top-level `qa_guidance` block (schema documented in `coverage-mapping` SKILL.md). The contract is enforced by `tests/test_qa_guidance_contract.py` — if the architect drafts a malformed contract, M3's self-confirm pass MUST detect and repair it (the validator is the structural check; the architect's reasoning is the semantic check).

## Phase M3 — Architect self-confirm loop

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m3.md` and execute it in full. Do not work from memory.

After M2, the **same architect** re-reads its own bundle + the source requirements + the cached maps, and asks one question of itself: *does the bundle still make sense?*

## Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m4.md` and execute it in full. Do not work from memory.

**Contract-first parallelism (v3.48.0) — before the dispatch.** If the slice needs backend surfaces the frontend must visualize (a new endpoint, or new attributes on an existing one), engage `contract-first-parallelism` first: the two agents co-design the inbound surface contract, the Lead approves it (the mini variant's Lead absorbs the `system-architect` `## Interface Contract Approval` role), and the backend provisions the endpoint AT ITS REAL PATH with a contract-conforming provisional payload registered in `<workspace>/.architect-team/contracts/ledger.json` and its retirement gate registered with `... declare-gate --json <contract.json> --registry "<workspace>/.architect-team/declared-gates.json"`. The frontend then builds its complete integration against the live surface instead of waiting on the backend's internals. The mock-retirement gate runs at M7 — see there.

## Phase M5 — mini-qa runs unit + integration + narrow Playwright

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m5.md` and execute it in full. Do not work from memory.

The Lead creates a `mini-qa` task in the shared list (teams mode) OR dispatches the `mini-qa` subagent (subagents mode) with:

## Phase M6 — Verdict gate

Read `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json`:

- `verdict: green` → proceed to **Phase M7** (auto-merge).
- `verdict: red-with-evidence` → proceed to **Phase M8** (re-eval loop; increment cycle counter).
- `verdict: env-failure` → halt. Write `.architect-team/mini/<slug>/env-failure.md` summarizing the env issue and surface to user. Do NOT increment the M8 cycle counter — env failures are not the fix's fault.

## Phase M7 — Auto-merge to main

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m7.md` and execute it in full. Do not work from memory.

**Mock-retirement gate (v3.48.0 — CFP-6).** If M4 created any interface contract, run the gate BEFORE the merge — a run does not close on a surface still serving a provisional payload:

## Phase M8 — Re-evaluation loop and escalation

> **STOP.** Before acting under this section, Read `skills/mini-architect-team-pipeline/references/phase-m8.md` and execute it in full. Do not work from memory.

On `verdict: red-with-evidence` from M6, the Lead increments the cycle counter and creates a fresh `system-architect` re-eval task in the shared list (teams mode) — or in teams mode, sends the existing `architect` teammate a `SendMessage` with the verdict and asks for the re-eval — OR dispatches the `system-architect` subagent again (subagents mode) for re-evaluation.

## Operating rules (non-negotiable)

The mini pipeline inherits the cross-cutting disciplines from `common-pipeline-conventions` AND the operating rules that apply to its phases. **Plus**:

- **Don't silently narrow the prompt's scope (v1.4.0).** If the mini architect's reading of the user's prompt at Phase M0/M2 is materially narrower than the prompt's literal meaning — particularly when the prompt contains a parity-implying verb (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) — surface the scope decision via `AskUserQuestion` BEFORE drafting the OpenSpec bundle at M2. The user's answer becomes the contract; silent reframing is the anti-pattern. Per `common-pipeline-conventions` `## Scope discipline`. This applies even though the mini pipeline's `## What this skill does NOT do` says *"no proposal-refiner Q&A loop"* — that exclusion covers PROCESS gates (the iterative grading loop is skipped). Scope-narrowing is a DOMAIN gate (per the v0.9.21 carve-out); the single clarification batch the M2 architect already surfaces when ambiguous IS where the scope question fires.
- **Reframing IS NOT a clarifying question.** A mini architect's instinct to "scope this down to fit in 5 ACs" when the literal prompt implies more is the same anti-pattern documented above — surface the scope decision; do not pre-narrow. If after the user's answer the work still exceeds 5 ACs, the mini variant's existing `needs-escalation` path (escalate to full `/architect-team`) is the right exit, NOT a silent narrowing.
- **Teammates MUST NOT run destructive git operations (v1.6.0).** The mini pipeline's `mini-qa`, implementer, and review teammates MUST NOT run `git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, or `git clean -f`. These manipulate state shared across teammates within the same run and caused the heirship-app-v2 reflog clobbering (concurrent stash + pop interleaving lost three of four teammates' work). For baseline verification, the orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` at Phase M0 and includes it in every teammate's spawn brief; teammates run `git diff $BASELINE_SHA -- <my-files>` instead of stashing. Per `common-pipeline-conventions` `## Teammate git discipline`.
- **Unbounded solving (v3.8.0).** There is NO iteration ceiling. The mini M4 → M8 loop never aborts on cycle count and never ends on incomplete work. On recurrence (the same proposal landing red repeatedly), the work is HANDED OFF to the full unbounded `/architect-team` pipeline on the same branch — a continuation of solving, not a give-up. The only interruptions are reaching success or pausing to collect required owner input. Per `common-pipeline-conventions` `## Unbounded solving discipline`.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Notifications (per-project email events — opt-in, best-effort)` | `skills/mini-architect-team-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md` | on demand |
| `MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)` | `skills/mini-architect-team-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` | on demand |
| `What this skill does NOT do` | `skills/mini-architect-team-pipeline/references/what-this-skill-does-not-do.md` | on demand |
| `QA Guidance` | `skills/mini-architect-team-pipeline/references/qa-guidance.md` | on demand |
| `Phase M3 — Architect self-confirm loop` | `skills/mini-architect-team-pipeline/references/phase-m3.md` | on demand |
| `Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)` | `skills/mini-architect-team-pipeline/references/phase-m4.md` | on demand |
| `Phase M5 — mini-qa runs unit + integration + narrow Playwright` | `skills/mini-architect-team-pipeline/references/phase-m5.md` | on demand |
| `Phase M7 — Auto-merge to main` | `skills/mini-architect-team-pipeline/references/phase-m7.md` | on demand |
| `Phase M8 — Re-evaluation loop and escalation` | `skills/mini-architect-team-pipeline/references/phase-m8.md` | on demand |
