"""Structural audits for the v1.7.0 frontend-missing-api-discipline change.

Asserts:
1. `agents/frontend.md` carries a `## Missing-API discipline` section that
   names the 4 forbidden anti-patterns, the right pattern (SR + pause +
   return), the SR origin-kind verbatim, and the SR payload shape.
2. `agents/backend.md` carries a `## Missing-API SR intake` section that
   names the SR origin-kind verbatim.
3. `agents/system-architect.md` Phase 2 architect brief documents the
   ordering-dependency check for `both`-layer features.
4. `skills/interaction-completeness/SKILL.md` recognizes the new
   `pending-backend` element classification + the SR-linkage rule.
5. `skills/team-spawning-and-review-gates/SKILL.md` lists
   `missing-api-for-frontend-element` as a recognized SR origin-kind +
   documents the routing (backend dispatched first; frontend re-dispatched).
6. `skills/common-pipeline-conventions/SKILL.md` carries a `## Frontend
   missing-API discipline` section naming the 4 anti-patterns + the right
   pattern.

The audits are grep-style — same shape as v1.6.0's
`tests/test_teammate_git_discipline.py`. A change that adds a runtime
detector for frontend agents faking / mocking / hardcoding / stubbing
would add additional behavioral tests; v1.7.0 is documentation +
structural, matching the v1.4.0 / v1.6.0 discipline shape.

The failure mode this discipline closes: a frontend agent encounters a
UI element that needs an endpoint which does not exist yet. Without a
named alternative, the agent silently fakes / mocks / hardcodes / stubs
— and downstream gates catch the defect only after the round trip is
wasted. v1.7.0 names the explicit alternative: surface a structured SR,
pause that element's work, return to wire when the backend ships.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


# The 4 forbidden anti-patterns named in the discipline. Each must appear
# (as the named verb / pattern) in the frontend agent body + in the
# canonical section. Parametrized so a missing pattern fails its own test
# rather than collapsing all four checks into one verdict.
FORBIDDEN_ANTIPATTERNS = (
    "fake",
    "mock",
    "hardcode",
    "stub",
)


# The canonical SR origin-kind for missing APIs. Three layers reference
# this verbatim (frontend agent body, backend agent body, team-spawning
# skill list); a future rename here is the single source of truth.
SR_ORIGIN_KIND = "missing-api-for-frontend-element"


def _read_skill_body(plugin_root: Path, skill_name: str) -> str:
    path = plugin_root / "skills" / skill_name / "SKILL.md"
    _, body = frontmatter.parse(path)
    return body


def _read_agent_body(plugin_root: Path, agent_name: str) -> str:
    path = plugin_root / "agents" / f"{agent_name}.md"
    _, body = frontmatter.parse(path)
    return body


def _section_body(body: str, heading: str) -> str:
    """Return the body of a single H2 section, from its heading to the next H2.

    Asserts the heading exists exactly once in the input body.
    """
    occurrences = body.count(heading)
    assert occurrences == 1, (
        f"expected `{heading}` to appear exactly once in the body, "
        f"found {occurrences}"
    )
    section_start = body.index(heading)
    rest = body[section_start:]
    next_h2 = rest.find("\n## ", 1)
    return rest if next_h2 == -1 else rest[:next_h2]


# ---- agents/frontend.md: the per-agent statement of the discipline ---------


def test_frontend_agent_has_missing_api_discipline_section_exactly_once(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 1: the section exists exactly once in `agents/frontend.md`."""
    body = _read_agent_body(plugin_root, "frontend")
    occurrences = body.count("## Missing-API discipline")
    assert occurrences == 1, (
        f"expected `## Missing-API discipline` to appear exactly once in "
        f"agents/frontend.md, found {occurrences}"
    )


@pytest.mark.parametrize("antipattern", FORBIDDEN_ANTIPATTERNS)
def test_frontend_missing_api_section_names_each_forbidden_antipattern(
    plugin_root: Path, antipattern: str
) -> None:
    """REQ-1 Scenario 2: the section names each of the 4 forbidden
    anti-patterns (faking / mocking / hardcoding / silently stubbing)."""
    body = _read_agent_body(plugin_root, "frontend")
    section = _section_body(body, "## Missing-API discipline")
    assert antipattern in section.lower(), (
        f"the `## Missing-API discipline` section in agents/frontend.md must "
        f"explicitly name `{antipattern}` as a forbidden anti-pattern (one of "
        f"the v1.7.0 forbidden four: fake / mock / hardcode / stub)"
    )


