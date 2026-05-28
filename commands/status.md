---
description: Show current dispatch mode (Agent Teams vs subagents fallback) + active architect-team worktrees + open solution requirements + last completed run. On-demand "where am I" query for the architect-team plugin. Pure read-only — no filesystem changes, no pipeline invocation, no commit.
argument-hint: ""
---

# /architect-team:status

Reports the current state of the architect-team plugin in the current cwd.
**Pure read-only** — no filesystem changes, no pipeline invocation, no commit.
Mirrors the v1.3.0 `/architect-team:cleanup-worktrees` shape: an explicit
user-facing utility command for asking *"what's happening with the plugin
right now?"* without starting a new pipeline run.

The report has 4 sections, each a brief block — the whole report fits in
~25 lines.

## Section 1 — Dispatch mode banner

Invoke `format_dispatch_banner()` from the v1.5.0 `scripts/setup/teams_mode.py`
helper via the polyglot Python pattern per `common-pipeline-conventions`
`## Cross-platform Python invocation`. The banner names whether the plugin
is in **AGENT TEAMS** mode or **SUBAGENTS (fallback)** mode + (in the
fallback case) the Reason: + the env-var / version / setup-command pointer
the user needs to enable teams mode.

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || echo "(dispatch banner unavailable; continuing.)"
```

## Section 2 — Active worktrees

List active `architect-team/*` worktrees via `git worktree list`. Show one
line per worktree: branch name + filesystem path. If none, print
*"(no active architect-team worktrees)"*.

```bash
git worktree list 2>/dev/null | grep -E '\[architect-team/' || echo "(no active architect-team worktrees)"
```

## Section 3 — Open solution requirements

Count + enumerate any open SRs under `.architect-team/solution-requirements/`.
SRs are JSON files (`SR-*.json`) emitted by the dev loop when an issue is
surfaced; `status: "open"` means the SR is awaiting team spawn / fix; any
other value means it's been picked up or resolved.

```bash
ls .architect-team/solution-requirements/SR-*.json 2>/dev/null | wc -l | tr -d ' ' | xargs -I{} echo "Open SRs (file count): {}"
grep -l '"status": *"open"' .architect-team/solution-requirements/SR-*.json 2>/dev/null || echo "(no open SR JSON files matched)"
```

## Section 4 — Last completed run

The most recent entry under `.architect-team/runs/` is the last completed
run's marker (the orchestrator writes one per Phase 8 / B8 / M7 success).
If the directory is empty or absent, print *"(no completed runs recorded)"*.

```bash
ls -t .architect-team/runs/ 2>/dev/null | head -1 | xargs -I{} echo "Last completed run: {}" 2>/dev/null || echo "(no completed runs recorded)"
```

## Out of scope

- **Live teammate roster** — listing currently-spawned teammates in real time
  is out of scope for v1.5.0; the dispatch banner is a startup snapshot.
- **JSON output mode** — v1.5.0 ships plain-text only. A `--json` variant
  could land in a later release if scripted consumers need it.
- **Filesystem mutation** — this command never deletes, never commits, never
  invokes the pipeline. Use `/architect-team:cleanup-worktrees` to clean
  merged worktrees on demand.
