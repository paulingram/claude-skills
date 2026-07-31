# -*- coding: utf-8 -*-
"""Tests for the v3.47.0 `_audit_declared_gates` Stop-audit arm (rule R9).

*Do not declare a gate and then ship without it.* The banking-app postmortem's
release announced that it gated on the full Playwright suite against the live
URL; the suite never ran, and nothing in the machinery remembered the promise.
`.architect-team/declared-gates.json` is that memory: naming a gate records it,
and the completion audit refuses to let the run finish while a recorded gate has
no `satisfied_at` and no evidence file with bytes in it.

Fail-open where it must be: a run that declared nothing has no registry, and an
absent registry is silence, not a violation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A workspace the audit recognizes as a real run (intake-state present)."""
    at = tmp_path / ".architect-team"
    at.mkdir()
    (at / "intake-state.json").write_text(json.dumps({"run_id": "r-1"}), encoding="utf-8")
    return tmp_path


def _at(workspace: Path) -> Path:
    return workspace / ".architect-team"


def _run_check(script: Path, workspace: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), "--check"],
        text=True, capture_output=True, cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _run_stop(script: Path, workspace: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True, capture_output=True, cwd=str(workspace),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _write_registry(workspace: Path, entries) -> Path:
    path = _at(workspace) / "declared-gates.json"
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


def _evidence_file(workspace: Path, relpath: str, body: str = "collected 42 items\n") -> Path:
    path = workspace / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _gate(**overrides) -> dict:
    entry = {
        "gate_id": "playwright-live-suite",
        "declaration_text": "The release gates on the full Playwright suite against the live URL.",
        "check_command_or_artifact": "npx playwright test --reporter=line",
        "declared_at": "2026-07-30T12:00:00Z",
    }
    entry.update(overrides)
    return entry


# --------------------------------------------------------------------------- #
# fail-open: a run that declared nothing
# --------------------------------------------------------------------------- #

def test_absent_registry_is_fail_open(script: Path, workspace: Path) -> None:
    """Scenario: absent registry is fail-open."""
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_empty_registry_is_clean(script: Path, workspace: Path) -> None:
    _write_registry(workspace, [])
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# an unsatisfied declared gate blocks, quoting its own words
# --------------------------------------------------------------------------- #

def test_unsatisfied_gate_blocks_quoting_the_declaration(script: Path, workspace: Path) -> None:
    """Scenario: unsatisfied gate blocks completion."""
    _write_registry(workspace, [_gate()])
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "full Playwright suite against the live URL" in r.stderr
    assert "playwright-live-suite" in r.stderr


def test_gate_with_satisfied_at_but_no_evidence_path_blocks(script: Path, workspace: Path) -> None:
    _write_registry(workspace, [_gate(satisfied_at="2026-07-30T13:00:00Z")])
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "evidence_path" in r.stderr


def test_gate_with_evidence_path_but_no_satisfied_at_blocks(script: Path,
                                                            workspace: Path) -> None:
    _evidence_file(workspace, ".architect-team/demos/playwright.txt")
    _write_registry(workspace, [
        _gate(evidence_path=".architect-team/demos/playwright.txt"),
    ])
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "satisfied_at" in r.stderr


def test_gate_whose_evidence_file_is_missing_blocks(script: Path, workspace: Path) -> None:
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=".architect-team/demos/never-written.txt",
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "never-written.txt" in r.stderr


def test_gate_whose_evidence_file_is_empty_blocks(script: Path, workspace: Path) -> None:
    """A zero-byte capture is the paper version of a check that never ran."""
    _evidence_file(workspace, ".architect-team/demos/empty.txt", body="")
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=".architect-team/demos/empty.txt",
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "empty" in r.stderr.lower()


def test_gate_whose_evidence_path_is_a_directory_blocks(script: Path, workspace: Path) -> None:
    (workspace / ".architect-team" / "demos").mkdir(parents=True)
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=".architect-team/demos",
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 2


# --------------------------------------------------------------------------- #
# a satisfied gate passes
# --------------------------------------------------------------------------- #

def test_satisfied_gate_passes(script: Path, workspace: Path) -> None:
    """Scenario: satisfied gate passes."""
    _evidence_file(workspace, ".architect-team/demos/playwright.txt")
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=".architect-team/demos/playwright.txt",
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_absolute_evidence_path_is_honored(script: Path, workspace: Path) -> None:
    path = _evidence_file(workspace, "captured/suite.txt")
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=str(path),
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_one_unsatisfied_among_several_blocks_and_names_only_that_one(script: Path,
                                                                     workspace: Path) -> None:
    _evidence_file(workspace, ".architect-team/demos/suite.txt")
    _write_registry(workspace, [
        _gate(gate_id="suite", satisfied_at="2026-07-30T13:00:00Z",
              evidence_path=".architect-team/demos/suite.txt"),
        _gate(gate_id="deploy-verified",
              declaration_text="The release gates on a verified dev deploy."),
    ])
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "deploy-verified" in r.stderr
    assert "verified dev deploy" in r.stderr


# --------------------------------------------------------------------------- #
# B3 (adversarial, medium): the cited evidence must be THIS run's evidence
#
# Any non-empty file anywhere satisfied a gate — '../outside-secret.txt' escaping
# the workspace, an absolute path to a system file, an unrelated README, and a
# one-byte file containing a single space. The arm's own text calls a zero-byte
# capture "the paper version of a check that never ran"; a one-space file is the
# same paper, and a file outside the run is not the run's evidence at all.
# --------------------------------------------------------------------------- #

def test_evidence_path_escaping_the_workspace_blocks(script: Path, workspace: Path,
                                                     tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("not this run's evidence\n", encoding="utf-8")
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path="../" + outside.name,
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_absolute_evidence_path_outside_the_workspace_blocks(script: Path,
                                                             workspace: Path,
                                                             tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere.txt"
    outside.write_text("unrelated\n", encoding="utf-8")
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=str(outside),
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


@pytest.mark.parametrize("body", [" ", "\n", "\t\r\n  ", "   \n\n "])
def test_whitespace_only_evidence_file_blocks(script: Path, workspace: Path,
                                              body: str) -> None:
    _evidence_file(workspace, ".architect-team/demos/blank.txt", body=body)
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=".architect-team/demos/blank.txt",
    )])
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_evidence_inside_the_workspace_still_passes(script: Path, workspace: Path) -> None:
    """The containment rule must not break the ordinary case."""
    _evidence_file(workspace, "captured/suite.txt", body="42 passed\n")
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path="captured/suite.txt",
    )])
    assert _run_check(script, workspace).returncode == 0


