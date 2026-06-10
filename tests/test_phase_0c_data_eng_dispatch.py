"""Structural tests for the v3.5.0 Phase 0c data-engineering dispatch."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PIPELINE = REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md"


# ---- main pipeline Phase 0c section ----


def test_main_pipeline_has_phase_0c_section() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    assert "## Phase 0c — Data-engineering dispatch check (v3.5.0)" in body


def test_phase_0c_positioned_between_phase_0b_and_phase_0() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    phase_0b_idx = body.find("## Phase 0b — Backend dispatch check (v3.4.0)")
    phase_0c_idx = body.find("## Phase 0c — Data-engineering dispatch check (v3.5.0)")
    phase_0_idx = body.find("## Phase 0 — Detection & Normalization")
    assert 0 < phase_0b_idx < phase_0c_idx < phase_0_idx


def test_phase_0c_documents_4_detection_ladders() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    assert "Prose patterns" in section
    assert "Tool keywords" in section
    assert "Codebase markers" in section
    assert "Document markers" in section


def test_phase_0c_names_canonical_tool_keywords() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    for tool in ("dbt", "Airflow", "Dagster", "Snowflake", "Databricks", "Kafka", "Flink", "Iceberg", "Delta"):
        assert tool in section


def test_phase_0c_names_canonical_prose_patterns() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    for prose in (
        "build a data warehouse",
        "design a dbt project",
        "build an Airflow DAG",
        "design a data pipeline",
        "build a streaming pipeline",
        "design a lakehouse",
        "build a CDC pipeline",
        "design a data product",
    ):
        assert prose in section


def test_phase_0c_names_4_branches() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    for branch in (
        "**A** — Data-eng + reference",
        "**B** — Data-eng + pure greenfield",
        "**C** — Mixed mode",
        "**D** — No data-eng detected",
    ):
        assert branch in section


def test_phase_0c_dispatches_data_engineering_exploration() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    assert "data-engineering-exploration" in section


def test_phase_0c_documents_mixed_mode_handling() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    # Mixed mode: Phase 0a or 0b fired first; data-engineering-exploration uses upstream API as input
    assert "Mixed mode" in section
    assert "upstream_api_contract_path" in section


def test_phase_0c_documents_pure_greenfield_phenotype_seeding() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    # Branch B: pure greenfield falls through but phenotype seeding may apply
    assert "config-management" in section
    assert "phenotype" in section.lower()


def test_phase_0c_documents_how_phase_0_reacts() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    assert "How Phase 0 reacts" in section
    assert "Skip the `plain` branch" in section or "skip the `plain` branch" in section.lower()


def test_phase_0c_documents_stage_6_validation_rules_as_phase_1_criteria() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    # The Stage 6 validation rules become Phase 1 acceptance criteria
    assert "Stage 6" in section
    assert "acceptance criteria" in section.lower()


def test_phase_0c_cross_references_v3_4_0_and_v3_3_1() -> None:
    body = MAIN_PIPELINE.read_text(encoding="utf-8")
    # Phase 0c follows the same architectural pattern as Phase 0a (v3.3.1) and Phase 0b (v3.4.0)
    # That cross-reference lives in the canonical home rather than the pipeline body, so check
    # that the pipeline body documents that mutual exclusivity at the trigger layer:
    section = body.split("## Phase 0c — Data-engineering dispatch check (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    assert "Phase 0a" in section
    assert "Phase 0b" in section
    # Mutually exclusive trigger semantics
    assert "mutually exclusive" in section.lower() or "independent" in section.lower()
