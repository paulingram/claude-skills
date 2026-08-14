# -*- coding: utf-8 -*-
"""Tests for the v3.47.0 completion-status-integrity gate (postmortem rule R3).

*Never accept a completion status from the producer.* Before v3.47.0 the review
gate scoped itself to tasks a teammate manifest claimed (`expected_review_evidence`)
and allowed everything else — which left the orchestrator free to flip its own
task-board items to `completed` mid-run with no evidence anywhere. The banking-app
postmortem is that hole: `completed` statuses relayed to the user while a route
white-screened for every persona.

The closure is deliberately narrow. It fires ONLY when all of: an ACTIVE run
marker, the completing session IS the run's orchestrator session, and the
kill-switch is unset. Every other direction fails OPEN, because this hook also
fires for foreign workflows and plain user task tracking — the existing
`_is_teammate_task` scoping rationale, preserved.

The second half of the file covers the marker field the session test stands on:
`session_id`, recorded at engagement so the gate and the Stop-audit share one
session basis (design D5).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hooks import run_continuity as rc
from tests.helpers.hook_runner import run_hook as _run

ORCH_SESSION = "sess-orchestrator-1"


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "review-gate-task.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / ".architect-team" / "reviews").mkdir(parents=True)
    (tmp_path / ".architect-team" / "teammates").mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ambient kill-switch / session id leaks into these subprocesses.

    The session-var list is DERIVED from `rc.SESSION_ID_ENV_VARS` rather than
    retyped: the suite runs inside a real Claude Code session that exports
    `CLAUDE_CODE_SESSION_ID`, so a var added to the constant but missed here
    would silently leak the harness's own session into every fixture."""
    for var in ("CT6_TASK_GATE_DISABLED", "CT6_RUN_CONTINUITY_DISABLED",
                *rc.SESSION_ID_ENV_VARS):
        monkeypatch.delenv(var, raising=False)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_marker(
    workspace: Path,
    *,
    status: str = "active",
    session_id: str | None = ORCH_SESSION,
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


def _write_manifest(workspace: Path, name: str, task_ids: list[str]) -> None:
    (workspace / ".architect-team" / "teammates" / f"{name}.json").write_text(
        json.dumps({
            "schema_version": 2,
            "teammate": name,
            "spawned_at": _now_iso(),
            "task_ids": task_ids,
            "files_owned": [],
            "expected_review_evidence": task_ids,
        }),
        encoding="utf-8",
    )


def _valid_evidence(task_id: str) -> dict:
    return {
        "schema_version": 7,
        "task_id": task_id,
        "teammate": "backend-test",
        "completed_at": _now_iso(),
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 1, "passing": 1, "unit": ["t1"], "integration": [], "e2e": []},
        "demo_artifact": "captured run output",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "backend-only slice",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "backend-only slice",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "no cross-layer surface",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "no UI surface",
        "oracle_match_review": "n/a",
        "oracle_match_review_note": "no oracle in scope",
        "baseline_clean_review": "n/a",
        "baseline_clean_review_note": "no tool-call log in scope",
        "no_fake_data_review": "n/a",
        "no_fake_data_review_note": "no production diff in scope",
        "adversarial_review": "n/a",
        "adversarial_review_note": "no adversarial dispatch in scope",
        "skill_invocation_audit": "n/a",
        "skill_invocation_audit_note": "no transcript in scope",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": _now_iso(),
        },
    }


def _subagents_payload(task_id: str, status: str = "completed",
                       session_id: str | None = ORCH_SESSION) -> dict:
    payload: dict = {
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": task_id, "status": status},
    }
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


def _teams_payload(task_id: str | None, session_id: str | None = ORCH_SESSION) -> dict:
    payload: dict = {"hook_event_name": "TaskCompleted"}
    if task_id is not None:
        payload["task"] = {"id": task_id}
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


# --------------------------------------------------------------------------- #
# the gate fires: an active run's orchestrator completing an unmanifested task
# --------------------------------------------------------------------------- #

def test_unmanifested_completion_blocks_during_active_run(script: Path, workspace: Path) -> None:
    """Scenario: orchestrator completes an unmanifested task mid-run."""
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 2, f"expected a block; stderr={r.stderr!r}"
    assert "board-7" in r.stderr


