"""Structural tests for the v2.21.0 No proxy-element verification discipline."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_canonical_section_present_in_common_pipeline_conventions() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    assert "## No proxy-element verification discipline (v2.21.0)" in body


def test_canonical_home_names_3_severities() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## No proxy-element verification discipline (v2.21.0)", 1)[1].split("\n## ", 1)[0]
    for sev in (
        "proxy-element-substituted",
        "unreachable-state-not-escalated",
        "semantic-target-mismatch",
    ):
        assert sev in section


def test_canonical_home_names_required_verdict_fields() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## No proxy-element verification discipline (v2.21.0)", 1)[1].split("\n## ", 1)[0]
    for field in (
        "target_element_selector",
        "target_element_semantic_label",
        "measured_element_selector",
        "measured_element_semantic_label",
        "reachability_status",
    ):
        assert field in section


def test_canonical_home_documents_new_sr_origin_kind() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## No proxy-element verification discipline (v2.21.0)", 1)[1].split("\n## ", 1)[0]
    assert "target-state-unreachable-needs-seed-data" in section


def test_canonical_home_includes_verbatim_user_prose() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## No proxy-element verification discipline (v2.21.0)", 1)[1].split("\n## ", 1)[0]
    assert "no patients monitored" in section
    assert "off that proxy" in section
    assert "wrongly reported" in section


def test_canonical_home_cross_references_v2_2_0() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text()
    section = body.split("## No proxy-element verification discipline (v2.21.0)", 1)[1].split("\n## ", 1)[0]
    assert "v2.2.0" in section


# ---- agent body extensions ----


def test_qa_replayer_has_v2_21_0_section() -> None:
    body = (REPO_ROOT / "agents" / "qa-replayer.md").read_text()
    assert "## No proxy-element verification discipline (v2.21.0)" in body
    assert "target_element_finding" in body


def test_interaction_observer_has_v2_21_0_section() -> None:
    body = (REPO_ROOT / "agents" / "interaction-observer.md").read_text()
    assert "## No proxy-element verification discipline (v2.21.0)" in body
    assert "reachability_status" in body


def test_interaction_reviewer_has_v2_21_0_section() -> None:
    body = (REPO_ROOT / "agents" / "interaction-reviewer.md").read_text()
    assert "## No proxy-element verification discipline (v2.21.0)" in body
    assert "target_match" in body


def test_system_architect_has_v2_21_0_section() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text()
    assert "## No proxy-element verification discipline (v2.21.0)" in body
    assert "target_element_finding" in body


# ---- pipeline wiring ----


def test_architect_team_pipeline_has_phase_5_gate() -> None:
    body = (REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md").read_text()
    assert "Target-element verification gate (v2.21.0)" in body
    assert "verify-target-element-measured" in body


def test_bug_fix_pipeline_has_phase_b6_gate() -> None:
    body = (REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md").read_text()
    assert "Target-element verification gate (v2.21.0)" in body
    assert "verify-target-element-measured" in body


def test_pipeline_gates_use_polyglot_python_pattern() -> None:
    for path in (
        REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md",
        REPO_ROOT / "skills" / "bug-fix-pipeline" / "SKILL.md",
    ):
        body = path.read_text()
        invocations = [
            ln for ln in body.splitlines()
            if "verify-target-element-measured" in ln
            and "python3" in ln
            and "|| python" in ln
        ]
        assert invocations, f"{path.name}: missing polyglot v2.21.0 invocation"


# ---- fixture ----


def test_canonical_fixture_exists() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "proxy-element-substituted.json"
    assert fx_path.exists()
    fx = json.loads(fx_path.read_text())
    assert "verification_artifact" in fx
    assert "_corrected_verification_artifact" in fx


def test_canonical_fixture_meta_lists_3_severities() -> None:
    fx_path = REPO_ROOT / "tests" / "fixtures" / "vao" / "proxy-element-substituted.json"
    fx = json.loads(fx_path.read_text())
    expected = sorted(fx["_meta"]["expected_severities"])
    assert expected == sorted([
        "proxy-element-substituted",
        "unreachable-state-not-escalated",
        "semantic-target-mismatch",
    ])
