"""Structural tests for the v0.9.25 bug-fix-pipeline planning-validation gate.

v0.9.22 introduced the bug-fix-pipeline; its Phase B3 originally delegated to
the main pipeline's Phase 1 validation gate, but Phase 1's loop conditions are
feature-shaped (authoring NEW Playwright specs, NEW dev-API criteria, NEW
Reuse Decisions for new files) and misfit bug-fix-shaped work where the
replication artifact from B2 IS the Playwright test. v0.9.25 gives the
bug-fix pipeline its OWN slim validation gate fit for bug-fix-shaped work.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_PATH = "skills/bug-fix-pipeline/SKILL.md"


def _read_body(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / SKILL_PATH)
    return body


def _phase_b3_section(body: str) -> str:
    """Return the Phase B3 section (from its header to the next H2)."""
    start = body.find("## Phase B3")
    assert start >= 0, "skill body must have a `## Phase B3` section"
    next_h2 = body.find("\n## ", start + 1)
    return body[start:next_h2] if next_h2 > 0 else body[start:]


def _gate_section(body: str) -> str:
    """Return the Bug-fix planning-validation gate sub-section."""
    start = body.find("### Bug-fix planning-validation gate")
    assert start >= 0, "Phase B3 must contain a `### Bug-fix planning-validation gate` sub-section"
    # The next H3 OR H2 ends the section.
    next_h = -1
    for marker in ("\n### ", "\n## "):
        idx = body.find(marker, start + 1)
        if idx > 0 and (next_h < 0 or idx < next_h):
            next_h = idx
    return body[start:next_h] if next_h > 0 else body[start:]


def test_phase_b3_no_longer_delegates_to_phase_1_gate(plugin_root: Path) -> None:
    """Phase B3 must no longer say 'the Phase 1 planning-validation gate' as the gate to run.

    The v0.9.24-era language said 'Run openspec validate --strict and the Phase 1
    planning-validation gate (the same gate as architect-team-pipeline Phase 1,
    applied to this change)' — that delegation is what v0.9.25 fixed.
    """
    section = _phase_b3_section(_read_body(plugin_root))
    # The exact prior delegation language must be gone.
    assert "the Phase 1 planning-validation gate (the same gate as `architect-team-pipeline` Phase 1, applied to this change)" not in section, (
        "v0.9.25 removed the Phase 1 delegation from Phase B3 — the prior language "
        "must no longer appear in the skill body"
    )


def test_phase_b3_explicitly_says_do_not_delegate(plugin_root: Path) -> None:
    """The skill must explicitly state that B3 does NOT delegate to Phase 1."""
    section = _phase_b3_section(_read_body(plugin_root))
    assert "Do NOT delegate" in section or "do NOT delegate" in section.lower() or "not delegate" in section.lower(), (
        "Phase B3 must explicitly state it does NOT delegate to the main pipeline's Phase 1 gate"
    )
    # And it must explain WHY (feature-shaped conditions trip on bug-fix work).
    assert "feature" in section.lower() and "bug-fix" in section.lower(), (
        "Phase B3 must explain WHY Phase 1's gate doesn't fit (Phase 1 is feature-shaped; B3 is bug-fix-shaped)"
    )


def test_bug_fix_validation_gate_section_exists(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "### Bug-fix planning-validation gate" in body, (
        "Phase B3 must contain a `### Bug-fix planning-validation gate` sub-section"
    )


def test_gate_documents_seven_conditions(plugin_root: Path) -> None:
    """The gate must enumerate exactly seven numbered conditions."""
    section = _gate_section(_read_body(plugin_root))
    # The section must say "seven" (or "7") + the conditions must be numbered 1..7.
    assert "seven" in section.lower() or "7" in section, (
        "gate section must state the condition count (seven)"
    )
    # Each numbered marker should appear once at the start of its line content.
    for n in range(1, 8):
        marker = f"{n}. **"
        assert marker in section, f"condition {n} (`{marker}...`) must be enumerated in the gate"


GATE_CONDITION_KEYWORDS = (
    ("OpenSpec validates", "condition 1 — openspec validate --strict passes"),
    ("Every artifact is done", "condition 2 — every artifact status is `done`"),
    ("at least one source requirement", "condition 3 — coverage map has a source requirement"),
    ("replication artifact paths", "condition 4 — coverage map records replication artifact paths"),
    ("Reuse-first compliance", "condition 5 — reuse-first compliance"),
    ("WHY cites the replication evidence", "condition 6 — proposal WHY cites verbatim evidence"),
    ("class*-scoped", "condition 7 — proposed fix is class-scoped"),
)


@pytest.mark.parametrize("phrase,description", GATE_CONDITION_KEYWORDS)
def test_gate_condition_present(plugin_root: Path, phrase: str, description: str) -> None:
    section = _gate_section(_read_body(plugin_root))
    assert phrase in section, f"gate must name {description} — looked for substring `{phrase}`"


def test_gate_distinguishes_frontend_vs_backend_artifact_requirements(plugin_root: Path) -> None:
    """Condition 4 must spell out that frontend/both bugs need BOTH artifacts;
    backend-only bugs need just the script."""
    section = _gate_section(_read_body(plugin_root))
    # Both keywords must appear in close proximity to "Playwright" + "backend diagnostic"/"backend script".
    assert "Playwright" in section, "gate must name Playwright as an artifact type"
    assert "backend diagnostic" in section.lower() or "backend script" in section.lower(), (
        "gate must name the backend artifact"
    )
    # The both-vs-only language MUST be explicit.
    assert "BOTH" in section, "gate must use 'BOTH' to make the dual-artifact rule unambiguous for frontend/both-layer bugs"


def test_gate_loop_exit_behavior_documented(plugin_root: Path) -> None:
    """The gate must document its loop behavior — refine + re-run until all conditions pass."""
    section = _gate_section(_read_body(plugin_root))
    # The "loop until all are true" language.
    assert "loops" in section.lower() and "until" in section.lower(), (
        "gate must document the loop-until-pass behavior"
    )
    # And the exit-to-Phase-B4 transition.
    assert "Phase B4" in section, (
        "gate must name Phase B4 (Generalization Audit) as the next phase after the gate exits"
    )


def test_gate_explains_why_not_phase_1(plugin_root: Path) -> None:
    """The gate section must include a 'Why not reuse Phase 1's gate?' rationale block."""
    section = _gate_section(_read_body(plugin_root))
    assert "Why not reuse Phase 1" in section or "Why not reuse the Phase 1" in section, (
        "gate section must include a 'Why not reuse Phase 1's gate?' rationale block"
    )


def test_gate_auto_mines_coverage_map(plugin_root: Path) -> None:
    """The gate must auto-mine the validated coverage map to MemPalace."""
    section = _gate_section(_read_body(plugin_root))
    assert "mempalace" in section.lower() and "mine" in section.lower(), (
        "gate must auto-mine the validated coverage map to MemPalace"
    )
    assert "coverage-map.json" in section, (
        "gate must name the coverage-map.json artifact in its mine command"
    )
