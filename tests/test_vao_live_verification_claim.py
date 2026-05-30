"""Layer 3 v2.2.0 tool — verify_live_verification_claim.

These tests pin the 7th deterministic verification tool's contract: positive
+ negative for each of the 6 severities (gesture-substitution /
self-verification-loop / prefill-masking / missing-screenshot /
missing-deployed-url / missing-semantic-assertion), determinism (sorted-keys
+ indent=2 bit-stable output), the 3 canonical synthetic-fixture round-trips,
the OPTIONAL schema v7 field semantics, and the CLI subcommand exit codes.
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


def _valid_artifact() -> dict:
    """A clean verification artifact that passes all 6 checks."""
    return {
        "target_url": "https://heirship-app-v2.example.com",
        "screenshot_path": "/tmp/screenshot.png",
        "click_targets": [
            {"selector": "input[name=affiant-email]", "coord": [620, 412]}
        ],
        "assertions": [
            "expect(page.locator('[role=menu]')).toHaveCount(0)",
            "expect(page.locator('input[name=affiant-email]')).toBeFocused()",
        ],
        "setup_actions": [
            "await page.goto('https://heirship-app-v2.example.com/matter/new')",
            "await page.click('button[data-testid=affiant-dropdown-trigger]')",
        ],
        "observed_state": "Dropdown open before assertion",
    }


def _valid_bug() -> dict:
    return {
        "summary": "Dropdown doesn't close when clicking another field",
        "gesture_pattern": "click any sibling field to close the dropdown",
        "requires_blank_state": False,
    }


# ===========================================================================
# Tool — empty input + clean-artifact passes
# ===========================================================================


def test_tool_exists(vao_tools):
    assert hasattr(vao_tools, "verify_live_verification_claim")
    assert callable(vao_tools.verify_live_verification_claim)


def test_clean_artifact_passes(vao_tools):
    v = vao_tools.verify_live_verification_claim(
        verification_artifact=_valid_artifact(),
        bug_description=_valid_bug(),
    )
    assert v["tool"] == "verify-live-verification-claim"
    assert v["valid"] is True
    assert v["gaps"] == []


def test_empty_artifact_fires_missing_fields(vao_tools):
    """Empty artifact should fire 3 'missing-*' severities (no URL, no screenshot, no assertions)."""
    v = vao_tools.verify_live_verification_claim(
        verification_artifact={},
        bug_description={},
    )
    assert v["valid"] is False
    severities = {g["severity"] for g in v["gaps"]}
    assert "missing-deployed-url" in severities
    assert "missing-screenshot" in severities
    assert "missing-semantic-assertion" in severities


def test_none_inputs_dont_raise(vao_tools):
    v = vao_tools.verify_live_verification_claim(None, None)
    assert v["tool"] == "verify-live-verification-claim"
    assert isinstance(v["gaps"], list)


# ===========================================================================
# Severity 1 — gesture-substitution
# ===========================================================================


def test_gesture_substitution_corner_coord(vao_tools):
    art = _valid_artifact()
    art["click_targets"] = [{"selector": "body", "coord": [8, 8]}]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "gesture-substitution" for g in v["gaps"])


def test_gesture_substitution_origin_coord(vao_tools):
    art = _valid_artifact()
    art["click_targets"] = [{"selector": "div.modal", "coord": [0, 0]}]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "gesture-substitution" for g in v["gaps"])


def test_gesture_substitution_backdrop_selector(vao_tools):
    art = _valid_artifact()
    art["click_targets"] = [{"selector": "[role=\"presentation\"]", "coord": [400, 300]}]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "gesture-substitution" for g in v["gaps"])


def test_gesture_substitution_data_backdrop_selector(vao_tools):
    art = _valid_artifact()
    art["click_targets"] = [{"selector": "[data-backdrop]", "coord": [500, 200]}]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "gesture-substitution" for g in v["gaps"])


def test_intended_backdrop_close_is_allowed(vao_tools):
    """When the click IS intended as a backdrop-close gesture, it's not a substitution."""
    art = _valid_artifact()
    art["click_targets"] = [{
        "selector": "body",
        "coord": [400, 300],
        "intended_backdrop_close": True,
    }]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    severities = {g["severity"] for g in v["gaps"]}
    assert "gesture-substitution" not in severities


def test_real_user_target_passes(vao_tools):
    art = _valid_artifact()  # already has input[name=affiant-email] at (620, 412)
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is True


# ===========================================================================
# Severity 2 — self-verification-loop
# ===========================================================================


