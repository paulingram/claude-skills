"""Structural tests for /architect-team:mini and /architect-team:mini-review-sweep."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


COMMAND_NAMES = ("mini", "mini-review-sweep")


@pytest.mark.parametrize("cmd", COMMAND_NAMES)
def test_command_file_exists(plugin_root: Path, cmd: str) -> None:
    assert (plugin_root / "commands" / f"{cmd}.md").exists()


@pytest.mark.parametrize("cmd", COMMAND_NAMES)
def test_command_frontmatter_valid(plugin_root: Path, cmd: str) -> None:
    fm, body = frontmatter.parse(plugin_root / "commands" / f"{cmd}.md")
    assert isinstance(fm["description"], str) and len(fm["description"]) > 20
    assert body.strip()


def test_mini_command_documents_both_input_forms(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "commands" / "mini.md")
    assert "requirements folder" in body.lower() or "requirements-folder" in body.lower()
    assert "plain-language" in body.lower()


def test_mini_command_lists_required_flags(plugin_root: Path) -> None:
    fm, body = frontmatter.parse(plugin_root / "commands" / "mini.md")
    full_text = (fm.get("argument-hint", "") + "\n" + body)
    for flag in ("--no-merge", "--squash-merge", "--no-commit", "--no-push", "--no-compact"):
        assert flag in full_text, f"mini command must document the {flag} flag"


def test_mini_command_points_to_skill(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "commands" / "mini.md")
    assert "mini-architect-team-pipeline" in body


def test_mini_sweep_command_documents_since_and_limit(plugin_root: Path) -> None:
    fm, body = frontmatter.parse(plugin_root / "commands" / "mini-review-sweep.md")
    full_text = (fm.get("argument-hint", "") + "\n" + body)
    for flag in ("--since", "--limit"):
        assert flag in full_text, f"mini-review-sweep must document the {flag} flag"


def test_mini_sweep_command_names_review_gates(plugin_root: Path) -> None:
    _, body = frontmatter.parse(plugin_root / "commands" / "mini-review-sweep.md")
    for gate in (
        "interaction-completeness",
        "editability-completeness",
        "visual-fidelity-reconciliation",
        "test-completeness-verifier",
        "dev-api-integration-testing",
    ):
        assert gate in body, f"mini-review-sweep must name the {gate!r} review gate"
