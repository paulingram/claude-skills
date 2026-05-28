"""Unit tests for the v1.0.0 hook trigger split — REQ-4 in
`openspec/changes/agent-teams-refactor/specs/agent-teams-mode/spec.md`.

The architect-team plugin's three enforcement hooks
(`review-gate-task.py`, `teammate-idle-check.py`,
`pipeline-completion-audit.py`) must handle BOTH trigger shapes:

- Subagents mode (the v0.9.x shape): `PostToolUse(TaskUpdate)`,
  `SubagentStop`, `Stop`.
- Teams mode (the v1.0.0 agent-teams shape): `TaskCompleted`,
  `TeammateIdle`, `Stop` (unchanged for completion-audit).

Enforcement contract — `.architect-team/reviews/<task-id>.json` v6
validation, exit 2 on gap with structured feedback — must be identical
across triggers. These tests prove the two payload shapes produce the
SAME exit code AND the SAME block-with-feedback message body for the
same underlying violation.

Spec scenarios:
- REQ-4.1 review-gate-task handles PostToolUse(TaskUpdate)
- REQ-4.2 review-gate-task handles TaskCompleted
- REQ-4.3 teammate-idle-check handles both SubagentStop and TeammateIdle
- REQ-4.4 pipeline-completion-audit Stop trigger unchanged
"""
import json
from pathlib import Path

import pytest

from tests.helpers.hook_runner import run_hook as _run


# --- fixtures -----------------------------------------------------------


@pytest.fixture()
def review_gate_script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "review-gate-task.py"


@pytest.fixture()
def idle_check_script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "teammate-idle-check.py"


@pytest.fixture()
def completion_audit_script(plugin_root: Path) -> Path:
    return plugin_root / "hooks" / "pipeline-completion-audit.py"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A temp workspace with the .architect-team layout the hooks expect."""
    (tmp_path / ".architect-team" / "reviews").mkdir(parents=True)
    (tmp_path / ".architect-team" / "teammates").mkdir(parents=True)
    return tmp_path


# --- helpers ------------------------------------------------------------


def _valid_evidence(task_id: str, teammate: str = "backend-test") -> dict:
    """Evidence schema v6 — must match hooks/review_evidence_schema.py exactly."""
    return {
        "schema_version": 6,
        "task_id": task_id,
        "teammate": teammate,
        "completed_at": "2026-05-28T10:00:00Z",
        "spec_review": "pass",
        "quality_review": "pass",
        "real_not_stubbed": True,
        "tests": {"added": 2, "passing": 2, "unit": ["t1", "t2"], "integration": [], "e2e": []},
        "demo_artifact": "curl http://example",
        "files_changed": ["src/x.py"],
        "reuse_compliance": "ok",
        "visual_fidelity_review": "n/a",
        "visual_fidelity_review_note": "backend-only slice; no frontend files touched",
        "test_completeness_review": "n/a",
        "test_completeness_review_note": "backend-only slice; integration is the qualifying kind",
        "integration_testing_review": "n/a",
        "integration_testing_review_note": "backend-only slice with no frontend; no cross-layer surface",
        "ui_interaction_review": "n/a",
        "ui_interaction_review_note": "backend-only slice; no UI/frontend interactive surface",
        "independent_review": {
            "reviewer": "task-reviewer",
            "verdict": "pass",
            "spec_review": "pass",
            "quality_review": "pass",
            "real_not_stubbed": True,
            "reuse_compliance": "ok",
            "reviewed_at": "2026-05-28T11:00:00Z",
        },
    }


def _write_manifest(workspace: Path, name: str, task_ids: list[str]) -> None:
    (workspace / ".architect-team" / "teammates" / f"{name}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "teammate": name,
                "spawned_at": "2026-05-28T09:00:00Z",
                "task_ids": task_ids,
                "files_owned": [],
                "expected_review_evidence": task_ids,
            }
        ),
        encoding="utf-8",
    )


def _write_evidence(workspace: Path, task_id: str, teammate: str = "backend-test") -> None:
    (workspace / ".architect-team" / "reviews" / f"{task_id}.json").write_text(
        json.dumps(_valid_evidence(task_id, teammate)), encoding="utf-8"
    )


def _post_tool_use_payload(task_id: str, status: str = "completed") -> dict:
    """Subagents-mode payload: PostToolUse hook firing on TaskUpdate."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": task_id, "status": status},
    }


def _task_completed_payload(task_id: str) -> dict:
    """Teams-mode payload: TaskCompleted hook firing on shared-task-list
    completion. Per https://code.claude.com/docs/en/hooks the task identifier
    travels under `task.id`."""
    return {
        "hook_event_name": "TaskCompleted",
        "task": {"id": task_id},
    }


