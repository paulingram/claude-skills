"""ui-interaction-fidelity REQ-010 — dynamic-value-discovery skill structural tests.

Reported gap: a design mockup is full of sample data — a name, a date, a dollar
amount — and a literal implementation hardcodes `"John Smith"` where the context
makes clear it is the logged-in user's name. Nothing in the pipeline — not the
architect specifying it, not the developer building it, not the evaluator
reviewing it — systematically asks "is this a fixed label, or sample data
standing in for a dynamic, data-bound value?" so the UI ships one person's
sample data to everyone.

REQ-010 adds the `dynamic-value-discovery` skill: a cross-role discipline
(modeled on `reuse-first-design`) that classifies every displayed value
`static` vs. `dynamic` FROM CONTEXT — never from the literal itself — mandates
that every `dynamic` value is bound to a named data source rather than the
design's hardcoded sample, and requires escalation when a classification is
genuinely ambiguous.

These tests assert the discipline is present and well-formed so it cannot
silently regress. Registration in `tests/test_skills.py`'s EXPECTED_SKILLS is a
sibling teammate's task and is intentionally NOT asserted here.
"""
from pathlib import Path

import pytest

from tests.helpers import frontmatter

SKILL = ("skills", "dynamic-value-discovery", "SKILL.md")

# Every dynamic signal the skill's rubric must enumerate (REQ-010 task 10.3 / spec).
DYNAMIC_SIGNALS = (
    "name",        # person names / usernames / display names
    "date",        # dates / timestamps / relative time
    "currency",    # currency amounts
    "count",       # counts / quantities
    "status",      # statuses / badges
    "ID",          # IDs / slugs / reference numbers
    "greeting",    # a greeting containing a name
    "record",      # any value in a record / entity detail view
    "list",        # any value in a repeating list or table row
)

# Every static signal the skill's rubric must enumerate (REQ-010 task 10.3 / spec).
STATIC_SIGNALS = (
    "nav",       # navigation labels
    "button",    # button / action text
    "heading",   # section headings / fixed page titles
    "helper",    # fixed helper / instructional text
    "brand",     # brand strings
)


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- skill exists + valid frontmatter --------------------------------------

def test_skill_file_exists_and_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, SKILL).strip(), "dynamic-value-discovery SKILL.md is empty"


def test_skill_frontmatter_is_valid(plugin_root: Path) -> None:
    """Valid frontmatter: name == dynamic-value-discovery, quoted description >= 20 chars."""
    path = plugin_root.joinpath(*SKILL)
    fm, body = frontmatter.parse(path)
    missing = {"name", "description"} - fm.keys()
    assert not missing, f"dynamic-value-discovery SKILL.md missing frontmatter keys: {missing}"
    assert fm["name"] == "dynamic-value-discovery", (
        f"frontmatter name must be 'dynamic-value-discovery', got {fm['name']!r}"
    )
    assert isinstance(fm["description"], str) and len(fm["description"]) >= 20, (
        "frontmatter description must be a substantive string of at least 20 chars"
    )
    assert body.strip(), "dynamic-value-discovery SKILL.md body is empty"


# --- the core discipline: static vs. dynamic, classified from context -------

def test_skill_names_both_static_and_dynamic_classifications(plugin_root: Path) -> None:
    """Every displayed value is one of two things — a static literal or a dynamic value."""
    content = _read(plugin_root, SKILL)
    assert "static" in content, "skill does not define the `static` classification"
    assert "dynamic" in content, "skill does not define the `dynamic` classification"


def test_skill_classifies_from_context_not_the_literal(plugin_root: Path) -> None:
    """The core rule (task 10.2): classification is made FROM CONTEXT, never from the value."""
    content = _read(plugin_root, SKILL)
    lower = content.lower()
    assert "from context" in lower, (
        "skill does not state that values are classified FROM CONTEXT"
    )
    assert "never from the literal" in lower or "not from the literal" in lower, (
        "skill does not state the classification is NOT made from the literal itself"
    )


def test_skill_states_the_same_literal_can_be_static_or_dynamic(plugin_root: Path) -> None:
    """The same string is dynamic in one place and static in another — context decides."""
    lower = _read(plugin_root, SKILL).lower()
    assert "same literal" in lower or "same string" in lower, (
        "skill does not state that the same literal/string can be static or dynamic"
    )
    assert "in one place" in lower and "in another" in lower, (
        "skill does not state a value can be static in one place and dynamic in another"
    )


def test_skill_names_the_context_classification_factors(plugin_root: Path) -> None:
    """Classification is from position, the value's nature, and the requirements/design."""
    lower = _read(plugin_root, SKILL).lower()
    assert "position" in lower, "skill does not name `position` as a classification factor"
    assert "nature" in lower, "skill does not name the value's `nature` as a factor"
    assert "design" in lower and "requirement" in lower, (
        "skill does not name the requirements/design language as a classification factor"
    )


# --- the dynamic-signal and static-signal rubrics ---------------------------

