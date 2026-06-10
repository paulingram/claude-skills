"""Structural tests for the `interaction-intuiter` agent (v0.9.21)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "interaction-intuiter"

REQUIRED_BODY_SECTIONS = (
    "## Inputs",
    "## Process",
    "## Output schema",
    "## Escalate-don't-guess",
    "## What this agent does NOT do",
)

EXPECTED_TOOLS_IN_ALLOWLIST = ("Read", "Glob", "Grep", "Bash", "Write", "TodoWrite")


def _agent_path(plugin_root: Path) -> Path:
    return plugin_root / "agents" / f"{AGENT_NAME}.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_agent_path(plugin_root))


def _tools_list(fm: dict) -> list[str]:
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return [t.strip() for t in raw if t]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def test_agent_file_exists(plugin_root: Path) -> None:
    assert _agent_path(plugin_root).exists()


def test_agent_frontmatter_has_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    for key in ("name", "description", "tools", "model", "color"):
        assert key in fm, f"interaction-intuiter agent: missing frontmatter key `{key}`"
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_opus(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert fm["model"] == "opus", "interaction-intuiter must use opus (judgment-heavy)"


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    """The intuiter is analysis-only — must NOT have Edit in its tools allowlist."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, (
        "interaction-intuiter MUST NOT have Edit in its tools allowlist — analysis-only on source code"
    )


def test_agent_tools_has_write(plugin_root: Path) -> None:
    """Write is required — the agent writes the per-codebase intuition map."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" in tools, "interaction-intuiter must have Write (it writes INTERACTION_INTUITION_MAP.md)"


@pytest.mark.parametrize("tool", EXPECTED_TOOLS_IN_ALLOWLIST)
def test_agent_tool_present(plugin_root: Path, tool: str) -> None:
    fm, _ = _read(plugin_root)
    assert tool in _tools_list(fm), f"interaction-intuiter tools must include `{tool}`"


@pytest.mark.parametrize("section", REQUIRED_BODY_SECTIONS)
def test_agent_body_section_present(plugin_root: Path, section: str) -> None:
    _, body = _read(plugin_root)
    assert section in body, f"interaction-intuiter agent body is missing section: {section}"


def test_agent_write_scope_documented(plugin_root: Path) -> None:
    """The agent body must explicitly state Write is only for the intuition map."""
    _, body = _read(plugin_root)
    start = body.find("## What this agent does NOT do")
    assert start >= 0
    next_section = body.find("\n## ", start + 1)
    section = body[start:next_section] if next_section > 0 else body[start:]
    assert "INTERACTION_INTUITION_MAP" in section or "intuition map" in section, (
        "the `## What this agent does NOT do` section must scope Write to the intuition map only"
    )
