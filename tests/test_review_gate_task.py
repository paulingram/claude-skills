"""Unit tests for hooks/review-gate-task.py.

The hook reads stdin (JSON), inspects the TaskUpdate args, and exits:
- 0 if status != "completed", OR if status == "completed" AND review evidence is valid
- 2 (block) if status == "completed" AND review evidence is missing or invalid

We invoke the script as a subprocess and feed crafted stdin.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "review-gate-task.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A temp workspace that becomes the hook script's cwd."""
    (tmp_path / ".architect-team" / "reviews").mkdir(parents=True)
    return tmp_path


def _run(script: Path, workspace: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    """Run the script with payload on stdin from inside workspace."""
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _make_payload(task_id: str, status: str) -> dict:
    return {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": task_id, "status": status},
    }


def _valid_evidence(task_id: str) -> dict:
    return {
        "schema_version": 1,
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
    }


def test_exits_zero_when_status_not_completed(script: Path, workspace: Path) -> None:
    r = _run(script, workspace, _make_payload("T-1", "in_progress"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_two_when_completed_but_no_evidence(script: Path, workspace: Path) -> None:
    r = _run(script, workspace, _make_payload("T-2", "completed"))
    assert r.returncode == 2
    assert "T-2" in r.stderr


def test_exits_zero_when_completed_with_valid_evidence(script: Path, workspace: Path) -> None:
    (workspace / ".architect-team" / "reviews" / "T-3.json").write_text(
        json.dumps(_valid_evidence("T-3")), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-3", "completed"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_exits_two_when_spec_review_failing(script: Path, workspace: Path) -> None:
    ev = _valid_evidence("T-4")
    ev["spec_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-4.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-4", "completed"))
    assert r.returncode == 2
    assert "spec_review" in r.stderr


def test_exits_two_when_tests_added_not_equal_passing(script: Path, workspace: Path) -> None:
    ev = _valid_evidence("T-5")
    ev["tests"]["passing"] = 2  # added is 3
    (workspace / ".architect-team" / "reviews" / "T-5.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-5", "completed"))
    assert r.returncode == 2
    assert "tests" in r.stderr


def test_exits_two_when_real_not_stubbed_false(script: Path, workspace: Path) -> None:
    ev = _valid_evidence("T-6")
    ev["real_not_stubbed"] = False
    (workspace / ".architect-team" / "reviews" / "T-6.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _make_payload("T-6", "completed"))
    assert r.returncode == 2
    assert "real_not_stubbed" in r.stderr


def test_exits_two_when_files_changed_empty(script: Path, workspace: Path) -> None:
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
