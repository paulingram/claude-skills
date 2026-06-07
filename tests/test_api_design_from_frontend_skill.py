"""Structural tests for the v3.4.0 api-design-from-frontend skill."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "api-design-from-frontend" / "SKILL.md"


def test_skill_md_exists() -> None:
    assert SKILL.is_file()


def test_skill_carries_frontmatter() -> None:
    body = SKILL.read_text()
    front, _, _ = body[3:].partition("---")
    assert "name: api-design-from-frontend" in front
    assert "description:" in front


def test_skill_documents_2_caller_paths() -> None:
    body = SKILL.read_text()
    assert "visual-to-api-design" in body
    assert "Phase 0b" in body


def test_skill_documents_3_stage_extraction() -> None:
    body = SKILL.read_text()
    assert "Stage 5" in body
    assert "Stage 6" in body
    assert "Stage 7" in body
    # And the corresponding phase names
    assert "Phase A1" in body
    assert "Phase A2" in body
    assert "Phase A3" in body


def test_skill_documents_3_output_maps() -> None:
    body = SKILL.read_text()
    for m in ("API_RETURNS_MAP.md", "API_DESIGN_MAP.md", "DATA_ARCHITECTURE_MAP.md"):
        assert m in body


def test_skill_documents_openspec_via_skill() -> None:
    body = SKILL.read_text()
    assert "openspec skill" in body or "openspec-propose" in body
    # Hand-written OpenSpec must be forbidden
    assert "forbidden" in body.lower() or "Hand-written" in body


def test_skill_documents_phenotype_dispatch() -> None:
    body = SKILL.read_text()
    section = body.split("## Phase A3", 1)[1].split("\n## ", 1)[0]
    for phenotype in ("user-management", "ai-management", "config-management"):
        assert phenotype in section


def test_skill_documents_3_reviewer_convergence_per_stage() -> None:
    body = SKILL.read_text()
    assert "3-reviewer convergence" in body
    assert "ralph-loop" in body
    for promise in ("API RETURNS MAP COMPLETE", "API DESIGN MAP COMPLETE", "DATA ARCHITECTURE MAP COMPLETE"):
        assert promise in body


def test_skill_documents_inputs_schema() -> None:
    body = SKILL.read_text()
    section = body.split("## Inputs", 1)[1].split("\n## ", 1)[0]
    for field in ("persona_map_path", "component_architecture_map_path", "page_catalog_path", "output_dir", "openspec_change_name", "frontend_read_only"):
        assert field in section


def test_skill_documents_frontend_read_only_mode() -> None:
    body = SKILL.read_text()
    assert "## Frontend-read-only mode" in body
    section = body.split("## Frontend-read-only mode", 1)[1].split("\n## ", 1)[0]
    assert "NEVER modified" in section or "read-only" in section.lower()


def test_skill_documents_desk_trace_play_test() -> None:
    body = SKILL.read_text()
    assert "desk-trace" in body or "desk trace" in body.lower()
    assert "play-test" in body or "play test" in body.lower()


def test_skill_documents_stage_6_checklist() -> None:
    body = SKILL.read_text()
    section = body.split("Stage-6 checklist", 1)[1].split("\n## ", 1)[0] if "Stage-6 checklist" in body else ""
    assert "Every page satisfiable" in section
    assert "CRUD" in section


def test_skill_documents_what_it_is_not() -> None:
    body = SKILL.read_text()
    assert "## What this skill is NOT" in body
