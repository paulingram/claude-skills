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

**MemPalace wake-up.** Same discipline as `architect-team-pipeline` — resolve `<workspace>` via `git rev-parse --show-toplevel`, then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. If `mempalace` is not on PATH, surface the same one-line note the bug-fix-pipeline uses and proceed without it. Per `mempalace-integration`, persist run artifacts (the OpenSpec bundle, the QA verdicts, the architect's M3 diffs) as the run progresses.

## Phase M1 — Maps freshness check

The mini variant uses **cached maps** wherever possible. Per `intake-and-mapping`, for each codebase the requirement touches:

1. Locate `<codebase>/docs/CODEBASE_MAP.md` and `<codebase>/docs/ROUTE_MAP.md` and the root `docs/INTEGRATION_MAP.md`.
2. Compare each map's `last_mapped` (or equivalent timestamp in its frontmatter) to the newest mtime of source files in its scope.
3. **Map fresh** (`last_mapped` ≥ newest src mtime) → use it as-is.
4. **Map stale or missing** → refresh **only the affected codebase**. Single-pass: dispatch `cartographer` for `CODEBASE_MAP.md` and `route-mapper` for `ROUTE_MAP.md`. **Do NOT** spawn ×3 reviewers; do NOT regenerate `INTEGRATION_MAP.md` unless the change crosses codebases. Single-pass refresh is the mini variant's whole-pipeline shape; trust the cartographer's first pass.

A stale `INTEGRATION_MAP.md` is the one case worth a ×3 escalation — but only when the change crosses codebases. For an in-codebase change, ignore stale integration-map sections.

Persist the maps (fresh or refreshed) into the working context for M2.

## Phase M2 — Architect drafts the 5-artifact OpenSpec bundle

Dispatch `system-architect` with the prompt + the cached maps from M1. The architect produces the **full 5-artifact OpenSpec bundle** in one pass at `openspec/changes/<slug>/`:

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

Dispatch the `backend` and `frontend` agents **in parallel** via a single Agent-tool call carrying multiple invocations (mirrors `architect-team-pipeline` Phase 2). Each receives:

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

Dispatch the `mini-qa` agent with:

- `proposal.md` (its `## QA Guidance` section is authoritative scope).
- `coverage-map.json` (the `qa_guidance` block mirrors the markdown; they MUST agree or the verdict is `red-with-evidence`).
- The git diff produced by M4.
- The dev-environment URL(s) from the target project's `design.md` `## Dev Environment` section.
- The slug.
- The current cycle number `<N>` (1 on first invocation; M8 increments on re-eval).

`mini-qa` runs per its agent spec: read QA Guidance, verify unit + integration coverage exists, run both suites, author ≤ 3 Playwright flows, deploy to dev, run Playwright against the live dev URL, emit verdict.

Per `dev-api-integration-testing`, integration tests MUST hit the real dev API; mocks are reserved for truly external, non-deterministic dependencies. Per `playwright-user-flows`, every Playwright flow is genuine user-driven interaction (page.goto → click → fill → waitFor → assert visible state), not an endpoint call masquerading as a flow.

`mini-qa` writes `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json` per cycle.

## Phase M6 — Verdict gate

Read `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json`:

- `verdict: green` → proceed to **Phase M7** (auto-merge).
- `verdict: red-with-evidence` → proceed to **Phase M8** (re-eval loop; increment cycle counter).
- `verdict: env-failure` → halt. Write `.architect-team/mini/<slug>/env-failure.md` summarizing the env issue and surface to user. Do NOT increment the M8 cycle counter — env failures are not the fix's fault.

## Phase M7 — Auto-merge to main

On `verdict: green` from M6, the orchestrator performs the auto-merge sequence. **This is the only point in any architect-team pipeline that pushes to `main` directly.**

### Doc-currency single-pass

Per `documentation-currency`, run a single-pass doc update (no producer/checker split) covering: `README.md`, `CHANGELOG.md`, `CODEBASE_MAP.md`, `INTEGRATION_MAP.md`, `CLAUDE.md`, per-codebase `ROUTE_MAP.md` / `DESIGN_MAP.md` if they exist and are touched. The mini variant runs this in-line rather than spawning a separate `doc-updater` agent — the architect handles it.

### Commit sequence

1. Stage all M4 + M5 + doc-currency changes.
2. Commit with trailers:
   ```
   Mini-Run: <slug>
   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
   Author override (this repo): `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
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

### Compact prompt

After successful merge, emit the standard `/compact` prompt (matches `architect-team-pipeline` Phase 8 behavior). Suppressed by `--no-compact`.

### Flags affecting M7

- `--no-merge` — skip the merge sequence entirely. The commit and push still happen on the working branch; the user merges manually. Falls back to existing `/architect-team` semantics.
- `--squash-merge` — replace the fast-forward with `git merge --squash mini/<slug>` + a single `Mini-Run:`-tagged commit. The architect/dev/QA commit chain is collapsed into one commit. Trade-off: easier `main` history; the sweep loses sub-commit granularity.
- `--no-commit` — skip the commit step (and therefore push + merge). Used when running the mini pipeline as a dry-run.
- `--no-push` — commit but do not push or merge.
- `--no-compact` — suppress the `/compact` prompt.

## Phase M8 — Re-evaluation loop and escalation

On `verdict: red-with-evidence` from M6, increment the cycle counter and dispatch the architect for re-evaluation.

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
