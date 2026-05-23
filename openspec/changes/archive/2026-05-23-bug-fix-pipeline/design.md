# Design — bug-fix-pipeline

## Context

The architect-team plugin has, through v0.9.21, optimized for feature work: 100%-coverage Phase 1, parallel team spawn at Phase 2, six independent Phase 5 review teams. For a feature that lands hundreds of lines of new code touching multiple components, that investment pays back many times over.

For a bug fix — a one-component, often one-file change — the same machinery is over-engineered. The user has separately reported the symptom: full-pipeline runs against a single-bug request take an hour to do what should take fifteen minutes, and the agent often produces a fix that special-cases the failing input instead of addressing the underlying class of bug because the discipline that catches generalization gaps lives in the visual / editability / interaction review teams which aren't relevant to most bug fixes.

The fix is a sibling pipeline shaped specifically to the bug-fix workflow plus a triage layer at the top of the main pipeline that auto-routes bug-shaped intake to the sibling.

## Architecture

### The skill: `bug-fix-pipeline`

A second orchestrator playbook, sibling to `architect-team-pipeline`, with five non-negotiable disciplines:

1. **Replicate first.** The first work item is to reproduce the symptom — Playwright user-flow for frontend bugs, backend script for backend bugs. A fix proposed without replication is a guess and gets rejected at the architect review (B4).
2. **Reproduction IS the regression test.** The artifact that demonstrated the bug is the artifact the QA replay verifies post-fix. No "now write a test" second step. For frontend bugs, the agent ALSO writes a backend diagnostic so the regression is covered on both sides of the contract.
3. **Generalize, never symptom-patch.** The `system-architect` Bug-Fix Generalization Audit reads the proposal and the replication and rejects fixes that special-case the failing input (a literal user-id in a conditional, a hard-coded category name in a switch). Override is explicit: the user has to say "patch it just for now."
4. **QA replay against live dev.** Post-fix, the `qa-replayer` agent re-runs the original replication against the deployed dev environment. Pass = symptom gone end-to-end. Fail = back to architect with new evidence.
5. **Live-dev-environment-by-default deploys.** Fixes are deployed to the dev environment URLs and confirmed-built BEFORE the QA replay. Production is an opt-in exception that escalates.

#### Phase outline

- **Phase B−1 — Intake & Mapping.** Reuses `intake-and-mapping` verbatim — same codebase discovery, same per-codebase ralph loop, same map-freshness rules, same integration mapping. The maps must be current before the bug-fix loop starts.
- **Phase B0 — Detection & Normalization.** Same as main pipeline Phase 0 — `plain`/`openspec`/`superpowers` classification; for `plain`, openspec init + kebab `<bug-slug>` derivation. (The bug-fix pipeline carries the SAME input-form rules as the main pipeline — folder OR prose.)
- **Phase B1 — Replication.** Dispatch the `bug-replicator` agent. The replicator reads the source description, identifies the failing path from CODEBASE_MAP / ROUTE_MAP / INTEGRATION_MAP, and writes + runs a Playwright user-flow (frontend) or a backend script (backend) that demonstrates the symptom against the live dev environment. Three exit verdicts: `reproduced` (good — proceed), `could-not-reproduce` (escalate with the evidence; the bug may already be fixed, or the description may be incomplete), `needs-clarification` (the description is genuinely ambiguous; emit a structured question — *"How did you experience the bug? What did you click? What did you expect to see vs. what you saw?"* — and pause).
- **Phase B2 — Reproduction-artifact promotion + backend diagnostic.** The replication artifact moves into the codebase's test directory (`tests/` or `e2e/`) under a `bug-fix-<slug>` name. For frontend bugs, the agent ALSO writes a backend diagnostic test that drives the same flow from the backend's view (a Python or Node script that calls the relevant endpoint(s) and asserts the data-layer outcome). The pair is the regression contract.
- **Phase B3 — OpenSpec proposal authoring.** Author `openspec/changes/<bug-slug>/proposal.md` + `design.md` + `specs/<cap>/spec.md` + `tasks.md` + `coverage-map.json` (same artifact chain as a feature change). The proposal cites the replication evidence verbatim, names the root cause if known, and proposes the fix. Validate via `openspec validate --strict`.
- **Phase B4 — Bug-Fix Generalization Audit.** Dispatch the `system-architect` agent in a new Bug-Fix Generalization Audit mode. Inputs: the source description, the replication artifact + its output, the proposal + design.md. Verdicts:
  - `pass` — the fix addresses the *class* of bug and is correctly scoped (no special-casing).
  - `needs-generalization` — the proposal special-cases the failing input. The architect cites the offending pattern and the underlying class of bug; the proposal returns to authoring (back to B3) for revision.
  - `needs-replacement` — the proposed approach is wrong (treats a symptom while leaving the root cause; uses the wrong layer; introduces a worse defect). The architect cites a better alternative; back to B3.
  - The user-explicit override: if the original requirement said *"hard-code it"*, *"just for now"*, *"hotfix"*, or equivalent, the architect records the authorization verbatim and lets a targeted fix proceed. The architect does NOT extrapolate authorization from silence.
