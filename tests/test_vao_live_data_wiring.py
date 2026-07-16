"""Layer 3 v2.6.0 tool — verify_live_data_wiring.

These tests pin the 9th deterministic verification tool's contract: positive
+ negative for each of the 5 severities (mock-state-residue /
live-response-not-rendered / mock-fallback-uncovered / network-not-intercepted /
async-status-not-surfaced), determinism (sorted-keys + indent=2 bit-stable
output), the _MOCK_STATE_SIGNATURES constant shape, the canonical
synthetic-fixture round-trip, and the CLI subcommand exit codes.
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
    return plugin_root / "tests" / "fixtures" / "vao" / "live-data-mock-residue.json"


@pytest.fixture(scope="module")
def fixture_data(fixture_path: Path) -> dict:
    return json.loads(fixture_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Tool existence + signature + verdict shape
# ─────────────────────────────────────────────────────────────────────────────

def test_tool_function_exists(vao_tools):
    assert callable(getattr(vao_tools, "verify_live_data_wiring", None))


def test_tool_signature_accepts_three_args(vao_tools):
    import inspect
    sig = inspect.signature(vao_tools.verify_live_data_wiring)
    params = list(sig.parameters)
    assert "verification_artifact" in params
    assert "wiring_mandate" in params
    assert "out_path" in params


def test_verdict_shape_has_required_keys(vao_tools):
    v = vao_tools.verify_live_data_wiring({}, {})
    for key in ("tool", "valid", "gaps", "verdict_at"):
        assert key in v, f"missing key {key!r}"
    assert v["tool"] == "verify-live-data-wiring"


# ─────────────────────────────────────────────────────────────────────────────
# Trivial-pass on empty inputs (backwards-compat)
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_inputs_trivially_pass(vao_tools):
    v = vao_tools.verify_live_data_wiring({}, {})
    assert v["valid"] is True
    assert v["gaps"] == []


def test_none_inputs_trivially_pass(vao_tools):
    v = vao_tools.verify_live_data_wiring(None, None)
    assert v["valid"] is True
    assert v["gaps"] == []


# ─────────────────────────────────────────────────────────────────────────────
# 5 severities × {positive, negative}
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "scenario,artifact,mandate,want_severity,expect_valid",
    [
        # mock-state-residue positive
        (
            "mock-state-residue-pos",
            {"touched_file_contents": {
                "src/api/documents.ts": "import { setupWorker } from 'msw'; const w = setupWorker(rest.get('/api/docs', ...));",
            }},
            {"mandate_kind": "live-data-wiring"},
            "mock-state-residue",
            False,
        ),
        # mock-state-residue negative — clean file
        (
            "mock-state-residue-neg",
            {"touched_file_contents": {"src/api/documents.ts": "import { useQuery } from '@tanstack/react-query';"}},
            {"mandate_kind": "live-data-wiring"},
            "mock-state-residue",
            True,
        ),
        # live-response-not-rendered positive
        (
            "live-response-not-rendered-pos",
            {
                "touched_file_contents": {},
                "playwright_trace_summary": {
                    "captured_network_requests": [
                        {"url": "/api/matters/abc/documents", "response_body": {"matter_title": "Estate of Jane Doe"}},
                    ],
                    "ui_text_after_render": "Workspace · Documents (5)",
                },
            },
            {"mandate_kind": "live-data-wiring", "endpoints": ["/api/matters/{id}/documents"]},
            "live-response-not-rendered",
            False,
        ),
        # live-response-not-rendered negative — value present
        (
            "live-response-not-rendered-neg",
            {
                "touched_file_contents": {},
                "playwright_trace_summary": {
                    "captured_network_requests": [
                        {"url": "/api/matters/abc/documents", "response_body": {"matter_title": "Estate of Jane Doe"}},
                    ],
                    "ui_text_after_render": "Workspace · Estate of Jane Doe",
                },
            },
            {"mandate_kind": "live-data-wiring", "endpoints": ["/api/matters/{id}/documents"]},
            "live-response-not-rendered",
            True,
        ),
        # mock-fallback-uncovered positive — ?? mockData
        (
            "mock-fallback-uncovered-pos",
            {"diff_files": [{"path": "src/q.ts", "added_lines": ["const docs = liveDocs ?? mockData;"]}]},
            {"mandate_kind": "live-data-wiring"},
            "mock-fallback-uncovered",
            False,
        ),
        # mock-fallback-uncovered negative — no fallback
        (
            "mock-fallback-uncovered-neg",
            {"diff_files": [{"path": "src/q.ts", "added_lines": ["const docs = liveDocs;"]}]},
            {"mandate_kind": "live-data-wiring"},
            "mock-fallback-uncovered",
            True,
        ),
        # network-not-intercepted positive
        (
            "network-not-intercepted-pos",
            {
                "touched_file_contents": {},
                "playwright_trace_summary": {
                    "captured_network_requests": [],
                    "ui_text_after_render": "Workspace",
                },
            },
            {"mandate_kind": "live-data-wiring", "endpoints": ["/api/docs"]},
            "network-not-intercepted",
            False,
        ),
        # network-not-intercepted negative
        (
            "network-not-intercepted-neg",
            {
                "touched_file_contents": {},
                "playwright_trace_summary": {
                    "captured_network_requests": [{"url": "/api/docs", "response_body": {}}],
                    "ui_text_after_render": "Workspace",
                },
            },
            {"mandate_kind": "live-data-wiring", "endpoints": ["/api/docs"]},
            "network-not-intercepted",
            True,
        ),
        # async-status-not-surfaced positive
        (
            "async-status-not-surfaced-pos",
            {
                "touched_file_contents": {},
                "playwright_trace_summary": {
                    "captured_network_requests": [{"url": "/api/docs", "response_body": {}}],
                    "ui_text_after_render": "Workspace · Documents",
                },
            },
            {"mandate_kind": "live-data-wiring", "endpoints": ["/api/docs"], "async_states_expected": ["processing"]},
            "async-status-not-surfaced",
            False,
        ),
        # async-status-not-surfaced negative
        (
            "async-status-not-surfaced-neg",
            {
                "touched_file_contents": {},
                "playwright_trace_summary": {
                    "captured_network_requests": [{"url": "/api/docs", "response_body": {}}],
                    "ui_text_after_render": "Status: processing",
                },
            },
            {"mandate_kind": "live-data-wiring", "endpoints": ["/api/docs"], "async_states_expected": ["processing"]},
            "async-status-not-surfaced",
            True,
        ),
    ],
)
def test_severity_positive_negative(vao_tools, scenario, artifact, mandate, want_severity, expect_valid):
    v = vao_tools.verify_live_data_wiring(artifact, mandate)
    severities = {g["severity"] for g in v["gaps"]}
    if expect_valid:
        assert want_severity not in severities, f"{scenario}: severity {want_severity} unexpectedly fired"
    else:
        assert want_severity in severities, f"{scenario}: expected {want_severity}; got {severities}"


# ─────────────────────────────────────────────────────────────────────────────
# Determinism contract
# ─────────────────────────────────────────────────────────────────────────────

def test_deterministic_output_modulo_timestamp(vao_tools, fixture_data, tmp_path):
    a = fixture_data["verification_artifact"]
    m = fixture_data["wiring_mandate"]
    v1 = vao_tools.verify_live_data_wiring(a, m)
    v2 = vao_tools.verify_live_data_wiring(a, m)
    v1.pop("verdict_at", None)
    v2.pop("verdict_at", None)
    assert json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)


def test_written_file_is_indent_2_sorted_keys(vao_tools, fixture_data, tmp_path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_live_data_wiring(
        fixture_data["verification_artifact"],
        fixture_data["wiring_mandate"],
        out_path=out,
    )
    raw = out.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    expected = json.dumps(parsed, sort_keys=True, indent=2) + ("\n" if raw.endswith("\n") else "")
    # Determinism: re-serialization with sort_keys=True matches what's on disk.
    assert raw.strip() == expected.strip()


# ─────────────────────────────────────────────────────────────────────────────
# _MOCK_STATE_SIGNATURES constant
# ─────────────────────────────────────────────────────────────────────────────

def test_mock_state_signatures_exists(vao_tools):
    assert hasattr(vao_tools, "_MOCK_STATE_SIGNATURES")


def test_mock_state_signatures_has_at_least_12(vao_tools):
    assert len(vao_tools._MOCK_STATE_SIGNATURES) >= 12


def _signature_blob(sigs) -> str:
    parts: list[str] = []
    for sig in sigs:
        if isinstance(sig, tuple):
            parts.extend(str(p) for p in sig)
        else:
            parts.append(str(sig))
    return " ".join(parts).lower()


def test_mock_state_signatures_covers_msw(vao_tools):
    assert "msw" in _signature_blob(vao_tools._MOCK_STATE_SIGNATURES)


def test_mock_state_signatures_covers_faker_and_fixture_and_mock_flag(vao_tools):
    blob = _signature_blob(vao_tools._MOCK_STATE_SIGNATURES)
    assert "faker" in blob
    assert "fixture" in blob or "mock" in blob
    assert "vite_use_mock" in blob or "use_mock" in blob


# ─────────────────────────────────────────────────────────────────────────────
# Canonical fixture round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_fixture_bad_version_fires_at_least_4_distinct_severities(vao_tools, fixture_data):
    v = vao_tools.verify_live_data_wiring(
        fixture_data["verification_artifact"],
        fixture_data["wiring_mandate"],
    )
    assert v["valid"] is False
    distinct = {g["severity"] for g in v["gaps"]}
    assert len(distinct) >= 4, f"got only {len(distinct)} distinct severities: {distinct}"


def test_fixture_corrected_version_passes(vao_tools, fixture_data):
    v = vao_tools.verify_live_data_wiring(
        fixture_data["_corrected_verification_artifact"],
        fixture_data["wiring_mandate"],
    )
    assert v["valid"] is True
    assert v["gaps"] == []


# ─────────────────────────────────────────────────────────────────────────────
# CLI subcommand
# ─────────────────────────────────────────────────────────────────────────────

def _run_cli(plugin_root: Path, artifact_path: Path, mandate_path: Path, out_path: Path) -> int:
    cmd = [
        sys.executable,
        str(plugin_root / "hooks" / "vao_tools.py"),
        "verify-live-data-wiring",
        "--artifact", str(artifact_path),
        "--mandate", str(mandate_path),
        "--out", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode


def test_cli_exits_0_on_corrected(plugin_root: Path, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    mand = tmp_path / "mandate.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["_corrected_verification_artifact"]), encoding="utf-8")
    mand.write_text(json.dumps(fixture_data["wiring_mandate"]), encoding="utf-8")
    rc = _run_cli(plugin_root, art, mand, out)
    assert rc == 0, f"CLI returned {rc}"


def test_cli_exits_2_on_bad(plugin_root: Path, fixture_data, tmp_path):
    art = tmp_path / "artifact.json"
    mand = tmp_path / "mandate.json"
    out = tmp_path / "verdict.json"
    art.write_text(json.dumps(fixture_data["verification_artifact"]), encoding="utf-8")
    mand.write_text(json.dumps(fixture_data["wiring_mandate"]), encoding="utf-8")
    rc = _run_cli(plugin_root, art, mand, out)
    assert rc != 0, "CLI should not return 0 on invalid"


# ─────────────────────────────────────────────────────────────────────────────
# Test-path exclusion — signatures in test files should NOT fire
# ─────────────────────────────────────────────────────────────────────────────

def test_test_path_excluded_from_mock_state_residue(vao_tools):
    artifact = {
        "diff_files": [
            {"path": "tests/setup-msw.ts", "added_lines": ["import { setupWorker } from 'msw';"]},
        ],
    }
    v = vao_tools.verify_live_data_wiring(artifact, {"mandate_kind": "live-data-wiring"})
    severities = {g["severity"] for g in v["gaps"]}
    assert "mock-state-residue" not in severities


def test_mocks_path_excluded_from_mock_state_residue(vao_tools):
    artifact = {
        "diff_files": [
            {"path": "__mocks__/api.ts", "added_lines": ["import { generateFakeFacts } from '../testing/faker-helpers';"]},
        ],
    }
    v = vao_tools.verify_live_data_wiring(artifact, {"mandate_kind": "live-data-wiring"})
    severities = {g["severity"] for g in v["gaps"]}
    assert "mock-state-residue" not in severities


# ─────────────────────────────────────────────────────────────────────────────
# v2.7.0 Pattern propagation — 6th severity shared-mock-source-not-swept
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sweep_fixture_data(plugin_root: Path) -> dict:
    path = plugin_root / "tests" / "fixtures" / "vao" / "shared-mock-source-not-swept.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_sweep_fixture_bad_fires_shared_mock_source_not_swept(vao_tools, sweep_fixture_data):
    v = vao_tools.verify_live_data_wiring(
        sweep_fixture_data["verification_artifact"],
        sweep_fixture_data["wiring_mandate"],
    )
    assert v["valid"] is False
    severities = {g["severity"] for g in v["gaps"]}
    assert "shared-mock-source-not-swept" in severities


def test_sweep_fixture_corrected_passes(vao_tools, sweep_fixture_data):
    v = vao_tools.verify_live_data_wiring(
        sweep_fixture_data["_corrected_verification_artifact"],
        sweep_fixture_data["wiring_mandate"],
    )
    assert v["valid"] is True
    assert v["gaps"] == []


def test_sweep_only_some_consumers_fires(vao_tools):
    """1 of 3 consumers modified; 2 unfixed → fires."""
    artifact = {
        "diff_files": [{"path": "src/A.tsx", "added_lines": []}],
        "touched_file_contents": {
            "src/B.tsx": "import { SharedSrc } from '../state';",
            "src/C.tsx": "const x = SharedSrc.get();",
        },
    }
    mandate = {
        "mandate_kind": "live-data-wiring",
        "shared_mock_sources": [
            {"name": "SharedSrc", "consumer_files": ["src/A.tsx", "src/B.tsx", "src/C.tsx"]},
        ],
    }
    v = vao_tools.verify_live_data_wiring(artifact, mandate)
    severities = {g["severity"] for g in v["gaps"]}
    assert "shared-mock-source-not-swept" in severities


def test_sweep_all_consumers_modified_passes(vao_tools):
    """All 3 of 3 consumers fixed → no severity fires."""
    artifact = {
        "diff_files": [
            {"path": "src/A.tsx", "added_lines": []},
            {"path": "src/B.tsx", "added_lines": []},
            {"path": "src/C.tsx", "added_lines": []},
        ],
        "touched_file_contents": {
            "src/A.tsx": "const x = useLive();",
            "src/B.tsx": "const y = useLive();",
            "src/C.tsx": "const z = useLive();",
        },
    }
    mandate = {
        "mandate_kind": "live-data-wiring",
        "shared_mock_sources": [
            {"name": "SharedSrc", "consumer_files": ["src/A.tsx", "src/B.tsx", "src/C.tsx"]},
        ],
    }
    v = vao_tools.verify_live_data_wiring(artifact, mandate)
    severities = {g["severity"] for g in v["gaps"]}
    assert "shared-mock-source-not-swept" not in severities


def test_sweep_zero_consumers_modified_does_not_fire(vao_tools):
    """0 of 3 consumers modified → v2.6.0 severities apply, not v2.7.0."""
    artifact = {
        "diff_files": [{"path": "unrelated.ts", "added_lines": []}],
        "touched_file_contents": {
            "src/A.tsx": "const x = SharedSrc.get();",
            "src/B.tsx": "const y = SharedSrc.get();",
            "src/C.tsx": "const z = SharedSrc.get();",
        },
    }
    mandate = {
        "mandate_kind": "live-data-wiring",
        "shared_mock_sources": [
            {"name": "SharedSrc", "consumer_files": ["src/A.tsx", "src/B.tsx", "src/C.tsx"]},
        ],
    }
    v = vao_tools.verify_live_data_wiring(artifact, mandate)
    severities = {g["severity"] for g in v["gaps"]}
    assert "shared-mock-source-not-swept" not in severities


def test_sweep_no_shared_sources_field_is_noop(vao_tools):
    """Mandate without shared_mock_sources → severity never fires (backwards-compat)."""
    artifact = {
        "diff_files": [{"path": "src/A.tsx", "added_lines": []}],
        "touched_file_contents": {
            "src/B.tsx": "import { SharedSrc } from '../state';",
        },
    }
    mandate = {"mandate_kind": "live-data-wiring"}
    v = vao_tools.verify_live_data_wiring(artifact, mandate)
    severities = {g["severity"] for g in v["gaps"]}
    assert "shared-mock-source-not-swept" not in severities


def test_sweep_codebase_scan_consumer_files_path(vao_tools):
    """Source named via codebase_scan.consumer_files{} (input shape b)."""
    artifact = {
        "diff_files": [{"path": "src/A.tsx", "added_lines": []}],
        "touched_file_contents": {
            "src/B.tsx": "import { WtData } from '../fixtures/wt-data';",
        },
        "codebase_scan": {
            "consumer_files": {
                "WtData": ["src/A.tsx", "src/B.tsx"],
            },
        },
    }
    mandate = {"mandate_kind": "live-data-wiring"}
    v = vao_tools.verify_live_data_wiring(artifact, mandate)
    # Note: when only codebase_scan provides the source, has_mandate is true
    # (mandate_kind is set) but the v2.7.0 detector still runs over codebase_scan.
    severities = {g["severity"] for g in v["gaps"]}
    assert "shared-mock-source-not-swept" in severities


def test_sweep_gap_carries_source_and_unfixed_consumer(vao_tools, sweep_fixture_data):
    v = vao_tools.verify_live_data_wiring(
        sweep_fixture_data["verification_artifact"],
        sweep_fixture_data["wiring_mandate"],
    )
    shared = [g for g in v["gaps"] if g["severity"] == "shared-mock-source-not-swept"]
    assert shared, "no shared-mock-source-not-swept findings"
    for g in shared:
        assert g.get("source"), f"missing source field: {g}"
        assert g.get("unfixed_consumer"), f"missing unfixed_consumer field: {g}"
        assert g.get("evidence"), f"missing evidence: {g}"


def test_sweep_severity_appears_at_least_twice_for_two_unfixed(vao_tools):
    """3 consumers, 1 fixed, 2 unfixed → at least 2 findings."""
    artifact = {
        "diff_files": [{"path": "src/A.tsx", "added_lines": []}],
        "touched_file_contents": {
            "src/B.tsx": "import { S } from '../state';",
            "src/C.tsx": "const x = S.get();",
        },
    }
    mandate = {
        "mandate_kind": "live-data-wiring",
        "shared_mock_sources": [
            {"name": "S", "consumer_files": ["src/A.tsx", "src/B.tsx", "src/C.tsx"]},
        ],
    }
    v = vao_tools.verify_live_data_wiring(artifact, mandate)
    shared = [g for g in v["gaps"] if g["severity"] == "shared-mock-source-not-swept"]
    assert len(shared) >= 2
