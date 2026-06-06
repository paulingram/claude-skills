"""Structural tests for the v2.17.0 /architect-team:classify-test-prod-safety slash command."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CMD = REPO_ROOT / "commands" / "classify-test-prod-safety.md"


def test_command_md_exists() -> None:
    assert CMD.is_file()


def test_command_carries_frontmatter() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert body.startswith("---")


def test_command_documents_argument_hint() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "argument-hint:" in body
    assert "--write-annotations" in body or "write-annotations" in body
    assert "--dry-run" in body or "dry-run" in body


def test_command_default_is_dry_run() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "dry-run" in body.lower()
    assert "default" in body.lower()


def test_command_invokes_skill() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "test-prod-safety-classifier" in body


def test_command_documents_dispatch_banner() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert (
        "teams_mode.py" in body
        or "format_dispatch_banner" in body
        or "Dispatch mode banner" in body
        or "dispatch banner" in body.lower()
    )


def test_command_documents_auto_cleanup() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "cleanup_merged_worktrees" in body or "cleanup-worktrees" in body or "merged worktrees" in body.lower()


def test_command_cross_references_canonical_home() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "common-pipeline-conventions" in body or "v2.17.0" in body
