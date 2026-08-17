"""The Bauplan dispatch record — AC3/AC4's evidence artifact (SRC-003 / D6).

AC3 binds "an armed run dispatches at least one `bauplan-*` skill" to run state
rather than to `hooks/skill_invocation_audit.py`, whose expectations are built
from CT6's OWN canonical commands and would never carry a third-party dispatch.
These tests pin the artifact AC3 and AC4 read.

Hermetic: every write lands under tmp_path; timestamps are injected, so nothing
here reads a clock and the assertions are exact.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bauplan import dispatch_record as dr

TS = "2026-08-17T07:30:00Z"


def _armed_run(tmp_path: Path) -> tuple[Path, str]:
    return tmp_path, "bauplan-warehouse"


# --------------------------------------------------------------------------- #
# The empty / absent case — AC4's "zero dispatches" must be readable, not a crash
# --------------------------------------------------------------------------- #


def test_absent_record_reads_as_empty_not_an_error(tmp_path: Path) -> None:
    """A run that never armed has no file. AC4 asserts zero dispatches against
    exactly this state, so it must read as an empty record rather than raise."""
    ws, slug = _armed_run(tmp_path)
    assert dr.read_record(ws, slug) == {
        "dispatches": [],
        "missed_capabilities": [],
        "precedence_conflicts": [],
    }
    assert dr.dispatched_skills(ws, slug) == []
    assert dr.summarize(ws, slug)["dispatch_count"] == 0
    assert not dr.record_path(ws, slug).exists()


def test_a_corrupt_record_degrades_to_empty_rather_than_crashing(tmp_path: Path) -> None:
    """This file is evidence ABOUT a run, never a gate ON it: a corrupt record
    must not take down the lane that is trying to append to it."""
    ws, slug = _armed_run(tmp_path)
    path = dr.record_path(ws, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"{not valid json at all")
    assert dr.read_record(ws, slug)["dispatches"] == []
    # and an append still succeeds, replacing the corrupt content
    dr.record_dispatch(ws, slug, skill="bauplan-explore-data", phase="D0",
                       teammate="data-eng", ts=TS)
    assert dr.dispatched_skills(ws, slug) == ["bauplan-explore-data"]


# --------------------------------------------------------------------------- #
# AC3 — an armed run records its dispatches
# --------------------------------------------------------------------------- #


def test_recording_a_dispatch_captures_skill_phase_teammate_and_ts(tmp_path: Path) -> None:
    """AC3 names exactly these four fields."""
    ws, slug = _armed_run(tmp_path)
    entry = dr.record_dispatch(ws, slug, skill="bauplan-data-pipeline",
                               phase="D2-D6", teammate="backend-data", ts=TS)
    assert entry == {"skill": "bauplan-data-pipeline", "phase": "D2-D6",
                     "teammate": "backend-data", "ts": TS}
    on_disk = json.loads(dr.record_path(ws, slug).read_text(encoding="utf-8"))
    assert on_disk["dispatches"] == [entry]


def test_dispatches_accumulate_in_order_across_calls(tmp_path: Path) -> None:
    ws, slug = _armed_run(tmp_path)
    for skill, phase in (("bauplan-explore-data", "D0"),
                         ("bauplan-data-assessment", "D0"),
                         ("bauplan-data-quality-checks", "Stage 6")):
        dr.record_dispatch(ws, slug, skill=skill, phase=phase, teammate="t", ts=TS)
    assert dr.dispatched_skills(ws, slug) == [
        "bauplan-explore-data", "bauplan-data-assessment", "bauplan-data-quality-checks",
    ]
    assert dr.summarize(ws, slug)["dispatch_count"] == 3


def test_repeated_dispatch_of_one_skill_counts_once_in_the_skill_list(tmp_path: Path) -> None:
    """`dispatched_skills` answers WHICH skills ran; `dispatch_count` answers how
    many times. Conflating them would let one skill dispatched twice look like
    two skills covered."""
    ws, slug = _armed_run(tmp_path)
    dr.record_dispatch(ws, slug, skill="bauplan-safe-ingestion", phase="D2", teammate="t", ts=TS)
    dr.record_dispatch(ws, slug, skill="bauplan-safe-ingestion", phase="D4", teammate="t", ts=TS)
    assert dr.dispatched_skills(ws, slug) == ["bauplan-safe-ingestion"]
    assert dr.summarize(ws, slug)["dispatch_count"] == 2


def test_a_non_bauplan_skill_is_refused(tmp_path: Path) -> None:
    """The record evidences THIS capability. Admitting an arbitrary skill name
    would let an unrelated dispatch satisfy AC3's 'at least one bauplan-*'."""
    ws, slug = _armed_run(tmp_path)
    with pytest.raises(ValueError, match="not a bauplan skill"):
        dr.record_dispatch(ws, slug, skill="data-engineering-exploration",
                           phase="D0", teammate="t", ts=TS)
    assert dr.read_record(ws, slug)["dispatches"] == []


# --------------------------------------------------------------------------- #
# SRC-003 — warn-and-degrade must be legible, not silent
# --------------------------------------------------------------------------- #


