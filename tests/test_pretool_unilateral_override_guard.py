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


# --- N3: the protected set may not be derived from the value under attack ----
#
# `_harness_tasks_root()` resolves through `open_work.tasks_root()`, which
# honours `CT6_TASKS_ROOT`. So ONE environment variable moved BOTH the gate's
# ground truth AND the guard protecting it: point it at an empty directory and
# the guard faithfully protects the decoy while the real `~/.claude/tasks` --
# the store the lock actually reads when the env is not set in the harness's own
# process -- is writable. The protected set is now the UNION of the real default
# root and whatever the env names: an env var may ADD to the protected set, it
# may never REMOVE the real store from it.
#
# Every test below stats or globs the DEFAULT root, so every one of them patches
# `Path.home()` first. ITEM 1 is specifically ABOUT the default root, so a test
# that dodged it would be testing nothing -- patching is the only honest way to
# exercise it without reading (or risking a write to) the developer's real store.


def _patch_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Point `Path.home()` at a tmp dir for the duration of one test."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))


def test_ct6_tasks_root_env_cannot_move_the_guard_off_the_real_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N3 (adversarial). The attack is one variable: set `CT6_TASKS_ROOT` to a
    decoy and the guard's protected set moves with it, leaving the real harness
    task store open to a direct `"status": "completed"` write -- which is
    exactly the ADV-5 bypass this arm exists to refuse."""
    home = tmp_path / "home"
    real_task = home / ".claude" / "tasks" / "session-abcdef12" / "1.json"
    real_task.parent.mkdir(parents=True)
    real_task.write_text('{"status": "pending"}', encoding="utf-8")
    _patch_home(monkeypatch, home)

    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "decoy"))  # the attack

    assert _targets_completion_lock_ground_truth(str(real_task)) == "harness-task-store"
    rc, msg = check_payload(_write_payload(str(real_task)))
    assert rc == 2, "the REAL harness task store must stay protected under any env value"
    assert "harness task store" in msg


def test_ct6_tasks_root_env_still_adds_its_root_to_the_protected_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the union, and why the fix is a union and not a
    replacement: `CT6_TASKS_ROOT` is this suite's own test seam, so the
    env-named root has to stay protected too."""
    home = tmp_path / "home"
    (home / ".claude" / "tasks").mkdir(parents=True)
    _patch_home(monkeypatch, home)
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "injected"))

    injected = tmp_path / "injected" / "session-abcdef12" / "7.json"
    assert _targets_completion_lock_ground_truth(str(injected)) == "harness-task-store"
    assert check_payload(_write_payload(str(injected)))[0] == 2


def test_default_root_protection_does_not_widen_to_the_rest_of_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL for N3. Protecting `~/.claude/tasks` unconditionally must not
    creep into `~/.claude/` or the home directory at large, and `tasks-backup`
    must not match on a string prefix. A guard that refuses ordinary writes is a
    worse bug than the hole it closes -- it gets switched off."""
    home = tmp_path / "home"
    (home / ".claude" / "tasks").mkdir(parents=True)
    _patch_home(monkeypatch, home)
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "decoy"))
    for benign in (
        str(home / ".claude" / "settings.json"),
        str(home / ".claude" / "tasks-backup" / "1.json"),
        str(home / "notes.md"),
        str(tmp_path / "src" / "index.ts"),
    ):
        assert _targets_completion_lock_ground_truth(benign) is None, benign
        assert check_payload(_write_payload(benign))[0] == 0, benign


# --- N2b: a hardlink is not a spelling ---------------------------------------
#
# The F-B fix resolves before matching, which closes case-folding, `..`
# traversal and junctions -- each of those is a different SPELLING of one path,
# and `Path.resolve()` collapses spellings. A hardlink is not a spelling: it is
# a second real directory entry for the same bytes, and `resolve()` returns the
# alias's OWN path because there is no "true" name to resolve to. So
# `notes/evil.json` hardlinked onto the ledger writes the real ledger and every
# name-based arm sees an unrelated file.
#
# Identity closes it: same `(st_dev, st_ino)` IS the protected file, whatever
# name it was reached by.


def _hardlink_or_skip(src: Path, dst: Path) -> None:
    """Hardlink `src` -> `dst`, or skip loudly.

    `os.link` works on NTFS but not on FAT/exFAT, across volumes, or without the
    right privileges on some configurations. A skip with a reason beats a test
    that silently passes because the attack could not be staged."""
    try:
        os.link(src, dst)
    except (OSError, NotImplementedError, AttributeError) as exc:  # pragma: no cover
        pytest.skip(f"os.link unsupported on this volume/permissions: {exc!r}")


def test_a_hardlink_alias_to_the_ask_ledger_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N2b (adversarial): `evil.json` hardlinked onto the ask-ledger writes the
    real ledger bytes, and the resolved-name arm cannot see it."""
    home = tmp_path / "home"
    (home / ".claude" / "tasks").mkdir(parents=True)
    _patch_home(monkeypatch, home)
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))

    state = tmp_path / ".architect-team"
    state.mkdir()
    ledger = state / _ASK_LEDGER_FILENAME
    ledger.write_text('{"schema": 1, "entries": []}', encoding="utf-8")
    alias = tmp_path / "notes" / "evil.json"
    alias.parent.mkdir()
    _hardlink_or_skip(ledger, alias)

    # The precondition that makes this a real hole rather than a hypothetical:
    # resolution -- the F-B fix -- genuinely cannot see through it.
    assert alias.resolve() != ledger.resolve(), "precondition: resolve() sees only the alias"
    assert alias.read_text(encoding="utf-8") == ledger.read_text(encoding="utf-8")

    assert _targets_completion_lock_ground_truth(str(alias)) == "ask-ledger"
    rc, msg = check_payload(_write_payload(str(alias)))
    assert rc == 2, "a write to the alias IS a write to the ledger"
    assert "ask-ledger" in msg


