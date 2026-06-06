"""v2.5.0 structural tests — assert the in-flight clarification discipline
is wired in common-pipeline-conventions and cross-referenced in the 3
pipeline-driving SKILL.md bodies + the 3 pipeline-driving slash command
bodies.

The discipline: when a pipeline is in-flight (Phase −2 → 8 / B−1 → B8 /
M0 → M7 executing) AND the user injects a message that does NOT explicitly
invoke /architect-team or cancel the run, the orchestrator MUST fold the
message into the in-flight pipeline's brief — NOT spawn a separate
workflow outside the pipeline.

Symmetric counterpart to v2.0.0 Layer 6 (skill_invocation_audit): the
inverse direction of "the agent should not operate outside the framework."
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ===========================================================================
# Canonical section in common-pipeline-conventions
# ===========================================================================


def test_canonical_section_exists(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "## In-flight clarification discipline (v2.5.0)" in body


def test_canonical_section_appears_once(plugin_root: Path):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert body.count("## In-flight clarification discipline (v2.5.0)") == 1


# ===========================================================================
# 3 detection signals are named
# ===========================================================================


@pytest.mark.parametrize("detection_signal", [
    "intake-state.json",
    "escalation-pending.md",
    "teammates/",
])
def test_canonical_section_names_detection_signals(plugin_root: Path, detection_signal: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert detection_signal in body, f"Detection signal {detection_signal!r} missing"


def test_canonical_section_documents_in_flight_meaning(plugin_root: Path):
    """The section must explain what 'in-flight' means in terms of state checks."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    # The section must reference at least 2 of these state-check concepts
    state_markers = ["phase", "in_progress", "completed_at", "unresolved"]
    hits = sum(1 for m in state_markers if m in body_lower)
    assert hits >= 2, f"section should reference state-check concepts; found {hits}"


# ===========================================================================
# 4 forbidden anti-patterns are named
# ===========================================================================


@pytest.mark.parametrize("anti_pattern_name", [
    "solve-with-tools-directly",
    "answer-conversationally",
    "spawn-sibling-invocation",
    "silently-ignore",
])
def test_canonical_section_names_forbidden_anti_patterns(plugin_root: Path, anti_pattern_name: str):
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert anti_pattern_name in body, f"Anti-pattern name {anti_pattern_name!r} missing"


def test_canonical_section_forbids_solving_outside_pipeline(plugin_root: Path):
    """The section must explicitly forbid operating outside the pipeline."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    # At least one of these phrases must appear
    assert any(p in body_lower for p in [
        "outside the pipeline",
        "outside the framework",
        "bypass the pipeline",
        "bypasses",
    ]), "section must explicitly forbid bypassing the pipeline"


# ===========================================================================
# Cancellation channel
# ===========================================================================


@pytest.mark.parametrize("cancel_phrase", [
    "cancel",
    "stop",
    "abort",
])
def test_canonical_section_names_cancellation_phrases(plugin_root: Path, cancel_phrase: str):
    """The cancellation channel must name at least 3 canonical cancel phrases."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert cancel_phrase in body_lower


def test_canonical_section_documents_default_leans_to_fold(plugin_root: Path):
    """The default must lean toward 'fold into pipeline', not toward cancel."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    body_lower = body.lower()
    # The section must explicitly state the default leans toward fold
    assert "lean" in body_lower or "default" in body_lower
    assert "fold" in body_lower


# ===========================================================================
# Clarifications log path
# ===========================================================================


def test_canonical_section_names_clarifications_log_path(plugin_root: Path):
    """The per-run clarifications log path is documented."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert ".architect-team/clarifications/" in body


# ===========================================================================
# Cross-references in 3 pipeline SKILL.md bodies
# ===========================================================================


@pytest.mark.parametrize("pipeline_skill", [
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
])
def test_pipeline_body_references_canonical_section(plugin_root: Path, pipeline_skill: str):
    """Each of the 3 pipeline-driving SKILL.md bodies must reference the new
    canonical section."""
    skill = plugin_root / "skills" / pipeline_skill / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "In-flight clarification" in body, (
        f"{pipeline_skill} must reference the v2.5.0 canonical section"
    )


