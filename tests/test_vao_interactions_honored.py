"""Layer 3 v2.1.0 tool — verify_interactions_honored.

These tests pin the 6th deterministic verification tool's contract: same
inputs produce byte-stable output, positive + negative + edge cases for
each severity ('intent-violated' / 'missing-handler' / 'action-kind-mismatch'),
the synthetic-fixture round-trip, and the OPTIONAL schema v7 field semantics.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def vao_tools(plugin_root: Path):
    spec = importlib.util.spec_from_file_location(
        "vao_tools",
        plugin_root / "hooks" / "vao_tools.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def schema_module(plugin_root: Path):
    spec = importlib.util.spec_from_file_location(
        "review_evidence_schema",
        plugin_root / "hooks" / "review_evidence_schema.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# verify_interactions_honored — positive cases
# ===========================================================================


def test_empty_oracle_interactions_trivially_passes(vao_tools):
    v = vao_tools.verify_interactions_honored(built_components=[], oracle_spec={})
    assert v["tool"] == "verify-interactions-honored"
    assert v["matched"] is True
    assert v["gaps"] == []
    assert v["total_count"] == 0


def test_no_interactions_field_trivially_passes(vao_tools):
    v = vao_tools.verify_interactions_honored(
        built_components=[],
        oracle_spec={"spec_shape": "component-tree"},
    )
    assert v["matched"] is True


def test_honored_intent_matches(vao_tools):
    oracle = {"interactions": [{
        "trigger_selector": "button[data-testid='logout']",
        "semantic_label": "Logout",
        "action_kind": "navigate",
        "target_url_or_state": "/dashboard",
        "resolved_intent": "navigate:/sign-in",
    }]}
    built = [{"path": "App.tsx", "handlers": [{
        "trigger_selector": "button[data-testid='logout']",
        "action_kind": "navigate",
        "target_url_or_state": "/sign-in",
    }]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is True
    assert v["honored_count"] == 1
    assert v["total_count"] == 1


def test_observed_action_used_when_no_resolved_intent(vao_tools):
    """When resolved_intent is absent, the observed action_kind + target IS
    the binding contract (the mockup's literal behavior)."""
    oracle = {"interactions": [{
        "trigger_selector": "button[data-testid='cancel']",
        "semantic_label": "Cancel",
        "action_kind": "reveal",
        "target_url_or_state": "modal-close",
    }]}
    built = [{"path": "Modal.tsx", "handlers": [{
        "trigger_selector": "button[data-testid='cancel']",
        "action_kind": "reveal",
        "target_url_or_state": "modal-close",
    }]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is True


def test_no_op_with_no_resolved_intent_is_skipped(vao_tools):
    """A no-op element with no resolved_intent isn't verified — the mockup
    intentionally has no handler; nothing to enforce in the built code."""
    oracle = {"interactions": [{
        "trigger_selector": "button[data-decorative]",
        "semantic_label": "Decorative",
        "action_kind": "no-op",
        "target_url_or_state": None,
    }]}
    v = vao_tools.verify_interactions_honored(built_components=[], oracle_spec=oracle)
    assert v["matched"] is True
    assert v["total_count"] == 0  # skipped


# ===========================================================================
# verify_interactions_honored — negative cases (severities)
# ===========================================================================


def test_missing_handler_severity(vao_tools):
    """The oracle says this trigger has an effect; built code has no handler."""
    oracle = {"interactions": [{
        "trigger_selector": "button[data-testid='delete']",
        "semantic_label": "Delete",
        "action_kind": "open-modal",
        "target_url_or_state": "confirm-delete-modal",
    }]}
    v = vao_tools.verify_interactions_honored(built_components=[], oracle_spec=oracle)
    assert v["matched"] is False
    assert v["gaps"][0]["severity"] == "missing-handler"


def test_intent_violated_severity(vao_tools):
    """resolved_intent says X; built code does Y. Both have the same action_kind
    but the target differs."""
    oracle = {"interactions": [{
        "trigger_selector": "button[data-testid='logout']",
        "semantic_label": "Logout",
        "action_kind": "navigate",
        "target_url_or_state": "/dashboard",
        "resolved_intent": "navigate:/sign-in",
    }]}
    built = [{"path": "App.tsx", "handlers": [{
        "trigger_selector": "button[data-testid='logout']",
        "action_kind": "navigate",
        "target_url_or_state": "/dashboard",
    }]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is False
    assert v["gaps"][0]["severity"] == "intent-violated"
    assert v["gaps"][0]["expected_target"] == "/sign-in"
    assert v["gaps"][0]["actual_target"] == "/dashboard"


def test_action_kind_mismatch_severity(vao_tools):
    """Oracle says open-modal; built code navigates instead."""
    oracle = {"interactions": [{
        "trigger_selector": "button[data-testid='delete']",
        "semantic_label": "Delete",
        "action_kind": "open-modal",
        "target_url_or_state": "confirm-modal",
    }]}
    built = [{"path": "Page.tsx", "handlers": [{
        "trigger_selector": "button[data-testid='delete']",
        "action_kind": "navigate",
        "target_url_or_state": "/deleted",
    }]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is False
    assert v["gaps"][0]["severity"] == "action-kind-mismatch"


# ===========================================================================
# Mixed scenarios
# ===========================================================================


def test_mixed_honored_and_gaps(vao_tools):
    oracle = {"interactions": [
        {"trigger_selector": "#a", "action_kind": "navigate", "target_url_or_state": "/x"},
        {"trigger_selector": "#b", "action_kind": "submit", "target_url_or_state": "/api"},
        {"trigger_selector": "#c", "action_kind": "open-modal", "target_url_or_state": "m"},
    ]}
    built = [{"path": "p.tsx", "handlers": [
        {"trigger_selector": "#a", "action_kind": "navigate", "target_url_or_state": "/x"},  # honored
        {"trigger_selector": "#b", "action_kind": "submit", "target_url_or_state": "/wrong"},  # intent-violated
        # #c missing → missing-handler
    ]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is False
    assert v["honored_count"] == 1
    assert v["total_count"] == 3
    assert len(v["gaps"]) == 2
    severities = {g["severity"] for g in v["gaps"]}
    assert severities == {"intent-violated", "missing-handler"}


def test_multiple_handlers_per_selector(vao_tools):
    """A selector with multiple handlers — the tool finds the matching one."""
    oracle = {"interactions": [{
        "trigger_selector": "#multi",
        "action_kind": "submit",
        "target_url_or_state": "/api/save",
    }]}
    built = [{"path": "p.tsx", "handlers": [
        {"trigger_selector": "#multi", "action_kind": "navigate", "target_url_or_state": "/elsewhere"},
        {"trigger_selector": "#multi", "action_kind": "submit", "target_url_or_state": "/api/save"},
    ]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is True


# ===========================================================================
# Determinism
# ===========================================================================


def test_deterministic_output(vao_tools, tmp_path: Path):
    """Two invocations on the same input must produce byte-identical output
    (modulo verdict_at)."""
    oracle = {"interactions": [{
        "trigger_selector": "#x",
        "action_kind": "navigate",
        "target_url_or_state": "/y",
    }]}
    built = [{"path": "p.tsx", "handlers": [{
        "trigger_selector": "#x",
        "action_kind": "navigate",
        "target_url_or_state": "/y",
    }]}]
    v1 = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle, out_path=tmp_path / "v1.json")
    v2 = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle, out_path=tmp_path / "v2.json")
    v1.pop("verdict_at")
    v2.pop("verdict_at")
    assert v1 == v2


def test_writes_verdict_file(vao_tools, tmp_path: Path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_interactions_honored(
        built_components=[],
        oracle_spec={},
        out_path=out,
    )
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["tool"] == "verify-interactions-honored"


def test_sorted_keys_in_output(vao_tools, tmp_path: Path):
    """The verdict JSON on disk has sorted keys — determinism contract."""
    out = tmp_path / "v.json"
    vao_tools.verify_interactions_honored(
        built_components=[],
        oracle_spec={},
        out_path=out,
    )
    raw = out.read_text(encoding="utf-8")
    # Alphabetical key order: gaps before honored_count before matched before tool before total_count before verdict_at
    assert raw.index('"gaps"') < raw.index('"honored_count"') < raw.index('"matched"') < raw.index('"tool"')
    assert raw.index('"tool"') < raw.index('"total_count"') < raw.index('"verdict_at"')


# ===========================================================================
# resolved_intent shapes
# ===========================================================================


def test_resolved_intent_string_shape(vao_tools):
    """resolved_intent as 'action_kind:target' string."""
    oracle = {"interactions": [{
        "trigger_selector": "#a",
        "action_kind": "navigate",
        "target_url_or_state": "/old",
        "resolved_intent": "navigate:/new",
    }]}
    built = [{"path": "p.tsx", "handlers": [{
        "trigger_selector": "#a",
        "action_kind": "navigate",
        "target_url_or_state": "/new",
    }]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is True


def test_resolved_intent_dict_shape(vao_tools):
    """resolved_intent as {action_kind, target} dict."""
    oracle = {"interactions": [{
        "trigger_selector": "#a",
        "action_kind": "navigate",
        "target_url_or_state": "/old",
        "resolved_intent": {"action_kind": "navigate", "target": "/new"},
    }]}
    built = [{"path": "p.tsx", "handlers": [{
        "trigger_selector": "#a",
        "action_kind": "navigate",
        "target_url_or_state": "/new",
    }]}]
    v = vao_tools.verify_interactions_honored(built_components=built, oracle_spec=oracle)
    assert v["matched"] is True


# ===========================================================================
# Synthetic fixture round-trip
# ===========================================================================


@pytest.fixture(scope="module")
def logout_misroute_fixture(plugin_root: Path):
    return json.loads(
        (plugin_root / "tests" / "fixtures" / "vao" / "interactive-mockup-logout-misroute.json").read_text(encoding="utf-8")
    )


def test_fixture_exists(logout_misroute_fixture):
    """The canonical fixture is loadable + carries the expected sections."""
    fx = logout_misroute_fixture
    assert "oracle_spec" in fx
    assert "built_components_misroute" in fx
    assert "built_components_honored" in fx
    assert "expected_interactions_honored_verdict_for_misroute" in fx
    assert "expected_interactions_honored_verdict_for_honored" in fx


def test_fixture_misroute_is_caught(vao_tools, logout_misroute_fixture):
    """The misroute case: built code routes Logout to /dashboard, oracle's
    resolved_intent says /sign-in. The tool must catch it."""
    fx = logout_misroute_fixture
    v = vao_tools.verify_interactions_honored(
        built_components=fx["built_components_misroute"],
        oracle_spec=fx["oracle_spec"],
    )
    assert v["matched"] is False
    expected = fx["expected_interactions_honored_verdict_for_misroute"]
    assert len(v["gaps"]) >= expected["gaps_count_minimum"]
    gap_selectors = {g["trigger_selector"] for g in v["gaps"]}
    for expected_sel in expected["expected_gap_selectors"]:
        assert expected_sel in gap_selectors


def test_fixture_honored_case_passes(vao_tools, logout_misroute_fixture):
    """The honored case: built code routes Logout to the resolved /sign-in."""
    fx = logout_misroute_fixture
    v = vao_tools.verify_interactions_honored(
        built_components=fx["built_components_honored"],
        oracle_spec=fx["oracle_spec"],
    )
    assert v["matched"] is True
    expected = fx["expected_interactions_honored_verdict_for_honored"]
    assert v["honored_count"] >= expected["honored_count_minimum"]


# ===========================================================================
# Schema v7 — optional interactions_honored_review field
# ===========================================================================


def _minimal_v7_evidence() -> dict:
    """Minimal v7-conformant evidence dict for testing the optional field
    independently."""
    return {
        "schema_version": 7,
        "task_id": "T-1",
        "teammate": "backend",
        "completed_at": "2026-05-30T10:00:00Z",
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
            "reviewed_at": "2026-05-30T10:30:00Z",
        },
    }


def test_optional_field_absent_does_not_block(schema_module):
    """v2.0.0 evidence files (which lack the field entirely) remain valid."""
    ev = _minimal_v7_evidence()
    assert "interactions_honored_review" not in ev
    gaps = schema_module.validate_evidence(ev)
    assert gaps == [], f"absent optional field must not yield gaps; gaps={gaps}"


def test_optional_field_pass_does_not_block(schema_module):
    ev = _minimal_v7_evidence()
    ev["interactions_honored_review"] = "pass"
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_na_with_note_does_not_block(schema_module):
    ev = _minimal_v7_evidence()
    ev["interactions_honored_review"] = "n/a"
    ev["interactions_honored_review_note"] = "no interactive-mockup oracle in scope"
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_fail_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["interactions_honored_review"] = "fail"
    gaps = schema_module.validate_evidence(ev)
    assert gaps
    assert any("interactions_honored_review" in g for g in gaps)


def test_optional_field_dict_shape_with_verdict_path(schema_module):
    ev = _minimal_v7_evidence()
    ev["interactions_honored_review"] = {
        "verdict": "pass",
        "verdict_path": ".architect-team/vao-verdicts/T-1-interactions-honored.json",
    }
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_dict_shape_missing_verdict_path_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["interactions_honored_review"] = {"verdict": "pass"}  # missing verdict_path
    gaps = schema_module.validate_evidence(ev)
    assert any("verdict_path" in g for g in gaps)


def test_required_fields_unchanged(schema_module):
    """REQUIRED_EVIDENCE_FIELDS still has 17 — the new field is OPTIONAL."""
    assert len(schema_module.REQUIRED_EVIDENCE_FIELDS) == 17
    assert "interactions_honored_review" not in schema_module.REQUIRED_EVIDENCE_FIELDS


def test_optional_vao_fields_tuple_exists(schema_module):
    """OPTIONAL_VAO_FIELDS includes the new field."""
    assert hasattr(schema_module, "OPTIONAL_VAO_FIELDS")
    assert "interactions_honored_review" in schema_module.OPTIONAL_VAO_FIELDS


def test_valid_interactions_honored_values_set(schema_module):
    assert schema_module.VALID_INTERACTIONS_HONORED_VALUES == {"pass", "n/a", "fail"}


# ===========================================================================
# CLI subcommand
# ===========================================================================


def test_cli_exits_zero_on_pass(plugin_root: Path, tmp_path: Path):
    import subprocess, sys
    components_path = tmp_path / "components.json"
    oracle_path = tmp_path / "oracle.json"
    components_path.write_text(json.dumps([]), encoding="utf-8")
    oracle_path.write_text(json.dumps({}), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(plugin_root / "hooks" / "vao_tools.py"),
         "verify-interactions-honored",
         "--components", str(components_path),
         "--oracle", str(oracle_path),
         "--out", str(tmp_path / "v.json")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_cli_exits_two_on_misroute(plugin_root: Path, tmp_path: Path):
    import subprocess, sys
    components_path = tmp_path / "components.json"
    oracle_path = tmp_path / "oracle.json"
    components_path.write_text(json.dumps([{
        "path": "p.tsx",
        "handlers": [{"trigger_selector": "#x", "action_kind": "navigate", "target_url_or_state": "/wrong"}],
    }]), encoding="utf-8")
    oracle_path.write_text(json.dumps({
        "interactions": [{
            "trigger_selector": "#x",
            "action_kind": "navigate",
            "target_url_or_state": "/right",
        }],
    }), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(plugin_root / "hooks" / "vao_tools.py"),
         "verify-interactions-honored",
         "--components", str(components_path),
         "--oracle", str(oracle_path),
         "--out", str(tmp_path / "v.json")],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
