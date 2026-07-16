"""v2.16.0 — `.architect-team/in-progress.md` 4th valid disposition tests.

The pipeline-completion-audit Stop hook previously offered 3 valid resolutions
(complete work / escalation-pending.md / remove .architect-team/). v2.16.0
adds a 4th: a fresh `in-progress.md` marker signals the agent is actively
waiting on a background process and the audit allows the Stop.

Fresh = mtime within IN_PROGRESS_FRESHNESS_SECONDS (default 1 hour). Stale
markers are treated as missing so abandoned runs cannot silently bypass.
"""
from __future__ import annotations

from tests.helpers.module_loader import load_module
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def hook_module(plugin_root: Path):
    mod = load_module(plugin_root / "hooks" / "pipeline-completion-audit.py", "pipeline_completion_audit")
    return mod


def _make_at(tmp_path: Path) -> Path:
    """Create a `.architect-team/` directory with a realistic state file
    that triggers a violation (so the audit would normally BLOCK)."""
    at = tmp_path / ".architect-team"
    at.mkdir()
    bf = at / "bug-fix" / "fix-foo"
    bf.mkdir(parents=True)
    (bf / "intake.json").write_text(json.dumps({"slug": "fix-foo"}), encoding="utf-8")
    return at


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

def test_in_progress_marker_constant_exists(hook_module):
    assert hasattr(hook_module, "IN_PROGRESS_MARKER")
    assert hook_module.IN_PROGRESS_MARKER == "in-progress.md"


def test_in_progress_freshness_constant_exists(hook_module):
    assert hasattr(hook_module, "IN_PROGRESS_FRESHNESS_SECONDS")
    assert hook_module.IN_PROGRESS_FRESHNESS_SECONDS == 3600


def test_in_progress_is_fresh_helper_exists(hook_module):
    assert callable(getattr(hook_module, "_in_progress_is_fresh", None))


# ─────────────────────────────────────────────────────────────────────────────
# Marker freshness logic
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_marker_is_not_fresh(hook_module, tmp_path):
    at = tmp_path / ".architect-team"
    at.mkdir()
    assert hook_module._in_progress_is_fresh(at) is False


def test_fresh_marker_is_fresh(hook_module, tmp_path):
    at = tmp_path / ".architect-team"
    at.mkdir()
    (at / "in-progress.md").write_text("active", encoding="utf-8")
    assert hook_module._in_progress_is_fresh(at) is True


def test_stale_marker_is_not_fresh(hook_module, tmp_path):
    at = tmp_path / ".architect-team"
    at.mkdir()
    marker = at / "in-progress.md"
    marker.write_text("stale", encoding="utf-8")
    # Force mtime to 2 hours ago.
    past = time.time() - 7200
    os.utime(marker, (past, past))
    assert hook_module._in_progress_is_fresh(at) is False


def test_marker_at_exact_threshold_is_fresh(hook_module, tmp_path):
    at = tmp_path / ".architect-team"
    at.mkdir()
    marker = at / "in-progress.md"
    marker.write_text("borderline", encoding="utf-8")
    # Set mtime to exactly the threshold ago.
    past = time.time() - hook_module.IN_PROGRESS_FRESHNESS_SECONDS + 10
    os.utime(marker, (past, past))
    assert hook_module._in_progress_is_fresh(at) is True


# ─────────────────────────────────────────────────────────────────────────────
# CLI integration — --check mode respects the marker
# ─────────────────────────────────────────────────────────────────────────────

def _run_hook(plugin_root: Path, cwd: Path, mode: str = "--check") -> tuple[int, str]:
    cmd = [
        sys.executable,
        str(plugin_root / "hooks" / "pipeline-completion-audit.py"),
        mode,
    ]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stderr


def test_check_mode_with_fresh_marker_exits_0(plugin_root, tmp_path):
    """A fresh in-progress.md marker overrides the violation and allows Stop."""
    at = _make_at(tmp_path)
    (at / "in-progress.md").write_text("active", encoding="utf-8")
    rc, stderr = _run_hook(plugin_root, tmp_path)
    assert rc == 0, f"expected exit 0 with fresh marker; got {rc}; stderr: {stderr}"


def test_check_mode_with_stale_marker_blocks(plugin_root, tmp_path):
    """A stale in-progress.md marker is treated as missing — the audit
    still BLOCKS."""
    at = _make_at(tmp_path)
    marker = at / "in-progress.md"
    marker.write_text("stale", encoding="utf-8")
    past = time.time() - 7200
    os.utime(marker, (past, past))
    rc, stderr = _run_hook(plugin_root, tmp_path)
    assert rc != 0
    assert "BLOCKED" in stderr


def test_check_mode_with_no_marker_blocks(plugin_root, tmp_path):
    """Without the marker, violations BLOCK as before."""
    _make_at(tmp_path)
    rc, stderr = _run_hook(plugin_root, tmp_path)
    assert rc != 0
    assert "BLOCKED" in stderr


def test_check_mode_with_no_at_directory_exits_0(plugin_root, tmp_path):
    """No .architect-team/ → not an architect-team run → exit 0."""
    rc, _ = _run_hook(plugin_root, tmp_path)
    assert rc == 0


# ─────────────────────────────────────────────────────────────────────────────
# BLOCKED message documents the new disposition
# ─────────────────────────────────────────────────────────────────────────────

def test_blocked_message_documents_4_dispositions(plugin_root, tmp_path):
    _make_at(tmp_path)
    rc, stderr = _run_hook(plugin_root, tmp_path)
    assert rc != 0
    # Must enumerate the 4 dispositions:
    assert "Four valid resolutions" in stderr or "1." in stderr
    assert "escalation-pending.md" in stderr
    assert "in-progress.md" in stderr
    assert "v2.16.0" in stderr
    assert "remove the .architect-team/ directory" in stderr.lower() or "abandoned" in stderr


def test_blocked_message_documents_freshness_threshold(plugin_root, tmp_path):
    _make_at(tmp_path)
    rc, stderr = _run_hook(plugin_root, tmp_path)
    assert rc != 0
    # The threshold value should appear in the message.
    assert "3600" in stderr or "60 minutes" in stderr or "1 hour" in stderr.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Command body audit — pipeline-completion-audit uses detect-once polyglot
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cmd_file", [
    "architect-team.md",
    "bug-fix.md",
    "ux-test.md",
])
def test_command_body_uses_v2160_detect_once_polyglot(plugin_root, cmd_file):
    """The v2.16.0 fix replaced `python3 X --check || python X --check` with
    `$(command -v python3 || command -v python) X --check` in the 3 command
    files that invoke pipeline-completion-audit.py. This eliminates the
    double-execution that caused the BLOCKED message to print twice."""
    body = (plugin_root / "commands" / cmd_file).read_text(encoding="utf-8")
    # The detect-once pattern must be present near the audit invocation.
    audit_lines = [
        line for line in body.splitlines()
        if "pipeline-completion-audit.py" in line
    ]
    assert audit_lines, f"{cmd_file} does not invoke pipeline-completion-audit"
    has_detect_once = any(
        "$(command -v python3" in line and "command -v python)" in line
        for line in audit_lines
    )
    assert has_detect_once, (
        f"{cmd_file} still uses the v2.9.0 `python3 X || python X` polyglot for "
        f"pipeline-completion-audit; the v2.16.0 fix uses the detect-once "
        f"`$(command -v python3 || command -v python) X` pattern to avoid "
        f"double-printing the BLOCKED message."
    )
