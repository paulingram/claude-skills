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

import contextlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# (A4 review-remediation) `safe_id` rejects path-traversal vectors ('/', '\\',
# leading '.', exact '..') in an identifier used as a filename component. The
# `run_id` is interpolated into the inbox filename, so it MUST be validated the
# same way the sibling hooks (review-gate-task.py / teammate-idle-check.py)
# validate their task IDs. Dual-form import: package shape (repo root on
# sys.path) and bare-module shape (the hook-runner puts hooks/ on sys.path).
try:  # package shape
    from hooks.review_evidence_schema import safe_id
except ImportError:  # bare-module shape
    from review_evidence_schema import safe_id

INBOX_RELATIVE_DIR = ".architect-team/inbox"
INTAKE_STATE_RELATIVE_PATH = ".architect-team/intake-state.json"

INJECTION_VIAS = ("slash-command", "natural-language-mid-run", "external-webhook")
CLASSIFICATIONS = ("scope-amendment", "clarification", "out-of-scope")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextlib.contextmanager
def _inbox_lock(path: Path, *, timeout: float = 5.0) -> Iterator[None]:
    """A cross-process advisory lock guarding one inbox file.

    (A4 review-remediation) The inbox's headline use case is a separate-terminal
    ``/architect-team:inject`` appending WHILE the orchestrator's
    ``mark_processed`` rewrites the file. ``os.replace`` makes the rewrite's
    swap atomic (no torn file, no truncation-on-crash) but does NOT by itself
    prevent a LOST UPDATE: an append that lands between ``mark_processed``'s
    read and its replace would be clobbered by the stale rewrite. Serializing
    append vs. rewrite through this lock closes that window — exactly the
    "can destroy a concurrently appended message" failure A4 names.

    Implemented with ``os.open(O_CREAT | O_EXCL)`` on a sidecar ``<file>.lock``
    — atomic + cross-process on BOTH POSIX and Windows, no fcntl/msvcrt needed
    and no third-party dependency (stdlib-only per the plugin's NF contract).
    Spins with a bounded backoff until the lock is acquired or ``timeout``
    elapses; on timeout it proceeds WITHOUT the lock rather than dead-locking a
    hook (best-effort: a stale lock from a crashed process must never wedge the
    inbox forever). A stale lock older than ``timeout`` is reclaimed.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd: int | None = None
    delay = 0.002
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            # Reclaim a stale lock left by a crashed holder.
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > timeout:
                    with contextlib.suppress(OSError):
                        os.unlink(lock_path)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                # Give up waiting — proceed lock-free rather than wedge a hook.
                break
            time.sleep(delay)
            delay = min(delay * 1.5, 0.05)
    try:
        yield
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
            with contextlib.suppress(OSError):
                os.unlink(lock_path)


def _atomic_replace(src: Path, dst: Path) -> None:
    """`os.replace(src, dst)` with a bounded retry for the transient Windows
    sharing violation.

    (A4 review-remediation) `os.replace` is atomic on POSIX and Windows. On
    Windows it can raise ``PermissionError`` when the destination is momentarily
    held open by another handle; a brief bounded retry rides out the overlap
    while preserving atomicity (the swap is all-or-nothing whenever it succeeds,
    and the original file is never truncated). POSIX never hits the retry.
    """
    delay = 0.005
    for _ in range(20):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            time.sleep(delay)
            delay = min(delay * 1.5, 0.05)
    os.replace(src, dst)  # final attempt — let a persistent failure raise


def _append_line(path: Path, line: str) -> None:
    """Append one line to `path` under the inbox lock, riding out the transient
    Windows sharing violation on open."""
    with _inbox_lock(path):
        delay = 0.005
        last_exc: PermissionError | None = None
        for _ in range(20):
            try:
                with path.open("a", encoding="utf-8") as f:
                    f.write(line)
                return
            except PermissionError as exc:  # destination mid-rename on Windows
                last_exc = exc
                time.sleep(delay)
                delay = min(delay * 1.5, 0.05)
        if last_exc is not None:
            raise last_exc


def _inbox_path(workspace: Path, run_id: str) -> Path:
    """Resolve the per-run inbox JSONL path.

    (A4 review-remediation) `run_id` is validated through `safe_id` BEFORE it is
    interpolated into the filename so a crafted id (``../../etc/passwd``,
    ``a/b``, ``..``) cannot escape the inbox directory. A rejected id raises
    ValueError; read-path callers (`read_inbox` / `unprocessed_messages`) and
    `mark_processed` catch it and degrade to the existing not-found contract
    (empty list / None), while the write path (`append_clarification`) lets it
    surface as the input-validation error it is.
    """
    if safe_id(str(run_id)) is None:
        raise ValueError(
            f"run_id {run_id!r} is not a safe path component "
            f"(rejected by safe_id: contains '/', '\\', a leading '.', or is '..')"
        )
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
    the file does not exist. Malformed lines are silently skipped.

    (A4) A run_id that fails `safe_id` is treated as "no inbox" — empty list —
    rather than raising, matching the not-found contract."""
    try:
        path = _inbox_path(workspace, run_id)
    except ValueError:
        return []
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
    _append_line(path, json.dumps(msg, sort_keys=True) + "\n")
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

    # (A4) A run_id that fails safe_id degrades to not-found (None), mirroring
    # the read-path contract — a traversal attempt never reaches the filesystem.
    try:
        path = _inbox_path(workspace, run_id)
    except ValueError:
        return None
    if not path.exists():
        return None

    # (A4) Hold the inbox lock across the WHOLE read-modify-write so a
    # concurrent /architect-team:inject append cannot land between the read and
    # the replace and get clobbered (the lost-update window). The append path
    # takes the same lock, so the two serialize.
    with _inbox_lock(path):
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

        # (A4) Atomic rewrite — temp file + os.replace (mirror
        # run_metrics.py:184-186). os.replace is atomic on POSIX and Windows, so
        # the swap is all-or-nothing: a reader sees the OLD or NEW file, never a
        # truncated one, and a crash mid-write leaves the original inbox intact.
        # The prior `path.write_text(...)` was the non-atomic form being replaced.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            "\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8"
        )
        _atomic_replace(tmp, path)
    return updated


def unprocessed_messages(workspace: Path, run_id: str) -> list[dict[str, Any]]:
    """Return every inbox message whose `processed_at` is null."""
    return [m for m in read_inbox(workspace, run_id) if m.get("processed_at") is None]


def inbox_path_for(workspace: Path, run_id: str) -> Path:
    """Public accessor for the inbox path — useful for tests + the slash command."""
    return _inbox_path(workspace, run_id)
