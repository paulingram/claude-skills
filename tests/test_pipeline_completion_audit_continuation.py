"""Tests for the v3.30.0 CONTINUATION GUARD in hooks/pipeline-completion-audit.py.

The legacy worklist-audit semantics are pinned by test_pipeline_completion_audit.py
(all preserved verbatim for non-engaged sessions). This file pins the new
behaviour: the run-lifecycle check (an ACTIVE active-run.json blocks a Stop even
with a clean worklist), the bounded no-progress persistence for ENGAGED
sessions (stop_hook_active no longer means give-up-after-one-block), the
auto-escalation at the budget, the resume nudge for non-engaged sessions, and
the --check mode's deliberate exclusion of the lifecycle check.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hooks import run_continuity as rc


@pytest.fixture()
def script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def _run_stop(script: Path, workspace: Path, payload: dict,
              env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop(rc.DISABLE_ENV, None)
    env.pop(rc.MAX_NO_PROGRESS_ENV, None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True, capture_output=True, cwd=str(workspace), env=env,
    )


def _run_check(script: Path, workspace: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop(rc.DISABLE_ENV, None)
    return subprocess.run(
        [sys.executable, str(script), "--check"],
        text=True, capture_output=True, cwd=str(workspace), env=env,
    )


def _at(workspace: Path) -> Path:
    d = workspace / ".architect-team"
    d.mkdir(exist_ok=True)
    return d


def _user(text: str, ts: str = "2026-07-03T10:00:00Z") -> dict:
    return {"type": "user", "timestamp": ts,
            "message": {"role": "user", "content": text}}


def _skill_call(skill: str, ts: str = "2026-07-03T10:00:05Z") -> dict:
    return {"type": "assistant", "timestamp": ts,
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]}}


def _engaged_transcript(workspace: Path, extra: list[dict] | None = None) -> Path:
    records = [
        _user("<command-name>/architect-team:architect-team</command-name> build it"),
        _skill_call("architect-team-pipeline"),
    ] + (extra or [])
    p = workspace / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


def _plain_transcript(workspace: Path) -> Path:
    p = workspace / "plain.jsonl"
    p.write_text(json.dumps(_user("continue")) + "\n", encoding="utf-8")
    return p


# --- run lifecycle: an active marker blocks a clean-worklist stop ------------

def test_active_marker_clean_worklist_blocks_stop(script: Path, workspace: Path) -> None:
    """THE arbitrary-stop gap: mid-run, worklist momentarily clean, model tries
    to end the turn with 'want me to continue?' — the Stop must be blocked."""
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    rc.update_marker(workspace, slug="my-feature", phase="Phase 3")
    r = _run_stop(script, workspace, {})
    assert r.returncode == 2, f"active run + clean worklist must still block; stderr={r.stderr!r}"
    assert "my-feature" in r.stderr
    assert "mark-complete" in r.stderr


def test_complete_marker_allows_stop(script: Path, workspace: Path) -> None:
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    rc.mark_complete(workspace)
    assert _run_stop(script, workspace, {}).returncode == 0


def test_check_mode_ignores_lifecycle(script: Path, workspace: Path) -> None:
    """Phase 8 runs --check BEFORE the auto-commit, while the run is still
    active — the lifecycle check must not apply there."""
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    assert _run_check(script, workspace).returncode == 0


def test_kill_switch_restores_legacy(script: Path, workspace: Path) -> None:
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    r = _run_stop(script, workspace, {}, env_extra={rc.DISABLE_ENV: "1"})
    assert r.returncode == 0


def test_malformed_marker_fails_open(script: Path, workspace: Path) -> None:
    p = rc.marker_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{broken", encoding="utf-8")
    assert _run_stop(script, workspace, {}).returncode == 0


# --- sanctioned pauses still win ---------------------------------------------

def test_escalation_marker_allows_despite_active_run(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    (at / "escalation-pending.md").write_text("waiting on the human", encoding="utf-8")
    assert _run_stop(script, workspace, {}).returncode == 0


def test_fresh_in_progress_allows_despite_active_run(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    (at / "in-progress.md").write_text("waiting on deploy", encoding="utf-8")
    assert _run_stop(script, workspace, {}).returncode == 0


# --- non-engaged sessions: legacy one-nudge + the resume directive -----------

def test_non_engaged_gets_one_nudge_with_resume_directive(script: Path, workspace: Path) -> None:
    _at(workspace)
    rc.engage_marker(workspace, "bug-fix-pipeline")
    t = _plain_transcript(workspace)
    r = _run_stop(script, workspace, {"transcript_path": str(t)})
    assert r.returncode == 2
    assert "RUN-CONTINUITY NOTE" in r.stderr
    assert 'Skill(skill="bug-fix-pipeline")' in r.stderr
    # legacy never-loop semantics preserved for non-engaged sessions
    r2 = _run_stop(script, workspace, {"transcript_path": str(t), "stop_hook_active": True})
    assert r2.returncode == 0


# --- engaged sessions: bounded persistence -----------------------------------

def test_engaged_blocks_past_stop_hook_active(script: Path, workspace: Path) -> None:
    """The one-block-then-give-up gap: an ENGAGED orchestrator session keeps
    getting blocked on subsequent stops (budget not yet exhausted)."""
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    t = _engaged_transcript(workspace)
    payload = {"transcript_path": str(t), "stop_hook_active": True}
    r = _run_stop(script, workspace, payload)
    assert r.returncode == 2, f"engaged session must be re-blocked; stderr={r.stderr!r}"
    assert "CONTINUE" in r.stderr
    assert "want me to continue" in r.stderr, "the message names the forbidden deferral"


def test_engaged_no_progress_auto_escalates_at_budget(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    t = _engaged_transcript(workspace)
    payload = {"transcript_path": str(t)}
    env = {rc.MAX_NO_PROGRESS_ENV: "1"}
    r1 = _run_stop(script, workspace, payload, env_extra=env)
    assert r1.returncode == 2, r1.stderr
    # nothing changed between stops => no progress => budget (1) exhausted
    r2 = _run_stop(script, workspace, payload, env_extra=env)
    assert r2.returncode == 0, r2.stderr
    assert "no-progress" in r2.stderr
    esc = at / "escalation-pending.md"
    assert esc.exists(), "auto-escalation must leave the sanctioned pause marker"
    assert "no progress" in esc.read_text(encoding="utf-8").lower()
    # and the NEXT stop is sanctioned via that marker
    assert _run_stop(script, workspace, payload, env_extra=env).returncode == 0


def test_engaged_progress_resets_budget(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    t = _engaged_transcript(workspace)
    payload = {"transcript_path": str(t)}
    env = {rc.MAX_NO_PROGRESS_ENV: "1"}
    assert _run_stop(script, workspace, payload, env_extra=env).returncode == 2
    time.sleep(0.01)
    (at / "reviews").mkdir(exist_ok=True)
    (at / "reviews" / "T1.json").write_text("{}", encoding="utf-8")  # progress
    r = _run_stop(script, workspace, payload, env_extra=env)
    assert r.returncode == 2, "progress => keep pushing (unbounded), not escalate"
    assert not (at / "escalation-pending.md").exists()


def test_engaged_with_violations_lists_worklist(script: Path, workspace: Path) -> None:
    at = _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    sr_dir = at / "solution-requirements"
    sr_dir.mkdir()
    (sr_dir / "SR-1.json").write_text(
        json.dumps({"solution_id": "SR-1", "status": "open",
                    "origin": {"kind": "editability-gap"}}), encoding="utf-8")
    t = _engaged_transcript(workspace)
    r = _run_stop(script, workspace, {"transcript_path": str(t)})
    assert r.returncode == 2
    assert "SR-1" in r.stderr and "CONTINUE" in r.stderr


def test_engaged_post_compact_block_directs_skill_reload(script: Path, workspace: Path) -> None:
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    t = _engaged_transcript(workspace, extra=[
        {"type": "system", "subtype": "compact_boundary"},
        _user("keep going", ts="2026-07-03T11:00:00Z"),
    ])
    r = _run_stop(script, workspace, {"transcript_path": str(t)})
    assert r.returncode == 2
    assert "re-invoke Skill" in r.stderr, "post-compact the block directs a playbook reload"


# --- v3.30.0 adversarial-review remediations ---------------------------------

def test_stale_marker_does_not_block_non_engaged(script: Path, workspace: Path) -> None:
    """Remediation #3: an abandoned run's marker stops gating after the
    staleness bound — no lifecycle block, no nudge tax on future sessions."""
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    m = rc.read_marker(workspace)
    m["updated_at"] = "2020-01-01T00:00:00+00:00"
    rc._atomic_write_json(rc.marker_path(workspace), m)
    assert _run_stop(script, workspace, {}).returncode == 0


def test_session_id_match_counts_as_engaged(script: Path, workspace: Path) -> None:
    """Remediation #4: the session recorded on the marker at engagement time
    is the orchestrator even when its Skill call scrolled past the transcript
    tail cap — the continuation guard applies via the session_id match."""
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline", "sess-orch")
    t = _plain_transcript(workspace)  # no Skill call visible in the transcript
    r = _run_stop(script, workspace, {
        "transcript_path": str(t),
        "session_id": "sess-orch",
        "stop_hook_active": True,
    })
    assert r.returncode == 2, f"session-id match must engage the guard; stderr={r.stderr!r}"
    assert "CONTINUE" in r.stderr


def test_engaged_block_touches_marker_freshness(script: Path, workspace: Path) -> None:
    """The continuation guard heartbeats the marker so a live run never goes
    stale — and the touch is fingerprint-excluded (no fake progress)."""
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    m = rc.read_marker(workspace)
    before = "2026-07-01T00:00:00+00:00"
    m["updated_at"] = before
    rc._atomic_write_json(rc.marker_path(workspace), m)
    t = _engaged_transcript(workspace)
    env = {rc.MAX_NO_PROGRESS_ENV: "3", rc.MARKER_STALE_HOURS_ENV: "999999"}
    assert _run_stop(script, workspace, {"transcript_path": str(t)}, env_extra=env).returncode == 2
    assert rc.read_marker(workspace)["updated_at"] != before, "the block must heartbeat the marker"
    # and two identical no-progress stops still increment despite the touch
    r = _run_stop(script, workspace, {"transcript_path": str(t)}, env_extra=env)
    assert r.returncode == 2 and "no-progress continuation attempt 1" in r.stderr


def test_new_block_messages_are_ascii(script: Path, workspace: Path) -> None:
    """Remediation #6: the new model-facing stderr strings stay ASCII so a
    cp1252 console renders them verbatim."""
    _at(workspace)
    rc.engage_marker(workspace, "architect-team-pipeline")
    rc.update_marker(workspace, slug="my-feature", phase="Phase 3")
    t = _engaged_transcript(workspace)
    r = _run_stop(script, workspace, {"transcript_path": str(t)})
    assert r.returncode == 2
    for line in r.stderr.splitlines():
        if line.startswith("pipeline-completion-audit: CONTINUE"):
            assert line == line.encode("ascii", "replace").decode("ascii"), (
                f"non-ASCII in the continuation block header: {line!r}"
            )
    assert "—" not in r.stderr, "em-dashes are banned from the new stderr strings"
