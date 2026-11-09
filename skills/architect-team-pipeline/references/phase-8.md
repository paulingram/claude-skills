# Phase 8 — Final Report

### The full suite once, before the merge to main (v4.0.0)

`python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 8 --json` returns every test with reason `full-suite-phase` -- no selector flag narrows it and `tests.full_suite_at` in `.architect-team-deploy.json` can only ADD phases. Run every layer plus the prod smoke suite (the `safety: prod` entries of `<e2e-dir>/suite-manifest.json`), record the results as evidence, then merge. This single full run is the safety net for everything the test index did not know (`skills/common-pipeline-conventions/references/test-selection.md`, Honest boundaries); Phases 3 and 5 ran the selected sets.

### Deploy mandate final gate (v2.20.0)

If `intake_state.deploy_mandate.active == true`, invoke the 18th Layer 3 tool `verify-deploy-mandate-satisfied` BEFORE emitting the final report — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Deploy-mandate row; it BLOCKS).

A non-zero exit (any of the 4 severities — `deploy-mandate-not-satisfied` / `plan-only-deliverable-on-deploy-mandate` / `adjacent-dependencies-claimed-as-deployment` / `partial-deploy-passed-off-as-deploy`) is a hard-fail. The orchestrator MUST NOT commit or push the run. The fix loop kicks in: route SRs with `origin.kind: "deploy-mandate-not-satisfied"`; the existing team-dispatch surface (backend if missing `deploy_target_url`; frontend if missing `frontend_url` or `unwired_elements_count > 0`) handles each gap.

See `common-pipeline-conventions/SKILL.md` `## Deploy mandate discipline (v2.20.0)` for the canonical home.

### Unilateral-override meta-gate (v3.0.0)

After all per-discipline Phase 8 gates pass, run the `verify-no-unilateral-override` Layer 3 tool as a META-confession check across every text artifact the run produced (final_report, verification_text, verification_notes, remediation_log, qa-replayer verdicts) — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Unilateral-override row; it BLOCKS). The `--sources` input is a JSON dict at `<workspace>/.architect-team/vao-evidence/<run-id>-text-sources.json` mapping source-name → text content (e.g., `{"final_report": "...", "verification_text": "...", "qa_replayer_notes": "..."}`).

A single severity (`unilateral-override-with-virtue-framed-confession`) fires when ANY source contains a virtue-framed opener + element-of-bypass admission. The orchestrator MUST NOT commit on a fail — re-invoke the pipeline against the same user prompt and produce text without the confession ritual.

See `common-pipeline-conventions/SKILL.md` `## Unilateral-override discipline (v3.0.0) — META` for the canonical home + the unified marker dictionary.

Emit a final report containing:

- For each original requirement: implementing commit(s) → test(s) → Playwright flow(s)
- Total commits, files changed, lines added/removed
- Total tests added (unit / integration / e2e), all passing
- All Playwright flows executed, with timing and pass status
- Appearance proposals per the run's `appearance_mode` (v3.14.0): under `strict`, a READ-ONLY "Appearance proposals (not implemented — strict mode)" listing citing `<workspace>/.architect-team/appearance-proposals/<run-id>.json` and stating how to act on them in a future invocation (imperative, never interrogative — no v2.10.0 follow-up-question phrasings); under `propose`, the per-proposal gate decisions with citations; under `innovate`, every `implemented-innovate` visual delta enumerated
- Each teammate spawned, its task group, and outcome
- Final statement: **"Spec `<change-name>` has been implemented."** Followed by the archive path.

### Mock-retirement gate (v3.48.0 — contract-first parallelism CFP-6)

