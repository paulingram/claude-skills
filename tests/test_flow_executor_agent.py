"""Structural tests for the `flow-executor` agent (v0.9.29)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "flow-executor"


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


def test_agent_tools_has_bash_and_write(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools(fm)
    assert "Bash" in tools
    assert "Write" in tools


@pytest.mark.parametrize("verdict", ("pass", "fail", "flaky", "env-failure"))
def test_verdict_named(plugin_root: Path, verdict: str) -> None:
    _, body = _read(plugin_root)
    assert verdict in body, f"agent body must name verdict `{verdict}`"


def test_redundancy_rationale_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "redundancy" in body.lower() or "3 executors" in body or "three executors" in body.lower(), (
        "agent must document the 3-executor redundancy rationale"
    )


def test_per_flow_result_path_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "executions/executor-" in body, "agent must document the per-flow result file path"


def test_agent_does_not_consult_others(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    # Accept both "Does NOT consult" (verb starts capitalized at sentence start) and
    # "do NOT consult" (in a list bullet) and case-insensitive variants.
    assert "not consult" in body.lower(), (
        "agent must state it does not consult the other 2 executors"
    )


def test_no_credential_leakage_rule(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "credential" in body.lower() and "process.env" in body, (
        "agent must document the credential-env-var-only discipline"
    )
