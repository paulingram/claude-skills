"""Tests for the v2.20.0 Layer 3 tool: verify_deploy_mandate_satisfied + the
prompt classifier detect_deploy_mandate_in_prompt.

Covers all 4 severities, module constants, prompt classifier, fixture
round-trip, and determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.vao_tools import (
    _ADJACENT_DEPENDENCY_MARKERS,
    _DEPLOY_COMPLETENESS_MODIFIERS,
    _DEPLOY_MANDATE_VERBS,
    _LOCAL_DEPLOY_URL_MARKERS,
    _PARTIAL_DEPLOY_MARKERS,
    _PLAN_ONLY_DELIVERABLE_MARKERS,
    detect_deploy_mandate_in_prompt,
    verify_deploy_mandate_satisfied,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "deploy-mandate-not-satisfied.json"


# ---- module constants ----


def test_deploy_mandate_verbs_include_core_verbs() -> None:
    for v in ("deploy", "launch", "ship", "publish", "go live"):
        assert v in _DEPLOY_MANDATE_VERBS


def test_deploy_completeness_modifiers_include_user_phrases() -> None:
    for m in ("fully", "100%", "all elements", "real and functional", "anything less is failure"):
        assert m in _DEPLOY_COMPLETENESS_MODIFIERS


def test_plan_only_markers_include_key_phrases() -> None:
    joined = " ".join(_PLAN_ONLY_DELIVERABLE_MARKERS).lower()
    assert "plan" in joined
    assert "blueprint" in joined or "roadmap" in joined


def test_adjacent_dependency_markers_include_audience_loom_phrases() -> None:
    joined = " ".join(_ADJACENT_DEPENDENCY_MARKERS).lower()
    assert "auth fix" in joined
    assert "building blocks" in joined or "demo agents" in joined


def test_partial_deploy_markers_include_thin_slice() -> None:
    assert "thin slice" in _PARTIAL_DEPLOY_MARKERS


def test_local_url_markers_include_localhost() -> None:
    assert "localhost" in _LOCAL_DEPLOY_URL_MARKERS
    assert "127.0.0.1" in _LOCAL_DEPLOY_URL_MARKERS


# ---- prompt classifier ----


def test_detect_returns_inactive_for_empty_prompt() -> None:
    d = detect_deploy_mandate_in_prompt("")
    assert d["active"] is False
    assert d["target_kind"] is None


def test_detect_returns_inactive_for_review_prompt() -> None:
    d = detect_deploy_mandate_in_prompt("review the codebase and tell me what's there")
    assert d["active"] is False


def test_detect_returns_inactive_for_prompt_with_no_modifier() -> None:
    # "deploying eventually" matches the verb but no completeness modifier;
    # the mandate requires BOTH.
    d = detect_deploy_mandate_in_prompt("give me a plan for deploying eventually")
    assert d["active"] is False


def test_detect_fires_on_user_verbatim_prose() -> None:
    p = "when I say deploy an application I dont want it to ask me tons of questions. when I say fully deploy it must have 1 criteria 100% of all elements active and real and functional."
    d = detect_deploy_mandate_in_prompt(p)
    assert d["active"] is True
    assert d["target_kind"] == "fullstack"
    assert "deploy" in d["matched_verbs"]
    assert any(m in d["matched_modifiers"] for m in ("fully", "100%", "all elements"))


def test_detect_recognizes_thin_slice_target_kind() -> None:
    p = "deploy a thin slice first — just the personas screen"
    d = detect_deploy_mandate_in_prompt(p)
    assert d["active"] is True
    assert d["target_kind"] == "thin-slice"


def test_detect_recognizes_api_only_target_kind() -> None:
    p = "deploy the backend api only, fully, no mocks"
    d = detect_deploy_mandate_in_prompt(p)
    assert d["active"] is True
    assert d["target_kind"] == "api-only"


# ---- tool: inactive mandate is no-op ----


def test_tool_inactive_mandate_passes() -> None:
    v = verify_deploy_mandate_satisfied({}, {"active": False})
    assert v["valid"] is True
    assert v["gaps"] == []
    assert v["deploy_mandate_active"] is False


def test_tool_no_mandate_dict_passes() -> None:
    v = verify_deploy_mandate_satisfied({}, None)
    assert v["valid"] is True


# ---- tool: severity 1 — deploy-mandate-not-satisfied (binding criteria) ----


def test_severity_missing_deploy_target_url() -> None:
    v = verify_deploy_mandate_satisfied(
        {"frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/login.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "deploy_target_url" for g in v["gaps"])


def test_severity_localhost_deploy_target_url() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "http://localhost:3000",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "deploy_target_url" for g in v["gaps"])


def test_severity_missing_frontend_url() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "frontend_url" for g in v["gaps"])


def test_severity_login_not_verified() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": False,
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "login_verified" for g in v["gaps"])


def test_severity_login_verified_but_no_evidence() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": None,
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "login_verification_evidence_path" for g in v["gaps"])


def test_severity_empty_live_data_assertions() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "live_data_for_every_screen" for g in v["gaps"])


def test_severity_mock_residue_count_positive() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 5, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "no_mock_residue" for g in v["gaps"])


def test_severity_unwired_elements_count_positive() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 3},
        {"active": True, "target_kind": "fullstack"},
    )
    assert v["valid"] is False
    assert any(g.get("binding_criterion") == "no_unwired_elements" for g in v["gaps"])


# ---- tool: severity 2 — plan-only-deliverable-on-deploy-mandate ----


def test_severity_plan_only_deliverable_fires() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
        final_report="Plan ✅ delivered. See SYNTHETIC_AUDIENCE_BACKEND_PLAN.md.",
    )
    assert v["valid"] is False
    assert any(g["severity"] == "plan-only-deliverable-on-deploy-mandate" for g in v["gaps"])


# ---- tool: severity 3 — adjacent-dependencies-claimed-as-deployment ----


def test_severity_adjacent_dependencies_fires() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
        final_report="All on your existing platforms, not your app. Auth fix complete. Demo agents created. Building blocks live.",
    )
    assert v["valid"] is False
    assert any(g["severity"] == "adjacent-dependencies-claimed-as-deployment" for g in v["gaps"])


# ---- tool: severity 4 — partial-deploy-passed-off-as-deploy ----


def test_severity_partial_deploy_fires_on_fullstack_mandate() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
        final_report="Thin slice deployed — start with just the personas screen.",
    )
    assert v["valid"] is False
    assert any(g["severity"] == "partial-deploy-passed-off-as-deploy" for g in v["gaps"])


def test_severity_partial_deploy_no_op_on_thin_slice_target() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/personas", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "thin-slice"},
        final_report="Thin slice deployed at https://app.example.com — personas screen live.",
    )
    assert v["valid"] is True
    assert all(g["severity"] != "partial-deploy-passed-off-as-deploy" for g in v["gaps"])


# ---- tool: clean pass ----


def test_clean_artifact_passes() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "frontend_url": "https://app.example.com", "login_verified": True,
         "login_verification_evidence_path": "/tmp/x.png",
         "live_data_assertions": [{"screen": "/", "live": True}],
         "mock_residue_count": 0, "unwired_elements_count": 0},
        {"active": True, "target_kind": "fullstack"},
        final_report="Deployed at https://app.example.com. 12 screens on live data. Login verified.",
    )
    assert v["valid"] is True
    assert v["gaps"] == []


# ---- fixture round-trip ----


def test_canonical_fixture_bad_fires_all_4_severities() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    v = verify_deploy_mandate_satisfied(
        fx["verification_artifact"], fx["deploy_mandate"], fx["final_report"]
    )
    assert v["valid"] is False
    sevs = sorted({g["severity"] for g in v["gaps"]})
    expected = sorted(fx["_meta"]["expected_severities"])
    assert sevs == expected


def test_canonical_fixture_corrected_passes() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    v = verify_deploy_mandate_satisfied(
        fx["_corrected_verification_artifact"],
        fx["deploy_mandate"],
        fx["_corrected_final_report"],
    )
    assert v["valid"] is True


# ---- output shape ----


def test_output_carries_tool_name() -> None:
    v = verify_deploy_mandate_satisfied({}, {"active": True})
    assert v["tool"] == "verify-deploy-mandate-satisfied"


def test_output_carries_target_kind_when_active() -> None:
    v = verify_deploy_mandate_satisfied({}, {"active": True, "target_kind": "spa-only"})
    assert v["target_kind"] == "spa-only"


def test_output_persists_to_out_path(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    verify_deploy_mandate_satisfied({}, {"active": True}, "", out_path=str(out))
    assert out.exists()
    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["tool"] == "verify-deploy-mandate-satisfied"


# ---- determinism ----


def test_output_is_deterministic_on_stable_input() -> None:
    artifact = {"deploy_target_url": "https://api.example.com", "frontend_url": "https://app.example.com",
                "login_verified": True, "login_verification_evidence_path": "/tmp/x.png",
                "live_data_assertions": [{"screen": "/", "live": True}],
                "mock_residue_count": 0, "unwired_elements_count": 0}
    mandate = {"active": True, "target_kind": "fullstack"}
    a = verify_deploy_mandate_satisfied(artifact, mandate, "Deployed.")
    b = verify_deploy_mandate_satisfied(artifact, mandate, "Deployed.")
    assert sorted((g["severity"] for g in a["gaps"])) == sorted((g["severity"] for g in b["gaps"]))


# ---- api-only target kind ----


def test_api_only_target_does_not_require_frontend_url() -> None:
    v = verify_deploy_mandate_satisfied(
        {"deploy_target_url": "https://api.example.com",
         "login_verified": True, "login_verification_evidence_path": "/tmp/x.png",
         "mock_residue_count": 0, "unwired_elements_count": 0,
         "live_data_assertions": []},
        {"active": True, "target_kind": "api-only"},
    )
    # frontend_url missing is OK for api-only; live_data_assertions empty is OK when frontend not required
    sevs = [g.get("binding_criterion") for g in v["gaps"]]
    assert "frontend_url" not in sevs
    assert "live_data_for_every_screen" not in sevs