def test_a_hardlink_alias_to_a_harness_task_file_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N2b, the ADV-5 half: the same trick against a harness task JSON, whose
    `"status"` field is the single value the task-list gate reads."""
    home = tmp_path / "home"
    (home / ".claude" / "tasks").mkdir(parents=True)
    _patch_home(monkeypatch, home)

    root = tmp_path / "tasks"
    task = root / "session-abcdef12" / "1.json"
    task.parent.mkdir(parents=True)
    task.write_text('{"status": "pending"}', encoding="utf-8")
    monkeypatch.setenv("CT6_TASKS_ROOT", str(root))

    alias = tmp_path / "notes" / "harmless.json"
    alias.parent.mkdir()
    _hardlink_or_skip(task, alias)

    assert alias.resolve() != task.resolve(), "precondition: resolve() sees only the alias"
    assert _targets_completion_lock_ground_truth(str(alias)) == "harness-task-store"
    rc, msg = check_payload(_write_payload(str(alias)))
    assert rc == 2, "a write to the alias IS a write to the task record"
    assert "harness task store" in msg


def test_identity_arm_leaves_ordinary_writes_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL for N2b, in the three shapes the arm must NOT catch:

      * a file that does not exist yet -- the common case for `Write`, and the
        one `os.stat` raises on;
      * an ordinary existing file with a single name;
      * two files hardlinked to EACH OTHER, neither of them protected -- this
        is the one that proves the arm matches identity WITH THE PROTECTED
        FILE, not merely "this path has more than one name".
    """
    home = tmp_path / "home"
    (home / ".claude" / "tasks").mkdir(parents=True)
    _patch_home(monkeypatch, home)
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))

    state = tmp_path / ".architect-team"
    state.mkdir()
    (state / _ASK_LEDGER_FILENAME).write_text("{}", encoding="utf-8")

    src = tmp_path / "src"
    src.mkdir()
    existing = src / "index.ts"
    existing.write_text("export const x = 1;\n", encoding="utf-8")
    linked_a = src / "shared.ts"
    linked_a.write_text("export const y = 2;\n", encoding="utf-8")
    linked_b = src / "shared-alias.ts"
    _hardlink_or_skip(linked_a, linked_b)

    for benign in (
        str(src / "brand-new-file.ts"),  # does not exist
        str(existing),
        str(linked_a),
        str(linked_b),  # nlink == 2, but not the ledger and not a task
    ):
        assert _targets_completion_lock_ground_truth(benign) is None, benign
        assert check_payload(_write_payload(benign))[0] == 0, benign


def test_identity_arm_never_raises_and_degrades_to_the_name_arms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`os.stat` is not guaranteed to answer -- a permission error, a dead
    network share, a filesystem that does not report inodes. This arm must
    degrade to the existing resolved-name comparison, never raise: PreToolUse
    treats exit 1 as NON-blocking, so a crash here opens the whole guard on
    exactly the input the caller controls."""
    home = tmp_path / "home"
    (home / ".claude" / "tasks").mkdir(parents=True)
    _patch_home(monkeypatch, home)
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "tasks"))

    state = tmp_path / ".architect-team"
    state.mkdir()
    canonical = state / _ASK_LEDGER_FILENAME
    canonical.write_text("{}", encoding="utf-8")

    # Imported here rather than at module scope so the other new properties in
    # this file fail on their own assertions instead of a collection error.
    import hooks.pretool_unilateral_override_guard as guard_mod
    from hooks.pretool_unilateral_override_guard import (
        _file_identity,
        _may_be_a_link_alias,
    )

    # The helpers must swallow ANY exception, not just OSError.
    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("stat is not available here")

    monkeypatch.setattr(guard_mod.os, "stat", _boom)
    assert _file_identity(canonical) is None
    assert _may_be_a_link_alias(canonical) in (True, False)  # a verdict, not a raise

    # And with stat merely failing the ordinary way, the name arms still work.
    monkeypatch.setattr(guard_mod.os, "stat", _oserror_stat)
    assert _targets_completion_lock_ground_truth(str(canonical)) == "ask-ledger"
    assert _targets_completion_lock_ground_truth(str(tmp_path / "src" / "a.ts")) is None
    assert check_payload(_write_payload(str(canonical)))[0] == 2


def _oserror_stat(*_a: object, **_k: object) -> None:
    raise PermissionError("stat denied")
