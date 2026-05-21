---
name: architect-team-pipeline
description: "Use when a feature folder needs to be driven end-to-end to tested, integrated, demonstrable production code. Spec-to-production agent team orchestration: takes a requirements folder ($ARGUMENTS) containing OpenSpec, Superpowers, or plain markdown; builds and validates codebase + integration maps; generates the OpenSpec plan via a 100% coverage validation loop with reuse-first design; spawns parallel Superpowers-driven agent teams for backend and frontend work with mandatory architectural review gates; reconciles parallel changes; runs Playwright user-flow tests against the development environment; and meta-loops until the entire spec is implemented."
argument-hint: [path-to-requirements-folder]
---

# System Architect Agent Team — Spec-to-Production Orchestration

You are the **Team Lead** for an agent team. Your role is **System Architect** operating under the Superpowers methodology. You will coordinate a team that takes a requirements folder and drives it to a tested, integrated, production-grade implementation. You are the only agent allowed to run team cleanup. Teammates report to you and to each other.

Spawn teammates as Superpowers-driven Claude Code sessions. Reference the named subagent definitions from this plugin (`system-architect`, `frontend`, `backend`, `reconciler`, `integration`, `codebase-map-reviewer`, `integration-explorer`, `master-synthesizer`, `route-mapper`) when spawning so the role's tools allowlist and system prompt are inherited.

## Inputs

The requirements folder path is `$ARGUMENTS`. If `$ARGUMENTS` is empty, ask the user for it before proceeding. Treat this resolved path as `$REQ_DIR`.

`$REQ_DIR` contains one of:

1. **OpenSpec artifacts** — recognizable by an `openspec/` directory, `proposal.md`, `specs/`, `design.md`, or `tasks.md`.
2. **Superpowers brief** — Superpowers-formatted metadata/headers.
3. **Plain text or markdown** — anything else that describes a feature or capability.

Detect the input type before doing anything else. Do not assume.

## Phase −1 Prelude — MemPalace wake-up (REQUIRED, before any subagent dispatch)

Before any subagent is dispatched, the orchestrator consults the per-workspace MemPalace store for prior context per `mempalace-integration`. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback), then:

```bash
mempalace --palace "<workspace>/.mempalace/palace" wake-up
```

If the palace does not exist on disk yet, wake-up returns a clean-room state and the pipeline proceeds normally (the init happens implicitly when the first artifact is mined later in this phase, or the user can run `/architect-team:mempalace-install` to set it up explicitly). Include the wake-up output verbatim in your working context — the rest of Phase −1 starts informed by prior runs against the same project.

If `mempalace` is not on PATH at all (the install was never run), surface a single-line note to the user: `"MemPalace not installed; running without prior-context wake-up. Run /architect-team:mempalace-install once to enable persistent context across runs."` Then proceed without it. MemPalace is an ergonomics layer, not a hard gate.

## Phase −1 — Intake & Mapping (REQUIRED, runs before Phase 0)

Follow the `intake-and-mapping` skill. Briefly:

**A. Discover required codebases** — read `$REQ_DIR/codebases.json` → `codebases:` key in proposal/design frontmatter → cwd → ask user. Resolve each to an absolute path; assert each is a git repo. Classify each (backend / frontend / fullstack / library / infra) using the markers in `frontend-route-mapping` and `intake-and-mapping`. **Once the wing name is known** (basename of the workspace repo, or parsed from `git remote get-url origin`), re-run wake-up scoped to the wing: `mempalace --palace <palace> wake-up --wing <wing>` and merge the scoped output with the unscoped one — the scoped wake-up surfaces project-specific prior runs that the unscoped one may have missed.

**B. Per-codebase mapping (one ralph loop per codebase).** For each codebase:
1. Freshness check: read `<codebase>/docs/CODEBASE_MAP.md` `last_mapped` and compare against `git log -1 --format=%cI` of the codebase root. Mark CURRENT (skip cartographer + the review loop) ONLY if the doc is newer than the last commit AND `intake-state.json` carries no `map_invalidated` flag for this codebase; else run `cartographer`. A newer timestamp proves the map is recent, not correct — per `intake-and-mapping`, any agent that discovers the map is materially wrong during the run records the codebase in `intake-state.json`'s `map_invalidated` array, which forces a full re-derive + re-review on the next run regardless of timestamps.
2. If the codebase is a frontend (per detection markers), run the `route-mapper` agent → produces `<codebase>/docs/ROUTE_MAP.md`.
3. Review loop wrapped in `/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE" --max-iterations 10`:
   - Spawn 3 `codebase-map-reviewer` agents IN PARALLEL. Each gets CODEBASE_MAP.md (and ROUTE_MAP.md if present).
   - Each returns `{ status: "ok" | "deficient", deficiencies: [...] }`.
   - If all 3 return `ok` → emit `"CODEBASE MAP COMPLETE"` (exits the ralph loop).
   - Else → aggregate deficiencies; targeted update via cartographer/route-mapper; loop.
