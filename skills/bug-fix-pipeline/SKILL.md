---
name: bug-fix-pipeline
description: "Use when a bug needs to be fixed end-to-end faster than the full architect-team-pipeline can deliver, but with the same rigor where it matters. A sibling orchestrator playbook whose Phases B−1 through B8 mirror the main pipeline's structural points but replace the Phase 2-5 parallel-team-spawn / 6-team-review with a tight replicate → reproduce-test → propose → fix → QA-replay loop. The body documents the five non-negotiable disciplines (replicate first, reproduction IS the regression test, generalized fix not symptom patch, QA replay against the live dev environment, live-dev-by-default with production opt-in). Accepts the same two input forms as the main /architect-team — a requirements folder OR a plain-language requirement typed directly as prose."
---

# bug-fix-pipeline

The `architect-team-pipeline` is excellent for greenfield features and substantial new capability work. For a known-bug-with-a-clear-symptom — *"the row-action menu's Delete button doesn't actually delete; clicking it just closes the menu"* — its 100%-coverage planning gate, parallel team spawn, six Phase 5 review teams, and master-review audit are weight a 30-line fix doesn't need. The `bug-fix-pipeline` keeps the discipline that matters (maps must be fresh; the proposal must be real; the fix must be generalized; testing must be against the live system) and replaces what doesn't apply to a bug fix with the discipline specific to one.

You are the **Team Lead** for the bug-fix variant. Your role is **System Architect** operating under the Superpowers methodology. You coordinate a tight loop that takes a bug — a folder of artifacts OR a plain-language description typed directly — and drives it to a verified resolution against the live dev environment.

## Plugin prerequisites (v3.9.0)

**superpowers is a HARD dependency.** A pre-flight check runs as the very first action of this pipeline — BEFORE Phase B−1 (Intake & Mapping) — and ABORTS the run if the superpowers plugin is unavailable. Resolve availability either way: (a) `~/.claude/plugins/installed_plugins.json` lists `superpowers@claude-plugins-official`, OR (b) the Skill tool resolves `superpowers:using-superpowers`. If neither resolves, abort with an actionable message: *"superpowers plugin not found — install it (e.g. `/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`) before running /architect-team:bug-fix; the pipeline's design / TDD / debugging / verification gates depend on it."* Do NOT silently degrade to a methodology-by-hand fallback. The canonical source of truth is `common-pipeline-conventions/SKILL.md` `## Uniform plugin usage (v3.9.0)`.

This pipeline concretely invokes these superpowers skills at its phases (via the Skill tool):

- `superpowers:brainstorming` — design / intake (Phase B3 proposal authoring, before drafting the fix design).
- `superpowers:test-driven-development` — implementation (Phase B2 reproduction-as-regression-test + Phase B5 implement, before writing the fix code).
- `superpowers:systematic-debugging` — RCA / diagnosis (Phase B1 replication + Phase B3 diagnostic-research-team, before proposing any fix).
- `superpowers:verification-before-completion` — review / completion gates (Phase B6 QA replay + Phase B7 archive, before claiming the bug resolved).

**Precedence.** User `CLAUDE.md` / `AGENTS.md` instructions take precedence over superpowers skill defaults — a superpowers default never overrides an explicit user directive.

## Five non-negotiable disciplines

