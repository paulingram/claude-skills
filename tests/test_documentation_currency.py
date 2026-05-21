"""v0.9.15 — documentation-currency gate structural tests.

Observed gap: pipeline runs shipped code but left the project docs (the maps,
CLAUDE.md, INTEGRATION_MAP.md) stale — README + CHANGELOG got updated, the rest
drifted. v0.9.15 adds a Phase 8 documentation-currency gate: before the push,
every doc is updated AND independently reviewed by the system-architect
(Documentation Currency Audit mode). These tests assert the discipline is
present across the skill, the agent, the pipeline, and the Stop hook.
"""
from pathlib import Path

import pytest

SKILL = ("skills", "documentation-currency", "SKILL.md")
SYS_ARCHITECT = ("agents", "system-architect.md")
PIPELINE = ("skills", "architect-team-pipeline", "SKILL.md")
COMPLETION_HOOK = ("hooks", "pipeline-completion-audit.py")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- the skill --------------------------------------------------------------

def test_skill_exists_and_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, SKILL).strip(), "documentation-currency SKILL.md is empty"


@pytest.mark.parametrize(
    "doc",
    ["CODEBASE_MAP.md", "ROUTE_MAP.md", "DESIGN_MAP.md", "INTEGRATION_MAP.md",
     "README.md", "CHANGELOG.md", "CLAUDE.md"],
)
def test_skill_names_the_whole_documentation_inventory(plugin_root: Path, doc: str) -> None:
    """The whole inventory is in scope — the maps drift precisely because only
    the README gets attention."""
    content = _read(plugin_root, SKILL)
    assert doc in content, f"documentation-currency skill does not list {doc} in its inventory"


def test_skill_documents_the_producer_checker_split(plugin_root: Path) -> None:
    """The orchestrator updates; the system-architect independently audits —
    the updater is not the auditor."""
    content = _read(plugin_root, SKILL).lower()
    assert "updater is not the auditor" in content or (
        "orchestrator updates" in content and "independent" in content
    ), "documentation-currency skill does not establish the producer/checker split"


def test_skill_documents_the_phase_8_gate(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "Phase 8" in content, "documentation-currency skill does not place the gate at Phase 8"
    assert "Documentation Currency Audit" in content, (
        "documentation-currency skill does not name the system-architect audit mode"
    )


# --- the system-architect mode ---------------------------------------------

def test_system_architect_has_documentation_currency_audit_mode(plugin_root: Path) -> None:
    content = _read(plugin_root, SYS_ARCHITECT)
    assert "Documentation Currency Audit" in content, (
        "system-architect does not document the Documentation Currency Audit mode"
    )
    assert "you do not write the docs" in content.lower() or (
        "producer is not the checker" in content.lower()
    ), "system-architect Documentation Currency Audit mode does not establish it audits, not writes"


# --- the pipeline Phase 8 gate ---------------------------------------------

def test_pipeline_phase_8_runs_the_documentation_currency_gate(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE)
    assert "documentation-currency" in content, (
        "architect-team-pipeline Phase 8 does not reference the documentation-currency gate"
    )
    assert "Documentation Currency Audit" in content, (
        "architect-team-pipeline does not dispatch the system-architect Documentation Currency Audit"
    )


# --- the Stop-hook check ----------------------------------------------------

def test_completion_audit_checks_documentation_currency(plugin_root: Path) -> None:
    content = _read(plugin_root, COMPLETION_HOOK)
    assert "_audit_documentation_currency" in content, (
        "pipeline-completion-audit.py has no _audit_documentation_currency check"
    )
    # wired into audit()
    assert content.count("_audit_documentation_currency") >= 2, (
        "_audit_documentation_currency is defined but not wired into audit()"
    )
    assert "documentation-currency" in content, (
        "the hook does not look for the .architect-team/documentation-currency/ verdict dir"
    )
