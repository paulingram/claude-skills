"""Unit tests for the v3.41.1 activation-drift fix.

Covers every acceptance criterion in
openspec/changes/gateway-activation-drift/coverage-map.json that is NOT already
pinned by test_replication.py:

  REQ-001 (status drift detection):
    - clean not-activated machine output unchanged (no drift text)
    - the explicit activation_drift field in the --json payload
    - token-only half-drift detection

  REQ-002 (carry-forward verify+heal):
    - verified-wording ok row (against args.port)
    - drifted+key heal row + report.activated=True + merge-preserving write
    - drifted+no-key FAIL row, never green carried-forward
    - corrupt-settings abort FAIL row (no write)
    - setup_entry display prints carried-forward only on the verified path

  REQ-003 (SessionStart activation heal):
    - dev-checkout no-op WITHOUT full injection
    - explicit-injection bypass
    - enabled-false no-op
    - subscription-mode no-op
    - dead-port no-op via injected port_probe
    - custom-BASE_URL preserved (never clobbered)
    - merge-preservation of unrelated keys (+ the agent-teams flag)
    - fail-open on corrupt/absent inputs (state, gateway.env, settings)
    - corrupt-settings abort (never overwrite a file we cannot parse)
    - half-drift token completion
    - main() heal order (activation before split)

Hermeticity: every artifact is tmp_path-sandboxed via the installer's
--settings-path + --base-dir (or CT6_GATEWAY_HOME) seams + the hook's
explicit-injection seam. The REAL ~/.claude/settings.json, the REAL
~/.architect-team/gateway/ state, and the LIVE gateway on port 4000 are NEVER
touched. No network (the port_probe is always injected). Fake keys only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


# --------------------------------------------------------------------------- #
# module loading
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def gw(plugin_root: Path) -> ModuleType:
    path = plugin_root / "scripts" / "setup" / "install_gateway.py"
    spec = importlib.util.spec_from_file_location(
        "install_gateway_fix_units_under_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["install_gateway_fix_units_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook_module(plugin_root: Path) -> ModuleType:
    path = plugin_root / "hooks" / "sessionstart-run-continuity.py"
    spec = importlib.util.spec_from_file_location(
        "sessionstart_run_continuity_fix_units_under_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _scrub_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticity: ambient enable signals must never leak into these tests."""
    for var in ("CT6_EXTERNAL_LLM", "CT6_CODEX_56_AVAILABLE",
                "CT6_GATEWAY_HOME", "OPENAI_API_KEY", "ZAI_API_KEY",
                "ANTHROPIC_API_KEY", "CT6_SECONDARY_PROVIDER"):
        monkeypatch.delenv(var, raising=False)


# --------------------------------------------------------------------------- #
# shared sandbox shape (mirrors test_replication.py's helpers)
# --------------------------------------------------------------------------- #


def _activated_state(gw: ModuleType, port: int = 4000) -> dict:
    """A gateway.json recording an ACTIVATED, split, zai-secondary machine."""
    return {
        "auth_mode": gw.AUTH_MODE_API_KEY,
        "port": port,
        "secondary_provider": "zai",
        "secondary_model": "glm-5.2",
        "secondary_alias": gw.SECONDARY_ALIAS,
        "codex_alias": gw.SECONDARY_ALIAS,
        "spawn_alias": gw.SPAWN_ALIAS_MODEL_ID,
        "spawn_alias_maps_to": "glm-5.2",
        "openai_model": None,
        "activated": True,
        "enabled": True,
        "registered": True,
        "model_policy": "secondary-split",
    }


def _seed_state_dir(gw: ModuleType, tmp_path: Path, port: int = 4000,
                    with_key: bool = True) -> Path:
    """Write a sandboxed gateway state dir (gateway.json + a fake-keyed
    gateway.env + a minimal config.yaml). Fake keys only."""
    base = tmp_path / "gw"
    base.mkdir(parents=True, exist_ok=True)
    gw._write_state(base, _activated_state(gw, port))
    env: dict[str, str] = {
        "ZAI_API_KEY": "zai-fake-key-for-units",
        "ANTHROPIC_API_KEY": "sk-fake-anthropic-key-for-units",
    }
    if with_key:
        env[gw.MASTER_KEY_VAR] = "sk-fake-ct6-master-key-for-units"
    gw.write_env_file(base / gw.ENV_FILE_NAME, env)
    (base / gw.CONFIG_NAME).write_text(
        "model_list:\n  - model_name: ct6-secondary\n    litellm_params:\n"
        "      model: hosted_vllm/glm-5.2\n",
        encoding="utf-8")
    return base


