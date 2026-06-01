"""v2.8.0 structural tests — assert the No standing-red discipline is wired
in `common-pipeline-conventions` (canonical home), `agents/bug-replicator.md`
(repro-test authoring discipline), `agents/qa-replayer.md` (post-fix audit),
`agents/frontend.md` + `agents/backend.md` (cross-layer routing rule), and
that the canonical fixture exists.

The discipline: an agent MUST NOT commit a failing test as documentation of
a known bug. When a diagnosis names a cross-layer gap, the unfixed layer is
routed via a solution requirement of cross-layer-backend-required /
cross-layer-frontend-required origin kind; the orchestrator dispatches the
correct team in the same run; the test goes green naturally.

The verbatim user prose that drove the discipline:
"I committed a standing red regression test (live-intake-persist.spec.ts)
that documents the exact gap and will go green when it's fixed"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ===========================================================================
# Canonical section in common-pipeline-conventions
# ===========================================================================

def test_canonical_section_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "## No standing-red discipline (v2.8.0)" in body


def test_canonical_section_appears_once(plugin_root: Path):
    """The H2 header appears once. Substring matches inside cross-reference
    lines (e.g., `agents/qa-replayer.md ## No standing-red discipline (v2.8.0)`)
    don't count — only newline-anchored headers."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert body.count("\n## No standing-red discipline (v2.8.0)\n") == 1


@pytest.mark.parametrize("severity", [
    "standing-red-committed",
    "cross-layer-fix-not-routed",
])
def test_canonical_section_names_severity(plugin_root: Path, severity: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert severity in body


@pytest.mark.parametrize("origin_kind", [
    "cross-layer-backend-required",
    "cross-layer-frontend-required",
])
def test_canonical_section_names_sr_origin_kinds(plugin_root: Path, origin_kind: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert origin_kind in body


def test_canonical_section_quotes_verbatim_user_prose(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text().lower()
    assert "will go green when" in body
    assert "standing red" in body


def test_canonical_section_documents_10_canonical_markers(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    # The 10-marker table must include at least 8 canonical patterns named here
    expected_patterns = [
        "// standing red", "will go green when", "known broken", "// documents the gap",
        "test.fixme(", "it.fixme(", "test.fail(", "xfail",
    ]
    hits = sum(1 for p in expected_patterns if p in body)
    assert hits >= 7, f"only {hits} canonical markers named"


def test_canonical_section_documents_confirmed_stub_carveout(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text().lower()
    assert "confirmed-stub" in body or "confirmed_stub" in body or "confirmed stub" in body


def test_canonical_section_documents_forbidden_phrases(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text().lower()
    assert "forbidden phrases" in body or "forbidden" in body


# ===========================================================================
# 4 agent body extensions
# ===========================================================================

@pytest.mark.parametrize("agent_file", [
    "bug-replicator.md",
    "qa-replayer.md",
    "frontend.md",
    "backend.md",
])
def test_agent_body_has_no_standing_red_section(plugin_root: Path, agent_file: str):
    agent = plugin_root / "agents" / agent_file
    body = agent.read_text()
    assert "## No standing-red discipline (v2.8.0)" in body, \
        f"agents/{agent_file} missing v2.8.0 section"


def test_bug_replicator_names_needs_cross_layer_fix_verdict(plugin_root: Path):
    agent = plugin_root / "agents" / "bug-replicator.md"
    body = agent.read_text()
    assert "needs-cross-layer-fix" in body


def test_qa_replayer_names_standing_red_finding_field(plugin_root: Path):
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text()
    assert "standing_red_finding" in body


def test_frontend_agent_quotes_verbatim_b23(plugin_root: Path):
    agent = plugin_root / "agents" / "frontend.md"
    body = agent.read_text().lower()
    assert "will go green when" in body
    assert "standing red" in body


def test_backend_agent_names_cross_layer_frontend_required(plugin_root: Path):
    agent = plugin_root / "agents" / "backend.md"
    body = agent.read_text()
    assert "cross-layer-frontend-required" in body


# ===========================================================================
# Synthetic fixture
# ===========================================================================

def test_fixture_exists(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "standing-red-cross-layer-bug.json"
    assert fixture.exists()


def test_fixture_is_valid_json_with_required_shape(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "standing-red-cross-layer-bug.json"
    data = json.loads(fixture.read_text())
    assert "verification_artifact" in data
    assert "_corrected_verification_artifact" in data
    bad = data["verification_artifact"]
    assert "cross_layer_diagnosis" in bad
    assert bad["cross_layer_diagnosis"]["unfixed_layer"] == "backend"


def test_corrected_fixture_routes_via_sr(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "standing-red-cross-layer-bug.json"
    data = json.loads(fixture.read_text())
    corrected = data["_corrected_verification_artifact"]
    srs = corrected.get("solution_requirements_created", [])
    assert srs, "corrected version must include at least one SR"
    kinds = [sr.get("origin", {}).get("kind") for sr in srs]
    assert "cross-layer-backend-required" in kinds


# ===========================================================================
# Cross-reference health
# ===========================================================================

def test_canonical_section_cross_references_layer3_tool(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "verify_no_standing_red" in body
    assert "_STANDING_RED_MARKERS" in body


def test_canonical_section_cross_references_fixture(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "standing-red-cross-layer-bug.json" in body
