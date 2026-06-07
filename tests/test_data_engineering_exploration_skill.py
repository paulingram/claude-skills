"""Structural tests for the v3.5.0 data-engineering-exploration skill."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "data-engineering-exploration" / "SKILL.md"


def test_skill_md_exists() -> None:
    assert SKILL.is_file()


def test_skill_carries_frontmatter() -> None:
    body = SKILL.read_text()
    front, _, _ = body[3:].partition("---")
    assert "name: data-engineering-exploration" in front
    assert "description:" in front


def test_skill_documents_2_caller_paths() -> None:
    body = SKILL.read_text()
    assert "Phase 0c" in body
    assert "mixed-mode" in body or "mixed mode" in body.lower()


def test_skill_documents_7_stages() -> None:
    body = SKILL.read_text()
    for stage in (
        "Stage 1 — Domain context",
        "Stage 2 — Conceptual data model",
        "Stage 3 — Service design",
        "Stage 4 — Volume + velocity analysis",
        "Stage 5 — Data security",
        "Stage 6 — MANDATORY validation + lineage + observability",
        "Stage 7 — OpenSpec authoring",
    ):
        assert stage in body


def test_skill_documents_7_completion_promises() -> None:
    body = SKILL.read_text()
    for promise in (
        "DOMAIN CONTEXT COMPLETE",
        "DATA MODEL COMPLETE",
        "SERVICE DESIGN COMPLETE",
        "VOLUME VELOCITY COMPLETE",
        "DATA SECURITY COMPLETE",
        "VALIDATION LINEAGE COMPLETE",
        "OPENSPEC AUTHORING COMPLETE",
    ):
        assert promise in body


def test_skill_documents_7_output_artifacts() -> None:
    body = SKILL.read_text()
    for artifact in (
        "DOMAIN_CONTEXT_MAP.md",
        "CONCEPTUAL_DATA_MODEL.md",
        "DATA_SERVICE_DESIGN_MAP.md",
        "VOLUME_VELOCITY_ANALYSIS_MAP.md",
        "DATA_SECURITY_MAP.md",
        "DATA_VALIDATION_LINEAGE_MAP.md",
    ):
        assert artifact in body


def test_skill_stage_1_delegates_to_domain_research_team() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 1 — Domain context", 1)[1].split("\n## ", 1)[0]
    assert "domain-research-team" in section
    assert "output_kind" in section
    assert "domain-context-map" in section


def test_skill_stage_1_documents_3_data_eng_outside_research_queries() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 1 — Domain context", 1)[1].split("\n## ", 1)[0]
    # The 3 mandatory data-engineering-specific outside research queries
    assert "data-stack patterns" in section
    assert "data products" in section.lower() or "data product" in section.lower()
    assert "regulatory" in section.lower() or "compliance" in section.lower()


def test_skill_stage_2_documents_entity_schema() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 2 — Conceptual data model", 1)[1].split("\n## ", 1)[0]
    for field in ("entity_id", "kind", "source_of_truth", "pii_classification", "natural_key", "scd_strategy"):
        assert field in section


def test_skill_stage_3_documents_phenotype_dispatch() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 3 — Service design", 1)[1].split("\n## ", 1)[0]
    assert "Phenotype dispatch" in section or "phenotype dispatch" in section.lower()
    assert "config-management" in section
    assert "ai-management" in section
    assert "user-management" in section


def test_skill_stage_3_consults_v3_5_0_convergence_rules() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 3 — Service design", 1)[1].split("\n## ", 1)[0]
    assert "Phenotype convergence rules (v3.5.0)" in section or "v3.5.0" in section


def test_skill_stage_4_documents_volume_velocity_schema() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 4 — Volume + velocity analysis", 1)[1].split("\n## ", 1)[0]
    for field in ("current_rows", "growth_rate_per_year", "freshness_sla", "capacity_sizing"):
        assert field in section


def test_skill_stage_5_documents_pii_phi_pci_classifications() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 5 — Data security", 1)[1].split("\n## ", 1)[0]
    for cls in ("PII", "PHI", "PCI", "GDPR", "HIPAA", "SOC2"):
        assert cls in section


def test_skill_stage_6_documents_mandatory_validation_defaults() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 6 — MANDATORY validation + lineage + observability (the v3.5.0 non-negotiable)", 1)[1].split("\n## ", 1)[0]
    # The Stage 6 section body uses MUST (not MANDATORY) — the MANDATORY signal is in the heading + the canonical home in common-pipeline-conventions
    assert section.count("MUST") >= 3
    assert "every transformation" in section.lower() or "Every transformation" in section
    assert "validation_rules" in section
    # Per user prose: "aggregate and by endpoint"
    assert "aggregate" in section.lower() and ("per-endpoint" in section.lower() or "endpoint" in section.lower())


def test_skill_stage_6_requires_blocker_severity_rule_per_transformation() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 6 — MANDATORY validation + lineage + observability (the v3.5.0 non-negotiable)", 1)[1].split("\n## ", 1)[0]
    assert "blocker" in section.lower()
    assert "≥ 1" in section or ">= 1" in section


def test_skill_stage_6_documents_lineage_frameworks() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 6 — MANDATORY validation + lineage + observability (the v3.5.0 non-negotiable)", 1)[1].split("\n## ", 1)[0]
    for framework in ("openlineage", "marquez", "datahub"):
        assert framework in section.lower()


def test_skill_stage_7_uses_openspec_propose() -> None:
    body = SKILL.read_text()
    section = body.split("## Stage 7 — OpenSpec authoring", 1)[1].split("\n## ", 1)[0]
    assert "openspec-propose" in section
    assert "NEVER hand-written" in section or "Hand-written" in section


def test_skill_documents_disciplines_respected() -> None:
    body = SKILL.read_text()
    section = body.split("## Disciplines this skill respects", 1)[1].split("\n## ", 1)[0]
    assert "v3.0.0" in section
    assert "v3.5.0" in section
    assert "v0.9.19" in section


def test_skill_documents_what_it_is_not() -> None:
    body = SKILL.read_text()
    assert "## What this skill is NOT" in body
