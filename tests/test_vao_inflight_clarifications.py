"""Tests for the v2.19.0 in-flight inbox + 17th Layer 3 tool.

Covers `hooks/inflight_inbox.py` module (read/append/mark_processed/
unprocessed_messages/current_run_id), the 17th Layer 3 tool
`verify_inflight_clarifications_processed`, fixture round-trip, and
determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.inflight_inbox import (
    CLASSIFICATIONS,
    INBOX_RELATIVE_DIR,
    INJECTION_VIAS,
    append_clarification,
    current_run_id,
    inbox_path_for,
    mark_processed,
    read_inbox,
    unprocessed_messages,
)
from hooks.vao_tools import verify_inflight_clarifications_processed

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "inflight-clarification-unprocessed.json"


# ---- module constants ----


def test_inbox_relative_dir() -> None:
    assert INBOX_RELATIVE_DIR == ".architect-team/inbox"


def test_injection_vias_includes_three_channels() -> None:
    assert "slash-command" in INJECTION_VIAS
    assert "natural-language-mid-run" in INJECTION_VIAS
    assert "external-webhook" in INJECTION_VIAS


def test_classifications_includes_three_kinds() -> None:
    assert "scope-amendment" in CLASSIFICATIONS
    assert "clarification" in CLASSIFICATIONS
    assert "out-of-scope" in CLASSIFICATIONS


# ---- inbox I/O ----


def test_read_inbox_returns_empty_when_missing(tmp_path: Path) -> None:
    assert read_inbox(tmp_path, "any-run") == []


def test_append_creates_inbox_dir_and_file(tmp_path: Path) -> None:
    msg = append_clarification(tmp_path, "run-1", "add CSV export")
    inbox = inbox_path_for(tmp_path, "run-1")
    assert inbox.exists()
    assert inbox.parent.name == "inbox"
    assert msg["text"] == "add CSV export"
    assert msg["processed_at"] is None
    assert msg["classification"] is None
    assert msg["message_id"]


def test_append_three_and_read_back(tmp_path: Path) -> None:
    append_clarification(tmp_path, "r1", "a")
    append_clarification(tmp_path, "r1", "b")
    append_clarification(tmp_path, "r1", "c")
    msgs = read_inbox(tmp_path, "r1")
    assert [m["text"] for m in msgs] == ["a", "b", "c"]


def test_append_rejects_empty_text(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_clarification(tmp_path, "r1", "")


def test_append_rejects_whitespace_only_text(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_clarification(tmp_path, "r1", "   ")


def test_append_rejects_invalid_injected_via(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_clarification(tmp_path, "r1", "hello", injected_via="invalid")


def test_unprocessed_messages_skips_processed(tmp_path: Path) -> None:
    m1 = append_clarification(tmp_path, "r1", "a")
    m2 = append_clarification(tmp_path, "r1", "b")
    mark_processed(tmp_path, "r1", m1["message_id"], classification="clarification", action_taken="x")
    unp = unprocessed_messages(tmp_path, "r1")
    assert [m["message_id"] for m in unp] == [m2["message_id"]]


def test_mark_processed_returns_updated_message(tmp_path: Path) -> None:
    m = append_clarification(tmp_path, "r1", "a")
    updated = mark_processed(tmp_path, "r1", m["message_id"], classification="scope-amendment", action_taken="re-ran Phase 2")
    assert updated is not None
    assert updated["processed_at"] is not None
    assert updated["classification"] == "scope-amendment"
    assert updated["action_taken"] == "re-ran Phase 2"


def test_mark_processed_returns_none_for_unknown_id(tmp_path: Path) -> None:
    append_clarification(tmp_path, "r1", "a")
    assert mark_processed(tmp_path, "r1", "nonexistent", classification="clarification", action_taken="x") is None


def test_mark_processed_rejects_invalid_classification(tmp_path: Path) -> None:
    m = append_clarification(tmp_path, "r1", "a")
    with pytest.raises(ValueError):
        mark_processed(tmp_path, "r1", m["message_id"], classification="invalid", action_taken="x")


def test_mark_processed_rejects_empty_action_taken(tmp_path: Path) -> None:
    m = append_clarification(tmp_path, "r1", "a")
    with pytest.raises(ValueError):
        mark_processed(tmp_path, "r1", m["message_id"], classification="clarification", action_taken="")


def test_mark_processed_preserves_other_lines(tmp_path: Path) -> None:
    m1 = append_clarification(tmp_path, "r1", "a")
    m2 = append_clarification(tmp_path, "r1", "b")
    m3 = append_clarification(tmp_path, "r1", "c")
    mark_processed(tmp_path, "r1", m2["message_id"], classification="clarification", action_taken="x")
    msgs = read_inbox(tmp_path, "r1")
    assert len(msgs) == 3
    assert [m["text"] for m in msgs] == ["a", "b", "c"]
    assert msgs[0]["processed_at"] is None
    assert msgs[1]["processed_at"] is not None
    assert msgs[2]["processed_at"] is None


# ---- current_run_id ----


def test_current_run_id_none_when_no_state(tmp_path: Path) -> None:
    assert current_run_id(tmp_path) is None


def test_current_run_id_returns_from_intake_state(tmp_path: Path) -> None:
    state_dir = tmp_path / ".architect-team"
    state_dir.mkdir()
    (state_dir / "intake-state.json").write_text(json.dumps({"run_id": "r-xyz-123"}), encoding="utf-8")
    assert current_run_id(tmp_path) == "r-xyz-123"


def test_current_run_id_none_when_malformed_state(tmp_path: Path) -> None:
    state_dir = tmp_path / ".architect-team"
    state_dir.mkdir()
    (state_dir / "intake-state.json").write_text("not json", encoding="utf-8")
    assert current_run_id(tmp_path) is None


# ---- 17th Layer 3 tool ----


def test_tool_returns_standard_shape(tmp_path: Path) -> None:
    v = verify_inflight_clarifications_processed(tmp_path, "r1")
    assert v["tool"] == "verify-inflight-clarifications-processed"
    assert "valid" in v
    assert "gaps" in v
    assert "verdict_at" in v
    assert "total_messages" in v
    assert "unprocessed_count" in v


def test_tool_passes_with_no_inbox(tmp_path: Path) -> None:
    v = verify_inflight_clarifications_processed(tmp_path, "r1")
    assert v["valid"] is True
    assert v["gaps"] == []
    assert v["total_messages"] == 0


def test_tool_passes_when_all_processed(tmp_path: Path) -> None:
    m1 = append_clarification(tmp_path, "r1", "a")
    m2 = append_clarification(tmp_path, "r1", "b")
    mark_processed(tmp_path, "r1", m1["message_id"], classification="clarification", action_taken="x")
    mark_processed(tmp_path, "r1", m2["message_id"], classification="clarification", action_taken="y")
    v = verify_inflight_clarifications_processed(tmp_path, "r1")
    assert v["valid"] is True
    assert v["total_messages"] == 2
    assert v["unprocessed_count"] == 0


def test_tool_fires_gap_per_unprocessed_message(tmp_path: Path) -> None:
    m1 = append_clarification(tmp_path, "r1", "a")
    append_clarification(tmp_path, "r1", "b")
    append_clarification(tmp_path, "r1", "c")
    mark_processed(tmp_path, "r1", m1["message_id"], classification="clarification", action_taken="x")
    v = verify_inflight_clarifications_processed(tmp_path, "r1")
    assert v["valid"] is False
    assert v["unprocessed_count"] == 2
    assert len(v["gaps"]) == 2
    for g in v["gaps"]:
        assert g["severity"] == "clarification-silently-ignored"


def test_tool_each_gap_carries_remediation(tmp_path: Path) -> None:
    append_clarification(tmp_path, "r1", "a")
    v = verify_inflight_clarifications_processed(tmp_path, "r1")
    for g in v["gaps"]:
        assert "remediation" in g
        assert "v2.19.0" in g["remediation"]


def test_tool_persists_to_out_path(tmp_path: Path) -> None:
    append_clarification(tmp_path, "r1", "a")
    out = tmp_path / "verdict.json"
    verify_inflight_clarifications_processed(tmp_path, "r1", out_path=str(out))
    assert out.exists()


# ---- fixture round-trip ----


def _materialize_inbox(workspace: Path, run_id: str, messages: list[dict]) -> None:
    inbox = inbox_path_for(workspace, run_id)
    inbox.parent.mkdir(parents=True, exist_ok=True)
    inbox.write_text("\n".join(json.dumps(m, sort_keys=True) for m in messages) + "\n", encoding="utf-8")


def test_canonical_fixture_bad_fires_clarification_silently_ignored(tmp_path: Path) -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rid = fx["_meta"]["run_id"]
    _materialize_inbox(tmp_path, rid, fx["inbox_messages"])
    v = verify_inflight_clarifications_processed(tmp_path, rid)
    assert v["valid"] is False
    assert v["unprocessed_count"] == fx["_meta"]["expected_unprocessed_count"]
    sevs = {g["severity"] for g in v["gaps"]}
    assert "clarification-silently-ignored" in sevs


def test_canonical_fixture_corrected_passes_cleanly(tmp_path: Path) -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rid = fx["_meta"]["run_id"]
    _materialize_inbox(tmp_path, rid, fx["_corrected_inbox_messages"])
    v = verify_inflight_clarifications_processed(tmp_path, rid)
    assert v["valid"] is True
    assert v["unprocessed_count"] == 0


# ---- determinism ----


def test_output_is_deterministic_on_stable_inbox(tmp_path: Path) -> None:
    append_clarification(tmp_path, "r1", "a")
    a = verify_inflight_clarifications_processed(tmp_path, "r1")
    b = verify_inflight_clarifications_processed(tmp_path, "r1")
    a_sevs = sorted((g["severity"], g.get("message_id")) for g in a["gaps"])
    b_sevs = sorted((g["severity"], g.get("message_id")) for g in b["gaps"])
    assert a_sevs == b_sevs
