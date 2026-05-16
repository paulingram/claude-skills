"""Unit tests for hooks/teammate-idle-check.py.

The hook reads stdin (JSON), looks up the subagent's manifest at
.architect-team/teammates/<name>.json, and for each task_id in
expected_review_evidence checks that a valid review-evidence file exists.

Exit codes:
- 0 if no manifest (this isn't an architect-team teammate), or all gaps clear
- 2 if any required evidence is missing or invalid
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "teammate-idle-check.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / ".architect-team" / "teammates").mkdir(parents=True)
    (tmp_path / ".architect-team" / "reviews").mkdir(parents=True)
    return tmp_path


def _run(script: Path, workspace: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _valid_evidence(task_id: str) -> dict:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "teammate": "any",
        "completed_at": "2026-05-16T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 1, "passing": 1, "unit": ["t"], "integration": [], "e2e": []},
        "demo_artifact": "demo",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
    }


def _write_manifest(workspace: Path, name: str, task_ids: list[str]) -> None:
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


def _write_evidence(workspace: Path, task_id: str) -> None:
    (workspace / ".architect-team" / "reviews" / f"{task_id}.json").write_text(
        json.dumps(_valid_evidence(task_id)), encoding="utf-8"
    )


def test_no_manifest_exits_zero(script: Path, workspace: Path) -> None:
    """If the subagent isn't an architect-team teammate, the hook allows."""
    payload = {"subagent": {"name": "some-other-agent"}}
    r = _run(script, workspace, payload)
    assert r.returncode == 0


def test_all_evidence_present_exits_zero(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-1", "T-2"])
    _write_evidence(workspace, "T-1")
    _write_evidence(workspace, "T-2")
    payload = {"subagent": {"name": "backend-test"}}
    r = _run(script, workspace, payload)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_missing_evidence_exits_two(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-1", "T-2"])
    _write_evidence(workspace, "T-1")  # T-2 missing
    payload = {"subagent": {"name": "backend-test"}}
    r = _run(script, workspace, payload)
    assert r.returncode == 2
    assert "T-2" in r.stderr


def test_invalid_evidence_exits_two(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-test", ["T-1"])
    bad = _valid_evidence("T-1")
    bad["spec_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-1.json").write_text(
        json.dumps(bad), encoding="utf-8"
    )
    payload = {"subagent": {"name": "backend-test"}}
    r = _run(script, workspace, payload)
    assert r.returncode == 2
    assert "T-1" in r.stderr
