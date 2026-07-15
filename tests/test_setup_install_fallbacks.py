"""REQ-001…004 + REQ-006 handoff — setup.py first-install hardening.

Covers the four setup-hardening behaviors that broke on a real Linux-VM install
(2026-07-05) plus the fable-availability heuristic note (Team A owns the setup.py
edit; Team B supplies the printed remediation string):

  REQ-001  Cartographer marketplace provenance (kingbootoshi/cartographer)
  REQ-002  npm EACCES fallback -> non-persistent --prefix ~/.local retry
  REQ-003  PEP-668 Python-deps ladder (uv -> pip --user -> --break-system-packages)
           + pip-absent remediation + tiktoken in the dep list
  REQ-004  Non-interactive consent: --yes flag + CT6_SETUP_ASSUME_YES env var
  REQ-006  setup prints the set_default_model fallback remediation (task 2.4)

A NEW focused test file (sanctioned by the design's Reuse Decision Log): the
install-ladder behaviors need INJECTED subprocess runners so the tests never
touch npm/pip/uv for real, which the existing tests/test_setup_teams_checks.py
module-import fixture is not shaped for.
"""
from __future__ import annotations

from tests.helpers.module_loader import load_module
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def setup_module(plugin_root: Path) -> ModuleType:
    path = plugin_root / "scripts" / "setup" / "setup.py"
    assert path.exists(), f"setup.py missing at {path}"
    mod = load_module(path, "setup_module_for_fallbacks")
    return mod


