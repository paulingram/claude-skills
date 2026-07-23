"""Structural tests for the `bug-replicator` agent (v0.9.22)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "bug-replicator"

REQUIRED_BODY_SECTIONS = (
    "## Inputs",
    "## Process",
    "## Exit verdicts",
    "## What this agent does NOT do",
    "## Hard rules",
)

EXIT_VERDICTS = ("reproduced", "could-not-reproduce", "needs-clarification")


def _agent_path(plugin_root: Path) -> Path:
    return plugin_root / "agents" / f"{AGENT_NAME}.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_agent_path(plugin_root))


def _tools_list(fm: dict) -> list[str]:
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return [t.strip() for t in raw if t]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def test_agent_file_exists(plugin_root: Path) -> None:
    assert _agent_path(plugin_root).exists()


def test_agent_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    for key in ("name", "description", "tools", "model", "color"):
        assert key in fm, f"bug-replicator: missing frontmatter key `{key}`"
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_opus(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    assert fm["model"] == "opus", (
        "bug-replicator is adversarial (reproduces the symptom; the artifact IS "
        "the regression test) — model: opus under the v3.43.0 delivery-adversarial "
        "split; lever scripts/setup/set_default_model.py --split delivery")


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, "bug-replicator must NOT have Edit (analysis + bounded test-file writes only)"


def test_agent_tools_has_write(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" in tools, "bug-replicator must have Write (it authors reproduction test files)"


def test_agent_tools_has_bash(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Bash" in tools, "bug-replicator must have Bash (it runs the artifacts it writes)"


@pytest.mark.parametrize("section", REQUIRED_BODY_SECTIONS)
def test_required_body_section_present(plugin_root: Path, section: str) -> None:
    _, body = _read(plugin_root)
    assert section in body, f"bug-replicator agent body missing section: {section}"


@pytest.mark.parametrize("verdict", EXIT_VERDICTS)
def test_exit_verdict_named(plugin_root: Path, verdict: str) -> None:
    _, body = _read(plugin_root)
    assert verdict in body, f"bug-replicator body must name the `{verdict}` exit verdict"


def test_agent_names_playwright_and_dev_api_skills(plugin_root: Path) -> None:
    _, body = _read(plugin_root)
    assert "playwright-user-flows" in body, "agent must reference playwright-user-flows skill"
    assert "dev-api-integration-testing" in body, "agent must reference dev-api-integration-testing skill"


def test_agent_must_currently_fail_rule(plugin_root: Path) -> None:
    """The agent body must state that the artifact MUST currently fail (the replication)."""
    _, body = _read(plugin_root)
    # The artifact-must-fail rule appears in the hard rules section.
    assert "must currently fail" in body.lower() or "MUST currently fail" in body, (
        "agent body must state the artifact must currently fail (= the replication)"
    )


# --- v0.9.32 — selector witness at authoring time ---------------------------


def test_selector_witness_discipline_documented(plugin_root: Path) -> None:
    """v0.9.32 — the agent body must mandate selector witness assertions on every action-call selector."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "selector witness" in body_lower, (
        "bug-replicator must name the 'selector witness' discipline"
    )
    # The witness must be MANDATORY for every interactive selector — not "best practice"
    assert "mandatory" in body_lower, (
        "the selector witness must be MANDATORY (not optional / best-practice)"
    )


def test_selector_witness_covers_three_failure_modes(plugin_root: Path) -> None:
    """The witness assertions cover (a) resolution wrong, (b) action not possible (disabled), (c) wrong-element-with-similar-text."""
    _, body = _read(plugin_root)
    # The discipline must reference each of the three Playwright assertions
    assert "toBeVisible" in body, "the selector witness must include `.toBeVisible()`"
    assert "toBeEnabled" in body, (
        "the selector witness must include `.toBeEnabled()` (catches the disabled-button case from v0.9.30 production)"
    )
    # The role / attribute disambiguation step must be documented
    body_lower = body.lower()
    assert "role" in body_lower and ("attribute" in body_lower or "tohaveattribute" in body_lower), (
        "the selector witness must document a role / attribute disambiguation step"
    )


def test_selector_witness_quotes_v0_9_30_production_case(plugin_root: Path) -> None:
    """The agent body must quote the v0.9.30 production case that motivated the witness."""
    _, body = _read(plugin_root)
    # The case quote names "Alabama" (the wrong-resolution element)
    assert "Alabama" in body or "state filter" in body, (
        "the agent body must reference the v0.9.30 'text=Alabama → state filter' production case"
    )


def test_selector_witness_in_hard_rules(plugin_root: Path) -> None:
    """The witness must appear in the 'Hard rules (non-negotiable)' section so it's structurally enforced."""
    _, body = _read(plugin_root)
    hard_rules_start = body.find("## Hard rules")
    assert hard_rules_start > 0, "agent must have a 'Hard rules' section"
    hard_rules_section = body[hard_rules_start:]
    assert "elector witness" in hard_rules_section, (
        "the selector witness must appear in the 'Hard rules' section (structural enforcement, not just guidance)"
    )
