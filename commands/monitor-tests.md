---
description: "Run the v3.3.0 test-run monitor team — a passive observer that watches a test source (local test command / CI job / production APM / log tail) and produces a per-run report at `<workspace>/.architect-team/monitor-runs/<run-id>/report.md`. Strictly log-only — no mid-run interrupts, no auto-SR filing, no pipeline gating. Three source adapters: LocalAdapter (auto-detected from a test command), CIAdapter (`--ci-job <name>`), ProductionQAAdapter (`--apm-url <url>` or `--log-tail <path>`)."
argument-hint: "<test-command> | --ci-job <name> | --apm-url <url> | --log-tail <path>"
---

# /architect-team:monitor-tests

Drive a passive monitor run against a test source. The skill `test-run-monitor` orchestrates 3 phases (M1 source detection / M2 watch + capture / M3 synthesize) and writes a per-run report under `<workspace>/.architect-team/monitor-runs/<run-id>/`.

This is the user-facing entry point to the v3.3.0 monitor team. Strictly passive — the monitor never modifies source, never injects inbox messages mid-run, never files SRs automatically. The user reads the report; the user decides what (if anything) becomes follow-up work.

## Dispatch mode banner — runs first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:monitor-tests" || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:monitor-tests"
```

## Argument parsing

`$MONITOR_INPUT` is everything after `/architect-team:monitor-tests`. The first flag found wins for adapter selection:

| Flag pattern | Adapter |
|---|---|
| `--ci-job <name>` (and optionally `--ci-provider <github\|gitlab\|circleci>`) | CIAdapter |
| `--apm-url <url>` (and optionally `--apm-provider <datadog\|newrelic\|sentry>`) | ProductionQAAdapter (APM variant) |
| `--log-tail <path>` | ProductionQAAdapter (log-tail variant) |
| (no flag — bare command starting with `pytest` / `npm` / `playwright` / `vitest` / `jest` / `mocha` / `cargo test` / `go test` / `dotnet test`) | LocalAdapter |

If `$MONITOR_INPUT` is empty:

```
Usage: /architect-team:monitor-tests <test-command> | --ci-job <name> | --apm-url <url> | --log-tail <path>

Examples:
  /architect-team:monitor-tests pytest tests/ -v
  /architect-team:monitor-tests --ci-job e2e-suite --ci-provider github
  /architect-team:monitor-tests --apm-url https://api.datadoghq.com/api/v1/...
  /architect-team:monitor-tests --log-tail /var/log/app.log
```

## Phase 1 — Workspace resolution

```bash
WORKSPACE="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Validate the workspace is a git repo. If not, surface a one-line note and exit cleanly — the monitor needs `.architect-team/` state to write its output.

## Phase 2 — Adapter detection + intake state

Per the rules above, pick the adapter. Generate the run-id:

```bash
RUN_ID="monitor-$(date -u +%Y-%m-%dT%H%M%S)-$(head -c 6 /dev/urandom | xxd -p | head -c 6)"
mkdir -p "${WORKSPACE}/.architect-team/monitor-runs/${RUN_ID}/findings"
```

Write the intake state:

```bash
python3 -c "
import json, os
from datetime import datetime, timezone
run_id = os.environ['RUN_ID']
state = {
    'run_id': run_id,
    'adapter': os.environ['ADAPTER'],
    'source_spec': os.environ['SOURCE_SPEC'],
    'started_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
}
path = f'${WORKSPACE}/.architect-team/monitor-runs/{run_id}/source.json'
with open(path, 'w') as f: json.dump(state, f, indent=2, sort_keys=True)
" || python -c "
import json, os
from datetime import datetime, timezone
run_id = os.environ['RUN_ID']
state = {
    'run_id': run_id,
    'adapter': os.environ['ADAPTER'],
    'source_spec': os.environ['SOURCE_SPEC'],
    'started_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
}
path = f'${WORKSPACE}/.architect-team/monitor-runs/{run_id}/source.json'
with open(path, 'w') as f: json.dump(state, f, indent=2, sort_keys=True)
"
```

## Phase 3 — Invoke the test-run-monitor skill

Use the `Skill` tool with `skill: test-run-monitor`. Pass the bound `$MONITOR_INPUT` + `$RUN_ID` + `$ADAPTER` + `$WORKSPACE` as inputs.

The skill dispatches the `test-run-watcher` agent at Phase M2 and the `monitor-synthesizer` agent at Phase M3. On completion, the skill returns the path to `report.md`.

## Phase 4 — Compact summary

After the skill returns, print:

```
╔════════════════════════════════════════════════════════════════╗
║  ◆  CT6 v3.3.0 test-run monitor — complete                     ║
║                                                                ║
║  Adapter:  <local | ci | production-qa>                        ║
║  Source:   <source-spec excerpt>                               ║
║  Run-id:   <run-id>                                            ║
║                                                                ║
║  Findings: <N total>                                           ║
║    flake:         <N>                                          ║
║    regression:    <N>                                          ║
║    environmental: <N>                                          ║
║    new:           <N>                                          ║
║                                                                ║
║  Report:   .architect-team/monitor-runs/<run-id>/report.md     ║
╚════════════════════════════════════════════════════════════════╝
```

## Safety rules

- Strictly passive. The command never modifies source files, never injects inbox messages, never files SRs, never gates any other pipeline.
- Read-only on the codebase. Write-only to `<workspace>/.architect-team/monitor-runs/<run-id>/`.
- Budget-bounded. Default 30-minute watcher budget; longer runs require explicit user authorization.
- Best-effort. A missing prerequisite (CI token unset / APM URL unresolvable / log file missing) produces a one-line note + clean exit, not a hard failure.

## Cross-references

- `skills/test-run-monitor/SKILL.md` — the canonical skill body documenting the 3-phase flow.
- `agents/test-run-watcher.md` (sonnet, color teal) — Phase M2 adapter execution + per-finding capture.
- `agents/monitor-synthesizer.md` (opus, color teal) — Phase M3 classification + report synthesis.
- `common-pipeline-conventions/SKILL.md` `## Test-run monitor discipline (v3.3.0)` — the canonical home + the 4-category classification + the per-run report schema.
