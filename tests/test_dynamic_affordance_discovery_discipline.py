"""v2.13.0 structural tests — assert the Dynamic affordance discovery + UX-test
environment sequencing disciplines are wired in `common-pipeline-conventions`,
the relevant agent bodies, and that the canonical fixtures exist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ===========================================================================
# Canonical sections
# ===========================================================================

def test_dynamic_affordance_canonical_section_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "## Dynamic affordance discovery discipline (v2.13.0)" in body


def test_dynamic_affordance_canonical_section_appears_once(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.count("\n## Dynamic affordance discovery discipline (v2.13.0)\n") == 1


def test_env_sequencing_canonical_section_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "## UX-test environment sequencing discipline (v2.13.0)" in body


def test_env_sequencing_canonical_section_appears_once(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.count("\n## UX-test environment sequencing discipline (v2.13.0)\n") == 1


def test_dynamic_affordance_quotes_verbatim_user_prose(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "missed dynamic requirements to handle file uplaods" in body or "file uplaods" in body
    assert "file-upload" in body


def test_env_sequencing_quotes_verbatim_user_prose(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "local" in body.lower() and "live dev" in body.lower()
    assert "tests locally and never tests the full spectrum" in body


@pytest.mark.parametrize("severity", [
    "affordance-not-addressed",
    "live-dev-environment-not-tested",
])
def test_canonical_section_names_severity(plugin_root: Path, severity: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert severity in body


def test_dynamic_affordance_section_documents_file_upload_signatures(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    # At least 5 representative signature classes named in the table
    expected = ['<input type="file"', "multipart/form-data", "react-dropzone",
                "multer", "PutObject", "Upload"]
    hits = sum(1 for e in expected if e in body)
    assert hits >= 5, f"only {hits} file-upload signatures named in canonical section"


# ===========================================================================
# Agent body extensions
# ===========================================================================

@pytest.mark.parametrize("agent_file,section_header", [
    ("frontend.md", "## Dynamic affordance discovery discipline (v2.13.0)"),
    ("frontend.md", "## UX-test environment sequencing discipline (v2.13.0)"),
    ("qa-replayer.md", "## UX-test environment sequencing discipline (v2.13.0)"),
    ("system-architect.md", "## Dynamic affordance discovery discipline (v2.13.0)"),
    ("codebase-map-reviewer.md", "## Dynamic affordance discovery discipline (v2.13.0)"),
])
def test_agent_body_has_v2_13_0_section(plugin_root: Path, agent_file: str, section_header: str):
    agent = plugin_root / "agents" / agent_file
    body = agent.read_text(encoding="utf-8")
    assert section_header in body, f"agents/{agent_file} missing {section_header!r}"


def test_system_architect_documents_affordance_coverage_finding_field(plugin_root: Path):
    agent = plugin_root / "agents" / "system-architect.md"
    body = agent.read_text(encoding="utf-8")
    assert "affordance_coverage_finding" in body
    assert "unaddressed_kinds" in body


def test_qa_replayer_documents_environments_observed_field(plugin_root: Path):
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text(encoding="utf-8")
    assert "environments_observed" in body


# ===========================================================================
# Synthetic fixtures
# ===========================================================================

def test_affordance_fixture_exists(plugin_root: Path):
    f = plugin_root / "tests" / "fixtures" / "vao" / "file-upload-affordance-missed.json"
    assert f.exists()


def test_env_seq_fixture_exists(plugin_root: Path):
    f = plugin_root / "tests" / "fixtures" / "vao" / "local-only-no-live-dev-run.json"
    assert f.exists()


def test_affordance_fixture_carries_required_shape(plugin_root: Path):
    f = plugin_root / "tests" / "fixtures" / "vao" / "file-upload-affordance-missed.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    assert "requirements_inventory" in data
    assert "verification_artifact" in data
    assert "_corrected_verification_artifact" in data
    # The bad version's codebase_scan has actual file-upload signatures
    files = data["verification_artifact"]["codebase_scan"]["files_scanned"]
    blob = " ".join(f.get("content_excerpt", "") for f in files).lower()
    assert "multer" in blob or "input type=\"file\"" in blob
    # The bad version's inventory does NOT address file-upload
    assert "file-upload" not in data["requirements_inventory"].get("addressed_affordances", [])


# ===========================================================================
# Cross-references
# ===========================================================================

def test_canonical_section_cross_references_tool(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "verify_affordance_coverage" in body
    assert "_AFFORDANCE_SIGNATURES" in body
    assert "_LOCAL_ENV_HOST_PATTERNS" in body


def test_canonical_section_cross_references_fixtures(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "file-upload-affordance-missed.json" in body
    assert "local-only-no-live-dev-run.json" in body


def test_canonical_section_names_new_sr_origin_kind(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "affordance-coverage-gap" in body