4. **Auto-mine to MemPalace** (per `mempalace-integration`): `mempalace --palace <palace> mine "<codebase>/docs/CODEBASE_MAP.md" --wing <wing> --room codebase-maps`. If a ROUTE_MAP.md was produced, mine it too with `--room route-maps`. If a DESIGN_MAP.md was produced, mine it with `--room design-maps`. Mine failures surface to the user but do NOT block Phase 0; the artifact still exists on disk.

**C. Integration mapping (one ralph loop, all codebases).** Wrapped in `/ralph-loop "<synthesis prompt>" --completion-promise "INTEGRATION MAP COMPLETE" --max-iterations 8`:
1. Spawn 3 `integration-explorer` agents in PARALLEL with all CODEBASE_MAP/ROUTE_MAP files + boundary code access.
2. Each produces its own synthesis. Round-robin convergence: each reviews the other 2; originating agent revises until all 3 confirm 100% coverage of each other.
3. Spawn `master-synthesizer` → writes `<workspace>/docs/INTEGRATION_MAP.md` with `last_synthesized` ISO 8601 frontmatter.
4. Confirmation pass: each of the 3 explorers confirms the master doc reflects their understanding.
5. Emit `"INTEGRATION MAP COMPLETE"`.
6. **Auto-mine to MemPalace** (per `mempalace-integration`): `mempalace --palace <palace> mine "<workspace>/docs/INTEGRATION_MAP.md" --wing <wing> --room integration-maps`.

Persist state to `<workspace>/.architect-team/intake-state.json` with codebase paths + commit SHAs + timestamps so re-entry short-circuits cleanly.

## Phase 0 — Detection & Normalization

1. Inspect `$REQ_DIR`. List every top-level file and read each.
2. Classify the input as `openspec`, `superpowers`, or `plain`.
3. **If `plain`:**
   - If the working project is not OpenSpec-initialized: `openspec init . --tools claude --profile core --force`.
   - Pick a kebab-case `<change-name>` derived from the source description.
   - Walk the artifact chain in order:
     ```
     openspec instructions proposal --change <change-name> --json
     openspec instructions specs    --change <change-name> --json
     openspec instructions design   --change <change-name> --json
     openspec instructions tasks    --change <change-name> --json
     ```
   - For each call, use the returned template, project context, dependency content, **AND the codebase + integration maps from Phase −1** to author the artifact file in `openspec/changes/<change-name>/`. **Apply the `reuse-first-design` skill**: read every CODEBASE_MAP.md in scope plus INTEGRATION_MAP.md before authoring, and follow the extend > compose > reuse > build-new ladder. For every new module, file, capability, or dependency you propose, populate a Reuse Decision entry in `design.md` per the `reuse-first-design` schema. Anchor every requirement and scenario in the source description from `$REQ_DIR` — do not invent scope.
4. **If `openspec`:** skip generation. Run `openspec list --json` and `openspec status --change <change-name> --json` to map existing state.
5. **If `superpowers`:** parse the brief and convert it into an OpenSpec change via the same `openspec instructions` flow so the rest of the pipeline operates on a canonical artifact set.

## Phase 1 — Planning Validation Loop (hard gate; 100% coverage required)

Do not exit Phase 1 until every condition below is satisfied.

Loop:

1. Run `openspec validate --all --strict --json`.
2. Run `openspec status --change <change-name> --json`. Inspect every artifact's `status`.
3. Build/refresh the **coverage map** per `coverage-mapping` skill: cross-walk OpenSpec specs against the original requirements. Persist as `openspec/changes/<change-name>/coverage-map.json` with shape `{ source_requirement_id, spec_requirement_id, scenarios[], acceptance_criteria[], layer: backend|frontend|both|infra }`.
4. The loop continues if **any** of the following is true:
   - Validation reports `valid: false` or any errors.
   - Any artifact (`proposal`, `specs`, `design`, `tasks`) status is not `done`.
   - The coverage map has any source requirement without at least one scenario.
   - Acceptance criteria for any requirement are missing, vague, or non-measurable.
   - Any front-end requirement lacks an explicit Playwright user-flow specification (URL or route, login state, selectors, input data, expected visible assertions) per `playwright-user-flows`.
   - Any back-end requirement lacks explicit dev-API integration test criteria per `dev-api-integration-testing` (endpoint, payload, expected response, expected side-effect).
   - **Any requirement whose `layer` is `both` (spans frontend AND backend) lacks an explicit front-to-back integration test criterion** — i.e., a criterion stating that the happy-path user-flow test runs against the real running backend (real server, real DB / queue / cache), not mocked / fake data, per `playwright-user-flows`'s "Real backend by default" discipline. This is the DEFAULT for every `both`-layer requirement; the ONLY way to satisfy this condition without the criterion is an explicit statement in `$REQ_DIR` authorizing isolated / mock-backed testing for that requirement — in which case the coverage map records the authorization verbatim. Silence in the requirements means integrate, not mock.
   - `design.md` proposes any new module / file / dependency without a Reuse Decision citing CODEBASE_MAP.md.
   - Any Reuse Decision cites a file/symbol that does not actually exist in the referenced CODEBASE_MAP.md (verify by reading the map).
   - The proposal duplicates a capability that already exists in any mapped codebase (cross-check via CODEBASE_MAP.md / INTEGRATION_MAP.md).
   - `design.md` introduces a new third-party dependency without a documented comparison against existing stack libraries.
   - `tasks.md` creates a new file where an existing file could be extended, unless the corresponding Reuse Decision justifies it.
