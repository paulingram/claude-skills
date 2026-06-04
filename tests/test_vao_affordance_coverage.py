"""Layer 3 v2.13.0 tool — verify_affordance_coverage.

These tests pin the 13th deterministic verification tool's contract: positive
+ negative for the single severity (affordance-not-addressed), the
_AFFORDANCE_SIGNATURES extensibility, the _FILE_UPLOAD_AFFORDANCE_SIGNATURES
coverage, determinism, the canonical fixture round-trip, and the CLI exit
codes.
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
    return plugin_root / "tests" / "fixtures" / "vao" / "file-upload-affordance-missed.json"


@pytest.fixture(scope="module")
def fixture_data(fixture_path: Path) -> dict:
    return json.loads(fixture_path.read_text())


# Tool existence + verdict shape

def test_tool_function_exists(vao_tools):
    assert callable(getattr(vao_tools, "verify_affordance_coverage", None))


def test_verdict_shape(vao_tools):
    v = vao_tools.verify_affordance_coverage({}, {})
    for key in ("tool", "valid", "gaps", "verdict_at"):
        assert key in v
    assert v["tool"] == "verify-affordance-coverage"


def test_empty_inputs_trivially_pass(vao_tools):
    v = vao_tools.verify_affordance_coverage({}, {})
    assert v["valid"] is True
    assert v["gaps"] == []


def test_none_inputs_trivially_pass(vao_tools):
    v = vao_tools.verify_affordance_coverage(None, None)
    assert v["valid"] is True


# _AFFORDANCE_SIGNATURES extensibility

def test_affordance_signatures_dict_exists(vao_tools):
    assert hasattr(vao_tools, "_AFFORDANCE_SIGNATURES")
    assert isinstance(vao_tools._AFFORDANCE_SIGNATURES, dict)


def test_file_upload_is_first_canonical_class(vao_tools):
    assert "file-upload" in vao_tools._AFFORDANCE_SIGNATURES


def test_file_upload_signatures_constant_exists(vao_tools):
    assert hasattr(vao_tools, "_FILE_UPLOAD_AFFORDANCE_SIGNATURES")


def test_file_upload_signatures_count(vao_tools):
    assert len(vao_tools._FILE_UPLOAD_AFFORDANCE_SIGNATURES) >= 25


# 8 representative signature classes — each fires affordance-not-addressed

@pytest.mark.parametrize("file_content", [
    '<input type="file" />',
    'enctype="multipart/form-data"',
    "import multer from 'multer';",
    "import { useDropzone } from 'react-dropzone';",
    "PutObject params...",
    "createPresignedPost",
    ">Upload<",
    "FileReader API",
])
def test_signature_fires(vao_tools, file_content):
    artifact = {
        "codebase_scan": {
            "files_scanned": [{"path": "src/foo.ts", "content_excerpt": file_content}],
        },
    }
    v = vao_tools.verify_affordance_coverage(artifact, {})
    sev = {g["severity"] for g in v["gaps"]}
    assert "affordance-not-addressed" in sev, (
        f"file content {file_content!r} did not fire affordance-not-addressed"
    )


def test_addressed_affordance_does_not_fire(vao_tools):
    artifact = {
        "codebase_scan": {
            "files_scanned": [{"path": "src/foo.ts", "content_excerpt": "import multer"}],
        },
    }
    inventory = {"addressed_affordances": ["file-upload"]}
    v = vao_tools.verify_affordance_coverage(artifact, inventory)
    assert v["valid"] is True


def test_confirmed_stub_does_not_fire(vao_tools):
    artifact = {
        "codebase_scan": {
            "files_scanned": [{"path": "src/foo.ts", "content_excerpt": "<input type=\"file\""}],
        },
    }
    inventory = {
        "confirmed_stubs": [
            {"affordance_kind": "file-upload", "user_confirmed_at": "2026-06-04T10:00Z"},
        ],
    }
    v = vao_tools.verify_affordance_coverage(artifact, inventory)
    assert v["valid"] is True


def test_clean_codebase_does_not_fire(vao_tools):
    artifact = {
        "codebase_scan": {
            "files_scanned": [{"path": "src/foo.ts", "content_excerpt": "const x = 1;"}],
        },
    }
    v = vao_tools.verify_affordance_coverage(artifact, {})
    assert v["valid"] is True


def test_gap_carries_signature_ids_and_matched_files(vao_tools):
    artifact = {
        "codebase_scan": {
            "files_scanned": [
                {"path": "src/A.tsx", "content_excerpt": "<input type=\"file\" />"},
                {"path": "server/upload.ts", "content_excerpt": "import multer"},
            ],
        },
    }
    v = vao_tools.verify_affordance_coverage(artifact, {})
    g = v["gaps"][0]
    assert g["affordance_kind"] == "file-upload"
    assert isinstance(g["signature_ids"], list)
    assert len(g["signature_ids"]) >= 2
    assert "src/A.tsx" in g["matched_files"]
    assert "server/upload.ts" in g["matched_files"]


# Case-insensitive matching

def test_signature_match_is_case_insensitive(vao_tools):
    artifact = {
        "codebase_scan": {
            "files_scanned": [{"path": "src/foo.ts", "content_excerpt": "IMPORT MULTER FROM 'MULTER';"}],
        },
    }
    v = vao_tools.verify_affordance_coverage(artifact, {})
    sev = {g["severity"] for g in v["gaps"]}
    assert "affordance-not-addressed" in sev


# Determinism

def test_deterministic_output_modulo_timestamp(vao_tools, fixture_data):
    a = fixture_data["verification_artifact"]
    inv = fixture_data["requirements_inventory"]
    v1 = vao_tools.verify_affordance_coverage(a, inv)
    v2 = vao_tools.verify_affordance_coverage(a, inv)
    v1.pop("verdict_at", None)
    v2.pop("verdict_at", None)
    assert json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)


def test_written_file_is_sorted_keys_indent_2(vao_tools, fixture_data, tmp_path):
    out = tmp_path / "verdict.json"
    vao_tools.verify_affordance_coverage(
        fixture_data["verification_artifact"],
        fixture_data["requirements_inventory"],
        out_path=out,
    )
    raw = out.read_text()
    parsed = json.loads(raw)
    expected = json.dumps(parsed, sort_keys=True, indent=2)
    assert raw.strip() == expected.strip()


# Canonical fixture round-trip

def test_fixture_bad_fires_affordance_not_addressed(vao_tools, fixture_data):
    v = vao_tools.verify_affordance_coverage(
        fixture_data["verification_artifact"],
        fixture_data["requirements_inventory"],
    )
    assert v["valid"] is False
    sev = {g["severity"] for g in v["gaps"]}
    assert "affordance-not-addressed" in sev


def test_fixture_corrected_passes(vao_tools, fixture_data):
    v = vao_tools.verify_affordance_coverage(
        fixture_data["_corrected_verification_artifact"],
        fixture_data["_corrected_requirements_inventory"],
    )
    assert v["valid"] is True


# CLI

def _run_cli(plugin_root: Path, artifact: Path, inventory: Path, out: Path) -> int:
    cmd = [
        sys.executable,
        str(plugin_root / "hooks" / "vao_tools.py"),
        "verify-affordance-coverage",
        "--artifact", str(artifact),
        "--inventory", str(inventory),
        "--out", str(out),
    ]
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def test_cli_exits_0_on_clean(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "art.json"
    inv = tmp_path / "inv.json"
    out = tmp_path / "out.json"
    art.write_text(json.dumps(fixture_data["_corrected_verification_artifact"]))
    inv.write_text(json.dumps(fixture_data["_corrected_requirements_inventory"]))
    assert _run_cli(plugin_root, art, inv, out) == 0


def test_cli_exits_nonzero_on_bad(plugin_root, fixture_data, tmp_path):
    art = tmp_path / "art.json"
    inv = tmp_path / "inv.json"
    out = tmp_path / "out.json"
    art.write_text(json.dumps(fixture_data["verification_artifact"]))
    inv.write_text(json.dumps(fixture_data["requirements_inventory"]))
    assert _run_cli(plugin_root, art, inv, out) != 0
