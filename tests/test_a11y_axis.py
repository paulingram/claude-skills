# -*- coding: utf-8 -*-
"""v3.10.0 (R6b) — the interaction-completeness accessibility axis.

Asserts:
1. `skills/interaction-completeness/SKILL.md` carries `## Accessibility axis (v3.10.0)`
   with keyboard-reachability / accessible-names / axe-core-via-Playwright, the
   `a11y-gap` sub-kind vocabulary, the `a11y-gap` SR origin kind, and the no-UI
   n/a rule.
2. `agents/interaction-reviewer.md` carries the matching `## Accessibility audit
   (v3.10.0)` section with the same vocabulary + n/a rule.

Stdlib-only; structural.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "interaction-completeness" / "SKILL.md"
REVIEWER = REPO_ROOT / "agents" / "interaction-reviewer.md"

A11Y_SUBKINDS = ("keyboard-unreachable", "missing-accessible-name", "axe-violation")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---- 1. the skill section ---------------------------------------------------


def test_skill_has_accessibility_axis_section() -> None:
    body = _read(SKILL)
    assert "## Accessibility axis (v3.10.0)" in body


def test_skill_axis_covers_the_three_audits() -> None:
    body = _read(SKILL).lower()
    assert "keyboard" in body and "reachab" in body, "keyboard reachability must be named"
    assert "accessible name" in body, "accessible names must be named"
    assert "axe-core" in body and "playwright" in body, "axe-core via Playwright must be named"


@pytest.mark.parametrize("sub_kind", A11Y_SUBKINDS)
def test_skill_names_a11y_subkinds(sub_kind: str) -> None:
    body = _read(SKILL)
    assert sub_kind in body, f"the skill must name the a11y sub-kind {sub_kind!r}"


def test_skill_names_a11y_gap_origin_kind() -> None:
    body = _read(SKILL)
    assert "a11y-gap" in body, "the skill must name the a11y-gap SR origin kind"
    assert 'origin.kind: "a11y-gap"' in body or "origin.kind: `a11y-gap`" in body or \
        "`a11y-gap` solution requirement" in body


def test_skill_states_no_ui_na_rule() -> None:
    body = _read(SKILL).lower()
    assert "n/a" in body and "no ui" in body, "the no-UI n/a rule must be stated"


# ---- 2. the agent audit section --------------------------------------------


def test_reviewer_has_accessibility_audit_section() -> None:
    body = _read(REVIEWER)
    assert "## Accessibility audit (v3.10.0)" in body


@pytest.mark.parametrize("sub_kind", A11Y_SUBKINDS)
def test_reviewer_names_a11y_subkinds(sub_kind: str) -> None:
    body = _read(REVIEWER)
    assert sub_kind in body, f"the reviewer must name the a11y sub-kind {sub_kind!r}"


def test_reviewer_names_a11y_findings_block_and_origin() -> None:
    body = _read(REVIEWER)
    assert "a11y_findings" in body, "the reviewer must write an a11y_findings block"
    assert "a11y-gap" in body, "the reviewer must route an a11y-gap SR"


def test_reviewer_states_no_ui_na_rule() -> None:
    body = _read(REVIEWER).lower()
    assert "n/a" in body and "no ui surface" in body, "the no-UI n/a rule must be stated"
