"""Structural tests for the v2.19.0 /architect-team:inject slash command."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CMD = REPO_ROOT / "commands" / "inject.md"


def test_command_md_exists() -> None:
    assert CMD.is_file()


def test_command_carries_frontmatter() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert body.startswith("---")
    front, _, _ = body[3:].partition("---")
    assert "description:" in front
    assert "argument-hint:" in front


def test_command_documents_message_argument() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "<message>" in body or "message" in body


def test_command_invokes_helper_module() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "inflight_inbox" in body
    assert "append_clarification" in body
    assert "current_run_id" in body


def test_command_handles_no_active_run() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "no active run" in body.lower() or "no in-flight" in body.lower()


def test_command_documents_dispatch_banner() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "teams_mode.py" in body or "format_dispatch_banner" in body


def test_command_cross_references_canonical_home() -> None:
    body = CMD.read_text(encoding="utf-8")
    assert "common-pipeline-conventions" in body
    assert "v2.19.0" in body


def test_command_uses_polyglot_python_pattern() -> None:
    body = CMD.read_text(encoding="utf-8")
    lines_with_python3_to_inbox = [
        ln for ln in body.splitlines()
        if "python3" in ln and ("inflight_inbox" in ln or "current_run_id" in ln)
    ]
    # At least the helper invocation lines use polyglot
    polyglot_lines = [ln for ln in lines_with_python3_to_inbox if "|| python" in ln]
    assert polyglot_lines, "expected at least one polyglot python3 / || python helper invocation"
