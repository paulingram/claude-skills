"""v0.9.19 — interaction-completeness discipline structural tests.

Reported gap: the architect-team pipeline keeps shipping frontend work that is
not what it claims to be. Playwright "user-flow" tests pass without driving the
UI (they call the API directly, or only navigate-and-assert); routes ship wired
to placeholder / "coming soon" pages instead of the live pages they should be;
and hardcoded sample values ship where a dynamic, data-bound value belongs.
None of the existing gates catches this — a grep finds PRESENT bad patterns,
not an untested button, a placeholder page, or a value hardcoded where it
should be dynamic.

v0.9.19 adds the `interaction-completeness` skill: three `interaction-reviewer`
agents (Opus) independently enumerate every interactive element AND every page,
classify each element by how it is wired and each page as live / placeholder /
confirmed-stub, verify every non-stub element has a genuine user-driven
Playwright test, trace each element to its endpoint, argue to a converged
interaction map, route gaps as solution requirements, and re-review until
satisfied — modeled on the proven `editability-completeness` skill.

These tests assert the discipline is present across the skill + agent so it
cannot silently regress. (Registration in EXPECTED_SKILLS / EXPECTED_AGENTS is
asserted by a later teammate per REQ-007 — not here.)
"""
from pathlib import Path

import pytest

from tests.helpers import frontmatter

SKILL = ("skills", "interaction-completeness", "SKILL.md")
AGENT = ("agents", "interaction-reviewer.md")

# Element wiring-classification rubric (task 1.3).
ELEMENT_CLASSIFICATIONS = (
    "endpoint-backed",
    "client-only",
    "confirmed-stub",
    "ambiguous",
)

# Page-classification rubric (task 9.1).
PAGE_CLASSIFICATIONS = (
    "live",
    "placeholder",
    "confirmed-stub",
)

# Gap kinds — interactive-element, page, and dynamic-value (tasks 3.3, 9.3, 11.4).
GAP_KINDS = ("unwired-control", "placeholder-page", "hardcoded-dynamic-value")

# Genuine user-interaction calls a real Playwright flow must use (task 1.4).
USER_INTERACTION_CALLS = (
    "page.click",
    "page.fill",
    "page.selectOption",
    "page.check",
    "page.press",
    "page.setInputFiles",
)

# Placeholder-signal naming tokens the rubric must enumerate (task 9.2).
PLACEHOLDER_NAMING_SIGNALS = ("Placeholder", "ComingSoon", "Stub", "Mock", "Demo", "WIP")

VALID_TOOLS = {
    "Read", "Edit", "Write", "Glob", "Grep", "LS", "Bash",
    "TodoWrite", "NotebookRead", "NotebookEdit",
    "WebFetch", "WebSearch", "Task",
}
VALID_MODELS = {"opus", "sonnet", "haiku"}
REQUIRED_AGENT_KEYS = {"name", "description", "tools", "model", "color"}
REQUIRED_SKILL_KEYS = {"name", "description"}


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- skill exists + valid frontmatter --------------------------------------

def test_skill_exists_and_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, SKILL).strip(), "interaction-completeness SKILL.md is empty"


def test_skill_frontmatter_valid(plugin_root: Path) -> None:
    """Valid frontmatter: name == interaction-completeness, a quoted >=20-char description."""
    fm, body = frontmatter.parse(plugin_root.joinpath(*SKILL))
    missing = REQUIRED_SKILL_KEYS - fm.keys()
    assert not missing, f"interaction-completeness SKILL.md missing frontmatter keys: {missing}"
    assert fm["name"] == "interaction-completeness", "skill frontmatter name mismatch"
    assert isinstance(fm["description"], str) and len(fm["description"]) >= 20, (
        "interaction-completeness description must be a substantive (>=20 char) string"
    )
    assert body.strip(), "interaction-completeness SKILL.md body is empty"


# --- skill core structure: 3 reviewers / converge / Round 3 / multi-pass ----

def test_skill_mandates_three_reviewers(plugin_root: Path) -> None:
    """Three interaction-reviewer agents, spawned in parallel."""
    content = _read(plugin_root, SKILL)
    lower = content.lower()
    assert "three" in lower and "interaction-reviewer" in content, (
        "interaction-completeness SKILL.md does not establish the three-reviewer team"
    )
    assert "parallel" in lower, (
        "interaction-completeness SKILL.md does not state the reviewers run in parallel"
    )


def test_skill_mandates_independent_analysis(plugin_root: Path) -> None:
    """Round 1 is independent — the rigor is parallel independence before convergence."""
    content = _read(plugin_root, SKILL).lower()
    assert "independent" in content, (
        "interaction-completeness SKILL.md does not establish independent Round 1 analysis"
    )


