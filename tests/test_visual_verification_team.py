"""v0.9.12 — visual-verification-team (capture / analyze / synthesize) tests.

The single-agent v0.9.11 verifier is decomposed into three roles so no one
agent can cut a step inside itself: visual-capture agents render the LIVE app
and produce countable artifacts; visual-analyzer agents do the OBJECTIVE
structural analysis (a deterministic DATA diff — not an agent eyeballing two
images); the system-architect synthesizes the gaps holistically into root
causes. These tests assert the three-role skill + agents + wire-up are present
and that the data-not-images discipline is stated.
"""
from pathlib import Path

import pytest

SKILL = ("skills", "visual-verification-team", "SKILL.md")
CAPTURE = ("agents", "visual-capture.md")
ANALYZER = ("agents", "visual-analyzer.md")
SYS_ARCHITECT = ("agents", "system-architect.md")
PIPELINE = ("skills", "architect-team-pipeline", "SKILL.md")
INTEGRATION = ("agents", "integration.md")
VISUAL_QA = ("commands", "visual-qa.md")
TEAM_SPAWN = ("skills", "team-spawning-and-review-gates", "SKILL.md")
VFR = ("skills", "visual-fidelity-reconciliation", "SKILL.md")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- the skill: three roles + the data-not-images rule ---------------------

def test_skill_exists_and_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, SKILL).strip(), "visual-verification-team SKILL.md is empty"


@pytest.mark.parametrize("role", ["visual-capture", "visual-analyzer", "system-architect"])
def test_skill_defines_all_three_roles(plugin_root: Path, role: str) -> None:
    content = _read(plugin_root, SKILL)
    assert role in content, f"visual-verification-team skill does not name the {role!r} role"


def test_skill_objective_layer_is_data_not_images(plugin_root: Path) -> None:
    """The load-bearing rule: the verdict is measured data, not an eyeballed image."""
    content = _read(plugin_root, SKILL).lower()
    assert "data" in content and "verdict" in content, (
        "visual-verification-team skill does not establish that the verdict is data"
    )
    assert "eyeball" in content or "impression" in content, (
        "visual-verification-team skill does not reject the eyeball-the-images anti-pattern"
    )
    assert "pixel diff" in content, (
        "visual-verification-team skill does not document pixel diff as the secondary image channel"
    )


def test_skill_has_countable_artifact_anticheat(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "countable" in content.lower(), (
        "visual-verification-team skill does not establish capture sets as countable artifacts"
    )
    assert "screens_captured" in content and "screens_analyzed" in content, (
        "visual-verification-team skill does not require captured==analyzed==design_map screen count"
    )


def test_skill_synthesizes_holistically_into_clusters(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL).lower()
    assert "cluster" in content, (
        "visual-verification-team skill does not cluster gaps into root causes"
    )


# --- the two new agents -----------------------------------------------------

def test_capture_agent_is_sonnet_and_mechanical(plugin_root: Path) -> None:
    content = _read(plugin_root, CAPTURE)
    assert "model: sonnet" in content, "visual-capture should run on sonnet"
    assert "no verdict" in content.lower() or "never judge" in content.lower() or (
        "mechanical" in content.lower()
    ), "visual-capture does not establish that it is mechanical and produces no verdicts"
    assert "live" in content.lower(), "visual-capture does not render the live app"


def test_analyzer_agent_is_opus_and_data_first(plugin_root: Path) -> None:
    content = _read(plugin_root, ANALYZER)
    assert "model: opus" in content, "visual-analyzer should run on opus"
    assert "data diff" in content.lower(), (
        "visual-analyzer does not establish the data diff as the verdict mechanism"
    )


@pytest.mark.parametrize("agent", [CAPTURE, ANALYZER])
def test_new_agents_are_read_only_on_source(plugin_root: Path, agent: tuple[str, ...]) -> None:
    content = _read(plugin_root, agent)
    tools_line = content.split("tools:")[1].split("\n")[0]
    assert "Edit" not in tools_line, f"{agent[-1]} must not have the Edit tool"


def test_system_architect_has_visual_gap_synthesis_mode(plugin_root: Path) -> None:
    content = _read(plugin_root, SYS_ARCHITECT)
    assert "Visual Gap Synthesis" in content, (
        "system-architect does not document the Visual Gap Synthesis mode"
    )


# --- wire-up + the old single verifier is gone ------------------------------

def test_old_single_verifier_agent_is_removed(plugin_root: Path) -> None:
    assert not (plugin_root / "agents" / "visual-fidelity-verifier.md").exists(), (
        "the superseded visual-fidelity-verifier agent file should have been removed"
    )


@pytest.mark.parametrize(
    "doc", [PIPELINE, INTEGRATION, VISUAL_QA, TEAM_SPAWN, VFR],
    ids=["pipeline", "integration", "visual-qa", "team-spawning", "reconciliation"],
)
def test_consumers_reference_the_team_not_the_old_verifier(
    plugin_root: Path, doc: tuple[str, ...]
) -> None:
    content = _read(plugin_root, doc)
    assert "visual-verification-team" in content, (
        f"{doc[-1]} does not reference the visual-verification-team"
    )
    assert "visual-fidelity-verifier" not in content, (
        f"{doc[-1]} still references the removed visual-fidelity-verifier agent"
    )