def test_self_verification_loop_detected(vao_tools):
    art = _valid_artifact()
    art["test_source_created_at"] = "2026-05-30T15:23:00Z"
    art["fix_session_started_at"] = "2026-05-30T14:55:00Z"
    art["test_assertions"] = ["expect(checkpointBtn.isDisabled()).toBe(true)"]
    art["fix_diff_strings"] = ["expect(checkpointBtn.isDisabled())"]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "self-verification-loop" for g in v["gaps"])


def test_test_authored_before_session_is_clean(vao_tools):
    """If the test was authored BEFORE the fix session started, it's independent."""
    art = _valid_artifact()
    art["test_source_created_at"] = "2026-05-30T12:00:00Z"
    art["fix_session_started_at"] = "2026-05-30T14:55:00Z"
    art["test_assertions"] = ["expect(checkpointBtn.isDisabled()).toBe(true)"]
    art["fix_diff_strings"] = ["expect(checkpointBtn.isDisabled())"]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    severities = {g["severity"] for g in v["gaps"]}
    assert "self-verification-loop" not in severities


def test_assertion_unrelated_to_fix_is_clean(vao_tools):
    art = _valid_artifact()
    art["test_source_created_at"] = "2026-05-30T15:23:00Z"
    art["fix_session_started_at"] = "2026-05-30T14:55:00Z"
    art["test_assertions"] = ["expect(some.UnrelatedThing).toBeVisible()"]
    art["fix_diff_strings"] = ["modified the auth handler"]
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    severities = {g["severity"] for g in v["gaps"]}
    assert "self-verification-loop" not in severities


def test_short_diff_strings_dont_match(vao_tools):
    """Short fix-diff substrings (< 6 chars) don't trigger the loop check."""
    art = _valid_artifact()
    art["test_source_created_at"] = "2026-05-30T15:23:00Z"
    art["fix_session_started_at"] = "2026-05-30T14:55:00Z"
    art["test_assertions"] = ["expect(thing).toBe(true)"]
    art["fix_diff_strings"] = ["if", "true", "()"]  # all < 6 chars
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    severities = {g["severity"] for g in v["gaps"]}
    assert "self-verification-loop" not in severities


# ===========================================================================
# Severity 3 — prefill-masking
# ===========================================================================


def test_prefill_masking_carter_demo(vao_tools):
    art = _valid_artifact()
    art["setup_actions"] = ["await page.goto('/matter/carter-demo')"]
    art["observed_state"] = "Family History step shows 12/12 answered"
    bug = _valid_bug()
    bug["requires_blank_state"] = True
    v = vao_tools.verify_live_verification_claim(art, bug)
    assert v["valid"] is False
    assert any(g["severity"] == "prefill-masking" for g in v["gaps"])


def test_prefill_masking_all_complete_marker(vao_tools):
    art = _valid_artifact()
    art["setup_actions"] = ["loadFixtureMatter('seeded-matter-001')"]
    art["observed_state"] = "step shows all-complete"
    bug = _valid_bug()
    bug["requires_blank_state"] = True
    v = vao_tools.verify_live_verification_claim(art, bug)
    assert any(g["severity"] == "prefill-masking" for g in v["gaps"])


def test_prefill_masking_100pct(vao_tools):
    art = _valid_artifact()
    art["setup_actions"] = ["await page.goto('/matter/demo-matter-123')"]
    art["observed_state"] = "progress: 100%"
    bug = _valid_bug()
    bug["requires_blank_state"] = True
    v = vao_tools.verify_live_verification_claim(art, bug)
    assert any(g["severity"] == "prefill-masking" for g in v["gaps"])


def test_demo_matter_but_bug_doesnt_need_blank_state_is_clean(vao_tools):
    """If the bug doesn't require blank state, loading a demo matter is fine."""
    art = _valid_artifact()
    art["setup_actions"] = ["await page.goto('/matter/carter-demo')"]
    art["observed_state"] = "N/N answered"
    bug = _valid_bug()
    bug["requires_blank_state"] = False
    v = vao_tools.verify_live_verification_claim(art, bug)
    severities = {g["severity"] for g in v["gaps"]}
    assert "prefill-masking" not in severities


def test_blank_state_test_against_demo_is_clean(vao_tools):
    """If the bug requires blank state AND the test reaches a genuinely-blank step, it's clean."""
    art = _valid_artifact()
    art["setup_actions"] = ["await page.goto('/matter/new')"]
    art["observed_state"] = "Estate step: 0/4 answered"
    bug = _valid_bug()
    bug["requires_blank_state"] = True
    v = vao_tools.verify_live_verification_claim(art, bug)
    severities = {g["severity"] for g in v["gaps"]}
    assert "prefill-masking" not in severities


# ===========================================================================
# Severity 4-6 — missing-* severities
# ===========================================================================


