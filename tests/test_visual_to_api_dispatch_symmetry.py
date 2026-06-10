"""Structural tests for the v3.3.1 Visual-to-API dispatch symmetry.

The visual-to-api-design skill's `## When this skill runs` section documents
4 trigger conditions for being dispatched at Phase 0. v3.3.1 closes the
asymmetry where the main pipeline's `architect-team-pipeline/SKILL.md`
didn't document the matching dispatch step on its side.

These tests assert that both bodies now document the same 4-condition
contract so that `/architect-team` and `/architect-team:visual-to-api`
deliver identical quality.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PIPELINE = REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md"
VISUAL_SKILL = REPO_ROOT / "skills" / "visual-to-api-design" / "SKILL.md"
BUG_FIX_PIPELINE = REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md"


# ---- main pipeline Phase 0a section ----


def test_main_pipeline_has_phase_0a_dispatch_section() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    assert "## Phase 0a — Visual-to-API dispatch check (v3.3.1)" in body


def test_phase_0a_names_canonical_intake_mode_signal() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0a — Visual-to-API dispatch check (v3.3.1)", 1)[1].split("\n## ", 1)[0]
    assert "intake_mode" in section
    assert '"visual-to-api"' in section
    assert "/architect-team:visual-to-api" in section


def test_phase_0a_names_4_dispatch_conditions() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0a — Visual-to-API dispatch check (v3.3.1)", 1)[1].split("\n## ", 1)[0]
    # Condition 1 — explicit signal
    assert "Explicit signal" in section
    # Conditions 2, 3, 4 — heuristics
    assert "Heuristic — codebase + no requirements" in section
    assert "Heuristic — partial requirements + explicit derive ask" in section
    assert "Heuristic — prose pattern" in section


def test_phase_0a_names_3_canonical_prose_patterns() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0a — Visual-to-API dispatch check (v3.3.1)", 1)[1].split("\n## ", 1)[0]
    for prose in (
        "review this codebase and design the API",
        "derive the API from the UI",
        "build out the backend for this frontend",
    ):
        assert prose in section


def test_phase_0a_documents_no_op_condition() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0a — Visual-to-API dispatch check (v3.3.1)", 1)[1].split("\n## ", 1)[0]
    assert "No-op condition" in section
    assert "pure-feature pipelines" in section


def test_phase_0a_documents_skill_invocation_via_skill_tool() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0a — Visual-to-API dispatch check (v3.3.1)", 1)[1].split("\n## ", 1)[0]
    assert "skill: visual-to-api-design" in section or "visual-to-api-design`" in section


def test_phase_0a_names_5_map_artifacts() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0a — Visual-to-API dispatch check (v3.3.1)", 1)[1].split("\n## ", 1)[0]
    for doc in (
        "PERSONA_MAP.md",
        "COMPONENT_ARCHITECTURE_MAP.md",
        "API_RETURNS_MAP.md",
        "API_DESIGN_MAP.md",
        "DATA_ARCHITECTURE_MAP.md",
    ):
        assert doc in section


def test_phase_0a_documents_how_phase_0_reacts() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0a — Visual-to-API dispatch check (v3.3.1)", 1)[1].split("\n## ", 1)[0]
    assert "How Phase 0 reacts" in section
    # When the dispatch fires, Phase 0 short-circuits the plain-branch authoring
    assert "Skip the `plain` branch" in section or "skip the `plain` branch" in section.lower()
    # The dispatched skill produces openspec via openspec-propose
    assert "openspec" in section.lower()


def test_phase_0a_positioned_before_phase_0() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    phase_0a_idx = body.find("## Phase 0a — Visual-to-API dispatch check (v3.3.1)")
    phase_0_idx = body.find("## Phase 0 — Detection & Normalization")
    assert phase_0a_idx > 0
    assert phase_0_idx > phase_0a_idx, "Phase 0a must appear BEFORE Phase 0 in the body"


# ---- visual-to-api-design skill side (already-documented contract) ----


def test_visual_skill_still_documents_when_this_skill_runs() -> None:
    body = VISUAL_SKILL.read_text(encoding="utf-8")
    assert "## When this skill runs" in body


def test_visual_skill_documents_4_dispatch_conditions() -> None:
    body = VISUAL_SKILL.read_text(encoding="utf-8")
    section = body.split("## When this skill runs", 1)[1].split("\n## ", 1)[0]
    assert "Explicit signal" in section
    assert "codebase + no requirements" in section
    assert "partial requirements" in section or "derive the API" in section
    # Heuristic prose pattern
    assert "derive the API from the UI" in section or "review this codebase and design the API" in section


def test_visual_skill_documents_canonical_intake_mode_signal() -> None:
    body = VISUAL_SKILL.read_text(encoding="utf-8")
    section = body.split("## When this skill runs", 1)[1].split("\n## ", 1)[0]
    assert "intake_mode" in section
    assert '"visual-to-api"' in section


# ---- symmetry: both sides agree ----


def test_both_bodies_name_the_same_canonical_signal() -> None:
    main_body = MAIN_PIPELINE.read_text(encoding="utf-8")
    vis_body = VISUAL_SKILL.read_text(encoding="utf-8")
    # The canonical signal — the intake-state.json::intake_mode field
    canonical = 'intake_mode == "visual-to-api"'
    assert canonical in main_body
    assert canonical in vis_body


def test_both_bodies_name_the_same_slash_command() -> None:
    main_body = MAIN_PIPELINE.read_text(encoding="utf-8")
    vis_body = VISUAL_SKILL.read_text(encoding="utf-8")
    assert "/architect-team:visual-to-api" in main_body
    assert "/architect-team:visual-to-api" in vis_body


# ---- bug-fix-pipeline is NOT affected ----


def test_bug_fix_pipeline_unchanged_by_v3_3_1() -> None:
    """The visual-to-api dispatch is a FEATURE-pipeline-only path. Bug-fix
    pipeline should not document Phase 0a (it has its own Phase B0)."""
    body = BUG_FIX_PIPELINE.read_text(encoding="utf-8")
    assert "Phase 0a — Visual-to-API dispatch check (v3.3.1)" not in body
