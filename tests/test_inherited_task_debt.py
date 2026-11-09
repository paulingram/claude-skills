"""Tests for v3.64.0 inherited-task-debt — the completion lock learns abandonment.

Field report (2026-08-23, a production workspace): a session inherited four open
harness tasks from terminated sessions (task lists outlive sessions — resume /
continue / compact keeps the same store, teams keep the team store, and the
harness carries lists across forks) and the completion lock held every turn on
work no live session could ever close. The operator ran the one command the
block printed (`run_continuity.py --mark-complete`) and it governed a different
gate — and REFUSED anyway, because `--check` saw the dead runs' debris.

Five closures, each pinned here with a control:

  D1  staleness discrimination — an open task untouched longer than the
      abandonment window is INHERITED DEBT: surfaced, never blocking.
      (Precedents: the marker staleness window, review remediation #3; the
      v3.55.0 frontend-E2E pre-existing-debt split.)
  D2  an operator retire surface (`open_work.py retire`) that closes a dead
      list — and structurally CANNOT touch a live task without --force.
  D3  the block message: stale tasks listed as non-blocking with the store dir
      named; the kill-switch section states the launch-env fact and names the
      task-abandonment window lever. The F-A rule is preserved: the block
      still never prints the substrate path.
  D4  the --mark-complete refusal names --stand-down as the abandonment path.
  D5  the lock's marker heartbeat fires only for ENGAGED sessions, so a dead
      run's marker can actually age out instead of being kept eternally fresh
      by unrelated wedged sessions.

Test seam: every test injects the harness task root via ``CT6_TASKS_ROOT`` at a
``tmp_path`` directory and refuses to run against the real ``~/.claude/tasks``.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hooks import open_work as ow
from hooks import run_continuity as rc
from tests.helpers.hook_runner import allowed, blocked, hook_text


SESSION = "abcdef1234567890"
FOREIGN_SESSION = "f00dfeedcafe0123"

_REAL_TASKS_ROOT = Path.home() / ".claude" / "tasks"

#: Every env lever this file's subjects read — stripped from each subprocess and
#: cleared for each in-process call, so an operator's exported switch cannot
#: silently green (or red) this file.
_ENV_LEVERS = (
    ow.DISABLE_ENV, ow.DISABLE_TASKS_ENV, ow.DISABLE_LEDGER_ENV,
    ow.DISABLE_OUTPUT_ENV, ow.LEDGER_BLOCKING_ENV,
    "CT6_TASK_STALE_HOURS", rc.MARKER_STALE_HOURS_ENV,
    rc.DISABLE_ENV, rc.MAX_NO_PROGRESS_ENV,
    "CT6_UNREGISTERED_RUN_GATE_DISABLED",
)


@pytest.fixture(autouse=True)
def _clean_levers(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _ENV_LEVERS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture()
def tasks_root(tmp_path: Path) -> Path:
    root = tmp_path / "harness-tasks"
    root.mkdir()
    return root


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture()
def continuity_cli(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "run_continuity.py"


@pytest.fixture()
def open_work_cli(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "open_work.py"


# --- plumbing (mirrors tests/test_completion_lock.py) ------------------------


def _write_task(
    tasks_root: Path,
    task_id: str,
    status: str,
    owner: str | None = None,
    subject: str | None = None,
    session_id: str = SESSION,
    age_hours: float = 0.0,
) -> Path:
    """One harness task file in the on-disk shape the harness uses.

    ``age_hours`` backdates the file's mtime — the only harness-written time
    signal a task carries (the JSON itself has no timestamps), and therefore
    the staleness discriminator D1 reads.
    """
    task: dict = {
        "id": task_id,
        "subject": subject or f"task {task_id}",
        "description": "",
        "activeForm": "working",
        "status": status,
        "blocks": [],
        "blockedBy": [],
    }
    if owner is not None:
        task["owner"] = owner
    d = tasks_root / f"session-{session_id[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{task_id}.json"
    p.write_text(json.dumps(task), encoding="utf-8")
    if age_hours:
        stamp = time.time() - age_hours * 3600.0
        os.utime(p, (stamp, stamp))
    return p


def _clean_env(tasks_root: Path, extra: dict | None = None) -> dict:
    resolved = tasks_root.resolve()
    assert _REAL_TASKS_ROOT not in resolved.parents and resolved != _REAL_TASKS_ROOT, (
        f"refusing to point a subject at the real harness task store: {resolved}"
    )
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for var in _ENV_LEVERS:
        env.pop(var, None)
    env[ow.TASKS_ROOT_ENV] = str(resolved)
    if extra:
        env.update(extra)
    return env


def _run_stop(
    script: Path,
    workspace: Path,
    tasks_root: Path,
    payload: dict,
    env_extra: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True, encoding="utf-8", capture_output=True,
        cwd=str(workspace), env=_clean_env(tasks_root, env_extra),
    )


def _run_retire(
    cli: Path, tasks_root: Path, argv: list[str],
    env_extra: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(cli), "retire", *argv],
        text=True, encoding="utf-8", capture_output=True,
        env=_clean_env(tasks_root, env_extra),
    )


def _evaluate(workspace: Path, tasks_root: Path) -> dict:
    return ow.evaluate_completion_lock(workspace, SESSION, [], tasks_root=tasks_root)


def _iso_minutes_ago(minutes: int) -> str:
    ts = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=minutes)
    return ts.isoformat()


def _backdate_marker(workspace: Path, minutes: int = 10) -> str:
    """Rewind the marker's heartbeat far enough to observe a touch, while
    staying comfortably inside the staleness window."""
    mp = rc.marker_path(workspace)
    marker = json.loads(mp.read_text(encoding="utf-8"))
    marker["updated_at"] = _iso_minutes_ago(minutes)
    mp.write_text(json.dumps(marker), encoding="utf-8")
    return marker["updated_at"]


# --- D1: staleness discrimination --------------------------------------------


def test_stale_open_task_does_not_block(workspace: Path, tasks_root: Path) -> None:
    """THE reported wedge: an open task left behind by a terminated session
    (untouched far longer than the abandonment window) must not refuse the
    stop — it is inherited debt, surfaced but never blocking."""
    _write_task(tasks_root, "9", "in_progress", owner="TemplateAudit",
                subject="Audit how field-mapping templates are managed today",
                age_hours=200.0)
    verdict = _evaluate(workspace, tasks_root)
    assert verdict["blocked"] is False, verdict["reasons"]
    assert verdict["open_tasks"] == []
    assert [t.get("id") for t in verdict["stale_tasks"]] == ["9"]


def test_control_fresh_open_task_still_blocks(workspace: Path, tasks_root: Path) -> None:
    """Falsifiability control: the same task with a fresh mtime holds the turn
    exactly as before — the discrimination is the mtime, nothing else."""
    _write_task(tasks_root, "9", "in_progress", owner="TemplateAudit",
                subject="Audit how field-mapping templates are managed today")
    verdict = _evaluate(workspace, tasks_root)
    assert verdict["blocked"] is True
    assert [t.get("id") for t in verdict["open_tasks"]] == ["9"]
    assert verdict["stale_tasks"] == []


def test_mixed_store_blocks_on_live_and_reports_stale(
    workspace: Path, tasks_root: Path
) -> None:
    _write_task(tasks_root, "1", "pending", subject="live lane")
    _write_task(tasks_root, "2", "pending", subject="dead lane", age_hours=200.0)
    verdict = _evaluate(workspace, tasks_root)
    assert verdict["blocked"] is True
    assert [t.get("id") for t in verdict["open_tasks"]] == ["1"]
    assert [t.get("id") for t in verdict["stale_tasks"]] == ["2"]
    joined = " ".join(verdict["reasons"])
    assert "advisory (not blocking)" in joined and "stale" in joined, (
        "a caller that renders only `reasons` must still see the stale debt"
    )


def test_unknown_mtime_counts_live() -> None:
    """Unknown is not abandoned: an item without a readable mtime stays on the
    blocking side, matching the lock's unknown-is-not-done asymmetry."""
    live, stale = ow.partition_stale_tasks([{"id": "1", "status": "pending"}])
    assert [t["id"] for t in live] == ["1"] and stale == []


