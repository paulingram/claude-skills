"""v3.36.0 — the external-LLM gateway installer (scripts/setup/install_gateway.py).

Offline coverage of the LiteLLM-gateway install lifecycle: base-dir/signal/key
resolution, the two AUTH MODES (api-key = full gateway; subscription = fable via
Claude sign-in, gateway OpenAI-only), config/launcher/descriptor generation,
secret hygiene (raw keys live ONLY in gateway.env and are masked everywhere
else), activation (settings.json env block + the codex role split) and its
subscription-mode refusal, uninstall symmetry, and the setup.py wiring.

Every test is hermetic: pip is never invoked (injected/skipped), no network, no
writes outside tmp_path, and ambient CT6_EXTERNAL_LLM / CT6_CODEX_56_AVAILABLE
are scrubbed (the v3.35.0 ambient-leak lesson applied to the new signal).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


# ---- Module loaders ----------------------------------------------------------


@pytest.fixture(scope="module")
def gw(plugin_root: Path) -> ModuleType:
    path = plugin_root / "scripts" / "setup" / "install_gateway.py"
    assert path.exists(), f"install_gateway.py missing at {path}"
    spec = importlib.util.spec_from_file_location("install_gateway_under_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # register BEFORE exec: @dataclass under `from __future__ import annotations`
    # resolves field types via sys.modules.get(cls.__module__)
    sys.modules["install_gateway_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def setup_module(plugin_root: Path) -> ModuleType:
    path = plugin_root / "scripts" / "setup" / "setup.py"
    spec = importlib.util.spec_from_file_location("setup_module_for_gateway", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _scrub_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticity: ambient enable signals must never leak into these tests."""
    monkeypatch.delenv("CT6_EXTERNAL_LLM", raising=False)
    monkeypatch.delenv("CT6_CODEX_56_AVAILABLE", raising=False)
    monkeypatch.delenv("CT6_GATEWAY_HOME", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


RAW_OPENAI_KEY = "sk-test-raw-openai-key-1234abcd"
RAW_ANTHROPIC_KEY = "sk-ant-test-raw-key-9876wxyz"


class _RecordingRunner:
    """Stand-in for subprocess.run: records commands, returns queued rcs."""

    def __init__(self, returncodes: list[int] | None = None) -> None:
        self._rcs = list(returncodes or [])
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):  # noqa: ANN001
        self.calls.append(list(cmd))
        rc = self._rcs.pop(0) if self._rcs else 0

        class _Res:
            returncode = rc
            stdout = ""
            stderr = "" if rc == 0 else "simulated failure"

        return _Res()


@pytest.fixture(autouse=True)
def _stub_registration(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> _RecordingRunner:
    """Hermeticity (v3.37.0): auto-registration EXECUTES commands by default —
    no test may ever run a real schtasks/systemctl/launchctl, write to the real
    home, or touch the real Startup folder. Stub the runner seam, pin the
    platform, and point the no-home Startup-folder resolution at tmp."""
    runner = _RecordingRunner()
    monkeypatch.setattr(gw, "_default_runner", runner)
    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **kwargs: runner.calls.append(list(cmd)))
    monkeypatch.setattr(gw, "_platform_key", lambda: "windows")
    real_startup_dir = gw._windows_startup_dir
    monkeypatch.setattr(
        gw, "_windows_startup_dir",
        lambda home=None: (tmp_path / "_startup") if home is None
        else real_startup_dir(home))
    return runner


