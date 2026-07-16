"""v2.2.0 structural tests — assert the verified-live discipline is wired
in common-pipeline-conventions, qa-replayer, bug-fix-pipeline, and the
optional schema field.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from tests.helpers.module_loader import load_module


# ===========================================================================
# Canonical section in common-pipeline-conventions
# ===========================================================================


def test_canonical_section_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "## Verified-live discipline (v2.2.0)" in body


def test_canonical_section_appears_once(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.count("## Verified-live discipline (v2.2.0)") == 1


# ----- 3 failure modes -----


@pytest.mark.parametrize("failure_mode", [
    "GESTURE SUBSTITUTION",
    "SELF-VERIFICATION LOOP",
    "PRE-POPULATED-STATE MASKING",
])
def test_canonical_section_names_failure_modes(plugin_root: Path, failure_mode: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert failure_mode in body


# ----- 4 required attestations -----


@pytest.mark.parametrize("attestation_phrase", [
    "Deployed-URL invocation",
    "Literal user gesture",
    "Semantic behavior assertion",
    "Captured screenshot",
])
def test_canonical_section_names_attestations(plugin_root: Path, attestation_phrase: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert attestation_phrase in body


# ----- 3 forbidden anti-patterns -----


@pytest.mark.parametrize("anti_pattern", [
    "Corner-clicks",
    "Self-authored unit tests",
    "Tests on pre-populated demo state",
])
def test_canonical_section_forbids_anti_patterns(plugin_root: Path, anti_pattern: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert anti_pattern in body


# ----- Cross-references -----


def test_canonical_section_references_verify_live_tool(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "verify-live-verification-claim" in body


def test_canonical_section_references_qa_replayer(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "qa-replayer" in body


def test_canonical_section_references_optional_field(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "live_verification_review" in body


# ===========================================================================
# qa-replayer Verification-Claim Audit section
# ===========================================================================


def test_qa_replayer_has_audit_section(plugin_root: Path):
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text(encoding="utf-8")
    assert "## Verification-Claim Audit (v2.2.0)" in body


def test_qa_replayer_names_three_self_checks(plugin_root: Path):
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text(encoding="utf-8")
    assert "Gesture audit" in body
    assert "Independence audit" in body
    assert "State audit" in body


def test_qa_replayer_documents_new_verdict(plugin_root: Path):
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text(encoding="utf-8")
    assert "bug-resolved-verification-suspect" in body


def test_qa_replayer_lists_three_suspect_modes(plugin_root: Path):
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text(encoding="utf-8")
    assert "gesture-substitution" in body
    assert "self-verification-loop" in body
    assert "prefill-masking" in body


# ===========================================================================
# bug-fix-pipeline Phase B6 wiring
# ===========================================================================


def test_bug_fix_pipeline_has_phase_b6_verification_audit(plugin_root: Path):
    pipeline = plugin_root / "skills" / "bug-fix-pipeline" / "SKILL.md"
    body = pipeline.read_text(encoding="utf-8")
    assert "Verification-Claim Audit (v2.2.0)" in body


def test_bug_fix_pipeline_documents_tool_invocation(plugin_root: Path):
    pipeline = plugin_root / "skills" / "bug-fix-pipeline" / "SKILL.md"
    body = pipeline.read_text(encoding="utf-8")
    assert "verify-live-verification-claim" in body


def test_bug_fix_pipeline_documents_routing_for_suspect_verdict(plugin_root: Path):
    pipeline = plugin_root / "skills" / "bug-fix-pipeline" / "SKILL.md"
    body = pipeline.read_text(encoding="utf-8")
    assert "bug-resolved-verification-suspect" in body


# ===========================================================================
# Schema v7 field
# ===========================================================================


@pytest.fixture(scope="module")
def schema_module(plugin_root: Path):
    import importlib.util
    mod = load_module(plugin_root / "hooks" / "review_evidence_schema.py", "review_evidence_schema")
    return mod


def test_schema_has_valid_live_verification_values(schema_module):
    assert hasattr(schema_module, "VALID_LIVE_VERIFICATION_VALUES")
    assert schema_module.VALID_LIVE_VERIFICATION_VALUES == {"pass", "n/a", "fail"}


def test_schema_optional_vao_fields_has_v2_2_0(schema_module):
    assert "live_verification_review" in schema_module.OPTIONAL_VAO_FIELDS


def test_schema_required_set_unchanged(schema_module):
    """v2.2.0 — REQUIRED_EVIDENCE_FIELDS stays at 17. The new field is OPTIONAL."""
    assert len(schema_module.REQUIRED_EVIDENCE_FIELDS) == 17


# ===========================================================================
# 3 canonical fixtures exist
# ===========================================================================


@pytest.mark.parametrize("fixture_name", [
    "gesture-substitution-corner-click",
    "self-authored-unit-test-loop",
    "prefill-masking-demo-matter",
])
def test_canonical_fixture_exists(plugin_root: Path, fixture_name: str):
    import json
    fx_path = plugin_root / "tests" / "fixtures" / "vao" / f"{fixture_name}.json"
    assert fx_path.exists(), f"missing canonical fixture: {fx_path}"
    data = json.loads(fx_path.read_text(encoding="utf-8"))
    assert "_meta" in data
    assert "verification_artifact" in data
    assert "bug_description" in data
    assert "expected_verdict_for_misverification" in data


# ===========================================================================
# Coverage-map JSON consistency
# ===========================================================================


def _find_change_or_archive_dir(plugin_root: Path) -> Path:
    """Resolve the openspec change folder, whether at the active or archived location."""
    direct = plugin_root / "openspec" / "changes" / "verified-live-discipline"
    if direct.is_dir():
        return direct
    archive = plugin_root / "openspec" / "changes" / "archive"
    if archive.is_dir():
        matches = list(archive.glob("*-verified-live-discipline"))
        if matches:
            return matches[0]
    raise AssertionError("verified-live-discipline change folder not found")


def test_openspec_change_or_archive_exists(plugin_root: Path):
    change = _find_change_or_archive_dir(plugin_root)
    for required in ("proposal.md", "design.md", "tasks.md", "coverage-map.json"):
        assert (change / required).exists(), f"missing artifact: {required}"


def test_proposal_documents_three_failure_modes(plugin_root: Path):
    proposal = _find_change_or_archive_dir(plugin_root) / "proposal.md"
    body = proposal.read_text(encoding="utf-8")
    for phrase in ("GESTURE SUBSTITUTION", "SELF-VERIFICATION LOOP", "PRE-POPULATED-STATE MASKING"):
        assert phrase in body


def test_coverage_map_has_all_requirements(plugin_root: Path):
    import json
    cmap = json.loads(
        (_find_change_or_archive_dir(plugin_root) / "coverage-map.json").read_text(encoding="utf-8")
    )
    req_ids = {r["id"] for r in cmap["requirements"]}
    assert len(req_ids) >= 8


# ===========================================================================
# v2.4.0 — External-state assertion + Evidence-artifact citation sub-sections
# ===========================================================================


def test_canonical_section_has_external_state_assertion_subsection(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "### External-state assertion (v2.4.0)" in body


def test_canonical_section_has_evidence_artifact_citation_subsection(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "### Evidence-artifact citation (v2.4.0)" in body


@pytest.mark.parametrize("external_kind", [
    "email", "payment", "push", "webhook-outbound", "oauth", "blob-storage",
])
def test_canonical_section_names_external_system_kinds(plugin_root: Path, external_kind: str):
    """The 6 canonical external-system kinds must be named in the v2.4.0 sub-section."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert external_kind in body, f"External-state sub-section missing {external_kind!r}"


