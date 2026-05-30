"""v2.1.0 structural tests — assert the interactive-mockup-discovery
framework is wired in the skill bodies + agent frontmatter + oracle-deriver
and interaction-intuiter extensions.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ===========================================================================
# Canonical skill body assertions (REQ-1)
# ===========================================================================


def test_skill_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    assert skill.exists(), f"missing canonical home: {skill}"


def test_skill_has_valid_frontmatter(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    assert body.startswith("---\n"), "skill must start with YAML frontmatter"
    assert "name: interactive-mockup-discovery" in body
    assert "description:" in body


@pytest.mark.parametrize("pass_phrase", [
    "Pass 1",
    "Pass 2",
])
def test_skill_names_both_passes(plugin_root: Path, pass_phrase: str):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    assert pass_phrase in body, f"skill missing {pass_phrase}"


def test_skill_names_observation_pass(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    body_lower = body.lower()
    assert "observation" in body_lower
    assert "interaction-observer" in body


def test_skill_names_intent_inference_pass(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    body_lower = body.lower()
    assert "intent inference" in body_lower or "intent-inference" in body_lower
    assert "interaction-intuiter" in body


@pytest.mark.parametrize("action_kind", [
    "navigate",
    "open-drawer",
    "open-modal",
    "submit",
    "input-text",
    "reveal",
    "no-op",
])
def test_skill_names_all_seven_action_kinds(plugin_root: Path, action_kind: str):
    """REQ-1 — the canonical skill names every action_kind value in the taxonomy."""
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    assert action_kind in body, f"skill missing action_kind {action_kind!r}"


def test_skill_documents_interactions_schema(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    for field in ("trigger_selector", "semantic_label", "action_kind", "observed_effect", "target_url_or_state"):
        assert field in body, f"skill missing schema field {field!r}"


def test_skill_documents_interaction_intent_gap(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    assert "interaction_intent_gap" in body


def test_skill_documents_phase_minus_1d_integration(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert "phase −1d" in body_lower or "phase -1d" in body_lower


def test_skill_documents_verify_interactions_honored(plugin_root: Path):
    skill = plugin_root / "skills" / "interactive-mockup-discovery" / "SKILL.md"
    body = skill.read_text()
    assert "verify-interactions-honored" in body


# ===========================================================================
# Agent frontmatter — interaction-observer (REQ-2)
# ===========================================================================


def test_interaction_observer_agent_exists(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-observer.md"
    assert agent.exists()


def test_interaction_observer_frontmatter(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-observer.md"
    body = agent.read_text()
    assert "name: interaction-observer" in body
    assert "model: opus" in body
    assert "description:" in body
    assert "color:" in body


def test_interaction_observer_has_uniform_discipline_sections(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-observer.md"
    body = agent.read_text()
    assert "## Operating context" in body
    assert "## Forbidden git operations" in body
    assert "## Checkpoint discipline" in body


def test_interaction_observer_documents_four_step_protocol(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-observer.md"
    body = agent.read_text()
    body_lower = body.lower()
    # The 4 steps named in the proposal: run mockup → enumerate → simulate → record
    assert "run the mockup" in body_lower or "running the mockup" in body_lower or "runs the mockup" in body_lower
    assert "enumerate" in body_lower
    assert "simulate" in body_lower
    assert "observed effect" in body_lower or "observed_effect" in body_lower


def test_interaction_observer_documents_bounded_write_scope(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-observer.md"
    body = agent.read_text()
    assert ".architect-team/oracle-spec/" in body or "interaction-evidence" in body


# ===========================================================================
# oracle-deriver extensions (REQ-3)
# ===========================================================================


def test_oracle_deriver_names_interactive_mockup_spec_shape(plugin_root: Path):
    agent = plugin_root / "agents" / "oracle-deriver.md"
    body = agent.read_text()
    assert "interactive-mockup" in body


def test_oracle_deriver_documents_dispatch_to_observer(plugin_root: Path):
    agent = plugin_root / "agents" / "oracle-deriver.md"
    body = agent.read_text()
    assert "interaction-observer" in body


# ===========================================================================
# interaction-intuiter extensions (REQ-4)
# ===========================================================================


def test_interaction_intuiter_has_intent_inference_mode(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-intuiter.md"
    body = agent.read_text()
    # The section heading the proposal mandates
    assert "INTENT-INFERENCE mode" in body or "INTENT-INFERENCE" in body or "intent inference" in body.lower()


def test_interaction_intuiter_documents_mismatch_matrix(plugin_root: Path):
    """The canonical home of the mismatch matrix lives in this agent body."""
    agent = plugin_root / "agents" / "interaction-intuiter.md"
    body = agent.read_text()
    # The matrix must name at least 5 representative semantic patterns
    for pattern in ("Logout", "Sign In", "Save", "Cancel", "Delete"):
        assert pattern in body, f"interaction-intuiter mismatch matrix missing {pattern!r}"


def test_interaction_intuiter_emits_interaction_intent_gap(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-intuiter.md"
    body = agent.read_text()
    assert "interaction_intent_gap" in body


# ===========================================================================
# Coverage-map JSON consistency
# ===========================================================================


def _find_change_or_archive_dir(plugin_root: Path) -> Path:
    """The openspec change folder may be at openspec/changes/<change>/ during
    the build OR archived under openspec/changes/archive/*-<change>/ after
    Phase 7. Tests must work in either state."""
    direct = plugin_root / "openspec" / "changes" / "interactive-mockup-discovery"
    if direct.is_dir():
        return direct
    archive = plugin_root / "openspec" / "changes" / "archive"
    if archive.is_dir():
        matches = list(archive.glob("*-interactive-mockup-discovery"))
        if matches:
            return matches[0]
    raise AssertionError("interactive-mockup-discovery change folder not found at either location")


def test_change_folder_or_archive_exists(plugin_root: Path):
    change = _find_change_or_archive_dir(plugin_root)
    for required in ("proposal.md", "design.md", "tasks.md", "coverage-map.json"):
        assert (change / required).exists(), f"missing artifact: {required}"


def test_proposal_names_two_passes_and_canonical_failure(plugin_root: Path):
    proposal = _find_change_or_archive_dir(plugin_root) / "proposal.md"
    body = proposal.read_text()
    body_lower = body.lower()
    for phrase in ("pass 1", "pass 2", "logout", "mockup"):
        assert phrase in body_lower, f"proposal missing fragment {phrase!r}"


def test_coverage_map_has_all_requirements(plugin_root: Path):
    import json
    cmap = json.loads(
        (_find_change_or_archive_dir(plugin_root) / "coverage-map.json").read_text()
    )
    req_ids = {r["id"] for r in cmap["requirements"]}
    # 9 requirements per the spec
    assert len(req_ids) >= 9


# ===========================================================================
# Skill / agent registration in test inventories
# ===========================================================================


def test_skill_registered_in_expected_skills(plugin_root: Path):
    test_skills = (plugin_root / "tests" / "test_skills.py").read_text()
    assert '"interactive-mockup-discovery"' in test_skills


def test_agent_registered_in_expected_agents(plugin_root: Path):
    test_agents = (plugin_root / "tests" / "test_agents.py").read_text()
    assert '"interaction-observer"' in test_agents
