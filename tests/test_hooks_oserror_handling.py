"""A9 (review-remediation): review-gate-task.py and teammate-idle-check.py treat
an OSError on the evidence read as a BLOCKING gap, not a traceback.

Both hooks caught `json.JSONDecodeError` on the evidence `read_text` but not
`OSError`. A Windows sharing-violation (the evidence file open in another
process) raises `OSError`, which previously propagated -> exit 1 -> the gate
was silently SKIPPED. A gate that cannot read its evidence must FAIL CLOSED
(blocking, exit 2 for review-gate-task; a blocking gap for teammate-idle-check),
identical to the missing-file branch.

These tests load each hook module by file path, build a real teammate
manifest + evidence file under a tmp cwd, monkeypatch `Path.read_text` to raise
OSError for the EVIDENCE file only (the manifest still reads fine), feed a
matching payload via a fake UTF-8 stdin, and assert the gate fails closed.
"""
from __future__ import annotations

from tests.helpers.module_loader import load_module
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "hooks"


def _load_hook(script: str) -> ModuleType:
    mod_name = "a9_" + script[:-3].replace("-", "_")
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        module = load_module(HOOKS_DIR / script, mod_name)
        return module
    finally:
        # Keep hooks/ on sys.path while the module's functions run (they import
        # review_evidence_schema lazily? no — at import time, already done).
        sys.path.remove(str(HOOKS_DIR))


class _FakeBuffer:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeStdin:
    def __init__(self, data: bytes):
        self.buffer = _FakeBuffer(data)

    def isatty(self) -> bool:
        return False

    def read(self) -> str:
        return self.buffer.read().decode("utf-8", "replace")


def _make_run(tmp_path: Path, task_id: str = "T-1") -> Path:
    """Create .architect-team/teammates/backend.json + reviews/<task>.json."""
    at = tmp_path / ".architect-team"
    (at / "teammates").mkdir(parents=True, exist_ok=True)
    (at / "reviews").mkdir(parents=True, exist_ok=True)
    (at / "teammates" / "backend.json").write_text(
        json.dumps({"name": "backend", "expected_review_evidence": [task_id]}),
        encoding="utf-8",
    )
    # A valid-enough evidence file (content irrelevant — read is monkeypatched
    # to raise OSError before parsing).
    (at / "reviews" / f"{task_id}.json").write_text("{}", encoding="utf-8")
    return tmp_path


def _patch_read_text_oserror_for_evidence(monkeypatch, task_id: str = "T-1") -> None:
    """Make Path.read_text raise OSError ONLY for the evidence file (the
    manifest + everything else still reads normally)."""
    real_read_text = Path.read_text
    needle = f"reviews"

    def _patched(self: Path, *a, **k):
        # Raise only for the specific evidence json under reviews/.
        if self.name == f"{task_id}.json" and needle in str(self).replace("\\", "/"):
            raise OSError(13, "Permission denied (simulated sharing violation)")
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", _patched)


def test_review_gate_task_oserror_fails_closed(tmp_path, monkeypatch) -> None:
    _make_run(tmp_path)
    monkeypatch.chdir(tmp_path)
    module = _load_hook("review-gate-task.py")

    payload = {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": "T-1", "status": "completed"},
    }
    monkeypatch.setattr(module.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))
    _patch_read_text_oserror_for_evidence(monkeypatch)

    rc = module.main()
    assert rc == 2, (
        f"review-gate-task must FAIL CLOSED (exit 2) when the evidence read "
        f"raises OSError; got {rc}"
    )


def test_review_gate_task_oserror_does_not_traceback(tmp_path, monkeypatch, capsys) -> None:
    _make_run(tmp_path)
    monkeypatch.chdir(tmp_path)
    module = _load_hook("review-gate-task.py")
    payload = {"tool_name": "TaskUpdate", "tool_input": {"taskId": "T-1", "status": "completed"}}
    monkeypatch.setattr(module.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))
    _patch_read_text_oserror_for_evidence(monkeypatch)

    # main() must RETURN 2, not raise.
    rc = module.main()
    assert rc == 2
    err = capsys.readouterr().err
    assert "could not be read" in err, (
        f"expected a fail-closed message naming the unreadable evidence; got {err!r}"
    )


def test_teammate_idle_check_oserror_fails_closed(tmp_path, monkeypatch) -> None:
    _make_run(tmp_path)
    monkeypatch.chdir(tmp_path)
    module = _load_hook("teammate-idle-check.py")

    # teammate-idle-check resolves the teammate NAME from the payload; the
    # TeammateIdle (teams-mode) payload carries it at teammate.name. The
    # hook_event_name routes _detect_trigger_mode -> "teams".
    payload = {"hook_event_name": "TeammateIdle", "teammate": {"name": "backend"}}
    monkeypatch.setattr(module.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))
    _patch_read_text_oserror_for_evidence(monkeypatch)

    rc = module.main()
    assert rc == 2, (
        f"teammate-idle-check must FAIL CLOSED (exit 2 — blocking gap) when the "
        f"evidence read raises OSError; got {rc}"
    )


def test_source_has_oserror_in_evidence_except() -> None:
    """Source-structural guard: both hooks name OSError in an except near the
    evidence read_text so the fix cannot silently regress."""
    for script in ("review-gate-task.py", "teammate-idle-check.py"):
        src = (HOOKS_DIR / script).read_text(encoding="utf-8")
        assert "except OSError" in src, (
            f"{script} no longer catches OSError on the evidence read (A9 regression)"
        )
