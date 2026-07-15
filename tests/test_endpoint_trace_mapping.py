"""Structural tests for the endpoint-trace-mapping skill + endpoint-tracer agent
(lineage roadmap P1 / the CDLG foundation).

These assert the *contract documentation* exists and is wired correctly:

* the skill is present with valid frontmatter and documents the two-layer
  extraction contract, REQ-DOC-06 witness verification, the two artifacts, and
  the func:// / asset:// nomenclature, and cites hooks/lineage_graph.py;
* the agent is present with valid frontmatter (tools / model / color) and
  carries the three canonical boilerplate blocks byte-faithfully so
  tests/test_agent_boilerplate_sync.py stays green.

The deterministic behavior of the CDLG core is covered by
tests/test_lineage_graph.py — these tests only cover the markdown contracts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter
from tests.helpers.module_loader import load_module


# ---------------------------------------------------------------------------
# Skill: skills/endpoint-trace-mapping/SKILL.md
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def skill_path(plugin_root: Path) -> Path:
    return plugin_root / "skills" / "endpoint-trace-mapping" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text(skill_path: Path) -> str:
    assert skill_path.exists(), f"skill missing at {skill_path}"
    return skill_path.read_text(encoding="utf-8")


def test_skill_exists_and_frontmatter_valid(skill_path: Path) -> None:
    fm, body = frontmatter.parse(skill_path)
    assert fm.get("name") == "endpoint-trace-mapping"
    assert isinstance(fm.get("description"), str) and len(fm["description"]) > 20
    assert body.strip(), "SKILL.md body is empty"


def test_skill_documents_two_layer_extraction(skill_text: str) -> None:
    lowered = skill_text.lower()
    assert "intra-service" in lowered
    assert "inter-service" in lowered
    # intra-service: LSP-first static seed + LLM-refine on ambiguity
    assert "lsp" in lowered
    assert "ambiguity" in lowered or "ambiguous" in lowered
    # inter-service: route/contract matching, NOT call-graph traversal
    assert "route/contract matching" in lowered or "route / contract matching" in lowered
    assert "not call-graph traversal" in lowered or "not a function edge" in lowered
    # reuses the existing maps as priors (REQ-DOC-07)
    assert "INTEGRATION_MAP" in skill_text
    assert "INTERACTION_INTUITION_MAP" in skill_text


def test_skill_documents_witness_verification(skill_text: str) -> None:
    assert "code-path-witness.json" in skill_text  # reuses existing witness
    assert "REQ-DOC-06" in skill_text
    lowered = skill_text.lower()
    assert "recall" in lowered
    assert "hallucination" in lowered
    # cite the module functions (the deterministic gate)
    assert "reconcile_with_witness" in skill_text
    assert "witness_gate" in skill_text


def test_skill_documents_artifacts(skill_text: str) -> None:
    assert "ENDPOINT_TRACE_MAP.md" in skill_text
    assert "lineage-graph.json" in skill_text
    lowered = skill_text.lower()
    assert "mermaid" in lowered
    assert "datestamp" in lowered or "last_traced" in skill_text


def test_skill_documents_nomenclature(skill_text: str) -> None:
    assert "func://" in skill_text
    assert "asset://" in skill_text
    assert "REQ-MEM-02" in skill_text
    # rename-stability fallback is named
    assert "stable_func_key" in skill_text
    assert "content_fingerprint" in skill_text


def test_skill_cites_the_deterministic_module(skill_text: str) -> None:
    assert "hooks/lineage_graph.py" in skill_text
    # the honest boundary: live extraction is the agent's job; the deterministic
    # pieces live in the module.
    lowered = skill_text.lower()
    assert "deterministic" in lowered


def test_skill_documents_cost_ceiling_and_freshness(skill_text: str) -> None:
    assert "REQ-DOC-08" in skill_text  # cost ceiling
    assert "REQ-DOC-04" in skill_text  # transitive freshness
    assert "transitive_stale_nodes" in skill_text
    assert "truncate_to_budget" in skill_text
    assert "MERMAID_MAX_NODES" in skill_text


def test_skill_documents_write_ownership(skill_text: str) -> None:
    # REQ-SAFE-01: lineage-graph.json is orchestrator-written or per-subset sharded
    assert "REQ-SAFE-01" in skill_text
    lowered = skill_text.lower()
    assert "orchestrator" in lowered
    assert "shard" in lowered


# ---------------------------------------------------------------------------
# Agent: agents/endpoint-tracer.md
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def agent_path(plugin_root: Path) -> Path:
    return plugin_root / "agents" / "endpoint-tracer.md"


@pytest.fixture(scope="module")
def agent_text(agent_path: Path) -> str:
    assert agent_path.exists(), f"agent missing at {agent_path}"
    return agent_path.read_text(encoding="utf-8")


def test_agent_exists_and_frontmatter_valid(agent_path: Path) -> None:
    fm, body = frontmatter.parse(agent_path)
    assert fm.get("name") == "endpoint-tracer"
    assert isinstance(fm.get("description"), str) and len(fm["description"]) > 20
    assert fm.get("model") in {"opus", "sonnet", "haiku", "fable"}
    assert fm.get("color")
    # tools list present and non-empty
    tools_raw = fm.get("tools")
    if isinstance(tools_raw, str):
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
    else:
        tools = set(tools_raw or [])
    assert tools, "agent tools list is empty"
    assert "Write" in tools and "Read" in tools
    assert body.strip(), "agent body is empty"


def test_agent_carries_canonical_boilerplate_blocks(agent_text: str, plugin_root: Path) -> None:
    """The agent must carry the three canonical blocks byte-faithfully so the
    boilerplate-sync drift guard recognizes it as a STANDARD agent (not 'other').
    """
    import importlib.util

    blocks = load_module(plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py", "agent_boilerplate_blocks_etm")

    # universal-newline form so CRLF/LF compare equal
    text_lf = agent_text.replace("\r\n", "\n").replace("\r", "\n")

    git_block = blocks.extract_block(text_lf, blocks.FORBIDDEN_GIT_OPERATIONS_HEADING)
    assert git_block == blocks.FORBIDDEN_GIT_OPERATIONS

    chk_block = blocks.extract_block(text_lf, blocks.CHECKPOINT_DISCIPLINE_HEADING)
    assert chk_block == blocks.CHECKPOINT_DISCIPLINE

    op_block = blocks.extract_block(text_lf, blocks.OPERATING_CONTEXT_HEADING)
    assert op_block is not None and op_block.startswith(blocks.OPERATING_CONTEXT)


def test_agent_is_registered_as_standard_in_boilerplate(plugin_root: Path) -> None:
    """endpoint-tracer must be in the baked standard_agents list for all 3 blocks."""
    import importlib.util

    blocks = load_module(plugin_root / "scripts" / "setup" / "agent_boilerplate_blocks.py", "agent_boilerplate_blocks_etm2")
    for block_id in ("forbidden-git-operations", "checkpoint-discipline", "operating-context"):
        assert "endpoint-tracer" in blocks.BLOCKS[block_id]["standard_agents"], (
            f"endpoint-tracer not registered as standard for {block_id}"
        )


def test_agent_body_describes_tracer_job(agent_text: str) -> None:
    assert "ENDPOINT_TRACE_MAP.md" in agent_text
    assert "lineage-graph.json" in agent_text
    assert "hooks/lineage_graph.py" in agent_text
    assert "code-path-witness.json" in agent_text
    lowered = agent_text.lower()
    # subset-only / scope discipline (cost control)
    assert "subset" in lowered
    # two-layer extraction named
    assert "intra-service" in lowered and "inter-service" in lowered
