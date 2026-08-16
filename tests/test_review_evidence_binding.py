"""v3.62.0 — evidence binding: `reviews/<id>.json` is not a unique key.

Field report (2026-08-16, measured live in BOTH directions on a real run):
harness task ids are small integers reused across lanes and runs, and the
review gate keyed evidence by the bare id. Two polarities of one defect:

  R1 (false PASS, unsound): pointing a manifest at "17" made the hook exit 0
     on ANOTHER lane's clean review — a task completed on borrowed evidence.
  R2 (false BLOCK, unusable): completing task 20 was blocked by
     lead-fullscale-local's FAILING review of a different task under the
     same reused id.

The fix binds evidence to the task identity beyond the id: evidence carries
`task_subject`, the gate resolves the completing task's own subject from the
harness store (payload session_id -> session-<sid8>/<id>.json), and

  * bound + matching      -> governs (pass or fail, as today);
  * bound + mismatched    -> INVISIBLE to this task: it neither passes nor
                             blocks it. With no matching evidence of its own
                             the task is refused with an ACTIONABLE message
                             naming the collision and the variant path to
                             write (`reviews/<id>.<slug>.json`) — so the
                             colliding lane writes its OWN evidence beside
                             the foreign file instead of fighting over one
                             name;
  * unbound (legacy)      -> exactly today's behaviour, pinned below as the
                             MIGRATION BOUNDARY;
  * subject unresolvable  -> legacy behaviour (fail-open on infrastructure —
                             the harness always sends session_id on real
                             events; a payload without one is a synthetic or
                             degraded case, and inventing a NEW block there
                             would be the F9 wedge shape).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.hook_runner import run_hook as _run
from tests.test_review_gate_task import _make_payload, _valid_evidence, _write_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "hooks" / "review-gate-task.py"

SESSION = "sess-orchestrator"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / ".architect-team" / "reviews").mkdir(parents=True)
    (tmp_path / ".architect-team" / "teammates").mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def tasks_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "harness-tasks"
    root.mkdir()
    monkeypatch.setenv("CT6_TASKS_ROOT", str(root))
    return root


def _harness_task(tasks_root: Path, session_id: str, task_id: str, subject: str) -> None:
    d = tasks_root / f"session-{session_id[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{task_id}.json").write_text(
        json.dumps({"id": task_id, "subject": subject, "status": "in_progress"}),
        encoding="utf-8",
    )


def _payload(task_id: str) -> dict:
    p = _make_payload(task_id, "completed")
    p["session_id"] = SESSION
    return p


def _bound(evidence: dict, subject: str) -> dict:
    evidence = dict(evidence)
    evidence["task_subject"] = subject
    return evidence


def _write_review(workspace: Path, name: str, evidence: dict) -> None:
    (workspace / ".architect-team" / "reviews" / name).write_text(
        json.dumps(evidence), encoding="utf-8"
    )


# --- R1: the false-pass polarity ---------------------------------------------


def test_R1_foreign_clean_review_same_id_is_refused(
    workspace: Path, tasks_root: Path
) -> None:
    """The measured live escape: a manifest pointed at '17' rides another
    lane's clean review to exit 0. With binding, the foreign evidence is
    visible as FOREIGN and the completion is refused."""
    _harness_task(tasks_root, SESSION, "17", "R1 mine: wire the parser")
    _write_manifest(workspace, "backend-a", ["17"])
    _write_review(workspace, "17.json",
                  _bound(_valid_evidence("17"), "F other lane: cache warmup"))
    r = _run(SCRIPT, workspace, _payload("17"))
    assert r.returncode == 2, f"borrowed clean evidence must not pass: {r.stderr!r}"
    low = r.stderr.lower()
    assert "reused" in low or "different task" in low, (
        "the block must name the id-collision, not a generic failure"
    )


# --- R2: the false-block polarity ----------------------------------------------


def test_R2_own_bound_evidence_governs_despite_foreign_failing_file(
    workspace: Path, tasks_root: Path
) -> None:
    """The mirror image measured live: a same-id FAILING review from another
    lane blocked an unrelated completion. With binding, the lane writes its
    OWN evidence as a variant file and the gate selects by subject."""
    _harness_task(tasks_root, SESSION, "20", "R2 mine: ship the exporter")
    _write_manifest(workspace, "backend-b", ["20"])
    foreign = _bound(_valid_evidence("20"), "F other lane: their thing")
    foreign["spec_review"] = "fail"
    _write_review(workspace, "20.json", foreign)
    _write_review(workspace, "20.r2-mine.json",
                  _bound(_valid_evidence("20"), "R2 mine: ship the exporter"))
    r = _run(SCRIPT, workspace, _payload("20"))
    assert r.returncode == 0, (
        f"another lane's failing review must not block a task that carries its "
        f"own bound, passing evidence: {r.stderr!r}"
    )


def test_R2_mismatch_only_block_is_actionable(
    workspace: Path, tasks_root: Path
) -> None:
    """No own evidence yet + a foreign failing file: still refused (a
    manifested completion never passes evidence-free), but for the RIGHT
    reason with the RIGHT remedy — write your own variant file — instead of
    'someone else's review failed you'."""
    _harness_task(tasks_root, SESSION, "20", "R2 mine: ship the exporter")
    _write_manifest(workspace, "backend-b", ["20"])
    foreign = _bound(_valid_evidence("20"), "F other lane: their thing")
    foreign["spec_review"] = "fail"
    _write_review(workspace, "20.json", foreign)
    r = _run(SCRIPT, workspace, _payload("20"))
    assert r.returncode == 2
    low = r.stderr.lower()
    assert "bound to" in low, (
        "the collision block must NAME the foreign binding — a generic "
        "missing-evidence message is not this block (witness W3's escape: "
        "with the collision branch dropped, the fallback message also said "
        "'reused', and this pin could not tell the two apart)"
    )
    assert "f other lane" in low, "the foreign subject itself must be quoted"
    assert f"20.{'r2-mine-ship-the-exporter'[:40]}" in r.stderr or "20." in r.stderr
    assert "spec_review" not in low, (
        "the foreign file's verdict details are not this task's failure"
    )


