"""Unit tests for hooks/review-gate-task.py.

The hook reads stdin (JSON), inspects the TaskUpdate args, and exits:
- 0 if status != "completed", OR if status == "completed" AND review evidence is valid
- 2 (block) if status == "completed" AND review evidence is missing or invalid

We invoke the script as a subprocess and feed crafted stdin.
"""
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hooks import run_continuity as rc
from tests.helpers.hook_runner import run_hook as _run

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: The mutation seam (F7). When set, `script` resolves to a MUTATED COPY of the
#: hook so the mutation table at the bottom can re-run a named test against a
#: deliberately broken engine WITHOUT ever writing to the repo.
_SCRIPT_ENV = "CT6_TEST_GATE_SCRIPT"

#: Set in a mutation child so the table's own tests never recurse.
_CHILD_ENV = "CT6_TEST_GATE_MUTATION_CHILD"

_IS_CHILD_RUN = os.environ.get(_CHILD_ENV) == "1"


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    override = os.environ.get(_SCRIPT_ENV, "").strip()
    if override:
        return Path(override)
    return plugin_root / "hooks" / "review-gate-task.py"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ambient kill-switch or session id leaks into these subprocesses.

    The session-var list is DERIVED from `rc.SESSION_ID_ENV_VARS` rather than
    retyped: the suite runs inside a real Claude Code session that exports
    `CLAUDE_CODE_SESSION_ID`, so a var added to the constant but missed here
    would leak the harness's own session into every fixture. Mirrors the
    sibling fixture in `tests/test_completion_status_integrity.py`."""
    for var in ("CT6_TASK_GATE_DISABLED", "CT6_RUN_CONTINUITY_DISABLED",
                *rc.SESSION_ID_ENV_VARS):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A temp workspace that becomes the hook script's cwd."""
    (tmp_path / ".architect-team" / "reviews").mkdir(parents=True)
    (tmp_path / ".architect-team" / "teammates").mkdir(parents=True)
    return tmp_path


def _make_payload(task_id: str, status: str) -> dict:
    return {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": task_id, "status": status},
    }


def _valid_evidence(task_id: str) -> dict:
    """Evidence schema v7 — must match hooks/review_evidence_schema.py exactly.

    The 17 top-level fields are the teammate's self-review (the 12 v6 fields
    plus the v7 VAO fields: oracle_match_review, baseline_clean_review,
    no_fake_data_review, adversarial_review, skill_invocation_audit). The
    `independent_review` block (v5, v0.9.13) is the verdict of an independent
    task-reviewer agent — `reviewer` must differ from `teammate`.
    """
    return {
        "schema_version": 7,
        "task_id": task_id,
        "teammate": "backend-test",
        "completed_at": "2026-05-16T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 3, "passing": 3, "unit": ["t1", "t2", "t3"], "integration": [], "e2e": []},
        "demo_artifact": "curl http://example",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "backend-only slice; no frontend files touched",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "backend-only slice; integration tests count as the qualifying kind for this slice",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "backend-only slice with no frontend; no cross-layer surface to integration-test front-to-back",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "backend-only slice; no UI/frontend interactive surface to verify",
        # v7 VAO fields — all 'n/a' for the synthetic backend test fixture
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "synthetic test fixture; no oracle artifact in scope",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "synthetic test fixture; no real teammate tool-call log",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "synthetic test fixture; no production-code diff in scope",
        "adversarial_review": "n/a",
        "adversarial_review_note": "synthetic test fixture; no Phase 3 adversarial dispatch in scope",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "synthetic test fixture; no session transcript / ledger in scope",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-05-16T11:00:00Z",
        },
    }


def _write_manifest(workspace: Path, name: str, task_ids: list[str]) -> None:
    """Create a teammate manifest claiming ownership of the given task IDs.

    The hook only enforces the review gate on tasks listed in some
    teammate's expected_review_evidence — so tests that exercise the gate
    must first publish a manifest declaring the task as a teammate task.
    """
    (workspace / ".architect-team" / "teammates" / f"{name}.json").write_text(
        json.dumps({
            "schema_version": 1,
            "teammate": name,
            "spawned_at": "2026-05-16T09:00:00Z",
            "task_ids": task_ids,
            "files_owned": [],
            "expected_review_evidence": task_ids,
        }),
        encoding="utf-8",
    )