def test_block_message_names_the_manifest_remediation(script: Path, workspace: Path) -> None:
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert "expected_review_evidence" in r.stderr, r.stderr
    assert "manifest" in r.stderr.lower(), r.stderr


def test_block_message_names_the_kill_switch(script: Path, workspace: Path) -> None:
    """A gate that can fire on a foreign workflow must say how to turn it off."""
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert "CT6_TASK_GATE_DISABLED" in r.stderr, r.stderr


def test_unmanifested_completion_blocks_in_teams_shape(script: Path, workspace: Path) -> None:
    _write_marker(workspace)
    r = _run(script, workspace, _teams_payload("board-9"))
    assert r.returncode == 2, f"expected a block; stderr={r.stderr!r}"
    assert "board-9" in r.stderr


def test_gate_fires_even_when_other_teammates_have_manifests(script: Path, workspace: Path) -> None:
    """A manifest claiming OTHER tasks does not launder this one."""
    _write_marker(workspace)
    _write_manifest(workspace, "backend-test", ["T-1", "T-2"])
    r = _run(script, workspace, _subagents_payload("T-99"))
    assert r.returncode == 2, f"expected a block; stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# fail-open: every missing precondition leaves foreign workflows alone
# --------------------------------------------------------------------------- #

def test_no_active_run_marker_allows(script: Path, workspace: Path) -> None:
    """Scenario: no active run — the pre-existing manifest-scoped behavior."""
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


@pytest.mark.parametrize("status", ["complete", "stood-down"])
def test_marker_not_active_allows(script: Path, workspace: Path, status: str) -> None:
    _write_marker(workspace, status=status)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_session_mismatch_allows(script: Path, workspace: Path) -> None:
    """A teammate (or any other session) completing a task is not the
    orchestrator relaying a producer's status — the gate stands down."""
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7", session_id="sess-teammate-2"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_marker_without_session_id_now_gates(script: Path, workspace: Path) -> None:
    """MOVED PIN (F7), recorded rather than silently edited.

    This asserted the OPPOSITE — "pre-upgrade markers carry a null session_id,
    they can never block" — and that was a defensible reading at v3.47.0, when
    the only cost of the null fail-open was a missed block. It stopped being
    defensible once the v3.57.0 unregistered-run arm made a single registered
    task enough to release the Stop hook: the two composed into a complete
    bypass, measured end to end against both real hooks — null-session marker,
    register one throwaway task, complete it (allowed at exit 0 here), Stop
    exits 0. No Bash, no marker deletion, no kill-switch.

    A False from `is_orchestrator_session` covers two situations and only one
    is a reason to stand down. A DIFFERENT recorded session is proof this is
    somebody else's completion; NO recorded session is not proof of anything.
    Unknown ownership is not somebody else's, so the gate applies.

    The shared predicate is unchanged — its null fail-open is deliberate and
    `pipeline-completion-audit.py` still relies on it. Only this consumer's
    reading of it moved. `test_payload_without_session_id_allows` below is the
    standdown that SURVIVES, and it is what keeps this from being a widening:
    a marker that names an owner still stands the gate down for a completion
    that does not name that owner."""
    _write_marker(workspace, session_id=None)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 2, (
        f"undeterminable ownership must not open the gate; stderr={r.stderr!r}"
    )
    assert "cannot be determined" in r.stderr, (
        "and the block must say WHY it fired rather than claiming a session "
        "it could not establish"
    )


