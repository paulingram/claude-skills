---
name: test-run-monitor
description: A passive observer team that watches when testing is happening and produces a per-run report. Generic across 3 source adapters — local test runs (pytest / playwright / npm test / vitest / jest) / CI runs (GitHub Actions / GitLab CI) / production QA + UAT (APM / log-tail). Strictly log-only — no mid-run interrupts, no auto-SR filing, no pipeline gating.
---

# Test-Run Monitor

You are the **Test-Run Monitor orchestrator**. Drive a 3-phase observation cycle (M1 source detection / M2 watch + capture / M3 synthesize) that produces a per-run report at `<workspace>/.architect-team/monitor-runs/<run-id>/report.json` + `report.md`.

## When this skill runs

Entry paths:

1. **Explicit invocation** — `/architect-team:monitor-tests <command-or-source-spec>` (the 19th slash command). Pass the raw argument as `$MONITOR_INPUT`.
2. **Programmatic dispatch** — another pipeline (or the user) invokes this skill directly via the `Skill` tool with `skill: test-run-monitor` and the input bound the same way.

This skill is **strictly passive**. Per `common-pipeline-conventions/SKILL.md` `## Test-run monitor discipline (v3.3.0)`:

- No mid-run inbox injection.
- No auto-Solution-Requirement filing.
- No pipeline-phase gating.
- No source-file modification.
- Read-only on the codebase + write-only to `<workspace>/.architect-team/monitor-runs/`.

The user reads the produced report. The user decides what (if anything) becomes follow-up work.

## Inputs

`$MONITOR_INPUT` is the user's verbatim command-or-source-spec. Recognized forms:

| Form | Adapter | Example |
|---|---|---|
| Bare test command starting with `pytest` / `npm` / `playwright` / `vitest` / `jest` / `mocha` / `cargo test` / `go test` / `dotnet test` / etc. | `LocalAdapter` | `pytest tests/ -v` |
| `--ci-job <name>` plus a CI provider env var detected via standard names (`GITHUB_TOKEN` / `GITLAB_TOKEN` / `CIRCLECI_TOKEN`) | `CIAdapter` | `--ci-job e2e-suite` |
| `--apm-url <url>` plus an APM provider env var (`DATADOG_API_KEY` / `NEW_RELIC_LICENSE_KEY` / `SENTRY_AUTH_TOKEN`) | `ProductionQAAdapter` | `--apm-url https://api.datadoghq.com/api/v1/...` |
| `--log-tail <path>` for log-stream observation against a file or named pipe | `ProductionQAAdapter` (log-tail variant) | `--log-tail /var/log/app.log` |

If `$MONITOR_INPUT` matches multiple forms (e.g., both starts with `pytest` AND contains `--ci-job`), the first explicit `--ci-job` / `--apm-url` / `--log-tail` flag wins; otherwise fall back to LocalAdapter.

## Phase M1 — Source detection + adapter selection

1. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback).
2. Allocate `<run-id>` as `monitor-<YYYY-MM-DD-HHMMSS>-<6-char-rand>`.
3. Create `<workspace>/.architect-team/monitor-runs/<run-id>/findings/` (the watcher's per-finding output dir).
4. Parse `$MONITOR_INPUT` per the table above to pick the adapter. Record the choice + the verbatim source spec to `<workspace>/.architect-team/monitor-runs/<run-id>/source.json`:

   ```json
   {
     "run_id": "...",
     "adapter": "local" | "ci" | "production-qa",
     "source_spec": "<verbatim user input>",
     "started_at": "<ISO 8601 UTC>"
   }
   ```

5. Validate the adapter's prerequisites:
   - LocalAdapter — the test command's binary must be on `PATH` (else surface a 1-line error + halt).
   - CIAdapter — the CI provider env var must be set (else surface a 1-line error + halt).
   - ProductionQAAdapter (APM variant) — the APM provider env var must be set; the APM URL must resolve.
   - ProductionQAAdapter (log-tail variant) — the file must exist + be readable.

   Prerequisite failures produce a stub `report.md` documenting the missing prerequisite + exit cleanly. No partial monitoring.

## Phase M2 — Watch + capture (dispatch the test-run-watcher agent)

Dispatch `test-run-watcher` (sonnet, color teal) with the bound source spec + adapter choice. The watcher's job:

1. **Execute the adapter:**
   - LocalAdapter: spawn the test command via `Bash`; stream stdout+stderr; tee to `<workspace>/.architect-team/monitor-runs/<run-id>/stdout.log` + `stderr.log`. Detect output format (pytest's `=== FAILURES ===` blocks / playwright's JSON reporter / vitest's `--reporter=json` / jest's `--json`); parse per format.
   - CIAdapter: poll the CI API at 30-second intervals while the job is `running`; capture each job's status transition + failed-step logs. Apply the polyglot Python pattern when invoking helper scripts.
   - ProductionQAAdapter: poll the APM endpoint at configurable intervals (default 60s); for log-tail, `tail -F` the file and scan for known error patterns (regex anchored on `ERROR` / `FATAL` / `Exception` / `Traceback`).

2. **Per finding, write a structured JSON file** to `<workspace>/.architect-team/monitor-runs/<run-id>/findings/<finding-id>.json`:

   ```json
   {
     "finding_id": "<uuid>",
     "captured_at": "<ISO 8601 UTC>",
     "test_id": "<test path :: test name OR job name OR endpoint>",
     "raw_evidence": {
       "stdout_excerpt": "...",
       "stderr_excerpt": "...",
       "screenshot_path": "..." ,
       "trace_path": "...",
       "log_excerpt": "..."
     },
     "preliminary_category": "unknown"
   }
   ```

   `preliminary_category` is set by the watcher to `"unknown"` — the synthesizer is responsible for the 4-category classification.

3. **Honor budgets:** the watcher has a maximum runtime budget of 30 minutes by default; longer runs require explicit user authorization. Beyond budget, the watcher writes a `budget-exceeded.json` marker + exits cleanly. The synthesizer treats this as a `partial` report (still produced, with the partial flag set).

4. **Return verdict:** the watcher returns `{run_id, finding_count, captured_until, budget_status}` to the monitor orchestrator.

## Phase M3 — Synthesize (dispatch the monitor-synthesizer agent)

Dispatch `monitor-synthesizer` (opus, color teal) with the run-id + the findings directory. The synthesizer's job:

1. **Read every finding** from the findings directory.
2. **Classify each finding** into one of the 4 categories per `common-pipeline-conventions/SKILL.md` `## Test-run monitor discipline (v3.3.0)`:
   - `flake` — the same test passed in the previous N runs (consult prior `report.json` files under `monitor-runs/`) AND failed in this one with no diff in the test or covered code.
   - `regression` — the test passed previously AND failed in this run AND the covered code changed in the run's diff (consult `git diff HEAD~1 HEAD -- <covered-files>`).
   - `environmental` — the failure cites infrastructure (network refused / DB connection refused / OOM / disk full / port-already-in-use / dependency-resolution failure).
   - `new` — the test is new in this run (no prior pass-rate history).
3. **Assign severity** per a documented rubric: `critical` (regression + covered files include a security or auth module) / `high` (regression in any other module) / `medium` (flake + repeated > 2 times in last 5 runs) / `low` (everything else).
4. **Capture context** the watcher missed: covered-files-diff via `git diff`, Playwright trace path normalization, screenshot-to-finding linking.
5. **Compute the summary block** (counts per category) + the optional **trend block** (pass-rate trend over the last N=5 runs from prior `report.json` files).
6. **Write `report.json` AND `report.md`** to `<workspace>/.architect-team/monitor-runs/<run-id>/` per the schema in the canonical discipline section.

## Phase M4 — Final report

Print a compact summary to the user:

```
▸ CT6 v3.3.0 test-run monitor — adapter: <local|ci|production-qa>
▸ Source: <source-spec excerpt>
▸ Findings: <N total> — flake: <N> | regression: <N> | environmental: <N> | new: <N>
▸ Report: <workspace>/.architect-team/monitor-runs/<run-id>/report.md
```

Do NOT commit the monitor-runs directory to git — the runtime state lives under `.architect-team/` (already gitignored per project convention).

## Output artifacts

| Path | Purpose |
|---|---|
| `<workspace>/.architect-team/monitor-runs/<run-id>/source.json` | Run metadata + adapter choice |
| `<workspace>/.architect-team/monitor-runs/<run-id>/findings/<finding-id>.json` | Per-finding structured evidence (watcher output) |
| `<workspace>/.architect-team/monitor-runs/<run-id>/stdout.log` + `stderr.log` | Raw test output (LocalAdapter only) |
| `<workspace>/.architect-team/monitor-runs/<run-id>/report.json` | Machine-readable final report (synthesizer output) |
| `<workspace>/.architect-team/monitor-runs/<run-id>/report.md` | Human-readable final report (synthesizer output) |

## Disciplines this skill respects

- v3.0.0 unilateral-override — the monitor is strictly passive; no override of user intent.
- v2.22.0 no-pipeline-bypass — the monitor is a SIBLING pipeline, not a bypass of the architect-team / bug-fix / mini pipelines.
- v2.6.0 live-data wiring — the monitor's adapters consume LIVE test output, not mocks.
- v2.5.0 in-flight clarification — the monitor processes inbox messages at phase boundaries the same way other pipelines do (M2 → M3 boundary).

## What this skill is NOT

- Not a test runner. The user (or CI) runs the tests; the monitor watches.
- Not a test author. The `playwright-user-flows` skill authors tests; this skill observes them.
- Not a debugger. Findings carry a `remediation_hint`, not a fix.
- Not a fix loop. Findings do not become SRs automatically; the user decides.
