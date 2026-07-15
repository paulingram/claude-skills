"""Layer 3 v2.14.0 tool — verify_no_implementation_scope_cut.

These tests pin the 14th deterministic verification tool's contract: positive
+ negative for each of the 3 severities (honest-scope-statement-emitted /
foundation-only-framing-with-full-build-mandate /
unilateral-implementation-scope-cut), the canonical marker allowlists,
determinism, fixture round-trip, CLI exit codes.
"""
from __future__ import annotations

from tests.helpers.module_loader import load_module
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def vao_tools(plugin_root: Path):
    mod = load_module(plugin_root / "hooks" / "vao_tools.py", "vao_tools")
    return mod


@pytest.fixture(scope="module")
def fixture_path(plugin_root: Path) -> Path:
    return plugin_root / "tests" / "fixtures" / "vao" / "honest-scope-statement-m0-foundation.json"


@pytest.fixture(scope="module")
def fixture_data(fixture_path: Path) -> dict:
    return json.loads(fixture_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Tool existence + verdict shape
# ─────────────────────────────────────────────────────────────────────────────

def test_tool_function_exists(vao_tools):
    assert callable(getattr(vao_tools, "verify_no_implementation_scope_cut", None))


def test_verdict_shape(vao_tools):
    v = vao_tools.verify_no_implementation_scope_cut({}, {})
    for key in ("tool", "valid", "gaps", "verdict_at"):
        assert key in v
    assert v["tool"] == "verify-no-implementation-scope-cut"


def test_empty_inputs_trivially_pass(vao_tools):
    v = vao_tools.verify_no_implementation_scope_cut({}, {})
    assert v["valid"] is True


def test_none_inputs_trivially_pass(vao_tools):
    v = vao_tools.verify_no_implementation_scope_cut(None, None)
    assert v["valid"] is True


def test_no_full_build_required_is_noop(vao_tools):
    """Even with the worst possible report, no-mandate is a no-op."""
    report = "⚠️ Honest scope statement. shippable-and-true. I stopped at the M0 boundary deliberately."
    v = vao_tools.verify_no_implementation_scope_cut({"final_report": report}, {})
    assert v["valid"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Marker constants
# ─────────────────────────────────────────────────────────────────────────────

def test_honest_scope_statement_markers_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_HONEST_SCOPE_STATEMENT_MARKERS")
    assert len(vao_tools._HONEST_SCOPE_STATEMENT_MARKERS) >= 12


def test_foundation_only_framing_markers_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_FOUNDATION_ONLY_FRAMING_MARKERS")
    assert len(vao_tools._FOUNDATION_ONLY_FRAMING_MARKERS) >= 6


def test_full_build_mandate_phrases_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_FULL_BUILD_MANDATE_PHRASES")
    blob = " ".join(vao_tools._FULL_BUILD_MANDATE_PHRASES).lower()
    assert "implement everything" in blob
    assert "build the whole thing" in blob
    assert "ship it all" in blob


def test_milestone_deferral_patterns_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_MILESTONE_DEFERRAL_PATTERNS")


# ─────────────────────────────────────────────────────────────────────────────
# 8 representative HONEST_SCOPE_STATEMENT markers — each fires
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("marker_text", [
    "Honest scope statement",
    "shippable-and-true",
    "I stopped at the M0",
    "stopped at the boundary deliberately",
    "rather than half-land",
    "multi-agent build on this foundation",
    "land incrementally without rework",
    "complete M0 foundation",
])
def test_honest_scope_statement_marker_fires(vao_tools, marker_text):
    report = f"Some context. {marker_text} more text here."
    mandate = {"full_build_required": True}
    v = vao_tools.verify_no_implementation_scope_cut(
        {"final_report": report}, mandate,
    )
    sev = {g["severity"] for g in v["gaps"]}
    assert "honest-scope-statement-emitted" in sev, (
        f"marker {marker_text!r} did not fire honest-scope-statement-emitted"
    )


def test_clean_report_no_honest_scope_marker(vao_tools):
    report = "All milestones complete. M1-M7 SRs routed for follow-up."
    # No HONEST markers but contains M1-M7 — still fires unilateral cut
    mandate = {"full_build_required": True}
    v = vao_tools.verify_no_implementation_scope_cut(
        {"final_report": report}, mandate,
    )
    sev = {g["severity"] for g in v["gaps"]}
    assert "honest-scope-statement-emitted" not in sev


# ─────────────────────────────────────────────────────────────────────────────
# foundation-only-framing
# ─────────────────────────────────────────────────────────────────────────────

def test_foundation_framing_fires_under_mandate(vao_tools):
    report = "M0 foundation deployed. Implementation paused at this layer."
    mandate = {"full_build_required": True}
    v = vao_tools.verify_no_implementation_scope_cut(
        {"final_report": report}, mandate,
    )
    sev = {g["severity"] for g in v["gaps"]}
    assert "foundation-only-framing-with-full-build-mandate" in sev


def test_foundation_framing_passes_with_scope_cut_SR(vao_tools):
    """A foundation-framing report passes when SRs cover the unimplemented portion."""
    report = "M0 foundation deployed."
    mandate = {"full_build_required": True}
    artifact = {
        "final_report": report,
        "solution_requirements_created": [
            {"id": "SR-1", "origin": {"kind": "incomplete-implementation-scope-required"}},
        ],
    }
    v = vao_tools.verify_no_implementation_scope_cut(artifact, mandate)
    sev = {g["severity"] for g in v["gaps"]}
    assert "foundation-only-framing-with-full-build-mandate" not in sev


# ─────────────────────────────────────────────────────────────────────────────
# unilateral-implementation-scope-cut
# ─────────────────────────────────────────────────────────────────────────────

def test_milestone_deferral_fires_under_mandate(vao_tools):
    report = "M0 done. milestones M1 through M7 left for future runs."
    mandate = {"full_build_required": True}
    v = vao_tools.verify_no_implementation_scope_cut(
        {"final_report": report}, mandate,
    )
    sev = {g["severity"] for g in v["gaps"]}
    assert "unilateral-implementation-scope-cut" in sev


def test_milestone_deferral_passes_with_scope_cut_SR(vao_tools):
    """Milestone-deferral report passes when SRs route the unimplemented portion."""
    report = "M0 done. milestones M1–M7 routed via SRs."
    mandate = {"full_build_required": True}
    artifact = {
        "final_report": report,
        "solution_requirements_created": [
            {"id": "SR-M1", "origin": {"kind": "incomplete-implementation-scope-required"}},
        ],
    }
    v = vao_tools.verify_no_implementation_scope_cut(artifact, mandate)
    sev = {g["severity"] for g in v["gaps"]}
    assert "unilateral-implementation-scope-cut" not in sev


# ─────────────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────────────

def test_deterministic_output_modulo_timestamp(vao_tools, fixture_data):
    a = fixture_data["verification_artifact"]
    m = fixture_data["scope_mandate"]
    v1 = vao_tools.verify_no_implementation_scope_cut(a, m)
    v2 = vao_tools.verify_no_implementation_scope_cut(a, m)
    v1.pop("verdict_at", None)
    v2.pop("verdict_at", None)
    assert json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)


def test_written_file_is_sorted_keys_indent_2(vao_tools, fixture_data, tmp_path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_no_implementation_scope_cut(
        fixture_data["verification_artifact"],
        fixture_data["scope_mandate"],
        out_path=out,
    )
    raw = out.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    expected = json.dumps(parsed, sort_keys=True, indent=2)
    assert raw.strip() == expected.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Canonical fixture round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_fixture_bad_fires_all_three_severities(vao_tools, fixture_data):
    v = vao_tools.verify_no_implementation_scope_cut(
        fixture_data["verification_artifact"],
        fixture_data["scope_mandate"],
    )
    assert v["valid"] is False
    sev = {g["severity"] for g in v["gaps"]}
    assert "honest-scope-statement-emitted" in sev
    assert "foundation-only-framing-with-full-build-mandate" in sev
    assert "unilateral-implementation-scope-cut" in sev


def test_fixture_corrected_passes(vao_tools, fixture_data):
    v = vao_tools.verify_no_implementation_scope_cut(
        fixture_data["_corrected_verification_artifact"],
        fixture_data["scope_mandate"],
    )
    assert v["valid"] is True
    assert v["gaps"] == []


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _run_cli(plugin_root: Path, artifact: Path, mandate: Path, out: Path) -> int:
    cmd = [
        sys.executable,
        str(plugin_root / "hooks" / "vao_tools.py"),
        "verify-no-implementation-scope-cut",
        "--artifact", str(artifact),
        "--mandate", str(mandate),
        "--out", str(out),
    ]
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def test_cli_exits_0_on_clean(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "art.json"
    man = tmp_path / "mandate.json"
    out = tmp_path / "out.json"
    art.write_text(json.dumps(fixture_data["_corrected_verification_artifact"]), encoding="utf-8")
    man.write_text(json.dumps(fixture_data["scope_mandate"]), encoding="utf-8")
    assert _run_cli(plugin_root, art, man, out) == 0


def test_cli_exits_nonzero_on_bad(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "art.json"
    man = tmp_path / "mandate.json"
    out = tmp_path / "out.json"
    art.write_text(json.dumps(fixture_data["verification_artifact"]), encoding="utf-8")
    man.write_text(json.dumps(fixture_data["scope_mandate"]), encoding="utf-8")
    assert _run_cli(plugin_root, art, man, out) != 0


# ─────────────────────────────────────────────────────────────────────────────
# Structural assertions for the canonical section + agent extensions
# ─────────────────────────────────────────────────────────────────────────────

def test_canonical_section_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "## No implementation-time scope cut discipline (v2.14.0)" in body


def test_canonical_section_appears_once(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.count("\n## No implementation-time scope cut discipline (v2.14.0)\n") == 1


def test_canonical_section_quotes_verbatim_user_prose(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "implement everything in full" in body
    assert "should never ever make such judgement" in body
    assert "M0 foundation" in body


@pytest.mark.parametrize("agent_file", [
    "system-architect.md",
    "frontend.md",
    "backend.md",
    "qa-replayer.md",
])
def test_agent_body_has_v2_14_0_section(plugin_root: Path, agent_file: str):
    agent = plugin_root / "agents" / agent_file
    body = agent.read_text(encoding="utf-8")
    assert "## No implementation-time scope cut discipline (v2.14.0)" in body
