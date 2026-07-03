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
    code, msg = check_payload(_payload(t, tool="Edit"))
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


def test_blocks_build_and_dispatch_tools_allows_setup_tools(tmp_path: Path) -> None:
    # v3.15.1: only build/dispatch tools gate before the Skill; read-only
    # investigation + the command wrapper's Bash setup do NOT.
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
    ])
    for tool in ("Edit", "Write", "NotebookEdit", "Agent", "Task", "TaskCreate", "TaskUpdate", "TaskStop"):
        code, _ = check_payload(_payload(t, tool=tool))
        assert code == 2, f"{tool} (build/dispatch) should be blocked while the mandate is pending"
    for tool in ("Read", "Bash", "Grep", "Glob", "ToolSearch", "WebFetch", "TodoWrite"):
        code, _ = check_payload(_payload(t, tool=tool))
        assert code == 0, f"{tool} (investigation/wrapper) must NOT be blocked"


def test_wrapper_banner_bash_before_skill_is_allowed(tmp_path: Path) -> None:
    # REGRESSION (v3.15.1): the exact server scenario — /architect-team invoked,
    # the model runs the command's documented FIRST step (the dispatch banner, a
    # Bash call) BEFORE the Skill. The gate must NOT block it (it previously did,
    # with a `*` matcher that blocked every non-Skill tool).
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
    ])
    banner_payload = {
        "tool_name": "Bash",
        "transcript_path": str(t),
        "tool_input": {"command": "python3 -c 'from teams_mode import format_dispatch_banner'"},
    }
    assert check_payload(banner_payload)[0] == 0
    # ToolSearch (schema lookups) likewise allowed before the Skill
    assert check_payload(_payload(t, tool="ToolSearch"))[0] == 0
    # but actually BUILDING (Edit) before the Skill is still blocked
    assert check_payload(_payload(t, tool="Edit"))[0] == 2


def test_known_limitation_bash_and_sendmessage_not_blocked(tmp_path: Path) -> None:
    # Documents the INTENTIONAL design choices (so a future maintainer doesn't
    # "fix" them and reintroduce the over-fire):
    #  - SendMessage (teammate-to-teammate) is not a build/dispatch-by-hand vector
    #    and is not blocked.
    #  - KNOWN LIMITATION: a Bash-mediated file write before the Skill is allowed
    #    (Bash can't be blocked without breaking the wrapper); backstopped by the
    #    after-the-fact Layer-6 audit.
    t = _write(tmp_path, [
        _user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z"),
    ])
    assert check_payload(_payload(t, tool="SendMessage"))[0] == 0
    bash_write = {"tool_name": "Bash", "transcript_path": str(t),
                  "tool_input": {"command": "cat > feature.py <<'EOF'\nx=1\nEOF"}}
    assert check_payload(bash_write)[0] == 0  # known, documented limitation


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
    code, msg = check_payload(_payload(t, tool="Edit"))
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
    code, _ = check_payload(_payload(pend, tool="Edit"))
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
    assert check_payload(_payload(pend, tool="Edit"))[0] == 2
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
    assert check_payload(_payload(pend, tool="Edit"))[0] == 2

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
    assert check_payload(_payload(t, tool="Edit"))[0] == 2


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
    assert check_payload(_payload(t, tool="Edit"))[0] == 2


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
    assert check_payload(_payload(t, tool="Edit"))[0] == 2


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
    assert check_payload({"tool_name": "Edit", "transcript_path": str(p)})[0] == 2


def test_tail_read_on_large_transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hooks.pretool_skill_gate as gate
    monkeypatch.setattr(gate, "_TAIL_BYTES", 400)
    filler = [_tool_result(f"2026-06-16T09:{i % 60:02d}:00Z") for i in range(80)]
    recs = filler + [_user(_command_text("architect-team:architect-team"), "2026-06-16T10:00:00Z")]
    t = _write(tmp_path, recs)
    assert t.stat().st_size > 400  # force the tail path
    assert check_payload(_payload(t, tool="Edit"))[0] == 2


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
    res = _run_hook(_payload(t, tool="Edit"))
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


# --------------------------------------------------------------------------- #
# arm 2 (v3.30.0): the sticky active-run check + deterministic engagement
# --------------------------------------------------------------------------- #

from hooks import run_continuity as rc  # noqa: E402
from hooks.pretool_skill_gate import record_engagement  # noqa: E402


def _compact_boundary() -> dict:
    return {"type": "system", "subtype": "compact_boundary"}


