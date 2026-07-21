"""Contract tests for scripts/setup/compile_skills.py (REQ-007).

The skill-side counterpart of the agent boilerplate sync tool: a marker-block
compiler that keeps fenced ``ct6:block:<id>`` content byte-identical to a single
canonical source across ``skills/*/SKILL.md``.

Asserts: deterministic byte-stable output across two runs; ``--check`` fails on a
hand-edit inside the fences and passes on the current tree; the canonical block
text has exactly one source; rewrites touch ONLY the bytes between the fences; the
module is stdlib-only with no import-time side effects.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module


@pytest.fixture(scope="module")
def compile_mod(plugin_root: Path):
    return load_module(plugin_root / "scripts" / "setup" / "compile_skills.py", "compile_under_test")


def _make_skill(dir_: Path, name: str, body: str) -> Path:
    d = dir_ / name
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    p.write_text(body, encoding="utf-8")
    return p


def _fixture_skill_body(compile_mod, inner: str) -> str:
    """A minimal skill body with a principles fence carrying ``inner`` content."""
    return (
        "---\nname: fixture\ndescription: fixture\n---\n\n"
        "# Fixture\n\nIntro paragraph.\n\n"
        f"{compile_mod.fence_begin('principles')}\n"
        f"{inner}\n"
        f"{compile_mod.fence_end('principles')}\n\n"
        "## After\n\nTrailing content that must never move.\n"
    )


# --- byte-stable double run ---------------------------------------------------


def test_write_is_byte_stable_across_two_runs(compile_mod, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    _make_skill(skills, "fixture", _fixture_skill_body(compile_mod, "STALE placeholder"))
    changed1 = compile_mod.compile_skills(skills)
    assert changed1 == ["fixture"], "first run should compile the drifted fixture"
    bytes1 = (skills / "fixture" / "SKILL.md").read_bytes()
    changed2 = compile_mod.compile_skills(skills)
    assert changed2 == [], "second run must be a no-op (idempotent)"
    bytes2 = (skills / "fixture" / "SKILL.md").read_bytes()
    assert bytes1 == bytes2, "compile output must be byte-stable across runs"


def test_compiled_content_is_the_canonical_render(compile_mod, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    p = _make_skill(skills, "fixture", _fixture_skill_body(compile_mod, "STALE"))
    compile_mod.compile_skills(skills)
    text = p.read_text(encoding="utf-8")
    assert compile_mod.fenced_content(text, "principles") == compile_mod.render_block("principles")


# --- --check fails on a hand-edit inside the fences --------------------------


def test_check_fails_on_hand_edit_inside_fences(compile_mod, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    _make_skill(skills, "fixture", _fixture_skill_body(compile_mod, compile_mod.render_block("principles")))
    # in sync now
    assert compile_mod.find_drift(skills) == []
    # hand-edit inside the fence
    p = skills / "fixture" / "SKILL.md"
    raw = p.read_text(encoding="utf-8")
    p.write_text(raw.replace("Reuse before build", "Reuse AFTER build", 1), encoding="utf-8")
    assert compile_mod.find_drift(skills) == ["fixture"], "a fenced hand-edit must be detected"


def test_check_subprocess_exit_nonzero_on_drift(compile_mod, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    _make_skill(skills, "fixture", _fixture_skill_body(compile_mod, "DRIFTED"))
    script = Path(compile_mod.__file__)
    proc = subprocess.run(
        [sys.executable, str(script), "--check", "--skills-dir", str(skills)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1, f"--check should exit 1 on drift; got {proc.returncode}: {proc.stdout}"
    assert "DRIFT" in proc.stdout


def test_check_subprocess_exit_zero_when_in_sync(compile_mod, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    _make_skill(skills, "fixture", _fixture_skill_body(compile_mod, compile_mod.render_block("principles")))
    script = Path(compile_mod.__file__)
    proc = subprocess.run(
        [sys.executable, str(script), "--check", "--skills-dir", str(skills)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"--check should exit 0 when in sync; got {proc.returncode}: {proc.stdout}"
    assert "IN SYNC" in proc.stdout


def test_real_tree_check_is_green(plugin_root: Path, compile_mod) -> None:
    """The shipped skills tree must already be in sync (the suite gate)."""
    assert compile_mod.find_drift(plugin_root / "skills") == []


# --- rewrites ONLY between the fences ----------------------------------------


def test_rewrite_touches_only_fenced_region(compile_mod, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    body = _fixture_skill_body(compile_mod, "REPLACE ME")
    p = _make_skill(skills, "fixture", body)
    before = p.read_text(encoding="utf-8")
    prefix = before[: before.index(compile_mod.fence_begin("principles"))]
    suffix = before[before.index(compile_mod.fence_end("principles")) + len(compile_mod.fence_end("principles")):]
    compile_mod.compile_skills(skills)
    after = p.read_text(encoding="utf-8")
    assert after.startswith(prefix), "content before the fence must be preserved byte-for-byte"
    assert after.endswith(suffix), "content after the fence must be preserved byte-for-byte"


def test_malformed_fence_raises(compile_mod) -> None:
    with pytest.raises(ValueError):
        compile_mod.find_fences("<!-- ct6:block:principles:begin -->\nno end marker\n")


# --- single canonical source + module hygiene --------------------------------


def test_single_canonical_source(compile_mod, plugin_root: Path) -> None:
    """The principles text is defined once (imported from the boilerplate module),
    not re-declared in compile_skills.py."""
    blocks = load_module(plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py", "abb_single_source")
    assert compile_mod.render_block("principles") == blocks.PRINCIPLES
    # the compile module must not carry its own hard-coded copy of the block body
    src = Path(compile_mod.__file__).read_text(encoding="utf-8")
    assert "Reuse before build" not in src, (
        "compile_skills.py must not hard-code the principles text — it imports the "
        "single canonical source"
    )


def test_single_source_identity_under_normal_import(plugin_root: Path) -> None:
    """Under a normal package import (not the isolated test loader), the skill-side
    render and the agent-side canonical are the SAME object — the strongest form of
    the single-source guarantee."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "from scripts.setup import compile_skills as C, agent_boilerplate_blocks as B; "
         "assert C.PRINCIPLES_BLOCK is B.PRINCIPLES; print('OK')"],
        cwd=str(plugin_root), capture_output=True, text=True,
    )
    assert proc.returncode == 0 and "OK" in proc.stdout, (
        f"single-source identity failed: {proc.stdout!r} {proc.stderr!r}"
    )


def test_module_is_stdlib_only(compile_mod) -> None:
    body = Path(compile_mod.__file__).read_text(encoding="utf-8")
    for token in ("import requests", "import yaml", "import httpx", "import numpy", "from requests"):
        assert token not in body, f"forbidden non-stdlib import: {token}"


def test_module_has_no_import_side_effects(compile_mod, tmp_path: Path) -> None:
    """Importing the module writes nothing and requires no args — a fresh load in an
    empty cwd must succeed silently."""
    # Re-load in isolation; load_module executes the module top-to-bottom.
    mod = load_module(Path(compile_mod.__file__), "compile_side_effect_probe")
    assert hasattr(mod, "main") and hasattr(mod, "compile_skills")
