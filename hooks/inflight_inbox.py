"""In-flight clarification inbox — v2.19.0.

Stdlib-only module. A per-run, append-only JSONL inbox at
`<workspace>/.architect-team/inbox/<run-id>.jsonl` where mid-run clarifications
from the user land. Read by the orchestrator at every phase boundary; verified
at Phase 8 by `hooks.vao_tools.verify_inflight_clarifications_processed`.

Each line is one JSON object with the v2.19.0 message schema:

    {
      "message_id": str,                 # uuid
      "text": str,                       # the user's verbatim message
      "injected_at": str,                # ISO 8601 UTC
      "injected_via": str,               # "slash-command" | "natural-language-mid-run" | "external-webhook"
      "source_session": str | None,      # claude-code session id (if known)
      "processed_at": str | None,        # ISO 8601 UTC, set when orchestrator processes
      "classification": str | None,      # "scope-amendment" | "clarification" | "out-of-scope" | None
      "action_taken": str | None,        # one-line description of what changed
    }

Use:

    from hooks.inflight_inbox import (
        append_clarification,
        mark_processed,
        read_inbox,
        unprocessed_messages,
        current_run_id,
    )

See `skills/common-pipeline-conventions/SKILL.md`
`## In-flight clarification injection mechanism (v2.19.0)` for the canonical
home.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INBOX_RELATIVE_DIR = ".architect-team/inbox"
INTAKE_STATE_RELATIVE_PATH = ".architect-team/intake-state.json"

INJECTION_VIAS = ("slash-command", "natural-language-mid-run", "external-webhook")
CLASSIFICATIONS = ("scope-amendment", "clarification", "out-of-scope")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _inbox_path(workspace: Path, run_id: str) -> Path:
    return Path(workspace) / INBOX_RELATIVE_DIR / f"{run_id}.jsonl"


def current_run_id(workspace: Path) -> str | None:
    """Read the active run-id from `<workspace>/.architect-team/intake-state.json`.
    Returns None when no run is in flight (file missing, malformed, or has no
    `run_id` key)."""
    path = Path(workspace) / INTAKE_STATE_RELATIVE_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return None
    return run_id


# ---------------------------------------------------------------------------
# Read / append / mark-processed
# ---------------------------------------------------------------------------


def read_inbox(workspace: Path, run_id: str) -> list[dict[str, Any]]:
    """Read every line of the per-run inbox JSONL. Returns an empty list when
    the file does not exist. Malformed lines are silently skipped."""
    path = _inbox_path(workspace, run_id)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            out.append(entry)
    return out


def append_clarification(
    workspace: Path,
    run_id: str,
    text: str,
    *,
    injected_via: str = "slash-command",
    source_session: str | None = None,
) -> dict[str, Any]:
    """Append a new clarification to the per-run inbox. Returns the created
    message dict. Creates the inbox directory + file if missing."""
    if injected_via not in INJECTION_VIAS:
        raise ValueError(f"injected_via must be one of {INJECTION_VIAS}, got {injected_via!r}")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    path = _inbox_path(workspace, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    msg = {
        "message_id": str(uuid.uuid4()),
        "text": text,
        "injected_at": _utc_now_iso(),
        "injected_via": injected_via,
        "source_session": source_session,
        "processed_at": None,
        "classification": None,
        "action_taken": None,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(msg, sort_keys=True) + "\n")
    return msg


def mark_processed(
    workspace: Path,
    run_id: str,
    message_id: str,
    *,
    classification: str,
    action_taken: str,
) -> dict[str, Any] | None:
    """Mark a message as processed. Rewrites the JSONL file in place (no
    deletions/reorderings — same line index, just updated fields). Returns
    the updated message dict, or None if not found."""
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"classification must be one of {CLASSIFICATIONS}, got {classification!r}")
    if not isinstance(action_taken, str) or not action_taken.strip():
        raise ValueError("action_taken must be a non-empty string")

    path = _inbox_path(workspace, run_id)
    if not path.exists():
        return None

    lines = path.read_text(encoding="utf-8").splitlines()
    out_lines: list[str] = []
    updated: dict[str, Any] | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue
        if isinstance(entry, dict) and entry.get("message_id") == message_id:
            entry["processed_at"] = _utc_now_iso()
            entry["classification"] = classification
            entry["action_taken"] = action_taken
            out_lines.append(json.dumps(entry, sort_keys=True))
            updated = entry
        else:
            out_lines.append(line)

    path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    return updated


def unprocessed_messages(workspace: Path, run_id: str) -> list[dict[str, Any]]:
    """Return every inbox message whose `processed_at` is null."""
    return [m for m in read_inbox(workspace, run_id) if m.get("processed_at") is None]


def inbox_path_for(workspace: Path, run_id: str) -> Path:
    """Public accessor for the inbox path — useful for tests + the slash command."""
    return _inbox_path(workspace, run_id)
