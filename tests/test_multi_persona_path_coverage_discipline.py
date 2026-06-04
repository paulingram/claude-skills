"""v2.11.0 structural tests — assert the Multi-persona path-coverage discipline
is wired in `common-pipeline-conventions` (canonical home), `agents/qa-replayer.md`
(post-fix per-persona re-replay gate), `agents/frontend.md` (implementer
per-persona test mandate), `agents/interaction-reviewer.md` (3-reviewer swarm
extension), `agents/bug-replicator.md` (cross-persona repro mandate), and that
the canonical fixture exists.

The discipline: features serving > 1 user persona MUST have a
persona-inventory.json artifact and at least one Playwright test per persona
exercising their entry_point, plus assertions for every cross_persona_dependency,
every submit_interaction (double-click idempotency), and every
backend_call_interaction (loading-state UI within 200ms).
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
    assert "## Multi-persona path-coverage discipline (v2.11.0)" in body


def test_canonical_section_appears_once_as_h2(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert body.count("\n## Multi-persona path-coverage discipline (v2.11.0)\n") == 1


@pytest.mark.parametrize("severity", [
    "persona-path-not-tested",
    "cross-persona-sync-not-asserted",
    "double-submit-not-tested",
    "loading-state-not-asserted",
])
def test_canonical_section_names_severity(plugin_root: Path, severity: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert severity in body


def test_canonical_section_quotes_verbatim_user_prose(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "title side" in body or "title agency view" in body
    assert "two matters were created" in body or "looked frozen" in body
    assert "attorney view" in body
    assert "claim a fix and fail to test" in body


def test_canonical_section_documents_persona_inventory_schema(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    # Schema fields must be named
    for field in [
        "persona_id", "entry_point", "expected_views", "expected_data_visibility",
        "cross_persona_dependencies",
    ]:
        assert field in body, f"persona-inventory schema missing field {field!r}"


def test_canonical_section_names_loading_state_hints(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text().lower()
    # At least 4 of the canonical loading-state hint classes named
    hints = ["spinner", "skeleton", "progress", "submitting", "aria-busy"]
    hits = sum(1 for h in hints if h in body)
    assert hits >= 4, f"only {hits} loading-state hints named"


def test_canonical_section_names_double_submit_threshold(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    # 500ms double-submit threshold must be mentioned
    assert "500" in body
    # 200ms loading-state delay threshold must be mentioned
    assert "200" in body


# ===========================================================================
# 4 agent body extensions
# ===========================================================================

@pytest.mark.parametrize("agent_file", [
    "qa-replayer.md",
    "frontend.md",
    "interaction-reviewer.md",
    "bug-replicator.md",
])
def test_agent_body_has_v2_11_0_section(plugin_root: Path, agent_file: str):
    agent = plugin_root / "agents" / agent_file
    body = agent.read_text()
    assert "## Multi-persona path-coverage discipline (v2.11.0)" in body, (
        f"agents/{agent_file} missing v2.11.0 section"
    )


def test_qa_replayer_names_per_persona_findings_field(plugin_root: Path):
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text()
    assert "per_persona_findings" in body


def test_frontend_lists_six_mandatory_assertions(plugin_root: Path):
    agent = plugin_root / "agents" / "frontend.md"
    body = agent.read_text()
    # Must enumerate: entry_point + live backend + visibility + cross-persona
    # + double-submit + loading-state
    for needed in [
        "entry_point", "live backend", "expected_data_visibility",
        "cross_persona_dependencies", "double-submit", "loading-state",
    ]:
        assert needed in body, f"frontend.md missing mandatory assertion {needed!r}"


def test_interaction_reviewer_names_persona_path_coverage_axis(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-reviewer.md"
    body = agent.read_text()
    assert "persona_path_coverage" in body
    assert "tested-with-cross-persona-sync" in body
    assert "entry-point-untested" in body


def test_bug_replicator_names_needs_persona_inventory_verdict(plugin_root: Path):
    agent = plugin_root / "agents" / "bug-replicator.md"
    body = agent.read_text()
    assert "needs-persona-inventory" in body


# ===========================================================================
# Synthetic fixture
# ===========================================================================

def test_fixture_exists(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "multi-persona-path-coverage-gap.json"
    assert fixture.exists()


def test_fixture_is_valid_json_with_required_shape(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "multi-persona-path-coverage-gap.json"
    data = json.loads(fixture.read_text())
    assert "persona_inventory" in data
    assert "verification_artifact" in data
    assert "_corrected_verification_artifact" in data
    personas = data["persona_inventory"]["personas"]
    assert len(personas) >= 4, "heirship fixture must enumerate ≥ 4 personas"


def test_fixture_corrected_covers_all_personas(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "multi-persona-path-coverage-gap.json"
    data = json.loads(fixture.read_text())
    corrected = data["_corrected_verification_artifact"]
    persona_ids = {p["persona_id"] for p in data["persona_inventory"]["personas"]}
    tested = {r["persona_id"] for r in corrected["playwright_test_runs"]}
    assert persona_ids == tested, (
        f"corrected fixture must test EVERY persona; missing: {persona_ids - tested}"
    )


# ===========================================================================
# Cross-references
# ===========================================================================

def test_canonical_section_cross_references_layer3_tool(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "verify_per_persona_path_coverage" in body
    assert "_LOADING_STATE_UI_HINTS" in body


def test_canonical_section_cross_references_fixture(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "multi-persona-path-coverage-gap.json" in body
