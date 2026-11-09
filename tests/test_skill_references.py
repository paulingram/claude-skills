"""Reference-extraction contract for the largest skills (REQ-005).

Deep, rarely-fired per-phase procedure detail is extracted from the largest
``skills/*/SKILL.md`` files into per-skill ``references/<id>.md`` blocks, each left
behind as a ``> **STOP.**`` pointer plus a ``## Reference index`` table. Extraction
keeps every heading (so cross-reference anchors still resolve) and — per the
mission's conservatism mandate — keeps every gate / discipline inline; only
behavior-neutral deep procedure detail moves.

Target and recorded before/after byte counts (the mission's "record before/after"):

    common-pipeline-conventions : 259290 -> 258442  (-848)   [Auto-worktree lifecycle]

The recorded counts are LF-normalized (the form the index carries). The repo runs
`core.autocrlf=true`, so a Windows working tree measures one extra byte per line
and this pin reads red there — a known platform artifact of `read_bytes()`, not a
regrowth. v3.47.0 grew the body by the declared-gates + spec-currency disciplines
and the compiled principles clause, then the adversarial-batch corrections (248657 -> 256080) and the
v3.59.0 evidence-integrity clause + v3.59.2 doc sweep (259281 -> 259250; the clause rode the
compiled principles block and the live-environment pointer was trimmed ~109 bytes to absorb it,
every trimmed detail verified present in references/local-dev-test-discipline.md). Before that
the v3.57.0 local->dev->test-on-dev discipline (258442 -> 259281; its bulk went straight to
references/local-dev-test-discipline.md, so the SKILL body took only the pointer and the
file still sits under the 259290 pre-extraction baseline). Before that the
v3.48.0 contract-first-parallelism canonical section (256080 -> 258442, a NEW cross-pipeline
discipline which the extraction mission's own 'keep every gate/discipline inline' rule requires to
stay in the body; its full protocol lives in skills/contract-first-parallelism/), still under
the baseline.

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
# Byte counts are LF-normalized (see the module docstring).
EXTRACTIONS = {
    # Byte ledger — APPEND transitions, never rewrite (the v3.59.3 lesson: a
    # rewritten ledger line misattributes which release spent the bytes).
    #   v3.42.0 extraction:   before 259290 -> after 259250 (the original move)
    #   v3.62.0 transition:   259250 -> 259287 (+37: the evidence-binding
    #     contract line in ## Independent review evidence — `task_subject` +
    #     the `<id>.<slug>.json` collision variant; trimmed twice to stay
    #     under the 259290 cap, which is UNCHANGED)
    #   v3.63.0 transition:   259287 -> 259100 (-187 NET, cap still UNCHANGED)
    #     ADDED `## Augment-never-replace discipline (v3.63.0)` as a heading +
    #     STOP pointer only, its full rules extracted to
    #     references/augment-never-replace.md — the section could not be carried
    #     inline at any length, since 259287 against the cap left 2 bytes.
    #     PAID FOR by compressing `## Local -> dev -> test-on-dev ...` (v3.57.0)
    #     to the same heading + STOP-pointer form its siblings already use: its
    #     inline paragraph DUPLICATED references/local-dev-test-discipline.md,
    #     which was already on disk, so no rule text was lost and nothing that
    #     cites the section by heading was disturbed. Making room by extraction
    #     is this regime's own mechanism; raising the cap would have defeated it.
    #   v3.66.0 transition:   259100 -> 257358 (-1742 NET, cap still UNCHANGED)
    #     ADDED `## Read this first` (the ranked binding rules, ~2.2 KB — the
    #     instruction-load fix: the rules that matter stop being buried),
    #     `## No self-imposed limits discipline (v3.66.0)` (~1.5 KB) and the
    #     authoring-rules clarifier on `## Operating rules`, which together
    #     took the file to 263699 — 4409 OVER the cap. PAID FOR by extracting
    #     the v2.5.0 narrative of `## In-flight clarification discipline`
    #     (failure shape, detection-signal table, fold procedure, anti-pattern
    #     rationales, cancellation table, clarifications-log schema — ~9.7 KB,
    #     orchestrator-only relevance that every agent was carrying) to
    #     references/in-flight-clarification-discipline.md behind a STOP
    #     pointer + a one-paragraph inline summary that keeps every phrase the
    #     suite pins; `### Parallel lanes (v3.16.0)` stays INLINE verbatim
    #     because tests/test_parallel_lane_inject.py pins its mechanics there.
    #     Same mechanism as v3.63.0: extraction, not a raised cap.
    #   v3.67.0 transition:   257358 -> 258527 (+1169, cap still UNCHANGED)
    #     ADDED `## Git commit identity discipline (v3.67.0)` in the house
    #     pointer shape — heading + STOP pointer to the NEW
    #     references/git-commit-identity.md + a one-paragraph rule — plus its
    #     Reference-index row. Fits inside the room the v3.66.0 extraction
    #     made; 763 bytes of headroom remain, so the NEXT addition pays by
    #     extraction again.
    #   v4.0.0 transition:    258527 -> 59615 (the constitution split, proposal
    #     change 2): every discipline section over 1300 bytes moved whole into
    #     references/<slug>.md behind a STOP pointer + its first paragraph; the
    #     ranked "Read this first", "No self-imposed limits", the compiled
    #     principles and the structural sections stay inline. This REVERSES the
    #     v3.42.0 "keep every gate/discipline inline" conservatism: the gates
    #     are enforced by hooks and Layer-3 tools, the prose is read on demand,
    #     and tests read the surface (SKILL.md with its chapters spliced in
    #     place -- tests/helpers/surfaces.py), not the raw body.
    #   v4.0.0 doc-debt pass: 59615 -> 63816. Four chapters that other v4.0.0
    #     workers created without a stub (deletion-discipline, test-selection,
    #     converge-workflows, native-methodology) gained their `## ` stub + STOP
    #     pointer + first paragraph and their Reference-index rows, so every
    #     chapter is reachable from the constitution; the Uniform-plugin-usage
    #     stub was reworded for the conditional-plugin / declare-record state.
    "common-pipeline-conventions": ("auto-worktree-lifecycle", 259290, 63816),
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


def _lf_byte_size(path: Path) -> int:
    """Size in LF-normalized bytes — the form the git index carries.

    The repo runs `core.autocrlf=true`, so a Windows working tree holds CRLF and a
    raw `read_bytes()` count exceeds the index form by exactly one byte per line.
    Counting the normalized form makes this assertion platform-independent, so the
    pin can actually PASS on every platform and FAIL only on a real regrowth. Every
    sibling assertion in this file already reads text rather than raw bytes.
    """
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


@pytest.mark.parametrize("skill,data", sorted(EXTRACTIONS.items()))
def test_target_skill_byte_count_reduced_vs_baseline(plugin_root: Path, skill: str, data) -> None:
    ref_id, baseline, recorded_after = data
    current = _lf_byte_size(plugin_root / "skills" / skill / "SKILL.md")
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