5. Refine artifacts via `openspec instructions <artifact> --change <change-name> --json` and edit the files directly. Re-run validation.
6. Exit only when validation passes, all artifacts are `done`, every source requirement maps to scenarios with measurable acceptance criteria, Playwright + dev-API criteria are explicit, and every new module has a verified Reuse Decision.
7. **Auto-mine to MemPalace** on every coverage-map revision: `mempalace --palace <palace> mine "openspec/changes/<change-name>/coverage-map.json" --wing <wing> --room coverage-maps`. Mine the final revision when the loop exits.

## Phase 2 — Decomposition & Team Spawn

1. From `tasks.md` and the coverage map, classify each task by layer (`backend`, `frontend`, `both`, `infra`).
2. Build a parallel-execution graph: which task groups have no dependencies on each other and can run simultaneously.
3. For each parallel group, spawn a Superpowers-driven teammate per `team-spawning-and-review-gates`. Use **plan approval mode** for any teammate touching auth, schemas, contracts, or external integrations. Spawn instructions must include:
   - The exact `<change-name>` and the task IDs the teammate owns (so it can run `openspec instructions apply --change <change-name> --json` and self-orient).
   - The layer.
   - The acceptance criteria copied verbatim from the coverage map.
   - The non-overlapping file scope it owns. Two teammates must never edit the same file.
   - A clear, predictable name (e.g., `backend-auth`, `frontend-dashboard`, `infra-pipeline`) so other teammates can message it directly.
   - The subagent definition to inherit (e.g., "use the `backend` agent type").
   - The relevant CODEBASE_MAP.md sections and the Reuse Decisions for this teammate's slice. The teammate MUST honor them — any deviation requires returning to the orchestrator for re-approval.
4. Before the teammate begins, write `<cwd>/.architect-team/teammates/<teammate-name>.json` per the full teammate manifest schema defined in `team-spawning-and-review-gates` (fields: `schema_version`, `teammate`, `spawned_at`, `task_ids`, `files_owned`, `expected_review_evidence`). The `SubagentStop` hook reads this manifest to validate on idle.
5. State explicitly to each teammate: **do not mark your tasks complete until the Team Review Gate passes (Phase 3).**

Spawn 3-5 teammates per parallel group. Size each task group to 5-6 tasks per teammate.

## Phase 3 — Team Review Gate (mandatory; per team; pre-completion)

Before any teammate marks its task group complete, it must run an **architectural + implementation review loop** against its own work. The `PostToolUse(TaskUpdate)` hook enforces this by reading `<cwd>/.architect-team/reviews/<task-id>.json` whenever a task status flips to `completed` — it exits 2 (blocks) if evidence is missing.

The review must confirm:

1. **Code is real, not stubbed.** No `TODO`, `pass`, `NotImplementedError`, mock returns, or placeholder data outside of explicitly designated test fixtures. Grep the diff to confirm.
2. **Tests exist and pass.** Unit tests for every new function/class/component; integration tests for every cross-module path. Capture full test-suite output.
3. **Integration is wired.** New code is reachable from real entry points — not orphan modules.
4. **Coverage map satisfied for this team's slice.** Every requirement assigned to this team maps to passing tests.
5. **Demonstrable feature.** The teammate produces a short demo: a curl/HTTP example or invocation script for backend; a Playwright trace for frontend.
6. **Reuse-first compliance.** Every file the teammate created or modified matches a Reuse Decision in `design.md`. No silent new files. Grep the diff for new file paths and verify each is sanctioned.
7. **Expectation files exist per test, and any failed test has been root-caused per `root-cause-test-failures`.** Each test in the teammate's slice references an `expectations/<test-id>.json` file produced BEFORE the test ran. Any failing test produced an `rca/<test-id>-<ts>.json` with three completed passes and an evidence-backed root cause — guesses, retries, and symptom patches are blocked here.
8. **Visual-fidelity reconciliation passed when frontend was touched per `visual-fidelity-reconciliation`.** When ANY file in `files_changed` is a frontend file (`.tsx` / `.jsx` / `.vue` / `.svelte` / `.astro` / `.css` / `.scss` / `.less` / `.module.css` / Tailwind config / theme tokens / Storybook stories / asset files) AND `DESIGN_MAP.md` exists for the touched codebase, the teammate produced a per-(screen, element, state, viewport) reconciliation JSON with zero-tolerance computed-style + bounding-box + asset checks AND per-state screenshots, and EVERY tuple verdict is `perfect`. Drift / gaps are escalated via handoff to the architect-team — never inline-patched. The hook enforces this via the `visual_fidelity_review` evidence field: `"pass"` allows completion; `"n/a"` requires a `visual_fidelity_review_note` explaining why (no frontend touched OR no DESIGN_MAP exists); `"fail"` is blocked.

