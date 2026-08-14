"""v3.61.0 — the task-deletion arm (`hooks/pretool_skill_gate.py`).

`TaskUpdate(status="deleted")` unlinks the harness task file, and the
completion lock reads that store as ground truth — so deletion during an
ACTIVE run releases the lock without the work closing. That was a NAMED
v3.56.0 honest boundary; this arm closes its tool-layer half.

Design constraints, each pinned below:

* fires on the payload alone (tool_name + tool_input + cwd + marker) — NO
  transcript dependence, so a missing/empty transcript cannot disarm it
  (the F7 null-session lesson: absent evidence must not stand a gate down);
* scoped to an ACTIVE, non-stale run marker in the payload's cwd — plain
  sessions and abandoned runs are untouched;
* `status: "completed"` stays fully legitimate — the arm narrows nothing
  about the honest path;
* `escalation-pending.md` does NOT stand it down: the pause file is
  agent-writable (ADV-1), so honouring it would be a two-step escape;
* its own kill-switch `CT6_TASK_DELETE_GATE_DISABLED`, and deliberately NOT
  `CT6_RUN_CONTINUITY_DISABLED` — one switch muting another gate is the F12
  undocumented-extra-kill-switch defect;
* blocks a TOOL CALL, never a Stop — there is no wedge: `completed` is
  always available, so no lane can be stuck on this arm.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.pretool_skill_gate import check_payload


def _marker(ws: Path, status: str = "active", *, started_ago: float = 60.0) -> None:
    import time

    at = ws / ".architect-team"
    at.mkdir(parents=True, exist_ok=True)
    started = time.time() - started_ago
    import datetime as _d

    iso = _d.datetime.fromtimestamp(started, _d.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    (at / "active-run.json").write_text(
        json.dumps({"status": status, "slug": "demo", "started_at": iso,
                    "last_progress_at": iso}),
        encoding="utf-8",
    )


def _delete_payload(ws: Path, status: str = "deleted", **extra) -> dict:
    p = {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": "7", "status": status},
        "cwd": str(ws),
    }
    p.update(extra)
    return p


# --- the blocking direction -------------------------------------------------


def test_deletion_during_an_active_run_is_refused(tmp_path: Path) -> None:
    _marker(tmp_path)
    code, msg = check_payload(_delete_payload(tmp_path))
    assert code == 2
    assert "deleted" in msg.lower()
    assert "completed" in msg.lower(), "the message must name the honest path"


def test_no_transcript_does_not_disarm(tmp_path: Path) -> None:
    """The F7 lesson: the arm reads the payload and the marker, not the
    transcript — a session the hook cannot see into is still gated."""
    _marker(tmp_path)
    code, _ = check_payload(_delete_payload(tmp_path, transcript_path=""))
    assert code == 2
    code, _ = check_payload(
        _delete_payload(tmp_path, transcript_path=str(tmp_path / "absent.jsonl"))
    )
    assert code == 2


def test_escalation_pending_does_not_stand_the_arm_down(tmp_path: Path) -> None:
    """`escalation-pending.md` is agent-writable (ADV-1). If it stood this arm
    down, the escape would be two tool calls instead of one."""
    _marker(tmp_path)
    (tmp_path / ".architect-team" / "escalation-pending.md").write_text(
        "awaiting a human", encoding="utf-8"
    )
    code, _ = check_payload(_delete_payload(tmp_path))
    assert code == 2


# --- the standing-down directions --------------------------------------------


def test_completed_is_untouched(tmp_path: Path) -> None:
    _marker(tmp_path)
    code, _ = check_payload(_delete_payload(tmp_path, status="completed"))
    assert code == 0


def test_other_statuses_are_untouched(tmp_path: Path) -> None:
    _marker(tmp_path)
    for status in ("pending", "in_progress"):
        code, _ = check_payload(_delete_payload(tmp_path, status=status))
        assert code == 0, status


def test_no_marker_means_no_gate(tmp_path: Path) -> None:
    code, _ = check_payload(_delete_payload(tmp_path))
    assert code == 0


def test_completed_marker_means_no_gate(tmp_path: Path) -> None:
    _marker(tmp_path, status="complete")
    code, _ = check_payload(_delete_payload(tmp_path))
    assert code == 0


def test_stale_marker_means_no_gate(tmp_path: Path) -> None:
    """An abandoned run must not tax the workspace forever — same rule as the
    sticky arm, same staleness engine (incl. the v3.60.0 one-hour floor)."""
    _marker(tmp_path, started_ago=400 * 3600)  # far beyond any stale window
    code, _ = check_payload(_delete_payload(tmp_path))
    assert code == 0


def test_no_cwd_fails_open(tmp_path: Path) -> None:
    _marker(tmp_path)
    p = _delete_payload(tmp_path)
    del p["cwd"]
    code, _ = check_payload(p)
    assert code == 0


def test_own_kill_switch_releases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _marker(tmp_path)
    monkeypatch.setenv("CT6_TASK_DELETE_GATE_DISABLED", "1")
    code, _ = check_payload(_delete_payload(tmp_path))
    assert code == 0


def test_continuity_switch_does_NOT_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The F12 rule: CT6_RUN_CONTINUITY_DISABLED governs the continuation
    guard. Letting it also mute this arm would make it an undocumented extra
    kill-switch for a gate that documents its own."""
    _marker(tmp_path)
    monkeypatch.setenv("CT6_RUN_CONTINUITY_DISABLED", "1")
    code, _ = check_payload(_delete_payload(tmp_path))
    assert code == 2


def test_message_names_its_own_kill_switch(tmp_path: Path) -> None:
    """F12's other half: a switch that exists must be enumerable from the
    block message, or it is undocumented."""
    _marker(tmp_path)
    _, msg = check_payload(_delete_payload(tmp_path))
    assert "CT6_TASK_DELETE_GATE_DISABLED" in msg


def test_non_deletion_taskupdate_still_hits_arm_one(tmp_path: Path) -> None:
    """The fall-through IS the contract: this arm ADDS to the existing gates,
    never replaces them. The first cut early-returned for every TaskUpdate and
    silently un-gated it from the arm-1 mandate check -- caught by the
    pre-existing arm-1 pin. This test holds the property from THIS file's side
    so both files now cover it independently."""
    transcript = tmp_path / "t.jsonl"
    content = "\n".join([
        "<command-message>architect-team:architect-team</command-message>",
        "<command-name>/architect-team:architect-team</command-name>",
        "<command-args>build the thing</command-args>",
    ])
    transcript.write_text(
        json.dumps({
            "type": "user",
            "message": {"role": "user", "content": content},
            "timestamp": "2026-06-16T10:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )
    payload = {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": "7", "status": "completed"},
        "cwd": str(tmp_path),
        "transcript_path": str(transcript),
    }
    code, msg = check_payload(payload)
    assert code == 2, "a non-deletion TaskUpdate must still gate on the unsatisfied mandate"
    assert "deleted" not in msg.lower(), "and the block must come from arm 1, not arm 3"