# --------------------------------------------------------------------------- #
# malformed registries surface rather than silently blessing the run
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("body", ["null", "123", '"x"'])
def test_non_array_json_is_reported_as_such_not_as_unreadable(script: Path,
                                                              workspace: Path,
                                                              body: str) -> None:
    """Observation (adversarial): valid JSON that is not an array was reported
    as 'unreadable / invalid JSON'. It parsed fine; say what is actually wrong."""
    (_at(workspace) / "declared-gates.json").write_text(body, encoding="utf-8")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "array" in r.stderr.lower(), r.stderr

def test_malformed_registry_blocks(script: Path, workspace: Path) -> None:
    (_at(workspace) / "declared-gates.json").write_text("{not json", encoding="utf-8")
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "declared-gates.json" in r.stderr


def test_registry_that_is_not_an_array_blocks(script: Path, workspace: Path) -> None:
    _write_registry(workspace, {"gate_id": "x"})
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "array" in r.stderr.lower()


def test_non_dict_entry_blocks(script: Path, workspace: Path) -> None:
    _write_registry(workspace, ["just a string"])
    r = _run_check(script, workspace)
    assert r.returncode == 2


def test_entry_without_declaration_text_still_blocks_readably(script: Path,
                                                              workspace: Path) -> None:
    _write_registry(workspace, [{"gate_id": "nameless"}])
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "nameless" in r.stderr


# --------------------------------------------------------------------------- #
# --check / Stop parity
# --------------------------------------------------------------------------- #

def test_stop_mode_blocks_the_same_way(script: Path, workspace: Path) -> None:
    _write_registry(workspace, [_gate()])
    r = _run_stop(script, workspace, {})
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "full Playwright suite against the live URL" in r.stderr


def test_stop_mode_allows_a_satisfied_registry(script: Path, workspace: Path) -> None:
    _evidence_file(workspace, ".architect-team/demos/playwright.txt")
    _write_registry(workspace, [_gate(
        satisfied_at="2026-07-30T13:00:00Z",
        evidence_path=".architect-team/demos/playwright.txt",
    )])
    r = _run_stop(script, workspace, {})
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_registry_alone_does_not_make_a_non_run_workspace_a_run(script: Path,
                                                                tmp_path: Path) -> None:
    """The arm lives inside `audit()`, which only runs for a real run — a bare
    directory with a stray registry is still not an architect-team run."""
    at = tmp_path / ".architect-team"
    at.mkdir()
    (at / "declared-gates.json").write_text(json.dumps([_gate()]), encoding="utf-8")
    r = _run_check(script, tmp_path)
    assert r.returncode == 0, f"stderr={r.stderr!r}"