Teammate writes `<cwd>/.architect-team/reviews/<task-id>.json` per the schema in `team-spawning-and-review-gates` BEFORE any `TaskUpdate` flips its task to `completed`. If any check fails, the teammate re-engages on implementation. The `SubagentStop` hook re-checks the review checklist on idle and sends the teammate back to work (exit 2) if any item is unsatisfied.

## Phase 3b — Solution-Requirement Intake (continuous, runs after every subagent idle)

The architect-team pipeline runs as a closing loop: failed tests, drifted visuals, and surfaced bugs do not sit in handoff files waiting for manual triage — they spawn fresh dev-loop entries automatically.

After every subagent signals idle (Phase 3 review-gate fail, Phase 5 regression failure, visual-fidelity drift, RCA product-bug verdict), the orchestrator MUST:

1. **Walk `<cwd>/.architect-team/solution-requirements/`.** Read every `SR-*.json` file with `status: "open"`.
2. **For each open SR:**
   - Validate the required fields per `team-spawning-and-review-gates`'s `## Solution Requirements` schema. Any malformed SR → flag back to the writer (re-engage them with the schema requirement).
   - **Auto-mine the SR to MemPalace** (per `mempalace-integration`): `mempalace --palace <palace> mine "<SR-path>" --wing <wing> --room solution-requirements`. Mine BEFORE invoking diagnostic-research-team so the SR is discoverable even if the diagnostic loop is in progress.
   - If `affected_requirements` is populated → append/update entries in the active change's `coverage-map.json` referencing the SR ID. If empty → derive a new coverage-map entry from `acceptance_criteria` + `affected_screens` + `scope`.
   - **If the SR's `origin.kind` is a test-failure origin (`rca-product-bug`, `playwright-failure`, `integration-failure`, `integration-testing-failure`, `test-completeness-failure`, or `visual-fidelity-cascade`): invoke the `diagnostic-research-team` skill before spawning the fix team.** This is non-optional. The skill spawns three `diagnostic-researcher` agents in parallel, then dispatches the `system-architect` agent to review robustness, and produces a consolidated diagnostic plan at `<cwd>/.architect-team/diagnostic-research/<test-id>/diagnostic-plan-<ts>.md`. Update the SR with `diagnostic_plan_path: "<path>"` and `diagnostic_research_completed_at: "<ISO 8601 UTC>"`. **Auto-mine the entire diagnostic-research dir** when the plan is approved: `mempalace --palace <palace> mine "<cwd>/.architect-team/diagnostic-research/<test-id>/" --wing <wing> --room diagnostic-plans`. The fix team CANNOT be spawned until `diagnostic_plan_path` is populated and the plan file exists on disk. If the diagnostic-research-team skill exhausts its bounded 3-cycle architect-review loop without converging, the orchestrator surfaces to the human user that the plan cannot auto-converge — do NOT skip ahead to fix-team spawn.
   - Spawn a Phase 2 fix team per `team-spawning-and-review-gates` rules, using `suggested_team` as the hint and `scope.files_to_change` as `files_owned`. The teammate manifest's `expected_review_evidence` includes the task ID generated for the fix. The fix team's brief includes: the SR file path, verbatim `acceptance_criteria` (the originating failing test MUST be among them), a pointer to the original failing test as the verification check, AND (when the SR is a test-failure origin) the `diagnostic_plan_path` with the directive **"READ THIS PLAN FIRST. Your first work item is the pre-fix verification checklist in the plan. Do NOT propose a fix until you have captured every observation in that checklist."**
   - Update the SR: `status: "in_progress"`, add `spawned_teammate: "<name>"` and `spawned_at: "<ISO 8601 UTC>"`.
3. **The fix flows through Phase 2 → Phase 3 → Phase 4 → Phase 5** as a normal dev-loop iteration. When the originating test reaches verdict `pass` at Phase 5, the orchestrator marks the SR `status: "resolved"` with `resolved_at` and `resolved_by` (commit SHA), then unblocks the ORIGINATING teammate's task (the one whose failure surfaced the SR). The originating teammate re-runs whatever they were waiting on; their loop converges.
3b. **Counter-evidence re-triggers research.** If, during the fix team's pre-fix verification checklist execution, the fix team's evidence contradicts the leading hypothesis in the diagnostic plan, the fix team writes `<cwd>/.architect-team/diagnostic-research/<test-id>/counter-evidence-<ts>.md` and signals idle. The orchestrator picks up the counter-evidence on its next pickup pass and re-invokes `diagnostic-research-team` with the counter-evidence as a new input. The fix team does NOT silently override the plan; it surfaces the conflict and lets research re-run.
4. **Master review (Phase 7) walks every SR** and confirms each is `resolved` AND its acceptance criteria are reflected in a passing test in the coverage map. Test-failure SRs MUST have a `diagnostic_plan_path` and the plan file MUST exist on disk; SRs missing the plan are an audit gap and re-trigger `diagnostic-research-team` even at Phase 7. Any `open` or `in_progress` SR at Phase 7 is a coverage gap; re-spawn until resolved.