def test_a_stale_marker_without_session_id_still_allows(
    script: Path, workspace: Path
) -> None:
    """The bound on the moved pin above, in the same file so the pair reads
    together: the genuine pre-upgrade case does not gate a workspace forever.
    An abandoned marker stops gating at the staleness bound, and `engage_marker`
    re-records a session the moment the current build runs."""
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    _write_marker(workspace, session_id=None, updated_at=old)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_payload_without_session_id_allows(script: Path, workspace: Path) -> None:
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7", session_id=None))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_kill_switch_allows(script: Path, workspace: Path,
                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: kill-switch honored."""
    monkeypatch.setenv("CT6_TASK_GATE_DISABLED", "1")
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


@pytest.mark.parametrize("value", ["0", "false", "no", ""])
def test_kill_switch_falsy_values_do_not_disable(script: Path, workspace: Path, value: str,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CT6_TASK_GATE_DISABLED", value)
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 2, f"{value!r} must not read as 'disabled'; stderr={r.stderr!r}"


def test_run_continuity_kill_switch_allows(script: Path, workspace: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """The substrate-wide kill-switch disables every run-continuity surface,
    this gate included."""
    monkeypatch.setenv("CT6_RUN_CONTINUITY_DISABLED", "1")
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_stale_marker_allows(script: Path, workspace: Path) -> None:
    """An abandoned run must not tax the workspace forever — same staleness
    posture the Stop-hook continuation guard applies."""
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=10)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    _write_marker(workspace, updated_at=old)
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_malformed_marker_allows(script: Path, workspace: Path) -> None:
    (workspace / ".architect-team" / "active-run.json").write_text("{not json", encoding="utf-8")
    r = _run(script, workspace, _subagents_payload("board-7"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_non_completed_status_allows(script: Path, workspace: Path) -> None:
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("board-7", status="in_progress"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_missing_task_id_allows(script: Path, workspace: Path) -> None:
    """Scenario: no task id extractable — nothing to look up, nothing to block."""
    _write_marker(workspace)
    r = _run(script, workspace, _teams_payload(None))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# regression: the manifested evidence flow is untouched
# --------------------------------------------------------------------------- #

def test_manifested_task_with_valid_evidence_completes(script: Path, workspace: Path) -> None:
    """Scenario: manifested task with valid evidence completes — exactly as before."""
    _write_marker(workspace)
    _write_manifest(workspace, "backend-test", ["T-3"])
    (workspace / ".architect-team" / "reviews" / "T-3.json").write_text(
        json.dumps(_valid_evidence("T-3")), encoding="utf-8"
    )
    r = _run(script, workspace, _subagents_payload("T-3"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_manifested_task_missing_evidence_still_blocks_on_evidence(script: Path,
                                                                   workspace: Path) -> None:
    """The manifested path must still fail for its OWN reason, not the new one."""
    _write_marker(workspace)
    _write_manifest(workspace, "backend-test", ["T-4"])
    r = _run(script, workspace, _subagents_payload("T-4"))
    assert r.returncode == 2
    assert "missing review evidence" in r.stderr


def test_path_traversal_task_id_blocks_before_the_new_gate(script: Path,
                                                           workspace: Path) -> None:
    _write_marker(workspace)
    r = _run(script, workspace, _subagents_payload("../evil"))
    assert r.returncode == 2
    assert "path-traversal" in r.stderr


# --------------------------------------------------------------------------- #
# B1 (adversarial, high): a validator that raises must FAIL CLOSED
#
# `validate_evidence` crashing propagated out of main(), the hook exited 1, and
# Claude Code treats exit 1 as a non-blocking error — the gate silently vanished
# for that completion. The hook's own A9 comment already committed to the
# opposite ("a gate that cannot READ its evidence fails closed"); this extends
# the same promise from reading to EVALUATING.
# --------------------------------------------------------------------------- #

def test_list_shaped_evidence_file_blocks_instead_of_crashing(script: Path,
                                                              workspace: Path) -> None:
    """A top-level JSON array is valid JSON but not an evidence object;
    `REQUIRED_EVIDENCE_FIELDS - evidence.keys()` raises AttributeError on it."""
    _write_manifest(workspace, "backend-test", ["T-9"])
    (workspace / ".architect-team" / "reviews" / "T-9.json").write_text(
        "[]", encoding="utf-8"
    )
    r = _run(script, workspace, _subagents_payload("T-9"))
    assert r.returncode == 2, f"must block, not exit 1; stderr={r.stderr!r}"


@pytest.mark.parametrize("body", ['"a string"', "123", "null", "true"])
def test_non_object_evidence_blocks_instead_of_crashing(script: Path, workspace: Path,
                                                        body: str) -> None:
    _write_manifest(workspace, "backend-test", ["T-10"])
    (workspace / ".architect-team" / "reviews" / "T-10.json").write_text(
        body, encoding="utf-8"
    )
    r = _run(script, workspace, _subagents_payload("T-10"))
    assert r.returncode == 2, f"must block, not exit 1; stderr={r.stderr!r}"


def test_evidence_that_would_crash_the_validator_cannot_skip_the_gate(
    script: Path, workspace: Path
) -> None:
    """THE B1 repro, end to end: evidence that SHOULD block, plus one added key
    whose value is unhashable. Before the fix this exited 1 and the completion
    sailed through; it must block exactly as it did without the key."""
    _write_manifest(workspace, "backend-test", ["T-11"])
    ev = _valid_evidence("T-11")
    ev["spec_review"] = "fail"
    ev["quality_review"] = "fail"
    ev["real_not_stubbed"] = False
    ev["check_integrity_review"] = []
    (workspace / ".architect-team" / "reviews" / "T-11.json").write_text(
        json.dumps(ev), encoding="utf-8"
    )
    r = _run(script, workspace, _subagents_payload("T-11"))
    assert r.returncode == 2, f"the added key must not disarm the gate; stderr={r.stderr!r}"


# --------------------------------------------------------------------------- #
# the marker field the session test stands on (design D5)
# --------------------------------------------------------------------------- #

def test_engage_records_an_explicit_session_id(tmp_path: Path) -> None:
    """Scenario: marker carries session id during a run."""
    rc.engage_marker(tmp_path, "architect-team-pipeline", "sess-A")
    assert rc.read_marker(tmp_path)["session_id"] == "sess-A"


def test_engage_falls_back_to_the_environment(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI engagement path (`--engage`) has no hook payload to read the
    session from; the environment is the fallback so the marker still records
    who owns the run."""
    monkeypatch.setenv("CT6_SESSION_ID", "sess-env")
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    assert rc.read_marker(tmp_path)["session_id"] == "sess-env"


