"""v0.9.6 — expensive-verification-debugging discipline structural tests.

Reported failure class: an agent debugging a deployed-app bug found three
independent Docker/Vite config defects sequentially, each verified by a
~3-4 min ECS rolling deploy — burning three expensive cycles on a symptom
whose three causes were all discoverable up-front by a static pathway audit
plus a free local bundle inspection.

v0.9.6 adds the `expensive-verification-debugging` skill: price the loop,
audit the whole failure pathway, find the cheapest faithful artifact, batch
every fix, spend the expensive cycle once. These tests assert the discipline
is present across the skill + its wire-up so it cannot silently regress.
"""
from pathlib import Path

import pytest

SKILL = ("skills", "expensive-verification-debugging", "SKILL.md")
RCA_SKILL = ("skills", "root-cause-test-failures", "SKILL.md")
PIPELINE_SKILL = ("skills", "architect-team-pipeline", "SKILL.md")
INTEGRATION_AGENT = ("agents", "integration.md")
FRONTEND_AGENT = ("agents", "frontend.md")
BACKEND_AGENT = ("agents", "backend.md")
DIAGNOSTIC_RESEARCHER = ("agents", "diagnostic-researcher.md")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def test_skill_exists_and_non_empty(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert content.strip(), "expensive-verification-debugging SKILL.md is empty"


@pytest.mark.parametrize(
    "concept",
    [
        "Price the loop",            # discipline 1
        "Audit the pathway",         # discipline 2
        "cheapest faithful artifact",  # discipline 3
        "Batch the fixes",           # discipline 4
    ],
)
def test_skill_states_the_four_disciplines(plugin_root: Path, concept: str) -> None:
    """All four disciplines must be present as named concepts."""
    content = _read(plugin_root, SKILL)
    assert concept in content, (
        f"expensive-verification-debugging SKILL.md missing discipline concept: {concept!r}"
    )


def test_skill_has_pathway_audit_artifact_schema(plugin_root: Path) -> None:
    """The skill must define the persisted pathway-audit artifact."""
    content = _read(plugin_root, SKILL)
    assert "failure-pathway" in content, "skill does not define the failure-pathway artifact path"
    assert "defects_found" in content, "skill's pathway-audit artifact lacks defects_found"
    assert '"pathway"' in content, "skill's pathway-audit artifact lacks the pathway stage list"


def test_skill_documents_multiple_simultaneous_causes(plugin_root: Path) -> None:
    """The core insight: a symptom can have several independent causes."""
    content = _read(plugin_root, SKILL)
    assert "greenfield" in content.lower(), (
        "skill does not connect multiple simultaneous breaks to greenfield pathways"
    )
    assert "found *a* bug" in content or "you found a bug" in content.lower(), (
        "skill does not reject the singular 'I found the bug' framing"
    )


def test_skill_has_two_cycle_strategy_switch_threshold(plugin_root: Path) -> None:
    """v3.8.0: after 2 expensive cycles the skill switches STRATEGY (pathway-audit
    + batch / re-route to diagnostic-research-team) — it does NOT stop the run.
    The batch-all-fixes efficiency discipline is kept; the give-up framing is gone."""
    content = _read(plugin_root, SKILL)
    low = content.lower()
    assert "2 expensive cycles" in content or "two expensive cycles" in low, (
        "skill does not define the 2-expensive-cycle strategy-switch threshold"
    )
    assert "diagnostic-research-team" in content, (
        "skill does not route the strategy switch to diagnostic-research-team"
    )
    # The batch-all-fixes efficiency discipline must remain.
    assert "batch" in low, "skill must keep the batch-all-fixes efficiency discipline"
    # The unbounded-solving discipline must be referenced — no give-up cap.
    assert "unbounded solving" in low, (
        "skill must reference the canonical Unbounded solving discipline (no give-up cap)"
    )
    # The old run-halting framing must be gone.
    assert "do not start a third cycle. instead" not in low, (
        "the old 'do not start a third cycle' give-up framing must be removed"
    )


def test_skill_has_worked_example(plugin_root: Path) -> None:
    """The worked example must be the real Vite/Docker case so it is concrete."""
    content = _read(plugin_root, SKILL)
    assert "dockerignore" in content, "skill worked example does not cover the .dockerignore stage"
    assert "import.meta" in content, "skill worked example does not cover the Vite import.meta stage"
    assert "COPY" in content, "skill worked example does not cover the Dockerfile COPY stage"


def test_skill_has_anti_pattern_table_and_red_flags(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "Anti-patterns to reject" in content, "skill lacks the anti-pattern table"
    assert "Red flags" in content, "skill lacks the red-flags STOP list"


def test_skill_has_proactive_greenfield_form(plugin_root: Path) -> None:
    """Strongest form: audit a new pathway BEFORE its first expensive cycle."""
    content = _read(plugin_root, SKILL)
    assert "before its first cycle" in content or "before the first cycle" in content.lower(), (
        "skill does not document the proactive (pre-first-cycle) greenfield audit"
    )


def test_skill_references_v092_no_wakeup_rule(plugin_root: Path) -> None:
    """While an expensive cycle runs, poll with a bounded loop — not a wakeup."""
    content = _read(plugin_root, SKILL)
    assert "wakeup" in content.lower(), (
        "skill does not reference the v0.9.2 no-arbitrary-wakeup rule for the wait window"
    )


def test_rca_skill_cross_references_the_new_skill(plugin_root: Path) -> None:
    """root-cause-test-failures Pass 3 must point at the new skill + name the
    multiple-simultaneous-causes category."""
    content = _read(plugin_root, RCA_SKILL)
    assert "expensive-verification-debugging" in content, (
        "root-cause-test-failures does not cross-reference expensive-verification-debugging"
    )
    assert "Multiple simultaneous causes" in content, (
        "root-cause-test-failures Pass 3 does not add the multiple-simultaneous-causes category"
    )


def test_pipeline_phase_5_references_the_skill(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL)
    assert "expensive-verification-debugging" in content, (
        "pipeline Phase 5 does not reference expensive-verification-debugging"
    )


@pytest.mark.parametrize(
    "agent_path",
    [INTEGRATION_AGENT, FRONTEND_AGENT, BACKEND_AGENT],
    ids=["integration", "frontend", "backend"],
)
def test_implementer_agents_have_the_hard_rule(plugin_root: Path, agent_path: tuple[str, ...]) -> None:
    """integration, frontend, and backend agents must each reference the skill
    as a hard rule against one-fix-per-cycle whack-a-mole."""
    content = _read(plugin_root, agent_path)
    assert "expensive-verification-debugging" in content, (
        f"{agent_path[-1]} does not reference expensive-verification-debugging"
    )


def test_diagnostic_researcher_covers_build_deploy_pathway(plugin_root: Path) -> None:
    """The diagnostic-researcher's 'full code flow' must explicitly include
    build / deploy / config pathway stages, not only application code."""
    content = _read(plugin_root, DIAGNOSTIC_RESEARCHER)
    assert "build / deploy / config" in content or "build/deploy/config" in content, (
        "diagnostic-researcher does not extend the pathway trace to build/deploy/config stages"
    )
