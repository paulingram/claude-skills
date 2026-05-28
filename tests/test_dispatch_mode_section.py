"""REQ-6: Pipeline-skill dispatch-mode section.

Each pipeline SKILL.md (`architect-team-pipeline`, `bug-fix-pipeline`,
`mini-architect-team-pipeline`) MUST contain a `## Dispatch mode` section
near the top (after `## Inputs`).

The canonical dispatch-mode rule body now lives in
`common-pipeline-conventions` `## Dispatch mode (v1.0.0)` (per SR-audit-dup-2A-003 /
SR-audit-eff-001). The 19 substring assertions that used to verify each
pipeline body's inline text now verify the SHARED skill's body. Each pipeline
body still carries a `## Dispatch mode` H2 (so a reader landing on the pipeline
can jump to the rule), and that H2 references the canonical home — a per-pipeline
reference-back assertion enforces that.

Scenarios from spec.md REQ-6:
  6.1 each pipeline SKILL.md has the section (exactly once)
  6.2 the canonical home names the env + version + flag
  6.3 the canonical home names the teams-mode primitives
  6.4 (new) each pipeline body references the canonical home
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

# Canonical home of the dispatch-mode rule (SR-audit-dup-2A-003 / SR-audit-eff-001).
CANONICAL_SKILL = "common-pipeline-conventions"


def _skill_path(plugin_root: Path, skill_name: str) -> Path:
    return plugin_root / "skills" / skill_name / "SKILL.md"


def _read_body(plugin_root: Path, skill_name: str) -> str:
    _, body = frontmatter.parse(_skill_path(plugin_root, skill_name))
    return body


def _dispatch_mode_section(body: str, header_token: str = "## Dispatch mode") -> str:
    """Extract a `## Dispatch mode...` H2 section's content (header + body up to next H2).

    The canonical body uses `## Dispatch mode (v1.0.0)`; pipeline bodies use `## Dispatch mode`.
    We accept either by matching the H2 prefix.
    """
    start = body.find(header_token)
    if start < 0:
        return ""
    # Find the next H2 heading after the start
    next_h2 = re.search(r"\n## (?!Dispatch mode)", body[start + len(header_token):])
    if next_h2 is None:
        return body[start:]
    return body[start : start + len(header_token) + next_h2.start()]


def _canonical_body(plugin_root: Path) -> str:
    return _read_body(plugin_root, CANONICAL_SKILL)


def _canonical_section(plugin_root: Path) -> str:
    """Extract the canonical `## Dispatch mode (v1.0.0)` section from common-pipeline-conventions."""
    body = _canonical_body(plugin_root)
    return _dispatch_mode_section(body, header_token="## Dispatch mode (v1.0.0)")


# ---- Scenario 6.1: section present exactly once in each pipeline -------------


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


def test_canonical_dispatch_mode_section_exists(plugin_root: Path) -> None:
    """The canonical home `common-pipeline-conventions` MUST carry the `## Dispatch mode (v1.0.0)` H2."""
    body = _canonical_body(plugin_root)
    assert "## Dispatch mode (v1.0.0)" in body, (
        f"{CANONICAL_SKILL}: missing canonical `## Dispatch mode (v1.0.0)` section "
        "(SR-audit-dup-2A-003 / SR-audit-eff-001)"
    )


# ---- Scenario 6.4: each pipeline references the canonical home ---------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_dispatch_section_references_canonical_home(
    plugin_root: Path, skill_name: str
) -> None:
    """Each pipeline body's `## Dispatch mode` section MUST cite `common-pipeline-conventions`
    as the canonical home of the rule (SR-audit-dup-2A-003)."""
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert CANONICAL_SKILL in section, (
        f"{skill_name}: `## Dispatch mode` section must reference the canonical home "
        f"`{CANONICAL_SKILL}` (SR-audit-dup-2A-003)"
    )


# ---- Scenario 6.2: env + version + flag named in canonical home --------------


def test_canonical_dispatch_mode_names_env_var(plugin_root: Path) -> None:
    section = _canonical_section(plugin_root)
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name the env var "
        "`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`"
    )


def test_canonical_dispatch_mode_names_version_requirement(plugin_root: Path) -> None:
    section = _canonical_section(plugin_root)
    assert "2.1.32" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name the Claude Code "
        "version requirement (`2.1.32`)"
    )


def test_canonical_dispatch_mode_names_no_teams_flag(plugin_root: Path) -> None:
    section = _canonical_section(plugin_root)
    assert "--no-teams" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name the `--no-teams` flag"
    )


def test_canonical_dispatch_mode_names_settings_json_source(plugin_root: Path) -> None:
    """The detection rule reads either the env var OR `~/.claude/settings.json`."""
    section = _canonical_section(plugin_root)
    assert "settings.json" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name the "
        "`~/.claude/settings.json` fallback source for the env var"
    )


# ---- Each pipeline body still names the rule's anchors (env / version / flag /
# settings) so a reader can find the rule even without jumping to the canonical
# home. These are now anchor-string assertions, not full-body assertions. -------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_dispatch_section_names_env_var(plugin_root: Path, skill_name: str) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in section, (
        f"{skill_name}: `## Dispatch mode` section must name the env var "
        "`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` as an anchor to the canonical rule"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_dispatch_section_names_version_requirement(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "2.1.32" in section, (
        f"{skill_name}: `## Dispatch mode` section must name the version requirement (`2.1.32`)"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_dispatch_section_names_no_teams_flag(plugin_root: Path, skill_name: str) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "--no-teams" in section, (
        f"{skill_name}: `## Dispatch mode` section must name the `--no-teams` flag"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_dispatch_section_names_settings_json_source(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "settings.json" in section, (
        f"{skill_name}: `## Dispatch mode` section must name `settings.json`"
    )


# ---- Scenario 6.3: teams-mode primitives named in canonical home -------------


def test_canonical_dispatch_mode_names_spawn_teammate_primitive(plugin_root: Path) -> None:
    """The canonical home spells out the 'Spawn teammate using the <role> agent type' primitive."""
    section = _canonical_section(plugin_root)
    body_lower = section.lower()
    assert "spawn teammate" in body_lower or "spawn a teammate" in body_lower, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name the spawn-a-teammate "
        "primitive (e.g., 'Spawn teammate using the <role> agent type')"
    )
    assert "agent type" in body_lower, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name the 'agent type' phrase"
    )


def test_canonical_dispatch_mode_names_send_message(plugin_root: Path) -> None:
    section = _canonical_section(plugin_root)
    assert "SendMessage" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name `SendMessage` "
        "as the teams-mode teammate-to-teammate communication primitive"
    )


def test_canonical_dispatch_mode_names_shared_task_list_path(plugin_root: Path) -> None:
    section = _canonical_section(plugin_root)
    assert "~/.claude/tasks/" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must reference the shared task "
        "list path at `~/.claude/tasks/<slug>/`"
    )


def test_canonical_dispatch_mode_names_subagents_mode_fallback(plugin_root: Path) -> None:
    """The canonical section must mention subagents mode (the v0.9.36 behavior is unchanged)."""
    section = _canonical_section(plugin_root)
    body_lower = section.lower()
    assert "subagents mode" in body_lower or "subagent mode" in body_lower, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name 'subagents mode' as the fallback"
    )


def test_canonical_dispatch_mode_records_decision_in_intake_state(plugin_root: Path) -> None:
    """The decision is made once at startup and recorded as `dispatch_mode` in intake-state.json."""
    section = _canonical_section(plugin_root)
    assert "dispatch_mode" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must state that the decision is "
        "recorded as `dispatch_mode` in intake-state.json"
    )
    assert "intake-state.json" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must reference `intake-state.json` "
        "as the persistence location"
    )


def test_canonical_dispatch_mode_names_background_named_dispatch(plugin_root: Path) -> None:
    """In teams mode the Lead spawns named teammates via the Agent tool with
    run_in_background and a stable name."""
    section = _canonical_section(plugin_root)
    assert "run_in_background" in section, (
        f"{CANONICAL_SKILL} `## Dispatch mode (v1.0.0)` must name `run_in_background: true` "
        "as the teams-mode spawn primitive"
    )


# Each pipeline body also names the subagents-mode + dispatch_mode + intake-state anchors
# so the mode-aware test in test_no_nested_teams_in_skills.py's
# `test_skill_describes_mode_aware_dispatch` keeps passing — anchored as sentence-level
# references, not full-body assertions. ----------------------------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_dispatch_section_records_decision_in_intake_state(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    assert "dispatch_mode" in section, (
        f"{skill_name}: `## Dispatch mode` section must name `dispatch_mode` (the persisted key)"
    )
    assert "intake-state.json" in section, (
        f"{skill_name}: `## Dispatch mode` section must reference `intake-state.json`"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_dispatch_section_names_subagents_mode_fallback(
    plugin_root: Path, skill_name: str
) -> None:
    body = _read_body(plugin_root, skill_name)
    section = _dispatch_mode_section(body)
    body_lower = section.lower()
    assert "subagents mode" in body_lower or "subagent mode" in body_lower, (
        f"{skill_name}: `## Dispatch mode` section must name 'subagents mode' as the fallback"
    )
