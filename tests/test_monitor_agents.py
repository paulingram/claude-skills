"""Structural tests for the v3.3.0 test-run-watcher + monitor-synthesizer agents."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WATCHER = REPO_ROOT / "agents" / "test-run-watcher.md"
SYNTH = REPO_ROOT / "agents" / "monitor-synthesizer.md"


# ---- test-run-watcher ----


def test_watcher_agent_exists() -> None:
    assert WATCHER.is_file()


def test_watcher_carries_frontmatter() -> None:
    body = WATCHER.read_text(encoding="utf-8")
    front, _, _ = body[3:].partition("---")
    assert "name: test-run-watcher" in front
    assert "model: sonnet" in front
    assert "color: teal" in front


def test_watcher_lists_required_tools() -> None:
    body = WATCHER.read_text(encoding="utf-8")
    front, _, _ = body[3:].partition("---")
    for tool in ("Read", "Glob", "Grep", "LS", "Bash", "Write"):
        assert tool in front


def test_watcher_documents_3_adapter_flows() -> None:
    body = WATCHER.read_text(encoding="utf-8")
    for adapter in ("LocalAdapter", "CIAdapter", "ProductionQAAdapter"):
        assert adapter in body


def test_watcher_documents_per_finding_json_contract() -> None:
    body = WATCHER.read_text(encoding="utf-8")
    assert "finding_id" in body
    assert "preliminary_category" in body
    assert "raw_evidence" in body


def test_watcher_documents_budget_enforcement() -> None:
    body = WATCHER.read_text(encoding="utf-8")
    assert "1800" in body or "30 minutes" in body
    assert "budget-exceeded.json" in body


def test_watcher_carries_forbidden_git_section() -> None:
    body = WATCHER.read_text(encoding="utf-8")
    assert "Forbidden git operations" in body
    assert "git stash" in body


def test_watcher_carries_checkpoint_discipline() -> None:
    body = WATCHER.read_text(encoding="utf-8")
    assert "Checkpoint discipline" in body


# ---- monitor-synthesizer ----


def test_synthesizer_agent_exists() -> None:
    assert SYNTH.is_file()


def test_synthesizer_carries_frontmatter() -> None:
    body = SYNTH.read_text(encoding="utf-8")
    front, _, _ = body[3:].partition("---")
    assert "name: monitor-synthesizer" in front
    assert "model: opus" in front
    assert "color: teal" in front


def test_synthesizer_documents_4_categories() -> None:
    body = SYNTH.read_text(encoding="utf-8")
    for cat in ("flake", "regression", "environmental", "new"):
        assert cat in body


def test_synthesizer_documents_severity_rubric() -> None:
    body = SYNTH.read_text(encoding="utf-8")
    for sev in ("critical", "high", "medium", "low"):
        assert sev in body


def test_synthesizer_documents_trend_block() -> None:
    body = SYNTH.read_text(encoding="utf-8")
    assert "trend" in body.lower()
    assert "last 5 runs" in body or "last_5_runs" in body


def test_synthesizer_documents_output_files() -> None:
    body = SYNTH.read_text(encoding="utf-8")
    assert "report.json" in body
    assert "report.md" in body


def test_synthesizer_carries_strictly_passive_contract() -> None:
    body = SYNTH.read_text(encoding="utf-8")
    assert "No source-file modification" in body or "no source-file modification" in body.lower()
    assert "No SR filing" in body or "no SR" in body.lower() or "passive" in body.lower()
