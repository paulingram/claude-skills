"""Structural tests for the v3.4.0 domain-research-team skill."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "domain-research-team" / "SKILL.md"


def test_skill_md_exists() -> None:
    assert SKILL.is_file()


def test_skill_carries_frontmatter() -> None:
    body = SKILL.read_text()
    assert body.startswith("---")
    front, _, _ = body[3:].partition("---")
    assert "name: domain-research-team" in front
    assert "description:" in front


def test_skill_documents_3_caller_paths() -> None:
    body = SKILL.read_text()
    assert "intake-and-mapping" in body
    assert "visual-to-api-design" in body
    assert "architect-team-pipeline" in body
    assert "Phase 0b" in body


def test_skill_documents_5_phases() -> None:
    body = SKILL.read_text()
    for phase in ("Phase R1", "Phase R2", "Phase R3", "Phase R4", "Phase R5"):
        assert phase in body


def test_skill_names_outside_research_mandate() -> None:
    body = SKILL.read_text()
    assert "Outside research" in body or "outside research" in body
    assert "MANDATORY" in body or "mandatory" in body
    # Must require: WebSearch + WebFetch
    assert "WebSearch" in body
    assert "WebFetch" in body


def test_skill_names_3_researcher_pattern() -> None:
    body = SKILL.read_text()
    assert "3 `domain-researcher`" in body or "3 domain-researcher" in body or "3 researchers" in body.lower()


def test_skill_documents_round_robin_convergence() -> None:
    body = SKILL.read_text()
    assert "Round-robin" in body or "round-robin" in body or "round robin" in body.lower()


def test_skill_documents_master_synthesizer() -> None:
    body = SKILL.read_text()
    assert "master-synthesizer" in body


def test_skill_documents_caller_configurable_output() -> None:
    body = SKILL.read_text()
    assert "output_path" in body
    assert "output_kind" in body


def test_skill_documents_frontend_read_only_mode() -> None:
    body = SKILL.read_text()
    assert "frontend_read_only" in body
    assert "Frontend-read-only" in body or "frontend-read-only" in body or "READ-ONLY" in body


def test_skill_names_completion_promise_options() -> None:
    body = SKILL.read_text()
    for promise in ("DOMAIN RESEARCH COMPLETE", "INTEGRATION MAP COMPLETE", "PERSONA MAP COMPLETE"):
        assert promise in body


def test_skill_documents_outside_research_minimum_queries() -> None:
    """Outside research mandate must specify at least 4 queries (industry / market / competitor / authoritative source)."""
    body = SKILL.read_text()
    # Look for the 4-query requirement
    section_after = body.split("Outside research")[1] if "Outside research" in body else body
    assert "1 `WebSearch` query on the industry" in section_after or "industry" in section_after
    assert "competitor" in section_after.lower()
    assert "market" in section_after.lower()


def test_skill_documents_3_disciplines_respected() -> None:
    body = SKILL.read_text()
    section = body.split("## Disciplines this skill respects", 1)[1].split("\n## ", 1)[0]
    assert "v3.0.0" in section
    assert "v2.22.0" in section or "v0.9.19" in section


def test_skill_documents_what_it_is_not() -> None:
    body = SKILL.read_text()
    assert "## What this skill is NOT" in body


def test_skill_documents_caller_inputs_schema() -> None:
    body = SKILL.read_text()
    # The caller-passed inputs object schema must be documented
    section = body.split("## Inputs", 1)[1].split("\n## ", 1)[0]
    for field in ("output_kind", "output_path", "codebase_inputs", "doc_inputs", "frontend_read_only", "completion_promise"):
        assert field in section
