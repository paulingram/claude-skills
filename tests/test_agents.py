"""Validate every expected agent is present with valid frontmatter."""
from pathlib import Path

import pytest

from tests.helpers import frontmatter

EXPECTED_AGENTS: set[str] = {
    "system-architect",
    "frontend",
    "backend",
    "reconciler",
    "integration",
    "scaffold-agent",
    "codebase-map-reviewer",
    "integration-explorer",
    "master-synthesizer",
    "route-mapper",
    "test-completeness-verifier",
    "diagnostic-researcher",
    "editability-reviewer",
    "visual-capture",
    "visual-analyzer",
    "task-reviewer",
    "interaction-reviewer",
    "interaction-intuiter",
    "bug-replicator",
    "qa-replayer",
    "bug-classifier",
    "doc-updater",
    "flow-explorer",
    "flow-executor",
    "fix-sensibility-checker",
    "prompt-refiner",
    "mini-qa",
    "oracle-deriver",
    "adversarial-reviewer",
}

REQUIRED_KEYS = {"name", "description", "tools", "model", "color"}
VALID_MODELS = {"opus", "sonnet", "haiku"}
VALID_TOOLS = {
    "Read", "Edit", "Write", "Glob", "Grep", "LS", "Bash",
    "TodoWrite", "NotebookRead", "NotebookEdit",
    "WebFetch", "WebSearch", "Task",
}


def _present_agents(plugin_root: Path) -> set[str]:
    agents_dir = plugin_root / "agents"
    if not agents_dir.is_dir():
        return set()
    return {p.stem for p in agents_dir.glob("*.md")}


def test_all_expected_agents_present(plugin_root: Path) -> None:
    present = _present_agents(plugin_root)
    missing = EXPECTED_AGENTS - present
    assert not missing, f"missing agent files: {sorted(missing)}"


@pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
def test_agent_frontmatter_valid(plugin_root: Path, agent_name: str) -> None:
    path = plugin_root / "agents" / f"{agent_name}.md"
    if not path.exists():
        pytest.skip(f"{agent_name} not present yet")
    fm, body = frontmatter.parse(path)
    missing_keys = REQUIRED_KEYS - fm.keys()
    assert not missing_keys, f"{agent_name}: missing frontmatter keys: {missing_keys}"
    assert fm["name"] == agent_name, f"{agent_name}: frontmatter name mismatch"
    assert isinstance(fm["description"], str) and len(fm["description"]) > 20
    assert fm["model"] in VALID_MODELS, f"{agent_name}: invalid model {fm['model']!r}"
    # tools may be a list (PyYAML) or a string (fallback); normalize
    tools_raw = fm["tools"]
    if isinstance(tools_raw, str):
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
    else:
        tools = set(tools_raw)
    bad_tools = tools - VALID_TOOLS
    assert not bad_tools, f"{agent_name}: unknown tools: {sorted(bad_tools)}"
    assert tools, f"{agent_name}: tools list is empty"
    assert body.strip(), f"{agent_name}: body is empty"
