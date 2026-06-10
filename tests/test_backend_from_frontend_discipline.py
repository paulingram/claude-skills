"""Cross-skill structural tests for the v3.4.0 backend-from-frontend
modularization discipline. Asserts that intake-and-mapping +
visual-to-api-design correctly document their delegation to the new
skills."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INTAKE = REPO_ROOT / "skills" / "intake-and-mapping" / "SKILL.md"
VISUAL = REPO_ROOT / "skills" / "visual-to-api-design" / "SKILL.md"


# ---- intake-and-mapping refactor (delegates to cartographer-team + domain-research-team) ----


def test_intake_documents_v3_4_0_cartographer_team_delegation() -> None:
    body = INTAKE.read_text(encoding="utf-8")
    assert "v3.4.0" in body
    assert "cartographer-team" in body
    # And it documents the Skill tool invocation
    assert "skill: cartographer-team" in body


def test_intake_documents_v3_4_0_domain_research_team_delegation() -> None:
    body = INTAKE.read_text(encoding="utf-8")
    assert "domain-research-team" in body
    assert "skill: domain-research-team" in body


def test_intake_documents_caller_inputs_for_cartographer_team() -> None:
    body = INTAKE.read_text(encoding="utf-8")
    # The delegation example must show the structured inputs
    section = body.split("Step 2: Run cartographer-team", 1)[1].split("\n## ", 1)[0]
    for field in ("codebase_path", "classification", "output_path", "frontend_read_only", "freshness_check"):
        assert field in section


def test_intake_documents_caller_inputs_for_domain_research_team() -> None:
    body = INTAKE.read_text(encoding="utf-8")
    section = body.split("delegates to domain-research-team", 1)[1].split("\n## ", 1)[0]
    for field in ("output_kind", "output_path", "codebase_inputs", "completion_promise"):
        assert field in section


def test_intake_documents_behavior_preservation() -> None:
    body = INTAKE.read_text(encoding="utf-8")
    # Behavior must be preserved bit-for-bit per the refactor contract
    assert "Behavior preserved" in body or "Behavior is preserved" in body or "behavior preserved" in body.lower()


# ---- visual-to-api-design refactor ----


def test_visual_skill_documents_stage_5_delegates_to_api_design_from_frontend() -> None:
    body = VISUAL.read_text(encoding="utf-8")
    section = body.split("### Stage 5", 1)[1].split("### Stage 6", 1)[0]
    assert "v3.4.0" in section
    assert "api-design-from-frontend" in section


def test_visual_skill_documents_stage_1_delegates_to_domain_research_team() -> None:
    body = VISUAL.read_text(encoding="utf-8")
    section = body.split("### Stage 1 — Personas + application classification", 1)[1].split("### Stage 2", 1)[0]
    assert "v3.4.0" in section
    assert "domain-research-team" in section


def test_visual_skill_preserves_stage_5_6_7_contract_documentation() -> None:
    """The stage descriptions stay as the canonical contract docs even after delegation."""
    body = VISUAL.read_text(encoding="utf-8")
    # The Stage 5/6/7 sections must still exist with their goal statements
    assert "### Stage 5 — Per-page REST returns" in body
    assert "### Stage 6" in body
    assert "### Stage 7" in body


# ---- registration ----


def test_test_skills_includes_3_new_skills() -> None:
    body = (REPO_ROOT / "tests" / "test_skills.py").read_text(encoding="utf-8")
    for skill in ("cartographer-team", "domain-research-team", "api-design-from-frontend"):
        assert f'"{skill}"' in body


def test_test_agents_includes_new_domain_researcher() -> None:
    body = (REPO_ROOT / "tests" / "test_agents.py").read_text(encoding="utf-8")
    assert '"domain-researcher"' in body


# ---- boilerplate sync ----


def test_boilerplate_sync_includes_domain_researcher() -> None:
    body = (REPO_ROOT / "scripts" / "setup" / "agent_boilerplate_blocks.py").read_text(encoding="utf-8")
    assert "domain-researcher" in body
