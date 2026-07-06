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

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "setup" / "set_default_model.py"
    assert path.exists(), f"set_default_model.py missing at {path}"
    spec = importlib.util.spec_from_file_location("set_default_model_module", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
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