def test_R1_and_R2_matching_bound_evidence_still_governs_normally(
    workspace: Path, tasks_root: Path
) -> None:
    """Binding narrows WHOSE evidence counts, never weakens WHAT it must say:
    a matching bound FAIL still blocks, a matching bound PASS still passes."""
    _harness_task(tasks_root, SESSION, "21", "mine: the importer")
    _write_manifest(workspace, "backend-c", ["21"])
    ok = _bound(_valid_evidence("21"), "mine: the importer")
    _write_review(workspace, "21.json", ok)
    assert _run(SCRIPT, workspace, _payload("21")).returncode == 0
    bad = dict(ok)
    bad["spec_review"] = "fail"
    _write_review(workspace, "21.json", bad)
    r = _run(SCRIPT, workspace, _payload("21"))
    assert r.returncode == 2
    assert "spec_review" in r.stderr.lower()


# --- the migration boundary, pinned ---------------------------------------------


def test_legacy_unbound_evidence_keeps_current_behaviour(
    workspace: Path, tasks_root: Path
) -> None:
    """Evidence written before this release carries no binding. It governs by
    id exactly as before — in BOTH directions — so no in-flight run breaks.
    This is the named migration boundary, not an oversight."""
    _harness_task(tasks_root, SESSION, "30", "mine: anything")
    _write_manifest(workspace, "backend-d", ["30"])
    _write_review(workspace, "30.json", _valid_evidence("30"))
    assert _run(SCRIPT, workspace, _payload("30")).returncode == 0
    bad = _valid_evidence("30")
    bad["spec_review"] = "fail"
    _write_review(workspace, "30.json", bad)
    assert _run(SCRIPT, workspace, _payload("30")).returncode == 2


def test_unresolvable_subject_falls_back_to_legacy(
    workspace: Path, tasks_root: Path
) -> None:
    """No session_id in the payload -> the completing task's subject cannot be
    resolved -> bound evidence cannot be verified -> legacy behaviour, never a
    NEW block on missing infrastructure. Real harness events always carry
    session_id; this is the degraded path, pinned as fail-open and named a
    boundary in the docs."""
    _harness_task(tasks_root, SESSION, "31", "mine: unreachable")
    _write_manifest(workspace, "backend-e", ["31"])
    _write_review(workspace, "31.json",
                  _bound(_valid_evidence("31"), "F other lane: foreign"))
    p = _make_payload("31", "completed")  # deliberately NO session_id
    r = _run(SCRIPT, workspace, p)
    assert r.returncode == 0, f"missing infra must not invent a new block: {r.stderr!r}"


def test_binding_match_is_case_and_whitespace_insensitive(
    workspace: Path, tasks_root: Path
) -> None:
    """A reviewer typing the subject with different case or spacing is the
    SAME task — normalization is casefold + whitespace-collapse, and dropping
    it would false-refuse honest evidence (witness W5)."""
    _harness_task(tasks_root, SESSION, "22", "mine: Ship   the Exporter")
    _write_manifest(workspace, "backend-f", ["22"])
    _write_review(workspace, "22.json",
                  _bound(_valid_evidence("22"), "MINE:  ship the  exporter"))
    r = _run(SCRIPT, workspace, _payload("22"))
    assert r.returncode == 0, f"case/whitespace variance must still match: {r.stderr!r}"

