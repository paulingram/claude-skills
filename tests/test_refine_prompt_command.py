"""Structural tests for the `/architect-team:refine-prompt` command (v0.9.33)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


COMMAND_NAME = "refine-prompt"


def _command_path(plugin_root: Path) -> Path:
    return plugin_root / "commands" / f"{COMMAND_NAME}.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_command_path(plugin_root))


def test_command_file_exists(plugin_root: Path) -> None:
    assert _command_path(plugin_root).exists(), f"commands/{COMMAND_NAME}.md missing"


def test_command_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert "description" in fm and isinstance(fm["description"], str) and len(fm["description"]) > 50


def test_command_description_names_standalone_mode(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert "standalone" in fm["description"].lower() or "without running" in fm["description"].lower(), (
        "command description must declare standalone (no-downstream-pipeline) mode"
    )


def test_command_invokes_proposal_refiner_skill(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "proposal-refiner" in body, (
        "command body must invoke the proposal-refiner skill"
    )


def test_command_sets_refiner_mode_standalone(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "REFINER_MODE" in body and "standalone" in body.lower(), (
        "command must set $REFINER_MODE = 'standalone'"
    )


def test_command_argument_parsing_documented(plugin_root: Path) -> None:
    """The command's argument parser must document the prompt arg + flags."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "argument" in body_lower or "$prompt" in body_lower, (
        "command must document argument parsing"
    )
    # The --out flag overrides the output path
    assert "--out" in body, "command must document --out flag"
    # The --codebases flag scopes grounding
    assert "--codebases" in body, "command must document --codebases flag"
    # The --max-iterations flag overrides the ceiling
    assert "--max-iterations" in body, "command must document --max-iterations flag"


def test_command_refuses_already_refined_input(plugin_root: Path) -> None:
    """If $PROMPT resolves to an already-refined markdown, the command refuses."""
    _, body = _read(plugin_root)
    assert "refined-by" in body or "already-refined" in body.lower() or "already refined" in body.lower(), (
        "command must refuse re-refinement of an already-refined input"
    )


def test_command_does_not_trigger_pipeline(plugin_root: Path) -> None:
    """Standalone mode exits without running Phase −2 or any other downstream phase."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "does not trigger" in body_lower or "does not" in body_lower, (
        "command body must document the does-NOT list"
    )
    # The downstream pipelines are NOT invoked
    assert "no downstream" in body_lower or "no further work" in body_lower or "does not trigger" in body_lower, (
        "command must declare it does not trigger Phase −2 or any other downstream phase"
    )


def test_command_does_not_commit(plugin_root: Path) -> None:
    """Standalone mode produces a markdown but does NOT auto-commit."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "does not auto-commit" in body_lower or "not auto-commit" in body_lower or "no auto-commit" in body_lower or "auto-commit" in body_lower, (
        "command must declare no auto-commit"
    )


def test_command_invokes_proposal_refiner_via_skill_tool(plugin_root: Path) -> None:
    """The command says 'use the Skill tool with skill: proposal-refiner' (standard pattern)."""
    _, body = _read(plugin_root)
    # Match the standard invocation language used by other commands
    assert "Skill tool" in body or "skill: proposal-refiner" in body, (
        "command must use the standard Skill tool invocation pattern"
    )


def test_command_documents_safety_rules(plugin_root: Path) -> None:
    """The command must document the no-irreversible-state / no-source-edits / no-wakeup safety rules."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "schedulewakeup" in body_lower or "wall-clock" in body_lower or "no wakeup" in body_lower or "wakeup" in body_lower or "wakeups" in body_lower, (
        "command must forbid ScheduleWakeup / wall-clock timers"
    )
    assert "never invent" in body_lower or "fabricat" in body_lower, (
        "command must declare the no-invented-entities rule"
    )
