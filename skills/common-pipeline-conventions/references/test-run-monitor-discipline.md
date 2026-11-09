# Test-run monitor discipline (v3.3.0)

A passive observer team that watches when testing is happening and produces a per-run report. Strictly log-only: no mid-run interrupts, no auto-SR filing, no pipeline gating. The monitor team is the answer to *"I want to know what's going on across my test runs without paying attention to each one."*

### Source-adapter taxonomy

The same monitor skill handles three distinct testing surfaces via per-source adapters. The orchestrator picks the adapter from the command argument (or the user's explicit `--ci-job` / `--apm-url` / `--log-tail` flag):

| Source | Adapter | Inputs | What it captures |
|---|---|---|---|
| **Local test runs** | `LocalAdapter` | a bare test command (`pytest tests/`, `npm test`, `playwright test`, `vitest run`, `jest`, etc.) | stdout / stderr / exit code / per-test pass+fail counts / captured screenshots for Playwright / trace zips |
| **CI runs** | `CIAdapter` | `--ci-job <name>` + a CI provider env var (`GITHUB_TOKEN` / `GITLAB_TOKEN`) | job status / failure logs / per-job timing / pass rate trend over the last N runs |
| **Production QA / UAT** | `ProductionQAAdapter` | `--apm-url <url>` + an APM token env var (Datadog / New Relic / Sentry) OR `--log-tail <path>` for log-stream observation | error rate / latency p95 / synthetic-probe failures / log-pattern anomalies |

### The 4 failure categories

The synthesizer classifies every finding into one of:

| Category | Trigger |
|---|---|
| `flake` | The same test passed in the previous N runs AND failed in this one with no diff in the test or covered code |
| `regression` | The test passed previously AND failed in this run AND the covered code changed in the run's diff |
| `environmental` | The failure cites infrastructure (network / DB connection refused / OOM / disk full / port-already-in-use / dependency-resolution failure) |
| `new` | The test is new in this run (no prior pass-rate history) — neutral observation, not a problem |

### The per-run report artifact

Path: `<workspace>/.architect-team/monitor-runs/<run-id>/report.json` + `report.md` (both written; JSON is the machine-readable contract, MD is the human-readable summary).

```json
{
  "run_id": "...",
  "monitor_version": "3.3.0",
  "adapter": "local" | "ci" | "production-qa",
  "source_spec": "...",                  // verbatim command or URL
  "started_at": "<ISO 8601 UTC>",
  "completed_at": "<ISO 8601 UTC>",
  "summary": {
    "total_tests": N,
    "passed": N,
    "failed": N,
    "flake_count": N,
    "regression_count": N,
    "environmental_count": N,
    "new_count": N
  },
  "findings": [
    {
      "finding_id": "...",
      "category": "flake" | "regression" | "environmental" | "new",
      "severity": "critical" | "high" | "medium" | "low",
      "test_id": "<test path :: test name>",
      "first_observed_at": "<ISO 8601 UTC>",
      "evidence": {
        "stdout_excerpt": "...",
        "stderr_excerpt": "...",
        "screenshot_path": "...",
        "trace_path": "...",
        "covered_files_diff": "..."
      },
      "remediation_hint": "..."
    }
  ]
}
```

### Strictly passive — non-negotiable

- The monitor MUST NOT inject inbox messages mid-run (v2.19.0 channel is reserved for the user, not for the monitor).
- The monitor MUST NOT auto-file Solution Requirements. The user reads the report; the user decides what becomes an SR.
- The monitor MUST NOT block any pipeline phase. It is observation-only.
- The monitor MUST NOT modify source files. Read-only on the codebase + write-only to `<workspace>/.architect-team/monitor-runs/`.

### Cross-references

- `skills/test-run-monitor/SKILL.md` — the canonical skill body documenting the 3-phase flow (M1 source detection / M2 watch + capture / M3 synthesize).
- `agents/test-run-watcher.md` — drives the source-specific adapter, captures structured findings.
- `agents/monitor-synthesizer.md` — produces the per-run report.
- `commands/monitor-tests.md` — the user-facing entry point `/architect-team:monitor-tests <command-or-source-spec>`.
- Companion to `playwright-user-flows` — the monitor is the SUBSEQUENT observation layer surfacing cross-run patterns (flake trends, environmental noise, regression timing).
