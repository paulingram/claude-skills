"""v0.9.4 — mempalace-integration skill + wire-up structural tests.

These tests assert that the integration skill exists, names the canonical
storage taxonomy, the auto-mine rules fire at every required phase of the
pipeline skill, and the three named subagents (system-architect,
diagnostic-researcher, route-mapper) document the search-before-output
discipline.
"""
from pathlib import Path

import pytest


SKILL_PATH = ("skills", "mempalace-integration", "SKILL.md")
PIPELINE_SKILL_PATH = ("skills", "architect-team-pipeline", "SKILL.md")
DIAGNOSTIC_RESEARCHER_PATH = ("agents", "diagnostic-researcher.md")
SYSTEM_ARCHITECT_PATH = ("agents", "system-architect.md")
ROUTE_MAPPER_PATH = ("agents", "route-mapper.md")

CANONICAL_ROOMS = (
    "codebase-maps",
    "route-maps",
    "integration-maps",
    "design-maps",
    "coverage-maps",
    "rca-artifacts",
    "diagnostic-plans",
    "solution-requirements",
    "handoffs",
    "architectural-decisions",
    "visual-fidelity-reports",
    "final-reports",
    "sessions",
)


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


@pytest.mark.parametrize("room", CANONICAL_ROOMS)
def test_skill_names_every_canonical_room(plugin_root: Path, room: str) -> None:
    """The integration skill must explicitly name every canonical room."""
    content = _read(plugin_root, SKILL_PATH)
    assert room in content, f"mempalace-integration SKILL.md missing canonical room {room!r}"


def test_skill_documents_per_workspace_palace_location(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL_PATH)
    assert ".mempalace/palace" in content, (
        "integration skill does not document the per-workspace palace path"
    )


def test_skill_documents_palace_flag_precedes_subcommand(plugin_root: Path) -> None:
    """--palace is a GLOBAL flag; failure to document this surfaces user confusion."""
    content = _read(plugin_root, SKILL_PATH)
    assert "GLOBAL" in content or "global" in content.lower(), (
        "integration skill does not flag that --palace is global / precedes subcommand"
    )


def test_pipeline_runs_wakeup_at_phase_minus_1(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "wake-up" in content, "pipeline skill does not run mempalace wake-up at Phase -1"
    assert "MemPalace wake-up" in content, (
        "pipeline skill does not name the Phase -1 wake-up as a MemPalace step"
    )


def test_pipeline_auto_mines_codebase_maps(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "--room codebase-maps" in content, (
        "pipeline skill does not auto-mine CODEBASE_MAP into the codebase-maps room"
    )


def test_pipeline_auto_mines_integration_maps(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "--room integration-maps" in content, (
        "pipeline skill does not auto-mine INTEGRATION_MAP into the integration-maps room"
    )


def test_pipeline_auto_mines_solution_requirements(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "--room solution-requirements" in content, (
        "pipeline skill does not auto-mine SRs into the solution-requirements room"
    )


def test_pipeline_auto_mines_diagnostic_plans(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "--room diagnostic-plans" in content, (
        "pipeline skill does not auto-mine diagnostic-research dir into diagnostic-plans room"
    )


def test_pipeline_auto_mines_final_reports(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "--room final-reports" in content, (
        "pipeline skill does not auto-mine Phase 8 final report into final-reports room"
    )


def test_pipeline_auto_mines_coverage_maps(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "--room coverage-maps" in content, (
        "pipeline skill does not auto-mine coverage-map.json into coverage-maps room"
    )


def test_diagnostic_researcher_searches_before_tracing(plugin_root: Path) -> None:
    content = _read(plugin_root, DIAGNOSTIC_RESEARCHER_PATH)
    assert "Search MemPalace" in content or "search MemPalace" in content.lower(), (
        "diagnostic-researcher does not search MemPalace before tracing"
    )
    assert "Step 0" in content, (
        "diagnostic-researcher does not name the search step as Step 0 (pre-trace)"
    )
    # Both rooms must be searched.
    assert "--room diagnostic-plans" in content, "researcher does not search diagnostic-plans room"
    assert "--room rca-artifacts" in content, "researcher does not search rca-artifacts room"


def test_system_architect_searches_before_recommendation(plugin_root: Path) -> None:
    content = _read(plugin_root, SYSTEM_ARCHITECT_PATH)
    assert "Search MemPalace" in content or "search MemPalace" in content.lower(), (
        "system-architect does not search MemPalace before recommending"
    )


def test_system_architect_recommendation_is_mined_to_architectural_decisions(plugin_root: Path) -> None:
    """The system-architect's recommendation must reach the architectural-decisions
    room. As of v0.9.9 the orchestrator performs the mine (mining is
    orchestrator-serialized) — the agent returns the path."""
    content = _read(plugin_root, SYSTEM_ARCHITECT_PATH)
    assert "architectural-decisions" in content, (
        "system-architect does not route its recommendation to the architectural-decisions room"
    )


def test_route_mapper_searches_before_routing(plugin_root: Path) -> None:
    content = _read(plugin_root, ROUTE_MAPPER_PATH)
    assert "Search MemPalace" in content or "search MemPalace" in content.lower(), (
        "route-mapper does not search MemPalace before enumerating routes"
    )
    assert "--room route-maps" in content, "route-mapper does not search route-maps room"


def test_route_mapper_auto_mines_route_map(plugin_root: Path) -> None:
    content = _read(plugin_root, ROUTE_MAPPER_PATH)
    assert "--room route-maps" in content, "route-mapper does not auto-mine ROUTE_MAP.md"


def test_skill_forbids_inventing_new_rooms(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL_PATH)
    # The discipline language must be explicit.
    assert "canonical" in content.lower(), "skill does not establish room names as canonical"


def test_skill_documents_mcp_wire_up(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL_PATH)
    assert "claude mcp add mempalace -- mempalace-mcp" in content, (
        "integration skill does not document the canonical MCP wire-up command"
    )


def test_skill_documents_search_audit_trail(plugin_root: Path) -> None:
    """The 'kept | discarded | supersedes | extended' annotation contract must be present."""
    content = _read(plugin_root, SKILL_PATH)
    for marker in ("kept", "discarded", "supersedes", "extended"):
        assert marker in content, (
            f"integration skill does not document the {marker!r} search-audit-trail annotation"
        )
