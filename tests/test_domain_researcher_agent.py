"""Structural tests for the v3.4.0 domain-researcher agent."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT = REPO_ROOT / "agents" / "domain-researcher.md"


def test_agent_md_exists() -> None:
    assert AGENT.is_file()


def test_agent_carries_frontmatter() -> None:
    body = AGENT.read_text(encoding="utf-8")
    front, _, _ = body[3:].partition("---")
    assert "name: domain-researcher" in front
    assert "model: opus" in front
    assert "color: amber" in front


def test_agent_has_webfetch_and_websearch_tools() -> None:
    body = AGENT.read_text(encoding="utf-8")
    front, _, _ = body[3:].partition("---")
    assert "WebFetch" in front
    assert "WebSearch" in front


def test_agent_has_standard_tools() -> None:
    body = AGENT.read_text(encoding="utf-8")
    front, _, _ = body[3:].partition("---")
    for tool in ("Read", "Glob", "Grep", "LS", "Bash", "Write"):
        assert tool in front


def test_agent_documents_outside_research_mandate() -> None:
    body = AGENT.read_text(encoding="utf-8")
    assert "MANDATORY" in body or "mandatory" in body.lower()
    assert "outside research" in body.lower()


def test_agent_documents_4_required_queries() -> None:
    body = AGENT.read_text(encoding="utf-8")
    section = body.split("Phase R2-OUT", 1)[1].split("\n## ", 1)[0] if "Phase R2-OUT" in body else ""
    # 4 required queries: industry, market, competitor, authoritative source
    assert "industry" in section.lower()
    assert "market" in section.lower()
    assert "competitor" in section.lower()
    assert "WebFetch" in section


def test_agent_documents_2_phase_work_loop() -> None:
    body = AGENT.read_text(encoding="utf-8")
    assert "Phase R2-IN" in body
    assert "Phase R2-OUT" in body
    assert "Phase R2-WRITE" in body
    assert "Phase R3" in body
    assert "Phase R5" in body


def test_agent_documents_draft_json_schema() -> None:
    body = AGENT.read_text(encoding="utf-8")
    section = body.split("Phase R2-WRITE", 1)[1].split("\n## ", 1)[0]
    for field in ("researcher_id", "personas", "outside_research", "industry_inference", "open_questions"):
        assert field in section


def test_agent_documents_frontend_read_only_compliance() -> None:
    body = AGENT.read_text(encoding="utf-8")
    assert "frontend_read_only" in body


def test_agent_carries_standard_boilerplate() -> None:
    body = AGENT.read_text(encoding="utf-8")
    assert "## Operating context (v1.0.0)" in body
    assert "## Forbidden git operations" in body
    assert "## Checkpoint discipline" in body


def test_agent_documents_what_you_must_not_do() -> None:
    body = AGENT.read_text(encoding="utf-8")
    assert "What you must NOT do" in body
