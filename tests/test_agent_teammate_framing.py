"""Validate every agent body is framed as a long-lived teammate (v1.0.0).

Covers REQ-5 (`Agent role-definition rewrite`) of the `agent-teams-refactor`
change. Four parametrized assertions per agent plus one global assertion on the
shared skill:

1. The body contains at least one of the long-lived framing strings
   (`teammate`, `long-lived`, `across multiple tasks within this run`).
2. The body does NOT contain self-spawn claims (regex on
   `I (will )?spawn ... team|in parallel|agents`). Internal `Agent`-tool
   sub-research within a teammate's task is permitted; only self-claims to
   spawn a team or N-parallel agents are forbidden.
3. The body contains the `## Operating context (v1.0.0)` section exactly once.
4. The body's operating-context section references the canonical shared
   section in `skills/team-spawning-and-review-gates/SKILL.md` (per
   `SR-audit-dup-2C-001` — the canonical paragraph lives in one place and the
   agent bodies point at it rather than each re-stating it).
5. The shared skill body contains the canonical long-lived-teammate paragraph
   (the contract owner check — if it disappears, the references the agents
   carry become dangling).
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

# The canonical shared section lives here; every agent body's operating-context
# section must reference it rather than re-stating the paragraph in full.
SHARED_SKILL_REL_PATH = "skills/team-spawning-and-review-gates/SKILL.md"
SHARED_SECTION_HEADING = "## Operating context (v1.0.0) — for teammate agents"
# A short, stable substring of the canonical paragraph used to verify it lives
# in the shared skill body (the contract owner). Choosing the explicit
# "Agent subagents for sub-research" clause because it is the load-bearing
# disambiguation between a permitted internal sub-research subagent and a
# forbidden nested team — and so a regression that flattens the paragraph would
# trip on this substring first.
SHARED_CANONICAL_SUBSTRING = (
    "Internal short-lived `Agent` subagents for sub-research within your task "
    "are permitted (per Claude Code's standard semantics) and are NOT a nested "
    "team."
)


def _agent_body(plugin_root: Path, agent_name: str) -> str:
    path = plugin_root / "agents" / f"{agent_name}.md"
    _, body = frontmatter.parse(path)
    return body


def _shared_skill_body(plugin_root: Path) -> str:
    path = plugin_root / SHARED_SKILL_REL_PATH
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
    # Count whole-line matches only — the agent's own H2 heading exists once.
    # A substring count would also match the shared-skill heading the agent
    # references inline (`## Operating context (v1.0.0) — for teammate agents`),
    # which is intentional — the reference quotes that heading and the test
    # must not punish the reference.
    occurrences = sum(
        1 for line in body.splitlines() if line.strip() == OPERATING_CONTEXT_HEADING
    )
    assert occurrences == 1, (
        f"{agent_name}: expected exactly one '{OPERATING_CONTEXT_HEADING}' "
        f"section heading line, found {occurrences}"
    )


@pytest.mark.parametrize("agent_name", EXPECTED_AGENTS)
def test_agent_body_references_shared_operating_context_section(
    plugin_root: Path, agent_name: str
) -> None:
    """Per SR-audit-dup-2C-001, the canonical paragraph lives once in the
    team-spawning-and-review-gates skill, and each agent body's operating-
    context section is a one-line pointer to it. Verify both substrings: the
    shared file path AND the canonical section heading."""
    body = _agent_body(plugin_root, agent_name)
    assert SHARED_SKILL_REL_PATH in body, (
        f"{agent_name}: body must reference the canonical shared skill at "
        f"'{SHARED_SKILL_REL_PATH}'; found no such reference"
    )
    assert SHARED_SECTION_HEADING in body, (
        f"{agent_name}: body must name the canonical shared section heading "
        f"'{SHARED_SECTION_HEADING}'; found no such reference"
    )


def test_shared_skill_carries_canonical_operating_context(
    plugin_root: Path,
) -> None:
    """The contract owner check: the shared skill at
    `skills/team-spawning-and-review-gates/SKILL.md` MUST carry the canonical
    `## Operating context (v1.0.0) — for teammate agents` section, and that
    section MUST contain the load-bearing internal-sub-research disambiguation
    clause. If this regresses, every agent's reference goes dangling."""
    body = _shared_skill_body(plugin_root)
    assert SHARED_SECTION_HEADING in body, (
        f"shared skill must carry the canonical section heading "
        f"'{SHARED_SECTION_HEADING}'; not found in "
        f"{SHARED_SKILL_REL_PATH}"
    )
    assert SHARED_CANONICAL_SUBSTRING in body, (
        f"shared skill must carry the canonical paragraph substring "
        f"distinguishing permitted internal `Agent` sub-research from a "
        f"forbidden nested team; not found in {SHARED_SKILL_REL_PATH}"
    )
