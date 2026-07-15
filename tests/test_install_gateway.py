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

v3.38.0 adds the interactive key-prompt + decline-record coverage: the
`_prompt_for_key` seam (interactive + TTY + unresolved + not-declined; hidden
getpass entry with the unachievable->visible degrade), the `key-declines.json`
record (blank-to-skip / the `decline` subcommand / auto-reset on resolution /
`--re-ask-keys`), the never-prompts matrix, and the setup_entry interactivity
pass-through. All prompt/TTY seams are injected — no test touches a real
console or a real getpass.
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


# ---- interactive key prompt + decline record (v3.38.0) ---------------------------


@pytest.fixture(autouse=True)
def _no_real_tty(gw: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticity (v3.38.0): main() opts into prompting on a real TTY, so a
    `pytest -s` run would otherwise hang install tests on a live getpass.
    Default every test to non-TTY; prompt tests re-stub the seams explicitly.
    raising=False keeps this fixture inert against a pre-v3.38.0 module."""
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: False, raising=False)


class _PromptRecorder:
    """Injectable prompt seam: records prompt messages, returns queued answers."""

    def __init__(self, answers: list[str] | None = None) -> None:
        self._answers = list(answers or [])
        self.messages: list[str] = []

    def __call__(self, message: str) -> str:
        self.messages.append(message)
        return self._answers.pop(0) if self._answers else ""


def _interactive(gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
                 answers: list[str]) -> _PromptRecorder:
    """Stub the TTY + prompt seams for an interactive run."""
    rec = _PromptRecorder(answers)
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)
    return rec


def _declines_on_disk(gw: ModuleType, base: Path) -> dict:
    path = base / gw.DECLINES_NAME
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def test_prompt_for_key_contract(gw: ModuleType) -> None:
    """The seam: non-TTY -> None without prompting; blank/whitespace -> None;
    a value comes back stripped."""
    def _boom(message):  # pragma: no cover - must never run
        raise AssertionError("prompt_fn must not fire on a non-TTY stdin")

    assert gw._prompt_for_key("openai", prompt_fn=_boom, isatty_fn=lambda: False) is None
    assert gw._prompt_for_key("openai", prompt_fn=lambda m: "", isatty_fn=lambda: True) is None
    assert gw._prompt_for_key("anthropic", prompt_fn=lambda m: "   ", isatty_fn=lambda: True) is None
    assert gw._prompt_for_key("openai", prompt_fn=lambda m: " sk-x ", isatty_fn=lambda: True) == "sk-x"


def test_default_prompt_seam_is_the_hidden_one(gw: ModuleType) -> None:
    """The DEFAULT prompt seam is the hidden (getpass-backed) entry — the
    never-echoed guarantee holds without any injection."""
    assert gw._default_prompt_fn is gw._hidden_prompt


def test_hidden_prompt_uses_getpass_when_achievable(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda message: "sk-hidden")
    monkeypatch.setattr("builtins.input", lambda message: (_ for _ in ()).throw(
        AssertionError("visible input() must not run when hidden entry works")))
    assert gw._hidden_prompt("K: ") == "sk-hidden"


def test_hidden_prompt_degrades_to_visible_only_when_unachievable(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The degrade condition is getpass's non-console fallback (GetPassWarning),
    NOT an import check — and the degrade carries a one-line visible-entry
    warning before reading."""
    import getpass
    import warnings as _warnings

    def _fallback(message):
        _warnings.warn("Can not control echo on the terminal.", getpass.GetPassWarning)
        return "SHOULD-NEVER-BE-RETURNED"  # pragma: no cover

    monkeypatch.setattr(getpass, "getpass", _fallback)
    monkeypatch.setattr("builtins.input", lambda message: "sk-visible")
    assert gw._hidden_prompt("K: ") == "sk-visible"
    out = capsys.readouterr().out
    assert "VISIBLE" in out or "visible" in out


def test_interactive_install_prompts_openai_then_anthropic(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Interactive + TTY + both slots absent: the seam fires per slot in D1
    order (openai then anthropic); captured keys land ONLY in gateway.env and
    mask to last-4 in every report line."""
    base = tmp_path / "gw"
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY, RAW_ANTHROPIC_KEY])
    assert _install(gw, base, "--interactive-prompts") == 0
    assert len(rec.messages) == 2
    assert "OPENAI_API_KEY" in rec.messages[0]
    assert "ANTHROPIC_API_KEY" in rec.messages[1]
    out = capsys.readouterr().out
    assert RAW_OPENAI_KEY not in out and RAW_ANTHROPIC_KEY not in out
    assert "…" + RAW_OPENAI_KEY[-4:] in out
    assert "…" + RAW_ANTHROPIC_KEY[-4:] in out
    env_vars = gw.read_env_file(base / gw.ENV_FILE_NAME)
    assert env_vars["OPENAI_API_KEY"] == RAW_OPENAI_KEY
    assert env_vars["ANTHROPIC_API_KEY"] == RAW_ANTHROPIC_KEY
    for name in (gw.CONFIG_NAME, gw.STATE_NAME):
        text = (base / name).read_text(encoding="utf-8")
        assert RAW_OPENAI_KEY not in text and RAW_ANTHROPIC_KEY not in text
    # both keys captured => api-key mode, enabled; no declines recorded
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["auth_mode"] == gw.AUTH_MODE_API_KEY
    assert state["enabled"] is True
    assert _declines_on_disk(gw, base) == {}


def test_blank_entry_skips_and_records_prompt_skip_decline(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Blank -> None -> today's absent-key path runs verbatim + the decline is
    recorded with via=prompt-skip."""
    base = tmp_path / "gw"
    rec = _interactive(gw, monkeypatch, ["", ""])
    assert _install(gw, base, "--interactive-prompts") == 0
    assert len(rec.messages) == 2
    out = capsys.readouterr().out
    assert "provisioned but NOT enabled" in out  # the honest absent-key outcome
    declines = _declines_on_disk(gw, base)
    assert set(declines) == {"openai", "anthropic"}
    for slot in ("openai", "anthropic"):
        assert declines[slot]["via"] == "prompt-skip"
        assert declines[slot]["declined_at"]


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, EOFError])
def test_interrupt_at_the_prompt_skips_like_blank(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], interrupt: type,
) -> None:
    """Adversarial remediation (probe iv): Ctrl-C / Ctrl-D at the prompt is a
    SKIP, not an abort — parity with the _prompt_user_consent house pattern
    (setup.py treats an interrupt as a 'no') and the librarian seam. The
    install completes exit 0, each interrupted slot records via=prompt-skip,
    and no key is written."""
    base = tmp_path / "gw"
    calls: list[str] = []

    def _interrupted(message: str) -> str:
        calls.append(message)
        raise interrupt()

    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_prompt_fn", _interrupted)
    assert _install(gw, base, "--interactive-prompts") == 0
    assert len(calls) == 2, "exactly-as-blank: the loop continues to the next slot"
    out = capsys.readouterr().out
    assert "provisioned but NOT enabled" in out  # the absent-key path verbatim
    declines = _declines_on_disk(gw, base)
    assert set(declines) == {"openai", "anthropic"}
    assert all(declines[slot]["via"] == "prompt-skip" for slot in declines)
    env_vars = gw.read_env_file(base / gw.ENV_FILE_NAME)
    assert set(env_vars) == {gw.MASTER_KEY_VAR}, "no key may be invented/written"