def _drifted_settings(tmp_path: Path) -> Path:
    """A settings.json holding ONLY the teams flag (the env block was dropped
    by a non-merge-preserving rewrite)."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(
        {"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}},
        indent=2), encoding="utf-8")
    return settings


def _stub_install_seams(gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
                        tmp_path: Path) -> None:
    """Stub the networked/process side seams so the install is hermetic."""
    monkeypatch.setattr(gw, "_default_runner",
                        lambda cmd, **kwargs: type("_R", (), {
                            "returncode": 0, "stdout": "", "stderr": ""})())
    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **kwargs: True)
    monkeypatch.setattr(gw, "_platform_key", lambda: "windows")
    monkeypatch.setattr(gw, "_windows_startup_dir",
                        lambda home=None: tmp_path / "_startup")
    monkeypatch.setattr(gw, "_default_models_prober",
                        lambda port, key, timeout=5.0: [])
    monkeypatch.setattr(gw, "_default_completion_prober",
                        lambda port, key, model, timeout=30.0,
                        expected_upstream=None: "ok")
    monkeypatch.setattr(gw, "_default_auth_prober",
                        lambda port, timeout=10.0: (True, "auth enforced"))
    monkeypatch.setattr(gw, "_default_model_info_prober",
                        lambda port, key, timeout=5.0: [])
    monkeypatch.setattr(gw, "CONFIRM_ATTEMPTS", 2)
    monkeypatch.setattr(gw, "CONFIRM_DELAY", 0)
    monkeypatch.setattr(gw, "RESTART_PORT_ATTEMPTS", 2)
    monkeypatch.setattr(gw, "RESTART_PORT_DELAY", 0)
    monkeypatch.setattr(gw, "RESTART_BIND_ATTEMPTS", 2)
    monkeypatch.setattr(gw, "RESTART_BIND_DELAY", 0)
    monkeypatch.setattr(gw, "litellm_installed", lambda: True)


def _tmp_agents(tmp_path: Path) -> Path:
    agents = tmp_path / "agents"
    agents.mkdir()
    for stem in ("backend", "system-architect"):
        (agents / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: fable\n---\n\nbody\n",
            encoding="utf-8")
    return agents


# --------------------------------------------------------------------------- #
# REQ-001: status drift detection
# --------------------------------------------------------------------------- #


def test_status_clean_not_activated_machine_is_unchanged(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A machine whose recorded `activated` is FALSY keeps today's output with
    NO drift text (drift text on a clean machine is a defect)."""
    base = _seed_state_dir(gw, tmp_path)
    # flip the recorded state to NOT activated (a clean install that was never
    # activated, but provisioned)
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    state["activated"] = False
    gw._write_state(base, state)
    settings = _drifted_settings(tmp_path)

    assert gw.main([
        "status", "--base-dir", str(base),
        "--settings-path", str(settings),
    ]) == 0
    out = capsys.readouterr().out.lower()
    # NO drift text on a clean machine
    for marker in ("drift", "drifted", "mismatch", "inconsistent",
                   "env block absent"):
        assert marker not in out, (
            f"clean not-activated machine printed drift text '{marker}' "
            "-- drift text must appear ONLY on genuine drift. "
            f"verbatim output:\n{out}")
    # the generic 'not applied' surface is preserved
    assert "not applied" in out


