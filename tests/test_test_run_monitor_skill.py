"""Structural tests for the v3.3.0 test-run-monitor skill body."""

from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface, surface_read

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "test-run-monitor" / "SKILL.md"


def test_skill_dir_exists() -> None:
    assert SKILL.parent.is_dir()


def test_skill_md_exists() -> None:
    assert SKILL.is_file()


def test_skill_carries_frontmatter() -> None:
    body = surface_read(SKILL)
    assert body.startswith("---")
    front, _, _ = body[3:].partition("---")
    assert "name: test-run-monitor" in front
    assert "description:" in front


def test_skill_names_3_phases() -> None:
    body = surface_read(SKILL)
    assert "Phase M1 — Source detection" in body
    assert "Phase M2 — Watch + capture" in body
    assert "Phase M3 — Synthesize" in body


def test_skill_names_3_adapters() -> None:
    body = surface_read(SKILL)
    for adapter in ("LocalAdapter", "CIAdapter", "ProductionQAAdapter"):
        assert adapter in body


def test_skill_documents_per_run_report_artifact() -> None:
    body = surface_read(SKILL)
    assert ".architect-team/monitor-runs/" in body
    assert "report.json" in body
    assert "report.md" in body


def test_skill_documents_finding_schema() -> None:
    body = surface_read(SKILL)
    assert "finding_id" in body
    assert "preliminary_category" in body
    assert "raw_evidence" in body


def test_skill_documents_4_failure_categories() -> None:
    body = surface_read(SKILL)
    for cat in ("flake", "regression", "environmental", "new"):
        assert cat in body


def test_skill_documents_strictly_passive_contract() -> None:
    body = surface_read(SKILL)
    assert "passive" in body.lower()
    assert "no SR" in body or "no Solution Requirement" in body or "no auto-SR" in body or "auto-Solution-Requirement" in body
    assert "no source-file modification" in body.lower() or "no source modification" in body.lower()


def test_skill_documents_2_agents_dispatched() -> None:
    body = surface_read(SKILL)
    assert "test-run-watcher" in body
    assert "monitor-synthesizer" in body


def test_skill_cross_references_canonical_home() -> None:
    body = surface_read(SKILL)
    assert "common-pipeline-conventions" in body
    assert "v3.3.0" in body


def test_skill_documents_no_default_budget() -> None:
    """v3.66.0 — inverted from the pre-v3.66.0 '30-minute default budget' pin.

    The watcher is UNBOUNDED by default and honors only a budget the USER
    passes (`<budget-seconds>`); a self-imposed default budget is the
    self-rationed investigation ETHOS principle 8 forbids."""
    body = surface_read(SKILL)
    low = body.lower()
    assert "budget" in low
    assert "no default budget" in low, "the skill must state there is NO default budget"
    assert "budget-seconds" in body, "the user's budget lever must be named"
    assert "30 minutes" not in body and "1800" not in body, (
        "no default budget value may be documented (v3.66.0 no-self-imposed-limits)"
    )
