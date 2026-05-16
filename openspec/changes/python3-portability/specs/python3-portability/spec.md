## ADDED Requirements

### Requirement: Setup command uses python3

The `/architect-team:architect-team-setup` slash command MUST invoke `python3` (not bare `python`) when launching `scripts/setup/setup.py`. The `allowed-tools` frontmatter MUST grant `Bash(python3:*)` permission (not `Bash(python:*)`).

#### Scenario: Fresh install on Ubuntu without python alias

- **GIVEN** a Linux system where `command -v python3` resolves but `command -v python` does not
- **WHEN** a user runs `/architect-team:architect-team-setup`
- **THEN** the setup script executes successfully and produces its status table
- **AND** no `python: command not found` error appears

#### Scenario: Frontmatter permission matches body command

- **GIVEN** the command's body invokes `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py"`
- **WHEN** the command frontmatter is parsed
- **THEN** `allowed-tools` contains `Bash(python3:*)`
- **AND** does NOT contain bare `Bash(python:*)`

### Requirement: Hooks use python3

Both review-gate hooks declared in `hooks/hooks.json` (`PostToolUse(TaskUpdate) → review-gate-task.py` and `SubagentStop → teammate-idle-check.py`) MUST invoke `python3` (not bare `python`) when executing their respective Python scripts.

#### Scenario: PostToolUse hook on Linux

- **GIVEN** a Linux system where `command -v python3` resolves but `command -v python` does not
- **WHEN** the Claude Code harness fires the `PostToolUse(TaskUpdate)` hook
- **THEN** `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/review-gate-task.py"` executes
- **AND** the hook either returns exit 0 (allowed) or exit 2 (gated) — never `command not found`

#### Scenario: SubagentStop hook on Linux

- **GIVEN** the same environment
- **WHEN** any subagent completes and the `SubagentStop` hook fires
- **THEN** `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/teammate-idle-check.py"` executes
- **AND** the hook either returns exit 0 or exit 2 — never `command not found`

### Requirement: Setup script reports python3 PATH resolution

`scripts/setup/setup.py` MUST verify that `python3` is resolvable on `$PATH` and report the result alongside the existing in-process Python version check. Absence of `python3` on PATH MUST produce a warning row (not a failure row) with OS-specific remediation guidance, because the script itself proves that *some* Python 3 interpreter exists.

#### Scenario: python3 is on PATH

- **GIVEN** a system where `shutil.which("python3")` returns a non-None path
- **WHEN** `python3 scripts/setup/setup.py --check-only` runs
- **THEN** the status table contains a `python3-on-path` row with status `"present"` and message containing the resolved path

#### Scenario: python3 is missing on Linux

- **GIVEN** a Linux system where `shutil.which("python3")` returns None
- **WHEN** `python3 scripts/setup/setup.py --check-only` runs
- **THEN** the status table contains a `python3-on-path` row with status `"warn"`
- **AND** the message contains the substring `python-is-python3` (the apt remediation)
- **AND** the overall exit code is 0 (warning is non-fatal)

#### Scenario: python3 is missing on Windows

- **GIVEN** a Windows system where `shutil.which("python3")` returns None
- **WHEN** `python3 scripts/setup/setup.py --check-only` runs
- **THEN** the `python3-on-path` row's message contains `py launcher` or `python.org installer`
- **AND** the overall exit code is 0

### Requirement: Test coverage for python3 invocations

The pytest suite MUST include explicit assertions covering the python3 invocation across all three surfaces (command, hooks, setup-script helper), so that any future regression that re-introduces bare `python` fails CI before release.

#### Scenario: Suite enforces python3 across surfaces

- **WHEN** `python -m pytest -v` runs from the repo root
- **THEN** the suite includes at minimum:
  - 1 test asserting `commands/architect-team-setup.md` uses `python3` in its body and `allowed-tools`
  - 1 test asserting each hook command in `hooks/hooks.json` starts with `python3 `
  - 3 tests covering the `_python3_on_path()` helper (present case, missing on Linux, missing on Windows)
- **AND** total suite size is ≥ 59 PASS