def test_sticky_blocks_resumed_session_build_tool(tmp_path: Path) -> None:
    """THE resume gap: marker active, latest prompt is just 'continue' (not a
    pipeline command — arm 1 stands down), no Skill in this session => build
    tools block until the Skill is re-invoked."""
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    code, msg = check_payload(_payload(t, tool="Edit"))
    assert code == 2, f"resumed hand-build must block; msg={msg!r}"
    assert "run-continuity" in msg
    assert 'Skill(skill="architect-team-pipeline")' in msg
    assert "--stand-down" in msg
    # read-only investigation and the wrapper's Bash setup stay open
    assert check_payload(_payload(t, tool="Read"))[0] == 0
    assert check_payload(_payload(t, tool="Bash"))[0] == 0
    # and the Skill tool itself is always allowed (the resolution path)
    assert check_payload(_payload(t, tool="Skill"))[0] == 0


def test_sticky_open_once_session_engages(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    t = _write(tmp_path, [
        _user("continue", "2026-07-03T10:00:00Z"),
        _skill_call("architect-team:architect-team-pipeline", "2026-07-03T10:00:05Z"),
    ])
    assert check_payload(_payload(t, tool="Edit"))[0] == 0
    assert check_payload(_payload(t, tool="Agent"))[0] == 0


def test_sticky_requires_reinvocation_after_compact(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "bug-fix-pipeline")
    base = [
        _user(_command_text("architect-team:bug-fix"), "2026-07-03T09:00:00Z"),
        _skill_call("bug-fix-pipeline", "2026-07-03T09:00:05Z"),
        _compact_boundary(),
        _user("keep going", "2026-07-03T11:00:00Z"),
    ]
    t = _write(tmp_path, base)
    code, msg = check_payload(_payload(t, tool="Write"))
    assert code == 2, "post-compact the playbook is gone; a build tool must wait for re-invocation"
    assert 'Skill(skill="bug-fix-pipeline")' in msg
    t2 = _write(tmp_path, base + [_skill_call("bug-fix-pipeline", "2026-07-03T11:00:10Z")], name="t2.jsonl")
    assert check_payload(_payload(t2, tool="Write"))[0] == 0


def test_sticky_stands_down_for_teammates(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    token = _write(tmp_path, [
        _user("[CT6-TEAMMATE backend RUN my-feature]\nYour tasks: T1, T2...", "2026-07-03T10:00:00Z"),
    ], name="teammate.jsonl")
    assert check_payload(_payload(token, tool="Edit"))[0] == 0
    brief = ("You are the frontend teammate. " * 70
             + "Write evidence to .architect-team/reviews/T3.json before completing.")
    legacy = _write(tmp_path, [_user(brief, "2026-07-03T10:00:00Z")], name="legacy.jsonl")
    assert check_payload(_payload(legacy, tool="Edit"))[0] == 0


def test_sticky_stands_down_for_sidechain_transcripts(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    t = _write(tmp_path, [_sidechain_user("subagent work item", "2026-07-03T10:00:00Z")])
    assert check_payload(_payload(t, tool="Edit"))[0] == 0


def test_sticky_ignores_complete_and_stood_down_markers(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.mark_complete(tmp_path)
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    assert check_payload(_payload(t, tool="Edit"))[0] == 0
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.stand_down(tmp_path, "user said work by hand")
    assert check_payload(_payload(t, tool="Edit"))[0] == 0


def test_sticky_requires_explicit_payload_cwd(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    payload = {"tool_name": "Edit", "transcript_path": str(t)}  # no cwd
    assert check_payload(payload)[0] == 0, "no explicit cwd => never consult ambient state"


def test_sticky_kill_switch(tmp_path: Path, monkeypatch) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    monkeypatch.setenv(rc.DISABLE_ENV, "1")
    assert check_payload(_payload(t, tool="Edit"))[0] == 0


def test_arm1_takes_precedence_over_sticky_message(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    t = _write(tmp_path, [_user(_command_text("architect-team:architect-team"), "2026-07-03T10:00:00Z")])
    code, msg = check_payload(_payload(t, tool="Edit"))
    assert code == 2
    assert "pipeline command that mandates a Skill" in msg, "arm 1 message wins on a pending mandate"


def test_record_engagement_writes_marker(tmp_path: Path) -> None:
    t = _write(tmp_path, [_user("<command-name>/architect-team:architect-team</command-name> build", "2026-07-03T10:00:00Z")])
    payload = {
        "tool_name": "Skill",
        "tool_input": {"skill": "architect-team:architect-team-pipeline"},
        "transcript_path": str(t),
        "cwd": str(tmp_path),
        "session_id": "sess-42",
    }
    record_engagement(payload)
    m = rc.read_marker(tmp_path)
    assert m is not None and m["status"] == "active"
    assert m["skill"] == "architect-team-pipeline"
    assert m["session_id"] == "sess-42"


def test_record_engagement_ignores_non_run_driving_skills(tmp_path: Path) -> None:
    t = _write(tmp_path, [_user("hello", "2026-07-03T10:00:00Z")])
    for skill in ("proposal-refiner", "data-dictionary", "closeout"):
        record_engagement({
            "tool_name": "Skill", "tool_input": {"skill": skill},
            "transcript_path": str(t), "cwd": str(tmp_path),
        })
    assert rc.read_marker(tmp_path) is None


def test_record_engagement_requires_cwd_and_user_session(tmp_path: Path) -> None:
    t = _write(tmp_path, [_user("go", "2026-07-03T10:00:00Z")])
    record_engagement({  # no cwd
        "tool_name": "Skill", "tool_input": {"skill": "architect-team-pipeline"},
        "transcript_path": str(t),
    })
    assert rc.read_marker(tmp_path) is None
    teammate = _write(tmp_path, [
        _user("[CT6-TEAMMATE qa RUN x]\ntasks...", "2026-07-03T10:00:00Z"),
    ], name="tm.jsonl")
    record_engagement({
        "tool_name": "Skill", "tool_input": {"skill": "architect-team-pipeline"},
        "transcript_path": str(teammate), "cwd": str(tmp_path),
    })
    assert rc.read_marker(tmp_path) is None, "a teammate session never engages the run marker"


def test_subprocess_sticky_block_end_to_end(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    res = _run_hook(_payload(t, tool="Edit"))
    assert res.returncode == 2
    assert b"run-continuity" in res.stderr


# --------------------------------------------------------------------------- #
# v3.30.0 adversarial-review remediations (sticky arm + engagement recording)
# --------------------------------------------------------------------------- #

def test_sticky_stands_down_during_escalation_pause(tmp_path: Path) -> None:
    """Remediation #3a: escalation-pending.md is the sanctioned human-decision
    pause — the human may direct hand-edits to resolve the very blocker, so
    the sticky arm must stand down exactly like the Stop guard does."""
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    (tmp_path / ".architect-team" / "escalation-pending.md").write_text(
        "waiting on the human", encoding="utf-8")
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    assert check_payload(_payload(t, tool="Edit"))[0] == 0


def test_sticky_stands_down_on_stale_marker(tmp_path: Path) -> None:
    """Remediation #3b: an abandoned run's marker must not tax the workspace
    forever — staleness stands the sticky arm down."""
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    m = rc.read_marker(tmp_path)
    m["updated_at"] = "2020-01-01T00:00:00+00:00"
    rc._atomic_write_json(rc.marker_path(tmp_path), m)
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    assert check_payload(_payload(t, tool="Edit"))[0] == 0


def test_pretooluse_skill_does_not_engage_marker(tmp_path: Path) -> None:
    """Remediation #2: engagement is recorded at PostToolUse (the Skill RAN),
    never at PreToolUse (a denied/errored call must not write a phantom
    active marker)."""
    t = _write(tmp_path, [_user("go", "2026-07-03T10:00:00Z")])
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Skill",
        "tool_input": {"skill": "architect-team-pipeline"},
        "transcript_path": str(t),
        "cwd": str(tmp_path),
    }
    res = _run_hook(payload)
    assert res.returncode == 0
    assert rc.read_marker(tmp_path) is None, "PreToolUse must not engage"
    payload["hook_event_name"] = "PostToolUse"
    res = _run_hook(payload)
    assert res.returncode == 0
    m = rc.read_marker(tmp_path)
    assert m is not None and m["status"] == "active", "PostToolUse engages"


def test_posttooluse_nonskill_never_blocks_or_engages(tmp_path: Path) -> None:
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    rc.mark_complete(tmp_path)
    t = _write(tmp_path, [_user("continue", "2026-07-03T10:00:00Z")])
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "transcript_path": str(t),
        "cwd": str(tmp_path),
    }
    res = _run_hook(payload)
    assert res.returncode == 0
    assert rc.read_marker(tmp_path)["status"] == "complete", (
        "a PostToolUse payload for a non-Skill tool never touches the marker"
    )


def test_errored_skill_run_does_not_engage(tmp_path: Path) -> None:
    """Re-verify residual: a run-driving Skill whose execution ERRORED must not
    engage the marker (the denied case never reaches PostToolUse at all)."""
    t = _write(tmp_path, [_user("go", "2026-07-03T10:00:00Z")])
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "tool_input": {"skill": "architect-team-pipeline"},
        "tool_response": {"is_error": True, "error": "skill not found"},
        "transcript_path": str(t),
        "cwd": str(tmp_path),
    }
    record_engagement(payload)
    assert rc.read_marker(tmp_path) is None, "an errored Skill run must not engage"
    payload["tool_response"] = {"content": "skill body loaded"}
    record_engagement(payload)
    assert rc.read_marker(tmp_path) is not None, "a successful run engages"