If this run created ANY interface contract at Phase 2 (`contract-first-parallelism`), the parallelism it bought was borrowed against server-side mocks. Closing the run repays it. Run the gate BEFORE the documentation-currency gate and the commit:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger "<workspace>/.architect-team/contracts/ledger.json" || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger "<workspace>/.architect-team/contracts/ledger.json"
```

**Any surface still `mock-serving` (or earlier) is a BLOCKING finding: the run does not close.** So is any entry the gate reports it could not read — an unrecognized state, an entry that is not an object, or a ledger wrapped in a shape the engine does not know. The gate fails CLOSED on all of them, because a green report on unparseable input is the one outcome worse than no gate. Route it back to the owning backend teammate to flip the surface to real data and verify end-to-end through the same live path the frontend already calls, then transition the ledger entry to `live` with its `verified_by` evidence. "Retire it next run" is not a disposition — it is exactly the deferral `## No end-of-run deferral discipline` forbids, and a mock that outlives its run is the debt the no-fake-data disciplines exist to prevent.

Also confirm no contract drifted while the internals were being built, in the retirement reading (`... drift --json <contract.json> --observed <observed-payload.json> --retirement` against a payload actually captured from the live surface), which additionally refuses a payload still carrying its provisional marker; a drift finding is a real defect, not paperwork — the frontend built against the approved shape.

Then capture the gate's output and close each contract's declared gate (`... satisfy-gate --gate-id cfp-retirement-<contract-id> --evidence <captured-output> --registry "<workspace>/.architect-team/declared-gates.json"`). Those entries are what the declared-gates ship check below and `_audit_declared_gates` block on — the registration is how "the run does not close" is enforced by machinery rather than by this instruction alone.

A run that created no contracts skips this gate: with no ledger file the command prints `no contracts recorded` and exits 0, so an absent or empty ledger is a no-op, not a failure.


### Documentation-currency gate (before the final report and the commit)

Per the `documentation-currency` skill, the run does NOT push with stale documentation. Immediately after the mock-retirement gate above, and before the final report is emitted and before the auto-commit:

0. **Bump version first.** Before the doc-updater dispatch, the orchestrator updates `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` to the target version. These two files are the version-source-of-truth; the doc-updater READS them but does NOT write them (they are explicitly outside its Bounded Write scope). Every other version reference across the inventory gets aligned to what those JSON files say.
1. **Update — the Lead creates a `doc-updater` task (v0.9.23).** The Lead creates a `doc-updater` task in the shared list (teams mode) OR dispatches the `doc-updater` subagent (subagents mode). The agent (opus, bounded `Write` ONLY to the documentation-currency inventory paths, NO `Edit`, NO source-code writes) reads the run's `git diff` against the merge base, the coverage map, the run ledger, and the current state of every inventory doc — `README.md` (per `readme-styling`), `CHANGELOG.md`, `CLAUDE.md` / `AGENTS.md` if present, and the maps (`CODEBASE_MAP.md`, `ROUTE_MAP.md`, `DESIGN_MAP.md`, `INTERACTION_INTUITION_MAP.md`, `INTEGRATION_MAP.md`). It identifies every stale section relative to what the run actually shipped and edits each in place via whole-file rewrites (the agent's allowlist excludes `Edit` to enforce whole-file consistency — partial-update inconsistency where one count is bumped but a related count isn't is the failure mode this prevents). Output: `<cwd>/.architect-team/documentation-currency/updates-<ISO-8601-UTC>.json` — every file touched + every section updated + the triggering justification (diff entry, coverage-map REQ, or count comparison). Promotion rationale (v0.9.23): the previous "the orchestrator performs the updates" sentence cracked when the orchestrator was at end-of-context with a 30-file diff — items got missed. A dedicated agent is the structural fix.
2. **Audit.** The Lead creates a `system-architect` task in **Documentation Currency Audit** mode (teams mode) OR dispatches the `system-architect` subagent in that mode (subagents mode). Unchanged from v0.9.15. It independently walks the `documentation-currency` inventory against the run's diff + the coverage map + the doc-updater's report and writes a verdict to `<cwd>/.architect-team/documentation-currency/audit-<ISO-8601-UTC>.json` (`overall: pass | fail` + per-doc findings). The `doc-updater` produced the doc updates; the `system-architect` is the independent checker (producer/checker, per the v0.9.13 discipline). The audit's verdict — not the agent's self-report — gates the commit.
3. **Gate.** A `fail` verdict names the exact stale docs — the orchestrator re-dispatches the `doc-updater` with the audit's findings as additional input, then re-audits. The auto-commit below does not proceed until the latest documentation-currency audit verdict is `overall: pass`; `pipeline-completion-audit.py` enforces this. This is non-negotiable: a stale map breaks the next run's reuse-first design, and a stale README ships a lie.

