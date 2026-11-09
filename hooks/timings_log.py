#!/usr/bin/env python3
"""Timing log -- the per-interval duration ledger behind the project homepage.

Stdlib-only. Library AND hook entry: imported by `scripts/notify/notify.py`
(phase / run intervals) and `scripts/homepage/` (stats + estimates), and run as
a script by the harness on `SubagentStart` / `SubagentStop` / `TaskCreated` /
`TaskCompleted` / `Stop` (agent, task and run intervals).

The ledger: ``<workspace>/.architect-team/run-history/timings.jsonl`` --
append-only, one JSON object per line::

    {"schema": "timing/v1", "run_id", "lane", "phase", "task_id", "agent",
     "model", "dispatch_mode", "kind": "agent" | "task" | "phase" | "run",
     "started_at", "ended_at", "duration_s", "outcome", "size_bucket"}

Open (not yet closed) intervals live beside it in ``timings-open.json`` keyed
by ``"<kind>:<key>"``; closing one pops it and appends the closed line.

Contract (never block, never lie):

  * The hook entry exits 0 on EVERY path. An exception is swallowed silently
    (reported on stderr only under ``CT6_TIMINGS_DEBUG=1``). A timing record
    is observability, never a gate.
  * ``CT6_TIMINGS_DISABLED=1`` is the kill switch -- nothing is read or written.
  * Agent / task intervals are recorded only while a CT6 run is ACTIVE in the
    workspace (the `hooks/run_continuity.py` marker), so an ad-hoc Agent
    dispatch in an unrelated project never lands in the estimate basis.
  * Every line is enriched (best effort, read-only) with ``run_id`` / ``lane``
    / ``phase`` / ``dispatch_mode`` / ``model`` / ``size_bucket`` from
    ``intake-state.json`` and the active-run marker when the caller did not
    supply them.
  * ``Stop`` closes the run interval ONLY once the marker is no longer active
    (the completion lock holds a run open across many Stops); every other
    open interval is then closed as ``outcome: "unknown"`` -- an unknown is
    recorded as unknown, never guessed.
  * ``CT6_TIMINGS_USER_MIRROR=1`` additionally appends every closed line to
    ``~/.architect-team/timings.jsonl`` (``CT6_TIMINGS_USER_MIRROR_PATH``
    overrides the location) so estimates can draw on every project.

Workspace resolution for the hook entry: the payload's ``cwd`` (else the
process cwd) -> its git toplevel -> that directory itself.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# Dual-form import per house convention: package shape (repo root on sys.path)
# then bare-module shape (hooks/ on sys.path -- the hook runner, or this file
# loaded by path, in which case its own directory is put on sys.path first).
try:  # package shape
    from hooks.shared_util import _utc_now_iso, read_jsonl
    from hooks.run_metrics import _RUN_START_KEYS, _read_intake_state
    from hooks.run_continuity import read_marker
except ImportError:  # bare-module shape
    _HERE = str(Path(__file__).resolve().parent)
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from shared_util import _utc_now_iso, read_jsonl
    from run_metrics import _RUN_START_KEYS, _read_intake_state
    from run_continuity import read_marker

SCHEMA = "timing/v1"
TIMINGS_RELATIVE_PATH = ".architect-team/run-history/timings.jsonl"
OPEN_RELATIVE_PATH = ".architect-team/run-history/timings-open.json"
LOCK_RELATIVE_PATH = ".architect-team/run-history/timings-open.lock"

KINDS = ("agent", "task", "phase", "run")
RECORD_FIELDS = (
    "schema", "run_id", "lane", "phase", "task_id", "agent", "model",
    "dispatch_mode", "kind", "started_at", "ended_at", "duration_s", "outcome",
    "size_bucket",
)
#: The context fields filled from intake-state / the marker when absent.
CONTEXT_FIELDS = ("run_id", "lane", "phase", "dispatch_mode", "model", "size_bucket")

OUTCOME_OK = "ok"
OUTCOME_UNKNOWN = "unknown"
#: A heartbeat line is a liveness point, not an interval; stats exclude it.
OUTCOME_HEARTBEAT = "heartbeat"

DISABLE_ENV = "CT6_TIMINGS_DISABLED"
DEBUG_ENV = "CT6_TIMINGS_DEBUG"
USER_MIRROR_ENV = "CT6_TIMINGS_USER_MIRROR"
USER_MIRROR_PATH_ENV = "CT6_TIMINGS_USER_MIRROR_PATH"
STALE_HOURS_ENV = "CT6_TIMINGS_STALE_HOURS"
DEFAULT_STALE_HOURS = 24.0

HOOK_EVENTS = ("SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted", "Stop")

#: Run-driving skill -> the lane label a user would say.
SKILL_TO_LANE = {
    "architect-team-pipeline": "architect-team",
    "bug-fix-pipeline": "bug-fix",
    "mini-architect-team-pipeline": "mini",
    "ux-test-builder": "ux-test",
    "data-eng-pipeline": "data-eng",
    "playwright-suite-builder": "playwright-suite",
    "diagnostic-research-team": "diagnostic-research",
}

_LOCK_WAIT_SECONDS = 2.0
_LOCK_POLL_SECONDS = 0.02


# --------------------------------------------------------------------------- #
# env + paths
# --------------------------------------------------------------------------- #

def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def disabled() -> bool:
    """True when the kill switch is set."""
    return _env_truthy(DISABLE_ENV)


def debug_enabled() -> bool:
    return _env_truthy(DEBUG_ENV)


def user_mirror_enabled() -> bool:
    return _env_truthy(USER_MIRROR_ENV)


def user_mirror_path() -> Path:
    """``~/.architect-team/timings.jsonl`` unless ``CT6_TIMINGS_USER_MIRROR_PATH``
    names another file."""
    override = os.environ.get(USER_MIRROR_PATH_ENV, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".architect-team" / "timings.jsonl"


def timings_path(workspace: Path | str) -> Path:
    return Path(workspace) / TIMINGS_RELATIVE_PATH


def open_store_path(workspace: Path | str) -> Path:
    return Path(workspace) / OPEN_RELATIVE_PATH


def stale_hours() -> float:
    raw = os.environ.get(STALE_HOURS_ENV, "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_STALE_HOURS


def _debug(message: str) -> None:
    if debug_enabled():
        print(f"timings_log: {message}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# time helpers
# --------------------------------------------------------------------------- #

def parse_iso(text: Any) -> datetime | None:
    """ISO-8601 -> aware UTC datetime, or None. Accepts a trailing ``Z``; a
    naive timestamp is read as UTC."""
    if not isinstance(text, str) or not text.strip():
        return None
    s = text.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def duration_seconds(started_at: Any, ended_at: Any) -> float | None:
    """``ended - started`` in seconds (3 decimals), clamped at 0; None when
    either stamp is missing or unparseable."""
    start = parse_iso(started_at)
    end = parse_iso(ended_at)
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds()
    return round(delta if delta >= 0 else 0.0, 3)


def _now_iso(now: str | None) -> str:
    return now if isinstance(now, str) and now.strip() else _utc_now_iso()


# --------------------------------------------------------------------------- #
# context enrichment (read-only, best effort)
# --------------------------------------------------------------------------- #

def _first_str(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def context_from_workspace(workspace: Path | str) -> dict[str, Any]:
    """The run context the ledger enriches every line with: ``run_id`` /
    ``lane`` / ``phase`` / ``dispatch_mode`` / ``model`` / ``size_bucket`` plus
    ``run_started_at``, from ``intake-state.json`` and the active-run marker.
    Missing fields are None. Never raises."""
    ctx: dict[str, Any] = {k: None for k in CONTEXT_FIELDS}
    ctx["run_started_at"] = None
    ctx["marker_status"] = None
    try:
        intake = _read_intake_state(Path(workspace))
    except Exception:  # pragma: no cover - the helper never raises; belt + braces
        intake = {}
    try:
        marker = read_marker(workspace) or {}
    except Exception:  # pragma: no cover
        marker = {}
    if not isinstance(marker, dict):
        marker = {}

    ctx["run_id"] = (_first_str(intake, "run_id", "runId", "slug")
                     or _first_str(marker, "run_id", "slug"))
    ctx["phase"] = _first_str(intake, "phase") or _first_str(marker, "phase")
    ctx["dispatch_mode"] = _first_str(intake, "dispatch_mode")
    ctx["model"] = _first_str(intake, "model", "default_model", "agent_model")
    ctx["size_bucket"] = _first_str(intake, "size_bucket", "size")
    lane = _first_str(intake, "lane", "pipeline")
    if lane is None:
        skill = _first_str(intake, "skill") or _first_str(marker, "skill")
        if skill:
            lane = SKILL_TO_LANE.get(skill, skill)
    ctx["lane"] = lane
    for key in _RUN_START_KEYS:
        value = intake.get(key)
        if isinstance(value, str) and parse_iso(value) is not None:
            ctx["run_started_at"] = value
            break
    if ctx["run_started_at"] is None:
        value = marker.get("started_at")
        if isinstance(value, str) and parse_iso(value) is not None:
            ctx["run_started_at"] = value
    ctx["marker_status"] = marker.get("status") if isinstance(marker.get("status"), str) else None
    return ctx


def workspace_engaged(workspace: Path | str) -> bool:
    """True iff a CT6 run is ACTIVE in ``workspace`` (the run-continuity
    marker says ``status: active``)."""
    try:
        marker = read_marker(workspace)
    except Exception:  # pragma: no cover
        return False
    return isinstance(marker, dict) and marker.get("status") == "active"


def _enrich(fields: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    out = dict(fields)
    for key in CONTEXT_FIELDS:
        if out.get(key) is None and ctx.get(key) is not None:
            out[key] = ctx[key]
    return out


# --------------------------------------------------------------------------- #
# records
# --------------------------------------------------------------------------- #

def make_record(kind: str, started_at: Any, ended_at: Any, outcome: str = OUTCOME_OK,
                **fields: Any) -> dict[str, Any]:
    """A closed timing line with every schema field present (None when unknown).
    Unknown ``fields`` are dropped -- the line schema is closed on purpose."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}; got {kind!r}")
    rec: dict[str, Any] = {name: None for name in RECORD_FIELDS}
    rec["schema"] = SCHEMA
    rec["kind"] = kind
    rec["started_at"] = started_at if isinstance(started_at, str) else None
    rec["ended_at"] = ended_at if isinstance(ended_at, str) else None
    rec["duration_s"] = duration_seconds(rec["started_at"], rec["ended_at"])
    rec["outcome"] = str(outcome) if outcome else OUTCOME_UNKNOWN
    for name in ("run_id", "lane", "phase", "task_id", "agent", "model",
                 "dispatch_mode", "size_bucket"):
        value = fields.get(name)
        if value is not None:
            rec[name] = value if isinstance(value, (str, int, float)) else str(value)
    return rec


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def append_line(workspace: Path | str, record: dict[str, Any]) -> Path:
    """Append one closed line to the workspace ledger (and the user mirror
    when enabled). Returns the ledger path."""
    path = timings_path(workspace)
    _append_jsonl(path, record)
    if user_mirror_enabled():
        try:
            _append_jsonl(user_mirror_path(), record)
        except OSError as exc:  # the mirror is a convenience, never a failure
            _debug(f"user mirror append failed: {exc}")
    return path


