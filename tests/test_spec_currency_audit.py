# -*- coding: utf-8 -*-
"""Tests for the v3.47.0 `_audit_spec_currency` Stop-audit arm (rule R6).

*The spec is a plan; the code is the fact.* The orchestrator owns spec currency
WHILE agents read it — so an artifact amended after Phase 2 dispatch silently
splits the run: teammates keep building against the spec they were briefed on
while the orchestrator reasons about the amended one. The fingerprint stamped
into each manifest at dispatch makes that decidable, and this arm refuses to let
the run complete while a teammate with UNFINISHED expected work is still
carrying a superseded stamp and no re-brief record.

Everything about the arm is scoped to what it can actually know: manifests
without a fingerprint (pre-upgrade), a run with no openspec change dir, and
teammates whose expected evidence is all on disk are simply not its business.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hooks.spec_fingerprint import compute_spec_fingerprint

STALE_FINGERPRINT = "0" * 64


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A real run whose active change is `openspec/changes/some-change/`."""
    at = tmp_path / ".architect-team"
    (at / "teammates").mkdir(parents=True)
    (at / "reviews").mkdir(parents=True)
    (at / "intake-state.json").write_text(
        json.dumps({"run_id": "r-1", "change_name": "some-change"}), encoding="utf-8"
    )
    change = tmp_path / "openspec" / "changes" / "some-change"
    (change / "specs" / "cap").mkdir(parents=True)
    (change / "proposal.md").write_text("# Proposal\n\nBuild it.\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [ ] 1.1 build it\n", encoding="utf-8")
    (change / "specs" / "cap" / "spec.md").write_text("## ADDED Requirements\n", encoding="utf-8")
    return tmp_path


def _at(workspace: Path) -> Path:
    return workspace / ".architect-team"


def _change_dir(workspace: Path) -> Path:
    return workspace / "openspec" / "changes" / "some-change"


def _current_fingerprint(workspace: Path) -> str:
    fp = compute_spec_fingerprint(_change_dir(workspace))
    assert fp is not None
    return fp


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


def _write_manifest(
    workspace: Path,
    name: str = "backend-auth",
    *,
    fingerprint: str | None = None,
    expected: list[str] | None = None,
    change_name: str = "some-change",
) -> Path:
    manifest = {
        "schema_version": 2,
        "teammate": name,
        "spawned_at": "2026-07-30T12:00:00Z",
        "change_name": change_name,
        "task_ids": ["1.1"],
        "files_owned": [],
        "expected_review_evidence": ["task-a"] if expected is None else expected,
        "baseline_sha": "abc123",
    }
    if fingerprint is not None:
        manifest["spec_fingerprint"] = fingerprint
    path = _at(workspace) / "teammates" / f"{name}.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _complete_expected_work(workspace: Path, task_ids: list[str]) -> None:
    for task_id in task_ids:
        (_at(workspace) / "reviews" / f"{task_id}.json").write_text(
            json.dumps({"task_id": task_id}), encoding="utf-8"
        )