def _subagent_stop_payload(name: str) -> dict:
    """Subagents-mode payload: SubagentStop hook firing when a one-shot Agent
    dispatch completes. Identity travels under `subagent.name`."""
    return {
        "hook_event_name": "SubagentStop",
        "subagent": {"name": name},
    }


def _teammate_idle_payload(name: str) -> dict:
    """Teams-mode payload: TeammateIdle hook firing when a long-lived teammate
    goes idle in the shared task list. Identity travels under `teammate.name`."""
    return {
        "hook_event_name": "TeammateIdle",
        "teammate": {"name": name},
    }


# --- REQ-4.1: review-gate-task handles PostToolUse(TaskUpdate) ----------


def test_review_gate_post_tool_use_allow_when_evidence_valid(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.1 baseline: subagents-mode payload + valid evidence => allow."""
    _write_manifest(workspace, "backend-test", ["T-PTU-1"])
    _write_evidence(workspace, "T-PTU-1")
    r = _run(review_gate_script, workspace, _post_tool_use_payload("T-PTU-1"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_review_gate_post_tool_use_block_when_evidence_missing(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.1: subagents-mode payload + missing evidence => exit 2."""
    _write_manifest(workspace, "backend-test", ["T-PTU-2"])
    r = _run(review_gate_script, workspace, _post_tool_use_payload("T-PTU-2"))
    assert r.returncode == 2
    assert "T-PTU-2" in r.stderr
    assert "missing review evidence" in r.stderr


# --- REQ-4.2: review-gate-task handles TaskCompleted --------------------


def test_review_gate_task_completed_allow_when_evidence_valid(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.2: teams-mode payload + valid evidence => allow.

    The TaskCompleted payload's task identifier travels under `task.id`,
    not `tool_input.taskId`. The hook must extract the right field and
    still find the SAME evidence file at the SAME path.
    """
    _write_manifest(workspace, "backend-test", ["T-TC-1"])
    _write_evidence(workspace, "T-TC-1")
    r = _run(review_gate_script, workspace, _task_completed_payload("T-TC-1"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_review_gate_task_completed_block_when_evidence_missing(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.2: teams-mode payload + missing evidence => exit 2 with the SAME
    block-with-feedback message as the subagents-mode equivalent."""
    _write_manifest(workspace, "backend-test", ["T-TC-2"])
    r = _run(review_gate_script, workspace, _task_completed_payload("T-TC-2"))
    assert r.returncode == 2
    assert "T-TC-2" in r.stderr
    assert "missing review evidence" in r.stderr


def test_review_gate_task_completed_block_when_evidence_invalid(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.2: teams-mode payload + structurally-invalid evidence => exit 2.

    The schema validation lives in `review_evidence_schema.validate_evidence`
    and is shared with the subagents-mode path; the failure mode must surface
    via the teams-mode trigger too.
    """
    _write_manifest(workspace, "backend-test", ["T-TC-3"])
    bad = _valid_evidence("T-TC-3")
    bad["spec_review"] = "fail"
    (workspace / ".architect-team" / "reviews" / "T-TC-3.json").write_text(
        json.dumps(bad), encoding="utf-8"
    )
    r = _run(review_gate_script, workspace, _task_completed_payload("T-TC-3"))
    assert r.returncode == 2
    assert "T-TC-3" in r.stderr
    assert "spec_review" in r.stderr


def test_review_gate_same_block_message_across_triggers(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.1 + 4.2: the SAME underlying violation (missing evidence) must
    produce the SAME block-with-feedback message body across both trigger
    shapes — the enforcement contract is identical, only the dispatch shape
    differs. Anything weaker is silent divergence."""
    _write_manifest(workspace, "backend-test", ["T-COMP-A", "T-COMP-B"])

    r_subagents = _run(review_gate_script, workspace, _post_tool_use_payload("T-COMP-A"))
    r_teams = _run(review_gate_script, workspace, _task_completed_payload("T-COMP-B"))

    assert r_subagents.returncode == 2
    assert r_teams.returncode == 2

    # Stderr will differ in the task_id substring, but the structural shape
    # (review-gate-task: blocking ... missing review evidence at ...) must match.
    assert "missing review evidence at" in r_subagents.stderr
    assert "missing review evidence at" in r_teams.stderr
    assert r_subagents.stderr.startswith("review-gate-task: blocking")
    assert r_teams.stderr.startswith("review-gate-task: blocking")


def test_review_gate_task_completed_ignored_when_not_teammate_task(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.2 scoping: a TaskCompleted event for a task that is NOT in any
    teammate manifest must NOT block. The same scoping rule that protects
    non-architect-team TaskUpdate flows must protect non-architect-team
    TaskCompleted flows."""
    # manifest claims a DIFFERENT task, so T-EXTERNAL is not a teammate task
    _write_manifest(workspace, "backend-test", ["T-OWNED"])
    r = _run(review_gate_script, workspace, _task_completed_payload("T-EXTERNAL"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_review_gate_task_completed_path_traversal_rejected(
    review_gate_script: Path, workspace: Path
) -> None:
    """REQ-4.2 + safe_id: a malicious task id via the TaskCompleted shape must
    be rejected with the same exit-2 semantics as via PostToolUse."""
    unsafe = "T-1/../../etc/passwd"
    _write_manifest(workspace, "backend-test", [unsafe])
    r = _run(review_gate_script, workspace, _task_completed_payload(unsafe))
    assert r.returncode == 2
    assert "path-traversal" in r.stderr


# --- REQ-4.3: teammate-idle-check handles both SubagentStop AND TeammateIdle


def test_idle_check_subagent_stop_allow_when_evidence_complete(
    idle_check_script: Path, workspace: Path
) -> None:
    """REQ-4.3 baseline: SubagentStop payload + all evidence present => allow."""
    _write_manifest(workspace, "backend-idle-a", ["T-SS-1", "T-SS-2"])
    _write_evidence(workspace, "T-SS-1")
    _write_evidence(workspace, "T-SS-2")
    r = _run(idle_check_script, workspace, _subagent_stop_payload("backend-idle-a"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_idle_check_teammate_idle_allow_when_evidence_complete(
    idle_check_script: Path, workspace: Path
) -> None:
    """REQ-4.3: TeammateIdle payload + all evidence present => allow.

    The teams-mode trigger carries identity under `teammate.name` instead of
    `subagent.name`. Same manifest lookup; same result.
    """
    _write_manifest(workspace, "backend-idle-b", ["T-TI-1", "T-TI-2"])
    _write_evidence(workspace, "T-TI-1")
    _write_evidence(workspace, "T-TI-2")
    r = _run(idle_check_script, workspace, _teammate_idle_payload("backend-idle-b"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_idle_check_teammate_idle_block_when_evidence_missing(
    idle_check_script: Path, workspace: Path
) -> None:
    """REQ-4.3: TeammateIdle payload + missing evidence => exit 2 with the
    SAME block-with-feedback message body."""
    _write_manifest(workspace, "backend-idle-c", ["T-TI-3", "T-TI-4"])
    _write_evidence(workspace, "T-TI-3")  # T-TI-4 missing
    r = _run(idle_check_script, workspace, _teammate_idle_payload("backend-idle-c"))
    assert r.returncode == 2
    assert "T-TI-4" in r.stderr
    assert "no review evidence" in r.stderr


def test_idle_check_same_block_message_across_triggers(
    idle_check_script: Path, workspace: Path
) -> None:
    """REQ-4.3: the SAME underlying violation (a missing evidence file for a
    task in the teammate's manifest) must produce the SAME block-with-feedback
    message body across SubagentStop and TeammateIdle."""
    _write_manifest(workspace, "backend-idle-d", ["T-DUP-1"])
    _write_manifest(workspace, "backend-idle-e", ["T-DUP-2"])

    r_subagents = _run(
        idle_check_script, workspace, _subagent_stop_payload("backend-idle-d")
    )
    r_teams = _run(
        idle_check_script, workspace, _teammate_idle_payload("backend-idle-e")
    )

    assert r_subagents.returncode == 2
    assert r_teams.returncode == 2
    # Structural prefix must match across both trigger shapes.
    assert r_subagents.stderr.startswith("teammate-idle-check: blocking idle of teammate")
    assert r_teams.stderr.startswith("teammate-idle-check: blocking idle of teammate")
    assert "no review evidence" in r_subagents.stderr
    assert "no review evidence" in r_teams.stderr


def test_idle_check_teammate_idle_invalid_evidence_blocks(
    idle_check_script: Path, workspace: Path
) -> None:
    """REQ-4.3: TeammateIdle + structurally-invalid evidence (a v6 schema gap)
    must block. The shared `validate_evidence` flow is exercised."""
    _write_manifest(workspace, "backend-idle-f", ["T-TI-INV"])
    bad = _valid_evidence("T-TI-INV")
    bad["real_not_stubbed"] = False
    (workspace / ".architect-team" / "reviews" / "T-TI-INV.json").write_text(
        json.dumps(bad), encoding="utf-8"
    )
    r = _run(idle_check_script, workspace, _teammate_idle_payload("backend-idle-f"))
    assert r.returncode == 2
    assert "T-TI-INV" in r.stderr
    assert "real_not_stubbed" in r.stderr


def test_idle_check_teammate_idle_no_manifest_allows(
    idle_check_script: Path, workspace: Path
) -> None:
    """REQ-4.3 scoping: a TeammateIdle for a name with no manifest at
    `.architect-team/teammates/<name>.json` is NOT an architect-team teammate;
    the hook must allow (same as SubagentStop for non-teammates)."""
    r = _run(idle_check_script, workspace, _teammate_idle_payload("some-other-agent"))
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_idle_check_teammate_idle_path_traversal_rejected(
    idle_check_script: Path, workspace: Path
) -> None:
    """REQ-4.3 + safe_id: a teammate name carrying path-traversal characters
    must be rejected via the teams-mode trigger too."""
    r = _run(
        idle_check_script,
        workspace,
        _teammate_idle_payload("backend/../../etc/passwd"),
    )
    assert r.returncode == 2
    assert "path-traversal" in r.stderr


# --- REQ-4.4: pipeline-completion-audit Stop trigger unchanged ---------


def test_completion_audit_stop_unchanged_clean_workspace(
    completion_audit_script: Path, workspace: Path
) -> None:
    """REQ-4.4: the Stop hook's behavior is the same in both modes — a clean
    workspace (no SRs, no editability dirs, no test-completeness fails)
    exits 0 regardless of which mode dispatched the run.

    The workspace has `.architect-team/teammates/` + `.architect-team/reviews/`
    but no other state, so `_is_real_run` returns False and the hook allows.
    """
    payload = {"hook_event_name": "Stop"}
    r = _run(completion_audit_script, workspace, payload)
    assert r.returncode == 0, f"stderr={r.stderr!r}"


def test_completion_audit_stop_blocks_on_open_sr_regardless_of_mode(
    completion_audit_script: Path, workspace: Path
) -> None:
    """REQ-4.4: an open solution requirement blocks the Stop hook in BOTH
    modes — the audit logic does not branch on mode; the same Stop trigger
    in both modes runs the same `audit()` body verbatim."""
    sr_dir = workspace / ".architect-team" / "solution-requirements"
    sr_dir.mkdir(parents=True)
    (sr_dir / "SR-test.json").write_text(
        json.dumps({"status": "open", "origin": {"kind": "unrelated"}}),
        encoding="utf-8",
    )
    # Need intake-state.json to satisfy _is_real_run
    (workspace / ".architect-team" / "intake-state.json").write_text(
        json.dumps({"dispatch_mode": "teams"}), encoding="utf-8"
    )

    payload = {"hook_event_name": "Stop"}
    r = _run(completion_audit_script, workspace, payload)
    assert r.returncode == 2
    assert "SR-test.json" in r.stderr


# --- hooks.json wiring (REQ-4 registration) ----------------------------


def test_hooks_json_registers_task_completed(plugin_root: Path) -> None:
    """REQ-4.2 wiring: hooks.json must register a TaskCompleted event that
    routes to review-gate-task.py — the teams-mode counterpart of the
    PostToolUse(TaskUpdate) registration."""
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["hooks"].get("TaskCompleted", [])
    assert entries, "no TaskCompleted hook registered"
    cmds = [h["command"] for entry in entries for h in entry["hooks"]]
    assert any("review-gate-task.py" in c for c in cmds), (
        f"no TaskCompleted command references review-gate-task.py; got: {cmds}"
    )


def test_hooks_json_registers_teammate_idle(plugin_root: Path) -> None:
    """REQ-4.3 wiring: hooks.json must register a TeammateIdle event that
    routes to teammate-idle-check.py — the teams-mode counterpart of the
    SubagentStop registration."""
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["hooks"].get("TeammateIdle", [])
    assert entries, "no TeammateIdle hook registered"
    cmds = [h["command"] for entry in entries for h in entry["hooks"]]
    assert any("teammate-idle-check.py" in c for c in cmds), (
        f"no TeammateIdle command references teammate-idle-check.py; got: {cmds}"
    )


def test_hooks_json_teams_mode_entries_use_polyglot_fallback(plugin_root: Path) -> None:
    """The new TaskCompleted + TeammateIdle entries must carry the same
    `|| python ...` polyglot fallback as the existing entries — the
    v0.9.30 cross-platform-hook contract from test_hooks_structure.py
    applies to ALL hook commands, including the new teams-mode entries.
    """
    path = plugin_root / "hooks" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for event in ("TaskCompleted", "TeammateIdle"):
        entries = data["hooks"].get(event, [])
        assert entries, f"missing {event} registration"
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                assert " || python " in cmd, (
                    f"{event} hook command missing polyglot fallback: {cmd!r}"
                )