def read_all(workspace: Path | str) -> list[dict[str, Any]]:
    """Every closed line (dicts only; malformed lines skipped)."""
    return [r for r in read_jsonl(timings_path(workspace)) if isinstance(r.get("kind"), str)]


# --------------------------------------------------------------------------- #
# the open-interval store
# --------------------------------------------------------------------------- #

def open_key(kind: str, key: Any) -> str:
    return f"{kind}:{key}"


@contextlib.contextmanager
def _store_lock(workspace: Path | str) -> Iterator[None]:
    """Best-effort exclusive lock around a read-modify-write of the open
    store (parallel SubagentStart hooks fire concurrently). Bounded wait; on
    timeout we proceed anyway -- a lost open record costs one interval, a
    hung hook costs the session."""
    lock = Path(workspace) / LOCK_RELATIVE_PATH
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                break
            time.sleep(_LOCK_POLL_SECONDS)
        except OSError:
            break
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                lock.unlink()
            except OSError:
                pass


def read_open(workspace: Path | str) -> dict[str, dict[str, Any]]:
    """The open-interval store (``{"<kind>:<key>": {...}}``); ``{}`` when
    missing or malformed."""
    path = open_store_path(workspace)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _write_open(workspace: Path | str, data: dict[str, dict[str, Any]]) -> None:
    path = open_store_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def open_interval(workspace: Path | str, kind: str, key: Any, **fields: Any) -> dict[str, Any]:
    """Record that an interval of ``kind`` keyed by ``key`` started.

    ``fields`` may carry any schema field (``started_at`` included; default
    now). Context fields absent from ``fields`` are filled from the workspace.
    Re-opening a key that is already open keeps the ORIGINAL ``started_at``
    (a duplicate start event is not a restart). Returns the open record."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}; got {kind!r}")
    if key is None or not str(key).strip():
        raise ValueError("key must be a non-empty identifier")
    ctx = context_from_workspace(workspace)
    enriched = _enrich(fields, ctx)
    started = enriched.pop("started_at", None)
    if not isinstance(started, str) or parse_iso(started) is None:
        started = _utc_now_iso()
    with _store_lock(workspace):
        store = read_open(workspace)
        okey = open_key(kind, key)
        existing = store.get(okey)
        rec: dict[str, Any] = {"kind": kind, "key": str(key), "started_at": started}
        if isinstance(existing, dict) and parse_iso(existing.get("started_at")) is not None:
            rec["started_at"] = existing["started_at"]
            for name, value in existing.items():
                if name not in rec and value is not None:
                    rec[name] = value
        for name in ("run_id", "lane", "phase", "task_id", "agent", "model",
                     "dispatch_mode", "size_bucket"):
            value = enriched.get(name)
            if value is not None:
                rec[name] = value
        store[okey] = rec
        _write_open(workspace, store)
    return rec


def close_interval(workspace: Path | str, kind: str, key: Any, outcome: str = OUTCOME_OK,
                   **fields: Any) -> dict[str, Any] | None:
    """Pop the open interval and append its closed line. Returns the closed
    record, or None when nothing was open under that key (nothing is
    fabricated for an interval whose start was never seen)."""
    ended = fields.pop("ended_at", None)
    ended = _now_iso(ended if isinstance(ended, str) else None)
    with _store_lock(workspace):
        store = read_open(workspace)
        rec = store.pop(open_key(kind, key), None)
        if rec is not None:
            _write_open(workspace, store)
    if rec is None:
        return None
    merged = {k: v for k, v in rec.items() if k not in ("kind", "key", "started_at")}
    for name, value in fields.items():
        if value is not None:
            merged[name] = value
    merged = _enrich(merged, context_from_workspace(workspace))
    closed = make_record(kind, rec.get("started_at"), ended, outcome, **merged)
    append_line(workspace, closed)
    return closed


def record(workspace: Path | str, kind: str, started_at: Any = None, ended_at: Any = None,
           outcome: str = OUTCOME_OK, **fields: Any) -> dict[str, Any]:
    """Append an already-known interval (no open store involved)."""
    ended = ended_at if isinstance(ended_at, str) else _utc_now_iso()
    enriched = _enrich(fields, context_from_workspace(workspace))
    rec = make_record(kind, started_at, ended, outcome, **enriched)
    append_line(workspace, rec)
    return rec


def close_stale(workspace: Path | str, max_age_hours: float | None = None,
                now: str | None = None) -> list[dict[str, Any]]:
    """Close every open interval older than ``max_age_hours`` as
    ``outcome: "unknown"``. Returns the closed records."""
    limit = stale_hours() if max_age_hours is None else float(max_age_hours)
    now_dt = parse_iso(_now_iso(now)) or datetime.now(timezone.utc)
    closed: list[dict[str, Any]] = []
    for okey, rec in list(read_open(workspace).items()):
        started = parse_iso(rec.get("started_at"))
        age_h = (now_dt - started).total_seconds() / 3600.0 if started else float("inf")
        if age_h > limit:
            kind, _, key = okey.partition(":")
            done = close_interval(workspace, kind, key, OUTCOME_UNKNOWN, ended_at=_now_iso(now))
            if done:
                closed.append(done)
    return closed


def close_all_open(workspace: Path | str, outcome: str = OUTCOME_UNKNOWN,
                   now: str | None = None, kinds: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Close every open interval (optionally only of ``kinds``) with ``outcome``."""
    closed: list[dict[str, Any]] = []
    for okey in list(read_open(workspace).keys()):
        kind, _, key = okey.partition(":")
        if kinds is not None and kind not in kinds:
            continue
        done = close_interval(workspace, kind, key, outcome, ended_at=_now_iso(now))
        if done:
            closed.append(done)
    return closed