def test_missed_capability_records_the_remediation_lines(tmp_path: Path) -> None:
    """A degraded run that names the miss without naming the fix leaves the
    reader knowing something was lost and not how to recover it."""
    ws, slug = _armed_run(tmp_path)
    entry = dr.record_missed_capability(
        ws, slug, capability="bauplan@bauplan-skills",
        remediation=["/plugin marketplace add BauplanLabs/bauplan-skills",
                     "/plugin install bauplan@bauplan-skills"],
        ts=TS,
    )
    assert entry["remediation"] == [
        "/plugin marketplace add BauplanLabs/bauplan-skills",
        "/plugin install bauplan@bauplan-skills",
    ]
    assert dr.summarize(ws, slug)["missed_capability_count"] == 1


def test_missed_capability_without_remediation_is_refused(tmp_path: Path) -> None:
    ws, slug = _armed_run(tmp_path)
    with pytest.raises(ValueError, match="remediation lines are required"):
        dr.record_missed_capability(ws, slug, capability="bauplan@bauplan-skills",
                                    remediation=[], ts=TS)
    with pytest.raises(ValueError, match="remediation lines are required"):
        dr.record_missed_capability(ws, slug, capability="bauplan@bauplan-skills",
                                    remediation=["   "], ts=TS)


def test_a_degraded_run_records_no_dispatches(tmp_path: Path) -> None:
    """The two lists are independent: degrading records a miss and leaves the
    dispatch list empty, so AC4's zero-dispatch assertion still holds."""
    ws, slug = _armed_run(tmp_path)
    dr.record_missed_capability(ws, slug, capability="bauplan@bauplan-skills",
                                remediation=["/plugin install bauplan@bauplan-skills"], ts=TS)
    summary = dr.summarize(ws, slug)
    assert summary["dispatch_count"] == 0
    assert summary["missed_capability_count"] == 1


# --------------------------------------------------------------------------- #
# The augment-never-replace carve-out — a governed conflict is RECORDED
# --------------------------------------------------------------------------- #


def test_precedence_conflict_is_recorded_with_both_sides(tmp_path: Path) -> None:
    """The platform rule may win on the platform's own operations, but only with
    the conflict recorded — otherwise a silently-overridden CT6 default is
    indistinguishable from one that never applied."""
    ws, slug = _armed_run(tmp_path)
    entry = dr.record_precedence_conflict(
        ws, slug,
        operation="publish to main",
        bauplan_rule="never write directly to main; branch and merge to publish",
        ct6_default="write to the working branch",
        resolution="bauplan rule governed",
        ts=TS,
    )
    assert entry["bauplan_rule"] and entry["ct6_default"] and entry["resolution"]
    assert dr.summarize(ws, slug)["precedence_conflict_count"] == 1


# --------------------------------------------------------------------------- #
# Path discipline
# --------------------------------------------------------------------------- #


def test_record_path_is_lane_scoped(tmp_path: Path) -> None:
    ws, slug = _armed_run(tmp_path)
    assert dr.record_path(ws, slug, "data-eng") == (
        tmp_path / ".architect-team" / "data-eng" / slug / "bauplan-dispatches.json"
    )
    assert dr.record_path(ws, slug, "bug-fix") == (
        tmp_path / ".architect-team" / "bug-fix" / slug / "bauplan-dispatches.json"
    )


def test_the_two_lanes_keep_separate_records(tmp_path: Path) -> None:
    ws, slug = _armed_run(tmp_path)
    dr.record_dispatch(ws, slug, skill="bauplan-explore-data", phase="D0",
                       teammate="t", ts=TS, lane="data-eng")
    dr.record_dispatch(ws, slug, skill="bauplan-debug-and-fix-pipeline", phase="B1",
                       teammate="t", ts=TS, lane="bug-fix")
    assert dr.dispatched_skills(ws, slug, "data-eng") == ["bauplan-explore-data"]
    assert dr.dispatched_skills(ws, slug, "bug-fix") == ["bauplan-debug-and-fix-pipeline"]


@pytest.mark.parametrize("bad", ["", "..", ".", "a/b", "a\\b"])
def test_an_unsafe_slug_is_refused(tmp_path: Path, bad: str) -> None:
    """A slug is a directory name. Traversal or an empty name would scatter
    evidence outside the run's own state directory, where the gate cannot find it."""
    with pytest.raises(ValueError, match="invalid run slug"):
        dr.record_path(tmp_path, bad)


def test_an_unknown_lane_is_refused(tmp_path: Path) -> None:
    """A typo must surface rather than silently create a stray directory."""
    with pytest.raises(ValueError, match="unknown lane"):
        dr.record_path(tmp_path, "slug", "data-engineering")


def test_writes_are_deterministic_no_clock_or_env_read(tmp_path: Path) -> None:
    """Same inputs, same bytes — a resumed run records the same thing twice
    rather than drifting, and a test can assert exact content."""
    a, b = tmp_path / "a", tmp_path / "b"
    for ws in (a, b):
        dr.record_dispatch(ws, "s", skill="bauplan-explore-data", phase="D0",
                           teammate="t", ts=TS)
    assert dr.record_path(a, "s").read_bytes() == dr.record_path(b, "s").read_bytes()
