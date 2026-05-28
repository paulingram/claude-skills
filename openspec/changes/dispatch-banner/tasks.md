# Tasks: dispatch-banner

Single implementer slice.

## Files owned

- Modify: `scripts/setup/teams_mode.py` (add `format_dispatch_banner` + diagnose helper)
- Create: `tests/test_dispatch_banner.py` (≥ 8 tests)
- Modify: `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` (banner step at top)
- Create: `commands/status.md`
- Modify: `tests/test_commands.py` (add `status` to EXPECTED_COMMANDS)
- Modify: `skills/architect-team-pipeline/SKILL.md` (Phase 8 trailer)
- Modify: `skills/bug-fix-pipeline/SKILL.md` (Phase B8 trailer)
- Modify: `skills/mini-architect-team-pipeline/SKILL.md` (M7 trailer)
- Modify: `.claude-plugin/plugin.json` (1.5.0)
- Modify: `.claude-plugin/marketplace.json` (1.5.0)
- Modify: `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`

## Tasks

- [TASK-1] In `scripts/setup/teams_mode.py`, add `format_dispatch_banner(env=None, settings_path=None, claude_cmd="claude", flag_no_teams=False) -> str` + internal `_diagnose_fallback_reason()` helper. Banner content per `design.md`. Stdlib only.

- [TASK-2] Author `tests/test_dispatch_banner.py` with ≥ 8 tests:
  - Teams banner contains expected literals (env var name, version, AGENT TEAMS heading)
  - Subagents banner contains expected literals (SUBAGENTS heading, Reason: prefix, pointer text)
  - Each of the 4 fallback reasons surfaces correctly (env-unset, version-too-low, --no-teams, settings-and-env-unset)
  - Status command file frontmatter parses
  - Status command body contains the 4 reported sections

- [TASK-3] Update `commands/architect-team.md`:
  - Add new section `## Dispatch mode banner (v1.5.0) — runs first` at the very TOP of the body (before the v1.3.0 auto-cleanup section)
  - Body uses the polyglot Python invocation pattern; result piped to stdout
  - Explicit "informational, not gating" prose

- [TASK-4] Same update to `commands/bug-fix.md`.

- [TASK-5] Same update to `commands/mini.md`.

- [TASK-6] Create `commands/status.md`:
  - Frontmatter description ≥ 30 chars
  - Body documents 4 reported sections: dispatch mode banner, active worktrees, open SRs, last completed run
  - Bash invocations using polyglot Python pattern

- [TASK-7] Add `status` to `EXPECTED_COMMANDS` in `tests/test_commands.py`.

- [TASK-8] Update `skills/architect-team-pipeline/SKILL.md` Phase 8 commit-message template — add `Dispatch-Mode: <mode>` trailer line above the existing `Co-Authored-By` trailer. Document deriving `<mode>` from `intake-state.json`.

- [TASK-9] Same update to `skills/bug-fix-pipeline/SKILL.md` Phase B8.

- [TASK-10] Same update to `skills/mini-architect-team-pipeline/SKILL.md` M7.

- [TASK-11] Version bumps: `plugin.json` + `marketplace.json` → `1.5.0`.

- [TASK-12] Docs:
  - CHANGELOG: prepend v1.5.0 entry (Added: banner formatter + status command + commit trailer; Migration: none — observability only)
  - CLAUDE.md: replace v1.4.0 lead with v1.5.0 lead naming the dispatch-mode banner; bump command count to 13; test count to ~1752
  - README: banner v1.5.0, badges, NEW IN v1.5.0 row, status timeline
  - CODEBASE_MAP: last_mapped 2026-05-28T06:00:00Z; add `status.md` to commands; new test file; tests ~1752 / 77
  - INTEGRATION_MAP: last_synthesized 2026-05-28T06:00:00Z; note observability addition

- [TASK-13] Commits (4 logical groups):
  1. `format_dispatch_banner` helper + `tests/test_dispatch_banner.py`
  2. 3 slash commands gain banner step + `commands/status.md` + `tests/test_commands.py` update
  3. 3 pipeline SKILL.md commit-trailer updates
  4. Version bump + docs

- [TASK-14] Phase 3 review-evidence at `.architect-team/reviews/v1.5.0-dispatch-banner.json` per v6. teammate = "v1.5.0-implementer". No `independent_review`.

- [TASK-15] Final test:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: ~1752 / 1 skipped.

## Acceptance

All 8 acceptance criteria from `proposal.md` `## QA Guidance`.
