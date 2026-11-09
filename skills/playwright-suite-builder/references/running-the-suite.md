# Running the suite

- **Dev suite** — the `dev` Playwright project, against the project's dev
  environment. This is what the merge-boundary full run (Phase 8 / B8 / M7 /
  D8 / U9 / P9 — `select --phase 8`) enumerates from the manifest and executes
  in its entirety; Phase 5 and its lane equivalents run the SELECTED flows
  (`skills/common-pipeline-conventions/references/test-selection.md`).
- **Prod smoke suite** — the `prod` project is a first-class runnable smoke suite
  against the production URL, and `skills/test-run-monitor` names it as a
  runnable TEST SOURCE through its existing **command-spawn path
  (`LocalAdapter`)**. Pass the prod project's Playwright command (e.g.
  `playwright test --project=prod`) as the monitor's input with the target
  pointed at production; the monitor's existing source table resolves a bare test
  command to `LocalAdapter` and spawns it. No new input form, no new
  prerequisite, no adapter change. Read-only by construction, enforced by P8 and
  re-checked by `verify-suite-manifest`.

  **Mind the adapter split — the name invites the wrong guess.**
  `ProductionQAAdapter` OBSERVES a signal production is already emitting (it
  polls an APM endpoint, or tails a log file) and executes nothing, so it cannot
  spawn this suite and is not the path for it. Running a prod suite IS a
  test-command spawn.