def test_recorded_decline_suppresses_the_prompt(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = tmp_path / "gw"
    assert gw.main(["decline", "openai", "--base-dir", str(base)]) == 0
    assert gw.main(["decline", "anthropic", "--base-dir", str(base)]) == 0
    capsys.readouterr()
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY])
    assert _install(gw, base, "--interactive-prompts") == 0
    assert rec.messages == [], "a declined slot must never re-prompt"
    out = capsys.readouterr().out
    assert "declined" in out, "the report must note the recorded decline"


def test_decline_subcommand_records_wrapper_and_clears(
    gw: ModuleType, tmp_path: Path
) -> None:
    base = tmp_path / "gw"
    assert gw.main(["decline", "openai", "--base-dir", str(base)]) == 0
    declines = _declines_on_disk(gw, base)
    assert declines["openai"]["via"] == "wrapper"
    assert declines["openai"]["declined_at"]
    assert gw.main(["decline", "openai", "--clear", "--base-dir", str(base)]) == 0
    assert not (base / gw.DECLINES_NAME).is_file(), "an emptied record removes the file"
    # clearing an absent decline is a tolerated no-op, not a failure
    assert gw.main(["decline", "openai", "--clear", "--base-dir", str(base)]) == 0


def test_decline_subcommand_rejects_unknown_slot(gw: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        gw.main(["decline", "master", "--base-dir", str(tmp_path / "gw")])


@pytest.mark.parametrize("path_kind", ["arg", "env", "file"])
def test_decline_auto_resets_when_key_resolves(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_kind: str
) -> None:
    """A slot's decline auto-resets whenever that slot's key resolves on ANY
    resolution path (args > env > gateway.env)."""
    base = tmp_path / "gw"
    if path_kind == "file":
        _install(gw, base, "--openai-key", RAW_OPENAI_KEY)  # seed gateway.env
    gw.main(["decline", "openai", "--base-dir", str(base)])
    assert "openai" in _declines_on_disk(gw, base)
    if path_kind == "arg":
        _install(gw, base, "--openai-key", RAW_OPENAI_KEY)
    elif path_kind == "env":
        monkeypatch.setenv("OPENAI_API_KEY", RAW_OPENAI_KEY)
        _install(gw, base)
    else:
        _install(gw, base)  # resolves from the seeded gateway.env
    assert "openai" not in _declines_on_disk(gw, base)


def test_re_ask_keys_clears_declines_and_reprompts(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "gw"
    gw.main(["decline", "openai", "--base-dir", str(base)])
    gw.main(["decline", "anthropic", "--base-dir", str(base)])
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY, ""])
    assert _install(gw, base, "--interactive-prompts", "--re-ask-keys") == 0
    assert len(rec.messages) == 2, "--re-ask-keys must make declined slots prompt again"
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)["OPENAI_API_KEY"] == RAW_OPENAI_KEY
    declines = _declines_on_disk(gw, base)
    assert set(declines) == {"anthropic"}  # the fresh blank re-records prompt-skip
    assert declines["anthropic"]["via"] == "prompt-skip"