def test_missing_screenshot(vao_tools):
    art = _valid_artifact()
    art["screenshot_path"] = None
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "missing-screenshot" for g in v["gaps"])


def test_missing_deployed_url(vao_tools):
    art = _valid_artifact()
    art["target_url"] = None
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "missing-deployed-url" for g in v["gaps"])


def test_localhost_url_fires_missing_deployed(vao_tools):
    art = _valid_artifact()
    art["target_url"] = "http://localhost:3000"
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "missing-deployed-url" for g in v["gaps"])


def test_127_url_fires_missing_deployed(vao_tools):
    art = _valid_artifact()
    art["target_url"] = "https://127.0.0.1:8080"
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert any(g["severity"] == "missing-deployed-url" for g in v["gaps"])


def test_file_url_fires_missing_deployed(vao_tools):
    art = _valid_artifact()
    art["target_url"] = "file:///tmp/index.html"
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert any(g["severity"] == "missing-deployed-url" for g in v["gaps"])


def test_missing_semantic_assertion(vao_tools):
    art = _valid_artifact()
    art["assertions"] = []
    v = vao_tools.verify_live_verification_claim(art, _valid_bug())
    assert v["valid"] is False
    assert any(g["severity"] == "missing-semantic-assertion" for g in v["gaps"])


# ===========================================================================
# Determinism contract
# ===========================================================================


def test_deterministic_output(vao_tools, tmp_path: Path):
    """Two invocations with the same inputs produce byte-identical output
    (modulo verdict_at)."""
    art = _valid_artifact()
    bug = _valid_bug()
    v1 = vao_tools.verify_live_verification_claim(art, bug, out_path=tmp_path / "v1.json")
    v2 = vao_tools.verify_live_verification_claim(art, bug, out_path=tmp_path / "v2.json")
    v1.pop("verdict_at")
    v2.pop("verdict_at")
    assert v1 == v2