def test_task_window_env_is_floored(
    workspace: Path, tasks_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT6_TASK_STALE_HOURS=0.0001 must not become a kill-switch that does not
    look like one (the S-3 lesson, applied to the new lever): a 30-minute-old
    task stays LIVE because the window floors at 1h."""
    monkeypatch.setenv("CT6_TASK_STALE_HOURS", "0.0001")
    _write_task(tasks_root, "1", "pending", age_hours=0.5)
    verdict = _evaluate(workspace, tasks_root)
    assert verdict["blocked"] is True
    assert [t.get("id") for t in verdict["open_tasks"]] == ["1"]


def test_task_window_env_shortens_above_the_floor(
    workspace: Path, tasks_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CT6_TASK_STALE_HOURS", "1")
    _write_task(tasks_root, "1", "pending", age_hours=2.0)
    verdict = _evaluate(workspace, tasks_root)
    assert verdict["blocked"] is False
    assert [t.get("id") for t in verdict["stale_tasks"]] == ["1"]


def test_task_window_defaults_to_marker_window(
    workspace: Path, tasks_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One abandonment lever by default: with no task-specific override the
    marker window governs, so the operator who tunes run-state staleness has
    tuned task staleness with it."""
    monkeypatch.setenv(rc.MARKER_STALE_HOURS_ENV, "2")
    _write_task(tasks_root, "1", "pending", age_hours=3.0)
    _write_task(tasks_root, "2", "pending", age_hours=1.5)
    verdict = _evaluate(workspace, tasks_root)
    assert verdict["blocked"] is True
    assert [t.get("id") for t in verdict["open_tasks"]] == ["2"]
    assert [t.get("id") for t in verdict["stale_tasks"]] == ["1"]


def test_stale_only_store_releases_the_hook_end_to_end(
    script: Path, workspace: Path, tasks_root: Path
) -> None:
    """The field scenario through the REAL hook: a store holding nothing but a
    dead session's tasks lets the turn end at exit 0."""
    for tid in ("8", "9", "10", "11"):
        _write_task(tasks_root, tid, "pending", age_hours=200.0)
    r = _run_stop(script, workspace, tasks_root, {"session_id": SESSION})
    assert allowed(r), f"stale-only debt must release; stderr={hook_text(r)!r}"


def test_control_fresh_store_still_blocks_the_hook_end_to_end(
    script: Path, workspace: Path, tasks_root: Path
) -> None:
    _write_task(tasks_root, "8", "pending", subject="critique both halves")
    r = _run_stop(script, workspace, tasks_root, {"session_id": SESSION})
    assert blocked(r), hook_text(r)
    assert "open harness tasks (1)" in hook_text(r)


# --- D3: the block message ----------------------------------------------------


def test_block_lists_stale_debt_as_non_blocking_and_names_the_store(
    script: Path, workspace: Path, tasks_root: Path
) -> None:
    _write_task(tasks_root, "1", "pending", subject="live lane")
    _write_task(tasks_root, "2", "pending", subject="dead lane from earlier run",
                age_hours=200.0)
    r = _run_stop(script, workspace, tasks_root, {"session_id": SESSION})
    assert blocked(r)
    assert "inherited stale open tasks (1)" in hook_text(r)
    assert "dead lane from earlier run" in hook_text(r)
    assert "NOT blocking" in hook_text(r)
    assert f"session-{SESSION[:8]}" in hook_text(r), "the store dir is named for the operator"
    # The F-A rule survives the new section: the block never prints the
    # substrate path, so it still hands the agent no release entry point.
    assert "open_work.py" not in hook_text(r)
    assert "retire" not in hook_text(r).casefold().replace("retired", ""), (
        "the retire verb is the operator's; the block points at the README only"
    )


def test_block_killswitch_section_states_the_launch_env_fact(
    script: Path, workspace: Path, tasks_root: Path
) -> None:
    """The field report's 'no way to override': the switches worked, but only
    in the environment the app was LAUNCHED from — a fact the block never
    stated. Now it does, alongside the task-abandonment lever."""
    _write_task(tasks_root, "1", "pending")
    r = _run_stop(script, workspace, tasks_root, {"session_id": SESSION})
    assert blocked(r)
    assert "LAUNCHED" in hook_text(r)
    assert "CT6_TASK_STALE_HOURS" in hook_text(r)


# --- D2: the operator retire surface -----------------------------------------


def test_retire_closes_stale_tasks_with_an_audit_trail(
    open_work_cli: Path, tasks_root: Path
) -> None:
    p = _write_task(tasks_root, "9", "in_progress", owner="TemplateAudit",
                    age_hours=200.0)
    r = _run_retire(open_work_cli, tasks_root,
                    ["--session", SESSION, "--reason", "runs terminated 08-18"])
    assert allowed(r), hook_text(r)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["status"] == "completed"
    assert data["metadata"]["ct6_retired"]["reason"] == "runs terminated 08-18"
    assert "9" in json.loads(r.stdout)["retired"]


def test_retire_refuses_live_tasks_without_force(
    open_work_cli: Path, tasks_root: Path
) -> None:
    """The closed boundary that makes the surface safe to document: the verb
    cannot move a LIVE task, so it can never release anything the lock is
    actually holding. --force is the human's explicit override."""
    p = _write_task(tasks_root, "1", "pending")
    r = _run_retire(open_work_cli, tasks_root,
                    ["--session", SESSION, "--reason", "cleanup"])
    assert r.returncode == 1
    assert "--force" in hook_text(r)
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "pending"


def test_retire_force_closes_live_tasks(
    open_work_cli: Path, tasks_root: Path
) -> None:
    p = _write_task(tasks_root, "1", "pending")
    r = _run_retire(open_work_cli, tasks_root,
                    ["--session", SESSION, "--reason", "operator decision", "--force"])
    assert allowed(r), hook_text(r)
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "completed"


def test_retire_requires_a_reason(open_work_cli: Path, tasks_root: Path) -> None:
    p = _write_task(tasks_root, "1", "pending", age_hours=200.0)
    r = _run_retire(open_work_cli, tasks_root,
                    ["--session", SESSION, "--reason", "   "])
    assert blocked(r)
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "pending"


def test_retire_scopes_to_named_task_ids(
    open_work_cli: Path, tasks_root: Path
) -> None:
    kept = _write_task(tasks_root, "1", "pending", age_hours=200.0)
    gone = _write_task(tasks_root, "2", "pending", age_hours=200.0)
    r = _run_retire(open_work_cli, tasks_root,
                    ["--session", SESSION, "--reason", "dead", "--task", "2"])
    assert allowed(r), hook_text(r)
    assert json.loads(kept.read_text(encoding="utf-8"))["status"] == "pending"
    assert json.loads(gone.read_text(encoding="utf-8"))["status"] == "completed"


def test_retire_accepts_the_dir_spelling_and_reports_a_missing_store(
    open_work_cli: Path, tasks_root: Path
) -> None:
    _write_task(tasks_root, "1", "pending", age_hours=200.0)
    r = _run_retire(open_work_cli, tasks_root,
                    ["--session", f"session-{SESSION[:8]}", "--reason", "dead"])
    assert allowed(r), hook_text(r)
    missing = _run_retire(open_work_cli, tasks_root,
                          ["--session", "0000000000", "--reason", "dead"])
    assert missing.returncode == 1
    assert "session-00000000" in hook_text(missing)


def test_retired_store_releases_the_lock_and_stays_registered(
    workspace: Path, open_work_cli: Path, tasks_root: Path
) -> None:
    """End to end: after the operator retires the dead list the lock releases,
    and the store still holds completed tasks — so the unregistered-run arm's
    'registered' condition remains satisfied (retire empties nothing)."""
    _write_task(tasks_root, "9", "in_progress", age_hours=200.0)
    r = _run_retire(open_work_cli, tasks_root,
                    ["--session", SESSION, "--reason", "dead run"])
    assert allowed(r), hook_text(r)
    verdict = _evaluate(workspace, tasks_root)
    assert verdict["blocked"] is False
    assert verdict["stale_tasks"] == [], "a retired task is closed, not stale debt"
    read = ow.read_harness_tasks(SESSION, tasks_root)
    assert read["items"], "the store must remain non-empty (registered)"


# --- D4: the refusal names the abandonment path ------------------------------


def test_mark_complete_refusal_names_stand_down(
    continuity_cli: Path, workspace: Path, tasks_root: Path
) -> None:
    """The field report ran the printed command and it refused on dead runs'
    debris, with no next move named. The refusal now points at --stand-down,
    which records abandonment and is deliberately not gated by this audit."""
    slug = workspace / ".architect-team" / "bug-fix" / "dead-slug"
    slug.mkdir(parents=True)
    r = subprocess.run(
        [sys.executable, str(continuity_cli), "--mark-complete",
         "--root", str(workspace)],
        text=True, encoding="utf-8", capture_output=True,
        env=_clean_env(tasks_root),
    )
    assert r.returncode == 1
    assert "REFUSED --mark-complete" in hook_text(r)
    assert "--stand-down" in hook_text(r)


# --- D5: the heartbeat is the engaged run's pulse ----------------------------


def test_lock_block_in_foreign_session_does_not_heartbeat_the_marker(
    script: Path, workspace: Path, tasks_root: Path
) -> None:
    """An unrelated session wedged on ITS OWN tasks must not keep another
    run's marker eternally fresh — that heartbeat is what made the field
    wedge self-sustaining (the marker could never cross the staleness window
    while anyone worked in the repo)."""
    rc.engage_marker(workspace, "architect-team-pipeline", FOREIGN_SESSION)
    stamp = _backdate_marker(workspace)
    _write_task(tasks_root, "1", "pending")
    r = _run_stop(script, workspace, tasks_root, {"session_id": SESSION})
    assert blocked(r), hook_text(r)
    after = json.loads(rc.marker_path(workspace).read_text(encoding="utf-8"))
    assert after["updated_at"] == stamp, (
        "a non-engaged session's lock block must not refresh the marker"
    )


def test_control_lock_block_in_the_orchestrator_session_still_heartbeats(
    script: Path, workspace: Path, tasks_root: Path
) -> None:
    """Direction control: the run's own orchestrator session (marker records
    THIS session id) keeps the marker fresh across lock blocks, so a live
    engaged run still never goes stale mid-flight."""
    rc.engage_marker(workspace, "architect-team-pipeline", SESSION)
    stamp = _backdate_marker(workspace)
    _write_task(tasks_root, "1", "pending")
    r = _run_stop(script, workspace, tasks_root, {"session_id": SESSION})
    assert blocked(r), hook_text(r)
    after = json.loads(rc.marker_path(workspace).read_text(encoding="utf-8"))
    assert after["updated_at"] != stamp, "the engaged run's heartbeat must survive"
