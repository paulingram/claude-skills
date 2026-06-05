---
name: mini-architect-team-pipeline
description: "Use when a small-to-medium feature change needs to be driven end-to-end faster than the full /architect-team can deliver, but with auto-merge to main on green QA. A sibling orchestrator playbook to architect-team-pipeline and bug-fix-pipeline. Speed comes from dropping phases and parallel-review fan-out — not from a weaker model; all roles run on Opus 4.7. Single architect (system-architect) drafts the full 5-artifact OpenSpec bundle with a mandatory ## QA Guidance section in proposal.md, self-confirms to a fixed point (capped at 3 passes), dispatches backend + frontend devs in parallel with non-overlapping file scope (the devs cross-review each other; no separate task-reviewer agent), and a single mini-qa agent runs unit + integration + 1–3 narrow Playwright flows tied to acceptance criteria against the live dev URL. On green the orchestrator commits with a Mini-Run: <slug> trailer and auto-merges to main; on red the architect re-evaluates (cycle cap = 3); on cycle 4 the work escalates to /architect-team with an escalation folder. Accepts the same two input forms as the main /architect-team — a requirements folder OR a plain-language requirement typed directly as prose."
---

# mini-architect-team-pipeline

The `/architect-team` pipeline is correct-by-construction at 8 phases, 26 agents, and ×3 reviewer convergence at multiple points. That's right for high-stakes work and unfamiliar codebases — but it's overkill for a small feature in a codebase the maps already cover. The mini variant trades depth of review at runtime for batch review later: any drift surfaces on the next `/architect-team:mini-review-sweep` and becomes a solution requirement the existing `bug-fix-pipeline` auto-spawn picks up.

You are the **Team Lead** for the mini variant. Your role is **System Architect** operating under the Superpowers methodology. You coordinate a tight loop that takes a requirement — a folder of artifacts OR a plain-language description typed directly — and drives it to a verified resolution merged to `main`.

## Inputs

