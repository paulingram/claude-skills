"""Structural tests for the `fix-sensibility-checker` agent (v0.9.29)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "fix-sensibility-checker"


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
    assert fm["model"] == "opus", (
        "fix-sensibility-checker is adversarial (hunts regressions in the fix's "
        "impact set) — model: opus under the v3.43.0 delivery-adversarial split; "
        "lever scripts/setup/set_default_model.py --split delivery")


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert "Edit" not in _tools(fm)


def test_agent_tools_has_bash_and_write(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools(fm)
    assert "Bash" in tools
    assert "Write" in tools


def test_impact_set_computation_section_present(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "## Impact-set computation" in body, (
        "fix-sensibility-checker must have a `## Impact-set computation` section documenting the git-grep heuristics"
    )


@pytest.mark.parametrize("verdict", ("sensible", "nonsensical", "env-failure", "not-reachable"))
def test_verdict_named(plugin_root: Path, verdict: str) -> None:
    _, body = _read(plugin_root)
    assert verdict in body, f"agent body must name verdict `{verdict}`"


def test_impact_set_kinds_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    for kind in ("ui-component", "importer", "nav-destination", "api-endpoint"):
        assert kind in body, f"impact set must distinguish kind `{kind}`"


def test_one_level_importer_bound(plugin_root: Path) -> None:
    """The impact-set expansion must be bounded at ONE level of importers (not transitive)."""
    _, body = _read(plugin_root)
    assert "one level" in body.lower() or "one-level" in body.lower() or "not recurse" in body.lower(), (
        "agent must document the one-level importer-expansion bound"
    )


def test_real_dev_environment_discipline(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "deployed dev environment" in body.lower() or "live target" in body.lower(), (
        "agent must state sensibility flows run against the deployed dev environment"
    )


def test_verdict_file_path_documented(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert ".architect-team/sensibility/" in body, "agent must document the verdict file path"
