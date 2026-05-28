"""Structural audits for the v1.4.0 scope-discipline change.

Asserts:
1. `skills/common-pipeline-conventions/SKILL.md` carries the canonical
   `## Scope discipline` section exactly once, naming the anti-pattern,
   the 6 parity-implying verbs, the AskUserQuestion surfacing pattern,
   the explicit forbidden patterns, and the v0.9.36 contrast.
2. Each of the 3 pipeline SKILL.md bodies references the canonical section.
3. `agents/prompt-refiner.md` documents the 6th `scope-fidelity` axis +
   updates the grade-schema JSON example.
4. `skills/proposal-refiner/SKILL.md` Phase R2 documents the 6th axis in the
   grade-schema JSON.
5. `agents/bug-classifier.md` carries an action-verb interpretation section.
6. `agents/system-architect.md` Master Review Audit mode + Phase 2 architect
   brief sections name the scope-narrowing check.

The audits are grep-style — they verify the discipline is documented in the
right places. A change that adds the discipline runtime detector in a future
v1.x would add additional behavioral tests; v1.4.0 is documentation +
structural.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


PIPELINE_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
)


PARITY_VERBS = (
    "match",
    "rebuild",
    "mirror",
    "parity",
    "make like",
    "replicate",
)


def _read_skill_body(plugin_root: Path, skill_name: str) -> str:
    path = plugin_root / "skills" / skill_name / "SKILL.md"
    _, body = frontmatter.parse(path)
    return body


def _read_agent_body(plugin_root: Path, agent_name: str) -> str:
    path = plugin_root / "agents" / f"{agent_name}.md"
    _, body = frontmatter.parse(path)
    return body


# ---- common-pipeline-conventions: the canonical home ------------------------


def test_common_pipeline_conventions_has_scope_discipline_section_exactly_once(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 1: the canonical section exists exactly once."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    occurrences = body.count("## Scope discipline")
    assert occurrences == 1, (
        f"expected `## Scope discipline` to appear exactly once in "
        f"common-pipeline-conventions/SKILL.md, found {occurrences}"
    )


def test_scope_discipline_section_names_anti_pattern_explicitly(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 2: the anti-pattern is explicitly named ('silently narrowing')."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    # The section must name the anti-pattern using the phrase "silently
    # narrowing" (the canonical handle in the proposal + the user's reported
    # failure mode).
    assert "silently narrow" in body.lower(), (
        "the canonical `## Scope discipline` section must explicitly name "
        "the anti-pattern as 'silently narrowing' (the phrase the proposal + "
        "the user's reported failure mode use)."
    )


def test_scope_discipline_section_contrasts_with_v0_9_36_anti_deferral(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 2 (b): the section contrasts the scope-narrowing anti-pattern
    with the v0.9.36 anti-deferral discipline (same shape, fired earlier)."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    # The v0.9.36 anti-deferral comparison must appear inside the Scope
    # discipline section, not just anywhere in the skill body.
    section_start = body.index("## Scope discipline")
    # Find the next H2 heading or EOF.
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    assert "v0.9.36" in section, (
        "the Scope discipline section must contrast the v1.4.0 scope-narrowing "
        "discipline with the v0.9.36 anti-deferral discipline (same shape, "
        "fired earlier in the timeline)"
    )


@pytest.mark.parametrize("verb", PARITY_VERBS)
def test_scope_discipline_section_lists_each_parity_verb(
    plugin_root: Path, verb: str
) -> None:
    """REQ-1 Scenario 3: each of the 6 parity-implying verbs appears in the section."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section_start = body.index("## Scope discipline")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    # The verb appears either as `**match**` (table row), as a quoted phrase,
    # or as plain prose — we just need to confirm it's there at least once.
    assert verb in section.lower(), (
        f"the parity-implying verb '{verb}' must appear in the canonical "
        f"`## Scope discipline` section (it is one of the 6 v1.4.0 verbs)"
    )