def test_skill_has_argue_to_convergence_round(plugin_root: Path) -> None:
    """The three reviewers ARGUE until they hold an identical converged map."""
    content = _read(plugin_root, SKILL)
    lower = content.lower()
    assert "argue to convergence" in lower, (
        "interaction-completeness SKILL.md does not document the argue-to-convergence round"
    )
    assert "round-robin" in lower, (
        "interaction-completeness SKILL.md does not document the round-robin convergence"
    )


def test_skill_has_architect_round_3_robustness_review(plugin_root: Path) -> None:
    """The converged map must pass an independent system-architect Round-3
    robustness review — three reviewers converging can share a blind spot."""
    content = _read(plugin_root, SKILL)
    assert "Round 3" in content, "interaction skill missing the Round 3 architect review"
    assert "system-architect" in content, (
        "interaction skill's Round 3 does not dispatch the system-architect agent"
    )
    assert "robustness" in content.lower(), (
        "interaction skill's Round 3 does not describe a robustness review"
    )


def test_skill_is_multi_pass_and_bounded(plugin_root: Path) -> None:
    """A bounded multi-pass outer loop — re-review after fixes until satisfied."""
    content = _read(plugin_root, SKILL)
    lower = content.lower()
    assert "multi-pass" in lower, "skill does not document the multi-pass loop"
    assert "satisfied" in content, "skill does not define the satisfied exit condition"
    assert "3 passes" in content or "three passes" in lower, (
        "skill does not bound the multi-pass loop"
    )


def test_skill_gaps_become_solution_requirements(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL).lower()
    assert "solution requirement" in content, (
        "interaction-completeness SKILL.md does not route gaps as solution requirements"
    )


def test_skill_reviewers_are_analysis_only(plugin_root: Path) -> None:
    """Reviewers must not write feature code — gaps go through the fix loop."""
    content = _read(plugin_root, SKILL)
    assert "analysis-only" in content.lower(), (
        "interaction-completeness SKILL.md does not establish reviewers as analysis-only"
    )


# --- skill: element AND page classification rubrics -------------------------

@pytest.mark.parametrize("classification", ELEMENT_CLASSIFICATIONS)
def test_skill_defines_every_element_wiring_class(plugin_root: Path, classification: str) -> None:
    """The element wiring rubric must name all four classes."""
    content = _read(plugin_root, SKILL)
    assert classification in content, (
        f"interaction-completeness SKILL.md missing element wiring class {classification!r}"
    )


@pytest.mark.parametrize("classification", PAGE_CLASSIFICATIONS)
def test_skill_defines_every_page_class(plugin_root: Path, classification: str) -> None:
    """The page rubric must name live / placeholder / confirmed-stub."""
    content = _read(plugin_root, SKILL)
    assert classification in content, (
        f"interaction-completeness SKILL.md missing page class {classification!r}"
    )


def test_skill_has_distinct_element_and_page_rubrics(plugin_root: Path) -> None:
    """The skill must define an element wiring rubric AND a separate page rubric."""
    content = _read(plugin_root, SKILL).lower()
    assert "wiring-classification rubric" in content or "wiring classification rubric" in content, (
        "interaction-completeness SKILL.md does not name an element wiring-classification rubric"
    )
    assert "page-classification rubric" in content or "page classification rubric" in content, (
        "interaction-completeness SKILL.md does not name a page-classification rubric"
    )


@pytest.mark.parametrize("gap_kind", GAP_KINDS)
def test_skill_defines_every_gap_kind(plugin_root: Path, gap_kind: str) -> None:
    content = _read(plugin_root, SKILL)
    assert gap_kind in content, (
        f"interaction-completeness SKILL.md missing gap kind {gap_kind!r}"
    )


# --- skill: scope covers elements AND pages, plus enumeration ---------------

def test_skill_scope_covers_elements_and_pages(plugin_root: Path) -> None:
    """The skill scope must cover every interactive element AND every page/route."""
    content = _read(plugin_root, SKILL).lower()
    assert "interactive element" in content, (
        "interaction-completeness SKILL.md scope does not cover interactive elements"
    )
    assert "page" in content and ("route" in content or "screen" in content), (
        "interaction-completeness SKILL.md scope does not cover pages/screens/routes"
    )


def test_skill_defines_converged_map_artifact(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL).lower()
    assert "converged interaction map" in content or "converged-map" in content, (
        "interaction-completeness SKILL.md does not define the converged interaction-map artifact"
    )


