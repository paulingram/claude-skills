"""v2.13.0 structural tests — assert the new skills/visual-to-api-design/
skill is present, well-formed, and documents the 4-stage pipeline with
3-reviewer convergence + per-stage checklists.
"""
from __future__ import annotations

from pathlib import Path

import pytest


SKILL_PATH = ("skills", "visual-to-api-design", "SKILL.md")


def _read_skill(plugin_root: Path) -> str:
    return plugin_root.joinpath(*SKILL_PATH).read_text(encoding="utf-8")


def test_skill_file_exists(plugin_root: Path):
    target = plugin_root.joinpath(*SKILL_PATH)
    assert target.exists(), f"{target} missing"
    assert target.read_text(encoding="utf-8").strip()


def test_skill_has_frontmatter(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert body.startswith("---\n")
    assert "\nname: visual-to-api-design\n" in body
    assert "\ndescription:" in body


def test_skill_documents_all_4_stages(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "### Stage 1 — Context discovery" in body
    assert "### Stage 2 — Per-persona research" in body
    assert "### Stage 3 — Page catalog" in body
    assert "### Stage 4 — Backend design from frontend" in body


@pytest.mark.parametrize("required_field", [
    "application_purpose",
    "industry",
    "use_case_summary",
    "pages_count",
    "personas_count",
])
def test_stage_1_documents_required_field(plugin_root: Path, required_field: str):
    body = _read_skill(plugin_root)
    assert required_field in body


@pytest.mark.parametrize("required_field", [
    "persona_id",
    "research_sources",
    "expected_workflows",
    "expected_data_needs",
    "expected_affordances",
])
def test_stage_2_documents_required_field(plugin_root: Path, required_field: str):
    body = _read_skill(plugin_root)
    assert required_field in body


@pytest.mark.parametrize("required_field", [
    "page_id",
    "elements",
    "element_id",
    "classification",
    "blurb",
    "is_dynamic",
    "needs_backend",
    "backend_endpoint_hint",
])
def test_stage_3_documents_required_field(plugin_root: Path, required_field: str):
    body = _read_skill(plugin_root)
    assert required_field in body


@pytest.mark.parametrize("required_layer", [
    "data",
    "services",
    "schema",
    "api",
])
def test_stage_4_documents_layer(plugin_root: Path, required_layer: str):
    body = _read_skill(plugin_root)
    # Layer must be named as a key + with checklist_verdict guarding
    assert required_layer in body
    assert "checklist_verdict" in body


def test_skill_documents_3_reviewer_convergence(plugin_root: Path):
    body = _read_skill(plugin_root).lower()
    assert "3 reviewer" in body or "3-reviewer" in body or "three reviewer" in body
    assert "round 1" in body
    assert "round 2" in body
    assert "round 3" in body


def test_skill_references_v0_9_19_pattern(plugin_root: Path):
    """The 3-reviewer convergence reuses the v0.9.19 interaction-completeness pattern."""
    body = _read_skill(plugin_root)
    assert "interaction-completeness" in body or "v0.9.19" in body


def test_skill_documents_per_stage_checklist_table(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "Per-stage checklist" in body or "per-stage checklist" in body or "checklists are the gate" in body.lower()
    # Each transition's checklist documented
    assert "Stage 1's `personas_count`" in body or "Stage 1 said" in body
    assert "Stage 3" in body and "needs_backend" in body


def test_skill_introduces_api_design_stage_incomplete_sr_kind(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "api-design-stage-incomplete" in body


def test_skill_quotes_verbatim_user_prose(plugin_root: Path):
    body = _read_skill(plugin_root)
    # The verbatim ask names "API desing", "complete catalog", "every element"
    body_lower = body.lower()
    assert "api desing" in body_lower or "api design" in body_lower
    assert "complete catalog" in body_lower or "page catalog" in body_lower
    assert "every element" in body_lower


def test_skill_documents_when_it_runs(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "## When this skill runs" in body or "When this skill runs" in body
    assert "Phase 0" in body


def test_skill_documents_cross_references(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "## Cross-references" in body or "## Cross-references" in body.replace("##", "##")
    # Must reference at least 3 related skills/agents
    assert "interaction-completeness" in body
    assert "verify_affordance_coverage" in body
    assert "system-architect" in body


def test_skill_documents_artifact_path_pattern(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert ".architect-team/visual-to-api-design/" in body


def test_skill_documents_frozen_artifact_chain(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "based_on_stage_" in body or "based_on_stage_1" in body
    assert "frozen_at" in body


def test_skill_documents_operating_rules(plugin_root: Path):
    body = _read_skill(plugin_root)
    assert "## Operating rules" in body
    # The 7 non-negotiable rules must be documented
    rules_indicators = ["frozen in order", "Checklists gate", "3-reviewer convergence",
                        "Read-only on source", "Cross-stage references by SHA",
                        "No deferral", "Stage 4's API layer"]
    hits = sum(1 for r in rules_indicators if r in body)
    assert hits >= 5, f"only {hits} operating rules documented"
