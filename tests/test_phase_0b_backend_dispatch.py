"""Structural tests for the v3.4.0 Phase 0b backend dispatch in
architect-team-pipeline. Symmetric to v3.3.1's Phase 0a symmetry test."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PIPELINE = REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md"
COMMON = REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md"


# ---- main pipeline Phase 0b section ----


def test_main_pipeline_has_phase_0b_dispatch_section() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    assert "## Phase 0b — Backend dispatch check (v3.4.0)" in body


def test_phase_0b_positioned_between_phase_0a_and_phase_0() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    phase_0a_idx = body.find("## Phase 0a — Visual-to-API dispatch check (v3.3.1)")
    phase_0b_idx = body.find("## Phase 0b — Backend dispatch check (v3.4.0)")
    phase_0_idx = body.find("## Phase 0 — Detection & Normalization")
    assert 0 < phase_0a_idx < phase_0b_idx < phase_0_idx


def test_phase_0b_names_4_branches() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0b — Backend dispatch check (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    for branch in (
        "Branch A — Existing API extension",
        "Branch B — Greenfield API + frontend codebase referenceable",
        "Branch C — Greenfield API + documentation referenceable",
        "Branch D — Pure greenfield",
    ):
        assert branch in section


def test_phase_0b_dispatches_all_3_new_skills_in_branch_b() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0b — Backend dispatch check (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    branch_b = section.split("Branch B", 1)[1].split("Branch C", 1)[0]
    assert "cartographer-team" in branch_b
    assert "domain-research-team" in branch_b
    assert "api-design-from-frontend" in branch_b


def test_phase_0b_dispatches_2_skills_in_branch_c() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0b — Backend dispatch check (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    branch_c = section.split("Branch C", 1)[1].split("Branch D", 1)[0]
    # Branch C: no cartographer-team (no codebase to map), but domain-research-team + api-design-from-frontend
    assert "domain-research-team" in branch_c
    assert "api-design-from-frontend" in branch_c


def test_phase_0b_documents_frontend_read_only_enforcement() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0b — Backend dispatch check (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    assert "Frontend-read-only enforcement" in section
    assert "frontend_read_only: true" in section
    assert "NEVER modified" in section or "never modified" in section.lower()


def test_phase_0b_documents_alternate_output_path() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0b — Backend dispatch check (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    assert ".architect-team/frontend-reference/" in section


def test_phase_0b_documents_how_phase_0_reacts() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0b — Backend dispatch check (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    assert "How Phase 0 reacts" in section
    # Phase 0 short-circuits the plain branch when Branch B or C fires
    assert "Skip the `plain` branch" in section or "skip the `plain` branch" in section.lower()


def test_phase_0b_cross_references_v3_3_1_phase_0a() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0b — Backend dispatch check (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    assert "Phase 0a" in section


# ---- common-pipeline-conventions canonical home ----


def test_canonical_section_present_in_common() -> None:
    body = COMMON.read_text(encoding="utf-8")
    assert "## Backend-from-frontend dispatch + analysis modularization (v3.4.0)" in body


def test_canonical_home_names_3_new_skills() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("## Backend-from-frontend dispatch + analysis modularization (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    for skill in ("cartographer-team", "domain-research-team", "api-design-from-frontend"):
        assert skill in section


def test_canonical_home_documents_4_branch_decision_tree() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("## Backend-from-frontend dispatch + analysis modularization (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    for branch in ("Existing API extension", "Greenfield API + frontend codebase", "Greenfield API + documentation", "Pure greenfield"):
        assert branch in section


def test_canonical_home_documents_outside_research_mandate() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("## Backend-from-frontend dispatch + analysis modularization (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    assert "outside research" in section.lower()
    assert "MANDATORY" in section or "mandatory" in section


def test_canonical_home_documents_frontend_read_only() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("## Backend-from-frontend dispatch + analysis modularization (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    assert "Frontend-read-only" in section or "frontend-read-only" in section
    assert "non-negotiable" in section.lower() or "hard rule" in section.lower() or "MUST" in section


def test_canonical_home_cross_references_v3_3_1() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("## Backend-from-frontend dispatch + analysis modularization (v3.4.0)", 1)[1].split("\n## ", 1)[0]
    assert "v3.3.1" in section