def test_direct_tty_install_prompts_without_the_flag(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1: main() itself is an interactive caller — a direct terminal run on a
    real TTY (no --json / --check-only) prompts without needing the flag, so
    direct install runs do not stay punt-only."""
    rec = _interactive(gw, monkeypatch, ["", ""])
    assert _install(gw, tmp_path / "gw") == 0
    assert len(rec.messages) == 2


def test_non_tty_never_prompts_even_with_the_flag(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-TTY stdin never prompts and does no decline bookkeeping — behavior
    stays byte-equivalent to the pre-change absent-key path."""
    base = tmp_path / "gw"
    rec = _PromptRecorder([RAW_OPENAI_KEY])
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)  # isatty stays False (autouse)
    assert _install(gw, base, "--interactive-prompts") == 0
    assert rec.messages == []
    assert not (base / gw.DECLINES_NAME).is_file()


def test_check_only_never_prompts_on_a_tty(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "gw"
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY])
    assert gw.main(["install", "--base-dir", str(base), "--check-only",
                    "--interactive-prompts"]) == 0
    assert rec.messages == []
    assert not base.exists(), "check-only must provision nothing"


def test_json_never_prompts_on_a_tty(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = tmp_path / "gw"
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY])
    assert _install(gw, base, "--json", "--interactive-prompts") == 0
    assert rec.messages == []
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "install"


