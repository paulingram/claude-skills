"""Structural tests for the mini-architect-team-pipeline skill (v0.10.0).

The skill is a sibling to architect-team-pipeline and bug-fix-pipeline —
faster, smaller surface area, single architect, single QA. Nine phases
M0–M8 with a tight architect → parallel-dev → QA → verdict loop and
auto-merge to main on green.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_NAME = "mini-architect-team-pipeline"

REQUIRED_PHASE_HEADERS = (
    "## Phase M0",
    "## Phase M1",
    "## Phase M2",
    "## Phase M3",
    "## Phase M4",
    "## Phase M5",
    "## Phase M6",
    "## Phase M7",
    "## Phase M8",
)


def _path(plugin_root: Path) -> Path:
    return plugin_root / "skills" / SKILL_NAME / "SKILL.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_path(plugin_root))


def test_skill_file_exists(plugin_root: Path) -> None:
    assert _path(plugin_root).exists()


def test_skill_frontmatter_valid(plugin_root: Path) -> None:
    fm, body = _read(plugin_root)
    assert fm["name"] == SKILL_NAME
    assert isinstance(fm["description"], str) and len(fm["description"]) > 100
    assert body.strip()


@pytest.mark.parametrize("phase_header", REQUIRED_PHASE_HEADERS)
def test_phase_header_present(plugin_root: Path, phase_header: str) -> None:
    _, body = _read(plugin_root)
    assert phase_header in body, f"missing phase header: {phase_header}"


def test_skill_documents_unbounded_handoff(plugin_root: Path) -> None:
    """v3.8.0: there is NO give-up cycle cap. When the same proposal keeps
    landing red (recurrence), the mini run HANDS OFF to the full unbounded
    /architect-team pipeline on the same branch — a continuation of solving,
    not a stop. The skill references the canonical Unbounded solving discipline."""
    _, body = _read(plugin_root)
    low = body.lower()
    assert "unbounded solving" in low, (
        "skill must reference the canonical Unbounded solving discipline"
    )
    assert "no iteration ceiling" in low or "no give-up cap" in low, (
        "skill must state there is no iteration ceiling / give-up cap"
    )
    assert "recurrence" in low, (
        "skill must frame the red-cycle trigger as recurrence (a signal to hand off)"
    )
    assert "hand off" in low or "hands off" in low or "hand-off" in low, (
        "skill must describe handing off to the full pipeline (a continuation, not a stop)"
    )
    # The old give-up framing must be gone.
    assert "cycle cap = 3" not in low and "escalate on cycle 4" not in low, (
        "the old 'cycle cap = 3 / escalate on cycle 4' give-up framing must be removed"
    )


def test_skill_documents_ac_cap(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "5 Acceptance Criteria" in body or "5 ACs" in body or "at most 5" in body, (
        "skill must document the ≤5 AC cap"
    )


def test_skill_documents_playwright_cap(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "3 Playwright" in body or "at most 3" in body, (
        "skill must document the ≤3 Playwright flow cap"
    )


def test_skill_documents_self_confirm_pass_cap(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "3 self-confirm" in body or "3 passes" in body, (
        "skill must document the cap of 3 M3 self-confirm passes"
    )


def test_skill_references_downstream_skills(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    for downstream in (
        "intake-and-mapping",
        "mempalace-integration",
        "dev-api-integration-testing",
        "playwright-user-flows",
        "coverage-mapping",
        "documentation-currency",
        "team-spawning-and-review-gates",
    ):
        assert downstream in body, f"skill must reference downstream skill: {downstream}"


def test_skill_names_qa_guidance_contract(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "## QA Guidance" in body, "skill must reference the ## QA Guidance contract by name"


def test_skill_names_mini_run_trailer(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "Mini-Run:" in body, "skill must reference the Mini-Run: commit trailer convention"


def test_skill_names_escalation_target(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "/architect-team" in body and "escalat" in body.lower(), (
        "skill must document escalation to /architect-team on cycle 4"
    )


def test_skill_names_auto_merge_to_main(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "merge" in body.lower() and "main" in body.lower(), (
        "skill must document auto-merge to main on green"
    )


def test_skill_names_no_merge_flag(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "--no-merge" in body, "skill must document the --no-merge opt-out flag"


def test_same_input_forms_guarantee(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "requirements folder" in body.lower(), "skill must name the folder input form"
    assert "plain-language" in body.lower(), "skill must name the plain-language input form"
    assert "first-class" in body.lower(), "skill must state both forms are first-class"


def test_skill_forbids_refusing_prose(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "never refuse" in body.lower() or "do NOT refuse" in body or "Never refuse" in body, (
        "skill must explicitly forbid refusing plain-language prose"
    )


def test_skill_documents_dev_cross_checks_dev(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "cross-check" in body.lower() or "cross-review" in body.lower(), (
        "skill must document the backend↔frontend cross-review pattern (no task-reviewer agent)"
    )