def test_engage_prefers_the_explicit_session_over_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CT6_SESSION_ID", "sess-env")
    rc.engage_marker(tmp_path, "architect-team-pipeline", "sess-explicit")
    assert rc.read_marker(tmp_path)["session_id"] == "sess-explicit"


def test_engage_records_null_when_no_session_is_discoverable(tmp_path: Path) -> None:
    """Fail-soft: an unknown session is null, never a fabricated value.

    This docstring used to end "— and a null session id can never satisfy the
    gate's session test", which was true prose about a behaviour F7 removed.
    A null session still cannot SATISFY the session test; what changed is that
    failing it no longer stands the gate down, because undeterminable ownership
    is not the same answer as a different owner. See
    `test_marker_without_session_id_now_gates`."""
    rc.engage_marker(tmp_path, "architect-team-pipeline")
    assert rc.read_marker(tmp_path)["session_id"] is None


def test_reengaging_an_active_marker_updates_the_session(tmp_path: Path) -> None:
    """A resumed run continues under whichever session re-invoked the skill."""
    rc.engage_marker(tmp_path, "architect-team-pipeline", "sess-A")
    started = rc.read_marker(tmp_path)["started_at"]
    rc.engage_marker(tmp_path, "architect-team-pipeline", "sess-B")
    marker = rc.read_marker(tmp_path)
    assert marker["session_id"] == "sess-B"
    assert marker["started_at"] == started, "re-engagement must preserve run identity"


def test_session_id_env_vars_names_the_real_harness_variable() -> None:
    """The harness exports CLAUDE_CODE_SESSION_ID (verified in a live teams
    run). A fallback that reads a name nothing sets is a fallback that never
    fires — pin the real one."""
    assert "CLAUDE_CODE_SESSION_ID" in rc.SESSION_ID_ENV_VARS


def test_resolve_session_id_reads_the_harness_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in rc.SESSION_ID_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-harness-real")
    assert rc.resolve_session_id() == "sess-harness-real"


