"""REQ-2 (skill-side audit): no nested-team patterns in the pipeline SKILL.md bodies.

Per the Agent Teams docs' "no nested teams" constraint and REQ-2:
  - No teammate role-definition or skill body claims that a non-Lead agent
    spawns its own team.
  - When a sentence in a skill body uses spawn / dispatch language, it MUST be
    framed as the LEAD owning the dispatch — either creating tasks in the
    shared list (teams mode) OR dispatching subagents (subagents mode).

This file audits the three pipeline SKILL.md bodies for the 8 enumerated
nested-team patterns (REQ-2 scenarios 2.1 — 2.7) and asserts every
spawn / dispatch sentence is Lead-owned.

The audit uses a structured allowlist: matches against the forbidden regex
must ALSO match one of the LEGAL Lead-owned phrasings.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.helpers import frontmatter


PIPELINE_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
)


# Patterns that suggest a nested-team / non-Lead spawn. These are the
# sentence-level patterns REQ-2 forbids when not Lead-attributed.
FORBIDDEN_PATTERNS = (
    r"spawn\s+\d+\s+\w[\w-]*\s+agents?\s+in\s+parallel",
    r"spawn\s+three\s+\w[\w-]*\s+agents?",
    r"dispatch\s+the\s+\w[\w-]*\s+team\b",
    r"dispatch\s+a\s+\w[\w-]*\s+team\b",
)


# When a spawn / dispatch sentence DOES appear, it must contain at least one of
# these Lead-owned anchors to make clear the Lead is the actor.
LEAD_OWNED_ANCHORS = (
    "the Lead",
    "The Lead",
    "the lead",  # tolerate sentence-internal lowercase
    "Lead creates",
    "Lead dispatches",
    "Lead adds",
    "Lead assigns",
    "Lead-owned",
    "Lead spawns",
    "orchestrator",  # the orchestrator IS the Lead in this codebase
    "Orchestrator",
)


def _skill_path(plugin_root: Path, skill_name: str) -> Path:
    return plugin_root / "skills" / skill_name / "SKILL.md"


def _read_body(plugin_root: Path, skill_name: str) -> str:
    _, body = frontmatter.parse(_skill_path(plugin_root, skill_name))
    return body


def _sentences_containing(body: str, pattern: str) -> list[str]:
    """Return all 'sentences' (paragraph lines or markdown bullet lines) that
    contain a regex match for `pattern`. Sentence boundaries are conservative —
    we split on blank lines AND on bullet boundaries to keep matches with the
    enclosing claim, which is what determines whether the Lead is the actor."""
    matches: list[str] = []
    # Walk paragraph-by-paragraph; within each paragraph walk line-by-line, and
    # also accept multi-sentence lines (split on '. ' too).
    rx = re.compile(pattern, flags=re.IGNORECASE)
    for paragraph in body.split("\n\n"):
        for line in paragraph.splitlines():
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                if rx.search(sentence):
                    matches.append(sentence.strip())
    return matches


def _is_lead_owned(sentence: str) -> bool:
    """True if the sentence contains a Lead-owned anchor."""
    return any(anchor in sentence for anchor in LEAD_OWNED_ANCHORS)


# ---- Scenario: zero unattributed nested-team patterns -----------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
@pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS)
def test_no_unattributed_spawn_or_dispatch_pattern(
    plugin_root: Path, skill_name: str, pattern: str
) -> None:
    """Every spawn / dispatch sentence MUST be Lead-attributed.

    The audit runs each forbidden regex against the skill body; for each
    matching sentence the test asserts a Lead-owned anchor is present in the
    same sentence. A match that lacks the anchor is a nested-team failure."""
    body = _read_body(plugin_root, skill_name)
    bad: list[str] = []
    for sentence in _sentences_containing(body, pattern):
        if not _is_lead_owned(sentence):
            bad.append(sentence)
    assert not bad, (
        f"{skill_name}: pattern /{pattern}/ matched sentence(s) WITHOUT a "
        f"Lead-owned anchor — nested-team failure. Offending sentence(s):\n  "
        + "\n  ".join(bad)
    )


# ---- Scenario 2.1 / 2.2 / 2.4 / 2.5 / 2.6 (architect-team-pipeline body) -----


# A "dispatch sentence" is a sentence that names a count + role + dispatch verb
# (e.g., "creates 3 codebase-map-reviewer tasks", "dispatches 3 ... subagents").
# It is NOT a catalog sentence ("the named subagent definitions are: A, B, C, ...").
# Pattern: the role token appears within 60 chars of an active dispatch verb.
DISPATCH_VERB_RX = re.compile(
    r"\b(spawn(?:s|ed|ing)?|dispatch(?:es|ed|ing)?|create(?:s|d)?|assign(?:s|ed)?|invoke(?:s|d)?|re-?creates?|re-?dispatch(?:es)?)\b",
    flags=re.IGNORECASE,
)


def _dispatch_sentences_for(body: str, role: str) -> list[str]:
    """Return sentences in `body` where `role` appears AND a dispatch verb appears
    AND the verb is within 80 chars of the role mention (to filter out catalog
    sentences where the role appears in a comma-separated list of definitions)."""
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if role not in sentence:
            continue
        # Find every role index; find every verb index; check proximity.
        role_indices = [m.start() for m in re.finditer(re.escape(role), sentence)]
        verb_indices = [m.start() for m in DISPATCH_VERB_RX.finditer(sentence)]
        if not verb_indices:
            continue
        # Catalog filter: if the role is one item in a long comma list of
        # backtick-wrapped names, skip — the verb is generic.
        if re.search(rf",\s*`{re.escape(role)}`\s*,", sentence) or re.search(rf",\s*`{re.escape(role)}`\s*\)", sentence):
            continue
        if any(abs(ri - vi) <= 120 for ri in role_indices for vi in verb_indices):
            out.append(sentence)
    return out


def test_codebase_map_reviewer_dispatch_is_lead_owned(plugin_root: Path) -> None:
    """REQ-2 Scenario 2.5: codebase-map-reviewer ×3 → Lead-owned."""
    body = _read_body(plugin_root, "architect-team-pipeline")
    found = _dispatch_sentences_for(body, "codebase-map-reviewer")
    assert found, "expected at least one sentence describing codebase-map-reviewer dispatch"
    for s in found:
        assert _is_lead_owned(s), (
            f"codebase-map-reviewer dispatch sentence is not Lead-owned: {s!r}"
        )


def test_integration_explorer_dispatch_is_lead_owned(plugin_root: Path) -> None:
    """REQ-2 Scenario 2.6: integration-explorer ×3 + master-synthesizer → Lead-owned."""
    body = _read_body(plugin_root, "architect-team-pipeline")
    found = _dispatch_sentences_for(body, "integration-explorer")
    assert found, "expected at least one sentence describing integration-explorer dispatch"
    for s in found:
        assert _is_lead_owned(s), (
            f"integration-explorer dispatch sentence is not Lead-owned: {s!r}"
        )


def test_task_reviewer_dispatch_is_lead_owned(plugin_root: Path) -> None:
    """REQ-2 Scenario 2.1: task-reviewer ×3 → Lead-owned."""
    body = _read_body(plugin_root, "architect-team-pipeline")
    found = _dispatch_sentences_for(body, "task-reviewer")
    assert found, "expected at least one sentence describing task-reviewer dispatch"
    for s in found:
        assert _is_lead_owned(s), (
            f"task-reviewer dispatch sentence is not Lead-owned: {s!r}"
        )


def test_editability_reviewer_dispatch_is_lead_owned(plugin_root: Path) -> None:
    """REQ-2 Scenario 2.2: editability-reviewer ×3 → Lead-owned."""
    body = _read_body(plugin_root, "architect-team-pipeline")
    found = _dispatch_sentences_for(body, "editability-reviewer")
    assert found, "expected at least one sentence describing editability-reviewer dispatch"
    for s in found:
        assert _is_lead_owned(s), (
            f"editability-reviewer dispatch sentence is not Lead-owned: {s!r}"
        )


def test_interaction_reviewer_dispatch_is_lead_owned(plugin_root: Path) -> None:
    """REQ-2: interaction-reviewer ×3 → Lead-owned (sibling to editability)."""
    body = _read_body(plugin_root, "architect-team-pipeline")
    found = _dispatch_sentences_for(body, "interaction-reviewer")
    assert found, "expected at least one sentence describing interaction-reviewer dispatch"
    for s in found:
        assert _is_lead_owned(s), (
            f"interaction-reviewer dispatch sentence is not Lead-owned: {s!r}"
        )


def test_diagnostic_researcher_dispatch_is_lead_owned(plugin_root: Path) -> None:
    """REQ-2 Scenario 2.4: diagnostic-research-team ×3 → Lead-owned."""
    body = _read_body(plugin_root, "architect-team-pipeline")
    # The skill references 'diagnostic-researcher' (the agent) AND
    # 'diagnostic-research-team' (the skill). Either flavor of dispatch
    # mention must be Lead-attributed.
    found = _dispatch_sentences_for(body, "diagnostic-researcher")
    found += _dispatch_sentences_for(body, "diagnostic-research-team")
    assert found, "expected at least one sentence describing diagnostic-researcher dispatch"
    for s in found:
        assert _is_lead_owned(s), (
            f"diagnostic-researcher dispatch sentence is not Lead-owned: {s!r}"
        )


# ---- Scenario 2.3 (visual-capture + visual-analyzer in architect pipeline) --


def test_visual_capture_and_analyzer_is_lead_owned(plugin_root: Path) -> None:
    """REQ-2 Scenario 2.3: visual-capture + visual-analyzer → Lead-owned (no team-internal spawn)."""
    body = _read_body(plugin_root, "architect-team-pipeline")
    found = (
        _dispatch_sentences_for(body, "visual-capture")
        + _dispatch_sentences_for(body, "visual-analyzer")
        + _dispatch_sentences_for(body, "visual-verification-team")
    )
    assert found, "expected at least one sentence describing visual-capture / visual-analyzer dispatch"
    for s in found:
        assert _is_lead_owned(s), (
            f"visual-capture/analyzer dispatch sentence is not Lead-owned: {s!r}"
        )


# ---- Negative audit (the grep audit) -----------------------------------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_no_first_person_spawn_a_team_claim(
    plugin_root: Path, skill_name: str
) -> None:
    """A skill body MUST NOT contain first-person 'I spawn the team' phrasings —
    that pattern is the agent-body anti-pattern REQ-2 forbids. The skill body
    is the orchestrator's playbook; first-person 'I' here is fine only when it
    refers to the Lead. But the explicit pattern 'I (will )?spawn .* team' is
    what the spec-level audit greps against."""
    body = _read_body(plugin_root, skill_name)
    forbidden = re.findall(
        r"\bI\s+(?:will\s+)?spawn\s+(?:the\s+)?\w[\w-]*\s+team\b",
        body,
        flags=re.IGNORECASE,
    )
    assert not forbidden, (
        f"{skill_name}: found first-person 'I spawn the <X> team' claim(s) — "
        f"REQ-2 forbids this in skill bodies. Matches: {forbidden}"
    )


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_lead_owns_dispatch_language_appears(
    plugin_root: Path, skill_name: str
) -> None:
    """Every pipeline skill MUST contain at least one explicit Lead-owned
    dispatch sentence — proving the rewrite has been applied."""
    body = _read_body(plugin_root, skill_name)
    # The skill is allowed to say "the Lead" / "the orchestrator" anywhere; we
    # just want to confirm at least one Lead-owned dispatch sentence exists.
    body_lower = body.lower()
    assert "the lead" in body_lower or "orchestrator" in body_lower, (
        f"{skill_name}: skill body must contain at least one explicit reference "
        "to the Lead / orchestrator owning the dispatch"
    )


# ---- Mode-aware dispatch language (the C4 rewrite signature) ---------------


@pytest.mark.parametrize("skill_name", PIPELINE_SKILLS)
def test_skill_describes_mode_aware_dispatch(
    plugin_root: Path, skill_name: str
) -> None:
    """The C4 rewrite produces sentences that describe BOTH teams-mode and
    subagents-mode dispatch in the same passage. At least one such mode-aware
    sentence must be present in the skill body (proving the rewrite landed)."""
    body = _read_body(plugin_root, skill_name)
    body_lower = body.lower()
    # The canonical phrasings are 'teams mode' and 'subagents mode'. Both
    # tokens must appear in the body so a reader can find the mode split.
    assert "teams mode" in body_lower, (
        f"{skill_name}: skill body must reference 'teams mode' (the mode-aware "
        "dispatch language from the C4 rewrite)"
    )
    assert "subagents mode" in body_lower, (
        f"{skill_name}: skill body must reference 'subagents mode' (the mode-aware "
        "dispatch language from the C4 rewrite)"
    )
