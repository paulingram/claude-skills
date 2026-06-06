"""v2.7.0 structural tests — assert the Pattern Propagation Mandate is wired
in `common-pipeline-conventions` (canonical sub-section under v2.6.0's Live-data
wiring discipline), the `agents/frontend.md` body (implementer-side discipline),
and the `agents/interaction-reviewer.md` body (reviewer-side sweep audit).

The discipline: when an agent fixes ONE mock-state instance under a
`wiring_mandate`, it MUST sweep the codebase for the SAME shared source and
fix ALL consumers — not announce one fix and offer the sweep as a follow-up.
The follow-up offer is itself the bug this section closes.

The 6th severity `shared-mock-source-not-swept` in `verify_live_data_wiring`
fires when the diff fixed some consumers of a named shared mock source but
left others unmodified while they still reference the source.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ===========================================================================
# Canonical sub-section in common-pipeline-conventions
# ===========================================================================


def test_canonical_subsection_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "### Pattern propagation mandate (v2.7.0)" in body


def test_canonical_subsection_appears_once(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.count("### Pattern propagation mandate (v2.7.0)") == 1


def test_canonical_subsection_names_6th_severity(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "shared-mock-source-not-swept" in body


def test_canonical_subsection_quotes_verbatim_user_prose(plugin_root: Path):
    """The canonical sub-section must include the verbatim user phrase that
    drove the discipline addition — *'say the word if you want me to sweep'*."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").lower()
    assert "say the word" in body
    assert "sweep" in body


@pytest.mark.parametrize("signature_class", [
    "fixture import",
    "hook",
    "seed function",
])
def test_canonical_subsection_names_3_signature_classes(plugin_root: Path, signature_class: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").lower()
    assert signature_class.lower() in body


def test_canonical_subsection_documents_3_step_sweep(plugin_root: Path):
    """The mandate must document trace → enumerate → fix as the per-instance protocol."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").lower()
    assert "trace the source" in body
    assert "enumerate" in body
    assert "fix every consumer" in body


# ===========================================================================
# Frontend agent body extension
# ===========================================================================


def test_frontend_agent_has_pattern_propagation_section(plugin_root: Path):
    agent = plugin_root / "agents" / "frontend.md"
    body = agent.read_text(encoding="utf-8")
    assert "## Pattern propagation mandate (v2.7.0)" in body


def test_frontend_agent_forbids_say_the_word_phrasing(plugin_root: Path):
    """The discipline must explicitly forbid the verbatim 'say the word' offer."""
    agent = plugin_root / "agents" / "frontend.md"
    body = agent.read_text(encoding="utf-8").lower()
    assert "say the word" in body
    assert "forbidden" in body or "do not" in body


def test_frontend_agent_documents_3_step_sweep(plugin_root: Path):
    agent = plugin_root / "agents" / "frontend.md"
    body = agent.read_text(encoding="utf-8").lower()
    assert "trace the source" in body
    assert "enumerate" in body


# ===========================================================================
# Interaction-reviewer extension
# ===========================================================================


def test_interaction_reviewer_has_pattern_propagation_sweep_section(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-reviewer.md"
    body = agent.read_text(encoding="utf-8")
    assert "### Pattern propagation sweep (v2.7.0)" in body


def test_interaction_reviewer_documents_5_step_audit(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-reviewer.md"
    body = agent.read_text(encoding="utf-8").lower()
    # the 5-step audit must walk identify → enumerate → compare → confirm → emit
    assert "identify the shared source" in body
    assert "enumerate consumers" in body
    assert "compare against the diff" in body
    assert "emit" in body


# ===========================================================================
# Synthetic fixture exists and round-trips
# ===========================================================================


def test_sweep_fixture_exists(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "shared-mock-source-not-swept.json"
    assert fixture.exists()


def test_sweep_fixture_is_valid_json_with_required_shape(plugin_root: Path):
    fixture = plugin_root / "tests" / "fixtures" / "vao" / "shared-mock-source-not-swept.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    assert "wiring_mandate" in data
    assert "verification_artifact" in data
    assert "_corrected_verification_artifact" in data
    assert "shared_mock_sources" in data["wiring_mandate"]
    assert len(data["wiring_mandate"]["shared_mock_sources"]) >= 1


# ===========================================================================
# Cross-reference back from v2.6.0 section to v2.7.0
# ===========================================================================


def test_v26_cross_references_v27_fixture(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "shared-mock-source-not-swept.json" in body


def test_v26_cross_references_v27_agent_section(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "agents/frontend.md" in body
    assert "Pattern propagation mandate (v2.7.0)" in body
