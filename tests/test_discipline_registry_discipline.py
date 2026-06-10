"""Structural tests for the v2.18.0 Codebase discipline registry discipline.

Audits the canonical doc home + per-pipeline Phase 0.1 wiring + cross-references
+ fixture presence + new SR origin kind documentation.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---- canonical home ----


def test_v2_18_0_section_present_in_common_pipeline_conventions() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Codebase discipline registry (v2.18.0)" in body


def test_canonical_home_names_3_severities() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Codebase discipline registry (v2.18.0)", 1)[1].split("\n## ", 1)[0]
    for sev in (
        "discipline-registry-missing",
        "discipline-not-applied",
        "discipline-stale",
    ):
        assert sev in section


def test_canonical_home_documents_registry_schema_path() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Codebase discipline registry (v2.18.0)", 1)[1].split("\n## ", 1)[0]
    assert ".architect-team/discipline-registry.json" in section


def test_canonical_home_documents_discipline_catalog() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Codebase discipline registry (v2.18.0)", 1)[1].split("\n## ", 1)[0]
    for d in (
        "prod-safe-test-classification",
        "live-data-wiring",
        "multi-persona-path-coverage",
        "affordance-coverage",
    ):
        assert d in section


def test_canonical_home_names_auto_apply_safe_distinction() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Codebase discipline registry (v2.18.0)", 1)[1].split("\n## ", 1)[0]
    assert "auto-apply-safe" in section.lower()
    assert "sr-route-only" in section.lower() or "SR-route-only" in section


def test_canonical_home_includes_verbatim_user_prose() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Codebase discipline registry (v2.18.0)", 1)[1].split("\n## ", 1)[0]
    assert "automatically when detected" in section
    assert "execute an update" in section


def test_canonical_home_documents_new_sr_origin_kind() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Codebase discipline registry (v2.18.0)", 1)[1].split("\n## ", 1)[0]
    assert "discipline-not-applied" in section


# ---- Phase 0.1 wiring in 3 pipeline bodies ----


def test_architect_team_pipeline_has_phase_0_1() -> None:
    body = (REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    assert "Phase 0.1" in body
    assert "Discipline freshness check" in body
    assert "v2.18.0" in body


def test_bug_fix_pipeline_has_phase_0_1() -> None:
    body = (REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    assert "Phase B0.1" in body or "Phase 0.1" in body
    assert "Discipline freshness check" in body
    assert "v2.18.0" in body


def test_mini_pipeline_has_phase_0_1() -> None:
    body = (REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    assert "Phase M0.1" in body or "Phase 0.1" in body
    assert "Discipline freshness check" in body
    assert "v2.18.0" in body


def test_each_pipeline_invokes_layer3_tool() -> None:
    for path in (
        REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md",
    ):
        body = path.read_text(encoding="utf-8")
        assert "verify-discipline-registry-current" in body, f"{path.name} missing tool invocation"


def test_registry_gate_polyglot_lives_in_cpc_table() -> None:
    """v3.10.0 (R3c): the per-body Phase 0.1 polyglot bash was collapsed into the
    canonical `## Layer 3 gate invocation table (v3.10.0)` (the detect-once polyglot
    form). Each pipeline body names the tool + references that table."""
    cpc = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Layer 3 gate invocation table (v3.10.0)" in cpc
    assert "verify-discipline-registry-current" in cpc, "the gate table must name the registry tool"
    assert "command -v python3 || command -v python" in cpc, "the table uses the detect-once polyglot form"
    for path in (
        REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md",
    ):
        body = path.read_text(encoding="utf-8")
        assert "verify-discipline-registry-current" in body, f"{path.name}: must still name the registry tool"
        assert "Layer 3 gate invocation table (v3.10.0)" in body, (
            f"{path.name}: must reference the canonical gate invocation table"
        )


# ---- canonical fixture ----


def test_canonical_fixture_exists() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "discipline-registry-not-applied.json"
    assert fx_path.exists()
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    assert "workspace_synthetic_files" in fx
    assert "_corrected_workspace_files" in fx


def test_canonical_fixture_meta_lists_expected_severities() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "discipline-registry-not-applied.json"
    fx = json.loads(fx_path.read_text(encoding="utf-8"))
    expected = set(fx["_meta"]["expected_severities"])
    assert "discipline-registry-missing" in expected
    assert "discipline-not-applied" in expected


# ---- module exports ----


def test_discipline_registry_module_exports() -> None:
    from hooks import discipline_registry

    for name in ("DISCIPLINE_CATALOG", "REGISTRY_RELATIVE_PATH", "SCHEMA_VERSION",
                 "freshness_check", "read_registry", "write_registry", "record_application"):
        assert hasattr(discipline_registry, name), f"discipline_registry missing {name!r}"
