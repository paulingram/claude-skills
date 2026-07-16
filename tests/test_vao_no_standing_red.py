"""Layer 3 v2.8.0 tool — verify_no_standing_red.

These tests pin the 10th deterministic verification tool's contract: positive
+ negative for each of the 2 severities (standing-red-committed /
cross-layer-fix-not-routed), determinism (sorted-keys + indent=2 bit-stable
output), the _STANDING_RED_MARKERS constant, the canonical synthetic-fixture
round-trip, and the CLI subcommand exit codes.
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
    return plugin_root / "tests" / "fixtures" / "vao" / "standing-red-cross-layer-bug.json"


@pytest.fixture(scope="module")
def fixture_data(fixture_path: Path) -> dict:
    return json.loads(fixture_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Tool existence + verdict shape
# ─────────────────────────────────────────────────────────────────────────────

def test_tool_function_exists(vao_tools):
    assert callable(getattr(vao_tools, "verify_no_standing_red", None))


def test_verdict_shape(vao_tools):
    v = vao_tools.verify_no_standing_red({})
    for key in ("tool", "valid", "gaps", "verdict_at"):
        assert key in v
    assert v["tool"] == "verify-no-standing-red"


def test_empty_artifact_trivially_passes(vao_tools):
    v = vao_tools.verify_no_standing_red({})
    assert v["valid"] is True
    assert v["gaps"] == []


def test_none_artifact_trivially_passes(vao_tools):
    v = vao_tools.verify_no_standing_red(None)
    assert v["valid"] is True


# ─────────────────────────────────────────────────────────────────────────────
# _STANDING_RED_MARKERS constant
# ─────────────────────────────────────────────────────────────────────────────

def test_markers_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_STANDING_RED_MARKERS")


def test_markers_has_at_least_10(vao_tools):
    assert len(vao_tools._STANDING_RED_MARKERS) >= 10


def test_markers_covers_canonical_phrases(vao_tools):
    blob = " ".join(p for _, p in vao_tools._STANDING_RED_MARKERS).lower()
    assert "standing red" in blob
    assert "will go green" in blob
    assert "fixme" in blob
    assert "test.fail" in blob


def test_cross_layer_sr_origin_kinds_exist(vao_tools):
    assert hasattr(vao_tools, "_CROSS_LAYER_SR_ORIGIN_KINDS")
    kinds = vao_tools._CROSS_LAYER_SR_ORIGIN_KINDS
    assert "cross-layer-backend-required" in kinds
    assert "cross-layer-frontend-required" in kinds


# ─────────────────────────────────────────────────────────────────────────────
# 2 severities × positive/negative
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("marker", [
    "// standing red",
    "// will go green when fixed",
    "// known broken",
    "test.fixme(",
    "it.fixme(",
    "test.fail(",
    "@pytest.mark.xfail",
])
def test_standing_red_marker_fires(vao_tools, marker):
    artifact = {
        "diff_files": [{
            "path": "tests/foo.spec.ts",
            "added_lines": [f"  {marker}"],
        }],
    }
    v = vao_tools.verify_no_standing_red(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "standing-red-committed" in severities


def test_marker_in_non_test_path_does_not_fire(vao_tools):
    """A standing-red marker in a non-test file is a separate code smell."""
    artifact = {
        "diff_files": [{
            "path": "src/component.ts",
            "added_lines": ["// will go green when fixed"],
        }],
    }
    v = vao_tools.verify_no_standing_red(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "standing-red-committed" not in severities


def test_confirmed_stub_exempts_test(vao_tools):
    artifact = {
        "diff_files": [{
            "path": "tests/foo.spec.ts",
            "added_lines": ["// will go green when fixed"],
        }],
        "confirmed_stubs": [
            {"path": "tests/foo.spec.ts", "reason": "awaiting Neo4j migration",
             "user_confirmed_at": "2026-06-01T12:00:00Z"},
        ],
    }
    v = vao_tools.verify_no_standing_red(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "standing-red-committed" not in severities


def test_confirmed_stub_as_string_path_exempts(vao_tools):
    """A confirmed-stub entry can also be a bare path string."""
    artifact = {
        "diff_files": [{
            "path": "tests/foo.spec.ts",
            "added_lines": ["// standing red"],
        }],
        "confirmed_stubs": ["tests/foo.spec.ts"],
    }
    v = vao_tools.verify_no_standing_red(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "standing-red-committed" not in severities


def test_clean_test_does_not_fire(vao_tools):
    artifact = {
        "diff_files": [{
            "path": "tests/foo.spec.ts",
            "added_lines": [
                "test('thing works', async () => {",
                "  expect(1 + 1).toBe(2);",
                "});",
            ],
        }],
    }
    v = vao_tools.verify_no_standing_red(artifact)
    assert v["valid"] is True


# cross-layer-fix-not-routed positive + negative

def test_cross_layer_with_standing_red_and_no_sr_fires(vao_tools):
    artifact = {
        "diff_files": [{
            "path": "tests/cross-layer.spec.ts",
            "added_lines": ["// will go green when fixed"],
        }],
        "cross_layer_diagnosis": {"unfixed_layer": "backend"},
    }
    v = vao_tools.verify_no_standing_red(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "cross-layer-fix-not-routed" in severities


def test_cross_layer_with_sr_does_not_fire(vao_tools):
    artifact = {
        "diff_files": [{
            "path": "tests/cross-layer.spec.ts",
            "added_lines": ["// will go green when fixed"],
        }],
        "cross_layer_diagnosis": {"unfixed_layer": "backend"},
        "solution_requirements_created": [
            {"id": "SR-1", "origin": {"kind": "cross-layer-backend-required"}},
        ],
    }
    v = vao_tools.verify_no_standing_red(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "cross-layer-fix-not-routed" not in severities


def test_cross_layer_without_standing_red_does_not_fire(vao_tools):
    """Cross-layer-fix-not-routed only fires WHEN a standing-red test is present."""
    artifact = {
        "diff_files": [],
        "cross_layer_diagnosis": {"unfixed_layer": "backend"},
        "solution_requirements_created": [],
    }
    v = vao_tools.verify_no_standing_red(artifact)
    severities = {g["severity"] for g in v["gaps"]}
    assert "cross-layer-fix-not-routed" not in severities


def test_cross_layer_severity_carries_unfixed_layer(vao_tools):
    artifact = {
        "diff_files": [{
            "path": "tests/x.spec.ts",
            "added_lines": ["// standing red"],
        }],
        "cross_layer_diagnosis": {"unfixed_layer": "backend"},
    }
    v = vao_tools.verify_no_standing_red(artifact)
    cross = [g for g in v["gaps"] if g["severity"] == "cross-layer-fix-not-routed"]
    assert cross
    assert cross[0]["unfixed_layer"] == "backend"


# ─────────────────────────────────────────────────────────────────────────────
# Determinism contract
# ─────────────────────────────────────────────────────────────────────────────

def test_deterministic_output_modulo_timestamp(vao_tools, fixture_data):
    a = fixture_data["verification_artifact"]
    v1 = vao_tools.verify_no_standing_red(a)
    v2 = vao_tools.verify_no_standing_red(a)
    v1.pop("verdict_at", None)
    v2.pop("verdict_at", None)
    assert json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)


def test_written_file_is_indent_2_sorted(vao_tools, fixture_data, tmp_path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_no_standing_red(fixture_data["verification_artifact"], out_path=out)
    raw = out.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    expected = json.dumps(parsed, sort_keys=True, indent=2)
    assert raw.strip() == expected.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Canonical fixture round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_fixture_bad_fires_both_severities(vao_tools, fixture_data):
    v = vao_tools.verify_no_standing_red(fixture_data["verification_artifact"])
    assert v["valid"] is False
    severities = {g["severity"] for g in v["gaps"]}
    assert "standing-red-committed" in severities
    assert "cross-layer-fix-not-routed" in severities


def test_fixture_corrected_passes(vao_tools, fixture_data):
    v = vao_tools.verify_no_standing_red(fixture_data["_corrected_verification_artifact"])
    assert v["valid"] is True
    assert v["gaps"] == []


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _run_cli(plugin_root: Path, artifact_path: Path, out_path: Path) -> int:
    cmd = [
        sys.executable,
        str(plugin_root / "hooks" / "vao_tools.py"),
        "verify-no-standing-red",
        "--artifact", str(artifact_path),
        "--out", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode


def test_cli_exits_0_on_clean(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["_corrected_verification_artifact"]), encoding="utf-8")
    rc = _run_cli(plugin_root, art, out)
    assert rc == 0


def test_cli_exits_nonzero_on_bad(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["verification_artifact"]), encoding="utf-8")
    rc = _run_cli(plugin_root, art, out)
    assert rc != 0
