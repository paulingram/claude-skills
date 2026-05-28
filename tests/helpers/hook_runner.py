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
        block per Claude Code's hook semantics).
    """
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
