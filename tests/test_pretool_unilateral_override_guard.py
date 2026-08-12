"""Tests for the v3.0.0 PreToolUse runtime guardrail."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.pretool_unilateral_override_guard import (
    _BYPASS_ALLOWED_PATH_FRAGMENTS,
    _PIPELINE_SKILL_NAMES,
    _find_workspace,
    _is_allowed_path,
    _read_intake_state,
    check_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---- module constants ----


def test_pipeline_skill_names_include_all_four_pipelines() -> None:
    for name in (
        "architect-team-pipeline",
        "bug-fix-pipeline",
        "mini-architect-team-pipeline",
        "ux-test-builder",
    ):
        assert name in _PIPELINE_SKILL_NAMES


def test_bypass_allowed_paths_include_architect_team_state() -> None:
    paths = " ".join(_BYPASS_ALLOWED_PATH_FRAGMENTS)
    assert ".architect-team" in paths
    assert ".mempalace" in paths
    assert "openspec/changes" in paths


# ---- helper: _is_allowed_path ----


def test_is_allowed_path_for_architect_team_state() -> None:
    assert _is_allowed_path("/repo/.architect-team/reviews/x.json") is True


def test_is_allowed_path_for_mempalace() -> None:
    assert _is_allowed_path("/repo/.mempalace/palace.db") is True


def test_is_allowed_path_for_openspec_changes() -> None:
    assert _is_allowed_path("/repo/openspec/changes/my-change/proposal.md") is True


def test_is_allowed_path_for_source_returns_false() -> None:
    assert _is_allowed_path("/repo/src/index.ts") is False


def test_is_allowed_path_empty_string_passes() -> None:
    assert _is_allowed_path("") is True  # treated as no-op


# ---- helper: _find_workspace ----


def test_find_workspace_in_workspace_root(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    found = _find_workspace(tmp_path)
    assert found == tmp_path.resolve()


def test_find_workspace_walks_up(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    found = _find_workspace(nested)
    assert found == tmp_path.resolve()


def test_find_workspace_returns_none_when_no_state(tmp_path: Path) -> None:
    """No marker in the CONTROLLED subtree => the walk never resolves to it.

    Hermeticity (v3.36.0): pytest's tmp_path lives under the user profile, and
    per-user CT6 state at ~/.architect-team/ (sanctioned since the v3.29.0
    librarian install; also the v3.36.0 gateway) makes the profile dir a REAL
    workspace ancestor — the walk finding IT is correct guard behavior, not a
    failure. So assert the walk finds nothing INSIDE tmp_path; a non-None
    result must be a genuine pre-existing marker outside the test's control."""
    found = _find_workspace(tmp_path)
    if found is not None:
        assert not found.is_relative_to(tmp_path.resolve())
        assert (found / ".architect-team").is_dir()
    else:
        assert found is None


# ---- helper: _read_intake_state ----


def test_read_intake_state_returns_none_when_missing(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    assert _read_intake_state(tmp_path) is None


def test_read_intake_state_returns_dict_when_present(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    (tmp_path / ".architect-team" / "intake-state.json").write_text(
        json.dumps({"run_id": "r1", "status": "in_progress", "phase": 2})
    , encoding="utf-8")
    state = _read_intake_state(tmp_path)
    assert state is not None
    assert state["run_id"] == "r1"


def test_read_intake_state_returns_none_on_malformed_json(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    (tmp_path / ".architect-team" / "intake-state.json").write_text("not json", encoding="utf-8")
    assert _read_intake_state(tmp_path) is None


# ---- check_payload: tool filtering ----


def test_non_edit_tool_passes() -> None:
    ec, msg = check_payload({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert ec == 0
    assert msg == ""


def test_grep_tool_passes() -> None:
    ec, msg = check_payload({"tool_name": "Grep", "tool_input": {"pattern": "x"}})
    assert ec == 0


def test_missing_file_path_passes() -> None:
    ec, msg = check_payload({"tool_name": "Edit", "tool_input": {}})
    assert ec == 0


# ---- check_payload: workspace resolution ----


def test_no_workspace_passes(tmp_path: Path) -> None:
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "x.py")},
        "cwd": str(tmp_path),
    })
    assert ec == 0


def test_workspace_without_intake_state_passes(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "src/x.py")},
        "cwd": str(tmp_path),
    })
    assert ec == 0


