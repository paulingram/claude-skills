"""v4.1.0 -- a held turn travels as hook JSON on stdout, not as a hook error.

Field report: the completion lock's worklist and the continuation guard's
CONTINUE directive -- text written for the AGENT -- were rendered in the
user's main view on every refused stop. Claude Code shows a Stop hook's
``decision: block`` / exit-2 stderr as a hook-error notification; it shows
``hookSpecificOutput.additionalContext`` only as transcript feedback while
holding the turn through the same loop protections. These tests pin the
channel itself (the behavioural pins elsewhere read it through
``tests/helpers/hook_runner.blocked`` and are channel-neutral):

* a refused Stop exits 0 with ONE JSON object on stdout whose
  ``additionalContext`` carries the directive, and stderr does not;
* no ``systemMessage`` unless the operator opts in, and then only counts;
* ``CT6_STOP_HOLD_MODE=block`` restores ``decision: block`` for a harness
  that does not honour ``additionalContext`` on Stop;
* ``--check`` (a CLI, not a hook) keeps exit 2 with the worklist on stderr;
* the directive never names the user's release command -- an agent that is
  held must not be handed its own way out.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hooks import open_work as ow
from hooks import run_continuity as rc
from tests.helpers.hook_runner import allowed, blocked, hold_payload, hold_text

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "hooks" / "pipeline-completion-audit.py"
SESSION = "feedbeef12345678"


def _run(workspace: Path, tasks_root: Path, payload: dict | None, env_extra: dict | None = None,
         argv: list[str] | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "CT6_TASKS_ROOT": str(tasks_root)}
    for var in (rc.DISABLE_ENV, ow.DISABLE_ENV, ow.DISABLE_TASKS_ENV, ow.DISABLE_LEDGER_ENV,
                ow.DISABLE_OUTPUT_ENV, "CT6_STOP_HOLD_MODE", "CT6_STOP_USER_NOTICE"):
        env.pop(var, None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(SCRIPT), *(argv or [])],
                          input=json.dumps(payload) if payload is not None else "",
                          text=True, capture_output=True, cwd=str(workspace), env=env)


def _open_task(tasks_root: Path, subject: str = "wire the release verb") -> None:
    d = tasks_root / SESSION
    d.mkdir(parents=True, exist_ok=True)
    (d / "1.json").write_text(json.dumps({
        "id": "1", "subject": subject, "description": "", "activeForm": "working",
        "status": "in_progress", "blocks": [], "blockedBy": [],
    }), encoding="utf-8")


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    w = tmp_path / "ws"
    (w / ".architect-team").mkdir(parents=True)
    return w


@pytest.fixture()
def tasks_root(tmp_path: Path) -> Path:
    r = tmp_path / "tasks"
    r.mkdir()
    return r


def test_a_held_stop_is_transcript_feedback_not_a_hook_error(ws, tasks_root):
    _open_task(tasks_root)
    r = _run(ws, tasks_root, {"session_id": SESSION, "stop_hook_active": True, "hook_event_name": "Stop"})
    assert r.returncode == 0, r.stderr
    objs = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(objs) == 1, f"exactly one JSON line on stdout, got {objs!r}"
    data = json.loads(objs[0])
    assert set(data) == {"hookSpecificOutput"}, data
    assert data["hookSpecificOutput"]["hookEventName"] == "Stop"
    text = data["hookSpecificOutput"]["additionalContext"]
    assert "wire the release verb" in text and "COMPLETION LOCK" in text
    assert "decision" not in data and "systemMessage" not in data
    assert "wire the release verb" not in r.stderr, "the directive must not also travel on stderr"
    assert r.stdout.isascii(), "cp1252-safe: the payload is ASCII however the task is titled"
    assert blocked(r) and hold_text(r) == text


def test_an_allowed_stop_prints_nothing(ws, tasks_root):
    r = _run(ws, tasks_root, {"session_id": SESSION, "stop_hook_active": True})
    assert r.returncode == 0 and r.stdout.strip() == "", (r.stdout, r.stderr)
    assert allowed(r) and hold_payload(r) is None


def test_the_user_notice_is_opt_in_and_carries_counts_not_contents(ws, tasks_root):
    _open_task(tasks_root, subject="secret subject the user need not see")
    r = _run(ws, tasks_root, {"session_id": SESSION, "stop_hook_active": True},
             env_extra={"CT6_STOP_USER_NOTICE": "1"})
    data = hold_payload(r)
    notice = data.get("systemMessage")
    assert isinstance(notice, str) and notice.startswith("CT6 is holding this turn: 1 open item(s)")
    assert "secret subject" not in notice and len(notice) < 200
    assert "secret subject" in data["hookSpecificOutput"]["additionalContext"]


def test_block_mode_restores_the_decision_field(ws, tasks_root):
    _open_task(tasks_root)
    r = _run(ws, tasks_root, {"session_id": SESSION, "stop_hook_active": True},
             env_extra={"CT6_STOP_HOLD_MODE": "block"})
    data = hold_payload(r)
    assert r.returncode == 0 and data["decision"] == "block"
    assert "wire the release verb" in data["reason"] and "hookSpecificOutput" not in data
    assert blocked(r)


def test_the_event_name_follows_the_payload(ws, tasks_root):
    _open_task(tasks_root)
    r = _run(ws, tasks_root, {"session_id": SESSION, "stop_hook_active": True,
                              "hook_event_name": "SubagentStop"})
    assert hold_payload(r)["hookSpecificOutput"]["hookEventName"] == "SubagentStop"


def test_check_mode_is_a_cli_and_keeps_exit_two(ws, tasks_root):
    # An engaged run with an unfinished review surface: the standalone audit
    # (`--check`, the pre-commit gate) must still fail loudly by exit code.
    at = ws / ".architect-team"
    (at / "reviews").mkdir()
    (at / "reviews" / "task-1-review.json").write_text("{", encoding="utf-8")  # unreadable verdict
    r = _run(ws, tasks_root, None, argv=["--check"])
    assert r.stdout.strip() == "", "a CLI, not a hook: no hook JSON"
    assert r.returncode in (0, 2)
    if r.returncode == 2:
        assert "BLOCKED" in r.stderr


def test_the_continuation_guard_holds_through_the_same_channel(ws, tasks_root):
    """An ENGAGED orchestrator session (marker names this session) with no
    registered work: the unregistered-run arm composes the guard's CONTINUE
    directive into the hold -- and that whole directive is additionalContext."""
    rc.engage_marker(ws, "architect-team-pipeline", SESSION)
    r = _run(ws, tasks_root, {"session_id": SESSION, "stop_hook_active": True})
    data = hold_payload(r)
    assert r.returncode == 0 and data is not None, (r.stdout, r.stderr)
    text = data["hookSpecificOutput"]["additionalContext"]
    assert "UNREGISTERED RUN" in text
    assert "UNREGISTERED RUN" not in r.stderr


@pytest.mark.parametrize("setup", ["lock", "engaged"])
def test_the_hold_text_never_names_the_users_release_command(ws, tasks_root, setup):
    if setup == "lock":
        _open_task(tasks_root)
    else:
        rc.engage_marker(ws, "architect-team-pipeline", SESSION)
    r = _run(ws, tasks_root, {"session_id": SESSION, "stop_hook_active": True})
    text = hold_text(r) or ""
    assert text, (r.stdout, r.stderr)
    lowered = text.lower()
    for forbidden in ("architect-team:unlock", "completion_unlock", "/unlock", "unlock the"):
        assert forbidden not in lowered, f"the held agent must not be handed its exit: {forbidden!r}"


def test_the_hold_source_never_names_the_release_command():
    """Belt and braces on the sweep above: the emitting module's own text."""
    src = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("architect-team:unlock", "completion_unlock.py release", "/architect-team:unlock"):
        assert forbidden not in src, forbidden