@pytest.fixture(autouse=True)
def _scrub_codex_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticity (v3.35.0): an ambient CT6_CODEX_56_AVAILABLE — the documented
    codex-split deploy config — must NEVER leak into these tests. Without this
    scrub, the two end-to-end main() tests below would route a truthy ambient
    signal into a REAL apply_model_policy write against the repo's own tracked
    agents/*.md. Tests that need the signal set it explicitly after this."""
    monkeypatch.delenv("CT6_CODEX_56_AVAILABLE", raising=False)


class _Result:
    """A minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _RecordingRunner:
    """A callable that records every invocation and returns queued results."""

    def __init__(self, results: list[_Result]) -> None:
        self._results = list(results)
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs):  # noqa: ANN001
        self.calls.append(list(cmd))
        if self._results:
            return self._results.pop(0)
        return _Result(returncode=0)


# ---- REQ-001: cartographer marketplace provenance ---------------------------


def test_cartographer_remediation_names_source_and_orders_steps(
    setup_module: ModuleType,
) -> None:
    """The cartographer remediation names kingbootoshi/cartographer and prints
    `/plugin marketplace add ...` BEFORE `/plugin install ...`."""
    lines = setup_module.plugin_remediation_lines("cartographer@cartographer-marketplace")
    add_idx = next(i for i, l in enumerate(lines) if "marketplace add kingbootoshi/cartographer" in l)
    install_idx = next(i for i, l in enumerate(lines) if "install cartographer@cartographer-marketplace" in l)
    assert lines[add_idx] == "/plugin marketplace add kingbootoshi/cartographer"
    assert lines[install_idx] == "/plugin install cartographer@cartographer-marketplace"
    assert add_idx < install_idx, "marketplace add must precede install"


def test_non_cartographer_plugin_single_install_line(setup_module: ModuleType) -> None:
    """A default-marketplace plugin gets only the install line — no marketplace add."""
    lines = setup_module.plugin_remediation_lines("superpowers@claude-plugins-official")
    assert lines == ["/plugin install superpowers@claude-plugins-official"]
    assert not any("marketplace add" in l for l in lines)


def test_print_report_prints_ordered_cartographer_remediation(
    setup_module: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """_print_report surfaces the ordered cartographer remediation on a miss."""
    setup_module._print_report([], [], ["cartographer@cartographer-marketplace"])
    out = capsys.readouterr().out
    add_pos = out.find("/plugin marketplace add kingbootoshi/cartographer")
    install_pos = out.find("/plugin install cartographer@cartographer-marketplace")
    assert add_pos != -1 and install_pos != -1
    assert add_pos < install_pos


# ---- REQ-002: npm EACCES fallback -------------------------------------------


def test_install_openspec_retries_with_prefix_on_eacces(setup_module: ModuleType) -> None:
    """An EACCES on the global install triggers a --prefix ~/.local retry whose
    message carries the persistent remediation."""
    runner = _RecordingRunner([
        _Result(returncode=1, stderr="npm ERR! code EACCES\nnpm ERR! ... not permitted"),
        _Result(returncode=0),
    ])
    with patch("shutil.which", return_value="/usr/bin/npm"):
        ok, detail = setup_module._install_openspec(runner=runner)
    assert ok is True
    assert len(runner.calls) == 2
    second = runner.calls[1]
    assert "--prefix" in second
    local = str(Path.home() / ".local")
    assert local in second
    assert detail is not None
    assert "npm config set prefix" in detail
    assert "~/.local/bin" in detail or "PATH" in detail


def test_install_openspec_never_mutates_npm_config(setup_module: ModuleType) -> None:
    """The retry NEVER runs `npm config set` — remediation is text only."""
    runner = _RecordingRunner([
        _Result(returncode=1, stderr="EACCES: permission denied"),
        _Result(returncode=0),
    ])
    with patch("shutil.which", return_value="/usr/bin/npm"):
        setup_module._install_openspec(runner=runner)
    for call in runner.calls:
        assert "config" not in call, f"must not mutate npm config: {call}"


def test_install_openspec_non_permission_error_does_not_retry(setup_module: ModuleType) -> None:
    """A non-permission failure is returned as-is with no --prefix retry."""
    runner = _RecordingRunner([
        _Result(returncode=1, stderr="npm ERR! 404 Not Found - GET registry"),
    ])
    with patch("shutil.which", return_value="/usr/bin/npm"):
        ok, detail = setup_module._install_openspec(runner=runner)
    assert ok is False
    assert len(runner.calls) == 1
    assert "404" in (detail or "")


def test_install_openspec_success_first_try(setup_module: ModuleType) -> None:
    runner = _RecordingRunner([_Result(returncode=0)])
    with patch("shutil.which", return_value="/usr/bin/npm"):
        ok, _ = setup_module._install_openspec(runner=runner)
    assert ok is True
    assert len(runner.calls) == 1
    assert "--prefix" not in runner.calls[0]


# ---- REQ-003: PEP-668 Python-deps ladder ------------------------------------


def test_install_packages_uv_rung_uses_uv(setup_module: ModuleType) -> None:
    runner = _RecordingRunner([_Result(returncode=0)])
    ok, _ = setup_module._install_packages(
        ["pytest"], runner=runner, uv_path="/usr/bin/uv"
    )
    assert ok is True
    cmd = runner.calls[0]
    assert cmd[0] == "/usr/bin/uv"
    assert "pip" in cmd and "install" in cmd


def test_install_packages_no_uv_uses_pip_user(setup_module: ModuleType) -> None:
    runner = _RecordingRunner([_Result(returncode=0)])
    ok, _ = setup_module._install_packages(
        ["pytest"], runner=runner, uv_path=None, pip_available=True
    )
    assert ok is True
    cmd = runner.calls[0]
    assert sys.executable in cmd
    assert "pip" in cmd and "install" in cmd and "--user" in cmd


def test_install_packages_externally_managed_retries_break_system(
    setup_module: ModuleType,
) -> None:
    runner = _RecordingRunner([
        _Result(returncode=1, stderr="error: externally-managed-environment\n... use --break-system-packages"),
        _Result(returncode=0),
    ])
    ok, _ = setup_module._install_packages(
        ["pytest"], runner=runner, uv_path=None, pip_available=True
    )
    assert ok is True
    assert len(runner.calls) == 2
    assert "--break-system-packages" in runner.calls[1]


def test_install_packages_no_pip_returns_remediation_no_traceback(
    setup_module: ModuleType,
) -> None:
    runner = _RecordingRunner([])  # must never be called
    ok, detail = setup_module._install_packages(
        ["pytest"], runner=runner, uv_path=None, pip_available=False
    )
    assert ok is False
    assert runner.calls == [], "no subprocess should run when pip is absent"
    assert detail is not None
    assert "python3-pip" in detail


def test_tiktoken_in_python_dep_list(setup_module: ModuleType) -> None:
    """cartographer needs tiktoken; it must be in the installed dep list."""
    assert "tiktoken" in setup_module.PYTHON_TEST_PACKAGES


# ---- REQ-004: non-interactive consent (--yes / CT6_SETUP_ASSUME_YES) ---------


def test_assume_yes_writes_settings_without_calling_input(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """assume_yes=True proceeds as 'y' WITHOUT invoking the interactive prompt."""
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")

    def _boom(_prompt):  # pragma: no cover - must never run
        raise AssertionError("input() must not be called under assume_yes")

    with patch.object(setup_module, "_claude_version_or_none", return_value=(2, 1, 32)), \
         patch.object(setup_module, "_prompt_user_consent", side_effect=_boom):
        name, status, detail = setup_module.check_teams_mode(
            check_only=False,
            no_prompt=False,
            env={},
            settings_path=settings,
            assume_yes=True,
        )
    assert status == "installed"
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"


def test_yes_flag_assumes_consent_end_to_end(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """main(['--yes']) writes settings.json without prompting when the flag is missing."""
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
    settings.write_text("{}", encoding="utf-8")

    def _boom(_prompt):  # pragma: no cover
        raise AssertionError("input() must not be called under --yes")

    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed), \
         patch.object(setup_module, "check_node_version", return_value=(True, "Node 22")), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "DEFAULT_USER_SETTINGS_PATH", settings, create=True), \
         patch.object(setup_module, "_claude_version_or_none", return_value=(2, 1, 32)), \
         patch.object(setup_module, "_prompt_user_consent", side_effect=_boom), \
         patch.dict("os.environ", {}, clear=False) as env:
        env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
        env.pop("CT6_SETUP_ASSUME_YES", None)
        env.pop("CT6_CODEX_56_AVAILABLE", None)  # never write agents/*.md from a test
        rc = setup_module.main(["--yes"])
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"
    assert rc == 0


def test_env_var_assumes_consent_end_to_end(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """CT6_SETUP_ASSUME_YES=1 has the same effect as --yes."""
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
    settings.write_text("{}", encoding="utf-8")

    def _boom(_prompt):  # pragma: no cover
        raise AssertionError("input() must not be called under CT6_SETUP_ASSUME_YES")

    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed), \
         patch.object(setup_module, "check_node_version", return_value=(True, "Node 22")), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "DEFAULT_USER_SETTINGS_PATH", settings, create=True), \
         patch.object(setup_module, "_claude_version_or_none", return_value=(2, 1, 32)), \
         patch.object(setup_module, "_prompt_user_consent", side_effect=_boom), \
         patch.dict("os.environ", {"CT6_SETUP_ASSUME_YES": "1"}, clear=False) as env:
        env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
        env.pop("CT6_CODEX_56_AVAILABLE", None)  # never write agents/*.md from a test
        rc = setup_module.main([])
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"
    assert rc == 0


def test_check_only_still_never_writes_even_with_assume_yes(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """--check-only is report-only and must never write, even with assume_yes."""
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    original = settings.read_text(encoding="utf-8")
    with patch.object(setup_module, "_claude_version_or_none", return_value=(2, 1, 32)):
        setup_module.check_teams_mode(
            check_only=True, no_prompt=True, env={}, settings_path=settings, assume_yes=True
        )
    assert settings.read_text(encoding="utf-8") == original


def test_yes_flag_is_parsed(setup_module: ModuleType) -> None:
    import subprocess
    res = subprocess.run(
        [sys.executable, str(Path(setup_module.__file__).resolve()), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert res.returncode == 0
    assert "--yes" in res.stdout


# ---- REQ-006 (task 2.4): fable-availability heuristic note -------------------


def test_check_model_default_always_notes_fable_fallback(setup_module: ModuleType) -> None:
    """SETUP-ADV-1: the note is UNCONDITIONAL — no version gate (Fable 5's alias
    shipping version is unknowable here). It ALWAYS surfaces the default + the
    verbatim set_default_model fallback lever."""
    name, status, detail = setup_module.check_model_default()
    assert status == "note"
    assert detail is not None
    assert "fable" in detail.lower()
    assert "set_default_model.py" in detail
    assert "--model opus" in detail


def test_check_model_default_has_no_version_gate_constant(setup_module: ModuleType) -> None:
    """SETUP-ADV-1: the false-precision (2,1,32) threshold constant is deleted."""
    assert not hasattr(setup_module, "FABLE_ALIAS_MIN_CLAUDE_VERSION")


def test_check_model_default_never_gates(setup_module: ModuleType) -> None:
    """The row status is 'note' — never a failing/blocking status (never gates)."""
    _, status, _ = setup_module.check_model_default()
    assert status not in {"failed", "missing", "warn", "fail"}


def test_check_model_default_wired_into_main(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [{}],
            "cartographer@cartographer-marketplace": [{}],
            "ralph-loop@claude-plugins-official": [{}],
        },
    }), encoding="utf-8")
    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed), \
         patch.object(setup_module, "check_node_version", return_value=(True, "Node 22")), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "check_teams_mode", return_value=("teams-mode", "present", None)), \
         patch.object(setup_module, "check_model_default", wraps=setup_module.check_model_default) as spy:
        setup_module.main(["--check-only"])
    assert spy.called, "check_model_default must be invoked by main()"


# ---- v3.35.0: Codex 5.6 model role split (availability-gated) ----------------


def test_resolve_codex_signal_precedence(setup_module: ModuleType) -> None:
    """--no-codex beats the env var; --codex asserts availability; env truthy
    counts as available; env SET-but-falsy is an explicit unavailability
    assertion; the var absent resolves to None (leave untouched)."""
    rs = setup_module.resolve_codex_signal
    assert rs(False, True, {"CT6_CODEX_56_AVAILABLE": "1"}) is False
    assert rs(True, False, {}) is True
    assert rs(False, False, {"CT6_CODEX_56_AVAILABLE": "1"}) is True
    assert rs(False, False, {"CT6_CODEX_56_AVAILABLE": "0"}) is False
    assert rs(False, False, {}) is None


def test_check_codex_option_is_an_informative_note(setup_module: ModuleType) -> None:
    """With no signal, setup surfaces the split as an option and states that the
    current operating model (uniform fable + the Opus fallback lever) stays."""
    name, status, detail = setup_module.check_codex_option()
    assert status == "note"
    assert "--codex" in detail
    assert "CT6_CODEX_56_AVAILABLE" in detail
    assert "codex-5.6-sol" in detail
    assert "fable" in detail


def _agents_copy(tmp_path: Path) -> Path:
    import shutil

    plugin_root = Path(__file__).resolve().parents[1]
    dst = tmp_path / "agents"
    shutil.copytree(plugin_root / "agents", dst)
    return dst


def test_apply_model_policy_check_only_writes_nothing(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    agents = _agents_copy(tmp_path)
    before = {p.name: p.read_bytes() for p in agents.glob("*.md")}
    name, status, detail = setup_module.apply_model_policy(True, True, agents_dir=agents)
    assert status == "note"
    assert "codex-split" in detail
    assert before == {p.name: p.read_bytes() for p in agents.glob("*.md")}


def test_apply_model_policy_applies_the_split(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    agents = _agents_copy(tmp_path)
    name, status, detail = setup_module.apply_model_policy(True, False, agents_dir=agents)
    assert status == "applied"
    assert "codex-5.6-sol" in detail
    lever = setup_module._load_model_lever()
    assert lever.policy_state(agents) == "codex-split"
    # Second run: already compliant, nothing rewritten.
    _, status2, _ = setup_module.apply_model_policy(True, False, agents_dir=agents)
    assert status2 == "present"


def test_apply_model_policy_no_codex_restores_the_operating_model(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    agents = _agents_copy(tmp_path)
    lever = setup_module._load_model_lever()
    lever.apply_split(agents)
    name, status, detail = setup_module.apply_model_policy(False, False, agents_dir=agents)
    assert status == "applied"
    assert "uniform fable" in detail
    assert lever.distribution(agents) == {"fable": 39}


def test_apply_model_policy_never_gates(setup_module: ModuleType) -> None:
    """Any lever failure degrades to a 'warn' row with the manual remediation —
    the model policy must never block setup."""
    def _boom() -> None:
        raise RuntimeError("lever unavailable")

    with patch.object(setup_module, "_load_model_lever", _boom):
        name, status, detail = setup_module.apply_model_policy(True, False)
    assert status == "warn"
    assert "--split codex" in detail


def test_apply_model_policy_missing_agents_dir_warns(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """A missing agents dir is a 'warn' row naming the path — never a success
    row claiming the split is in effect with 0 files rewritten."""
    missing = tmp_path / "nonexistent-agents"
    name, status, detail = setup_module.apply_model_policy(True, False, agents_dir=missing)
    assert status == "warn"
    assert "not found" in detail
    assert "--split codex" in detail


def _wired_main(setup_module: ModuleType, tmp_path: Path, argv: list[str]):
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [{}],
            "cartographer@cartographer-marketplace": [{}],
            "ralph-loop@claude-plugins-official": [{}],
        },
    }), encoding="utf-8")
    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed), \
         patch.object(setup_module, "check_node_version", return_value=(True, "Node 22")), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "check_teams_mode", return_value=("teams-mode", "present", None)), \
         patch.object(setup_module, "apply_model_policy",
                      return_value=("model-policy", "note", None)) as policy_spy, \
         patch.object(setup_module, "check_codex_option",
                      wraps=setup_module.check_codex_option) as option_spy:
        setup_module.main(argv)
    return policy_spy, option_spy


def test_codex_flag_routes_to_apply_model_policy(
    setup_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CT6_CODEX_56_AVAILABLE", raising=False)
    policy_spy, option_spy = _wired_main(setup_module, tmp_path, ["--check-only", "--codex"])
    assert policy_spy.called
    assert policy_spy.call_args[0][0] is True  # codex_signal
    assert not option_spy.called


def test_no_signal_routes_to_the_option_note(
    setup_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CT6_CODEX_56_AVAILABLE", raising=False)
    policy_spy, option_spy = _wired_main(setup_module, tmp_path, ["--check-only"])
    assert option_spy.called
    assert not policy_spy.called


def test_env_var_signal_routes_to_apply_model_policy(
    setup_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CT6_CODEX_56_AVAILABLE", "1")
    policy_spy, option_spy = _wired_main(setup_module, tmp_path, ["--check-only"])
    assert policy_spy.called
    assert policy_spy.call_args[0][0] is True
    assert not option_spy.called
