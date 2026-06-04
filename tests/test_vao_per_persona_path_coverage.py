"""Layer 3 v2.11.0 tool — verify_per_persona_path_coverage.

These tests pin the 12th deterministic verification tool's contract: positive
+ negative for each of the 4 severities (persona-path-not-tested /
cross-persona-sync-not-asserted / double-submit-not-tested /
loading-state-not-asserted), determinism, the canonical synthetic-fixture
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
    return plugin_root / "tests" / "fixtures" / "vao" / "multi-persona-path-coverage-gap.json"


@pytest.fixture(scope="module")
def fixture_data(fixture_path: Path) -> dict:
    return json.loads(fixture_path.read_text())


# ─────────────────────────────────────────────────────────────────────────────
# Tool existence + verdict shape
# ─────────────────────────────────────────────────────────────────────────────

def test_tool_function_exists(vao_tools):
    assert callable(getattr(vao_tools, "verify_per_persona_path_coverage", None))


def test_verdict_shape_has_required_keys(vao_tools):
    v = vao_tools.verify_per_persona_path_coverage({}, {})
    for key in ("tool", "valid", "gaps", "verdict_at"):
        assert key in v
    assert v["tool"] == "verify-per-persona-path-coverage"


def test_empty_inventory_trivially_passes(vao_tools):
    v = vao_tools.verify_per_persona_path_coverage({}, {})
    assert v["valid"] is True
    assert v["gaps"] == []


def test_none_inputs_trivially_pass(vao_tools):
    v = vao_tools.verify_per_persona_path_coverage(None, None)
    assert v["valid"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Loading-state UI hints constant
# ─────────────────────────────────────────────────────────────────────────────

def test_loading_state_ui_hints_exists(vao_tools):
    assert hasattr(vao_tools, "_LOADING_STATE_UI_HINTS")


def test_loading_state_ui_hints_covers_canonical_classes(vao_tools):
    blob = " ".join(vao_tools._LOADING_STATE_UI_HINTS).lower()
    assert "spinner" in blob
    assert "skeleton" in blob
    assert "progress" in blob or "progressbar" in blob
    assert "submitting" in blob or "saving" in blob
    assert "aria-busy" in blob


def test_double_submit_timing_threshold_constant(vao_tools):
    assert hasattr(vao_tools, "_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS")
    assert vao_tools._DOUBLE_SUBMIT_TIMING_THRESHOLD_MS == 500


def test_loading_state_max_delay_constant(vao_tools):
    assert hasattr(vao_tools, "_LOADING_STATE_MAX_DELAY_MS")
    assert vao_tools._LOADING_STATE_MAX_DELAY_MS == 200


# ─────────────────────────────────────────────────────────────────────────────
# persona-path-not-tested
# ─────────────────────────────────────────────────────────────────────────────

def test_persona_path_not_tested_fires_when_missing(vao_tools):
    inventory = {"personas": [
        {"persona_id": "client", "entry_point": "https://x/client"},
        {"persona_id": "attorney", "entry_point": "https://x/atty"},
    ]}
    artifact = {"playwright_test_runs": [
        {"persona_id": "client", "entry_url": "https://x/client", "assertions": ["x"]},
    ]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "persona-path-not-tested" in sev
    pids = {g["persona_id"] for g in v["gaps"] if g["severity"] == "persona-path-not-tested"}
    assert "attorney" in pids


def test_persona_path_not_tested_does_not_fire_when_all_tested(vao_tools):
    inventory = {"personas": [{"persona_id": "client", "entry_point": "https://x/client"}]}
    artifact = {"playwright_test_runs": [{"persona_id": "client"}]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "persona-path-not-tested" not in sev


# ─────────────────────────────────────────────────────────────────────────────
# cross-persona-sync-not-asserted
# ─────────────────────────────────────────────────────────────────────────────

def test_cross_persona_sync_not_asserted_fires(vao_tools):
    inventory = {"personas": [
        {
            "persona_id": "client",
            "entry_point": "https://x/c",
            "cross_persona_dependencies": [
                {"writes_data": "matter.client_email", "must_appear_in_persona": "attorney"},
            ],
        },
        {"persona_id": "attorney", "entry_point": "https://x/atty"},
    ]}
    artifact = {"playwright_test_runs": [
        {"persona_id": "client"},
        {"persona_id": "attorney"},
    ]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "cross-persona-sync-not-asserted" in sev


def test_cross_persona_sync_asserted_does_not_fire(vao_tools):
    inventory = {"personas": [
        {
            "persona_id": "client",
            "entry_point": "https://x/c",
            "cross_persona_dependencies": [
                {"writes_data": "matter.client_email", "must_appear_in_persona": "attorney"},
            ],
        },
        {"persona_id": "attorney", "entry_point": "https://x/atty"},
    ]}
    artifact = {"playwright_test_runs": [
        {
            "persona_id": "client",
            "cross_persona_assertions": [
                {"writes_data": "matter.client_email", "asserted_in_persona": "attorney"},
            ],
        },
        {"persona_id": "attorney"},
    ]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "cross-persona-sync-not-asserted" not in sev


# ─────────────────────────────────────────────────────────────────────────────
# double-submit-not-tested
# ─────────────────────────────────────────────────────────────────────────────

def test_double_submit_not_tested_fires_when_no_rapid_pair(vao_tools):
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "submit_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "clicks_with_timing": [{"selector": "button[data-testid=create]", "ts_ms": 1000}],
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "double-submit-not-tested" in sev


def test_double_submit_passes_with_rapid_pair_and_single_record(vao_tools):
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "submit_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "clicks_with_timing": [
            {"selector": "button[data-testid=create]", "ts_ms": 1000},
            {"selector": "button[data-testid=create]", "ts_ms": 1300},
        ],
        "record_count_after_double_click": 1,
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "double-submit-not-tested" not in sev


def test_double_submit_fires_when_record_count_wrong(vao_tools):
    """Two rapid clicks but record_count is 2 (the bug) — still fires."""
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "submit_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "clicks_with_timing": [
            {"selector": "button[data-testid=create]", "ts_ms": 1000},
            {"selector": "button[data-testid=create]", "ts_ms": 1300},
        ],
        "record_count_after_double_click": 2,
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "double-submit-not-tested" in sev


def test_double_submit_fires_when_clicks_too_far_apart(vao_tools):
    """Two clicks but > 500ms apart — not a double-submit test."""
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "submit_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "clicks_with_timing": [
            {"selector": "button[data-testid=create]", "ts_ms": 1000},
            {"selector": "button[data-testid=create]", "ts_ms": 2500},
        ],
        "record_count_after_double_click": 1,
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "double-submit-not-tested" in sev


# ─────────────────────────────────────────────────────────────────────────────
# loading-state-not-asserted
# ─────────────────────────────────────────────────────────────────────────────

def test_loading_state_not_asserted_fires(vao_tools):
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "backend_call_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "ui_states_observed": [],
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "loading-state-not-asserted" in sev


def test_loading_state_passes_with_spinner_observed(vao_tools):
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "backend_call_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "ui_states_observed": ["spinner appeared"],
        "loading_state_delays_ms": [80],
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "loading-state-not-asserted" not in sev


def test_loading_state_passes_with_submitting_text(vao_tools):
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "backend_call_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "ui_states_observed": ["Submitting..."],
        "loading_state_delays_ms": [100],
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "loading-state-not-asserted" not in sev


def test_loading_state_fires_when_delay_too_long(vao_tools):
    """Loading state observed but only after > 200ms — UI looked frozen."""
    inventory = {"personas": [{
        "persona_id": "client", "entry_point": "https://x/c",
        "backend_call_interaction": "button[data-testid=create]",
    }]}
    artifact = {"playwright_test_runs": [{
        "persona_id": "client",
        "ui_states_observed": ["spinner"],
        "loading_state_delays_ms": [500],
    }]}
    v = vao_tools.verify_per_persona_path_coverage(artifact, inventory)
    sev = {g["severity"] for g in v["gaps"]}
    assert "loading-state-not-asserted" in sev


# ─────────────────────────────────────────────────────────────────────────────
# Determinism contract
# ─────────────────────────────────────────────────────────────────────────────

def test_deterministic_output_modulo_timestamp(vao_tools, fixture_data):
    a = fixture_data["verification_artifact"]
    inv = fixture_data["persona_inventory"]
    v1 = vao_tools.verify_per_persona_path_coverage(a, inv)
    v2 = vao_tools.verify_per_persona_path_coverage(a, inv)
    v1.pop("verdict_at", None)
    v2.pop("verdict_at", None)
    assert json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)


def test_written_file_is_sorted_keys_indent_2(vao_tools, fixture_data, tmp_path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_per_persona_path_coverage(
        fixture_data["verification_artifact"],
        fixture_data["persona_inventory"],
        out_path=out,
    )
    raw = out.read_text()
    parsed = json.loads(raw)
    expected = json.dumps(parsed, sort_keys=True, indent=2)
    assert raw.strip() == expected.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Canonical fixture round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_fixture_bad_fires_all_four_severities(vao_tools, fixture_data):
    v = vao_tools.verify_per_persona_path_coverage(
        fixture_data["verification_artifact"],
        fixture_data["persona_inventory"],
    )
    assert v["valid"] is False
    sev = {g["severity"] for g in v["gaps"]}
    assert "persona-path-not-tested" in sev
    assert "cross-persona-sync-not-asserted" in sev
    assert "double-submit-not-tested" in sev
    assert "loading-state-not-asserted" in sev


def test_fixture_corrected_passes(vao_tools, fixture_data):
    v = vao_tools.verify_per_persona_path_coverage(
        fixture_data["_corrected_verification_artifact"],
        fixture_data["persona_inventory"],
    )
    assert v["valid"] is True
    assert v["gaps"] == []


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _run_cli(plugin_root: Path, artifact_path: Path, inventory_path: Path, out_path: Path) -> int:
    cmd = [
        sys.executable,
        str(plugin_root / "hooks" / "vao_tools.py"),
        "verify-per-persona-path-coverage",
        "--artifact", str(artifact_path),
        "--inventory", str(inventory_path),
        "--out", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode


def test_cli_exits_0_on_clean(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    inv = tmp_path / "inventory.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["_corrected_verification_artifact"]))
    inv.write_text(json.dumps(fixture_data["persona_inventory"]))
    rc = _run_cli(plugin_root, art, inv, out)
    assert rc == 0


def test_cli_exits_nonzero_on_bad(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    inv = tmp_path / "inventory.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["verification_artifact"]))
    inv.write_text(json.dumps(fixture_data["persona_inventory"]))
    rc = _run_cli(plugin_root, art, inv, out)
    assert rc != 0
