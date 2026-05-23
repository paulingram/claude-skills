"""Structural tests asserting that v0.9.21's Phase −1D interaction-intuition
production + bulk-verify gate is wired across every relevant pipeline file."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


def _read_body(plugin_root: Path, relpath: str) -> str:
    path = plugin_root / relpath
    assert path.exists(), f"required file missing: {relpath}"
    _, body = frontmatter.parse(path)
    return body


# ─── Pipeline skill: the gate's primary anchor ─────────────────────────────


def test_pipeline_skill_contains_phase_1d_section(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    # The section heading or sub-section heading must include both "Phase −1D" and "bulk-verify".
    assert "Phase −1D" in body, "pipeline skill must name 'Phase −1D'"
    assert "bulk-verify" in body, "pipeline skill must name the 'bulk-verify' gate"


def test_pipeline_skill_names_intuiter_in_phase_1d(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    # interaction-intuiter is dispatched at the Phase −1D SUB-SECTION (not the casual mentions in
    # other paragraphs). Anchor on the bold sub-section heading `**D. Phase −1D` which only appears
    # at the actual section header.
    anchor = body.find("**D. Phase −1D")
    assert anchor >= 0, (
        "pipeline skill must have a `**D. Phase −1D` sub-section under `## Phase −1 — Intake & Mapping`"
    )
    # The next H2 header bounds the sub-section.
    next_h2 = body.find("\n## ", anchor + 1)
    section = body[anchor:next_h2] if next_h2 > 0 else body[anchor:]
    assert "interaction-intuiter" in section, (
        "the Phase −1D sub-section must dispatch the interaction-intuiter agent"
    )
    assert "bulk-verify" in section, "the Phase −1D sub-section heading must contain 'bulk-verify'"


@pytest.mark.parametrize("reply_phrase", ("all correct", "all incorrect"))
def test_pipeline_skill_names_reply_format(plugin_root: Path, reply_phrase: str) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    assert reply_phrase in body, (
        f"pipeline skill must document the `{reply_phrase}` reply format for the bulk-verify gate"
    )


def test_pipeline_skill_documents_integer_list_reply(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    # The third format: comma- or whitespace-separated list of integers.
    assert "comma" in body.lower() and "integer" in body.lower(), (
        "pipeline skill must document the comma/whitespace-separated integer-list reply format"
    )


def test_pipeline_skill_auto_confirmation_rule(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    # The rule: items the user did NOT flag get user_verdict=confirmed automatically.
    assert "auto-record" in body.lower() or "auto-recorded" in body.lower() or "auto-confirm" in body.lower(), (
        "pipeline skill must state the auto-confirmation rule for unflagged items"
    )
    assert "user_verdict" in body, "pipeline skill must name the user_verdict field"
    assert "confirmed_action" in body, "pipeline skill must name confirmed_action"
    assert "confirmed_endpoint" in body, "pipeline skill must name confirmed_endpoint"


def test_pipeline_skill_phase_0_binding_input(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    # Phase 0 reads INTERACTION_INTUITION_MAP.md with confirmed: true.
    p0 = body.find("## Phase 0")
    assert p0 >= 0
    p1 = body.find("## Phase 1", p0 + 1)
    phase0_block = body[p0:p1]
    assert "INTERACTION_INTUITION_MAP" in phase0_block, (
        "Phase 0 section must read INTERACTION_INTUITION_MAP.md as a binding input"
    )
    assert "binding input" in phase0_block.lower(), (
        "Phase 0 must explicitly state the confirmed map is a binding input"
    )
    assert "superseded_by" in phase0_block, (
        "Phase 0 must define the superseded_by override mechanism"
    )


def test_pipeline_skill_phase_1_loop_condition(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    p1 = body.find("## Phase 1")
    assert p1 >= 0
    p2 = body.find("## Phase 2", p1 + 1)
    phase1_block = body[p1:p2]
    assert "INTERACTION_INTUITION_MAP" in phase1_block, (
        "Phase 1 loop conditions must reference INTERACTION_INTUITION_MAP for frontend / both-layer requirements"
    )


def test_pipeline_skill_default_mode_carve_out(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    start = body.find("## Default mode of operation")
    assert start >= 0
    # The carve-out is in this section.
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "process gate" in section.lower(), "Default mode of operation must name 'process gate'"
    assert "domain gate" in section.lower(), "Default mode of operation must name 'domain gate'"
    assert "Phase −1D" in section, "Default mode of operation carve-out must name Phase −1D as a domain gate"


# ─── intake-and-mapping skill ──────────────────────────────────────────────


def test_intake_skill_phase_1d_section(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/intake-and-mapping/SKILL.md")
    assert "Phase −1D" in body, "intake-and-mapping must name Phase −1D"
    assert "interaction-intuiter" in body, "intake-and-mapping must name the interaction-intuiter agent"
    assert "INTERACTION_INTUITION_MAP" in body, "intake-and-mapping must name the per-codebase artifact"


# ─── frontend-route-mapping skill ──────────────────────────────────────────


def test_route_mapping_skill_names_intuition_consumer(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/frontend-route-mapping/SKILL.md")
    assert "interaction-intuition" in body, (
        "frontend-route-mapping must name interaction-intuition as a downstream consumer of ROUTE_MAP.md"
    )
    assert "Phase −1D" in body, "frontend-route-mapping must reference Phase −1D"


# ─── design-fidelity-mapping skill ─────────────────────────────────────────


def test_design_mapping_skill_names_intuition_consumer(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "skills/design-fidelity-mapping/SKILL.md")
    assert "interaction-intuition" in body, (
        "design-fidelity-mapping must name interaction-intuition as a downstream consumer of DESIGN_MAP.md"
    )


# ─── route-mapper agent ────────────────────────────────────────────────────


def test_route_mapper_agent_names_intuiter_downstream(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "agents/route-mapper.md")
    assert "interaction-intuiter" in body, (
        "route-mapper agent must note that its output feeds interaction-intuiter at Phase −1D"
    )


# ─── command file ──────────────────────────────────────────────────────────


def test_command_proposal_first_bullet_names_domain_gates(plugin_root: Path) -> None:
    """commands/architect-team.md's --proposal-first bullet must clarify the domain-gate carve-out."""
    path = plugin_root / "commands" / "architect-team.md"
    assert path.exists()
    fm, body = frontmatter.parse(path)
    # Anchor on the bullet form `- \`--proposal-first\``, which only matches the actual flag bullet
    # (NOT the natural-language trigger paragraph above it, which mentions `--proposal-first` as text).
    bullet_anchor = body.find("- `--proposal-first`")
    assert bullet_anchor >= 0, (
        "command file must have a `- \\`--proposal-first\\`` flag bullet"
    )
    # The bullet runs until the next `\n- ` or the next blank-line + section.
    next_bullet = body.find("\n- ", bullet_anchor + 1)
    bullet = body[bullet_anchor:next_bullet] if next_bullet > 0 else body[bullet_anchor:bullet_anchor + 2000]
    assert "domain gate" in bullet.lower(), (
        "--proposal-first bullet must clarify domain gates fire regardless of this flag"
    )
    assert "Phase −1D" in bullet, "--proposal-first bullet must name Phase −1D as a domain gate"
