"""Structural tests for the v2.20.0 Deploy mandate discipline."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_canonical_section_present_in_common_pipeline_conventions() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    assert "## Deploy mandate discipline (v2.20.0)" in body


def test_canonical_home_names_4_severities() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Deploy mandate discipline (v2.20.0)", 1)[1].split("\n## ", 1)[0]
    for sev in (
        "deploy-mandate-not-satisfied",
        "plan-only-deliverable-on-deploy-mandate",
        "adjacent-dependencies-claimed-as-deployment",
        "partial-deploy-passed-off-as-deploy",
    ):
        assert sev in section


def test_canonical_home_names_5_binding_criteria() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Deploy mandate discipline (v2.20.0)", 1)[1].split("\n## ", 1)[0]
    for crit in (
        "deploy_target_url",
        "frontend_url",
        "login_verified",
        "live_data_for_every_screen",
        "no_mock_residue",
    ):
        assert crit in section


def test_canonical_home_includes_verbatim_user_prose() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Deploy mandate discipline (v2.20.0)", 1)[1].split("\n## ", 1)[0]
    assert "100% of all elements" in section
    assert "anything less is failure" in section


def test_canonical_home_documents_new_sr_origin_kind() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Deploy mandate discipline (v2.20.0)", 1)[1].split("\n## ", 1)[0]
    assert "deploy-mandate-not-satisfied" in section


def test_canonical_home_names_target_kinds() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Deploy mandate discipline (v2.20.0)", 1)[1].split("\n## ", 1)[0]
    for kind in ("fullstack", "thin-slice", "api-only", "spa-only"):
        assert kind in section


# ---- agent body extensions ----


def test_frontend_agent_has_v2_20_0_section() -> None:
    body = (REPO_ROOT / "agents" / "frontend.md").read_text()
    assert "## Deploy mandate discipline (v2.20.0)" in body


def test_backend_agent_has_v2_20_0_section() -> None:
    body = (REPO_ROOT / "agents" / "backend.md").read_text()
    assert "## Deploy mandate discipline (v2.20.0)" in body


def test_qa_replayer_agent_has_v2_20_0_section() -> None:
    body = (REPO_ROOT / "agents" / "qa-replayer.md").read_text()
    assert "## Deploy mandate discipline (v2.20.0)" in body


def test_qa_replayer_documents_deploy_mandate_finding_block() -> None:
    body = (REPO_ROOT / "agents" / "qa-replayer.md").read_text()
    assert "deploy_mandate_finding" in body


def test_system_architect_has_v2_20_0_section() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text()
    assert "## Deploy mandate discipline (v2.20.0)" in body


def test_system_architect_documents_deploy_mandate_finding_block() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text()
    assert "deploy_mandate_finding" in body


# ---- pipeline body wiring ----


def test_architect_team_pipeline_has_phase_minus_2_detection() -> None:
    body = (REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md").read_text()
    assert "Phase −2 deploy-mandate detection (v2.20.0)" in body
    assert "detect_deploy_mandate_in_prompt" in body


def test_architect_team_pipeline_has_phase_8_final_gate() -> None:
    body = (REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md").read_text()
    assert "Deploy mandate final gate (v2.20.0)" in body
    assert "verify-deploy-mandate-satisfied" in body


def test_bug_fix_pipeline_has_phase_8_final_gate() -> None:
    body = (REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md").read_text()
    assert "Deploy mandate final gate (v2.20.0)" in body
    assert "verify-deploy-mandate-satisfied" in body


def test_mini_pipeline_has_phase_m7_gate() -> None:
    body = (REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md").read_text()
    assert "Deploy mandate final gate (v2.20.0)" in body
    assert "verify-deploy-mandate-satisfied" in body


def test_each_pipeline_uses_polyglot_python_pattern() -> None:
    for path in (
        REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md",
    ):
        body = path.read_text()
        invocations = [
            ln for ln in body.splitlines()
            if "verify-deploy-mandate-satisfied" in ln
            and "python3" in ln
            and "|| python" in ln
        ]
        assert invocations, f"{path.name}: missing polyglot deploy-mandate gate invocation"


# ---- fixture ----


def test_canonical_fixture_exists() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "deploy-mandate-not-satisfied.json"
    assert fx_path.exists()
    fx = json.loads(fx_path.read_text())
    assert "deploy_mandate" in fx
    assert fx["deploy_mandate"]["active"] is True
    assert "_corrected_verification_artifact" in fx


def test_canonical_fixture_meta_lists_all_4_severities() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "deploy-mandate-not-satisfied.json"
    fx = json.loads(fx_path.read_text())
    expected = sorted(fx["_meta"]["expected_severities"])
    assert expected == sorted([
        "deploy-mandate-not-satisfied",
        "plan-only-deliverable-on-deploy-mandate",
        "adjacent-dependencies-claimed-as-deployment",
        "partial-deploy-passed-off-as-deploy",
    ])


# ---- relationship to v2.14.0 ----


def test_canonical_home_cross_references_v2_14_0_and_v2_10_0() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## Deploy mandate discipline (v2.20.0)", 1)[1].split("\n## ", 1)[0]
    assert "v2.14.0" in section
    assert "v2.10.0" in section