def test_status_json_payload_has_explicit_activation_drift_field(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The --json payload gains a first-class `activation_drift` field (B4
    supplement-1): the dict is hand-built, so drift must be explicit on the
    machine-readable surface, not implicit in steps[]."""
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)

    assert gw.main([
        "status", "--base-dir", str(base),
        "--settings-path", str(settings), "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "activation_drift" in payload, (
        "the --json payload has no activation_drift field -- drift must be "
        "first-class on the machine-readable surface")
    assert payload["activation_drift"] is True
    assert payload["activated"] is False


def test_status_clean_machine_json_activation_drift_is_false(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean not-activated machine's --json payload has activation_drift=false."""
    base = _seed_state_dir(gw, tmp_path)
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    state["activated"] = False
    gw._write_state(base, state)
    settings = _drifted_settings(tmp_path)

    assert gw.main([
        "status", "--base-dir", str(base),
        "--settings-path", str(settings), "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["activation_drift"] is False


def test_status_detects_token_only_half_drift(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """B4 supplement-2: a rewrite that drops ONLY the token (BASE_URL still
    ours) is half-drift — the fully-applied predicate covers it, so status
    names the drift."""
    base = _seed_state_dir(gw, tmp_path)
    port = 4000
    # half-drift settings: BASE_URL ours, token absent
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "env": {
            "ANTHROPIC_BASE_URL": gw.gateway_url(port),
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
        }
    }, indent=2), encoding="utf-8")

    assert gw.main([
        "status", "--base-dir", str(base),
        "--settings-path", str(settings),
    ]) == 0
    out = capsys.readouterr().out.lower()
    assert "drift" in out, (
        "half-drift (BASE_URL ours, token absent) was not surfaced -- the "
        "fully-applied predicate must cover token-only loss. "
        f"verbatim output:\n{out}")
    # claude_env_applied() (BASE_URL-only) would read this as True; the drift
    # detector must catch what it misses.
    assert gw.claude_env_applied(settings, port) is True
    assert gw.activation_fully_applied(settings, port) is False


def test_status_footer_uses_drifted_qualifier(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The footer prints a drift qualifier instead of the generic 'not applied'
    in the drift case only."""
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)

    assert gw.main([
        "status", "--base-dir", str(base),
        "--settings-path", str(settings),
    ]) == 0
    out = capsys.readouterr().out
    assert "Claude Code activation: DRIFTED" in out


# --------------------------------------------------------------------------- #
# REQ-002: carry-forward verify+heal
# --------------------------------------------------------------------------- #


def test_carry_forward_verified_path_names_verification(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The verified carry-forward row states the settings.json verification
    (against args.port — the served port, B4 gap-3)."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path)
    port = 4000
    # settings.json STILL carries the matching env block (verified)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {
        "ANTHROPIC_BASE_URL": gw.gateway_url(port),
        "ANTHROPIC_AUTH_TOKEN": "sk-fake-ct6-master-key-for-units",
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    }}, indent=2), encoding="utf-8")
    agents = _tmp_agents(tmp_path)

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--settings-path", str(settings), "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-units",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "verified" in out.lower(), (
        f"verified carry-forward row does not name the verification. output:\n{out}")
    assert "carried forward" in out.lower()


def test_carry_forward_verified_uses_served_port_not_stale_prior_port(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B4 gap-3: the verification uses args.port (the served port THIS install
    records), never a stale prior_state port. A prior_state port that differs
    from args.port must NOT read as verified against the stale port."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path, port=4000)
    # The install runs with --port 4001 (the new served port). settings.json
    # carries the env block for the OLD port 4000 — verifying against the stale
    # prior port would false-green; verifying against args.port (4001) catches
    # the drift and heals.
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {
        "ANTHROPIC_BASE_URL": gw.gateway_url(4000),  # the OLD port
        "ANTHROPIC_AUTH_TOKEN": "sk-fake-ct6-master-key-for-units",
    }}, indent=2), encoding="utf-8")
    agents = _tmp_agents(tmp_path)

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--port", "4001",
        "--settings-path", str(settings), "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-units",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    # The heal re-applied for the SERVED port 4001 (NOT a false-green verified
    # row against the stale 4000).
    assert "drift healed" in out.lower(), (
        f"carry-forward verified against a stale prior port instead of the "
        f"served args.port. output:\n{out}")
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == gw.gateway_url(4001)


def test_carry_forward_drifted_heals_and_sets_activated(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Drifted + readable master key → apply_claude_env heal + heal row +
    report.activated=True; the env block is re-applied merge-preservingly."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    settings = _drifted_settings(tmp_path)  # only the teams flag
    agents = _tmp_agents(tmp_path)
    port = 4000

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--settings-path", str(settings), "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-units",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "drift healed" in out.lower(), (
        f"drifted+key path did not print the heal row. output:\n{out}")
    # the env block was re-applied merge-preservingly (teams flag survives)
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == gw.gateway_url(port)
    assert data["env"]["ANTHROPIC_AUTH_TOKEN"] == "sk-fake-ct6-master-key-for-units"
    assert data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"
    # the state-write records activated=True (consent + now-genuinely-true)
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is True


def test_carry_forward_drifted_no_key_is_fail_row_never_green(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Drifted + absent persisted master key → FAIL row with remediation; no
    surface prints a green carried-forward.

    NOTE: in the normal install flow `resolve_keys` always regenerates + persists
    a master key (install_gateway.py:504), so by the time the carry-forward
    branch reads `gateway.env` the key is present. The absent-key branch is a
    DEFENSIVE safety net the design specifies for robustness (a corrupted
    gateway.env, a future caller that bypasses resolve_keys). This test forces
    the net to fire by monkeypatching `read_env_file` to omit the master key
    for the carry-forward read only — proving the FAIL row + remediation emit
    correctly and no green carried-forward prints."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    settings = _drifted_settings(tmp_path)
    agents = _tmp_agents(tmp_path)

    real_read_env_file = gw.read_env_file

    def _no_master_key(path):
        out = real_read_env_file(path)
        # strip the master key from the carry-forward read (the path the
        # carry-forward branch reads). resolve_keys has already run by then, so
        # this only affects the heal-time read.
        if path == base / gw.ENV_FILE_NAME:
            out.pop(gw.MASTER_KEY_VAR, None)
        return out

    monkeypatch.setattr(gw, "read_env_file", _no_master_key)

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--settings-path", str(settings), "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-units",
    ])
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "drift" in out, (
        f"drifted+no-key path did not name the drift. output:\n{out}")
    assert "install --activate" in out, (
        f"drifted+no-key path did not name the install --activate remediation. "
        f"output:\n{out}")
    # the settings file was NOT written (no key to write)
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "ANTHROPIC_BASE_URL" not in data.get("env", {})
    # no green carried-forward
    assert "carried forward" not in out


def test_carry_forward_corrupt_settings_aborts_never_overwrites(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B4 gap-4: a corrupt settings.json is NEVER auto-overwritten — only an
    explicit --activate may. The carry-forward path emits a FAIL row naming the
    corruption and does NOT call apply_claude_env."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    # a CORRUPT settings.json (unparseable JSON)
    settings = tmp_path / "settings.json"
    corrupt_body = "{not valid json"
    settings.write_text(corrupt_body, encoding="utf-8")
    agents = _tmp_agents(tmp_path)

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--settings-path", str(settings), "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-units",
    ])
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "unparseable" in out, (
        f"corrupt-settings path did not name the corruption. output:\n{out}")
    # the corrupt file was NOT overwritten (byte-preserved)
    assert settings.read_text(encoding="utf-8") == corrupt_body


def test_carry_forward_corrupt_settings_fail_row_surfaces_in_setup_entry(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unhealable/corrupt path surfaces the fail row via setup_entry's
    failed-steps branch (degrades the setup row to warn) — never a green
    carried-forward."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    settings = tmp_path / "settings.json"
    settings.write_text("{not valid json", encoding="utf-8")
    agents = _tmp_agents(tmp_path)

    name, status, detail = gw.setup_entry(
        enable=True, check_only=False, assume_yes=False,
        base_dir=str(base), settings_path=str(settings),
        agents_dir=str(agents), interactive=False, secondary="zai")
    assert status == "warn", (
        f"corrupt-settings path did not degrade setup_entry to warn; "
        f"status={status} detail={detail}")
    assert "unparseable" in detail.lower()


def test_setup_entry_carried_forward_only_on_verified_path(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """setup_entry's activated_display prints 'carried-forward' ONLY when
    activation_carried is genuinely verified (not on the healed path, which
    prints activated=True-shaped output via report.activated). Uses --no-register
    to avoid the live-restart probe (environmental noise unrelated to the
    carry-forward wording under test)."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    port = 4000
    # verified settings (matches the served port)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {
        "ANTHROPIC_BASE_URL": gw.gateway_url(port),
        "ANTHROPIC_AUTH_TOKEN": "sk-fake-ct6-master-key-for-units",
    }}, indent=2), encoding="utf-8")
    agents = _tmp_agents(tmp_path)

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--settings-path", str(settings), "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-units",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "carried forward" in out.lower(), (
        f"verified path did not print carried-forward wording. output:\n{out}")
    # the verified row names the settings.json verification
    assert "verified" in out.lower()


