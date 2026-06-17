#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PreCompact closeout hook — the CO-1 trigger.

Fires BEFORE context is compacted (the `PreCompact` hook event). It runs the
deterministic closeout engine (`hooks/closeout_check.py`) against the current
working tree and, when the documentation-currency inventory appears STALE
relative to what the session changed, surfaces a reminder telling the agent to
run the closeout review (the `closeout` skill / `/architect-team:closeout`)
BEFORE compacting — review the changes against the requirement, confirm every
affected doc, and update any that are stale (CO-2/CO-3).

This is a DOUBLE-CHECK, not a gate. It NEVER blocks compaction (it always exits
0): a hook is deterministic code and cannot author doc prose; the actual review +
update is the agent's job, prompted by this reminder. The requirement (CO-3) is
that closeout "suggests continuing the update and then performs the update
itself" — agent behaviour, which this reminder initiates.

Delivery: the reminder is emitted on BOTH channels a Claude Code hook can use —
`systemMessage` (user-visible) and `hookSpecificOutput.additionalContext`
(agent-visible) — so whichever the installed harness honours, the reminder lands.

SAFETY (deliberately conservative — this fires at a sensitive moment):
- ALWAYS exits 0 — never blocks or delays compaction.
- Silent when docs appear current (no noise) or when there is nothing to assess.
- Fails open on ANY error (unreadable payload, git failure, import failure):
  prints nothing and exits 0.

Registered in `hooks/hooks.json` as `PreCompact[*]`. Payload read from stdin.
Stdlib-only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Dual-form import of the engine: package shape (repo root on sys.path ->
# ``hooks.closeout_check``) then bare-module shape (the hook-runner puts
# ``hooks/`` on sys.path). If neither resolves, fail open.
try:  # pragma: no cover - exercised both ways across environments
    from hooks import closeout_check  # type: ignore
except Exception:  # pragma: no cover
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import closeout_check  # type: ignore
    except Exception:
        closeout_check = None  # type: ignore


def _resolve_repo_root(payload: dict[str, Any]) -> str:
    """Best-effort repo root: the payload cwd, else the process cwd.

    When the payload omits cwd we prefer the actual current working directory (the
    session's project) over the plugin's own install dir, so the closeout never
    assesses the plugin checkout by mistake."""
    cwd = payload.get("cwd") or payload.get("workspace") or payload.get("project_dir")
    if isinstance(cwd, str) and cwd.strip():
        return cwd
    try:
        return os.getcwd()
    except OSError:
        return str(Path(__file__).resolve().parents[1])


def _build_reminder(assessment: dict[str, Any], trigger: str) -> str:
    """Render the human/agent-facing closeout reminder from an assessment."""
    lines = [
        "⚑ CLOSEOUT CHECK (before compaction) — documentation may be out of date.",
        "",
    ]
    for sig in assessment.get("signals", []):
        lines.append(f"  • [{sig.get('severity')}] {sig.get('signal')}: {sig.get('detail')}")
    lines.append("")
    lines.append(
        "Before you compact, run the closeout review — the `closeout` skill (or "
        "`/architect-team:closeout`): review what changed this session against the "
        "requirement, confirm every affected doc in the currency inventory "
        "(README / CHANGELOG / CLAUDE.md / docs/*_MAP.md), and UPDATE any that are "
        "stale. Do the update now rather than deferring it past the compaction."
    )
    if trigger == "auto":
        lines.append(
            "(This compaction was auto-triggered; the closeout update is still "
            "expected — perform it, then let compaction proceed.)"
        )
    return "\n".join(lines)


def main() -> int:
    # Read the hook payload (fail open on anything unexpected).
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    if closeout_check is None:
        return 0

    try:
        repo_root = _resolve_repo_root(payload)
        collected = closeout_check.collect_changed_files(repo_root)
        if not collected.get("changed"):
            return 0  # nothing changed this session -> nothing to remind about
        assessment = closeout_check.assess_closeout(
            collected["changed"], added_files=collected.get("added")
        )
    except Exception:
        return 0  # fail open

    if assessment.get("docs_appear_current", True):
        return 0  # silent when docs look current

    try:
        reminder = _build_reminder(assessment, str(payload.get("trigger", "")))
        out = {
            "systemMessage": reminder,
            "hookSpecificOutput": {
                "hookEventName": "PreCompact",
                "additionalContext": reminder,
            },
        }
        sys.stdout.write(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
