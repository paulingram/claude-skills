"""Tests for the PreToolUse hard-gate (real-time skill-invocation enforcement).

`hooks/pretool_skill_gate.py` upgrades the Layer-6 skill-invocation audit from
after-the-fact DETECTION to real-time PREVENTION: when the session transcript's
most-recent genuine user prompt is an unsatisfied pipeline-command request, the
hook BLOCKS (exit 2) the first non-Skill tool call until a matching Skill call
appears.

Coverage:
  - gate CLOSED on an unsatisfied pipeline command; OPEN after a matching Skill
  - the Skill tool itself is always allowed
  - plugin-prefixed skill names satisfy (architect-team:architect-team-pipeline)
  - user-precedence: a NEW request needs its OWN Skill call (ts ordering)
  - self-clearing escape: a non-pipeline follow-up prompt stands the gate down
  - prose form ("use the architect team") gates; non-pipeline commands do NOT
  - fail-open: no transcript / missing file / garbled JSONL / internal error
  - the REAL nested Claude Code transcript shape (message.content string + blocks)
  - universality: no codebase-specific strings / absolute paths in the hook
  - wiring: hooks.json registers PreToolUse[*] -> the hook via CLAUDE_PLUGIN_ROOT
  - reuse: the hook imports detection from skill_invocation_audit
  - end-to-end: the hook as a subprocess blocks / allows / fails open under cp1252
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hooks.pretool_skill_gate import check_payload

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pretool_skill_gate.py"


# --------------------------------------------------------------------------- #
# transcript-record builders (the REAL nested Claude Code shape)
# --------------------------------------------------------------------------- #

def _user(text: str, ts: str, user_type: str = "external") -> dict:
    return {
        "type": "user",
        "userType": user_type,
        "timestamp": ts,
        "message": {"role": "user", "content": text},
    }


def _user_blocks(blocks: list, ts: str, user_type: str = "external") -> dict:
    return {
        "type": "user",
        "userType": user_type,
        "timestamp": ts,
        "message": {"role": "user", "content": blocks},
    }


def _skill_call(skill: str, ts: str) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": skill}}],
        },
    }


def _tool_result(ts: str) -> dict:
    # role=user but content is a tool_result block (NOT a genuine user prompt).
    return {
        "type": "user",
        "userType": "external",
        "timestamp": ts,
        "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]},
    }


def _meta_body(text: str, ts: str) -> dict:
    # the harness echoes the loaded command/skill BODY back as an isMeta user
    # record (same/newer ts, full of pipeline text) right after the Skill call.
    return {"type": "user", "userType": "external", "isMeta": True, "timestamp": ts,
            "message": {"role": "user", "content": text}}


def _system_notification(text: str, ts: str) -> dict:
    return {"type": "user", "userType": "external", "promptSource": "system", "timestamp": ts,
            "message": {"role": "user", "content": text}}


def _sidechain_user(text: str, ts: str) -> dict:
    return {"type": "user", "userType": "external", "isSidechain": True, "timestamp": ts,
            "message": {"role": "user", "content": text}}


def _command_text(plugin_command: str, args: str = "do the thing") -> str:
    """The harness's recorded shape for a slash-command invocation."""
    return (
        f"<command-message>{plugin_command}</command-message>\n"
        f"<command-name>/{plugin_command}</command-name>\n"
        f"<command-args>{args}</command-args>"
    )


def _write(tmp_path: Path, records: list[dict], name: str = "transcript.jsonl") -> Path:
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return p


def _payload(transcript: Path, tool: str = "Read") -> dict:
    return {"tool_name": tool, "transcript_path": str(transcript), "cwd": str(transcript.parent)}


# --------------------------------------------------------------------------- #
# core gate behaviour
# --------------------------------------------------------------------------- #

def test_dormant_when_no_pipeline_request(tmp_path: Path) -> None:
    t = _write(tmp_path, [_user("please refactor the parser", "2026-06-16T10:00:00Z")])
    code, msg = check_payload(_payload(t))
    assert code == 0 and msg == ""


def test_blocks_unsatisfied_pipeline_command(tmp_path: Path) -> None:
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
    ])
    code, msg = check_payload(_payload(t, tool="Read"))
    assert code == 2
    assert "BLOCKED" in msg
    assert "architect-team-pipeline" in msg


