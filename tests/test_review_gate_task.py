"""Unit tests for hooks/review-gate-task.py.

The hook reads stdin (JSON), inspects the TaskUpdate args, and exits:
- 0 if status != "completed", OR if status == "completed" AND review evidence is valid
- 2 (block) if status == "completed" AND review evidence is missing or invalid

We invoke the script as a subprocess and feed crafted stdin.
"""
import json
from pathlib import Path

import pytest

from tests.helpers.hook_runner import run_hook as _run


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "review-gate-task.py"


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
