---
description: Report which CT6 codebase disciplines have been applied to the current codebase (the v2.18.0 codebase discipline registry). Read-only by default; pass --apply to auto-execute auto-apply-safe disciplines that are missing or stale. The same logic Phase 0.1 fires automatically at every pipeline-run start, exposed as a user-triggered standalone command for "is my codebase up to date with CT6?"
argument-hint: "[--apply] [--workspace <path>]"
---

# /architect-team:discipline-status

Reports per-discipline applied / not-applied / stale state for the current
codebase, against the CT6 discipline catalog (`hooks/discipline_registry.py`
`DISCIPLINE_CATALOG`). With `--apply`, auto-executes any auto-apply-safe
discipline the freshness check finds missing or stale.

This is the user-facing entry point to the same freshness-check mechanism
that Phase 0.1 of every `/architect-team` family run fires automatically.
Use it when you want to inspect or remediate the codebase WITHOUT starting
a full pipeline run.

## Dispatch mode banner — runs first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:discipline-status" || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:discipline-status"
```

## Argument parsing

Recognised flags:

- `--apply` → auto-execute every auto-apply-safe discipline the freshness check finds un-applied or stale. Default OFF — without the flag the command is read-only.
- `--workspace <path>` → operate on the given codebase root instead of cwd. Default: `git -C <cwd> rev-parse --show-toplevel` (cwd fallback).

## Phase 1 — Resolve workspace

```bash
WORKSPACE="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
```

## Phase 2 — Run the freshness check

Invoke the 16th Layer 3 tool:

```bash
mkdir -p "${WORKSPACE}/.architect-team/vao-verdicts"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
VERDICT="${WORKSPACE}/.architect-team/vao-verdicts/${RUN_ID}-discipline-registry.json"
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-discipline-registry-current --workspace "${WORKSPACE}" --out "${VERDICT}" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-discipline-registry-current --workspace "${WORKSPACE}" --out "${VERDICT}"
```

## Phase 3 — Display the report

Read the verdict JSON. Render a clean per-discipline table:

```
CT6 codebase discipline status — workspace: <workspace>

  Discipline                              Version   Status              Evidence
  ─────────────────────────────────────────────────────────────────────────────
  prod-safe-test-classification           v2.17.0   ✓ applied           38 tests classified
  live-data-wiring                        v2.6.0    ⚠ not applied (SR)  mock-state in 3 files
  multi-persona-path-coverage             v2.11.0   ⚠ not applied (SR)  persona-inventory missing
  affordance-coverage                     v2.13.0   ⚠ not applied (SR)  file-upload affordance detected

  Registry: <workspace>/.architect-team/discipline-registry.json
  Last freshness check: <ISO timestamp from registry>
```

`Status` legend:
- `✓ applied` — registry entry exists AND codebase shows it applied
- `⏳ stale` — registry entry exists BUT codebase has advanced past it
- `▸ auto-apply-safe (run --apply)` — un-applied AND can be auto-executed
- `⚠ not applied (SR)` — un-applied AND requires human-decision SR routing
- `✓ trivially applied` — no codebase surface the discipline covers (e.g., zero tests for the classifier)

## Phase 4 — Apply mode (when `--apply` was passed)

For every gap with `auto_apply_safe == true`:

1. Print a one-line banner: `▸ CT6 v2.18.0: applying <discipline> via <auto_update_command>`
2. Invoke the command/skill named in `auto_update_command` against the workspace
3. On success, record the application via `hooks.discipline_registry.record_application(workspace, discipline, ...)`
4. Re-run the freshness check at the end and print the updated table

For gaps with `auto_apply_safe == false`: print a one-line note recommending the SR route + the canonical `sr_origin_kind`. The `discipline-status` command does NOT spawn fix loops directly — that's the pipeline's job (Phase 0.1 routes them automatically; this command surfaces them for user awareness).

## Safety rules

- Read-only by default. The `--apply` flag is the only path to mutations.
- Even with `--apply`, only `auto_apply_safe == true` disciplines run. SR-route-only disciplines never auto-execute — they require pipeline integration.
- Best-effort. If `verify-discipline-registry-current` fails for any reason, surface the error and exit cleanly. Do NOT amend or delete the registry file on tool failure.

## Cross-references

- `skills/common-pipeline-conventions/SKILL.md` `## Codebase discipline registry (v2.18.0)` — the canonical home.
- `hooks/discipline_registry.py` — the catalog + freshness-check helper module.
- `hooks/vao_tools.py::verify_discipline_registry_current` — the 16th Layer 3 tool this command invokes.
- `skills/architect-team-pipeline/SKILL.md` `## Phase 0.1 — Discipline freshness check (v2.18.0)` — the automatic counterpart that fires at every pipeline run.