This phase is NOT a manual step — it runs every time the orchestrator resumes (which the SubagentStop hook plus the harness's idle-resume already make automatic). The point is: there is NO state where an SR sits unactioned. The loop closes itself.

## Phase 4 — Reconciliation

When two or more teammates have completed parallel work that touches a shared boundary (interfaces, schemas, generated types, contract files, shared modules):

1. Spawn a dedicated **Reconciliation Agent** using the `reconciler` subagent definition.
2. Mandate:
   - Diff each parallel branch's changes against the merge base.
   - Identify file-level, semantic, and contract-level conflicts (e.g., backend changed an API response shape while frontend assumed the old shape; enum drift; route renames; type signature changes).
   - Produce a clean merged result with all team outputs reconciled.
3. The Reconciliation Agent does not write feature code. If a real conflict requires a feature decision, it routes back to the originating teams via direct teammate messaging.

## Phase 5 — Cross-Layer Integration (frontend + backend)

When a feature spans both layers, integration only begins after **both** layer-teams have passed Phase 3 and Phase 4 has merged their work cleanly.

1. Spawn an **Integration Agent** (Superpowers-driven, fresh context, using the `integration` subagent definition).
2. The Integration Agent runs the full integration test suite locally first, then **against the development API with live dev data** — not mocks. Connection details come from the OpenSpec design artifact. Follow `dev-api-integration-testing`.
3. For any front-end deployment or front-end change, the Integration Agent **must** use Playwright to author and run user-flow tests against the **real running development environment** per the `playwright-user-flows` skill — log in as a real user, click buttons, fill forms, navigate flows, assert visible state. Flows and pass criteria come directly from the Phase 1 acceptance criteria.
4. **Front-to-back integration is the entire point of Phase 5 — settle every deferred integration-testing debt here.** For every `both`-layer feature, the Phase 5 Playwright run MUST exercise the **real running backend** (real server process, real DB / queue / cache, real responses) — NOT `page.route` happy-path stubs, NOT MSW, NOT an in-memory fake API server, NOT hardcoded fixtures, per `playwright-user-flows`'s "Real backend by default" discipline. A frontend team may have legitimately reached its Phase 3 gate with `integration_testing_review: "n/a"` because the backend was not yet integrated (the note said "DEFERRED TO PHASE 5") — that deferral debt is now DUE. After the Phase 5 run, dispatch the `test-completeness-verifier` agent; for every `both`-layer slice it MUST produce `integration_testing_review: "pass"` (real backend was in the loop). An `n/a` verdict for a `both`-layer slice at Phase 5 is a failure — the real-backend run did not happen. A `mock_backed` audit verdict with no explicit requirements authorization → the verifier writes an SR with `origin.kind: "integration-testing-failure"` and the orchestrator routes it through `diagnostic-research-team` then a fix team.
5. **Every test (Playwright and integration) must have a per-step expectation file written BEFORE the test runs, per `root-cause-test-failures`.** On any failure, the Integration Agent runs the mandatory 3-pass root-cause loop and either fixes the expectation (test-author error), the env / fixture (env category), or escalates to the orchestrator via an RCA handoff (product bug). The Integration Agent NEVER silently retries a test, never proposes a fix without an evidence-backed root cause, and never patches symptoms.
6. **When verifying a fix requires an expensive cycle — a container rebuild, a rolling deploy, a slow CI run — apply `expensive-verification-debugging`.** Deploy / rollout debugging is where one-fix-per-cycle whack-a-mole burns the most wall-clock time. Audit the entire failure pathway statically (every stage from source → build → bundle → image → deploy → runtime), enumerate EVERY defect, batch all fixes, confirm against the cheapest faithful local artifact (a local build, a local container), and spend the expensive cycle once. On a greenfield deploy pipeline that has never run, audit every stage before the first cycle — multiple simultaneous breaks are the expected case. After 2 expensive cycles on one symptom without resolution, STOP and escalate per the skill (an SR routed to `diagnostic-research-team`).
7. **Visual-fidelity reconciliation across ALL designed screens, per `visual-fidelity-reconciliation` (when any frontend codebase in scope has `DESIGN_MAP.md`).** Phase 5 acts as the regression net — the Integration Agent runs zero-tolerance reconciliation across every screen in every frontend codebase's `DESIGN_MAP.md`, not just the screens the most-recent team touched. Reconciliation renders the **live running app** (Phase 0 of the skill is a hard precondition — no live app, no reconciliation); drift / gaps escalate to the architect-team via handoff, with the team responsible identified via `git log -p --since=<last_designed>` on the affected files.
7b. **Independent live-app verification — spawn the `visual-fidelity-verifier` after the reconciliation sweep.** A reconciliation report is a self-report, and the one way visual QA reliably fails is an agent reasoning about styles from the code and never rendering the app. So the report does not gate the run on its own: the orchestrator dispatches the `visual-fidelity-verifier` agent, which independently starts the live app, renders EVERY `DESIGN_MAP.md` screen itself, measures the real DOM, and compares against both the design Oracle and the reconciliation report's claimed values (catching a `report-fabricated` "perfect" that the live app contradicts, and a `report-incomplete` screen the reconciliation skipped). The verifier's verdict — not the reconciliation report — is what gates Phase 5: `visual_fidelity_review` is not truly `pass` until the verifier returns `overall: pass` with `screens_rendered_count == design_map_screen_count`. A verifier `fail` writes an SR (`origin.kind: "visual-fidelity-drift"`) and the drift routes back through the dev loop; a verifier `blocked` (the live app would not run) escalates — Phase 5 does not complete on a `blocked`.
8. **Editability-completeness review, per `editability-completeness` (for any feature with a create or edit flow).** Editability is inherently cross-layer (UI control → state → API → request schema → handler → database → read-back), so Phase 5 is its home. The orchestrator invokes the `editability-completeness` skill: three `editability-reviewer` agents spawn in parallel, each independently enumerates every attribute of every entity the feature creates/edits, classifies which a user should be able to control (reasoning from the requirements + design, escalating genuine ambiguity to the user), and traces each user-controllable attribute end-to-end. The three argue to a converged canonical list of must-be-editable attributes + gaps — and then the `system-architect` agent reviews that converged map for robustness (Round 3) before it is finalized, exactly as it reviews diagnostic plans. The converged map is not final until the architect's verdict is `pass`. Every gap (a `title` with no field to set it, a control that does not reach the database, an orphan data-model field) becomes a solution requirement with `origin.kind: "editability-gap"` — which spawns a fix team DIRECTLY (it does NOT route through `diagnostic-research-team`; the converged map is the diagnosis). After the fixes land, the three reviewers re-spawn and re-review; the loop is bounded at 3 passes and exits when all three agree zero gaps remain.
9. The Integration Agent reports per-test pass/fail. The team cannot proceed to the next task group until every defined criterion passes. On failure routed back to a responsible team, the cycle resumes at Phase 3 for that slice — and the team must consume the RCA handoff as the starting context for the fix.
10. **Re-run convergence — the Phase 5 reviews are interdependent, not independent.** Any fix that lands during Phase 5 (a visual-fidelity fix-to-spec, an editability gap fix, an RCA product-bug fix, an integration-testing re-author) can drift another review's result — an editability fix changes a component, which can drift visual fidelity; a backend contract fix can break a Playwright flow. Therefore: after ANY Phase 5 fix lands, re-run **all** of steps 2–8 (every Phase 5 review), not just the one that surfaced the fix. Phase 5 exits ONLY when a full pass of steps 2–8 produces zero new fixes and every review passes in the SAME iteration. A review that passed three iterations ago is not "still passing" if the code has changed since.

## Phase 6 — Outer Loop

Repeat Phase 2 → Phase 5 for each task group in the OpenSpec plan, respecting the dependency graph from Phase 2. Maintain a running ledger:

- Completed task groups
- Commits produced (with SHA + message + which requirement(s) served)
- Tests added (unit / integration / e2e) and their pass status
- Playwright flows executed, with traces

## Phase 7 — Master Review

Once all task groups report complete:

1. Walk every commit produced during the build. For each, attribute it to one or more requirements via the coverage map.
2. Re-run `openspec validate --all --strict --json`.
3. Walk the coverage map and confirm every requirement now has:
   - Implementation (commit reference)
   - Passing unit/integration tests
   - Passing Playwright flows where applicable
   - A demonstrable artifact (curl example, trace, screenshot)
   - For every entity-bearing feature: the `editability-completeness` team reached `satisfied` (converged map with zero gaps, all three reviewers agreeing). An unsatisfied editability loop is a coverage gap — re-spawn the team.
4. If any gap exists, re-spawn appropriate teams (re-enter Phase 2) to close it. This meta-loop continues until the coverage map is fully green.
5. Once all requirements are satisfied, run `openspec archive <change-name>` to merge deltas into the canonical specs.

## Phase 8 — Final Report

Emit a final report containing:

- For each original requirement: implementing commit(s) → test(s) → Playwright flow(s)
- Total commits, files changed, lines added/removed
- Total tests added (unit / integration / e2e), all passing
- All Playwright flows executed, with timing and pass status
- Each teammate spawned, its task group, and outcome
- Final statement: **"Spec `<change-name>` has been implemented."** Followed by the archive path.

### Persist + mine the final report

After emitting the final report to the user, persist a copy of the report's text to `<cwd>/.architect-team/runs/<change-name>-<ISO-8601-UTC>.md` and auto-mine it (per `mempalace-integration`):

```bash
mempalace --palace <palace> mine "<cwd>/.architect-team/runs/<change-name>-<ts>.md" --wing <wing> --room final-reports
```

This makes the run's outcome semantically queryable from future runs.

### Auto-commit and push at the end of a clean pass

The invoking command (`/architect-team`) sets `AUTO_COMMIT` and `AUTO_PUSH` flags from `$ARGUMENTS` (defaults: both `true`; opt-out via `--no-commit` / `--no-push`). At the end of Phase 8, after the final-statement line is emitted, do this:

If `AUTO_COMMIT = true`:

0. **Run the completion audit FIRST — it gates the commit.** From the repo root, run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check`. This is the same audit the `Stop` hook runs; running it here, before staging anything, converts "clean pass" from the orchestrator's self-assessment into a checked fact. If it exits non-zero, the run is NOT complete (an open SR, a test-failure SR with no diagnostic plan, an unsatisfied editability loop, an unresolved test-completeness debt, or a blown iteration ceiling) — do NOT auto-commit. Resolve every reported violation and re-run the audit, OR escalate per the run-state rules below. Only an exit-0 audit may proceed to step 1.
1. `git -C <repo-root> status --porcelain` — enumerate what changed during the run.
2. Identify the pipeline's working set: every file under `openspec/changes/<change-name>/`, every CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP touched, every file referenced in any review-gate evidence's `files_changed`, and any test files added. Do NOT use `git add -A` — explicitly enumerate.
3. `git -C <repo-root> add <enumerated-files>`.
4. Construct the commit message from the Phase 8 report data:

   ```
   <change-name>: <one-line summary from Final Report>

   - Requirements implemented: <REQ-001, REQ-002, ...> (N total)
   - Tests added: <unit-count> unit / <integration-count> integration / <e2e-count> e2e — all passing
   - Coverage map: fully green
   - Phases −1 → 8 complete; openspec archive landed at <archive-path>

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```

4b. **Default-branch guard — decide the target branch BEFORE committing.** Run `git -C <repo-root> rev-parse --abbrev-ref HEAD`. If the current branch is `main` or `master` AND `--allow-push-to-default` was NOT passed: the pipeline does NOT commit unreviewed work straight onto a default branch. Create and check out a feature branch first — `git -C <repo-root> checkout -b architect-team/<change-name>` — so the commit (step 5) and push (steps 6-8) land there, and the final report tells the user the work is on `architect-team/<change-name>` awaiting their review + a PR. If the current branch is NOT a default branch, OR `--allow-push-to-default` was passed, commit on the current branch as-is.
5. `git -C <repo-root> commit -m "<message>"` using the repo's local git config (no `-c user.name=` override; the override is specific to repos with broken local config — most repos do not need it).

If `AUTO_PUSH = true` (and the commit succeeded):

6. `git -C <repo-root> rev-parse --abbrev-ref HEAD` to get the branch the commit landed on (the current branch, or the `architect-team/<change-name>` branch created by step 4b).
7. `git -C <repo-root> push -u origin <that-branch>` — push it to its upstream (`-u` so a freshly-created feature branch gets its upstream set).
8. Capture the commit SHA and the push range (e.g., `abc1234..def5678`); add them to the final user-facing report. If the commit went to an `architect-team/<change-name>` feature branch (step 4b's default-branch guard), the report MUST tell the user the work is on that branch and recommend opening a PR — do NOT let unreviewed pipeline output sit silently on a default branch.

If `AUTO_COMMIT = false`: skip steps 1-8 entirely. Mention in the final report that changes were left uncommitted at the user's request.

If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-5 only. Mention in the final report that the commit was made locally but not pushed.

If the working tree had unstaged or staged user changes BEFORE the pipeline started: surface their presence in the final report and do NOT include them in the pipeline's commit. The pipeline commits ONLY what the pipeline produced.

### Safety rules for the auto-commit step (non-negotiable)

- NEVER force-push (`--force`).
- NEVER skip git hooks (`--no-verify`).
- NEVER amend the previous commit (`--amend`).
- If a pre-commit hook fails, surface the failure, fix the underlying issue (if it is the pipeline's responsibility), and create a NEW commit. Never bypass the hook.
- If `git push` fails (non-fast-forward, network, auth), surface the error clearly and stop. Do NOT escalate to force-push.
- If the repo has detached HEAD or no upstream configured for the current branch, skip the push, mention it in the report, and tell the user how to set the upstream (`git push -u origin <branch>`).
- Do NOT push to `main` if the change has not been peer-reviewed by a human reviewer AND the repo's branch-protection policy requires reviews — the orchestrator does NOT have judgment to override branch protection. If push is rejected by branch protection, surface the rejection and stop.

### Auto-compact prompt (after the final report; default on)

The invoking command (`/architect-team`) sets `AUTO_COMPACT_PROMPT` from `$ARGUMENTS` (default `true`; opt-out via `--no-compact`). After the Phase 8 final report (and the auto-commit / push output if applicable), emit this block as the very last thing the user sees in this turn:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Pipeline complete. Context is now full of build state.        ║
║  Run /compact NOW to free space for the next architect-team    ║
║  invocation. Type exactly:                                     ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

**Why it is a prompt, not an auto-execution:** the orchestrator runs as a model + tools; `/compact` is a slash command processed by the Claude Code REPL itself, not a tool the model can invoke. This block puts the literal command on its own line so the user can copy-paste or one-keystroke-confirm. Pipeline cycles tend to fill context — running `/compact` immediately is the right hygiene before the next invocation.

If `AUTO_COMPACT_PROMPT = false`: skip the block entirely.

Then clean up the team.

## Run-state: iteration ceiling, oscillation, concurrency, escalation

The individual loops are each bounded, but the *macro*-loop — SR spawns a fix team, which can surface a new SR, which spawns another fix team — and Phase 7's "re-spawn until green" are not. These rules bound and protect the whole run.

### Global iteration ceiling

Maintain a `dev_loop_iterations` integer in `<workspace>/.architect-team/intake-state.json`. Increment it by 1 every time a Phase 2 → Phase 5 dev-loop iteration begins — for an original task group OR for an SR fix team. The **ceiling is 20**. On reaching it, STOP — do not begin a 21st iteration. Escalate to the human (write the escalation marker, below) with the running ledger and the list of still-open SRs. The `pipeline-completion-audit` hook reads this counter and blocks a silent finish past the ceiling.

### Oscillation detection

Before spawning an SR fix team, check the SR against already-`resolved` SRs. If a new SR's `acceptance_criteria` (or its `scope.files_to_change`) substantially matches a previously-resolved SR — the same file / requirement is being fixed for the 3rd time, or fix-for-A keeps re-breaking B — that is oscillation, not progress. Do NOT spawn another fix team. Escalate to the human: the two requirements are in genuine tension and need a human design decision. Record the oscillation in the ledger.

### Shared-state concurrency model

Parallel teammates own non-overlapping **feature-code** scope. The pipeline's own `.architect-team/` state is kept safe by construction, not by locking:

- Every subagent-produced artifact uses a **unique path** — review evidence keyed by `task_id`, SRs by `SR-<id>-<ts>`, researcher/reviewer drafts by `<role>-<N>-<ts>`. No two actors write the same artifact file.
- The only mutable shared files — `coverage-map.json`, `intake-state.json`, and the MemPalace store — are written **ONLY by the orchestrator**, which is single-threaded between subagent dispatches (the harness blocks the orchestrator's turn while a subagent runs). Subagents NEVER write these files; a subagent that needs a coverage-map update returns the request to the orchestrator.
- `mempalace mine` is therefore orchestrator-serialized. If a `mine` call still reports `database is locked`, retry it with a tight bounded in-turn backoff (a few attempts, short sleeps — NOT a scheduled wakeup, per the no-arbitrary-timers rule). Mining is idempotent, so a retry is always safe.

### Escalation marker

Whenever the orchestrator stops a turn to wait on a human decision (a Phase 1 ambiguity, an `ambiguous` editability attribute, an oscillation, a bounded loop that exhausted without converging, a push rejected by branch protection), it MUST write `<workspace>/.architect-team/escalation-pending.md` describing exactly what the human must decide. Remove that file when the human responds and the run resumes. The `pipeline-completion-audit` `Stop` hook treats the marker as "legitimately paused for a human" and allows the stop; with NO marker, the hook blocks a stop that leaves the run incomplete. The marker is how the orchestrator distinguishes "I am done" from "I am waiting" — never stop silently on incomplete work.

## Operating rules (non-negotiable)

- Do not begin Phase 2 until Phase 1's validation gate has passed.
- Do not allow any team to mark complete without Phase 3 evidence (the hook enforces this; do not bypass).
- Never integrate without Phase 4 reconciliation when parallel work exists.
- Never declare done at Phase 7 with any coverage gap; re-spawn teams instead.
- Wait for teammates rather than doing their work yourself. **Subagent waits are synchronous and harness-managed** — when you dispatch a subagent via the Task tool, the harness blocks your turn until that subagent finishes (or stops). That IS the wait. You do not need to schedule anything.
- **NEVER schedule arbitrary wall-clock wakeups, cron jobs, or background timer tools from inside the pipeline.** `ScheduleWakeup`, `CronCreate`, `PushNotification`, and similar deferred-execution tools are reserved for explicit `/loop` dynamic-mode invocations and user-requested cron triggers — they are NEVER appropriate inside a pipeline phase. The pipeline runs synchronously, phase-by-phase, in one continuous flow. When iterating via `/ralph-loop` or `/loop`, those commands manage their own cadence — do not stack timer delays on top. When polling for an external resource (dev server ready, build complete, deploy live), use a tight bounded in-turn poll (e.g., `until curl -fsS <url>; do sleep 2; done` with a hard timeout) — not a scheduled wakeup that ends the turn.
- **NEVER respond to the user with "I scheduled a wakeup for N minutes" or "I'll come back to this later" or any phrasing that defers pipeline work via a wall-clock timer.** Pipeline progress is immediate and responsive. If you feel tempted to defer via a timer, you are wrong — either the subagent dispatch handles the wait synchronously, or there is no real reason to wait. Surface the actual blocker to the user (a specific external state being polled, a teammate that needs re-spawning, a missing input, a manual decision required) instead of inserting an opaque delay. The user must never see an arbitrary timer-based deferral.
- Use direct teammate messaging for cross-team coordination (frontend ↔ backend handoffs, contract changes).
- Each teammate owns a distinct file scope. Two teammates never edit the same file.
- The shared task list is the source of truth for progress.
- Respect the global iteration ceiling (20) and the oscillation rule — escalate, never grind past them.
- Never end a run silently on incomplete work: either the `pipeline-completion-audit` runs clean, or you have written `.architect-team/escalation-pending.md`. The `Stop` hook enforces this.
- Run `pipeline-completion-audit.py --check` before the Phase 8 auto-commit; an exit-2 audit blocks the commit.

---

If `$ARGUMENTS` is empty, ask the user for the requirements folder path now and do nothing else until they provide it.
