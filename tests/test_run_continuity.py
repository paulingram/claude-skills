"""Unit tests for hooks/run_continuity.py (v3.30.0).

The run-continuity substrate: the active-run lifecycle marker, the progress
fingerprint + no-progress guard state, the transcript analysis helpers
(engagement / compact boundaries / teammate detection), and the CLI.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hooks import run_continuity as rc


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def _write_transcript(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


def _user(text: str, ts: str = "2026-07-03T10:00:00Z", **extra) -> dict:
    rec = {"type": "user", "timestamp": ts,
           "message": {"role": "user", "content": text}}
    rec.update(extra)
    return rec


def _skill_call(skill: str, ts: str = "2026-07-03T10:01:00Z") -> dict:
    return {
        "type": "assistant", "timestamp": ts,
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": skill}},
        ]},
    }


# --- marker lifecycle --------------------------------------------------------

def test_no_marker_reads_none_and_inactive(workspace: Path) -> None:
    assert rc.read_marker(workspace) is None
    assert rc.marker_is_active(workspace) is False


def test_engage_creates_active_marker(workspace: Path) -> None:
    m = rc.engage_marker(workspace, "architect-team-pipeline", "sess-1")
    assert m is not None and m["status"] == "active"
    assert rc.marker_is_active(workspace) is True
    on_disk = rc.read_marker(workspace)
    assert on_disk["skill"] == "architect-team-pipeline"
    assert on_disk["session_id"] == "sess-1"
    assert on_disk["schema"] == 1


def test_reengage_active_preserves_run_identity(workspace: Path) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline", "sess-1")
    rc.update_marker(workspace, slug="my-feature", phase="Phase 5", run_id="r-9")
    started = rc.read_marker(workspace)["started_at"]
    m = rc.engage_marker(workspace, "bug-fix-pipeline", "sess-2")
    assert m["started_at"] == started, "re-engaging an active run keeps started_at"
    assert m["slug"] == "my-feature" and m["phase"] == "Phase 5"
    assert m["skill"] == "bug-fix-pipeline" and m["session_id"] == "sess-2"


def test_engage_after_complete_starts_fresh(workspace: Path) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline")
    rc.update_marker(workspace, slug="old-run")
    rc.mark_complete(workspace)
    assert rc.marker_is_active(workspace) is False
    m = rc.engage_marker(workspace, "mini-architect-team-pipeline")
    assert m["status"] == "active" and m["slug"] is None, "a completed marker is replaced, not resumed"


def test_mark_complete_and_stand_down(workspace: Path) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline")
    m = rc.mark_complete(workspace)
    assert m["status"] == "complete" and m["completed_at"]
    rc.engage_marker(workspace, "architect-team-pipeline")
    m = rc.stand_down(workspace, "Paul said: do this one by hand")
    assert m["status"] == "stood-down"
    sd = workspace / ".architect-team" / rc.STAND_DOWN_FILENAME
    assert sd.exists() and "do this one by hand" in sd.read_text(encoding="utf-8")


def test_mark_complete_without_marker_is_none(workspace: Path) -> None:
    assert rc.mark_complete(workspace) is None
    assert rc.stand_down(workspace, "x") is None


def test_malformed_marker_reads_none(workspace: Path) -> None:
    p = rc.marker_path(workspace)
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    assert rc.read_marker(workspace) is None
    assert rc.marker_is_active(workspace) is False


def test_kill_switch_disables_active(workspace: Path, monkeypatch) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline")
    monkeypatch.setenv(rc.DISABLE_ENV, "1")
    assert rc.continuity_disabled() is True
    assert rc.marker_is_active(workspace) is False
    monkeypatch.setenv(rc.DISABLE_ENV, "0")
    assert rc.continuity_disabled() is False
    assert rc.marker_is_active(workspace) is True


def test_max_no_progress_env(monkeypatch) -> None:
    monkeypatch.delenv(rc.MAX_NO_PROGRESS_ENV, raising=False)
    assert rc.max_no_progress_stops() == rc.DEFAULT_MAX_NO_PROGRESS
    monkeypatch.setenv(rc.MAX_NO_PROGRESS_ENV, "7")
    assert rc.max_no_progress_stops() == 7
    monkeypatch.setenv(rc.MAX_NO_PROGRESS_ENV, "0")
    assert rc.max_no_progress_stops() == rc.DEFAULT_MAX_NO_PROGRESS
    monkeypatch.setenv(rc.MAX_NO_PROGRESS_ENV, "garbage")
    assert rc.max_no_progress_stops() == rc.DEFAULT_MAX_NO_PROGRESS


# --- fingerprint + guard state ----------------------------------------------

def test_fingerprint_stable_then_changes_on_state_write(workspace: Path) -> None:
    at = workspace / ".architect-team"
    at.mkdir()
    (at / "intake-state.json").write_text("{}", encoding="utf-8")
    fp1 = rc.run_fingerprint(workspace)
    assert fp1 == rc.run_fingerprint(workspace), "no changes => stable"
    time.sleep(0.01)
    (at / "intake-state.json").write_text('{"x": 1}', encoding="utf-8")
    assert rc.run_fingerprint(workspace) != fp1, "a state write is progress"


def test_fingerprint_excludes_self_and_liveness_files(workspace: Path) -> None:
    at = workspace / ".architect-team"
    at.mkdir()
    (at / "intake-state.json").write_text("{}", encoding="utf-8")
    fp1 = rc.run_fingerprint(workspace)
    (at / rc.GUARD_STATE_FILENAME).write_text('{"n": 1}', encoding="utf-8")
    (at / "in-progress.md").write_text("alive", encoding="utf-8")
    assert rc.run_fingerprint(workspace) == fp1, (
        "the guard's own state file and the liveness marker are not progress"
    )


def test_note_continuation_block_counting(workspace: Path) -> None:
    (workspace / ".architect-team").mkdir()
    assert rc.note_continuation_block(workspace, "fp-A", "prompt-1") == 0
    assert rc.note_continuation_block(workspace, "fp-A", "prompt-1") == 1
    assert rc.note_continuation_block(workspace, "fp-A", "prompt-1") == 2
    # progress resets
    assert rc.note_continuation_block(workspace, "fp-B", "prompt-1") == 0
    assert rc.note_continuation_block(workspace, "fp-B", "prompt-1") == 1
    # a fresh user prompt resets
    assert rc.note_continuation_block(workspace, "fp-B", "prompt-2") == 0
    rc.clear_guard_state(workspace)
    assert rc.read_guard_state(workspace) == {}


# --- transcript analysis ------------------------------------------------------

def test_session_engaged_pipeline_bare_and_prefixed(tmp_path: Path) -> None:
    t = _write_transcript(tmp_path / "t.jsonl", [
        _user("continue"),
        _skill_call("architect-team:architect-team-pipeline"),
    ])
    records = rc.read_transcript(t)
    assert rc.session_engaged_pipeline(records) is True
    t2 = _write_transcript(tmp_path / "t2.jsonl", [
        _user("continue"),
        _skill_call("data-dictionary"),
    ])
    assert rc.session_engaged_pipeline(rc.read_transcript(t2)) is False


def test_engagement_since_last_compact_boundary(tmp_path: Path) -> None:
    base = [
        _user("/architect-team build the thing"),
        _skill_call("architect-team-pipeline"),
        {"type": "system", "subtype": "compact_boundary"},
        _user("continue", ts="2026-07-03T11:00:00Z"),
    ]
    records = rc.read_transcript(_write_transcript(tmp_path / "a.jsonl", base))
    assert rc.session_engaged_pipeline(records) is True, "whole-ledger form"
    assert rc.session_engaged_pipeline(records, since_last_compact=True) is False, (
        "the compact boundary dropped the playbook from context"
    )
    re_invoked = base + [_skill_call("architect-team-pipeline", ts="2026-07-03T11:01:00Z")]
    records2 = rc.read_transcript(_write_transcript(tmp_path / "b.jsonl", re_invoked))
    assert rc.session_engaged_pipeline(records2, since_last_compact=True) is True


def test_compact_boundary_summary_shape(tmp_path: Path) -> None:
    records = rc.read_transcript(_write_transcript(tmp_path / "c.jsonl", [
        _user("/architect-team go"),
        _skill_call("architect-team-pipeline"),
        _user("summary of the conversation...", isCompactSummary=True),
        _user("continue", ts="2026-07-03T12:00:00Z"),
    ]))
    assert rc.session_engaged_pipeline(records, since_last_compact=True) is False


def test_teammate_detection_token(tmp_path: Path) -> None:
    records = rc.read_transcript(_write_transcript(tmp_path / "d.jsonl", [
        _user("[CT6-TEAMMATE backend RUN my-feature]\nYour tasks: ..."),
    ]))
    assert rc.is_teammate_transcript(records) is True


def test_teammate_detection_brief_heuristic(tmp_path: Path) -> None:
    brief = (
        "You are the backend teammate for run my-feature. " * 60
        + " Write evidence to .architect-team/reviews/T1.json before completing."
    )
    assert len(brief) >= 1500
    records = rc.read_transcript(_write_transcript(tmp_path / "e.jsonl", [_user(brief)]))
    assert rc.is_teammate_transcript(records) is True


def test_user_session_not_teammate(tmp_path: Path) -> None:
    records = rc.read_transcript(_write_transcript(tmp_path / "f.jsonl", [
        _user("<command-name>/architect-team:architect-team</command-name> build it"),
        _user("continue", ts="2026-07-03T11:00:00Z"),
    ]))
    assert rc.is_teammate_transcript(records) is False
    short = rc.read_transcript(_write_transcript(tmp_path / "g.jsonl", [_user("continue")]))
    assert rc.is_teammate_transcript(short) is False


def test_genuine_prompt_and_anchor(tmp_path: Path) -> None:
    sidechain_only = rc.read_transcript(_write_transcript(tmp_path / "h.jsonl", [
        _user("subagent brief", isSidechain=True),
    ]))
    assert rc.session_has_genuine_prompt(sidechain_only) is False
    assert rc.latest_prompt_anchor(sidechain_only) == ""
    records = rc.read_transcript(_write_transcript(tmp_path / "i.jsonl", [
        _user("first", ts="2026-07-03T09:00:00Z"),
        _user("second", ts="2026-07-03T10:30:00Z"),
    ]))
    assert rc.session_has_genuine_prompt(records) is True
    assert rc.latest_prompt_anchor(records) == "2026-07-03T10:30:00Z"


# --- CLI ----------------------------------------------------------------------

def _cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[1] / "hooks" / "run_continuity.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True, capture_output=True, cwd=str(cwd),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def test_cli_status_engage_set_complete(workspace: Path) -> None:
    r = _cli(["--status"], workspace)
    assert r.returncode == 0 and json.loads(r.stdout)["active"] is False

    r = _cli(["--engage", "architect-team-pipeline"], workspace)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "active"

    r = _cli(["--set", "phase=Phase 5", "slug=my-feature"], workspace)
    assert r.returncode == 0
    m = json.loads(r.stdout)
    assert m["phase"] == "Phase 5" and m["slug"] == "my-feature"

    r = _cli(["--set", "status=complete"], workspace)
    assert r.returncode != 0 or json.loads(r.stdout).get("status") == "active", (
        "--set must not perform lifecycle transitions"
    )

    r = _cli(["--mark-complete"], workspace)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "complete"


def test_cli_stand_down_and_root(workspace: Path, tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert _cli(["--engage", "bug-fix-pipeline", "--root", str(workspace)], other).returncode == 0
    r = _cli(["--stand-down", "user said stop using the team", "--root", str(workspace)], other)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "stood-down"
    assert (workspace / ".architect-team" / rc.STAND_DOWN_FILENAME).exists()


def test_cli_error_paths(workspace: Path) -> None:
    assert _cli(["--mark-complete"], workspace).returncode == 1
    assert _cli(["--stand-down", "x"], workspace).returncode == 1
    assert _cli(["--engage"], workspace).returncode == 1
    assert _cli(["--set"], workspace).returncode == 1
    assert _cli(["--bogus-flag"], workspace).returncode == 1


# --- v3.30.0 adversarial-review remediations ---------------------------------

def test_marker_staleness(workspace: Path, monkeypatch) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline")
    assert rc.marker_is_stale(rc.read_marker(workspace)) is False
    # update_marker refreshes updated_at, so write the stale stamp directly
    m = rc.read_marker(workspace)
    m["updated_at"] = "2020-01-01T00:00:00+00:00"
    rc._atomic_write_json(rc.marker_path(workspace), m)
    assert rc.marker_is_stale(rc.read_marker(workspace)) is True
    assert rc.marker_is_stale({"updated_at": "not-a-date"}) is True
    assert rc.marker_is_stale(None) is True
    monkeypatch.setenv(rc.MARKER_STALE_HOURS_ENV, "999999")
    assert rc.marker_is_stale(rc.read_marker(workspace)) is False


def test_touch_marker_refreshes_and_is_fingerprint_excluded(workspace: Path) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline")
    m = rc.read_marker(workspace)
    m["updated_at"] = "2020-01-01T00:00:00+00:00"
    rc._atomic_write_json(rc.marker_path(workspace), m)
    fp = rc.run_fingerprint(workspace)
    rc.touch_marker(workspace)
    assert rc.marker_is_stale(rc.read_marker(workspace)) is False
    assert rc.run_fingerprint(workspace) == fp, (
        "the staleness heartbeat must never read as run progress"
    )


def test_transcript_slices_small_and_truncated(tmp_path: Path) -> None:
    small = _write_transcript(tmp_path / "small.jsonl", [_user("hi")])
    tail, head, truncated = rc.load_transcript_slices(small)
    assert truncated is False and head == [] and len(tail) == 1

    big = tmp_path / "big.jsonl"
    brief = _user("[CT6-TEAMMATE backend RUN my-feature]\nYour tasks: T1.")
    filler = {"type": "assistant", "timestamp": "t",
              "message": {"role": "assistant", "content": "x" * 4000}}
    with open(big, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(brief) + "\n")
        fh.write(json.dumps(_skill_call("architect-team-pipeline")) + "\n")
        for _ in range(600):  # ~2.4 MB of filler evicts the head from the tail
            fh.write(json.dumps(filler) + "\n")
        fh.write(json.dumps(_user("latest nudge", ts="2026-07-03T12:00:00Z")) + "\n")
    tail, head, truncated = rc.load_transcript_slices(big)
    assert truncated is True and head, "big transcript must yield a head slice"
    assert rc.is_teammate_transcript(tail, head_records=head, truncated=True) is True, (
        "the CT6-TEAMMATE token at the transcript HEAD must be seen past the tail cap"
    )
    assert rc.session_engaged_pipeline(tail, head_records=head, truncated=True) is True, (
        "a head-slice Skill invocation counts as engagement"
    )


def test_truncated_without_head_fails_open(tmp_path: Path) -> None:
    records = rc.read_transcript(_write_transcript(tmp_path / "t.jsonl", [_user("continue")]))
    assert rc.is_teammate_transcript(records, head_records=[], truncated=True) is True, (
        "cannot see the brief region => treat as teammate (never brick a worker)"
    )
    assert rc.session_engaged_pipeline(records, head_records=[], truncated=True) is None, (
        "no invocation in either slice of a truncated transcript is AMBIGUOUS"
    )


def test_cli_mark_complete_guarded_by_worklist(workspace: Path) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline")
    sr_dir = workspace / ".architect-team" / "solution-requirements"
    sr_dir.mkdir(parents=True)
    (sr_dir / "SR-1.json").write_text(json.dumps(
        {"solution_id": "SR-1", "status": "open", "origin": {"kind": "editability-gap"}}
    ), encoding="utf-8")
    r = _cli(["--mark-complete"], workspace)
    assert r.returncode == 1 and "REFUSED" in r.stderr, (
        "open worklist debt must refuse --mark-complete"
    )
    assert rc.read_marker(workspace)["status"] == "active"
    r2 = _cli(["--mark-complete", "--force"], workspace)
    assert r2.returncode == 0 and json.loads(r2.stdout)["status"] == "complete"
    log = workspace / ".architect-team" / rc.COMPLETION_LOG_FILENAME
    assert log.exists() and "forced" in log.read_text(encoding="utf-8")


def test_completion_log_written_on_lifecycle_exits(workspace: Path) -> None:
    rc.engage_marker(workspace, "architect-team-pipeline")
    rc.mark_complete(workspace)
    rc.engage_marker(workspace, "bug-fix-pipeline")
    rc.stand_down(workspace, "user said by hand")
    text = (workspace / ".architect-team" / rc.COMPLETION_LOG_FILENAME).read_text(encoding="utf-8")
    assert "mark-complete" in text and "stand-down" in text
