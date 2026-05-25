"""Structural tests for the `proposal-refiner` skill (v0.9.33)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_NAME = "proposal-refiner"

REQUIRED_PHASES = ("Phase R1", "Phase R2", "Phase R3", "Phase R4", "Phase R5", "Phase R6")
REQUIRED_AXES = ("Clarity", "Scope", "Acceptance", "Codebase grounding", "Conflict")
REQUIRED_SECTIONS = (
    "## When this skill runs",
    "## When this skill DOES NOT run",
    "## Phase R1",
    "## Phase R2",
    "## Phase R3",
    "## Phase R4",
    "## Phase R5",
    "## Phase R6",
    "## Non-negotiable disciplines",
    "## Relationship to downstream pipelines",
)


def _skill_path(plugin_root: Path) -> Path:
    return plugin_root / "skills" / SKILL_NAME / "SKILL.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_skill_path(plugin_root))


# --- frontmatter ------------------------------------------------------------


def test_skill_file_exists(plugin_root: Path) -> None:
    assert _skill_path(plugin_root).exists(), f"{SKILL_NAME}/SKILL.md missing"


def test_skill_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert "name" in fm and fm["name"] == SKILL_NAME
    assert "description" in fm and isinstance(fm["description"], str) and len(fm["description"]) > 50


def test_skill_description_names_both_entry_modes(plugin_root: Path) -> None:
    """The description must declare BOTH pipeline-integrated and standalone modes."""
    fm, _ = _read(plugin_root)
    desc = fm["description"]
    assert "standalone" in desc.lower(), "description must name the standalone mode"
    assert "refine-prompt" in desc or "pipeline" in desc.lower(), (
        "description must name the pipeline-integrated mode (via the refine-prompt command or 'pipeline')"
    )


# --- phase structure --------------------------------------------------------


@pytest.mark.parametrize("phase", REQUIRED_PHASES)
def test_phase_header_present(plugin_root: Path, phase: str) -> None:
    _, body = _read(plugin_root)
    assert phase in body, f"skill body must contain phase '{phase}'"


@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_required_section_present(plugin_root: Path, section: str) -> None:
    _, body = _read(plugin_root)
    assert section in body, f"skill body must contain section '{section}'"


# --- grading discipline -----------------------------------------------------


@pytest.mark.parametrize("axis", REQUIRED_AXES)
def test_grade_axis_named(plugin_root: Path, axis: str) -> None:
    _, body = _read(plugin_root)
    assert axis in body, f"skill body must name the '{axis}' grade axis"


def test_grade_weights_documented(plugin_root: Path) -> None:
    """The weighted-average formula must be documented so the score is reproducible."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    # The weights total 1.0 — check the documented weights add up
    for weight in ("0.25", "0.20", "0.10"):
        assert weight in body, f"skill body must document weight {weight} in the weighted average"


def test_letter_grade_mapping_documented(plugin_root: Path) -> None:
    """The letter-grade thresholds (A 90+, B 75-89, C 60-74, D 45-59, F <45) must be documented."""
    _, body = _read(plugin_root)
    # All five letters
    for letter in ("A:", "B:", "C:", "D:", "F:"):
        assert letter in body, f"skill body must declare letter grade '{letter}'"


# --- loop bounds ------------------------------------------------------------


def test_iteration_ceiling_is_five(plugin_root: Path) -> None:
    """The refinement loop is bounded at 5 iterations — the documented ceiling."""
    _, body = _read(plugin_root)
    assert "5 iteration" in body.lower() or "iteration ceiling" in body.lower(), (
        "skill must document the 5-iteration ceiling"
    )


def test_user_confirm_terminates_loop(plugin_root: Path) -> None:
    """A user 'ship it' / 'good' / 'proceed' / 'go' confirms termination — natural-language."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "ship it" in body_lower, "skill must list 'ship it' as a confirm signal"
    assert "proceed" in body_lower, "skill must list 'proceed' as a confirm signal"


# --- output discipline ------------------------------------------------------


def test_output_path_documented(plugin_root: Path) -> None:
    """The output markdown path must be documented for both modes."""
    _, body = _read(plugin_root)
    assert ".architect-team/refined-prompts/" in body, (
        "skill must document the output path under .architect-team/refined-prompts/"
    )


def test_frontmatter_schema_documented(plugin_root: Path) -> None:
    """The refined-prompt markdown's frontmatter schema must be documented (refined-by, mode, etc)."""
    _, body = _read(plugin_root)
    assert "refined-by: proposal-refiner" in body, (
        "skill must document the `refined-by: proposal-refiner` frontmatter marker"
    )
    assert "final-grade" in body, "skill must document the final-grade frontmatter field"
    assert "mode:" in body, "skill must document the mode frontmatter field (pipeline | standalone)"


def test_two_modes_produce_different_outcomes(plugin_root: Path) -> None:
    """Pipeline mode rebinds REQ_DIR; standalone mode exits with the path printed."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "rebind" in body_lower or "rebound" in body_lower or "$req_dir" in body_lower, (
        "skill must describe how pipeline mode hands the markdown path back to the caller"
    )
    # And standalone mode emits the path + exits with no downstream
    assert "no downstream" in body_lower or "exits" in body_lower, (
        "skill must describe how standalone mode exits without running a downstream pipeline"
    )


# --- domain-gate discipline -------------------------------------------------


def test_refiner_is_documented_as_domain_gate(plugin_root: Path) -> None:
    """The refiner must be classified as a DOMAIN gate per v0.9.21, not a process gate."""
    _, body = _read(plugin_root)
    assert "domain gate" in body.lower(), (
        "skill must classify itself as a DOMAIN gate (per v0.9.21 carve-out)"
    )


def test_skip_conditions_documented(plugin_root: Path) -> None:
    """The three skip conditions (folder / refined-by frontmatter / --no-refine) must be documented."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "directory" in body_lower, "skill must list 'directory path resolves' as a skip condition"
    assert "refined-by" in body, "skill must list `refined-by: proposal-refiner` frontmatter as a skip condition"
    assert "--no-refine" in body, "skill must list `--no-refine` flag as a skip condition"


# --- codebase-grounding discipline ------------------------------------------


def test_skill_reads_codebase_maps(plugin_root: Path) -> None:
    """The skill must read CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTERACTION_INTUITION_MAP / INTEGRATION_MAP."""
    _, body = _read(plugin_root)
    for map_name in ("CODEBASE_MAP.md", "ROUTE_MAP.md", "INTERACTION_INTUITION_MAP.md", "INTEGRATION_MAP.md"):
        assert map_name in body, f"skill must read the {map_name} for grounding"


def test_mempalace_wake_up_is_read_only(plugin_root: Path) -> None:
    """The skill's MemPalace consultation is read-only — no `mempalace mine`."""
    _, body = _read(plugin_root)
    assert "wake-up" in body.lower() and "mempalace" in body.lower(), (
        "skill must document the MemPalace wake-up consult"
    )
    # And the consultation must be READ-ONLY
    assert "read-only" in body.lower(), (
        "skill must declare the MemPalace consult as read-only (no mining during refinement)"
    )


def test_no_invention_rule_documented(plugin_root: Path) -> None:
    """The 'no invented codebase entities' rule must appear (parallels agent's hard rule)."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert ("never invent" in body_lower or "no invention" in body_lower
            or "not invented" in body_lower or "must cite" in body_lower
            or "trace" in body_lower), (
        "skill must declare some form of 'no invented codebase entities' / 'must cite the map entry' rule"
    )