def test_exits_zero_when_status_not_completed(script: Path, workspace: Path) -> None:
    r = _run(script, workspace, _make_payload("T-1", "in_progress"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_two_when_completed_but_no_evidence(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-2"])
    r = _run(script, workspace, _make_payload("T-2", "completed"))
    assert r.returncode == 2
    assert "T-2" in r.stderr


def test_exits_zero_when_completed_with_valid_evidence(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-3"])
    (workspace / ".architect-team" / "reviews" / "T-3.json").write_text(
        json.dumps(_valid_evidence("T-3")), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-3", "completed"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_two_when_spec_review_failing(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-4"])
    ev = _valid_evidence("T-4")
    ev["spec_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-4.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-4", "completed"))
    assert r.returncode == 2
    assert "spec_review" in r.stderr


def test_exits_two_when_tests_added_not_equal_passing(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-5"])
    ev = _valid_evidence("T-5")
    ev["tests"]["passing"] = 2  # added is 3
    (workspace / ".architect-team" / "reviews" / "T-5.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-5", "completed"))
    assert r.returncode == 2
    assert "tests" in r.stderr


def test_exits_two_when_real_not_stubbed_false(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-6"])
    ev = _valid_evidence("T-6")
    ev["real_not_stubbed"] = False
    (workspace / ".architect-team" / "reviews" / "T-6.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-6", "completed"))
    assert r.returncode == 2
    assert "real_not_stubbed" in r.stderr


def test_exits_two_when_files_changed_empty(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-7"])
    ev = _valid_evidence("T-7")
    ev["files_changed"] = []
    (workspace / ".architect-team" / "reviews" / "T-7.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-7", "completed"))
    assert r.returncode == 2
    assert "files_changed" in r.stderr


def test_exits_zero_on_unrelated_tool(script: Path, workspace: Path) -> None:
    # Hook should ignore tool calls that aren't TaskUpdate.
    payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}
    r = _run(script, workspace, payload)
    assert r.returncode == 0


def test_exits_zero_when_task_not_in_any_manifest(script: Path, workspace: Path) -> None:
    """REQ-007: hook scopes its enforcement to architect-team teammate tasks.

    TaskUpdate→completed for a task ID that isn't listed in any teammate's
    expected_review_evidence must NOT block. This covers orchestrator-internal
    task tracking, user TaskCreate/TaskUpdate flows, and any other workflow
    that uses TaskUpdate outside the architect-team pipeline.
    """
    # Manifest exists but assigns a DIFFERENT task; T-99 is not a teammate task.
    _write_manifest(workspace, "backend-test", ["T-1", "T-2"])
    r = _run(script, workspace, _make_payload("T-99", "completed"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_zero_when_no_teammates_dir(script: Path, workspace: Path, tmp_path: Path) -> None:
    """Absent .architect-team/teammates/ dir means no architect-team workflow
    is in progress at all. Don't block ANY TaskUpdate."""
    # Use a fresh tmp dir that has no .architect-team layout at all.
    pristine = tmp_path / "pristine"
    pristine.mkdir()
    r = _run(script, pristine, _make_payload("T-anything", "completed"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


@pytest.mark.parametrize("unsafe_id", [
    "T-1/../../etc/passwd",
    "T-1\\..\\..\\malicious",
    ".hidden",
    "..",
])
def test_exits_two_when_taskid_has_path_traversal(
    script: Path, workspace: Path, unsafe_id: str
) -> None:
    """REQ-002: task_id values containing path-traversal chars must be rejected."""
    _write_manifest(workspace, "backend-test", [unsafe_id])
    r = _run(script, workspace, _make_payload(unsafe_id, "completed"))
    assert r.returncode == 2, f"expected exit 2 for unsafe id {unsafe_id!r}, stderr={r.stderr!r}"
    assert unsafe_id in r.stderr or "path-traversal" in r.stderr, (
        f"stderr should name the rejected id; got: {r.stderr!r}"
    )


def test_exits_two_when_quality_review_failing(script: Path, workspace: Path) -> None:
    """REQ-003: quality_review != 'pass' must be blocked."""
    _write_manifest(workspace, "backend-test", ["T-10"])
    ev = _valid_evidence("T-10")
    ev["quality_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-10.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-10", "completed"))
    assert r.returncode == 2
    assert "quality_review" in r.stderr


def test_exits_two_when_reuse_compliance_failing(script: Path, workspace: Path) -> None:
    """REQ-003: reuse_compliance != 'ok' must be blocked."""
    _write_manifest(workspace, "backend-test", ["T-11"])
    ev = _valid_evidence("T-11")
    ev["reuse_compliance"] = "pending"
    (workspace / ".architect-team" / "reviews" / "T-11.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-11", "completed"))
    assert r.returncode == 2
    assert "reuse_compliance" in r.stderr


@pytest.mark.parametrize("artifact", ["", "   "])
def test_exits_two_when_demo_artifact_empty(
    script: Path, workspace: Path, artifact: str
) -> None:
    """REQ-003: empty or whitespace-only demo_artifact must be blocked."""
    _write_manifest(workspace, "backend-test", ["T-12"])
    ev = _valid_evidence("T-12")
    ev["demo_artifact"] = artifact
    (workspace / ".architect-team" / "reviews" / "T-12.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-12", "completed"))
    assert r.returncode == 2
    assert "demo_artifact" in r.stderr


def test_exits_two_when_tests_added_zero(script: Path, workspace: Path) -> None:
    """REQ-003: tests.added == 0 must be blocked."""
    _write_manifest(workspace, "backend-test", ["T-13"])
    ev = _valid_evidence("T-13")
    ev["tests"]["added"] = 0
    ev["tests"]["passing"] = 0
    (workspace / ".architect-team" / "reviews" / "T-13.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-13", "completed"))
    assert r.returncode == 2
    assert "tests" in r.stderr


def test_exits_two_when_evidence_json_malformed(script: Path, workspace: Path) -> None:
    """REQ-003: malformed evidence JSON (not valid JSON) must be blocked."""
    _write_manifest(workspace, "backend-test", ["T-14"])
    (workspace / ".architect-team" / "reviews" / "T-14.json").write_text(
        "not json", encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-14", "completed"))
    assert r.returncode == 2
    assert "T-14" in r.stderr


# v0.5.0 — visual-fidelity-reconciliation enforcement


def test_exits_zero_when_visual_fidelity_pass(script: Path, workspace: Path) -> None:
    """v0.5.0: visual_fidelity_review='pass' is a valid completion."""
    _write_manifest(workspace, "frontend-test", ["T-V1"])
    ev = _valid_evidence("T-V1")
    ev["visual_fidelity_review"] = "pass"
    ev.pop("visual_fidelity_review_note", None)  # note not required when value is "pass"
    (workspace / ".architect-team" / "reviews" / "T-V1.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-V1", "completed"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_two_when_visual_fidelity_fail(script: Path, workspace: Path) -> None:
    """v0.5.0: visual_fidelity_review='fail' must block — teammate must escalate."""
    _write_manifest(workspace, "frontend-test", ["T-V2"])
    ev = _valid_evidence("T-V2")
    ev["visual_fidelity_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-V2.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-V2", "completed"))
    assert r.returncode == 2
    assert "visual_fidelity_review" in r.stderr
    assert "escalate" in r.stderr.lower() or "handoff" in r.stderr.lower()


def test_exits_two_when_visual_fidelity_missing(script: Path, workspace: Path) -> None:
    """v0.5.0: visual_fidelity_review field absent entirely must block."""
    _write_manifest(workspace, "frontend-test", ["T-V3"])
    ev = _valid_evidence("T-V3")
    ev.pop("visual_fidelity_review", None)
    ev.pop("visual_fidelity_review_note", None)
    (workspace / ".architect-team" / "reviews" / "T-V3.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-V3", "completed"))
    assert r.returncode == 2
    assert "visual_fidelity_review" in r.stderr


@pytest.mark.parametrize("invalid_value", ["yes", "true", "ok", "passed", ""])
def test_exits_two_when_visual_fidelity_invalid_value(
    script: Path, workspace: Path, invalid_value: str
) -> None:
    """v0.5.0: visual_fidelity_review must be one of pass / n/a / fail."""
    _write_manifest(workspace, "frontend-test", ["T-V4"])
    ev = _valid_evidence("T-V4")
    ev["visual_fidelity_review"] = invalid_value
    (workspace / ".architect-team" / "reviews" / "T-V4.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-V4", "completed"))
    assert r.returncode == 2
    assert "visual_fidelity_review" in r.stderr


