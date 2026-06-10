"""Structural tests for the v3.5.0 Phenotype convergence rules section."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON = REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md"
AI_MGMT_BLUEPRINT = REPO_ROOT / "phenotypes" / "ai-management" / "blueprint.md"


def test_canonical_section_present() -> None:
    body = COMMON.read_text(encoding="utf-8")
    assert "## Phenotype convergence rules (v3.5.0)" in body


def test_pairing_matrix_documents_3_phenotypes() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    for phenotype in ("user-management", "ai-management", "config-management"):
        assert phenotype in section


def test_pairing_matrix_documents_ai_management_pairs_with_user_management() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    # ai-management implies user-management for user-facing AI products
    assert "ai-management" in section
    assert "user-management" in section
    # Should reference the in-phenotype documentation
    assert "blueprint" in section.lower() or "blueprint.md" in section


def test_pairing_matrix_documents_ai_management_pairs_with_config_management() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    # ai-management always deploys via config-management
    assert "config-management" in section


def test_pairing_matrix_documents_data_eng_phenotype_dispatch() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    assert "data-engineering-exploration" in section


def test_pairing_matrix_clarifies_standard_ai_user_management_layer() -> None:
    """User's prompt: 'we apparently reference ai user management and configs but
    we also have a standard AI user management layer as well.' v3.5.0 should
    clarify that ai-management auth + permissions + quotas BUILD ON TOP OF
    user-management's identity layer."""
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    # Either explicit phrase about "standard AI user management layer" OR
    # explanation of layering
    assert "standard AI user management" in section or (
        "BUILT ON TOP OF" in section or "built on top of" in section
    )


def test_pairing_matrix_documents_dispatch_points() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    # The dispatch points that must consult the rules
    assert "api-design-from-frontend" in section
    assert "data-engineering-exploration" in section
    assert "visual-to-api-design" in section


def test_pairing_matrix_documents_domain_gate_compatibility() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    assert "domain gate" in section or "AskUserQuestion" in section


def test_pairing_matrix_documents_what_rules_are_NOT() -> None:
    body = COMMON.read_text(encoding="utf-8")
    section = body.split("\n## Phenotype convergence rules (v3.5.0)\n", 1)[1].split("\n## ", 1)[0]
    assert "What the v3.5.0 rules section is NOT" in section or "is NOT" in section


def test_ai_management_blueprint_documents_user_management_pairing() -> None:
    """The v3.5.0 convergence rules surface what ai-management's own blueprint
    already documents. Verify the underlying documentation is consistent."""
    body = AI_MGMT_BLUEPRINT.read_text(encoding="utf-8")
    # ai-management blueprint should mention user-management as a paired phenotype
    assert "user-management" in body
