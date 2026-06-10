"""Structural assertions for the v3.9.0 Uniform plugin usage discipline.

Every pipeline body must:
  - treat superpowers as a HARD dependency with a pre-flight abort gate,
  - reference the canonical ``## Uniform plugin usage (v3.9.0)`` section,
  - name all four concrete superpowers Skill invocations, and
  - apply uniform openspec gates (mini gains validate --all + archive; bug-fix
    no longer carries a bare ``openspec validate --strict`` without ``--all``).
"""
import re
from pathlib import Path

import pytest

# The four pipeline bodies this discipline standardizes.
PIPELINE_BODIES = [
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
    "ux-test-builder",
]

CANONICAL_REFERENCE = "## Uniform plugin usage (v3.9.0)"

FOUR_SUPERPOWERS_SKILLS = [
    "superpowers:brainstorming",
    "superpowers:test-driven-development",
    "superpowers:systematic-debugging",
    "superpowers:verification-before-completion",
]


def _body(plugin_root: Path, skill_name: str) -> str:
    path = plugin_root / "skills" / skill_name / "SKILL.md"
    assert path.exists(), f"{skill_name}/SKILL.md missing"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("skill_name", PIPELINE_BODIES)
def test_body_references_canonical_uniform_section(plugin_root: Path, skill_name: str) -> None:
    body = _body(plugin_root, skill_name)
    assert CANONICAL_REFERENCE in body, (
        f"{skill_name}: must reference the canonical '{CANONICAL_REFERENCE}' "
        "section in common-pipeline-conventions"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_BODIES)
def test_body_has_prerequisites_section(plugin_root: Path, skill_name: str) -> None:
    body = _body(plugin_root, skill_name)
    assert "## Plugin prerequisites (v3.9.0)" in body, (
        f"{skill_name}: must carry a '## Plugin prerequisites (v3.9.0)' section"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_BODIES)
def test_body_states_superpowers_hard_preflight_abort(plugin_root: Path, skill_name: str) -> None:
    body = _body(plugin_root, skill_name)
    lower = body.lower()
    assert "superpowers" in lower, f"{skill_name}: must name superpowers"
    assert "hard" in lower, f"{skill_name}: must state superpowers is a HARD dependency"
    assert ("abort" in lower) or ("pre-flight" in lower), (
        f"{skill_name}: must state a pre-flight check that aborts the run"
    )
    # The two canonical resolution channels must both be named.
    assert "superpowers@claude-plugins-official" in body, (
        f"{skill_name}: must name the installed_plugins.json resolution channel"
    )
    assert "superpowers:using-superpowers" in body, (
        f"{skill_name}: must name the Skill-tool resolution channel"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_BODIES)
def test_body_names_all_four_superpowers_skills(plugin_root: Path, skill_name: str) -> None:
    body = _body(plugin_root, skill_name)
    for skill in FOUR_SUPERPOWERS_SKILLS:
        assert skill in body, f"{skill_name}: must name '{skill}'"


@pytest.mark.parametrize("skill_name", PIPELINE_BODIES)
def test_body_notes_user_instruction_precedence(plugin_root: Path, skill_name: str) -> None:
    body = _body(plugin_root, skill_name)
    lower = body.lower()
    assert "precedence" in lower, f"{skill_name}: must note user-instruction precedence"
    assert ("claude.md" in lower) or ("agents.md" in lower), (
        f"{skill_name}: precedence note must name CLAUDE.md / AGENTS.md"
    )


def test_mini_has_validate_all_strict_and_archive(plugin_root: Path) -> None:
    body = _body(plugin_root, "mini-architect-team-pipeline")
    assert "openspec validate --all --strict" in body, (
        "mini: must add 'openspec validate --all --strict' at its planning/review gate"
    )
    assert "openspec archive" in body, "mini: must add 'openspec archive' at its final phase (M7)"
    # The existing fast-forward auto-merge must be preserved.
    assert "git merge --ff-only" in body, "mini: must KEEP the existing 'git merge --ff-only'"


def test_bugfix_validate_lines_all_carry_all_flag(plugin_root: Path) -> None:
    """Every 'openspec validate' line in bug-fix must put --all before --strict.

    Guards against the regressed bare 'openspec validate --strict' (without
    --all) that the v3.9.0 parity change replaced.
    """
    body = _body(plugin_root, "bug-fix-pipeline")
    validate_lines = [ln for ln in body.splitlines() if "openspec validate" in ln]
    assert validate_lines, "bug-fix: expected at least one 'openspec validate' line"
    for ln in validate_lines:
        assert "openspec validate --all --strict" in ln, (
            f"bug-fix: validate line lacks '--all' before '--strict': {ln.strip()!r}"
        )
    # No occurrence of the bare form should survive (e.g. '--strict' not preceded by '--all').
    bare = re.findall(r"openspec validate --strict", body)
    assert not bare, (
        f"bug-fix: found {len(bare)} bare 'openspec validate --strict' occurrence(s) "
        "lacking --all"
    )


def test_mini_validate_line_carries_all_flag(plugin_root: Path) -> None:
    body = _body(plugin_root, "mini-architect-team-pipeline")
    bare = re.findall(r"openspec validate --strict", body)
    assert not bare, "mini: 'openspec validate' must use '--all --strict', never a bare '--strict'"