@pytest.mark.parametrize("anti_pattern_marker", [
    "response body",
    "third-party API",
    "UI display text",
])
def test_canonical_section_names_external_anti_patterns(plugin_root: Path, anti_pattern_marker: str):
    """The 3 forbidden anti-patterns are named in the v2.4.0 sub-section."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert anti_pattern_marker.lower() in body_lower


@pytest.mark.parametrize("artifact_format", [
    "Playwright trace",
    "network log",
    "screenshot",
    "external-API response",
])
def test_canonical_section_names_artifact_formats(plugin_root: Path, artifact_format: str):
    """Accepted artifact formats are named in the Evidence-artifact sub-section."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert artifact_format.lower() in body_lower


def test_canonical_section_names_evidence_required_attributes(plugin_root: Path):
    """The sub-section names structural requirements (exists on disk / > 0 bytes / is a file)."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert "exist on disk" in body_lower or "exists on disk" in body_lower
    assert "0 bytes" in body_lower or "> 0 bytes" in body_lower
    assert "file (not a directory)" in body_lower or "not a directory" in body_lower


def test_v2_4_0_subsections_cross_reference_new_fixtures(plugin_root: Path):
    """v2.4.0 canonical positive cases (the 2 new fixtures) are cross-referenced."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "external-state-not-asserted-email-invite.json" in body
    assert "fabricated-verification-table.json" in body


# ===========================================================================
# v2.4.0 — 2 new canonical fixtures exist
# ===========================================================================


@pytest.mark.parametrize("fixture_name", [
    "external-state-not-asserted-email-invite",
    "fabricated-verification-table",
])
def test_v2_4_0_canonical_fixture_exists(plugin_root: Path, fixture_name: str):
    import json
    fx_path = plugin_root / "tests" / "fixtures" / "vao" / f"{fixture_name}.json"
    assert fx_path.exists(), f"missing v2.4.0 canonical fixture: {fx_path}"
    data = json.loads(fx_path.read_text(encoding="utf-8"))
    assert "_meta" in data
    assert "verification_artifact" in data
    assert "_corrected_verification_artifact" in data