def test_opens_after_matching_skill(tmp_path: Path) -> None:
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _skill_call("architect-team-pipeline", "2026-06-16T10:00:05Z"),
    ])
    code, msg = check_payload(_payload(t, tool="Read"))
    assert code == 0 and msg == ""


def test_opens_after_plugin_prefixed_skill(tmp_path: Path) -> None:
    # The harness may record the plugin-prefixed skill name.
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _skill_call("architect-team:architect-team-pipeline", "2026-06-16T10:00:05Z"),
    ])
    code, _ = check_payload(_payload(t, tool="Bash"))
    assert code == 0


def test_skill_tool_always_allowed_even_with_pending_mandate(tmp_path: Path) -> None:
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
    ])
    code, msg = check_payload(_payload(t, tool="Skill"))
    assert code == 0 and msg == ""


def test_blocks_every_non_skill_tool(tmp_path: Path) -> None:
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
    ])
    for tool in ("Read", "Bash", "Edit", "Write", "Grep", "Glob", "Agent", "TodoWrite"):
        code, _ = check_payload(_payload(t, tool=tool))
        assert code == 2, f"{tool} should be blocked while the mandate is pending"


# --------------------------------------------------------------------------- #
# user-precedence (a NEW request needs its OWN Skill call)
# --------------------------------------------------------------------------- #

def test_user_precedence_new_request_needs_new_skill(tmp_path: Path) -> None:
    # request#1 satisfied by a Skill call, THEN a new request#2 with no Skill
    # after it -> the stale earlier Skill call must NOT satisfy request#2.
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _skill_call("architect-team-pipeline", "2026-06-16T10:00:05Z"),
        _tool_result("2026-06-16T10:00:06Z"),
        _user(_command_text("architect-team:bug-fix"), "2026-06-16T11:00:00Z"),
    ])
    code, msg = check_payload(_payload(t, tool="Read"))
    assert code == 2
    assert "bug-fix-pipeline" in msg


def test_satisfaction_persists_across_a_long_run(tmp_path: Path) -> None:
    # command -> Skill -> many later tool-result records (no new user prompt):
    # the gate stays OPEN because the command is still satisfied.
    records = [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _skill_call("architect-team-pipeline", "2026-06-16T10:00:05Z"),
    ]
    for i in range(20):
        records.append(_tool_result(f"2026-06-16T10:0{1+i//10}:{i%60:02d}Z"))
    t = _write(tmp_path, records)
    code, _ = check_payload(_payload(t, tool="Edit"))
    assert code == 0


# --------------------------------------------------------------------------- #
# self-clearing escape + prose + non-pipeline commands
# --------------------------------------------------------------------------- #

def test_nonpipeline_followup_prompt_stands_gate_down(tmp_path: Path) -> None:
    # An unsatisfied command, THEN the user sends a plain follow-up that is NOT
    # a pipeline command -> the most-recent prompt has no request -> allow.
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _user("actually never mind, just answer my question in chat", "2026-06-16T10:05:00Z"),
    ])
    code, _ = check_payload(_payload(t, tool="Read"))
    assert code == 0


def test_prose_form_blocks_then_opens(tmp_path: Path) -> None:
    pend = _write(tmp_path, [
        _user("please use the architect team to build the dashboard", "2026-06-16T10:00:00Z"),
    ], name="pend.jsonl")
    code, _ = check_payload(_payload(pend, tool="Read"))
    assert code == 2

    ok = _write(tmp_path, [
        _user("please use the architect team to build the dashboard", "2026-06-16T10:00:00Z"),
        _skill_call("architect-team-pipeline", "2026-06-16T10:00:09Z"),
    ], name="ok.jsonl")
    code, _ = check_payload(_payload(ok, tool="Read"))
    assert code == 0


@pytest.mark.parametrize("plugin_command", [
    "architect-team:status",
    "architect-team:memory",
    "architect-team:discipline-status",
])
def test_nonpipeline_plugin_commands_not_gated(tmp_path: Path, plugin_command: str) -> None:
    t = _write(tmp_path, [_user(_command_text(plugin_command), "2026-06-16T10:00:00Z")])
    code, _ = check_payload(_payload(t, tool="Read"))
    assert code == 0


