"""Cross-skill structural tests for the v3.5.0 Data engineering exploration discipline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON = REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md"


def test_canonical_section_present() -> None:
    body = COMMON.read_text()
    assert "## Data engineering exploration discipline (v3.5.0)" in body


def test_canonical_section_documents_7_stages() -> None:
    body = COMMON.read_text()
    section = body.split("## Data engineering exploration discipline (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    for stage in (
        "Stage 1 — Domain context",
        "Stage 2 — Conceptual data model",
        "Stage 3 — Service design",
        "Stage 4 — Volume + velocity analysis",
        "Stage 5 — Data security",
        "Stage 6 — Validation + lineage + observability",
        "Stage 7 — OpenSpec conversion",
    ):
        assert stage in section


def test_canonical_section_documents_mandatory_validation_lineage_defaults() -> None:
    body = COMMON.read_text()
    section = body.split("## Data engineering exploration discipline (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    # User prose: "by default any data engineering pipelines should have strong data validation
    # components and logging to ensure every records transform and modification, in aggregate
    # and by endpoint, should be properly traced."
    assert "MANDATORY" in section or "mandatory" in section
    assert "every record" in section.lower() or "every record" in section.lower()
    assert "aggregate" in section.lower()
    # Either "per endpoint" or "per-endpoint"
    assert "endpoint" in section.lower()


def test_canonical_section_documents_6_per_run_mandates() -> None:
    body = COMMON.read_text()
    section = body.split("## Data engineering exploration discipline (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    for mandate in (
        "Per-transformation validation rules",
        "End-to-end lineage tracking",
        "Aggregate metrics",
        "Per-endpoint metrics",
        "Anomaly detection",
        "Alerting + escalation",
    ):
        assert mandate in section


def test_canonical_section_documents_phase_0c_detection_ladder() -> None:
    body = COMMON.read_text()
    section = body.split("## Data engineering exploration discipline (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    assert "Phase 0c" in section
    assert "Prose patterns" in section
    assert "Tool keywords" in section
    assert "Codebase markers" in section
    assert "Document markers" in section


def test_canonical_section_documents_convergence_with_other_dispatch_paths() -> None:
    body = COMMON.read_text()
    section = body.split("## Data engineering exploration discipline (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    assert "Phase 0a" in section
    assert "Phase 0b" in section
    assert "Phase 0c" in section


def test_canonical_section_documents_mixed_mode() -> None:
    body = COMMON.read_text()
    section = body.split("## Data engineering exploration discipline (v3.5.0)", 1)[1].split("\n## ", 1)[0]
    # Mixed requests trigger Phase 0a + Phase 0c in sequence
    assert "mixed" in section.lower()


# ---- registration ----


def test_test_skills_includes_data_engineering_exploration() -> None:
    body = (REPO_ROOT / "tests" / "test_skills.py").read_text()
    assert '"data-engineering-exploration"' in body