def test_status_and_uninstall_never_prompt(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "gw"
    _install(gw, base)
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY])
    assert gw.main(["status", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert gw.main(["uninstall", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert rec.messages == []


def test_status_reports_declined_slots(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """status appends declined=<slots> when entries exist — and keeps every
    existing field verbatim (the decline suppresses the PROMPT, never the truth)."""
    base = tmp_path / "gw"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY)
    gw.main(["decline", "anthropic", "--base-dir", str(base)])
    capsys.readouterr()
    assert gw.main(["status", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert "declined=anthropic" in out
    assert "mode=subscription" in out
    assert "enabled=" in out and "activated=" in out and "registered=" in out
    assert "ANTHROPIC_API_KEY=absent" in out  # the absent state stays honest


def test_status_without_declines_omits_the_field(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "gw"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY)
    capsys.readouterr()
    assert gw.main(["status", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert "declined=" not in capsys.readouterr().out


def test_plain_uninstall_keeps_the_record_purge_removes_it(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    """Uninstall symmetry: the decline record is state — it survives a plain
    uninstall and goes with the state dir under --purge."""
    base = tmp_path / "gw"
    _install(gw, base)
    gw.main(["decline", "openai", "--base-dir", str(base)])
    assert (base / gw.DECLINES_NAME).is_file()
    assert gw.main(["uninstall", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert (base / gw.DECLINES_NAME).is_file()
    assert gw.main(["uninstall", "--base-dir", str(base), "--purge",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert not base.exists()


# ---- setup_entry interactivity pass-through (v3.38.0) ----------------------------


def test_setup_entry_interactive_pass_through_prompts(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """setup_entry(assume_yes=False, check_only=False) on a TTY appends
    --interactive-prompts — the interactive setup run reaches the seam."""
    rec = _interactive(gw, monkeypatch, ["", ""])
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=False,
            base_dir=str(tmp_path / "gw"))
    assert status == "applied"
    assert len(rec.messages) == 2


def test_setup_entry_assume_yes_never_prompts(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--yes-equivalent runs never prompt (the existing assume_yes -> --activate
    convention is unchanged)."""
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY, RAW_ANTHROPIC_KEY])
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=True,
            base_dir=str(tmp_path / "gw"),
            settings_path=str(tmp_path / "settings.json"),
            agents_dir=str(tmp_agents))
    assert rec.messages == []
    assert status == "applied"


def test_setup_entry_check_only_never_prompts(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY])
    name, status, detail = gw.setup_entry(
        enable=True, check_only=True, assume_yes=False,
        base_dir=str(tmp_path / "gw"))
    assert rec.messages == []
    assert status == "note"
    assert not (tmp_path / "gw").exists()


def test_setup_entry_non_tty_never_prompts(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _PromptRecorder([RAW_OPENAI_KEY])
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)  # isatty stays False (autouse)
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=False,
            base_dir=str(tmp_path / "gw"))
    assert rec.messages == []
    assert status == "applied"


def test_setup_entry_explicit_interactive_false_suppresses(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The explicit interactive=False override (setup.py forwards --no-prompt
    this way) suppresses prompting even on a TTY."""
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY])
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=False,
            base_dir=str(tmp_path / "gw"), interactive=False)
    assert rec.messages == []
    assert status == "applied"


def test_setup_entry_interactive_true_still_guarded_by_assume_yes(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The NOT-assume_yes / NOT-check_only guards are unconditional — an
    (erroneous) interactive=True cannot override them."""
    rec = _interactive(gw, monkeypatch, [RAW_OPENAI_KEY])
    with patch.object(gw, "litellm_installed", return_value=True):
        gw.setup_entry(
            enable=True, check_only=False, assume_yes=True,
            base_dir=str(tmp_path / "gw"),
            settings_path=str(tmp_path / "settings.json"),
            agents_dir=str(tmp_agents), interactive=True)
    assert rec.messages == []


def test_setup_entry_prompt_exception_degrades_to_warn(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Posture preservation: a raising prompt seam (e.g. interrupted stdin)
    degrades to the existing warn row — the prompt never gates setup."""
    def _boom(message):
        raise RuntimeError("interrupted stdin")

    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_prompt_fn", _boom)
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=False,
            base_dir=str(tmp_path / "gw"))
    assert status == "warn"
    assert "install_gateway.py" in (detail or "")