@pytest.mark.parametrize("missing_or_empty", [None, "", "   "])
def test_exits_two_when_visual_fidelity_na_without_note(
    script: Path, workspace: Path, missing_or_empty
) -> None:
    """v0.5.0: visual_fidelity_review='n/a' requires a non-empty justification note."""
    _write_manifest(workspace, "frontend-test", ["T-V5"])
    ev = _valid_evidence("T-V5")
    ev["visual_fidelity_review"] = "n/a"
    if missing_or_empty is None:
        ev.pop("visual_fidelity_review_note", None)
    else:
        ev["visual_fidelity_review_note"] = missing_or_empty
    (workspace / ".architect-team" / "reviews" / "T-V5.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-V5", "completed"))
    assert r.returncode == 2
    assert "visual_fidelity_review_note" in r.stderr or "n/a" in r.stderr


# v0.9.0 — test-completeness-review enforcement


def test_exits_zero_when_test_completeness_pass(script: Path, workspace: Path) -> None:
    """v0.9.0: test_completeness_review='pass' is a valid completion."""
    _write_manifest(workspace, "backend-test", ["T-T1"])
    ev = _valid_evidence("T-T1")
    ev["test_completeness_review"] = "pass"
    ev.pop("test_completeness_review_note", None)  # note not required when value is "pass"
    (workspace / ".architect-team" / "reviews" / "T-T1.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-T1", "completed"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_two_when_test_completeness_fail(script: Path, workspace: Path) -> None:
    """v0.9.0: test_completeness_review='fail' must block — teammate must escalate via SR auto-spawn."""
    _write_manifest(workspace, "backend-test", ["T-T2"])
    ev = _valid_evidence("T-T2")
    ev["test_completeness_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-T2.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-T2", "completed"))
    assert r.returncode == 2
    assert "test_completeness_review" in r.stderr
    assert "escalat" in r.stderr.lower() or "sr" in r.stderr.lower() or "auto-spawn" in r.stderr.lower()