def _write_rebrief(workspace: Path, filename: str) -> Path:
    handoffs = _at(workspace) / "handoffs"
    handoffs.mkdir(exist_ok=True)
    path = handoffs / filename
    path.write_text("Re-briefed against the amended proposal.\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# the arm fires: an in-flight teammate briefed against a superseded spec
# --------------------------------------------------------------------------- #

def test_stale_in_flight_manifest_blocks(script: Path, workspace: Path) -> None:
    """Scenario: amended spec with un-rebriefed teammate blocks."""
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "backend-auth" in r.stderr


def test_violation_names_the_remediation(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    r = _run_check(script, workspace)
    assert "re-brief" in r.stderr.lower(), r.stderr
    assert "spec_fingerprint" in r.stderr, r.stderr


def test_amending_the_spec_after_dispatch_makes_a_current_manifest_stale(
    script: Path, workspace: Path
) -> None:
    """The realistic sequence: stamp at dispatch, then amend the proposal."""
    _write_manifest(workspace, "backend-auth", fingerprint=_current_fingerprint(workspace))
    assert _run_check(script, workspace).returncode == 0
    (_change_dir(workspace) / "proposal.md").write_text(
        "# Proposal\n\nBuild it — amended after dispatch.\n", encoding="utf-8"
    )
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "backend-auth" in r.stderr


def test_only_the_stale_teammate_is_named(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=_current_fingerprint(workspace),
                    expected=["task-a"])
    _write_manifest(workspace, "frontend-ui", fingerprint=STALE_FINGERPRINT,
                    expected=["task-b"])
    r = _run_check(script, workspace)
    assert r.returncode == 2
    assert "frontend-ui" in r.stderr
    assert "backend-auth" not in r.stderr


# --------------------------------------------------------------------------- #
# what clears it
# --------------------------------------------------------------------------- #

def test_matching_fingerprint_passes(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=_current_fingerprint(workspace))
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_rebrief_record_clears_a_stale_manifest(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    _write_rebrief(workspace, "2026-07-30-rebrief-backend-auth.md")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_rebrief_record_spelling_variants_are_recognized(script: Path, workspace: Path) -> None:
    """`*rebrief*<teammate>*` is matched on the alphanumeric skeleton, so
    `re-brief_backend_auth` counts as the same record."""
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    _write_rebrief(workspace, "re-brief_backend_auth_2026-07-30.md")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_rebrief_for_a_different_teammate_does_not_clear(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    _write_rebrief(workspace, "rebrief-frontend-ui.md")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "backend-auth" in r.stderr


def test_an_unrelated_handoff_does_not_clear(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    _write_rebrief(workspace, "handoff-backend-auth-status.md")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# B2 (adversarial, medium-high): a re-brief must clear the teammate it names —
# and only that teammate. Skeleton substring matching cleared 'backend' with a
# re-brief for 'backend-auth', cleared 'hei-claims' with one for 'hei-claims-2',
# and cleared a teammate named 'ui' with 'rebrief-build-guide.md' (b-UI-ld).
# Attribution now runs on whole tokens, and where several KNOWN teammate names
# match one filename the longest wins.
# --------------------------------------------------------------------------- #

def test_rebrief_for_a_longer_teammate_does_not_clear_the_shorter_one(
    script: Path, workspace: Path
) -> None:
    _write_manifest(workspace, "backend", fingerprint=STALE_FINGERPRINT,
                    expected=["task-a"])
    _write_manifest(workspace, "backend-auth", fingerprint=_current_fingerprint(workspace),
                    expected=["task-b"])
    _write_rebrief(workspace, "rebrief-backend-auth.md")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"'backend' must stay flagged; stderr={r.stderr!r}"
    assert "'backend'" in r.stderr


def test_rebrief_naming_a_longer_teammate_id_does_not_clear_its_prefix(
    script: Path, workspace: Path
) -> None:
    _write_manifest(workspace, "hei-claims", fingerprint=STALE_FINGERPRINT,
                    expected=["task-a"])
    _write_manifest(workspace, "hei-claims-2", fingerprint=_current_fingerprint(workspace),
                    expected=["task-b"])
    _write_rebrief(workspace, "orchestrator-to-hei-claims-2-rebrief.md")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"'hei-claims' must stay flagged; stderr={r.stderr!r}"


def test_a_teammate_name_embedded_in_an_unrelated_word_does_not_clear(
    script: Path, workspace: Path
) -> None:
    """'ui' is a substring of 'build' once punctuation is squashed away."""
    _write_manifest(workspace, "ui", fingerprint=STALE_FINGERPRINT, expected=["task-a"])
    _write_rebrief(workspace, "rebrief-build-guide.md")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"'ui' must stay flagged; stderr={r.stderr!r}"


def test_the_correctly_named_teammate_is_still_cleared(script: Path,
                                                       workspace: Path) -> None:
    """The fix must not break the case the contract is FOR."""
    _write_manifest(workspace, "backend", fingerprint=_current_fingerprint(workspace),
                    expected=["task-b"])
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT,
                    expected=["task-a"])
    _write_rebrief(workspace, "rebrief-backend-auth.md")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_an_explicit_teammate_field_in_the_handoff_clears_unambiguously(
    script: Path, workspace: Path
) -> None:
    """Filename inference is a convenience; a handoff that names its teammate
    explicitly is authoritative and immune to every collision above."""
    _write_manifest(workspace, "ui", fingerprint=STALE_FINGERPRINT, expected=["task-a"])
    handoffs = _at(workspace) / "handoffs"
    handoffs.mkdir(exist_ok=True)
    (handoffs / "rebrief-2026-07-31.md").write_text(
        '{"kind": "rebrief", "teammate": "ui", "reason": "spec amended"}\n',
        encoding="utf-8",
    )
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# B6 (adversarial, low-medium): a garbage evidence file is not completed work
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# R5 / R1 (adversarial round 3b) at the audit surface
# --------------------------------------------------------------------------- #

def test_integer_typed_expected_id_resolves_its_evidence_file(script: Path,
                                                              workspace: Path) -> None:
    """R5 at the audit: an int-typed expected id must resolve reviews/3.json, so
    a teammate whose work HAS landed is not held in-flight forever (and one whose
    work has not is not waved through)."""
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT,
                    expected=[3])
    assert _run_check(script, workspace).returncode == 2  # evidence absent
    (_at(workspace) / "reviews" / "3.json").write_text(
        json.dumps({"task_id": "3"}), encoding="utf-8"
    )
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"int id must resolve its file; stderr={r.stderr!r}"


@pytest.mark.parametrize("entry", [
    "reviews/hei-group2.json",
    "hei-group2.json",
    "..",
    {"task": "x"},
    None,
])
def test_unusable_expected_entry_is_a_violation(script: Path, workspace: Path,
                                                entry) -> None:
    """R1 at the audit: an entry that can never match any task id is a REGISTRATION
    that silently enforces nothing. The audit names the manifest and the entry."""
    _write_manifest(workspace, "backend-auth",
                    fingerprint=_current_fingerprint(workspace), expected=[entry])
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "backend-auth" in r.stderr
    assert "expected_review_evidence" in r.stderr


def test_well_formed_entries_are_not_flagged(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth",
                    fingerprint=_current_fingerprint(workspace), expected=["task-a", 3])
    _complete_expected_work(workspace, ["task-a", "3"])
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_archived_manifests_are_not_scanned(script: Path, workspace: Path) -> None:
    """The manifest scan is non-recursive by contract: manifests retired into a
    subdirectory (the Lead's archive of completed runs) must not participate."""
    archive = _at(workspace) / "teammates" / "archive-pre-hei"
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "old-run.json").write_text(
        json.dumps({"teammate": "old-run", "spec_fingerprint": STALE_FINGERPRINT,
                    "expected_review_evidence": ["reviews/old.json"]}),
        encoding="utf-8",
    )
    _write_manifest(workspace, "backend-auth",
                    fingerprint=_current_fingerprint(workspace), expected=["task-a"])
    _complete_expected_work(workspace, ["task-a"])
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"archived manifests must be inert; stderr={r.stderr!r}"


@pytest.mark.parametrize("body", ["{not json", "", "[]", "null"])
def test_unreadable_expected_evidence_is_not_completed_work(script: Path,
                                                            workspace: Path,
                                                            body: str) -> None:
    """`.is_file()` alone let a 0-byte or corrupt evidence file convert
    in-flight work into 'landed' and stand the arm down."""
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT,
                    expected=["task-a"])
    (_at(workspace) / "reviews" / "task-a.json").write_text(body, encoding="utf-8")
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_completed_expected_work_is_not_in_flight(script: Path, workspace: Path) -> None:
    """A teammate whose expected evidence is all on disk is done reading the
    spec — a stale stamp cannot mislead work that already landed."""
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT,
                    expected=["task-a", "task-b"])
    _complete_expected_work(workspace, ["task-a", "task-b"])
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_partially_completed_work_is_still_in_flight(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT,
                    expected=["task-a", "task-b"])
    _complete_expected_work(workspace, ["task-a"])
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# fail-open directions
# --------------------------------------------------------------------------- #