1. **Replicate first.** Phase B1 reproduces the symptom — a Playwright user-flow for frontend bugs, a backend script for backend bugs — against the live dev environment, BEFORE any fix is proposed. A fix without a replication is a guess and gets rejected at the architect review (Phase B4).
2. **Reproduction IS the regression test.** The Playwright flow / backend script that demonstrated the bug becomes the test the QA replay verifies against post-fix. No "now write a test" second step. For frontend bugs the agent ALSO writes a **backend diagnostic test** so the regression is covered on both sides of the contract.
3. **Generalize, never symptom-patch.** The `system-architect` Bug-Fix Generalization Audit at Phase B4 rejects fixes that special-case the failing input — a literal user-id in a conditional, a hard-coded category name in a switch. The override is explicit: the user has to say *"hard-code it"* / *"hotfix this one"* / equivalent. Silence is NOT authorization.
4. **QA replay against live dev.** Phase B6 dispatches the `qa-replayer` against the deployed fix, re-running the original replication artifacts verbatim. The pass criterion is *"the originating symptom is gone end-to-end"* — not "the test passes," but the original failure mode is no longer reproducible — AND *"the code-path execution witness confirms the fix's buggy handler was actually invoked by the test"* (v0.9.31). A test that passes via a different code path (selector misidentification, precondition skip, sibling-handler entry) is the failure mode v0.9.31's witness exists to catch; the new verdict `test-did-not-exercise-fix` routes back to **Phase B2** (re-author the test) instead of B3 (re-propose the fix), because the FIX may be correct and the TEST may be wrong — separate axes, separate recovery paths.
5. **Live-dev-environment-by-default.** Phase B5 ALWAYS deploys the fix to the dev environment (per the target project's `design.md` `## Dev Environment` section) before Phase B6 testing. Builds confirmed green first. Production is an explicit opt-in exception (`--environment production`) that escalates a structured question to the user.

## Inputs

`$REQ_DIR` (bound by `/architect-team:bug-fix` from the user's argument) is the **bug**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to the main `/architect-team`:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding bug-report artifacts, screenshots, prior diagnostic notes, or an OpenSpec brief.
2. **A plain-language requirement** — prose typed directly as the argument: a sentence or paragraph describing the symptom, the user's experience, expected vs. actual behavior. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — **do NOT refuse plain-language prose**, **do NOT treat the first word of a sentence as a path**, **do NOT ask the user for a folder when prose was given**. Ask only when `$REQ_DIR` is genuinely empty. The codebase the bug applies to is the cwd (a git repo) unless the prose explicitly names another path.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

## Dispatch mode

Per `common-pipeline-conventions` `## Dispatch mode (v1.0.0)`, the selection (env `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` + `claude --version >= 2.1.32` + `--no-teams` flag, also readable from `~/.claude/settings.json`) is computed ONCE — for the bug-fix pipeline, at the top of Phase B−1 — and persisted as `dispatch_mode: "teams"` or `dispatch_mode: "subagents"` to `<workspace>/.architect-team/intake-state.json` (the bug-fix pipeline reuses the main pipeline's `intake-state.json`). Every later phase reads it; the hook scripts branch on it (teams mode = `TaskCompleted` / `TeammateIdle`; subagents mode = `PostToolUse(TaskUpdate)` / `SubagentStop`). The teams-mode primitives (Lead spawns named teammates via the Agent tool with `run_in_background: true`, agent type inherited, `SendMessage` for coordination, shared task list at `~/.claude/tasks/<slug>/`) and the subagents-mode primitives (ephemeral Agent-tool dispatches, fresh context per call, no `SendMessage`, handoff files for coordination) are spelled out in the canonical section — do not re-explain them inline. Wherever this skill body says *"the Lead creates a `<role>` task (teams mode) OR dispatches the `<role>` subagent (subagents mode)"*, the branch is decided by `dispatch_mode`; both halves of the sentence are real, the orchestrator picks one at execution time. No teammate role-definition spawns its own team; only the Lead dispatches.

## Default mode of operation

Same as `architect-team-pipeline` v0.9.20: **drive end-to-end, gates are opt-in for *process* gates, fire for *domain* gates** (per the v0.9.21 carve-out). The bug-fix pipeline's domain gates — fire regardless of `--proposal-first`:

- **Phase B1 ambiguity-escalation question** — when the bug description is genuinely incomplete (no screen named, no steps named, no expected-vs-actual). The agent does NOT guess; it asks. This is part of the deliverable.
- **`needs-clarification` verdict in any phase** — a structured ask to the user is the right move when the work cannot proceed responsibly.
- **`--environment production` escalation** — production deploys are user decisions.

Process gates (proposal-first pause, "do you want me to proceed?", obvious-answer clarifying questions) follow the same opt-in rule as the main pipeline.

## Appearance-change policy (v3.14.0)

A bug-fix run is `strict` by nature: the mandate is the named symptom, and restoring the intended behavior/appearance the bug broke (spec restoration) is in scope — restyling beyond it is not. The fix MUST NOT bundle visual "polish", layout tweaks, or new UI surface the bug report never named; improvement ideas surfaced during the fix are recorded to `<workspace>/.architect-team/appearance-proposals/<run-id>.json` (status `recorded`) and listed read-only in the Phase B7 report — imperative, never interrogative. The `--appearance` flag can widen a run explicitly (`propose` / `innovate`); `appearance_mode` is bound at the top of Phase B−1 into `intake-state.json` alongside the dispatch-mode selection and carried in every spawn brief. Canonical home: `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`.

## Notifications (per-project email events — opt-in, best-effort)

Per `common-pipeline-conventions` `## Notifications wiring convention`, this pipeline emits the five recognized events (`phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, `deploy`) via the notifier CLI at `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`. The discipline is opt-in (gated on `.architect-team-notify.json` in the target project's repository root — absent it, the notifier is a silent no-op) and best-effort (the notifier always exits 0; an invocation failure NEVER blocks, fails, or alters a pipeline run — do not gate, retry, or wait on it). Every invocation uses the polyglot `python3 ... || python ...` form per `common-pipeline-conventions` `## Cross-platform Python invocation`.

**Phase-boundary wiring (`phase_start` / `phase_complete`) — applies to every B-phase.** At the **start of each phase** (Phase B−1, B0, B1, B2, B3, B4, B5, B6, B7, B8), as the first action of that phase, the orchestrator emits a `phase_start` event; at the **end of each phase**, as the last action before moving to the next phase, it emits a `phase_complete` event. Both pass `--phase` with the canonical phase name (e.g., `"Phase B3 — OpenSpec proposal authoring"`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_start --project <name> --phase "Phase B1 — Bug Replication" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_start --project <name> --phase "Phase B1 — Bug Replication"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_complete --project <name> --phase "Phase B1 — Bug Replication" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" phase_complete --project <name> --phase "Phase B1 — Bug Replication"
```

The remaining three events (`issue_discovered`, `git_commit`, `deploy`) are wired at specific phase steps marked inline below:

- **`issue_discovered`** — fires at **Phase B6** when the `qa-replayer` returns `bug-still-present` and the orchestrator writes a fresh solution requirement back to the loop. `--summary` carries the SR's failure-mode description (verbatim from the qa-replayer's verdict's `symptom_check.gap_if_not_gone` field).
- **`git_commit`** — fires at **Phase B8** immediately after the bug-fix commit succeeds, with `--commit <SHA>`. Same wiring point as the main pipeline's Phase 8 commit.
- **`deploy`** — fires at **Phase B5** when the fix is deployed to the dev environment, with `--layer <layer>` (e.g., `frontend` / `backend` / `fullstack`). The bug-fix pipeline is "deploy-by-default" (per Phase B5); production deploys are gated on the `--environment production` escalation and the user's explicit go, so a `--environment production` invocation emits this notification only AFTER the user confirms.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

Per `common-pipeline-conventions` `## MemPalace wake-up precondition` (which points at the canonical rule in `mempalace-integration` `## Phase A — Wake-up at pipeline start`): when the bug-fix pipeline is invoked DIRECTLY via `/architect-team:bug-fix` (not routed in from the main pipeline's Phase −2), the unscoped wake-up runs as the earliest action of this pipeline — before any subagent dispatch, including the Phase B−1 intake-and-mapping flow. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback), then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. Include the wake-up output verbatim — the bug-fix loop benefits from prior-context recall (past bug-replications mined to `bug-replications`, past QA-replay verdicts mined to `qa-replays`, past architect generalization-audit verdicts mined to `bug-fix-audits`). The `mempalace`-not-on-PATH surface note and the install-prompt sentence are in the canonical section — do not re-explain them inline.

**When the bug-fix pipeline is reached via the main pipeline's Phase −2 routing** (the classifier returned `bug` or `mixed`), the unscoped wake-up has ALREADY run there — this section is a no-op in that case (the carve-out is the bug-fix-specific entry-condition the canonical rule doesn't carry, since it is unique to this pipeline). A SECOND, **wing-scoped** wake-up (`--wing <wing>`) runs from inside Phase B−1A (which reuses `intake-and-mapping`'s Phase −1A flow) once the wing name is discovered, regardless of entry path.

After EVERY background Agent dispatch in this pipeline (Phase B−1 mapping ralph loops, Phase B1 bug-replicator + bug-classifier, Phase B2 backend diagnostic, Phase B3 system-architect, Phase B4 generalization audit, Phase B5 fix-team teammates, Phase B6 qa-replayer, Phase B6b fix-sensibility-checker, Phase B8 doc-updater), route the raw dispatch result through `wrap_agent_result()` from `scripts/setup/agent_resume.py` per `common-pipeline-conventions` `## Background-agent resume discipline` BEFORE treating the work as complete. Truncated / stream-timed-out results auto-resume up to 2 attempts; `resumed_failed=True` surfaces to the user with on-disk artifacts cited.

### In-flight clarification handling (v2.5.0)

If the user injects a message mid-run (after this skill has begun executing any of Phase B−1 → B8) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, the orchestrator MUST treat the message as a **clarification or scope amendment to the IN-FLIGHT bug-fix run** — append it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase (re-run Phase B0 → B1 replication if scope materially shifted; otherwise fold into the next phase's inputs), and continue the pipeline. The orchestrator MUST NOT solve the clarification with tools directly bypassing the pipeline, answer conversationally without folding, spawn a sibling `/architect-team` invocation, or silently ignore. Full rules in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.

## Phase B0.1 — Discipline freshness check (v2.18.0)

Same shape as the main pipeline's Phase 0.1 — invoke `verify-discipline-registry-current` (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the Discipline-freshness row), auto-apply safe disciplines, route the rest as SRs. See `common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)`. Runs AFTER the MemPalace wake-up + entry-condition checks above and BEFORE Phase B−1. Best-effort — a failure of the verify-tool never blocks the bug-fix loop; surface a one-line note and proceed.

## Phase-boundary inbox check (v2.19.0)

Same shape as the main pipeline's `## Phase-boundary inbox check` — at the start of every numbered bug-fix phase (B−1 / B0 / B1 / B2 / B3 / B4 / B5 / B6 / B6b / B7 / B8) AND after every subagent dispatch returns, read the in-flight inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` via `hooks.inflight_inbox.unprocessed_messages`, classify each new message per v2.5.0, mark_processed. Phase B8 invokes the 17th Layer 3 tool `verify-inflight-clarifications-processed` to gate against silently-ignored messages (per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)`, the In-flight inbox row).

See `common-pipeline-conventions/SKILL.md` `## In-flight clarification injection mechanism (v2.19.0)` for the canonical home.

## Phase B−1 — Intake & Mapping (REQUIRED, runs before Phase B0)

Follow the `intake-and-mapping` skill verbatim — same codebase discovery (read `$REQ_DIR/codebases.json` → frontmatter → cwd → ask user); same per-codebase ralph loop with cartographer + route-mapper + 3-reviewer convergence; same map-freshness rules (read `last_mapped` and compare against `git log -1 --format=%cI`; re-derive if stale or if `map_invalidated`); same integration mapping; same MemPalace wake-up + mining.

**The freshness pre-scan is non-negotiable.** A bug fix proposed against a stale map is the second-worst class of bug fix (after one proposed without replication). If the maps are current per the freshness rules, Phase B−1 short-circuits cleanly and the loop moves to B0 quickly.

Per the v0.9.21 Phase −1D step in `intake-and-mapping`: if any frontend codebase is in scope and a low-confidence interaction-intuition union exists at the end of Phase −1, the bulk-verify gate fires before B0. This is a domain gate; it applies here too.

## Phase B0 — Detection & Normalization

Same as `architect-team-pipeline` Phase 0 — `plain` / `openspec` / `superpowers` classification, openspec init if needed, kebab `<bug-slug>` derived from the description.

For `plain` (the common case for a bug report), pick a `<bug-slug>` that names the symptom plainly: `fix-row-delete-button`, `fix-analysis-totals-zero`, `fix-login-redirect-loop`. Avoid generic names (`bugfix`, `quickfix`). The slug names the OpenSpec change AND the eventual feature branch.

The change-name convention: bug-fix changes get the same `architect-team/<bug-slug>` feature-branch pattern; the OpenSpec change lives at `openspec/changes/<bug-slug>/`.

## Phase B1 — Bug Replication

The Lead creates a `bug-replicator` task in the shared list (teams mode) OR dispatches the `bug-replicator` subagent (subagents mode), one per affected codebase (usually just one). Inputs to the agent:

- The bug description (the source prose OR the bug-report artifacts).
- The relevant CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP / INTERACTION_INTUITION_MAP (when present).
- The dev-environment URL(s) from the target project's `design.md` `## Dev Environment` section.

The agent's process (apply `superpowers:systematic-debugging` throughout — replicate and root-cause before any fix is proposed, per `## Plugin prerequisites (v3.9.0)`):

1. **Identify the failing path** from the description + maps. For frontend bugs: which route, which component, which interactive element. For backend bugs: which endpoint, which payload shape, which side-effect.
2. **Write the replication artifact** at the appropriate location in the target codebase:
   - Frontend bugs → a Playwright user-flow per `playwright-user-flows` at `tests/e2e/bug-fix-<bug-slug>/<flow>.spec.ts` (or the codebase's e2e convention). The flow exercises the real UI path — real `page.click`, real `page.fill`, real `page.waitFor` — against the live dev URL.
   - Backend bugs → a script (Python with `httpx`, or Node, per the target's conventions) at `tests/bug-fix-<bug-slug>/<script>.py` that calls the failing endpoint(s) against the live dev API and asserts the failing condition.
3. **Run the artifact** against the live dev environment. Capture the output verbatim. **The artifact MUST currently fail** — that is the replication. If it passes (the bug isn't actually present), exit with `could-not-reproduce`.
4. **Report a verdict**: one of `reproduced` (bug confirmed; proceed to B2), `could-not-reproduce` (the bug isn't present; escalate to the user with the evidence — the bug may already be fixed, or the description may be incomplete), `needs-clarification` (the description is genuinely ambiguous; emit a structured question and pause).

**The canonical ambiguity-escalation question (Phase B1):**

*"I need a bit more detail to replicate this — can you describe how you experienced the bug? Specifically: (1) what page or screen were you on, (2) what did you click / type / submit, (3) what did you expect to see, and (4) what actually happened? A screenshot or video would help if you have one."*

The replicator does NOT guess at the steps. A guessed replication that doesn't reproduce the bug burns an iteration; an honest `needs-clarification` saves the loop.

**Hard rule:** Phase B1 does NOT proceed to B2 without a `reproduced` verdict. "We'll figure it out at QA" is forbidden.

**Verdict file mandate (v0.9.36).** The orchestrator writes a structured verdict file at `<cwd>/.architect-team/bug-fix/<bug-slug>/b1-replication-verdict.json` immediately after the `bug-replicator` returns. The `pipeline-completion-audit` hook checks for this file's existence and verdict. Schema:

```json
{
  "phase": "B1",
  "bug_slug": "<bug-slug>",
  "verdict": "reproduced" | "could-not-reproduce" | "needs-clarification",
  "artifact_paths": ["<path-to-playwright-flow>", "<path-to-backend-diagnostic>"],
  "artifact_executed": true,
  "failing_output_captured": true,
  "dev_environment_url": "<the URL the artifact ran against>",
  "timestamp": "<ISO 8601>"
}
```

`artifact_executed` and `failing_output_captured` are both **mandatory `true`** for a `reproduced` verdict — the replicator must have actually run the artifact (not just written it) and captured the verbatim failing output (not described it). A verdict file with `artifact_executed: false` is structurally invalid and the completion audit blocks on it. **This is the enforcement mechanism for testing**: the pipeline cannot complete without proof that the replication test was actually executed against the live dev environment.

## Structured bug-isolation (v3.8.0)

Closes REQ-DIAG-01 / REQ-DIAG-02 / REQ-DIAG-05 (the P0 "quick wins" of the CT6 Lineage & Logical Bug-Isolation Upgrade — `docs/LINEAGE_UPGRADE_REQUIREMENTS.md`). The historical failure: diagnosis discovered the relevant code path *while theorizing* — a deep-analysis subagent was dispatched before anyone had frozen the endpoint scope or established, with an executed call, whether the defect even lived on the API side. Cheap, decisive checks were skipped in favor of expensive reasoning. v3.8.0 inserts a **structured pre-diagnosis sequence** so the cheap checks always precede deep analysis.

### The mandatory order

The bug-fix pipeline's pre-diagnosis order is, explicitly:

**replicate → scope-isolate → light-discriminant → call-map → diagnose**

- **replicate** — Phase B1 (already executed above): the symptom is reproduced against the live dev environment and the failing output is captured.
- **scope-isolate** — the scope-isolation gate below (REQ-DIAG-01): freeze the exact endpoint set the reproduced failure touches.
- **light-discriminant** — the executed FE/API discriminant below (REQ-DIAG-02): one real authenticated call decides FE-bug vs API-bug BEFORE any code is read deeply.
- **call-map** — the call-map step below (REQ-DIAG-03 placeholder; full CDLG extraction is P2): lay out the in-scope endpoint's handler chain before forming hypotheses.
- **diagnose** — only now does deep analysis run: Phase B3's proposal authoring + (when the root cause is unclear) the `diagnostic-research-team` dispatch, **bounded to the frozen scope set**.

**Out-of-order execution is a discipline failure (REQ-DIAG-05).** Running deep diagnosis — dispatching a `diagnostic-researcher`, opening the handler source to theorize — BEFORE the scope artifact and the discriminant verdict have been recorded is a gate failure, not a shortcut. The run ledger MUST show the cheap checks (scope, discriminant) completed and recorded BEFORE any deep-analysis subagent dispatch. This is the run-order analog of the v0.9.36 *"testing must be EXECUTED, not described"* discipline: the cheap checks are not optional reasoning steps, they are recorded artifacts that gate what comes next.

### Scope-isolation gate (REQ-DIAG-01)

Immediately after the B1 `reproduced` verdict, BEFORE B2's artifact promotion, the orchestrator (or the `bug-replicator`, whose evidence the orchestrator records) enumerates the **pages** involved in the reproduced failure and subsets to the **exact endpoints those pages call**. This is frozen as a scope artifact at:

```
<workspace>/.architect-team/bug-isolation/<bug-slug>/scope.json
```

Schema:

```json
{
  "phase": "scope-isolation",
  "bug_slug": "<bug-slug>",
  "pages": ["<route or page url the failure was reproduced on>", "..."],
  "endpoint_set": ["GET /api/...", "POST /api/...", "..."],
  "derived_from": ["INTEGRATION_MAP", "INTERACTION_INTUITION_MAP", "ROUTE_MAP", "the captured B1 network log"],
  "timestamp": "<ISO 8601>"
}
```

`pages[]` is the set of routes/screens the reproduced failure exercised; `endpoint_set[]` is the EXACT set of endpoints those pages call (read from the captured B1 Playwright network log + the INTEGRATION_MAP / INTERACTION_INTUITION_MAP priors). **Every later diagnostic step is BOUNDED to `endpoint_set`** — the discriminant calls only in-scope endpoints, the call-map traces only in-scope handlers, the diagnosis cites only in-scope code. A diagnostic step that reaches for code outside the frozen endpoint set is rejected; if the failure genuinely implicates an out-of-scope endpoint, the scope artifact is re-frozen with that endpoint added (an explicit, recorded widening) rather than silently followed.

### Light FE/API discriminant — EXECUTED, not reasoned (REQ-DIAG-02)

Before ANY deep code analysis, make a **real authenticated call against the live dev environment** — the same live-dev discipline as B1/B2 — to the in-scope endpoint(s), **as the affected user**, and assert whether correct data is returned. This single executed call branches the diagnosis: a 4xx/5xx or a correct-shape-but-wrong-data response points at the API; a 2xx returning correct data (while the UI still shows the symptom) points at the frontend. Record the verdict at:

```
<workspace>/.architect-team/bug-isolation/<bug-slug>/discriminant.json
```

Schema:

```json
{
  "phase": "light-discriminant",
  "bug_slug": "<bug-slug>",
  "endpoint": "<the in-scope endpoint the call hit>",
  "fe_api_verdict": "frontend-bug" | "api-bug" | "inconclusive",
  "request": {"method": "GET", "url": "<dev URL>", "auth": "<affected-user session>"},
  "response": {"status": <int>, "body_excerpt": "<first N chars / relevant fields>"},
  "executed": true,
  "timestamp": "<ISO 8601>"
}
```

`fe_api_verdict` is one of `frontend-bug` (the API returned correct data; the defect is in the client's rendering / state / wiring), `api-bug` (the API returned wrong/missing data or errored), or `inconclusive` (the call could not decide — e.g. the endpoint needs un-synthesizable state; the call-map + deep diagnosis then arbitrate). The verdict MUST be backed by the captured request/response (status + body excerpt) — `executed: true` is mandatory.

**A code-read verdict does NOT satisfy this gate.** *"I read the handler and it looks like the frontend isn't sending the right param, so this is a frontend bug"* is the **"verified by reading the code"** anti-pattern — the exact failure mode v0.9.36's *"testing must be EXECUTED, not described"* discipline forbids. The discriminant is an executed call with captured evidence or it has not happened. The `fe_api_verdict` recorded here is later compared against the layer the fix actually landed in (the `wrong_layer` metric, REQ-SAFE-02 — see `common-pipeline-conventions` `## Run metrics + success measurement (v3.8.0)`); a discriminant that "said FE" but whose fix landed in the API is a measured wrong-layer event, which is only meaningful because the discriminant was a real executed call rather than a guess.

### Call-map step (REQ-DIAG-03 — placeholder hook)

Before hypothesis formation, lay out the in-scope endpoint's recursive call pattern (endpoint → functions → sub-functions). This is the forward-reference seam to the **Code & Data Lineage Graph (CDLG)** and its `ENDPOINT_TRACE_MAP.md` / `lineage-graph.json` extraction (REQ-CDL-06, roadmap phase **P2** — not implemented here):

> **Call-map step:** consume the endpoint trace / CDLG call-map when available (REQ-CDL-06, P2); until then, trace the in-scope endpoint's handler chain manually, bounded to the scope set.

This section is a placeholder hook only — it does NOT implement graph extraction. When the CDLG ships, this step reads the runtime-verified call tree for the in-scope slice; until then the diagnosis traces the handler chain by hand, strictly within `endpoint_set`. Either way the call-map precedes diagnosis, so hypotheses are reasoned against a laid-out structure rather than discovered mid-theorizing.

### Wiring into the phase order

The structured sequence threads the existing phases without renumbering them: **B1 replicate** produces the failing artifact; the **scope-isolation gate** and the **executed light-discriminant** run between B1 and B2 (recorded under `.architect-team/bug-isolation/<bug-slug>/`); **B2** promotes the artifacts; the **call-map step** runs before **B3**'s proposal authoring; **B3/B3b diagnose** (proposal + the `diagnostic-research-team` dispatch when the root cause is unclear) is the deep-analysis step that all of the above gate, and it is bounded to the frozen scope set throughout.

## Phase B2 — Reproduction-artifact promotion + backend diagnostic

The replication artifact from B1 IS the regression test — this is `superpowers:test-driven-development` in its purest form (the failing test exists before the fix code is written, per `## Plugin prerequisites (v3.9.0)`). Move it to its permanent location in the target codebase's test directory if it isn't already there. The pair the QA replayer will run at B6:

- **Frontend bug:** the Playwright user-flow AT `tests/e2e/bug-fix-<bug-slug>/<flow>.spec.ts` PLUS a **backend diagnostic test** the same agent (still `bug-replicator`) authors next. The backend diagnostic exercises the SAME flow from the backend's view — it calls the endpoint(s) the Playwright flow drove and asserts the data-layer outcome (the row was actually deleted from the DB, the user's permission grant actually persisted, etc.). The backend diagnostic catches a regression that the Playwright flow alone might miss (a UI that appears to succeed but doesn't actually update the data).
- **Backend-only bug:** the backend script alone suffices.

Both artifacts must currently fail (they are reproducing the bug). Phase B6 will re-run them post-fix and require them to pass — that is the regression contract.

**Selector witness assertions (v0.9.32) — MANDATORY in every Playwright artifact.** The `bug-replicator` instruments every action-call selector (`page.click`, `page.fill`, `page.selectOption`, `page.press`, `page.setInputFiles`, `page.check`, `page.hover`, `page.dragTo`) with witness assertions immediately preceding the action — `await expect(locator, '<author intent message>').toBeVisible()` + `.toBeEnabled()` + a disambiguating role / attribute check when the text match is permissive. The witness produces an EARLY, self-diagnosing failure when a selector resolves wrong — preventing the wasted B3→B4→B5→B6 cycle when a `text=Alabama` grabs a state filter instead of the intended tech name (the v0.9.30 production case). The full pattern + the three failure modes the witness covers live in `agents/bug-replicator.md`. The witness is the structural complement to Phase B6's code-path execution witness (v0.9.31): B2 catches the failure at AUTHORING time, B6 catches it at QA-replay time — both gates are needed because either alone leaves residual failure modes.

**Email-aware reproduction (v0.9.34).** When the bug involves an email-dependent flow (invite link broken, password-reset email missing, notification click-through fails), the `bug-replicator` activates the `email-testing` skill discipline automatically. Phase E1 detects email surface in the bug's failing path; E2 provisions Mailpit as the SMTP trap; E3 captures the sent email and classifies every link; E4 follows every link in Playwright and completes the flow each link initiates. The email capture + link-follow steps persist in the `.spec.ts` replication artifact — they are part of the regression test the `qa-replayer` re-runs at Phase B6. The agent reads the email template source BEFORE triggering the send so it understands the email's purpose and can make purpose-informed assertions. See `email-testing` skill for full discipline.

Persist the artifacts under `<target-codebase>/tests/bug-fix-<bug-slug>/` (or the codebase's convention) and stage them; they become part of the same commit the fix lands in at Phase B7.

## Phase B3 — OpenSpec proposal authoring

Author a slim OpenSpec change at `openspec/changes/<bug-slug>/`. Apply `superpowers:brainstorming` to settle the fix's design intent before drafting (per `## Plugin prerequisites (v3.9.0)`); when the root cause is unclear, the `diagnostic-research-team` dispatch carries `superpowers:systematic-debugging`. The artifact chain is the same as a feature change: `proposal.md`, `design.md`, `specs/<cap>/spec.md`, `tasks.md`, `coverage-map.json`. The proposal:

- **Cites the replication evidence verbatim.** Quote the artifact's failing output as the source of the failure-mode statement.
- **Names the root cause** if known from the replication (a missing await, a broken contract assumption, a stale cached value). If the root cause is genuinely unclear after the replication, the Lead routes through `diagnostic-research-team` per the main pipeline's Phase 3b discipline — same flow, same plan, same architect-review gate (the Lead creates 3 `diagnostic-researcher` tasks in the shared list in teams mode, or dispatches 3 `diagnostic-researcher` subagents in parallel via a single Agent-tool batch in subagents mode; no researcher spawns the architect — only the Lead does).
- **Proposes the fix.** The fix targets the root cause, not the symptom. State the class of bug being addressed (not just the failing input).
- **Includes Reuse Decisions** per `reuse-first-design` for any new file the fix introduces. A bug fix that extends an existing function gets a one-line Reuse Decision; a bug fix that needs a new module gets a full one.

Run `openspec validate --all --strict`. **Do NOT delegate to `architect-team-pipeline` Phase 1's validation gate** — its conditions are shaped for feature work (authoring NEW Playwright user-flows, NEW dev-API integration criteria, NEW Reuse Decisions for new files) and trip on bug-fix-shaped work (the replication artifact from B2 IS the Playwright flow; the fix typically extends existing handlers, not new ones). v0.9.25 gave the bug-fix pipeline its OWN slim planning-validation gate, named below.

### Bug-fix planning-validation gate (Phase B3 exit criterion)

The gate loops until ALL seven conditions below are true. Each iteration refines `proposal.md` / `design.md` / `coverage-map.json` and re-runs the gate; the gate exits when all seven pass, and Phase B4 (Bug-Fix Generalization Audit) runs next.

1. **OpenSpec validates.** `openspec validate --all --strict --json` reports `valid: true` with no errors.
2. **Every artifact is done.** `proposal.md`, `design.md`, `specs/<cap>/spec.md`, `tasks.md` all report `status: done` per `openspec status --change <bug-slug> --json`.
3. **The coverage map has at least one source requirement** — the bug description itself (as `REQ-001` typically).
4. **The coverage map records the replication artifact paths from Phase B2 as the verification target:**
   - For `frontend` or `both`-layer bugs: BOTH the Playwright user-flow path (`tests/e2e/bug-fix-<bug-slug>/<flow>.spec.ts` or equivalent) AND the backend diagnostic script path (`tests/bug-fix-<bug-slug>/<script>.py` or equivalent) are recorded as `acceptance_criteria` entries.
   - For `backend`-only bugs: the backend script path is recorded as the `acceptance_criteria` entry.
5. **Reuse-first compliance.** Every NEW file `design.md` introduces has a Reuse Decision citing CODEBASE_MAP.md per `reuse-first-design`; every EXISTING file the fix extends has a one-line acknowledgment of which existing function/handler/route it extends (the bug-fix typical *"extends `<function>` at `<path>:<line>`"* pattern). A bug fix that touches no new files and only extends existing handlers satisfies this trivially.
6. **The proposal's WHY cites the replication evidence verbatim.** `proposal.md`'s `## Why` section quotes the artifact's verbatim failing output (per Phase B2's evidence requirement). A bug-fix proposal without quoted evidence is fiction.
7. **The proposed fix is *class*-scoped in the design.** `design.md`'s `## Proposed fix` section describes the *class* of bug the fix addresses, not just the specific failing input. (Note: this is the *attempt* check — the architect's Bug-Fix Generalization Audit at Phase B4 is the rigorous verdict. B3's gate confirms the proposal *tries* to reason at the class level; B4 confirms the reasoning is correct.)

**Auto-mine** the validated coverage map: `mempalace --palace <palace> mine "openspec/changes/<bug-slug>/coverage-map.json" --wing <wing>`.

**Why not reuse Phase 1's gate?** Phase 1's loop has feature-shaped conditions like *"Any front-end requirement lacks an explicit Playwright user-flow specification (URL or route, login state, selectors, input data, expected visible assertions)"*. For a bug fix, the Playwright flow IS the replication artifact from B2 — already authored, already failing. Forcing the same loop conditions trips the bug-fix path on either (a) a literal-reading-fail (the Playwright spec doesn't exist as new authoring), or (b) a liberal-reading-pass (the orchestrator handwaves *"the replication artifact IS the criterion"*). The first burns iterations; the second is fragile. The bug-fix gate names its conditions in bug-fix terms, so the check is exact.

## Phase B4 — Bug-Fix Generalization Audit

The Lead creates a `system-architect` task in **Bug-Fix Generalization Audit** mode (teams mode) OR dispatches the `system-architect` subagent in that mode (subagents mode). Inputs:

- The source description (the bug report).
- The replication evidence (the artifact paths + their failing output).
- The proposal + `design.md` + the diff of the proposed fix (when the fix is implementation-ready) OR the spec'd approach (when the fix isn't yet implemented).
- The relevant CODEBASE_MAP + INTEGRATION_MAP.

The audit's verdict is one of:

- **`pass`** — the fix addresses the *class* of bug and is correctly scoped. No special-casing of the failing input. The architect cites the class explicitly: *"This fix addresses the class of bugs where a soft-delete is treated as a hard-delete by the row-action handler; the change to the handler correctly affects every row, not just the one the user reported."*
- **`needs-generalization`** — the proposal special-cases the failing input. The architect cites the offending pattern (the literal user-id, the hard-coded category, the targeted conditional) and describes the underlying class of bug. The proposal returns to authoring (back to Phase B3) for revision.
- **`needs-replacement`** — the proposed approach is wrong (treats a symptom while leaving the root cause; uses the wrong layer; introduces a worse defect). The architect cites a better alternative; back to B3.

**The user-authorized override.** If the source description explicitly authorized a targeted fix — phrasings like *"hard-code it for now"*, *"just for this one user"*, *"hotfix before the demo"*, *"patch it just temporarily"* — the architect records the authorization verbatim in the verdict and lets a targeted fix proceed. The architect does NOT extrapolate authorization from silence; a description that doesn't address generalization is NOT authorization. The audit verdict's reasoning field carries the authorization quote.

**Genuinely-narrow classes are NOT generalization gaps.** A bug whose class is exactly one input (a singleton config issue, an enum value that doesn't exist anywhere else, a one-time data fix) is general for its class. The audit's reasoning field cites the class size when relevant.

The audit verdict gates Phase B5: the implementing team does NOT touch code until the verdict is `pass`.

## Phase B5 — Implement + deploy to dev

The Lead creates ONE focused fix-team task in the shared list (teams mode) OR dispatches ONE focused fix-team subagent (subagents mode) — a `frontend` or `backend` agent depending on layer; for `both`-layer bugs, the Lead sequences them or runs them in parallel with non-overlapping file scope per the main pipeline's Phase 2 rules — usually a bug fix is single-layer or has a clear primary. Brief includes:

- The OpenSpec change name + the relevant tasks from `tasks.md`.
- The proposed approach from `design.md` (architect-approved at B4).
- The replication artifacts (the failing flow / script) as the verification target.
- The acceptance criterion: the replication artifacts pass when re-run against the deployed fix.

The team writes Phase 3 review-gate evidence per the existing schema (v7) — the 17 required fields including `real_not_stubbed`, `tests`, `integration_testing_review`, `test_completeness_review`, `demo_artifact`, `reuse_compliance`, `visual_fidelity_review` (for frontend touches), `ui_interaction_review`, and the 5 Verified Agent Output fields (`oracle_match_review` / `baseline_clean_review` / `no_fake_data_review` / `adversarial_review` / `skill_invocation_audit`). The `task-reviewer` independently re-reviews and writes the `independent_review` block; only its `verdict: pass` opens the Phase 3 gate. (Same gate as the main pipeline — bug fixes don't skip review-gate evidence.)

**After local tests pass, deploy to the dev environment.** Read the target project's `design.md` `## Dev Environment` section for the deploy command (`npm run deploy:dev`, `make dev-deploy`, `gh workflow run ...`, etc.) and the dev URL. Run the deploy, then poll the dev environment's health endpoint or build-status URL with a tight bounded in-turn loop until builds are green. A failed build is a Phase B5 escalation that routes back to the implementing team for diagnosis (probably a build-config issue, a missing env var, a dependency drift) — it is NOT a QA-replay failure. The bug-fix loop must never confuse a deploy failure with a fix failure.

**The `--environment production` exception.** If the run was invoked with `--environment production` (or the user's prose names the target as production), the orchestrator escalates a structured question:

*"This run is targeting production. A production deploy is your decision, not mine. The fix is implemented and verified locally; please confirm: (a) deploy to production now, (b) deploy to a staging environment first, or (c) hold for manual review."*

Phase B5 does NOT auto-deploy to production. The user's answer is the green light.

**Notification (best-effort, per `## Notifications`):** if the target project supplies `.architect-team-notify.json`, the orchestrator emits a `deploy` event with `--layer <layer>` (e.g., `frontend` / `backend` / `fullstack`) at the start of the dev deploy. Invoke from the target project's root and proceed immediately regardless of the notifier's outcome:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer>
```

This `deploy` invocation is best-effort and NEVER blocks, fails, or delays the dev deploy — a notifier failure does not affect the deploy or the QA replay.

## Phase B6 — QA replay against live dev

The QA replay is this pipeline's `superpowers:verification-before-completion` gate — evidence (the originating symptom is gone end-to-end against the live dev environment) before any claim that the bug is resolved, per `## Plugin prerequisites (v3.9.0)`.

The Lead creates a `qa-replayer` task in the shared list (teams mode) OR dispatches the `qa-replayer` subagent (subagents mode). Inputs:

- The path(s) to the reproduction artifact(s) from B2.
- The dev environment URL(s).
- The bug description (for the symptom-gone-end-to-end verification).
- **The fix's git diff** (v0.9.31) — the unified diff of the fix's commit vs. its parent, used in the code-path execution witness (Step 4.5) to identify the buggy handler(s) and their invocation fingerprints.

The replayer's process:

1. Re-run the Playwright flow against the live dev environment, verbatim (no edits to the flow). **Capture the Playwright trace with network log (`trace: 'on'`)** — the network log is the witness data the code-path gate consumes at step 5.
2. Re-run the backend diagnostic script against the live dev API, verbatim (no edits). **Capture the dev API access log for the test window** — same purpose.
3. Compare the output against the original failing output captured in B1.
4. Verify the originating symptom — what the USER experienced — is gone end-to-end. NOT just "the test passes" — the failure mode is no longer reproducible.
5. **Code-path execution witness (v0.9.31)** — cross-check the fix's git diff against the captured network log + access log. For each handler the fix touched, determine an invocation fingerprint (the endpoint the handler calls, a DOM state-change unique to the path, a console sentinel) and assert at least one fingerprint was observed during the test. A test that passes but never invoked the fix's handler (selector misidentification, precondition skip, sibling-handler entry) is a `test-did-not-exercise-fix` verdict — distinct from `bug-still-present`. Origin case (v0.9.30 production):

   > *"My Playwright never actually completed a Schedule click. The test's tech-selector grabbed 'Alabama' (a state filter) instead of a real tech, so the Schedule button stayed disabled — and I declared REQ-001 PASS based only on the Unschedule path's panel-stayed-open assertion. The Unschedule path goes through `handleUnschedule`; the Schedule path goes through `handleSchedule` where the fix lives. The test never invoked `handleSchedule` at all."*

   The full witness procedure (handler identification, fingerprint selection, trace/log capture, cross-check) lives in the `qa-replayer` agent body (`agents/qa-replayer.md` Step 4.5). The orchestrator does NOT replicate it here — the agent is the source of truth.

The replayer's verdict is one of:

- **`bug-resolved`** — the artifacts pass, the originating symptom is gone, AND the code-path witness verdict is `pass` (at least one fix-touched handler was observably invoked) or `n/a` (the fix's diff has no observable handlers — comments / imports / types only). Proceed to B6b (sensibility check) → B7 (archive).
- **`bug-still-present`** — the artifacts fail (or pass technically but the symptom is still observable) AND the code-path witness is `pass` or `n/a` (the test DID exercise the fix's handler — the fix just isn't doing what it should). The replayer writes a solution requirement back to the orchestrator with the new evidence (the current failing output, the differences from the pre-fix failing output). The loop returns to **B3** — a FRESH OpenSpec proposal authored on the new evidence (not an amendment to the previous proposal; the previous proposal is closed and a new one opened to keep the audit trail clean). **The FIX is on trial here**, not the test. **Notification (best-effort, per `## Notifications`):** the orchestrator emits an `issue_discovered` event with the SR's failure-mode description as `--summary` immediately before re-entering B3. It invokes the notifier from the target project's root and proceeds immediately regardless of the notifier's outcome:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the SR's failure-mode description>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the SR's failure-mode description>"
  ```

  This `issue_discovered` invocation is best-effort and NEVER blocks or alters the bug-fix loop — a notifier failure does not stop the next iteration. The loop continues.
- **`test-did-not-exercise-fix`** (v0.9.31) — the deploy applied, the artifacts technically passed, the symptom-check looked ok, BUT the code-path witness verdict is `fail` — at least one fix-touched handler with a derivable fingerprint was `not_invoked`. The fix may be correct or wrong; we don't know yet because the test didn't actually exercise it. The replayer writes a solution requirement with `origin.kind: "test-coverage-gap"` and a `gap` field listing every `not_invoked` handler + the likely cause (selector misidentification / precondition skip / sibling-handler entry — directly from the agent's `gap_if_failed` field). The orchestrator routes back to **Phase B2** (re-author the reproduction artifact with corrected selectors + explicit witness assertions; the architect's proposal at B3 is NOT necessarily wrong — the test is). After re-authoring, B3 (re-validate the proposal against the new artifacts) → B4 → B5 → B6 again. **The TEST is on trial here**, not the fix. Emits the same `issue_discovered` notification as `bug-still-present` (with `--summary` carrying the witness gap description) so subscribers see iteration churn regardless of which axis fails. Recurrence detection still applies — when `test-did-not-exercise-fix` recurs on the same bug (e.g. 3 consecutive verdicts), the loop does NOT stop: it continues from a DIFFERENT angle (re-route the re-authoring through `diagnostic-research-team` for a deeper selector/witness analysis, broaden the artifact, try an alternate gesture strategy) and surfaces the recurrence loudly. If the artifact genuinely needs user-provided element IDs that only the owner can supply, that specific required input is surfaced via the required-input marker while the run keeps working everything else — never a give-up. Per `common-pipeline-conventions` `## Unbounded solving discipline`.
- **`env-failure`** — the artifacts couldn't run (the dev environment is down, the deploy didn't apply, the browser is mis-configured). Routes to the implementing team for env diagnosis, NOT to the architect. The env issue must be resolved before re-running the replay — but the fix isn't on trial; the env is.

**Loop bounds (v3.8.0 — none):** the bug-fix loop is UNBOUNDED — it runs until the symptom is gone end-to-end, with no iteration ceiling (most bug fixes converge in 1-3 iterations, but the loop never aborts on count). The `dev_loop_iterations` counter in `intake-state.json` increments every B3 → B6 cycle purely as an observability signal, never as a stop condition. Recurrence detection still applies: a fix that keeps re-breaking the same symptom (or the same proposal landing 3 times) does NOT stop — the loop continues from a DIFFERENT angle (re-route through diagnostic-research, broaden scope, alternate strategy) and surfaces the recurrence loudly. Per `architect-team-pipeline`'s `## Run-state: unbounded solving, concurrency, required-input gates`.

**Verdict file mandate (v0.9.36).** The orchestrator writes a structured verdict file at `<cwd>/.architect-team/bug-fix/<bug-slug>/b6-qa-replay-verdict.json` immediately after the `qa-replayer` returns (overwritten on each B6 iteration — only the final verdict matters for the completion audit). The `pipeline-completion-audit` hook checks for this file's existence and verdict. Schema:

```json
{
  "phase": "B6",
  "bug_slug": "<bug-slug>",
  "verdict": "bug-resolved" | "bug-still-present" | "test-did-not-exercise-fix" | "env-failure",
  "artifacts_rerun": ["<path-to-playwright-flow>", "<path-to-backend-diagnostic>"],
  "artifacts_executed_against_live_dev": true,
  "symptom_gone_end_to_end": true,
  "code_path_witness_passed": true,
  "dev_environment_url": "<the URL the artifacts ran against>",
  "iteration": <integer, 1-based>,
  "timestamp": "<ISO 8601>"
}
```

`artifacts_executed_against_live_dev` is **mandatory `true`** for a `bug-resolved` verdict — the replayer must have actually re-run the artifacts against the deployed dev environment (not just read them, not just described the expected outcome, not just run them locally). `symptom_gone_end_to_end` and `code_path_witness_passed` must also be `true` for `bug-resolved`. A verdict file where ANY of these three fields is `false` on a `bug-resolved` verdict is structurally invalid and the completion audit blocks on it. **This is the enforcement mechanism for QA testing**: the pipeline cannot complete without proof that the fix was actually verified against the live dev environment.

### Phase B6 Verification-Claim Audit (v2.2.0)

After the qa-replayer returns its verdict and BEFORE Phase B6b runs, the orchestrator invokes the v2.2.0 Layer 3 tool `verify-live-verification-claim` against the qa-replayer's `verification_artifact` + `bug_description` blocks. This is the structural gate that catches the 3 named failure modes the qa-replayer's self-audit (per `agents/qa-replayer.md` `## Verification-Claim Audit (v2.2.0)`) is supposed to surface.

Invocation:

The interpreter is selected ONCE via `$(command -v python3 || command -v python)` (the v2.16.0 detect-once form) and the script is anchored with `${CLAUDE_PLUGIN_ROOT}` so it resolves regardless of the install location — never a hardcoded plugin-cache path:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-live-verification-claim \
  --artifact "<cwd>/.architect-team/qa-replays/<bug-slug>/verification-artifact.json" \
  --bug "<cwd>/.architect-team/qa-replays/<bug-slug>/bug-description.json" \
  --out "<cwd>/.architect-team/vao-verdicts/<bug-slug>-live-verification.json"
```

The tool's verdict — `valid: true|false` with named severity gaps — IS the authoritative gate:

- **`valid: true` AND qa-replayer verdict is `bug-resolved`** → accept; proceed to B6b sensibility check → B7 archive.
- **`valid: false` AND qa-replayer verdict is `bug-resolved-verification-suspect`** → the qa-replayer correctly self-flagged. Route to **Phase B2 re-replication** with the suspect mode as input:
  - `gesture-substitution` → re-author the reproduction artifact with the correct user gesture (NOT a corner-click or backdrop selector).
  - `self-verification-loop` → re-author the test such that its creation predates the fix OR its assertion does NOT mirror any substring from the fix's git diff.
  - `prefill-masking` → re-author the setup to drive the test to the bug-exposing state (blank matter, navigate to a genuinely-blank step).
- **`valid: false` AND qa-replayer verdict is `bug-resolved`** → CONFLICT. The qa-replayer's self-audit missed what the tool caught. Re-route to deeper diagnosis and re-replication; if the gap genuinely needs an owner decision the orchestrator can't make, surface it via the required-input marker per `## Run-state: unbounded solving, concurrency, required-input gates` (write `.architect-team/escalation-pending.md` with the conflict report) while continuing all other work; the owner reviews the gap between the qa-replayer's self-audit and the tool's deterministic check before any further routing.
- **`valid: true` AND qa-replayer verdict is `bug-resolved-verification-suspect`** → CONFLICT in the other direction (the qa-replayer was more conservative than the tool). Surface the conflict but DEFAULT to the qa-replayer's more conservative verdict — route to Phase B2 re-replication with the suspect mode. The tool's `valid: true` may be a false negative on the tool's heuristics; the agent's self-audit may have caught something the tool's static rules don't see (a novel gesture-substitution shape, e.g.).

The schema v7 evidence file's optional `live_verification_review` field MUST cite this verdict path (`live_verification_review: {verdict: "pass" | "fail", verdict_path: "<vao-verdicts/<bug-slug>-live-verification.json>"}`). If the qa-replayer's `verified_live: true` is claimed in evidence, the schema v7 hook requires the field to be present and non-`fail`.

## Phase B6b — Logical Sensibility Check (v0.9.29)

After Phase B6 returns `bug-resolved` and BEFORE Phase B7's archive, the orchestrator runs a logical sensibility check on the impact set of the fix. Closes a real-world gap surfaced by user feedback:

> *"Why am I seeing 'Sign-in is unavailable — the authentication service is not configured for this build' when it clearly is? How did this make it out of your fix module and why didn't you catch this. The fix correctly routes Sign Back In to /login, but the deployed bundle is hermetic (no VITE_* baked), so the LoginScreen shows 'auth-unavailable.' There needs to be a post deployment check for sensibility on all elements touched."*

B6's QA-replay verifies the ORIGINAL symptom is gone (clicking Sign Back In routes to `/login` — necessary). The user's experience was still broken because `/login` itself rendered "auth-unavailable" — the fix didn't break the route, but the route's destination was broken independently and the QA-replay's narrow scope didn't catch it. B6b widens the verification: the agent reads the fix's git diff, computes the **impact set** (changed files + their importers + nav destinations + endpoints), and runs minimal Playwright sensibility flows on each impact-set item against the deployed dev environment.

**Why a new phase, not an enhancement to B6:** B6's `qa-replayer` runs the SPECIFIC reproduction artifact from B2. Its scope is intentionally narrow — "is the user's reported symptom gone?" Widening B6 would muddy that contract. B6b adds a separate phase + a separate agent (`fix-sensibility-checker`) so each role's responsibility stays crisp.

### Process

1. **Compute the impact set.** The orchestrator (or the dispatched `fix-sensibility-checker` agent — the canonical impact-set computation is in the agent body's `## Impact-set computation` section) reads `git diff <merge-base>..<fix-commit-sha> --name-only` and classifies each changed file (UI component / page / API endpoint / style / config). For each changed file, the agent expands to importers (one level — `git grep` for the file's import paths) + nav destinations (for changed pages — `<Link to=` / `router.push(` / `navigate(` patterns) + endpoints (for changed API handlers).
2. **The Lead creates a `fix-sensibility-checker` task in the shared list (teams mode) OR dispatches the `fix-sensibility-checker` subagent (subagents mode)** with the impact set + the deployed dev URL + the credentials env-var.
3. **The agent authors minimal Playwright sensibility flows per impact-set item.** Each flow is small (5-10 lines): navigate to the page / load the component / call the endpoint, and assert it renders without an error banner ("auth-unavailable", "service-unavailable", "configuration-missing", "could not load", "500", "404"), without console errors, without broken auth surfaces, without missing-data placeholders.
4. **The agent runs the sensibility flows against the deployed dev environment** (per `playwright-user-flows` — same real-running-app discipline as B6).
5. **Per-item verdict:** one of `sensible` / `nonsensical` / `env-failure` / `not-reachable`. Persisted in the agent's verdict file at `<cwd>/.architect-team/sensibility/<bug-slug>/checker-<ts>.json`.
6. **The orchestrator pools the verdicts:**
   - **All `sensible`** → B6b passes; proceed to B7.
   - **Any `nonsensical`** → the orchestrator writes a FRESH solution requirement for each `nonsensical` item with `origin.kind: "fix-regression"`, the failing impact-set item as the symptom, the captured trace + screenshots as evidence. The new SR routes back through the bug-fix-pipeline (recursive — a new B−1 → B8 loop on the new bug). The CURRENT fix is NOT marked complete; the new SR resolves first, then B6 + B6b re-run on the new state.
   - **Any `env-failure`** → routes to the implementing team for env diagnosis (parity with B6's `env-failure` handling).
   - **Any `not-reachable`** → logged in the verdict file as an audit-trail item; no SR generated (the item being not-reachable means the fix can't have broken it from the user's view).

### Unbounded recursion (loop until resolved)

The fix-regression loop runs until the bug is resolved end-to-end — there is NO iteration ceiling, per `architect-team-pipeline`'s `## Run-state: unbounded solving, concurrency, required-input gates`. Keep DETECTING recurrence: when the SAME fix-regression recurs (the original bug likely has a deeper architectural issue), do NOT stop — continue from a DIFFERENT angle: re-route through `diagnostic-research-team` for a deeper root-cause pass, broaden the fix scope, or try an alternate strategy, and surface the recurrence loudly. Track the fix-regression-cycle counter in the SR ledger purely as an observability signal. Only a genuine need for owner input (a deeper design decision only the owner can make) becomes a required-input pause via the marker — never a give-up.

### The --no-deploy skip

If the user invoked the bug-fix run with `--no-deploy` (the dev environment is hand-managed), B6b is SKIPPED with a note in the final report: *"Logical Sensibility Check (Phase B6b) was skipped because `--no-deploy` was set. The QA-replay at Phase B6 verified the original symptom is gone, but the impact set was NOT independently sensibility-checked. Consider re-running the bug-fix without `--no-deploy` for the full verification."* Phase B7 then runs without B6b's verdict.

### SR origin kinds the bug-fix-pipeline now recognizes

The SR-intake behavior inherited from the main pipeline's Phase 3b (when a bug-fix run is itself spawned by an SR, vs. directly via `/architect-team:bug-fix`) recognizes these SR origin kinds:

| `origin.kind` | Source phase | Routing |
|---|---|---|
| `ux-flow-failure` | `ux-test-builder` Phase U8 (v0.9.29) | Normal bug-fix-pipeline flow B−1 → B8, with the failing flow as the regression-test contract |
| `fix-regression` | bug-fix-pipeline Phase B6b (v0.9.29) | Same as above — recursive on the original bug-fix run |
| (other existing kinds — `rca-product-bug`, `playwright-failure`, etc.) | Various (v0.9.22 and prior) | Same |

### Target-element verification gate (v2.21.0)

After the qa-replayer's verdict but BEFORE proceeding to Phase B6b sensibility check, invoke the 19th Layer 3 tool against the qa-replayer's verification artifact:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-target-element-measured --artifact "<workspace>/.architect-team/qa-replays/<bug-slug>.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-target-element.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-target-element-measured --artifact "<workspace>/.architect-team/qa-replays/<bug-slug>.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-target-element.json"
```

If any of the 3 severities fires (`proxy-element-substituted` / `unreachable-state-not-escalated` / `semantic-target-mismatch`), the qa-replayer's `bug-resolved` verdict is OVERRIDDEN to `bug-still-present` with the gap as the explicit failure reason. The orchestrator routes an SR with `origin.kind: target-state-unreachable-needs-seed-data` so the responsible team seeds the missing target state. See `common-pipeline-conventions/SKILL.md` `## No proxy-element verification discipline (v2.21.0)` for the canonical home.

## Phase B7 — Archive + Report

On `bug-resolved` at B6 (AND the v2.21.0 target-element gate passing):

1. Run `openspec archive <bug-slug>` to merge the spec deltas into `openspec/specs/`.
2. Emit the final report:
   - The bug description (one line).
   - The replication evidence path(s) + the original failing output (one line per).
   - The fix's commit SHA(s) + the implementing team's name.
   - The Phase B4 generalization-audit verdict (`pass` + the architect's reasoning quote).
   - The Phase B5 deploy verification (the dev URL + the build-green confirmation).
   - The Phase B6 QA-replay evidence (the now-passing artifacts + the symptom-gone confirmation).
   - The total iteration count (typically 1 or 2; flag if ≥ 5).
   - Final statement: **"Bug `<bug-slug>` has been resolved."** Followed by the archive path.

## Phase B8 — Commit + push

### Run-metric recording (v3.8.0)

As part of Phase B8, record the run's §6 success metrics via `hooks/run_metrics.record_run_metrics(workspace, run_id, metrics)` — `dev_loop_iterations`, `first_pass_fix`, `oscillation_count`, `bug_still_present_count`, `fix_regression_count`, `fe_api_verdict` (from `discriminant.json`), `layer_fixed`, the derived `wrong_layer`, and the REQ-DOC-06 `cdlg_edge_recall` / `cdlg_hallucination_rate` (None until the CDLG ships). The metrics land at `<workspace>/.architect-team/run-metrics/<run_id>.json` and are mined to MemPalace run-history. See `common-pipeline-conventions/SKILL.md` `## Run metrics + success measurement (v3.8.0)` for the canonical home + the frozen-bug-benchmark protocol.

### Deploy mandate final gate (v2.20.0)

If `intake_state.deploy_mandate.active == true`, invoke the 18th Layer 3 tool `verify-deploy-mandate-satisfied` BEFORE proceeding with commit + push — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Deploy-mandate row; it BLOCKS). Any of the 4 severities blocks the commit. The bug-fix loop routes SRs with `origin.kind: "deploy-mandate-not-satisfied"`. See `common-pipeline-conventions/SKILL.md` `## Deploy mandate discipline (v2.20.0)` for the canonical home.

### Unilateral-override meta-gate (v3.0.0)

After the deploy-mandate gate, run the 21st Layer 3 tool `verify-no-unilateral-override` as a meta-confession check across all text artifacts the bug-fix run produced (final_report, qa-replayer verdict notes, bug-replicator reproduction-text, remediation_log) — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Unilateral-override row; it BLOCKS). Single severity `unilateral-override-with-virtue-framed-confession` blocks the commit. See `common-pipeline-conventions/SKILL.md` `## Unilateral-override discipline (v3.0.0) — META` for the canonical home.

Same flow as `architect-team-pipeline` Phase 8 — **documentation-currency gate first** (the `doc-updater` agent dispatch + the `system-architect` Documentation Currency Audit + the commit-blocking gate, per v0.9.23 — same dispatch, same audit, same enforcement as the main pipeline), then completion audit gate, default-branch guard (the work lands on `architect-team/<bug-slug>` feature branch unless `--allow-push-to-default`), commit with the standard message template, push to the feature branch, recommend a PR. **Auto-merge to main (v3.7.0):** when `AUTO_MERGE_MAIN = true` (the default; `--no-auto-merge` opts out) AND the completion audit passed AND the commit landed on `architect-team/<bug-slug>`, after the push call `merge_branch_to_main_and_prune('architect-team/<bug-slug>', '${WORKTREE_PATH}', push=<AUTO_PUSH>)` via the polyglot Python (same invocation as `architect-team-pipeline` Phase 8's `### Auto-merge to main` section; run from the MAIN checkout). On `reason: "merged-and-pruned"` report merged + pruned (branch deleted local + remote, worktree removed) and SKIP the finalize step below. On `conflict: true` fall back to the feature-branch + PR-recommend path + the finalize step below. On `reason: "push-rejected"` (branch protection) STOP + report, never force. When `--no-auto-merge`, skip this and run the finalize step below verbatim. Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`. **End-of-run worktree finalize (v3.6.0):** after the push (and the v3.7.0 auto-merge step when it did NOT already prune the worktree) and before the auto-compact prompt — when this run created a worktree — call `finalize_run_worktree(Path('${WORKTREE_PATH}'))` via the polyglot Python pattern (same invocation as `architect-team-pipeline` Phase 8's `### End-of-run worktree finalize` section): it removes the worktree + branch if the branch is merged into `origin/main`, otherwise leaves the folder and returns a `warning` the orchestrator prints verbatim. Unmerged work is never auto-deleted. Auto-compact prompt at the very end (unless `--no-compact`).

**Documentation-currency gate at Phase B8 (per the `documentation-currency` skill + v0.9.23's `doc-updater` agent):**

0. **Bump version first** — the orchestrator updates `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to the target version. The bug-fix pipeline's typical version bump is a patch (e.g., `0.9.22` → `0.9.23`) since a bug-fix loop ships a small slice; the orchestrator decides the level.
1. **Update — the Lead creates a `doc-updater` task** (v0.9.23, opus, bounded `Write` only to the documentation-currency inventory paths) in the shared list (teams mode) OR dispatches the `doc-updater` subagent (subagents mode). Same dispatch shape as the main pipeline's Phase 8. The agent reads the bug-fix loop's `git diff` (typically small — one or two files plus the new test artifact) and updates whatever inventory docs the diff invalidated. For a tiny bug-fix diff the agent walks the inventory, finds zero stale sections, writes a report with `updates: []` (or a minimal CHANGELOG entry), and exits cheaply. The cost of the dispatch is negligible; the value is structural — bug fixes are not exempt from the doc-currency gate.
2. **Audit — the Lead creates a `system-architect` task** in Documentation Currency Audit mode (teams mode) OR dispatches the `system-architect` subagent in that mode (subagents mode). Unchanged from v0.9.15. Independent verification.
3. **Gate.** `pipeline-completion-audit.py` blocks the commit until the audit verdict is `overall: pass` — same enforcement as the main pipeline.

The completion audit verifies the bug-fix loop closed cleanly — every iteration's SR resolved, the final QA-replay verdict is `bug-resolved`, the master-review audit verdict at B7 (if any) is `pass`, the doc-currency audit verdict is `pass`, no escalation marker pending.

The commit message format:

```
<bug-slug>: <one-line bug-resolved summary>

- Bug class: <the class of bug addressed>
- Replication: <artifact path(s)>
- Generalization-audit verdict: pass (<one-line architect reasoning>)
- QA-replay verdict: bug-resolved end-to-end (<dev URL>)
- Iterations: <N>
- Phases B−1 → B8 complete; openspec archive landed at <archive-path>

Dispatch-Mode: <teams|subagents>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

The `Dispatch-Mode:` trailer (v1.5.0) is derived from
`.architect-team/intake-state.json`'s `dispatch_mode` field — the orchestrator
recorded it at startup per v1.0.0's mode-detection contract. Values are
`teams` (Agent Teams primitive) or `subagents` (the ephemeral subagent
fallback). The trailer makes `git log --format=%(trailers)` queryable for
archeological "which mode produced this bug-fix commit?" questions without
needing to grep JSON. Read the value once at B8 commit-build time; it does
NOT change mid-run.

**Notification (best-effort, per `## Notifications`):** immediately after the commit succeeds and BEFORE the push, the orchestrator emits a `git_commit` event with the new commit's SHA. Same wiring as the main pipeline's Phase 8 commit notification:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha>
```

This `git_commit` invocation is best-effort and NEVER blocks, fails, or alters the commit or the subsequent push — a notifier failure does not affect git in any way.

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

| Rationalization | Rebuttal |
|---|---|
| "I'll skip replication and just propose the fix; the bug description is clear." | A description is not a replication. A clear description with a wrong-by-one-step replication is exactly the failure mode that produces a fix that doesn't actually address the bug. Replicate first. |
| "The Playwright flow is enough for a frontend bug — I'll skip the backend diagnostic." | A UI that appears to succeed but doesn't update the data is a class of bug the Playwright flow alone can miss. The backend diagnostic catches it. |
| "Hard-coding the user-id is fine — it's just to unblock them." | If the user explicitly said *"hard-code it"* the architect records the authorization and lets the fix proceed. If the user didn't say so, that is symptom-patching the architect REJECTS. |
| "The test passes now — the bug is fixed." | The test passing is necessary, not sufficient. The pass criterion is the originating symptom is gone end-to-end. Verify against the symptom, not just the test. |
| "I'll deploy to production directly — it's a small fix." | Production deploys escalate. Even a small fix can break in production for reasons local + dev didn't surface. The user confirms or the orchestrator stops. |
| "The QA replay failed — let me tweak the test." | NEVER edit the reproduction artifact at QA replay. If the replay fails, route back to architect with the new evidence. The artifact IS the contract. |
| "I'll skip the freshness check — it's a quick fix." | A stale map produces a fix proposal against an out-of-date understanding of the codebase. Same rule as the main pipeline; no shortcut. |
| "This is a feature, not a bug — but I'll run the bug-fix pipeline anyway because it's faster." | The classifier guards against this at the main-pipeline triage. For an explicit `/architect-team:bug-fix` invocation, Phase B0 examines the description with the same classifier and warns on a `feature` verdict. |
| "These remaining bugs merit their own focused `/architect-team:bug-fix` run — depth would suffer if batched here." | This is the pipeline refusing to do its job. The user asked you to fix bugs; fix them. If you identified them, you fix them — in THIS run, not a hypothetical future one. The only deferral is an explicit user instruction. |
| "I'll describe what the test would show instead of actually running it." | A description is not a test. Run the artifact. Capture the output. Write the verdict file. The `pipeline-completion-audit` hook blocks without executed-test evidence — and it should. |
| "Cluster B needs user input so I'll skip it." | Ask the user the question (that is what the ambiguity-escalation exists for) and then fix it. Deferring to a separate run instead of asking the question is avoidance, not efficiency. |
| "This bug requires investigation before fixing — I'll document it and move on." | Investigate it NOW. The `diagnostic-research-team` exists for exactly this. Route it through 3 diagnostic researchers, get the root cause, fix it. "Document and move on" is the anti-pattern the whole pipeline exists to prevent. |
| "The user said 'match the oracle' — I'll do data enrichment in this run and defer the visual rebuild to a separate run." | This is silently narrowing the prompt's scope — the v1.4.0 anti-pattern. `match` / `rebuild` / `mirror` / `parity` / `make like` / `replicate` imply visual + structural + behavioral parity. If your reading is narrower, surface the scope decision via `AskUserQuestion` BEFORE starting; do not unilaterally split the work into "this run" and "future runs." Per `common-pipeline-conventions` `## Scope discipline`. |

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
