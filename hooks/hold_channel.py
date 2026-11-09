"""The quiet Stop-hold channel's harness pin (v4.1.1).

Why this exists. Since v4.1.0 a refused Stop travels as hook JSON on stdout
with ``hookSpecificOutput.additionalContext``: Claude Code keeps the turn open
through the same loop protections as ``decision: block`` but shows the text
only as transcript feedback, so the agent's worklist no longer lands on the
user's screen. That behaviour is Claude Code's, verified against its hooks
documentation and the harness this plugin shipped on. If a later Claude Code
stops honouring ``additionalContext`` on Stop, the completion lock would keep
printing its hold and the harness would simply end the turn: the lock would be
disarmed and look fine. A kill-switch (``CT6_STOP_HOLD_MODE=block``) is a
remedy, not a detector.

What this is. One constant pair naming the harness range the quiet channel was
VERIFIED on, a reader for the running harness version, and a verdict the
SessionStart hook prints as one line when the harness is outside that range:
older than the first verified build (the field may not exist yet), or on a
newer release line nobody has re-verified. Re-verifying is the chapter
``references/completion-unlock.md`` describes; bumping the pin is a one-line
edit here, recorded in the CHANGELOG like any other release fact.

Version sources, in order: ``claude --version`` on PATH; the ``version`` field
the harness stamps on every transcript record (the SessionStart payload names
the transcript); nothing. An unknown version produces no warning -- a notice
on every harness that lacks the binary would be noise the user learns to
ignore -- and ``hold_channel_verdict`` says so in its ``reason`` for anyone
who asks. Stdlib-only; no import-time side effects.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# The harness the quiet hold channel was verified on. The lower bound is the
# first build the verification ran against; the line is the release line
# (major, minor) whose later patches are taken as the same behaviour. A newer
# LINE is unverified until someone re-verifies and bumps both constants.
HOLD_CHANNEL_VERIFIED_MIN: Tuple[int, int, int] = (2, 1, 319)
HOLD_CHANNEL_VERIFIED_LINE: Tuple[int, int] = (2, 1)
HOLD_CHANNEL_PIN_DISABLE_ENV = "CT6_HOLD_CHANNEL_PIN_DISABLED"
HOLD_MODE_ENV = "CT6_STOP_HOLD_MODE"

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _env_truthy(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v not in ("", "0", "false", "no")


def parse_version(text: Any) -> Optional[Tuple[int, int, int]]:
    """The first ``X.Y.Z`` triple in ``text``, or None."""
    if not isinstance(text, str):
        return None
    m = _VERSION_RE.search(text)
    if not m:
        return None
    try:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:  # pragma: no cover - the regex admits digits only
        return None


def version_from_cli(claude_cmd: str = "claude", runner=subprocess.run) -> Optional[Tuple[int, int, int]]:
    """``claude --version`` parsed, or None when the binary is absent or odd."""
    try:
        if shutil.which(claude_cmd) is None:
            return None
        result = runner([claude_cmd, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if getattr(result, "returncode", 1) != 0:
        return None
    return parse_version(getattr(result, "stdout", "") or "")


def version_from_transcript(transcript_path: Any, max_lines: int = 200) -> Optional[Tuple[int, int, int]]:
    """The ``version`` the harness stamps on transcript records, from the first
    lines of the transcript the payload names; None when absent or unreadable."""
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return None
    path = Path(os.path.expanduser(transcript_path))
    try:
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    v = parse_version(rec.get("version"))
                    if v:
                        return v
    except OSError:
        return None
    return None


def detect_version(payload: Optional[Dict[str, Any]] = None, claude_cmd: str = "claude",
                   runner=subprocess.run) -> Tuple[Optional[Tuple[int, int, int]], str]:
    """(version, source) -- source is ``cli`` / ``transcript`` / ``unknown``."""
    v = version_from_cli(claude_cmd, runner)
    if v:
        return v, "cli"
    if isinstance(payload, dict):
        v = version_from_transcript(payload.get("transcript_path") or payload.get("transcriptPath"))
        if v:
            return v, "transcript"
    return None, "unknown"


def hold_channel_verdict(version: Optional[Tuple[int, int, int]]) -> Dict[str, Any]:
    """Is the running harness inside the range the quiet hold channel was
    verified on? Returns ``{"status", "reason", "version"}`` with status
    ``verified`` / ``older-than-verified`` / ``newer-line-unverified`` /
    ``unknown``. Pure."""
    if version is None:
        return {"status": "unknown", "version": None,
                "reason": "the Claude Code version could not be read (no `claude` on PATH and no transcript version), so the hold channel's pin cannot be checked"}
    label = ".".join(str(x) for x in version)
    if version < HOLD_CHANNEL_VERIFIED_MIN:
        return {"status": "older-than-verified", "version": label,
                "reason": f"Claude Code {label} predates {'.'.join(map(str, HOLD_CHANNEL_VERIFIED_MIN))}, the first build the quiet hold channel (additionalContext on Stop) was verified on; that field may not be honoured there"}
    if (version[0], version[1]) != HOLD_CHANNEL_VERIFIED_LINE:
        return {"status": "newer-line-unverified", "version": label,
                "reason": f"Claude Code {label} is a newer release line than {'.'.join(map(str, HOLD_CHANNEL_VERIFIED_LINE))}.x, where the quiet hold channel (additionalContext on Stop) was last verified"}
    return {"status": "verified", "version": label, "reason": "inside the verified range"}


def hold_channel_warning(payload: Optional[Dict[str, Any]] = None, claude_cmd: str = "claude",
                         runner=subprocess.run, env: Optional[Dict[str, str]] = None) -> str:
    """The one line SessionStart prints, or "" when there is nothing to say:
    the pin is disabled, the hold mode is already ``block`` (the loud channel
    needs no pin), the version is unknown, or the harness is inside the range."""
    e = os.environ if env is None else env
    if (e.get(HOLD_CHANNEL_PIN_DISABLE_ENV, "") or "").strip().lower() not in ("", "0", "false", "no"):
        return ""
    if (e.get(HOLD_MODE_ENV, "") or "").strip().lower() == "block":
        return ""
    version, source = detect_version(payload, claude_cmd, runner)
    verdict = hold_channel_verdict(version)
    if verdict["status"] in ("verified", "unknown"):
        return ""
    return (
        f"[CT6 hold channel] {verdict['reason']} (read from {source}). If agents stop with work "
        "still open, the completion lock may be disarmed on this harness: set "
        f"{HOLD_MODE_ENV}=block to use the hook-error channel instead, or re-verify the "
        "quiet channel and bump HOLD_CHANNEL_VERIFIED_* in hooks/hold_channel.py "
        f"({HOLD_CHANNEL_PIN_DISABLE_ENV}=1 silences this line)."
    )
