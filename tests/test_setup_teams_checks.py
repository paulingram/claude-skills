"""REQ-7: Setup ergonomics — scenarios 7.1 through 7.4.

Exercises the new `check_teams_mode()` function in scripts/setup/setup.py + the
`--no-prompt` and `--check-only` flag behavior wrt the agent-teams flag.

Scenarios from spec.md REQ-7:
  7.1 setup.py --check-only reports flag + version status
  7.2 consent flow writes settings.json idempotently (no consent => suggested edit)
  7.3 README documents the requirement (Slice E owns — SKIP-on-missing pin)
  7.4 CLAUDE.md overview names teams mode (Slice E owns — SKIP-on-missing pin)
"""
from __future__ import annotations

import importlib.util
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from tests.helpers.module_loader import load_module


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def setup_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/setup.py via importlib."""
    path = plugin_root / "scripts" / "setup" / "setup.py"
    assert path.exists(), f"setup.py missing at {path}"
    mod = load_module(path, "setup_module_for_teams")
    return mod


def _fake_run_factory(stdout: str, returncode: int = 0):
    class _Result:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""
    def _run(*_a, **_kw) -> _Result:
        return _Result()
    return _run


# ---- Scenario 7.1: --check-only reports status ------------------------------


def test_check_teams_mode_reports_present_when_env_set_and_version_ok(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """check_teams_mode returns (name, 'present', detail) when env + version qualify."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}), encoding="utf-8")
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        name, status, detail = setup_module.check_teams_mode(
            check_only=True,
            no_prompt=True,
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=settings,
        )
    assert "teams-mode" in name or "agent-teams" in name or "teams_mode" in name
    assert status == "present"


def test_check_teams_mode_reports_missing_when_flag_not_set(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        name, status, detail = setup_module.check_teams_mode(
            check_only=True,
            no_prompt=True,
            env={},
            settings_path=settings,
        )
    assert status == "missing"
    assert detail is not None
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in detail


def test_check_teams_mode_reports_warn_on_low_version(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}), encoding="utf-8")
    with patch("subprocess.run", _fake_run_factory("2.1.31")):
        name, status, detail = setup_module.check_teams_mode(
            check_only=True,
            no_prompt=True,
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=settings,
        )
    # Low version => unsatisfied; the detail must name 2.1.32.
    assert status in {"missing", "warn", "fail"}
    assert detail is not None
    assert "2.1.32" in detail


def test_check_only_mode_does_not_write_settings(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """--check-only must NEVER modify user files even when teams mode is unsatisfied."""
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    original = settings.read_text(encoding="utf-8")
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        setup_module.check_teams_mode(
            check_only=True,
            no_prompt=True,
            env={},
            settings_path=settings,
        )
    assert settings.read_text(encoding="utf-8") == original


def test_main_returns_nonzero_when_teams_mode_unsatisfied_check_only(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """REQ-7.1: --check-only exits non-zero when teams mode is unsatisfied."""
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [{}],
            "cartographer@cartographer-marketplace": [{}],
            "ralph-loop@claude-plugins-official": [{}],
        },
    }), encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")  # no env block

    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed), \
         patch.object(setup_module, "check_node_version", return_value=(True, "Node 22.0 (need ≥ 20.19)")), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "DEFAULT_USER_SETTINGS_PATH", settings, create=True), \
         patch.object(setup_module, "_claude_version_or_none", return_value=(2, 1, 32)), \
         patch.dict("os.environ", {}, clear=False) as env:
        env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
        rc = setup_module.main(["--check-only"])
    # Exit non-zero when teams mode is unsatisfied per REQ-7.1.
    assert rc != 0


# ---- Scenario 7.2: consent flow writes settings.json -----------------------