def test_exits_two_when_test_completeness_missing(script: Path, workspace: Path) -> None:
    """v0.9.0: test_completeness_review field absent entirely must block."""
    _write_manifest(workspace, "backend-test", ["T-T3"])
    ev = _valid_evidence("T-T3")
    ev.pop("test_completeness_review", None)
    ev.pop("test_completeness_review_note", None)
    (workspace / ".architect-team" / "reviews" / "T-T3.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-T3", "completed"))
    assert r.returncode == 2
    assert "test_completeness_review" in r.stderr


@pytest.mark.parametrize("invalid_value", ["yes", "true", "ok", "passed", ""])
def test_exits_two_when_test_completeness_invalid_value(
    script: Path, workspace: Path, invalid_value: str
) -> None:
    """v0.9.0: test_completeness_review must be one of pass / n/a / fail."""
    _write_manifest(workspace, "backend-test", ["T-T4"])
    ev = _valid_evidence("T-T4")
    ev["test_completeness_review"] = invalid_value
    (workspace / ".architect-team" / "reviews" / "T-T4.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-T4", "completed"))
    assert r.returncode == 2
    assert "test_completeness_review" in r.stderr


@pytest.mark.parametrize("missing_or_empty", [None, "", "   "])
def test_exits_two_when_test_completeness_na_without_note(
    script: Path, workspace: Path, missing_or_empty
) -> None:
    """v0.9.0: test_completeness_review='n/a' requires a non-empty justification note."""
    _write_manifest(workspace, "backend-test", ["T-T5"])
    ev = _valid_evidence("T-T5")
    ev["test_completeness_review"] = "n/a"
    if missing_or_empty is None:
        ev.pop("test_completeness_review_note", None)
    else:
        ev["test_completeness_review_note"] = missing_or_empty
    (workspace / ".architect-team" / "reviews" / "T-T5.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-T5", "completed"))
    assert r.returncode == 2
    assert "test_completeness_review_note" in r.stderr or "n/a" in r.stderr


# v0.9.5 — integration-testing-review enforcement (real backend, not fake data)


def test_exits_zero_when_integration_testing_pass(script: Path, workspace: Path) -> None:
    """v0.9.5: integration_testing_review='pass' is a valid completion."""
    _write_manifest(workspace, "fullstack-test", ["T-I1"])
    ev = _valid_evidence("T-I1")
    ev["integration_testing_review"] = "pass"
    ev.pop("integration_testing_review_note", None)  # note not required when value is "pass"
    (workspace / ".architect-team" / "reviews" / "T-I1.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-I1", "completed"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_two_when_integration_testing_fail(script: Path, workspace: Path) -> None:
    """v0.9.5: integration_testing_review='fail' must block — tests ran against fake data."""
    _write_manifest(workspace, "fullstack-test", ["T-I2"])
    ev = _valid_evidence("T-I2")
    ev["integration_testing_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-I2.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-I2", "completed"))
    assert r.returncode == 2
    assert "integration_testing_review" in r.stderr
    assert "real backend" in r.stderr.lower() or "mock" in r.stderr.lower()


