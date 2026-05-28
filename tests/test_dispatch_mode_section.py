"""REQ-6: Pipeline-skill dispatch-mode section.

Each pipeline SKILL.md (`architect-team-pipeline`, `bug-fix-pipeline`,
`mini-architect-team-pipeline`) MUST contain a `## Dispatch mode` section
near the top (after `## Inputs`) describing the mode-detection rule.

Scenarios from spec.md REQ-6:
  6.1 each pipeline SKILL.md has the section (exactly once)
  6.2 the section names the env + version + flag
  6.3 the section names the teams-mode primitives
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.helpers import frontmatter


PIPELINE_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
)


def _skill_path(plugin_root: Path, skill_name: str) -> Path:
    return plugin_root / "skills" / skill_name / "SKILL.md"


def _read_body(plugin_root: Path, skill_name: str) -> str:
    _, body = frontmatter.parse(_skill_path(plugin_root, skill_name))
    return body


def _dispatch_mode_section(body: str) -> str:
    """Extract the `## Dispatch mode` H2 section's content (header + body up to next H2)."""
    start = body.find("## Dispatch mode")
    if start < 0:
        return ""
    # Find the next H2 heading after the start
    next_h2 = re.search(r"\n## (?!Dispatch mode)", body[start + len("## Dispatch mode"):])
    if next_h2 is None:
        return body[start:]
    return body[start : start + len("## Dispatch mode") + next_h2.start()]


# ---- Scenario 6.1: section present exactly once ------------------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_section_present_exactly_once(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    # Count occurrences of the heading. Use the exact H2 line so we don't match
    # references like "## Dispatch mode section" elsewhere.
    matches = re.findall(r"^## Dispatch mode\s*$", body, flags=re.MULTILINE)
    assert len(matches) == 1, (
        f"{skill_name}: expected exactly one '## Dispatch mode' H2 section, "
        f"found {len(matches)}"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_section_appears_after_inputs(
    plugin_root: Path, skill_name: str
) -> None:
    """The section should come AFTER `## Inputs` per the spec — it documents how the
    pipeline reads its environment at startup, which is a precondition for everything else."""
    body = _read_body(plugin_root, skill_name)
    inputs_pos = body.find("## Inputs")
    dispatch_pos = body.find("## Dispatch mode")
    assert inputs_pos >= 0, f"{skill_name}: missing `## Inputs` section"
    assert dispatch_pos >= 0, f"{skill_name}: missing `## Dispatch mode` section"
    assert dispatch_pos > inputs_pos, (
        f"{skill_name}: `## Dispatch mode` ({dispatch_pos}) must appear AFTER "
        f"`## Inputs` ({inputs_pos})"
    )


# ---- Scenario 6.2: env + version + flag named -------------------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_env_var(plugin_root: Path, skill_name: str) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in section, (
        f"{skill_name}: `## Dispatch mode` section must name the env var "
        "`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_version_requirement(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "2.1.32" in section, (
        f"{skill_name}: `## Dispatch mode` section must name the Claude Code "
        "version requirement (`2.1.32`)"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_no_teams_flag(plugin_root: Path, skill_name: str) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "--no-teams" in section, (
        f"{skill_name}: `## Dispatch mode` section must name the `--no-teams` flag"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_settings_json_source(
    plugin_root: Path, skill_name: str
) -> None:
    """The detection rule reads either the env var OR `~/.claude/settings.json`."""
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    # Accept either the path or the file name; both are documented spellings.
    assert "settings.json" in section, (
        f"{skill_name}: `## Dispatch mode` section must name the `~/.claude/settings.json` "
        "fallback source for the env var"
    )


# ---- Scenario 6.3: teams-mode primitives named ------------------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_spawn_teammate_primitive(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    # The docs use phrasings like "Spawn teammate using the <role> agent type".
    # Accept either the canonical phrasing or a near-equivalent ("spawn a teammate"
    # with "agent type"), but require both halves so we exercise the documented form.
    body_lower = section.lower()
    assert "spawn teammate" in body_lower or "spawn a teammate" in body_lower, (
        f"{skill_name}: `## Dispatch mode` section must name the spawn-a-teammate "
        "primitive (e.g., 'Spawn teammate using the <role> agent type')"
    )
    assert "agent type" in body_lower, (
        f"{skill_name}: `## Dispatch mode` section must name the 'agent type' "
        "phrase from the agent-teams docs"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_send_message(plugin_root: Path, skill_name: str) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "SendMessage" in section, (
        f"{skill_name}: `## Dispatch mode` section must name `SendMessage` as the "
        "teams-mode teammate-to-teammate communication primitive"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_shared_task_list_path(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "~/.claude/tasks/" in section, (
        f"{skill_name}: `## Dispatch mode` section must reference the shared task "
        "list path at `~/.claude/tasks/<slug>/`"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_subagents_mode_fallback(
    plugin_root: Path, skill_name: str
) -> None:
    """The section must mention subagents mode (the v0.9.36 behavior is unchanged)."""
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    body_lower = section.lower()
    assert "subagents mode" in body_lower or "subagent mode" in body_lower, (
        f"{skill_name}: `## Dispatch mode` section must name 'subagents mode' "
        "as the fallback"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_records_decision_in_intake_state(
    plugin_root: Path, skill_name: str
) -> None:
    """The decision is made once at startup and recorded as `dispatch_mode` in intake-state.json."""
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "dispatch_mode" in section, (
        f"{skill_name}: `## Dispatch mode` section must state that the decision is "
        "recorded as `dispatch_mode` in intake-state.json"
    )
    assert "intake-state.json" in section, (
        f"{skill_name}: `## Dispatch mode` section must reference `intake-state.json` "
        "as the persistence location"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_dispatch_mode_names_background_named_dispatch(
    plugin_root: Path, skill_name: str
) -> None:
    """In teams mode the Lead spawns named teammates via the Agent tool with
    run_in_background and a stable name."""
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "run_in_background" in section, (
        f"{skill_name}: `## Dispatch mode` section must name `run_in_background: true` "
        "as the teams-mode spawn primitive"
    )