# ---- check_payload: pipeline state ----


def _make_workspace_with_active_pipeline(tmp_path: Path, run_id: str = "r1") -> Path:
    (tmp_path / ".architect-team").mkdir()
    (tmp_path / ".architect-team" / "intake-state.json").write_text(
        json.dumps({"run_id": run_id, "status": "in_progress", "phase": 2})
    , encoding="utf-8")
    return tmp_path


def test_active_pipeline_blocks_edit_to_source(tmp_path: Path) -> None:
    ws = _make_workspace_with_active_pipeline(tmp_path)
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(ws / "src/index.ts")},
        "cwd": str(ws),
    })
    assert ec == 2
    assert "BLOCKED" in msg
    assert "v3.0.0" in msg


def test_active_pipeline_allows_edit_to_architect_team_state(tmp_path: Path) -> None:
    ws = _make_workspace_with_active_pipeline(tmp_path)
    ec, msg = check_payload({
        "tool_name": "Write",
        "tool_input": {"file_path": str(ws / ".architect-team/reviews/r.json")},
        "cwd": str(ws),
    })
    assert ec == 0


def test_active_pipeline_allows_edit_to_openspec_changes(tmp_path: Path) -> None:
    ws = _make_workspace_with_active_pipeline(tmp_path)
    ec, msg = check_payload({
        "tool_name": "Write",
        "tool_input": {"file_path": str(ws / "openspec/changes/my-change/proposal.md")},
        "cwd": str(ws),
    })
    assert ec == 0


def test_not_in_progress_status_passes(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    (tmp_path / ".architect-team" / "intake-state.json").write_text(
        json.dumps({"run_id": "r1", "status": "completed", "phase": 8})
    , encoding="utf-8")
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "src/x.py")},
        "cwd": str(tmp_path),
    })
    assert ec == 0


def test_phase_8_or_higher_passes(tmp_path: Path) -> None:
    (tmp_path / ".architect-team").mkdir()
    (tmp_path / ".architect-team" / "intake-state.json").write_text(
        json.dumps({"run_id": "r1", "status": "in_progress", "phase": 8})
    , encoding="utf-8")
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "src/x.py")},
        "cwd": str(tmp_path),
    })
    assert ec == 0


def test_active_pipeline_with_skill_in_ledger_passes(tmp_path: Path) -> None:
    ws = _make_workspace_with_active_pipeline(tmp_path)
    (ws / ".architect-team" / "run-history").mkdir()
    (ws / ".architect-team" / "run-history" / "r1-toolcalls.jsonl").write_text(
        json.dumps({"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}}) + "\n"
    , encoding="utf-8")
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(ws / "src/x.py")},
        "cwd": str(ws),
    })
    assert ec == 0


def test_active_pipeline_with_bug_fix_skill_in_ledger_passes(tmp_path: Path) -> None:
    ws = _make_workspace_with_active_pipeline(tmp_path)
    (ws / ".architect-team" / "run-history").mkdir()
    (ws / ".architect-team" / "run-history" / "r1-toolcalls.jsonl").write_text(
        json.dumps({"tool": "Skill", "tool_input": {"skill": "bug-fix-pipeline"}}) + "\n"
    , encoding="utf-8")
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(ws / "src/x.py")},
        "cwd": str(ws),
    })
    assert ec == 0


def test_block_message_lists_disclosure_options(tmp_path: Path) -> None:
    ws = _make_workspace_with_active_pipeline(tmp_path)
    ec, msg = check_payload({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(ws / "src/x.py")},
        "cwd": str(ws),
    })
    assert ec == 2
    assert "(a) Invoke the pipeline Skill first" in msg
    assert "(b) Explicitly disclose the bypass" in msg


# ---- v3.56.0: completion-lock ground truth is immutable to agents ----------
#
# ADV-3 / ADV-5. The lock's whole claim is that its exit condition comes from
# files the HARNESS writes. Two direct-write escapes defeat that without going
# near a tool the existing gates watch: one `Write` flips every ask-ledger entry
# to `resolved`, and writing `"status": "completed"` straight into a task JSON
# bypasses `review-gate-task.py` entirely, because that hook is
# `PostToolUse(TaskUpdate)` and only ever sees the tool. Both are mitigated here
# rather than in a new guard: this file already refuses agent edits of
# `.architect-team-deploy.json`, so it is the same pattern and the same
# unconditional placement.