def test_frontend_missing_api_section_names_sr_origin_kind_verbatim(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 3: the section names the SR origin-kind
    `missing-api-for-frontend-element` verbatim — this is the exact string
    the orchestrator's Phase 3b SR walker matches on, so it must appear in
    the agent's instructions."""
    body = _read_agent_body(plugin_root, "frontend")
    section = _section_body(body, "## Missing-API discipline")
    assert SR_ORIGIN_KIND in section, (
        f"the `## Missing-API discipline` section in agents/frontend.md must "
        f"name the SR `origin.kind: \"{SR_ORIGIN_KIND}\"` verbatim — it is "
        f"the contract the orchestrator's Phase 3b SR walker matches on"
    )


def test_frontend_missing_api_section_documents_pause_and_return(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 3 (b): the section instructs the agent to PAUSE work
    on the element after writing the SR, and to RETURN to wire when the
    orchestrator re-dispatches with the SR resolved."""
    body = _read_agent_body(plugin_root, "frontend")
    section = _section_body(body, "## Missing-API discipline")
    assert "pause" in section.lower(), (
        "the `## Missing-API discipline` section in agents/frontend.md must "
        "instruct the agent to PAUSE work on the element after writing the SR "
        "(the discipline's third step — without pause, the agent reverts to "
        "the anti-patterns)"
    )
    # Either the verb "return" or the noun "re-dispatch" / "redispatch" /
    # "wire up" signals the return-to-wire step.
    return_signal = any(
        signal in section.lower()
        for signal in ("return", "re-dispatch", "redispatch", "wire up")
    )
    assert return_signal, (
        "the `## Missing-API discipline` section in agents/frontend.md must "
        "instruct the agent to RETURN and wire up when the orchestrator "
        "re-dispatches with the SR resolved (the discipline's fourth step)"
    )


def test_frontend_missing_api_section_documents_sr_payload_shape(
    plugin_root: Path,
) -> None:
    """REQ-1 Scenario 4: the section documents that the SR payload describes
    the required endpoint (method, path, request shape, response shape, error
    cases)."""
    body = _read_agent_body(plugin_root, "frontend")
    section = _section_body(body, "## Missing-API discipline")
    # Required endpoint contract pieces — each must appear in the SR-payload
    # description so the agent knows what to put in the SR.
    payload_terms = ("method", "path", "request", "response")
    for term in payload_terms:
        assert term in section.lower(), (
            f"the `## Missing-API discipline` section in agents/frontend.md "
            f"must document the SR payload's endpoint-contract shape — "
            f"`{term}` is missing (the discipline requires method + path + "
            f"request shape + response shape + error cases)"
        )


# ---- agents/backend.md: the SR intake side of the discipline ---------------


def test_backend_agent_has_missing_api_sr_intake_section_exactly_once(
    plugin_root: Path,
) -> None:
    """REQ-2 Scenario 1: the section exists exactly once in `agents/backend.md`."""
    body = _read_agent_body(plugin_root, "backend")
    occurrences = body.count("## Missing-API SR intake")
    assert occurrences == 1, (
        f"expected `## Missing-API SR intake` to appear exactly once in "
        f"agents/backend.md, found {occurrences}"
    )


def test_backend_missing_api_intake_section_names_sr_origin_kind_verbatim(
    plugin_root: Path,
) -> None:
    """REQ-2 Scenario 2: the backend agent's intake section names the SR
    `origin.kind: "missing-api-for-frontend-element"` verbatim — the same
    string the frontend agent uses to author the SR."""
    body = _read_agent_body(plugin_root, "backend")
    section = _section_body(body, "## Missing-API SR intake")
    assert SR_ORIGIN_KIND in section, (
        f"the `## Missing-API SR intake` section in agents/backend.md must "
        f"name `{SR_ORIGIN_KIND}` verbatim — the same string the frontend "
        f"agent writes into the SR's `origin.kind` field. Cross-agent "
        f"consistency on the kind name is the contract."
    )


def test_backend_missing_api_intake_section_documents_shape_surfacing(
    plugin_root: Path,
) -> None:
    """REQ-2 corollary: the backend's intake section documents surfacing the
    actual endpoint shape in the dispatch report so the frontend can confirm
    before wiring (and so a schema diff is visible if the contract had to
    change)."""
    body = _read_agent_body(plugin_root, "backend")
    section = _section_body(body, "## Missing-API SR intake")
    # The section must mention the dispatch report (or report) AND the
    # endpoint shape so the frontend has the contract for wire-up.
    assert "shape" in section.lower(), (
        "the `## Missing-API SR intake` section in agents/backend.md must "
        "document surfacing the ACTUAL endpoint shape in the dispatch report "
        "so the frontend agent can confirm before wiring"
    )
    assert "report" in section.lower(), (
        "the `## Missing-API SR intake` section in agents/backend.md must "
        "reference the dispatch report (the artifact the frontend reads to "
        "confirm the endpoint shape matches the SR's spec)"
    )


# ---- agents/system-architect.md: Phase 2 ordering-dependency check ---------


def test_system_architect_phase_2_documents_both_layer_ordering_check(
    plugin_root: Path,
) -> None:
    """REQ-3 Scenario 1: the Phase 2 architect brief section in
    `agents/system-architect.md` documents identifying backend-vs-frontend
    ordering dependencies for `both`-layer features AND mentions the
    missing-API SR pattern as the default."""
    body = _read_agent_body(plugin_root, "system-architect")
    # The Phase 2 check is documented across the body — the explicit phrase
    # the body uses to mark a both-layer feature must appear at least once.
    assert "both" in body, (
        "agents/system-architect.md must reference `both`-layer features in "
        "the Phase 2 brief discussion of ordering-dependency checks"
    )
    # The discipline must mention ordering or the SR origin-kind explicitly
    # so the architect knows what to check for.
    has_ordering_check = any(
        term in body.lower()
        for term in ("ordering", "sequence", "backend first", "backend-first")
    )
    assert has_ordering_check, (
        "agents/system-architect.md Phase 2 architect brief must document "
        "identifying backend-vs-frontend ordering dependencies for "
        "`both`-layer features (one of `ordering` / `sequence` / "
        "`backend first` / `backend-first` must appear)"
    )
    # The default mechanism — the missing-API SR — must be named.
    assert SR_ORIGIN_KIND in body or "missing-API SR" in body or "missing-api" in body.lower(), (
        f"agents/system-architect.md Phase 2 architect brief must mention "
        f"the missing-API SR pattern as the default mechanism for "
        f"`both`-layer ordering (one of `{SR_ORIGIN_KIND}`, `missing-API SR`, "
        f"or `missing-api` must appear)"
    )


# ---- interaction-completeness: pending-backend classification ---------------


def test_interaction_completeness_recognizes_pending_backend_classification(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1: the skill body names `pending-backend` as a
    recognized element classification AND documents the SR-linkage rule."""
    body = _read_skill_body(plugin_root, "interaction-completeness")
    assert "pending-backend" in body, (
        "skills/interaction-completeness/SKILL.md must recognize the new "
        "`pending-backend` element classification (v1.7.0 — a UI element "
        "awaiting an SR-tracked backend endpoint)"
    )


def test_interaction_completeness_documents_sr_linkage_rule(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1 (b): the skill body states the SR-linkage rule —
    the interaction-reviewer accepts `pending-backend` only when a matching
    open SR with `origin.kind: "missing-api-for-frontend-element"` exists."""
    body = _read_skill_body(plugin_root, "interaction-completeness")
    # The skill body must name the SR origin-kind so the linkage is explicit.
    assert SR_ORIGIN_KIND in body, (
        f"skills/interaction-completeness/SKILL.md must name "
        f"`{SR_ORIGIN_KIND}` as the SR `origin.kind` that authorizes a "
        f"`pending-backend` classification (the SR-linkage rule)"
    )


def test_interaction_completeness_documents_without_sr_is_gap(
    plugin_root: Path,
) -> None:
    """REQ-4 Scenario 1 (c): the skill body states that without the matching
    SR, the element is a gap (the existing `unwired-control` rule)."""
    body = _read_skill_body(plugin_root, "interaction-completeness")
    # The body must indicate that pending-backend WITHOUT the SR is a gap —
    # the rule "no SR → gap" is the inverse of the SR-linkage rule, both
    # documented together.
    # Find the section / paragraph that introduces pending-backend.
    pb_idx = body.find("pending-backend")
    # Look in a window around the first mention for gap-signaling language.
    window = body[max(0, pb_idx - 200) : pb_idx + 1500]
    assert "gap" in window.lower(), (
        "skills/interaction-completeness/SKILL.md must state that without a "
        "matching open SR, a `pending-backend` classification falls back to "
        "the gap rule (an unwired-control gap, the existing rule)"
    )


# ---- team-spawning-and-review-gates: SR origin-kind + routing --------------


def test_team_spawning_lists_missing_api_origin_kind(
    plugin_root: Path,
) -> None:
    """REQ-5 Scenario 1: the team-spawning skill body lists
    `missing-api-for-frontend-element` in its enumerated SR origin-kinds."""
    body = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    assert SR_ORIGIN_KIND in body, (
        f"skills/team-spawning-and-review-gates/SKILL.md must list "
        f"`{SR_ORIGIN_KIND}` in its recognized SR `origin.kind` enumeration "
        f"— agents MUST NOT invent kinds, so the kind must be added to the "
        f"canonical list before agents reference it"
    )


def test_team_spawning_documents_routing_for_missing_api_sr(
    plugin_root: Path,
) -> None:
    """REQ-5 Scenario 1 (b): the team-spawning skill body documents the
    routing — backend dispatched FIRST with the SR; frontend re-dispatched
    after backend completion. The divergence from standard SR flow is that
    it does NOT route through `diagnostic-research-team` (this isn't a test
    failure)."""
    body = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    # Locate every occurrence of the SR origin-kind in the body and inspect
    # the windows around each. The kind appears in the schema enum AND in
    # the routing paragraph; the routing paragraph is the one that must
    # name "backend first" / "dispatches the backend" — the schema enum
    # row is the canonical kind-list and need not carry the routing.
    body_lower = body.lower()
    routing_terms = ("backend dispatched", "backend first", "backend-first", "dispatches the backend")
    has_backend_first = any(term in body_lower for term in routing_terms)
    assert has_backend_first, (
        "skills/team-spawning-and-review-gates/SKILL.md must document that "
        "a `missing-api-for-frontend-element` SR dispatches the BACKEND "
        "first (NOT diagnostic-research-team) — the routing divergence is "
        "the v1.7.0 contract. One of `backend dispatched` / `backend first` "
        "/ `backend-first` / `dispatches the backend` must appear in the "
        "body."
    )
    # Locate the routing paragraph (the one describing the kind's routing)
    # and confirm it sits near the kind's mention — at least one occurrence
    # of the kind must be within 4000 chars of a routing-term occurrence,
    # so the rule and its routing read as a single statement somewhere.
    routing_idx = -1
    for term in routing_terms:
        i = body_lower.find(term)
        if i >= 0:
            routing_idx = i
            break
    assert routing_idx >= 0  # established by the assertion above
    # Confirm any occurrence of the kind sits within 4000 chars of the
    # routing description — this asserts the rule + routing live in the
    # same logical section, not orphaned far apart.
    proximities: list[int] = []
    start = 0
    while True:
        idx = body.find(SR_ORIGIN_KIND, start)
        if idx < 0:
            break
        proximities.append(abs(idx - routing_idx))
        start = idx + len(SR_ORIGIN_KIND)
    assert proximities and min(proximities) <= 4000, (
        "The routing description and at least one mention of the "
        "`missing-api-for-frontend-element` kind must be near each other "
        "(within 4000 chars) so the rule + routing read as a single "
        "section. Closest distance found: "
        f"{min(proximities) if proximities else 'none'}"
    )
    # The "does NOT route through diagnostic-research-team" divergence is
    # important enough that it should appear in the body somewhere.
    assert "diagnostic-research-team" in body_lower, (
        "skills/team-spawning-and-review-gates/SKILL.md must reference "
        "`diagnostic-research-team` in the SR-routing documentation so the "
        "divergence (missing-api SRs DON'T route through it) is visible"
    )


# ---- common-pipeline-conventions: the canonical discipline section ---------


def test_common_pipeline_conventions_has_frontend_missing_api_section(
    plugin_root: Path,
) -> None:
    """REQ-6 Scenario 1: the canonical `## Frontend missing-API discipline`
    section exists exactly once in `common-pipeline-conventions/SKILL.md`."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    occurrences = body.count("## Frontend missing-API discipline")
    assert occurrences == 1, (
        f"expected `## Frontend missing-API discipline` to appear exactly "
        f"once in skills/common-pipeline-conventions/SKILL.md, found "
        f"{occurrences}"
    )


@pytest.mark.parametrize("antipattern", FORBIDDEN_ANTIPATTERNS)
def test_canonical_section_names_each_forbidden_antipattern(
    plugin_root: Path, antipattern: str
) -> None:
    """REQ-6 Scenario 1 (b): the canonical section names each of the 4
    forbidden anti-patterns (faking / mocking / hardcoding / silently
    stubbing)."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Frontend missing-API discipline")
    assert antipattern in section.lower(), (
        f"the canonical `## Frontend missing-API discipline` section must "
        f"explicitly name `{antipattern}` as a forbidden anti-pattern "
        f"(one of the v1.7.0 forbidden four)"
    )


def test_canonical_section_documents_right_pattern(
    plugin_root: Path,
) -> None:
    """REQ-6 Scenario 1 (c): the canonical section names the right pattern
    — SR + pause + return."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Frontend missing-API discipline")
    # All three discipline steps must appear in the section.
    assert "pause" in section.lower(), (
        "the canonical `## Frontend missing-API discipline` section must "
        "name the PAUSE step of the right pattern (after writing the SR, "
        "pause work on the element)"
    )
    return_signal = any(
        signal in section.lower()
        for signal in ("return", "re-dispatch", "redispatch")
    )
    assert return_signal, (
        "the canonical `## Frontend missing-API discipline` section must "
        "name the RETURN-to-wire step of the right pattern"
    )
    assert SR_ORIGIN_KIND in section, (
        f"the canonical `## Frontend missing-API discipline` section must "
        f"name the SR `origin.kind: \"{SR_ORIGIN_KIND}\"` verbatim — the "
        f"discipline pivots on it"
    )


def test_canonical_section_cross_references_neighbor_skills(
    plugin_root: Path,
) -> None:
    """REQ-6 Scenario 1 (d): the canonical section cross-references the
    three neighbor surfaces — the frontend agent body, the backend agent
    body, and the team-spawning skill — so a reader who lands here can find
    every layer."""
    body = _read_skill_body(plugin_root, "common-pipeline-conventions")
    section = _section_body(body, "## Frontend missing-API discipline")
    assert "frontend.md" in section, (
        "the canonical section must cross-reference `agents/frontend.md` so "
        "readers can find the per-agent statement of the discipline"
    )
    assert "backend.md" in section, (
        "the canonical section must cross-reference `agents/backend.md` so "
        "readers can find the SR intake side of the discipline"
    )
    assert "team-spawning-and-review-gates" in section, (
        "the canonical section must cross-reference "
        "`team-spawning-and-review-gates` so readers can find the SR "
        "origin-kind enumeration + the routing"
    )


# ---- Cross-agent consistency on the kind name ------------------------------


def test_three_layers_use_same_sr_origin_kind_verbatim(
    plugin_root: Path,
) -> None:
    """All three layers (frontend agent, backend agent, team-spawning skill)
    must use the exact same SR origin-kind string. Any drift on the spelling
    is a contract violation — the orchestrator matches on the literal."""
    frontend = _read_agent_body(plugin_root, "frontend")
    backend = _read_agent_body(plugin_root, "backend")
    team_spawning = _read_skill_body(plugin_root, "team-spawning-and-review-gates")
    canonical = _read_skill_body(plugin_root, "common-pipeline-conventions")
    interaction = _read_skill_body(plugin_root, "interaction-completeness")
    for layer_name, layer_body in (
        ("agents/frontend.md", frontend),
        ("agents/backend.md", backend),
        ("skills/team-spawning-and-review-gates/SKILL.md", team_spawning),
        ("skills/common-pipeline-conventions/SKILL.md", canonical),
        ("skills/interaction-completeness/SKILL.md", interaction),
    ):
        assert SR_ORIGIN_KIND in layer_body, (
            f"{layer_name} must contain the verbatim SR origin-kind "
            f"`{SR_ORIGIN_KIND}` — cross-layer consistency on the literal "
            f"is what makes the orchestrator's match work"
        )


def test_three_layers_use_same_pending_backend_classification(
    plugin_root: Path,
) -> None:
    """The `pending-backend` classification name is used by both the
    interaction-completeness skill (where it's defined) and the canonical
    discipline section (where it's referenced as the wire-up target).
    Frontend + backend agent bodies need not name it (they use the SR
    origin-kind), but the two skills MUST agree on the spelling."""
    interaction = _read_skill_body(plugin_root, "interaction-completeness")
    canonical = _read_skill_body(plugin_root, "common-pipeline-conventions")
    for layer_name, layer_body in (
        ("skills/interaction-completeness/SKILL.md", interaction),
        ("skills/common-pipeline-conventions/SKILL.md", canonical),
    ):
        assert "pending-backend" in layer_body, (
            f"{layer_name} must contain the verbatim classification name "
            f"`pending-backend` — the spelling must agree across the two "
            f"skills that reference it"
        )