def _run_already_recorded(workspace: Path | str, run_id: str) -> bool:
    for rec in read_all(workspace):
        if (rec.get("kind") == "run" and rec.get("run_id") == run_id
                and rec.get("outcome") != OUTCOME_HEARTBEAT):
            return True
    return False


def close_run(workspace: Path | str, outcome: str = OUTCOME_OK,
              now: str | None = None) -> list[dict[str, Any]]:
    """Close the run interval(s). Open ``run`` intervals are closed with
    ``outcome``; when none is open, ONE run line is recorded from
    ``intake-state.json``'s ``started_at`` (via the `run_metrics` helpers) --
    unless that run_id already has a closed run line, so repeated Stops after
    completion cannot duplicate it. Returns the records written."""
    ended = _now_iso(now)
    closed = close_all_open(workspace, outcome, now=ended, kinds=("run",))
    if closed:
        return closed
    ctx = context_from_workspace(workspace)
    run_id = ctx.get("run_id")
    started = ctx.get("run_started_at")
    if not run_id or not started or _run_already_recorded(workspace, run_id):
        return []
    rec = make_record("run", started, ended, outcome, **{k: ctx.get(k) for k in CONTEXT_FIELDS})
    append_line(workspace, rec)
    return [rec]


# --------------------------------------------------------------------------- #
# hook entry
# --------------------------------------------------------------------------- #

