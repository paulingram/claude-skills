"""Reference-extraction contract for the largest skills (REQ-005).

Deep, rarely-fired per-phase procedure detail is extracted from the largest
``skills/*/SKILL.md`` files into per-skill ``references/<id>.md`` blocks, each left
behind as a ``> **STOP.**`` pointer plus a ``## Reference index`` table. Extraction
keeps every heading (so cross-reference anchors still resolve) and — per the
mission's conservatism mandate — keeps every gate / discipline inline; only
behavior-neutral deep procedure detail moves.

Target and recorded before/after byte counts (the mission's "record before/after"):

    common-pipeline-conventions : 259290 -> 248657  (-10633)  [Auto-worktree lifecycle]

HONEST DIVERGENCE — the other two of the three largest skills (architect-team-pipeline
133226 B, bug-fix-pipeline 89329 B) are NOT targets. They are the pipeline
orchestrators, and exhaustive per-block analysis (verified against the full discipline
test-suite) found every substantial block in each to be one of: a gate (Phase 8's
deploy-mandate / unilateral-override / doc-currency gates; bug-fix Phase B4 / B6 / B8
gates), a discipline (Structured bug-isolation; run-state; operating rules), or wiring
whose tokens the suite grep-pins anywhere in the body (notifications, agent-resume,
Layer-3 tool invocations, INTERACTION_INTUITION_MAP binding-input). The mission's
"keep every gate/discipline inline" rule requires all of those to stay in the body.
The only behavior-neutral candidate blocks that remain — architect-team-pipeline's
Phase 4 (897 B) and bug-fix-pipeline's "Relationship to other skills" (1262 B) — are
each smaller than the mandated principles block this run injects (1381 B), so no
conservative extraction can net-reduce either without either breaking the suite or
moving a discipline out of the skill body. Both are forbidden, so this test asserts
the one skill (common-pipeline-conventions) that carries a genuinely
behavior-neutral, rarely-fired, test-safe heavy block.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# skill dir -> (reference id, pre-change baseline bytes, recorded after bytes)
EXTRACTIONS = {
    "common-pipeline-conventions": ("auto-worktree-lifecycle", 259290, 248657),
}

# the STOP pointer's cited-path grammar: > **STOP.** ... Read `<path>` ...
_POINTER_RE = re.compile(r">\s*\*\*STOP\.\*\*.*?Read\s+`([^`]+)`", re.DOTALL)


def _section_body(text: str, heading: str) -> str:
    """The body (excluding the heading line) of the '## heading' section."""
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if l.rstrip() == heading)
    end = next(
        (i for i in range(start + 1, len(lines))
         if lines[i].startswith("## ") and lines[i].rstrip() != heading),
        len(lines),
    )
    return "\n".join(lines[start + 1:end]).strip()


@pytest.mark.parametrize("skill,data", sorted(EXTRACTIONS.items()))
def test_extracted_reference_file_exists_and_is_nontrivial(plugin_root: Path, skill: str, data) -> None:
    ref_id, _, _ = data
    ref = plugin_root / "skills" / skill / "references" / f"{ref_id}.md"
    assert ref.exists(), f"missing extracted reference file: {ref}"
    body = ref.read_text(encoding="utf-8")
    assert len(body.encode("utf-8")) > 800, f"{ref}: extracted reference looks too small to be a real block"
    assert body.startswith("# "), f"{ref}: reference file must open with an H1 title"


@pytest.mark.parametrize("skill", sorted(EXTRACTIONS))
def test_skill_has_reference_index(plugin_root: Path, skill: str) -> None:
    text = (plugin_root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "## Reference index" in text, f"{skill}: missing the '## Reference index' section"
    ref_id = EXTRACTIONS[skill][0]
    assert f"references/{ref_id}.md" in text, (
        f"{skill}: Reference index does not cite references/{ref_id}.md"
    )


@pytest.mark.parametrize("skill", sorted(EXTRACTIONS))
def test_every_stop_pointer_resolves(plugin_root: Path, skill: str) -> None:
    """Every `> **STOP.**` pointer in a modified skill cites a real file on disk."""
    text = (plugin_root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    cited = _POINTER_RE.findall(text)
    assert cited, f"{skill}: no STOP pointer found"
    for rel in cited:
        assert (plugin_root / rel).exists(), f"{skill}: STOP pointer cites a non-existent file: {rel}"


@pytest.mark.parametrize("skill,data", sorted(EXTRACTIONS.items()))
def test_target_skill_byte_count_reduced_vs_baseline(plugin_root: Path, skill: str, data) -> None:
    ref_id, baseline, recorded_after = data
    current = len((plugin_root / "skills" / skill / "SKILL.md").read_bytes())
    assert current < baseline, (
        f"{skill}: current {current} bytes is not reduced vs baseline {baseline}"
    )
    # the recorded 'after' must stay accurate (guards a silent regrowth of the skill)
    assert current == recorded_after, (
        f"{skill}: current {current} bytes != recorded after {recorded_after}; "
        f"update the recorded before/after in EXTRACTIONS if this change is intended"
    )


@pytest.mark.parametrize("skill,data", sorted(EXTRACTIONS.items()))
def test_deep_detail_moved_out_not_duplicated(plugin_root: Path, skill: str, data) -> None:
    """The extracted section in the skill is now just the STOP pointer (the deep
    detail lives in the reference, not duplicated in the skill body)."""
    ref_id = data[0]
    skill_text = (plugin_root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    ref_body = (plugin_root / "skills" / skill / "references" / f"{ref_id}.md").read_text(encoding="utf-8")
    # locate the section whose pointer cites this reference
    heading = None
    for m in re.finditer(r"^(## .+)$", skill_text, flags=re.MULTILINE):
        h = m.group(1).rstrip()
        body = _section_body(skill_text, h)
        if f"references/{ref_id}.md" in body and "**STOP.**" in body:
            heading = h
            break
    assert heading is not None, f"{skill}: could not find the extracted section pointing at {ref_id}"
    remaining = _section_body(skill_text, heading)
    assert "**STOP.**" in remaining, f"{skill}: the extracted section must carry the STOP pointer"
    # the remaining in-skill body is far smaller than the moved reference body
    assert len(remaining.encode("utf-8")) < len(ref_body.encode("utf-8")) // 2, (
        f"{skill}: the section body did not shrink — extraction may have duplicated rather than moved detail"
    )