def test_resolve_session_id_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in rc.SESSION_ID_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    assert rc.resolve_session_id() is None
    assert rc.resolve_session_id("sess-X") == "sess-X"
    monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-harness")
    assert rc.resolve_session_id() == "sess-harness"
    monkeypatch.setenv("CT6_SESSION_ID", "sess-ct6")
    assert rc.resolve_session_id() == "sess-ct6"
    assert rc.resolve_session_id("   ") == "sess-ct6", "blank explicit falls through"


def test_is_orchestrator_session_is_the_one_shared_basis() -> None:
    marker = {"status": "active", "session_id": "sess-A"}
    assert rc.is_orchestrator_session(marker, "sess-A") is True
    assert rc.is_orchestrator_session(marker, "sess-B") is False
    assert rc.is_orchestrator_session(marker, "") is False
    assert rc.is_orchestrator_session(marker, None) is False
    assert rc.is_orchestrator_session({"session_id": None}, "sess-A") is False
    assert rc.is_orchestrator_session(None, "sess-A") is False


def _run_cli(plugin_root: Path, workspace: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(plugin_root / "hooks" / "run_continuity.py"),
         *args, "--root", str(workspace)],
        text=True, capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def test_cli_engage_records_the_session_id_flag(plugin_root: Path, tmp_path: Path) -> None:
    r = _run_cli(plugin_root, tmp_path, "--engage", "architect-team-pipeline",
                 "--session-id", "sess-cli")
    assert r.returncode == 0, r.stderr
    assert rc.read_marker(tmp_path)["session_id"] == "sess-cli"


