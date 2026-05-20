"""v0.9.7 — editability-completeness discipline structural tests.

Reported gap: the design gets wired up, but not every attribute the frontend
exposes is actually editable end-to-end. An entity has a `title`, but there is
no field to set it when creating the thing — and no existing gate catches it
(playwright tests buttons that work; visual-fidelity tests how it looks).

v0.9.7 adds the `editability-completeness` skill: three editability-reviewer
agents (Opus) independently enumerate every attribute, classify which a user
should control, trace each end-to-end (UI -> state -> API -> request schema ->
handler -> database -> read-back), argue to a converged list, route gaps as
solution requirements, and re-review until satisfied.

These tests assert the discipline is present across the skill + agent +
command + wire-up so it cannot silently regress.
"""
from pathlib import Path

import pytest

SKILL = ("skills", "editability-completeness", "SKILL.md")
AGENT = ("agents", "editability-reviewer.md")
COMMAND = ("commands", "editability-audit.md")
PIPELINE_SKILL = ("skills", "architect-team-pipeline", "SKILL.md")
TEAM_SPAWN_SKILL = ("skills", "team-spawning-and-review-gates", "SKILL.md")
MEMPALACE_SKILL = ("skills", "mempalace-integration", "SKILL.md")

CLASSIFICATIONS = (
    "user-editable",
    "user-settable-at-create-only",
    "system-managed",
    "derived",
    "dynamic-via-action",
    "ambiguous",
)

TRACE_STAGES = (
    "create_control",
    "edit_control",
    "control_to_state",
    "state_to_request",
    "request_schema",
    "handler_to_db",
    "read_back",
)

GAP_KINDS = ("missing-control", "dead-control", "orphan-field", "no-readback", "schema-mismatch")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- skill exists + core structure -----------------------------------------

def test_skill_exists_and_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, SKILL).strip(), "editability-completeness SKILL.md is empty"


@pytest.mark.parametrize("classification", CLASSIFICATIONS)
def test_skill_defines_every_classification(plugin_root: Path, classification: str) -> None:
    """The editability classification rubric must name all six categories."""
    content = _read(plugin_root, SKILL)
    assert classification in content, (
        f"editability-completeness SKILL.md missing classification {classification!r}"
    )


@pytest.mark.parametrize("stage", TRACE_STAGES)
def test_skill_defines_every_trace_stage(plugin_root: Path, stage: str) -> None:
    """The end-to-end trace must enumerate all seven stages UI->DB->read-back."""
    content = _read(plugin_root, SKILL)
    assert stage in content, (
        f"editability-completeness SKILL.md missing trace stage {stage!r}"
    )


@pytest.mark.parametrize("gap_kind", GAP_KINDS)
def test_skill_defines_every_gap_kind(plugin_root: Path, gap_kind: str) -> None:
    content = _read(plugin_root, SKILL)
    assert gap_kind in content, (
        f"editability-completeness SKILL.md missing gap kind {gap_kind!r}"
    )


def test_skill_mandates_three_reviewers(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL).lower()
    assert "three" in content and "editability-reviewer" in content, (
        "editability-completeness SKILL.md does not establish the three-reviewer team"
    )


def test_skill_has_argue_to_convergence_round(plugin_root: Path) -> None:
    """The user explicitly wants the three to ARGUE until they have a clear list."""
    content = _read(plugin_root, SKILL)
    assert "argue to convergence" in content.lower(), (
        "editability-completeness SKILL.md does not document the argue-to-convergence round"
    )


def test_skill_is_multi_pass_and_bounded(plugin_root: Path) -> None:
    """The user wants it to 'do it again until satisfied' — a bounded multi-pass loop."""
    content = _read(plugin_root, SKILL)
    assert "multi-pass" in content.lower(), "skill does not document the multi-pass loop"
    assert "satisfied" in content, "skill does not define the satisfied exit condition"
    assert "3 passes" in content or "three passes" in content.lower(), (
        "skill does not bound the multi-pass loop"
    )


def test_skill_reviewers_are_analysis_only(plugin_root: Path) -> None:
    """Reviewers must not write feature code — gaps go through the fix loop."""
    content = _read(plugin_root, SKILL)
    assert "analysis-only" in content.lower(), (
        "editability-completeness SKILL.md does not establish reviewers as analysis-only"
    )


def test_skill_escalates_ambiguous_attributes(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "escalat" in content.lower() and "ambiguous" in content.lower(), (
        "skill does not require ambiguous attributes to be escalated to the human"
    )


def test_skill_has_worked_example_of_the_title_gap(plugin_root: Path) -> None:
    """The user's canonical example — a title with no field to set it — must appear."""
    content = _read(plugin_root, SKILL).lower()
    assert "title" in content, "skill does not use the title attribute as the worked example"


# --- agent ------------------------------------------------------------------

def test_agent_exists_and_is_opus(plugin_root: Path) -> None:
    """The user explicitly asked for an Opus AI to do this review."""
    content = _read(plugin_root, AGENT)
    assert "model: opus" in content, "editability-reviewer must run on the opus model"


def test_agent_is_read_only_on_source(plugin_root: Path) -> None:
    content = _read(plugin_root, AGENT)
    assert "Read-only on source" in content or "read-only on source" in content.lower(), (
        "editability-reviewer does not establish read-only-on-source posture"
    )
    assert "Edit" not in content.split("tools:")[1].split("\n")[0], (
        "editability-reviewer must not have the Edit tool"
    )


def test_agent_forbids_round_1_consultation(plugin_root: Path) -> None:
    content = _read(plugin_root, AGENT)
    assert "independent" in content.lower(), (
        "editability-reviewer does not enforce Round 1 independence"
    )


# --- command ----------------------------------------------------------------

def test_command_exists(plugin_root: Path) -> None:
    assert _read(plugin_root, COMMAND).strip(), "editability-audit command is empty"


def test_command_invokes_the_skill(plugin_root: Path) -> None:
    content = _read(plugin_root, COMMAND)
    assert "editability-completeness" in content, (
        "editability-audit command does not invoke the editability-completeness skill"
    )


# --- pipeline + team-spawning wire-up ---------------------------------------

def test_pipeline_phase_5_runs_editability_review(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL)
    assert "editability-completeness" in content, (
        "pipeline does not invoke editability-completeness in Phase 5"
    )


def test_pipeline_phase_7_confirms_editability_satisfied(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL)
    assert "editability-completeness" in content and "satisfied" in content, (
        "pipeline Phase 7 does not confirm the editability team reached satisfied"
    )


def test_team_spawning_has_editability_gap_origin(plugin_root: Path) -> None:
    content = _read(plugin_root, TEAM_SPAWN_SKILL)
    assert "editability-gap" in content, (
        "team-spawning SR origin.kind enum does not include editability-gap"
    )


def test_editability_gap_does_not_route_through_diagnostic_research(plugin_root: Path) -> None:
    """The converged map IS the diagnosis — editability-gap SRs spawn fix teams directly."""
    content = _read(plugin_root, TEAM_SPAWN_SKILL)
    assert "editability-gap` SRs spawn a fix team DIRECTLY" in content or (
        "editability-gap" in content and "do NOT route through" in content
    ), "team-spawning does not state editability-gap SRs bypass diagnostic-research-team"


def test_mempalace_has_editability_maps_room(plugin_root: Path) -> None:
    content = _read(plugin_root, MEMPALACE_SKILL)
    assert "editability-maps" in content, (
        "mempalace-integration canonical room table does not include editability-maps"
    )
