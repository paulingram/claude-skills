"""v4.1.0 -- releasing a completion hold is the USER's verb.

Field reports: holds that outlived the work (a task nobody closed, an ask the
transcript never resolved, a converge gate never recorded) and holds that
outlived the user's own "good enough, move on". ``hooks/completion_unlock.py``
turns the user's decision into released state under a durable record, and
three enforcement points keep it the user's: the PreToolUse gate's Arm 5
(the release verb only inside the /architect-team:unlock command turn), the
command's ``disable-model-invocation``, and the override guard on the record.
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
from tests.helpers.frontmatter import parse_text
from tests.helpers.module_loader import load_module
from tests.helpers.surfaces import skill_surface

REPO_ROOT = Path(__file__).resolve().parents[1]
UNLOCK = REPO_ROOT / "hooks" / "completion_unlock.py"
SESSION = "feedbeef12345678"


@pytest.fixture()
def mod():
    return load_module(UNLOCK, "completion_unlock_under_test")


@pytest.fixture()
def audit():
    return load_module(REPO_ROOT / "hooks" / "pipeline-completion-audit.py", "audit_for_unlock")


@pytest.fixture()
def gate():
    return load_module(REPO_ROOT / "hooks" / "pretool_skill_gate.py", "skill_gate_for_unlock")


@pytest.fixture()
def guard():
    return load_module(REPO_ROOT / "hooks" / "pretool_unilateral_override_guard.py", "override_guard_for_unlock")


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    w = tmp_path / "ws"
    (w / ".architect-team").mkdir(parents=True)
    return w


@pytest.fixture()
def tasks_root(tmp_path: Path, monkeypatch) -> Path:
    r = tmp_path / "tasks"
    r.mkdir()
    monkeypatch.setenv("CT6_TASKS_ROOT", str(r))
    for var in ("CT6_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "CT6_UNLOCK_GATE_DISABLED"):
        monkeypatch.delenv(var, raising=False)
    return r


def _open_task(tasks_root: Path, tid: str = "1", subject: str = "wire the release verb", sid: str = SESSION) -> None:
    d = tasks_root / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tid}.json").write_text(json.dumps({
        "id": tid, "subject": subject, "description": "", "activeForm": "w",
        "status": "in_progress", "blocks": [], "blockedBy": [],
    }), encoding="utf-8")


def _open_ask(ws: Path, text: str = "also add the README section") -> None:
    ow.ledger_path(ws).write_text(json.dumps({"schema": ow.LEDGER_SCHEMA, "entries": [{
        "id": "ask0", "text": text, "first_seen": "2026-08-01T00:00:00Z",
        "status": "open", "resolved_at": None, "evidence": None}]}), encoding="utf-8")


def _declare_gate(ws: Path, kind: str = "codebase-map") -> None:
    rec = load_module(REPO_ROOT / "scripts" / "converge" / "record.py", "converge_record_for_unlock")
    rec.declare(ws, kind, "CODEBASE MAP COMPLETE", 3)


def _full_hold(ws: Path, tasks_root: Path) -> None:
    _open_task(tasks_root)
    _open_ask(ws)
    _declare_gate(ws)
    rc.engage_marker(ws, "architect-team-pipeline", SESSION)


# --- inspect -------------------------------------------------------------------

def test_inspect_names_every_hold(mod, ws, tasks_root):
    _full_hold(ws, tasks_root)
    rep = mod.inspect_holds(ws)
    assert rep["held"] is True
    assert rep["session"] == {"session_id": SESSION, "source": "run-marker"}
    assert [t["id"] for t in rep["tasks"]["live"]] == ["1"]
    assert [a["id"] for a in rep["asks"]] == ["ask0"]
    assert rep["gates"]["open"] == ["converge:codebase-map"] and rep["gates"]["waived"] == []
    assert rep["run"]["status"] == "active"
    assert len(rep["holds"]) == 4


def test_inspect_on_a_clean_workspace_reports_nothing(mod, ws, tasks_root):
    rep = mod.inspect_holds(ws)
    assert rep["held"] is False and rep["holds"] == [] and rep["releases"] == []


def test_inspect_resolves_the_only_session_with_open_work(mod, ws, tasks_root):
    _open_task(tasks_root, sid="0123456789abcdef")
    rep = mod.inspect_holds(ws)
    assert rep["session"]["source"] == "only-session-with-open-work"
    assert rep["session"]["session_id"] == "0123456789abcdef"
    assert [t["id"] for t in rep["tasks"]["live"]] == ["1"]


# --- release -------------------------------------------------------------------

def test_release_closes_every_source_under_one_record(mod, ws, tasks_root):
    _full_hold(ws, tasks_root)
    summary = mod.release(ws, "good enough, move on with what you have")
    assert summary["problems"] == [] and summary["remaining"] == []
    record = Path(summary["record_path"])
    assert record.parent == ws / ".architect-team" / "releases" and record.name.startswith("unlock-")
    payload = json.loads(record.read_text(encoding="utf-8"))
    assert payload["schema"] == "ct6-unlock/v1" and payload["reason"] == "good enough, move on with what you have"
    assert payload["session_id"] == SESSION and len(payload["before"]["holds"]) == 4 and payload["after"]["holds"] == []
    # tasks: retired through the operator verb, reason on the task
    task = json.loads((tasks_root / SESSION / "1.json").read_text(encoding="utf-8"))
    assert task["status"] == "completed" and "good enough" in task["metadata"]["ct6_retired"]["reason"]
    # asks: resolved with the record as evidence
    assert ow.open_ledger_entries(ws) == []
    ledger = json.loads(ow.ledger_path(ws).read_text(encoding="utf-8"))
    assert "releases/unlock-" in ledger["entries"][0]["evidence"]
    # gates: WAIVED, never satisfied
    gates = json.loads((ws / ".architect-team" / "declared-gates.json").read_text(encoding="utf-8"))
    g = gates[0]
    assert g["waived_by"] == "user" and g["waived_at"] and "satisfied_at" not in g
    assert g["evidence_path"].endswith(record.name)
    # run: stood down with the words, guard cleared
    marker = rc.read_marker(ws)
    assert marker["status"] == "stood-down"
    assert "good enough" in (ws / ".architect-team" / "pipeline-stand-down.md").read_text(encoding="utf-8")
    # decisions ledger: one line the homepage can show
    lines = (ws / ".architect-team" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["chosen"] == "/architect-team:unlock"
    assert mod.inspect_holds(ws)["held"] is False


def test_release_needs_the_users_words(mod, ws, tasks_root):
    with pytest.raises(ValueError):
        mod.release(ws, "   ")
    assert not (ws / ".architect-team" / "releases").exists()


def test_dry_run_changes_nothing(mod, ws, tasks_root):
    _full_hold(ws, tasks_root)
    out = mod.release(ws, "just looking", dry_run=True)
    assert out["record_path"] is None and len(out["would_release"]) == 4
    assert not (ws / ".architect-team" / "releases").exists()
    assert mod.inspect_holds(ws)["held"] is True


def test_scope_limits_the_release(mod, ws, tasks_root):
    _full_hold(ws, tasks_root)
    summary = mod.release(ws, "clear the gates only", scope=["gates"])
    rep = mod.inspect_holds(ws)
    assert rep["gates"]["open"] == [] and rep["gates"]["waived"] == ["converge:codebase-map"]
    assert rep["tasks"]["live"] and rep["asks"] and rep["run"]["status"] == "active"
    assert summary["remaining"], "the other sources are still held and the engine says so"


# --- the Stop arm honours a real waiver and nothing less --------------------------

def test_the_declared_gates_arm_accepts_a_user_waiver_with_a_real_record(mod, audit, ws, tasks_root):
    _declare_gate(ws)
    at = ws / ".architect-team"
    assert audit._audit_declared_gates(at), "open gate blocks before the release"
    mod.release(ws, "good enough", scope=["gates"])
    assert audit._audit_declared_gates(at) == []


@pytest.mark.parametrize("tamper, fragment", [
    (lambda g, ws: g.__setitem__("waived_by", "agent"), "waived_by is not 'user'"),
    (lambda g, ws: g.__setitem__("evidence_path", ".architect-team/declared-gates.json"), "not a release record"),
    (lambda g, ws: g.__setitem__("evidence_path", ".architect-team/releases/unlock-never.json"), "does not exist"),
    (lambda g, ws: g.__delitem__("evidence_path"), "cites no evidence_path"),
    (lambda g, ws: Path(ws, g["evidence_path"]).write_text("  \n", encoding="utf-8"), "EMPTY release record"),
])
def test_a_waiver_without_a_real_record_does_not_hold(mod, audit, ws, tasks_root, tamper, fragment):
    _declare_gate(ws)
    mod.release(ws, "good enough", scope=["gates"])
    path = ws / ".architect-team" / "declared-gates.json"
    gates = json.loads(path.read_text(encoding="utf-8"))
    tamper(gates[0], ws)
    path.write_text(json.dumps(gates), encoding="utf-8")
    violations = audit._audit_declared_gates(ws / ".architect-team")
    assert violations and any(fragment in v for v in violations), violations


def test_a_bare_waived_flag_an_agent_could_write_is_refused(audit, ws):
    _declare_gate(ws)
    path = ws / ".architect-team" / "declared-gates.json"
    gates = json.loads(path.read_text(encoding="utf-8"))
    gates[0]["waived_at"] = "2026-11-09T00:00:00Z"
    path.write_text(json.dumps(gates), encoding="utf-8")
    assert audit._audit_declared_gates(ws / ".architect-team")


# --- Arm 5: the release verb runs only inside the user's command turn --------------

RELEASE_CMD = 'python3 "$CLAUDE_PLUGIN_ROOT/hooks/completion_unlock.py" release --root "$(pwd)" --reason "good enough"'
UNLOCK_PROMPT = ("<command-message>unlock</command-message>\n<command-name>/architect-team:unlock</command-name>\n"
                 "<command-args>good enough, move on</command-args>")


def _transcript(tmp_path: Path, *prompts: str, teammate: bool = False) -> str:
    p = tmp_path / "t.jsonl"
    lines = []
    for i, text in enumerate(prompts):
        if teammate and i == 0:
            text = f"[CT6-TEAMMATE backend RUN slug]\n{text}"
        lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": text},
                                 "timestamp": f"2026-11-09T00:0{i}:00Z"}))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def _bash(command: str, transcript: str | None, cwd: Path) -> dict:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    if transcript:
        payload["transcript_path"] = transcript
    return payload


def test_arm5_allows_the_release_inside_the_users_command_turn(gate, tmp_path, tasks_root):
    code, _ = gate.check_payload(_bash(RELEASE_CMD, _transcript(tmp_path, "finish it", UNLOCK_PROMPT), tmp_path))
    assert code == 0


@pytest.mark.parametrize("prompts, why", [
    (("please finish the run",), "not the /architect-team:unlock command"),
    ((UNLOCK_PROMPT, "actually keep going"), "not the /architect-team:unlock command"),
])
def test_arm5_refuses_the_release_from_any_other_turn(gate, tmp_path, tasks_root, prompts, why):
    code, msg = gate.check_payload(_bash(RELEASE_CMD, _transcript(tmp_path, *prompts), tmp_path))
    assert code == 2 and why in msg and "USER's verb" in msg


def test_arm5_fails_closed_without_a_transcript(gate, tmp_path, tasks_root):
    code, msg = gate.check_payload(_bash(RELEASE_CMD, None, tmp_path))
    assert code == 2 and "no transcript" in msg


def test_arm5_refuses_a_teammate_session(gate, tmp_path, tasks_root):
    code, msg = gate.check_payload(_bash(RELEASE_CMD, _transcript(tmp_path, UNLOCK_PROMPT, teammate=True), tmp_path))
    assert code == 2 and "teammate or subagent" in msg


def test_arm5_never_gates_inspect_or_status(gate, tmp_path, tasks_root):
    for verb in ("inspect", "status"):
        cmd = RELEASE_CMD.replace("release", verb)
        code, _ = gate.check_payload(_bash(cmd, _transcript(tmp_path, "what holds this?"), tmp_path))
        assert code == 0, verb


def test_arm5_kill_switch_is_the_humans(gate, tmp_path, tasks_root, monkeypatch):
    monkeypatch.setenv("CT6_UNLOCK_GATE_DISABLED", "1")
    code, _ = gate.check_payload(_bash(RELEASE_CMD, _transcript(tmp_path, "finish"), tmp_path))
    assert code == 0


# --- the record is written by the engine, never authored --------------------------

@pytest.mark.parametrize("tool", ["Write", "Edit"])
def test_override_guard_refuses_hand_written_release_records(guard, tmp_path, tool):
    payload = {"tool_name": tool, "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".architect-team" / "releases" / "unlock-1.json"),
                              "content": "{}", "old_string": "a", "new_string": "b"}}
    code, msg = guard.check_payload(payload)
    assert code == 2 and "release record" in msg
    other = dict(payload); other["tool_input"] = {**payload["tool_input"], "file_path": str(tmp_path / "src" / "releases" / "x.json")}
    assert guard.check_payload(other)[0] == 0


# --- the surfaces ------------------------------------------------------------------

def test_the_command_is_the_users_alone():
    fm, body = parse_text((REPO_ROOT / "commands" / "unlock.md").read_text(encoding="utf-8"))
    assert fm.get("disable-model-invocation") in (True, "true")
    assert "completion_unlock.py" in body and "inspect" in body and "release" in body
    assert "AskUserQuestion" in body and "verbatim" in body
    assert "Never propose it" in body


def test_every_agent_carries_the_two_moves():
    core = skill_surface("ct6-agent-core")
    assert "## Held turns (v4.1.0)" in core
    assert "finish that work, or show the user what is open" in core
    assert "/architect-team:unlock" in core and "never yours" in core


def test_the_constitution_stub_points_at_the_chapter():
    conv = skill_surface("common-pipeline-conventions")
    assert "## Completion-hold release (v4.1.0)" in conv
    assert "references/completion-unlock.md" in conv
    chapter = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "references" / "completion-unlock.md").read_text(encoding="utf-8")
    assert "Arm 5" in chapter and "disable-model-invocation" in chapter and "Honest boundary" in chapter
    index = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "references" / "INDEX.md").read_text(encoding="utf-8")
    assert "| always | `skills/common-pipeline-conventions/references/completion-unlock.md` |" in index


def test_cli_round_trip(ws, tasks_root):
    _full_hold(ws, tasks_root)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    def run(*args):
        return subprocess.run([sys.executable, str(UNLOCK), *args], capture_output=True, text=True, env=env, cwd=str(REPO_ROOT))

    insp = run("inspect", "--root", str(ws), "--json")
    assert insp.returncode == 0 and json.loads(insp.stdout)["held"] is True
    blank = run("release", "--root", str(ws), "--reason", "  ")
    assert blank.returncode == 2
    rel = run("release", "--root", str(ws), "--reason", "good enough, move on with what you have")
    assert rel.returncode == 0 and "released:" in rel.stdout and "record:" in rel.stdout, rel.stderr
    st = run("status", "--root", str(ws), "--json")
    rows = json.loads(st.stdout)
    assert len(rows) == 1 and rows[0]["reason"].startswith("good enough")
    again = run("inspect", "--root", str(ws))
    assert again.stdout.startswith("held: no")


def test_module_is_ascii_and_stdlib():
    src = UNLOCK.read_text(encoding="utf-8")
    src.encode("ascii")
    allowed = {"__future__", "argparse", "contextlib", "io", "json", "sys", "pathlib", "typing",
               "hooks", "open_work", "run_continuity", "decisions_ledger", "shared_util"}
    import ast
    for node in ast.walk(ast.parse(src)):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        for mod in names:
            assert mod in allowed, mod
