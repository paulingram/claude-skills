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
