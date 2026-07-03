#!/usr/bin/env python3
"""SessionStart hook — run-continuity resume directive (v3.30.0).

Fires on every session start (`startup` / `resume` / `clear` / `compact`
sources). When the workspace's `.architect-team/active-run.json` marker says a
pipeline run is ACTIVE (see hooks/run_continuity.py), this hook injects a
short directive into the session's context: re-invoke the run-driving Skill
FIRST, then continue the run — do not solve by hand.

This is the PROACTIVE half of the v3.30.0 run-continuity pair (the sticky arm
in hooks/pretool_skill_gate.py is the enforcement half): a resumed session, a
fresh session opened in a mid-run workspace, and — critically — the same
session right after a context compaction (`source: "compact"`, where the
pipeline playbook text has just been dropped from context) all get told,
before their first action, that a run is in flight and how to resume it.

Output contract: plain stdout on exit 0 is added to the session context (the
documented SessionStart behaviour). No marker / inactive marker / kill-switch
/ ANY error => print nothing, exit 0. This hook never blocks anything.

Stdlib-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Dual-form import per house convention (package shape, then bare-module).
try:  # pragma: no cover - exercised by both import paths
    from hooks import run_continuity as _rc
except ImportError:  # pragma: no cover - bare-module fallback
    try:
        import run_continuity as _rc  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - substrate unavailable
        _rc = None  # type: ignore[assignment]


def _read_stdin_utf8() -> str:
    """Raw-bytes UTF-8 payload read (cp1252-safe; the A8 pattern)."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


def build_directive(payload: dict) -> str:
    """The resume directive for this payload, or "" when nothing applies.

    Pure function — safe to call from tests with any payload shape."""
    if _rc is None or _rc.continuity_disabled():
        return ""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        return ""
    marker = _rc.read_marker(cwd)
    if not isinstance(marker, dict) or marker.get("status") != "active":
        return ""
    skill = marker.get("skill") or "architect-team-pipeline"
    slug = marker.get("slug") or marker.get("run_id") or "(unnamed)"
    phase = marker.get("phase") or "(unknown)"
    started = marker.get("started_at") or "(unknown)"
    source = str(payload.get("source") or "")
    hooks_dir = Path(__file__).resolve().parent
    if _rc.marker_is_stale(marker):
        # An abandoned run's marker no longer gates anything (the sticky arm
        # and Stop guard stand down on staleness) — inform, don't direct.
        return (
            "[CT6 run-continuity] A STALE active-run marker was found in this "
            f"workspace: slug={slug} phase={phase} skill={skill} "
            f"last-activity={marker.get('updated_at') or '(unknown)'}. It no "
            "longer gates any tools. If the run should RESUME, invoke "
            f"Skill(skill=\"{skill}\"); if it was abandoned, clear the marker: "
            f"python \"{hooks_dir / 'run_continuity.py'}\" --stand-down "
            "\"<why>\" (or --mark-complete if it actually finished)."
        )
    compact_note = (
        "Your context was just COMPACTED - the pipeline playbook text is no "
        "longer in context. "
    ) if source == "compact" else ""
    return (
        "[CT6 run-continuity] An architect-team run is ACTIVE and incomplete "
        f"in this workspace: slug={slug} phase={phase} skill={skill} "
        f"started={started}.\n"
        f"{compact_note}"
        f"REQUIRED: invoke Skill(skill=\"{skill}\") as your FIRST action - "
        "before any build/dispatch tool - to load the pipeline playbook, then "
        "resume the run from its recorded state and drive it to completion "
        "(the PreToolUse run-continuity gate enforces this; the Stop-hook "
        "continuation guard keeps the run working until it is marked "
        "complete). Do NOT solve the run's work by hand and do NOT ask the "
        "user whether to continue.\n"
        "Exceptions: if the USER explicitly directs work outside the "
        "pipeline, record it via\n"
        f"    python \"{hooks_dir / 'run_continuity.py'}\" --stand-down \"<the user's words>\"\n"
        "If this session is a CT6 pipeline TEAMMATE (your first message is a "
        "spawn brief / carries the CT6-TEAMMATE token), IGNORE this notice "
        "and execute your brief."
    )


def main() -> int:
    try:
        raw = _read_stdin_utf8() if not sys.stdin.isatty() else ""
    except (OSError, ValueError):
        raw = ""
    payload: dict = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            pass
    try:
        directive = build_directive(payload)
    except Exception:  # fail open — never wedge a session start on a bug here
        return 0
    if directive:
        print(directive)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