def test_exits_two_when_integration_testing_missing(script: Path, workspace: Path) -> None:
    """v0.9.5: integration_testing_review field absent entirely must block."""
    _write_manifest(workspace, "fullstack-test", ["T-I3"])
    ev = _valid_evidence("T-I3")
    ev.pop("integration_testing_review", None)
    ev.pop("integration_testing_review_note", None)
    (workspace / ".architect-team" / "reviews" / "T-I3.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-I3", "completed"))
    assert r.returncode == 2
    assert "integration_testing_review" in r.stderr


@pytest.mark.parametrize("invalid_value", ["yes", "true", "ok", "passed", ""])
def test_exits_two_when_integration_testing_invalid_value(
    script: Path, workspace: Path, invalid_value: str
) -> None:
    """v0.9.5: integration_testing_review must be one of pass / n/a / fail."""
    _write_manifest(workspace, "fullstack-test", ["T-I4"])
    ev = _valid_evidence("T-I4")
    ev["integration_testing_review"] = invalid_value
    (workspace / ".architect-team" / "reviews" / "T-I4.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-I4", "completed"))
    assert r.returncode == 2
    assert "integration_testing_review" in r.stderr


@pytest.mark.parametrize("missing_or_empty", [None, "", "   "])
def test_exits_two_when_integration_testing_na_without_note(
    script: Path, workspace: Path, missing_or_empty
) -> None:
    """v0.9.5: integration_testing_review='n/a' requires a non-empty justification note."""
    _write_manifest(workspace, "fullstack-test", ["T-I5"])
    ev = _valid_evidence("T-I5")
    ev["integration_testing_review"] = "n/a"
    if missing_or_empty is None:
        ev.pop("integration_testing_review_note", None)
    else:
        ev["integration_testing_review_note"] = missing_or_empty
    (workspace / ".architect-team" / "reviews" / "T-I5.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-I5", "completed"))
    assert r.returncode == 2
    assert "integration_testing_review_note" in r.stderr or "n/a" in r.stderr


# ===========================================================================
# F7 — the null-session hole in the unmanifested-task completion gate
# ===========================================================================
#
# THE ESCAPE, reproduced by execution before any of this was written. The
# v3.47.0 gate refuses an orchestrator's completion of a task NO manifest
# mentions, but it first asks `is_orchestrator_session(marker, session)`, which
# returns False whenever the marker records a NULL session — so a null-session
# marker opened the gate completely:
#
#   marker records THIS session  -> TaskUpdate(completed) exit 2  BLOCKED
#   marker records NO session    -> TaskUpdate(completed) exit 0  ALLOWED
#
# and composed with the v3.57.0 unregistered-run arm that made a complete
# bypass of it: no tasks -> Stop exit 2; register one throwaway -> Stop exit 2;
# flip the throwaway to completed -> Stop exit 0. One junk task and the run
# stops clean, with no Bash, no marker deletion, and no kill-switch.
#
# THE FIX IS SCOPED TO THIS CONSUMER. `is_orchestrator_session` is shared with
# `pipeline-completion-audit.py`, and its null fail-open is deliberate and
# documented there. What is wrong is only this consumer's READING of it: a
# false answer was being treated as "not the orchestrator, so skip the gate"
# when for a null-session marker it means "ownership is UNDETERMINABLE". Unknown
# is not "no" — the same asymmetry as `open_work.open_task_items` counting an
# unknown status as OPEN. The gate now stands down only for a session that is
# DEMONSTRABLY a different one.


ORCH = "sess-orchestrator"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_marker(
    workspace: Path,
    *,
    status: str = "active",
    session_id: str | None = ORCH,
    updated_at: str | None = None,
) -> None:
    (workspace / ".architect-team" / "active-run.json").write_text(
        json.dumps({
            "schema": 1,
            "status": status,
            "skill": "architect-team-pipeline",
            "session_id": session_id,
            "started_at": _now_iso(),
            "updated_at": updated_at or _now_iso(),
            "run_id": "run-1",
            "slug": "some-change",
            "phase": "Phase 3",
            "completed_at": None,
            "stand_down_reason": None,
        }),
        encoding="utf-8",
    )


def _completion(task_id: str = "board-7", session_id: str | None = ORCH) -> dict:
    payload: dict = {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": task_id, "status": "completed"},
    }
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


# --- the hole, closed --------------------------------------------------------


def test_a_null_session_marker_still_gates_an_unmanifested_completion(
    script: Path, workspace: Path
) -> None:
    """THE escape. An ACTIVE run whose marker records no session cannot tell
    who owns the completion — and undeterminable ownership must not be read as
    proof that this is somebody else's task to close."""
    _write_marker(workspace, session_id=None)
    r = _run(script, workspace, _completion())
    assert r.returncode == 2, (
        f"a null-session marker must not open the gate; stderr={r.stderr!r}"
    )
    assert "board-7" in r.stderr