def _read_stdin_utf8() -> str:
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


def _dig(payload: dict[str, Any], dotted: str) -> Any:
    node: Any = payload
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _first_present(payload: dict[str, Any], *paths: str) -> str | None:
    for path in paths:
        value = _dig(payload, path)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
            return str(value).strip()
    return None


def agent_key(payload: dict[str, Any]) -> str | None:
    """The identifier an agent interval is keyed by -- whichever of the
    harness's id / name / type fields is present (inspected defensively)."""
    return _first_present(
        payload, "agent_id", "agentId", "subagent_id", "subagent.id", "agent_name",
        "subagent.name", "subagent_name", "teammate.name", "agent_type",
        "subagent_type", "tool_input.subagent_type", "task_id", "taskId",
    )


def agent_label(payload: dict[str, Any]) -> str | None:
    """The agent's type / name for the ``agent`` field."""
    return _first_present(
        payload, "agent_type", "subagent_type", "tool_input.subagent_type", "agent_name",
        "subagent.name", "subagent_name", "teammate.name", "agent_id", "agentId",
    )


def task_key(payload: dict[str, Any]) -> str | None:
    return _first_present(payload, "task.id", "task.taskId", "task_id", "taskId",
                          "tool_input.taskId", "tool_input.task_id")


def resolve_workspace(payload: dict[str, Any], cwd: Path | None = None) -> Path:
    """Payload ``cwd`` (else the process cwd) -> its git toplevel -> itself."""
    start: Path | None = None
    raw = payload.get("cwd") if isinstance(payload, dict) else None
    if isinstance(raw, str) and raw.strip():
        candidate = Path(raw.strip())
        if candidate.is_dir():
            start = candidate
    if start is None:
        start = Path(cwd) if cwd is not None else Path.cwd()
    try:
        completed = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if completed.returncode == 0:
            top = completed.stdout.strip()
            if top and Path(top).is_dir():
                return Path(top)
    except (OSError, subprocess.SubprocessError):
        pass
    return start