import os

from hooks.pretool_unilateral_override_guard import (
    _ASK_LEDGER_FILENAME,
    _harness_tasks_root,
    _targets_completion_lock_ground_truth,
)


def _write_payload(file_path: str, tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": file_path}}


def test_tasks_root_resolution_matches_open_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard defers to the substrate's own resolver so the protected set can
    never drift from the set the lock actually reads. It returns the RESOLVED
    form (it compares against resolved write targets), so compare resolved."""
    from hooks import open_work

    monkeypatch.delenv("CT6_TASKS_ROOT", raising=False)
    assert _harness_tasks_root() == open_work.tasks_root().resolve()
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "injected"))
    assert _harness_tasks_root() == open_work.tasks_root().resolve()
    assert _ASK_LEDGER_FILENAME == open_work.LEDGER_FILENAME


def test_write_to_ask_ledger_is_blocked(tmp_path: Path) -> None:
    """ADV-3: one Write flipping every entry to 'resolved' would empty the
    gate's open-work list without doing any of the work."""
    ledger = tmp_path / ".architect-team" / _ASK_LEDGER_FILENAME
    code, message = check_payload(_write_payload(str(ledger)))
    assert code == 2, "the ask-ledger must not be agent-writable"
    assert "ask-ledger" in message
    assert str(ledger) in message


def test_write_to_a_harness_task_file_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADV-5: writing status=completed into the task JSON never touches
    TaskUpdate, so review-gate-task.py never sees it."""
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))
    target = tmp_path / "tasks" / "session-abcdef12" / "1.json"
    code, message = check_payload(_write_payload(str(target)))
    assert code == 2, "the harness task store must not be agent-writable"
    assert "harness task store" in message
    assert "TaskUpdate" in message, "the message must name the gate being reached around"
    assert str(target) in message


def test_ground_truth_guard_covers_edit_and_notebookedit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))
    task = str(tmp_path / "tasks" / "session-abcdef12" / "1.json")
    for tool in ("Edit", "Write", "NotebookEdit"):
        code, _ = check_payload(_write_payload(task, tool=tool))
        assert code == 2, f"{tool} must be refused on the harness task list"


def test_ground_truth_guard_fires_with_no_pipeline_run_active(tmp_path: Path) -> None:
    """Unconditional, like the deploy-config arm: the completion lock fires in
    EVERY session, so its ground truth needs protecting in every session, not
    only inside a CT6 run. A tmp_path workspace has no intake-state.json."""
    ledger = tmp_path / ".architect-team" / _ASK_LEDGER_FILENAME
    assert check_payload(_write_payload(str(ledger)))[0] == 2


def test_ground_truth_guard_does_not_capture_neighbours(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL. Over-blocking here would make ordinary state writes impossible
    and get the whole guard switched off, so pin what it must NOT catch."""
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))
    for benign in (
        str(tmp_path / ".architect-team" / "reviews" / "T-1.json"),
        str(tmp_path / ".architect-team" / "active-run.json"),
        str(tmp_path / "docs" / "ask-ledger.json"),   # right name, wrong home
        str(tmp_path / "src" / "index.ts"),
    ):
        assert _targets_completion_lock_ground_truth(benign) is None, benign
        assert check_payload(_write_payload(benign))[0] == 0, benign