### Persist + mine the final report

After emitting the final report to the user, persist a copy of the report's text to `<cwd>/.architect-team/runs/<change-name>-<ISO-8601-UTC>.md` and auto-mine it (per `mempalace-integration`):

```bash
mempalace --palace <palace> mine "<cwd>/.architect-team/runs/<change-name>-<ts>.md" --wing <wing>
```

This makes the run's outcome semantically queryable from future runs.

### Declared-gates ship check (v3.47.0)

Before the auto-commit below runs, every gate this run DECLARED must be satisfied. Walk `<workspace>/.architect-team/declared-gates.json`: each entry needs a `satisfied_at` and an `evidence_path` that exists and is non-empty. An unsatisfied entry stops the ship step — run the check the entry names, capture its output, append the satisfaction fields, and only then proceed. An absent registry is fail-open (this run declared nothing). The completion audit in step 0 below enforces the same rule via `_audit_declared_gates`, quoting the gate's own `declaration_text` back; checking here first means the run fixes it before staging rather than after. Never edit or delete an entry to make the audit pass — that is the unilateral override the meta-gate catches. Canonical rule: `common-pipeline-conventions` `## Declared-gates discipline (v3.47.0)`.

### Frontend-E2E loop-exit gate (v3.55.0)

A frontend-impacting change is not done until a real user clicked through it. Before the auto-commit runs, every frontend slice this run shipped must carry a genuine passing E2E verdict at `<workspace>/.architect-team/frontend-e2e/<slice>-verdict.json` — the artifact the Phase 5 integration / frontend agent writes when it runs the Playwright user-flow against the live dev environment (see Phase 5). The run-level `_audit_frontend_e2e` arm in `pipeline-completion-audit.py` (step 0 below) aggregates `files_changed` across `.architect-team/reviews/*.json`, runs the v3.44.0 `changed_files_touch_frontend` detector, and — for any slice that touched a real frontend UI file — BLOCKS the commit unless its verdict is `verdict == "passed"` AND passes DEEP genuineness. The arm REUSES the 22nd Layer-3 tool `verify-frontend-e2e-loop-exit` (not a shallow `len()>=1` count): a verdict whose `user_driven_actions` are all `page.request`/`fetch` (api-only), whose `visible_state_assertions` are only title/navigate asserts (vacuous), that was not executed against a live env, or whose `trace_path` names no existing file is BLOCKED by the arm and named by its escape severity (described-not-executed, API-only, vacuous-navigate-assert, trace-claimed-but-absent). The per-task `frontend_impact_e2e_review` note cannot escape this: the run-level arm requires the EXECUTED, genuine artifact, never the note. Kill-switch `CT6_FRONTEND_E2E_GATE_DISABLED` is the operator escape if the gate ever misfires; a run that touched no frontend is a no-op.

**The gate is scoped to THIS run (v3.57.0), and satisfying it is the run's own job.** `.architect-team/reviews/` is cumulative, so the arm considers only slices this run owns — claimed by a teammate manifest, or written after the active-run marker's `started_at` — and prints how many it excluded as inherited debt. A newly-introduced gate must never wall off the next commit with a previous run's backlog. And when a frontend slice has no verdict yet because the route is not deployed or dev has no data, that is **Phase 5's work, not a question for the user**: bring the environment up (or run `deploy_command`), seed the records the flow needs through the application's own create path, then run the flow. See `common-pipeline-conventions` `## Local -> dev -> test-on-dev is the pipeline's job, not the user's (v3.57.0)`. Escalate only a genuine external blocker — asking *"how do you want to proceed?"* with a recommended option attached is the run asking permission to do its own job.

> **STOP.** When every gate above is green, Read `skills/architect-team-pipeline/references/phase-8-commit.md` and execute it in full: the auto-commit, the safety rules, the auto-merge, the worktree finalize, the mark-complete, the run-complete notification and the auto-compact prompt.
