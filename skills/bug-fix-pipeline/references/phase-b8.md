# Phase B8 — Commit + push

### The full suite once, before the merge (v4.0.0)

`python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 8 --json` returns every test with reason `full-suite-phase` -- no selector flag narrows it and `tests.full_suite_at` in `.architect-team-deploy.json` can only ADD phases. Run every layer plus the prod smoke suite (the `safety: prod` entries of `<e2e-dir>/suite-manifest.json`, when one exists), record the results as evidence, then commit and merge. This single full run is the safety net for everything the test index did not know (`skills/common-pipeline-conventions/references/test-selection.md`, Honest boundaries); B5 ran the selected set and B6 replayed the reproduction artifacts.

### Run-metric recording (v3.8.0)

As part of Phase B8, record the run's §6 success metrics via `hooks/run_metrics.record_run_metrics(workspace, run_id, metrics)` — `dev_loop_iterations`, `first_pass_fix`, `oscillation_count`, `bug_still_present_count`, `fix_regression_count`, `fe_api_verdict` (from `discriminant.json`), `layer_fixed`, the derived `wrong_layer`, and the REQ-DOC-06 `cdlg_edge_recall` / `cdlg_hallucination_rate` (None until the CDLG ships). The metrics land at `<workspace>/.architect-team/run-metrics/<run_id>.json` and are mined to MemPalace run-history. See `common-pipeline-conventions/SKILL.md` `## Run metrics + success measurement (v3.8.0)` for the canonical home + the frozen-bug-benchmark protocol.

### Deploy mandate final gate (v2.20.0)

If `intake_state.deploy_mandate.active == true`, invoke the 18th Layer 3 tool `verify-deploy-mandate-satisfied` BEFORE proceeding with commit + push — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Deploy-mandate row; it BLOCKS). Any of the 4 severities blocks the commit. The bug-fix loop routes SRs with `origin.kind: "deploy-mandate-not-satisfied"`. See `common-pipeline-conventions/SKILL.md` `## Deploy mandate discipline (v2.20.0)` for the canonical home.

### Unilateral-override meta-gate (v3.0.0)

After the deploy-mandate gate, run the `verify-no-unilateral-override` Layer 3 tool as a meta-confession check across all text artifacts the bug-fix run produced (final_report, qa-replayer verdict notes, bug-replicator reproduction-text, remediation_log) — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Unilateral-override row; it BLOCKS). Single severity `unilateral-override-with-virtue-framed-confession` blocks the commit. See `common-pipeline-conventions/SKILL.md` `## Unilateral-override discipline (v3.0.0) — META` for the canonical home.

### Declared-gates ship check (v3.47.0)

After the override meta-gate and before commit + push, walk `<workspace>/.architect-team/declared-gates.json`: every entry the run appended when it named a ship / deploy / merge condition must carry `satisfied_at` and an `evidence_path` that exists and is non-empty. An unsatisfied entry blocks the commit — run the named check, capture its output, append the satisfaction fields. Absent registry is fail-open. A bug-fix run declares these often ("this ships once the QA replay is green against the deployed dev URL"), so the registry is where that promise is kept rather than remembered. `_audit_declared_gates` in `pipeline-completion-audit.py` enforces it at the same gate that already blocks the commit. Canonical rule: `common-pipeline-conventions` `## Declared-gates discipline (v3.47.0)`.

The B8 commit (and any auto-merge) is authored as the checkout's RECORDED person per `common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)` — the `git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=` pair from `.architect-team/git-identity.json`; never a hardcoded author, never ambient git config alone.

Same flow as `architect-team-pipeline` Phase 8 — **documentation-currency gate first** (the `doc-updater` agent dispatch + the `system-architect` Documentation Currency Audit + the commit-blocking gate, per v0.9.23 — same dispatch, same audit, same enforcement as the main pipeline), then completion audit gate, default-branch guard (the work lands on `architect-team/<bug-slug>` feature branch unless `--allow-push-to-default`), commit with the standard message template, push to the feature branch, recommend a PR. **Auto-merge to main (v3.7.0):** when `AUTO_MERGE_MAIN = true` (the default; `--no-auto-merge` opts out) AND the completion audit passed AND the commit landed on `architect-team/<bug-slug>`, after the push call `merge_branch_to_main_and_prune('architect-team/<bug-slug>', '${WORKTREE_PATH}', push=<AUTO_PUSH>)` via the polyglot Python (same invocation as `architect-team-pipeline` Phase 8's `### Auto-merge to main` section; run from the MAIN checkout). On `reason: "merged-and-pruned"` report merged + pruned (branch deleted local + remote, worktree removed) and SKIP the finalize step below. On `conflict: true` fall back to the feature-branch + PR-recommend path + the finalize step below. On `reason: "push-rejected"` (branch protection) STOP + report, never force. When `--no-auto-merge`, skip this and run the finalize step below verbatim. Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`. **End-of-run worktree finalize (v3.6.0):** after the push (and the v3.7.0 auto-merge step when it did NOT already prune the worktree) and before the auto-compact prompt — when this run created a worktree — call `finalize_run_worktree(Path('${WORKTREE_PATH}'))` via the polyglot Python pattern (same invocation as `architect-team-pipeline` Phase 8's `### End-of-run worktree finalize` section): it removes the worktree + branch if the branch is merged into `origin/main`, otherwise leaves the folder and returns a `warning` the orchestrator prints verbatim. Unmerged work is never auto-deleted. Auto-compact prompt at the very end (unless `--no-compact`).

