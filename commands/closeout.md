---
description: Run the closeout double-check (CO-1…CO-3) at the end of a work session — review what changed this session against the requirement, confirm the documentation-currency inventory is up to date, and update any stale doc rather than just flagging it. Read-only with --check (deterministic staleness signals only); the default performs the review + update via the closeout skill. The same check the PreCompact hook fires automatically before context is compacted, exposed as a user-triggered standalone command.
argument-hint: "[--check] [--workspace <path>]"
---

# /architect-team:closeout

Closes out a work session: confirms the documentation reflects what changed and
updates any doc that is lax — BEFORE you compact or declare the work done. This
is the manual entry point to the same mechanism the `PreCompact` hook
(`hooks/precompact-closeout.py`) fires automatically before compaction.

Use it when you want to verify or remediate documentation currency at a session
boundary WITHOUT starting a full pipeline run. It works from the git working-tree
diff, so it functions in any repo, pipeline or not.

## Dispatch mode banner — runs first

The interpreter is selected ONCE via `$(command -v python3 || command -v python)`
(the v2.16.0 detect-once form), so the banner script runs exactly once. Best-effort
— a subprocess failure surfaces a one-line note and the command continues.

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:closeout"
```

## Argument parsing

Recognised flags:

- `--check` → read-only: run the deterministic engine and print the staleness
  signals only; do NOT update any doc. Default OFF — without the flag the command
  performs the full review + update.
- `--workspace <path>` → operate on the given codebase root instead of cwd.
  Default: `git -C <cwd> rev-parse --show-toplevel` (cwd fallback).

## Phase 1 — Resolve workspace

```bash
WORKSPACE="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
```

## Phase 2 — Run the deterministic closeout engine

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/closeout_check.py" --repo "${WORKSPACE}" --json
```

Read the assessment: `docs_appear_current`, the `signals` list
(`code-changed-no-doc` / `version-bumped-no-changelog` /
`source-changed-no-changelog` / `new-surface-undocumented`), and the `changed`
breakdown. A clean result means the STRUCTURAL check passed — semantic currency
is still reviewed in Phase 3.

## Phase 3 — Review and update (unless `--check`)

Invoke the **`closeout` skill** (Skill tool: `closeout`) and follow it:

1. Review the working-tree changes against the requirement (CO-2) — which
   documentation-currency docs does each change affect, and is each current?
2. For any stale/incomplete doc, **update it** (CO-3) via the `documentation-currency`
   discipline + the `doc-updater` whole-file-rewrite pattern — touching ONLY the
   inventory paths, never source / tests / `openspec/*` / the version
   source-of-truth. For an isolated/heavy pass, spawn the `closeout-agent`.
3. Confirm what was reviewed and updated.

With `--check`, STOP after Phase 2 — print the signals + recommendation and do
not modify any file.

## Safety rules

- `--check` is read-only. The default performs doc updates but is bounded to the
  documentation-currency inventory (never source, tests, `openspec/*`, or
  `.claude-plugin/*`).
- Best-effort engine. If `closeout_check.py` fails for any reason, surface the
  error and fall back to the manual review in Phase 3 — do NOT block.
- The closeout never bumps the version; that is the orchestrator's job. It brings
  the docs into line with whatever the version source-of-truth already says.

## Cross-references

- `skills/closeout/SKILL.md` — the canonical contract (CO-1…CO-3).
- `hooks/closeout_check.py` — the deterministic staleness engine this command invokes.
- `hooks/precompact-closeout.py` — the automatic PreCompact counterpart that fires before compaction.
- `skills/documentation-currency/SKILL.md` — the currency inventory + per-doc rules the update applies.
- `agents/closeout-agent.md` — the spawnable worker for an isolated closeout pass.