def test_setup_entry_healed_path_does_not_print_carried_forward(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The healed path prints activated=True-shaped output (via report.activated),
    NOT 'carried-forward' (carried-forward is the verified-path-only wording)."""
    _stub_install_seams(gw, monkeypatch, tmp_path)
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    settings = _drifted_settings(tmp_path)  # drifted → heal path
    agents = _tmp_agents(tmp_path)

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--settings-path", str(settings), "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-units",
    ])
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "drift healed" in out
    # the healed path does NOT print carried-forward (it prints the heal row)
    assert "carried forward" not in out


# --------------------------------------------------------------------------- #
# REQ-003: SessionStart activation heal — guards
# --------------------------------------------------------------------------- #


def _heal_args(gw: ModuleType, base: Path, settings: Path,
               port_probe=None) -> dict:
    """The explicit-injection seam kwargs for maybe_heal_activation."""
    kwargs = {
        "gateway_state_path": base / gw.STATE_NAME,
        "settings_path": settings,
    }
    if port_probe is not None:
        kwargs["port_probe"] = port_probe
    return kwargs


def test_heal_dev_checkout_no_op_without_full_injection(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dev checkout (plugin_root NOT under plugins_base) is NEVER rewritten.
    WITHOUT full injection (no gateway_state_path + settings_path), the guard
    fires and the heal is a no-op even when the drift shape exists."""
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)
    # plugin_root = a tmp_path dir NOT under any plugins_base
    dev_root = tmp_path / "dev-checkout"
    dev_root.mkdir()
    plugins_base = tmp_path / "plugins"
    plugins_base.mkdir()
    note = hook_module.maybe_heal_activation(
        plugin_root=dev_root, plugins_base=plugins_base)
    assert note == ""
    # settings.json untouched
    assert "ANTHROPIC_BASE_URL" not in json.loads(
        settings.read_text(encoding="utf-8")).get("env", {})


