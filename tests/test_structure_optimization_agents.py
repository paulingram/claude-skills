"""v3.11.0 structural tests - the three structure-optimization agents + the
system-architect Restructure Plan Audit mode.

The structure-optimization pipeline (see tests/test_structure_optimization_skill.py)
spawns three NEW agent roles with producer/checker separation:

* ``structure-analyst`` (opus, x3)  - independent restructure drafts carrying a
  FULL file partition (every tracked file is in the movement table or the
  explicit stays list);
* ``reference-tracer`` (sonnet, xN) - mechanical reference-closure over an
  assigned shard of the converged movement table, file:line evidence per entry;
* ``structure-adversary`` (opus, x3) - refutation-only review that hunts for
  missed references via search modalities the tracers did not use, re-runs the
  partition check, and only goes quiet after two consecutive all-clean rounds.

Plus ONE extended agent: ``system-architect`` gains the Restructure Plan Audit
mode (Phase S6 of the pipeline).

IMPORTANT (Windows cp1252 portability): every file read passes
``encoding="utf-8"`` explicitly and this module is ASCII-only. Headings in the
agent bodies may use an em-dash; assertions match ASCII prefix + ASCII tail
substrings rather than embedding the em-dash literal.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter
from tests.test_agents import VALID_COLORS, VALID_MODELS, VALID_TOOLS

NEW_AGENTS = ("structure-analyst", "reference-tracer", "structure-adversary")

# The three canonical boilerplate H2s every standard agent carries
# (synced by scripts/setup/sync_agent_boilerplate.py).
BOILERPLATE_H2S = (
    "## Operating context (v1.0.0)",
    "## Forbidden git operations",
    "## Checkpoint discipline",
)


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def _agent(plugin_root: Path, name: str) -> tuple[dict, str]:
    path = plugin_root / "agents" / f"{name}.md"
    assert path.exists(), f"agents/{name}.md missing"
    return frontmatter.parse(path)


# --------------------------------------------------------------------------- #
# 1. Presence + frontmatter validity (house palettes)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("agent_name", NEW_AGENTS)
def test_agent_present_with_valid_frontmatter(plugin_root: Path, agent_name: str) -> None:
    fm, body = _agent(plugin_root, agent_name)
    assert fm["name"] == agent_name
    assert isinstance(fm["description"], str) and len(fm["description"]) > 40
    assert fm["model"] in VALID_MODELS
    assert fm["color"] in VALID_COLORS
    tools_raw = fm["tools"]
    tools = (
        {t.strip() for t in tools_raw.split(",") if t.strip()}
        if isinstance(tools_raw, str)
        else set(tools_raw)
    )
    assert tools and not (tools - VALID_TOOLS), f"{agent_name}: bad tools {tools}"
    assert body.strip()


def test_analyst_and_adversary_are_opus_tracer_is_sonnet(plugin_root: Path) -> None:
    """Design reasoning (analyst) and refutation (adversary) get opus; the
    mechanical reference crawl (tracer) is sonnet."""
    assert _agent(plugin_root, "structure-analyst")[0]["model"] == "opus"
    assert _agent(plugin_root, "structure-adversary")[0]["model"] == "opus"
    assert _agent(plugin_root, "reference-tracer")[0]["model"] == "sonnet"


# --------------------------------------------------------------------------- #
# 2. Canonical boilerplate blocks (sync_agent_boilerplate.py standard agents)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("agent_name", NEW_AGENTS)
@pytest.mark.parametrize("h2", BOILERPLATE_H2S)
def test_agent_carries_canonical_boilerplate(plugin_root: Path, agent_name: str, h2: str) -> None:
    body = _read(plugin_root, "agents", f"{agent_name}.md")
    assert h2 in body, f"{agent_name}: missing canonical block {h2!r}"


# --------------------------------------------------------------------------- #
# 3. Per-agent mandates
# --------------------------------------------------------------------------- #


def test_structure_analyst_mandate(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "structure-analyst.md")
    # The full-partition obligation: every tracked file accounted for.
    assert "partition" in body
    assert "stays" in body
    assert "movement table" in body
    assert "git ls-files" in body
    # Round-1 independence (same contract as codebase-map-reviewer).
    assert "do NOT consult" in body
    # Drafts land in the run directory, never in the target codebase.
    assert ".architect-team/structure-optimization/" in body
    # Brainstorming discipline before committing to an approach.
    assert "superpowers:brainstorming" in body


def test_reference_tracer_mandate(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "reference-tracer.md")
    # Mechanical closure with evidence, over an assigned shard.
    assert "file:line" in body
    assert "shard" in body
    assert "references_in" in body
    assert "references_out_relative" in body
    # The search surfaces beyond plain imports.
    for kind in ("config", "ci", "docs", "string-path"):
        assert kind in body, f"reference-tracer: missing search surface {kind!r}"
    # Never judges the structure; reports what must change.
    assert "do NOT judge" in body or "never judges" in body


def test_structure_adversary_mandate(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "structure-adversary.md")
    # Refutation-only mandate.
    assert "refute" in body.lower()
    # Independent search modalities (not the tracers' searches re-run).
    assert "modalit" in body  # modality / modalities
    assert "basename" in body
    assert "git log --follow" in body
    # Re-runs the deterministic partition check itself.
    assert "partition check" in body
    # The exit rule the skill enforces.
    assert "two consecutive" in body
    # Migration-order hazards are in scope.
    assert "cyclic" in body or "cycle" in body


@pytest.mark.parametrize("agent_name", NEW_AGENTS)
def test_agent_names_producer_checker_separation(plugin_root: Path, agent_name: str) -> None:
    """v0.9.13 discipline at pipeline scale: analysts design, tracers crawl,
    adversaries refute - no role verifies its own output."""
    body = _read(plugin_root, "agents", f"{agent_name}.md")
    assert "producer-cannot-be-its-own-checker" in body


# --------------------------------------------------------------------------- #
# 4. system-architect Restructure Plan Audit mode
# --------------------------------------------------------------------------- #


def test_system_architect_has_restructure_plan_audit_mode(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "system-architect.md")
    assert "## Restructure Plan Audit" in body
    # Indexed in the audit-modes index.
    index_start = body.index("## Audit modes (index)")
    index_section = body[index_start: body.index("## ", index_start + 10)]
    assert "Restructure Plan Audit" in index_section


def test_restructure_plan_audit_verdict_keys(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "system-architect.md")
    for key in (
        "partition_check_confirmed",
        "reference_closure_spot_check",
        "migration_order_sound",
    ):
        assert key in body, f"system-architect: Restructure Plan Audit missing verdict key {key!r}"