def test_cli_engage_records_the_environment_session_id(plugin_root: Path, tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CT6_SESSION_ID", "sess-env-cli")
    r = _run_cli(plugin_root, tmp_path, "--engage", "architect-team-pipeline")
    assert r.returncode == 0, r.stderr
    assert rc.read_marker(tmp_path)["session_id"] == "sess-env-cli"


def test_cli_engage_without_a_session_still_engages(plugin_root: Path, tmp_path: Path) -> None:
    """Recording the session is best-effort; it never blocks engagement."""
    r = _run_cli(plugin_root, tmp_path, "--engage", "architect-team-pipeline")
    assert r.returncode == 0, r.stderr
    marker = rc.read_marker(tmp_path)
    assert marker["status"] == "active"
    assert marker["session_id"] is None


# --------------------------------------------------------------------------- #
# teams mode: ONE session id for the Lead and every teammate
#
# The gate was specced on the premise that the orchestrator's session is
# distinguishable from a teammate's. In CT6's DEFAULT dispatch mode (Agent
# Teams) that premise is false: the Lead and every teammate run under a single
# `CLAUDE_CODE_SESSION_ID` and a single transcript, so the session test matches
# for all of them. Without the registration test below, every teammate
# completing its own shared board task is blocked and the run wedges.
#
# What still blocks is what the postmortem actually described: a task no
# manifest mentions ANYWHERE — an arbitrary board item flipped to `completed`.
# --------------------------------------------------------------------------- #

def _write_manifest_with_board_task(workspace: Path, name: str, *, shared_task_id: str,
                                    task_ids: list[str], evidence_ids: list[str]) -> None:
    """The real CT6 manifest shape: the board id and the tasks.md ids are
    recorded SEPARATELY from the evidence ids."""
    (workspace / ".architect-team" / "teammates" / f"{name}.json").write_text(
        json.dumps({
            "schema_version": 2,
            "teammate": name,
            "spawned_at": _now_iso(),
            "shared_task_id": shared_task_id,
            "task_ids": task_ids,
            "files_owned": [],
            "expected_review_evidence": evidence_ids,
        }),
        encoding="utf-8",
    )


def test_board_task_registered_as_shared_task_id_is_not_unmanifested(
    script: Path, workspace: Path
) -> None:
    """THE teams-mode regression: the completing session IS the marker's session
    (there is only one), but the board task is registered to a teammate, so the
    gate stands down and the run proceeds."""
    _write_marker(workspace)
    _write_manifest_with_board_task(
        workspace, "hei-hooks-gates",
        shared_task_id="4", task_ids=["2.1", "2.2"], evidence_ids=["hei-group2"],
    )
    r = _run(script, workspace, _subagents_payload("4"))
    assert r.returncode == 0, f"a registered board task must complete; stderr={r.stderr!r}"


def test_board_task_registered_as_shared_task_id_in_teams_shape(script: Path,
                                                                workspace: Path) -> None:
    _write_marker(workspace)
    _write_manifest_with_board_task(
        workspace, "hei-hooks-gates",
        shared_task_id="4", task_ids=["2.1"], evidence_ids=["hei-group2"],
    )
    r = _run(script, workspace, _teams_payload("4"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_task_registered_in_task_ids_is_not_unmanifested(script: Path,
                                                         workspace: Path) -> None:
    _write_marker(workspace)
    _write_manifest_with_board_task(
        workspace, "hei-hooks-gates",
        shared_task_id="4", task_ids=["2.1"], evidence_ids=["hei-group2"],
    )
    r = _run(script, workspace, _subagents_payload("2.1"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_a_task_no_manifest_mentions_anywhere_still_blocks(script: Path,
                                                           workspace: Path) -> None:
    """The hole the postmortem described stays closed: manifests exist, none
    mentions this id in ANY field, and the run's session flips it to completed."""
    _write_marker(workspace)
    _write_manifest_with_board_task(
        workspace, "hei-hooks-gates",
        shared_task_id="4", task_ids=["2.1"], evidence_ids=["hei-group2"],
    )
    r = _run(script, workspace, _subagents_payload("board-99"))
    assert r.returncode == 2, f"stderr={r.stderr!r}"
    assert "board-99" in r.stderr


def test_registration_does_not_weaken_the_evidence_gate(script: Path,
                                                        workspace: Path) -> None:
    """Standing down for a REGISTERED board id must not leak into the evidence
    scope: an id in expected_review_evidence still needs its evidence file."""
    _write_marker(workspace)
    _write_manifest_with_board_task(
        workspace, "hei-hooks-gates",
        shared_task_id="4", task_ids=["2.1"], evidence_ids=["hei-group2"],
    )
    r = _run(script, workspace, _subagents_payload("hei-group2"))
    assert r.returncode == 2
    assert "missing review evidence" in r.stderr


# --------------------------------------------------------------------------- #
# R5 / R9b / R1 (adversarial round 3b) — where ids meet manifests
#
# R5: a task id arrives from the harness as a STRING, but a manifest may record
# it as a JSON number. `"3" in [3]` is False, so an integer-typed entry silently
# voided the evidence gate for that task — the exact "registered but unenforced"
# shape this slice exists to close.
#
# R9b: a manifest that parses to a LIST crashed the ownership scan with
# AttributeError. In hook semantics a crash is exit 1, which is fail-OPEN — one
# malformed file in the directory disarmed the gate for every task.
#
# R1: an `expected_review_evidence` entry that can never match any task id (a
# path, an evidence FILENAME, a non-id type) fails silently — the gate simply
# never fires for that teammate and nothing says so.
# --------------------------------------------------------------------------- #

def _write_raw_manifest(workspace: Path, name: str, body) -> None:
    (workspace / ".architect-team" / "teammates" / f"{name}.json").write_text(
        json.dumps(body), encoding="utf-8"
    )


def test_integer_typed_expected_id_still_enforces_evidence(script: Path,
                                                           workspace: Path) -> None:
    """R5: `expected_review_evidence: [3]` must own task "3"."""
    _write_raw_manifest(workspace, "backend-test", {
        "schema_version": 2, "teammate": "backend-test",
        "task_ids": [3], "files_owned": [], "expected_review_evidence": [3],
    })
    r = _run(script, workspace, _subagents_payload("3"))
    assert r.returncode == 2, f"an int-typed id must not void the gate; stderr={r.stderr!r}"
    assert "missing review evidence" in r.stderr


def test_integer_typed_expected_id_accepts_valid_evidence(script: Path,
                                                          workspace: Path) -> None:
    _write_raw_manifest(workspace, "backend-test", {
        "schema_version": 2, "teammate": "backend-test",
        "task_ids": [3], "files_owned": [], "expected_review_evidence": [3],
    })
    (workspace / ".architect-team" / "reviews" / "3.json").write_text(
        json.dumps(_valid_evidence("3")), encoding="utf-8"
    )
    r = _run(script, workspace, _subagents_payload("3"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


@pytest.mark.parametrize("body", [[], [{"teammate": "x"}], "a string", 123, None])
def test_non_object_manifest_never_crashes_the_scan(script: Path, workspace: Path,
                                                    body) -> None:
    """R9b: a malformed manifest is skipped with a warning — never a crash, and
    never a silent disarming of the gate for the manifests that ARE valid."""
    _write_raw_manifest(workspace, "broken", body)
    _write_manifest(workspace, "backend-test", ["T-20"])
    r = _run(script, workspace, _subagents_payload("T-20"))
    assert r.returncode == 2, f"the valid manifest must still be found; stderr={r.stderr!r}"
    assert "missing review evidence" in r.stderr


def test_non_object_manifest_alone_does_not_block_an_unowned_task(script: Path,
                                                                  workspace: Path) -> None:
    _write_raw_manifest(workspace, "broken", [])
    r = _run(script, workspace, _subagents_payload("T-21"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


@pytest.mark.parametrize("entry", [
    "reviews/hei-group2.json",
    ".architect-team/reviews/x.json",
    "hei-group2.json",
    "..",
    ".hidden",
    {"task": "x"},
    ["x"],
    None,
    True,
    "",
])
def test_unusable_expected_entry_is_warned_about(script: Path, workspace: Path,
                                                 entry) -> None:
    """R1: an entry that can never match any task id must SAY so rather than
    silently never firing."""
    _write_raw_manifest(workspace, "backend-test", {
        "schema_version": 2, "teammate": "backend-test",
        "task_ids": [], "files_owned": [], "expected_review_evidence": [entry],
    })
    r = _run(script, workspace, _subagents_payload("T-22"))
    assert "expected_review_evidence" in r.stderr, r.stderr
    assert "backend-test" in r.stderr, r.stderr


def test_usable_entries_produce_no_warning(script: Path, workspace: Path) -> None:
    """The warning must be silent for well-formed manifests — both string and
    integer ids are usable."""
    _write_raw_manifest(workspace, "backend-test", {
        "schema_version": 2, "teammate": "backend-test",
        "task_ids": ["T-1", 3], "files_owned": [],
        "expected_review_evidence": ["T-1", 3],
    })
    r = _run(script, workspace, _subagents_payload("T-99"))
    assert "expected_review_evidence" not in r.stderr, r.stderr


# --------------------------------------------------------------------------- #
# the two enforcement surfaces agree on who the orchestrator is
# --------------------------------------------------------------------------- #

def _run_stop_audit(plugin_root: Path, workspace: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(plugin_root / "hooks" / "pipeline-completion-audit.py")],
        input=json.dumps(payload), text=True, capture_output=True,
        cwd=str(workspace), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def test_both_surfaces_agree_on_the_orchestrator_session(
    plugin_root: Path, script: Path, workspace: Path
) -> None:
    """One session basis, two gates (design D5).

    The completion-status gate and the Stop-hook continuation guard both ask
    `run_continuity.is_orchestrator_session`. This pins the agreement
    behaviourally: for the SAME workspace and marker, the session the gate
    blocks is the session the Stop audit treats as the run's orchestrator (it
    gets the CONTINUE block rather than the legacy one-shot allow), and the
    session the gate leaves alone is the one the audit does not.
    """
    _write_marker(workspace)

    gate_owner = _run(script, workspace, _subagents_payload("board-7"))
    audit_owner = _run_stop_audit(plugin_root, workspace, {
        "session_id": ORCH_SESSION, "stop_hook_active": True,
    })
    assert gate_owner.returncode == 2, gate_owner.stderr
    assert audit_owner.returncode == 2, audit_owner.stderr
    assert "CONTINUE" in audit_owner.stderr

    gate_other = _run(script, workspace, _subagents_payload("board-7", session_id="sess-other"))
    audit_other = _run_stop_audit(plugin_root, workspace, {
        "session_id": "sess-other", "stop_hook_active": True,
    })
    assert gate_other.returncode == 0, gate_other.stderr
    assert audit_other.returncode == 0, audit_other.stderr
