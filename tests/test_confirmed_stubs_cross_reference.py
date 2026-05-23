"""Structural tests for v0.9.28 — confirmed-stubs cross-reference (cohesion-review issue #5).

v0.9.21's Phase −1D bulk-verify gate records user-confirmed stubs in the
per-codebase `INTERACTION_INTUITION_MAP.md` (`user_verdict: confirmed-stub`).
v0.9.19's Phase 5 interaction-completeness team records confirmed stubs in
the converged interaction map + `coverage-map.json` `confirmed_stubs[]`.

Pre-v0.9.28: the two surfaces didn't cross-reference each other, so the
Phase 5 team would re-escalate the same `confirmed-stub` question to the
user that Phase −1D had already resolved — a poor UX.

v0.9.28 wires the pre-population: the Phase 5 reviewers read
`INTERACTION_INTUITION_MAP.md` before enumerating, pre-populate
`confirmed_stubs[]` for every element with `user_verdict: confirmed-stub`,
and do NOT re-ask the user. The cross-reference is bidirectional with the
v0.9.21 binding-input rule: `confirmed`-action entries flow to Phase 0;
`confirmed-stub` entries flow to Phase 5.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


def _read_body(plugin_root: Path, relpath: str) -> str:
    _, body = frontmatter.parse(plugin_root / relpath)
    return body


# ─── interaction-completeness: the consumer of pre-confirmed stubs ─────────


def test_interaction_completeness_references_intuition_map(plugin_root: Path) -> None:
    """The Phase 5 skill must reference INTERACTION_INTUITION_MAP.md as a source."""
    body = _read_body(plugin_root, "skills/interaction-completeness/SKILL.md")
    assert "INTERACTION_INTUITION_MAP" in body, (
        "interaction-completeness skill must reference INTERACTION_INTUITION_MAP.md "
        "(the Phase −1D source of pre-confirmed stubs)"
    )


def test_interaction_completeness_documents_pre_population(plugin_root: Path) -> None:
    """The skill must explicitly document the Phase −1D → Phase 5 pre-population."""
    body = _read_body(plugin_root, "skills/interaction-completeness/SKILL.md")
    # Look for the dedicated section header
    assert "### Pre-population from Phase −1D" in body, (
        "interaction-completeness skill must have a `### Pre-population from Phase −1D` section"
    )


def test_interaction_completeness_says_not_re_escalated(plugin_root: Path) -> None:
    """The skill must promise the user is NOT re-asked the same question."""
    body = _read_body(plugin_root, "skills/interaction-completeness/SKILL.md")
    # The pre-population section's main UX promise
    section_start = body.find("### Pre-population from Phase −1D")
    assert section_start >= 0
    next_h = body.find("\n### ", section_start + 1)
    section = body[section_start:next_h] if next_h > 0 else body[section_start:]

    assert "NEVER re-escalate" in section or "not re-asked" in section.lower() or "don't ask the user twice" in section.lower(), (
        "Pre-population section must state the user is NOT re-asked the same question"
    )
    # And mention the keying on element_id (the matching mechanism).
    assert "element_id" in section, (
        "Pre-population section must name `element_id` as the cross-reference key"
    )


def test_interaction_completeness_handles_stale_intuition(plugin_root: Path) -> None:
    """The skill must handle the case where the intuition map's element no longer exists in the enumeration."""
    body = _read_body(plugin_root, "skills/interaction-completeness/SKILL.md")
    section_start = body.find("### Pre-population from Phase −1D")
    next_h = body.find("\n### ", section_start + 1)
    section = body[section_start:next_h] if next_h > 0 else body[section_start:]

    assert "stale-intuition" in section.lower() or "stale intuition" in section.lower() or "escalations" in section.lower(), (
        "Pre-population section must document the stale-intuition / map-changed case"
    )


# ─── interaction-intuition: documents the downstream flow ─────────────────


def test_interaction_intuition_documents_downstream_pre_population(plugin_root: Path) -> None:
    """The intuition skill's Relationship section must note the downstream flow to Phase 5."""
    body = _read_body(plugin_root, "skills/interaction-intuition/SKILL.md")
    # Find the interaction-completeness bullet in Relationship to other skills.
    section_start = body.find("## Relationship to other skills")
    assert section_start >= 0
    next_h = body.find("\n## ", section_start + 1)
    section = body[section_start:next_h] if next_h > 0 else body[section_start:]

    assert "confirmed-stub" in section, (
        "Relationship section must mention `confirmed-stub` downstream flow"
    )
    assert "flow downstream" in section.lower() or "flows downstream" in section.lower() or "downstream to Phase 5" in section, (
        "Relationship section must explicitly note the downstream flow to Phase 5"
    )


