"""Tests for scripts/setup/set_default_model.py — the uniform agent-model lever.

The v3.32.0 Fable-5 default ships every agent as ``model: fable``; this stdlib CLI
is the sanctioned, deterministic lever that rewrites the frontmatter ``model:``
field uniformly (and is the implemented Opus-4.8 fallback: ``--model opus``). These
tests exercise the lever against a throwaway copy of the real ``agents/`` directory
so they are robust to whatever the committed model state happens to be.

Module-load style mirrors tests/test_teams_mode.py: loaded via importlib, NOT a
package import.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from types import ModuleType

import pytest
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "setup" / "set_default_model.py"
    assert path.exists(), f"set_default_model.py missing at {path}"
    mod = load_module(path, "set_default_model_module")
    return mod


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load()


@pytest.fixture()
def tmp_agents(tmp_path: Path) -> Path:
    """A throwaway copy of the real agents/ directory."""
    dst = tmp_path / "agents"
    shutil.copytree(REPO_ROOT / "agents", dst)
    return dst


# --------------------------------------------------------------------------- #
# flip semantics
# --------------------------------------------------------------------------- #

def test_flip_to_opus_makes_all_uniform(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "opus")
    assert mod.distribution(tmp_agents) == {"opus": 39}


def test_flip_back_to_fable(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "opus")
    mod.set_model(tmp_agents, "fable")
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_flip_only_touches_the_model_line(mod: ModuleType, tmp_agents: Path) -> None:
    """Bodies stay byte-identical except the single frontmatter ``model:`` line."""
    # Establish a deterministic uniform baseline so every file genuinely changes
    # on the next flip regardless of the committed state.
    mod.set_model(tmp_agents, "haiku")
    baseline = {p.name: p.read_text(encoding="utf-8") for p in tmp_agents.glob("*.md")}
    mod.set_model(tmp_agents, "opus")
    for p in sorted(tmp_agents.glob("*.md")):
        before = baseline[p.name].splitlines()
        after = p.read_text(encoding="utf-8").splitlines()
        assert len(before) == len(after), f"{p.name}: line count changed"
        diffs = [i for i, (b, a) in enumerate(zip(before, after)) if b != a]
        assert len(diffs) == 1, f"{p.name}: expected exactly one changed line, got {diffs}"
        i = diffs[0]
        assert before[i].lstrip().startswith("model:"), f"{p.name}: changed line is not the model line"
        assert after[i].strip() == "model: opus", f"{p.name}: model line not rewritten"


def test_idempotent(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "opus")
    assert mod.set_model(tmp_agents, "opus") == []


def test_trailing_bytes_preserved(mod: ModuleType, tmp_agents: Path) -> None:
    """The whole-file bytes outside the model line survive a flip verbatim."""
    mod.set_model(tmp_agents, "sonnet")
    sample = sorted(tmp_agents.glob("*.md"))[0]
    before = sample.read_bytes()
    mod.set_model(tmp_agents, "opus")
    after = sample.read_bytes()
    assert before.replace(b"model: sonnet", b"model: opus", 1) == after


# --------------------------------------------------------------------------- #
# --check reporting
# --------------------------------------------------------------------------- #

def test_check_reports_uniform_fable(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    mod.set_model(tmp_agents, "fable")
    rc = mod.main(["--check", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fable: 39" in out
    assert "uniform: yes (fable)" in out


def test_check_reports_mixed(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    mod.set_model(tmp_agents, "opus")
    one = sorted(tmp_agents.glob("*.md"))[0]
    one.write_text(
        one.read_text(encoding="utf-8").replace("model: opus", "model: sonnet", 1),
        encoding="utf-8",
    )
    rc = mod.main(["--check", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "uniform: no" in out
    assert "opus: 38" in out
    assert "sonnet: 1" in out


# --------------------------------------------------------------------------- #
# validation + CLI
# --------------------------------------------------------------------------- #

def test_unknown_model_rejected_touches_nothing(mod: ModuleType, tmp_agents: Path) -> None:
    before = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    rc = mod.main(["--model", "gpt-4o", "--agents-dir", str(tmp_agents)])
    assert rc == 1
    after = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    assert before == after


def test_main_model_flip_returns_zero(mod: ModuleType, tmp_agents: Path) -> None:
    rc = mod.main(["--model", "fable", "--agents-dir", str(tmp_agents)])
    assert rc == 0
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_valid_models_are_the_four(mod: ModuleType) -> None:
    assert set(mod.VALID_MODELS) == {"fable", "opus", "sonnet", "haiku"}


def test_default_agents_dir_resolves(mod: ModuleType) -> None:
    d = mod._default_agents_dir()
    assert d.is_dir() and d.name == "agents"


# --------------------------------------------------------------------------- #
# Codex 5.6 role split (v3.35.0)
# --------------------------------------------------------------------------- #

def _model_of(agents_dir: Path, stem: str, mod: ModuleType) -> str:
    text = (agents_dir / f"{stem}.md").read_text(encoding="utf-8")
    return mod.read_model_value(text)


def test_role_map_covers_exactly_the_shipped_agents(mod: ModuleType, tmp_agents: Path) -> None:
    """Every shipped agent stem is classified, no stale stems linger, and the
    two role buckets are disjoint — a newly added agent must be classified (or
    it defaults to the fable bucket and shows up in --check as unclassified)."""
    stems = {p.stem for p in tmp_agents.glob("*.md")}
    assert set(mod.AGENT_ROLES) == stems, "AGENT_ROLES drifted from agents/*.md"
    overlap = mod.ARCHITECTURE_CONTROL_DESIGN_AGENTS & mod.DEVELOPMENT_CHECKING_TESTING_AGENTS
    assert not overlap, f"agents classified in BOTH role buckets: {overlap}"


def test_split_applies_the_role_models(mod: ModuleType, tmp_agents: Path) -> None:
    mod.apply_split(tmp_agents)
    dist = mod.distribution(tmp_agents)
    assert dist == {
        "fable": len(mod.ARCHITECTURE_CONTROL_DESIGN_AGENTS),
        mod.CODEX_MODEL: len(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS),
    }


def test_split_role_spot_checks(mod: ModuleType, tmp_agents: Path) -> None:
    """The owner directive verbatim: development + code checking + testing on
    codex; architecture + control + design on fable."""
    mod.apply_split(tmp_agents)
    for dev in ("backend", "frontend", "integration", "task-reviewer",
                "adversarial-reviewer", "qa-replayer", "test-completeness-verifier"):
        assert _model_of(tmp_agents, dev, mod) == mod.CODEX_MODEL, dev
    for arch in ("system-architect", "oracle-deriver", "mcp-design-agent",
                 "master-synthesizer", "prompt-refiner", "route-mapper"):
        assert _model_of(tmp_agents, arch, mod) == "fable", arch


def test_split_is_idempotent(mod: ModuleType, tmp_agents: Path) -> None:
    mod.apply_split(tmp_agents)
    assert mod.apply_split(tmp_agents) == []


def test_split_only_touches_the_model_line(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "haiku")
    baseline = {p.name: p.read_text(encoding="utf-8") for p in tmp_agents.glob("*.md")}
    mod.apply_split(tmp_agents)
    for p in sorted(tmp_agents.glob("*.md")):
        before = baseline[p.name].splitlines()
        after = p.read_text(encoding="utf-8").splitlines()
        assert len(before) == len(after), f"{p.name}: line count changed"
        diffs = [i for i, (b, a) in enumerate(zip(before, after)) if b != a]
        assert len(diffs) == 1, f"{p.name}: expected exactly one changed line"
        assert before[diffs[0]].lstrip().startswith("model:"), p.name


def test_apply_policy_available_applies_split(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "fable")  # deterministic baseline (the ship state)
    policy, changed = mod.apply_policy(tmp_agents, True)
    assert policy == "codex-split"
    assert sorted(changed) == sorted(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS)
    assert mod.policy_state(tmp_agents) == "codex-split"


def test_apply_policy_unavailable_restores_the_operating_model(
    mod: ModuleType, tmp_agents: Path
) -> None:
    """No codex => the current operating model: uniform fable (the Opus
    fallback where fable is unavailable stays the --model opus lever)."""
    mod.apply_split(tmp_agents)
    policy, changed = mod.apply_policy(tmp_agents, False)
    assert policy == "uniform-fable"
    assert sorted(changed) == sorted(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS)
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_policy_state_transitions(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "fable")
    assert mod.policy_state(tmp_agents) == "uniform-fable"
    mod.apply_split(tmp_agents)
    assert mod.policy_state(tmp_agents) == "codex-split"
    one = tmp_agents / "backend.md"
    one.write_text(
        one.read_text(encoding="utf-8").replace(f"model: {mod.CODEX_MODEL}", "model: haiku", 1),
        encoding="utf-8",
    )
    assert mod.policy_state(tmp_agents) == "mixed"
    mod.set_model(tmp_agents, "opus")
    assert mod.policy_state(tmp_agents) == "uniform-opus"


def test_codex_available_env_parsing(mod: ModuleType) -> None:
    for truthy in ("1", "true", "YES", " True "):
        assert mod.codex_available({mod.CODEX_ENV_VAR: truthy}) is True, truthy
    for falsy in ("0", "false", "no", ""):
        assert mod.codex_available({mod.CODEX_ENV_VAR: falsy}) is False, falsy
    assert mod.codex_available({}) is False


def test_codex_signal_from_env_is_tri_state(mod: ModuleType) -> None:
    """Truthy => True; SET-but-falsy => False (explicit unavailability); the
    var ABSENT => None (no signal — callers must leave the state untouched)."""
    assert mod.codex_signal_from_env({mod.CODEX_ENV_VAR: "1"}) is True
    assert mod.codex_signal_from_env({mod.CODEX_ENV_VAR: "0"}) is False
    assert mod.codex_signal_from_env({mod.CODEX_ENV_VAR: ""}) is False
    assert mod.codex_signal_from_env({}) is None


def test_role_for_unknown_stem_defaults_to_fable_bucket(mod: ModuleType) -> None:
    """Fail-safe: an unclassified (e.g. newly scaffolded) agent never lands on
    codex — it defaults to the architecture/control/design (fable) bucket."""
    assert mod.role_for("some-brand-new-agent") == mod.ROLE_ARCHITECTURE
    assert mod.role_for("backend") == mod.ROLE_DEVELOPMENT


def test_unclassified_stems_surface_in_check(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    (tmp_agents / "brand-new-agent.md").write_text(
        "---\nname: brand-new-agent\nmodel: fable\n---\nbody\n", encoding="utf-8"
    )
    rc = mod.main(["--check", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "unclassified" in out and "brand-new-agent" in out


def test_cli_split_codex(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    rc = mod.main(["--split", "codex", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "codex-split" in out
    assert mod.policy_state(tmp_agents) == "codex-split"


def test_cli_auto_follows_the_env_signal(
    mod: ModuleType, tmp_agents: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv(mod.CODEX_ENV_VAR, "1")
    assert mod.main(["--auto", "--agents-dir", str(tmp_agents)]) == 0
    assert mod.policy_state(tmp_agents) == "codex-split"
    monkeypatch.setenv(mod.CODEX_ENV_VAR, "0")
    assert mod.main(["--auto", "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert "uniform-fable" in out
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_cli_auto_without_signal_leaves_state_untouched(
    mod: ModuleType, tmp_agents: Path, monkeypatch, capsys
) -> None:
    """--auto with CT6_CODEX_56_AVAILABLE ABSENT is a no-op: a manually applied
    lever state (e.g. the Opus fallback for a pre-fable harness) is never
    silently clobbered back to fable."""
    monkeypatch.delenv(mod.CODEX_ENV_VAR, raising=False)
    mod.set_model(tmp_agents, "opus")  # the sanctioned manual Opus fallback state
    before = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    assert mod.main(["--auto", "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert "no availability signal" in out
    assert "untouched" in out
    assert before == {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}


def test_cli_check_reports_policy_state(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    mod.set_model(tmp_agents, "fable")
    mod.main(["--check", "--agents-dir", str(tmp_agents)])
    assert "policy: uniform-fable" in capsys.readouterr().out
    mod.apply_split(tmp_agents)
    mod.main(["--check", "--agents-dir", str(tmp_agents)])
    assert "policy: codex-split" in capsys.readouterr().out


def test_cli_codex_model_override(mod: ModuleType, tmp_agents: Path) -> None:
    rc = mod.main([
        "--split", "codex", "--codex-model", "codex-5.6-luna",
        "--agents-dir", str(tmp_agents),
    ])
    assert rc == 0
    assert _model_of(tmp_agents, "backend", mod) == "codex-5.6-luna"
    assert _model_of(tmp_agents, "system-architect", mod) == "fable"
    assert mod.policy_state(tmp_agents, "codex-5.6-luna") == "codex-split"


def test_uniform_codex_is_still_rejected(mod: ModuleType, tmp_agents: Path) -> None:
    """codex NEVER applies uniformly — architecture/control/design agents must
    stay on fable, so the uniform lever refuses the codex id."""
    before = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    rc = mod.main(["--model", mod.CODEX_MODEL, "--agents-dir", str(tmp_agents)])
    assert rc == 1
    assert before == {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
