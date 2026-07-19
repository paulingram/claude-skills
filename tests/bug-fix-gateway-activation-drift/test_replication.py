"""Replication artifact for bug gateway-activation-drift (Phase B1/B2).

Reproduces the activation-drift failure class observed live 2026-07-18->19:

ACTIVATION DRIFT (the green lie):
  "Activation" is the settings.json `env` block (`ANTHROPIC_BASE_URL` +
  `ANTHROPIC_AUTH_TOKEN` pointing at the local gateway) that
  `install_gateway.py --activate` writes merge-preservingly into
  ~/.claude/settings.json. Something rewrote settings.json
  NON-merge-preservingly and dropped the block while
  ~/.architect-team/gateway/gateway.json still recorded `activated: true`.

THREE FACETS of the bug, each pinned by one test below:

  FACET-A (status misreport): `install_gateway.py status --settings-path <X>`
  reads `claude_env_applied(settings_path, port)` -- but it prints the result
  as a bare `activated=True/False` with NO drift qualifier when the recorded
  gateway.json state says `activated: true`. EXPECTED post-fix: the surface
  names the drift explicitly (e.g. "activation DRIFTED -- gateway.json
  activated=true but settings.json env block absent"). CURRENT: it prints
  `activated=False` with no drift call-out -- a status surface that shows
  neither green nor alarm while the recorded state is a green lie.

  FACET-B (install carry-forward misreport): a plain `install` (no
  `--activate`) on a machine whose prior gateway.json records `activated:
  true` sets `report.activation_carried = True` and prints
  `activated=carried-forward; CONFIRMED serving live` -- WITHOUT ever
  verifying `claude_env_applied()` against the given `--settings-path`. The
  carry-forward path trusts the recorded state verbatim. EXPECTED post-fix:
  the carry-forward predicate verifies the env block against settings.json
  and downgrades/surfaces drift when the block is absent. CURRENT: it asserts
  carried-forward green from the recorded state alone.

  FACET-C (missing SessionStart heal): `hooks/sessionstart-run-continuity.py`
  has `maybe_heal_model_split` (re-applies the secondary role split from
  gateway state) but NO symmetric activation heal -- nothing re-applies the
  settings.json env block when gateway.json says `activated: true` and the
  block is absent. EXPECTED post-fix: a `maybe_heal_claude_env` (or
  equivalent) seam exists alongside `maybe_heal_model_split` and
  re-applies the env block merge-preservingly from gateway state, fail-open.
  CURRENT: assert-fail because no such behavior exists.

These tests FAIL against the pre-fix source (that is the replication) and
are the permanent regression contract the QA replay re-runs post-fix.

Hermeticity: every artifact is tmp_path-sandboxed via the installer's
`--settings-path` + `--base-dir` (or `CT6_GATEWAY_HOME`) seams. The REAL
~/.claude/settings.json, the REAL ~/.architect-team/gateway/ state, and the
LIVE gateway on port 4000 are NEVER touched. No network. Fake keys only.
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


REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# module loading
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def gw(plugin_root: Path) -> ModuleType:
    path = plugin_root / "scripts" / "setup" / "install_gateway.py"
    assert path.exists(), f"install_gateway.py missing at {path}"
    spec = importlib.util.spec_from_file_location(
        "install_gateway_activation_drift_under_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["install_gateway_activation_drift_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook_module(plugin_root: Path) -> ModuleType:
    path = plugin_root / "hooks" / "sessionstart-run-continuity.py"
    assert path.exists(), f"sessionstart hook missing at {path}"
    spec = importlib.util.spec_from_file_location(
        "sessionstart_run_continuity_activation_drift_under_test", path)
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
# sandbox state shape (mirrors what install_gateway's _write_state produces on
# an api-key activated + secondary-split machine -- the exact observed shape)
# --------------------------------------------------------------------------- #


def _drifted_state(gw: ModuleType, port: int = 4000) -> dict:
    """A gateway.json that records an ACTIVATED, split, zai-secondary machine
    (the green recorded state), to pair with a settings.json that has LOST the
    env block (the drifted reality)."""
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


def _drifted_settings(tmp_path: Path) -> Path:
    """A settings.json holding ONLY the teams flag -- the exact observed
    drifted shape (the env block was dropped by a non-merge-preserving
    rewrite). NO ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(
        {"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}},
        indent=2), encoding="utf-8")
    return settings


