"""Structural tests for the `bug-replicator` agent (v0.9.22)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "bug-replicator"

REQUIRED_BODY_SECTIONS = (
    "## Inputs",
    "## Process",
    "## Exit verdicts",
    "## What this agent does NOT do",
    "## Hard rules",
)

EXIT_VERDICTS = ("reproduced", "could-not-reproduce", "needs-clarification")


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
        assert key in fm, f"bug-replicator: missing frontmatter key `{key}`"
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_opus(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert fm["model"] == "opus", "bug-replicator must use opus (judgment-heavy)"


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, "bug-replicator must NOT have Edit (analysis + bounded test-file writes only)"


def test_agent_tools_has_write(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" in tools, "bug-replicator must have Write (it authors reproduction test files)"


def test_agent_tools_has_bash(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Bash" in tools, "bug-replicator must have Bash (it runs the artifacts it writes)"


@pytest.mark.parametrize("section", REQUIRED_BODY_SECTIONS)
def test_required_body_section_present(plugin_root: Path, section: str) -> None:
    _, body = _read(plugin_root)
    assert section in body, f"bug-replicator agent body missing section: {section}"


@pytest.mark.parametrize("verdict", EXIT_VERDICTS)
def test_exit_verdict_named(plugin_root: Path, verdict: str) -> None:
    _, body = _read(plugin_root)
    assert verdict in body, f"bug-replicator body must name the `{verdict}` exit verdict"


def test_agent_names_playwright_and_dev_api_skills(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "playwright-user-flows" in body, "agent must reference playwright-user-flows skill"
    assert "dev-api-integration-testing" in body, "agent must reference dev-api-integration-testing skill"


def test_agent_must_currently_fail_rule(plugin_root: Path) -> None:
    """The agent body must state that the artifact MUST currently fail (the replication)."""
    _, body = _read(plugin_root)
    # The artifact-must-fail rule appears in the hard rules section.
    assert "must currently fail" in body.lower() or "MUST currently fail" in body, (
        "agent body must state the artifact must currently fail (= the replication)"
    )