def test_ground_truth_guard_survives_a_junk_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guard that raises on a malformed path exits 1, and PreToolUse treats
    exit 1 as non-blocking -- so it would degrade OPEN on exactly the input the
    caller controls. Every one of these must return a verdict, not an
    exception."""
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))
    for junk in ("", "\x00", "://://", "?" * 4096, "con", "//?/UNC/nope"):
        assert _targets_completion_lock_ground_truth(junk) is None, junk
        assert check_payload(_write_payload(junk))[0] in (0, 2), junk


def test_ledger_guard_resolves_before_matching_so_spellings_cannot_evade_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-B (independent review): the ask-ledger arm compared `p.name` and
    `p.parent.name` as RAW strings while its harness-task-store sibling
    resolved. Two one-Write bypasses reached the SAME real file and returned
    exit 0 where the canonical spelling returned 2 -- an inconsistency inside a
    single function, on the platform this repo is developed on:

      * NTFS is case-insensitive, so `.ARCHITECT-TEAM/ASK-LEDGER.JSON` is the
        canonical file under a different spelling.
      * `.architect-team/reviews/../ask-ledger.json` re-enters the same file
        through a sibling directory.

    The original tests only ever exercised the canonical spelling, which is
    exactly how this survived to review. Both attacks are positive cases here.
    """
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))
    at = tmp_path / ".architect-team"
    (at / "reviews").mkdir(parents=True)
    canonical = at / _ASK_LEDGER_FILENAME
    canonical.write_text('{"schema": 1, "entries": []}', encoding="utf-8")

    attacks = {
        "canonical": str(canonical),
        "case-folded": str(tmp_path / ".ARCHITECT-TEAM" / "ASK-LEDGER.JSON"),
        "traversal re-entry": str(at / "reviews" / ".." / _ASK_LEDGER_FILENAME),
    }
    for label, spelling in attacks.items():
        assert _targets_completion_lock_ground_truth(spelling) == "ask-ledger", label
        rc, msg = check_payload(_write_payload(spelling))
        assert rc == 2, f"{label} must be refused; got {rc}"
        assert "ask-ledger" in msg, label


def test_ledger_guard_resolution_does_not_swallow_a_same_named_neighbour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control for the fix above. Resolving must not widen the net: a file
    with the ledger's name outside a `.architect-team/` parent stays allowed. A
    guard that blocks legitimate writes gets disabled, which defeats it just as
    thoroughly as one that can be spelled around."""
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))
    for benign in (
        str(tmp_path / "notes" / _ASK_LEDGER_FILENAME),
        str(tmp_path / ".architect-team-backup" / _ASK_LEDGER_FILENAME),
        str(tmp_path / ".architect-team" / "ask-ledger.json.bak"),
    ):
        assert _targets_completion_lock_ground_truth(benign) is None, benign
        assert check_payload(_write_payload(benign))[0] == 0, benign


def test_ask_ledger_arm_resists_case_and_traversal_spellings(tmp_path: Path) -> None:
    """F-B (independent review). The ask-ledger arm once matched `p.name` /
    `p.parent.name` as raw strings while its harness-task-store sibling
    resolved. Two one-Write bypasses followed on NTFS -- an uppercase spelling
    and a `..` re-entry, each reaching the SAME real file and returning exit 0
    where the canonical spelling returned 2.

    These are positive cases rather than a mutation entry because their absence
    IS the defect: the arm was only ever tested against the canonical spelling,
    which is exactly how it survived to review."""
    state = tmp_path / ".architect-team"
    state.mkdir()
    canonical = state / _ASK_LEDGER_FILENAME
    canonical.write_text('{"schema": 1, "entries": []}', encoding="utf-8")

    spellings = [
        str(canonical),
        str(tmp_path / ".ARCHITECT-TEAM" / "ASK-LEDGER.JSON"),
        str(tmp_path / ".architect-team" / "Ask-Ledger.json"),
        str(state / "reviews" / ".." / _ASK_LEDGER_FILENAME),
        str(tmp_path / ".architect-team" / "." / _ASK_LEDGER_FILENAME),
        str(state / "sub" / ".." / _ASK_LEDGER_FILENAME),
    ]
    for spelling in spellings:
        assert _targets_completion_lock_ground_truth(spelling) == "ask-ledger", spelling
        assert check_payload(_write_payload(spelling))[0] == 2, spelling


def test_ask_ledger_arm_still_declines_a_same_named_file_elsewhere(tmp_path: Path) -> None:
    """CONTROL for the test above. Resolving must not widen the arm into every
    file called ask-ledger.json -- the `.architect-team/` parent requirement is
    what keeps an unrelated file out, and over-blocking here would train someone
    to switch the guard off."""
    for benign in (
        str(tmp_path / "docs" / _ASK_LEDGER_FILENAME),
        str(tmp_path / ".architect-team" / "reviews" / _ASK_LEDGER_FILENAME),
        str(tmp_path / "ask-ledger.json"),
    ):
        assert _targets_completion_lock_ground_truth(benign) is None, benign
        assert check_payload(_write_payload(benign))[0] == 0, benign
