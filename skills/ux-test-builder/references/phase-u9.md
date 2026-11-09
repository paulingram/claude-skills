# Phase U9 — Final report

Emit a summary report at `<cwd>/.architect-team/runs/ux-test-<persona-slug>-<ts>.md`:

- **Persona:** the description verbatim.
- **Objectives:** the user's stated objective.
- **Target:** the URL (or dev environment reference).
- **Credentials:** the env-var name (NEVER the secret).
- **Site-map freshness:** refreshed at U1, or cached.
- **Distilled flow count + source breakdown:** literal + per-explorer attribution.
- **Per-flow consensus verdicts:** the verdict table.
- **Disagreement summary:** which flows needed re-examination + how many cycles; any flows escalated.
- **Bug count + bug-fix-pipeline SR references:** the list of SRs queued in the bug-fix-pipeline.
- **Final statement:** *"UX test plan for persona `<persona-slug>` against `<target>` executed. N flows attempted, M passed, K failed, B bugs documented and routed to bug-fix-pipeline."*

**Documentation currency and the homepage (v4.0.0).** Before the commit below, the `documentation-currency` gate runs as in Phase 8 (the `doc-updater` dispatch + the independent `system-architect` audit — `## Relationship to other skills`), and its whole-file currency walk ends with a homepage rebuild (best-effort, never blocking; `project-homepage` `## Rebuild moments`): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"`.

**The full suite once, before the commit (v4.0.0).** `python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 8 --json` returns every test with reason `full-suite-phase` -- the target's whole suite including the dev Playwright project enumerated from `<e2e-dir>/suite-manifest.json` (the flows this run registers below are part of it). Run it against the live target, record the result in the report, then commit; U6 ran the run's own distilled flows, which are the deliverable, not a selection. The rule: `skills/common-pipeline-conventions/references/test-selection.md`.

**Register the run's flows in the suite manifest.** When the target codebase carries `<e2e-dir>/suite-manifest.json`, register the distilled flows there per `playwright-suite-builder` before the commit below — one entry per flow, `persona` set to this run's persona slug, `kind: journey`, `source: user-flow` — so a run's flows become part of the target's durable suite instead of living only in this run's state directory. Absent a suite manifest, behavior is unchanged.

**Declared-gates ship check (v3.47.0).** Before the commit + push below, walk `<workspace>/.architect-team/declared-gates.json`: every entry must carry `satisfied_at` and an `evidence_path` that exists and is non-empty. A UX-test run declares gates in exactly the place they are easiest to lose — "we close this out once every distilled flow has run against the live target" — so an unsatisfied entry blocks the close-out until the named check runs and its output is cited. Absent registry is fail-open. Canonical rule: `common-pipeline-conventions` `## Declared-gates discipline (v3.47.0)`.

Persist the report; auto-mine to MemPalace (`--room ux-test-reports`); auto-commit + push per the Phase 8 default-branch guard discipline, the commit authored as the checkout's RECORDED person per `common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)` (the `git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=` pair — never a default author) (feature branch `architect-team/ux-test-<persona-slug>` unless `--allow-push-to-default`). **Immediately after the commit succeeds**, emit a `git_commit` notification (best-effort, per `## Notifications`) with the new commit's SHA — same wiring as the main pipeline's Phase 8 commit:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha> --details "<the UX-test report + flow specs this commit ships>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha> --details "<the UX-test report + flow specs this commit ships>"
```

**Mark the run complete (v3.30.0 — the LAST state action of U9):** after the commit + push land, run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete || python "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete` from the workspace root. Until then the run-continuity enforcement treats the UX-test run as in-flight. Keep `--set phase="Phase U<N>" slug=ux-test-<persona-slug>` current at phase boundaries. Per `common-pipeline-conventions` `## Run continuity discipline (v3.30.0)`. Note: bugs routed to `bug-fix-pipeline` at U8 are their OWN runs with their own markers — the UX run marks complete when ITS phases are done, per the SR hand-off contract.

**Delivery manifest — the bill of sale (v3.46.0).** Before emitting `run_complete`, produce the run's delivery manifest per the `delivery-manifest` skill. Assemble the manifest data (plain-speak problem statement; stakeholder-executable validation steps, EACH with an expected result; for a feature, the location + name + functionality of every new element; if the user provided a template/example document, match its vocabulary and layout), write it to `<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.json`, gate on the engine's zero-error validation, and render the markdown:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.json" --repo-root . || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.json" --repo-root .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.json" --out "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.md" --email || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.json" --out "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.md" --email
```

A blocking validation finding means the manifest is a draft — fix the data and re-validate before publishing (advisories are prose-quality pointers). The rendered manifest embeds into the final email via the `--plan-file` flag on the `run_complete` invocation below, and is presented to the user as the run's closing deliverable (copy-paste ready).


**Run-complete notification (v3.34.0 — the run's final email, best-effort, per `## Notifications`):** immediately after the run is marked complete (and after U9's own `phase_complete`), emit `run_complete` ONCE — the final-statement summary as an email:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id "ux-test-<persona-slug>" --elapsed "<elapsed since run start>" --commit <commit-sha> --details "<N flows attempted, M passed, K failed, B bugs documented and routed to bug-fix-pipeline>" --progress "All U-phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.md" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id "ux-test-<persona-slug>" --elapsed "<elapsed since run start>" --commit <commit-sha> --details "<N flows attempted, M passed, K failed, B bugs documented and routed to bug-fix-pipeline>" --progress "All U-phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/ux-test-<persona-slug>-manifest.md"
```
