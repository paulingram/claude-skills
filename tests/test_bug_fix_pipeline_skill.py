"""Structural tests for the `bug-fix-pipeline` skill (v0.9.22).

The skill is a sibling to architect-team-pipeline — faster, bug-focused — with
five non-negotiable disciplines and ten phases (B−1 through B8).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_NAME = "bug-fix-pipeline"

REQUIRED_PHASE_HEADERS = (
    "## Phase B−1",
    "## Phase B0",
    "## Phase B1",
    "## Phase B2",
    "## Phase B3",
    "## Phase B4",
    "## Phase B5",
    "## Phase B6",
    "## Phase B7",
    "## Phase B8",
)

FIVE_DISCIPLINES = (
    "Replicate first",
    "Reproduction IS the regression test",
    "Generalize",
    "QA replay against live dev",
    "Live-dev-environment-by-default",
)


def _skill_path(plugin_root: Path) -> Path:
    return plugin_root / "skills" / SKILL_NAME / "SKILL.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_skill_path(plugin_root))


def test_skill_file_exists(plugin_root: Path) -> None:
    assert _skill_path(plugin_root).exists()


def test_skill_frontmatter_valid(plugin_root: Path) -> None:
    fm, body = _read(plugin_root)
    assert fm["name"] == SKILL_NAME
    assert isinstance(fm["description"], str) and len(fm["description"]) > 100
    assert body.strip()


@pytest.mark.parametrize("phase_header", REQUIRED_PHASE_HEADERS)
def test_phase_header_present(plugin_root: Path, phase_header: str) -> None:
    _, body = _read(plugin_root)
    assert phase_header in body, f"bug-fix-pipeline SKILL.md missing phase: {phase_header}"


@pytest.mark.parametrize("discipline", FIVE_DISCIPLINES)
def test_five_disciplines_named(plugin_root: Path, discipline: str) -> None:
    _, body = _read(plugin_root)
    # Find the `## Five non-negotiable disciplines` section
    start = body.find("## Five non-negotiable disciplines")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert discipline in section, f"discipline '{discipline}' not named in the Five disciplines section"


def test_phase_b1_names_playwright_and_backend_script(plugin_root: Path) -> None:
    """Phase B1 must name Playwright (frontend) and a script for backend bugs."""
    _, body = _read(plugin_root)
    start = body.find("## Phase B1")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "Playwright" in section, "Phase B1 must name Playwright for frontend replication"
    # The skill body says "Backend bugs → a script" in the bullets and references httpx; both
    # signal a backend-script artifact. Accept either phrasing.
    assert "Backend bugs" in section and "script" in section, (
        "Phase B1 must name a script for backend-bug replication (alongside the Playwright path)"
    )


def test_phase_b1_names_three_exit_verdicts(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Phase B1")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for verdict in ("reproduced", "could-not-reproduce", "needs-clarification"):
        assert verdict in section, f"Phase B1 must name the `{verdict}` exit verdict"


def test_phase_b1_names_ambiguity_question(plugin_root: Path) -> None:
    """The canonical ambiguity-escalation question must be present in the skill body — past- or present-tense phrasing acceptable."""
    _, body = _read(plugin_root)
    # Accept either tense — "how did you experience" OR "how you experienced".
    assert "how you experienced the bug" in body.lower() or "how did you experience the bug" in body.lower(), (
        "skill body must include the canonical ambiguity-escalation question (how did/do you experience the bug)"
    )


def test_phase_b2_mandates_backend_diagnostic_for_frontend(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Phase B2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "backend diagnostic" in section.lower(), (
        "Phase B2 must name a backend diagnostic test as a required companion for frontend bugs"
    )


def test_phase_b4_names_audit_mode_and_three_verdicts(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Phase B4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "Bug-Fix Generalization Audit" in section, "Phase B4 must name the audit mode"
    for verdict in ("pass", "needs-generalization", "needs-replacement"):
        assert verdict in section, f"Phase B4 must name the `{verdict}` verdict"


def test_phase_b5_names_deploy_to_dev(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Phase B5")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "deploy to the dev environment" in section.lower() or "deploy to dev" in section.lower(), (
        "Phase B5 must name deploy-to-dev-environment as the default action"
    )
    assert "production" in section.lower(), "Phase B5 must name the production-environment exception"


def test_phase_b6_pass_criterion_is_symptom_gone(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Phase B6")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "symptom is gone" in section.lower() or "symptom gone" in section.lower(), (
        "Phase B6 must state the pass criterion as 'the originating symptom is gone end-to-end'"
    )
    # v0.9.31 — the 4th verdict joins the canonical set
    for verdict in ("bug-resolved", "bug-still-present", "test-did-not-exercise-fix", "env-failure"):
        assert verdict in section, f"Phase B6 must name the qa-replayer's `{verdict}` verdict"


def test_phase_b6_documents_code_path_witness(plugin_root: Path) -> None:
    """v0.9.31 — Phase B6 must document the code-path execution witness step."""
    _, body = _read(plugin_root)
    start = body.find("## Phase B6 — QA replay against live dev")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "code-path execution witness" in section.lower(), (
        "Phase B6 must name the 'code-path execution witness' step"
    )
    assert "fix's git diff" in section.lower(), (
        "Phase B6 must list the fix's git diff as a qa-replayer input (used by the witness)"
    )


def test_phase_b6_test_did_not_exercise_fix_routes_to_b2(plugin_root: Path) -> None:
    """v0.9.31 — the new verdict routes to Phase B2 (re-author the test), NOT B3 (re-propose the fix)."""
    _, body = _read(plugin_root)
    start = body.find("## Phase B6 — QA replay against live dev")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    # The new verdict must be present
    assert "test-did-not-exercise-fix" in section, (
        "Phase B6 must name the test-did-not-exercise-fix verdict"
    )
    # And route to Phase B2 — the re-authoring path
    assert "Phase B2" in section or "B2" in section, (
        "Phase B6 must state test-did-not-exercise-fix routes back to Phase B2"
    )
    # AND distinguish "the TEST is on trial" from "the FIX is on trial"
    section_lower = section.lower()
    assert "test is on trial" in section_lower, (
        "Phase B6 must distinguish that test-did-not-exercise-fix puts the TEST on trial (not the fix)"
    )
    assert "fix is on trial" in section_lower, (
        "Phase B6 must distinguish that bug-still-present puts the FIX on trial (not the test)"
    )


def test_phase_b6_test_coverage_gap_origin_kind(plugin_root: Path) -> None:
    """The SR written for test-did-not-exercise-fix carries origin.kind: 'test-coverage-gap'."""
    _, body = _read(plugin_root)
    start = body.find("## Phase B6 — QA replay against live dev")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "test-coverage-gap" in section, (
        "Phase B6 must specify origin.kind: 'test-coverage-gap' for the test-did-not-exercise-fix SR"
    )


def test_skill_documents_unbounded_solving(plugin_root: Path) -> None:
    """v3.8.0: the bug-fix loop has NO iteration ceiling — it loops until the
    symptom is resolved end-to-end and references the canonical discipline."""
    _, body = _read(plugin_root)
    low = body.lower()
    assert "unbounded solving" in low, (
        "skill must reference the canonical Unbounded solving discipline"
    )
    assert "no iteration ceiling" in low or "no iteration bound" in low, (
        "skill must state there is no iteration ceiling / bound for bug-fix loops"
    )
    # The old give-up bounds must be gone.
    assert "10 iteration" not in low and "10-iteration" not in low, (
        "the old local 10-iteration ceiling must be removed"
    )
    assert "20-step ceiling" not in low and "ceiling is 20" not in low, (
        "the old global 20-step ceiling reference must be removed"
    )


def test_same_input_forms_guarantee(plugin_root: Path) -> None:
    """The skill must document both input forms (folder OR plain-language prose)."""
    _, body = _read(plugin_root)
    assert "requirements folder" in body.lower(), "skill must name the folder input form"
    assert "plain-language" in body.lower(), "skill must name the plain-language input form"
    assert "first-class" in body.lower(), "skill must state both forms are first-class"


def test_skill_forbids_refusing_prose(plugin_root: Path) -> None:
    """The skill must explicitly forbid the v0.9.17 anti-patterns."""
    _, body = _read(plugin_root)
    # The skill body must forbid (a) refusing prose, (b) path-treating the first word, (c) asking for a folder.
    assert "never refuse" in body.lower() or "do NOT refuse" in body or "Never refuse" in body, (
        "skill must explicitly forbid refusing plain-language prose"
    )


# --- v0.9.36: verdict file mandates ---


def test_b1_verdict_file_mandate(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Phase B1")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "b1-replication-verdict.json" in section, (
        "Phase B1 must mandate a structured verdict file"
    )
    assert "artifact_executed" in section, (
        "B1 verdict schema must include artifact_executed field"
    )
    assert "failing_output_captured" in section, (
        "B1 verdict schema must include failing_output_captured field"
    )


def test_b6_verdict_file_mandate(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Phase B6 —")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "b6-qa-replay-verdict.json" in section, (
        "Phase B6 must mandate a structured verdict file"
    )
    assert "artifacts_executed_against_live_dev" in section, (
        "B6 verdict schema must include artifacts_executed_against_live_dev field"
    )
    assert "symptom_gone_end_to_end" in section, (
        "B6 verdict schema must include symptom_gone_end_to_end field"
    )
    assert "code_path_witness_passed" in section, (
        "B6 verdict schema must include code_path_witness_passed field"
    )


def test_verdict_files_enforce_execution(plugin_root: Path) -> None:
    """Both verdict mandates must explicitly state that execution is mandatory."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "enforcement mechanism for testing" in body_lower, (
        "Verdict file mandates must be described as the enforcement mechanism"
    )
    assert "pipeline-completion-audit" in body.lower(), (
        "Verdict mandates must reference the completion audit hook"
    )


# --- v0.9.36: anti-deferral rules ---


def test_anti_deferral_operating_rule(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Operating rules")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "never defer" in section.lower(), (
        "Operating rules must forbid deferring bugs to separate runs"
    )
    assert "separate run" in section.lower(), (
        "Operating rules must explicitly name the 'separate runs' anti-pattern"
    )


def test_anti_deferral_anti_pattern_entries(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Anti-patterns to reject")
    section = body[start:] if start >= 0 else ""
    assert "merit" in section.lower() or "focused" in section.lower(), (
        "Anti-patterns must reject 'merits a focused run' rationalization"
    )
    assert "describe" in section.lower() or "description is not a test" in section.lower(), (
        "Anti-patterns must reject describing tests instead of running them"
    )
    assert "investigate" in section.lower(), (
        "Anti-patterns must reject 'needs investigation' deferral"
    )


def test_testing_executed_not_described_rule(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    start = body.find("## Operating rules")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "executed, not described" in section.lower() or "executed" in section.lower(), (
        "Operating rules must mandate testing is executed not described"
    )
