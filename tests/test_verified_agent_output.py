"""Layer 5 structural tests — assert the v2.0.0 Verified Agent Output (VAO)
framework is wired in the skill bodies and the canonical SKILL.md is the
documented home.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from tests.helpers.module_loader import load_module


# ===========================================================================
# Canonical skill body assertions (REQ-1 in the spec)
# ===========================================================================


def test_vao_skill_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "verified-agent-output" / "SKILL.md"
    assert skill.exists(), f"missing canonical home: {skill}"


def test_vao_skill_has_valid_frontmatter(plugin_root: Path):
    skill = plugin_root / "skills" / "verified-agent-output" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.startswith("---\n"), "skill must start with YAML frontmatter"
    assert "name: verified-agent-output" in body
    assert "description:" in body


@pytest.mark.parametrize("layer_phrase", [
    "Layer 1",
    "Layer 2",
    "Layer 3",
    "Layer 4",
    "Layer 5",
    "Layer 6",
])
def test_vao_skill_names_all_six_layers(plugin_root: Path, layer_phrase: str):
    """REQ-1 — the canonical skill explicitly names all six layers."""
    skill = plugin_root / "skills" / "verified-agent-output" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert layer_phrase in body, f"VAO skill missing canonical mention of {layer_phrase}"


@pytest.mark.parametrize("shape", [
    "parity-verb",
    "backend-dep",
    "shared-tree",
    "dynamic-value",
    "default",
])
def test_vao_skill_enumerates_task_shape_taxonomy(plugin_root: Path, shape: str):
    """REQ-1 — the skill names every task shape in the Layer 2 taxonomy."""
    skill = plugin_root / "skills" / "verified-agent-output" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert shape in body, f"VAO skill missing task-shape {shape!r}"


@pytest.mark.parametrize("pairing", [
    ("parity-verb", "oracle-divergence-hunter"),
    ("backend-dep", "fake-data-hunter"),
    ("shared-tree", "git-discipline-hunter"),
    ("dynamic-value", "hardcoded-literal-hunter"),
    ("default", "general-anti-pattern-hunter"),
])
def test_vao_skill_documents_pairings(plugin_root: Path, pairing):
    """REQ-1 — the skill documents the per-shape adversarial-reviewer pairings."""
    skill = plugin_root / "skills" / "verified-agent-output" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    shape, hunter = pairing
    # The pairing must appear within reasonable proximity in the body.
    assert hunter in body, f"VAO skill missing adversarial-reviewer role {hunter!r}"
    # Soft proximity check — both terms should appear in the body.
    assert shape in body


@pytest.mark.parametrize("tool", [
    "verify-oracle-match",
    "verify-baseline-clean",
    "verify-no-fake-data",
    "verify-every-element",
    "verify-rendered-parity",
])
def test_vao_skill_names_all_five_tools(plugin_root: Path, tool: str):
    """REQ-1 — the canonical skill documents all 5 Layer-3 tools."""
    skill = plugin_root / "skills" / "verified-agent-output" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert tool in body, f"VAO skill missing tool {tool!r}"


# ===========================================================================
# Schema v7 — REQ-5 + REQ-15
# ===========================================================================


@pytest.fixture(scope="module")
def schema_module(plugin_root: Path):
    import importlib.util
    mod = load_module(plugin_root / "hooks" / "review_evidence_schema.py", "review_evidence_schema")
    return mod


def test_schema_version_is_seven(schema_module):
    """REQ-5 — SCHEMA_VERSION constant equals 7."""
    assert schema_module.SCHEMA_VERSION == 7


@pytest.mark.parametrize("field", [
    "oracle_match_review",
    "baseline_clean_review",
    "no_fake_data_review",
    "adversarial_review",
    "skill_invocation_audit",
])
def test_schema_v7_required_field(schema_module, field: str):
    """REQ-5 — each of the 5 new VAO fields is in REQUIRED_EVIDENCE_FIELDS."""
    assert field in schema_module.REQUIRED_EVIDENCE_FIELDS


def test_schema_v7_valid_values_sets_exist(schema_module):
    """REQ-5 — the VALID_*_VALUES sets exist for each new VAO field."""
    assert schema_module.VALID_ORACLE_MATCH_VALUES == {"pass", "n/a", "fail"}
    assert schema_module.VALID_BASELINE_CLEAN_VALUES == {"pass", "n/a", "fail"}
    assert schema_module.VALID_NO_FAKE_DATA_VALUES == {"pass", "n/a", "fail"}
    assert schema_module.VALID_ADVERSARIAL_REVIEW_VALUES == {"pass", "n/a", "fail"}
    assert schema_module.VALID_SKILL_INVOCATION_AUDIT_VALUES == {"pass", "n/a", "fail"}


def _minimal_v7_evidence() -> dict:
    """A minimal v7-conformant evidence dict for negative-test purposes."""
    return {
        "schema_version": 7,
        "task_id": "T-1",
        "teammate": "backend",
        "completed_at": "2026-05-29T10:00:00Z",
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
            "reviewed_at": "2026-05-29T10:30:00Z",
        },
    }


def test_minimal_v7_evidence_passes(schema_module):
    """A structurally-valid v7 dict passes validation."""
    gaps = schema_module.validate_evidence(_minimal_v7_evidence())
    assert gaps == [], f"v7 minimal evidence must pass; gaps={gaps}"


@pytest.mark.parametrize("vao_field", [
    "oracle_match_review",
    "baseline_clean_review",
    "no_fake_data_review",
    "adversarial_review",
    "skill_invocation_audit",
])
def test_schema_v7_blocks_missing_vao_field(schema_module, vao_field: str):
    """REQ-5 — validate_evidence rejects a dict missing any VAO field."""
    ev = _minimal_v7_evidence()
    del ev[vao_field]
    gaps = schema_module.validate_evidence(ev)
    assert gaps, f"missing {vao_field!r} must yield a gap"


@pytest.mark.parametrize("vao_field", [
    "oracle_match_review",
    "baseline_clean_review",
    "no_fake_data_review",
    "adversarial_review",
    "skill_invocation_audit",
])
def test_schema_v7_blocks_vao_field_fail(schema_module, vao_field: str):
    """REQ-5 — validate_evidence rejects a v7 dict whose VAO field is 'fail'."""
    ev = _minimal_v7_evidence()
    ev[vao_field] = "fail"
    gaps = schema_module.validate_evidence(ev)
    assert gaps
    assert any(vao_field in g for g in gaps), f"expected {vao_field!r} in gaps: {gaps}"


def test_schema_v7_dict_shape_requires_verdict_path(schema_module):
    """REQ-5 — the dict-shape v7 field requires a non-empty verdict_path."""
    ev = _minimal_v7_evidence()
    ev["visual_fidelity_review"] = {"verdict": "pass"}  # missing verdict_path
    gaps = schema_module.validate_evidence(ev)
    assert any("verdict_path" in g for g in gaps)


def test_schema_v7_dict_shape_with_verdict_path_passes(schema_module):
    """REQ-5 — the dict-shape v7 field passes when verdict + verdict_path are present."""
    ev = _minimal_v7_evidence()
    ev["oracle_match_review"] = {
        "verdict": "pass",
        "verdict_path": ".architect-team/vao-verdicts/T-1-oracle-match.json",
    }
    gaps = schema_module.validate_evidence(ev)
    assert gaps == [], f"dict-shape pass must validate; gaps={gaps}"


# ===========================================================================
# v2.0.0 proposal artifacts present in the openspec change
# ===========================================================================


def _find_archived_change_dir(plugin_root: Path) -> Path:
    """The openspec change folder is moved to openspec/changes/archive/
    once `openspec archive` runs at release time. The archive folder is
    prefixed with the archive date (e.g., 2026-05-30-verified-agent-output).
    """
    archive = plugin_root / "openspec" / "changes" / "archive"
    matches = list(archive.glob("*-verified-agent-output"))
    assert matches, f"no archived verified-agent-output folder under {archive}"
    return matches[0]


def test_openspec_change_archived(plugin_root: Path):
    """Post-archive — the openspec change MUST be present under archive/
    and the canonical spec landed under specs/."""
    archived = _find_archived_change_dir(plugin_root)
    for required in ("proposal.md", "design.md", "tasks.md", "coverage-map.json"):
        assert (archived / required).exists(), f"missing openspec artifact in archive: {required}"
    assert (archived / "specs" / "verified-agent-output" / "spec.md").exists()
    canonical = plugin_root / "openspec" / "specs" / "verified-agent-output" / "spec.md"
    assert canonical.exists(), "canonical spec missing under openspec/specs/"


def test_openspec_proposal_documents_all_six_layers(plugin_root: Path):
    proposal = _find_archived_change_dir(plugin_root) / "proposal.md"
    body = proposal.read_text(encoding="utf-8")
    for layer in ("Layer 1", "Layer 2", "Layer 3", "Layer 4", "Layer 5", "Layer 6"):
        assert layer in body, f"proposal missing {layer}"


def test_openspec_proposal_documents_heirship_failure_modes(plugin_root: Path):
    """The proposal must name the heirship failure modes the framework
    was amended to close."""
    proposal = _find_archived_change_dir(plugin_root) / "proposal.md"
    body = proposal.read_text(encoding="utf-8")
    for fragment in (
        "Oracle structure mismatch",
        "Source-audit",
        "Execution-time scope narrowing",
        "Skill-not-invoked",
    ):
        assert fragment in body, f"proposal missing failure-mode fragment {fragment!r}"


# ===========================================================================
# Coverage-map JSON consistency
# ===========================================================================


def test_coverage_map_lists_layer_6_requirements(plugin_root: Path):
    import json
    cmap = json.loads(
        (_find_archived_change_dir(plugin_root) / "coverage-map.json").read_text(encoding="utf-8")
    )
    req_titles = {r["title"] for r in cmap["requirements"]}
    assert any("Layer 6" in t for t in req_titles), "coverage map missing Layer 6 requirement"
    assert any("skill_invocation_audit" in t for t in req_titles), (
        "coverage map missing schema v7 skill_invocation_audit requirement"
    )
    assert any("Skill-invocation discipline" in t for t in req_titles), (
        "coverage map missing common-pipeline-conventions Layer 6 doc requirement"
    )


def test_coverage_map_lists_seven_fixtures(plugin_root: Path):
    import json
    cmap = json.loads(
        (_find_archived_change_dir(plugin_root) / "coverage-map.json").read_text(encoding="utf-8")
    )
    req10 = next((r for r in cmap["requirements"] if r["id"] == "REQ-10"), None)
    assert req10 is not None
    covered = req10["covered_by"]
    for fixture in [
        "tests/fixtures/vao/scope-narrowing.json",
        "tests/fixtures/vao/git-stash-clobber.json",
        "tests/fixtures/vao/frontend-fake-data.json",
        "tests/fixtures/vao/oracle-structure-mismatch.json",
        "tests/fixtures/vao/chrome-mount-level-mismatch.json",
        "tests/fixtures/vao/execution-time-variance.json",
        "tests/fixtures/vao/skill-not-invoked.json",
    ]:
        assert fixture in covered, f"REQ-10 coverage missing {fixture!r}"


# ===========================================================================
# v3.47.0 — the OPTIONAL `check_integrity_review` field (check-falsifiability)
#
# A check is not evidence until it has been shown able to fail. The field cites
# the `verify-check-can-fail` verdict; it follows the validated-when-present
# pattern of `interactions_honored_review` (v2.1.0) / `live_verification_review`
# (v2.2.0) / `appearance_scope_review` (v3.14.0) — absent means an existing v7
# evidence file stays valid, present means the value is validated and a `fail`
# blocks. A `pass` additionally MUST cite the verdict path: an uncited "the
# checks were fine" is exactly the self-attestation the field exists to refuse.
# ===========================================================================


def test_check_integrity_review_absent_stays_valid(schema_module):
    """Scenario: absent field stays valid — zero blast on existing v7 files."""
    ev = _minimal_v7_evidence()
    assert "check_integrity_review" not in ev
    gaps = schema_module.validate_evidence(ev)
    assert gaps == [], f"absent optional field must not yield gaps; gaps={gaps}"


def test_check_integrity_review_is_not_required(schema_module):
    assert "check_integrity_review" not in schema_module.REQUIRED_EVIDENCE_FIELDS
    assert len(schema_module.REQUIRED_EVIDENCE_FIELDS) == 17


def test_check_integrity_review_in_optional_vao_fields(schema_module):
    assert "check_integrity_review" in schema_module.OPTIONAL_VAO_FIELDS


def test_check_integrity_valid_values_set(schema_module):
    assert schema_module.VALID_CHECK_INTEGRITY_VALUES == {"pass", "n/a", "fail"}


def test_check_integrity_review_fail_blocks(schema_module):
    """Scenario: present fail blocks."""
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = "fail"
    gaps = schema_module.validate_evidence(ev)
    assert any("check_integrity_review" in g for g in gaps), gaps


def test_check_integrity_review_dict_fail_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = {
        "verdict": "fail",
        "verdict_path": ".architect-team/vao-verdicts/T-1-check-can-fail.json",
    }
    gaps = schema_module.validate_evidence(ev)
    assert any("check_integrity_review" in g for g in gaps), gaps


def test_check_integrity_review_invalid_value_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = "probably fine"
    gaps = schema_module.validate_evidence(ev)
    assert any("check_integrity_review" in g for g in gaps), gaps


def test_check_integrity_review_na_requires_a_note(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = "n/a"
    gaps = schema_module.validate_evidence(ev)
    assert any("check_integrity_review" in g for g in gaps), gaps


def test_check_integrity_review_na_with_note_passes(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = "n/a"
    ev["check_integrity_review_note"] = "no verification commands cited for this slice"
    assert schema_module.validate_evidence(ev) == []


def test_check_integrity_review_bare_pass_requires_a_citation(schema_module):
    """A `pass` with no cited verdict path is refused — the citation IS the
    difference between a verdict and an attestation."""
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = "pass"
    gaps = schema_module.validate_evidence(ev)
    assert any("check_integrity_review" in g for g in gaps), gaps
    assert any("verdict_path" in g for g in gaps), gaps


def test_check_integrity_review_dict_pass_with_verdict_path_passes(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = {
        "verdict": "pass",
        "verdict_path": ".architect-team/vao-verdicts/T-1-check-can-fail.json",
    }
    assert schema_module.validate_evidence(ev) == []


def test_check_integrity_review_dict_pass_without_verdict_path_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = {"verdict": "pass"}
    gaps = schema_module.validate_evidence(ev)
    assert any("verdict_path" in g for g in gaps), gaps


def test_check_integrity_review_string_pass_with_sibling_citation_passes(schema_module):
    """The string shape stays available when the verdict path is cited in the
    sibling field — the same accommodation the other optional fields make for
    tool-mediated verdicts surfaced inline."""
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = "pass"
    ev["check_integrity_review_verdict_path"] = (
        ".architect-team/vao-verdicts/T-1-check-can-fail.json"
    )
    assert schema_module.validate_evidence(ev) == []


def test_check_integrity_review_empty_sibling_citation_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = "pass"
    ev["check_integrity_review_verdict_path"] = "   "
    gaps = schema_module.validate_evidence(ev)
    assert any("check_integrity_review" in g for g in gaps), gaps


# --- B1 (adversarial hei-adversary-g2, high): an unhashable value must not crash
# the validator. `value not in valid_values` raises TypeError for a list, the
# exception escapes the hook's main(), the hook exits 1, and Claude Code treats
# exit 1 as non-blocking — so ONE added key silently skipped the entire review
# gate. A gate that cannot evaluate its evidence must fail CLOSED, never vanish.

@pytest.mark.parametrize("bad_value", [[], ["pass"], {"pass"}, 7, 3.5, True, None])
def test_unhashable_or_wrong_typed_optional_field_yields_a_gap_not_a_crash(
    schema_module, bad_value
):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = bad_value
    gaps = schema_module.validate_evidence(ev)  # must not raise
    assert any("check_integrity_review" in g for g in gaps), gaps


@pytest.mark.parametrize("field", [
    "visual_fidelity_review",
    "test_completeness_review",
    "integration_testing_review",
    "ui_interaction_review",
    "oracle_match_review",
    "baseline_clean_review",
    "no_fake_data_review",
    "adversarial_review",
    "skill_invocation_audit",
])
def test_unhashable_value_on_any_review_field_yields_a_gap_not_a_crash(
    schema_module, field
):
    """The same crash class on every value-checked field — closed in one place."""
    ev = _minimal_v7_evidence()
    ev[field] = []
    gaps = schema_module.validate_evidence(ev)  # must not raise
    assert any(field in g for g in gaps), gaps


def test_unhashable_value_inside_the_dict_shape_yields_a_gap_not_a_crash(schema_module):
    ev = _minimal_v7_evidence()
    ev["check_integrity_review"] = {"verdict": [], "verdict_path": "x.json"}
    gaps = schema_module.validate_evidence(ev)  # must not raise
    assert any("check_integrity_review" in g for g in gaps), gaps


def test_check_integrity_review_does_not_disturb_the_other_optional_fields(schema_module):
    """Regression: adding the field must not change validation of the three
    optional fields that preceded it."""
    ev = _minimal_v7_evidence()
    ev["interactions_honored_review"] = "pass"
    ev["live_verification_review"] = "pass"
    ev["appearance_scope_review"] = "pass"
    assert schema_module.validate_evidence(ev) == []
