"""Tests for the v3.16.0 responsive + parallel-lane inject mechanism.

The feature: an injected `parallel-problem` is worked in a SANCTIONED concurrent
in-run LANE (a background team holding a disjoint file-scope lock) instead of
being folded sequentially, and the orchestrator polls the inbox on every wake
(not only at phase boundaries). The orchestrator behavior itself is prompt-driven
doctrine; these tests pin the CODE surface (`parallel-problem` classification +
the `lane_id` linkage), the end-to-end MECHANISM (the dogfood: append -> read
promptly -> lock-isolated lane -> mark processed -> verifier counts it), the lock
isolation that makes a lane safe, and the doctrine wording across the skills/
command/verifier so a future edit can't silently drop it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hooks.inflight_inbox import (
    CLASSIFICATIONS,
    append_clarification,
    mark_processed,
    read_inbox,
    unprocessed_messages,
)
from hooks.locks import acquire_lock, globs_intersect, release_lock
from hooks.vao_tools import verify_inflight_clarifications_processed

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "lane-run"


# --------------------------------------------------------------------------- #
# code surface — the parallel-problem classification + lane_id linkage
# --------------------------------------------------------------------------- #

def test_parallel_problem_is_a_classification() -> None:
    assert "parallel-problem" in CLASSIFICATIONS


def test_append_initializes_lane_id_none(tmp_path: Path) -> None:
    msg = append_clarification(tmp_path, RUN_ID, "fix the export", injected_via="slash-command")
    assert msg["lane_id"] is None
    assert msg["classification"] is None


def test_parallel_problem_requires_lane_id(tmp_path: Path) -> None:
    msg = append_clarification(tmp_path, RUN_ID, "a separable problem")
    with pytest.raises(ValueError):
        mark_processed(tmp_path, RUN_ID, msg["message_id"],
                       classification="parallel-problem", action_taken="spawned a lane")


def test_parallel_problem_records_lane_id(tmp_path: Path) -> None:
    msg = append_clarification(tmp_path, RUN_ID, "a separable problem")
    updated = mark_processed(tmp_path, RUN_ID, msg["message_id"],
                             classification="parallel-problem",
                             action_taken="spawned lane B on docs/**",
                             lane_id="lane-B")
    assert updated["lane_id"] == "lane-B"
    assert updated["classification"] == "parallel-problem"
    assert updated["processed_at"] is not None
    assert read_inbox(tmp_path, RUN_ID)[0]["lane_id"] == "lane-B"  # persisted


def test_other_classifications_still_work_without_lane_id(tmp_path: Path) -> None:
    for cls in ("scope-amendment", "clarification", "out-of-scope"):
        m = append_clarification(tmp_path, RUN_ID, f"msg {cls}")
        u = mark_processed(tmp_path, RUN_ID, m["message_id"], classification=cls, action_taken="ok")
        assert u["classification"] == cls


# --------------------------------------------------------------------------- #
# end-to-end dogfood: append -> read promptly -> lock-isolated lane -> processed
# --------------------------------------------------------------------------- #

def test_parallel_lane_end_to_end(tmp_path: Path) -> None:
    locks = tmp_path / "locks"
    # the in-flight run holds the main file scope
    main = acquire_lock("hooks/**", 600, "main-team", locks_dir=locks)
    assert main["status"] == "acquired"

    # a separable problem is injected
    msg = append_clarification(tmp_path, RUN_ID, "also fix the docs generator")
    # the orchestrator reads it promptly (it is unprocessed, available immediately)
    assert any(m["message_id"] == msg["message_id"] for m in unprocessed_messages(tmp_path, RUN_ID))

    # a DISJOINT lane scope acquires its own lock and runs concurrently
    lane = acquire_lock("docs/**", 600, "lane-docs", locks_dir=locks)
    assert lane["status"] == "acquired"  # disjoint -> true parallel

    # the lane is recorded on the message
    mark_processed(tmp_path, RUN_ID, msg["message_id"],
                   classification="parallel-problem",
                   action_taken="spawned lane lane-docs on docs/**",
                   lane_id=lane["lock_id"])

    # the Phase-8 verifier counts it processed (NOT silently ignored)
    verdict = verify_inflight_clarifications_processed(tmp_path, RUN_ID)
    assert verdict["valid"] is True
    assert verdict["unprocessed_count"] == 0

    release_lock(lane["lock_id"], locks_dir=locks)
    release_lock(main["lock_id"], locks_dir=locks)


def test_overlapping_lane_scope_is_blocked(tmp_path: Path) -> None:
    # lane isolation is enforced by the existing lock layer: an OVERLAPPING scope
    # cannot run as a concurrent lane (it must queue or fold, never collide).
    locks = tmp_path / "locks"
    main = acquire_lock("hooks/**", 600, "main-team", locks_dir=locks)
    assert main["status"] == "acquired"
    overlapping = acquire_lock("hooks/inflight_inbox.py", 600, "lane-x", locks_dir=locks)
    assert overlapping["status"] == "blocked"
    assert globs_intersect("hooks/**", "hooks/inflight_inbox.py")
    release_lock(main["lock_id"], locks_dir=locks)


# --------------------------------------------------------------------------- #
# doctrine — the orchestrator behavior is prompt-driven; pin the wording so a
# future edit cannot silently drop the responsiveness / parallel-lane protocol
# --------------------------------------------------------------------------- #

def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_canonical_documents_parallel_lanes() -> None:
    body = _read("skills/common-pipeline-conventions/SKILL.md")
    assert "### Parallel lanes (v3.16.0)" in body
    assert "parallel-problem" in body
    # the sibling-vs-lane distinction is explicitly drawn
    assert "is NOT this anti-pattern" in body or "is NOT a sibling" in body


def test_canonical_documents_poll_on_every_wake_and_honest_limit() -> None:
    body = _read("skills/common-pipeline-conventions/SKILL.md").lower()
    assert "on every wake" in body
    # the honest harness constraint is stated (polling, not async push/preemption)
    assert "not preemption" in body or "not an event-driven" in body


def test_canonical_documents_isolation_and_dispatch_residuals() -> None:
    # the adversarial-review honesty fixes must stay documented:
    body = _read("skills/common-pipeline-conventions/SKILL.md")
    # (a) lock isolation is file-glob/advisory; cdlg_overlap is NOT wired in
    assert "Isolation residual" in body
    assert "NOT wired into `acquire_lock`" in body
    # (b) subagents-mode degrades lanes to sequential (no overclaim of concurrency)
    assert "Dispatch-mode caveat (v3.16.0)" in body
    assert "subagents-mode fallback" in body
    # (c) a failed lane spawn downgrades the classification (never wedges Phase 8)
    assert "If the lane FAILS to spawn" in body


def test_pipeline_bodies_updated() -> None:
    for p in ("skills/architect-team-pipeline/SKILL.md",
              "skills/bug-fix-pipeline/SKILL.md",
              "skills/mini-architect-team-pipeline/SKILL.md"):
        body = _read(p)
        assert "background-dispatch return / wake" in body, p
        assert "parallel-problem" in body, p


def test_inject_command_updated() -> None:
    body = _read("commands/inject.md")
    assert "parallel-problem" in body
    assert "wake" in body.lower()


def test_verifier_remediation_mentions_parallel_problem() -> None:
    assert "parallel-problem" in _read("hooks/vao/registry_inflight.py")