def test_writes_verdict_file(vao_tools, tmp_path: Path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_live_verification_claim(
        verification_artifact=_valid_artifact(),
        bug_description=_valid_bug(),
        out_path=out,
    )
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["tool"] == "verify-live-verification-claim"


def test_sorted_keys_in_output(vao_tools, tmp_path: Path):
    out = tmp_path / "v.json"
    vao_tools.verify_live_verification_claim(
        verification_artifact=_valid_artifact(),
        bug_description=_valid_bug(),
        out_path=out,
    )
    raw = out.read_text()
    assert raw.index('"gaps"') < raw.index('"tool"') < raw.index('"valid"') < raw.index('"verdict_at"')


# ===========================================================================
# Synthetic fixture round-trips
# ===========================================================================


@pytest.fixture(scope="module")
def fixture_gesture(plugin_root: Path):
    return json.loads(
        (plugin_root / "tests" / "fixtures" / "vao" / "gesture-substitution-corner-click.json").read_text()
    )


@pytest.fixture(scope="module")
def fixture_loop(plugin_root: Path):
    return json.loads(
        (plugin_root / "tests" / "fixtures" / "vao" / "self-authored-unit-test-loop.json").read_text()
    )


@pytest.fixture(scope="module")
def fixture_prefill(plugin_root: Path):
    return json.loads(
        (plugin_root / "tests" / "fixtures" / "vao" / "prefill-masking-demo-matter.json").read_text()
    )


def test_fixture_gesture_caught(vao_tools, fixture_gesture):
    v = vao_tools.verify_live_verification_claim(
        verification_artifact=fixture_gesture["verification_artifact"],
        bug_description=fixture_gesture["bug_description"],
    )
    assert v["valid"] is False
    severities = {g["severity"] for g in v["gaps"]}
    assert "gesture-substitution" in severities


def test_fixture_loop_caught(vao_tools, fixture_loop):
    v = vao_tools.verify_live_verification_claim(
        verification_artifact=fixture_loop["verification_artifact"],
        bug_description=fixture_loop["bug_description"],
    )
    assert v["valid"] is False
    severities = {g["severity"] for g in v["gaps"]}
    assert "self-verification-loop" in severities


def test_fixture_prefill_caught(vao_tools, fixture_prefill):
    v = vao_tools.verify_live_verification_claim(
        verification_artifact=fixture_prefill["verification_artifact"],
        bug_description=fixture_prefill["bug_description"],
    )
    assert v["valid"] is False
    severities = {g["severity"] for g in v["gaps"]}
    assert "prefill-masking" in severities


def test_fixture_gesture_corrected_passes(vao_tools, fixture_gesture):
    """The fixture also carries _corrected_verification_artifact showing what
    a valid verification looks like — confirm it passes."""
    v = vao_tools.verify_live_verification_claim(
        verification_artifact=fixture_gesture["_corrected_verification_artifact"],
        bug_description=fixture_gesture["bug_description"],
    )
    assert v["valid"] is True


def test_fixture_loop_corrected_passes(vao_tools, fixture_loop):
    v = vao_tools.verify_live_verification_claim(
        verification_artifact=fixture_loop["_corrected_verification_artifact"],
        bug_description=fixture_loop["bug_description"],
    )
    assert v["valid"] is True


def test_fixture_prefill_corrected_passes(vao_tools, fixture_prefill):
    v = vao_tools.verify_live_verification_claim(
        verification_artifact=fixture_prefill["_corrected_verification_artifact"],
        bug_description=fixture_prefill["bug_description"],
    )
    assert v["valid"] is True


# ===========================================================================
# CLI subcommand
# ===========================================================================


def test_cli_exits_zero_on_valid(plugin_root: Path, tmp_path: Path):
    import subprocess, sys
    art_path = tmp_path / "art.json"
    bug_path = tmp_path / "bug.json"
    art_path.write_text(json.dumps(_valid_artifact()))
    bug_path.write_text(json.dumps(_valid_bug()))
    r = subprocess.run(
        [sys.executable, str(plugin_root / "hooks" / "vao_tools.py"),
         "verify-live-verification-claim",
         "--artifact", str(art_path),
         "--bug", str(bug_path),
         "--out", str(tmp_path / "v.json")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_cli_exits_two_on_gesture_substitution(plugin_root: Path, tmp_path: Path):
    import subprocess, sys
    art = _valid_artifact()
    art["click_targets"] = [{"selector": "body", "coord": [8, 8]}]
    art_path = tmp_path / "art.json"
    bug_path = tmp_path / "bug.json"
    art_path.write_text(json.dumps(art))
    bug_path.write_text(json.dumps(_valid_bug()))
    r = subprocess.run(
        [sys.executable, str(plugin_root / "hooks" / "vao_tools.py"),
         "verify-live-verification-claim",
         "--artifact", str(art_path),
         "--bug", str(bug_path),
         "--out", str(tmp_path / "v.json")],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


# ===========================================================================
# Schema v7 — optional live_verification_review field
# ===========================================================================


def _minimal_v7_evidence() -> dict:
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
    """v2.0.0 / v2.1.0 evidence files (no live_verification_review) remain valid."""
    ev = _minimal_v7_evidence()
    assert "live_verification_review" not in ev
    gaps = schema_module.validate_evidence(ev)
    assert gaps == [], f"absent optional field must not yield gaps; gaps={gaps}"


def test_optional_field_pass_does_not_block(schema_module):
    ev = _minimal_v7_evidence()
    ev["live_verification_review"] = "pass"
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_na_with_note_does_not_block(schema_module):
    ev = _minimal_v7_evidence()
    ev["live_verification_review"] = "n/a"
    ev["live_verification_review_note"] = "no 'verified live' claim in this evidence"
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_fail_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["live_verification_review"] = "fail"
    gaps = schema_module.validate_evidence(ev)
    assert gaps
    assert any("live_verification_review" in g for g in gaps)


def test_optional_field_dict_shape_with_verdict_path(schema_module):
    ev = _minimal_v7_evidence()
    ev["live_verification_review"] = {
        "verdict": "pass",
        "verdict_path": ".architect-team/vao-verdicts/T-1-live-verification.json",
    }
    gaps = schema_module.validate_evidence(ev)
    assert gaps == []


def test_optional_field_dict_shape_missing_verdict_path_blocks(schema_module):
    ev = _minimal_v7_evidence()
    ev["live_verification_review"] = {"verdict": "pass"}
    gaps = schema_module.validate_evidence(ev)
    assert any("verdict_path" in g for g in gaps)


def test_required_fields_unchanged(schema_module):
    """v2.2.0 — REQUIRED_EVIDENCE_FIELDS still has 17."""
    assert len(schema_module.REQUIRED_EVIDENCE_FIELDS) == 17
    assert "live_verification_review" not in schema_module.REQUIRED_EVIDENCE_FIELDS


def test_optional_vao_fields_tuple_includes_v2_2_0(schema_module):
    """OPTIONAL_VAO_FIELDS now includes both v2.1.0 and v2.2.0 fields."""
    assert "interactions_honored_review" in schema_module.OPTIONAL_VAO_FIELDS
    assert "live_verification_review" in schema_module.OPTIONAL_VAO_FIELDS


def test_valid_live_verification_values_set(schema_module):
    assert schema_module.VALID_LIVE_VERIFICATION_VALUES == {"pass", "n/a", "fail"}
