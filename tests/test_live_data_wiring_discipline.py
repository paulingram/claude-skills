"""v2.6.0 structural tests — assert the live-data wiring discipline is wired
in `common-pipeline-conventions` (canonical home), the `interaction-completeness`
skill body (3-reviewer mandate extension), and the `interaction-reviewer` agent
body (per-reviewer audit protocol).

The discipline: when the requirement carries parity-implying wording
(*"wire to live data"* / *"remove mocks"* / *"stop using fixtures"* /
*"use real backend"*), the orchestrator annotates the slice with a
`wiring_mandate`, and the 3 `interaction-reviewer` agents extend their Round-1
mandate with a 2-pass audit (Playwright first, then code) that fires one of 5
named severities into a `live_data_wiring_findings` convergence-report block.

The verdict is consumed by the v2.6.0 `verify_live_data_wiring` Layer 3 tool,
whose findings gate the `live_verification_review` schema-v7 optional field.
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
    body = skill.read_text(encoding="utf-8")
    assert "## Live-data wiring discipline (v2.6.0)" in body


def test_canonical_section_appears_once(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.count("## Live-data wiring discipline (v2.6.0)") == 1


# ===========================================================================
# 5 severities named verbatim
# ===========================================================================


@pytest.mark.parametrize("severity", [
    "mock-state-residue",
    "live-response-not-rendered",
    "mock-fallback-uncovered",
    "network-not-intercepted",
    "async-status-not-surfaced",
])
def test_canonical_section_names_severity(plugin_root: Path, severity: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert severity in body, f"severity {severity!r} not named in canonical section"


# ===========================================================================
# 2-pass verification workflow is documented
# ===========================================================================


def test_canonical_section_documents_two_pass_workflow(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").lower()
    # Playwright pass + code-side audit must both be named
    assert "playwright" in body
    assert "code" in body  # code-side audit
    # Tamper test is part of the Playwright pass
    assert "tamper" in body


# ===========================================================================
# wiring_mandate annotation + canonical phrases
# ===========================================================================


def test_canonical_section_names_wiring_mandate_annotation(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "wiring_mandate" in body


def test_canonical_section_names_at_least_3_mandate_phrases(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").lower()
    phrases = [
        "wire to live data",
        "remove mock",
        "stop using fixture",
        "use real backend",
        "hook up the real api",
    ]
    hits = sum(1 for p in phrases if p in body)
    assert hits >= 3, f"only {hits} of {len(phrases)} mandate phrases named"


# ===========================================================================
# 3-reviewer Phase 5 swarm extension is referenced
# ===========================================================================


def test_canonical_section_references_3_reviewer_swarm(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").lower()
    assert "3-reviewer" in body or "3 reviewer" in body or "three reviewer" in body or "interaction-completeness" in body


# ===========================================================================
# Async-status surface rule + canonical state list
# ===========================================================================


def test_canonical_section_documents_async_status_rule(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").lower()
    states = ["loading", "processing", "done", "pending"]
    hits = sum(1 for s in states if s in body)
    assert hits >= 3, f"async-status canonical state list incomplete: {hits} states"


# ===========================================================================
# interaction-completeness extension sub-section
# ===========================================================================


def test_interaction_completeness_has_live_data_wiring_axis(plugin_root: Path):
    skill = plugin_root / "skills" / "interaction-completeness" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "## Live-data wiring axis (v2.6.0)" in body


def test_interaction_completeness_references_live_data_wiring_findings(plugin_root: Path):
    skill = plugin_root / "skills" / "interaction-completeness" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "live_data_wiring_findings" in body


# ===========================================================================
# interaction-reviewer agent extension
# ===========================================================================


def test_interaction_reviewer_has_live_data_wiring_audit_section(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-reviewer.md"
    body = agent.read_text(encoding="utf-8")
    assert "## Live-data wiring audit (v2.6.0)" in body


def test_interaction_reviewer_documents_2_pass_audit(plugin_root: Path):
    agent = plugin_root / "agents" / "interaction-reviewer.md"
    body = agent.read_text(encoding="utf-8").lower()
    assert "playwright" in body
    assert "code-side" in body or "code side" in body
    assert "tamper" in body


# ===========================================================================
# Coverage-map JSON consistency
# ===========================================================================


def test_coverage_map_change_name(plugin_root: Path):
    coverage = plugin_root / "openspec" / "changes" / "live-data-wiring-discipline" / "coverage-map.json"
    if not coverage.exists():
        pytest.skip("coverage map archived; structural assertions live in archive")
    data = json.loads(coverage.read_text(encoding="utf-8"))
    assert data["change"] == "live-data-wiring-discipline"
    assert data["version"] == "2.6.0"


def test_coverage_map_requirements_cover_all_pillars(plugin_root: Path):
    coverage = plugin_root / "openspec" / "changes" / "live-data-wiring-discipline" / "coverage-map.json"
    if not coverage.exists():
        pytest.skip("coverage map archived; structural assertions live in archive")
    data = json.loads(coverage.read_text(encoding="utf-8"))
    titles = " | ".join(r["title"] for r in data["requirements"])
    assert "common-pipeline-conventions" in titles
    assert "Layer 3 tool" in titles
    assert "_MOCK_STATE_SIGNATURES" in titles
    assert "interaction-completeness" in titles
    assert "interaction-reviewer" in titles
