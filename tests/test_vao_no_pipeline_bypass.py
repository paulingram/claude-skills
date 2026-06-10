"""Tests for the v2.22.0 Layer 3 tool: verify_no_pipeline_bypass.

Covers the 5 severities (pipeline-bypassed-after-slash-command /
solo-implementation-instead-of-team-dispatch / independent-review-bypassed /
openspec-bypassed / pipeline-confession-language-detected), module constants,
prompt classifier, ledger scanner, fixture round-trip, determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.vao_tools import (
    _PIPELINE_CONFESSION_MARKERS,
    _PIPELINE_DRIVING_SKILLS,
    _PIPELINE_SLASH_COMMAND_PREFIXES,
    _detect_no_openspec_optout,
    _detect_pipeline_invoked,
    _scan_ledger_for_pipeline_elements,
    verify_no_pipeline_bypass,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "pipeline-bypassed-solo-implementation.json"


# ---- module constants ----


def test_pipeline_confession_markers_include_bypass_admission() -> None:
    for m in ("i bypassed all of that", "built it solo", "i overrode your"):
        assert m in _PIPELINE_CONFESSION_MARKERS


def test_pipeline_confession_markers_include_element_confessions() -> None:
    for m in ("no subagents", "no independent review", "no openspec", "no worktree"):
        assert m in _PIPELINE_CONFESSION_MARKERS


def test_pipeline_confession_markers_include_rationalization() -> None:
    for m in ("driving directly from the plan", "tokens into code instead of",
              "mapping/spec ceremony"):
        assert m in _PIPELINE_CONFESSION_MARKERS


def test_pipeline_confession_markers_include_post_hoc_framing() -> None:
    for m in ("the honest framing is", "i told you i was", "your call to make"):
        assert m in _PIPELINE_CONFESSION_MARKERS


def test_pipeline_driving_skills_complete() -> None:
    for s in ("architect-team-pipeline", "bug-fix-pipeline",
              "mini-architect-team-pipeline", "ux-test-builder"):
        assert s in _PIPELINE_DRIVING_SKILLS


def test_pipeline_slash_command_prefixes_complete() -> None:
    for p in ("/architect-team", "/architect-team:bug-fix",
              "/architect-team:mini", "/architect-team:ux-test"):
        assert p in _PIPELINE_SLASH_COMMAND_PREFIXES


# ---- prompt classifier ----


def test_detect_pipeline_invoked_on_slash_command() -> None:
    assert _detect_pipeline_invoked("/architect-team build the dashboard") is True


def test_detect_pipeline_invoked_on_bug_fix_command() -> None:
    assert _detect_pipeline_invoked("/architect-team:bug-fix the login button") is True


def test_detect_pipeline_invoked_on_mini_command() -> None:
    assert _detect_pipeline_invoked("/architect-team:mini add a tooltip") is True


def test_detect_pipeline_not_invoked_on_plain_prose() -> None:
    assert _detect_pipeline_invoked("please add CSV export") is False


def test_detect_pipeline_not_invoked_on_empty_string() -> None:
    assert _detect_pipeline_invoked("") is False


def test_detect_no_openspec_optout() -> None:
    assert _detect_no_openspec_optout("/architect-team --no-openspec build it") is True
    assert _detect_no_openspec_optout("/architect-team build it") is False


# ---- ledger scanner ----


def test_scan_empty_ledger_returns_zeros() -> None:
    counts = _scan_ledger_for_pipeline_elements([])
    assert counts["agent_dispatches"] == 0
    assert counts["skill_invocations"] == 0
    assert counts["first_source_edit_before_skill"] is False


def test_scan_ledger_counts_agent_dispatches() -> None:
    ledger = [
        {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
        {"tool": "Agent", "tool_input": {"subagent_type": "y"}},
        {"tool": "Bash", "tool_input": {"command": "ls"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["agent_dispatches"] == 2


def test_scan_ledger_counts_skill_invocations() -> None:
    ledger = [
        {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["skill_invocations"] == 1


def test_scan_ledger_detects_source_edit_before_skill() -> None:
    ledger = [
        {"tool": "Edit", "tool_input": {"file_path": "/repo/src/x.ts"}},
        {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["first_source_edit_before_skill"] is True


def test_scan_ledger_does_not_flag_edit_after_skill() -> None:
    ledger = [
        {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
        {"tool": "Edit", "tool_input": {"file_path": "/repo/src/x.ts"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["first_source_edit_before_skill"] is False


def test_scan_ledger_does_not_flag_architect_team_state_writes() -> None:
    ledger = [
        {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/intake-state.json"}},
        {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["first_source_edit_before_skill"] is False


def test_scan_ledger_counts_openspec_bash_calls() -> None:
    ledger = [
        {"tool": "Bash", "tool_input": {"command": "openspec init"}},
        {"tool": "Bash", "tool_input": {"command": "openspec validate my-change"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["openspec_calls"] == 2


def test_scan_ledger_counts_worktree_creations() -> None:
    ledger = [
        {"tool": "Bash", "tool_input": {"command": "git worktree add ../repo-slug -b architect-team/slug"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["worktree_creations"] == 1


def test_scan_ledger_counts_review_evidence_files() -> None:
    ledger = [
        {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/task-1.json"}},
        {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/task-2.json"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["review_evidence_files"] == 2


def test_scan_ledger_review_evidence_requires_json_extension() -> None:
    """Operator-precedence regression: a non-.json write under a reviews/ dir
    must NOT count as review evidence. The detection is `(A or B) and .json`,
    not the buggy `A or (B and .json)` that counted any .architect-team/reviews/
    write regardless of extension."""
    ledger = [
        # non-.json under the canonical reviews dir — must NOT count
        {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/notes.md"}},
        # non-.json under a loose reviews/ dir — must NOT count
        {"tool": "Write", "tool_input": {"file_path": "/repo/reviews/summary.txt"}},
        # a real .json review-evidence file — DOES count
        {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/task-9.json"}},
    ]
    counts = _scan_ledger_for_pipeline_elements(ledger)
    assert counts["review_evidence_files"] == 1


# ---- severity 1: pipeline-bypassed-after-slash-command ----


def test_severity_bypass_after_slash_fires_on_pre_skill_edit() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Edit", "tool_input": {"file_path": "/repo/src/x.ts"}},
        ],
    )
    assert v["valid"] is False
    assert any(g["severity"] == "pipeline-bypassed-after-slash-command" for g in v["gaps"])


# ---- severity 2: solo-implementation-instead-of-team-dispatch ----


def test_severity_solo_implementation_fires_with_no_agent_dispatches() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Edit", "tool_input": {"file_path": "/repo/src/x.ts"}},
        ],
    )
    assert v["valid"] is False
    assert any(g["severity"] == "solo-implementation-instead-of-team-dispatch" for g in v["gaps"])


def test_severity_solo_implementation_does_not_fire_with_agent_dispatches() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "y"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
            {"tool": "Bash", "tool_input": {"command": "openspec init"}},
        ],
    )
    assert all(g["severity"] != "solo-implementation-instead-of-team-dispatch" for g in v["gaps"])


# ---- severity 3: independent-review-bypassed ----


def test_severity_review_bypassed_fires_when_agents_but_no_evidence() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Bash", "tool_input": {"command": "openspec init"}},
        ],
    )
    assert any(g["severity"] == "independent-review-bypassed" for g in v["gaps"])


# ---- severity 4: openspec-bypassed ----


def test_severity_openspec_bypassed_fires_when_no_openspec_calls() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
        ],
    )
    assert any(g["severity"] == "openspec-bypassed" for g in v["gaps"])


def test_severity_openspec_bypassed_does_not_fire_when_no_openspec_optout() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team --no-openspec build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
        ],
    )
    assert all(g["severity"] != "openspec-bypassed" for g in v["gaps"])


# ---- severity 4 (broadened): openspec usage via skill / change-folder -------


def test_openspec_bypassed_does_not_fire_with_openspec_propose_skill() -> None:
    """A mini/exploration run that authored the change via the openspec-propose
    Skill (not a Bash call) must NOT trip openspec-bypassed."""
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team:mini add a tooltip",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "mini-architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Skill", "tool_input": {"skill": "openspec-propose"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
        ],
    )
    assert all(g["severity"] != "openspec-bypassed" for g in v["gaps"])


def test_openspec_bypassed_does_not_fire_with_opsx_propose_skill() -> None:
    """The opsx:propose alias is also recognized as legitimate openspec usage."""
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Skill", "tool_input": {"skill": "opsx:propose"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
        ],
    )
    assert all(g["severity"] != "openspec-bypassed" for g in v["gaps"])


def test_openspec_bypassed_does_not_fire_with_openspec_change_artifact() -> None:
    """An openspec/changes/<name>/ artifact write is evidence openspec was used."""
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/openspec/changes/my-change/proposal.md"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
        ],
    )
    assert all(g["severity"] != "openspec-bypassed" for g in v["gaps"])


def test_openspec_bypassed_change_artifact_detected_on_windows_path() -> None:
    """Backslash (Windows) paths into openspec\\changes\\ also count."""
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Edit", "tool_input": {"file_path": "C:\\repo\\openspec\\changes\\my-change\\tasks.md"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
        ],
    )
    assert all(g["severity"] != "openspec-bypassed" for g in v["gaps"])


def test_openspec_bypassed_still_fires_when_truly_never_used() -> None:
    """TRUE-positive preserved: no Bash openspec, no propose Skill, no change
    artifact → openspec-bypassed STILL fires."""
    v = verify_no_pipeline_bypass(
        user_prompt="/architect-team build it",
        toolcall_ledger=[
            {"tool": "Skill", "tool_input": {"skill": "architect-team-pipeline"}},
            {"tool": "Agent", "tool_input": {"subagent_type": "x"}},
            {"tool": "Write", "tool_input": {"file_path": "/repo/.architect-team/reviews/r.json"}},
        ],
    )
    assert any(g["severity"] == "openspec-bypassed" for g in v["gaps"])


def test_scan_ledger_counts_openspec_propose_skill_invocations() -> None:
    counts = _scan_ledger_for_pipeline_elements([
        {"tool": "Skill", "tool_input": {"skill": "openspec-propose"}},
        {"tool": "Skill", "tool_input": {"skill": "opsx:propose"}},
    ])
    assert counts["openspec_propose_skill_invocations"] == 2


def test_scan_ledger_counts_openspec_change_artifacts() -> None:
    counts = _scan_ledger_for_pipeline_elements([
        {"tool": "Write", "tool_input": {"file_path": "/repo/openspec/changes/c/proposal.md"}},
        {"tool": "Edit", "tool_input": {"file_path": "C:\\repo\\openspec\\changes\\c\\tasks.md"}},
    ])
    assert counts["openspec_change_artifacts"] == 2


# ---- severity 5: pipeline-confession-language-detected ----


def test_severity_confession_fires_on_bypass_admission() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="plain task description",
        toolcall_ledger=[],
        final_report="No — I bypassed all of that and built it solo.",
    )
    assert v["valid"] is False
    assert any(g["severity"] == "pipeline-confession-language-detected" for g in v["gaps"])


def test_severity_confession_fires_on_overrode_admission() -> None:
    v = verify_no_pipeline_bypass(
        final_report="I overrode your explicit choice to use the pipeline.",
    )
    assert any(g["severity"] == "pipeline-confession-language-detected" for g in v["gaps"])


def test_severity_confession_fires_on_no_subagents() -> None:
    v = verify_no_pipeline_bypass(
        final_report="The work was done with no subagents, no independent review, no OpenSpec, no worktree.",
    )
    assert any(g["severity"] == "pipeline-confession-language-detected" for g in v["gaps"])


def test_severity_confession_does_not_fire_on_clean_report() -> None:
    v = verify_no_pipeline_bypass(
        final_report="Spec my-change has been implemented. All tests passing.",
    )
    assert v["valid"] is True


# ---- backwards-compat: pipeline not invoked + no confession ----


def test_no_op_when_pipeline_not_invoked_and_no_confession() -> None:
    v = verify_no_pipeline_bypass(
        user_prompt="please add this feature",
        toolcall_ledger=[
            {"tool": "Edit", "tool_input": {"file_path": "/repo/src/x.ts"}},
        ],
        final_report="Done.",
    )
    assert v["valid"] is True
    assert v["pipeline_invoked"] is False


# ---- fixture round-trip ----


def test_canonical_fixture_bad_fires_4_severities() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    v = verify_no_pipeline_bypass(
        fx["user_prompt"], fx["toolcall_ledger"], fx["final_report"]
    )
    assert v["valid"] is False
    sevs = sorted({g["severity"] for g in v["gaps"]})
    expected = sorted(fx["_meta"]["expected_severities"])
    assert sevs == expected


def test_canonical_fixture_corrected_passes() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    v = verify_no_pipeline_bypass(
        fx["user_prompt"], fx["_corrected_ledger"], fx["_corrected_final_report"]
    )
    assert v["valid"] is True


# ---- output shape ----


def test_output_carries_tool_name() -> None:
    v = verify_no_pipeline_bypass()
    assert v["tool"] == "verify-no-pipeline-bypass"


def test_output_persists_to_out_path(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    verify_no_pipeline_bypass(out_path=str(out))
    assert out.exists()


# ---- determinism ----


def test_output_deterministic_on_stable_input() -> None:
    prompt = "/architect-team x"
    ledger = [{"tool": "Edit", "tool_input": {"file_path": "/repo/src/x.ts"}}]
    a = verify_no_pipeline_bypass(prompt, ledger)
    b = verify_no_pipeline_bypass(prompt, ledger)
    assert sorted((g["severity"] for g in a["gaps"])) == sorted((g["severity"] for g in b["gaps"]))