def test_builtin_repl_commands_not_gated(tmp_path: Path) -> None:
    t = _write(tmp_path, [_user(
        "<command-name>/effort</command-name>\n<command-args>max</command-args>",
        "2026-06-16T10:00:00Z",
    )])
    code, _ = check_payload(_payload(t, tool="Read"))
    assert code == 0


def test_bug_fix_command_gated_and_satisfied_by_bugfix_skill(tmp_path: Path) -> None:
    pend = _write(tmp_path, [
        _user(_command_text("architect-team:bug-fix"), "2026-06-16T10:00:00Z"),
    ], name="bf_pend.jsonl")
    assert check_payload(_payload(pend, tool="Read"))[0] == 2
    ok = _write(tmp_path, [
        _user(_command_text("architect-team:bug-fix"), "2026-06-16T10:00:00Z"),
        _skill_call("bug-fix-pipeline", "2026-06-16T10:00:03Z"),
    ], name="bf_ok.jsonl")
    assert check_payload(_payload(ok, tool="Read"))[0] == 0


# --------------------------------------------------------------------------- #
# fail-open safety
# --------------------------------------------------------------------------- #

def test_failopen_no_transcript_path() -> None:
    assert check_payload({"tool_name": "Read"}) == (0, "")


def test_failopen_missing_transcript_file(tmp_path: Path) -> None:
    code, _ = check_payload({"tool_name": "Read", "transcript_path": str(tmp_path / "nope.jsonl")})
    assert code == 0


def test_failopen_garbled_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "garbled.jsonl"
    p.write_text("not json\n{broken\n\n{}\n", encoding="utf-8")
    code, _ = check_payload({"tool_name": "Read", "transcript_path": str(p)})
    assert code == 0


def test_failopen_empty_payload() -> None:
    assert check_payload({}) == (0, "")


# --------------------------------------------------------------------------- #
# the REAL nested transcript shape (string content + content blocks)
# --------------------------------------------------------------------------- #

def test_real_nested_shape_blocks_and_opens(tmp_path: Path) -> None:
    # exactly the shape observed in a live Claude Code transcript: top-level
    # type/timestamp/userType + nested message.{role,content}; command recorded
    # as a string content with <command-name> markers.
    pend = _write(tmp_path, [
        {"type": "user", "userType": "external", "timestamp": "2026-06-16T10:00:00Z",
         "message": {"role": "user", "content": _command_text("architect-team:architect-team")}},
    ], name="nested_pend.jsonl")
    assert check_payload(_payload(pend, tool="Read"))[0] == 2

    opened = _write(tmp_path, [
        {"type": "user", "userType": "external", "timestamp": "2026-06-16T10:00:00Z",
         "message": {"role": "user", "content": _command_text("architect-team:architect-team")}},
        {"type": "assistant", "timestamp": "2026-06-16T10:00:04Z",
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": "Loading the pipeline."},
             {"type": "tool_use", "name": "Skill", "input": {"skill": "architect-team:architect-team-pipeline"}},
         ]}},
    ], name="nested_open.jsonl")
    assert check_payload(_payload(opened, tool="Read"))[0] == 0


def test_user_text_in_content_blocks(tmp_path: Path) -> None:
    # content as a list of text blocks (rather than a bare string)
    t = _write(tmp_path, [
        _user_blocks([{"type": "text", "text": _command_text("architect-team:architect-team")}],
                     "2026-06-16T10:00:00Z"),
    ])
    assert check_payload(_payload(t, tool="Read"))[0] == 2


# --------------------------------------------------------------------------- #
# injected / meta record exclusion (the BRICK regressions — modelled on real
# Claude Code transcript behaviour, found by adversarial review against two
# real transcripts)
# --------------------------------------------------------------------------- #