def _seed_state_dir(gw: ModuleType, tmp_path: Path, port: int = 4000
                    ) -> Path:
    """Write a sandboxed gateway state dir (gateway.json + a fake-keyed
    gateway.env + a minimal config.yaml) mirroring the install's own state-
    writing logic. Fake keys only."""
    base = tmp_path / "gw"
    base.mkdir(parents=True, exist_ok=True)
    gw._write_state(base, _drifted_state(gw, port))
    # fake-keyed gateway.env -- NEVER real keys
    gw.write_env_file(base / gw.ENV_FILE_NAME, {
        gw.MASTER_KEY_VAR: "sk-fake-ct6-master-key-for-repro",
        "ZAI_API_KEY": "zai-fake-key-for-repro",
        "ANTHROPIC_API_KEY": "sk-fake-anthropic-key-for-repro",
    })
    # minimal config.yaml so `enabled` resolves True (config-file presence)
    (base / gw.CONFIG_NAME).write_text(
        "model_list:\n  - model_name: ct6-secondary\n    litellm_params:\n"
        "      model: hosted_vllm/glm-5.2\n",
        encoding="utf-8")
    return base


# --------------------------------------------------------------------------- #
# FACET-A: status misreport (the green lie)
# --------------------------------------------------------------------------- #


def test_status_surfaces_activation_drift_explicitly(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FACET-A: `status` against a drifted state (gateway.json activated=true
    + settings.json env block absent) MUST surface activation drift
    explicitly -- NOT print a bare `activated=False` with no qualifier while
    the recorded state claims activated=true.

    Reproduces the green-lie symptom: every status surface shows green
    (recorded activated=true) while the real settings.json is drifted.
    """
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)

    # status WITHOUT --live: no probe, no network (per repo docs)
    rc = gw.main([
        "status", "--base-dir", str(base),
        "--settings-path", str(settings),
    ])
    assert rc == 0
    out = capsys.readouterr().out

    # The recorded state says activated=true; the real settings.json is drifted.
    # CURRENT (pre-fix): the surface prints `activated=False` (because
    # claude_env_applied() reads the settings file) with NO drift call-out --
    # silently contradicting the recorded `activated=true`. The two truths
    # disagree and the surface names neither the disagreement nor the drift.
    # EXPECTED (post-fix): the disagreement is surfaced explicitly.
    state = json.loads((base / gw.STATE_NAME).read_text(encoding="utf-8"))
    assert state["activated"] is True, "fixture precond: recorded activated=true"
    assert not gw.claude_env_applied(settings, 4000), (
        "fixture precond: settings.json env block is absent (drifted)")

    # The marker must DISTINGUISH drift from a plain not-activated state.
    # Generic "not applied" / "activated=False" text is emitted on EVERY
    # not-activated machine (including a clean install that was never
    # activated) -- that is NOT a drift call-out. The post-fix surface must
    # name the disagreement: recorded activated=true vs settings env block
    # absent.
    drift_markers = ("drift", "drifted", "mismatch", "inconsistent",
                     "stale activation", "activation broken", "env block absent",
                     "settings.json missing", "recorded activated",
                     "recorded true")
    assert any(m in out.lower() for m in drift_markers), (
        "status output does NOT surface activation drift explicitly -- "
        "recorded activated=True while settings.json env block is absent, "
        "but the surface reports only a bare `activated=False` / "
        "`not applied` with no drift/mismatch qualifier. "
        f"verbatim output:\n{out}")


def test_status_cli_subprocess_end_to_end_pins_the_report_surface(
    gw: ModuleType, tmp_path: Path,
) -> None:
    """FACET-A (end-to-end): at least ONE artifact executes the real CLI
    subprocess against the sandboxed state, so the report surface itself is
    pinned (not just the function-level assertion).

    Captures the verbatim green-lie output as failing evidence.
    """
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["CT6_GATEWAY_HOME"] = str(base)
    # scrub live-probe triggers from the inherited env
    for var in ("CT6_EXTERNAL_LLM", "CT6_CODEX_56_AVAILABLE",
                "OPENAI_API_KEY", "ZAI_API_KEY", "ANTHROPIC_API_KEY",
                "CT6_SECONDARY_PROVIDER", "CT6_PLUGIN_REGISTRY"):
        env.pop(var, None)

    import subprocess
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "setup"
                             / "install_gateway.py"),
         "status", "--base-dir", str(base),
         "--settings-path", str(settings)],
        capture_output=True, text=True, env=env, timeout=60,
        encoding="utf-8", errors="replace")
    out = result.stdout

    # Reproduction evidence: the surface must name the drift. Pre-fix it does
    # not -- it prints `activated=False` next to a recorded activated=true.
    drift_markers = ("drift", "drifted", "mismatch", "inconsistent",
                     "stale activation", "activation broken", "env block absent",
                     "settings.json missing", "recorded activated",
                     "recorded true")
    assert any(m in out.lower() for m in drift_markers), (
        "REAL CLI `status` output does NOT surface activation drift -- "
        "recorded gateway.json activated=True while settings.json env block "
        "is absent. Verbatim output:\n" + out
    )


# --------------------------------------------------------------------------- #
# FACET-B: install carry-forward misreport
# --------------------------------------------------------------------------- #


def test_carry_forward_verifies_claude_env_against_settings(
    gw: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FACET-B: a plain `install` (no --activate) on a machine whose recorded
    gateway.json says `activated: true` MUST verify `claude_env_applied()`
    against the given `--settings-path` before reporting the activation as
    carried-forward green.

    Reproduces the install-path green lie: a re-install reported
    "activated=carried-forward; CONFIRMED serving live" while the real
    settings.json was drifted (env block absent). The carry-forward
    predicate at install_gateway.py:3201-3209 trusts the recorded state
    verbatim and never reads settings.json.
    """
    base = _seed_state_dir(gw, tmp_path)
    settings = _drifted_settings(tmp_path)
    # a sandboxed agents dir so the install's policy_state read doesn't touch
    # the real installed plugin copy
    agents = tmp_path / "agents"
    agents.mkdir()
    for stem in ("backend", "system-architect"):
        (agents / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: fable\n---\n\nbody\n",
            encoding="utf-8")

    # stub the networked/process side seams so the install is hermetic
    monkeypatch.setattr(gw, "_default_runner",
                        lambda cmd, **kwargs: type("_R", (), {
                            "returncode": 0, "stdout": "", "stderr": ""})())
    monkeypatch.setattr(gw, "_default_spawner",
                        lambda cmd, **kwargs: True)
    monkeypatch.setattr(gw, "_platform_key", lambda: "windows")
    monkeypatch.setattr(gw, "_windows_startup_dir",
                        lambda home=None: tmp_path / "_startup")
    # no live gateway probe (no-register + the live-probe stubs stand down)
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
    # litellm presence so install_litellm() is skipped
    monkeypatch.setattr(gw, "litellm_installed", lambda: True)

    rc = gw.main([
        "install", "--base-dir", str(base), "--no-install", "--no-register",
        "--settings-path", str(settings),
        "--agents-dir", str(agents),
        "--secondary", "zai", "--zai-key", "zai-fake-key-for-repro",
    ])
    assert rc == 0
    out = capsys.readouterr().out

    # CURRENT (pre-fix): the carry-forward path sets activation_carried=True
    # from prior_state alone and prints `activated=carried-forward` with no
    # settings.json verification. EXPECTED (post-fix): the output surfaces
    # the drift (the env block is absent despite the recorded activated=true).
    drift_markers = ("drift", "drifted", "mismatch", "inconsistent",
                     "stale activation", "activation broken", "env block absent",
                     "settings.json missing", "not applied")
    assert any(m in out.lower() for m in drift_markers), (
        "install carry-forward path reports green (activated=carried-forward) "
        "from recorded state alone -- never verified claude_env_applied() "
        "against the given --settings-path, which is drifted. "
        f"verbatim output:\n{out}")


# --------------------------------------------------------------------------- #
# FACET-C: missing SessionStart heal
# --------------------------------------------------------------------------- #


def test_sessionstart_has_activation_heal_seam(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FACET-C (drift-heal E2E via explicit-injection seam): the SessionStart
    hook MUST expose `maybe_heal_activation(gateway_state_path=...,
    settings_path=..., port_probe=...)` -- symmetric to
    `maybe_heal_model_split`. Passing BOTH `gateway_state_path` AND
    `settings_path` bypasses the installed-copy guard (programmatic consent
    to sandbox paths -- B4 gap-1i). Given the drifted shape (gateway.json
    {activated:true, enabled:true, auth_mode:api-key, port:<p>} + sandbox
    gateway.env with CT6_GATEWAY_MASTER_KEY=<fake> + settings.json holding
    ONLY the agent-teams flag), the heal MUST: probe 127.0.0.1:<p> via the
    injected `port_probe` (recorded `enabled` never trusted bare -- B4
    gap-2), then merge-preservingly write ANTHROPIC_BASE_URL +
    ANTHROPIC_AUTH_TOKEN into settings.json, preserving pre-existing keys,
    and return a non-empty note.

    Reproduces the missing-heal gap: `maybe_heal_model_split` exists at
    hooks/sessionstart-run-continuity.py:136 but NO symmetric
    `maybe_heal_activation` exists, so a drifted settings.json is never
    restored at session start.
    """
    port = 4000
    base = _seed_state_dir(gw, tmp_path, port=port)
    settings = _drifted_settings(tmp_path)
    fake_master_key = "sk-fake-ct6-master-key-for-repro"

    heal_fn = getattr(hook_module, "maybe_heal_activation", None)
    assert heal_fn is not None and callable(heal_fn), (
        "SessionStart hook has NO `maybe_heal_activation` seam. "
        "`maybe_heal_model_split` heals the model split but nothing heals "
        "the settings.json env block when gateway.json says activated=true "
        "and the block is absent -- activation drift persists across "
        "session restarts."
    )

    # Explicit-injection bypass: BOTH gateway_state_path + settings_path
    # passed (programmatic consent to sandbox paths; the installed-copy
    # guard is bypassed per design C). port_probe injected True so the
    # gateway-liveness guard stands up (no real socket, no network).
    note = heal_fn(
        gateway_state_path=base / gw.STATE_NAME,
        settings_path=settings,
        port_probe=lambda _port, _timeout=0.25: True,
    )
    assert isinstance(note, str) and note.strip(), (
        "maybe_heal_activation returned no note -- it did not perform a heal "
        "on the drifted shape (recorded activated=true, settings env block "
        "absent). The explicit-injection seam must heal when the recorded "
        "state says activated and the port is live."
    )

    data = json.loads(settings.read_text(encoding="utf-8"))
    env = data.get("env", {})
    assert env.get("ANTHROPIC_BASE_URL") == f"http://127.0.0.1:{port}", (
        f"heal did not set ANTHROPIC_BASE_URL to http://127.0.0.1:{port}; "
        f"got env={env!r}"
    )
    assert env.get("ANTHROPIC_AUTH_TOKEN") == fake_master_key, (
        "heal did not set ANTHROPIC_AUTH_TOKEN to the persisted master key; "
        f"got ANTHROPIC_AUTH_TOKEN={env.get('ANTHROPIC_AUTH_TOKEN')!r}"
    )
    # merge-preservation: the agent-teams flag survives the heal
    assert env.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1", (
        "heal did not preserve the pre-existing agent-teams flag "
        "(merge-preserving write regression)."
    )
    assert gw.claude_env_applied(settings, port), (
        "claude_env_applied() does not read the healed settings as applied"
    )


def test_sessionstart_main_invokes_activation_heal(
    hook_module: ModuleType, gw: ModuleType, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """FACET-C (main()-wiring): the SessionStart hook's `main()` MUST invoke
    `maybe_heal_activation` and print its note to stdout (alongside the
    model-split heal note). Replaces the unsatisfiable
    `test_sessionstart_main_does_not_restore_drifted_env` (its HOME
    monkeypatch cannot redirect Path.home() on Windows Python 3.8+, and its
    asserted path never matched the default resolution -- B4 gap-1ii).

    Satisfiable post-fix: monkeypatch `hook_module.maybe_heal_activation`
    to return a marker note, feed main() empty stdin, assert the marker
    reaches stdout. Pre-fix: `maybe_heal_activation` does not exist, so the
    attribute lookup fails -- the test fails for the RIGHT reason (the seam
    is absent, so main() cannot be wiring it in).
    """
    marker = "[CT6-activation-heal-marker] invoked from main()"
    if getattr(hook_module, "maybe_heal_activation", None) is None:
        pytest.fail(
            "SessionStart hook has no `maybe_heal_activation` attribute -- "
            "main() cannot invoke an activation heal that does not exist. "
            "(B4 gap-1ii repair: this test now asserts the seam exists + is "
            "wired into main() via a marker-note monkeypatch.)"
        )

    monkeypatch.setattr(hook_module, "maybe_heal_activation",
                        lambda *a, **kw: marker)
    # main() reads stdin (the SessionStart payload); empty stdin is fine
    monkeypatch.setattr("sys.stdin", type("_S", (), {
        "isatty": lambda self: False, "read": lambda self: ""})())
    try:
        hook_module.main()
    except SystemExit:
        pass

    out = capsys.readouterr().out
    assert marker in out, (
        "main() did NOT invoke maybe_heal_activation (the marker note it "
        "returned did not reach stdout). The activation heal is not wired "
        "into the SessionStart main() path. "
        f"verbatim stdout:\n{out}"
    )


# --------------------------------------------------------------------------- #
# FACET-D (REQ-004) -- the ROOT CLOBBERER: the repo's own test suite
# deactivates the REAL machine.
#
# `tests/test_install_gateway.py::test_uninstall_purge_removes_state_dir`
# sandboxes --base-dir and --agents-dir but NOT --settings-path. `_cmd_uninstall`
# then resolves the DEFAULT real ~/.claude/settings.json and `remove_claude_env`
# strips ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN whenever the recorded
# BASE_URL matches the port. On CI / a never-activated machine it silently
# no-ops; on the owner's ACTIVATED machine EVERY full suite run deactivates the
# gateway. This is the root cause of BOTH observed drift incidents.
#
# The no-op-on-a-clean-machine property is exactly why this went unnoticed --
# so the replication MUST stand up an ACTIVATED sentinel. A test run against an
# already-drifted machine proves nothing.
# --------------------------------------------------------------------------- #


def _hermetic_seams(gw: ModuleType, monkeypatch: pytest.MonkeyPatch,
                    tmp_path: Path) -> None:
    """Stub every process/network seam so install+uninstall never runs a real
    schtasks/systemctl, opens a real socket, or touches the real Startup dir."""
    monkeypatch.setattr(gw, "_default_runner",
                        lambda cmd, **kwargs: type("_R", (), {
                            "returncode": 0, "stdout": "", "stderr": ""})())
    monkeypatch.setattr(gw, "_default_spawner", lambda cmd, **kwargs: True)
    monkeypatch.setattr(gw, "_platform_key", lambda: "windows")
    monkeypatch.setattr(gw, "_windows_startup_dir",
                        lambda home=None: tmp_path / "_startup")


def _activated_sentinel(tmp_path: Path, port: int = 4000) -> Path:
    """A stand-in for the REAL ~/.claude/settings.json on an ACTIVATED machine:
    the gateway env block is present and points at `port`."""
    sentinel = tmp_path / "SENTINEL-real-settings.json"
    sentinel.write_text(json.dumps({"env": {
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "ANTHROPIC_AUTH_TOKEN": "sk-fake-master-key-for-repro",
    }}, indent=2), encoding="utf-8")
    return sentinel


def test_uninstall_default_path_fallback_reaches_whatever_it_resolves(
    gw: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-004 mechanism: `uninstall` with no --settings-path resolves
    `_setup.DEFAULT_USER_SETTINGS_PATH` and strips the gateway env block from
    whatever that points at.

    This behavior is CORRECT for a real user running a real uninstall -- that
    is what uninstall is for -- so the product is not on trial here. What makes
    it dangerous is a TEST invoking it while the default still resolves the
    developer's real ~/.claude/settings.json. This test pins the blast radius
    (the fallback is live and it does strip) so the sandboxing guarantees below
    are demonstrably load-bearing rather than decorative.
    """
    sentinel = _activated_sentinel(tmp_path)
    monkeypatch.setattr(gw._setup, "DEFAULT_USER_SETTINGS_PATH", sentinel)
    _hermetic_seams(gw, monkeypatch, tmp_path)

    base = tmp_path / "gw"
    assert gw.main(["install", "--base-dir", str(base), "--no-install",
                    "--no-register"]) == 0
    # verbatim from the historical leaker's shape -- no --settings-path
    assert gw.main(["uninstall", "--base-dir", str(base), "--purge",
                    "--agents-dir", str(tmp_path / "no-agents")]) == 0

    env = json.loads(sentinel.read_text(encoding="utf-8")).get("env", {})
    assert "ANTHROPIC_BASE_URL" not in env, (
        "the default-path fallback did not reach the sentinel — if this stops "
        "being true the sandboxing below is guarding nothing")
    assert env.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1", (
        "remove_claude_env must stay merge-preserving on unrelated keys")


def test_the_historical_leaker_now_sandboxes_its_settings_path(
    plugin_root: Path,
) -> None:
    """REQ-004 (a): `test_uninstall_purge_removes_state_dir` -- the test that
    actually deactivated the owner's machine on every suite run -- must name an
    explicit --settings-path.

    Asserted at source level because the damage is invisible at runtime on any
    machine that is not currently activated, which is exactly how it survived
    undetected.
    """
    src = (plugin_root / "tests" / "test_install_gateway.py").read_text(
        encoding="utf-8")
    marker = "def test_uninstall_purge_removes_state_dir"
    start = src.find(marker)
    assert start != -1, "the historical leaker test has been renamed or removed"
    body = src[start:start + 900]
    assert "--settings-path" in body, (
        "REQ-004 REPRODUCED: test_uninstall_purge_removes_state_dir still runs "
        "a REAL uninstall without --settings-path. On an activated machine "
        "every full suite run strips the gateway env block from the real "
        "~/.claude/settings.json while gateway.json still records "
        f"activated=true. body:\n{body[:400]}")


def test_install_gateway_module_absorbs_default_settings_path(
    plugin_root: Path,
) -> None:
    """REQ-004 (b): `tests/test_install_gateway.py` must carry an autouse
    fixture that redirects the module-under-test's resolved default settings
    path to a per-test sentinel, so NO test in that module -- present or future,
    whether or not its author remembers --settings-path -- can reach the real
    file. Assert-sentinel-first: side-effect-free, and fails pre-fix."""
    src = (plugin_root / "tests" / "test_install_gateway.py").read_text(
        encoding="utf-8")
    assert "DEFAULT_USER_SETTINGS_PATH" in src, (
        "REQ-004 REPRODUCED: tests/test_install_gateway.py has NO "
        "DEFAULT_USER_SETTINGS_PATH redirect. Every test in the module that "
        "omits --settings-path resolves the REAL ~/.claude/settings.json.")


def test_conftest_carries_a_real_state_tripwire(plugin_root: Path) -> None:
    """REQ-004 (c): a session-scoped tripwire in tests/conftest.py must
    snapshot the real settings.json + gateway.json + gateway.env at suite start
    and fail LOUDLY at suite end on any mutation -- converting a future leak of
    this class, in ANY test file, into a named suite failure."""
    src = (plugin_root / "tests" / "conftest.py").read_text(encoding="utf-8")
    for needle in ("settings.json", "gateway.json", "gateway.env"):
        assert needle in src, (
            "REQ-004 REPRODUCED: tests/conftest.py has no real-state tripwire "
            f"({needle!r} never referenced). A future test that clobbers the "
            "real machine state would again go unnoticed until a user noticed "
            "their gateway had silently deactivated.")