def test_interaction_intuition_cross_reference_is_bidirectional(plugin_root: Path) -> None:
    """The intuition skill must note this is the bidirectional partner to v0.9.21's binding-input rule."""
    body = _read_body(plugin_root, "skills/interaction-intuition/SKILL.md")
    section_start = body.find("## Relationship to other skills")
    next_h = body.find("\n## ", section_start + 1)
    section = body[section_start:next_h] if next_h > 0 else body[section_start:]

    assert "bidirectional" in section.lower(), (
        "Relationship section must describe the cross-reference as bidirectional (partner to v0.9.21's binding-input rule)"
    )


# ─── architect-team-pipeline: Phase 5 step 8b references the pre-population ─


def test_pipeline_phase_5_step_8b_documents_pre_population(plugin_root: Path) -> None:
    """The pipeline skill's Phase 5 step 8b (interaction-completeness review) must note the pre-population."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    # Find step 8b
    p5_start = body.find("## Phase 5")
    assert p5_start >= 0
    next_p = body.find("\n## ", p5_start + 1)
    phase5 = body[p5_start:next_p] if next_p > 0 else body[p5_start:]

    # Step 8b is the interaction-completeness step.
    assert "Pre-population from Phase −1D" in phase5 or "INTERACTION_INTUITION_MAP" in phase5 and "pre-populate" in phase5.lower(), (
        "Phase 5 step 8b must reference the Phase −1D pre-population mechanism for confirmed stubs"
    )


# ─── Polish items #7-#10 ──────────────────────────────────────────────────


def test_default_mode_section_has_sub_headings(plugin_root: Path) -> None:
    """v0.9.28 (issue #8) — `## Default mode of operation` gains H3 sub-headings for navigability."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    section_start = body.find("## Default mode of operation")
    next_h2 = body.find("\n## ", section_start + 1)
    section = body[section_start:next_h2] if next_h2 > 0 else body[section_start:]

    # The three sub-sections we added
    assert "### Gates are opt-in" in section, "Default mode section must have a `### Gates are opt-in (process gates)` sub-heading"
    assert "### Process gates vs. domain gates" in section, "Default mode section must have a `### Process gates vs. domain gates` sub-heading"
    assert "### Proposal-first mode" in section, "Default mode section must have a `### Proposal-first mode` sub-heading"


def test_system_architect_has_audit_modes_index(plugin_root: Path) -> None:
    """v0.9.28 (issue #9) — system-architect.md gains an Audit modes index near the top."""
    body = _read_body(plugin_root, "agents/system-architect.md")
    assert "## Audit modes" in body, "system-architect must have an `## Audit modes` index section"

    # The index must appear EARLY (before the first audit mode section).
    index_pos = body.find("## Audit modes")
    first_audit_section_pos = body.find("## Diagnostic Plan Review")
    assert index_pos < first_audit_section_pos, (
        "Audit modes index must appear lexically BEFORE the first audit-mode section"
    )

    # The index must list all 7 audit modes (plus the default mode).
    index_end = body.find("\n## ", index_pos + 1)
    index = body[index_pos:index_end] if index_end > 0 else body[index_pos:]
    for mode in (
        "Diagnostic Plan Review",
        "Editability Map Review",
        "Interaction Map Review",
        "Visual Gap Synthesis",
        "Master Review Audit",
        "Documentation Currency Audit",
        "Bug-Fix Generalization Audit",
    ):
        assert mode in index, f"Audit modes index must list `{mode}`"


def test_intake_skill_documents_phase_1d_nomenclature(plugin_root: Path) -> None:
    """v0.9.28 (issue #7) — intake-and-mapping documents the Phase −1D structural-level choice."""
    body = _read_body(plugin_root, "skills/intake-and-mapping/SKILL.md")
    assert "Nomenclature note" in body, (
        "intake-and-mapping must document the Phase −1D H2-vs-H3 structural choice as intentional"
    )


def test_codebase_map_documents_cached_plugin_lag(plugin_root: Path) -> None:
    """v0.9.28 (issue #10) — CODEBASE_MAP documents the plugin-cache vs. source-on-disk lag."""
    body = (plugin_root / "docs/CODEBASE_MAP.md").read_text(encoding="utf-8")
    assert "Plugin-cache" in body or "plugin-cache" in body.lower() or "cache lag" in body.lower(), (
        "CODEBASE_MAP must document the plugin-cache vs. source-on-disk lag (operational reality)"
    )


def test_codebase_map_marks_v0_9_23_dogfood_historical(plugin_root: Path) -> None:
    """v0.9.28 (issue #6) — CODEBASE_MAP marks the v0.9.23 dogfood asymmetry as historical."""
    body = (plugin_root / "docs/CODEBASE_MAP.md").read_text(encoding="utf-8")
    # The v0.9.23 doc-updater dogfood asymmetry was a one-time bootstrap event.
    assert "v0.9.23 dogfood" in body.lower() or "doc-updater" in body and "v0.9.24" in body, (
        "CODEBASE_MAP must reference the v0.9.23 doc-updater bootstrap asymmetry as historical (closed)"
    )
