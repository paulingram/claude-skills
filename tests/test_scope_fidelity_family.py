# -*- coding: utf-8 -*-
"""v3.10.0 (R1c) — the `## Scope-fidelity discipline family (v3.10.0)` CPC section.

Asserts the canonical family section exists in
`skills/common-pipeline-conventions/SKILL.md` and:
1. names the five member disciplines as one family,
2. states the shared 3-disposition model (fixed-with-commit / SR-routed / confirmed-stub),
3. carries a WHEN-each-fires comparison table preserving the firing-moment distinctions.

Stdlib-only; structural (narrative-pinning per Decision 4 — pins the RULE tokens,
not removed narrative).
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CPC = REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md"


def _section() -> str:
    body = CPC.read_text(encoding="utf-8")
    marker = "## Scope-fidelity discipline family (v3.10.0)"
    assert marker in body, "the CPC must carry the Scope-fidelity discipline family section"
    start = body.index(marker)
    rest = body[start:]
    nxt = rest.find("\n## ", 1)
    return rest if nxt == -1 else rest[:nxt]


def test_family_section_present() -> None:
    section = _section()
    assert section.startswith("## Scope-fidelity discipline family (v3.10.0)")


@pytest.mark.parametrize(
    "version",
    ["v0.9.36", "v1.4.0", "v2.8.0", "v2.10.0", "v2.14.0"],
)
def test_family_names_all_five_members(version: str) -> None:
    section = _section()
    assert version in section, f"the family table must name the {version} member"


def test_family_states_3_disposition_model() -> None:
    section = _section().lower()
    # the 3 dispositions: fixed-with-commit / SR-routed / confirmed-stub
    assert "3-disposition" in section or "three disposition" in section or \
        ("fixed in this change" in section and "confirmed-stub" in section)
    assert "sr" in section and "confirmed-stub" in section
    assert "commit" in section, "fixed-with-commit-citation disposition must be named"


def test_family_has_firing_moment_table() -> None:
    section = _section()
    # the comparison table preserves the per-member firing moments
    assert "Firing moment" in section or "firing moment" in section.lower()
    for moment in ("intake", "commit", "end-of-run", "implementation"):
        assert moment in section.lower(), f"firing moment {moment!r} must be preserved"
    # it's a markdown table
    assert section.count("|") >= 12, "the family section must carry a comparison table"


def test_family_references_unilateral_override_meta() -> None:
    """The v3.0.0 META layer over the family is cross-referenced (without creating a
    `## Unilateral-override discipline` header collision)."""
    section = _section()
    assert "v3.0.0" in section and "override" in section.lower()
