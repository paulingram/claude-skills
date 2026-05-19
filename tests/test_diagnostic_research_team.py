"""v0.9.3 — Test-failure SR triage discipline.

When a failing test escalates back to the orchestrator via a solution
requirement with a test-failure origin, the orchestrator MUST invoke the
`diagnostic-research-team` skill BEFORE spawning the Phase 2 fix team. The
skill spawns three `diagnostic-researcher` agents in parallel, has the
`system-architect` agent review their drafts for robustness, and produces a
consolidated diagnostic plan that becomes a required input to the fix-team
brief. The fix team's first work item is the pre-fix verification checklist
in the plan; it cannot propose a fix until that checklist is complete.

These tests assert the contract is documented across the canonical docs so
the wire-up cannot silently regress.
"""
from pathlib import Path

import pytest

SKILL_PATH = ("skills", "diagnostic-research-team", "SKILL.md")
AGENT_PATH = ("agents", "diagnostic-researcher.md")
ARCHITECT_AGENT_PATH = ("agents", "system-architect.md")
PIPELINE_SKILL_PATH = ("skills", "architect-team-pipeline", "SKILL.md")
RCA_SKILL_PATH = ("skills", "root-cause-test-failures", "SKILL.md")

TEST_FAILURE_ORIGINS = (
    "rca-product-bug",
    "playwright-failure",
    "integration-failure",
    "test-completeness-failure",
    "visual-fidelity-cascade",
)


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def test_diagnostic_research_team_skill_exists(plugin_root: Path) -> None:
    """The skill file must exist and have a non-empty body."""
    content = _read(plugin_root, SKILL_PATH)
    assert content.strip(), "diagnostic-research-team SKILL.md is empty"


def test_diagnostic_researcher_agent_exists(plugin_root: Path) -> None:
    """The agent file must exist and have a non-empty body."""
    content = _read(plugin_root, AGENT_PATH)
    assert content.strip(), "diagnostic-researcher agent file is empty"


@pytest.mark.parametrize("origin_kind", TEST_FAILURE_ORIGINS)
def test_skill_names_every_test_failure_origin(plugin_root: Path, origin_kind: str) -> None:
    """The skill must explicitly name every test-failure origin.kind value
    so the orchestrator knows when to invoke it vs. when to skip."""
    content = _read(plugin_root, SKILL_PATH)
    assert origin_kind in content, (
        f"diagnostic-research-team SKILL.md does not name origin.kind {origin_kind!r}"
    )


def test_skill_mandates_three_researchers(plugin_root: Path) -> None:
    """Three parallel researchers is the contract — not two, not four."""
    content = _read(plugin_root, SKILL_PATH)
    # Phrasing varies; we accept either canonical reference.
    assert ("three diagnostic-researcher" in content.lower()
            or "three researchers" in content.lower()
            or "spawn three" in content.lower()), (
        "diagnostic-research-team SKILL.md does not establish the three-researcher contract"
    )


def test_skill_requires_architect_review(plugin_root: Path) -> None:
    """The system-architect review step is the gate between researchers and fix team."""
    content = _read(plugin_root, SKILL_PATH)
    assert "system-architect" in content, (
        "diagnostic-research-team SKILL.md does not reference the system-architect agent"
    )
    assert "robustness" in content.lower(), (
        "diagnostic-research-team SKILL.md does not describe the robustness review"
    )


def test_pipeline_phase_3b_invokes_skill(plugin_root: Path) -> None:
    """Phase 3b of the pipeline must invoke diagnostic-research-team before
    fix-team spawn for test-failure SRs."""
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "diagnostic-research-team" in content, (
        "Phase 3b does not invoke the diagnostic-research-team skill"
    )
    assert "diagnostic_plan_path" in content, (
        "Phase 3b does not gate fix-team spawn on diagnostic_plan_path"
    )


def test_pipeline_blocks_fix_team_without_plan(plugin_root: Path) -> None:
    """The wire-up must say the fix team cannot be spawned without the plan."""
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    # Look for the explicit blocking language. Phrasing is flexible but the
    # contract must be present.
    assert "CANNOT be spawned" in content or "cannot be spawned" in content, (
        "Phase 3b does not block fix-team spawn pending diagnostic plan"
    )


def test_architect_agent_documents_review_mode(plugin_root: Path) -> None:
    """system-architect must document the diagnostic-plan-review responsibility."""
    content = _read(plugin_root, ARCHITECT_AGENT_PATH)
    assert "Diagnostic Plan Review" in content or "diagnostic plan review" in content.lower(), (
        "system-architect agent does not document Diagnostic Plan Review mode"
    )
    assert "robustness rubric" in content.lower() or "robustness" in content.lower(), (
        "system-architect agent does not describe the robustness rubric"
    )


def test_rca_skill_references_new_skill(plugin_root: Path) -> None:
    """root-cause-test-failures Phase C must point at diagnostic-research-team
    so teammates know what happens to their RCA after they signal idle."""
    content = _read(plugin_root, RCA_SKILL_PATH)
    assert "diagnostic-research-team" in content, (
        "root-cause-test-failures does not reference diagnostic-research-team in Phase C"
    )


def test_researcher_agent_is_read_only_on_source(plugin_root: Path) -> None:
    """The researcher agent body must explicitly say it is read-only on source code."""
    content = _read(plugin_root, AGENT_PATH)
    assert "Read-only on source" in content or "read-only on source" in content.lower(), (
        "diagnostic-researcher agent does not establish read-only-on-source posture"
    )


def test_researcher_agent_forbids_consulting_other_researchers(plugin_root: Path) -> None:
    """Parallel independence is the core mechanism — agent must enforce it."""
    content = _read(plugin_root, AGENT_PATH)
    assert "No consulting" in content or "no consulting" in content.lower(), (
        "diagnostic-researcher agent does not forbid consulting between researchers"
    )