- **Phase B5 — Implement + deploy to dev.** A focused fix team (single teammate, since bug-fix scope is by definition narrow) implements the fix per the proposal. The team writes Phase 3 review-gate evidence as usual (the existing schema applies — `ui_interaction_review`, `visual_fidelity_review`, etc., with the bug-fix slice's appropriate values). After local tests pass, **deploy to the dev environment** per the target project's `design.md` `## Dev Environment` section. Confirm builds green (a tight in-turn poll on the deploy's health endpoint or build status). The exception, and the ONLY exception, is when the run was explicitly invoked with `--environment production` — in which case the orchestrator escalates a structured question (production deploys are user-decisions) and does not deploy automatically.
- **Phase B6 — QA replay against live dev.** Dispatch the `qa-replayer` agent. The replayer's input is the reproduction artifact from Phase B2 (the Playwright flow + the backend diagnostic, OR the backend script alone). It re-runs them against the live dev environment, verbatim — no edits, no shortcuts. **Pass criterion: the originating symptom is gone end-to-end.** Not "the test passes" — the original failure mode is no longer reproducible (the page renders the expected data; the row actually deletes; the redirect goes to the right place). On `bug-still-present`, the replayer writes a solution requirement back to the orchestrator with the new evidence; the loop returns to B3 (fresh OpenSpec proposal — *new* proposal, not amended) and continues. Bounded at 10 bug-fix iterations (the global 20-step ceiling caps absolutely).
- **Phase B7 — Archive + Report.** `openspec archive <bug-slug>`. Final report with the replication evidence, the fix's commit SHA, the QA-replay evidence, the bug-resolved-end-to-end statement.
- **Phase B8 — Commit + push.** Same default-branch guard as the main pipeline — `architect-team/<bug-slug>` feature branch unless `--allow-push-to-default`. Auto-compact prompt at the very end.

The skill body is parallel-structured to `architect-team-pipeline` so a maintainer who knows one can navigate the other.

### The triage layer in the main pipeline

The main `architect-team-pipeline` skill gains a new **Phase −2 — Triage & Routing** section before the existing Phase −1 prelude:

1. Dispatch the new `bug-classifier` agent with the source description. The classifier returns:
   ```json
   { "kind": "bug" | "feature" | "mixed" | "unclear",
     "bug_portion": "<the bug-portion of the requirement, or null>",
     "feature_portion": "<the feature-portion of the requirement, or null>",
     "confidence": "high" | "medium" | "low",
     "reasoning": "<one-line citation of the language signals that drove the classification>" }
   ```
2. Apply the verdict:
   - **`bug`** — invoke the `bug-fix-pipeline` skill against the requirement. Do NOT continue to Phase −1. The bug-fix pipeline handles intake-and-mapping itself.
   - **`feature`** — continue to Phase −1 as before. No behavior change for feature runs.
   - **`mixed`** — spawn two subagents IN PARALLEL in a single message: one running `bug-fix-pipeline` against `bug_portion`, one running `architect-team-pipeline` against `feature_portion` (with the Phase −2 triage already done, so it skips re-triage to avoid infinite recursion). Await both. Integrate their commit ranges in the final report.
   - **`unclear`** — emit a structured question to the user ("Is this a bug to fix, a new capability to build, or both?") and pause. This is a domain gate (per v0.9.21's process-vs-domain-gate carve-out — the gate fires regardless of `--proposal-first` because the user's answer changes what is built).
3. Explicit user overrides:
   - The `/architect-team:bug-fix` slash command sets `forced_kind: "bug"` — skip classification; route directly to `bug-fix-pipeline`.
   - The `--bug-fix` flag on `/architect-team` does the same.
   - The `--feature-only` flag on `/architect-team` forces `feature` (bypasses classification — for users who explicitly want feature-pipeline rigor on what the classifier might call a small bug).
4. The classifier's verdict + the orchestrator's routing decision are mined to MemPalace `--room triage-verdicts` so prior runs inform classifier calibration.

### The classifier's algorithm

The `bug-classifier` is intentionally lightweight (sonnet, no Bash). Its inputs are the source description text + the per-codebase maps. Its outputs are the verdict JSON above. Its method:

1. **Lex-pass** the description for bug-keywords (`bug, broken, fix, doesn't work, error, crash, fails, stuck, regression, wrong, incorrect, blank, 404, 500, stale, won't, can't, isn't`) and feature-keywords (`add, build, implement, support, enable, create, extend, new, feature, capability, want to be able to`). Count both.
2. **Read** the description as prose to confirm the lex signal is genuine — a sentence describing a feature might contain "fix" as an aspiration; a bug description might use "add" when referring to what the system should do. The lex signal is a starting hint, not the answer.
3. **Decide**:
   - Bug-keywords present + feature-keywords absent + symptom-describing structure (a verb-noun-pair describing failure: *"the row doesn't delete"*) → `bug`.
   - Feature-keywords present + bug-keywords absent + capability-describing structure (*"add a new export button"*) → `feature`.
   - Both present and both describe distinct work items (*"the heir totals are wrong; also add a CSV export"*) → `mixed` with bug_portion and feature_portion populated.
   - Both present but they describe the SAME work (*"add a fix for the broken delete"*) → `bug` (the "add" was idiomatic).
   - Genuinely ambiguous (a one-line "review the auth flow") → `unclear`.
4. **Confidence**: `high` when both the lex signal and the structural read agree strongly; `medium` when one is partial; `low` when the prose is sparse.

The classifier is honest about uncertainty — `low` confidence on a `bug` verdict produces a soft-route the orchestrator can confirm with the user OR fall back to the full pipeline ("classified as bug with low confidence; if this is actually a feature, reply `--feature-only` to re-route").

### Same-input-forms guarantee

Both `bug-fix-pipeline` and `/architect-team:bug-fix` accept the **same two input forms** as the main pipeline: a requirements folder (a path resolving to an existing directory) OR a plain-language requirement (prose typed directly as the argument — a sentence, a paragraph, a bug report, a symptom description). The classification rules in the command's argument-parsing block mirror `/architect-team`'s rules verbatim: never refuse prose, never path-treat the first word of a sentence, never ask "give me a folder." The skill bodies enforce the same: when `$REQ_DIR` is plain-language prose, the codebase the bug applies to is the cwd (a git repo) unless the prose names another path.

## Reuse Decisions

| Decision | Choice | Justification |
|---|---|---|
| Bug-fix orchestrator playbook | **build-new** `bug-fix-pipeline` skill | The main `architect-team-pipeline` skill is 432+ lines optimized for feature work; bolting bug-fix discipline onto it would double its size and make either workflow harder to read. A sibling skill is cleaner. Both share `## Default mode of operation`, the run-state rules, and the safety rules verbatim by reference. |
| Intake + maps | **reuse** `intake-and-mapping` verbatim | Phase B−1 is literally the existing intake-and-mapping flow — no shortcut, no abbreviated version. The maps must be fresh; that discipline is solved. |
| Plain/folder detection | **reuse** main pipeline's Phase 0 logic | Same `plain`/`openspec`/`superpowers` classification + openspec init + change-name derivation. |
| Playwright user-flow | **reuse** `playwright-user-flows` verbatim | The bug-replicator drives Playwright per the existing skill — real `page.click`/`page.fill`, real running dev env, the genuine-flow audit. Phase B6 QA replay uses the same flow. |
| Backend script | **reuse** `dev-api-integration-testing` verbatim | The bug-replicator's backend script follows the same discipline (real dev API, real responses, no mocks). |
| RCA on failure-to-reproduce | **reuse** `root-cause-test-failures` verbatim | When B1 returns `could-not-reproduce`, the replicator's evidence routes through the same 3-pass RCA loop. |
| Generalization architect review | **extend** the existing `system-architect` agent with a new Bug-Fix Generalization Audit mode | The agent already has Master Review Audit, Diagnostic Plan Review, Documentation Currency Audit, Interaction Map Review modes. A fifth mode (sixth?) adds a section to the agent body; no new agent. |
| Proposal authoring | **reuse** `coverage-mapping` + `reuse-first-design` + the Phase 1 planning-validation gate | Bug-fix proposals are real OpenSpec changes; same Phase 1 gate; same validation; same reuse-first ladder. |
| Bug replicator | **build-new** `bug-replicator` agent | Discrete role: read description → drive Playwright OR backend script → report verdict + evidence. Doesn't fit into any existing agent's scope. opus (judgment-heavy when interpreting the bug description into a flow). |
| QA replayer | **build-new** `qa-replayer` agent | Discrete role: re-run a reproduction artifact → verdict against a clear symptom criterion. opus, read-only on source. |
| Bug classifier | **build-new** `bug-classifier` agent | Discrete role: lex + structural read of intake → kind + portions verdict. sonnet (the classification is structured and language-pattern-driven, not deep reasoning), analysis-only tools. |
| Main pipeline dispatch | **extend** `architect-team-pipeline` with a new Phase −2 | A single section addition to the existing skill; not a rewrite. Preserves all existing Phase −1 → 8 behavior for `feature` and `unclear` routes. |
| Same-input-forms | **reuse** the v0.9.17 argument-parsing rules verbatim | Both the new command and the new skill cite the existing rules and inherit them. |
| Iteration ceiling | **reuse** the global 20-step ceiling + oscillation detection | A bug-fix-loop iteration counts the same as a feature-fix iteration. The bug-fix pipeline adds a tighter LOCAL ceiling (10) as an early-escalation signal. |
| Documentation currency | **reuse** the v0.9.15 Phase 8 documentation-currency gate | The bug-fix pipeline's Phase B7 archive + B8 commit run through the same doc-currency audit as the main pipeline. |
| Tests | **reuse** the existing pytest structural-test pattern | New tests follow `tests/test_interaction_intuition_skill.py`'s shape; `EXPECTED_*` sets in the central files are appended. |

No new third-party dependency. No new file outside `skills/`, `agents/`, `commands/`, `tests/`, `.claude-plugin/`, and the top-level docs.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The classifier mis-classifies a feature as a bug and the user gets the faster pipeline when they wanted the full rigor. | (a) The classifier returns confidence; `low` confidence on `bug` triggers a soft-route with a confirmation message ("classified as bug — reply `--feature-only` to escalate"). (b) The `--feature-only` flag is documented prominently. (c) The classifier's prompt is calibrated against past intake archives mined to MemPalace. |
| The classifier returns `mixed` when the bug and feature share a file, and the parallel spawn produces a merge conflict. | The classifier reports `mixed` with file-scope hints when it can; the orchestrator's parallel-spawn prompt includes "if you discover your file scope overlaps the other branch, signal idle with a `scope-conflict` and the orchestrator will sequence instead of parallelize." A scope conflict is a recognized escalation, not a failure. |
| The bug-replicator can't reproduce the symptom and the loop stalls. | `could-not-reproduce` is a recognized verdict that escalates (writes the evidence + the bug description + the maps the replicator consulted), with the orchestrator emitting a structured question to the user — *"I attempted X but the symptom didn't appear; can you confirm the steps?"*. The bug-fix loop does NOT proceed to B3 without a successful replication; "we'll figure it out at QA" is forbidden. |
| The architect's generalization audit is over-strict and rejects fixes that are correctly localized (e.g., a one-line conditional that DOES address a class because the class is exactly the one input). | The audit verdict is `pass` / `needs-generalization` / `needs-replacement` — and the audit body includes a "is the class genuinely one-input" question. A genuinely-narrow class IS general for that class. The audit's `reasoning` field cites the class size when relevant. The user can also explicitly authorize a targeted fix ("hotfix this one"). |
| The QA-replayer reports `bug-still-present` for a different reason (env failure, deploy didn't apply, browser version drift). | The replayer's verdict has three states: `bug-resolved`, `bug-still-present`, `env-failure`. An `env-failure` does NOT route back to architect — it routes to the implementing team for env diagnosis (probably a build-cache issue or a deploy-not-applied). Only `bug-still-present` (the deploy applied AND the symptom is back) re-engages the architect. |
| The live-dev-by-default rule conflicts with a repo that has no dev environment configured. | The bug-fix pipeline reads the target project's `design.md` `## Dev Environment` section; absent that, B5 escalates ("no dev environment configured; please provide a dev URL or invoke with `--no-deploy`"). The default is to test live, but the orchestrator gracefully escalates when the live target doesn't exist. |
| The main pipeline's Phase −2 dispatch creates an infinite-recursion path (Phase −2 → mixed → spawn architect-team-pipeline → Phase −2 → mixed → ...). | The Phase −2 dispatch sets `triage_done: true` in the spawned subagent's environment; the spawned subagent's Phase −2 sees the flag and skips classification. The recursion is bounded at depth 1. |
| The bug-fix pipeline ships and immediately people invoke it on actual features by mistake. | The classifier guards against the lex-level mistake. For explicit `/architect-team:bug-fix` invocations, the skill body's first phase (B0) examines the description with the same classifier; on a `feature` verdict, it warns the user ("this looks like a feature, not a bug; run `/architect-team` instead, or pass `--force-bug` to proceed") and waits. |
| Future skill drift — someone removes the classifier from Phase −2 and the main pipeline silently runs the full rigor for every bug. | The wiring tests assert the classifier reference is present in both `architect-team-pipeline/SKILL.md`'s Phase −2 AND `commands/architect-team.md`'s flag list. A drift breaks the test suite. |