def test_ismeta_body_echo_after_skill_does_not_reblock(tmp_path: Path) -> None:
    # REGRESSION: after the model CORRECTLY invokes the Skill, the harness echoes
    # the loaded command/skill BODY back as an isMeta:true user record with a
    # NEWER timestamp, full of pipeline text. That body must NOT become the anchor
    # / re-raise the mandate / make the just-made Skill call look stale.
    body = ("# Architect-Team Orchestration\n\nUse /architect-team:architect-team ...\n"
            "Invoke the architect-team-pipeline skill via the Skill tool ...")
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00.000Z"),
        _skill_call("architect-team:architect-team-pipeline", "2026-06-16T10:00:05.057Z"),
        _meta_body(body, "2026-06-16T10:00:05.071Z"),     # +14ms, isMeta -> excluded
        _tool_result("2026-06-16T10:00:06.000Z"),
    ])
    for tool in ("Read", "Bash", "Edit", "Grep"):
        code, msg = check_payload(_payload(t, tool=tool))
        assert code == 0, f"isMeta body-echo wrongly re-blocked {tool}: {msg[:120]!r}"


def test_lone_ismeta_record_does_not_gate(tmp_path: Path) -> None:
    t = _write(tmp_path, [_meta_body(_command_text("architect-team:architect-team"),
                                     "2026-06-16T10:00:00Z")])
    assert check_payload(_payload(t, tool="Read"))[0] == 0


def test_system_task_notification_does_not_gate(tmp_path: Path) -> None:
    t = _write(tmp_path, [_system_notification(
        "<task-notification>subagent: use /architect-team:bug-fix and bug-fix-pipeline"
        "</task-notification>", "2026-06-16T10:00:00Z")])
    assert check_payload(_payload(t, tool="Read"))[0] == 0


def test_sidechain_record_does_not_gate(tmp_path: Path) -> None:
    # subagent transcript — cannot call the user-facing Skill; must never block
    t = _write(tmp_path, [_sidechain_user(_command_text("architect-team:architect-team"),
                                          "2026-06-16T10:00:00Z")])
    assert check_payload(_payload(t, tool="Read"))[0] == 0


def test_genuine_command_still_anchors_past_later_meta(tmp_path: Path) -> None:
    # a genuine UNSATISFIED command followed by an isMeta body echo: still blocks
    # (the echo is excluded, the genuine command remains the anchor, unsatisfied).
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _meta_body("# body ... architect-team-pipeline ...", "2026-06-16T10:00:00Z"),
    ])
    assert check_payload(_payload(t, tool="Read"))[0] == 2


# --------------------------------------------------------------------------- #
# satisfaction matching precision (no substring false-satisfy)
# --------------------------------------------------------------------------- #

def test_any_pipeline_skill_engagement_satisfies(tmp_path: Path) -> None:
    # The gate prevents driving-by-hand, not tier mismatch: engaging ANY pipeline
    # skill after a pipeline command satisfies the mandate. This is what lets the
    # documented first step of /architect-team (invoke proposal-refiner, THEN the
    # pipeline) avoid a false block in the refinement window — the real case
    # observed in transcript 468083f2.
    for skill in ("proposal-refiner", "architect-team:proposal-refiner",
                  "mini-architect-team-pipeline"):
        t = _write(tmp_path, [
            _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
            _skill_call(skill, "2026-06-16T10:00:05Z"),
        ], name=f"eng_{skill.replace(':', '_')}.jsonl")
        assert check_payload(_payload(t, tool="Read"))[0] == 0, f"{skill} should satisfy engagement"


def test_nonpipeline_skill_with_substring_name_does_not_satisfy(tmp_path: Path) -> None:
    # a skill that merely CONTAINS a pipeline name as a substring (but is not a
    # pipeline skill) must NOT satisfy — satisfaction is exact/base, never a
    # loose substring (the Finding-4 fix).
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _skill_call("some-architect-team-pipeline-helper", "2026-06-16T10:00:05Z"),
    ])
    assert check_payload(_payload(t, tool="Read"))[0] == 2


def test_mini_command_satisfied_by_mini_skill(tmp_path: Path) -> None:
    # the mini command IS satisfied by the mini skill (exact/base match holds)
    t = _write(tmp_path, [
        _user(_command_text("architect-team:mini"), "2026-06-16T10:00:00Z"),
        _skill_call("architect-team:mini-architect-team-pipeline", "2026-06-16T10:00:05Z"),
    ])
    assert check_payload(_payload(t, tool="Read"))[0] == 0