**Documentation-currency gate at Phase B8 (per the `documentation-currency` skill + v0.9.23's `doc-updater` agent):**

0. **Bump version first** — the orchestrator updates `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to the target version. The bug-fix pipeline's typical version bump is a patch (e.g., `0.9.22` → `0.9.23`) since a bug-fix loop ships a small slice; the orchestrator decides the level.
1. **Update — the Lead creates a `doc-updater` task** (v0.9.23, opus, bounded `Write` only to the documentation-currency inventory paths) in the shared list (teams mode) OR dispatches the `doc-updater` subagent (subagents mode). Same dispatch shape as the main pipeline's Phase 8. The agent reads the bug-fix loop's `git diff` (typically small — one or two files plus the new test artifact) and updates whatever inventory docs the diff invalidated. For a tiny bug-fix diff the agent walks the inventory, finds zero stale sections, writes a report with `updates: []` (or a minimal CHANGELOG entry), and exits cheaply. The cost of the dispatch is negligible; the value is structural — bug fixes are not exempt from the doc-currency gate.
1b. **Rebuild the homepage (v4.0.0, best-effort, never blocking).** The page is part of the documentation inventory; the doc-updater's currency walk ends with a rebuild from the now-current sources (`project-homepage` `## Rebuild moments`): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"`.
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
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
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

**Mark the run complete (v3.30.0 — the LAST state action of B8):** after the commit + push (and auto-merge, when it applies) have landed, run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete || python "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete` from the workspace root. Until this runs, the run-continuity enforcement treats the bug-fix run as in-flight (Stops blocked, resumed sessions directed back into this skill). Keep `--set phase="Phase B<N>" slug=<bug-slug>` current at phase boundaries. Per `common-pipeline-conventions` `## Run continuity discipline (v3.30.0)`.

**Delivery manifest — the bill of sale (v3.46.0).** Before emitting `run_complete`, produce the run's delivery manifest per the `delivery-manifest` skill. Assemble the manifest data (plain-speak problem statement; stakeholder-executable validation steps, EACH with an expected result; for a feature, the location + name + functionality of every new element; if the user provided a template/example document, match its vocabulary and layout), write it to `<workspace>/.architect-team/delivery/<bug-slug>-manifest.json`, gate on the engine's zero-error validation, and render the markdown:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/<bug-slug>-manifest.json" --repo-root . || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/<bug-slug>-manifest.json" --repo-root .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/<bug-slug>-manifest.json" --out "<workspace>/.architect-team/delivery/<bug-slug>-manifest.md" --email || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/<bug-slug>-manifest.json" --out "<workspace>/.architect-team/delivery/<bug-slug>-manifest.md" --email
```

A blocking validation finding means the manifest is a draft — fix the data and re-validate before publishing (advisories are prose-quality pointers). The rendered manifest embeds into the final email via the `--plan-file` flag on the `run_complete` invocation below, and is presented to the user as the run's closing deliverable (copy-paste ready).


**Run-complete notification (v3.34.0 — the run's final email, best-effort, per `## Notifications`):** immediately after the run is marked complete (and after B8's own `phase_complete`), emit `run_complete` ONCE — telling recipients the bug-fix run finished end-to-end, that the symptom is gone, and what the fix was:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id <bug-slug> --elapsed "<elapsed since run start>" --commit <final-commit-sha> --details "<bug resolved: the class fixed, QA-replay verdict bug-resolved end-to-end, iterations>" --progress "All B-phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/<bug-slug>-manifest.md" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id <bug-slug> --elapsed "<elapsed since run start>" --commit <final-commit-sha> --details "<bug resolved: the class fixed, QA-replay verdict bug-resolved end-to-end, iterations>" --progress "All B-phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/<bug-slug>-manifest.md"
```
