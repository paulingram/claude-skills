#!/usr/bin/env python3
"""Agent-teams mode detection for the architect-team plugin (v1.0.0).

The pipeline skills (`architect-team-pipeline`, `bug-fix-pipeline`,
`mini-architect-team-pipeline`) call `is_teams_mode_available()` at startup to
decide whether to dispatch in teams mode (Lead + long-lived teammates + shared
task list) or subagents mode (the v0.9.36 ephemeral-Agent-tool path).

Teams mode is selected ONLY when ALL of the following are true:

  1. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set to a truthy value via env
     OR via `~/.claude/settings.json -> env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`.
  2. `claude --version` parses to a SemVer-ish version >= 2.1.32.
  3. The `--no-teams` flag was not passed.

Truthy env values (case-insensitive): "1", "true", "yes".
Falsy / unrecognized values (case-insensitive): "0", "false", "", "no", anything else.

Reuse Decision: RD-2 (build-new — no existing equivalent). Stdlib only per NF-2.
The version comparison is hand-rolled as a tuple-of-ints (no `packaging.version`
dependency, matching the plugin's stdlib-only convention used in
`scripts/setup/setup.py` `check_node_version_string`).

References:
  - https://code.claude.com/docs/en/agent-teams (the canonical primitive)
  - openspec/changes/agent-teams-refactor/specs/agent-teams-mode/spec.md REQ-1
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Mapping


# ---- Constants ---------------------------------------------------------------

ENV_VAR_NAME = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"

# Claude Code minimum version that ships the experimental Agent Teams primitive.
MIN_CLAUDE_VERSION: tuple[int, int, int] = (2, 1, 32)

# Default user-level Claude settings path. Overridable via the `settings_path`
# parameter so tests can inject a tmp_path.
DEFAULT_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"

# Case-insensitive truthy values for the experimental flag. The Agent Teams
# docs canonicalize on "1"; "true" / "yes" are accepted to match common
# user-config habits.
_TRUTHY_VALUES = frozenset({"1", "true", "yes"})

# A SemVer-ish parser. `claude --version` historically prints lines like
# "2.1.32 (Claude Code)" or just "2.1.32". We grab the first three-dot-numeric
# triple anywhere in the output.
_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")


# ---- Public API --------------------------------------------------------------


def is_teams_mode_available(
    env: Mapping[str, str] | None = None,
    settings_path: Path | None = None,
    claude_cmd: str = "claude",
    flag_no_teams: bool = False,
) -> bool:
    """Return True when teams mode should be selected, False otherwise.

    Args:
        env: process environment to inspect. Defaults to os.environ. A test can
            pass a dict to inject `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`.
        settings_path: path to a Claude settings.json. Defaults to
            ~/.claude/settings.json. If the file is missing, unreadable, or has
            no env block, the settings-source check simply returns False — no
            exception escapes.
        claude_cmd: the executable to invoke for the version check. Defaults to
            "claude". Passed through to subprocess.run.
        flag_no_teams: if True, force subagents mode even when env + version
            qualify. This is the `--no-teams` escape hatch.

    Returns:
        True when teams mode should be selected, False otherwise.

    Never raises — every probe is wrapped in a tolerant try/except so a
    malformed settings file, a missing claude binary, or a slow subprocess can
    never crash pipeline startup.
    """
    if flag_no_teams:
        return False

    if not _flag_is_set(env, settings_path):
        return False

    return _claude_version_meets_minimum(claude_cmd)


def detect_no_teams_flag(argv: list[str]) -> bool:
    """Return True iff argv contains the exact `--no-teams` token.

    Substring / prefix matches don't count: `--no-teamswhatever` returns False.
    """
    return "--no-teams" in argv


# ---- Internals ---------------------------------------------------------------


def _is_truthy(value: str | None) -> bool:
    """Truthy iff the value (lowercased, stripped) is in the truthy set."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VALUES


def _flag_is_set(
    env: Mapping[str, str] | None,
    settings_path: Path | None,
) -> bool:
    """Return True when the experimental flag is truthy in env OR settings.json."""
    if env is None:
        env = os.environ

    if _is_truthy(env.get(ENV_VAR_NAME)):
        return True

    return _flag_in_settings(settings_path)


def _flag_in_settings(settings_path: Path | None) -> bool:
    """Inspect settings.json for env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS truthy.

    Returns False on any probe failure (missing file, unreadable file, malformed
    JSON, missing env block). Never raises.
    """
    path = settings_path if settings_path is not None else DEFAULT_SETTINGS_PATH
    try:
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError, ValueError):
        return False

    if not isinstance(data, dict):
        return False
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        return False
    return _is_truthy(env_block.get(ENV_VAR_NAME))


def _claude_version_meets_minimum(claude_cmd: str) -> bool:
    """Run `claude --version`, parse the result, compare against MIN_CLAUDE_VERSION."""
    try:
        result = subprocess.run(
            [claude_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    if result.returncode != 0:
        return False

    parsed = _parse_version(result.stdout or "")
    if parsed is None:
        return False
    return parsed >= MIN_CLAUDE_VERSION


def _parse_version(text: str) -> tuple[int, int, int] | None:
    """Parse the first `X.Y.Z` triple from `text`, returning None if absent."""
    match = _VERSION_PATTERN.search(text)
    if not match:
        return None
    try:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:  # pragma: no cover — re-matches guarantee numeric
        return None