`$REQ_DIR` (bound by `/architect-team:mini` from the user's argument) is the **requirement**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to the main `/architect-team`:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding requirement artifacts, screenshots, prior notes, or an OpenSpec brief.
2. **A plain-language requirement** — prose typed directly as the argument. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — **never refuse plain-language prose**, **do NOT treat the first word of a sentence as a path**, **do NOT ask the user for a folder when prose was given**. Ask only when `$REQ_DIR` is genuinely empty. The codebase the requirement applies to is the cwd (a git repo) unless the prose explicitly names another path.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

## Dispatch mode

Per `common-pipeline-conventions` `## Dispatch mode (v1.0.0)`, the selection (env `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` + `claude --version >= 2.1.32` + `--no-teams` flag, also readable from `~/.claude/settings.json`) is computed ONCE — for the mini pipeline, at the top of Phase M0 — and persisted as `dispatch_mode: "teams"` or `dispatch_mode: "subagents"` to `<workspace>/.architect-team/intake-state.json` (the mini pipeline shares the main pipeline's `intake-state.json` location). Every later phase reads it; the hook scripts branch on it (teams mode = `TaskCompleted` / `TeammateIdle`; subagents mode = `PostToolUse(TaskUpdate)` / `SubagentStop`). The teams-mode primitives (Lead spawns named teammates via the Agent tool with `run_in_background: true`, agent type inherited, `SendMessage` for coordination, shared task list at `~/.claude/tasks/<slug>/`) and the subagents-mode primitives (ephemeral Agent-tool dispatches, fresh context per call, no `SendMessage`, handoff files for coordination) are spelled out in the canonical section — do not re-explain them inline.

**Mini-specific behavior.** In teams mode the mini variant runs four named teammates — `architect`, `backend-dev`, `frontend-dev`, `mini-qa` — and uses `SendMessage` specifically for the M4 cross-review (each dev sends its `self_review` evidence to the other for the `independent_review` block). In subagents mode the M4 backend + frontend parallel dispatch is the canonical batched-parallel pattern — a single Agent-tool call carrying both invocations. Wherever this skill body says *"the Lead creates a `<role>` task (teams mode) OR dispatches the `<role>` subagent (subagents mode)"*, the branch is decided by `dispatch_mode`; both halves of the sentence are real, the orchestrator picks one at execution time. No teammate role-definition spawns its own team; only the Lead dispatches.

## Notifications (per-project email events — opt-in, best-effort)

Per `common-pipeline-conventions` `## Notifications wiring convention`, the mini pipeline emits notification events via the notifier CLI at `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`. The discipline is opt-in (gated on `.architect-team-notify.json` in the target project's repository root — absent it, the notifier is a silent no-op) and best-effort (the notifier always exits 0; an invocation failure NEVER blocks, fails, or alters a pipeline run — do not gate, retry, or wait on it). Every invocation uses the polyglot `python3 ... || python ...` form per `common-pipeline-conventions` `## Cross-platform Python invocation`.

The mini pipeline is the only pipeline that auto-merges to `main`, so observing a Mini-Run on the default branch is exactly the event a stakeholder would want notified on — the v1.0.0 decision is to wire notifications into the mini variant for parity with the main and bug-fix pipelines.

**Phase-boundary wiring (`phase_start` / `phase_complete`) — applies to every M-phase.** At the **start of each phase** (Phase M0, M1, M2, M3, M4, M5, M6, M7, M8), as the first action of that phase, the orchestrator emits a `phase_start` event; at the **end of each phase**, as the last action before moving to the next phase, it emits a `phase_complete` event. Both pass `--phase` with the canonical phase name:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_start --project <name> --phase "Phase M5 — mini-qa runs unit + integration + narrow Playwright" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_start --project <name> --phase "Phase M5 — mini-qa runs unit + integration + narrow Playwright"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_complete --project <name> --phase "Phase M5 — mini-qa runs unit + integration + narrow Playwright" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_complete --project <name> --phase "Phase M5 — mini-qa runs unit + integration + narrow Playwright"
```

The remaining three events (`issue_discovered`, `git_commit`, `deploy`) are wired at specific M-phase steps:

- **`deploy`** — fires at **Phase M5** when `mini-qa` deploys to the dev environment for the Playwright run, with `--layer <layer>`.
- **`git_commit`** — fires at **Phase M7** immediately after the Mini-Run commit succeeds (BEFORE the auto-merge to main), with `--commit <SHA>`. This is the highest-signal event in any mini-run — the commit will land on `main`.
- **`issue_discovered`** — fires at **Phase M8** when a `red-with-evidence` verdict from M6 triggers the re-eval loop, with `--summary` carrying the verdict's failure-mode description.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

Per `common-pipeline-conventions` `## MemPalace wake-up precondition` (which points at the canonical rule in `mempalace-integration` `## Phase A — Wake-up at pipeline start`): the unscoped wake-up runs as the earliest action of Phase M0 — before any subagent dispatch. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback), then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. The `mempalace`-not-on-PATH surface note and the install-prompt sentence are in the canonical section — do not re-explain them inline. Per `mempalace-integration`, persist run artifacts (the OpenSpec bundle, the QA verdicts, the architect's M3 diffs) as the run progresses.

After EVERY background Agent dispatch in this pipeline (Phase M2 system-architect drafting, Phase M3 architect self-confirm loop, Phase M4 backend + frontend devs in parallel, Phase M5 mini-qa, Phase M7 doc-updater), route the raw dispatch result through `wrap_agent_result()` from `scripts/setup/agent_resume.py` per `common-pipeline-conventions` `## Background-agent resume discipline` BEFORE treating the work as complete. Truncated / stream-timed-out results auto-resume up to 2 attempts; `resumed_failed=True` surfaces to the user with on-disk artifacts cited.

## What this skill does NOT do

- **No proposal-refiner Q&A loop** — the architect grounds prose directly. If ambiguous, the architect surfaces ONE clarification batch before drafting; no iterative grading loop.
- **No Phase −2 bug-classifier triage** — feature work is assumed. (Bug fixes use `/architect-team:bug-fix`.)
- **No ×3 reviewer convergence anywhere** — single architect, two devs (cross-reviewing each other), one QA.
- **No `task-reviewer` agent at the review gate** — the devs cross-review each other's diffs; the v6 review-evidence schema's reviewer-is-the-other-dev pattern still satisfies the existing reviewer-≠-teammate hook check.
- **No `test-completeness-verifier` at gate time** — `mini-qa` does its own coverage check against `## QA Guidance`.
- **No visual / editability / interaction reviewers at runtime** — deferred to `/architect-team:mini-review-sweep`.
- **No `reconciler`** — non-overlapping file scope eliminates parallel-branch merges.
- **No `documentation-currency` producer/checker split at runtime** — runs single-pass at M7 before merge; the heavyweight sweep catches doc-drift later.

These deferrals are the source of the mini variant's speed. The accompanying trade-off is that drift surfaces in batch via the sweep, not at runtime — accept that trade-off explicitly when invoking `/architect-team:mini`.

### In-flight clarification handling (v2.5.0)

If the user injects a message mid-run (after this skill has begun executing any of Phase M0 → M7) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, the orchestrator MUST treat the message as a **clarification or scope amendment to the IN-FLIGHT mini run** — append it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase (re-run Phase M0 → M2 if scope materially shifted; otherwise fold into the next phase's inputs), and continue the pipeline. The orchestrator MUST NOT solve the clarification with tools directly, answer conversationally without folding, spawn a sibling `/architect-team` invocation, or silently ignore. Full rules in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.

## Phase M0.1 — Discipline freshness check (v2.18.0)

Same shape as the main pipeline's Phase 0.1 — invoke `verify-discipline-registry-current`, auto-apply safe disciplines, route the rest as SRs. See `common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)`. Runs AFTER the MemPalace wake-up and BEFORE Phase M0 intake.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-discipline-registry-current --workspace "<workspace>" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-discipline-registry.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-discipline-registry-current --workspace "<workspace>" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-discipline-registry.json"
```

Best-effort — a failure of the verify-tool never blocks the mini loop; surface a one-line note and proceed.

## Phase-boundary inbox check (v2.19.0)

Same shape as the main pipeline's `## Phase-boundary inbox check` — at the start of every mini phase (M0 / M1 / M2 / M3 / M4 / M5 / M6 / M7) AND after every subagent dispatch returns, read the in-flight inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` via `hooks.inflight_inbox.unprocessed_messages`, classify each new message per v2.5.0, mark_processed. Phase M7 invokes the 17th Layer 3 tool to gate against silently-ignored messages.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-inflight-clarifications-processed --workspace "<workspace>" --run-id "<run-id>" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-inflight-clarifications.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-inflight-clarifications-processed --workspace "<workspace>" --run-id "<run-id>" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-inflight-clarifications.json"
```

See `common-pipeline-conventions/SKILL.md` `## In-flight clarification injection mechanism (v2.19.0)` for the canonical home.

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

### Acceptance Criteria
- [AC-1] <user-observable behavior>
(≤ 5 ACs. >5 means the change is too large for the mini pipeline — split or escalate.)

### Unit Test Targets
- <file:function or file:class>: <what to assert>
(Per-file targets the dev MUST cover; mini-qa verifies each ran and passed.)

### Integration Test Targets
- <real dev API endpoint or DB-touching path>: <what to assert>
(Real backend, real dev data — per dev-api-integration-testing; no mocks.)

### Playwright Flows
- [AC-1] <flow name>: <entry URL on dev> → <user actions> → <assertion>
(≤ 3 Playwright flows. Each binds to an AC by ID. Runs against the live dev URL.)

### Out of Scope
- <thing the QA agent must NOT test, with reason>
```

The `coverage-map.json` carries the same content as a top-level `qa_guidance` block (schema documented in `coverage-mapping` SKILL.md). The contract is enforced by `tests/test_qa_guidance_contract.py` — if the architect drafts a malformed contract, M3's self-confirm pass MUST detect and repair it (the validator is the structural check; the architect's reasoning is the semantic check).

**If the requirement requires more than 5 ACs**: the architect surfaces this to the user as `needs-escalation` and stops. The mini variant is for small-to-medium changes; >5 ACs means the change should run through `/architect-team` directly.

## Phase M3 — Architect self-confirm loop

After M2, the **same architect** re-reads its own bundle + the source requirements + the cached maps, and asks one question of itself: *does the bundle still make sense?*

Iterate to a **fixed point**: edit in place, re-read, repeat. Exit when a pass produces zero edits. **Cap = 3 self-confirm passes.** On cap, the architect freezes its current draft and proceeds, noting the unresolved divergence in a `## M3 unresolved` section at the bottom of `proposal.md` so M5's QA agent scrutinizes that area especially carefully.

Each pass must answer at minimum:

1. Does the `## QA Guidance` contract validate? (Run the parser; fix violations.)
2. Does every AC have a covering Playwright flow? (And every flow bind to an AC?)
3. Does the file scope in `tasks.md` not overlap between backend and frontend?
4. Does the proposal's WHY still match the user's prose / folder?
5. Are the maps the architect cited at M2 still in working context?

The self-confirm pass is **structural + semantic**, not free-form refinement. If the architect finds itself rewriting the proposal's voice or scope on a second pass, that's a sign M2 was wrong — note this in the unresolved section rather than spinning.

## Phase M4 — Parallel dev dispatch (backend + frontend, cross-review)

The Lead creates `backend` + `frontend` tasks **in parallel** in the shared list (teams mode) OR dispatches the `backend` and `frontend` subagents **in parallel** via a single Agent-tool call carrying multiple invocations (subagents mode) — mirrors `architect-team-pipeline` Phase 2. Each receives:

- `tasks.md` from M2/M3 — with the file-scope partition.
- `coverage-map.json` — including the `qa_guidance` block.
- The cached maps from M1.

Per `team-spawning-and-review-gates`, the file scopes MUST NOT overlap. If the architect's `tasks.md` accidentally overlaps scopes, this is an M3 failure — return to M3 with the conflict noted (does not consume an M8 cycle).

### Cross-review (no `task-reviewer` agent)

Instead of dispatching a separate `task-reviewer` agent, the **two devs cross-review each other's diffs**:

- After `backend` writes its `self_review` block in the review-evidence file v6, the orchestrator dispatches `frontend` with the additional task of writing the `independent_review` block for `backend`'s evidence file (and vice versa).
- The v6 schema's existing `reviewer != teammate` invariant is satisfied: `frontend` reviewing `backend`'s task has `teammate: backend, reviewer: frontend`, which is not the self-review forbidden pattern.
- The cross-review is **lightweight** — verify the diff matches the task's acceptance criteria, run the linters/type-checkers the diff touches, grep the diff for `TODO`, `NotImplementedError`, mock-return placeholders, and the new-file Reuse Decision.

The trade-off: weaker independence than a dedicated reviewer. Mitigation: `mini-qa`'s coverage check at M5 catches missing test coverage; the `/architect-team:mini-review-sweep` command catches the rest in batch.

On review-evidence write, the existing `hooks/review-gate-task.py` runs unchanged — the dev↔dev cross-review case satisfies the existing schema invariants and needs no hook change (verified by `tests/test_mini_review_gate_dev_cross_check.py`).

## Phase M5 — mini-qa runs unit + integration + narrow Playwright

The Lead creates a `mini-qa` task in the shared list (teams mode) OR dispatches the `mini-qa` subagent (subagents mode) with:

- `proposal.md` (its `## QA Guidance` section is authoritative scope).
- `coverage-map.json` (the `qa_guidance` block mirrors the markdown; they MUST agree or the verdict is `red-with-evidence`).
- The git diff produced by M4.
- The dev-environment URL(s) from the target project's `design.md` `## Dev Environment` section.
- The slug.
- The current cycle number `<N>` (1 on first invocation; M8 increments on re-eval).

`mini-qa` runs per its agent spec: read QA Guidance, verify unit + integration coverage exists, run both suites, author ≤ 3 Playwright flows, deploy to dev, run Playwright against the live dev URL, emit verdict.

**Deploy notification (best-effort, per `## Notifications`).** When `mini-qa` brings the dev environment up for the Playwright run, the orchestrator emits a `deploy` event with `--layer <layer>`. Invoke from the target project's root and proceed immediately regardless of the notifier's outcome:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer>
```

This `deploy` invocation is best-effort and NEVER blocks, fails, or delays bringing the dev environment up — a notifier failure does not affect the deploy or the QA run.

Per `dev-api-integration-testing`, integration tests MUST hit the real dev API; mocks are reserved for truly external, non-deterministic dependencies. Per `playwright-user-flows`, every Playwright flow is genuine user-driven interaction (page.goto → click → fill → waitFor → assert visible state), not an endpoint call masquerading as a flow.

`mini-qa` writes `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json` per cycle.

## Phase M6 — Verdict gate

Read `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json`:

- `verdict: green` → proceed to **Phase M7** (auto-merge).
- `verdict: red-with-evidence` → proceed to **Phase M8** (re-eval loop; increment cycle counter).
- `verdict: env-failure` → halt. Write `.architect-team/mini/<slug>/env-failure.md` summarizing the env issue and surface to user. Do NOT increment the M8 cycle counter — env failures are not the fix's fault.

## Phase M7 — Auto-merge to main

### Deploy mandate final gate (v2.20.0)

If `intake_state.deploy_mandate.active == true`, invoke the 18th Layer 3 tool BEFORE the auto-merge sequence:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-deploy-mandate-satisfied --artifact "<workspace>/.architect-team/vao-evidence/<run-id>.json" --mandate "<workspace>/.architect-team/intake-state.json" --final-report "<workspace>/.architect-team/final-reports/<run-id>.md" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-deploy-mandate.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-deploy-mandate-satisfied --artifact "<workspace>/.architect-team/vao-evidence/<run-id>.json" --mandate "<workspace>/.architect-team/intake-state.json" --final-report "<workspace>/.architect-team/final-reports/<run-id>.md" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-deploy-mandate.json"
```

Any of the 4 severities blocks the auto-merge. The mini loop routes the failure back to Phase M8 cycle as `verdict: red` with the deploy-mandate gap as the explicit failure reason; the architect re-spawns to satisfy the missing binding criterion. See `common-pipeline-conventions/SKILL.md` `## Deploy mandate discipline (v2.20.0)` for the canonical home.

### Unilateral-override meta-gate (v3.0.0)

After the deploy-mandate gate, run the 21st Layer 3 tool as a meta-confession check across all text artifacts the mini run produced (architect's M3 self-confirm verdict, mini-qa M5 verdict notes, M6 final summary):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-no-unilateral-override --sources "<workspace>/.architect-team/vao-evidence/<run-id>-text-sources.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-unilateral-override.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-no-unilateral-override --sources "<workspace>/.architect-team/vao-evidence/<run-id>-text-sources.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-unilateral-override.json"
```

Single severity `unilateral-override-with-virtue-framed-confession` blocks the auto-merge; routes to Phase M8 cycle as red. See `common-pipeline-conventions/SKILL.md` `## Unilateral-override discipline (v3.0.0) — META` for the canonical home.

On `verdict: green` from M6, the orchestrator performs the auto-merge sequence. **This is the only point in any architect-team pipeline that pushes to `main` directly.**

### Doc-currency single-pass

Per `documentation-currency`, run a single-pass doc update (no producer/checker split) covering: `README.md`, `CHANGELOG.md`, `CODEBASE_MAP.md`, `INTEGRATION_MAP.md`, `CLAUDE.md`, per-codebase `ROUTE_MAP.md` / `DESIGN_MAP.md` if they exist and are touched. The mini variant runs this in-line rather than spawning a separate `doc-updater` agent — the architect handles it.

### Commit sequence

1. Stage all M4 + M5 + doc-currency changes.
2. Commit with trailers:
   ```
   Mini-Run: <slug>
   Dispatch-Mode: <teams|subagents>
   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
   Author override (this repo): `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`

   The `Dispatch-Mode:` trailer (v1.5.0) is derived from
   `.architect-team/intake-state.json`'s `dispatch_mode` field — recorded
   at M0 startup per v1.0.0's mode-detection contract. Values are `teams`
   (Agent Teams primitive) or `subagents` (the ephemeral subagent fallback).
   Sits alongside the existing `Mini-Run:` trailer so
   `/architect-team:mini-review-sweep` can filter sweep candidates by both
   dimensions when needed. Read the value once at M7 commit-build time; it
   does NOT change mid-run.
2b. **Immediately after the commit succeeds**, the orchestrator emits a `git_commit` notification (best-effort, per `## Notifications`), with `--commit <SHA>`. This is the highest-signal mini-run event — the commit will shortly land on `main` via the auto-merge sequence below. Invoke from the target project's root and proceed immediately:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha>
   ```

   This `git_commit` invocation is best-effort and NEVER blocks, fails, or alters the commit, the subsequent push, or the merge — a notifier failure does not affect git in any way.
3. Push the working branch: `git push -u origin mini/<slug>`.

### Merge sequence

1. `git fetch origin`
2. If `main` is unchanged since branch creation: fast-forward `main` to the branch tip:
   ```bash
   git checkout main && git merge --ff-only mini/<slug> && git push origin main
   ```
3. If `main` has advanced: rebase the branch on `main` then fast-forward:
   ```bash
   git rebase origin/main && git push --force-with-lease origin mini/<slug>
   git checkout main && git merge --ff-only mini/<slug> && git push origin main
   ```
4. If rebase produces conflicts: **halt**. Write `.architect-team/mini/<slug>/merge-conflict.json` with the conflict files and surface to the user. **Never** auto-resolve. **Never** use `--no-verify`. **Never** use `--force` (only `--force-with-lease`).
5. On success: delete the working branch locally and remotely (`git push origin --delete mini/<slug>; git branch -d mini/<slug>`).

### Cleanup the run worktree (v1.3.0)

After the merge succeeds and the branch is deleted (step 5 above), remove the
run worktree itself. The mini pipeline just merged its own branch to main;
the worktree's purpose is fulfilled. This is the "in-run cleanup" trigger
documented in `common-pipeline-conventions` `## Auto-worktree lifecycle`
`### Auto-cleanup (v1.3.0)` — the other trigger (the start-of-run sweep at
the slash commands) handles every OTHER prior-run merged worktree.

Invoke `cleanup_run_worktree` against the current worktree path, with
`remove_branch=False` because step 5 already deleted the branch (a second
`git branch -d` would be a no-op-with-error). Polyglot pattern:

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_run_worktree; from pathlib import Path; cleanup_run_worktree(Path.cwd(), remove_branch=False)" || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_run_worktree; from pathlib import Path; cleanup_run_worktree(Path.cwd(), remove_branch=False)"
```

`cleanup_run_worktree` is idempotent — if the worktree has already been
removed by some other path, the call is a no-op. The `git worktree remove`
runs from the main repo's toplevel (not from inside the worktree being
removed), so it doesn't break the orchestrator's cwd mid-call; the helper
handles that by resolving `_git_show_toplevel()` to the MAIN repo.

This in-run cleanup is best-effort just like the start-of-run sweep: a
failure surfaces a one-line note and the `/compact` prompt below still
fires.

### Compact prompt

After successful merge, emit the standard `/compact` prompt (matches `architect-team-pipeline` Phase 8 behavior). Suppressed by `--no-compact`.

### Flags affecting M7

- `--no-merge` — skip the merge sequence entirely. The commit and push still happen on the working branch; the user merges manually. Falls back to existing `/architect-team` semantics.
- `--squash-merge` — replace the fast-forward with `git merge --squash mini/<slug>` + a single `Mini-Run:`-tagged commit. The architect/dev/QA commit chain is collapsed into one commit. Trade-off: easier `main` history; the sweep loses sub-commit granularity.
- `--no-commit` — skip the commit step (and therefore push + merge). Used when running the mini pipeline as a dry-run.
- `--no-push` — commit but do not push or merge.
- `--no-compact` — suppress the `/compact` prompt.

## Phase M8 — Re-evaluation loop and escalation

On `verdict: red-with-evidence` from M6, the Lead increments the cycle counter and creates a fresh `system-architect` re-eval task in the shared list (teams mode) — or in teams mode, sends the existing `architect` teammate a `SendMessage` with the verdict and asks for the re-eval — OR dispatches the `system-architect` subagent again (subagents mode) for re-evaluation.

**Issue-discovered notification (best-effort, per `## Notifications`).** Before re-dispatching the architect, the orchestrator emits an `issue_discovered` event with the verdict's failure-mode description as `--summary`. Invoke from the target project's root and proceed immediately regardless of the notifier's outcome:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the red verdict's failure-mode description>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the red verdict's failure-mode description>"
```

This `issue_discovered` invocation is best-effort and NEVER blocks or alters the M8 re-eval — a notifier failure does not stop the next mini-cycle.

### Re-eval pass

The architect reads:

- `qa-verdict-cycle-<N>.json` — the full evidence trail of what failed.
- The original `proposal.md` + `tasks.md` + `coverage-map.json`.
- The cached maps from M1.

The architect edits the OpenSpec bundle in place (proposal, tasks, coverage-map) to address the failure. The architect MUST NOT just retry the same plan — the verdict's `responsible_role_on_red` field tells the architect which team's instructions were wrong. The re-eval modifies those instructions, then loops back to **Phase M4** (parallel dev re-dispatch) with the new tasks.md.

### Cycle cap = 3, escalate on cycle 4

After three red verdicts on the same proposal (`cycle: 1`, `cycle: 2`, `cycle: 3` in the qa-verdict files), the orchestrator **escalates** to `/architect-team`. The mini pipeline is for changes that converge fast — three red cycles is the signal that the change is not "mini" in nature and needs the full pipeline's heavyweight machinery.

### Escalation handoff (cycle 4)

Build the escalation folder at `.architect-team/mini/<slug>/escalation/`:

```
escalation/
    prompt.md              — original user prompt verbatim (from .architect-team/mini/<slug>/prompt.md
                             or the folder REQ_DIR's contents copied in)
    proposal.md            — the latest architect draft (final M3 state from cycle 3)
    qa-evidence/
        qa-verdict-cycle-1.json
        qa-verdict-cycle-2.json
        qa-verdict-cycle-3.json
    architect-diffs/
        m3-edits-cycle-1.diff
        m3-edits-cycle-2.diff
        m3-edits-cycle-3.diff
    escalation-context.md  — branch ref (mini/<slug>), the maps that were used (with their
                             last_mapped timestamps), the escalation reason in prose
```

Re-spawn the full pipeline: `/architect-team .architect-team/mini/<slug>/escalation/`. The full pipeline reads this folder as a normal `$REQ_DIR` and resumes from Phase −1 on the **same working branch** — the mini run does NOT switch branches before handing off, so the full pipeline's work continues on `mini/<slug>` and merges from there per its own Phase 8 rules.

Mini run exits with this user-facing message:

```
Mini run for <slug> escalated to full /architect-team after 3 red QA cycles.
Continuing on branch mini/<slug>. See .architect-team/mini/<slug>/escalation/escalation-context.md
for the failure trail.
```

## Operating rules (non-negotiable)

The mini pipeline inherits the cross-cutting disciplines from `common-pipeline-conventions` AND the operating rules that apply to its phases. **Plus**:

- **Don't silently narrow the prompt's scope (v1.4.0).** If the mini architect's reading of the user's prompt at Phase M0/M2 is materially narrower than the prompt's literal meaning — particularly when the prompt contains a parity-implying verb (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) — surface the scope decision via `AskUserQuestion` BEFORE drafting the OpenSpec bundle at M2. The user's answer becomes the contract; silent reframing is the anti-pattern. Per `common-pipeline-conventions` `## Scope discipline`. This applies even though the mini pipeline's `## What this skill does NOT do` says *"no proposal-refiner Q&A loop"* — that exclusion covers PROCESS gates (the iterative grading loop is skipped). Scope-narrowing is a DOMAIN gate (per the v0.9.21 carve-out); the single clarification batch the M2 architect already surfaces when ambiguous IS where the scope question fires.
- **Reframing IS NOT a clarifying question.** A mini architect's instinct to "scope this down to fit in 5 ACs" when the literal prompt implies more is the same anti-pattern documented above — surface the scope decision; do not pre-narrow. If after the user's answer the work still exceeds 5 ACs, the mini variant's existing `needs-escalation` path (escalate to full `/architect-team`) is the right exit, NOT a silent narrowing.
- **Teammates MUST NOT run destructive git operations (v1.6.0).** The mini pipeline's `mini-qa`, implementer, and review teammates MUST NOT run `git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, or `git clean -f`. These manipulate state shared across teammates within the same run and caused the heirship-app-v2 reflog clobbering (concurrent stash + pop interleaving lost three of four teammates' work). For baseline verification, the orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` at Phase M0 and includes it in every teammate's spawn brief; teammates run `git diff $BASELINE_SHA -- <my-files>` instead of stashing. Per `common-pipeline-conventions` `## Teammate git discipline`.