@pytest.fixture()
def tmp_agents(tmp_path: Path) -> Path:
    """A tiny agents/ dir with one stem per role bucket, both on fable."""
    agents = tmp_path / "agents"
    agents.mkdir()
    for stem in ("backend", "system-architect"):
        (agents / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: fable\n---\n\nbody\n", encoding="utf-8")
    return agents


def _install(gw: ModuleType, base: Path, *extra: str) -> int:
    """Run the install subcommand offline (--no-install: pip never touched)."""
    return gw.main(["install", "--base-dir", str(base), "--no-install", *extra])


# ---- signal + base-dir + key resolution ---------------------------------------


def test_signal_tri_state(gw: ModuleType) -> None:
    assert gw.resolve_external_llm_signal(True, False, {}) is True
    assert gw.resolve_external_llm_signal(False, True, {}) is False
    # the explicit disable flag overrides a truthy env var
    assert gw.resolve_external_llm_signal(False, True, {"CT6_EXTERNAL_LLM": "1"}) is False
    assert gw.resolve_external_llm_signal(False, False, {"CT6_EXTERNAL_LLM": "1"}) is True
    assert gw.resolve_external_llm_signal(False, False, {"CT6_EXTERNAL_LLM": "0"}) is False
    assert gw.resolve_external_llm_signal(False, False, {}) is None


def test_setup_signal_agrees_with_installer(gw: ModuleType, setup_module: ModuleType) -> None:
    """setup.py's tri-state read and the installer's must never diverge."""
    for env in ({}, {"CT6_EXTERNAL_LLM": "1"}, {"CT6_EXTERNAL_LLM": "no"}):
        assert (setup_module.resolve_external_llm_signal(False, False, env)
                == gw.resolve_external_llm_signal(False, False, env))


def test_base_dir_precedence(gw: ModuleType, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit"
    from_env = {gw.ENV_HOME: str(tmp_path / "from-env")}
    assert gw.resolve_base_dir(str(explicit), from_env) == explicit
    assert gw.resolve_base_dir(None, from_env) == tmp_path / "from-env"
    assert gw.resolve_base_dir(None, {}) == Path.home() / ".architect-team" / "gateway"


def test_env_file_roundtrip_ignores_comments(gw: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "gateway.env"
    gw.write_env_file(path, {"B_KEY": "two=parts", "A_KEY": "one", "EMPTY": ""})
    text = path.read_text(encoding="utf-8")
    assert "EMPTY" not in text, "empty values are dropped, not written"
    path.write_text(text + "# comment\n\n", encoding="utf-8")
    assert gw.read_env_file(path) == {"A_KEY": "one", "B_KEY": "two=parts"}
    assert gw.read_env_file(tmp_path / "missing.env") == {}


def test_resolve_keys_precedence_and_master_key_stability(
    gw: ModuleType, tmp_path: Path
) -> None:
    base = tmp_path / "gw"
    keys1 = gw.resolve_keys(base, openai_arg=None, env={"OPENAI_API_KEY": "sk-from-env"})
    assert keys1["OPENAI_API_KEY"] == "sk-from-env"
    master = keys1[gw.MASTER_KEY_VAR]
    assert master.startswith("sk-ct6-")
    gw.write_env_file(base / gw.ENV_FILE_NAME, keys1)
    # an explicit arg beats env + file; the master key is PRESERVED across runs
    keys2 = gw.resolve_keys(base, openai_arg="sk-from-arg",
                            env={"OPENAI_API_KEY": "sk-from-env"})
    assert keys2["OPENAI_API_KEY"] == "sk-from-arg"
    assert keys2[gw.MASTER_KEY_VAR] == master


def test_auth_mode_resolution(gw: ModuleType) -> None:
    assert gw.resolve_auth_mode({"ANTHROPIC_API_KEY": "sk-ant"}) == gw.AUTH_MODE_API_KEY
    assert gw.resolve_auth_mode({"OPENAI_API_KEY": "sk"}) == gw.AUTH_MODE_SUBSCRIPTION
    assert gw.resolve_auth_mode({}) == gw.AUTH_MODE_SUBSCRIPTION


# ---- generated artifacts -------------------------------------------------------


def test_config_subscription_mode_is_openai_only(gw: ModuleType) -> None:
    cfg = gw.build_gateway_config(gw.AUTH_MODE_SUBSCRIPTION)
    assert f"model_name: {gw.CODEX_ALIAS}" in cfg
    assert "os.environ/OPENAI_API_KEY" in cfg
    assert f"os.environ/{gw.MASTER_KEY_VAR}" in cfg
    # NO Anthropic route: fable stays on Claude Code's native sign-in auth
    assert "anthropic" not in cfg.lower()


def test_config_api_key_mode_adds_anthropic_catch_all(gw: ModuleType) -> None:
    cfg = gw.build_gateway_config(gw.AUTH_MODE_API_KEY)
    assert '- model_name: "*"' in cfg
    assert '"anthropic/*"' in cfg
    assert "os.environ/ANTHROPIC_API_KEY" in cfg
    # secrets are env REFERENCES — a raw key can never appear (none is passed in)
    assert "sk-" not in cfg.replace("sk-ct6", "")


def test_config_codex_alias_matches_model_lever(gw: ModuleType, plugin_root: Path) -> None:
    """The alias written into agents/*.md by the v3.35.0 split and the alias the
    gateway routes MUST be the same string, or the split points at nothing."""
    lever_path = plugin_root / "scripts" / "setup" / "set_default_model.py"
    spec = importlib.util.spec_from_file_location("lever_for_gateway_test", lever_path)
    assert spec is not None and spec.loader is not None
    lever = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lever)
    assert gw.CODEX_ALIAS == lever.CODEX_MODEL


def test_launcher_per_platform(gw: ModuleType, tmp_path: Path) -> None:
    name_win, body_win = gw.build_launcher("windows", tmp_path, 4000)
    assert name_win == "run_gateway.bat"
    assert str(tmp_path / gw.ENV_FILE_NAME) in body_win
    assert str(tmp_path / gw.CONFIG_NAME) in body_win
    assert "--port 4000" in body_win
    # litellm's banner crashes cp1252 consoles — the launcher must force UTF-8
    assert "PYTHONUTF8" in body_win
    name_sh, body_sh = gw.build_launcher("linux", tmp_path, 4123)
    assert name_sh == "run_gateway.sh"
    assert body_sh.startswith("#!/bin/sh")
    assert "--port 4123" in body_sh
    assert "PYTHONUTF8" in body_sh


def test_claude_env_block(gw: ModuleType) -> None:
    block = gw.build_claude_env_block(4000, "sk-ct6-master")
    assert block == {
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
        "ANTHROPIC_AUTH_TOKEN": "sk-ct6-master",
    }


# ---- settings.json activation --------------------------------------------------


def test_apply_claude_env_merges_and_preserves(gw: ModuleType, tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(
        {"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}, "other": True}),
        encoding="utf-8")
    gw.apply_claude_env(settings, 4000, "sk-ct6-m")
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"
    assert data["other"] is True
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"
    assert gw.claude_env_applied(settings, 4000)
    assert not gw.claude_env_applied(settings, 5000)


def test_remove_claude_env_only_removes_our_value(gw: ModuleType, tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    # a user-customized base URL is NEVER clobbered
    settings.write_text(json.dumps(
        {"env": {"ANTHROPIC_BASE_URL": "https://my-corp-gateway.example",
                 "ANTHROPIC_AUTH_TOKEN": "corp"}}), encoding="utf-8")
    assert gw.remove_claude_env(settings, 4000) is False
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == "https://my-corp-gateway.example"
    # ours IS removed, other keys preserved
    gw.apply_claude_env(settings, 4000, "sk-ct6-m")
    settings_data = json.loads(settings.read_text(encoding="utf-8"))
    settings_data["env"]["KEEP"] = "yes"
    settings.write_text(json.dumps(settings_data), encoding="utf-8")
    assert gw.remove_claude_env(settings, 4000) is True
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "ANTHROPIC_BASE_URL" not in data["env"]
    assert "ANTHROPIC_AUTH_TOKEN" not in data["env"]
    assert data["env"]["KEEP"] == "yes"


# ---- install lifecycle ----------------------------------------------------------


def test_install_no_keys_is_provisioned_but_disabled(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "gw"
    assert _install(gw, base) == 0
    out = capsys.readouterr().out
    assert "provisioned but NOT enabled" in out
    assert (base / gw.CONFIG_NAME).is_file()
    assert (base / gw.ENV_FILE_NAME).is_file()
    # only the generated master key lives in gateway.env
    env_vars = gw.read_env_file(base / gw.ENV_FILE_NAME)
    assert set(env_vars) == {gw.MASTER_KEY_VAR}
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["enabled"] is False
    assert state["auth_mode"] == gw.AUTH_MODE_SUBSCRIPTION


def test_install_with_openai_key_enables_and_masks(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "gw"
    assert _install(gw, base, "--openai-key", RAW_OPENAI_KEY) == 0
    out = capsys.readouterr().out
    assert "enabled" in out
    # the raw key appears ONLY in gateway.env — masked in output, absent elsewhere
    assert RAW_OPENAI_KEY not in out
    assert "…" + RAW_OPENAI_KEY[-4:] in out
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)["OPENAI_API_KEY"] == RAW_OPENAI_KEY
    for name in (gw.CONFIG_NAME, gw.STATE_NAME):
        assert RAW_OPENAI_KEY not in (base / name).read_text(encoding="utf-8")
    launcher = list(base.glob("run_gateway.*"))
    assert launcher and RAW_OPENAI_KEY not in launcher[0].read_text(encoding="utf-8")
    desc = list((base / gw.DESCRIPTOR_DIRNAME).glob(f"{gw.SERVICE_NAME}.*"))
    assert desc, "boot descriptor must be written"
    assert RAW_OPENAI_KEY not in desc[0].read_text(encoding="utf-8")


def test_install_check_only_provisions_nothing(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "gw"
    assert gw.main(["install", "--base-dir", str(base), "--check-only",
                    "--openai-key", RAW_OPENAI_KEY]) == 0
    assert not base.exists()
    out = capsys.readouterr().out
    assert "would install" in out
    assert RAW_OPENAI_KEY not in out


def test_install_reinstall_preserves_master_key(gw: ModuleType, tmp_path: Path) -> None:
    base = tmp_path / "gw"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY)
    master1 = gw.read_env_file(base / gw.ENV_FILE_NAME)[gw.MASTER_KEY_VAR]
    _install(gw, base)  # idempotent re-run, key + master preserved from the file
    env_vars = gw.read_env_file(base / gw.ENV_FILE_NAME)
    assert env_vars[gw.MASTER_KEY_VAR] == master1
    assert env_vars["OPENAI_API_KEY"] == RAW_OPENAI_KEY


def test_install_invokes_pip_ladder_when_litellm_missing(
    gw: ModuleType, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    with patch.object(gw, "litellm_installed", return_value=False), \
         patch.object(gw._setup, "_install_packages",
                      side_effect=lambda pkgs: (calls.append(list(pkgs)), (True, None))[1]):
        assert gw.main(["install", "--base-dir", str(tmp_path / "gw"),
                        "--openai-key", RAW_OPENAI_KEY]) == 0
    # the wheel-forcing flag must ride along: litellm's sdist needs a Rust
    # toolchain (observed failing on a real Windows install)
    assert calls == [list(gw.LITELLM_INSTALL_ARGS)]
    assert calls[0][-1] == gw.LITELLM_PACKAGE
    assert "--only-binary" in calls[0]


def test_install_pip_failure_is_a_fail_step_not_a_crash(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with patch.object(gw, "litellm_installed", return_value=False), \
         patch.object(gw._setup, "_install_packages",
                      return_value=(False, "no network")):
        assert gw.main(["install", "--base-dir", str(tmp_path / "gw"),
                        "--openai-key", RAW_OPENAI_KEY]) == 0
    out = capsys.readouterr().out
    assert "[x]" in out and "no network" in out


# ---- activation -----------------------------------------------------------------


def test_activate_api_key_mode_writes_settings_and_applies_split(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(settings), "--agents-dir", str(tmp_agents),
    ) == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"
    master = gw.read_env_file(base / gw.ENV_FILE_NAME)[gw.MASTER_KEY_VAR]
    assert data["env"]["ANTHROPIC_AUTH_TOKEN"] == master
    # the split: dev bucket → codex alias, architecture bucket stays fable
    assert f"model: {gw.CODEX_ALIAS}" in (tmp_agents / "backend.md").read_text(encoding="utf-8")
    assert "model: fable" in (tmp_agents / "system-architect.md").read_text(encoding="utf-8")
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is True
    assert state["auth_mode"] == gw.AUTH_MODE_API_KEY


def test_activate_subscription_mode_refuses_honestly(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No Anthropic key → fable stays on Claude sign-in: NO settings.json write,
    NO codex split, and the printed note says exactly why + the remediation."""
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY,
        "--activate", "--settings-path", str(settings), "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert not settings.exists(), "subscription mode must never write settings.json"
    assert "model: fable" in (tmp_agents / "backend.md").read_text(encoding="utf-8")
    assert "subscription mode" in out
    assert "sign-in" in out
    assert "ANTHROPIC_API_KEY" in out  # the remediation to reach full-gateway mode


# ---- uninstall ------------------------------------------------------------------


def test_uninstall_reverses_activation(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key",
             RAW_ANTHROPIC_KEY, "--activate", "--settings-path", str(settings),
             "--agents-dir", str(tmp_agents))
    assert gw.main(["uninstall", "--base-dir", str(base), "--settings-path",
                    str(settings), "--agents-dir", str(tmp_agents)]) == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "ANTHROPIC_BASE_URL" not in data["env"]
    # uniform fable restored on BOTH buckets
    for stem in ("backend", "system-architect"):
        assert "model: fable" in (tmp_agents / f"{stem}.md").read_text(encoding="utf-8")
    assert not list((base / gw.DESCRIPTOR_DIRNAME).glob(f"{gw.SERVICE_NAME}.*"))
    assert base.exists(), "state dir stays unless --purge"


def test_uninstall_purge_removes_state_dir(gw: ModuleType, tmp_path: Path) -> None:
    base = tmp_path / "gw"
    _install(gw, base)
    assert gw.main(["uninstall", "--base-dir", str(base), "--purge",
                    "--agents-dir", str(tmp_path / "no-agents")]) == 0
    assert not base.exists()


def test_uninstall_check_only_touches_nothing(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key",
             RAW_ANTHROPIC_KEY, "--activate", "--settings-path", str(settings),
             "--agents-dir", str(tmp_agents))
    assert gw.main(["uninstall", "--base-dir", str(base), "--check-only",
                    "--settings-path", str(settings),
                    "--agents-dir", str(tmp_agents)]) == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"
    assert f"model: {gw.CODEX_ALIAS}" in (tmp_agents / "backend.md").read_text(encoding="utf-8")


def test_uninstall_leaves_non_split_model_state_untouched(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    """A manual lever state (e.g. the Opus fallback) is never clobbered."""
    for stem in ("backend", "system-architect"):
        path = tmp_agents / f"{stem}.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "model: fable", "model: opus"), encoding="utf-8")
    base = tmp_path / "gw"
    _install(gw, base)
    assert gw.main(["uninstall", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    for stem in ("backend", "system-architect"):
        assert "model: opus" in (tmp_agents / f"{stem}.md").read_text(encoding="utf-8")


# ---- auto-registration (v3.37.0) --------------------------------------------------


def test_register_windows_shape(gw: ModuleType, tmp_path: Path) -> None:
    runner = _RecordingRunner()
    ok, detail = gw.register_gateway("windows", tmp_path / "run_gateway.bat",
                                     runner=runner)
    assert ok and "started" in detail
    create, run = runner.calls
    assert create[:4] == ["schtasks", "/create", "/tn", gw.SERVICE_NAME]
    assert "/sc" in create and create[create.index("/sc") + 1] == "onlogon"
    assert "/f" in create
    assert str(tmp_path / "run_gateway.bat") in create[create.index("/tr") + 1]
    assert run[:3] == ["schtasks", "/run", "/tn"]


def test_register_linux_user_systemd(gw: ModuleType, tmp_path: Path) -> None:
    runner = _RecordingRunner()
    ok, _ = gw.register_gateway("linux", tmp_path / "run_gateway.sh",
                                home=tmp_path, runner=runner)
    assert ok
    unit = tmp_path / ".config" / "systemd" / "user" / f"{gw.SERVICE_NAME}.service"
    body = unit.read_text(encoding="utf-8")
    # user-level: never sudo, never the system multi-user.target
    assert "WantedBy=default.target" in body
    assert "multi-user.target" not in body
    assert ["systemctl", "--user", "daemon-reload"] in runner.calls
    assert ["systemctl", "--user", "enable", "--now", gw.SERVICE_NAME] in runner.calls
    assert not any("sudo" in c for call in runner.calls for c in call)


def test_register_darwin_launch_agent(gw: ModuleType, tmp_path: Path) -> None:
    runner = _RecordingRunner()
    ok, _ = gw.register_gateway("darwin", tmp_path / "run_gateway.sh",
                                home=tmp_path, runner=runner)
    assert ok
    plist = tmp_path / "Library" / "LaunchAgents" / f"{gw.SERVICE_NAME}.plist"
    assert plist.is_file()
    assert ["launchctl", "load", "-w", str(plist)] in runner.calls


def test_register_windows_falls_back_to_startup_shim(
    gw: ModuleType, tmp_path: Path, _stub_registration: "_RecordingRunner"
) -> None:
    """schtasks /create denied (observed on a real non-elevated Windows 11
    shell) => a Startup-folder shim is written + the launcher started now."""
    runner = _RecordingRunner([1])  # /create denied; everything after rc 0
    launcher = tmp_path / "run.bat"
    ok, detail = gw.register_gateway("windows", launcher, home=tmp_path,
                                     runner=runner)
    assert ok and "startup-folder shim" in detail
    shim = (tmp_path / "AppData" / "Roaming" / "Microsoft" / "Windows"
            / "Start Menu" / "Programs" / "Startup" / f"{gw.SERVICE_NAME}.cmd")
    assert shim.is_file()
    assert str(launcher) in shim.read_text(encoding="utf-8")
    # start-now goes through the DETACHED spawner seam (a captured-pipe run
    # would block until the gateway itself exits) — the autouse stub records it
    assert ["cmd", "/c", str(launcher)] in _stub_registration.calls


def test_register_windows_total_failure_returns_detail(
    gw: ModuleType, tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where a home dir should be", encoding="utf-8")
    runner = _RecordingRunner([1])
    ok, detail = gw.register_gateway("windows", tmp_path / "x.bat",
                                     home=blocker, runner=runner)
    assert ok is False
    assert "fallback also failed" in detail


def test_unregister_windows_stops_then_deletes(gw: ModuleType) -> None:
    runner = _RecordingRunner()
    ok, detail = gw.unregister_gateway("windows", runner=runner)
    assert ok and "removed" in detail
    assert runner.calls[0][:2] == ["schtasks", "/end"]
    assert runner.calls[1][:2] == ["schtasks", "/delete"]
    # an absent task is a tolerated no-op, not a failure (home=None resolves
    # through the autouse-stubbed startup dir, which is fresh and empty)
    runner2 = _RecordingRunner([0, 1])
    ok2, detail2 = gw.unregister_gateway("windows", runner=runner2)
    assert ok2 and "no-op" in detail2


def test_install_auto_registers_when_enabled(
    gw: ModuleType, tmp_path: Path, _stub_registration: "_RecordingRunner",
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _install(gw, tmp_path / "gw", "--openai-key", RAW_OPENAI_KEY) == 0
    out = capsys.readouterr().out
    assert "auto-registered: yes" in out
    creates = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/create"]]
    assert creates, "install must register the gateway when enabled"
    state = json.loads((tmp_path / "gw" / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["registered"] is True


def test_install_no_register_skips(
    gw: ModuleType, tmp_path: Path, _stub_registration: "_RecordingRunner",
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _install(gw, tmp_path / "gw", "--openai-key", RAW_OPENAI_KEY,
                    "--no-register") == 0
    out = capsys.readouterr().out
    assert "auto-registered: no" in out
    assert not [c for c in _stub_registration.calls if c and c[0] == "schtasks"]


def test_install_not_enabled_defers_registration(
    gw: ModuleType, tmp_path: Path, _stub_registration: "_RecordingRunner",
) -> None:
    assert _install(gw, tmp_path / "gw") == 0  # no OpenAI key
    assert not [c for c in _stub_registration.calls if c and c[0] == "schtasks"]


def test_install_registration_failure_degrades(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(gw, "register_gateway",
                        lambda *a, **k: (False, "simulated denial"))
    assert _install(gw, tmp_path / "gw", "--openai-key", RAW_OPENAI_KEY) == 0
    out = capsys.readouterr().out
    assert "[x]" in out and "register manually" in out
    assert "auto-registered: no" in out


def test_uninstall_unregisters(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    _stub_registration: "_RecordingRunner",
) -> None:
    base = tmp_path / "gw"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY)
    _stub_registration.calls.clear()
    assert gw.main(["uninstall", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert ["schtasks", "/end", "/tn", gw.SERVICE_NAME] in _stub_registration.calls
    assert ["schtasks", "/delete", "/tn", gw.SERVICE_NAME, "/f"] in _stub_registration.calls


# ---- status ---------------------------------------------------------------------


def test_status_masks_keys_and_reports_mode(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "gw"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY)
    capsys.readouterr()
    assert gw.main(["status", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert RAW_OPENAI_KEY not in out
    assert "…" + RAW_OPENAI_KEY[-4:] in out
    assert "mode=subscription" in out


# ---- setup.py wiring -------------------------------------------------------------


def test_setup_entry_check_only_is_a_note(gw: ModuleType, tmp_path: Path) -> None:
    name, status, detail = gw.setup_entry(
        enable=True, check_only=True, assume_yes=False,
        base_dir=str(tmp_path / "gw"))
    assert status == "note"
    assert "would install" in (detail or "")
    assert not (tmp_path / "gw").exists()


def test_setup_entry_disable_check_only_is_a_note(gw: ModuleType, tmp_path: Path) -> None:
    name, status, detail = gw.setup_entry(
        enable=False, check_only=True, assume_yes=False,
        base_dir=str(tmp_path / "gw"))
    assert status == "note"


def test_setup_entry_enable_without_consent_hints_activation(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=False,
            base_dir=str(tmp_path / "gw"),
            settings_path=str(tmp_path / "settings.json"),
            agents_dir=str(tmp_agents))
    assert status == "applied"
    assert "mode=subscription" in (detail or "")
    assert "sign-in" in (detail or "")
    assert not (tmp_path / "settings.json").exists()


def test_setup_entry_never_raises(gw: ModuleType, tmp_path: Path) -> None:
    def _boom(args, base):
        raise RuntimeError("boom")

    with patch.dict(gw._HANDLERS, {"install": _boom}):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=False,
            base_dir=str(tmp_path / "gw"))
    assert status == "warn"
    assert "install_gateway.py" in (detail or "")


def _run_setup_main(setup_module: ModuleType, tmp_path: Path, argv: list[str]):
    """Run setup.main with every heavy check stubbed; return the two spies."""
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({"version": 2, "plugins": {
        "superpowers@claude-plugins-official": {},
        "cartographer@cartographer-marketplace": {},
        "ralph-loop@claude-plugins-official": {},
    }}), encoding="utf-8")
    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed), \
         patch.object(setup_module, "check_node_version", return_value=(True, "Node 22")), \
         patch.object(setup_module, "ensure_openspec", return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools", return_value=("pytest", "present", None)), \
         patch.object(setup_module, "ensure_playwright", return_value=("playwright", "present", None)), \
         patch.object(setup_module, "check_teams_mode", return_value=("teams-mode", "present", None)), \
         patch.object(setup_module, "_write_last_run"), \
         patch.object(setup_module, "apply_external_llm_policy",
                      return_value=("external-llm", "applied", None)) as policy_spy, \
         patch.object(setup_module, "check_external_llm_option",
                      wraps=setup_module.check_external_llm_option) as option_spy:
        setup_module.main(argv)
    return policy_spy, option_spy


def test_setup_main_routes_external_llm_flag(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    policy_spy, option_spy = _run_setup_main(setup_module, tmp_path, ["--external-llm"])
    assert policy_spy.called
    (enable, check_only, assume_yes) = policy_spy.call_args[0]
    assert enable is True and check_only is False
    assert not option_spy.called


def test_setup_main_routes_no_external_llm_flag(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    policy_spy, _ = _run_setup_main(setup_module, tmp_path, ["--no-external-llm"])
    assert policy_spy.called
    assert policy_spy.call_args[0][0] is False


def test_setup_main_no_signal_surfaces_note(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    policy_spy, option_spy = _run_setup_main(setup_module, tmp_path, [])
    assert not policy_spy.called
    assert option_spy.called


def test_setup_flags_are_mutually_exclusive(setup_module: ModuleType) -> None:
    with pytest.raises(SystemExit):
        setup_module.main(["--external-llm", "--no-external-llm"])


def test_apply_external_llm_policy_never_gates(setup_module: ModuleType) -> None:
    with patch.object(setup_module, "_load_gateway_installer",
                      side_effect=RuntimeError("boom")):
        name, status, detail = setup_module.apply_external_llm_policy(True, False, False)
    assert status == "warn"
    assert "install_gateway.py" in (detail or "")


def test_apply_external_llm_policy_real_loader_check_only(
    setup_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """REGRESSION (v3.37.1): apply_external_llm_policy through the REAL
    _load_gateway_installer (no patching). The loader must register the module
    in sys.modules before exec or install_gateway's @dataclass definitions die
    under `from __future__ import annotations` — observed on a real
    `setup --external-llm` run as a warn row ('NoneType' has no '__dict__').
    check_only keeps it side-effect-free; a warn here means the loader broke."""
    monkeypatch.setenv("CT6_GATEWAY_HOME", str(tmp_path / "gw"))
    name, status, detail = setup_module.apply_external_llm_policy(
        True, check_only=True, assume_yes=False)
    assert status == "note", f"real loader failed: {detail}"
    assert "would install" in (detail or "")
