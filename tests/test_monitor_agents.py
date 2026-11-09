"""Structural tests for the v3.3.0 test-run-watcher + monitor-synthesizer agents."""

from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface, surface_read

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WATCHER = REPO_ROOT / "agents" / "test-run-watcher.md"
SYNTH = REPO_ROOT / "agents" / "monitor-synthesizer.md"


# ---- test-run-watcher ----


def test_watcher_agent_exists() -> None:
    assert WATCHER.is_file()


def test_watcher_carries_frontmatter() -> None:
    body = surface_read(WATCHER)
    front, _, _ = body[3:].partition("---")
    assert "name: test-run-watcher" in front
    assert "model: sonnet" in front
    assert "color: cyan" in front  # v3.10.0 R4d: teal -> cyan (documented palette)


def test_watcher_lists_required_tools() -> None:
    body = surface_read(WATCHER)
    front, _, _ = body[3:].partition("---")
    # v3.10.0 R4a: LS retired (covered by Glob/Read/Bash).
    for tool in ("Read", "Glob", "Grep", "Bash", "Write"):
        assert tool in front


def test_watcher_documents_3_adapter_flows() -> None:
    body = surface_read(WATCHER)
    for adapter in ("LocalAdapter", "CIAdapter", "ProductionQAAdapter"):
        assert adapter in body


def test_watcher_documents_per_finding_json_contract() -> None:
    body = surface_read(WATCHER)
    assert "finding_id" in body
    assert "preliminary_category" in body
    assert "raw_evidence" in body


def test_watcher_documents_budget_enforcement() -> None:
    """v3.66.0 — a budget applies ONLY when the user passes <budget-seconds>;
    there is no default (inverted from the pre-v3.66.0 agent-chosen 1800s)."""
    body = surface_read(WATCHER)
    low = body.lower()
    assert "1800" not in body and "30 minutes" not in low, "no agent-chosen default budget"
    assert "no default budget" in low or "unbounded by default" in low
    assert "budget-seconds" in low
    assert "budget-exceeded.json" in body


def test_watcher_carries_forbidden_git_section() -> None:
    body = surface_read(WATCHER)
    assert "Forbidden git operations" in body
    assert "git stash" in body


def test_watcher_carries_checkpoint_discipline() -> None:
    body = surface_read(WATCHER)
    assert "Checkpoint discipline" in body


# ---- monitor-synthesizer ----


def test_synthesizer_agent_exists() -> None:
    assert SYNTH.is_file()


def test_synthesizer_carries_frontmatter() -> None:
    body = surface_read(SYNTH)
    front, _, _ = body[3:].partition("---")
    assert "name: monitor-synthesizer" in front
    assert "model: sonnet" in front
    assert "color: cyan" in front  # v3.10.0 R4d: teal -> cyan (documented palette)


def test_synthesizer_documents_4_categories() -> None:
    body = surface_read(SYNTH)
    for cat in ("flake", "regression", "environmental", "new"):
        assert cat in body


def test_synthesizer_documents_severity_rubric() -> None:
    body = surface_read(SYNTH)
    for sev in ("critical", "high", "medium", "low"):
        assert sev in body


def test_synthesizer_documents_trend_block() -> None:
    body = surface_read(SYNTH)
    assert "trend" in body.lower()
    assert "last 5 runs" in body or "last_5_runs" in body


def test_synthesizer_documents_output_files() -> None:
    body = surface_read(SYNTH)
    assert "report.json" in body
    assert "report.md" in body


def test_synthesizer_carries_strictly_passive_contract() -> None:
    body = surface_read(SYNTH)
    assert "No source-file modification" in body or "no source-file modification" in body.lower()
    assert "No SR filing" in body or "no SR" in body.lower() or "passive" in body.lower()
