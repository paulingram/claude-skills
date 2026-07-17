"""Tests for hooks/sessionstart-run-continuity.py (v3.30.0).

The SessionStart resume directive: an ACTIVE active-run.json marker injects
the resume-via-Skill directive into the session context; anything else prints
nothing. Always exit 0 — this hook never blocks.
"""
from tests.helpers.module_loader import load_module
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hooks import run_continuity as rc

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "sessionstart-run-continuity.py"


def _load_module():
    mod = load_module(HOOK, "sessionstart_run_continuity")
    return mod


def _run(payload: dict | str, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop(rc.DISABLE_ENV, None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        text=True, capture_output=True, cwd=str(REPO_ROOT), env=env,
    )


def test_wired_in_hooks_json() -> None:
    data = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    entries = data["hooks"].get("SessionStart", [])
    assert entries, "no SessionStart hooks defined"
    cmds = [h["command"] for entry in entries for h in entry["hooks"]]
    assert any("sessionstart-run-continuity.py" in c for c in cmds)


def test_silent_without_marker(tmp_path: Path) -> None:
    r = _run({"cwd": str(tmp_path), "source": "startup"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_active_marker_injects_directive(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.update_marker(tmp_path, slug="my-feature", phase="Phase 5")
    r = _run({"cwd": str(tmp_path), "source": "resume"})
    assert r.returncode == 0
    assert "[CT6 run-continuity]" in r.stdout
    assert 'Skill(skill="architect-team-pipeline")' in r.stdout
    assert "my-feature" in r.stdout and "Phase 5" in r.stdout
    assert "--stand-down" in r.stdout
    assert "CT6-TEAMMATE" in r.stdout, "teammate sessions are told to ignore the notice"


def test_compact_source_sharpens_the_note(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "bug-fix-pipeline")
    r = _run({"cwd": str(tmp_path), "source": "compact"})
    assert "COMPACTED" in r.stdout
    r2 = _run({"cwd": str(tmp_path), "source": "startup"})
    assert "COMPACTED" not in r2.stdout


def test_silent_for_complete_and_stood_down(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.mark_complete(tmp_path)
    assert _run({"cwd": str(tmp_path), "source": "startup"}).stdout.strip() == ""
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.stand_down(tmp_path, "user said no pipeline")
    assert _run({"cwd": str(tmp_path), "source": "startup"}).stdout.strip() == ""


def test_kill_switch_silences(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    r = _run({"cwd": str(tmp_path), "source": "startup"}, env_extra={rc.DISABLE_ENV: "1"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_fail_open_on_garbage(tmp_path: Path) -> None:
    assert _run("{not json").returncode == 0
    assert _run({}).returncode == 0
    p = rc.marker_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{broken", encoding="utf-8")
    r = _run({"cwd": str(tmp_path), "source": "startup"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_build_directive_pure_function(tmp_path: Path) -> None:
    mod = _load_module()
    assert mod.build_directive({}) == ""
    assert mod.build_directive({"cwd": ""}) == ""
    rc.engage_marker(tmp_path, "ux-test-builder")
    out = mod.build_directive({"cwd": str(tmp_path), "source": "resume"})
    assert 'Skill(skill="ux-test-builder")' in out


# --------------------------------------------------------------------------- #
# v3.39.0 — model-split self-heal
# --------------------------------------------------------------------------- #
#
# A plugin update ships uniform-fable agent files into a fresh cache dir,
# silently reverting an applied codex role split. When the gateway state says
# the split is desired AND the hook runs from an INSTALLED plugin copy whose
# agents/ drifted, the hook re-applies the split. A dev checkout is NEVER
# rewritten; every failure path returns "" (fail-open).
#
# ADV3-1 (heal-to-recorded-alias): the heal restores the split to the alias
# the gateway STATE records as served — it never writes an alias the running
# gateway config doesn't route. A v3.40 state records `secondary_alias`
# (normally ct6-secondary); a legacy v3.39 state records only `codex_alias`
# (codex-5.6-sol) and its config.yaml routes ONLY that alias, so the heal
# RETAINS it (migration to the neutral alias happens at install time, which
# regenerates the config). No recorded alias at all => fail-open no-op.

import shutil  # noqa: E402


def _fake_installed_plugin(tmp_path: Path, model: str = "fable") -> tuple[Path, Path]:
    """A fake installed plugin copy (under a fake plugins base) carrying the
    REAL model lever + a two-agent agents/ dir, plus the plugins base."""
    plugins_base = tmp_path / "plugins"
    root = plugins_base / "cache" / "architect-team-marketplace" / "architect-team" / "9.9.9"
    (root / "agents").mkdir(parents=True)
    for stem in ("backend", "system-architect"):
        (root / "agents" / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmodel: {model}\n---\n\nbody\n", encoding="utf-8")
    (root / "scripts" / "setup").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "scripts" / "setup" / "set_default_model.py",
                root / "scripts" / "setup" / "set_default_model.py")
    return root, plugins_base


def _gateway_state(tmp_path: Path, **overrides) -> Path:
    """A v3.40-shape gateway state: split desired, neutral alias recorded."""
    state = {"activated": True, "auth_mode": "api-key",
             "model_policy": "secondary-split",
             "secondary_alias": "ct6-secondary", "codex_alias": "ct6-secondary"}
    state.update(overrides)
    path = tmp_path / "gateway.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def _legacy_gateway_state(tmp_path: Path, **overrides) -> Path:
    """A v3.39-shape state: codex-split policy, legacy alias, NO
    secondary_alias — that machine's config.yaml routes ONLY codex-5.6-sol."""
    state = {"activated": True, "auth_mode": "api-key",
             "model_policy": "codex-split", "codex_alias": "codex-5.6-sol"}
    state.update(overrides)
    path = tmp_path / "gateway.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def test_heal_reapplies_split_to_drifted_installed_copy(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)  # uniform fable = drifted
    note = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_gateway_state(tmp_path))
    assert "self-heal" in note and "re-applied" in note
    assert "model: ct6-secondary" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")
    assert "model: fable" in (
        root / "agents" / "system-architect.md").read_text(encoding="utf-8")


def test_heal_restores_the_state_recorded_alias_in_both_directions(
    tmp_path: Path,
) -> None:
    """ADV3-1: a drifted copy heals to the alias the STATE records as served.
    Legacy state => the legacy alias comes back (the machine keeps working
    against the running v3.39 config, which routes nothing else) and the note
    names the install --activate migration path; v3.40 state => agents
    carrying the legacy alias migrate to the recorded neutral alias."""
    mod = _load_module()
    # direction 1: drifted-to-uniform-fable agents + LEGACY state
    legacy = tmp_path / "legacy"
    root, plugins_base = _fake_installed_plugin(legacy)
    note = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_legacy_gateway_state(legacy))
    backend_text = (root / "agents" / "backend.md").read_text(encoding="utf-8")
    assert "model: codex-5.6-sol" in backend_text
    assert "ct6-secondary" not in backend_text, \
        "the heal must never write an alias the recorded config doesn't route"
    assert "model: fable" in (
        root / "agents" / "system-architect.md").read_text(encoding="utf-8")
    assert "codex-5.6-sol" in note and "retained" in note.lower()
    assert "install --activate" in note  # the migration remediation
    # direction 2: agents carrying the LEGACY alias + a v3.40 state
    modern = tmp_path / "modern"
    root2, plugins_base2 = _fake_installed_plugin(modern)
    backend2 = root2 / "agents" / "backend.md"
    backend2.write_text(backend2.read_text(encoding="utf-8").replace(
        "model: fable", "model: codex-5.6-sol"), encoding="utf-8")
    note2 = mod.maybe_heal_model_split(
        plugin_root=root2, plugins_base=plugins_base2,
        gateway_state_path=_gateway_state(modern))
    assert "ct6-secondary" in note2
    assert "model: ct6-secondary" in backend2.read_text(encoding="utf-8")


def test_heal_is_silent_when_agents_already_match_the_recorded_alias(
    tmp_path: Path,
) -> None:
    """Agents already on the recorded alias => silent no-op, both generations."""
    mod = _load_module()
    for label, state_fn, alias in (
            ("legacy", _legacy_gateway_state, "codex-5.6-sol"),
            ("modern", _gateway_state, "ct6-secondary")):
        case = tmp_path / label
        root, plugins_base = _fake_installed_plugin(case)
        backend = root / "agents" / "backend.md"
        backend.write_text(backend.read_text(encoding="utf-8").replace(
            "model: fable", f"model: {alias}"), encoding="utf-8")
        note = mod.maybe_heal_model_split(
            plugin_root=root, plugins_base=plugins_base,
            gateway_state_path=state_fn(case))
        assert note == "", label
        assert f"model: {alias}" in backend.read_text(encoding="utf-8"), label


def test_heal_alias_always_matches_what_the_state_says_is_served(
    tmp_path: Path,
) -> None:
    """Serving-side consistency (the ADV3-1 demanded pin): after ANY heal, the
    alias written into agents/*.md equals the alias the recorded state says
    the gateway config routes (secondary_alias, else legacy codex_alias)."""
    mod = _load_module()
    for label, state_fn in (("legacy", _legacy_gateway_state),
                            ("modern", _gateway_state)):
        case = tmp_path / label
        root, plugins_base = _fake_installed_plugin(case)
        state_path = state_fn(case)
        note = mod.maybe_heal_model_split(
            plugin_root=root, plugins_base=plugins_base,
            gateway_state_path=state_path)
        assert note != "", label
        state = json.loads(state_path.read_text(encoding="utf-8"))
        served = state.get("secondary_alias") or state.get("codex_alias")
        assert f"model: {served}" in (
            root / "agents" / "backend.md").read_text(encoding="utf-8"), label


def test_heal_noop_without_a_recorded_alias(tmp_path: Path) -> None:
    """No recorded alias at all => the heal never guesses — fail-open no-op."""
    mod = _load_module()
    # keys entirely absent
    absent = tmp_path / "absent"
    root, plugins_base = _fake_installed_plugin(absent)
    state_path = absent / "gateway.json"
    state_path.write_text(json.dumps({
        "activated": True, "auth_mode": "api-key",
        "model_policy": "secondary-split"}), encoding="utf-8")
    assert mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=state_path) == ""
    assert "model: fable" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")
    # keys present but null
    null_case = tmp_path / "null"
    root2, plugins_base2 = _fake_installed_plugin(null_case)
    assert mod.maybe_heal_model_split(
        plugin_root=root2, plugins_base=plugins_base2,
        gateway_state_path=_gateway_state(
            null_case, secondary_alias=None, codex_alias=None)) == ""
    assert "model: fable" in (
        root2 / "agents" / "backend.md").read_text(encoding="utf-8")


def test_heal_treats_a_whitespace_alias_as_absent(tmp_path: Path) -> None:
    """ADV3B-2: recorded values are trimmed BEFORE the truthiness check — a
    corrupt whitespace-only secondary_alias never masks a valid legacy
    codex_alias (the heal fires with the legacy alias), and an all-whitespace
    record reads as absent (fail-open no-op, never a literal-whitespace
    model line)."""
    mod = _load_module()
    masked = tmp_path / "masked"
    root, plugins_base = _fake_installed_plugin(masked)
    note = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_gateway_state(
            masked, secondary_alias="   ", codex_alias="codex-5.6-sol"))
    assert "codex-5.6-sol" in note
    assert "model: codex-5.6-sol" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")
    blank = tmp_path / "blank"
    root2, plugins_base2 = _fake_installed_plugin(blank)
    assert mod.maybe_heal_model_split(
        plugin_root=root2, plugins_base=plugins_base2,
        gateway_state_path=_gateway_state(
            blank, secondary_alias="   ", codex_alias=" ")) == ""
    assert "model: fable" in (
        root2 / "agents" / "backend.md").read_text(encoding="utf-8")


def test_heal_never_rewrites_a_dev_checkout(tmp_path: Path) -> None:
    """The root guard: a plugin root OUTSIDE the plugins base (a dev checkout,
    this repo itself) is never rewritten — even with a codex-split state."""
    mod = _load_module()
    root, _ = _fake_installed_plugin(tmp_path)
    note = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=tmp_path / "elsewhere",
        gateway_state_path=_gateway_state(tmp_path))
    assert note == ""
    assert "model: fable" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")


def test_heal_noop_when_state_does_not_want_the_split(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)
    for overrides in ({"model_policy": "uniform-fable"},
                      {"activated": False},
                      {"auth_mode": "subscription"}):
        note = mod.maybe_heal_model_split(
            plugin_root=root, plugins_base=plugins_base,
            gateway_state_path=_gateway_state(tmp_path, **overrides))
        assert note == "", overrides
    assert "model: fable" in (
        root / "agents" / "backend.md").read_text(encoding="utf-8")


def test_heal_noop_when_split_already_applied_or_state_missing(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)
    # missing state file => fail-open no-op
    assert mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=tmp_path / "absent.json") == ""
    # apply once, then the healed state is a silent no-op
    first = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_gateway_state(tmp_path))
    assert first != ""
    again = mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=_gateway_state(tmp_path))
    assert again == ""


def test_heal_fail_open_on_garbage_state(tmp_path: Path) -> None:
    mod = _load_module()
    root, plugins_base = _fake_installed_plugin(tmp_path)
    bad = tmp_path / "gateway.json"
    bad.write_text("{not json", encoding="utf-8")
    assert mod.maybe_heal_model_split(
        plugin_root=root, plugins_base=plugins_base,
        gateway_state_path=bad) == ""
