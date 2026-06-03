"""v2.10.0 structural tests — assert the No end-of-run deferral discipline is
wired in `common-pipeline-conventions` (canonical home), `agents/system-architect.md`
(Master Review Audit gate), `agents/qa-replayer.md` (post-fix verdict gate),
`agents/frontend.md` + `agents/backend.md` (implementer-side discipline), and
that the canonical fixture exists.

The discipline: agents MUST NOT end a run by cataloguing in-scope work as
"Deferred" and bouncing the unfixed items back to the user as a "Want me to
continue?" decision question. Every in-scope item has exactly one of three
valid dispositions: (a) fixed in this change, (b) routed via SR, (c)
confirmed-stub with explicit user citation.

Verbatim user prose driving this rule:
"⏳ Deferred — 7 bugs, 4 work-items (each a real change, not a one-liner) …
Want me to continue with the deferred 7? I'd take them cluster-by-cluster
(A → B → C → D) … Your call. … this is not allowed. fix it and ensure your
fix is strong"
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
    assert "## No end-of-run deferral discipline (v2.10.0)" in body


def test_canonical_section_appears_once_as_h2(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert body.count("\n## No end-of-run deferral discipline (v2.10.0)\n") == 1


@pytest.mark.parametrize("severity", [
    "deferred-work-catalog",
    "followup-decision-question",
    "wrap-up-with-known-bugs",
])
def test_canonical_section_names_severity(plugin_root: Path, severity: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert severity in body


def test_canonical_section_quotes_verbatim_user_prose(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "⏳ Deferred" in body or "Deferred — 7 bugs" in body
    assert "Want me to continue" in body
    assert "Your call" in body


@pytest.mark.parametrize("marker", [
    "⏳ Deferred",
    "cluster-by-cluster",
    "A → B → C → D",
    "Want me to continue",
    "Your call",
    "ideally in a fresh context",
])
def test_canonical_section_documents_canonical_markers(plugin_root: Path, marker: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert marker in body, f"canonical marker {marker!r} missing"


def test_canonical_section_documents_three_valid_dispositions(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text().lower()
    # Three valid disposition channels must be named
    assert "fixed in this change" in body
    assert "solution requirement" in body
    assert "confirmed-stub" in body or "confirmed_stub" in body


def test_canonical_section_distinguishes_from_neighbor_disciplines(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    # Comparison table must reference at least 3 prior disciplines
    refs = ["v0.9.36", "v1.4.0", "v2.8.0"]
    for ref in refs:
        assert ref in body, f"comparison table missing reference to {ref!r}"


# ===========================================================================
# 4 agent body extensions
# ===========================================================================

@pytest.mark.parametrize("agent_file", [
    "system-architect.md",
    "qa-replayer.md",
    "frontend.md",
    "backend.md",
])
def test_agent_body_has_v2_10_0_section(plugin_root: Path, agent_file: str):
    agent = plugin_root / "agents" / agent_file
    body = agent.read_text()
    assert "## No end-of-run deferral discipline (v2.10.0)" in body, (
        f"agents/{agent_file} missing v2.10.0 section"
    )


def test_system_architect_names_end_of_run_deferral_finding_field(plugin_root: Path):
    """The Master Review Audit verdict must add an end_of_run_deferral_finding block."""
    agent = plugin_root / "agents" / "system-architect.md"
    body = agent.read_text()
    assert "end_of_run_deferral_finding" in body


def test_qa_replayer_names_end_of_run_deferral_finding_field(plugin_root: Path):
    """The qa-replayer verdict must add an end_of_run_deferral_finding block."""
    agent = plugin_root / "agents" / "qa-replayer.md"
    body = agent.read_text()
    assert "end_of_run_deferral_finding" in body


@pytest.mark.parametrize("agent_file", [
    "frontend.md",
    "backend.md",
])
def test_implementer_agents_name_three_dispositions(plugin_root: Path, agent_file: str):
    """frontend.md + backend.md must enumerate the 3 valid item dispositions."""
    agent = plugin_root / "agents" / agent_file
    body = agent.read_text().lower()
    # Three dispositions: fixed in diff, SR routed, confirmed-stub
    assert "fixed in" in body
    assert "sr" in body or "solution requirement" in body
    assert "confirmed-stub" in body or "confirmed_stub" in body


# ===========================================================================
# Forbidden phrase coverage in agent bodies (frontend explicitly lists them)
# ===========================================================================

@pytest.mark.parametrize("forbidden_phrase", [
    "⏳ Deferred",
    "cluster-by-cluster",
    "Want me to continue",
    "Your call",
])
def test_frontend_agent_lists_forbidden_phrases(plugin_root: Path, forbidden_phrase: str):
    agent = plugin_root / "agents" / "frontend.md"
    body = agent.read_text()
    assert forbidden_phrase in body, (
        f"frontend.md does not list forbidden phrase {forbidden_phrase!r}"
    )


# ===========================================================================
# Synthetic fixture exists + round-trips
# ===========================================================================

def test_fixture_exists(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "in-scope-deferral-cluster-list.json"
    assert fixture.exists()


def test_fixture_is_valid_json_with_required_shape(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "in-scope-deferral-cluster-list.json"
    data = json.loads(fixture.read_text())
    assert "verification_artifact" in data
    assert "_corrected_verification_artifact" in data
    assert "final_report" in data["verification_artifact"]
    assert "⏳ Deferred" in data["verification_artifact"]["final_report"]


def test_corrected_fixture_has_dispositions_for_every_item(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "in-scope-deferral-cluster-list.json"
    data = json.loads(fixture.read_text())
    corrected = data["_corrected_verification_artifact"]
    # At least one of each disposition channel
    assert corrected.get("solution_requirements_created"), "corrected missing SRs"
    assert corrected.get("confirmed_stubs"), "corrected missing confirmed_stubs"
    assert corrected.get("implementing_commits"), "corrected missing implementing_commits"


# ===========================================================================
# Cross-reference health
# ===========================================================================

def test_canonical_section_cross_references_layer3_tool(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "verify_no_end_of_run_deferral" in body
    assert "_DEFERRAL_CATALOG_MARKERS" in body
    assert "_FOLLOWUP_QUESTION_MARKERS" in body


def test_canonical_section_cross_references_fixture(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text()
    assert "in-scope-deferral-cluster-list.json" in body
