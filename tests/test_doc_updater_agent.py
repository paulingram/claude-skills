"""Structural tests for the `doc-updater` agent (v0.9.23).

The agent is dispatched at Phase 8 of architect-team-pipeline and Phase B8 of
bug-fix-pipeline. It performs the documentation-currency update step that was
previously orchestrator-performed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "doc-updater"

REQUIRED_BODY_SECTIONS = (
    "## Inputs",
    "## Process",
    "## Output schema",
    "## Bounded Write scope",
    "## What this agent does NOT do",
    "## Hard rules",
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


def test_agent_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    for key in ("name", "description", "tools", "model", "color"):
        assert key in fm
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_opus(plugin_root: Path) -> None:
    """Doc-updater is judgment-heavy (identify stale sections across a 30-file diff)."""
    fm, _ = _read(plugin_root)
    assert fm["model"] == "opus", "doc-updater must use opus (judgment-heavy)"


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    """The agent uses whole-file rewrites via Write — Edit is deliberately excluded."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, (
        "doc-updater MUST NOT have Edit — whole-file rewrites via Write enforce consistency "
        "across related invariants (the failure mode Edit allows is partial updates)"
    )


def test_agent_tools_has_write(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" in tools, "doc-updater must have Write (it rewrites inventory docs)"


def test_agent_tools_has_bash(plugin_root: Path) -> None:
    """Bash is required to run `git diff` and `pytest --collect-only`."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Bash" in tools, "doc-updater must have Bash (git diff + pytest --collect-only)"


@pytest.mark.parametrize("tool", EXPECTED_TOOLS_IN_ALLOWLIST)
def test_agent_tool_present(plugin_root: Path, tool: str) -> None:
    fm, _ = _read(plugin_root)
    assert tool in _tools_list(fm), f"doc-updater tools must include `{tool}`"


@pytest.mark.parametrize("section", REQUIRED_BODY_SECTIONS)
def test_agent_body_section_present(plugin_root: Path, section: str) -> None:
    _, body = _read(plugin_root)
    assert section in body, f"doc-updater agent body missing section: {section}"


def test_bounded_write_scope_enumerated(plugin_root: Path) -> None:
    """The `## Bounded Write scope` section must enumerate the allowed inventory paths."""
    _, body = _read(plugin_root)
    start = body.find("## Bounded Write scope")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    # Each inventory doc must be enumerated.
    for doc in ("README.md", "CHANGELOG.md", "CLAUDE.md", "CODEBASE_MAP.md", "INTEGRATION_MAP.md"):
        assert doc in section, f"Bounded Write scope must enumerate `{doc}`"


def test_what_this_agent_does_not_do_forbids_critical_paths(plugin_root: Path) -> None:
    """The negative-space section must forbid writes to source code, tests, openspec, version JSON."""
    _, body = _read(plugin_root)
    start = body.find("## What this agent does NOT do")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]

    # Source code prohibited.
    assert "source code" in section.lower(), "section must forbid source-code writes"
    # Tests prohibited.
    assert "test" in section.lower(), "section must address test files"
    # openspec/* prohibited.
    assert "openspec" in section.lower(), "section must forbid openspec/* writes"
    # plugin.json / marketplace.json prohibited (version-source-of-truth).
    assert "plugin.json" in section or "marketplace.json" in section, (
        "section must forbid writes to .claude-plugin/plugin.json or marketplace.json"
    )


def test_process_five_steps_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Process")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    # Five steps with specific names.
    for step in ("Inventory walk", "Diff scan", "Staleness identification", "Update in place", "Report"):
        assert step in section, f"Process section must name step: {step}"


def test_stale_section_schema_fields(plugin_root: Path) -> None:
    """The agent body must document the stale_section entry schema."""
    _, body = _read(plugin_root)
    for field in ("doc_path", "section_anchor", "current_value", "expected_value", "justification"):
        assert field in body, f"agent body must document the stale_section field `{field}`"


def test_whole_file_rewrite_strategy_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "whole-file rewrite" in body.lower() or "whole-file rewrites" in body.lower(), (
        "agent body must document the whole-file-rewrite strategy"
    )
