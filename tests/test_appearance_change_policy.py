"""Structural tests for the v3.14.0 appearance-change policy discipline.

The discipline closes the verbatim user-reported failure: "sometimes when
asking for updates, the agent will arbitrarily change our front end, adding
things we didnt explicitly ask for as part of an ask to improve." Three modes
govern unsolicited frontend-appearance changes -- strict (DEFAULT: no
appearance-affecting change beyond the explicit mandate; ideas recorded as
proposals, never implemented), propose (proposals surfaced at a user approval
gate; only approved ones implemented), innovate (authorized, but every delta
logged + DESIGN_MAP-reconciled).

These tests pin: the canonical section in common-pipeline-conventions, the
--appearance flag on the 3 pipeline commands, the per-pipeline references, the
per-agent statements (frontend / task-reviewer / system-architect), the
team-spawning evidence-contract docs, and the schema v7 OPTIONAL
appearance_scope_review field semantics (same contract as v2.1.0's
interactions_honored_review and v2.2.0's live_verification_review).
"""
from __future__ import annotations

from tests.helpers.module_loader import load_module
from pathlib import Path

import pytest

from tests.helpers import pins


@pytest.fixture(scope="module")
def schema_module(plugin_root: Path):
    mod = load_module(plugin_root / "hooks" / "review_evidence_schema.py", "review_evidence_schema")
    return mod


@pytest.fixture(scope="module")
def conventions_body(plugin_root: Path) -> str:
    return (
        plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    ).read_text(encoding="utf-8")


SECTION_HEADING = "## Appearance-change policy discipline (v3.14.0)"


# ===========================================================================
# Canonical section -- common-pipeline-conventions
# ===========================================================================


def test_canonical_section_exists_exactly_once(conventions_body: str):
    """Exactly one HEADING LINE (cross-reference mentions of the heading
    string inside other sections / the section's own cross-ref list do not
    count)."""
    heading_lines = [
        line
        for line in conventions_body.splitlines()
        if line.strip() == SECTION_HEADING
    ]
    assert len(heading_lines) == 1


def test_verbatim_user_prose_failure_shape(conventions_body: str):
    """The driving user prose is quoted verbatim (house style keeps typos)."""
    assert "arbitrarily change our front end" in conventions_body
    assert "by default we are strict on appearance changes" in conventions_body


def test_three_modes_named(conventions_body: str):
    for mode in ("**`strict`**", "**`propose`**", "**`innovate`**"):
        assert mode in conventions_body, f"mode row {mode} missing"


def test_strict_is_the_default(conventions_body: str):
    assert "`strict` is the DEFAULT" in conventions_body


def test_backend_changes_unrestricted(conventions_body: str):
    """Paul's carve-out: 'do what you need to on the backend'."""
    assert "do what you need to on the backend" in conventions_body


def test_flag_spelling_documented(conventions_body: str):
    assert "--appearance <strict|propose|innovate>" in conventions_body


def test_intake_state_binding_key(conventions_body: str):
    assert "`appearance_mode`" in conventions_body
    assert "intake-state.json" in conventions_body


def test_proposals_artifact_path(conventions_body: str):
    assert ".architect-team/appearance-proposals/" in conventions_body


def test_proposal_status_vocabulary(conventions_body: str):
    for status in (
        "`recorded`",
        "`approved`",
        "`rejected`",
        "`implemented-approved`",
        "`implemented-innovate`",
    ):
        assert status in conventions_body, f"proposal status {status} missing"


def test_three_mandate_sources_named(conventions_body: str):
    assert "**Requirement text.**" in conventions_body
    assert "**Spec restoration.**" in conventions_body
    assert "**Mandated-capability minimum.**" in conventions_body


def test_no_new_layer3_tool_note(conventions_body: str):
    """v3.14.0 ships gate + schema enforcement, no deterministic tool (the
    v3.5.0 phenotype-rules precedent). The section says so explicitly."""
    assert "NO new Layer 3 tool" in conventions_body


def test_strict_report_phrasing_is_imperative_not_interrogative(
    conventions_body: str,
):
    """Listing unimplemented proposals must not trip the v2.10.0
    followup-question markers."""
    assert "never interrogative" in conventions_body


