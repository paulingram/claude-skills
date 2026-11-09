"""v4.0.0 -- the Claude 5 task-tool floor (proposal change 1).

Claude 5 models get TaskCreate / TaskUpdate only with
``CLAUDE_CODE_ENABLE_TODO_TOOLS=1``. Three surfaces carry the floor:

* ``hooks/open_work.py`` -- the DEFAULT harness task root being absent is a
  measured, advisory gap (the source is unavailable), while a REDIRECTED root
  that is absent stays unknown state and blocks (the v3.60.0 F13 contract).
  The session directory resolves both the current ``<root>/<session id>/``
  layout and the legacy ``<root>/session-<sid8>/`` one.
* ``scripts/setup/setup.py`` -- ``check_task_tools`` reports / writes the flag
  with the same consent shape as the teams flag.
* ``hooks/sessionstart-run-continuity.py`` -- one warning line in a CT6
  workspace that has neither the opt-in nor a task root.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ow():
    return load_module(REPO_ROOT / "hooks" / "open_work.py", "ow_floor")


@pytest.fixture()
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_CODE_ENABLE_TODO_TOOLS", raising=False)
    monkeypatch.delenv("CT6_TASKS_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    return tmp_path


# --- session directory layouts ------------------------------------------------


def test_session_task_dir_prefers_full_id_layout(ow, tmp_path):
    root = tmp_path / "tasks"
    full = root / "c942cf72-9738-5694-b451-9c0d1b4753f2"
    full.mkdir(parents=True)
    assert ow.session_task_dir(root, "c942cf72-9738-5694-b451-9c0d1b4753f2") == full


def test_session_task_dir_falls_back_to_legacy_layout(ow, tmp_path):
    root = tmp_path / "tasks"
    legacy = root / "session-c942cf72"
    legacy.mkdir(parents=True)
    assert ow.session_task_dir(root, "c942cf72-9738-5694-b451-9c0d1b4753f2") == legacy


def test_session_task_dir_reports_full_id_path_when_neither_exists(ow, tmp_path):
    root = tmp_path / "tasks"
    root.mkdir()
    assert ow.session_task_dir(root, "abcdef12-x") == root / "abcdef12-x"


def test_read_harness_tasks_reads_full_id_layout(ow, tmp_path):
    root = tmp_path / "tasks"
    sid = "c942cf72-9738-5694-b451-9c0d1b4753f2"
    (root / sid).mkdir(parents=True)
    (root / sid / "1.json").write_text(json.dumps({"id": "1", "subject": "s", "status": "pending"}), encoding="utf-8")
    read = ow.read_harness_tasks(sid, root)
    assert [i["id"] for i in read["items"]] == ["1"]
    assert read["unreadable"] == [] and read["unavailable"] is None


# --- default vs redirected root --------------------------------------------------


def test_default_root_missing_is_unavailable_not_unreadable(ow, clean_env):
    read = ow.read_harness_tasks("abcd1234-sess", None)
    assert read["unreadable"] == []
    assert read["unavailable"] is not None
    assert "does not exist" in read["unavailable"]["reason"]
    assert "CLAUDE_CODE_ENABLE_TODO_TOOLS" in read["unavailable"]["reason"]


def test_default_root_missing_with_opt_in_names_the_other_cause(ow, clean_env, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENABLE_TODO_TOOLS", "1")
    read = ow.read_harness_tasks("abcd1234-sess", None)
    assert read["unavailable"] is not None
    assert "opt-in is configured" in read["unavailable"]["reason"]


def test_redirected_root_missing_still_blocks_as_unknown(ow, clean_env, tmp_path):
    read = ow.read_harness_tasks("abcd1234-sess", tmp_path / "nope")
    assert read["unavailable"] is None
    assert len(read["unreadable"]) == 1 and "does not exist" in read["unreadable"][0]["reason"]


def test_env_redirected_root_missing_still_blocks(ow, clean_env, tmp_path, monkeypatch):
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "redirected-nope"))
    read = ow.read_harness_tasks("abcd1234-sess", None)
    assert read["unavailable"] is None and len(read["unreadable"]) == 1


def test_completion_lock_degrades_to_advisory_when_default_root_absent(ow, clean_env, tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = ow.evaluate_completion_lock(workspace, "abcd1234-sess", records=[])
    assert result["blocked"] is False
    assert result["unreadable"] == []
    assert any("task-list source is unavailable" in n for n in result["advisory_notes"])


# --- the opt-in probe -------------------------------------------------------------


def test_task_tools_opted_in_from_env(ow, clean_env, monkeypatch):
    assert ow.task_tools_opted_in() is False
    monkeypatch.setenv("CLAUDE_CODE_ENABLE_TODO_TOOLS", "true")
    assert ow.task_tools_opted_in() is True


def test_task_tools_opted_in_from_settings(ow, clean_env, tmp_path):
    settings = tmp_path / "home" / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"env": {"CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}}), encoding="utf-8")
    assert ow.task_tools_opted_in(settings_path=settings) is True
    settings.write_text("{not json", encoding="utf-8")
    assert ow.task_tools_opted_in(settings_path=settings) is False


# --- setup.py -------------------------------------------------------------------


@pytest.fixture()
def setup_mod():
    return load_module(REPO_ROOT / "scripts" / "setup" / "setup.py", "setup_for_task_tools")


def test_check_task_tools_present_via_env(setup_mod, tmp_path):
    name, status, detail = setup_mod.check_task_tools(
        check_only=True, no_prompt=True, env={"CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"},
        settings_path=tmp_path / "settings.json",
    )
    assert (name, status) == ("task-tools", "present") and "env" in detail


def test_check_task_tools_check_only_reports_missing_without_writing(setup_mod, tmp_path):
    settings = tmp_path / "settings.json"
    name, status, detail = setup_mod.check_task_tools(
        check_only=True, no_prompt=False, env={}, settings_path=settings,
    )
    assert status == "missing" and "CLAUDE_CODE_ENABLE_TODO_TOOLS" in detail
    assert not settings.exists()


def test_check_task_tools_assume_yes_writes_beside_the_teams_flag(setup_mod, tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"env": {setup_mod.TEAMS_ENV_VAR: "1"}, "other": 1}), encoding="utf-8")
    name, status, _ = setup_mod.check_task_tools(
        check_only=False, no_prompt=False, env={}, settings_path=settings, assume_yes=True,
    )
    assert status == "installed"
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"] == {setup_mod.TEAMS_ENV_VAR: "1", "CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}
    assert data["other"] == 1
    # idempotent
    name, status, _ = setup_mod.check_task_tools(
        check_only=False, no_prompt=False, env={}, settings_path=settings, assume_yes=True,
    )
    assert status == "present"


def test_check_task_tools_no_prompt_prints_and_does_not_write(setup_mod, tmp_path, capsys):
    settings = tmp_path / "settings.json"
    _, status, _ = setup_mod.check_task_tools(check_only=False, no_prompt=True, env={}, settings_path=settings)
    assert status == "missing" and not settings.exists()
    assert "[task-tools]" in capsys.readouterr().out


def test_setup_main_carries_a_task_tools_row(setup_mod):
    src = (REPO_ROOT / "scripts" / "setup" / "setup.py").read_text(encoding="utf-8")
    assert "check_task_tools(" in src.split("def main(")[1]


# --- SessionStart warning ----------------------------------------------------------


@pytest.fixture()
def ss_mod():
    return load_module(REPO_ROOT / "hooks" / "sessionstart-run-continuity.py", "ss_for_task_tools")


def test_sessionstart_warns_in_ct6_workspace_without_opt_in(ss_mod, clean_env, tmp_path):
    ws = tmp_path / "ws"
    (ws / ".architect-team").mkdir(parents=True)
    note = ss_mod.maybe_warn_task_tools({"cwd": str(ws)})
    assert note.startswith("[CT6 task tools]")
    assert "CLAUDE_CODE_ENABLE_TODO_TOOLS=1" in note


def test_sessionstart_silent_outside_ct6_workspace(ss_mod, clean_env, tmp_path):
    ws = tmp_path / "plain"
    ws.mkdir()
    assert ss_mod.maybe_warn_task_tools({"cwd": str(ws)}) == ""


def test_sessionstart_silent_when_opted_in_or_root_exists(ss_mod, clean_env, tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / ".architect-team").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CODE_ENABLE_TODO_TOOLS", "1")
    assert ss_mod.maybe_warn_task_tools({"cwd": str(ws)}) == ""
    monkeypatch.delenv("CLAUDE_CODE_ENABLE_TODO_TOOLS")
    (tmp_path / "home" / ".claude" / "tasks").mkdir(parents=True)
    assert ss_mod.maybe_warn_task_tools({"cwd": str(ws)}) == ""


# --- review gate reads the full-id layout ------------------------------------------------


def test_review_gate_reads_subject_from_full_id_task_dir(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(REPO_ROOT / "hooks"))
    rg = load_module(REPO_ROOT / "hooks" / "review-gate-task.py", "rg_for_task_tools")
    assert rg._ow is not None
    root = tmp_path / "tasks"
    sid = "c942cf72-9738-5694-b451-9c0d1b4753f2"
    (root / sid).mkdir(parents=True)
    (root / sid / "7.json").write_text(json.dumps({"id": "7", "subject": "wire the export"}), encoding="utf-8")
    monkeypatch.setattr(rg._ow, "tasks_root", lambda explicit=None: root)
    assert rg._completing_task_subject({"session_id": sid}, "7") == "wire the export"


# --- agents no longer list the disabled TodoWrite tool --------------------------------------


def test_no_agent_lists_todowrite():
    offenders = [p.name for p in (REPO_ROOT / "agents").glob("*.md")
                 if "TodoWrite" in p.read_text(encoding="utf-8")]
    assert offenders == []
