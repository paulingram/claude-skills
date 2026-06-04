"""Structural tests for the v2.17.0 `test-prod-safety-classifier` skill body."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "test-prod-safety-classifier" / "SKILL.md"


def test_skill_directory_exists() -> None:
    assert SKILL.parent.is_dir()


def test_skill_md_exists() -> None:
    assert SKILL.is_file()


def test_skill_carries_frontmatter() -> None:
    body = SKILL.read_text()
    assert body.startswith("---")
    front, _, _ = body[3:].partition("---")
    assert "name:" in front
    assert "description:" in front


def test_skill_mentions_both_modes() -> None:
    body = SKILL.read_text()
    assert "mass-classify" in body.lower() or "mass classify" in body.lower()
    assert "auto-classify" in body.lower() or "auto classify" in body.lower()


def test_skill_mentions_layer3_tool() -> None:
    body = SKILL.read_text()
    assert "verify-test-prod-safety-classification" in body or "verify_test_prod_safety_classification" in body


def test_skill_mentions_phase_3_integration() -> None:
    body = SKILL.read_text()
    assert "Phase 3" in body or "phase 3" in body or "phase-3" in body.lower()


def test_skill_documents_4_severities() -> None:
    body = SKILL.read_text()
    for sev in (
        "unclassified-test",
        "prod-deployment-runs-unsafe-test",
        "mutation-in-prod-safe-test",
        "classification-mismatch",
    ):
        assert sev in body, f"skill missing severity {sev!r}"


def test_skill_documents_new_sr_origin_kind() -> None:
    body = SKILL.read_text()
    assert "prod-safety-classification-required" in body


def test_skill_documents_output_artifact_path() -> None:
    body = SKILL.read_text()
    assert ".architect-team/test-prod-safety" in body


def test_skill_cross_references_canonical_home() -> None:
    body = SKILL.read_text()
    assert "common-pipeline-conventions" in body