def test_a_null_session_marker_gates_even_with_no_payload_session(
    script: Path, workspace: Path
) -> None:
    """Neither side names a session, so ownership is undeterminable from both
    directions at once. Same rule, and pinned separately because it is the
    configuration an attacker reaches by simply not sending one."""
    _write_marker(workspace, session_id=None)
    r = _run(script, workspace, _completion(session_id=None))
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_the_block_does_not_claim_a_session_it_cannot_prove(
    script: Path, workspace: Path
) -> None:
    """Message honesty. The block's standing wording asserts "this completion
    comes from the run's own session" — which is exactly what a null-session
    marker CANNOT establish. A gate whose first sentence overclaims is a gate
    the reader stops believing, so the undeterminable case says so instead."""
    _write_marker(workspace, session_id=None)
    err = _run(script, workspace, _completion()).stderr
    assert "comes from the run's own session" not in err, (
        "the block must not claim ownership it could not determine"
    )
    assert "cannot be determined" in err or "undeterminable" in err


def test_the_block_still_names_the_runs_own_session_when_it_can_prove_it(
    script: Path, workspace: Path
) -> None:
    """The control for the message change: where ownership IS provable the
    original, stronger wording must survive."""
    _write_marker(workspace, session_id=ORCH)
    err = _run(script, workspace, _completion()).stderr
    assert "comes from the run's own session" in err


# --- everything the fix must leave exactly as it was -------------------------


