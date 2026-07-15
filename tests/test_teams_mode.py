"""REQ-1: Mode detection — scenarios 1.1 through 1.6.

Exercises `scripts/setup/teams_mode.py` `is_teams_mode_available` + `detect_no_teams_flag`.
Loads the module via importlib so we don't need a package layout.

Scenarios from spec.md REQ-1:
  1.1 env var set + version OK -> teams mode
  1.2 settings.json fallback -> teams mode
  1.3 low Claude Code version -> subagents mode (with note)
  1.4 --no-teams flag overrides -> subagents mode
  1.5 unset env + no settings -> subagents mode silently
  1.6 falsy env value -> subagents mode
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest
from tests.helpers.module_loader import load_module


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def teams_mode_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/teams_mode.py via importlib (matches setup_script.py pattern)."""
    path = plugin_root / "scripts" / "setup" / "teams_mode.py"
    assert path.exists(), f"teams_mode.py missing at {path}"
    mod = load_module(path, "teams_mode_module")
    return mod


# ---- Fake subprocess factory -------------------------------------------------


def _fake_run_factory(version_string: str, returncode: int = 0):
    """Return a subprocess.run replacement that emits `version_string` on stdout."""
    class _Result:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = version_string
            self.stderr = ""
    def _run(*_args: Any, **_kwargs: Any) -> _Result:
        return _Result()
    return _run


def _write_settings(tmp_path: Path, env_value: str | None) -> Path:
    """Write a fake ~/.claude/settings.json. If env_value is None, write {} (no env block)."""
    settings = tmp_path / "settings.json"
    if env_value is None:
        settings.write_text("{}", encoding="utf-8")
    else:
        settings.write_text(json.dumps({"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": env_value}}), encoding="utf-8")
    return settings


# ---- Scenario 1.1: env var set + version OK ---------------------------------


def test_teams_mode_when_env_truthy_and_version_ok(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    with patch("subprocess.run", _fake_run_factory("2.1.32 (Claude Code)")):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, None),
            claude_cmd="claude",
            flag_no_teams=False,
        )
    assert result is True


def test_teams_mode_when_env_truthy_value_yes(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """Truthy is case-insensitive across the documented forms."""
    with patch("subprocess.run", _fake_run_factory("2.2.0")):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "YES"},
            settings_path=_write_settings(tmp_path, None),
        )
    assert result is True


def test_teams_mode_when_env_truthy_value_true(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "true"},
            settings_path=_write_settings(tmp_path, None),
        )
    assert result is True


# ---- Scenario 1.2: settings.json fallback ------------------------------------


def test_teams_mode_when_only_settings_json_truthy(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """env var unset, settings.json carries the env entry, version qualifies."""
    settings = _write_settings(tmp_path, "1")
    with patch("subprocess.run", _fake_run_factory("2.2.0")):
        result = teams_mode_module.is_teams_mode_available(
            env={},
            settings_path=settings,
            flag_no_teams=False,
        )
    assert result is True


def test_teams_mode_settings_json_missing_is_ok(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """A non-existent settings.json doesn't crash — it just doesn't satisfy the flag check."""
    nope = tmp_path / "missing.json"
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        result = teams_mode_module.is_teams_mode_available(
            env={},
            settings_path=nope,
        )
    assert result is False


# ---- Scenario 1.3: low Claude Code version -----------------------------------


def test_subagents_mode_when_version_below_minimum(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    with patch("subprocess.run", _fake_run_factory("2.1.31")):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, None),
        )
    assert result is False


def test_subagents_mode_when_version_unparseable(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    with patch("subprocess.run", _fake_run_factory("garbage not a version")):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, None),
        )
    assert result is False


def test_subagents_mode_when_claude_cmd_missing(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """If subprocess.run raises (claude not on PATH), we treat the version check as failing."""
    def _raise(*_a, **_kw):
        raise FileNotFoundError("claude not on PATH")
    with patch("subprocess.run", _raise):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, None),
        )
    assert result is False


# ---- Scenario 1.4: --no-teams flag overrides ---------------------------------


def test_subagents_mode_when_no_teams_flag_forces_off(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    with patch("subprocess.run", _fake_run_factory("2.2.0")):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=_write_settings(tmp_path, "1"),
            flag_no_teams=True,
        )
    assert result is False


def test_detect_no_teams_flag_finds_argv(teams_mode_module: ModuleType) -> None:
    assert teams_mode_module.detect_no_teams_flag(["--no-teams"]) is True
    assert teams_mode_module.detect_no_teams_flag(["foo", "--no-teams", "bar"]) is True
    assert teams_mode_module.detect_no_teams_flag([]) is False
    assert teams_mode_module.detect_no_teams_flag(["--teams"]) is False
    assert teams_mode_module.detect_no_teams_flag(["--no-teamswhatever"]) is False


# ---- Scenario 1.5: unset env + no settings → silent subagents ---------------


def test_subagents_mode_when_env_and_settings_both_missing(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        result = teams_mode_module.is_teams_mode_available(
            env={},
            settings_path=_write_settings(tmp_path, None),
        )
    assert result is False


# ---- Scenario 1.6: falsy env value ------------------------------------------


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "", "garbage"])
def test_subagents_mode_when_env_value_is_falsy_or_unrecognized(
    teams_mode_module: ModuleType, tmp_path: Path, value: str
) -> None:
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        result = teams_mode_module.is_teams_mode_available(
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": value},
            settings_path=_write_settings(tmp_path, None),
        )
    assert result is False


# ---- Cross-cutting: settings.json malformed is tolerated --------------------


def test_subagents_mode_when_settings_json_malformed(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    """A corrupt settings.json never crashes mode detection — it just doesn't grant teams."""
    settings = tmp_path / "settings.json"
    settings.write_text("{not valid json", encoding="utf-8")
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        result = teams_mode_module.is_teams_mode_available(
            env={},
            settings_path=settings,
        )
    assert result is False


def test_subagents_mode_when_settings_json_missing_env_block(
    teams_mode_module: ModuleType, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"other": "stuff"}), encoding="utf-8")
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        result = teams_mode_module.is_teams_mode_available(
            env={},
            settings_path=settings,
        )
    assert result is False
