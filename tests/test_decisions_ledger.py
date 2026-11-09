"""Tests for hooks/decisions_ledger.py -- the append-only decisions ledger
(change 15, the homepage's Decisions panel).

Pinned: the line schema, the closed kind enum (an unknown kind is REFUSED,
never coerced to ``other``), rejected-option normalization from both the dict
and the ``label=why`` string forms, run_id / phase defaulting from
intake-state, append-only behaviour (an earlier line is byte-identical after
a later append), and the ``add`` / ``list`` CLI incl. exit code 2 on a bad
kind. ASCII-only module.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER = REPO_ROOT / "hooks" / "decisions_ledger.py"


@pytest.fixture(scope="module")
def dl() -> ModuleType:
    return load_module(LEDGER, "ct6_decisions_ledger_under_test")


def _intake(ws: Path, **fields) -> None:
    state = ws / ".architect-team"
    state.mkdir(parents=True, exist_ok=True)
    base = {"run_id": "run-d-1", "phase": "Phase -2"}
    base.update(fields)
    (state / "intake-state.json").write_text(json.dumps(base), encoding="utf-8")


def _lines(ws: Path) -> list[str]:
    path = ws / ".architect-team" / "decisions.jsonl"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LEDGER), *args], capture_output=True, text=True,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def test_append_writes_schema_line_and_read_all_returns_it(dl: ModuleType, tmp_path: Path) -> None:
    rec = dl.append(tmp_path, kind="triage", summary="Routed to bug-fix", chosen="bug-fix",
                    rejected=[{"label": "mini", "why": "two layers"}], refs=["proposal.md"],
                    run_id="run-x", phase="Phase -2", at="2026-08-01T09:00:00Z")
    assert set(rec.keys()) == set(dl.RECORD_FIELDS)
    assert rec["schema"] == "decision/v1"
    assert rec["rejected"] == [{"label": "mini", "why": "two layers"}]
    assert rec["refs"] == ["proposal.md"]
    assert dl.read_all(tmp_path) == [rec]
    assert len(_lines(tmp_path)) == 1


def test_run_id_and_phase_default_from_intake_state(dl: ModuleType, tmp_path: Path) -> None:
    _intake(tmp_path, run_id="run-d-7", phase="Phase 1")
    rec = dl.append(tmp_path, kind="reuse", summary="Reused totals.py")
    assert rec["run_id"] == "run-d-7" and rec["phase"] == "Phase 1"
    explicit = dl.append(tmp_path, kind="reuse", summary="Again", run_id="run-other", phase="P9")
    assert explicit["run_id"] == "run-other" and explicit["phase"] == "P9"


def test_without_intake_state_fields_are_null(dl: ModuleType, tmp_path: Path) -> None:
    rec = dl.append(tmp_path, kind="other", summary="no intake here")
    assert rec["run_id"] is None and rec["phase"] is None


def test_unknown_kind_is_refused_not_coerced(dl: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        dl.append(tmp_path, kind="whim", summary="x")
    assert _lines(tmp_path) == []
    with pytest.raises(ValueError):
        dl.append(tmp_path, kind="triage", summary="   ")


def test_kinds_enum_is_the_documented_eight(dl: ModuleType) -> None:
    assert dl.KINDS == ("triage", "reuse", "contract-approval", "appearance", "principles",
                        "sr-routing", "option-choice", "other")


def test_rejected_normalization_forms(dl: ModuleType) -> None:
    out = dl.normalize_rejected(["mini=too narrow", {"label": "defer", "why": "blocks checkout"},
                                "bare-label", 42, {"why": "no label"}])
    assert out == [{"label": "mini", "why": "too narrow"},
                   {"label": "defer", "why": "blocks checkout"},
                   {"label": "bare-label", "why": ""}]
    assert dl.normalize_rejected(None) == []
    assert dl.normalize_rejected("a=b") == [{"label": "a", "why": "b"}]
    assert dl.normalize_refs(["x.md", "", 3, " y.json "]) == ["x.md", "y.json"]


def test_append_only_earlier_line_unchanged(dl: ModuleType, tmp_path: Path) -> None:
    dl.append(tmp_path, kind="appearance", summary="strict", chosen="strict", at="2026-08-01T09:00:00Z")
    first = _lines(tmp_path)[0]
    dl.append(tmp_path, kind="appearance", summary="reversed: propose", chosen="propose", at="2026-08-01T10:00:00Z")
    lines = _lines(tmp_path)
    assert len(lines) == 2 and lines[0] == first
    assert dl.by_kind(dl.read_all(tmp_path)) == {"appearance": 2}


def test_read_all_skips_malformed_lines(dl: ModuleType, tmp_path: Path) -> None:
    dl.append(tmp_path, kind="triage", summary="ok")
    path = tmp_path / ".architect-team" / "decisions.jsonl"
    with open(path, "a", encoding="utf-8") as h:
        h.write("not json\n{\"schema\": \"decision/v1\"}\n")
    assert len(dl.read_all(tmp_path)) == 1


def test_cli_add_and_list(tmp_path: Path) -> None:
    _intake(tmp_path, run_id="run-cli", phase="CFP-3")
    r = _cli("add", "--workspace", str(tmp_path), "--kind", "contract-approval",
             "--summary", "Approved the orders contract v2", "--chosen", "v2",
             "--rejected", "v1=missing pagination", "--ref", "contracts/orders.json", "--json")
    assert r.returncode == 0, r.stderr
    rec = json.loads(r.stdout)
    assert rec["kind"] == "contract-approval" and rec["run_id"] == "run-cli" and rec["phase"] == "CFP-3"
    assert rec["rejected"] == [{"label": "v1", "why": "missing pagination"}]
    assert rec["refs"] == ["contracts/orders.json"]
    r2 = _cli("list", "--workspace", str(tmp_path), "--json")
    assert r2.returncode == 0
    listed = json.loads(r2.stdout)
    assert listed["count"] == 1 and listed["by_kind"] == {"contract-approval": 1}
    assert listed["decisions"][0]["summary"] == "Approved the orders contract v2"
    r3 = _cli("list", "--workspace", str(tmp_path))
    assert "[contract-approval]" in r3.stdout and "=> v2" in r3.stdout


def test_cli_rejects_unknown_kind_with_exit_2(tmp_path: Path) -> None:
    r = _cli("add", "--workspace", str(tmp_path), "--kind", "whim", "--summary", "x")
    assert r.returncode == 2
    assert _lines(tmp_path) == []


def test_cli_list_empty_ledger(tmp_path: Path) -> None:
    r = _cli("list", "--workspace", str(tmp_path))
    assert r.returncode == 0 and "no decisions recorded" in r.stdout


def test_cli_list_filters_by_kind_and_limit(tmp_path: Path) -> None:
    for i, kind in enumerate(("triage", "reuse", "reuse")):
        assert _cli("add", "--workspace", str(tmp_path), "--kind", kind, "--summary", f"d{i}").returncode == 0
    r = _cli("list", "--workspace", str(tmp_path), "--kind", "reuse", "--limit", "1", "--json")
    data = json.loads(r.stdout)
    assert data["count"] == 1 and data["decisions"][0]["summary"] == "d2"


def test_module_source_contract() -> None:
    src = LEDGER.read_text(encoding="utf-8")
    assert src.isascii()
    assert "shared_util import _utc_now_iso" in src and "def _utc_now_iso" not in src