# --- skill: test-authenticity audit (task 1.4) ------------------------------

def test_skill_audits_genuine_user_driven_tests(plugin_root: Path) -> None:
    """Every non-stub element needs a genuine user-driven Playwright test —
    not a direct API call, not a vacuous navigate-and-assert."""
    content = _read(plugin_root, SKILL)
    lower = content.lower()
    assert "page.request" in content, (
        "skill does not forbid page.request.* direct API calls in user-flow tests"
    )
    assert "navigate-and-assert" in lower, (
        "skill does not flag a vacuous navigate-and-assert masquerading as a flow"
    )


@pytest.mark.parametrize("call", USER_INTERACTION_CALLS)
def test_skill_names_genuine_interaction_calls(plugin_root: Path, call: str) -> None:
    """The test-authenticity audit names the genuine user-interaction calls."""
    content = _read(plugin_root, SKILL)
    assert call in content, (
        f"interaction-completeness SKILL.md does not name the genuine interaction call {call!r}"
    )


def test_skill_defines_element_to_endpoint_trace(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL).lower()
    assert "endpoint" in content and "trace" in content, (
        "interaction-completeness SKILL.md does not define the element-to-endpoint trace"
    )


# --- skill: confirmed-stub mechanism (REQ-003) ------------------------------

def test_skill_confirmed_stub_requires_user_confirmation(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    lower = content.lower()
    assert "confirmed-stub" in content, "skill does not define the confirmed-stub class"
    assert "user confirmation" in lower or "explicit user confirmation" in lower, (
        "skill does not require explicit user confirmation for a confirmed-stub"
    )
    assert "confirmed_stubs" in content and "coverage-map.json" in content, (
        "skill does not record confirmed stubs in coverage-map.json confirmed_stubs[]"
    )


def test_skill_escalates_rather_than_guessing(plugin_root: Path) -> None:
    """An inert element / placeholder page / ambiguous case escalates — never a guess."""
    content = _read(plugin_root, SKILL).lower()
    assert "escalat" in content and "ambiguous" in content, (
        "skill does not require ambiguous elements/pages to be escalated to the human"
    )
    assert "never a silent pass" in content or "never guess" in content or "do not guess" in content, (
        "skill does not forbid silently passing an unconfirmed inert control / placeholder page"
    )


# --- skill: placeholder-signal rubric (REQ-009) -----------------------------

@pytest.mark.parametrize("signal", PLACEHOLDER_NAMING_SIGNALS)
def test_skill_placeholder_rubric_names_signal(plugin_root: Path, signal: str) -> None:
    """The placeholder-signal rubric enumerates the naming tokens."""
    content = _read(plugin_root, SKILL)
    assert signal in content, (
        f"interaction-completeness placeholder-signal rubric missing {signal!r}"
    )


def test_skill_placeholder_rubric_has_behavioral_signals(plugin_root: Path) -> None:
    """Beyond naming: coming-soon content, a data-driven page with no API calls,
    a near-empty shell, a route-table entry pointing at a placeholder."""
    content = _read(plugin_root, SKILL).lower()
    assert "coming soon" in content, "placeholder rubric missing the coming-soon content signal"
    assert "no api call" in content, (
        "placeholder rubric missing the data-driven-page-with-no-API-calls signal"
    )
    assert "route" in content and "table" in content, (
        "placeholder rubric missing the route-table-points-at-a-placeholder signal"
    )


def test_skill_cross_checks_pages_against_design_and_route_map(plugin_root: Path) -> None:
    content = _read(plugin_root, SKILL)
    assert "ROUTE_MAP.md" in content, (
        "skill does not cross-check pages against ROUTE_MAP.md"
    )
    assert "design" in content.lower(), (
        "skill does not cross-check pages against the design / requirements"
    )


# --- skill: dynamic-value-discovery wiring (task 11.4) ----------------------

def test_skill_applies_dynamic_value_discovery(plugin_root: Path) -> None:
    """Task 11.4 — the skill instructs the reviewer to apply dynamic-value-discovery
    and report a hardcoded-should-be-dynamic value as a hardcoded-dynamic-value gap."""
    content = _read(plugin_root, SKILL)
    assert "dynamic-value-discovery" in content, (
        "interaction-completeness SKILL.md does not reference the dynamic-value-discovery skill"
    )
    assert "hardcoded-dynamic-value" in content, (
        "interaction-completeness SKILL.md does not define the hardcoded-dynamic-value gap kind"
    )


# --- agent: exists, frontmatter, opus, analysis-only ------------------------

def test_agent_exists_and_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, AGENT).strip(), "interaction-reviewer agent file is empty"