def test_heal_explicit_injection_bypasses_copy_guard(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """B4 gap-1i: passing BOTH gateway_state_path AND settings_path bypasses
    the installed-copy guard (programmatic consent to sandbox paths)."""
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note.strip()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"


def test_heal_enabled_false_no_op(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """State with enabled falsy → no-op (the gateway is not enabled)."""
    base = _seed_state_dir(gw, tmp_path)
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    state["enabled"] = False
    gw._write_state(base, state)
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note == ""
    assert "ANTHROPIC_BASE_URL" not in json.loads(
        settings.read_text(encoding="utf-8")).get("env", {})


def test_heal_subscription_mode_no_op(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """State with auth_mode != api-key → no-op (the env block exists only in
    api-key mode)."""
    base = _seed_state_dir(gw, tmp_path)
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    state["auth_mode"] = gw.AUTH_MODE_SUBSCRIPTION
    gw._write_state(base, state)
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note == ""


def test_heal_activated_false_no_op(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """State with activated falsy → no-op (no recorded consent to heal from)."""
    base = _seed_state_dir(gw, tmp_path)
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    state["activated"] = False
    gw._write_state(base, state)
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note == ""


@pytest.mark.parametrize(
    "flip",
    [
        pytest.param({"activated": False}, id="clears-activated"),
        pytest.param({"auth_mode": "subscription"}, id="moves-off-api-key"),
    ],
)
def test_heal_suppressed_by_recorded_state_even_on_a_live_port(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
    flip: dict,
) -> None:
    """RECORDED CONSENT — not port liveness — is the suppression seam.

    Forward-compatibility pin for the credit-exhaustion failover capability
    (fail over to Claude sign-in when the upstream key is out of credits).
    That failover deliberately un-points Claude Code by stripping the
    settings.json env block; it must not be fought by this heal on the next
    session start.

    The failover's post-state is reproduced exactly: recorded state flipped
    (either arm a failover might use), env block stripped, and the port STILL
    LIVE — a credit-dead gateway keeps binding its port, so the liveness probe
    is green and proves nothing about the upstream's ability to serve. The heal
    must stay silent on the strength of recorded state ALONE.

    If this breaks, the guard order regressed (probe hoisted above the state
    guards, or a state guard dropped) and the failover would be silently undone
    every session start — re-pointing sessions at a gateway that cannot serve.
    """
    base = _seed_state_dir(gw, tmp_path)
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    state.update(flip)
    gw._write_state(base, state)
    settings = _drifted_settings(tmp_path)

    probe_calls: list[int] = []

    def _live_probe(port: int, _timeout: float = 0.25) -> bool:
        probe_calls.append(port)
        return True  # credit-dead gateway still accepts TCP

    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings, port_probe=_live_probe))

    assert note == "", (
        "recorded state was flipped to the post-failover shape, so the heal "
        f"must be silent even on a live port; got note={note!r}")
    # The failover's work stands: the env block is still gone.
    assert "ANTHROPIC_BASE_URL" not in json.loads(
        settings.read_text(encoding="utf-8")).get("env", {})
    # And the state guards short-circuited BEFORE the probe — the ordering that
    # makes recorded state a sufficient suppression seam.
    assert probe_calls == [], (
        "state guards must short-circuit before the liveness probe; the probe "
        f"was called with {probe_calls}")


def test_heal_dead_port_no_op(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """B4 gap-2: a dead gateway is never wired in. The injected port_probe
    returns False → no-op (re-pointing sessions at a dead gateway would
    hard-break them)."""
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: False))
    assert note == ""
    assert "ANTHROPIC_BASE_URL" not in json.loads(
        settings.read_text(encoding="utf-8")).get("env", {})


def test_heal_custom_base_url_never_clobbered(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """A present-but-DIFFERENT ANTHROPIC_BASE_URL is never clobbered (a user-
    customized value wins — the same posture as remove_claude_env)."""
    base = _seed_state_dir(gw, tmp_path)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {
        "ANTHROPIC_BASE_URL": "https://custom.example.com/api",
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    }}, indent=2), encoding="utf-8")
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note == ""
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == "https://custom.example.com/api"


