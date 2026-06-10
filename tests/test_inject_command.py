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


def test_inflight_inbox_helpers_use_polyglot_pattern() -> None:
    """B1/B3 (review-remediation): the inflight_inbox helper snippets (the RUN_ID
    detector + the append block) are read-only and never exit 2, so they remain in
    the v2.9.0 polyglot `python3 -c "..." || python -c "..."` form."""
    body = CMD.read_text(encoding="utf-8")
    lines_with_python3_to_inbox = [
        ln for ln in body.splitlines()
        if "python3" in ln and ("inflight_inbox" in ln or "current_run_id" in ln)
    ]
    polyglot_lines = [ln for ln in lines_with_python3_to_inbox if "|| python" in ln]
    assert polyglot_lines, "expected at least one polyglot python3 / || python helper invocation"


def test_banner_uses_detect_once_pattern() -> None:
    """B3 (review-remediation): the teams_mode --banner invocation converts to the
    v2.16.0 detect-once form (no `python3 X || python X` double-invocation)."""
    body = CMD.read_text(encoding="utf-8")
    banner_lines = [ln for ln in body.splitlines() if "teams_mode.py" in ln and "--banner" in ln]
    assert banner_lines, "expected a teams_mode --banner invocation"
    for ln in banner_lines:
        assert "$(command -v python3 || command -v python)" in ln, (
            f"banner invocation must use detect-once, got: {ln!r}"
        )
        assert "|| python " not in ln, (
            f"detect-once banner must not contain the `|| python ` double-invocation, got: {ln!r}"
        )


def test_helper_snippets_insert_plugin_root_on_syspath() -> None:
    """B1 (review-remediation): every python snippet importing hooks.inflight_inbox
    must first insert ${CLAUDE_PLUGIN_ROOT} onto sys.path so the import resolves
    regardless of cwd."""
    body = CMD.read_text(encoding="utf-8")
    # Every snippet that imports the helper module must carry the sys.path insert.
    assert "sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}')" in body, (
        "inflight_inbox helper snippets must insert ${CLAUDE_PLUGIN_ROOT} onto sys.path (B1)"
    )


def test_message_passed_quote_safe_via_env_var() -> None:
    """B1 (review-remediation): the message must be passed via an environment
    variable (read with os.environ), not interpolated as '''${MESSAGE}''' — so a
    message containing quotes / $ / backticks is handled verbatim. The check targets
    the actual append_clarification(...) CALL: the message argument must read from
    os.environ, and must NOT be the raw '''${MESSAGE}''' interpolation. (Prose that
    NAMES the forbidden form to explain why it's avoided is fine — only an actual
    append_clarification(ws, rid, '''${MESSAGE}''', ...) call is the defect.)"""
    body = CMD.read_text(encoding="utf-8")
    assert "AT_INJECT_MESSAGE" in body, "message must be passed via the AT_INJECT_MESSAGE env var (B1)"
    assert "os.environ['AT_INJECT_MESSAGE']" in body, "snippet must read the message from os.environ (B1)"
    # The append call must read the message from os.environ, never interpolate it.
    assert "append_clarification(ws, rid, os.environ['AT_INJECT_MESSAGE']" in body, (
        "append_clarification must take the message from os.environ (B1)"
    )
    assert "append_clarification(ws, rid, '''${MESSAGE}'''" not in body, (
        "append_clarification must NOT interpolate '''${MESSAGE}''' as the message argument (B1)"
    )
