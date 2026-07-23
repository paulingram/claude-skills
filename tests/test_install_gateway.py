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
import os
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
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CT6_SECONDARY_PROVIDER", raising=False)


@pytest.fixture(autouse=True)
def _sandbox_default_settings_path(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    """REQ-004 GLOBAL hermeticity for this module: every subcommand that does
    not receive an explicit ``--settings-path`` falls back to
    ``_setup.DEFAULT_USER_SETTINGS_PATH`` — the developer's REAL
    ``~/.claude/settings.json``. ``uninstall`` then calls ``remove_claude_env``
    on it, stripping ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN whenever the
    recorded BASE_URL matches the port.

    On CI and on never-activated machines that silently no-ops, which is
    precisely why it survived undetected: the damage is invisible except on an
    ACTIVATED machine, where every full suite run deactivated the gateway while
    ``gateway.json`` still recorded ``activated: true`` — the drift this change
    exists to fix, caused by this change's own test suite.

    Redirect the fallback at a per-test sentinel so NO test in this module —
    present or future, whether or not its author remembers ``--settings-path``
    — can reach the real file. Tests that pass ``--settings-path`` explicitly
    are unaffected (the argument beats the fallback); the sentinel simply
    absorbs anything that would otherwise escape.
    """
    sentinel = tmp_path / "SENTINEL-default-user-settings.json"
    monkeypatch.setattr(gw._setup, "DEFAULT_USER_SETTINGS_PATH", sentinel)
    return sentinel


def test_default_settings_path_fallback_is_absorbed_by_the_sentinel(
    gw: ModuleType, tmp_path: Path,
    _sandbox_default_settings_path: Path,
) -> None:
    """REQ-004 probe: prove the autouse redirect actually absorbs the fallback.

    Assert-sentinel-first and side-effect-free: it stands up an ACTIVATED
    sentinel, runs the historically-leaking invocation shape (no
    ``--settings-path``), and asserts the strip landed on the SENTINEL. Pre-fix
    — with no redirect in place — the strip lands on the real file and the
    sentinel is never even created, so this fails without touching anything.
    """
    sentinel = _sandbox_default_settings_path
    sentinel.write_text(json.dumps({"env": {
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
        "ANTHROPIC_AUTH_TOKEN": "sk-fake-master-key",
    }}, indent=2), encoding="utf-8")

    assert gw._setup.DEFAULT_USER_SETTINGS_PATH == sentinel, (
        "the autouse redirect is not in effect — the module would resolve the "
        "REAL ~/.claude/settings.json")

    base = tmp_path / "gw"
    _install(gw, base)
    assert gw.main(["uninstall", "--base-dir", str(base), "--purge",
                    "--agents-dir", str(tmp_path / "no-agents")]) == 0

    # The strip landed HERE, on the sentinel — never on the real file.
    env = json.loads(sentinel.read_text(encoding="utf-8")).get("env", {})
    assert "ANTHROPIC_BASE_URL" not in env, (
        "the fallback resolution did not land on the sentinel")
    assert env.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1", (
        "remove_claude_env must stay merge-preserving on unrelated keys")


RAW_OPENAI_KEY = "sk-test-raw-openai-key-1234abcd"
RAW_ZAI_KEY = "zai-test-raw-key-4567efgh"
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


