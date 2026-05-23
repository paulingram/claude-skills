"""Structural tests for the `qa-replayer` agent (v0.9.22)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "qa-replayer"

EXIT_VERDICTS = ("bug-resolved", "bug-still-present", "env-failure")


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
    fm, _ = _read(plugin_root)
    assert fm["model"] == "opus"


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, "qa-replayer must NOT have Edit"


def test_agent_tools_no_write(plugin_root: Path) -> None:
    """The QA replayer re-runs artifacts via Bash; it does NOT write feature code or artifacts."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" not in tools, "qa-replayer must NOT have Write (re-runs only; verdict via Bash heredoc)"


def test_agent_tools_has_bash(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Bash" in tools, "qa-replayer must have Bash to re-run reproduction artifacts"


@pytest.mark.parametrize("verdict", EXIT_VERDICTS)
def test_exit_verdict_named(plugin_root: Path, verdict: str) -> None:
    _, body = _read(plugin_root)
    assert verdict in body, f"qa-replayer body must name the `{verdict}` verdict"


def test_pass_criterion_is_symptom_gone_end_to_end(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "symptom" in body.lower() and "end-to-end" in body.lower(), (
        "qa-replayer body must state the 'originating symptom is gone end-to-end' pass criterion"
    )


def test_env_failure_routes_to_implementing_team(plugin_root: Path) -> None:
    """On env-failure, route to implementing team — NOT to the architect (the fix is not on trial)."""
    _, body = _read(plugin_root)
    assert "implementing team" in body.lower(), (
        "qa-replayer body must state that env-failure routes to the implementing team"
    )


def test_agent_does_not_modify_artifacts(plugin_root: Path) -> None:
    """The replayer re-runs the reproduction artifacts verbatim — no edits."""
    _, body = _read(plugin_root)
    assert "verbatim" in body.lower(), "qa-replayer must state it re-runs artifacts verbatim"
    assert "no edits" in body.lower() or "NEVER edit" in body, (
        "qa-replayer must explicitly forbid editing the reproduction artifacts"
    )
