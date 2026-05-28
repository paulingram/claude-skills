# Spec: dispatch-banner capability

## ADDED Requirements

### Requirement: Banner formatter helper

`scripts/setup/teams_mode.py` SHALL gain a `format_dispatch_banner(env=None, settings_path=None, claude_cmd="claude", flag_no_teams=False) -> str` function that returns the dispatch-mode banner string for the current environment. Stdlib only.

#### Scenario: teams banner returned when teams mode available

- **WHEN** `format_dispatch_banner()` is called and `is_teams_mode_available()` returns True
- **THEN** the returned string contains `Dispatch mode: AGENT TEAMS`
- **AND** it contains `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
- **AND** it contains `2.1.32`

#### Scenario: subagents banner returned when teams mode unavailable

- **WHEN** `format_dispatch_banner()` is called and `is_teams_mode_available()` returns False
- **THEN** the returned string contains `Dispatch mode: SUBAGENTS` (or `Dispatch mode: SUBAGENTS (fallback)`)
- **AND** it contains the substring `Reason:` followed by a non-empty diagnosis
- **AND** it contains pointer text on how to enable teams mode

#### Scenario: fallback reason names env-var-unset

- **WHEN** `format_dispatch_banner(env={})` is called (no env var set, no settings file injected)
- **THEN** the returned banner names "not set" or equivalent prose explaining the missing env var

#### Scenario: fallback reason names version-too-low

- **WHEN** env is set truthy but `claude --version` reports a version below `2.1.32`
- **THEN** the banner names the version mismatch in its `Reason:` line

#### Scenario: fallback reason names --no-teams flag

- **WHEN** `format_dispatch_banner(flag_no_teams=True)` is called even with env + version OK
- **THEN** the banner names `--no-teams` in its `Reason:` line

### Requirement: Slash commands print the banner first

Each of `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` SHALL document printing the dispatch-mode banner as the FIRST user-visible action of the invocation — before argument parsing, before auto-cleanup, before any other step.

#### Scenario: each command body documents the banner step

- **WHEN** each of the 3 slash command bodies is parsed
- **THEN** the first user-visible action documented is the dispatch-mode banner print
- **AND** the body references `format_dispatch_banner` (or the equivalent helper invocation)

#### Scenario: banner is informational (not gating)

- **WHEN** the banner step body is read
- **THEN** it explicitly states the banner is informational and NEVER blocks the run
- **AND** it states that subprocess failure surfaces a one-line note and the run continues

### Requirement: Status command exists

The plugin SHALL ship a `/architect-team:status` command at `commands/status.md`. The command body SHALL document reporting: dispatch mode banner, active `architect-team/*` worktrees, open SRs (count + paths), last completed run.

#### Scenario: command file exists with valid frontmatter

- **WHEN** `commands/status.md` is parsed
- **THEN** it has a valid frontmatter with `description` ≥ 30 chars
- **AND** the body documents the 4 reported sections

#### Scenario: command is registered in EXPECTED_COMMANDS

- **WHEN** `tests/test_commands.py`'s `EXPECTED_COMMANDS` set is read
- **THEN** it contains `"status"`

### Requirement: Phase 8 commit gets Dispatch-Mode trailer

The 3 pipeline skill bodies' Phase 8 (and mini-pipeline's M7) commit-message section SHALL document adding a `Dispatch-Mode: <teams|subagents>` trailer alongside the existing `Co-Authored-By` trailer. The value SHALL be derived from `.architect-team/intake-state.json`'s `dispatch_mode` field.

#### Scenario: architect-team-pipeline Phase 8 documents the trailer

- **WHEN** the Phase 8 commit-message template in `skills/architect-team-pipeline/SKILL.md` is parsed
- **THEN** it includes a `Dispatch-Mode: <mode>` line

#### Scenario: bug-fix-pipeline Phase B8 documents the trailer

- **WHEN** the Phase B8 commit-message template in `skills/bug-fix-pipeline/SKILL.md` is parsed
- **THEN** it includes a `Dispatch-Mode: <mode>` line

#### Scenario: mini-pipeline M7 documents the trailer

- **WHEN** the M7 commit-message template in `skills/mini-architect-team-pipeline/SKILL.md` is parsed
- **THEN** it includes a `Dispatch-Mode: <mode>` line

### Requirement: Structural tests assert the banner and command shape

The plugin SHALL ship `tests/test_dispatch_banner.py` with ≥ 8 tests covering:
- Both banner shapes (teams + subagents fallback)
- The 4 fallback reasons (env-unset, version-too-low, --no-teams, settings-and-env-unset)
- The presence of the dispatch-mode-banner section in each of the 3 pipeline slash commands
- The status command frontmatter + body sections

#### Scenario: ≥ 8 tests collected

- **WHEN** `python3 -m pytest tests/test_dispatch_banner.py --collect-only` runs
- **THEN** it collects ≥ 8 test cases
- **AND** all collected tests pass

### Requirement: Version bumped to 1.5.0

`1.5.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top of `CHANGELOG.md`, README banner + version badge, CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.5.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "1.5.0"`