def test_disposition_model_interplay(conventions_body: str):
    """Unimplemented proposals are NOT v2.10.0 in-scope deferrals."""
    assert "NOT in-scope items in the v2.10.0 sense" in conventions_body


def test_sr_gating_flag(conventions_body: str):
    """Completeness-SRs that ADD new visible UI surface are user-gated under
    strict/propose via appearance_gated."""
    assert "`appearance_gated: true`" in conventions_body


def test_anti_pattern_markers(conventions_body: str):
    assert "while I was at it" in conventions_body
    assert "took the liberty" in conventions_body


def test_inverse_axis_of_scope_fidelity(conventions_body: str):
    """Scope-fidelity catches under-delivery; this catches visual
    over-delivery."""
    assert "visual over-delivery" in conventions_body


def test_evidence_field_documented_in_section(conventions_body: str):
    assert "appearance_scope_review" in conventions_body
    assert "VALID_APPEARANCE_SCOPE_VALUES" in conventions_body


def test_spec_restoration_always_in_scope(conventions_body: str):
    """Drift-to-spec fixes (visual-fidelity-reconciliation / visual-qa) and
    bug fixes restoring intended appearance stay valid in every mode."""
    assert "restoring documented appearance is not an appearance change" in (
        conventions_body.lower()
    )


# ===========================================================================
# Pipeline bodies -- the 3 implementing pipelines reference the policy
# ===========================================================================


@pytest.mark.parametrize(
    "skill_dir",
    [
        "architect-team-pipeline",
        "bug-fix-pipeline",
        "mini-architect-team-pipeline",
    ],
)
def test_pipeline_references_policy(plugin_root: Path, skill_dir: str):
    body = (plugin_root / "skills" / skill_dir / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Appearance-change policy" in body, (
        f"{skill_dir} must reference the canonical appearance-change policy"
    )


def test_main_pipeline_phase_minus2_binding(plugin_root: Path):
    body = (
        plugin_root / "skills" / "architect-team-pipeline" / "SKILL.md"
    ).read_text(encoding="utf-8")
    # NOTE: the pipeline body spells Phase −2 with U+2212 (minus sign).
    assert (
        "### Phase −2 appearance-mode binding (v3.14.0)" in body
    )