@pytest.fixture(autouse=True)
def _stub_live_probe(gw: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticity (v3.39.0; completion probe v3.41.0; /model/info seam
    v3.41.0 iteration 3): the post-install confirm step probes the LIVE local
    gateway's /v1/models AND /v1/messages by default — no test may ever open
    a real socket (a REAL gateway may be listening on the default port) or
    sleep through the retry backoff. Serve the expected ids + a non-empty
    completion instantly; failure tests override the probers and the zeroed
    backoff stands. The served-state staleness prober raises by default —
    the honest keyless/cold-start shape (an unreachable /model/info cannot
    judge staleness, so no proactive restart fires; the spawn-mandatory
    confirm is the fail-closed backstop) — and staleness tests override it
    with a fake serving the stale group set."""
    monkeypatch.setattr(
        gw, "_default_models_prober",
        lambda port, key, timeout=5.0: [
            gw.SECONDARY_ALIAS, gw.SPAWN_ALIAS_MODEL_ID, gw.FABLE_MODEL])
    monkeypatch.setattr(
        gw, "_default_completion_prober",
        lambda port, key, model, timeout=30.0, expected_upstream=None: "ok")
    # Iteration 5: the auth-enforcement probe (invalid-key rejection) rides
    # the same seam discipline — a REAL gateway may listen on port 4000, so
    # the default here reports auth enforced; the 200/5xx failure tests
    # override it per-test.
    monkeypatch.setattr(
        gw, "_default_auth_prober",
        lambda port, timeout=10.0: (
            True, "auth enforcement VERIFIED — a deliberately-invalid key "
                  "was rejected with HTTP 401"))

    def _no_live_model_info(port, key, timeout=5.0):
        raise ConnectionRefusedError("hermetic: no live /model/info")

    monkeypatch.setattr(gw, "_default_model_info_prober", _no_live_model_info)
    monkeypatch.setattr(gw, "CONFIRM_ATTEMPTS", 2)
    monkeypatch.setattr(gw, "CONFIRM_DELAY", 0)
    # Iteration 4: the verified restart's port-grace + bind-verification polls
    # ride the same zeroed-backoff discipline (never a real sleep in tests).
    monkeypatch.setattr(gw, "RESTART_PORT_ATTEMPTS", 2)
    monkeypatch.setattr(gw, "RESTART_PORT_DELAY", 0)
    monkeypatch.setattr(gw, "RESTART_BIND_ATTEMPTS", 2)
    monkeypatch.setattr(gw, "RESTART_BIND_DELAY", 0)


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


def _staging_attempts(calls: list[list[str]]) -> list[list[str]]:
    """The staging-launcher spawn calls a recorded command list carries — the
    iteration-6 (SR-glm-fix-iter6) verify-then-swap attempt evidence: every
    install restart now STAGES the replacement before any live stop."""
    return [c for c in calls
            if any("run_gateway_staging" in str(part) for part in c)]


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


def test_secondary_provider_resolution_ladder(
    gw: ModuleType, tmp_path: Path
) -> None:
    base = tmp_path / "gw"
    gw._write_state(base, {"secondary_provider": "openai"})
    assert gw.resolve_secondary_provider(
        "zai", base, env={gw.ENV_SECONDARY_PROVIDER: "openai"})[:2] == ("zai", "flag")
    assert gw.resolve_secondary_provider(
        None, base, env={gw.ENV_SECONDARY_PROVIDER: "zai"})[:2] == ("zai", "env")
    assert gw.resolve_secondary_provider(None, base, env={})[:2] == ("openai", "recorded")


def test_secondary_provider_grandfather_and_default(gw: ModuleType, tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    gw._write_state(legacy, {"openai_model": "gpt-old"})
    assert gw.resolve_secondary_provider(None, legacy, env={})[:2] == (
        "openai", "grandfather")
    fresh = tmp_path / "fresh"
    assert gw.resolve_secondary_provider(None, fresh, env={})[:2] == (
        "openai", "default")


def test_secondary_provider_interactive_and_reask(gw: ModuleType, tmp_path: Path) -> None:
    base = tmp_path / "gw"
    gw._write_state(base, {"secondary_provider": "openai"})
    calls: list[str] = []

    def choose(message: str) -> str:
        calls.append(message)
        return "zai"

    provider, source, error = gw.resolve_secondary_provider(
        None, base, env={}, interactive=True, prompt_fn=choose,
        isatty_fn=lambda: True)
    assert (provider, source, error) == ("openai", "recorded", None)
    assert calls == []
    provider, source, error = gw.resolve_secondary_provider(
        None, base, env={}, re_ask=True, interactive=True, prompt_fn=choose,
        isatty_fn=lambda: True)
    assert (provider, source, error) == ("zai", "interactive", None)
    assert len(calls) == 1


def test_secondary_provider_unknown_is_error(gw: ModuleType, tmp_path: Path) -> None:
    provider, source, error = gw.resolve_secondary_provider(
        "bogus", tmp_path / "gw", env={})
    assert provider is None and source == "flag"
    assert "openai" in (error or "") and "zai" in (error or "")


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
    assert f"model_name: {gw.SECONDARY_ALIAS}" in cfg
    assert "os.environ/OPENAI_API_KEY" in cfg
    assert f"os.environ/{gw.MASTER_KEY_VAR}" in cfg
    # NO Anthropic route: fable stays on Claude Code's native sign-in auth
    assert "anthropic" not in cfg.lower()


def test_zai_config_shape_and_secret_hygiene(gw: ModuleType) -> None:
    """v3.41.0 (BUG-A): the zai route rides the registry's hosted_vllm
    (strict chat-completions) dialect — the openai/ prefix drove LiteLLM's
    Anthropic-format bridge through the OpenAI Responses API, which api.z.ai
    does not implement (live 404 at /v4/responses)."""
    cfg = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION,
        secondary_provider="zai",
        secondary_model="glm-5.2")
    assert f"model_name: {gw.SECONDARY_ALIAS}" in cfg
    assert "model: hosted_vllm/glm-5.2" in cfg
    assert "model: openai/glm-5.2" not in cfg
    assert "api_key: os.environ/ZAI_API_KEY" in cfg
    assert "api_base: https://api.z.ai/api/paas/v4" in cfg
    assert RAW_ZAI_KEY not in cfg


def test_secondary_model_override_preserves_provider_prefix(gw: ModuleType) -> None:
    cfg = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION,
        secondary_provider="zai",
        secondary_model="glm-custom")
    assert "model: hosted_vllm/glm-custom" in cfg
    assert "api_base: https://api.z.ai/api/paas/v4" in cfg


@pytest.mark.parametrize("provider", ["openai", "zai"])
def test_generator_shape_is_provider_neutral(gw: ModuleType, provider: str) -> None:
    """B4-note pin (glm-secondary-route-fix): BOTH providers get the same
    generator shape — the registry-dialect secondary route, the spawn-alias
    impersonation route mapped to the SAME dialect-prefixed model, and (in
    api-key mode) both emitted BEFORE the anthropic catch-all. Provider
    neutrality is machine-enforced, not a zai special case."""
    entry = gw.SECONDARY_PROVIDERS[provider]
    expected_route = f"{entry['route_dialect']}/{entry['model']}"
    cfg = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider=provider)
    for alias in (gw.SECONDARY_ALIAS, gw.SPAWN_ALIAS_MODEL_ID):
        block_start = cfg.index(f"model_name: {alias}")
        route_line = next(
            ln for ln in cfg[block_start:].splitlines()
            if ln.strip().startswith("model: "))
        assert route_line.strip() == f"model: {expected_route}", alias
        assert block_start < cfg.index('model_name: "*"'), alias
    # no hard-coded prefix survives anywhere in the generator output for a
    # provider whose dialect is not openai
    if entry["route_dialect"] != "openai":
        assert f"openai/{entry['model']}" not in cfg


def test_config_api_key_mode_adds_anthropic_catch_all(gw: ModuleType) -> None:
    cfg = gw.build_gateway_config(gw.AUTH_MODE_API_KEY)
    assert '- model_name: "*"' in cfg
    assert '"anthropic/*"' in cfg
    assert "os.environ/ANTHROPIC_API_KEY" in cfg
    # secrets are env REFERENCES — a raw key can never appear (none is passed in)
    assert "sk-" not in cfg.replace("sk-ct6", "")


def test_config_api_key_mode_has_explicit_anthropic_routes(gw: ModuleType) -> None:
    """v3.38.1 (SR-gateway-wildcard-route): the '*' catch-all alone was
    field-observed broken — every known Anthropic id gets its OWN route, fable
    first, all emitted BEFORE the catch-all tail. v3.41.0: the ONE exception
    is the spawn alias, whose explicit route IS the impersonation route — a
    duplicate model_name would form a LiteLLM load-balancing group mixing the
    secondary with the real Anthropic model."""
    cfg = gw.build_gateway_config(gw.AUTH_MODE_API_KEY)
    assert "claude-fable-5" in gw.ANTHROPIC_EXPLICIT_MODELS[0]
    assert "claude-opus-4-8" in gw.ANTHROPIC_EXPLICIT_MODELS
    for anthropic_id in gw.ANTHROPIC_EXPLICIT_MODELS:
        assert f"- model_name: {anthropic_id}\n" in cfg, anthropic_id
        if anthropic_id == gw.SPAWN_ALIAS_MODEL_ID:
            assert f"model: anthropic/{anthropic_id}\n" not in cfg, \
                "the spawn alias must have exactly ONE route (the impersonation)"
            continue
        assert f"model: anthropic/{anthropic_id}\n" in cfg, anthropic_id
    # ordering: every explicit route precedes the catch-all
    assert cfg.rindex("model: anthropic/claude-fable-5") < cfg.index('- model_name: "*"')
    # the spawn alias appears exactly once — one model_name, one backend
    assert cfg.count(f"- model_name: {gw.SPAWN_ALIAS_MODEL_ID}\n") == 1


def test_config_subscription_mode_has_no_anthropic_routes(gw: ModuleType) -> None:
    """Subscription mode still writes ZERO Anthropic-backed routes — fable
    stays on Claude Code's native sign-in auth (the v3.36.0 posture,
    unchanged). v3.41.0: the spawn alias line IS present, but it is a
    secondary-backed impersonation route (the chosen provider's key), never
    an anthropic/ route or an ANTHROPIC_API_KEY reference."""
    cfg = gw.build_gateway_config(gw.AUTH_MODE_SUBSCRIPTION)
    assert "model: anthropic/" not in cfg
    assert "ANTHROPIC_API_KEY" not in cfg
    for anthropic_id in gw.ANTHROPIC_EXPLICIT_MODELS:
        if anthropic_id == gw.SPAWN_ALIAS_MODEL_ID:
            continue  # the impersonation route — secondary-backed, allowed
        assert anthropic_id not in cfg, anthropic_id


def test_config_secondary_alias_matches_model_lever(gw: ModuleType, plugin_root: Path) -> None:
    """The alias written into agents/*.md and the gateway route must match."""
    lever_path = plugin_root / "scripts" / "setup" / "set_default_model.py"
    spec = importlib.util.spec_from_file_location("lever_for_gateway_test", lever_path)
    assert spec is not None and spec.loader is not None
    lever = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lever)
    assert gw.SECONDARY_ALIAS == lever.SECONDARY_ALIAS
    assert gw.CODEX_ALIAS == lever.CODEX_MODEL  # deprecated reader compatibility


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


def test_install_zai_records_provider_and_keeps_raw_key_only_in_env(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    assert RAW_ZAI_KEY not in out
    assert "secondary=zai/glm-5.2" in out or "zai/glm-5.2" in out
    env_vars = gw.read_env_file(base / gw.ENV_FILE_NAME)
    assert env_vars["ZAI_API_KEY"] == RAW_ZAI_KEY
    for path in (base / gw.CONFIG_NAME, base / gw.STATE_NAME):
        assert RAW_ZAI_KEY not in path.read_text(encoding="utf-8")
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["secondary_provider"] == "zai"
    assert state["secondary_model"] == "glm-5.2"
    assert state["secondary_alias"] == gw.SECONDARY_ALIAS
    assert state["codex_alias"] == gw.SECONDARY_ALIAS


def test_secondary_model_and_deprecated_openai_model_synonym(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "secondary"
    _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY,
             "--secondary-model", "glm-custom")
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["secondary_model"] == "glm-custom"
    assert "model: hosted_vllm/glm-custom" in (base / gw.CONFIG_NAME).read_text(encoding="utf-8")
    legacy = tmp_path / "legacy"
    _install(gw, legacy, "--openai-key", RAW_OPENAI_KEY,
             "--openai-model", "gpt-custom")
    assert "deprecated" in capsys.readouterr().err.lower()
    state = json.loads((legacy / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["secondary_model"] == "gpt-custom"


def test_install_unknown_provider_writes_no_state(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "bogus") == 0
    assert not (base / gw.STATE_NAME).exists()
    out = capsys.readouterr().out
    assert "unknown secondary provider" in out
    assert "openai" in out and "zai" in out


def test_fake_provider_registry_entry_is_the_whole_integration(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-001 extensibility acceptance: ONE new SECONDARY_PROVIDERS dict entry
    is a complete provider integration — the install resolves --secondary
    <fake>, grows the per-provider key flag, generates the config route with
    the entry's route DIALECT / key_env / api_base, and records the choice,
    all WITHOUT any code change. monkeypatch.setitem mutates the SHARED lever
    registry dict in place (installer + parser + lever see one object) and
    removes the entry on teardown. The fake entry deliberately uses a
    chat-completions-only dialect: a third such provider is exactly one dict
    entry, no generator edit (the B4 class statement)."""
    fake_key = "fake-raw-key-0000zzzz"
    monkeypatch.setitem(gw.SECONDARY_PROVIDERS, "fakeprov", {
        "model": "fake-model-9",
        "key_env": "FAKEPROV_API_KEY",
        "route_dialect": "hosted_vllm",
        "api_base": "https://fake.example/v1",
        "label": "FakeProv Fake 9 (fake-model-9)",
    })
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "fakeprov",
                    "--fakeprov-key", fake_key) == 0
    config = (base / gw.CONFIG_NAME).read_text(encoding="utf-8")
    assert "model: hosted_vllm/fake-model-9" in config
    assert "openai/fake-model-9" not in config
    assert "api_key: os.environ/FAKEPROV_API_KEY" in config
    assert "api_base: https://fake.example/v1" in config
    assert fake_key not in config, "raw keys never reach config.yaml"
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)["FAKEPROV_API_KEY"] == fake_key
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["secondary_provider"] == "fakeprov"
    assert state["secondary_model"] == "fake-model-9"
    assert state["enabled"] is True


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


def test_provider_switch_retains_the_other_providers_stored_key(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADV3-2: switching --secondary must never DELETE the other provider's
    stored key from gateway.env (the baseline carried OPENAI_API_KEY forward
    on every rewrite). Switch to zai: the OpenAI key stays while zai behaves
    per its OWN resolution (provisioned but NOT enabled without a zai key);
    switch back: enabled again with NO re-supply."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--openai-key", RAW_OPENAI_KEY) == 0
    master = gw.read_env_file(base / gw.ENV_FILE_NAME)[gw.MASTER_KEY_VAR]
    capsys.readouterr()
    assert _install(gw, base, "--secondary", "zai") == 0
    out = capsys.readouterr().out
    env_vars = gw.read_env_file(base / gw.ENV_FILE_NAME)
    assert env_vars["OPENAI_API_KEY"] == RAW_OPENAI_KEY, \
        "a provider switch must not delete the other provider's stored key"
    assert env_vars[gw.MASTER_KEY_VAR] == master
    assert "provisioned but NOT enabled" in out
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["secondary_provider"] == "zai"
    assert state["enabled"] is False
    # switch back: the retained key re-enables without re-supplying anything
    assert _install(gw, base, "--secondary", "openai") == 0
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["secondary_provider"] == "openai"
    assert state["enabled"] is True
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)["OPENAI_API_KEY"] == RAW_OPENAI_KEY


def test_policy_strings_are_single_sourced_from_the_lever(gw: ModuleType) -> None:
    """ADV3-5 note: the canonical/legacy model-policy strings live in the lever
    and the gateway imports them — no duplicated literals to drift."""
    assert gw.POLICY_SECONDARY_SPLIT == gw._lever.POLICY_SECONDARY_SPLIT \
        == "secondary-split"
    assert gw.POLICY_UNIFORM_FABLE == gw._lever.POLICY_UNIFORM_FABLE \
        == "uniform-fable"
    assert gw.LEGACY_POLICY_CODEX_SPLIT == gw._lever.LEGACY_POLICY_CODEX_SPLIT \
        == "codex-split"


def test_secondary_help_derives_provider_names_from_the_registry(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADV3-6 note: the --secondary help enumeration derives from the registry
    — a new entry extends the help automatically instead of the help lying."""
    monkeypatch.setitem(gw.SECONDARY_PROVIDERS, "fakeprov", {
        "model": "fake-model-9", "key_env": "FAKEPROV_API_KEY",
        "route_dialect": "openai", "api_base": None,
        "label": "FakeProv Fake 9 (fake-model-9)"})
    help_text = gw._build_parser().format_help()
    assert "fakeprov|openai|zai" in help_text


def test_provider_prompt_interrupt_defaults_to_openai_and_is_recorded(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADV3-7(b), pinned deliberate: Ctrl-C / Ctrl-D at the interactive
    provider prompt selects the documented ladder's FINAL rung — default
    openai — and the install proceeds and RECORDS the choice like any
    default (parity with the key prompt's interrupt-means-skip pattern)."""
    def raise_interrupt(message: str) -> str:
        raise KeyboardInterrupt

    def raise_eof(message: str) -> str:
        raise EOFError

    assert gw._prompt_for_provider(
        prompt_fn=raise_interrupt, isatty_fn=lambda: True) == "openai"
    assert gw._prompt_for_provider(
        prompt_fn=raise_eof, isatty_fn=lambda: True) == "openai"
    # end-to-end: an interactive install interrupted at the provider prompt
    # completes and records secondary_provider=openai in gateway.json.
    monkeypatch.setattr(gw, "_default_provider_prompt_fn", raise_interrupt)
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_prompt_fn", lambda message: "")  # keys: blank-skip
    base = tmp_path / "gw"
    assert _install(gw, base, "--interactive-prompts") == 0
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["secondary_provider"] == "openai"


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
    # the split: dev bucket → the spawn-compatible impersonation alias
    # (v3.41.0 — the harness spawn gate rejects custom ids), architecture
    # bucket stays fable
    assert f"model: {gw.SPAWN_ALIAS_MODEL_ID}" in (tmp_agents / "backend.md").read_text(encoding="utf-8")
    assert "model: fable" in (tmp_agents / "system-architect.md").read_text(encoding="utf-8")
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is True
    assert state["auth_mode"] == gw.AUTH_MODE_API_KEY
    # v3.41.0 impersonation disclosure in state
    assert state["spawn_alias"] == gw.SPAWN_ALIAS_MODEL_ID
    assert state["spawn_alias_maps_to"] == "gpt-5.6-sol"


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


def test_setup_entry_zai_subscription_is_honest_and_provider_neutral(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    """REQ-005 symmetry: a zai install with NO Anthropic key is subscription
    mode with the SAME guarantees as the OpenAI twin — the split stays OFF,
    ANTHROPIC_BASE_URL is never written to settings.json — and the one-row
    setup summary derives the served provider from the registry entry's label
    (single-sourced), never from hand-written 'OpenAI' prose."""
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    gw.write_env_file(base / gw.ENV_FILE_NAME, {"ZAI_API_KEY": RAW_ZAI_KEY})
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=True,
            base_dir=str(base), settings_path=str(settings),
            agents_dir=str(tmp_agents), secondary="zai")
    assert status == "applied"
    detail = detail or ""
    assert not settings.exists(), \
        "subscription mode must never write ANTHROPIC_BASE_URL to settings.json"
    assert "model: fable" in (tmp_agents / "backend.md").read_text(encoding="utf-8"), \
        "the secondary split must stay OFF in subscription mode"
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["auth_mode"] == gw.AUTH_MODE_SUBSCRIPTION
    assert state["activated"] is False
    assert state["model_policy"] == "uniform-fable"
    assert "secondary=zai/glm-5.2" in detail
    assert "sign-in" in detail  # the honest why
    assert "serves OpenAI only" not in detail, \
        "the served-provider prose must come from the registry, not a hard-coded string"
    assert str(gw.SECONDARY_PROVIDERS["zai"]["label"]) in detail


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


def test_uninstall_restores_legacy_alias_split_from_legacy_state(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    legacy_alias = gw._lever.LEGACY_SECONDARY_ALIASES[0]
    gw._lever.apply_split(tmp_agents, legacy_alias)
    base = tmp_path / "gw"
    gw._write_state(base, {
        "port": gw.DEFAULT_PORT,
        "model_policy": "codex-split",
        "codex_alias": legacy_alias,
    })
    assert gw.main([
        "uninstall", "--base-dir", str(base),
        "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents),
    ]) == 0
    assert gw._lever.distribution(tmp_agents) == {"fable": 2}


def test_uninstall_purge_removes_state_dir(gw: ModuleType, tmp_path: Path) -> None:
    base = tmp_path / "gw"
    _install(gw, base)
    # REQ-004: --settings-path is MANDATORY here. Without it `_cmd_uninstall`
    # resolves the DEFAULT real ~/.claude/settings.json and `remove_claude_env`
    # strips the gateway env block from the developer's own machine on every
    # suite run (the root cause of both 2026-07-18/19 drift incidents). The
    # autouse `_sandbox_default_settings_path` fixture is the backstop; naming
    # the path explicitly is the primary guard.
    assert gw.main(["uninstall", "--base-dir", str(base), "--purge",
                    "--settings-path", str(tmp_path / "settings.json"),
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
    assert f"model: {gw.SPAWN_ALIAS_MODEL_ID}" in (tmp_agents / "backend.md").read_text(encoding="utf-8")


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
    """Stub the TTY + key prompt seams; provider choice defaults to OpenAI."""
    rec = _PromptRecorder(answers)
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)
    monkeypatch.setattr(gw, "_default_provider_prompt_fn", lambda message: "")
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


def test_interactive_zai_prompts_zai_then_anthropic(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "gw"
    rec = _PromptRecorder([RAW_ZAI_KEY, RAW_ANTHROPIC_KEY])
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_provider_prompt_fn", lambda message: "zai")
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)
    assert _install(gw, base, "--interactive-prompts") == 0
    assert "ZAI_API_KEY" in rec.messages[0]
    assert "ANTHROPIC_API_KEY" in rec.messages[1]
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)["ZAI_API_KEY"] == RAW_ZAI_KEY


def test_zai_decline_suppresses_provider_key_prompt(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "gw"
    gw.main(["decline", "zai", "--base-dir", str(base)])
    rec = _PromptRecorder([RAW_ANTHROPIC_KEY])
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_provider_prompt_fn", lambda message: "zai")
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)
    assert _install(gw, base, "--secondary", "zai", "--interactive-prompts") == 0
    assert len(rec.messages) == 1 and "ANTHROPIC_API_KEY" in rec.messages[0]
    assert _declines_on_disk(gw, base)["zai"]["via"] == "wrapper"


def test_zai_blank_prompt_skips_and_records_zai_decline(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """REQ-003 parity (i): blank at the hidden ZAI_API_KEY prompt skips — the
    absent-key path runs verbatim and the decline records under the 'zai' slot
    with via=prompt-skip, exactly like the OpenAI slot."""
    base = tmp_path / "gw"
    rec = _PromptRecorder(["", ""])
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)
    assert _install(gw, base, "--secondary", "zai", "--interactive-prompts") == 0
    assert len(rec.messages) == 2
    assert "ZAI_API_KEY" in rec.messages[0]
    assert "ANTHROPIC_API_KEY" in rec.messages[1]
    out = capsys.readouterr().out
    assert "provisioned but NOT enabled" in out  # the honest absent-key outcome
    declines = _declines_on_disk(gw, base)
    assert set(declines) == {"zai", "anthropic"}
    assert declines["zai"]["via"] == "prompt-skip"


@pytest.mark.parametrize("path_kind", ["arg", "env", "file"])
def test_zai_decline_auto_resets_when_key_resolves(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_kind: str
) -> None:
    """REQ-003 parity (ii): a recorded zai decline auto-resets whenever the
    ZAI key resolves on ANY resolution path (args > env > gateway.env)."""
    base = tmp_path / "gw"
    if path_kind == "file":
        _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY)
    gw.main(["decline", "zai", "--base-dir", str(base)])
    assert "zai" in _declines_on_disk(gw, base)
    if path_kind == "arg":
        _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY)
    elif path_kind == "env":
        monkeypatch.setenv("ZAI_API_KEY", RAW_ZAI_KEY)
        _install(gw, base, "--secondary", "zai")
    else:
        _install(gw, base)  # provider recorded in state; key from gateway.env
    assert "zai" not in _declines_on_disk(gw, base)


def test_re_ask_keys_clears_zai_decline_and_reprompts(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-003 parity (iii): --re-ask-keys clears a recorded zai decline so the
    ZAI_API_KEY prompt fires again."""
    base = tmp_path / "gw"
    gw.main(["decline", "zai", "--base-dir", str(base)])
    rec = _PromptRecorder([RAW_ZAI_KEY, ""])
    monkeypatch.setattr(gw, "_default_isatty_fn", lambda: True)
    monkeypatch.setattr(gw, "_default_prompt_fn", rec)
    assert _install(gw, base, "--secondary", "zai", "--interactive-prompts",
                    "--re-ask-keys") == 0
    assert len(rec.messages) == 2, "--re-ask-keys must make the declined zai slot prompt again"
    assert "ZAI_API_KEY" in rec.messages[0]
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)["ZAI_API_KEY"] == RAW_ZAI_KEY
    assert "zai" not in _declines_on_disk(gw, base)


def test_zai_missing_key_messages_name_zai_env_never_openai(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """REQ-003 parity (iv): on a zai install every missing-key message names
    ZAI_API_KEY — the registry's key_env — never a hard-coded OpenAI key. The
    api-key-mode no-secondary-key install exercises BOTH remaining sites: the
    registration-deferred line and the cannot-activate line."""
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--secondary", "zai", "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents)) == 0
    out = capsys.readouterr().out
    assert "set ZAI_API_KEY (env) or re-run with --zai-key" in out
    reg_line = next(l for l in out.splitlines() if "registration deferred" in l)
    act_line = next(l for l in out.splitlines() if "cannot activate" in l)
    assert "ZAI_API_KEY" in reg_line
    assert "ZAI_API_KEY" in act_line
    assert "OpenAI" not in out and "OPENAI_API_KEY" not in out


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
    monkeypatch.setattr(gw, "_default_provider_prompt_fn", lambda message: "")
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


# ---- v3.39.0: runtime split targeting + live split confirmation ----------------
#
# The split must land where the RUNTIME reads agents (the installed plugin
# cache copy, via Claude Code's installed_plugins.json), and a completed
# install must CONFIRM the live gateway actually serves the split's ids —
# the step the v3.38.1 field bug (a broken config passing every install
# step) proved necessary.


def _fake_installed_plugin(tmp_path: Path) -> tuple[Path, Path]:
    """A fake installed plugin cache copy + a registry pointing at it."""
    install = (tmp_path / "plugins" / "cache" / "architect-team-marketplace"
               / "architect-team" / "9.9.9")
    agents = install / "agents"
    agents.mkdir(parents=True)
    for stem in ("backend", "system-architect"):
        (agents / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: fable\n---\n\nbody\n", encoding="utf-8")
    registry = tmp_path / "installed_plugins.json"
    registry.write_text(json.dumps({"version": 2, "plugins": {
        "architect-team@architect-team-marketplace": [
            {"scope": "user", "installPath": str(install)}]}}), encoding="utf-8")
    return agents, registry


def test_activation_targets_installed_plugin_copy(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With NO --agents-dir, the split lands on the INSTALLED plugin copy —
    the agents Claude Code actually runs — never the dev checkout (whose
    committed ship state is uniform fable and would revert it)."""
    installed_agents, registry = _fake_installed_plugin(tmp_path)
    monkeypatch.setenv(gw._lever.PLUGIN_REGISTRY_ENV, str(registry))
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
    ) == 0
    assert f"model: {gw.SPAWN_ALIAS_MODEL_ID}" in (
        installed_agents / "backend.md").read_text(encoding="utf-8")
    assert "model: fable" in (
        installed_agents / "system-architect.md").read_text(encoding="utf-8")
    # the repo's own agents/ must be untouched by the gateway split (its committed
    # ship state — backend is a delivery agent, model: opus under the v3.43.0
    # delivery-adversarial split; the gateway's SECONDARY split never rewrites the
    # dev checkout, only the installed copy)
    repo_backend = Path(gw._REPO_ROOT) / "agents" / "backend.md"
    assert "model: opus" in repo_backend.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert str(installed_agents) in out  # the split step NAMES its target


def test_install_confirms_live_split(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A registered api-key install ends in the live confirmation: the gateway
    serves codex + fable => split_confirmed True + the plain confirmation."""
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED: CT6 runs the split" in out
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["model_policy"] == "secondary-split"


def test_confirm_failure_restarts_once_then_warns(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    monkeypatch: pytest.MonkeyPatch, _stub_registration: "_RecordingRunner",
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A gateway serving only the OLD config (missing fable) gets ONE repair
    attempt; still missing => an honest fail step, exit stays 0 (never
    gates). Iteration 6 (SR-glm-fix-iter6): the repair is VERIFY-THEN-SWAP —
    the attempt evidence is the STAGING launch, and because staging cannot be
    verified here (the hermetic /model/info seam is unreachable) the serving
    instance is never stopped (never-dark: no tracked stop at all)."""
    monkeypatch.setattr(gw, "_default_models_prober",
                        lambda port, key, timeout=5.0: [gw.SECONDARY_ALIAS])
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert "NOT serving claude-fable-5" in out
    assert "status --live" in out  # the remediation
    # the repair attempt is the staging launch (verify-then-swap) …
    assert _staging_attempts(_stub_registration.calls), \
        "confirm failure must attempt the never-dark repair (staging launch)"
    # … and a failed staging means the serving instance was never touched
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert not ends, "NEVER-DARK: no live stop may fire when staging failed"
    assert "NEVER-DARK" in out and "Staging failure" in out
    assert not [c for c in _stub_registration.calls if c and c[0] == "sudo"]


def test_confirm_recovers_after_restart(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """A stale process serving the pre-regeneration config is healed by the
    restart: probes fail before it, succeed after => confirmed ok."""
    restarted = {"done": False}

    def prober(port, key, timeout=5.0):
        if restarted["done"]:
            return [gw.SECONDARY_ALIAS, gw.SPAWN_ALIAS_MODEL_ID, gw.FABLE_MODEL]
        return [gw.SECONDARY_ALIAS]

    real_restart = gw.restart_gateway

    def fake_restart(platform_key, launcher, name=gw.SERVICE_NAME, runner=None,
                     **verification_context):
        # Iteration 4: the install call sites now pass the verification
        # context (port/master_key/generated_config). This pin is about the
        # REPAIR-CYCLE re-probe, not the restart mechanics, so the fake drops
        # the context and runs the legacy tracked restart — the verified
        # restart's own contracts are pinned in the iteration-4 section.
        restarted["done"] = True
        return real_restart(platform_key, launcher, name, runner)

    monkeypatch.setattr(gw, "_default_models_prober", prober)
    monkeypatch.setattr(gw, "restart_gateway", fake_restart)
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED: CT6 runs the split" in out
    assert "after restart" in out


def test_confirm_unreachable_names_the_url(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def prober(port, key, timeout=5.0):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(gw, "_default_models_prober", prober)
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert "unreachable" in out
    assert gw.gateway_url(gw.DEFAULT_PORT) in out


def test_subscription_mode_confirm_expects_codex_only(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Subscription mode serves the secondary only — the confirm step must NOT
    demand fable from the gateway (fable rides Claude Code's sign-in auth).
    The spawn alias IS demanded: the subscription config routes it too."""
    monkeypatch.setattr(
        gw, "_default_models_prober",
        lambda port, key, timeout=5.0: [gw.SECONDARY_ALIAS,
                                        gw.SPAWN_ALIAS_MODEL_ID])
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY,
        "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED" in out
    assert "NOT serving" not in out


def test_check_only_never_probes(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probes = {"n": 0}

    def prober(port, key, timeout=5.0):
        probes["n"] += 1
        return []

    monkeypatch.setattr(gw, "_default_models_prober", prober)
    assert _install(gw, tmp_path / "gw", "--openai-key", RAW_OPENAI_KEY,
                    "--check-only") == 0
    assert probes["n"] == 0


def test_no_register_skips_confirm_with_hint(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--no-register means the installer never started the gateway — the
    confirm step skips (no probe, no schtasks) and points at status --live."""
    probes = {"n": 0}

    def prober(port, key, timeout=5.0):
        probes["n"] += 1
        return []

    monkeypatch.setattr(gw, "_default_models_prober", prober)
    assert _install(gw, tmp_path / "gw", "--openai-key", RAW_OPENAI_KEY,
                    "--no-register") == 0
    assert probes["n"] == 0
    assert "status --live" in capsys.readouterr().out


def test_status_live_probes_and_confirms(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = tmp_path / "gw"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key",
             RAW_ANTHROPIC_KEY, "--activate",
             "--settings-path", str(tmp_path / "settings.json"),
             "--agents-dir", str(tmp_agents))
    capsys.readouterr()
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED: CT6 runs the split" in out


def test_status_live_expects_the_state_recorded_alias_for_legacy_installs(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADV3-3: a WORKING legacy (v3.39) install — whose config routes only
    codex-5.6-sol — must probe GREEN: the --live expectation is the
    STATE-RECORDED alias (secondary_alias, falling back to the legacy
    codex_alias), never a hard-coded newest alias."""
    base = tmp_path / "gw"
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        "OPENAI_API_KEY": RAW_OPENAI_KEY,
        "ANTHROPIC_API_KEY": RAW_ANTHROPIC_KEY,
        gw.MASTER_KEY_VAR: "sk-ct6-legacy-master"})
    (base / gw.CONFIG_NAME).write_text("# legacy v3.39 config\n", encoding="utf-8")
    gw._write_state(base, {
        "auth_mode": gw.AUTH_MODE_API_KEY, "port": gw.DEFAULT_PORT,
        "activated": True, "enabled": True, "registered": True,
        "openai_model": "gpt-5.6-sol", "codex_alias": "codex-5.6-sol",
        "model_policy": "codex-split"})
    monkeypatch.setattr(
        gw, "_default_models_prober",
        lambda port, key, timeout=5.0: ["codex-5.6-sol", gw.FABLE_MODEL])
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_path / "agents-absent")]) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED" in out
    assert "NOT serving" not in out


def test_status_without_live_never_probes(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probes = {"n": 0}

    def prober(port, key, timeout=5.0):
        probes["n"] += 1
        return []

    monkeypatch.setattr(gw, "_default_models_prober", prober)
    base = tmp_path / "gw"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY, "--no-register")
    probes["n"] = 0
    assert gw.main(["status", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert probes["n"] == 0


def test_restart_gateway_per_os_never_sudo(gw: ModuleType, tmp_path: Path) -> None:
    launcher = tmp_path / "run_gateway.sh"
    for platform_key, expected in (
        ("windows", ["schtasks", "/run"]),
        ("linux", ["systemctl", "--user", "restart"]),
        ("darwin", ["launchctl", "kickstart"]),
    ):
        runner = _RecordingRunner()
        ok, detail = gw.restart_gateway(platform_key, launcher, runner=runner)
        assert ok, f"{platform_key}: {detail}"
        flat = list(runner.calls)
        assert any(c[: len(expected)] == expected for c in flat), \
            f"{platform_key} missing {expected}: {flat}"
        assert not [c for c in flat if c and c[0] == "sudo"]


def test_uninstall_records_deactivated_state(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    """Uninstall must flip the recorded state (activated False + uniform-fable)
    so the SessionStart self-heal never re-applies an uninstalled split — and
    it is the ONLY sanctioned downgrade path (ADV3B-1): the non-activate
    carry-forward must never resurrect the uninstalled state either."""
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key",
             RAW_ANTHROPIC_KEY, "--activate", "--settings-path", str(settings),
             "--agents-dir", str(tmp_agents))
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["model_policy"] == "secondary-split"
    assert gw.main(["uninstall", "--base-dir", str(base), "--settings-path",
                    str(settings), "--agents-dir", str(tmp_agents)]) == 0
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is False
    assert state["model_policy"] == "uniform-fable"
    # a later plain install carries the DOWNGRADED state forward verbatim —
    # neither resurrecting the split nor touching the restored agents
    assert _install(gw, base, "--settings-path", str(settings),
                    "--agents-dir", str(tmp_agents)) == 0
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is False
    assert state["model_policy"] == "uniform-fable"
    for stem in ("backend", "system-architect"):
        assert "model: fable" in (
            tmp_agents / f"{stem}.md").read_text(encoding="utf-8")


# ---- ADV3B — non-activate reinstall consistency (v3.40.0) ---------------------
#
# ADV3B-1 (MAJOR): a plain (non---activate) install regenerates config.yaml to
# route ONLY the neutral alias. On a legacy-activated (v3.39) machine that used
# to BREAK the working split: agents kept codex-5.6-sol (migration was
# --activate-gated) while the regenerated config stopped routing it, and the
# state write downgraded activated/model_policy — disarming the SessionStart
# self-heal and making status --live false-confirm. The sanctioned fix:
# serving-side consistency (any on-disk legacy split migrates to the neutral
# alias in the SAME run that regenerates the config, --activate or not) +
# state carry-forward (a non-activate install preserves the prior
# activated/model_policy; uninstall is the ONLY downgrade path — which also
# closes ADV3B-5, the modern-machine heal-disarm).


def _legacy_activated_machine(
    gw: ModuleType, base: Path, agents: Path, settings: Path
) -> None:
    """A WORKING v3.39 machine: legacy-alias split on disk, api-key keys in
    gateway.env, a config routing only codex-5.6-sol, settings.json activated,
    and a v3.39-shape state (codex_alias only, codex-split, activated)."""
    legacy_alias = gw._lever.LEGACY_SECONDARY_ALIASES[0]
    gw._lever.apply_split(agents, legacy_alias)
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        "OPENAI_API_KEY": RAW_OPENAI_KEY,
        "ANTHROPIC_API_KEY": RAW_ANTHROPIC_KEY,
        gw.MASTER_KEY_VAR: "sk-ct6-legacy-master"})
    (base / gw.CONFIG_NAME).write_text(
        f"model_list:\n  - model_name: {legacy_alias}\n", encoding="utf-8")
    gw.apply_claude_env(settings, gw.DEFAULT_PORT, "sk-ct6-legacy-master")
    gw._write_state(base, {
        "auth_mode": gw.AUTH_MODE_API_KEY, "port": gw.DEFAULT_PORT,
        "activated": True, "enabled": True, "registered": True,
        "openai_model": "gpt-5.6-sol", "codex_alias": legacy_alias,
        "model_policy": "codex-split"})


def test_non_activate_reinstall_migrates_legacy_split_and_preserves_activation(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADV3B-1: plain `install` (no --activate) over a legacy-activated machine
    must NOT break the working split — the on-disk legacy split migrates to
    the alias the just-regenerated config routes (serving-side consistency),
    the state carries activated + the split policy forward (no silent
    deactivation), and status --live stays truthful."""
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    _legacy_activated_machine(gw, base, tmp_agents, settings)
    assert _install(gw, base, "--settings-path", str(settings),
                    "--agents-dir", str(tmp_agents)) == 0
    # agents migrated to the SPAWN alias — the id the just-written config
    # routes AND the harness spawn gate accepts (v3.41.0)
    assert f"model: {gw.SPAWN_ALIAS_MODEL_ID}" in (
        tmp_agents / "backend.md").read_text(encoding="utf-8")
    assert "model: fable" in (
        tmp_agents / "system-architect.md").read_text(encoding="utf-8")
    assert f"model_name: {gw.SECONDARY_ALIAS}" in (
        base / gw.CONFIG_NAME).read_text(encoding="utf-8")
    assert "migrated" in capsys.readouterr().out  # the run SAYS it moved the alias
    # state honesty: activated + split policy carried forward, aliases recorded
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is True, \
        "a non-activate install must never silently deactivate"
    assert state["model_policy"] == "secondary-split"
    assert state["secondary_alias"] == gw.SECONDARY_ALIAS
    assert state["spawn_alias"] == gw.SPAWN_ALIAS_MODEL_ID
    # status --live is TRUTHFUL: the probed spawn alias IS what the agents carry
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(settings),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert "CONFIRMED: CT6 runs the split" in capsys.readouterr().out
    assert f"model: {state['spawn_alias']}" in (
        tmp_agents / "backend.md").read_text(encoding="utf-8")


def test_non_activate_reinstall_keeps_the_self_heal_armed(
    gw: ModuleType, tmp_path: Path
) -> None:
    """ADV3B-1/ADV3B-5: after a plain re-install the recorded state must still
    ARM the SessionStart self-heal — an immediate heal is a silent no-op
    (agents already consistent), and after a plugin update reverts the
    installed copy to uniform fable the heal FIRES and restores the split."""
    import shutil

    from tests.helpers.module_loader import load_module
    hook = load_module(
        Path(gw._REPO_ROOT) / "hooks" / "sessionstart-run-continuity.py",
        "sessionstart_hook_for_gateway_tests")
    # a fake INSTALLED plugin copy carrying the real lever
    plugins_base = tmp_path / "plugins"
    root = plugins_base / "cache" / "mp" / "architect-team" / "9.9.9"
    agents = root / "agents"
    agents.mkdir(parents=True)
    for stem in ("backend", "system-architect"):
        (agents / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: fable\n---\n\nbody\n", encoding="utf-8")
    (root / "scripts" / "setup").mkdir(parents=True)
    shutil.copy(Path(gw._REPO_ROOT) / "scripts" / "setup" / "set_default_model.py",
                root / "scripts" / "setup" / "set_default_model.py")
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    _legacy_activated_machine(gw, base, agents, settings)
    assert _install(gw, base, "--settings-path", str(settings),
                    "--agents-dir", str(agents)) == 0
    # immediately after: armed but a silent no-op (agents already consistent)
    assert hook.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=base / gw.STATE_NAME) == ""
    # a plugin update reverts the installed copy to uniform fable...
    for stem in ("backend", "system-architect"):
        (agents / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: fable\n---\n\nbody\n", encoding="utf-8")
    note = hook.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=base / gw.STATE_NAME)
    assert "self-heal" in note, \
        "a non-activate re-install must not disarm the heal on an activated machine"
    # the heal targets the state-recorded SPAWN alias (v3.41.0)
    assert f"model: {gw.SPAWN_ALIAS_MODEL_ID}" in (
        agents / "backend.md").read_text(encoding="utf-8")


def test_non_activate_reinstall_carries_modern_state_forward(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    """ADV3B-5: a plain re-install of an ACTIVATED modern (v3.40) machine
    carries activated/model_policy forward untouched — no downgrade — and
    never touches the already-neutral agents."""
    base = tmp_path / "gw"
    settings = tmp_path / "settings.json"
    _install(gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key",
             RAW_ANTHROPIC_KEY, "--activate", "--settings-path", str(settings),
             "--agents-dir", str(tmp_agents))
    before = {stem: (tmp_agents / f"{stem}.md").read_text(encoding="utf-8")
              for stem in ("backend", "system-architect")}
    assert _install(gw, base, "--settings-path", str(settings),
                    "--agents-dir", str(tmp_agents)) == 0
    for stem, text in before.items():
        assert (tmp_agents / f"{stem}.md").read_text(encoding="utf-8") == text, \
            f"{stem}: a plain re-install must not touch already-neutral agents"
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is True
    assert state["model_policy"] == "secondary-split"
    assert state["secondary_alias"] == gw.SECONDARY_ALIAS


def test_fresh_plain_install_remains_split_neutral(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    """The carry-forward must not invent state: a fresh plain install (no
    prior gateway.json) keeps the baseline posture — agents untouched,
    activated False, uniform-fable."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key",
                    RAW_ANTHROPIC_KEY,
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)) == 0
    for stem in ("backend", "system-architect"):
        assert "model: fable" in (
            tmp_agents / f"{stem}.md").read_text(encoding="utf-8")
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is False
    assert state["model_policy"] == "uniform-fable"


def test_plain_install_missing_agents_dir_reports_skipped_migration(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """ADV3C-4: a missing/typo'd --agents-dir on a PLAIN (non---activate)
    install must surface a skipped row — the --activate path already prints
    one for the same condition (its secondary-split row); the plain path must
    not skip the step-3b legacy-alias migration silently."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--openai-key", RAW_OPENAI_KEY,
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_path / "agents-absent")) == 0
    out = capsys.readouterr().out
    assert "alias-migration" in out
    assert "agents dir not found" in out
    assert "--split secondary" in out  # the row carries the manual remediation


def test_status_live_treats_a_whitespace_alias_as_absent(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADV3B-2: a corrupt whitespace-only secondary_alias must neither mask
    the valid legacy codex_alias nor be probed as a literal — the recorded
    values are trimmed BEFORE the truthiness check."""
    base = tmp_path / "gw"
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        "OPENAI_API_KEY": RAW_OPENAI_KEY,
        "ANTHROPIC_API_KEY": RAW_ANTHROPIC_KEY,
        gw.MASTER_KEY_VAR: "sk-ct6-legacy-master"})
    (base / gw.CONFIG_NAME).write_text("# legacy v3.39 config\n", encoding="utf-8")
    gw._write_state(base, {
        "auth_mode": gw.AUTH_MODE_API_KEY, "port": gw.DEFAULT_PORT,
        "activated": True, "enabled": True, "registered": True,
        "secondary_alias": "   ", "codex_alias": "codex-5.6-sol",
        "model_policy": "codex-split"})
    monkeypatch.setattr(
        gw, "_default_models_prober",
        lambda port, key, timeout=5.0: ["codex-5.6-sol", gw.FABLE_MODEL])
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_path / "agents-absent")]) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED" in out
    assert "NOT serving" not in out


def test_setup_entry_reports_live_confirmation(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path
) -> None:
    """The one-call promise: setup --external-llm --yes ends in a summary that
    SAYS the split is confirmed live — no surprise follow-up steps."""
    base = tmp_path / "gw"
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        "OPENAI_API_KEY": RAW_OPENAI_KEY,
        "ANTHROPIC_API_KEY": RAW_ANTHROPIC_KEY})
    with patch.object(gw, "litellm_installed", return_value=True):
        name, status, detail = gw.setup_entry(
            enable=True, check_only=False, assume_yes=True,
            base_dir=str(base),
            settings_path=str(tmp_path / "settings.json"),
            agents_dir=str(tmp_agents))
    assert status == "applied"
    assert "secondary split applied" in (detail or "")
    assert "CONFIRMED live" in (detail or "")
    assert "CT6 runs the split" in (detail or "")


# ---- v3.41.0 (glm-secondary-route-fix): spawn alias + completion probe ----------
#
# BUG-A: the registry hard-coded the openai/ dialect, which 404s on providers
# without the OpenAI Responses API (api.z.ai). BUG-B: the Agent-Teams spawn
# path rejects custom model ids client-side, so the split's frontmatter value
# must be a REAL Claude id the gateway impersonates (disclosed). Wrong-hop:
# confirm probed /v1/models only, so "CONFIRMED live" shipped over a broken
# /v1/messages hop. tests/bug-fix-glm-secondary-route-fix/test_replication.py
# is the frozen regression contract; these pin the surrounding behavior.


def test_spawn_alias_is_single_sourced_and_a_real_claude_id(gw: ModuleType) -> None:
    """The impersonation id is pinned (changing it is a deliberate act), is
    single-sourced from the lever (the split writes the same id the gateway
    routes), and is a REAL Claude id the harness accepts at spawn."""
    assert gw.SPAWN_ALIAS_MODEL_ID == "claude-haiku-4-5"
    assert gw.SPAWN_ALIAS_MODEL_ID == gw._lever.SPAWN_ALIAS_MODEL_ID
    assert gw.SPAWN_ALIAS_MODEL_ID in gw.ANTHROPIC_EXPLICIT_MODELS, \
        "the spawn alias must be a known-real Claude model id"


def test_confirm_completion_failure_blocks_the_confirmed_claim(
    gw: ModuleType,
) -> None:
    """The wrong-hop fix: a gateway that LISTS the expected models but cannot
    complete a /v1/messages call must NOT confirm — the detail names the
    failed completion hop and every alias tried."""
    def completion_boom(port, key, model, timeout=30.0, expected_upstream=None):
        raise ConnectionError("404 /v4/responses")

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID, gw.SECONDARY_ALIAS],
        completion_prober=completion_boom)
    assert ok is False
    assert "/v1/messages" in detail and "FAILED" in detail
    assert gw.SPAWN_ALIAS_MODEL_ID in detail and gw.SECONDARY_ALIAS in detail


def test_confirm_completion_falls_back_to_the_neutral_alias(
    gw: ModuleType,
) -> None:
    """The LEGACY call shape (no mandatory candidate declared): a spawn-alias
    completion failing falls back to ct6-secondary; the success detail names
    the alias that actually completed + the honest spawn-hop boundary.
    Iteration 3 (SR-glm-fix-iter3): install and spawn-recorded status --live
    no longer use this shape — they declare the spawn alias MANDATORY, so
    fallback green survives only for pre-spawn-alias legacy states."""
    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        if model == gw.SPAWN_ALIAS_MODEL_ID:
            raise ConnectionError("boom")
        return "pong"

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID, gw.SECONDARY_ALIAS],
        completion_prober=completion)
    assert ok is True
    assert f"completion CONFIRMED via {gw.SECONDARY_ALIAS}" in detail
    assert "fresh session" in detail  # the two-hop honesty note


def test_confirm_without_completion_models_keeps_listing_semantics(
    gw: ModuleType,
) -> None:
    """No completion candidates (legacy call shape) => the /v1/models-only
    behavior is unchanged and no completion probe fires."""
    def completion_boom(port, key, model, timeout=30.0, expected_upstream=None):  # pragma: no cover
        raise AssertionError("completion probe must not fire")

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_prober=completion_boom)
    assert ok is True and "completion" not in detail


def test_install_confirm_reports_the_completion_hop(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end: a registered api-key install's CONFIRMED row carries the
    /v1/messages completion evidence (via the spawn alias, per the autouse
    stub) — not just the model listing."""
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED: CT6 runs the split" in out
    assert "/v1/messages" in out
    assert f"completion CONFIRMED via {gw.SPAWN_ALIAS_MODEL_ID}" in out


def test_install_completion_failure_restarts_once_then_fails_honestly(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    monkeypatch: pytest.MonkeyPatch, _stub_registration: "_RecordingRunner",
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A gateway listing every id but failing the completion hop gets the
    same ONE repair cycle, then an honest fail row (exit stays 0).
    Iteration 6 (SR-glm-fix-iter6): the repair is verify-then-swap — the
    attempt evidence is the staging launch, and the completion failure hits
    the STAGING ladder too (same seam), so the serving instance is never
    stopped (never-dark)."""
    def completion_boom(port, key, model, timeout=30.0, expected_upstream=None):
        raise ConnectionError("simulated 404")

    monkeypatch.setattr(gw, "_default_completion_prober", completion_boom)
    base = tmp_path / "gw"
    assert _install(
        gw, base, "--openai-key", RAW_OPENAI_KEY, "--anthropic-key", RAW_ANTHROPIC_KEY,
        "--activate", "--settings-path", str(tmp_path / "settings.json"),
        "--agents-dir", str(tmp_agents),
    ) == 0
    out = capsys.readouterr().out
    assert "completion hop FAILED" in out
    assert "CONFIRMED: CT6 runs the split" not in out
    assert _staging_attempts(_stub_registration.calls), \
        "a completion failure must attempt the never-dark repair (staging)"
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert not ends, "NEVER-DARK: no live stop may fire when staging failed"


def test_install_records_spawn_alias_and_status_discloses_it(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Disclosure: gateway.json records spawn_alias + spawn_alias_maps_to, and
    status prints the impersonation mapping plainly."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["spawn_alias"] == gw.SPAWN_ALIAS_MODEL_ID
    assert state["spawn_alias_maps_to"] == "glm-5.2"
    capsys.readouterr()
    assert gw.main(["status", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert f"{gw.SPAWN_ALIAS_MODEL_ID} -> glm-5.2 (impersonated secondary)" in out


def test_pre_spawn_alias_state_gets_no_disclosure_row(
    gw: ModuleType, tmp_path: Path, tmp_agents: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A legacy state without spawn_alias prints no impersonation row — the
    disclosure never claims a mapping the recorded config does not route."""
    base = tmp_path / "gw"
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        "OPENAI_API_KEY": RAW_OPENAI_KEY, gw.MASTER_KEY_VAR: "sk-ct6-m"})
    (base / gw.CONFIG_NAME).write_text("# legacy config\n", encoding="utf-8")
    gw._write_state(base, {
        "auth_mode": gw.AUTH_MODE_API_KEY, "port": gw.DEFAULT_PORT,
        "codex_alias": "codex-5.6-sol", "model_policy": "codex-split"})
    assert gw.main(["status", "--base-dir", str(base),
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_agents)]) == 0
    assert "impersonated secondary" not in capsys.readouterr().out


def test_status_live_completion_uses_only_state_recorded_aliases(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status --live on a legacy (pre-spawn-alias) state probes ONLY the
    recorded alias — the completion candidates never include the modern spawn
    alias its config does not route."""
    probed: list[str] = []

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        return "pong"

    base = tmp_path / "gw"
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        "OPENAI_API_KEY": RAW_OPENAI_KEY,
        "ANTHROPIC_API_KEY": RAW_ANTHROPIC_KEY,
        gw.MASTER_KEY_VAR: "sk-ct6-legacy-master"})
    (base / gw.CONFIG_NAME).write_text("# legacy v3.39 config\n", encoding="utf-8")
    gw._write_state(base, {
        "auth_mode": gw.AUTH_MODE_API_KEY, "port": gw.DEFAULT_PORT,
        "activated": True, "enabled": True, "registered": True,
        "openai_model": "gpt-5.6-sol", "codex_alias": "codex-5.6-sol",
        "model_policy": "codex-split"})
    monkeypatch.setattr(
        gw, "_default_models_prober",
        lambda port, key, timeout=5.0: ["codex-5.6-sol", gw.FABLE_MODEL])
    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_path / "agents-absent")]) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED" in out
    assert probed == ["codex-5.6-sol"]
    assert gw.SPAWN_ALIAS_MODEL_ID not in probed


def test_check_only_and_no_register_never_run_the_completion_probe(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--check-only / --no-register never probe — unchanged for the new
    completion hop (the pinned no-probe posture extends to /v1/messages)."""
    probes = {"n": 0}

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        probes["n"] += 1
        return "pong"

    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    assert _install(gw, tmp_path / "gw1", "--openai-key", RAW_OPENAI_KEY,
                    "--check-only") == 0
    assert _install(gw, tmp_path / "gw2", "--openai-key", RAW_OPENAI_KEY,
                    "--no-register") == 0
    assert probes["n"] == 0


# ---- v3.41.0 iteration 2 (SR-glm-fix-iter2): restart-on-regeneration + the
# upstream-verifying completion probe --------------------------------------------
#
# The first deploy exposed two further wrong-hop class members (live-verified
# at B6): (1) register/start is start-if-not-running, so a RUNNING pre-deploy
# process kept serving the prior config after config.yaml regeneration (stale
# marker claude-ct6-secondary in /model/info); (2) the /v1/messages completion
# probe was upstream-blind — the anthropic/* wildcard dynamically instantiated
# a real-Haiku deployment for the spawn alias and the probe accepted it (6/6
# probes, real-Haiku response cost) while setup reported the split live.


def _deployments(gw: ModuleType) -> list[dict]:
    """A /model/info data shape mirroring the B6 incident: the secondary's
    deployment plus the wildcard's dynamically-instantiated real-Haiku one."""
    return [
        {"model_name": gw.SPAWN_ALIAS_MODEL_ID,
         "litellm_params": {"model": "hosted_vllm/glm-5.2"},
         "model_info": {"id": "dep-glm"}},
        {"model_name": gw.SPAWN_ALIAS_MODEL_ID,
         "litellm_params": {"model": "anthropic/claude-haiku-4-5"},
         "model_info": {"id": "883c743106d3"}},
    ]


class _FakeResponse:
    """Minimal urlopen context-manager stand-in (headers + JSON body)."""

    def __init__(self, payload: dict, headers: dict | None = None) -> None:
        self._payload = json.dumps(payload).encode("utf-8")
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def test_install_restarts_a_running_gateway_when_config_content_changes(
    gw: ModuleType, tmp_path: Path, _stub_registration: "_RecordingRunner",
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """A config-REgenerating install (prior config.yaml content differs from
    the regenerated one) restarts the gateway BEFORE confirming — register's
    start-if-not-running left the B6 stale process serving the prior config.
    Iteration 4: the restart is bind-VERIFIED, so the healthy post-restart
    gateway is simulated by a /model/info fake serving the regenerated
    config."""
    base = tmp_path / "gw"
    base.mkdir()
    (base / gw.CONFIG_NAME).write_text(
        "# stale pre-deploy hand-edit\n", encoding="utf-8")
    monkeypatch.setattr(gw, "_default_model_info_prober",
                        _model_info_matching_config(gw, base, "openai"))
    assert _install(gw, base, "--openai-key", RAW_OPENAI_KEY) == 0
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert ends, "a config-regenerating install must restart the running gateway"
    out = capsys.readouterr().out
    assert "content changed" in out and "restarted" in out
    assert "bind VERIFIED" in out


def test_install_fresh_or_identical_config_never_restarts(
    gw: ModuleType, tmp_path: Path, _stub_registration: "_RecordingRunner",
) -> None:
    """No restart churn where none is needed: a FRESH install (no prior
    config; register's own start covers it) and a byte-identical re-install
    (healthy process already serves exactly this config) never stop/restart.
    Iteration 3 nuance: this test's /model/info seam is UNREACHABLE (the
    autouse default) — cannot-judge never proactively restarts; a REACHABLE
    stale served state on a byte-identical re-install now does (the
    escape-replay test below), and a reachable MATCHING one still does not
    (test_install_matching_served_state_never_restarts)."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--openai-key", RAW_OPENAI_KEY) == 0
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert not ends, "a fresh install must not restart (nothing stale can run)"
    _stub_registration.calls.clear()
    assert _install(gw, base, "--openai-key", RAW_OPENAI_KEY) == 0
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert not ends, "an idempotent re-install must not churn a healthy process"


def test_install_restart_triggers_on_any_content_change_not_group_set(
    gw: ModuleType, tmp_path: Path, _stub_registration: "_RecordingRunner",
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """The auditor pin: the restart trigger is a BYTE-level config diff, not a
    model-group set comparison — a prior config with the SAME model_name set
    but a different api_base still restarts (set-shape detection would miss
    exactly that class of change)."""
    base = tmp_path / "gw"
    monkeypatch.setattr(gw, "_default_model_info_prober",
                        _model_info_matching_config(gw, base, "zai"))
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    prior = (base / gw.CONFIG_NAME).read_text(encoding="utf-8")
    tweaked = prior.replace("api.z.ai/api/paas/v4", "api.z.ai/api/paas/v3")
    assert tweaked != prior, "the api_base tweak must actually change the bytes"
    (base / gw.CONFIG_NAME).write_text(tweaked, encoding="utf-8")
    _stub_registration.calls.clear()
    capsys.readouterr()
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert ends, "an api_base-only change keeps the group set but MUST restart"
    assert "content changed" in capsys.readouterr().out


def test_assert_expected_deployment_passes_on_the_registry_route(
    gw: ModuleType,
) -> None:
    assert gw._assert_expected_deployment(
        "dep-glm", _deployments(gw), "hosted_vllm/glm-5.2"
    ) == "hosted_vllm/glm-5.2"


def test_assert_expected_deployment_mismatch_names_the_observed_upstream(
    gw: ModuleType,
) -> None:
    """The B6 incident shape: the wildcard's real-Haiku deployment answered —
    the failure must name BOTH the observed and the expected upstream."""
    with pytest.raises(ValueError) as exc:
        gw._assert_expected_deployment(
            "883c743106d3", _deployments(gw), "hosted_vllm/glm-5.2")
    msg = str(exc.value)
    assert "served by anthropic/claude-haiku-4-5" in msg
    assert "expected hosted_vllm/glm-5.2" in msg


def test_assert_expected_deployment_unknown_id_fails(gw: ModuleType) -> None:
    """An unresolvable x-litellm-model-id can NOT verify the upstream — that
    is a failure, never a silent pass (fail-closed, unlike the blind probe)."""
    with pytest.raises(ValueError) as exc:
        gw._assert_expected_deployment(
            "no-such-id", _deployments(gw), "hosted_vllm/glm-5.2")
    assert "absent from /model/info" in str(exc.value)


def test_http_completion_probe_fails_naming_the_wildcard_upstream(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The REAL probe (hermetic — urlopen stubbed): x-litellm-model-id is
    captured from the POST response, resolved via GET /model/info, and a
    completion served by the real-Haiku deployment raises with the observed
    upstream named."""
    def fake_urlopen(req, timeout=0):
        if req.full_url.endswith("/v1/messages"):
            return _FakeResponse(
                {"content": [{"type": "text", "text": "ok"}]},
                headers={"x-litellm-model-id": "883c743106d3"})
        assert req.full_url.endswith("/model/info")
        return _FakeResponse({"data": _deployments(gw)})

    monkeypatch.setattr(gw.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError) as exc:
        gw._http_completion_probe(
            4000, "sk-m", gw.SPAWN_ALIAS_MODEL_ID,
            expected_upstream="hosted_vllm/glm-5.2")
    assert "served by anthropic/claude-haiku-4-5" in str(exc.value)


def test_http_completion_probe_passes_on_the_secondary_deployment(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(req, timeout=0):
        if req.full_url.endswith("/v1/messages"):
            return _FakeResponse(
                {"content": [{"type": "text", "text": "ok"}]},
                headers={"x-litellm-model-id": "dep-glm"})
        return _FakeResponse({"data": _deployments(gw)})

    monkeypatch.setattr(gw.urllib.request, "urlopen", fake_urlopen)
    assert gw._http_completion_probe(
        4000, "sk-m", gw.SPAWN_ALIAS_MODEL_ID,
        expected_upstream="hosted_vllm/glm-5.2") == "ok"


def test_http_completion_probe_without_model_id_header_cannot_verify(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response with no x-litellm-model-id header cannot be verified —
    fail-closed when an upstream expectation is in force."""
    monkeypatch.setattr(
        gw.urllib.request, "urlopen",
        lambda req, timeout=0: _FakeResponse(
            {"content": [{"type": "text", "text": "ok"}]}))
    with pytest.raises(ValueError) as exc:
        gw._http_completion_probe(
            4000, "sk-m", gw.SPAWN_ALIAS_MODEL_ID,
            expected_upstream="hosted_vllm/glm-5.2")
    assert "cannot verify" in str(exc.value)


def test_http_completion_probe_no_expectation_skips_model_info(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The legacy call shape (no expected_upstream) keeps the plain
    completion-hop semantics: no /model/info request is made."""
    urls: list[str] = []

    def fake_urlopen(req, timeout=0):
        urls.append(req.full_url)
        return _FakeResponse({"content": [{"type": "text", "text": "ok"}]})

    monkeypatch.setattr(gw.urllib.request, "urlopen", fake_urlopen)
    assert gw._http_completion_probe(4000, "sk-m", "any-model") == "ok"
    assert urls and all(u.endswith("/v1/messages") for u in urls)


def test_confirm_upstream_mismatch_blocks_confirmed_and_names_the_upstream(
    gw: ModuleType,
) -> None:
    """A wildcard-served completion FAILS the confirm — the detail names the
    observed upstream so the operator sees who actually answered."""
    def wildcard_served(port, key, model, timeout=30.0, expected_upstream=None):
        raise ValueError(
            f"served by anthropic/claude-haiku-4-5, expected {expected_upstream}")

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID],
        completion_prober=wildcard_served,
        expected_upstream="hosted_vllm/glm-5.2")
    assert ok is False
    assert "served by anthropic/claude-haiku-4-5" in detail
    assert "hosted_vllm/glm-5.2" in detail


def test_confirm_hands_expected_upstream_to_the_completion_prober(
    gw: ModuleType,
) -> None:
    """The expectation rides the injectable seam (keyless CI stays hermetic),
    and a verified confirm says so in the detail."""
    seen: list[str | None] = []

    def prober(port, key, model, timeout=30.0, expected_upstream=None):
        seen.append(expected_upstream)
        return "ok"

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID],
        completion_prober=prober, expected_upstream="hosted_vllm/glm-5.2")
    assert ok is True and seen == ["hosted_vllm/glm-5.2"]
    assert "upstream deployment verified = hosted_vllm/glm-5.2" in detail


@pytest.mark.parametrize(
    ("provider", "key_flag", "key_value"),
    [("openai", "--openai-key", RAW_OPENAI_KEY),
     ("zai", "--zai-key", RAW_ZAI_KEY)])
def test_install_probes_with_the_registry_derived_upstream(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    provider: str, key_flag: str, key_value: str,
) -> None:
    """Auditor note 3 (no constant): the expected upstream is derived from the
    REGISTRY at probe time — per provider, `<route_dialect>/<model>` — never a
    hard-coded route."""
    seen: list[str | None] = []

    def prober(port, key, model, timeout=30.0, expected_upstream=None):
        seen.append(expected_upstream)
        return "ok"

    monkeypatch.setattr(gw, "_default_completion_prober", prober)
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", provider, key_flag, key_value) == 0
    entry = gw.SECONDARY_PROVIDERS[provider]
    assert seen and seen[0] == f"{entry['route_dialect']}/{entry['model']}"


def test_install_wrong_upstream_completion_triggers_the_restart_repair(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    _stub_registration: "_RecordingRunner", capsys: pytest.CaptureFixture[str],
) -> None:
    """The B6 incident replayed end-to-end: the first confirm's completion is
    wildcard-served (stale process) → the existing ONE-restart repair cycle
    fires → the post-restart re-probe confirms the secondary's deployment.
    Iteration 4: the repair restart is bind-VERIFIED, so the healthy
    post-restart gateway is simulated by a /model/info fake serving the
    generated config. Iteration 6: the repair is verify-then-swap — the
    STAGED instance (running the regenerated config on the staging port)
    completes correctly, which is what sanctions the live cutover; the live
    port keeps answering wildcard-served until the swap."""
    staging_port = gw.DEFAULT_PORT + gw.STAGING_PORT_OFFSET

    def prober(port, key, model, timeout=30.0, expected_upstream=None):
        if port == staging_port:  # the staged replacement serves correctly
            return "ok"
        ends = [c for c in _stub_registration.calls
                if c[:2] == ["schtasks", "/end"]]
        if not ends:  # pre-restart: the stale process's wildcard answers
            raise ValueError(
                f"served by anthropic/claude-haiku-4-5, "
                f"expected {expected_upstream}")
        return "ok"

    monkeypatch.setattr(gw, "_default_completion_prober", prober)
    base = tmp_path / "gw"
    monkeypatch.setattr(gw, "_default_model_info_prober",
                        _model_info_matching_config(gw, base, "zai"))
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED" in out and "after restart" in out
    assert "staging VERIFIED" in out, \
        "the cutover must have been sanctioned by a staging-green ladder"
    ends = [c for c in _stub_registration.calls
            if c[:2] == ["schtasks", "/end"]]
    assert ends, "the wrong-upstream completion must trigger the restart repair"
    assert (_first_index(_stub_registration.calls,
                         _staging_attempts(_stub_registration.calls)[0])
            < _first_index(_stub_registration.calls, ["schtasks", "/end"])), \
        "never-dark ordering: staging launches BEFORE any live stop"


def test_status_live_probes_with_the_registry_derived_upstream(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status --live derives the same registry expectation from the recorded
    provider + model — observation gets the identity check too."""
    seen: list[str | None] = []

    def prober(port, key, model, timeout=30.0, expected_upstream=None):
        seen.append(expected_upstream)
        return "ok"

    monkeypatch.setattr(gw, "_default_completion_prober", prober)
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    seen.clear()
    capsys.readouterr()
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_path / "agents-absent")]) == 0
    entry = gw.SECONDARY_PROVIDERS["zai"]
    assert seen == [f"{entry['route_dialect']}/{entry['model']}"]
    assert "CONFIRMED" in capsys.readouterr().out


# ---- v3.41.0 iteration 3 (SR-glm-fix-iter3): spawn-alias-mandatory confirm +
# served-state staleness ----------------------------------------------------------
#
# The SECOND deploy went green while the listener stayed stale — two escapes:
# (1) confirm fell back to ct6-secondary, whose upstream is correct in BOTH
# the old and new configs, so the anthropic-served spawn alias never failed
# anything ("CONFIRMED via ct6-secondary" — TRUE but IRRELEVANT); (2) the
# restart trigger byte-diffed the generated config against the PRIOR FILE,
# and iteration 1 had already regenerated the file — file-current-
# process-stale matches no byte diff. The spawn alias (when recorded) is now
# the MANDATORY completion candidate, and staleness is judged against the
# SERVED state (/model/info) with the byte diff kept as the cheap first check.

ZAI_ROUTE = "hosted_vllm/glm-5.2"
STALE_MARKER_GROUP = "claude-ct6-secondary"


def _served_from_config(gw: ModuleType, config_text: str,
                        secondary_route: str) -> list[dict]:
    """A /model/info data set that MATCHES a generated config: one deployment
    per non-wildcard group, secondary-bound aliases on the secondary route,
    Anthropic ids on their real upstreams."""
    deps: list[dict] = []
    for i, group in enumerate(sorted(gw._config_model_groups(config_text))):
        if "*" in group:
            continue
        model = (secondary_route
                 if group in (gw.SECONDARY_ALIAS, gw.SPAWN_ALIAS_MODEL_ID)
                 else f"anthropic/{group}")
        deps.append({"model_name": group,
                     "litellm_params": {"model": model},
                     "model_info": {"id": f"dep-{i}"}})
    return deps


def _stale_served_deployments(gw: ModuleType) -> list[dict]:
    """The /model/info the SECOND deploy actually observed: the stale marker
    group still served, and the spawn alias answered by the wildcard's
    dynamically-instantiated real-Anthropic deployment (883c743106d3)."""
    return [
        {"model_name": gw.SECONDARY_ALIAS,
         "litellm_params": {"model": ZAI_ROUTE},
         "model_info": {"id": "dep-old-secondary"}},
        {"model_name": STALE_MARKER_GROUP,
         "litellm_params": {"model": ZAI_ROUTE},
         "model_info": {"id": "dep-stale-marker"}},
        {"model_name": gw.SPAWN_ALIAS_MODEL_ID,
         "litellm_params": {"model": "anthropic/claude-haiku-4-5"},
         "model_info": {"id": "883c743106d3"}},
    ]


def _model_info_matching_config(gw: ModuleType, base: Path, provider: str):
    """A /model/info prober fake that serves whatever ``base/config.yaml``
    routes AT CALL TIME — the healthy 'the new instance bound the port and
    serves the regenerated config' shape iteration-4 bind verification
    expects. Reads the file per call so it always reflects the config the
    install just regenerated."""
    entry = gw.SECONDARY_PROVIDERS[provider]
    route = f"{entry['route_dialect']}/{entry['model']}"

    def prober(port, key, timeout=5.0):
        text = (base / gw.CONFIG_NAME).read_text(encoding="utf-8")
        return _served_from_config(gw, text, route)

    return prober


def test_config_model_groups_parses_the_real_generator_output(
    gw: ModuleType,
) -> None:
    """The staleness parser is pinned against the REAL generator in both auth
    modes — a generator shape change must break THIS test, never silently
    blind served-state detection."""
    sub = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    assert gw._config_model_groups(sub) == {
        gw.SECONDARY_ALIAS, gw.SPAWN_ALIAS_MODEL_ID}
    api = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    expected = {gw.SECONDARY_ALIAS, gw.SPAWN_ALIAS_MODEL_ID, "*"}
    expected.update(gw.ANTHROPIC_EXPLICIT_MODELS)
    assert gw._config_model_groups(api) == expected


def test_served_state_staleness_none_when_served_matches(gw: ModuleType) -> None:
    """A running gateway serving exactly the generated groups on the expected
    upstreams is NOT stale — no restart churn on a healthy process."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    served = _served_from_config(gw, config, ZAI_ROUTE)
    assert gw._served_state_staleness(
        config, served,
        {gw.SECONDARY_ALIAS: ZAI_ROUTE,
         gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE}) is None


def test_served_state_staleness_names_the_stale_marker_group(
    gw: ModuleType,
) -> None:
    """A served group the generated config does not route — the exact
    stale-process signature the B6 witness observed (the leftover
    claude-ct6-secondary marker) — reads as stale, named."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    served = _served_from_config(gw, config, ZAI_ROUTE) + [
        {"model_name": STALE_MARKER_GROUP,
         "litellm_params": {"model": ZAI_ROUTE},
         "model_info": {"id": "dep-stale-marker"}}]
    reason = gw._served_state_staleness(
        config, served,
        {gw.SECONDARY_ALIAS: ZAI_ROUTE, gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE})
    assert reason is not None and STALE_MARKER_GROUP in reason
    assert "does not route" in reason


def test_served_state_staleness_catches_wrong_upstream_with_equal_group_sets(
    gw: ModuleType,
) -> None:
    """The decisive iteration-3 check: the group-name sets can be IDENTICAL
    (the new config routes claude-haiku-4-5 explicitly; the stale process
    serves the same name via the wildcard's real-Anthropic instantiation)
    while the serving upstream is wrong — the upstream comparison must catch
    what any group-set comparison alone cannot."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    served = _served_from_config(gw, config, ZAI_ROUTE)
    for dep in served:
        if dep["model_name"] == gw.SPAWN_ALIAS_MODEL_ID:
            dep["litellm_params"]["model"] = "anthropic/claude-haiku-4-5"
    reason = gw._served_state_staleness(
        config, served,
        {gw.SECONDARY_ALIAS: ZAI_ROUTE, gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE})
    assert reason is not None
    assert "anthropic/claude-haiku-4-5" in reason and ZAI_ROUTE in reason
    assert "does not route" not in reason and "does not serve" not in reason


def test_served_state_staleness_names_a_missing_generated_group(
    gw: ModuleType,
) -> None:
    """A generated group the running gateway does not serve means the process
    predates the route — stale, named."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    served = [d for d in _served_from_config(gw, config, ZAI_ROUTE)
              if d["model_name"] != gw.SPAWN_ALIAS_MODEL_ID]
    reason = gw._served_state_staleness(
        config, served,
        {gw.SECONDARY_ALIAS: ZAI_ROUTE, gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE})
    assert reason is not None
    assert "does not serve" in reason and gw.SPAWN_ALIAS_MODEL_ID in reason


def test_served_state_staleness_ignores_wildcard_groups(gw: ModuleType) -> None:
    """Wildcard groups are excluded on BOTH sides: a /model/info that lists no
    '*' entry for the generated catch-all never reads as stale, and a served
    '*' entry never counts as extra (its representation varies by LiteLLM
    version)."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    served = _served_from_config(gw, config, ZAI_ROUTE)
    expectations = {gw.SECONDARY_ALIAS: ZAI_ROUTE,
                    gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE}
    assert gw._served_state_staleness(config, served, expectations) is None
    served.append({"model_name": "*",
                   "litellm_params": {"model": "anthropic/*"},
                   "model_info": {"id": "dep-wildcard"}})
    assert gw._served_state_staleness(config, served, expectations) is None


def test_confirm_mandatory_spawn_failure_never_falls_back(
    gw: ModuleType,
) -> None:
    """SR-glm-fix-iter3 root cause 1: the prober fails ONLY on the spawn alias
    and ct6-secondary would answer fine — with the spawn alias MANDATORY the
    confirm must FAIL and the fallback candidate must never even be probed."""
    probed: list[str] = []

    def prober(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        if model == gw.SPAWN_ALIAS_MODEL_ID:
            raise ValueError(
                f"served by anthropic/claude-haiku-4-5, "
                f"expected {expected_upstream}")
        return "ok"

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID, gw.SECONDARY_ALIAS],
        completion_prober=prober, expected_upstream=ZAI_ROUTE,
        mandatory_completion_model=gw.SPAWN_ALIAS_MODEL_ID)
    assert ok is False
    assert probed == [gw.SPAWN_ALIAS_MODEL_ID], \
        "the fallback candidate must never be probed past a mandatory failure"
    assert "MANDATORY" in detail
    assert "served by anthropic/claude-haiku-4-5" in detail


def test_confirm_mandatory_rejects_a_fallback_only_success(
    gw: ModuleType,
) -> None:
    """Defensive pin: even if a (buggy future) call site lists the mandatory
    candidate AFTER a fallback, a completion that arrived via the fallback
    alone cannot confirm — the guard rejects it by name."""
    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SECONDARY_ALIAS, gw.SPAWN_ALIAS_MODEL_ID],
        completion_prober=(
            lambda port, key, model, timeout=30.0, expected_upstream=None: "ok"),
        mandatory_completion_model=gw.SPAWN_ALIAS_MODEL_ID)
    assert ok is False
    assert "MANDATORY" in detail and gw.SPAWN_ALIAS_MODEL_ID in detail


def test_install_confirm_is_spawn_mandatory_no_fallback_green(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    _stub_registration: "_RecordingRunner", capsys: pytest.CaptureFixture[str],
) -> None:
    """Escape 1 at the install call site: the spawn alias stays anthropic-
    served (every probe fails, even after the repair restart) while
    ct6-secondary would answer fine — the install confirm must FAIL and the
    neutral alias must never be completion-probed."""
    probed: list[str] = []

    def prober(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        if model == gw.SPAWN_ALIAS_MODEL_ID:
            raise ValueError(
                f"served by anthropic/claude-haiku-4-5, "
                f"expected {expected_upstream}")
        return "ok"

    monkeypatch.setattr(gw, "_default_completion_prober", prober)
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    assert "completion hop FAILED" in out and "MANDATORY" in out
    assert "CONFIRMED" not in out
    assert gw.SECONDARY_ALIAS not in probed, \
        "install must never go green (or even probe) via the ct6-secondary fallback"
    # Iteration 6: the repair attempt is the never-dark staging launch; the
    # unverifiable staging (hermetic /model/info unreachable) means the
    # serving instance is never stopped.
    assert _staging_attempts(_stub_registration.calls), \
        "the mandatory spawn failure must still fire the repair (staging)"
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert not ends, "NEVER-DARK: no live stop may fire when staging failed"


def test_install_replays_the_file_current_process_stale_escape(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    _stub_registration: "_RecordingRunner", capsys: pytest.CaptureFixture[str],
) -> None:
    """THE SR-glm-fix-iter3 escape replayed end-to-end: the config file is
    CURRENT (a prior run already regenerated it — the byte diff is silent),
    the PROCESS still serves the old config (/model/info shows the stale
    marker group + the anthropic-served spawn alias), and the state records
    spawn_alias. The install must restart on the served-state mismatch and
    must never go green via the ct6-secondary fallback. Iteration 4: the
    restart is bind-VERIFIED, so the /model/info fake is STATEFUL — stale
    until the restart's stop half fires, then serving the regenerated config
    (the restart actually healing the served state). Iteration 6: the fakes
    are PORT-aware — the staged replacement on the staging port serves the
    regenerated config correctly (staging-green is what sanctions touching
    the live instance), while the live port stays stale until the swap."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    _stub_registration.calls.clear()
    capsys.readouterr()
    probed: list[str] = []
    staging_port = gw.DEFAULT_PORT + gw.STAGING_PORT_OFFSET

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        if port == staging_port:  # the staged replacement serves correctly
            return "ok"
        ends = [c for c in _stub_registration.calls
                if c[:2] == ["schtasks", "/end"]]
        if not ends:  # pre-restart: the stale process's wildcard answers
            raise ValueError(
                f"served by anthropic/claude-haiku-4-5, "
                f"expected {expected_upstream}")
        return "ok"

    healed = _model_info_matching_config(gw, base, "zai")

    def model_info(port, key, timeout=5.0):
        if port == staging_port:  # the staged replacement serves correctly
            return healed(port, key, timeout)
        ends = [c for c in _stub_registration.calls
                if c[:2] == ["schtasks", "/end"]]
        if not ends:  # pre-restart: the stale process still answers
            return _stale_served_deployments(gw)
        return healed(port, key, timeout)

    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert ends, \
        "served-state staleness must fire the restart (the byte diff is silent here)"
    assert (_first_index(_stub_registration.calls,
                         _staging_attempts(_stub_registration.calls)[0])
            < _first_index(_stub_registration.calls, ["schtasks", "/end"])), \
        "never-dark ordering: the staging launch precedes any live stop"
    assert "STALE" in out and STALE_MARKER_GROUP in out
    assert "anthropic/claude-haiku-4-5" in out
    assert gw.SECONDARY_ALIAS not in probed, \
        "never green via the ct6-secondary fallback"
    assert f"completion CONFIRMED via {gw.SPAWN_ALIAS_MODEL_ID}" in out


def test_install_served_state_restart_failure_stays_honest(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The SR's 'restart (or fail naming the staleness)' arm: when the
    served-state restart CANNOT be executed, the run still names the
    staleness and the spawn-mandatory confirm fails honestly — never green."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    capsys.readouterr()

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        raise ValueError(
            f"served by anthropic/claude-haiku-4-5, "
            f"expected {expected_upstream}")

    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _stale_served_deployments(gw))
    monkeypatch.setattr(
        gw, "restart_gateway",
        lambda *a, **k: (False, "simulated restart failure"))
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    assert "STALE" in out and STALE_MARKER_GROUP in out
    assert "completion hop FAILED" in out
    assert "CONFIRMED" not in out


def test_install_matching_served_state_never_restarts(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    _stub_registration: "_RecordingRunner",
) -> None:
    """A REACHABLE /model/info that matches the generated config (groups +
    expected upstreams) is healthy — a byte-identical re-install must not
    churn it."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    config = (base / gw.CONFIG_NAME).read_text(encoding="utf-8")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _served_from_config(gw, config, ZAI_ROUTE))
    _stub_registration.calls.clear()
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    ends = [c for c in _stub_registration.calls if c[:2] == ["schtasks", "/end"]]
    assert not ends, "a served state matching the generated config must not restart"


def test_status_live_spawn_recorded_is_mandatory_no_fallback(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status --live on a modern state (spawn_alias recorded): a failing
    spawn-alias probe means FAIL — ct6-secondary is never completion-probed
    and never confirms in its place (status observes; install repairs)."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    probed: list[str] = []

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        raise ValueError(
            f"served by anthropic/claude-haiku-4-5, "
            f"expected {expected_upstream}")

    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    capsys.readouterr()
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_path / "agents-absent")]) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED" not in out and "MANDATORY" in out
    assert probed and set(probed) == {gw.SPAWN_ALIAS_MODEL_ID}
    assert gw.SECONDARY_ALIAS not in probed


def test_status_live_legacy_state_without_spawn_alias_keeps_secondary_green(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The iteration-3 carve-out pinned: a state with NO spawn_alias recorded
    (its config never routed one) still confirms green via the recorded
    secondary alias — spawn-mandatory applies only when the state records
    the spawn alias."""
    probed: list[str] = []

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        return "pong"

    base = tmp_path / "gw"
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        "ZAI_API_KEY": RAW_ZAI_KEY, gw.MASTER_KEY_VAR: "sk-ct6-m"})
    (base / gw.CONFIG_NAME).write_text("# pre-spawn-alias config\n",
                                       encoding="utf-8")
    gw._write_state(base, {
        "auth_mode": gw.AUTH_MODE_API_KEY, "port": gw.DEFAULT_PORT,
        "activated": True, "enabled": True, "registered": True,
        "secondary_provider": "zai", "secondary_model": "glm-5.2",
        "secondary_alias": gw.SECONDARY_ALIAS,
        "model_policy": "secondary-split"})
    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    assert gw.main(["status", "--base-dir", str(base), "--live",
                    "--settings-path", str(tmp_path / "settings.json"),
                    "--agents-dir", str(tmp_path / "agents-absent")]) == 0
    out = capsys.readouterr().out
    assert "CONFIRMED" in out
    assert probed == [gw.SECONDARY_ALIAS]
    assert gw.SPAWN_ALIAS_MODEL_ID not in probed


# ---- v3.41.0 iteration 4 (SR-glm-fix-iter4): stop-by-port + bind-verified
# restart ---------------------------------------------------------------------------
#
# The THIRD deploy: iteration-3's served-state detection and spawn-mandatory
# confirm behaved exactly as designed (staleness named, confirm failed
# closed) — but the "restart" was a no-op. Port 4000 was held by an UNTRACKED
# process (PID 68724, started manually during diagnosis) across TWO restarts:
# the tracked stop (schtasks /end) only stops the task-managed process, and
# each blocked start leaked a doomed litellm instance (5 zombies observed).
# The verified restart now (10a) stops BY PORT — only after the tracked stop
# fails to free the gateway's own configured port, resolving the LISTENING
# pid via netstat/lsof and stopping THAT pid, image-agnostic — and (10b)
# reports restarted ONLY after the new instance binds and serves the
# generated config (the iteration-3 served-state seam), a still-held port
# being a NAMED failure after at most one start attempt.

INCIDENT_HOLDER_PID = 68724


class _PortAwareRunner:
    """subprocess.run stand-in with a live PORT model: ``netstat`` reports
    the configured holder pid LISTENING on the gateway port until it is
    stopped — by ``taskkill /pid <holder>`` (when kill_rc is 0), or by the
    tracked ``schtasks /end`` itself when ``tracked_stop_frees`` is True (the
    ordering pin's control case). ``tasklist`` reports the holder's image;
    every other command succeeds."""

    def __init__(self, port: int = 4000,
                 holder_pid: int | None = INCIDENT_HOLDER_PID,
                 image: str = "diagnostic-python.exe",
                 tracked_stop_frees: bool = False,
                 kill_rc: int = 0,
                 kill_err: str = "ERROR: Access is denied.") -> None:
        self.port = port
        self.holder_pid = holder_pid
        self.image = image
        self.tracked_stop_frees = tracked_stop_frees
        self.kill_rc = kill_rc
        self.kill_err = kill_err
        self.held = holder_pid is not None
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):  # noqa: ANN001
        cmd = list(cmd)
        self.calls.append(cmd)
        rc, out, err = 0, "", ""
        if cmd[:2] == ["schtasks", "/end"] and self.tracked_stop_frees:
            self.held = False
        elif cmd[0] == "netstat":
            rows = ["", "Active Connections", "",
                    "  Proto  Local Address          Foreign Address"
                    "        State           PID",
                    "  TCP    0.0.0.0:135            0.0.0.0:0        "
                    "      LISTENING       1084"]
            if self.held:
                rows += [
                    f"  TCP    127.0.0.1:{self.port}         0.0.0.0:0"
                    f"              LISTENING       {self.holder_pid}",
                    f"  TCP    [::]:{self.port}              [::]:0   "
                    f"              LISTENING       {self.holder_pid}"]
            rows.append("  TCP    127.0.0.1:49152        127.0.0.1:49153"
                        "        ESTABLISHED     4321")
            out = "\n".join(rows) + "\n"
        elif cmd[0] == "tasklist":
            out = (f'"{self.image}","{self.holder_pid}","Console","1",'
                   f'"123,456 K"\n')
        elif cmd[0] == "taskkill":
            rc = self.kill_rc
            if rc == 0 and len(cmd) > 2 and cmd[2] == str(self.holder_pid):
                self.held = False
            elif rc != 0:
                err = self.kill_err

        class _Res:
            returncode = rc
            stdout = out
            stderr = err

        return _Res()


def _first_index(calls: list[list[str]], prefix: list[str]) -> int:
    for i, c in enumerate(calls):
        if c[:len(prefix)] == prefix:
            return i
    raise AssertionError(f"{prefix} never recorded in {calls}")


def _verified_kwargs(gw: ModuleType, config: str) -> dict:
    return dict(port=4000, master_key="sk-m", generated_config=config,
                expected_upstreams={gw.SECONDARY_ALIAS: ZAI_ROUTE,
                                    gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE})


def test_windows_netstat_parse_resolves_the_listening_pid(
    gw: ModuleType,
) -> None:
    """The pure parser pinned on real-shaped netstat output: the LISTENING
    row on the exact port wins (IPv4 or IPv6); a near-miss port (:14000), an
    ESTABLISHED row on the port, and garbage never match."""
    text = (
        "\nActive Connections\n\n"
        "  Proto  Local Address          Foreign Address        State           PID\n"
        "  TCP    0.0.0.0:14000          0.0.0.0:0              LISTENING       111\n"
        "  TCP    127.0.0.1:4000         127.0.0.1:49200        ESTABLISHED     222\n"
        f"  TCP    [::]:4000              [::]:0                 LISTENING       {INCIDENT_HOLDER_PID}\n")
    assert gw._windows_port_listener_pid(text, 4000) == INCIDENT_HOLDER_PID
    free = ("  TCP    0.0.0.0:135            0.0.0.0:0              "
            "LISTENING       1084\n")
    assert gw._windows_port_listener_pid(free, 4000) is None
    assert gw._windows_port_listener_pid("not netstat output at all", 4000) is None


def test_posix_lsof_parse_resolves_the_first_pid(gw: ModuleType) -> None:
    assert gw._posix_port_listener_pid("68724\n70001\n") == 68724
    assert gw._posix_port_listener_pid("") is None
    assert gw._posix_port_listener_pid("lsof: command garbage\n") is None


def test_restart_gateway_legacy_call_shape_skips_port_machinery(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """Without the verification context (no port/master_key/config) the
    restart keeps its pre-iteration-4 tracked stop+start, byte-identical —
    no netstat, no taskkill, no bind poll."""
    runner = _PortAwareRunner()
    ok, detail = gw.restart_gateway(
        "windows", tmp_path / "launch-gateway.cmd", runner=runner)
    assert ok and detail == "scheduled task restarted"
    assert not [c for c in runner.calls if c[0] in ("netstat", "taskkill")]


def test_restart_stops_the_untracked_port_holder_and_verifies_the_bind(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE SR-glm-fix-iter4 escape at the unit level: the tracked stop is a
    no-op on the untracked holder (PID 68724) => the pid is resolved from the
    gateway's own port and stopped, the ONE start fires, the bind verifies,
    and the SUCCESS detail names the resolved pid+image (the audit trail for
    having stopped a process the tracker did not own)."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _served_from_config(gw, config, ZAI_ROUTE))
    runner = _PortAwareRunner()
    ok, detail = gw.restart_gateway(
        "windows", tmp_path / "launch-gateway.cmd", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok, detail
    assert "bind VERIFIED" in detail
    assert str(INCIDENT_HOLDER_PID) in detail
    assert "diagnostic-python.exe" in detail
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", str(INCIDENT_HOLDER_PID),
                      "/t", "/f"]], \
        "a deliberate port-freeing stop takes the holder's tree (/t)"
    # ordering: tracked stop -> port resolution -> pid kill -> the ONE start
    i_end = _first_index(runner.calls, ["schtasks", "/end"])
    i_netstat = _first_index(runner.calls, ["netstat"])
    i_kill = _first_index(runner.calls, ["taskkill"])
    i_run = _first_index(runner.calls, ["schtasks", "/run"])
    assert i_end < i_netstat < i_kill < i_run
    assert len([c for c in runner.calls if c[:2] == ["schtasks", "/run"]]) == 1


def test_port_kill_fires_only_after_tracked_stop_fails_to_free(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The B4 auditor's ordering pin: when the tracked stop ITSELF frees the
    port, the pid-kill fallback never fires — it must not drift into being
    the primary path. The port check runs only downstream of the tracked
    stop."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _served_from_config(gw, config, ZAI_ROUTE))
    runner = _PortAwareRunner(tracked_stop_frees=True)
    ok, detail = gw.restart_gateway(
        "windows", tmp_path / "launch-gateway.cmd", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok, detail
    assert "bind VERIFIED" in detail
    assert not [c for c in runner.calls if c[0] == "taskkill"], \
        "the pid-kill must never fire when the tracked stop freed the port"
    assert (_first_index(runner.calls, ["schtasks", "/end"])
            < _first_index(runner.calls, ["netstat"]))


def test_port_holder_kill_refused_reports_honestly_and_never_starts(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """Refusal honesty: an access-denied pid stop returns a named failure —
    resolved pid + image + the refusal + a manual remediation — and NO start
    is attempted (a blocked start would only leak a doomed instance)."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    runner = _PortAwareRunner(kill_rc=1)
    ok, detail = gw.restart_gateway(
        "windows", tmp_path / "launch-gateway.cmd", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok is False
    assert "REFUSED" in detail
    assert str(INCIDENT_HOLDER_PID) in detail
    assert "diagnostic-python.exe" in detail
    assert "Access is denied" in detail
    assert f"taskkill /pid {INCIDENT_HOLDER_PID} /t /f" in detail
    assert "no start attempted" in detail
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/run"]], \
        "a refused port-holder stop must never attempt the start"


def test_port_holder_kill_is_image_agnostic(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The B4 auditor's no-image-guard pin: the kill keys on PORT OWNERSHIP,
    never on the process image — a holder that is not litellm at all is
    stopped identically (an image-name guard would reintroduce launcher-shape
    special-casing), with the image reported honestly."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _served_from_config(gw, config, ZAI_ROUTE))
    runner = _PortAwareRunner(image="totally-unrelated-tool.exe")
    ok, detail = gw.restart_gateway(
        "windows", tmp_path / "launch-gateway.cmd", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok, detail
    assert [c for c in runner.calls if c[0] == "taskkill"], \
        "the kill must fire on the port-holding pid regardless of its image"
    assert "totally-unrelated-tool.exe" in detail


def test_restart_bind_failure_unreachable_is_named_no_spawn_loop(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """10b: a start whose instance never answers /model/info is a NAMED
    failure — 'restarted' is never reported on faith, and exactly ONE start
    is attempted (the incident leaked 5 doomed instances)."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    runner = _PortAwareRunner(holder_pid=None)  # port free; the autouse
    # /model/info seam raises (unreachable) — the bind can never verify.
    ok, detail = gw.restart_gateway(
        "windows", tmp_path / "launch-gateway.cmd", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok is False
    assert "NOT verified" in detail
    assert "never answered /model/info" in detail and "4000" in detail
    assert "no further start attempted" in detail
    assert len([c for c in runner.calls if c[:2] == ["schtasks", "/run"]]) == 1
    assert not [c for c in runner.calls if c[0] == "taskkill"]


def test_restart_bind_failure_stale_serve_is_named(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """10b's second arm: the new instance answers but still serves a state
    that does not match the generated config — named, never 'restarted'."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _stale_served_deployments(gw))
    runner = _PortAwareRunner(holder_pid=None)
    ok, detail = gw.restart_gateway(
        "windows", tmp_path / "launch-gateway.cmd", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok is False
    assert "does not match the generated config" in detail
    assert STALE_MARKER_GROUP in detail
    assert len([c for c in runner.calls if c[:2] == ["schtasks", "/run"]]) == 1


def test_install_replays_the_untracked_port_holder_escape(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """THE SR-glm-fix-iter4 escape replayed end-to-end at the install call
    site: config file CURRENT (byte diff silent), the PROCESS stale (served
    state names the marker + the anthropic-served spawn alias), and the port
    held by the untracked diagnostic pid the tracked stop cannot touch. The
    install must resolve + stop the port-holder, bind-verify the ONE new
    start, and go green only through the spawn-mandatory completion.
    Iteration 6: the /model/info fake is PORT-aware — the staged replacement
    on the staging port serves the regenerated config (staging-green
    sanctions the cutover) while the live port answers stale until the
    holder is stopped."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    capsys.readouterr()
    runner = _PortAwareRunner()
    monkeypatch.setattr(gw, "_default_runner", runner)
    probed: list[str] = []
    staging_port = gw.DEFAULT_PORT + gw.STAGING_PORT_OFFSET

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        return "ok"

    healed = _model_info_matching_config(gw, base, "zai")

    def model_info(port, key, timeout=5.0):
        if port == staging_port:  # the staged replacement serves correctly
            return healed(port, key, timeout)
        killed = [c for c in runner.calls if c[0] == "taskkill"]
        if not killed:  # pre-kill: the untracked holder still answers stale
            return _stale_served_deployments(gw)
        return healed(port, key, timeout)

    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", str(INCIDENT_HOLDER_PID),
                      "/t", "/f"]], \
        "the untracked port-holder must be stopped by pid, tree-wide (/t)"
    assert (_first_index(runner.calls, ["schtasks", "/end"])
            < _first_index(runner.calls, ["taskkill"])), \
        "the pid stop fires only after the tracked stop failed to free the port"
    assert "STALE" in out and STALE_MARKER_GROUP in out
    assert str(INCIDENT_HOLDER_PID) in out
    assert "diagnostic-python.exe" in out
    assert "bind VERIFIED" in out
    assert f"completion CONFIRMED via {gw.SPAWN_ALIAS_MODEL_ID}" in out
    assert gw.SECONDARY_ALIAS not in probed, \
        "never green via the ct6-secondary fallback"


# ---- v3.41.0 iteration 5 (SR-glm-fix-iter5, USER MANDATE "make sure that
# never happens on install"): exactly-one-instance + start-ownership +
# auth-enforcement + master-key never-rotate --------------------------------------
#
# The FOURTH deploy's aftermath: 8 accumulated litellm instances (~12 GB) —
# register's start-now half ran `schtasks /run` on EVERY install — and after
# the iteration-4 port-holder kill an ENV-BROKEN zombie (master key
# unresolvable) stole port 4000 in the race window. The state-match
# bind-verify PASSED on it (same config file) while every real-token request
# failed into LiteLLM's no-DB 400 path, breaking the user's live fable
# sessions. Closed by: (11a) an owned-instance sweep (cmdline carries THIS
# state dir's config path — the ownership proof; Windows path forms
# normalized) before the ONE start, with register never blind-starting over a
# held port; (11b) post-start ownership — the port-holder must BE the
# just-launched instance (launch-window match where pid lineage is opaque);
# (11c) a negative auth probe in confirm — a deliberately-invalid key MUST be
# rejected 4xx (200 = unenforced, 5xx = the no-DB prisma crash; both fail,
# named); (11d) the master key never rotates on re-install (rotation would
# invalidate the settings.json auth token live sessions depend on).

ZOMBIE_PID = 111          # the pre-existing env-broken owned instance
SERVING_PID = 9716        # the incident's healthy hand-started survivor
LAUNCHED_PID = 20001      # the pid a /run start creates in the model


def _owned_cmd(base: Path, form: str = "plain") -> str:
    """A realistic gateway cmdline carrying this state dir's config path, in
    the requested path form (the Windows-normalization cases)."""
    cfg = str(base / "config.yaml")
    if form == "upper":
        cfg = cfg.upper()
    elif form == "fwd":
        cfg = cfg.replace("\\", "/")
    return f'"C:\\py\\Scripts\\litellm" --config "{cfg}" --port 4000'


def _cim_row(pid: int, entry: tuple) -> str:
    """A fake CIM listing row. Legacy ``(cmdline, image)`` entries emit the
    two-field ``pid|cmdline`` shape — parsed as one-node trees, the
    pre-iteration-7 per-pid identity, keeping every iteration-4/5/6 fixture
    byte-meaningful. Rich ``(cmdline, image, ppid, created)`` entries emit
    the real four-field ``pid|ppid|creation|cmdline`` shape that feeds
    iteration-7 tree grouping (ppid/created may be None → empty field)."""
    if len(entry) >= 4:
        ppid = "" if entry[2] is None else entry[2]
        created = "" if entry[3] is None else entry[3]
        return f"{pid}|{ppid}|{created}|{entry[0]}\n"
    return f"{pid}|{entry[0]}\n"


class _ProcessAwareRunner:
    """subprocess.run stand-in extending the iteration-4 port model with a
    PROCESS POPULATION: the CIM listing reports ``pid|cmdline`` rows (or the
    rich four-field rows when a population entry carries ppid/created —
    see ``_cim_row``), ``tasklist /fi "PID eq N"`` reports that pid's image,
    ``taskkill /pid N`` removes N from the population (freeing the port when
    N holds it), ``schtasks /end`` never touches an untracked instance, and
    ``schtasks /run`` LAUNCHES a new owned instance — which claims the port
    unless a configured zombie wins the race (``race_winner_pid``)."""

    def __init__(self, base: Path, port: int = 4000,
                 processes: dict[int, tuple[str, str]] | None = None,
                 holder_pid: int | None = None,
                 launch_pid: int = LAUNCHED_PID,
                 race_winner_pid: int | None = None,
                 kill_rc: int = 0,
                 kill_err: str = "ERROR: Access is denied.") -> None:
        self.base = base
        self.port = port
        self.processes = dict(processes or {})  # pid -> (cmdline, image)
        self.holder_pid = holder_pid
        self.launch_pid = launch_pid
        self.race_winner_pid = race_winner_pid
        self.kill_rc = kill_rc
        self.kill_err = kill_err
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):  # noqa: ANN001
        cmd = list(cmd)
        self.calls.append(cmd)
        rc, out, err = 0, "", ""
        if cmd[0] == "powershell":
            out = "".join(_cim_row(pid, entry)
                          for pid, entry in sorted(self.processes.items()))
        elif cmd[0] == "netstat":
            rows = ["", "Active Connections", "",
                    "  Proto  Local Address          Foreign Address"
                    "        State           PID",
                    "  TCP    0.0.0.0:135            0.0.0.0:0        "
                    "      LISTENING       1084"]
            if self.holder_pid is not None:
                rows.append(
                    f"  TCP    127.0.0.1:{self.port}         0.0.0.0:0"
                    f"              LISTENING       {self.holder_pid}")
            out = "\n".join(rows) + "\n"
        elif cmd[0] == "tasklist":
            pid = int(cmd[2].split()[-1])
            image = self.processes.get(pid, ("", "ghost.exe"))[1]
            out = f'"{image}","{pid}","Console","1","123,456 K"\n'
        elif cmd[0] == "taskkill":
            rc = self.kill_rc
            if rc == 0:
                pid = int(cmd[2])
                self.processes.pop(pid, None)
                if pid == self.holder_pid:
                    self.holder_pid = None
            else:
                err = self.kill_err
        elif cmd[:2] == ["schtasks", "/run"]:
            self.processes[self.launch_pid] = (
                _owned_cmd(self.base), "litellm.exe")
            self.holder_pid = (self.race_winner_pid
                               if self.race_winner_pid is not None
                               else self.launch_pid)

        class _Res:
            returncode = rc
            stdout = out
            stderr = err

        return _Res()


def test_pid_cmdline_parses_are_pure_and_narrow(gw: ModuleType) -> None:
    """The two process-listing parsers pinned: pid|cmdline rows (Windows CIM,
    split on the FIRST pipe so a cmdline pipe survives) and `ps -axo
    pid=,args=` rows; garbage never parses."""
    win = ("1234|litellm --config C:\\gw\\config.yaml --port 4000\n"
           "77|cmd /c a | b\n"
           "notpid|junk\n"
           "no separator line\n")
    assert gw._windows_pid_cmdlines(win) == [
        (1234, "litellm --config C:\\gw\\config.yaml --port 4000"),
        (77, "cmd /c a | b"),
    ]
    posix = ("  321 /usr/bin/litellm --config /gw/config.yaml\n"
             "junk line\n"
             " 44 ps -axo pid=,args=\n")
    assert gw._posix_pid_cmdlines(posix) == [
        (321, "/usr/bin/litellm --config /gw/config.yaml"),
        (44, "ps -axo pid=,args="),
    ]


def test_owned_match_normalizes_windows_path_forms(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The B4 auditor's normalization note pinned: ownership matching survives
    case differences, forward/backslash separators, and the 8.3 short-name
    form (via the injectable short-path seam) — while a DIFFERENT state dir's
    config path and our own pid never match."""
    base = tmp_path / "gw"
    other = tmp_path / "other-gw"
    monkeypatch.setattr(
        gw, "_default_short_path_fn",
        lambda path: "C:\\USERS\\PAUL~1\\GATEW~1\\CONFIG~1.YAM")
    population = {
        11: (_owned_cmd(base), "litellm.exe"),
        12: (_owned_cmd(base, "upper"), "litellm.exe"),
        13: (_owned_cmd(base, "fwd"), "python.exe"),
        14: ('litellm --config "c:/users/paul~1/gatew~1/config~1.yam"',
             "litellm.exe"),
        15: (_owned_cmd(other), "litellm.exe"),
        os.getpid(): (_owned_cmd(base), "python.exe"),
    }
    runner = _ProcessAwareRunner(base, processes=population)
    owned = gw._owned_gateway_instances("windows", base, runner)
    assert owned is not None
    assert sorted(p for p, _ in owned) == [11, 12, 13, 14], \
        "long/upper/forward-slash/8.3 forms match; other dirs + self never do"
    # cannot-enumerate is fail-open None, never an empty claim
    def deny(cmd, **kwargs):  # noqa: ANN001
        class _Res:
            returncode = 1
            stdout = ""
            stderr = "denied"
        return _Res()

    assert gw._owned_gateway_instances("windows", base, deny) is None


def test_register_sweeps_owned_zombies_before_the_single_start(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """11a: with the ownership context, register stops EVERY owned instance
    (the accumulated-zombie population) BEFORE its one start — kills strictly
    precede the /run — and the report names each stopped pid + image."""
    base = tmp_path / "gw"
    runner = _ProcessAwareRunner(base, processes={
        ZOMBIE_PID: (_owned_cmd(base), "python.exe"),
        112: (_owned_cmd(base, "fwd"), "litellm.exe"),
    })
    ok, detail = gw.register_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        base=base, port=4000)
    assert ok, detail
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", str(ZOMBIE_PID), "/f"],
                     ["taskkill", "/pid", "112", "/f"]]
    assert (_first_index(runner.calls, ["taskkill"])
            < _first_index(runner.calls, ["schtasks", "/run"])), \
        "the sweep fires before the single start"
    assert len([c for c in runner.calls if c[:2] == ["schtasks", "/run"]]) == 1
    assert f"stopped owned instance pid {ZOMBIE_PID} (python.exe)" in detail
    assert "stopped owned instance pid 112 (litellm.exe)" in detail
    assert set(runner.processes) == {LAUNCHED_PID}, \
        "exactly one owned instance after the install path"


def test_register_never_blind_starts_over_a_serving_owned_instance(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """11a's no-blind-start pin: an owned instance already serving the port is
    KEPT (register skips the start — the unconditional every-install start was
    the accumulation source) while its owned zombie siblings are swept."""
    base = tmp_path / "gw"
    runner = _ProcessAwareRunner(base, processes={
        SERVING_PID: (_owned_cmd(base), "litellm.exe"),
        ZOMBIE_PID: (_owned_cmd(base), "python.exe"),
    }, holder_pid=SERVING_PID)
    ok, detail = gw.register_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        base=base, port=4000)
    assert ok, detail
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/run"]], \
        "register must never blind-start over a serving owned instance"
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", str(ZOMBIE_PID), "/f"]], \
        "the serving instance is kept; only its zombie siblings are swept"
    assert (f"start skipped — an owned instance already serves port 4000 "
            f"(pid {SERVING_PID}") in detail
    assert set(runner.processes) == {SERVING_PID}


def test_register_skips_start_over_a_foreign_held_port(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """A FOREIGN port-holder (not owned by this state dir) also blocks the
    start — starting over a held port would only leak a doomed instance; the
    verified restart's port-holder stop is the sanctioned remover."""
    base = tmp_path / "gw"
    runner = _ProcessAwareRunner(base, processes={
        INCIDENT_HOLDER_PID: ("some-diagnostic --no-config", "diagnostic-python.exe"),
        ZOMBIE_PID: (_owned_cmd(base), "python.exe"),
    }, holder_pid=INCIDENT_HOLDER_PID)
    ok, detail = gw.register_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        base=base, port=4000)
    assert ok, detail
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/run"]]
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", str(ZOMBIE_PID), "/f"]], \
        "owned zombies are swept; the foreign holder is NOT killed here"
    assert (f"start skipped — port 4000 is held by pid {INCIDENT_HOLDER_PID}"
            in detail)
    assert "does not own" in detail


def test_register_legacy_call_shape_keeps_blind_start_byte_identical(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """Without the ownership context (no base/port) register keeps its
    pre-iteration-5 behavior byte-identical: create + start, no process
    listing, no netstat, no kills."""
    runner = _ProcessAwareRunner(tmp_path, processes={
        ZOMBIE_PID: (_owned_cmd(tmp_path), "python.exe")})
    ok, detail = gw.register_gateway(
        "windows", tmp_path / "run_gateway.bat", runner=runner)
    assert ok and detail == "scheduled task registered (onlogon) + started"
    assert [c[0] for c in runner.calls] == ["schtasks", "schtasks"]


def test_owned_sweep_refusal_is_named_with_remediation(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """Refusal honesty (the iteration-4 posture extended to the sweep): an
    access-denied zombie stop is a named row — pid, image, the refusal, the
    manual remediation — and never a silent success."""
    base = tmp_path / "gw"
    runner = _ProcessAwareRunner(base, processes={
        ZOMBIE_PID: (_owned_cmd(base), "python.exe")}, kill_rc=1)
    ok, detail = gw.register_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        base=base, port=4000)
    assert ok, detail
    assert f"stopping owned instance pid {ZOMBIE_PID} (python.exe) was REFUSED" in detail
    assert "Access is denied" in detail
    assert f"taskkill /pid {ZOMBIE_PID} /t /f" in detail


def test_post_start_ownership_catches_a_zombie_race_winner(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE deploy-4 escape at the unit level: after the one start, a
    PRE-EXISTING env-broken zombie wins the port race and serves a state that
    MATCHES the generated config — iteration 4's bind-verify passed exactly
    this. The ownership check now names it as a failure (who, not just what),
    with no further start and no silent service."""
    base = tmp_path / "gw"
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _served_from_config(gw, config, ZAI_ROUTE))
    runner = _ProcessAwareRunner(base, processes={
        ZOMBIE_PID: (_owned_cmd(base), "python.exe")},
        race_winner_pid=ZOMBIE_PID)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok is False
    assert "NOT verified" in detail
    assert f"port claimed by pid {ZOMBIE_PID}" in detail
    assert "PRE-EXISTING owned instance" in detail
    assert "no_db_connection" in detail
    assert f"taskkill /pid {ZOMBIE_PID} /t /f" in detail  # the remediation hint
    assert "no further start attempted" in detail
    assert len([c for c in runner.calls if c[:2] == ["schtasks", "/run"]]) == 1
    assert not [c for c in runner.calls if c[0] == "taskkill"], \
        "the race winner is named, never auto-killed into a kill/start loop"


def test_post_start_ownership_verifies_the_just_launched_instance(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The healthy path: the port-holder after the one start IS the
    just-launched instance (launch-window match on the pid-opaque Windows
    launcher) — the success detail says so alongside the served-state
    verification."""
    base = tmp_path / "gw"
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _served_from_config(gw, config, ZAI_ROUTE))
    runner = _ProcessAwareRunner(base)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok, detail
    assert "bind VERIFIED" in detail
    assert (f"bound by the just-launched instance (pid {LAUNCHED_PID}, "
            f"launch-window match)") in detail


def test_auth_enforcement_probe_grades_the_three_outcomes(
    gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """11c's probe pinned at the HTTP level (arms corrected in iteration 5b):
    4xx = enforced, clean; 200 = NOT enforced (the env-broken-zombie state),
    the only FAIL arm; 5xx = enforcement HELD with a named warning — service
    was DENIED via the LiteLLM no-DB prisma crash, which is how every
    healthy DB-less CT6 gateway answers an invalid key (a 5xx-FAIL arm would
    fail-close every healthy install). The deliberately-invalid key is NEVER
    echoed in any detail (the B4 auditor's never-echo note)."""
    sent: list[str] = []

    def urlopen_4xx(req, timeout=10.0):
        sent.append(req.headers.get("Authorization", ""))
        raise gw.urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr(gw.urllib.request, "urlopen", urlopen_4xx)
    ok, detail = gw._http_auth_enforcement_probe(4000)
    assert ok is True and "HTTP 401" in detail
    assert sent and sent[0].startswith("Bearer sk-ct6-auth-probe-")
    assert sent[0].split("Bearer ")[1] not in detail, \
        "the invalid probe key must never be echoed"

    monkeypatch.setattr(
        gw.urllib.request, "urlopen",
        lambda req, timeout=10.0: _FakeResponse({"data": []}))
    ok, detail = gw._http_auth_enforcement_probe(4000)
    assert ok is False
    assert "NOT ENFORCED" in detail and "HTTP 200" in detail

    def urlopen_5xx(req, timeout=10.0):
        raise gw.urllib.error.HTTPError(
            req.full_url, 500, "Internal Server Error", None, None)

    monkeypatch.setattr(gw.urllib.request, "urlopen", urlopen_5xx)
    ok, detail = gw._http_auth_enforcement_probe(4000)
    assert ok is True, "a crash-5xx denial is enforcement, not a failure"
    assert "DENIED service" in detail and "warning" in detail
    assert "HTTP 500" in detail and "prisma" in detail and "README" in detail


def test_confirm_requires_auth_enforcement_after_the_completion(
    gw: ModuleType,
) -> None:
    """11c in the confirm ladder (arms corrected in iteration 5b): a
    confirmed completion with a 200-unenforced auth probe FAILS the confirm
    naming the auth state; the crash-500 arm is enforcement-with-a-named-
    warning — the confirm PROCEEDS and the warning rides the success detail
    next to the completion confirmation; a clean 4xx probe is reported in
    the success detail; the /v1/models-only legacy shape never probes
    auth."""
    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID],
        completion_prober=lambda *a, **k: "pong",
        auth_prober=lambda port, timeout=10.0: (
            False, "auth is NOT ENFORCED — the gateway ACCEPTED a "
                   "deliberately-invalid key (HTTP 200)"))
    assert ok is False
    assert "auth-enforcement probe FAILED" in detail
    assert "NOT ENFORCED" in detail
    assert "CONFIRMED" not in detail

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID],
        completion_prober=lambda *a, **k: "pong",
        auth_prober=lambda port, timeout=10.0: (
            True, "auth enforcement HELD with a named warning — the "
                  "deliberately-invalid key was DENIED service, but via a "
                  "crash (HTTP 500) rather than a clean 4xx: the LiteLLM "
                  "no-DB prisma quirk"))
    assert ok is True, "a crash-500 denial must not fail a serving confirm"
    assert "completion CONFIRMED" in detail, \
        "the 5xx-warn may only ever ride a passed completion rung"
    assert "DENIED service" in detail and "prisma" in detail

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID],
        completion_prober=lambda *a, **k: "pong",
        auth_prober=lambda port, timeout=10.0: (
            True, "auth enforcement VERIFIED — a deliberately-invalid key "
                  "was rejected with HTTP 401"))
    assert ok is True and "auth enforcement VERIFIED" in detail

    def never(port, timeout=10.0):  # pragma: no cover - the pin
        raise AssertionError("the listing-only legacy shape must not probe auth")

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1, auth_prober=never)
    assert ok is True and "auth" not in detail


def test_a_down_gateway_never_surfaces_the_5xx_warn_green(
    gw: ModuleType,
) -> None:
    """The iteration-5b auditor pin, explicit: the 5xx-warn may only read as
    'enforced' in a confirm whose real-key completion rung PASSED in the
    same run. When the completion rung fails, the auth rung never fires —
    so a down/broken gateway (whose crash-500s an auth prober would grade
    as a warn) can never ride the warning to a green confirm."""
    def warn_never_reached(port, timeout=10.0):  # pragma: no cover - the pin
        raise AssertionError(
            "the auth rung must never fire when the completion rung failed")

    def completion_down(*a, **k):
        raise ValueError("connection refused — the gateway is down")

    ok, detail = gw.confirm_gateway_serving(
        4000, "sk-m", [gw.SECONDARY_ALIAS], attempts=1,
        completion_models=[gw.SPAWN_ALIAS_MODEL_ID],
        completion_prober=completion_down,
        auth_prober=warn_never_reached)
    assert ok is False
    assert "completion hop FAILED" in detail
    assert "warning" not in detail and "prisma" not in detail
    assert "CONFIRMED" not in detail


def test_master_key_never_rotates_on_reinstall(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """11d: a re-install preserves an existing CT6_GATEWAY_MASTER_KEY
    byte-identically — rotation would invalidate the settings.json
    ANTHROPIC_AUTH_TOKEN every live session depends on (the deploy-4
    aftermath class). Rotation exists only as a hypothetical future explicit
    flag; no flag today. preserved_env_keys covers the master key, and even a
    provider SWITCH re-install carries it forward."""
    assert gw.MASTER_KEY_VAR in gw.preserved_env_keys()
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    first = gw.read_env_file(base / gw.ENV_FILE_NAME)[gw.MASTER_KEY_VAR]
    assert first.startswith("sk-ct6-")
    # plain re-install
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)[gw.MASTER_KEY_VAR] == first
    # provider-switch re-install
    assert _install(gw, base, "--secondary", "openai",
                    "--openai-key", RAW_OPENAI_KEY) == 0
    assert gw.read_env_file(base / gw.ENV_FILE_NAME)[gw.MASTER_KEY_VAR] == first
    # the pure resolver preserves it too
    resolved = gw.resolve_keys(base, secondary_provider="zai", env={})
    assert resolved[gw.MASTER_KEY_VAR] == first


def test_install_replays_the_zombie_race_escape(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """THE SR-glm-fix-iter5 escape replayed end-to-end at the install call
    site: an owned env-broken zombie sibling + an owned serving instance on a
    stale state. The install must sweep the zombie BEFORE any start (no
    zombie left to race), keep-not-blind-start over the serving instance,
    verified-restart it (stale served state), verify the new instance OWNS
    the port, and go green only with auth provably enforced — ending at
    exactly ONE owned instance. Iteration 6: the /model/info fake is
    PORT-aware — the staged replacement on the staging port serves the
    regenerated config (staging-green sanctions the cutover) while the live
    port answers stale until the serving survivor is stopped."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    capsys.readouterr()
    runner = _ProcessAwareRunner(base, processes={
        ZOMBIE_PID: (_owned_cmd(base, "upper"), "python.exe"),
        SERVING_PID: (_owned_cmd(base), "litellm.exe"),
    }, holder_pid=SERVING_PID)
    monkeypatch.setattr(gw, "_default_runner", runner)
    probed: list[str] = []
    staging_port = gw.DEFAULT_PORT + gw.STAGING_PORT_OFFSET

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        probed.append(model)
        return "ok"

    healed = _model_info_matching_config(gw, base, "zai")

    def model_info(port, key, timeout=5.0):
        if port == staging_port:  # the staged replacement serves correctly
            return healed(port, key, timeout)
        serving_killed = any(
            c[:3] == ["taskkill", "/pid", str(SERVING_PID)]
            for c in runner.calls)
        if not serving_killed:  # the stale survivor still answers
            return _stale_served_deployments(gw)
        return healed(port, key, timeout)

    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", str(ZOMBIE_PID), "/f"],
                     ["taskkill", "/pid", str(SERVING_PID), "/t", "/f"]], \
        ("the zombie sweep precedes the port-holder stop; nothing else "
         "killed — and the two stop predicates differ (iteration 7 pin 1): "
         "the SWEEP kills per-pid (no /t — a tree link the enumeration "
         "missed must never cascade into the listener) while the DELIBERATE "
         "cutover stop takes the holder's whole tree (/t)")
    assert (_first_index(runner.calls, ["taskkill"])
            < _first_index(runner.calls, ["schtasks", "/run"])), \
        "no start fires while the zombie population exists"
    assert len([c for c in runner.calls if c[:2] == ["schtasks", "/run"]]) == 1
    assert f"stopped owned instance pid {ZOMBIE_PID}" in out
    assert (f"start skipped — an owned instance already serves port 4000 "
            f"(pid {SERVING_PID}") in out
    assert "STALE" in out
    assert "bind VERIFIED" in out
    assert (f"bound by the just-launched instance (pid {LAUNCHED_PID}, "
            f"launch-window match)") in out
    assert f"completion CONFIRMED via {gw.SPAWN_ALIAS_MODEL_ID}" in out
    assert "auth enforcement VERIFIED" in out
    assert gw.SECONDARY_ALIAS not in probed
    assert set(runner.processes) == {LAUNCHED_PID}, \
        "the exactly-one-instance invariant holds end-to-end"


# ---- v3.41.0 iteration 6 (SR-glm-fix-iter6, USER MANDATE 2 — the 2026-07-18
# OFFLINE incident): verify-then-swap, never dark -----------------------------------
#
# Every deploy was stop-then-start on the LIVE port — the one every active
# Claude session routes through — so each deploy opened a dark window and a
# port race, and the winner among 8 piled-up instances (all entered through
# run_gateway.bat) had an UNRESOLVED CT6_GATEWAY_MASTER_KEY: LiteLLM's DB-less
# auth fallback answered every request 400 no_db_connection and the user's
# sessions went OFFLINE. Closed by: (12a) the replacement is PROVEN on a
# staging port through the FULL ladder (bind + served-state + staging-bind
# ownership + REAL-key completion with upstream identity + auth enforcement —
# rung conjunction structurally proves config AND env health) BEFORE the
# serving instance is touched, with the staged instance stopped on ALL exit
# paths (the B4 auditor's REQUIRED pin) and a bounded post-cutover re-verify;
# (12b) the generated launcher refuses to launch over ITS OWN already-
# LISTENING port (naming the holder pid) and logs masked master-key presence
# (first 8 chars or MISSING) before exec; (12c) the recovery procedure is
# codified in README troubleshooting + the confirm failure hints.

STAGING_PID = 30001        # the pid the staged replacement gets in the model
FOREIGN_SQUATTER_PID = 40404


class _SwapAwareRunner:
    """The iteration-6 model: the _ProcessAwareRunner process/port model
    extended with a STAGING port and a spawner hook. Spawning the staging
    launcher (any command naming run_gateway_staging) creates the staged
    instance — an OWNED process (its cmdline carries this state dir's
    config path) that binds the staging port when ``staging_binds`` (or
    loses the bind race to ``staging_race_winner_pid``); ``taskkill``
    removes any pid and frees whichever port it holds; ``schtasks /run``
    launches the live replacement exactly as the iteration-5 model does.
    ``spawn`` appends to the same ``calls`` list, so staging/stop/start
    ordering is assertable end-to-end."""

    def __init__(self, base: Path, port: int = 4000,
                 staging_port: int | None = None,
                 processes: dict[int, tuple[str, str]] | None = None,
                 holder_pid: int | None = None,
                 staging_holder_pid: int | None = None,
                 launch_pid: int = LAUNCHED_PID,
                 staging_pid: int = STAGING_PID,
                 staging_binds: bool = True,
                 staging_race_winner_pid: int | None = None,
                 race_winner_pid: int | None = None,
                 kill_rc: int = 0,
                 kill_err: str = "ERROR: Access is denied.") -> None:
        self.base = base
        self.port = port
        self.staging_port = staging_port if staging_port is not None else port + 1
        self.processes = dict(processes or {})  # pid -> (cmdline, image)
        self.holder_pid = holder_pid
        self.staging_holder = staging_holder_pid
        self.launch_pid = launch_pid
        self.staging_pid = staging_pid
        self.staging_binds = staging_binds
        self.staging_race_winner_pid = staging_race_winner_pid
        self.race_winner_pid = race_winner_pid
        self.kill_rc = kill_rc
        self.kill_err = kill_err
        self.calls: list[list[str]] = []

    def spawn(self, cmd, **kwargs):  # the _default_spawner hook
        cmd = list(cmd)
        self.calls.append(cmd)
        if any("run_gateway_staging" in str(part) for part in cmd):
            cfg = str(self.base / "config.yaml")
            self.processes[self.staging_pid] = (
                f'"C:\\py\\Scripts\\litellm" --config "{cfg}" '
                f"--port {self.staging_port}", "litellm.exe")
            if self.staging_race_winner_pid is not None:
                self.staging_holder = self.staging_race_winner_pid
            elif self.staging_binds:
                self.staging_holder = self.staging_pid

    def __call__(self, cmd, **kwargs):  # noqa: ANN001
        cmd = list(cmd)
        self.calls.append(cmd)
        rc, out, err = 0, "", ""
        if cmd[0] == "powershell":
            out = "".join(_cim_row(pid, entry)
                          for pid, entry in sorted(self.processes.items()))
        elif cmd[0] == "netstat":
            rows = ["", "Active Connections", "",
                    "  Proto  Local Address          Foreign Address"
                    "        State           PID",
                    "  TCP    0.0.0.0:135            0.0.0.0:0        "
                    "      LISTENING       1084"]
            if self.holder_pid is not None:
                rows.append(
                    f"  TCP    127.0.0.1:{self.port}         0.0.0.0:0"
                    f"              LISTENING       {self.holder_pid}")
            if self.staging_holder is not None:
                rows.append(
                    f"  TCP    127.0.0.1:{self.staging_port}         0.0.0.0:0"
                    f"              LISTENING       {self.staging_holder}")
            out = "\n".join(rows) + "\n"
        elif cmd[0] == "tasklist":
            pid = int(cmd[2].split()[-1])
            image = self.processes.get(pid, ("", "ghost.exe"))[1]
            out = f'"{image}","{pid}","Console","1","123,456 K"\n'
        elif cmd[0] == "taskkill":
            rc = self.kill_rc
            if rc == 0:
                pid = int(cmd[2])
                self.processes.pop(pid, None)
                if pid == self.holder_pid:
                    self.holder_pid = None
                if pid == self.staging_holder:
                    self.staging_holder = None
            else:
                err = self.kill_err
        elif cmd[:2] == ["schtasks", "/run"]:
            self.processes[self.launch_pid] = (
                _owned_cmd(self.base), "litellm.exe")
            self.holder_pid = (self.race_winner_pid
                               if self.race_winner_pid is not None
                               else self.launch_pid)

        class _Res:
            returncode = rc
            stdout = out
            stderr = err

        return _Res()


def _swap_kwargs(gw: ModuleType, config: str) -> dict:
    """The iteration-6 restart context — the iteration-4/5 verification
    context PLUS the staging port + the mandatory completion model, exactly
    what the install call sites pass."""
    return dict(port=4000, master_key="sk-m", generated_config=config,
                expected_upstreams={gw.SECONDARY_ALIAS: ZAI_ROUTE,
                                    gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE},
                staging_port=4000 + gw.STAGING_PORT_OFFSET,
                completion_model=gw.SPAWN_ALIAS_MODEL_ID)


def _swap_fixture(gw: ModuleType, tmp_path: Path,
                  monkeypatch: pytest.MonkeyPatch,
                  **runner_kwargs) -> tuple[Path, str, "_SwapAwareRunner"]:
    """A live serving instance on a stale state + a healthy staging model:
    base dir with the real generated config on disk, a _SwapAwareRunner
    whose spawner hook is wired, and the PORT-aware /model/info fake (the
    staged replacement serves the generated config once bound; the live
    port answers stale while the old survivor holds it, healed after)."""
    base = tmp_path / "gw"
    base.mkdir(parents=True, exist_ok=True)
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    (base / gw.CONFIG_NAME).write_text(config, encoding="utf-8")
    runner_kwargs.setdefault("holder_pid", SERVING_PID)
    runner_kwargs.setdefault(
        "processes", {SERVING_PID: (_owned_cmd(base), "litellm.exe")})
    runner = _SwapAwareRunner(base, **runner_kwargs)
    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **k: runner.spawn(cmd))
    healed = _model_info_matching_config(gw, base, "zai")

    def model_info(port, key, timeout=5.0):
        if port == runner.staging_port:
            if runner.staging_holder is None:
                raise ConnectionRefusedError("staging port not bound")
            return healed(port, key, timeout)
        if runner.holder_pid == SERVING_PID:
            return _stale_served_deployments(gw)
        if runner.holder_pid is None:
            raise ConnectionRefusedError("live port not bound")
        return healed(port, key, timeout)

    monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    return base, config, runner


def test_staging_launcher_name_and_port_guard_keyed_on_own_port(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """12b, the B4 auditor's note pinned BOTH ways: the live launcher's port
    guard refuses on the LIVE port; a staging launcher (generated with the
    staging port) keys its guard on the STAGING port only — so a busy live
    port never refuses a legitimate staging launch, and the guard names the
    holder pid before exiting. The guard sits BEFORE env sourcing and the
    litellm exec on every platform."""
    assert gw._staging_launcher_name("run_gateway.bat") == "run_gateway_staging.bat"
    assert gw._staging_launcher_name("run_gateway.sh") == "run_gateway_staging.sh"
    _, live = gw.build_launcher("windows", tmp_path, 4000)
    _, staging = gw.build_launcher("windows", tmp_path, 4001)
    assert ":4000 .*LISTENING" in live and "REFUSING to launch" in live
    assert "exit /b 1" in live
    assert "held by pid %%p" in live, "the refusal must name the holder pid"
    assert ":4001 .*LISTENING" in staging
    assert ":4000 .*LISTENING" not in staging, \
        "the staging guard must key on the port THIS launch binds, never the live port"
    assert live.index("REFUSING to launch") < live.index("gateway.env")
    assert live.index("REFUSING to launch") < live.index("--config")
    _, sh_live = gw.build_launcher("linux", tmp_path, 4000)
    _, sh_staging = gw.build_launcher("linux", tmp_path, 4001)
    assert "lsof -ti tcp:4000" in sh_live and "REFUSING to launch" in sh_live
    assert "exit 1" in sh_live
    assert "held by pid $ct6_holder" in sh_live
    assert "lsof -ti tcp:4001" in sh_staging
    assert "lsof -ti tcp:4000" not in sh_staging
    assert sh_live.index("REFUSING to launch") < sh_live.index("gateway.env")
    assert sh_live.index("REFUSING to launch") < sh_live.index("exec ")


def test_launcher_masked_key_log_first8_or_missing(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """12b, the incident recommendation pinned: the launcher logs masked
    master-key presence AFTER sourcing gateway.env and BEFORE exec'ing
    litellm — the first 8 chars EXACTLY (never wider) when resolved, an
    explicit MISSING arm when unset (the incident's undiagnosable state:
    nothing recorded whether the env ever loaded)."""
    _, bat = gw.build_launcher("windows", tmp_path, 4000)
    assert f"%{gw.MASTER_KEY_VAR}:~0,8%" in bat
    assert f"{gw.MASTER_KEY_VAR} MISSING" in bat
    assert ":~0," not in bat.replace(":~0,8", ""), \
        "the mask must never widen beyond the first 8 chars"
    assert bat.index("gateway.env") < bat.index(":~0,8") < bat.index("--config")
    _, sh = gw.build_launcher("linux", tmp_path, 4000)
    assert "printf '%.8s'" in sh
    assert f"{gw.MASTER_KEY_VAR} MISSING" in sh
    assert sh.index("gateway.env") < sh.index("%.8s") < sh.index("exec ")


def test_verify_then_swap_green_stages_tears_down_then_cuts_over(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """12a green path at the unit level: staging launches, passes the FULL
    ladder, is torn down (the required pin's green arm), and ONLY THEN does
    the live cutover fire through the existing iteration-4/5 machinery —
    ordering pinned staging-spawn < staging-teardown < live stop < the one
    start. The post-cutover ladder re-verifies completion + auth on the live
    port, and the final population is exactly the launched instance."""
    base, config, runner = _swap_fixture(gw, tmp_path, monkeypatch)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert ok, detail
    assert "staging VERIFIED" in detail
    assert "bind VERIFIED" in detail
    assert "post-cutover ladder re-verified" in detail
    spawn_i = _first_index(runner.calls, _staging_attempts(runner.calls)[0])
    staging_kill_i = _first_index(
        runner.calls, ["taskkill", "/pid", str(STAGING_PID)])
    end_i = _first_index(runner.calls, ["schtasks", "/end"])
    live_kill_i = _first_index(
        runner.calls, ["taskkill", "/pid", str(SERVING_PID)])
    run_i = _first_index(runner.calls, ["schtasks", "/run"])
    assert spawn_i < staging_kill_i < end_i < live_kill_i < run_i, \
        "stage → verify → tear down → only then the live cutover"
    assert STAGING_PID not in runner.processes
    assert runner.staging_holder is None, "no accumulation on the staging port"
    assert set(runner.processes) == {LAUNCHED_PID}


@pytest.mark.parametrize("kind", ["bind", "served-state", "completion", "auth"])
def test_staging_failure_leaves_the_old_instance_serving(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    """12a per failure kind: ANY staging-ladder failure (bind, served-state,
    real-key completion, auth enforcement) leaves the OLD instance serving —
    no tracked stop, no live kill, no start — and fails honestly naming the
    rung; the staged instance is torn down on every failure path (the
    required pin's ladder-failure arm)."""
    base, config, runner = _swap_fixture(
        gw, tmp_path, monkeypatch, staging_binds=(kind != "bind"))
    if kind == "served-state":
        healed = _model_info_matching_config(gw, base, "zai")

        def model_info(port, key, timeout=5.0):
            if port == runner.staging_port and runner.staging_holder is not None:
                return _stale_served_deployments(gw)  # staged serve mismatched
            if port == runner.staging_port:
                raise ConnectionRefusedError("staging port not bound")
            return _stale_served_deployments(gw)

        monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    if kind == "completion":
        def completion(port, key, model, timeout=30.0, expected_upstream=None):
            if port == runner.staging_port:
                raise ValueError("HTTP 400 no_db_connection (unresolved env)")
            return "ok"

        monkeypatch.setattr(gw, "_default_completion_prober", completion)
    if kind == "auth":
        def auth(port, timeout=10.0):
            if port == runner.staging_port:
                return False, ("auth is NOT ENFORCED — the gateway ACCEPTED "
                               "a deliberately-invalid key (HTTP 200)")
            return True, "auth enforcement VERIFIED"

        monkeypatch.setattr(gw, "_default_auth_prober", auth)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert not ok
    assert "NEVER-DARK" in detail and "Staging failure" in detail
    rung_text = {
        "bind": "never answered /model/info on staging port",
        "served-state": "serves a state that does not match the generated config",
        "completion": "real-key completion rung FAILED",
        "auth": "auth-enforcement rung FAILED",
    }[kind]
    assert rung_text in detail
    # never dark: the serving instance untouched, nothing stopped or started
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/end"]]
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/run"]]
    assert not [c for c in runner.calls
                if c[:3] == ["taskkill", "/pid", str(SERVING_PID)]]
    assert runner.holder_pid == SERVING_PID and SERVING_PID in runner.processes
    # the required pin: the staged instance is stopped on the failure path
    assert STAGING_PID not in runner.processes
    assert runner.staging_holder is None, "no accumulation on the staging port"
    assert [c for c in runner.calls
            if c[:3] == ["taskkill", "/pid", str(STAGING_PID)]], \
        "the staging teardown must have stopped the staged instance"


def test_staging_teardown_fires_on_an_exception_mid_ladder(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE REQUIRED PIN's exception arm (try/finally posture): a crash
    injected mid-ladder (after the staged instance bound) still stops the
    staged instance, and the failure is honest — the serving instance was
    never touched."""
    base, config, runner = _swap_fixture(gw, tmp_path, monkeypatch)

    def exploding_auth(port, timeout=10.0):
        raise RuntimeError("injected mid-ladder crash")

    monkeypatch.setattr(gw, "_default_auth_prober", exploding_auth)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert not ok
    assert "staging ladder crashed" in detail
    assert "injected mid-ladder crash" in detail
    assert "NEVER-DARK" in detail
    assert [c for c in runner.calls
            if c[:3] == ["taskkill", "/pid", str(STAGING_PID)]], \
        "teardown must fire on the exception path too (try/finally)"
    assert STAGING_PID not in runner.processes
    assert runner.staging_holder is None
    assert runner.holder_pid == SERVING_PID and SERVING_PID in runner.processes
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/end"]]


def test_staging_preflight_foreign_squatter_fails_honestly_never_killed(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FOREIGN process already bound to the staging port is an honest
    staging failure — it is not ours to kill (the ownership-proof posture),
    the holder is named with a remediation, and the live instance keeps
    serving."""
    base, config, runner = _swap_fixture(
        gw, tmp_path, monkeypatch, staging_holder_pid=FOREIGN_SQUATTER_PID)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert not ok
    assert "NEVER-DARK" in detail
    assert "does not provably own" in detail
    assert str(FOREIGN_SQUATTER_PID) in detail
    assert not [c for c in runner.calls if c[0] == "taskkill"], \
        "a foreign staging-port holder is never killed"
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/end"]]
    assert runner.holder_pid == SERVING_PID


def test_staging_preflight_clears_owned_leaked_residue_then_stages(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An OWNED instance squatting the staging port is leaked residue from a
    prior badly-ended run (the backstop the auditor demanded stay a backstop,
    not the mechanism): the preflight clears it BY PID, then staging proceeds
    to green and the swap completes."""
    residue_pid = 555
    base, config, runner = _swap_fixture(
        gw, tmp_path, monkeypatch, staging_holder_pid=residue_pid)
    runner.processes[residue_pid] = (
        f'"C:\\py\\Scripts\\litellm" --config '
        f'"{base / "config.yaml"}" --port {runner.staging_port}',
        "litellm.exe")
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert ok, detail
    assert "cleared leaked staging residue" in detail
    assert str(residue_pid) in detail
    assert residue_pid not in runner.processes
    assert "staging VERIFIED" in detail
    assert set(runner.processes) == {LAUNCHED_PID}


def test_staging_bind_race_winner_fails_the_ownership_rung(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The B4 auditor's staging-hygiene note pinned: the iteration-5
    ownership rung applies to the STAGING bind — a pre-existing owned zombie
    stealing the staging port during the launch window must not answer the
    ladder on behalf of the staged instance; staging fails naming the
    squatter and the live instance keeps serving."""
    racer_pid = 777
    base, config, runner = _swap_fixture(
        gw, tmp_path, monkeypatch, staging_race_winner_pid=racer_pid)
    runner.processes[racer_pid] = (_owned_cmd(base, "upper"), "python.exe")
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert not ok
    assert "staging ownership rung FAILED" in detail
    assert str(racer_pid) in detail
    assert "PRE-EXISTING owned instance" in detail
    assert runner.holder_pid == SERVING_PID, "the live instance keeps serving"
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/end"]]
    # teardown still ran: the squatter holding the staging port was stopped
    # (it is OURS — an owned zombie — and it is not the live holder), and the
    # never-bound staged instance was swept as launch-window residue.
    assert runner.staging_holder is None
    assert racer_pid not in runner.processes
    assert STAGING_PID not in runner.processes


def test_cutover_retry_exhaustion_embeds_the_recovery_procedure(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staging green, but a zombie keeps winning the live bind race: cutover
    attempt 1 fails (raced), the ONE bounded retry stops the port-race
    holder via the iteration-4 port stop and tries again, the race returns —
    the honest exhaustion failure names the DARK risk and EMBEDS the
    codified recovery procedure (this is the one honest-fail path that can
    leave the box dark)."""
    racer_pid = 888
    base, config, runner = _swap_fixture(
        gw, tmp_path, monkeypatch, race_winner_pid=racer_pid)
    runner.processes[racer_pid] = (_owned_cmd(base, "fwd"), "python.exe")
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert not ok
    assert "EXHAUSTED" in detail and "DARK" in detail
    assert "RECOVERY (the 2026-07-18 offline-incident procedure)" in detail
    assert "Stop-Process" in detail, \
        "the exhaustion message embeds the kill-matching-config procedure"
    assert "run_gateway.bat / run_gateway.sh" in detail
    runs = [c for c in runner.calls if c[:2] == ["schtasks", "/run"]]
    assert len(runs) == 2, "exactly the one start + the ONE bounded retry"
    assert STAGING_PID not in runner.processes, "staging still torn down"


def test_install_deploys_never_dark_staging_green_then_cutover(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """12a green path END-TO-END at the install call site: a stale live
    process + a healthy env ⇒ the deploy stages the replacement on the
    staging port, verifies the full ladder, tears staging down, THEN swaps —
    staging-spawn < staging-teardown < live stop < the one start — and goes
    green through the spawn-mandatory confirm with exactly one owned
    instance left."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    capsys.readouterr()
    runner = _SwapAwareRunner(base, holder_pid=SERVING_PID, processes={
        SERVING_PID: (_owned_cmd(base), "litellm.exe")})
    monkeypatch.setattr(gw, "_default_runner", runner)
    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **k: runner.spawn(cmd))
    healed = _model_info_matching_config(gw, base, "zai")

    def model_info(port, key, timeout=5.0):
        if port == runner.staging_port:
            if runner.staging_holder is None:
                raise ConnectionRefusedError("staging port not bound")
            return healed(port, key, timeout)
        if runner.holder_pid == SERVING_PID:
            return _stale_served_deployments(gw)
        if runner.holder_pid is None:
            raise ConnectionRefusedError("live port not bound")
        return healed(port, key, timeout)

    monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    spawn_i = _first_index(runner.calls, _staging_attempts(runner.calls)[0])
    staging_kill_i = _first_index(
        runner.calls, ["taskkill", "/pid", str(STAGING_PID)])
    end_i = _first_index(runner.calls, ["schtasks", "/end"])
    live_kill_i = _first_index(
        runner.calls, ["taskkill", "/pid", str(SERVING_PID)])
    run_i = _first_index(runner.calls, ["schtasks", "/run"])
    assert spawn_i < staging_kill_i < end_i < live_kill_i < run_i, \
        "never-dark ordering holds end-to-end at the install call site"
    assert "staging VERIFIED" in out and "bind VERIFIED" in out
    assert f"completion CONFIRMED via {gw.SPAWN_ALIAS_MODEL_ID}" in out
    assert set(runner.processes) == {LAUNCHED_PID}
    assert runner.staging_holder is None, "no accumulation on the staging port"


def test_install_replays_the_offline_incident_bad_env_staging(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """THE 2026-07-18 offline incident replayed end-to-end: the replacement's
    env is BROKEN (unresolved CT6_GATEWAY_MASTER_KEY ⇒ LiteLLM's DB-less
    auth fallback answers the REAL key 400 no_db_connection). Staged FIRST,
    the breakage fails the staging completion rung — served-state matches
    (the config is fine; the ENV is broken — exactly what rung conjunction
    exists to catch) — and the SERVING instance is never touched: the
    sessions routing through the live port stay up, the install fails
    honestly, and the confirm failure hint carries the recovery procedure."""
    base = tmp_path / "gw"
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    capsys.readouterr()
    runner = _SwapAwareRunner(base, holder_pid=SERVING_PID, processes={
        SERVING_PID: (_owned_cmd(base), "litellm.exe")})
    monkeypatch.setattr(gw, "_default_runner", runner)
    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **k: runner.spawn(cmd))
    staging_port = gw.DEFAULT_PORT + gw.STAGING_PORT_OFFSET
    healed = _model_info_matching_config(gw, base, "zai")

    def model_info(port, key, timeout=5.0):
        if port == staging_port:
            if runner.staging_holder is None:
                raise ConnectionRefusedError("staging port not bound")
            return healed(port, key, timeout)  # config fine — env broken
        return _stale_served_deployments(gw)   # the stale live survivor

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        if port == staging_port:
            raise ValueError(
                'HTTP Error 400: {"error":{"message":"No connected db.",'
                '"type":"no_db_connection"}} — the master key never resolved '
                "in the staged instance's env")
        raise ValueError(f"served by anthropic/claude-haiku-4-5, "
                         f"expected {expected_upstream}")

    monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    assert _install(gw, base, "--secondary", "zai", "--zai-key", RAW_ZAI_KEY) == 0
    out = capsys.readouterr().out
    assert "NEVER-DARK" in out and "Staging failure" in out
    assert "real-key completion rung FAILED" in out
    assert "no_db_connection" in out
    # the serving instance was NEVER touched — the sessions stay up
    assert runner.holder_pid == SERVING_PID and SERVING_PID in runner.processes
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/end"]]
    assert not [c for c in runner.calls
                if c[:3] == ["taskkill", "/pid", str(SERVING_PID)]]
    # the bad-env staged instance did not accumulate (the required pin)
    assert STAGING_PID not in runner.processes
    assert runner.staging_holder is None
    # honest failure end-to-end: no CONFIRMED, and the failure hint carries
    # the codified recovery procedure (12c)
    assert "CONFIRMED" not in out
    assert "RECOVERY (the 2026-07-18 offline-incident procedure)" in out


# ---- v3.41.0 iteration 7 (SR-glm-fix-iter7, CRITICAL — deploy-6 darkened the
# port a SECOND time): tree-aware instances, route-aware staleness ------------
#
# Live forensics, defect A: the exactly-one sweep kept listener pid 54032
# (python.exe) and stopped pid 30828 (litellm.exe) as a non-holder — but they
# were the SAME instance (cmd → litellm.exe → python.exe); killing the parent
# killed the listener and the port went dark (the iteration-5 deploy's kill
# of 81780/9716 was the same class). Defect B: /model/info advertises the
# catch-all's wildcard expansions (23 anthropic/<id> groups on a FRESH
# instance), which the name-set diff read as unrouted extras — false stale,
# the accelerant behind the forced restarts and their race windows — while
# bare NAME matching would blind the true marker (anthropic/* matches its
# NAME; only its serving ROUTE contradicts). Closed by (13a) TREE-based
# instance identity with two pinned stop predicates (PIN 1: the sweep is
# port-holder-tree IMMUNE, per-pid, no /t; the deliberate port-freeing stops
# take the holder's WHOLE tree, root-first, /t) and (13b) TWO-ARMED
# route-contradiction staleness (PIN 2: served→config with explicit-route
# precedence over catch-all expansion + config→served completeness), with
# wildcard patterns read from the generated config at comparison time.

SVCHOST_PID = 800            # the shared service parent — NEVER instance glue
TREE_ROOT_PID = 30000        # cmd.exe /c run_gateway.bat — the launcher root
TREE_MID_PID = 30828         # litellm.exe — deploy-6's killed "non-holder"
TREE_LISTENER_PID = 54032    # python.exe — deploy-6's darkened listener


def _tree_chain(base: Path, root: int = TREE_ROOT_PID,
                mid: int = TREE_MID_PID,
                listener: int = TREE_LISTENER_PID,
                t0: int = 1000) -> dict[int, tuple]:
    """The deploy-6 forensic chain as RICH population entries (cmdline,
    image, ppid, created): svchost (un-affiliated service parent) →
    cmd /c run_gateway.bat (affiliated root) → litellm.exe (owned) →
    python.exe (owned listener)."""
    return {
        SVCHOST_PID: ("svchost.exe -k netsvcs", "svchost.exe", None, t0 - 100),
        root: (f'cmd /c "{base / "run_gateway.bat"}"', "cmd.exe",
               SVCHOST_PID, t0),
        mid: (_owned_cmd(base), "litellm.exe", root, t0 + 10),
        listener: (_owned_cmd(base), "python.exe", mid, t0 + 20),
    }


def _rich_table(processes: dict[int, tuple]) -> list[tuple]:
    """A population as ``_process_table`` rows (pid, ppid, created, cmdline)."""
    return [(pid, entry[2], entry[3], entry[0])
            for pid, entry in sorted(processes.items())]


def _wildcard_expansion_rows(n: int = 23) -> list[dict]:
    """The catch-all's wildcard-ADVERTISED expansions exactly as deploy-6's
    /model/info listed them: concrete anthropic/<id> groups whose serving
    route IS their own expansion (23 in the live forensics)."""
    return [{"model_name": f"anthropic/claude-syn-{i}",
             "litellm_params": {"model": f"anthropic/claude-syn-{i}"},
             "model_info": {"id": f"dep-wild-{i}"}} for i in range(n)]


def test_process_rows_parse_rich_legacy_and_pin_the_cim_columns(
    gw: ModuleType,
) -> None:
    """The iteration-7 process-row parsers pinned: rich four-field rows carry
    ppid + creation (a cmdline pipe survives the three-split), empty tree
    fields parse as None, and legacy two-field rows still parse as one-node
    trees — the graceful pre-iteration-7 degradation, never a guessed tree.
    The CIM command itself must request ParentProcessId + CreationDate as a
    sortable ordinal — dropping either would silently blind tree identity."""
    win = ("88|77|123456|cmd /c a | b\n"
           "99|| |python.exe run.py\n"
           "1234|litellm --config C:/gw/config.yaml --port 4000\n"
           "notpid|junk\n"
           "no separator line\n")
    assert gw._windows_process_rows(win) == [
        (88, 77, 123456, "cmd /c a | b"),
        (99, None, None, "python.exe run.py"),
        (1234, None, None, "litellm --config C:/gw/config.yaml --port 4000"),
    ]
    posix = ("  321 1 /usr/bin/litellm --config /gw/config.yaml\n"
             "  44 ps -axo pid=,ppid=,args=\n"
             "junk line\n")
    assert gw._posix_process_rows(posix) == [
        (321, 1, None, "/usr/bin/litellm --config /gw/config.yaml"),
        (44, None, None, "ps -axo pid=,ppid=,args="),
    ]
    cim = " ".join(gw._WINDOWS_PROCESS_LIST_CMD)
    assert "ParentProcessId" in cim and "CreationDate" in cim
    assert "ToFileTimeUtc" in cim, \
        "creation must be emitted as a sortable ordinal (recycled-pid links)"


def test_instance_tree_groups_the_deploy6_chain_root_first(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """13a's identity primitive on the exact forensic chain: the tree of the
    LISTENER is the whole instance root-first (cmd → litellm → python); the
    tree of the mid pid is the SAME set; the un-affiliated svchost service
    parent is never instance glue — a sibling instance launched through the
    same svchost stays a SEPARATE component — and a user's interactive shell
    (bare cmd.exe, no state-dir path in its cmdline) never joins the tree it
    launched. No table ⇒ the one-node fail-open tree."""
    base = tmp_path / "gw"
    keys = gw._affiliation_keys("windows", base)
    procs = _tree_chain(base)
    procs.update({
        41000: (f'cmd /c "{base / "run_gateway.bat"}"', "cmd.exe",
                SVCHOST_PID, 2000),
        41001: (_owned_cmd(base), "litellm.exe", 41000, 2010),
    })
    table = _rich_table(procs)
    expected = [TREE_ROOT_PID, TREE_MID_PID, TREE_LISTENER_PID]
    assert gw._instance_tree(TREE_LISTENER_PID, table, keys) == expected
    assert gw._instance_tree(TREE_MID_PID, table, keys) == expected
    assert gw._instance_tree(41001, table, keys) == [41000, 41001], \
        "two instances sharing a service parent never merge into one tree"
    shell_table = _rich_table({
        500: ("cmd.exe", "cmd.exe", None, 10),
        601: (_owned_cmd(base), "litellm.exe", 500, 20),
    })
    assert gw._instance_tree(601, shell_table, keys) == [601], \
        "an interactive shell that launched a gateway by hand never joins"
    assert gw._instance_tree(
        TREE_LISTENER_PID, None, keys) == [TREE_LISTENER_PID], \
        "no table ⇒ the one-node fail-open tree, never a guess"


def test_instance_tree_severs_recycled_pid_and_roots_orphaned_chains(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """The B4 auditor's pid-reuse note pinned: a 'parent' whose creation
    ordinal is LATER than its child's is a recycled pid — the link is
    severed and the child roots its own tree (a false join could shield a
    foreign process from the sweep or wrongly immunize/kill across
    instances). A dead root (ppid absent from the table) leaves the tree
    rooted at the surviving ancestor."""
    base = tmp_path / "gw"
    keys = gw._affiliation_keys("windows", base)
    recycled = _rich_table({
        TREE_ROOT_PID: (f'cmd /c "{base / "run_gateway.bat"}"', "cmd.exe",
                        SVCHOST_PID, 9000),  # born AFTER its 'children'
        TREE_MID_PID: (_owned_cmd(base), "litellm.exe", TREE_ROOT_PID, 1010),
        TREE_LISTENER_PID: (_owned_cmd(base), "python.exe",
                            TREE_MID_PID, 1020),
    })
    assert gw._instance_tree(TREE_LISTENER_PID, recycled, keys) == [
        TREE_MID_PID, TREE_LISTENER_PID], \
        "the recycled-pid 'parent' must not join the tree"
    assert gw._instance_tree(TREE_ROOT_PID, recycled, keys) == [TREE_ROOT_PID]
    orphaned = _rich_table({
        TREE_MID_PID: (_owned_cmd(base), "litellm.exe", 999999, 1010),
        TREE_LISTENER_PID: (_owned_cmd(base), "python.exe",
                            TREE_MID_PID, 1020),
    })
    assert gw._instance_tree(TREE_LISTENER_PID, orphaned, keys) == [
        TREE_MID_PID, TREE_LISTENER_PID], \
        "a dead cmd root leaves the tree rooted at the surviving ancestor"


def test_deploy6_replay_tree_sweep_never_darkens_the_port(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """THE deploy-6 replay (PIN 1, sweep direction): the serving instance is
    the cmd → litellm.exe(30828) → python.exe(54032, LISTENING) chain — the
    exact forensic pids. The old per-pid sweep stopped 30828 as a
    'non-holder' and the listener died with its parent; port dark; user
    offline (second occurrence — the iteration-5 deploy's kill of 81780/9716
    was the same class, retro-covered here). The tree-aware sweep stops
    NOTHING (every owned pid is in the port-holder's tree), keeps the
    relatives with an honest note, and skips the start."""
    base = tmp_path / "gw"
    runner = _ProcessAwareRunner(base, processes=_tree_chain(base),
                                 holder_pid=TREE_LISTENER_PID)
    ok, detail = gw.register_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        base=base, port=4000)
    assert ok, detail
    assert not [c for c in runner.calls if c[0] == "taskkill"], \
        "PIN 1 (sweep): never touch ANY pid in the port-holder's tree"
    assert not [c for c in runner.calls if c[:2] == ["schtasks", "/run"]]
    assert f"kept owned instance pid {TREE_MID_PID}" in detail
    assert "port-holder's process tree" in detail
    assert runner.holder_pid == TREE_LISTENER_PID, "the port never went dark"
    assert TREE_MID_PID in runner.processes
    assert TREE_LISTENER_PID in runner.processes


def test_tree_sweep_clears_a_disjoint_zombie_tree_but_not_the_serving_tree(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """The sweep still does its iteration-5 job under tree identity: a
    DISJOINT accumulated zombie instance (its own cmd → litellm → python
    chain, not holding the port) is cleared — owned members root-first,
    per-pid (never /t: a tree link the enumeration failed to see must never
    cascade into the listener) — while the serving tree is untouched."""
    base = tmp_path / "gw"
    procs = _tree_chain(base)
    procs.update({
        41000: (f'cmd /c "{base / "run_gateway.bat"}"', "cmd.exe",
                SVCHOST_PID, 2000),
        41001: (_owned_cmd(base), "litellm.exe", 41000, 2010),
        41002: (_owned_cmd(base, "fwd"), "python.exe", 41001, 2020),
    })
    runner = _ProcessAwareRunner(base, processes=procs,
                                 holder_pid=TREE_LISTENER_PID)
    ok, detail = gw.register_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        base=base, port=4000)
    assert ok, detail
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", "41001", "/f"],
                     ["taskkill", "/pid", "41002", "/f"]], \
        "owned zombie members only, root-first, per-pid — no /t on a sweep"
    assert TREE_LISTENER_PID in runner.processes
    assert TREE_MID_PID in runner.processes
    assert "stopped owned instance pid 41001" in detail
    assert "stopped owned instance pid 41002" in detail


def test_recycled_pid_zombie_is_not_shielded_by_a_false_parent_link(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """The auditor's recycled-pid fixture at the SWEEP level: an owned
    zombie whose ppid points at the LISTENER but whose creation ordinal
    PRECEDES the listener's (the 'parent' pid was recycled) must NOT join
    the serving tree — a false join would shield it from the sweep and
    reintroduce the accumulation class."""
    base = tmp_path / "gw"
    procs = _tree_chain(base)  # listener created at t0+20 = 1020
    procs[61000] = (_owned_cmd(base, "upper"), "python.exe",
                    TREE_LISTENER_PID, 900)  # 'child' born before the parent
    runner = _ProcessAwareRunner(base, processes=procs,
                                 holder_pid=TREE_LISTENER_PID)
    ok, detail = gw.register_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        base=base, port=4000)
    assert ok, detail
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/pid", "61000", "/f"]], \
        "the false-linked zombie is swept; the true tree is untouched"
    assert TREE_LISTENER_PID in runner.processes
    assert TREE_MID_PID in runner.processes


def test_cutover_stop_takes_the_holders_whole_tree_root_first(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PIN 1's second direction: the DELIBERATE port-freeing stop (the
    iteration-4 repair the cutover reuses) acts on the holder's WHOLE tree —
    root first, each member with tree-kill semantics (/t) — never a lone
    pid: stopping only the listener leaves a respawn-capable parent, and
    stopping only a parent was the deploy-6 darkening."""
    base = tmp_path / "gw"
    config = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    monkeypatch.setattr(
        gw, "_default_model_info_prober",
        lambda port, key, timeout=5.0: _served_from_config(gw, config, ZAI_ROUTE))
    runner = _ProcessAwareRunner(base, processes=_tree_chain(base),
                                 holder_pid=TREE_LISTENER_PID)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_verified_kwargs(gw, config))
    assert ok, detail
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills == [
        ["taskkill", "/pid", str(TREE_ROOT_PID), "/t", "/f"],
        ["taskkill", "/pid", str(TREE_MID_PID), "/t", "/f"],
        ["taskkill", "/pid", str(TREE_LISTENER_PID), "/t", "/f"]], \
        "the whole holder tree, root-first, tree-kill semantics"
    assert "whole process tree, root-first" in detail
    assert "bind VERIFIED" in detail


def test_teardown_staging_never_touches_the_live_holders_tree(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Iteration 7 hardens the teardown's live exclusion from a lone pid to
    the live holder's whole TREE: a live-instance relative that first
    appears inside the staging launch window (a worker the listener spawned
    mid-deploy) is launch-window residue by the OLD pid-equality rule and
    would have been swept — killing a serving-tree member is the deploy-6
    darkening. Staging fails (the incident's completion rung), the staged
    instance is torn down, and every live-tree pid — including the
    mid-window worker — survives."""
    base = tmp_path / "gw"
    worker_pid = 54033
    base_chain = _tree_chain(base)
    _, config, runner = _swap_fixture(
        gw, tmp_path, monkeypatch, processes=base_chain,
        holder_pid=TREE_LISTENER_PID)
    orig_spawn = runner.spawn

    def spawn_and_fork_worker(cmd):
        orig_spawn(cmd)
        runner.processes[worker_pid] = (
            _owned_cmd(base), "python.exe", TREE_LISTENER_PID, 1030)

    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **k: spawn_and_fork_worker(cmd))

    def completion(port, key, model, timeout=30.0, expected_upstream=None):
        raise ValueError("HTTP 400 no_db_connection (unresolved env)")

    monkeypatch.setattr(gw, "_default_completion_prober", completion)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert not ok
    assert "NEVER-DARK" in detail
    assert STAGING_PID not in runner.processes, "staging still torn down"
    assert worker_pid in runner.processes, \
        ("a live-tree member appearing during the staging window must never "
         "be swept as staging residue — killing any serving-tree member can "
         "take the listener down")
    assert TREE_LISTENER_PID in runner.processes
    assert TREE_MID_PID in runner.processes
    assert runner.holder_pid == TREE_LISTENER_PID
    kills = [c for c in runner.calls if c[0] == "taskkill"]
    assert kills and all(c[2] == str(STAGING_PID) for c in kills), \
        "only the staged instance is stopped on this teardown"


def test_config_model_routes_parses_the_real_generator_output(
    gw: ModuleType,
) -> None:
    """The route parser pinned against the REAL generator in both auth modes
    and BOTH providers — a generator shape change must break THIS test,
    never silently blind route-contradiction staleness. Wildcard patterns
    ride the same parse (provider-neutral: read from the generated config at
    comparison time, never hard-coded)."""
    sub = gw.build_gateway_config(
        gw.AUTH_MODE_SUBSCRIPTION, secondary_provider="zai")
    assert gw._config_model_routes(sub) == [
        (gw.SECONDARY_ALIAS, ZAI_ROUTE),
        (gw.SPAWN_ALIAS_MODEL_ID, ZAI_ROUTE)]
    api = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    pairs = gw._config_model_routes(api)
    assert pairs[0] == (gw.SECONDARY_ALIAS, ZAI_ROUTE)
    assert pairs[1] == (gw.SPAWN_ALIAS_MODEL_ID, ZAI_ROUTE)
    assert pairs[-1] == ("*", "anthropic/*"), \
        "the catch-all pattern is part of the parse — staleness derives its wildcard patterns from it"
    for anthropic_id in gw.ANTHROPIC_EXPLICIT_MODELS:
        if anthropic_id == gw.SPAWN_ALIAS_MODEL_ID:
            continue
        assert (anthropic_id, f"anthropic/{anthropic_id}") in pairs
    api_openai = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="openai")
    entry = gw.SECONDARY_PROVIDERS["openai"]
    openai_route = f"{entry['route_dialect']}/{entry['model']}"
    assert (gw.SPAWN_ALIAS_MODEL_ID,
            openai_route) in gw._config_model_routes(api_openai), \
        "provider-neutral: the openai spawn route parses identically"


def test_fresh_instance_wildcard_advertised_expansions_are_not_stale(
    gw: ModuleType,
) -> None:
    """THE deploy-6 false-positive replay (13b): a FRESH instance's
    /model/info lists the catch-all's 23 wildcard-advertised anthropic/<id>
    expansions; the old group-set diff read them as unrouted extras and
    forced the restarts whose race windows darkened the port. Each
    expansion's serving route agrees with the config's own catch-all
    pattern — routed, NOT stale — and a healthy long-running instance that
    has dynamically instantiated MORE concrete pass-through groups is
    equally clean (the accelerant is gone)."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    expectations = {gw.SECONDARY_ALIAS: ZAI_ROUTE,
                    gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE}
    fresh = _served_from_config(gw, config, ZAI_ROUTE) + _wildcard_expansion_rows()
    assert gw._served_state_staleness(config, fresh, expectations) is None
    long_running = fresh + _wildcard_expansion_rows(30)
    assert gw._served_state_staleness(
        config, long_running, expectations) is None


def test_genuinely_stale_marker_still_fails_under_the_catch_all(
    gw: ModuleType,
) -> None:
    """13b's no-over-correction pin: the true stale marker
    (claude-ct6-secondary, the leftover hand-edit route) is matched BY NAME
    by the anthropic/* catch-all — a bare name-pattern check would go blind
    — but its SERVING route (hosted_vllm/glm-5.2) contradicts the
    catch-all's expansion: still stale, still named, even on a served state
    that also lists the fresh wildcard expansions."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    expectations = {gw.SECONDARY_ALIAS: ZAI_ROUTE,
                    gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE}
    served = (_served_from_config(gw, config, ZAI_ROUTE)
              + _wildcard_expansion_rows()
              + [{"model_name": STALE_MARKER_GROUP,
                  "litellm_params": {"model": ZAI_ROUTE},
                  "model_info": {"id": "dep-stale-marker"}}])
    reason = gw._served_state_staleness(config, served, expectations)
    assert reason is not None and STALE_MARKER_GROUP in reason
    assert "does not route" in reason
    assert "claude-syn-0" not in reason, \
        "the fresh expansions never ride the failure"


def test_spawn_alias_explicit_route_precedence_over_catch_all(
    gw: ModuleType,
) -> None:
    """The auditor's precedence note pinned: the spawn alias's stale serving
    route (anthropic/claude-haiku-4-5) IS a consistent catch-all expansion
    of its own name — only explicit-route precedence catches the
    contradiction; without it a stale process absorbing the alias would
    read fresh and the accelerant resurrects. The healthy explicit route
    stays clean on the identical served shape."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    expectations = {gw.SECONDARY_ALIAS: ZAI_ROUTE,
                    gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE}
    healthy = (_served_from_config(gw, config, ZAI_ROUTE)
               + _wildcard_expansion_rows())
    assert gw._served_state_staleness(config, healthy, expectations) is None
    absorbed = [dict(dep, litellm_params=dict(dep["litellm_params"]))
                for dep in healthy]
    for dep in absorbed:
        if dep["model_name"] == gw.SPAWN_ALIAS_MODEL_ID:
            dep["litellm_params"]["model"] = (
                f"anthropic/{gw.SPAWN_ALIAS_MODEL_ID}")
    reason = gw._served_state_staleness(config, absorbed, expectations)
    assert reason is not None
    assert f"anthropic/{gw.SPAWN_ALIAS_MODEL_ID}" in reason
    assert ZAI_ROUTE in reason
    assert "does not route" not in reason and "does not serve" not in reason


def test_missing_explicit_group_is_stale_the_completeness_arm(
    gw: ModuleType,
) -> None:
    """PIN 2 (config→served completeness): a stale process that predates the
    spawn alias serves NO explicit claude-haiku-4-5 group — the catch-all
    silently absorbs the alias (its anthropic/claude-haiku-4-5 expansion may
    even be advertised) — and the served→config arm alone would read it
    fresh. The completeness arm names the missing explicit group."""
    config = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    expectations = {gw.SECONDARY_ALIAS: ZAI_ROUTE,
                    gw.SPAWN_ALIAS_MODEL_ID: ZAI_ROUTE}
    served = [d for d in _served_from_config(gw, config, ZAI_ROUTE)
              if d["model_name"] != gw.SPAWN_ALIAS_MODEL_ID]
    served += _wildcard_expansion_rows()
    served.append({"model_name": f"anthropic/{gw.SPAWN_ALIAS_MODEL_ID}",
                   "litellm_params": {
                       "model": f"anthropic/{gw.SPAWN_ALIAS_MODEL_ID}"},
                   "model_info": {"id": "dep-absorbed"}})
    reason = gw._served_state_staleness(config, served, expectations)
    assert reason is not None
    assert "does not serve" in reason
    assert gw.SPAWN_ALIAS_MODEL_ID in reason


def test_staging_rung_passes_on_a_fresh_wildcard_advertising_instance(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deploy-6's SECOND finding replayed at the swap level: the staging
    served-state rung listed the fresh staged instance's 23 wildcard
    expansions as unrouted extras and false-failed the never-dark path.
    With route-contradiction staleness the same served shape passes the
    rung and the swap completes green end-to-end."""
    base = tmp_path / "gw"
    base.mkdir(parents=True, exist_ok=True)
    config = gw.build_gateway_config(
        gw.AUTH_MODE_API_KEY, secondary_provider="zai")
    (base / gw.CONFIG_NAME).write_text(config, encoding="utf-8")
    runner = _SwapAwareRunner(base, holder_pid=SERVING_PID, processes={
        SERVING_PID: (_owned_cmd(base), "litellm.exe")})
    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **k: runner.spawn(cmd))
    healed = _model_info_matching_config(gw, base, "zai")

    def model_info(port, key, timeout=5.0):
        if port == runner.staging_port:
            if runner.staging_holder is None:
                raise ConnectionRefusedError("staging port not bound")
            return healed(port, key, timeout) + _wildcard_expansion_rows()
        if runner.holder_pid == SERVING_PID:
            return _stale_served_deployments(gw)
        if runner.holder_pid is None:
            raise ConnectionRefusedError("live port not bound")
        return healed(port, key, timeout) + _wildcard_expansion_rows()

    monkeypatch.setattr(gw, "_default_model_info_prober", model_info)
    ok, detail = gw.restart_gateway(
        "windows", base / "run_gateway.bat", runner=runner,
        **_swap_kwargs(gw, config))
    assert ok, detail
    assert "staging VERIFIED" in detail
    assert "post-cutover ladder re-verified" in detail
    assert set(runner.processes) == {LAUNCHED_PID}
    assert runner.staging_holder is None, "no accumulation on the staging port"