def test_no_prompt_prints_suggested_edit_without_writing(
    setup_module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REQ-7.2: with --no-prompt, do NOT write — print the suggested edit instead."""
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    original = settings.read_text(encoding="utf-8")

    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        setup_module.check_teams_mode(
            check_only=False,
            no_prompt=True,
            env={},
            settings_path=settings,
        )

    # File unchanged.
    assert settings.read_text(encoding="utf-8") == original
    # Suggested edit was printed.
    captured = capsys.readouterr().out + capsys.readouterr().err
    # Either the env var name or the canonical settings.json snippet must be surfaced.
    full = captured
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in full or "settings.json" in full


def test_consent_yes_writes_settings_idempotently(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """REQ-7.2: interactive 'y' writes settings.json idempotently (re-run is safe)."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"other_key": "preserved"}), encoding="utf-8")

    fake_input = lambda _prompt: "y"
    with patch("subprocess.run", _fake_run_factory("2.1.32")), \
         patch.object(setup_module, "_prompt_user_consent", side_effect=fake_input):
        # First run: write.
        setup_module.check_teams_mode(
            check_only=False,
            no_prompt=False,
            env={},
            settings_path=settings,
        )

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data.get("env", {}).get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1"
    assert data.get("other_key") == "preserved", "Existing settings.json content must be preserved"

    # Idempotency: second run with the flag already present should not duplicate.
    with patch("subprocess.run", _fake_run_factory("2.1.32")):
        setup_module.check_teams_mode(
            check_only=False,
            no_prompt=False,
            env={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
            settings_path=settings,
        )
    data2 = json.loads(settings.read_text(encoding="utf-8"))
    assert data2 == data


def test_consent_no_does_not_write(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """REQ-7.2: declining the prompt leaves settings.json untouched."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"existing": "ok"}), encoding="utf-8")
    original = settings.read_text(encoding="utf-8")

    with patch("subprocess.run", _fake_run_factory("2.1.32")), \
         patch.object(setup_module, "_prompt_user_consent", return_value="n"):
        setup_module.check_teams_mode(
            check_only=False,
            no_prompt=False,
            env={},
            settings_path=settings,
        )

    assert settings.read_text(encoding="utf-8") == original


def test_consent_settings_file_missing_creates_it(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    assert not settings.exists()

    with patch("subprocess.run", _fake_run_factory("2.1.32")), \
         patch.object(setup_module, "_prompt_user_consent", return_value="y"):
        setup_module.check_teams_mode(
            check_only=False,
            no_prompt=False,
            env={},
            settings_path=settings,
        )

    assert settings.exists()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data.get("env", {}).get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1"


# ---- Scenarios 7.3 + 7.4: Slice E owns; SKIP-on-missing pin ----------------


def test_readme_documents_requirement(plugin_root: Path) -> None:
    """REQ-7.3: README's top 200 lines mention the flag + the version. Slice E owns the edit."""
    readme = plugin_root / "README.md"
    assert readme.exists(), "README.md missing — repo invariant"
    head = "\n".join(readme.read_text(encoding="utf-8").splitlines()[:200])
    if "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in head or "2.1.32" not in head:
        pytest.skip(
            "Slice E (docs) has not yet landed the README Requirements section. "
            "This test wakes up automatically once README.md mentions both "
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS and 2.1.32 in its first 200 lines."
        )
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in head
    assert "2.1.32" in head


def test_claude_md_overview_names_teams_mode(plugin_root: Path) -> None:
    """REQ-7.4: CLAUDE.md mentions teams mode + the experimental flag. Slice E owns the edit."""
    claude_md = plugin_root / "CLAUDE.md"
    assert claude_md.exists(), "CLAUDE.md missing — repo invariant"
    text = claude_md.read_text(encoding="utf-8")
    has_teams = "teams mode" in text.lower() or "agent teams" in text.lower()
    has_flag = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in text
    if not (has_teams and has_flag):
        pytest.skip(
            "Slice E (docs) has not yet landed the CLAUDE.md teams-mode overview. "
            "This test wakes up automatically once CLAUDE.md mentions both "
            "teams mode / agent teams AND the CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS flag."
        )
    assert has_teams
    assert has_flag


# ---- Wiring: check_teams_mode is integrated into main() ---------------------


def test_main_invokes_check_teams_mode(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """The new check must be wired into the existing main() flow."""
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [{}],
            "cartographer@cartographer-marketplace": [{}],
            "ralph-loop@claude-plugins-official": [{}],
        },
    }), encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}), encoding="utf-8")

    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed), \
         patch.object(setup_module, "check_node_version", return_value=(True, "Node 22.0 (need ≥ 20.19)")), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "DEFAULT_USER_SETTINGS_PATH", settings, create=True), \
         patch.object(setup_module, "_claude_version_or_none", return_value=(2, 1, 32)), \
         patch.object(setup_module, "check_teams_mode", wraps=setup_module.check_teams_mode) as spy, \
         patch.dict("os.environ", {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}):
        rc = setup_module.main(["--check-only", "--no-prompt"])
    assert spy.called, "check_teams_mode must be invoked by main()"
    assert rc == 0  # everything satisfied


def test_no_prompt_flag_is_parsed(setup_module: ModuleType) -> None:
    """The --no-prompt flag is exposed on the CLI."""
    parser_help = subprocess.run(
        [sys.executable, str(Path(setup_module.__file__).resolve()), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert parser_help.returncode == 0
    assert "--no-prompt" in parser_help.stdout
