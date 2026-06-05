"""Tests for the v2.21.0 Layer 3 tool: verify_target_element_measured.

Covers the 3 severities (proxy-element-substituted /
unreachable-state-not-escalated / semantic-target-mismatch), the marker-text
backup detector, module constants, helper normalizers, fixture round-trip,
determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.vao_tools import (
    _PROXY_SUBSTITUTION_MARKERS,
    _REACHABILITY_NOT_REACHED_VALUES,
    _UNREACHABLE_STATE_MARKERS,
    _normalize_selector,
    _selectors_match,
    _semantic_labels_match,
    verify_target_element_measured,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "proxy-element-substituted.json"


# ---- module constants ----


def test_proxy_substitution_markers_include_substitution_language() -> None:
    for m in ("measured a different element", "off that proxy", "as a proxy"):
        assert m in _PROXY_SUBSTITUTION_MARKERS


def test_proxy_substitution_markers_include_fallback_language() -> None:
    for m in ("fell back to measuring", "the closest measurable", "the sibling element"):
        assert m in _PROXY_SUBSTITUTION_MARKERS


def test_proxy_substitution_markers_include_confession_language() -> None:
    for m in ("did not visually confirm", "i wrongly reported", "passing off"):
        assert m in _PROXY_SUBSTITUTION_MARKERS


def test_unreachable_state_markers_include_user_phrases() -> None:
    for m in ("couldn't reach", "could not reach", "every day had"):
        assert m in _UNREACHABLE_STATE_MARKERS


def test_reachability_not_reached_values_include_canonical_values() -> None:
    for v in ("unreachable", "state-not-triggered", "fixture-did-not-produce-target-state"):
        assert v in _REACHABILITY_NOT_REACHED_VALUES


# ---- selector normalization ----


def test_normalize_selector_lowercases() -> None:
    assert _normalize_selector("[Data-TestID=\"X\"]") == "[data-testid=\"x\"]"


def test_normalize_selector_handles_whitespace() -> None:
    assert _normalize_selector("  div   .x   ") == "div .x"


def test_normalize_selector_sorts_alternates() -> None:
    a = _normalize_selector("b, a, c")
    b = _normalize_selector("c, b, a")
    assert a == b


def test_selectors_match_handles_whitespace_variants() -> None:
    assert _selectors_match("div .x", "div  .x") is True


def test_selectors_match_lowercase_insensitive() -> None:
    assert _selectors_match("[data-testid='X']", "[data-testid='x']") is True


def test_selectors_dont_match_when_different() -> None:
    assert _selectors_match("[data-testid='a']", "[data-testid='b']") is False


def test_selectors_both_none_match() -> None:
    assert _selectors_match(None, None) is True


def test_selectors_one_none_dont_match() -> None:
    assert _selectors_match("[data-testid='x']", None) is False


# ---- semantic-label normalization ----


def test_semantic_labels_match_case_insensitive() -> None:
    assert _semantic_labels_match("No Patients Monitored", "no patients monitored") is True


def test_semantic_labels_match_hyphen_vs_space() -> None:
    assert _semantic_labels_match("no-patients-monitored", "no patients monitored") is True


def test_semantic_labels_dont_match_when_different() -> None:
    assert _semantic_labels_match("empty state", "coverage badge") is False


# ---- severity 1: proxy-element-substituted (structured) ----


def test_proxy_severity_fires_on_selector_mismatch_with_passing() -> None:
    v = verify_target_element_measured({
        "target_element_selector": "[data-testid='a']",
        "measured_element_selector": "[data-testid='b']",
        "verdict": "passing",
    })
    assert v["valid"] is False
    assert any(g["severity"] == "proxy-element-substituted" for g in v["gaps"])


def test_proxy_severity_does_not_fire_when_verdict_not_passing() -> None:
    v = verify_target_element_measured({
        "target_element_selector": "[data-testid='a']",
        "measured_element_selector": "[data-testid='b']",
        "verdict": "bug-still-present",
    })
    assert all(g["severity"] != "proxy-element-substituted" for g in v["gaps"])


def test_proxy_severity_does_not_fire_when_selectors_match() -> None:
    v = verify_target_element_measured({
        "target_element_selector": "[data-testid='a']",
        "measured_element_selector": "[data-testid='a']",
        "verdict": "passing",
    })
    assert v["valid"] is True


# ---- severity 2: unreachable-state-not-escalated ----


def test_unreachable_severity_fires_on_unreachable_with_passing() -> None:
    v = verify_target_element_measured({
        "reachability_status": "unreachable",
        "verdict": "passing",
    })
    assert v["valid"] is False
    assert any(g["severity"] == "unreachable-state-not-escalated" for g in v["gaps"])


def test_unreachable_severity_fires_on_state_not_triggered() -> None:
    v = verify_target_element_measured({
        "reachability_status": "state-not-triggered",
        "verdict": "passing",
    })
    assert any(g["severity"] == "unreachable-state-not-escalated" for g in v["gaps"])


def test_unreachable_severity_does_not_fire_when_reached() -> None:
    v = verify_target_element_measured({
        "reachability_status": "reached",
        "target_element_selector": "[data-testid='a']",
        "measured_element_selector": "[data-testid='a']",
        "verdict": "passing",
    })
    assert all(g["severity"] != "unreachable-state-not-escalated" for g in v["gaps"])


def test_unreachable_severity_does_not_fire_when_verdict_not_passing() -> None:
    v = verify_target_element_measured({
        "reachability_status": "unreachable",
        "verdict": "cannot-verify",
    })
    assert all(g["severity"] != "unreachable-state-not-escalated" for g in v["gaps"])


# ---- severity 3: semantic-target-mismatch ----


def test_semantic_mismatch_fires_with_passing_verdict() -> None:
    v = verify_target_element_measured({
        "target_element_semantic_label": "empty state",
        "measured_element_semantic_label": "coverage badge label",
        "verdict": "passing",
    })
    assert v["valid"] is False
    assert any(g["severity"] == "semantic-target-mismatch" for g in v["gaps"])


def test_semantic_mismatch_does_not_fire_when_labels_match() -> None:
    v = verify_target_element_measured({
        "target_element_semantic_label": "empty state",
        "measured_element_semantic_label": "Empty State",
        "verdict": "passing",
    })
    assert all(g["severity"] != "semantic-target-mismatch" for g in v["gaps"])


# ---- marker-text backup detector ----


def test_marker_backup_fires_on_off_that_proxy_phrase() -> None:
    v = verify_target_element_measured({
        "verification_text": "I wrongly reported item 7 as passing off that proxy.",
    })
    assert v["valid"] is False
    assert any("off that proxy" in str(g.get("matched_markers") or "") for g in v["gaps"])


def test_marker_backup_fires_on_did_not_visually_confirm() -> None:
    v = verify_target_element_measured({
        "verification_notes": "no, I did not visually confirm the empty state."
    })
    assert v["valid"] is False


def test_marker_backup_does_not_fire_on_clean_text() -> None:
    v = verify_target_element_measured({
        "verification_text": "Asserted directly against the target element. Test passed.",
        "target_element_selector": "[data-testid='a']",
        "measured_element_selector": "[data-testid='a']",
        "reachability_status": "reached",
        "verdict": "passing",
    })
    assert v["valid"] is True


# ---- backwards-compat ----


def test_empty_artifact_passes_no_op() -> None:
    v = verify_target_element_measured({})
    assert v["valid"] is True
    assert v["gaps"] == []


def test_artifact_without_claims_passes() -> None:
    v = verify_target_element_measured({"verdict": "passing"})
    assert v["valid"] is True


# ---- fixture round-trip ----


def test_canonical_fixture_bad_fires_3_severities() -> None:
    fx = json.loads(FIXTURE.read_text())
    v = verify_target_element_measured(fx["verification_artifact"])
    assert v["valid"] is False
    sevs = sorted({g["severity"] for g in v["gaps"]})
    expected = sorted(fx["_meta"]["expected_severities"])
    assert sevs == expected


def test_canonical_fixture_corrected_passes() -> None:
    fx = json.loads(FIXTURE.read_text())
    v = verify_target_element_measured(fx["_corrected_verification_artifact"])
    assert v["valid"] is True


# ---- output shape ----


def test_output_carries_tool_name() -> None:
    v = verify_target_element_measured({})
    assert v["tool"] == "verify-target-element-measured"


def test_output_persists_to_out_path(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    verify_target_element_measured({}, out_path=str(out))
    assert out.exists()
    persisted = json.loads(out.read_text())
    assert persisted["tool"] == "verify-target-element-measured"


# ---- determinism ----


def test_output_deterministic_on_stable_input() -> None:
    artifact = {
        "target_element_selector": "[data-testid='a']",
        "measured_element_selector": "[data-testid='b']",
        "verdict": "passing",
    }
    a = verify_target_element_measured(artifact)
    b = verify_target_element_measured(artifact)
    assert sorted((g["severity"] for g in a["gaps"])) == sorted((g["severity"] for g in b["gaps"]))
