"""Validate every agent body is framed as a long-lived teammate (v1.0.0).

Covers REQ-5 (`Agent role-definition rewrite`) of the `agent-teams-refactor`
change. Three parametrized assertions per agent:

1. The body contains at least one of the long-lived framing strings
   (`teammate`, `long-lived`, `across multiple tasks within this run`).
2. The body does NOT contain self-spawn claims (regex on
   `I (will )?spawn ... team|in parallel|agents`). Internal `Agent`-tool
   sub-research within a teammate's task is permitted; only self-claims to
   spawn a team or N-parallel agents are forbidden.
3. The body contains the `## Operating context (v1.0.0)` section exactly once.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.helpers import frontmatter

EXPECTED_AGENTS: tuple[str, ...] = (
    "backend",
    "bug-classifier",
    "bug-replicator",
    "codebase-map-reviewer",
    "diagnostic-researcher",
    "doc-updater",
    "editability-reviewer",
    "fix-sensibility-checker",
    "flow-executor",
    "flow-explorer",
    "frontend",
    "integration",
    "integration-explorer",
    "interaction-intuiter",
    "interaction-reviewer",
    "master-synthesizer",
    "mini-qa",
    "prompt-refiner",
    "qa-replayer",
    "reconciler",
    "route-mapper",
    "scaffold-agent",
    "system-architect",
    "task-reviewer",
    "test-completeness-verifier",
    "visual-analyzer",
    "visual-capture",
)

LONG_LIVED_FRAMING_STRINGS: tuple[str, ...] = (
    "teammate",
    "long-lived",
    "across multiple tasks within this run",
)

# Matches self-spawn claims a teammate must NOT make. Catches phrasings like
# "I will spawn the X team", "I spawn three reviewers in parallel",
# "I spawn additional agents". Does NOT catch descriptive references to the
# orchestrator/Lead dispatching the agent (e.g., "the orchestrator spawns
# three researchers in parallel").
SPAWN_CLAIM_RE = re.compile(
    r"\bI (will )?spawn .{0,40}\b(team|in parallel|agents)\b",
    re.IGNORECASE,
)

OPERATING_CONTEXT_HEADING = "## Operating context (v1.0.0)"


def _agent_body(plugin_root: Path, agent_name: str) -> str:
    path = plugin_root / "agents" / f"{agent_name}.md"
    _, body = frontmatter.parse(path)
    return body


@pytest.mark.parametrize("agent_name", EXPECTED_AGENTS)
def test_agent_body_carries_long_lived_framing(
    plugin_root: Path, agent_name: str
) -> None:
    body = _agent_body(plugin_root, agent_name)
    lowered = body.lower()
    matches = [s for s in LONG_LIVED_FRAMING_STRINGS if s.lower() in lowered]
    assert matches, (
        f"{agent_name}: body must contain at least one long-lived framing "
        f"string from {LONG_LIVED_FRAMING_STRINGS}; found none"
    )


@pytest.mark.parametrize("agent_name", EXPECTED_AGENTS)
def test_agent_body_contains_no_self_spawn_claim(
    plugin_root: Path, agent_name: str
) -> None:
    body = _agent_body(plugin_root, agent_name)
    hits = SPAWN_CLAIM_RE.findall(body)
    assert not hits, (
        f"{agent_name}: body contains self-spawn claim(s) {hits!r}; "
        f"only the Lead spawns teams — rewrite to Lead-deferred phrasing"
    )


@pytest.mark.parametrize("agent_name", EXPECTED_AGENTS)
def test_agent_body_has_operating_context_section(
    plugin_root: Path, agent_name: str
) -> None:
    body = _agent_body(plugin_root, agent_name)
    occurrences = body.count(OPERATING_CONTEXT_HEADING)
    assert occurrences == 1, (
        f"{agent_name}: expected exactly one '{OPERATING_CONTEXT_HEADING}' "
        f"section, found {occurrences}"
    )