def test_a_demonstrably_different_session_still_stands_the_gate_down(
    script: Path, workspace: Path
) -> None:
    """The standdown that must SURVIVE: a session the marker proves is not the
    run's own. This is the whole point of scoping the change to the null case —
    a teammate or an unrelated session is still left alone."""
    _write_marker(workspace, session_id=ORCH)
    r = _run(script, workspace, _completion(session_id="sess-somebody-else"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_a_recorded_session_with_no_payload_session_still_stands_down(
    script: Path, workspace: Path
) -> None:
    """Pinned in `tests/test_completion_status_integrity.py` too and unchanged
    here: the marker names an owner, the payload names nobody, so this
    completion is not shown to be the owner's."""
    _write_marker(workspace, session_id=ORCH)
    r = _run(script, workspace, _completion(session_id=None))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_no_marker_leaves_an_unmanifested_completion_alone(
    script: Path, workspace: Path
) -> None:
    """The blast-radius direction, and the one that matters most. Foreign
    workflows and plain user task tracking are protected by the MARKER check,
    never by the session check — so narrowing the session check cannot reach
    them."""
    r = _run(script, workspace, _completion())
    assert r.returncode == 0, f"no run, no gate; stderr={r.stderr!r}"


def test_a_stale_null_session_marker_does_not_gate(
    script: Path, workspace: Path
) -> None:
    """Why the pre-upgrade cost is bounded: an abandoned marker stops gating at
    the staleness bound, so a null-session marker left in a long-lived
    workspace heals itself rather than gating that workspace forever."""
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    _write_marker(workspace, session_id=None, updated_at=old)
    r = _run(script, workspace, _completion())
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_a_completed_run_marker_with_a_null_session_does_not_gate(
    script: Path, workspace: Path
) -> None:
    _write_marker(workspace, session_id=None, status="complete")
    r = _run(script, workspace, _completion())
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_a_manifested_task_is_never_gated_by_this_arm(
    script: Path, workspace: Path
) -> None:
    """The teammate protection survives. A task the run REGISTERED to somebody
    is not the postmortem's arbitrary board item, whatever the marker records
    about sessions — in Agent Teams mode the Lead and every teammate share one
    session id, so this is the check that keeps a run from wedging the moment
    each group finishes.

    The evidence file is written because a manifested task owes one to the
    OTHER arm — the first cut of this test omitted it, went red, and was red for
    the right reason under the wrong arm. Supplying it is what makes the exit
    code attributable to the arm under test.

    NOTE what this measures: `main()` routes a task in `expected_review_evidence`
    to the EVIDENCE arm and never reaches the unmanifested arm at all, so the
    protection here is the routing. The `_is_registered_task` guard INSIDE the
    unmanifested arm covers the wider case, pinned separately below — the
    mutation harness is what forced the two apart, by surviving a mutation of
    that guard against this test."""
    _write_manifest(workspace, "backend", ["board-7"])
    (workspace / ".architect-team" / "reviews" / "board-7.json").write_text(
        json.dumps(_valid_evidence("board-7")), encoding="utf-8"
    )
    _write_marker(workspace, session_id=None)
    r = _run(script, workspace, _completion())
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_a_task_registered_only_as_a_shared_board_id_is_not_gated(
    script: Path, workspace: Path
) -> None:
    """The WIDER registration the in-arm guard exists for, and the case a
    null-session marker now makes reachable.

    A CT6 manifest records the same work under two id spaces: `task_ids` (the
    tasks.md ids, which `expected_review_evidence` mirrors) and
    `shared_task_id` (the Agent-Teams board id). A board id that appears ONLY as
    `shared_task_id` is not an `expected_review_evidence` task, so `main()`
    routes it to the unmanifested arm — and the run HAS registered it. Gating it
    would wedge a teammate closing the board task its own manifest names, which
    is the exact failure the v3.47.0 docstring records condition (c) to
    prevent."""
    (workspace / ".architect-team" / "teammates" / "backend.json").write_text(
        json.dumps({
            "schema_version": 2,
            "teammate": "backend",
            "shared_task_id": "board-7",
            "task_ids": [],
            "expected_review_evidence": [],
            "files_owned": [],
        }),
        encoding="utf-8",
    )
    _write_marker(workspace, session_id=None)
    r = _run(script, workspace, _completion())
    assert r.returncode == 0, f"a registered board id must not be gated; {r.stderr!r}"


def test_a_non_completed_status_is_untouched_by_the_null_session_gate(
    script: Path, workspace: Path
) -> None:
    """The gate is about a COMPLETION claim. Moving a task to in_progress
    asserts nothing that needs evidence."""
    _write_marker(workspace, session_id=None)
    r = _run(script, workspace, _make_payload("board-7", "in_progress"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


# --- the operator's exits, unchanged -----------------------------------------


def test_the_task_gate_kill_switch_releases_the_null_session_case(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_marker(workspace, session_id=None)
    monkeypatch.setenv("CT6_TASK_GATE_DISABLED", "1")
    r = _run(script, workspace, _completion())
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_the_run_continuity_kill_switch_releases_the_null_session_case(
    script: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_marker(workspace, session_id=None)
    monkeypatch.setenv("CT6_RUN_CONTINUITY_DISABLED", "1")
    r = _run(script, workspace, _completion())
    assert r.returncode == 0, f"stderr={r.stderr!r}"


# ===========================================================================
# The mutation table — every F7 property, witnessed
# ===========================================================================
#
# Each row breaks exactly one rule in a COPY of the hook (the repo file is never
# touched) and re-runs THAT rule's test against the copy in a child pytest.
# Classification is by the CHILD PROCESS EXIT CODE — never a parsed pytest
# summary line. Three guards make the exit code mean what it says: the fragment
# is asserted UNIQUELY present, the copy's sha256 is asserted CHANGED before the
# child runs, and a baseline child over every target is asserted GREEN first.

_HOOK_REL = Path("hooks") / "review-gate-task.py"

_MUTATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("M1 null-session-marker-opens-the-gate",
     "test_a_null_session_marker_still_gates_an_unmanifested_completion",
     "        if owner_known and not _rc.is_orchestrator_session(marker, session_id):",
     "        if not _rc.is_orchestrator_session(marker, session_id):"),
    ("M2 a-different-session-is-wedged",
     "test_a_demonstrably_different_session_still_stands_the_gate_down",
     "        if owner_known and not _rc.is_orchestrator_session(marker, session_id):",
     "        if False and not _rc.is_orchestrator_session(marker, session_id):"),
    ("M3 owner-known-is-computed-wrong",
     "test_a_recorded_session_with_no_payload_session_still_stands_down",
     "        owner_known = bool(recorded)",
     "        owner_known = False  # mutated: every marker reads as ownerless"),
    ("M4 the-block-overclaims-the-session",
     "test_the_block_does_not_claim_a_session_it_cannot_prove",
     '        "this completion comes from the run\'s own session"\n        if owner_known else',
     '        "this completion comes from the run\'s own session"\n        if True else'),
    # Targets the SHARED-BOARD-ID test, not the expected_review_evidence one:
    # `main()` never reaches this arm for the latter, so mutating the in-arm
    # guard against it changed nothing and the row survived. The harness is what
    # separated the routing from the guard.
    ("M5 a-registered-board-id-is-gated",
     "test_a_task_registered_only_as_a_shared_board_id_is_not_gated",
     "        if _is_registered_task(task_id, cwd):",
     "        if False and _is_registered_task(task_id, cwd):"),
    ("M6 an-abandoned-run-gates-forever",
     "test_a_stale_null_session_marker_does_not_gate",
     "        if _rc.marker_is_stale(marker):",
     "        if False and _rc.marker_is_stale(marker):"),
    # A bare `if False and ...` here is a mutation the code SURVIVES: with no
    # marker, `marker` stays None, `marker_is_stale(None)` returns True, and the
    # next line allows anyway. That is the sibling guard absorbing it, not the
    # rule being measured — so the marker is replaced with a synthetic active,
    # never-stale one, which breaks the rule without breaking the code.
    ("M7 a-workspace-with-no-run-is-gated",
     "test_no_marker_leaves_an_unmanifested_completion_alone",
     '        marker = _rc.read_marker(cwd)\n'
     '        if not isinstance(marker, dict) or marker.get("status") != "active":',
     '        marker = _rc.read_marker(cwd) or {"status": "active",\n'
     '                                          "updated_at": "2999-01-01T00:00:00Z"}\n'
     '        if False and marker.get("status") != "active":'),
    ("M8 the-kill-switches-do-nothing",
     "test_the_task_gate_kill_switch_releases_the_null_session_case",
     "        if _task_gate_disabled() or _rc.continuity_disabled():",
     "        if False and (_task_gate_disabled() or _rc.continuity_disabled()):"),
)

_MUTATION_TARGETS = tuple(dict.fromkeys(row[1] for row in _MUTATIONS))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_child(selection: str, mutant: Path) -> subprocess.CompletedProcess:
    """Re-run THIS file's tests in a child against a copy of the hook.

    Both `<repo>` and `<repo>/hooks` go on PYTHONPATH: the hook's substrate
    import is dual-form, but `from review_evidence_schema import ...` is BARE
    and resolves only from the hooks directory. A copy placed elsewhere would
    otherwise die at import and every row would "catch" for the wrong reason.
    """
    env = dict(os.environ, PYTHONUTF8="1",
               **{_CHILD_ENV: "1", _SCRIPT_ENV: str(mutant)})
    prior = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_REPO_ROOT), str(_REPO_ROOT / "hooks")] + ([prior] if prior else [])
    )
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(Path(__file__).resolve()),
         "-k", selection, "-q", "-p", "no:cacheprovider", "--no-header"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT), env=env,
    )