@pytest.mark.parametrize("pipeline_skill", [
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
])
def test_pipeline_body_marks_v2_5_0(plugin_root: Path, pipeline_skill: str):
    """Each pipeline body's reference must carry the v2.5.0 marker."""
    skill = plugin_root / "skills" / pipeline_skill / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    # The cross-reference paragraph mentions v2.5.0 explicitly
    assert "v2.5.0" in body or "2.5.0" in body, (
        f"{pipeline_skill} v2.5.0 marker missing in cross-reference"
    )


# ===========================================================================
# Cross-references in 3 pipeline-driving slash command bodies
# ===========================================================================


@pytest.mark.parametrize("command_name", [
    "architect-team",
    "bug-fix",
    "mini",
])
def test_command_body_references_canonical_section(plugin_root: Path, command_name: str):
    """Each pipeline-driving slash command body must reference the canonical
    section so the discipline is in scope from the moment the user invokes."""
    command = plugin_root / "commands" / f"{command_name}.md"
    body = command.read_text(encoding="utf-8")
    assert "In-flight clarification" in body, (
        f"commands/{command_name}.md must reference the v2.5.0 canonical section"
    )


@pytest.mark.parametrize("command_name", [
    "architect-team",
    "bug-fix",
    "mini",
])
def test_command_body_names_forbidden_anti_patterns(plugin_root: Path, command_name: str):
    """Each command body must explicitly forbid bypass behaviors so the
    orchestrator can't claim the rule isn't in scope at invocation time."""
    command = plugin_root / "commands" / f"{command_name}.md"
    body = command.read_text(encoding="utf-8")
    body_lower = body.lower()
    # At least one forbidden phrase must appear
    assert any(p in body_lower for p in [
        "forbidden",
        "must not",
        "bypass",
    ])


# ===========================================================================
# Symmetry with v2.0.0 Layer 6
# ===========================================================================


def test_canonical_section_cites_symmetry_with_layer_6(plugin_root: Path):
    """The new discipline references its symmetry with v2.0.0 Layer 6
    (skill_invocation_audit)."""
    skill = plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    # Find the v2.5.0 section text — it should mention Layer 6 OR skill_invocation_audit
    body_lower = body.lower()
    assert ("layer 6" in body_lower) or ("skill_invocation_audit" in body_lower)


# ===========================================================================
# Coverage-map JSON consistency
# ===========================================================================


def _find_change_or_archive_dir(plugin_root: Path) -> Path:
    direct = plugin_root / "openspec" / "changes" / "in-flight-clarification-discipline"
    if direct.is_dir():
        return direct
    archive = plugin_root / "openspec" / "changes" / "archive"
    if archive.is_dir():
        matches = list(archive.glob("*-in-flight-clarification-discipline"))
        if matches:
            return matches[0]
    raise AssertionError("in-flight-clarification-discipline change folder not found")


def test_openspec_change_or_archive_exists(plugin_root: Path):
    change = _find_change_or_archive_dir(plugin_root)
    for required in ("proposal.md", "design.md", "tasks.md", "coverage-map.json"):
        assert (change / required).exists(), f"missing artifact: {required}"


def test_proposal_documents_failure_shape(plugin_root: Path):
    proposal = _find_change_or_archive_dir(plugin_root) / "proposal.md"
    body = proposal.read_text(encoding="utf-8")
    # The failure shape (verbatim user transcript) must be in the proposal
    assert "CSV export" in body or "wait, also" in body, (
        "proposal must include the concrete failure shape example"
    )


def test_coverage_map_has_all_requirements(plugin_root: Path):
    import json
    cmap = json.loads(
        (_find_change_or_archive_dir(plugin_root) / "coverage-map.json").read_text(encoding="utf-8")
    )
    req_ids = {r["id"] for r in cmap["requirements"]}
    assert len(req_ids) >= 5
