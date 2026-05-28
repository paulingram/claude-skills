# Proposal: dispatch-banner (v1.5.0)

## Why

The user's direct question — *"how do I know if a team is deployed via agent teams vs subagents?"* — exposed a real observability gap. v1.0.0 introduced teams-mode-by-default-with-subagents-fallback dispatch but made the decision SILENT: it lands in `.architect-team/intake-state.json` but there's no user-visible signal. Users have to grep JSON or trust that the mode they expect is the mode they got.

v1.5.0 ships three pieces of dispatch-mode observability:

1. **Startup banner** — every `/architect-team` family invocation prints a one-block banner as its FIRST user-visible output, naming the active dispatch mode + the reason it was picked.
2. **`/architect-team:status` command** — on-demand "where am I" query showing dispatch mode + active worktrees + open SRs + last completed run.
3. **`Dispatch-Mode: teams|subagents` commit trailer** — added at Phase 8 commits so `git log` can answer "which mode produced this commit" archeologically.

## What changes

1. **`scripts/setup/teams_mode.py` extended** with `format_dispatch_banner() -> str`:
   - Returns the multi-line banner string (teams or subagents fallback)
   - Detects env / settings.json / version / `--no-teams` flag presence
   - Names WHY the mode was picked (so subagent fallback explains itself)
2. **Three slash commands updated** — `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` — each prints the banner as the FIRST user-visible action of the run (before the existing auto-cleanup + arg parsing).
3. **New `commands/status.md`** — `/architect-team:status` invocation. Reports:
   - Current dispatch mode banner
   - Active `architect-team/*` worktrees (via `git worktree list`)
   - Open SRs (count + paths in `.architect-team/solution-requirements/`)
   - Last completed run (latest entry in `.architect-team/runs/`)
4. **Phase 8 commit-trailer addition** — the 3 pipeline skill bodies' Phase 8 (or M7 for mini) commit-message section gains a `Dispatch-Mode: <mode>` trailer alongside the existing `Co-Authored-By` trailer. The orchestrator computes `<mode>` from `intake-state.json`.
5. **8 new tests** covering: banner formatting in both modes, the reason-for-mode explanation, the status command structure, the trailer pattern.
6. **Version bump to v1.5.0** in plugin.json + marketplace.json + CHANGELOG + CLAUDE.md + README + maps.

## QA Guidance

### Acceptance Criteria

- [AC-1] `scripts/setup/teams_mode.py` exposes `format_dispatch_banner() -> str` — stdlib only; returns the appropriate banner string based on detection result.
- [AC-2] The teams-mode banner names the env var status (✓ or ✗ with explanation), Claude Code version status, and the `is_teams_mode_available()` final verdict.
- [AC-3] The subagents-fallback banner names WHY the fallback fired (which condition was unmet) + how to enable teams mode (env var + version + setup command pointer).
- [AC-4] Each of the 3 pipeline-driving slash commands documents printing the banner as the FIRST user-visible action, before any argument parsing.
- [AC-5] `commands/status.md` exists; invocable as `/architect-team:status`; reports dispatch mode + active worktrees + open SRs + last completed run.
- [AC-6] The 3 pipeline skill bodies' Phase 8 / M7 commit-message section documents adding a `Dispatch-Mode: <teams|subagents>` trailer alongside the existing `Co-Authored-By` trailer.
- [AC-7] All existing tests pass (1744 baseline) + 8 new tests. Target: 1752 / 1 skipped.
- [AC-8] Version `1.5.0` consistent across plugin.json, marketplace.json, CHANGELOG, README, CLAUDE.md.

### Unit Test Targets

- `teams_mode.py:format_dispatch_banner`: returns the teams banner when `is_teams_mode_available()` is True; the subagents banner otherwise
- The teams banner contains literal strings: `Dispatch mode`, `AGENT TEAMS`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, `2.1.32`
- The subagents banner contains: `Dispatch mode`, `SUBAGENTS`, plus the relevant fallback reason
- Structural tests on the 3 slash commands + the new status command

### Integration Test Targets

- N/A.

### Playwright Flows

- N/A.

### Out of Scope

- **Live teammate roster in the banner** — listing currently-spawned teammates in real time. The banner is a startup snapshot. The status command can show this later if needed.
- **Mode override via flag at runtime** — already exists as `--no-teams` (v1.0.0). v1.5.0 just makes the resulting mode visible.
- **Automated cron / hook integration** — not needed; the banner is part of the pipeline body.

## Impact

- **Modified:** `scripts/setup/teams_mode.py` (+1 function), 3 slash commands, 3 pipeline SKILL.md bodies (Phase 8 / M7 trailer), CHANGELOG, CLAUDE.md, README, CODEBASE_MAP, INTEGRATION_MAP, plugin.json, marketplace.json.
- **New:** `commands/status.md`, `tests/test_dispatch_banner.py`, 1 openspec change folder.
- **Test count:** 1744 → ~1752.
- **Version:** v1.4.0 → **v1.5.0**.
- **Backwards-compatible:** observability only. Existing dispatch behavior is unchanged.