def handle_event(payload: dict[str, Any], workspace: Path | str,
                 now: str | None = None) -> dict[str, Any]:
    """Map one hook payload onto the ledger. Returns a summary
    ``{"event", "action", "records": [...]}``; raises nothing the entry does
    not catch (library callers see the exceptions)."""
    event = payload.get("hook_event_name") if isinstance(payload, dict) else None
    summary: dict[str, Any] = {"event": event, "action": "ignored", "records": []}
    if event not in HOOK_EVENTS:
        return summary
    when = _now_iso(now)

    if event == "Stop":
        ctx = context_from_workspace(workspace)
        if ctx.get("marker_status") == "active":
            # The run is still open (the completion lock holds it); only age
            # out intervals that can no longer be live.
            summary["action"] = "run-active"
            summary["records"] = close_stale(workspace, now=when)
            return summary
        status = ctx.get("marker_status")
        outcome = {"complete": OUTCOME_OK, "stood-down": "stood-down"}.get(status or "", OUTCOME_UNKNOWN)
        records = close_run(workspace, outcome, now=when)
        records += close_all_open(workspace, OUTCOME_UNKNOWN, now=when)
        summary["action"] = "run-closed" if records else "nothing-open"
        summary["records"] = records
        return summary

    if not workspace_engaged(workspace):
        summary["action"] = "not-engaged"
        return summary

    if event == "SubagentStart":
        key = agent_key(payload)
        if not key:
            summary["action"] = "no-key"
            return summary
        rec = open_interval(workspace, "agent", key, started_at=when,
                            agent=agent_label(payload),
                            task_id=_first_present(payload, "task_id", "taskId", "task.id"),
                            model=_first_present(payload, "model", "agent_model"))
        summary["action"] = "opened"
        summary["records"] = [rec]
        return summary

    if event == "SubagentStop":
        key = agent_key(payload)
        if not key:
            summary["action"] = "no-key"
            return summary
        outcome = _first_present(payload, "outcome", "status") or OUTCOME_OK
        rec = close_interval(workspace, "agent", key, outcome, ended_at=when,
                             agent=agent_label(payload))
        summary["action"] = "closed" if rec else "not-open"
        summary["records"] = [rec] if rec else []
        return summary

    if event == "TaskCreated":
        key = task_key(payload)
        if not key:
            summary["action"] = "no-key"
            return summary
        rec = open_interval(workspace, "task", key, started_at=when, task_id=key,
                            agent=_first_present(payload, "task.owner", "task.assignee", "owner"))
        summary["action"] = "opened"
        summary["records"] = [rec]
        return summary

    # TaskCompleted
    key = task_key(payload)
    if not key:
        summary["action"] = "no-key"
        return summary
    rec = close_interval(workspace, "task", key, OUTCOME_OK, ended_at=when, task_id=key)
    summary["action"] = "closed" if rec else "not-open"
    summary["records"] = [rec] if rec else []
    return summary


def main(argv: list[str] | None = None) -> int:
    """Hook entry: stdin JSON -> ledger. Exits 0 on every path."""
    try:
        if disabled():
            return 0
        raw = _read_stdin_utf8()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            return 0
        workspace = resolve_workspace(payload)
        summary = handle_event(payload, workspace)
        _debug(f"{summary.get('event')}: {summary.get('action')} "
               f"({len(summary.get('records') or [])} record(s)) in {workspace}")
    except Exception as exc:  # noqa: BLE001 - a timing record never blocks a session
        _debug(f"swallowed {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
