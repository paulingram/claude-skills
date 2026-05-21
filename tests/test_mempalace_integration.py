"""v0.9.4 — mempalace-integration skill + wire-up structural tests.

These tests assert that the integration skill exists, names the canonical
storage taxonomy, the auto-mine rules fire at every required phase of the
pipeline skill, and the three named subagents (system-architect,
diagnostic-researcher, route-mapper) document the search-before-output
discipline.

v0.9.14 — `mempalace mine` accepts only `--wing` (verified against mempalace
3.3.5; `mine` has no `--room` flag — rooms are auto-detected by `mempalace
init` from directory structure). The auto-mine assertions therefore check that
each artifact path is mined, and a regression test guards that no skill /
agent / command reintroduces a `mine ... --room` command form.
"""
import re
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


# --- command extraction -----------------------------------------------------
# Real CLI invocations live in fenced code blocks or inline-code spans. Prose
# that merely *names* a flag (e.g. the sentence "`mine` has no `--room` flag")
# never places a full `mempalace ... mine ...` command in a single code unit,
# so extracting code units and scanning them is immune to prose false matches.

_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)
_INLINE_RE = re.compile(r"`([^`\n]+)`")


def _code_units(content: str) -> list[str]:
    """Every shell-command-bearing unit in a markdown doc: each fenced code
    block (line-continuations joined) plus each inline-code span."""
    units: list[str] = []
    for block in _FENCE_RE.findall(content):
        # Join backslash line-continuations so a multi-line command is one unit.
        joined = re.sub(r"\\\n\s*", " ", block)
        units.extend(line.strip() for line in joined.splitlines() if line.strip())
    units.extend(span.strip() for span in _INLINE_RE.findall(content))
    return units


def _commands_with_token(content: str, token: str) -> list[str]:
    """Return every `mempalace ...` command unit that contains a bare `token`
    word (e.g. 'mine' or 'search')."""
    word = re.compile(rf"(?<![\w-]){re.escape(token)}(?![\w-])")
    return [
        unit for unit in _code_units(content)
        if "mempalace" in unit and word.search(unit)
    ]


def _iter_doc_files(plugin_root: Path):
    """Every .md file under skills/, agents/, commands/."""
    for sub in ("skills", "agents", "commands"):
        base = plugin_root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            yield path


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


# Each artifact must still be auto-mined — but `mempalace mine` takes `--wing`
# only (no `--room`; rooms are init-detected from directory structure). Each
# test asserts the artifact path is mined and that the mine command carries no
# `--room` flag.

def _mine_commands(content: str) -> list[str]:
    """Return every `mempalace ... mine ...` invocation found in code spans /
    fenced code blocks of a doc, as single-line strings."""
    return _commands_with_token(content, "mine")


def test_pipeline_auto_mines_codebase_maps(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "CODEBASE_MAP.md" in content and 'mine "<codebase>/docs/CODEBASE_MAP.md"' in content, (
        "pipeline skill does not auto-mine CODEBASE_MAP.md"
    )


def test_pipeline_auto_mines_integration_maps(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert 'mine "<workspace>/docs/INTEGRATION_MAP.md"' in content, (
        "pipeline skill does not auto-mine INTEGRATION_MAP.md"
    )


def test_pipeline_auto_mines_solution_requirements(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert 'mine "<SR-path>"' in content, (
        "pipeline skill does not auto-mine SRs"
    )


def test_pipeline_auto_mines_diagnostic_plans(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert "diagnostic-research/<test-id>/" in content and (
        'mine "<cwd>/.architect-team/diagnostic-research/<test-id>/"' in content
    ), "pipeline skill does not auto-mine the diagnostic-research dir"


def test_pipeline_auto_mines_final_reports(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert 'mine "<cwd>/.architect-team/runs/<change-name>-<ts>.md"' in content, (
        "pipeline skill does not auto-mine the Phase 8 final report"
    )


def test_pipeline_auto_mines_coverage_maps(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL_PATH)
    assert 'mine "openspec/changes/<change-name>/coverage-map.json"' in content, (
        "pipeline skill does not auto-mine coverage-map.json"
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


# --- v0.9.14 regression guard: `mempalace mine` has no `--room` flag --------
# mempalace 3.3.5's `mine` subcommand accepts --mode/--wing/--no-gitignore/
# --include-ignored/--agent/--limit/--redetect-origin/--dry-run/--extract and
# NOTHING else. Rooms are auto-detected by `mempalace init` from directory
# structure. A `mine ... --room` command errors with `unrecognized arguments`
# on every call. These tests fail if any skill / agent / command reintroduces
# the defect — so it cannot silently return.

def test_no_doc_uses_mine_with_room_flag(plugin_root: Path) -> None:
    """No skill / agent / command may document a `mempalace ... mine` command
    carrying a `--room` flag. `mine` takes `--wing` only."""
    offenders: list[str] = []
    for path in _iter_doc_files(plugin_root):
        content = path.read_text(encoding="utf-8")
        for cmd in _commands_with_token(content, "mine"):
            # A genuine mine *command* — not a `search` command that happens
            # to mention 'mine' in prose-free code (search commands are caught
            # by the token filter only when they contain the word 'mine').
            if "search" in cmd:
                continue
            if "--room" in cmd:
                rel = path.relative_to(plugin_root).as_posix()
                offenders.append(f"{rel}: {cmd}")
    assert not offenders, (
        "`mempalace mine` has no `--room` flag (mempalace 3.3.5 — rooms are "
        "init-detected from directory structure). Remove `--room` from these "
        "mine commands:\n  " + "\n  ".join(offenders)
    )


def test_search_room_flag_still_permitted(plugin_root: Path) -> None:
    """Guard against over-correction: `mempalace search --room` IS valid and
    the integration skill must keep documenting it for the named agents."""
    content = _read(plugin_root, SKILL_PATH)
    search_cmds = _commands_with_token(content, "search")
    assert any("--room" in cmd for cmd in search_cmds), (
        "integration skill no longer documents any `search --room` query — "
        "the room-scoped search contract for named agents was lost"
    )


def test_integration_skill_states_mine_takes_wing_only(plugin_root: Path) -> None:
    """The operating rules must explicitly record that `mine` takes `--wing`
    only and that rooms are init-detected — the durable fix for the defect."""
    content = _read(plugin_root, SKILL_PATH).lower()
    assert "auto-detect" in content or "auto-detected" in content, (
        "integration skill does not state rooms are auto-detected"
    )
    assert "mempalace init" in content, (
        "integration skill does not attribute room detection to `mempalace init`"
    )