def test_pre_upgrade_manifests_are_fail_open(script: Path, workspace: Path) -> None:
    """Scenario: pre-upgrade runs are fail-open — no manifest carries a stamp."""
    _write_manifest(workspace, "backend-auth", fingerprint=None)
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_no_openspec_change_dir_is_fail_open(script: Path, workspace: Path) -> None:
    for path in sorted(_change_dir(workspace).rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    _change_dir(workspace).rmdir()
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_unresolvable_change_name_is_fail_open(script: Path, workspace: Path) -> None:
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"run_id": "r-1", "change_name": "a-change-that-does-not-exist"}),
        encoding="utf-8",
    )
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT,
                    change_name="a-change-that-does-not-exist")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_empty_fingerprint_string_is_fail_open(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint="   ")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_malformed_manifest_does_not_crash_the_audit(script: Path, workspace: Path) -> None:
    (_at(workspace) / "teammates" / "broken.json").write_text("{not json", encoding="utf-8")
    _write_manifest(workspace, "backend-auth", fingerprint=_current_fingerprint(workspace))
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_manifest_with_no_expected_evidence_is_not_in_flight(script: Path,
                                                             workspace: Path) -> None:
    """No expected work means nothing the spec state can corrupt."""
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT, expected=[])
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_traversal_in_the_change_name_is_refused(script: Path, workspace: Path) -> None:
    """A slug is a directory NAME; it never escapes openspec/changes/."""
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"run_id": "r-1", "change_name": "../../etc"}), encoding="utf-8"
    )
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT,
                    change_name="../../etc")
    r = _run_check(script, workspace)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# change-dir resolution sources + --check / Stop parity
# --------------------------------------------------------------------------- #

def test_change_dir_resolves_from_the_active_run_marker(script: Path, workspace: Path) -> None:
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"run_id": "r-1"}), encoding="utf-8"  # no change_name
    )
    (_at(workspace) / "active-run.json").write_text(
        json.dumps({"schema": 1, "status": "active", "slug": "some-change",
                    "session_id": None, "updated_at": "2026-07-30T12:00:00Z"}),
        encoding="utf-8",
    )
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_change_dir_resolves_from_the_manifest_change_name(script: Path,
                                                           workspace: Path) -> None:
    (_at(workspace) / "intake-state.json").write_text(
        json.dumps({"run_id": "r-1"}), encoding="utf-8"
    )
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    r = _run_check(script, workspace)
    assert r.returncode == 2, f"stderr={r.stderr!r}"


def test_stop_mode_blocks_the_same_way(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=STALE_FINGERPRINT)
    r = _run_stop(script, workspace, {})
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "backend-auth" in r.stderr


def test_stop_mode_allows_a_current_manifest(script: Path, workspace: Path) -> None:
    _write_manifest(workspace, "backend-auth", fingerprint=_current_fingerprint(workspace))
    r = _run_stop(script, workspace, {})
    assert r.returncode == 0, f"stderr={r.stderr!r}"