def test_heal_healthy_machine_no_op(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """Present-and-equal BASE_URL with token present → healthy, no-op."""
    base = _seed_state_dir(gw, tmp_path)
    port = 4000
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "ANTHROPIC_AUTH_TOKEN": "sk-fake-ct6-master-key-for-units",
    }}, indent=2), encoding="utf-8")
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note == ""


def test_heal_half_drift_completes_token(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """B4 supplement-2: BASE_URL equals ours but token absent (half-drift) →
    complete the pair (the URL is provably ours, so completing the pair is
    safe)."""
    base = _seed_state_dir(gw, tmp_path)
    port = 4000
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    }}, indent=2), encoding="utf-8")
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note.strip()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_AUTH_TOKEN"] == "sk-fake-ct6-master-key-for-units"
    # the teams flag survives
    assert data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"


def test_heal_merge_preserves_unrelated_keys(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """The heal is merge-preserving: unrelated top-level keys + unrelated env
    entries + the agent-teams flag all survive."""
    base = _seed_state_dir(gw, tmp_path)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "env": {
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
            "SOME_OTHER_VAR": "preserve-me",
        },
        "theme": "dark",
        "some_top_level": {"nested": True},
    }, indent=2), encoding="utf-8")
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note.strip()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"
    assert data["env"]["SOME_OTHER_VAR"] == "preserve-me"
    assert data["theme"] == "dark"
    assert data["some_top_level"] == {"nested": True}