def test_scope_discipline_section_documents_visual_structural_behavioral_parity(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 3 (b): the section states that the verbs imply visual +
    structural + behavioral parity (not data-only / partial)."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section_start = body.index("## Scope discipline")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    # The phrase "visual + structural + behavioral parity" (or close prose)
    # MUST appear so a reader knows the verbs imply full parity.
    assert "visual + structural + behavioral parity" in section.lower(), (
        "the canonical section must explicitly state that the parity-implying "
        "verbs imply visual + structural + behavioral parity (not data-only "
        "or partial)"
    )


def test_scope_discipline_section_documents_ask_user_question_surfacing_pattern(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 4: the section instructs the agent to surface the scope
    question via `AskUserQuestion` BEFORE starting work."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section_start = body.index("## Scope discipline")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    # The AskUserQuestion tool name (canonical) MUST appear with surfacing
    # language; merely mentioning "ask the user" is too vague.
    assert "AskUserQuestion" in section, (
        "the canonical section must instruct the agent to surface the scope "
        "decision via the `AskUserQuestion` tool BEFORE starting work"
    )


def test_scope_discipline_section_is_called_a_domain_gate(plugin_root: Path) -> None:
    """REQ-1 Scenario 4 (b): the section explicitly states scope-narrowing IS a
    domain gate (per the v0.9.21 carve-out)."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section_start = body.index("## Scope discipline")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    assert "domain gate" in section.lower(), (
        "the canonical section must state that scope-narrowing IS a domain "
        "gate (so it fires regardless of `--proposal-first`)"
    )


def test_scope_discipline_section_forbids_documented_deferral_patterns(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 5: the section explicitly forbids the four documented
    failure modes (queued-for-next-runs / phase-1-of-N / unilateral-split /
    narrow-then-document)."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section_start = body.index("## Scope discipline")
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    # Three of the four canonical forbidden patterns must appear (substring
    # match, case-insensitive).
    needed = [
        "queued for next runs",
        "phase 1 of N",
        "this run",
        "future runs",
    ]
    missing = [n for n in needed if n.lower() not in section.lower()]
    assert not missing, (
        "the canonical section must explicitly forbid the documented "
        f"deferral patterns; missing language: {missing}"
    )


# ---- 3 pipeline bodies reference the canonical section ----------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_body_references_scope_discipline_section(
    plugin_root: Path, skill_name: str
) -> None:
    """REQ-2 Scenarios 2.1 / 2.2 / 2.3: each of the 3 pipeline bodies references
    the canonical `common-pipeline-conventions` `## Scope discipline` section."""
    body = _read_skill_body(plugin_root, skill_name)
    # Accept either the literal phrase or the canonical reference shape.
    canonical = "common-pipeline-conventions` `## Scope discipline"
    assert canonical in body, (
        f"{skill_name}/SKILL.md must reference the canonical "
        f"`common-pipeline-conventions` `## Scope discipline` section "
        f"(found neither of the accepted phrasings)"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_pipeline_body_mentions_v1_4_0_anti_pattern(
    plugin_root: Path, skill_name: str
) -> None:
    """REQ-2 (corollary): each pipeline body explicitly stamps the rule with the
    v1.4.0 version marker, so a reader knows the rule is the new scope discipline
    and not a generic 'follow the prompt' line."""
    body = _read_skill_body(plugin_root, skill_name)
    assert "v1.4.0" in body, (
        f"{skill_name}/SKILL.md must stamp the scope-discipline entry with the "
        f"v1.4.0 version marker so the source of the rule is auditable"
    )


# ---- prompt-refiner agent has the 6th axis ---------------------------------


def test_prompt_refiner_agent_documents_scope_fidelity_axis(
    plugin_root: Path,
) -> None:
    """REQ-3 Scenario 1: `agents/prompt-refiner.md` body contains the
    `scope-fidelity` substring (the new axis name)."""
    body = _read_agent_body(plugin_root, "prompt-refiner")
    assert "scope-fidelity" in body, (
        "agents/prompt-refiner.md must document the `scope-fidelity` axis "
        "(the 6th v1.4.0 axis)"
    )


def test_prompt_refiner_grade_schema_includes_scope_fidelity(
    plugin_root: Path,
) -> None:
    """REQ-3 Scenario 1 (b): the grade-schema JSON example shows `scope-fidelity`."""
    body = _read_agent_body(plugin_root, "prompt-refiner")
    # The schema example for `axes` must list scope-fidelity alongside the
    # other 5 axes. Look for the substring inside the schema block.
    assert '"scope-fidelity":' in body, (
        "agents/prompt-refiner.md grade-schema example must include "
        "`\"scope-fidelity\":` as one of the `axes` entries"
    )


def test_prompt_refiner_documents_axis_as_domain_gate(plugin_root: Path) -> None:
    """REQ-3 Scenario 2: the body states that a flagged `scope-fidelity` is a
    domain gate (the user MUST be asked to confirm scope before proceeding)."""
    body = _read_agent_body(plugin_root, "prompt-refiner")
    # The discipline must explicitly call the flagged axis a "domain gate" so
    # the agent knows to surface the scope question (rather than treat it as
    # a regular question).
    assert "domain gate" in body.lower(), (
        "agents/prompt-refiner.md must state that a flagged `scope-fidelity` "
        "is a DOMAIN gate — the user MUST be asked to confirm the scope "
        "before the refinement loop proceeds"
    )


# ---- proposal-refiner skill documents the 6th axis -------------------------


def test_proposal_refiner_skill_phase_r2_includes_scope_fidelity(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1: `skills/proposal-refiner/SKILL.md` Phase R2 grade
    schema includes `scope-fidelity`."""
    body = _read_skill_body(plugin_root, "proposal-refiner")
    # Find Phase R2 and confirm the axis appears AFTER it (the schema lives
    # in that section).
    r2_idx = body.find("Phase R2")
    assert r2_idx != -1, "Phase R2 section missing from proposal-refiner skill"
    rest = body[r2_idx:]
    assert "scope-fidelity" in rest, (
        "skills/proposal-refiner/SKILL.md Phase R2 must include `scope-fidelity` "
        "in the grade-schema JSON example"
    )


def test_proposal_refiner_skill_documents_six_axis_weights(plugin_root: Path) -> None:
    """REQ-4 corollary: the skill documents the v1.4.0 weighted-overall formula
    accommodating the 6th axis (sum to 1.0)."""
    body = _read_skill_body(plugin_root, "proposal-refiner")
    # The body should reference ScopeFidelity or scope-fidelity in the weights
    # description.
    assert (
        "ScopeFidelity 0.17" in body or "scope-fidelity*0.17" in body
    ), (
        "skills/proposal-refiner/SKILL.md must document the v1.4.0 weight "
        "redistribution including `ScopeFidelity 0.17` (the new axis's weight)"
    )


# ---- bug-classifier action-verb interpretation -----------------------------


def test_bug_classifier_has_action_verb_interpretation_section(
    plugin_root: Path,
) -> None:
    """REQ-5 Scenario 1: `agents/bug-classifier.md` contains a section on
    action-verb interpretation."""
    body = _read_agent_body(plugin_root, "bug-classifier")
    # The canonical heading for the v1.4.0 addition.
    assert "Action-verb interpretation" in body, (
        "agents/bug-classifier.md must contain an `## Action-verb interpretation` "
        "section documenting the parity-verb rule"
    )


@pytest.mark.parametrize("verb", PARITY_VERBS)
def test_bug_classifier_lists_each_parity_verb(plugin_root: Path, verb: str) -> None:
    """REQ-5 Scenario 1 (b): each of the 6 parity-implying verbs appears in the
    bug-classifier body's action-verb section."""
    body = _read_agent_body(plugin_root, "bug-classifier")
    assert verb in body.lower(), (
        f"agents/bug-classifier.md must list the parity-implying verb '{verb}' "
        f"in its action-verb interpretation section"
    )


def test_bug_classifier_documents_unclear_verdict_routing(plugin_root: Path) -> None:
    """REQ-5 Scenario 1 (c): the body instructs the classifier to return
    `unclear` (with a scope-clarifying question) on a parity-verb prompt with
    narrower-than-literal interpretation."""
    body = _read_agent_body(plugin_root, "bug-classifier")
    # The rule: parity-verb + narrower reading -> kind: unclear. The body must
    # explicitly state this routing.
    assert "unclear" in body and "scope-clarifying" in body.lower(), (
        "agents/bug-classifier.md must document that a parity-verb prompt with "
        "narrower interpretation triggers the `unclear` verdict with a "
        "scope-clarifying question (NOT `bug` or `feature` with silently "
        "narrowed scope)"
    )


# ---- system-architect Master Review Audit + Phase 2 brief ------------------


def test_system_architect_master_review_audit_names_scope_narrowing_check(
    plugin_root: Path,
) -> None:
    """REQ-6 Scenario 1: the Master Review Audit mode references the scope-narrowing
    check (a verdict-failure condition on silent narrowings)."""
    body = _read_agent_body(plugin_root, "system-architect")
    # Find the Master Review Audit section.
    mra_idx = body.find("## Master Review Audit")
    assert mra_idx != -1, "Master Review Audit section missing"
    # Find the next H2 (or EOF).
    rest = body[mra_idx:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    # The section must reference the scope-discipline check AND the v1.4.0
    # rule.
    assert "Scope discipline" in section and "v1.4.0" in section, (
        "system-architect.md Master Review Audit section must reference the "
        "canonical `common-pipeline-conventions` `## Scope discipline` rule "
        "and stamp the addition with the v1.4.0 version marker"
    )


def test_system_architect_master_review_audit_verdict_has_scope_fidelity_finding(
    plugin_root: Path,
) -> None:
    """REQ-6 Scenario 1 (b): the Master Review Audit verdict schema gains a
    `scope_fidelity_finding` block."""
    body = _read_agent_body(plugin_root, "system-architect")
    mra_idx = body.find("## Master Review Audit")
    rest = body[mra_idx:]
    next_h2 = rest.find("\n## ", 1)
    section = rest if next_h2 == -1 else rest[:next_h2]
    assert "scope_fidelity_finding" in section, (
        "the Master Review Audit verdict JSON must include a "
        "`scope_fidelity_finding` field so a silent narrowing produces a "
        "structured finding"
    )


def test_system_architect_phase_2_brief_documents_scope_check(plugin_root: Path) -> None:
    """REQ-6 Scenario 2: the Phase 2 architect brief (default Output mode +
    Core Process) names the scope-narrowing detection rule."""
    body = _read_agent_body(plugin_root, "system-architect")
    # The Output section + Core Process step 2 (the Phase 2 scope check) must
    # both reference scope-discipline. The shortest grep is to confirm both
    # the Output's `Scope check` line and the Core Process scope-check step.
    assert "Scope check" in body, (
        "system-architect.md Output section must include a `Scope check` "
        "structured field documenting the v1.4.0 Phase 2 architect-brief "
        "scope-narrowing detection"
    )
    # The Core Process scope-check step references the canonical section.
    assert "Scope discipline" in body, (
        "system-architect.md Core Process must reference the canonical "
        "`common-pipeline-conventions` `## Scope discipline` rule"
    )
