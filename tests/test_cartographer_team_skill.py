"""Structural tests for the v3.4.0 cartographer-team skill."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cartographer-team" / "SKILL.md"


def test_skill_md_exists() -> None:
    assert SKILL.is_file()


def test_skill_carries_frontmatter() -> None:
    body = SKILL.read_text()
    front, _, _ = body[3:].partition("---")
    assert "name: cartographer-team" in front
    assert "description:" in front


def test_skill_documents_3_caller_paths() -> None:
    body = SKILL.read_text()
    assert "intake-and-mapping" in body
    assert "Phase 0b" in body
    assert "bug-fix-pipeline" in body


def test_skill_documents_5_phases() -> None:
    body = SKILL.read_text()
    for phase in ("Phase C1", "Phase C2", "Phase C3", "Phase C4", "Phase C5"):
        assert phase in body


def test_skill_documents_freshness_pre_check() -> None:
    body = SKILL.read_text()
    assert "Freshness pre-check" in body
    assert "last_mapped" in body


def test_skill_documents_3_reviewer_convergence() -> None:
    body = SKILL.read_text()
    assert "3-reviewer convergence" in body or "3 `codebase-map-reviewer`" in body
    assert "ralph-loop" in body
    assert "CODEBASE MAP COMPLETE" in body


def test_skill_documents_caller_configurable_output() -> None:
    body = SKILL.read_text()
    section = body.split("## Inputs", 1)[1].split("\n## ", 1)[0]
    for field in ("codebase_path", "classification", "output_path", "produce_route_map", "frontend_read_only", "freshness_check"):
        assert field in section


def test_skill_documents_frontend_read_only_enforcement() -> None:
    body = SKILL.read_text()
    section = body.split("## Frontend-read-only enforcement", 1)[1].split("\n## ", 1)[0]
    assert "NO file under `codebase_path` may be created, modified, or deleted" in section
    assert "alternate" in section.lower() or "frontend-reference" in section


def test_skill_documents_route_map_handling() -> None:
    body = SKILL.read_text()
    assert "ROUTE_MAP.md" in body
    assert "route-mapper" in body or "route_map_output_path" in body


def test_skill_documents_mempalace_skip_for_read_only() -> None:
    body = SKILL.read_text()
    section = body.split("## Phase C4", 1)[1].split("\n## ", 1)[0]
    assert "SKIP" in section or "skip" in section.lower()
    assert "frontend_read_only" in section


def test_skill_disciplines_respected() -> None:
    body = SKILL.read_text()
    section = body.split("## Disciplines this skill respects", 1)[1].split("\n## ", 1)[0]
    assert "v3.0.0" in section
    assert "v1.6.0" in section
    assert "v0.9.19" in section


def test_skill_documents_what_it_is_not() -> None:
    body = SKILL.read_text()
    assert "## What this skill is NOT" in body
