"""Tests for hooks/timings_log.py -- the per-interval timing ledger (change 15).

The ledger is observability under a never-block contract, so the pins run in
both directions: an interval that was opened is closed with its duration, an
interval whose start was never seen is NOT fabricated, a run is closed only
once the active-run marker is no longer active, a stale open interval is
closed as ``unknown`` (never as a guessed success), the hook entry exits 0 on
every path (malformed stdin included) and stays silent unless
``CT6_TIMINGS_DEBUG=1``, the kill switch writes nothing, and the user-level
mirror receives the same line the project ledger does.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers.hook_runner import run_hook
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "timings_log.py"


@pytest.fixture(scope="module")
def tl() -> ModuleType:
    return load_module(HOOK, "ct6_timings_log_under_test")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _engage(ws: Path, *, status: str = "active", run_id: str = "run-t-1",
            skill: str = "bug-fix-pipeline", intake: dict | None = None,
            started_at: str | None = None) -> None:
    """Write the active-run marker + intake-state the ledger enriches from."""
    state = ws / ".architect-team"
    state.mkdir(parents=True, exist_ok=True)
    started = started_at or _iso(_now() - timedelta(minutes=30))
    marker = {"schema": 1, "status": status, "skill": skill, "session_id": None,
              "started_at": started, "updated_at": _iso(_now()), "run_id": run_id,
              "slug": "checkout-fix", "phase": "Phase B3", "completed_at": None,
              "stand_down_reason": None}
    (state / "active-run.json").write_text(json.dumps(marker), encoding="utf-8")
    base = {"run_id": run_id, "phase": "Phase B3", "dispatch_mode": "subagents",
            "model": "opus", "size_bucket": "medium", "started_at": started}
    if intake is not None:
        base.update(intake)
    (state / "intake-state.json").write_text(json.dumps(base), encoding="utf-8")


def _lines(ws: Path) -> list[dict]:
    path = ws / ".architect-team" / "run-history" / "timings.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _open(ws: Path) -> dict:
    path = ws / ".architect-team" / "run-history" / "timings-open.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# --------------------------------------------------------------------------- #
# library: open / close / record / read
# --------------------------------------------------------------------------- #

def test_open_then_close_appends_one_line_with_duration(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    started = _iso(_now() - timedelta(seconds=90))
    opened = tl.open_interval(tmp_path, "agent", "a-1", started_at=started, agent="backend")
    assert opened["started_at"] == started
    assert _open(tmp_path)["agent:a-1"]["agent"] == "backend"
    closed = tl.close_interval(tmp_path, "agent", "a-1", "ok", ended_at=_iso(_now()))
    assert closed is not None
    assert closed["kind"] == "agent" and closed["outcome"] == "ok"
    assert closed["agent"] == "backend"
    assert 85 <= closed["duration_s"] <= 95
    assert _open(tmp_path) == {}, "closing pops the open record"
    lines = _lines(tmp_path)
    assert len(lines) == 1 and lines[0] == closed
    assert set(lines[0].keys()) == set(tl.RECORD_FIELDS), "the line schema is closed"
    assert lines[0]["schema"] == "timing/v1"


def test_close_without_open_fabricates_nothing(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    assert tl.close_interval(tmp_path, "task", "T-9") is None
    assert _lines(tmp_path) == []


def test_record_direct_and_read_all(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    rec = tl.record(tmp_path, "phase", started_at="2026-08-01T09:00:00Z",
                    ended_at="2026-08-01T09:02:30Z", outcome="ok", phase="B3")
    assert rec["duration_s"] == 150.0
    assert tl.read_all(tmp_path) == [rec]


def test_reopen_keeps_original_started_at(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    first = _iso(_now() - timedelta(minutes=5))
    tl.open_interval(tmp_path, "task", "T-1", started_at=first)
    tl.open_interval(tmp_path, "task", "T-1", started_at=_iso(_now()))
    assert _open(tmp_path)["task:T-1"]["started_at"] == first


def test_make_record_rejects_unknown_kind(tl: ModuleType) -> None:
    with pytest.raises(ValueError):
        tl.make_record("sprint", None, None)
    with pytest.raises(ValueError):
        tl.open_interval(Path("."), "sprint", "x")


def test_duration_helpers(tl: ModuleType) -> None:
    assert tl.duration_seconds("2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z") == 60.0
    assert tl.duration_seconds("2026-01-01T00:01:00Z", "2026-01-01T00:00:00Z") == 0.0
    assert tl.duration_seconds(None, "2026-01-01T00:00:00Z") is None
    assert tl.duration_seconds("garbage", "2026-01-01T00:00:00Z") is None
    assert tl.parse_iso("2026-01-01T00:00:00+02:00").hour == 22


# --------------------------------------------------------------------------- #
# enrichment
# --------------------------------------------------------------------------- #

def test_enrichment_from_intake_state(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path, intake={"lane": "bug-fix"})
    rec = tl.record(tmp_path, "task", started_at="2026-08-01T09:00:00Z",
                    ended_at="2026-08-01T09:00:10Z", task_id="T-2")
    assert rec["run_id"] == "run-t-1"
    assert rec["lane"] == "bug-fix"
    assert rec["phase"] == "Phase B3"
    assert rec["dispatch_mode"] == "subagents"
    assert rec["model"] == "opus"
    assert rec["size_bucket"] == "medium"


def test_lane_falls_back_to_marker_skill(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path, skill="bug-fix-pipeline")
    ctx = tl.context_from_workspace(tmp_path)
    assert ctx["lane"] == "bug-fix"
    assert ctx["marker_status"] == "active"
    assert ctx["run_started_at"] is not None


def test_caller_fields_win_over_intake(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path, intake={"lane": "bug-fix"})
    rec = tl.record(tmp_path, "phase", started_at="2026-08-01T09:00:00Z",
                    ended_at="2026-08-01T09:00:10Z", phase="Phase B5", lane="mini")
    assert rec["phase"] == "Phase B5" and rec["lane"] == "mini"


def test_context_without_any_state_is_all_none(tl: ModuleType, tmp_path: Path) -> None:
    ctx = tl.context_from_workspace(tmp_path)
    assert all(ctx[k] is None for k in tl.CONTEXT_FIELDS)
    assert tl.workspace_engaged(tmp_path) is False


# --------------------------------------------------------------------------- #
# hook entry: one synthetic payload per event
# --------------------------------------------------------------------------- #

def test_subagent_start_opens_agent_interval(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    r = run_hook(HOOK, tmp_path, {"hook_event_name": "SubagentStart", "agent_id": "a-42",
                                  "agent_type": "backend", "cwd": str(tmp_path)})
    assert r.returncode == 0 and r.stderr == ""
    store = _open(tmp_path)
    assert "agent:a-42" in store
    assert store["agent:a-42"]["agent"] == "backend"
    assert store["agent:a-42"]["run_id"] == "run-t-1"


def test_subagent_stop_closes_agent_interval(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    run_hook(HOOK, tmp_path, {"hook_event_name": "SubagentStart", "agent_id": "a-42",
                              "agent_type": "backend", "cwd": str(tmp_path)})
    r = run_hook(HOOK, tmp_path, {"hook_event_name": "SubagentStop", "agent_id": "a-42",
                                  "agent_type": "backend", "cwd": str(tmp_path)})
    assert r.returncode == 0
    lines = _lines(tmp_path)
    assert len(lines) == 1
    assert lines[0]["kind"] == "agent" and lines[0]["agent"] == "backend"
    assert lines[0]["outcome"] == "ok" and lines[0]["duration_s"] >= 0
    assert _open(tmp_path) == {}


def test_subagent_payload_keyed_defensively(tl: ModuleType) -> None:
    assert tl.agent_key({"subagent": {"name": "qa-1"}}) == "qa-1"
    assert tl.agent_key({"subagent_type": "frontend"}) == "frontend"
    assert tl.agent_key({"teammate": {"name": "lead"}}) == "lead"
    assert tl.agent_key({"task_id": "T-3"}) == "T-3"
    assert tl.agent_key({}) is None
    assert tl.agent_label({"agent_id": "x", "agent_type": "backend"}) == "backend"


def test_task_created_and_completed_bracket_task_interval(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    r1 = run_hook(HOOK, tmp_path, {"hook_event_name": "TaskCreated",
                                   "task": {"id": "T-7", "subject": "wire totals"}, "cwd": str(tmp_path)})
    assert r1.returncode == 0
    assert _open(tmp_path)["task:T-7"]["task_id"] == "T-7"
    r2 = run_hook(HOOK, tmp_path, {"hook_event_name": "TaskCompleted",
                                   "task": {"id": "T-7"}, "cwd": str(tmp_path)})
    assert r2.returncode == 0
    lines = _lines(tmp_path)
    assert len(lines) == 1 and lines[0]["kind"] == "task" and lines[0]["task_id"] == "T-7"


def test_task_completed_with_flat_task_id_shape(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    tl.open_interval(tmp_path, "task", "T-8")
    r = run_hook(HOOK, tmp_path, {"hook_event_name": "TaskCompleted", "taskId": "T-8", "cwd": str(tmp_path)})
    assert r.returncode == 0
    assert [l["task_id"] for l in _lines(tmp_path)] == ["T-8"]


def test_stop_while_run_active_leaves_run_open(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path, status="active")
    tl.open_interval(tmp_path, "agent", "a-1")
    r = run_hook(HOOK, tmp_path, {"hook_event_name": "Stop", "cwd": str(tmp_path)})
    assert r.returncode == 0
    assert _lines(tmp_path) == [], "an active run is never closed by a blocked Stop"
    assert "agent:a-1" in _open(tmp_path), "a fresh open interval survives an active-run Stop"


def test_stop_after_completion_records_run_from_intake_and_closes_open_as_unknown(
    tl: ModuleType, tmp_path: Path
) -> None:
    started = _iso(_now() - timedelta(minutes=45))
    _engage(tmp_path, status="complete", started_at=started, intake={"lane": "bug-fix"})
    tl.open_interval(tmp_path, "agent", "a-1", agent="backend")
    r = run_hook(HOOK, tmp_path, {"hook_event_name": "Stop", "cwd": str(tmp_path)})
    assert r.returncode == 0
    lines = _lines(tmp_path)
    runs = [l for l in lines if l["kind"] == "run"]
    agents = [l for l in lines if l["kind"] == "agent"]
    assert len(runs) == 1
    assert runs[0]["started_at"] == started and runs[0]["outcome"] == "ok"
    assert runs[0]["lane"] == "bug-fix" and runs[0]["run_id"] == "run-t-1"
    assert 44 * 60 <= runs[0]["duration_s"] <= 46 * 60
    assert len(agents) == 1 and agents[0]["outcome"] == "unknown"
    assert _open(tmp_path) == {}
    # A second Stop after completion must not duplicate the run line.
    r2 = run_hook(HOOK, tmp_path, {"hook_event_name": "Stop", "cwd": str(tmp_path)})
    assert r2.returncode == 0
    assert len([l for l in _lines(tmp_path) if l["kind"] == "run"]) == 1


def test_stop_closes_open_run_interval_with_marker_outcome(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path, status="stood-down")
    tl.open_interval(tmp_path, "run", "run-t-1", started_at=_iso(_now() - timedelta(minutes=3)))
    summary = tl.handle_event({"hook_event_name": "Stop"}, tmp_path)
    assert summary["action"] == "run-closed"
    runs = [l for l in _lines(tmp_path) if l["kind"] == "run"]
    assert len(runs) == 1 and runs[0]["outcome"] == "stood-down"


def test_stale_open_interval_closed_as_unknown_even_while_active(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path, status="active")
    tl.open_interval(tmp_path, "agent", "old", started_at=_iso(_now() - timedelta(hours=48)))
    tl.open_interval(tmp_path, "agent", "fresh")
    summary = tl.handle_event({"hook_event_name": "Stop"}, tmp_path)
    assert summary["action"] == "run-active"
    lines = _lines(tmp_path)
    assert [l["outcome"] for l in lines] == ["unknown"]
    assert "agent:fresh" in _open(tmp_path) and "agent:old" not in _open(tmp_path)


def test_not_engaged_workspace_records_nothing(tl: ModuleType, tmp_path: Path) -> None:
    r = run_hook(HOOK, tmp_path, {"hook_event_name": "SubagentStart", "agent_id": "a-1",
                                  "agent_type": "backend", "cwd": str(tmp_path)})
    assert r.returncode == 0 and r.stderr == ""
    assert not (tmp_path / ".architect-team" / "run-history").exists()


def test_unknown_event_is_ignored(tl: ModuleType, tmp_path: Path) -> None:
    _engage(tmp_path)
    summary = tl.handle_event({"hook_event_name": "PreToolUse", "tool_name": "Bash"}, tmp_path)
    assert summary["action"] == "ignored" and _lines(tmp_path) == []


# --------------------------------------------------------------------------- #
# kill switch, exception silence, debug
# --------------------------------------------------------------------------- #

def test_kill_switch_writes_nothing(tl: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _engage(tmp_path)
    monkeypatch.setenv("CT6_TIMINGS_DISABLED", "1")
    r = run_hook(HOOK, tmp_path, {"hook_event_name": "SubagentStart", "agent_id": "a-1",
                                  "agent_type": "backend", "cwd": str(tmp_path)})
    assert r.returncode == 0 and r.stderr == ""
    assert not (tmp_path / ".architect-team" / "run-history").exists()


def _raw_run(payload_text: str, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(HOOK)], input=payload_text, text=True,
                          capture_output=True, cwd=str(cwd), env=env)


def test_malformed_stdin_exits_zero_silently(tmp_path: Path) -> None:
    _engage(tmp_path)
    r = _raw_run("this is not json", tmp_path)
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


def test_debug_env_reports_to_stderr_only(tmp_path: Path) -> None:
    _engage(tmp_path)
    r = _raw_run("this is not json", tmp_path, {"CT6_TIMINGS_DEBUG": "1"})
    assert r.returncode == 0
    assert r.stdout == ""
    assert "timings_log:" in r.stderr and "swallowed" in r.stderr


def test_empty_stdin_exits_zero(tmp_path: Path) -> None:
    r = _raw_run("", tmp_path)
    assert r.returncode == 0 and r.stderr == ""


def test_hook_source_contract(tl: ModuleType) -> None:
    src = HOOK.read_text(encoding="utf-8")
    assert "shared_util import _utc_now_iso" in src, "imports _utc_now_iso from shared_util (single definition)"
    assert "def _utc_now_iso" not in src
    assert tl.HOOK_EVENTS == ("SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted", "Stop")
    assert tl.KINDS == ("agent", "task", "phase", "run")
    assert src.isascii(), "hook source must be ASCII-only"


# --------------------------------------------------------------------------- #
# user mirror
# --------------------------------------------------------------------------- #

def test_user_mirror_receives_the_same_line(tl: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _engage(tmp_path)
    mirror = tmp_path / "home" / ".architect-team" / "timings.jsonl"
    monkeypatch.setenv("CT6_TIMINGS_USER_MIRROR", "1")
    monkeypatch.setenv("CT6_TIMINGS_USER_MIRROR_PATH", str(mirror))
    assert tl.user_mirror_path() == mirror
    tl.open_interval(tmp_path, "phase", "B3", started_at=_iso(_now() - timedelta(seconds=10)))
    closed = tl.close_interval(tmp_path, "phase", "B3")
    assert closed is not None
    mirrored = [json.loads(l) for l in mirror.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert mirrored == [closed]
    assert _lines(tmp_path) == [closed]


def test_user_mirror_off_by_default(tl: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _engage(tmp_path)
    mirror = tmp_path / "mirror.jsonl"
    monkeypatch.delenv("CT6_TIMINGS_USER_MIRROR", raising=False)
    monkeypatch.setenv("CT6_TIMINGS_USER_MIRROR_PATH", str(mirror))
    tl.record(tmp_path, "task", started_at="2026-08-01T09:00:00Z", ended_at="2026-08-01T09:00:01Z")
    assert not mirror.exists()


# --------------------------------------------------------------------------- #
# workspace resolution
# --------------------------------------------------------------------------- #

def test_resolve_workspace_prefers_payload_cwd_then_falls_back(tl: ModuleType, tmp_path: Path) -> None:
    here = tmp_path / "here"
    here.mkdir()
    assert tl.resolve_workspace({"cwd": str(here)}, cwd=tmp_path) == here
    assert tl.resolve_workspace({"cwd": str(tmp_path / "missing")}, cwd=tmp_path) == tmp_path
    assert tl.resolve_workspace({}, cwd=tmp_path) == tmp_path


def test_resolve_workspace_climbs_to_git_toplevel(tl: ModuleType, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "sub" / "deeper").mkdir(parents=True)
    init = subprocess.run(["git", "init", "-q", str(repo)], capture_output=True, text=True)
    if init.returncode != 0:
        pytest.skip("git unavailable")
    resolved = tl.resolve_workspace({"cwd": str(repo / "sub" / "deeper")})
    assert resolved.resolve() == repo.resolve()