def test_main_pipeline_phase8_lists_proposals(plugin_root: Path):
    body = (
        plugin_root / "skills" / "architect-team-pipeline" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "appearance-proposals" in body


@pytest.mark.parametrize(
    "skill_dir",
    ["bug-fix-pipeline", "mini-architect-team-pipeline"],
)
def test_sibling_pipelines_carry_policy_section(
    plugin_root: Path, skill_dir: str
):
    body = (plugin_root / "skills" / skill_dir / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "## Appearance-change policy (v3.14.0)" in body


# ===========================================================================
# Slash commands -- the --appearance flag
# ===========================================================================


@pytest.mark.parametrize(
    "command_file", ["architect-team.md", "bug-fix.md", "mini.md"]
)
def test_command_documents_appearance_flag(
    plugin_root: Path, command_file: str
):
    body = (plugin_root / "commands" / command_file).read_text(
        encoding="utf-8"
    )
    assert "--appearance" in body
    assert "APPEARANCE_MODE" in body
    assert "Default `strict`" in body


@pytest.mark.parametrize(
    "command_file", ["architect-team.md", "bug-fix.md"]
)
def test_command_no_flags_default_includes_strict(
    plugin_root: Path, command_file: str
):
    body = (plugin_root / "commands" / command_file).read_text(
        encoding="utf-8"
    )
    assert "APPEARANCE_MODE = strict" in body


# ===========================================================================
# Agents -- frontend (implementer), task-reviewer (checker),
# system-architect (master auditor)
# ===========================================================================


@pytest.mark.parametrize(
    "agent_file",
    ["frontend.md", "task-reviewer.md", "system-architect.md"],
)
def test_agent_carries_policy_section(plugin_root: Path, agent_file: str):
    body = (plugin_root / "agents" / agent_file).read_text(encoding="utf-8")
    assert SECTION_HEADING in body, (
        f"agents/{agent_file} must carry the per-agent policy statement"
    )


def test_task_reviewer_checks_delta_trace(plugin_root: Path):
    body = (plugin_root / "agents" / "task-reviewer.md").read_text(
        encoding="utf-8"
    )
    assert "appearance_scope_review" in body


def test_frontend_records_proposals_not_implements(plugin_root: Path):
    body = (plugin_root / "agents" / "frontend.md").read_text(
        encoding="utf-8"
    )
    assert "appearance-proposals" in body


# ===========================================================================
# team-spawning-and-review-gates -- evidence-contract docs
# ===========================================================================


def test_team_spawning_documents_third_optional_field(plugin_root: Path):
    body = (
        plugin_root / "skills" / "team-spawning-and-review-gates" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "appearance_scope_review" in body
    assert "3 `OPTIONAL_VAO_FIELDS`" in body


def test_readme_counts_three_optional_fields(plugin_root: Path):
    body = (plugin_root / "README.md").read_text(encoding="utf-8")
    assert "Plus 3 OPTIONAL VAO fields" in body


# ===========================================================================
# Schema v7 -- optional appearance_scope_review field
# ===========================================================================


def _minimal_v7_evidence() -> dict:
    """Minimal v7-conformant evidence dict for testing the optional field
    independently (mirrors tests/test_vao_interactions_honored.py)."""
    return {
        "schema_version": 7,
        "task_id": "T-1",
        "teammate": "backend",
        "completed_at": "2026-06-11T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 1, "passing": 1, "unit": ["x"], "integration": [], "e2e": []},
        "demo_artifact": "demo",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "synthetic",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "synthetic",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "synthetic",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "synthetic",
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "synthetic",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "synthetic",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "synthetic",
        "adversarial_review": "n/a",
        "adversarial_review_note": "synthetic",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "synthetic",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-06-11T10:30:00Z",
        },
    }


def test_field_in_optional_vao_fields(schema_module):
    assert "appearance_scope_review" in schema_module.OPTIONAL_VAO_FIELDS


def test_prior_optional_fields_still_present(schema_module):
    assert "interactions_honored_review" in schema_module.OPTIONAL_VAO_FIELDS
    assert "live_verification_review" in schema_module.OPTIONAL_VAO_FIELDS


def test_valid_values_set(schema_module):
    assert schema_module.VALID_APPEARANCE_SCOPE_VALUES == {
        "pass",
        "n/a",
        "fail",
    }


def test_required_fields_unchanged(schema_module):
    """REQUIRED_EVIDENCE_FIELDS stays at 17 -- the new field is OPTIONAL (the
    v2.1.0 / v2.2.0 backwards-compat guarantee, third application)."""
    assert len(schema_module.REQUIRED_EVIDENCE_FIELDS) == pins.EXPECTED_EVIDENCE_FIELD_COUNT
    assert (
        "appearance_scope_review"
        not in schema_module.REQUIRED_EVIDENCE_FIELDS
    )


def test_optional_field_absent_does_not_block(schema_module):
    """Pre-v3.14.0 evidence files (which lack the field entirely) remain
    valid."""
    ev = _minimal_v7_evidence()
    assert "appearance_scope_review" not in ev
    gaps = schema_module.validate_evidence(ev)
    assert gaps == [], f"absent optional field must not yield gaps; gaps={gaps}"


def test_optional_field_pass_does_not_block(schema_module):
    ev = _minimal_v7_evidence()
    ev["appearance_scope_review"] = "pass"
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_na_with_note_does_not_block(schema_module):
    ev = _minimal_v7_evidence()
    ev["appearance_scope_review"] = "n/a"
    ev["appearance_scope_review_note"] = (
        "backend-only slice; no frontend presentation surface touched"
    )
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_na_without_note_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["appearance_scope_review"] = "n/a"
    gaps = schema_module.validate_evidence(ev)
    assert any("appearance_scope_review_note" in g for g in gaps)


def test_optional_field_fail_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["appearance_scope_review"] = "fail"
    gaps = schema_module.validate_evidence(ev)
    assert gaps
    assert any("appearance_scope_review" in g for g in gaps)


def test_optional_field_dict_shape_with_verdict_path(schema_module):
    ev = _minimal_v7_evidence()
    ev["appearance_scope_review"] = {
        "verdict": "pass",
        "verdict_path": ".architect-team/appearance-proposals/run-1.json",
    }
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_dict_shape_missing_verdict_path_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["appearance_scope_review"] = {"verdict": "pass"}
    gaps = schema_module.validate_evidence(ev)
    assert any("verdict_path" in g for g in gaps)
