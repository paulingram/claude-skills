"""Subprocess helper for invoking architect-team hook scripts in tests.

The three hook tests — `test_review_gate_task.py`, `test_teammate_idle_check.py`,
and `test_hooks_trigger_split.py` — all need to run a Python hook script as a
subprocess, feed a JSON payload to its stdin, and inspect the returncode +
stderr. Each previously carried its own verbatim copy of `_run(script,
workspace, payload)`. Drift risk: if hook invocation conventions change (a new
env var becomes required, the working-directory rule changes, a timeout needs
configuring), three places would have to update in lockstep.

This module exists so there is one place that knows how to invoke a hook
script the way the hooks themselves expect:

- stdin carries the JSON payload (the Claude Code hook contract);
- the script's cwd is the test workspace, so it resolves
  `.architect-team/...` relative to that workspace;
- `PYTHONIOENCODING=utf-8` is forced into the env so stdout/stderr decode
  consistently on Windows runners (where the default code page can otherwise
  mangle non-ASCII bytes the hook emits).

Stdlib only — `subprocess`, `json`, `sys`, `os`, `pathlib` — to keep the
helper usable from any test without extra dependencies.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_hook(
    script: Path,
    workspace: Path,
    payload: dict,
) -> "subprocess.CompletedProcess[str]":
    """Run a hook script as a subprocess with `payload` on stdin.

    Parameters
    ----------
    script:
        Absolute path to the hook script (e.g. ``hooks/review-gate-task.py``).
    workspace:
        Directory that becomes the subprocess's cwd. Hooks resolve
        ``.architect-team/...`` paths relative to this directory, so tests
        construct a temp workspace seeded with the required layout and pass
        it here.
    payload:
        The JSON-serialisable dict that will be written to the script's stdin.
        Matches the Claude Code hook payload contract (e.g. ``{"tool_name":
        "TaskUpdate", "tool_input": {...}}`` or ``{"hook_event_name":
        "TaskCompleted", "task": {"id": ...}}``).

    Returns
    -------
    subprocess.CompletedProcess[str]
        The completed process with text-mode ``stdout`` and ``stderr``
        captured; ``returncode`` is the hook's exit status (0 = allow, 2 =
        block for PreToolUse gates and ``--check`` CLIs). A Stop hook that
        HOLDS the turn exits 0 with hook JSON on stdout (v4.1.0) -- read it
        through ``blocked`` / ``allowed`` / ``hook_text`` below.
    """
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


# ---------------------------------------------------------------------------
# v4.1.0 -- reading a Stop hook's verdict.
#
# The completion audit used to refuse a stop with the directive on stderr and
# exit 2; since v4.1.0 it prints hook JSON on stdout and exits 0, carrying the
# directive in ``hookSpecificOutput.additionalContext`` (transcript-only "Stop
# hook feedback") or, under CT6_STOP_HOLD_MODE=block, in ``reason`` beside
# ``decision: "block"``. PreToolUse gates and ``--check`` CLIs still block with
# exit 2 and stderr. These three readers make a test indifferent to the
# channel: ``blocked`` / ``allowed`` say whether the hook refused, ``hook_text``
# is everything it said. A pin that cares about the CHANNEL itself reads
# ``hold_payload`` directly (tests/test_stop_hold_channel.py).
# ---------------------------------------------------------------------------

def hold_payload(proc) -> "dict | None":
    """The hook JSON object a Stop hook printed on stdout, or None."""
    out = getattr(proc, "stdout", None) or ""
    for line in reversed(out.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def hold_text(proc) -> "str | None":
    """The directive a Stop hook held the turn with, or None when it allowed."""
    data = hold_payload(proc)
    if not data:
        return None
    hso = data.get("hookSpecificOutput")
    if isinstance(hso, dict) and isinstance(hso.get("additionalContext"), str):
        return hso["additionalContext"]
    if data.get("decision") == "block":
        return str(data.get("reason") or "")
    return None


def blocked(proc) -> bool:
    """True when the hook refused: a Stop hold (JSON on stdout) or an exit-2 block."""
    return hold_text(proc) is not None or proc.returncode == 2


def allowed(proc) -> bool:
    """True when the hook let the event through: exit 0 and no hold on stdout."""
    return proc.returncode == 0 and hold_text(proc) is None


def hook_text(proc) -> str:
    """Everything the hook said: the Stop hold text (if any), then stderr."""
    held = hold_text(proc)
    return ((held + "\n") if held else "") + (getattr(proc, "stderr", None) or "")