def test_heal_fail_open_on_absent_state(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """Missing gateway state file → fail-open no-op."""
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(
        gateway_state_path=tmp_path / "absent-gateway.json",
        settings_path=settings,
        port_probe=lambda _p, _t=0.25: True)
    assert note == ""


def test_heal_fail_open_on_corrupt_state(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """Corrupt gateway.json → fail-open no-op."""
    base = tmp_path / "gw"
    base.mkdir()
    (base / gw.STATE_NAME).write_text("{not json", encoding="utf-8")
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(
        gateway_state_path=base / gw.STATE_NAME,
        settings_path=settings,
        port_probe=lambda _p, _t=0.25: True)
    assert note == ""


def test_heal_fail_open_on_absent_master_key(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """Absent persisted master key → fail-open no-op (unhealable; the install
    --activate path is the remediation)."""
    base = _seed_state_dir(gw, tmp_path, with_key=False)
    settings = _drifted_settings(tmp_path)
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note == ""
    assert "ANTHROPIC_BASE_URL" not in json.loads(
        settings.read_text(encoding="utf-8")).get("env", {})


def test_heal_corrupt_settings_aborts_never_overwrites(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """A corrupt existing settings.json → abort fail-open (never overwrite a
    file we cannot parse — only an explicit install --activate may)."""
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    settings = tmp_path / "settings.json"
    corrupt_body = "{not valid json"
    settings.write_text(corrupt_body, encoding="utf-8")
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note == ""
    # byte-preserved
    assert settings.read_text(encoding="utf-8") == corrupt_body


def test_heal_missing_settings_creates_it(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """A MISSING settings.json is healable (the apply step creates it)."""
    base = _seed_state_dir(gw, tmp_path, with_key=True)
    settings = tmp_path / "subdir" / "settings.json"
    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings,
        port_probe=lambda _p, _t=0.25: True))
    assert note.strip()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"


def test_heal_uses_recorded_port(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
) -> None:
    """The heal uses state.get('port', 4000) — a non-default recorded port
    flows into the BASE_URL + the port_probe argument."""
    port = 4077
    base = _seed_state_dir(gw, tmp_path, port=port)
    settings = _drifted_settings(tmp_path)
    probed: list[int] = []

    def probe(p, _t=0.25):
        probed.append(p)
        return True

    note = hook_module.maybe_heal_activation(**_heal_args(
        gw, base, settings, port_probe=probe))
    assert note.strip()
    assert probed == [port]
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == f"http://127.0.0.1:{port}"


# --------------------------------------------------------------------------- #
# REQ-003: main() wiring + heal order
# --------------------------------------------------------------------------- #


def test_main_heals_activation_before_split(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """B4 supplement-3: main() invokes the activation heal FIRST, then the
    split heal (order test-pinned — the wire heal precedes the policy heal so
    the notes read coherently on a machine recovering from both drifts)."""
    order: list[str] = []
    monkeypatch.setattr(hook_module, "maybe_heal_activation",
                        lambda *a, **kw: order.append("activation") or "")
    monkeypatch.setattr(hook_module, "maybe_heal_model_split",
                        lambda *a, **kw: order.append("split") or "")
    monkeypatch.setattr("sys.stdin", type("_S", (), {
        "isatty": lambda self: False, "read": lambda self: ""})())
    try:
        hook_module.main()
    except SystemExit:
        pass
    assert order == ["activation", "split"], (
        f"main() heal order was {order!r}, expected ['activation', 'split']")


def test_main_prints_activation_heal_note(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """main() prints the activation heal note to stdout alongside the split
    note (both reach the session context)."""
    marker = "[CT6-activation-heal-marker-from-main]"
    monkeypatch.setattr(hook_module, "maybe_heal_activation",
                        lambda *a, **kw: marker)
    monkeypatch.setattr(hook_module, "maybe_heal_model_split",
                        lambda *a, **kw: "")
    monkeypatch.setattr("sys.stdin", type("_S", (), {
        "isatty": lambda self: False, "read": lambda self: ""})())
    try:
        hook_module.main()
    except SystemExit:
        pass
    assert marker in capsys.readouterr().out
