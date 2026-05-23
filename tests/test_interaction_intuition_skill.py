"""Structural tests for the `interaction-intuition` skill.

The skill defines the discovery-phase enforcement layer added at v0.9.21:
every frontend codebase in scope at Phase −1D produces an explicit per-element
intuition cross-walking ROUTE_MAP × DESIGN_MAP × INTEGRATION_MAP.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_NAME = "interaction-intuition"

REQUIRED_SECTIONS = (
    "## Inputs",
    "## Outputs",
    "## Confidence rubric",
    "## Per-element intuition",
    "## Artifact schema",
    "## Escalate-don't-guess",
    "## Domain-gate carve-out",
)

CONFIDENCE_LABELS = ("high", "medium", "low", "unknown")


def _skill_path(plugin_root: Path) -> Path:
    return plugin_root / "skills" / SKILL_NAME / "SKILL.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_skill_path(plugin_root))


def test_skill_file_exists(plugin_root: Path) -> None:
    path = _skill_path(plugin_root)
    assert path.exists(), f"{path} is missing"


def test_skill_frontmatter_valid(plugin_root: Path) -> None:
    fm, body = _read(plugin_root)
    assert fm["name"] == SKILL_NAME
    assert isinstance(fm["description"], str) and len(fm["description"]) > 100, (
        "interaction-intuition description should explain the skill substantively"
    )
    assert body.strip(), "skill body cannot be empty"


@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_skill_contains_required_section(plugin_root: Path, section: str) -> None:
    _, body = _read(plugin_root)
    assert section in body, f"interaction-intuition SKILL.md is missing section: {section}"


@pytest.mark.parametrize("label", CONFIDENCE_LABELS)
def test_confidence_label_named_in_rubric(plugin_root: Path, label: str) -> None:
    """Every confidence label must appear in the Confidence rubric section."""
    _, body = _read(plugin_root)
    rubric_start = body.find("## Confidence rubric")
    assert rubric_start >= 0, "## Confidence rubric section is missing"
    next_section = body.find("\n## ", rubric_start + 1)
    rubric = body[rubric_start:next_section] if next_section > 0 else body[rubric_start:]
    # Labels appear in backticks in the rubric: `high`, `medium`, etc.
    assert f"`{label}`" in rubric, f"confidence label `{label}` not named in `## Confidence rubric`"


def test_must_surface_rule_stated(plugin_root: Path) -> None:
    """`low` and `unknown` MUST surface to the Phase −1D gate."""
    _, body = _read(plugin_root)
    # The rule may be phrased a few ways — but it MUST name both labels + "surface" + the gate.
    rubric_start = body.find("## Confidence rubric")
    next_section = body.find("\n## ", rubric_start + 1)
    rubric = body[rubric_start:next_section] if next_section > 0 else body[rubric_start:]
    assert "`low`" in rubric and "`unknown`" in rubric, "rubric must name both low and unknown labels"
    assert "MUST surface" in rubric or "must surface" in rubric, (
        "rubric must state that low/unknown items MUST surface to the Phase −1D gate"
    )
    assert "Phase −1D" in body, "skill body must reference Phase −1D"


def test_bias_toward_high_when_supported(plugin_root: Path) -> None:
    """The rubric must include calibration guidance (don't over-classify as low)."""
    _, body = _read(plugin_root)
    assert "Bias toward `high`" in body or "bias toward `high`" in body or "Bias toward high" in body, (
        "the skill must include calibration guidance — bias toward high confidence when the evidence supports it"
    )


def test_domain_gate_carve_out_present(plugin_root: Path) -> None:
    """The `## Domain-gate carve-out` section must distinguish process gates from domain gates."""
    _, body = _read(plugin_root)
    start = body.find("## Domain-gate carve-out")
    assert start >= 0
    next_section = body.find("\n## ", start + 1)
    section = body[start:next_section] if next_section > 0 else body[start:]
    # The carve-out names BOTH "process gate" and "domain gate" (or similar distinction).
    assert "process gate" in section.lower(), "carve-out must name 'process gate'"
    assert "domain gate" in section.lower(), "carve-out must name 'domain gate'"
    # And it must cite the v0.9.20 gates-opt-in rule it complements.
    assert "v0.9.20" in section or "Default mode of operation" in section, (
        "carve-out must cite the v0.9.20 gates-opt-in rule (or the Default mode of operation section)"
    )


def test_skill_references_intuiter_agent(plugin_root: Path) -> None:
    """The skill must reference the interaction-intuiter agent that produces its output."""
    _, body = _read(plugin_root)
    assert "interaction-intuiter" in body, "skill must reference the interaction-intuiter agent"


def test_skill_references_artifact_path(plugin_root: Path) -> None:
    """The skill must name the per-codebase artifact path."""
    _, body = _read(plugin_root)
    assert "INTERACTION_INTUITION_MAP.md" in body, (
        "skill must name the per-codebase artifact INTERACTION_INTUITION_MAP.md"
    )
