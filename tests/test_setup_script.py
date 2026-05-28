"""Unit tests for scripts/setup/setup.py — exercise the pure functions in isolation.

We import the module directly via importlib (since it lives outside the package
layout) and patch shutil.which / subprocess.run where needed.
"""
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


@pytest.fixture(scope="module")
def setup_module(plugin_root: Path) -> ModuleType:
    path = plugin_root / "scripts" / "setup" / "setup.py"
    assert path.exists(), f"setup.py missing at {path}"
    spec = importlib.util.spec_from_file_location("setup_module", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_python_version_passes_on_310(setup_module: ModuleType) -> None:
    ok, msg = setup_module.check_python_version(min_major=3, min_minor=10, current=(3, 10, 0))
    assert ok, msg


def test_check_python_version_fails_on_old(setup_module: ModuleType) -> None:
    ok, msg = setup_module.check_python_version(min_major=3, min_minor=10, current=(3, 9, 7))
    assert not ok
    assert "3.10" in msg


def test_check_node_version_passes(setup_module: ModuleType) -> None:
    ok, msg = setup_module.check_node_version_string("v20.19.0", min_major=20, min_minor=19)
    assert ok, msg


def test_check_node_version_fails_old(setup_module: ModuleType) -> None:
    ok, msg = setup_module.check_node_version_string("v18.20.0", min_major=20, min_minor=19)
    assert not ok
    assert "20.19" in msg


def test_check_node_version_fails_unparseable(setup_module: ModuleType) -> None:
    ok, _ = setup_module.check_node_version_string("nonsense", min_major=20, min_minor=19)
    assert not ok


def test_check_plugin_presence_finds_installed(setup_module: ModuleType, tmp_path: Path) -> None:
    installed = {
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [{"version": "5.1.0", "scope": "user"}],
        },
    }
    p = tmp_path / "installed_plugins.json"
    p.write_text(json.dumps(installed), encoding="utf-8")
    present, missing = setup_module.check_plugin_presence(
        installed_path=p,
        required={
            "superpowers@claude-plugins-official",
            "cartographer@cartographer-marketplace",
        },
    )
    assert "superpowers@claude-plugins-official" in present
    assert "cartographer@cartographer-marketplace" in missing


def test_check_plugin_presence_missing_file(setup_module: ModuleType, tmp_path: Path) -> None:
    """If installed_plugins.json doesn't exist, every required plugin is reported missing."""
    present, missing = setup_module.check_plugin_presence(
        installed_path=tmp_path / "nope.json",
        required={"superpowers@claude-plugins-official"},
    )
    assert not present
    assert missing == {"superpowers@claude-plugins-official"}


def test_check_plugin_presence_bad_json(setup_module: ModuleType, tmp_path: Path) -> None:
    """A non-JSON installed_plugins.json should treat every required plugin as missing."""
    p = tmp_path / "installed_plugins.json"
    p.write_text("not json at all", encoding="utf-8")
    present, missing = setup_module.check_plugin_presence(
        installed_path=p,
        required={"superpowers@claude-plugins-official"},
    )
    assert not present
    assert missing == {"superpowers@claude-plugins-official"}


def test_check_only_mode_does_not_run_installers(setup_module: ModuleType, tmp_path: Path) -> None:
    """In --check-only mode, ensure_* functions never call their _install_* helpers."""
    with patch.object(setup_module, "_install_openspec") as m_open, \
         patch.object(setup_module, "_install_packages") as m_pkgs, \
         patch.object(setup_module, "_install_playwright") as m_pw:
        setup_module.ensure_openspec(check_only=True, force=False)
        setup_module.ensure_python_test_tools(check_only=True, force=False)
        setup_module.ensure_playwright(check_only=True, force=False)
        m_open.assert_not_called()
        m_pkgs.assert_not_called()
        m_pw.assert_not_called()


def test_main_returns_zero_when_everything_present(setup_module: ModuleType, tmp_path: Path, capsys) -> None:
    """If all deps are present, main(['--check-only']) returns 0."""
    installed = {
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [{}],
            "cartographer@cartographer-marketplace": [{}],
            "ralph-loop@claude-plugins-official": [{}],
        },
    }
    installed_path = tmp_path / "installed.json"
    installed_path.write_text(json.dumps(installed), encoding="utf-8")
    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed_path), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest+httpx+...", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "check_teams_mode", return_value=("teams-mode", "present", None)):
        rc = setup_module.main(["--check-only"])
    assert rc == 0


def test_main_returns_one_when_plugin_missing(setup_module: ModuleType, tmp_path: Path) -> None:
    """If a required plugin is missing, main() returns 1."""
    installed_path = tmp_path / "installed.json"
    installed_path.write_text(json.dumps({"version": 2, "plugins": {}}), encoding="utf-8")
    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed_path), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest+httpx+...", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "check_teams_mode", return_value=("teams-mode", "present", None)):
        rc = setup_module.main(["--check-only"])
    assert rc == 1


# ---- REQ-003 / REQ-004: _python3_on_path helper tests ----------------------


def test_python3_on_path_returns_true_when_present(setup_module: ModuleType) -> None:
    """When shutil.which('python3') resolves, helper returns (True, resolved_path)."""
    with patch("shutil.which", return_value="/usr/bin/python3"):
        result = setup_module._python3_on_path()
    assert result == (True, "/usr/bin/python3")


def test_python3_on_path_returns_remediation_when_missing_linux(setup_module: ModuleType) -> None:
    """On Linux, missing python3 returns (False, str) with apt remediation hint."""
    with patch("shutil.which", return_value=None), \
         patch.object(setup_module.sys, "platform", "linux"):
        ok, msg = setup_module._python3_on_path()
    assert ok is False
    assert isinstance(msg, str)
    assert "python-is-python3" in msg


def test_python3_on_path_returns_remediation_when_missing_windows(setup_module: ModuleType) -> None:
    """On Windows, missing python3 returns (False, str) with py launcher / python.org hint."""
    with patch("shutil.which", return_value=None), \
         patch.object(setup_module.sys, "platform", "win32"):
        ok, msg = setup_module._python3_on_path()
    assert ok is False
    assert isinstance(msg, str)
    assert ("py launcher" in msg or "python.org" in msg)
