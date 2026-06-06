"""Structural tests for the v2.18.0 /architect-team:discipline-status command."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CMD = REPO_ROOT / "commands" / "discipline-status.md"


def test_command_md_exists() -> None:
    assert CMD.is_file()


def test_command_carries_frontmatter() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert body.startswith("---")
    front, _, _ = body[3:].partition("---")
    assert "description:" in front
    assert "argument-hint:" in front


def test_command_documents_apply_flag() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "--apply" in body


def test_command_documents_workspace_flag() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "--workspace" in body


def test_command_default_is_read_only() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "read-only" in body.lower()


def test_command_invokes_layer3_tool() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "verify-discipline-registry-current" in body


def test_command_documents_dispatch_banner() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "teams_mode.py" in body or "format_dispatch_banner" in body


def test_command_cross_references_canonical_home() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "common-pipeline-conventions" in body
    assert "v2.18.0" in body
