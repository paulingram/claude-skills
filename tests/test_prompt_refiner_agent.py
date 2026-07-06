"""Structural tests for the `prompt-refiner` agent (v0.9.33)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


AGENT_NAME = "prompt-refiner"

REQUIRED_AXES = ("clarity", "scope", "acceptance", "grounding", "conflict")


def _agent_path(plugin_root: Path) -> Path:
    return plugin_root / "agents" / f"{AGENT_NAME}.md"


def _read(plugin_root: Path) -> tuple[dict, str]:
    return frontmatter.parse(_agent_path(plugin_root))


def _tools_list(fm: dict) -> list[str]:
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return [t.strip() for t in raw if t]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


# --- file + frontmatter -----------------------------------------------------


def test_agent_file_exists(plugin_root: Path) -> None:
    assert _agent_path(plugin_root).exists(), f"agents/{AGENT_NAME}.md missing"


def test_agent_frontmatter_required_keys(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    for key in ("name", "description", "tools", "model", "color"):
        assert key in fm, f"frontmatter missing required key '{key}'"
    assert fm["name"] == AGENT_NAME


def test_agent_model_is_fable(plugin_root: Path) -> None:
    """The grader is judgment-heavy; opus is the required model."""
    fm, _ = _read(plugin_root)
    assert fm["model"] == "fable", "prompt-refiner must be model: fable (v3.32.0 uniform default; lever scripts/setup/set_default_model.py)"


# --- tools posture ----------------------------------------------------------


def test_agent_tools_no_edit(plugin_root: Path) -> None:
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Edit" not in tools, "prompt-refiner must not have Edit (read-only on source)"


def test_agent_has_write_bounded(plugin_root: Path) -> None:
    """Write IS in the allowlist but bounded to .architect-team/refined-prompts/."""
    fm, body = _read(plugin_root)
    tools = _tools_list(fm)
    assert "Write" in tools, (
        "prompt-refiner must have Write (verdict files at .architect-team/refined-prompts/)"
    )
    assert ".architect-team/refined-prompts/" in body, (
        "prompt-refiner body must document the bounded Write scope"
    )


def test_agent_has_read_and_grep(plugin_root: Path) -> None:
    """Read + Glob + Grep for map-reading (LS retired in v3.10.0 R4a)."""
    fm, _ = _read(plugin_root)
    tools = _tools_list(fm)
    for required in ("Read", "Glob", "Grep"):
        assert required in tools, f"prompt-refiner must have {required}"


# --- grading axes -----------------------------------------------------------


@pytest.mark.parametrize("axis", REQUIRED_AXES)
def test_axis_named(plugin_root: Path, axis: str) -> None:
    _, body = _read(plugin_root)
    assert axis in body.lower(), f"agent body must name the '{axis}' axis"


def test_axes_have_score_range_documented(plugin_root: Path) -> None:
    """Each axis must document the 1-10 score range with anchors for 1 and 10."""
    _, body = _read(plugin_root)
    # The agent table documents 'What earns 1' / 'What earns 10'
    assert "earns 1" in body, "agent must document what earns score 1 per axis"
    assert "earns 10" in body, "agent must document what earns score 10 per axis"


# --- verdict schema ---------------------------------------------------------


def test_verdict_schema_has_required_fields(plugin_root: Path) -> None:
    """The verdict JSON schema must declare iteration / axes / overall_score / overall_letter / next_questions."""
    _, body = _read(plugin_root)
    for required in ('"iteration"', '"axes"', '"overall_score"', '"overall_letter"', '"next_questions"'):
        assert required in body, f"verdict schema must declare {required}"


def test_question_schema_required_fields(plugin_root: Path) -> None:
    """Each next_questions entry has axis / ambiguity / codebase_anchor / question / form / options."""
    _, body = _read(plugin_root)
    for required in ('"axis"', '"ambiguity"', '"codebase_anchor"', '"question"', '"form"'):
        assert required in body, f"question schema must declare {required}"


def test_three_question_forms(plugin_root: Path) -> None:
    """choose-one / free-form / yes-no must all be documented."""
    _, body = _read(plugin_root)
    for form in ("choose-one", "free-form", "yes-no"):
        assert form in body, f"question schema must declare form '{form}'"


def test_question_cap_is_five(plugin_root: Path) -> None:
    """The 2-5 questions-per-iteration cap is documented."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "5 question" in body_lower or "5 questions" in body_lower or "cap at 5" in body_lower, (
        "agent must declare the 2-5 questions-per-iteration cap"
    )


# --- codebase-grounding rules -----------------------------------------------


def test_no_invented_entities_rule(plugin_root: Path) -> None:
    """Rule #1: never invent a route / endpoint / file / function."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "never invent" in body_lower or "fabrication" in body_lower, (
        "agent must declare the 'never invent codebase entities' rule"
    )


def test_always_cite_map_section_rule(plugin_root: Path) -> None:
    """Rule #2: cite the map + section/line, not just a bare entity name."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "cite" in body_lower, "agent must require citation of the source map"
    # Examples: "ROUTE_MAP.md → ... line 47" or "CODEBASE_MAP.md → ... lines 42-65"
    assert "line" in body_lower, (
        "agent must require map citations to include file:section/line specificity"
    )


def test_interaction_intuition_cross_reference(plugin_root: Path) -> None:
    """For frontend bugs/features, INTERACTION_INTUITION_MAP must be consulted to avoid re-asking confirmed items."""
    _, body = _read(plugin_root)
    assert "INTERACTION_INTUITION_MAP" in body, (
        "agent must cross-reference INTERACTION_INTUITION_MAP.md (Phase −1D's pre-confirmed elements)"
    )


def test_mempalace_context_consumption(plugin_root: Path) -> None:
    """The agent must use MemPalace context when present to surface prior-run relevance."""
    _, body = _read(plugin_root)
    assert "mempalace" in body.lower(), "agent must reference MemPalace context (read-only)"


# --- what the agent does NOT do ---------------------------------------------


def test_agent_does_not_interact_with_user(plugin_root: Path) -> None:
    """The agent emits structured questions; the ORCHESTRATOR runs AskUserQuestion."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "askuserquestion" in body_lower or "ask user question" in body_lower, (
        "agent must reference AskUserQuestion to clarify ownership"
    )
    assert "orchestrator" in body_lower, "agent must distinguish its role from the orchestrator's"


def test_agent_does_not_edit_working_prompt(plugin_root: Path) -> None:
    """The orchestrator composes the next iteration's prompt; the agent only grades."""
    _, body = _read(plugin_root)
    assert "does not edit" in body.lower() or "DOES NOT edit" in body, (
        "agent must declare it does NOT edit the working_prompt"
    )


# --- verbatim-quoting requirement -------------------------------------------


def test_rationale_must_quote_verbatim(plugin_root: Path) -> None:
    """Every per-axis rationale must quote the prompt verbatim, not paraphrase."""
    _, body = _read(plugin_root)
    body_lower = body.lower()
    assert "verbatim" in body_lower, "agent must require verbatim quoting in rationales"
    assert "paraphras" in body_lower, "agent must forbid paraphrasing in rationales"