def test_skill_defines_a_dynamic_signal_rubric(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "dynamic-signal rubric" in content.lower() or "dynamic signal" in content.lower(), (
        "skill does not define a dynamic-signal rubric"
    )


def test_skill_defines_a_static_signal_rubric(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "static-signal rubric" in content.lower() or "static signal" in content.lower(), (
        "skill does not define a static-signal rubric"
    )


@pytest.mark.parametrize("signal", DYNAMIC_SIGNALS)
def test_dynamic_signal_rubric_lists_every_signal(plugin_root: Path, signal: str) -> None:
    """The dynamic-signal rubric must enumerate names, dates, currency, counts,
    statuses, IDs, a greeting with a name, and values in record / list contexts."""
    content = _read(plugin_root, SKILL).lower()
    assert signal.lower() in content, (
        f"dynamic-value-discovery SKILL.md missing dynamic signal {signal!r}"
    )


@pytest.mark.parametrize("signal", STATIC_SIGNALS)
def test_static_signal_rubric_lists_every_signal(plugin_root: Path, signal: str) -> None:
    """The static-signal rubric must enumerate nav labels, button text,
    section headings, fixed helper text, and brand strings."""
    content = _read(plugin_root, SKILL).lower()
    assert signal.lower() in content, (
        f"dynamic-value-discovery SKILL.md missing static signal {signal!r}"
    )


# --- the binding rule + the escalation rule ---------------------------------

def test_skill_mandates_binding_dynamic_values_to_a_data_source(plugin_root: Path) -> None:
    """Task 10.4: every value classified `dynamic` is bound to a NAMED data source."""
    lower = _read(plugin_root, SKILL).lower()
    assert "data source" in lower, "skill does not mention binding to a data source"
    assert "named data source" in lower, (
        "skill does not mandate binding to a NAMED data source"
    )
    assert "bound" in lower or "bind" in lower, (
        "skill does not mandate that dynamic values are bound"
    )


def test_skill_forbids_shipping_the_hardcoded_sample_literal(plugin_root: Path) -> None:
    """A dynamic value must never ship as the design's hardcoded sample literal."""
    lower = _read(plugin_root, SKILL).lower()
    assert "hardcode" in lower, (
        "skill does not address shipping the design's hardcoded sample literal"
    )
    assert "sample" in lower, (
        "skill does not frame the mockup literal as sample data standing in for a value"
    )


def test_skill_escalates_ambiguous_classifications(plugin_root: Path) -> None:
    """Task 10.4: a genuinely ambiguous classification escalates to the human."""
    lower = _read(plugin_root, SKILL).lower()
    assert "escalat" in lower, "skill does not require escalation"
    assert "ambiguous" in lower, "skill does not name the ambiguous case"
    assert "human" in lower, "skill does not escalate to the human"


def test_skill_escalation_is_a_structured_question(plugin_root: Path) -> None:
    """Escalation is a structured question — never a vague one (the editability pattern)."""
    lower = _read(plugin_root, SKILL).lower()
    assert "structured" in lower and "question" in lower, (
        "skill does not require the escalation to be a structured question"
    )


def test_skill_forbids_default_guessing(plugin_root: Path) -> None:
    """The skill must reject default-guessing a classification under time pressure."""
    lower = _read(plugin_root, SKILL).lower()
    assert "guess" in lower, (
        "skill does not address (and reject) guessing a classification"
    )


# --- cross-role discipline + the hardcoded-dynamic-value gap ----------------

def test_skill_is_a_cross_role_discipline(plugin_root: Path) -> None:
    """D8: the discipline is applied by the architect, the developer, and the evaluator."""
    lower = _read(plugin_root, SKILL).lower()
    assert "architect" in lower, "skill does not name the architect role"
    assert "developer" in lower, "skill does not name the developer role"
    assert "evaluator" in lower, "skill does not name the evaluator role"
    assert "cross-role" in lower, "skill does not frame itself as a cross-role discipline"


def test_skill_defines_the_hardcoded_dynamic_value_gap(plugin_root: Path) -> None:
    """A dynamic value shipped hardcoded is a `hardcoded-dynamic-value` gap at review."""
    content = _read(plugin_root, SKILL)
    assert "hardcoded-dynamic-value" in content, (
        "skill does not define the `hardcoded-dynamic-value` gap kind the evaluator flags"
    )


def test_skill_has_an_anti_pattern_rationalizations_table(plugin_root: Path) -> None:
    """Like reuse-first-design, the skill carries an anti-pattern rationalizations table."""
    lower = _read(plugin_root, SKILL).lower()
    assert "rationalization" in lower, (
        "skill does not include an anti-pattern rationalizations table"
    )
    assert "rebuttal" in lower, (
        "the rationalizations table does not pair each rationalization with a rebuttal"
    )


def test_skill_has_hard_rules(plugin_root: Path) -> None:
    """Like reuse-first-design, the skill ends with non-negotiable hard rules."""
    lower = _read(plugin_root, SKILL).lower()
    assert "hard rules" in lower, "skill does not define a hard-rules section"
    assert "non-negotiable" in lower, "skill's hard rules are not marked non-negotiable"
