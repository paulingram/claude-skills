"""Layer 3 v2.10.0 tool — verify_no_end_of_run_deferral.

These tests pin the 11th deterministic verification tool's contract: positive
+ negative for each of the 3 severities (deferred-work-catalog /
followup-decision-question / wrap-up-with-known-bugs), the canonical marker
allowlists (_DEFERRAL_CATALOG_MARKERS, _FOLLOWUP_QUESTION_MARKERS), determinism
(sorted-keys + indent=2 bit-stable output), the canonical synthetic-fixture
round-trip, and the CLI subcommand exit codes.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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
def fixture_path(plugin_root: Path) -> Path:
    return plugin_root / "tests" / "fixtures" / "vao" / "in-scope-deferral-cluster-list.json"


@pytest.fixture(scope="module")
def fixture_data(fixture_path: Path) -> dict:
    return json.loads(fixture_path.read_text())


# ─────────────────────────────────────────────────────────────────────────────
# Tool existence + verdict shape
# ─────────────────────────────────────────────────────────────────────────────

def test_tool_function_exists(vao_tools):
    assert callable(getattr(vao_tools, "verify_no_end_of_run_deferral", None))


def test_verdict_shape_has_required_keys(vao_tools):
    v = vao_tools.verify_no_end_of_run_deferral({})
    for key in ("tool", "valid", "gaps", "verdict_at"):
        assert key in v
    assert v["tool"] == "verify-no-end-of-run-deferral"


def test_empty_artifact_trivially_passes(vao_tools):
    v = vao_tools.verify_no_end_of_run_deferral({})
    assert v["valid"] is True
    assert v["gaps"] == []


def test_none_artifact_trivially_passes(vao_tools):
    v = vao_tools.verify_no_end_of_run_deferral(None)
    assert v["valid"] is True


def test_empty_final_report_trivially_passes(vao_tools):
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": ""})
    assert v["valid"] is True
    assert v["gaps"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Marker constants
# ─────────────────────────────────────────────────────────────────────────────

def test_deferral_catalog_markers_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_DEFERRAL_CATALOG_MARKERS")


def test_deferral_catalog_markers_has_at_least_12(vao_tools):
    assert len(vao_tools._DEFERRAL_CATALOG_MARKERS) >= 12


def test_followup_question_markers_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_FOLLOWUP_QUESTION_MARKERS")


def test_followup_question_markers_has_at_least_10(vao_tools):
    assert len(vao_tools._FOLLOWUP_QUESTION_MARKERS) >= 10


def test_item_disposition_citations_exist(vao_tools):
    assert hasattr(vao_tools, "_ITEM_DISPOSITION_CITATIONS")
    # SR / confirmed-stub / commit citations must be in the allowlist
    blob = " ".join(vao_tools._ITEM_DISPOSITION_CITATIONS).lower()
    assert "sr-" in blob
    assert "confirmed" in blob or "commit" in blob


# ─────────────────────────────────────────────────────────────────────────────
# 12 deferral-catalog markers — each fires `deferred-work-catalog`
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("marker_text", [
    "⏳ Deferred",
    "Deferred — ",
    "cluster-by-cluster",
    "A → B → C",
    "A -> B -> C",
    "each a real change",
    "not a one-liner",
    "I'd take them",
    "Defer to a future change",
    "punt to later",
    "pick up next time",
    "out of scope for this session",
])
def test_deferral_catalog_marker_fires(vao_tools, marker_text):
    report = f"Some context. {marker_text} more text here."
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    severities = {g["severity"] for g in v["gaps"]}
    assert "deferred-work-catalog" in severities, (
        f"marker {marker_text!r} did not fire deferred-work-catalog"
    )


def test_clean_report_no_deferral_catalog_marker(vao_tools):
    report = "All items fixed. Tests pass. Run complete."
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    severities = {g["severity"] for g in v["gaps"]}
    assert "deferred-work-catalog" not in severities


# ─────────────────────────────────────────────────────────────────────────────
# 10 followup-question markers — each fires `followup-decision-question`
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("marker_text", [
    "Want me to continue",
    "Your call",
    "ideally in a fresh context",
    "say the word",
    "let me know if",
    "Shall I proceed",
    "Do you want me to",
    "Should I take",
    "Is it OK if I",
    "If you'd like",
])
def test_followup_question_marker_fires(vao_tools, marker_text):
    report = f"Done with first phase. {marker_text} the rest?"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    severities = {g["severity"] for g in v["gaps"]}
    assert "followup-decision-question" in severities, (
        f"marker {marker_text!r} did not fire followup-decision-question"
    )


def test_clean_report_no_followup_question(vao_tools):
    report = "All 11 items dispositioned. Run complete."
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    severities = {g["severity"] for g in v["gaps"]}
    assert "followup-decision-question" not in severities


# ─────────────────────────────────────────────────────────────────────────────
# wrap-up-with-known-bugs
# ─────────────────────────────────────────────────────────────────────────────

def test_enumerated_items_without_disposition_fires(vao_tools):
    """A bulleted list of ≥ 3 items with no disposition citations fires."""
    report = (
        "Run summary:\n"
        "- Bug #1: not fixed yet\n"
        "- Bug #2: needs more investigation\n"
        "- Bug #3: too complex for this session\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" in severities


def test_enumerated_items_with_sr_disposition_does_not_fire(vao_tools):
    """A bulleted list with SR citations is dispositioned → no fire."""
    report = (
        "Run summary:\n"
        "- Bug #1: SR-101 routed (cross-layer-backend-required)\n"
        "- Bug #2: SR-102 routed (interaction-gap)\n"
        "- Bug #3: SR-103 routed (live-data-wiring-gap)\n"
    )
    artifact = {
        "final_report": report,
        "solution_requirements_created": [
            {"id": "SR-101"}, {"id": "SR-102"}, {"id": "SR-103"},
        ],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" not in severities


def test_enumerated_items_with_commit_disposition_does_not_fire(vao_tools):
    """Items citing commit-sha → dispositioned."""
    report = (
        "Run summary:\n"
        "- Bug #1 — commit-sha:abc123\n"
        "- Bug #2 — commit-sha:def456\n"
        "- Bug #3 — commit-sha:ghi789\n"
    )
    artifact = {
        "final_report": report,
        "implementing_commits": ["abc123", "def456", "ghi789"],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" not in severities


def test_enumerated_items_with_confirmed_stub_does_not_fire(vao_tools):
    """Items citing confirmed-stub → dispositioned."""
    report = (
        "Run summary:\n"
        "- Item #1: confirmed_stub (user_confirmed_at 2026-06-01)\n"
        "- Item #2: confirmed-stub (user_confirmed_at 2026-06-01)\n"
        "- Item #3: confirmed_stub (user_confirmed_at 2026-06-01)\n"
    )
    artifact = {
        "final_report": report,
        "confirmed_stubs": [
            {"path": "#1"}, {"path": "#2"}, {"path": "#3"},
        ],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" not in severities


def test_two_or_fewer_bullets_does_not_fire(vao_tools):
    """Under-threshold bullets (< 3) do not fire wrap-up-with-known-bugs."""
    report = (
        "Two known issues:\n"
        "- thing one\n"
        "- thing two\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" not in severities


# ─────────────────────────────────────────────────────────────────────────────
# Determinism contract
# ─────────────────────────────────────────────────────────────────────────────

def test_deterministic_output_modulo_timestamp(vao_tools, fixture_data):
    a = fixture_data["verification_artifact"]
    v1 = vao_tools.verify_no_end_of_run_deferral(a)
    v2 = vao_tools.verify_no_end_of_run_deferral(a)
    v1.pop("verdict_at", None)
    v2.pop("verdict_at", None)
    assert json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)


def test_written_file_is_sorted_keys_indent_2(vao_tools, fixture_data, tmp_path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_no_end_of_run_deferral(fixture_data["verification_artifact"], out_path=out)
    raw = out.read_text()
    parsed = json.loads(raw)
    expected = json.dumps(parsed, sort_keys=True, indent=2)
    assert raw.strip() == expected.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Canonical fixture round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_fixture_bad_fires_all_three_severities(vao_tools, fixture_data):
    v = vao_tools.verify_no_end_of_run_deferral(fixture_data["verification_artifact"])
    assert v["valid"] is False
    severities = {g["severity"] for g in v["gaps"]}
    assert "deferred-work-catalog" in severities
    assert "followup-decision-question" in severities
    assert "wrap-up-with-known-bugs" in severities


def test_fixture_corrected_passes(vao_tools, fixture_data):
    v = vao_tools.verify_no_end_of_run_deferral(fixture_data["_corrected_verification_artifact"])
    assert v["valid"] is True
    assert v["gaps"] == []


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _run_cli(plugin_root: Path, artifact_path: Path, out_path: Path) -> int:
    cmd = [
        sys.executable,
        str(plugin_root / "hooks" / "vao_tools.py"),
        "verify-no-end-of-run-deferral",
        "--artifact", str(artifact_path),
        "--out", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode


def test_cli_exits_0_on_clean(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["_corrected_verification_artifact"]))
    rc = _run_cli(plugin_root, art, out)
    assert rc == 0


def test_cli_exits_nonzero_on_bad(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["verification_artifact"]))
    rc = _run_cli(plugin_root, art, out)
    assert rc != 0


# ─────────────────────────────────────────────────────────────────────────────
# v2.12.0 — Cross-discipline gate consistency regressions
# ─────────────────────────────────────────────────────────────────────────────


def test_v211_per_persona_success_report_does_not_trip_v210_wrap_up(vao_tools):
    """v2.12.0 fix — a legitimate v2.11.0 per-persona success report
    enumerating 4 personas with `tested green` outcomes used to trip
    v2.10.0's `wrap-up-with-known-bugs` because `_ITEM_DISPOSITION_CITATIONS`
    didn't recognize per-persona disposition channels. The fix extended the
    citation list to include `playwright_test_runs` / `per_persona_findings`
    / `tested green` / `persona_id:` / `entry_point:`."""
    report = (
        "All 4 personas tested with full path coverage:\n"
        "\n"
        "- client-email-link: tested green; entry_point opened; "
        "cross-persona sync to title-agency asserted\n"
        "- title-agency-intake: tested green; form saves; attorney sees the change\n"
        "- attorney-dashboard: tested green; all roles render\n"
        "- family-member-intake: tested green; loading state surfaces\n"
        "\n"
        "Per-persona Playwright runs all green. Run complete.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" not in severities, (
        "v2.11.0 success report wrongly fires v2.10.0 wrap-up-with-known-bugs"
    )


def test_playwright_test_runs_array_counts_as_disposition(vao_tools):
    """A verification artifact carrying playwright_test_runs[] is sufficient
    disposition — even when the report has no inline citation tokens."""
    report = (
        "Run summary:\n"
        "- item alpha: done\n"
        "- item beta: done\n"
        "- item gamma: done\n"
    )
    artifact = {
        "final_report": report,
        "playwright_test_runs": [
            {"persona_id": "a"}, {"persona_id": "b"}, {"persona_id": "c"},
        ],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" not in severities


def test_per_persona_findings_object_counts_as_disposition(vao_tools):
    """A verification artifact carrying per_persona_findings is sufficient
    disposition."""
    report = (
        "Run summary:\n"
        "- item alpha: done\n"
        "- item beta: done\n"
        "- item gamma: done\n"
    )
    artifact = {
        "final_report": report,
        "per_persona_findings": {"personas_total": 3, "personas_tested": 3, "gaps": []},
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "wrap-up-with-known-bugs" not in severities


def test_heirship_deferral_still_fires_after_v212_widening(vao_tools, fixture_data):
    """Regression — widening the disposition channels must NOT weaken the
    detection of the verbatim heirship deferral case. The v2.10.0 fixture
    must continue to fire all 3 severities."""
    v = vao_tools.verify_no_end_of_run_deferral(fixture_data["verification_artifact"])
    severities = {g["severity"] for g in v["gaps"]}
    assert "deferred-work-catalog" in severities
    assert "followup-decision-question" in severities
    assert "wrap-up-with-known-bugs" in severities


def test_disposition_citations_constant_includes_v211_tokens(vao_tools):
    """The v2.12.0 widening must include the persona-coverage citation tokens."""
    blob = " ".join(vao_tools._ITEM_DISPOSITION_CITATIONS).lower()
    assert "playwright_test_runs" in blob
    assert "per_persona_findings" in blob
    assert "tested green" in blob or "tested-green" in blob
    assert "persona_id" in blob
    # And the prior v2.10.0 tokens remain.
    assert "commit-sha:" in vao_tools._ITEM_DISPOSITION_CITATIONS
    assert "SR-" in vao_tools._ITEM_DISPOSITION_CITATIONS
    assert "confirmed_stub" in vao_tools._ITEM_DISPOSITION_CITATIONS
