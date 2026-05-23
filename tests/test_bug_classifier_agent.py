"""Structural tests for the `bug-classifier` agent (v0.9.22)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "bug-classifier"

VERDICT_KINDS = ("bug", "feature", "mixed", "unclear")
VERDICT_FIELDS = ("kind", "bug_portion", "feature_portion", "confidence", "reasoning")


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


def test_agent_model_is_sonnet(plugin_root: Path) -> None:
    """Classifier is lightweight — sonnet, not opus."""
    fm, _ = _read(plugin_root)
    assert fm["model"] == "sonnet", "bug-classifier must use sonnet (lightweight classification)"


def test_agent_tools_minimal_analysis_only(plugin_root: Path) -> None:
    """Bug-classifier is analysis-only: Read/Glob/Grep/TodoWrite — no Bash, no Edit, no Write."""
    fm, _ = _read(plugin_root)
    tools = set(_tools_list(fm))
    allowed = {"Read", "Glob", "Grep", "TodoWrite"}
    forbidden = {"Bash", "Edit", "Write"}
    assert tools <= allowed, f"bug-classifier tools must be subset of {allowed}; got extras: {tools - allowed}"
    assert tools.isdisjoint(forbidden), f"bug-classifier MUST NOT have any of {forbidden}; got: {tools & forbidden}"
    # All four allowed tools should be present.
    assert tools == allowed, f"bug-classifier tools must be exactly {allowed}; got: {tools}"


@pytest.mark.parametrize("kind", VERDICT_KINDS)
def test_verdict_kind_value_named(plugin_root: Path, kind: str) -> None:
    _, body = _read(plugin_root)
    assert kind in body, f"bug-classifier body must name the `{kind}` verdict value"


@pytest.mark.parametrize("field", VERDICT_FIELDS)
def test_verdict_schema_field_named(plugin_root: Path, field: str) -> None:
    _, body = _read(plugin_root)
    assert field in body, f"bug-classifier body must name the verdict field `{field}`"


def test_lex_pass_method_documented(plugin_root: Path) -> None:
    """The agent body must document the lex-pass-then-structural-read method."""
    _, body = _read(plugin_root)
    assert "lex" in body.lower() or "lex-pass" in body.lower(), (
        "agent body must document the lex-pass step"
    )
    # And the keyword-list approach.
    assert "bug-keyword" in body.lower() or "Bug-keyword" in body, "agent must list bug-keywords"
    assert "feature-keyword" in body.lower() or "Feature-keyword" in body, "agent must list feature-keywords"


def test_explicit_flag_overrides_documented(plugin_root: Path) -> None:
    """The agent must honor --bug-fix and --feature-only flag overrides."""
    _, body = _read(plugin_root)
    assert "--bug-fix" in body, "agent must document the --bug-fix flag override"
    assert "--feature-only" in body, "agent must document the --feature-only flag override"