@pytest.mark.skipif(_IS_CHILD_RUN, reason="child run - never recurse")
def test_mutation_baseline_every_target_is_green(
    plugin_root: Path, tmp_path: Path
) -> None:
    """The harness's own control, run against an UNMUTATED COPY so the
    copy-and-inject plumbing is proven sound. Without it every red below could
    be the plumbing rather than the mutation."""
    copy = tmp_path / "baseline" / _HOOK_REL.name
    copy.parent.mkdir(parents=True)
    shutil.copy2(plugin_root / _HOOK_REL, copy)
    r = _run_child(" or ".join(_MUTATION_TARGETS), copy)
    assert r.returncode == 0, (
        "baseline child run is not green - a mutation's red would be "
        f"unattributable:\nrc={r.returncode}\n{r.stdout[-4000:]}\n{r.stderr[-2000:]}"
    )


@pytest.mark.skipif(_IS_CHILD_RUN, reason="child run - never recurse")
@pytest.mark.parametrize("rule,target,fragment,replacement", _MUTATIONS,
                         ids=[row[0].split()[0] for row in _MUTATIONS])
def test_each_rule_is_killed_by_its_mutation(
    plugin_root: Path, tmp_path: Path,
    rule: str, target: str, fragment: str, replacement: str,
) -> None:
    """One row: break the rule in a copy, prove the named test notices."""
    mutant = tmp_path / "mutant" / _HOOK_REL.name
    mutant.parent.mkdir(parents=True)
    shutil.copy2(plugin_root / _HOOK_REL, mutant)
    before = _sha(mutant)

    src = mutant.read_text(encoding="utf-8")
    assert src.count(fragment) == 1, (
        f"{rule}: the fragment appears {src.count(fragment)} times, not once - "
        "the table has drifted from the code and this row would mutate the "
        "wrong site (or nothing)"
    )
    mutant.write_text(src.replace(fragment, replacement), encoding="utf-8")
    after = _sha(mutant)
    assert before != after, f"{rule}: the mutation was a no-op ({before})"

    child = _run_child(target, mutant)
    assert child.returncode != 0, (
        f"{rule}: `{target}` PASSED against the mutant - the rule is not what "
        f"that test measures.\nchild stdout:\n{child.stdout[-4000:]}"
    )
