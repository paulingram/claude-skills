## Why

The `architect-team` plugin's `/architect-team:architect-team-setup` slash command and both PostToolUse / SubagentStop hooks invoke the bare interpreter name `python`. On modern Linux distributions (Ubuntu 20.04+, Debian 11+, Fedora 35+) and on macOS 12.3+, the OS ships only `python3` — `python` does not exist on `$PATH`. Result: a fresh install of the plugin fails the setup command with `python: command not found` and silently breaks both review-gate enforcement hooks. The plugin is documented as cross-platform but is in fact only usable on systems where the user has manually aliased `python → python3`.

Reproduced on a Linux server during dogfood install:

```
❯ /architect-team:architect-team-setup
⎿  Error: Shell command failed for pattern "```! python "/home/paul/.claude/plugins/cache/architect-team-marketplace/architect-team/0.2.3/scripts/setup/setup.py"
   /bin/bash: line 1: python: command not found
```

## What Changes

- **Modify** `commands/architect-team-setup.md` to invoke `python3` instead of `python`, and update the `allowed-tools` permission frontmatter to match (`Bash(python3:*)`). (REQ-001)
- **Modify** `hooks/hooks.json` to invoke `python3` instead of `python` for both the `PostToolUse(TaskUpdate) → review-gate-task.py` hook and the `SubagentStop → teammate-idle-check.py` hook. (REQ-002)
- **Modify** `scripts/setup/setup.py` to detect and report when `python3` is not on `$PATH` (separate from the existing in-process version check, which only knows about *this* interpreter). On detection failure, print actionable remediation per OS. (REQ-003)
- **Add** unit tests for the new `python3-on-PATH` detection branch in `scripts/setup/setup.py`. (REQ-004)
- **Modify** `README.md` to document the `python3` prerequisite and the one-line Windows / Ubuntu remediation steps. (REQ-005)
- **Release v0.2.4**: bump `version` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (0.2.3 → 0.2.4), prepend `## [0.2.4] — 2026-05-16` entry to `CHANGELOG.md`, commit with explicit author override, annotated tag `v0.2.4`, push `main` + tag. (REQ-006)

No new external dependencies. No new skills, agents, or commands. No breaking changes — `python3` is the canonical Python 3 invocation on all three platforms the plugin supports:

- **Linux** (Ubuntu/Debian/Fedora/Arch/Alpine): `python3` is the default. `python` is only present if the user installed the `python-is-python3` alias package.
- **macOS** 12.3+: `python3` is the default (the `/usr/bin/python` symlink to Python 2 was removed in Monterey).
- **Windows** with python.org installer 3.7+: `python3.exe` is generated alongside `python.exe`. With the Microsoft Store stub or `py` launcher, `python3` resolves via the launcher.

## Capabilities

### New Capabilities

None. Every REQ extends an existing file.

### Modified Capabilities

This change introduces a single capability `python3-portability` that documents the requirements and acceptance criteria for the v0.2.4 release.

- `python3-portability`: the plugin's command, hooks, and setup-script invocations all use `python3` (not bare `python`) so that fresh installs work on stock Linux and macOS without manual aliasing.

## Impact

**Affected files (≤7):**

- `commands/architect-team-setup.md` (REQ-001) — change command body + `allowed-tools`.
- `hooks/hooks.json` (REQ-002) — change both `command` strings.
- `scripts/setup/setup.py` (REQ-003) — add `_python3_on_path()` helper + reporting row.
- `tests/test_setup_script.py` (REQ-004) — add ≥3 new test cases for the helper.
- `README.md` (REQ-005) — add a "Prerequisites" subsection or extend the existing one.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md` (REQ-006) — version + release.

**Affected APIs:** none external.

**Affected dependencies:** none.

**Affected systems:** the in-process Claude Code harness loads the modified hooks + command on `/reload-plugins`. The setup script is invoked manually by users.

**Reuse-first decision summary:** every change extends an existing file. Zero new modules. Zero new dependencies. The detection helper in REQ-003 is a new function within `scripts/setup/setup.py` (not a new file). Test additions in REQ-004 extend `tests/test_setup_script.py` following its established `setup_module` fixture pattern. Per `reuse-first-design`, this satisfies the extend > compose > reuse > build-new ladder with extension at every step.
