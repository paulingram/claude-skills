"""A8 (review-remediation): the four hooks decode stdin as UTF-8.

`pipeline-completion-audit.py`, `review-gate-task.py`, `teammate-idle-check.py`,
and `pretool_unilateral_override_guard.py` previously read stdin through the
locale text codec (`sys.stdin.read()`). A hook payload is JSON that can carry
UTF-8 — an emoji in a task title — and on a cp1252 console the locale decode
raises `UnicodeDecodeError`, degrading the gate to a silent traceback/no-op.

This test pipes a UTF-8-encoded JSON payload (with an emoji) to each hook as a
subprocess, forcing the child's stdio encoding to cp1252, and asserts the hook
does NOT traceback (it decodes the payload and runs its logic). Each hook
fail-opens to exit 0 for a benign / non-matching payload, which is the safe
outcome we assert.

Two layers:
  1. Each hook's `_read_stdin_utf8()` helper decodes raw bytes as utf-8.
  2. End-to-end subprocess: a UTF-8 payload under a cp1252 child does not crash.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "hooks"

# Hook scripts that A8 switched to UTF-8 stdin decoding.
A8_HOOKS = [
    "pipeline-completion-audit.py",
    "review-gate-task.py",
    "teammate-idle-check.py",
    "pretool_unilateral_override_guard.py",
]

# A JSON payload carrying a multi-byte UTF-8 emoji in a task title — the exact
# A8 regression trigger.
_EMOJI = "\U0001F680"  # rocket
_UTF8_PAYLOAD = json.dumps(
    {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": f"T-{_EMOJI}-title", "status": "completed"},
        "task": {"title": f"Ship {_EMOJI} the dashboard"},
        "stop_hook_active": False,
    }
).encode("utf-8")


def _run_hook(script: str, payload_bytes: bytes, cp1252: bool = True):
    env = dict(os.environ)
    if cp1252:
        # Force the child's stdio codec to cp1252 — the Windows-console
        # condition the bug manifests under. The hook must STILL decode the
        # UTF-8 stdin bytes correctly because it reads sys.stdin.buffer.
        env["PYTHONIOENCODING"] = "cp1252"
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=payload_bytes,
        capture_output=True,
        cwd=str(REPO_ROOT),  # a dir with no live .architect-team run -> hooks no-op
        env=env,
    )


@pytest.mark.parametrize("script", A8_HOOKS)
def test_hook_file_exists(script: str) -> None:
    assert (HOOKS_DIR / script).exists(), f"{script} missing"


@pytest.mark.parametrize("script", A8_HOOKS)
def test_utf8_stdin_payload_does_not_traceback_under_cp1252(script: str) -> None:
    r = _run_hook(script, _UTF8_PAYLOAD, cp1252=True)
    stderr = r.stderr.decode("utf-8", "replace")
    assert "UnicodeDecodeError" not in stderr, (
        f"{script} raised UnicodeDecodeError on a UTF-8 stdin payload under "
        f"cp1252 — the gate degraded to a silent no-op. stderr={stderr!r}"
    )
    assert "Traceback" not in stderr, (
        f"{script} tracebacked on a UTF-8 stdin payload: {stderr!r}"
    )
    # The hooks fail-open to exit 0 for this benign payload (no live run / not a
    # teammate task / not a unilateral-override edit).
    assert r.returncode == 0, (
        f"{script} exited {r.returncode} on a benign UTF-8 payload "
        f"(expected fail-open 0); stderr={stderr!r}"
    )


@pytest.mark.parametrize("script", A8_HOOKS)
def test_empty_stdin_is_handled(script: str) -> None:
    """An empty stdin (no payload) must not crash either — the `if raw.strip()`
    / isatty guard handles it."""
    r = _run_hook(script, b"", cp1252=True)
    stderr = r.stderr.decode("utf-8", "replace")
    assert "Traceback" not in stderr, f"{script} tracebacked on empty stdin: {stderr!r}"
    assert r.returncode == 0


@pytest.mark.parametrize("script", A8_HOOKS)
def test_read_stdin_helper_decodes_utf8(script: str, monkeypatch) -> None:
    """Unit-level: each hook exposes `_read_stdin_utf8` that decodes raw bytes
    as utf-8 (not the locale codec)."""
    mod_name = script[:-3].replace("-", "_")
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        import importlib

        # The hook filenames use hyphens; load via importlib from the file path.
        spec = importlib.util.spec_from_file_location(mod_name, HOOKS_DIR / script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert hasattr(module, "_read_stdin_utf8"), (
            f"{script} is missing the _read_stdin_utf8 helper (A8)"
        )

        # Feed raw UTF-8 bytes through a fake stdin with a `.buffer`.
        class _FakeBuffer:
            def __init__(self, data: bytes):
                self._data = data

            def read(self) -> bytes:
                return self._data

        class _FakeStdin:
            def __init__(self, data: bytes):
                self.buffer = _FakeBuffer(data)

        raw = f"emoji {_EMOJI} test".encode("utf-8")
        monkeypatch.setattr(module.sys, "stdin", _FakeStdin(raw))
        decoded = module._read_stdin_utf8()
        assert decoded == f"emoji {_EMOJI} test", (
            f"{script}._read_stdin_utf8 did not utf-8-decode the bytes: {decoded!r}"
        )
    finally:
        sys.path.remove(str(HOOKS_DIR))