# --------------------------------------------------------------------------- #
# transcript read branches (array form + tail-read on a large transcript)
# --------------------------------------------------------------------------- #

def test_json_array_transcript_form(tmp_path: Path) -> None:
    p = tmp_path / "arr.json"
    p.write_text(json.dumps([_user(_command_text("architect-team:architect-team"),
                                   "2026-06-16T10:00:00Z")]), encoding="utf-8")
    assert check_payload({"tool_name": "Read", "transcript_path": str(p)})[0] == 2


def test_tail_read_on_large_transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hooks.pretool_skill_gate as gate
    monkeypatch.setattr(gate, "_TAIL_BYTES", 400)
    filler = [_tool_result(f"2026-06-16T09:{i % 60:02d}:00Z") for i in range(80)]
    recs = filler + [_user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z")]
    t = _write(tmp_path, recs)
    assert t.stat().st_size > 400  # force the tail path
    assert check_payload(_payload(t, tool="Read"))[0] == 2


# --------------------------------------------------------------------------- #
# universality (no codebase-specific strings / absolute paths)
# --------------------------------------------------------------------------- #

def test_hook_has_no_codebase_specific_strings() -> None:
    src = HOOK.read_text(encoding="utf-8")
    lowered = src.lower()
    # specific codebases / users / apps that must never be hardcoded
    for token in ("claude_skill_lib", "claude-skill-lib", "cannonical", "blackraven",
                  "/home/", "/users/", "c:\\", "paulingram"):
        assert token not in lowered, f"codebase-specific token leaked into the hook: {token!r}"


def test_hook_has_no_absolute_paths() -> None:
    import re
    src = HOOK.read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:[\\/]{1,2}Users", src), "absolute Windows path in the hook"
    assert "/home/" not in src and "/Users/" not in src


def test_hook_reuses_skill_invocation_audit_detection() -> None:
    src = HOOK.read_text(encoding="utf-8")
    assert "skill_invocation_audit" in src
    assert "find_skill_requests" in src
    assert "COMMAND_TO_SKILLS" in src


# --------------------------------------------------------------------------- #
# wiring
# --------------------------------------------------------------------------- #

def test_hooks_json_registers_pretool_star() -> None:
    data = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    pretool = data["hooks"]["PreToolUse"]
    star_entries = [e for e in pretool if e.get("matcher") == "*"]
    assert star_entries, "expected a PreToolUse '*' matcher entry for the skill-gate"
    cmds = [h["command"] for e in star_entries for h in e.get("hooks", [])]
    assert any("pretool_skill_gate.py" in c for c in cmds), "skill-gate not wired into PreToolUse[*]"
    # portable wiring only — no absolute paths
    for c in cmds:
        if "pretool_skill_gate.py" in c:
            assert "${CLAUDE_PLUGIN_ROOT}" in c


# --------------------------------------------------------------------------- #
# end-to-end (the hook as a subprocess — actually executed)
# --------------------------------------------------------------------------- #

def _run_hook(payload: dict, encoding: str = "utf-8") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "0" if encoding != "utf-8" else "1"
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        cwd=str(REPO_ROOT),
        capture_output=True,
        env=env,
        timeout=60,
    )


def test_subprocess_blocks_unsatisfied(tmp_path: Path) -> None:
    t = _write(tmp_path, [_user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z")])
    res = _run_hook(_payload(t, tool="Read"))
    assert res.returncode == 2
    assert b"BLOCKED" in res.stderr


def test_subprocess_allows_after_skill(tmp_path: Path) -> None:
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
        _skill_call("architect-team-pipeline", "2026-06-16T10:00:05Z"),
    ])
    res = _run_hook(_payload(t, tool="Read"))
    assert res.returncode == 0


def test_subprocess_failopen_on_cp1252_with_utf8_payload(tmp_path: Path) -> None:
    # a UTF-8 payload (emoji) under a non-UTF8 interpreter must not traceback;
    # benign/non-matching payload fail-opens to exit 0.
    payload = {"tool_name": "Read", "transcript_path": str(tmp_path / "x.jsonl"), "note": "🚀"}
    res = _run_hook(payload, encoding="cp1252")
    assert res.returncode == 0
    assert b"Traceback" not in res.stderr
