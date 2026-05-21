"""v0.9.8 — readme-styling skill + README freshness structural tests.

The `readme-styling` skill codifies the house bitmap aesthetic so that any
agent authoring a README produces it with the same flair — banner, gradient
dividers, box-drawing panels, ASCII flowcharts, logic maps (routing + gates),
status timeline, badges.

These tests assert (1) the skill names every required element — including the
logic-maps requirement the user explicitly asked for; (2) the plugin's own
README applies the style AND stays current — its banner version and inventory
counts must match the real plugin state, so a version bump cannot silently
leave the README stale.
"""
import json
import re
from pathlib import Path

import pytest

SKILL = ("skills", "readme-styling", "SKILL.md")
README = ("README.md",)
PLUGIN_JSON = (".claude-plugin", "plugin.json")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- the skill --------------------------------------------------------------

def test_skill_exists_and_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, SKILL).strip(), "readme-styling SKILL.md is empty"


@pytest.mark.parametrize(
    "element",
    ["banner", "divider", "panel", "flowchart", "logic map", "timeline", "badge"],
)
def test_skill_documents_every_styling_element(plugin_root: Path, element: str) -> None:
    """The skill must cover every element of the house style."""
    content = _read(plugin_root, SKILL).lower()
    assert element in content, f"readme-styling SKILL.md does not document {element!r}"


def test_skill_requires_logic_maps_with_gates(plugin_root: Path) -> None:
    """The user explicitly asked for logic maps showing routing + gates."""
    content = _read(plugin_root, SKILL)
    assert "Logic map" in content, "skill does not have a Logic maps section"
    assert "REQUIRED" in content, "skill does not mark logic maps as required"
    assert "Gate node" in content or "gate node" in content.lower(), (
        "skill does not define the gate-node vocabulary for logic maps"
    )
    assert "routing" in content.lower(), (
        "skill does not establish that logic maps show routing"
    )


def test_skill_has_the_bare_fence_rule(plugin_root: Path) -> None:
    """The key technical rule: ASCII art goes in a BARE fenced block (no language tag)."""
    content = _read(plugin_root, SKILL)
    assert "BARE" in content or "bare fenced" in content.lower(), (
        "readme-styling SKILL.md does not state the bare-fence rule for ASCII art"
    )


def test_skill_has_glyph_palette_and_anti_patterns(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "glyph palette" in content.lower(), "skill lacks the glyph palette"
    assert "Anti-patterns" in content, "skill lacks the anti-pattern table"
    assert "Consistency rules" in content, "skill lacks the consistency rules"


# --- v0.9.16: canvas / centering, color, theming engine --------------------

def test_skill_documents_canvas_and_centering(plugin_root: Path) -> None:
    """v0.9.16: one canvas width; every element built to it or centered within it."""
    content = _read(plugin_root, SKILL).lower()
    assert "canvas" in content, "readme-styling skill does not define a canvas width"
    assert "center" in content, "readme-styling skill does not document centering"


def test_skill_documents_pipe_and_graph_alignment(plugin_root: Path) -> None:
    """v0.9.16: pipe tables + ASCII graphs must be column-aligned and centered."""
    content = _read(plugin_root, SKILL).lower()
    assert "align" in content and ("pipe table" in content or "ascii table" in content), (
        "readme-styling skill does not document pipe-table / ASCII-graph alignment"
    )


def test_skill_documents_color_models(plugin_root: Path) -> None:
    """v0.9.16: both GitHub-safe color (badges + Mermaid) and the ANSI variant."""
    content = _read(plugin_root, SKILL)
    assert "Mermaid" in content, "readme-styling skill does not cover Mermaid (GitHub color)"
    assert "ANSI" in content, "readme-styling skill does not cover the ANSI terminal variant"


def test_skill_documents_theming_engine(plugin_root: Path) -> None:
    """v0.9.16: preset themes + the interactive picker + the theme marker."""
    content = _read(plugin_root, SKILL)
    assert "readme-theme" in content, (
        "readme-styling skill does not define the readme-theme marker"
    )
    assert "picker" in content.lower(), (
        "readme-styling skill does not document the interactive theme picker"
    )
    for theme in ("midnight", "phosphor", "amber"):
        assert theme in content, f"readme-styling skill is missing the {theme!r} preset theme"


# --- the README applies the style ------------------------------------------

def test_readme_has_block_letter_banner(plugin_root: Path) -> None:
    content = _read(plugin_root, README)
    assert "█" in content, "README has no block-letter banner"


def test_readme_has_gradient_dividers(plugin_root: Path) -> None:
    content = _read(plugin_root, README)
    assert "█▓▒░" in content and "░▒▓█" in content, (
        "README is missing the gradient section dividers"
    )


def test_readme_has_inventory_grid(plugin_root: Path) -> None:
    content = _read(plugin_root, README)
    assert "┌─ SKILLS" in content, "README is missing the boxed inventory grid"


def test_readme_includes_logic_maps(plugin_root: Path) -> None:
    """The user explicitly asked: the README must include logic maps showing
    routing and gates. Assert the section + the gate-node glyph are present."""
    content = _read(plugin_root, README)
    assert "LOGIC MAP" in content.upper(), "README has no LOGIC MAPS section"
    assert "▣" in content, (
        "README logic maps do not use the gate-node glyph (▣) — gates are not shown"
    )


def test_readme_has_theme_marker(plugin_root: Path) -> None:
    """v0.9.16: the README records its theme in the architect-team:readme-theme marker."""
    content = _read(plugin_root, README)
    assert "architect-team:readme-theme=" in content, (
        "README is missing the <!-- architect-team:readme-theme=... --> marker"
    )


# --- the README stays current ----------------------------------------------

def test_readme_banner_version_matches_plugin_json(plugin_root: Path) -> None:
    """The banner's spaced version (e.g. 'v 0 . 9 . 8') must match plugin.json."""
    version = json.loads(_read(plugin_root, PLUGIN_JSON))["version"]
    spaced = "v " + " . ".join(version.split("."))
    content = _read(plugin_root, README)
    assert spaced in content, (
        f"README banner does not show the current version — expected {spaced!r} "
        f"(plugin.json version is {version!r})"
    )


def _count_dir_children(plugin_root: Path, subdir: str, has: str) -> int:
    d = plugin_root / subdir
    if not d.is_dir():
        return 0
    if has == "SKILL.md":
        return sum(1 for c in d.iterdir() if c.is_dir() and (c / "SKILL.md").exists())
    return sum(1 for c in d.glob("*.md"))


def test_readme_inventory_counts_match_reality(plugin_root: Path) -> None:
    """The README inventory grid header counts must match the real plugin —
    so a version bump cannot leave the README silently stale."""
    content = _read(plugin_root, README)
    n_skills = _count_dir_children(plugin_root, "skills", "SKILL.md")
    n_agents = _count_dir_children(plugin_root, "agents", "*.md")
    n_commands = _count_dir_children(plugin_root, "commands", "*.md")

    assert f"SKILLS ({n_skills})" in content, (
        f"README inventory grid does not say SKILLS ({n_skills}) — "
        f"there are {n_skills} skill dirs"
    )
    assert f"AGENTS ({n_agents})" in content, (
        f"README inventory grid does not say AGENTS ({n_agents}) — "
        f"there are {n_agents} agent files"
    )
    assert f"COMMANDS ({n_commands})" in content, (
        f"README inventory grid does not say COMMANDS ({n_commands}) — "
        f"there are {n_commands} command files"
    )
