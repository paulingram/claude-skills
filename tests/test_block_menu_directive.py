"""v3.61.2 — the continuation/lock block menu is an agent directive, not a menu.

Field report (2026-08-16, a live run on another machine): a session with a
lingering active-run marker re-printed the full block menu at the USER on
every conversational turn. The agent never acted on it. Three message defects
induced that, each now pinned:

  1. nothing said "do not relay this text to the user" — hook feedback is
     agent-directed by design, and the text never said so;
  2. the mark-complete command carried no ``--root``, so it silently
     depended on the shell's cwd — one failed attempt teaches the agent the
     command "does not work", after which it recites instead of acting;
  3. the menu led with the escalation option's "user must decide" phrasing,
     priming deferral, with the common stuck case (run finished, marker
     never closed) buried last.

The lock composes this same text with no budget, so the repetition had no
ceiling — hence terse-on-repeat: full directive on the first block, a short
form once the caller's existing consecutive counter shows the same block
repeating. No new state files (the F5 lesson) — the guard's no-progress count
and the lock's N5b notify state already exist and are fingerprint-excluded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture(scope="module")
def audit_mod():
    return load_module(AUDIT_SCRIPT, "pca_block_menu")


def _text(audit_mod, *, violations=None, repeat_count=0, root=None):
    return audit_mod._continuation_block_text(
        violations if violations is not None else ["task 7 is open"],
        {"status": "active", "slug": "demo", "skill": "architect-team-pipeline"},
        False,
        None,
        root=root if root is not None else Path("C:/ws/demo"),
        repeat_count=repeat_count,
    )


# --- the agent-directive properties (full form) -------------------------------


def test_block_forbids_relaying_to_the_user(audit_mod) -> None:
    t = _text(audit_mod)
    low = t.lower()
    assert "never print" in low and "to the user" in low, (
        "the block must state it is agent-directed and must not be shown to the user"
    )
    assert "never ask them which option applies" in low or "never ask the user which" in low


def test_mark_complete_command_carries_root(audit_mod) -> None:
    """Defect 2: the command must not depend on the shell's cwd — the hook
    KNOWS the workspace and must say it."""
    t = _text(audit_mod, root=Path("C:/ws/demo"))
    assert "--mark-complete" in t
    assert "--root" in t, "the mark-complete command must carry --root"
    assert "C:/ws/demo" in t.replace("\\", "/"), "the injected root must be THIS workspace"


def test_finished_case_comes_before_the_escalation_case(audit_mod) -> None:
    """Defect 3: the common stuck case leads; the deferral-priming phrasing
    trails.

    Measured INSIDE the decision procedure, not the whole block: the worklist
    above it contains the lifecycle line, which also says `--mark-complete`,
    and the first draft of this test matched THAT occurrence — a pin passing
    for the wrong reason, exposed by mutation witness W5 escaping (the
    demote-mutation moved the real option order and this test stayed green)."""
    t = _text(audit_mod)
    assert "Decide by CHECKING" in t
    procedure = t[t.index("Decide by CHECKING"):]
    finished = procedure.find("--mark-complete")
    escalate = procedure.find("escalation-pending.md")
    assert finished != -1 and escalate != -1
    assert finished < escalate, "finished-case must be option 1, escalation last"


def test_escalation_is_named_the_only_user_facing_case(audit_mod) -> None:
    t = _text(audit_mod).lower()
    assert "only case where the user" in t


def test_finished_case_says_act_yourself(audit_mod) -> None:
    """The exact failure observed live: the agent waited for permission."""
    t = _text(audit_mod).lower()
    assert "yourself" in t and "no human approval" in t


# --- terse-on-repeat -----------------------------------------------------------


def test_first_block_is_the_full_directive(audit_mod) -> None:
    t = _text(audit_mod, repeat_count=1)
    assert "--mark-complete" in t and "escalation-pending.md" in t
    assert len(t) > 900, "the first block carries the full decision procedure"


def test_repeat_blocks_are_terse(audit_mod) -> None:
    t = _text(audit_mod, repeat_count=3)
    assert len(t) < 700, f"a repeated identical block must be terse, got {len(t)} chars"
    assert "#3" in t or "block 3" in t.lower(), "the terse form numbers the repeat"


def test_terse_form_is_still_actionable_and_still_agent_only(audit_mod) -> None:
    """Terse must never cost the two properties that matter: the no-relay rule
    and the copy-pasteable exit."""
    t = _text(audit_mod, repeat_count=5)
    low = t.lower()
    assert "--mark-complete" in t and "--root" in t
    assert "not" in low and "user" in low, "the no-relay rule survives terseness"


def test_terse_form_names_the_worklist_head(audit_mod) -> None:
    """Three violations PLUS the active marker's lifecycle line = 4 open items,
    so the head shows one and the remainder is 3 — the lifecycle line counts,
    because it IS an open item (the run is not marked complete). The first
    draft of this test said '+2 more', silently excluding it."""
    t = _text(audit_mod, violations=["task 7 is open", "task 8 is open", "task 9 is open"],
              repeat_count=4)
    assert "task 7 is open" in t
    assert "+3 more" in t


# --- wiring: both call sites must pass the new arguments -----------------------


def test_both_call_sites_pass_root_and_repeat_count() -> None:
    """Defaulted keywords fail open, so a call site that omits them silently
    loses --root and terseness — the one-of-two-places shape. Pin the source."""
    src = AUDIT_SCRIPT.read_text(encoding="utf-8")
    call_sites = src.count("_continuation_block_text(") - 1  # minus the def
    assert call_sites >= 2, "expected the guard site and the lock-composition site"
    # The def declares `repeat_count: int = 0` (annotation form), so every
    # occurrence of the literal `repeat_count=` is a CALL passing it.
    assert src.count("repeat_count=") >= call_sites, (
        "every _continuation_block_text call site must pass repeat_count explicitly"
    )
    assert src.count("root=root") >= call_sites, (
        "every _continuation_block_text call site must pass root explicitly"
    )


# --- the lock-side feed: _lock_consecutive + end-to-end terseness --------------
#
# The unit tests above pass repeat_count directly, which proves the text
# builder but not the FEED (the v3.59.0 registered-and-nowhere-else lesson: a
# parameter nothing supplies is inert with a green suite). Two closures:
# a unit test on the N5b-state reader, and a real three-stop subprocess run
# proving the third consecutive block arrives terse.


def test_lock_consecutive_reads_the_notify_state(audit_mod, tmp_path: Path) -> None:
    import json as _json
    at = tmp_path / ".architect-team"
    at.mkdir(parents=True)
    assert audit_mod._lock_consecutive(tmp_path, "abcdef1234567890") == 0, "absent state -> 0 (full text)"
    (at / audit_mod._LOCK_NOTIFY_STATE).write_text(
        _json.dumps({"abcdef12": {"consecutive": 4, "notified": False}}),
        encoding="utf-8")
    assert audit_mod._lock_consecutive(tmp_path, "abcdef1234567890") == 4
    assert audit_mod._lock_consecutive(tmp_path, "9999ffff00000000") == 0, "another session's count never bleeds"


def test_third_consecutive_stop_is_terse_end_to_end(tmp_path: Path) -> None:
    """Three real Stop invocations against one wedged workspace: the first
    block carries the full decision procedure, the third arrives terse —
    proving the notify-state counter actually FEEDS repeat_count through the
    composed lock path, not just that the builder honours the parameter."""
    from tests.test_completion_lock import (
        SESSION, _active_run, _engaged_transcript, _run_stop,
    )
    script = AUDIT_SCRIPT
    workspace = tmp_path / "ws"
    workspace.mkdir()
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    _active_run(workspace, session_id=SESSION)
    t = _engaged_transcript(workspace)
    payload = {"session_id": SESSION, "transcript_path": str(t)}

    outs = []
    for _ in range(3):
        r = _run_stop(script, workspace, tasks_root, payload)
        assert r.returncode == 2, "the wedge must keep blocking throughout"
        outs.append(r.stderr)

    assert "Decide by CHECKING" in outs[0], "first block = the full directive"
    assert "state unchanged" in outs[2], "third block = the terse form"
    assert "--mark-complete" in outs[2] and "--root" in outs[2], (
        "terse must still carry the fully-qualified exit"
    )
    assert len(outs[2]) < len(outs[0]), "terse is genuinely shorter"