def test_agent_frontmatter_has_five_valid_keys(plugin_root: Path) -> None:
    """The agent has the 5 required frontmatter keys, name match, valid model."""
    fm, body = frontmatter.parse(plugin_root.joinpath(*AGENT))
    missing = REQUIRED_AGENT_KEYS - fm.keys()
    assert not missing, f"interaction-reviewer missing frontmatter keys: {missing}"
    assert fm["name"] == "interaction-reviewer", "interaction-reviewer frontmatter name mismatch"
    assert isinstance(fm["description"], str) and len(fm["description"]) > 20, (
        "interaction-reviewer description must be a substantive string"
    )
    assert "color" in fm and str(fm["color"]).strip(), "interaction-reviewer missing a color"
    assert body.strip(), "interaction-reviewer agent body is empty"


def test_agent_is_opus(plugin_root: Path) -> None:
    """Judgment-heavy review — the reviewer runs on the opus model."""
    fm, _ = frontmatter.parse(plugin_root.joinpath(*AGENT))
    assert fm["model"] in VALID_MODELS, f"interaction-reviewer invalid model {fm['model']!r}"
    assert fm["model"] == "opus", "interaction-reviewer must run on the opus model"


def test_agent_tools_are_valid(plugin_root: Path) -> None:
    """Every tool in the agent's tools list is from the valid tool set."""
    fm, _ = frontmatter.parse(plugin_root.joinpath(*AGENT))
    tools_raw = fm["tools"]
    if isinstance(tools_raw, str):
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
    else:
        tools = set(tools_raw)
    assert tools, "interaction-reviewer tools list is empty"
    bad = tools - VALID_TOOLS
    assert not bad, f"interaction-reviewer has unknown tools: {sorted(bad)}"


def test_agent_has_no_edit_tool(plugin_root: Path) -> None:
    """Analysis-only — the reviewer must not have Edit access to feature code."""
    fm, _ = frontmatter.parse(plugin_root.joinpath(*AGENT))
    tools_raw = fm["tools"]
    if isinstance(tools_raw, str):
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
    else:
        tools = set(tools_raw)
    assert "Edit" not in tools, "interaction-reviewer must not have the Edit tool (analysis-only)"


def test_agent_is_read_only_on_source(plugin_root: Path) -> None:
    content = _read(plugin_root, AGENT)
    assert "Read-only on source" in content or "read-only on source" in content.lower(), (
        "interaction-reviewer does not establish read-only-on-source posture"
    )
    assert "analysis-only" in content.lower(), (
        "interaction-reviewer does not establish the analysis-only posture"
    )


def test_agent_forbids_round_1_consultation(plugin_root: Path) -> None:
    content = _read(plugin_root, AGENT)
    assert "independent" in content.lower(), (
        "interaction-reviewer does not enforce Round 1 independence"
    )


# --- agent: body covers the reviewer's job ----------------------------------

def test_agent_body_covers_element_and_page_enumeration(plugin_root: Path) -> None:
    content = _read(plugin_root, AGENT).lower()
    assert "interactive element" in content and "page" in content, (
        "interaction-reviewer body does not cover enumerating interactive elements AND pages"
    )


def test_agent_body_covers_test_authenticity_audit(plugin_root: Path) -> None:
    content = _read(plugin_root, AGENT)
    lower = content.lower()
    assert "page.request" in content, (
        "interaction-reviewer body does not forbid page.request.* direct API calls"
    )
    assert "page.click" in content, (
        "interaction-reviewer body does not name the genuine page.click interaction call"
    )
    assert "navigate-and-assert" in lower, (
        "interaction-reviewer body does not flag the vacuous navigate-and-assert"
    )


def test_agent_body_covers_hardcoded_dynamic_value(plugin_root: Path) -> None:
    """Task 11.4 — the reviewer applies dynamic-value-discovery and flags
    hardcoded-dynamic-value gaps."""
    content = _read(plugin_root, AGENT)
    assert "dynamic-value-discovery" in content, (
        "interaction-reviewer body does not reference the dynamic-value-discovery skill"
    )
    assert "hardcoded-dynamic-value" in content, (
        "interaction-reviewer body does not flag hardcoded-dynamic-value gaps"
    )


def test_agent_body_covers_convergence_and_map(plugin_root: Path) -> None:
    content = _read(plugin_root, AGENT).lower()
    assert "convergence" in content, (
        "interaction-reviewer body does not cover round-robin convergence"
    )
    assert "converged" in content and "map" in content, (
        "interaction-reviewer body does not cover writing the converged interaction map"
    )
