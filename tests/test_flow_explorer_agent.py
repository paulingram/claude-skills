"""Structural tests for the `flow-explorer` agent (v0.9.29)."""
from __future__ import annotations

from pathlib import Path

from tests.helpers import frontmatter


AGENT_NAME = "flow-explorer"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(plugin_root / "agents" / f"{AGENT_NAME}.md")


def _tools(fm: dict) -> list[str]:
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return [t.strip() for t in raw if t]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def test_agent_file_exists(plugin_root: Path) -> None:
    assert (plugin_root / "agents" / f"{AGENT_NAME}.md").exists()


def test_agent_registered(plugin_root: Path) -> None:
    from tests.test_agents import EXPECTED_AGENTS
    assert AGENT_NAME in EXPECTED_AGENTS


def test_agent_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    for key in ("name", "description", "tools", "model", "color"):
        assert key in fm
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_opus(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert fm["model"] == "opus"


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert "Edit" not in _tools(fm)


def test_agent_tools_has_write(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert "Write" in _tools(fm)


def test_agent_body_10_to_15_directive(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "10-15" in body, "agent must specify the 10-15-additional-flows directive"


def test_agent_body_forbids_rephrasing_literal(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "NEVER rephrase" in body or "do not rephrase" in body.lower() or "rephrase" in body.lower(), (
        "agent must explicitly forbid rephrasing the literal flow"
    )


def test_agent_body_documents_required_sections(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    for section in ("## Inputs", "## Process", "## Output schema", "## Bounded Write scope", "## What this agent does NOT do", "## Hard rules"):
        assert section in body, f"agent body missing section: {section}"


def test_agent_proposal_schema_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    for field in ("name", "goal_one_line", "steps", "rationale", "adjacency_to_literal"):
        assert field in body, f"agent body must document the proposal-entry field `{field}`"
