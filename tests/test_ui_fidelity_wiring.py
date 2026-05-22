"""ui-interaction-fidelity REQ-006 / REQ-011.1-3 — pipeline + discipline wiring.

REQ-006 wires the new `interaction-completeness` verification team and the v6
`ui_interaction_review` review-gate field into the pipeline and the surrounding
discipline: `architect-team-pipeline` (Phase 5 invokes the team, Phase 3 names
the field), `playwright-user-flows` (references the field, the confirmed-stub
mechanism, placeholder-page detection, and the verification team),
`team-spawning-and-review-gates` (documents the v6 evidence schema and the new
field), and the `frontend` / `integration` agents (emit the field, honor the
confirmed-stub + no-unconfirmed-placeholder-pages rules).

REQ-011.1/11.2/11.3 wires the `dynamic-value-discovery` skill into the
developer (`frontend` / `backend`), the architect (`system-architect` agent +
the `design-fidelity-mapping` skill — the DESIGN_MAP classifies each per-screen
value static/dynamic and names the data source), and the evaluator.

These structural tests assert the wiring is genuinely PRESENT across the
skills and agents this teammate owns, so it cannot silently regress. They are
the qualifying test kind for this infra slice (no frontend, no HTTP API). The
schema-validation behavior of `ui_interaction_review` itself, and the
registration of the new skills/agent, are sibling teammates' tasks and are
intentionally NOT re-asserted here. Style follows `tests/test_hooks_structure.py`
and `tests/test_interaction_completeness.py`.
"""
from pathlib import Path

import pytest

# --- file paths this teammate's wiring touches ------------------------------

PIPELINE = ("skills", "architect-team-pipeline", "SKILL.md")
PLAYWRIGHT = ("skills", "playwright-user-flows", "SKILL.md")
TEAM_SPAWNING = ("skills", "team-spawning-and-review-gates", "SKILL.md")
DESIGN_FIDELITY = ("skills", "design-fidelity-mapping", "SKILL.md")
INTERACTION_COMPLETENESS = ("skills", "interaction-completeness", "SKILL.md")
FRONTEND = ("agents", "frontend.md")
BACKEND = ("agents", "backend.md")
INTEGRATION = ("agents", "integration.md")
SYSTEM_ARCHITECT = ("agents", "system-architect.md")
INTERACTION_REVIEWER = ("agents", "interaction-reviewer.md")
TEST_COMPLETENESS_VERIFIER = ("agents", "test-completeness-verifier.md")

# The three interaction gap kinds REQ-006/011 route as solution requirements.
INTERACTION_GAP_KINDS = ("unwired-control", "placeholder-page", "hardcoded-dynamic-value")

# The genuine user-interaction calls a real Playwright flow must use.
USER_INTERACTION_CALLS = (
    "page.click",
    "page.fill",
    "page.selectOption",
    "page.check",
    "page.press",
    "page.setInputFiles",
)


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    text = target.read_text(encoding="utf-8")
    assert text.strip(), f"{target} is empty"
    return text


# === REQ-006 — architect-team-pipeline wiring ===============================


def test_pipeline_references_interaction_completeness(plugin_root: Path) -> None:
    """The pipeline skill must reference the interaction-completeness team."""
    content = _read(plugin_root, PIPELINE)
    assert "interaction-completeness" in content, (
        "architect-team-pipeline SKILL.md does not reference the "
        "interaction-completeness team"
    )


def test_pipeline_phase_5_invokes_interaction_completeness_team(plugin_root: Path) -> None:
    """Phase 5 must invoke the interaction-completeness team for an in-scope
    frontend slice — its mandatory cross-layer home."""
    content = _read(plugin_root, PIPELINE)
    phase5_marker = "## Phase 5 — Cross-Layer Integration"
    phase6_marker = "## Phase 6 — Outer Loop"
    assert phase5_marker in content, "architect-team-pipeline SKILL.md has no Phase 5 section"
    assert phase6_marker in content, "architect-team-pipeline SKILL.md has no Phase 6 section"
    phase5 = content[content.index(phase5_marker):content.index(phase6_marker)]
    assert "interaction-completeness" in phase5, (
        "Phase 5 of architect-team-pipeline SKILL.md does not invoke the "
        "interaction-completeness team"
    )
    assert "interaction-reviewer" in phase5, (
        "Phase 5 does not spawn the interaction-reviewer agents"
    )
    lower = phase5.lower()
    assert "parallel" in lower, (
        "Phase 5's interaction-completeness invocation does not run the reviewers in parallel"
    )


def test_pipeline_phase_3_names_ui_interaction_review_field(plugin_root: Path) -> None:
    """The Phase 3 review-gate description must name the ui_interaction_review field."""
    content = _read(plugin_root, PIPELINE)
    phase3_marker = "## Phase 3 — Team Review Gate"
    phase3b_marker = "## Phase 3b"
    assert phase3_marker in content, "architect-team-pipeline SKILL.md has no Phase 3 section"
    assert phase3b_marker in content, "architect-team-pipeline SKILL.md has no Phase 3b section"
    phase3 = content[content.index(phase3_marker):content.index(phase3b_marker)]
    assert "ui_interaction_review" in phase3, (
        "Phase 3 review-gate description of architect-team-pipeline SKILL.md "
        "does not name the ui_interaction_review field"
    )


def test_pipeline_phase_3_describes_ui_interaction_review_semantics(plugin_root: Path) -> None:
    """The Phase 3 description must give the pass / n-a / fail semantics."""
    content = _read(plugin_root, PIPELINE)
    phase3 = content[content.index("## Phase 3 — Team Review Gate"):content.index("## Phase 3b")]
    for value in ('"pass"', '"n/a"', '"fail"'):
        assert value in phase3, (
            f"Phase 3's ui_interaction_review description does not give the {value} semantics"
        )


def test_pipeline_phase_7_walks_interaction_completeness(plugin_root: Path) -> None:
    """Phase 7 master review confirms the interaction-completeness team reached
    `satisfied` for every frontend feature — mirroring the editability check."""
    content = _read(plugin_root, PIPELINE)
    phase7 = content[content.index("## Phase 7 — Master Review"):content.index("## Phase 8")]
    assert "interaction-completeness" in phase7, (
        "Phase 7 master review does not walk the interaction-completeness team"
    )


# === REQ-006 — playwright-user-flows wiring =================================


def test_playwright_references_interaction_completeness_team(plugin_root: Path) -> None:
    """playwright-user-flows must reference the independent interaction-completeness
    verification team."""
    content = _read(plugin_root, PLAYWRIGHT)
    assert "interaction-completeness" in content, (
        "playwright-user-flows SKILL.md does not reference the interaction-completeness "
        "verification team"
    )
    assert "interaction-reviewer" in content, (
        "playwright-user-flows SKILL.md does not name the interaction-reviewer team"
    )


def test_playwright_references_ui_interaction_review_field(plugin_root: Path) -> None:
    """playwright-user-flows must reference the v6 ui_interaction_review field."""
    content = _read(plugin_root, PLAYWRIGHT)
    assert "ui_interaction_review" in content, (
        "playwright-user-flows SKILL.md does not reference the ui_interaction_review field"
    )
    assert "v6" in content or "schema v6" in content.lower(), (
        "playwright-user-flows SKILL.md does not identify the evidence schema as v6"
    )


def test_playwright_references_confirmed_stub_mechanism(plugin_root: Path) -> None:
    """playwright-user-flows must reference the confirmed-stub mechanism."""
    content = _read(plugin_root, PLAYWRIGHT)
    lower = content.lower()
    assert "confirmed-stub" in content, (
        "playwright-user-flows SKILL.md does not reference the confirmed-stub mechanism"
    )
    assert "user confirmation" in lower or "explicit user confirmation" in lower, (
        "playwright-user-flows SKILL.md does not state confirmed-stub needs user confirmation"
    )


def test_playwright_references_placeholder_page_detection(plugin_root: Path) -> None:
    """playwright-user-flows must reference placeholder-page detection."""
    content = _read(plugin_root, PLAYWRIGHT)
    lower = content.lower()
    assert "placeholder-page" in content or "placeholder page" in lower, (
        "playwright-user-flows SKILL.md does not reference placeholder-page detection"
    )
    assert "coming soon" in lower, (
        "playwright-user-flows SKILL.md placeholder-page reference omits the coming-soon signal"
    )


def test_playwright_flags_vacuous_navigate_and_assert(plugin_root: Path) -> None:
    """The interaction-completeness reference must explain test-authenticity —
    a direct API call and a vacuous navigate-and-assert are both not genuine flows."""
    content = _read(plugin_root, PLAYWRIGHT)
    lower = content.lower()
    assert "navigate-and-assert" in lower, (
        "playwright-user-flows SKILL.md does not flag a vacuous navigate-and-assert"
    )
    assert "page.request" in content, (
        "playwright-user-flows SKILL.md does not contrast a genuine flow with page.request.*"
    )


# === REQ-006 — team-spawning-and-review-gates wiring ========================


def test_team_spawning_documents_ui_interaction_review(plugin_root: Path) -> None:
    """team-spawning-and-review-gates must document the ui_interaction_review field."""
    content = _read(plugin_root, TEAM_SPAWNING)
    assert "ui_interaction_review" in content, (
        "team-spawning-and-review-gates SKILL.md does not document ui_interaction_review"
    )


def test_team_spawning_documents_v6_schema(plugin_root: Path) -> None:
    """The schema must be documented as v6 — the version references are updated."""
    content = _read(plugin_root, TEAM_SPAWNING)
    assert '"schema_version": 6' in content, (
        "team-spawning-and-review-gates SKILL.md evidence example is not schema_version 6"
    )
    assert "v6" in content, (
        "team-spawning-and-review-gates SKILL.md does not reference the v6 schema"
    )


def test_team_spawning_ui_interaction_review_value_semantics(plugin_root: Path) -> None:
    """The field must be documented with pass / n/a / fail value semantics —
    mirroring how visual_fidelity_review is documented."""
    content = _read(plugin_root, TEAM_SPAWNING)
    # Locate the validity bullet for ui_interaction_review.
    marker = "`ui_interaction_review` must be one of"
    assert marker in content, (
        "team-spawning-and-review-gates SKILL.md does not document the "
        "ui_interaction_review valid value set"
    )
    idx = content.index(marker)
    bullet = content[idx:idx + 1200]
    for value in ('"pass"', '"n/a"', '"fail"'):
        assert value in bullet, (
            f"the ui_interaction_review validity bullet omits the {value} value"
        )


def test_team_spawning_ui_interaction_review_blocks_fail(plugin_root: Path) -> None:
    """`fail` is blocked by the hook — the field's documentation must say so."""
    content = _read(plugin_root, TEAM_SPAWNING)
    idx = content.index("`ui_interaction_review` must be one of")
    bullet = content[idx:idx + 1200]
    lower = bullet.lower()
    assert "block" in lower, (
        "team-spawning-and-review-gates SKILL.md does not say the hook BLOCKS "
        "ui_interaction_review='fail'"
    )
    assert "solution requirement" in lower, (
        "the ui_interaction_review='fail' documentation does not route the gap "
        "through a solution requirement"
    )


def test_team_spawning_ui_interaction_review_note_required_on_na(plugin_root: Path) -> None:
    """`n/a` requires a non-empty ui_interaction_review_note — mirroring the
    visual_fidelity_review_note rule."""
    content = _read(plugin_root, TEAM_SPAWNING)
    marker = "`ui_interaction_review_note` is required"
    assert marker in content, (
        "team-spawning-and-review-gates SKILL.md does not document the "
        "ui_interaction_review_note n/a-note rule"
    )
    idx = content.index(marker)
    bullet = content[idx:idx + 600]
    assert 'ui_interaction_review == "n/a"' in bullet, (
        "the ui_interaction_review_note rule does not tie the note to the n/a value"
    )


def test_team_spawning_evidence_example_carries_ui_interaction_review(plugin_root: Path) -> None:
    """The JSON evidence example must carry the ui_interaction_review field."""
    content = _read(plugin_root, TEAM_SPAWNING)
    # The example uses an n/a value, so the note must be present alongside it.
    assert '"ui_interaction_review":' in content, (
        "team-spawning-and-review-gates SKILL.md evidence example omits ui_interaction_review"
    )
    assert '"ui_interaction_review_note":' in content, (
        "team-spawning-and-review-gates SKILL.md evidence example omits "
        "ui_interaction_review_note alongside the n/a value"
    )


def test_team_spawning_evidence_field_count_is_twelve(plugin_root: Path) -> None:
    """The self-review field count must read 12, not 11, after adding the v6 field."""
    content = _read(plugin_root, TEAM_SPAWNING)
    assert "12 top-level" in content, (
        "team-spawning-and-review-gates SKILL.md still says 11 top-level fields — "
        "the v6 ui_interaction_review field makes it 12"
    )
    assert "11 top-level" not in content, (
        "team-spawning-and-review-gates SKILL.md still has a stale '11 top-level' "
        "field-count reference"
    )


@pytest.mark.parametrize("gap_kind", INTERACTION_GAP_KINDS)
def test_team_spawning_solution_requirement_origin_kinds(plugin_root: Path, gap_kind: str) -> None:
    """The SR origin.kind enum must include the three interaction gap kinds."""
    content = _read(plugin_root, TEAM_SPAWNING)
    assert gap_kind in content, (
        f"team-spawning-and-review-gates SKILL.md SR schema omits the "
        f"interaction gap kind {gap_kind!r}"
    )


def test_team_spawning_lists_interaction_completeness_as_sr_consumer(plugin_root: Path) -> None:
    """The mandatory-SR-consumers section must list the interaction-completeness team."""
    content = _read(plugin_root, TEAM_SPAWNING)
    assert "`interaction-completeness` team" in content, (
        "team-spawning-and-review-gates SKILL.md does not list the "
        "interaction-completeness team as a mandatory SR consumer"
    )


# === REQ-011.2 — design-fidelity-mapping wiring =============================


def test_design_fidelity_references_dynamic_value_discovery(plugin_root: Path) -> None:
    """design-fidelity-mapping must reference the dynamic-value-discovery skill."""
    content = _read(plugin_root, DESIGN_FIDELITY)
    assert "dynamic-value-discovery" in content, (
        "design-fidelity-mapping SKILL.md does not reference the dynamic-value-discovery skill"
    )


def test_design_fidelity_classifies_values_static_or_dynamic(plugin_root: Path) -> None:
    """The DESIGN_MAP's per-screen specs must classify each value static/dynamic."""
    content = _read(plugin_root, DESIGN_FIDELITY)
    lower = content.lower()
    assert "static" in lower and "dynamic" in lower, (
        "design-fidelity-mapping SKILL.md does not classify per-screen values static/dynamic"
    )
    assert "value_class" in content, (
        "design-fidelity-mapping SKILL.md per-screen specs do not carry a value_class field"
    )
    # The classification lives inside the Per-Screen Visual Specs section.
    specs_marker = "## Per-Screen Visual Specs"
    assert specs_marker in content, (
        "design-fidelity-mapping SKILL.md has no Per-Screen Visual Specs section"
    )
    specs = content[content.index(specs_marker):]
    assert "value_class" in specs, (
        "the static/dynamic value classification is not in the Per-Screen Visual Specs section"
    )


def test_design_fidelity_names_data_source_for_dynamic_values(plugin_root: Path) -> None:
    """For each dynamic value the DESIGN_MAP must name its data source."""
    content = _read(plugin_root, DESIGN_FIDELITY)
    assert "data_source" in content, (
        "design-fidelity-mapping SKILL.md does not name a data_source for dynamic values"
    )
    lower = content.lower()
    assert "named data source" in lower or "named source" in lower, (
        "design-fidelity-mapping SKILL.md does not require a NAMED data source per "
        "dynamic value"
    )


def test_design_fidelity_classifies_from_context(plugin_root: Path) -> None:
    """The classification must be made from context, not the literal — the
    dynamic-value-discovery core rule."""
    content = _read(plugin_root, DESIGN_FIDELITY).lower()
    assert "from context" in content, (
        "design-fidelity-mapping SKILL.md does not classify values FROM CONTEXT"
    )


# === REQ-011.1 — developer agents apply dynamic-value-discovery =============


@pytest.mark.parametrize("agent", [FRONTEND, BACKEND])
def test_developer_agent_references_dynamic_value_discovery(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """Both frontend and backend agents must reference dynamic-value-discovery."""
    content = _read(plugin_root, agent)
    assert "dynamic-value-discovery" in content, (
        f"{agent[-1]} does not reference the dynamic-value-discovery skill"
    )


@pytest.mark.parametrize("agent", [FRONTEND, BACKEND])
def test_developer_agent_binds_dynamic_values_not_hardcode(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """Each developer agent must instruct: bind dynamic values, never hardcode
    the design's sample data."""
    content = _read(plugin_root, agent)
    lower = content.lower()
    assert "hardcode" in lower, (
        f"{agent[-1]} does not forbid hardcoding the design's sample data"
    )
    assert "bind" in lower or "bound" in lower, (
        f"{agent[-1]} does not instruct binding dynamic values"
    )
    assert "data source" in lower, (
        f"{agent[-1]} does not reference binding to a data source"
    )


# === REQ-011.2 — system-architect consults dynamic-value-discovery ==========


def test_system_architect_consults_dynamic_value_discovery(plugin_root: Path) -> None:
    """system-architect must consult dynamic-value-discovery when reviewing specs/designs."""
    content = _read(plugin_root, SYSTEM_ARCHITECT)
    assert "dynamic-value-discovery" in content, (
        "system-architect.md does not consult the dynamic-value-discovery skill"
    )
    lower = content.lower()
    assert "spec" in lower and "design" in lower, (
        "system-architect.md does not tie dynamic-value-discovery to reviewing specs/designs"
    )


# === REQ-006 — frontend / integration emit ui_interaction_review ============


@pytest.mark.parametrize("agent", [FRONTEND, INTEGRATION])
def test_agent_sets_ui_interaction_review(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """frontend and integration agents must instruct setting ui_interaction_review."""
    content = _read(plugin_root, agent)
    assert "ui_interaction_review" in content, (
        f"{agent[-1]} does not instruct the agent to set ui_interaction_review"
    )


@pytest.mark.parametrize("agent", [FRONTEND, INTEGRATION])
def test_agent_ui_interaction_review_value_semantics(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """The agent's ui_interaction_review instruction must give pass / n/a / fail."""
    content = _read(plugin_root, agent)
    for value in ('"pass"', '"n/a"', '"fail"'):
        assert value in content, (
            f"{agent[-1]} ui_interaction_review instruction omits the {value} value"
        )


@pytest.mark.parametrize("agent", [FRONTEND, INTEGRATION])
def test_agent_honors_confirmed_stub_mechanism(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """frontend and integration must honor the confirmed-stub mechanism —
    a confirmed-stub requires explicit user confirmation."""
    content = _read(plugin_root, agent)
    lower = content.lower()
    assert "confirmed-stub" in content, (
        f"{agent[-1]} does not reference the confirmed-stub mechanism"
    )
    assert "user confirmation" in lower or "explicit user confirmation" in lower, (
        f"{agent[-1]} does not state a confirmed-stub needs explicit user confirmation"
    )


@pytest.mark.parametrize("agent", [FRONTEND, INTEGRATION])
def test_agent_honors_no_unconfirmed_placeholder_pages_rule(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """frontend and integration must honor the no-unconfirmed-placeholder-pages rule."""
    content = _read(plugin_root, agent)
    lower = content.lower()
    assert "placeholder" in lower, (
        f"{agent[-1]} does not address placeholder pages"
    )
    assert "live page" in lower, (
        f"{agent[-1]} does not contrast a placeholder against the real live page"
    )


@pytest.mark.parametrize("agent", [FRONTEND, INTEGRATION])
def test_agent_ui_interaction_review_fail_is_blocked(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """Each agent must state the hook blocks ui_interaction_review='fail' and the
    gap routes through a solution requirement."""
    content = _read(plugin_root, agent)
    lower = content.lower()
    assert "block" in lower, (
        f"{agent[-1]} does not state the hook blocks ui_interaction_review='fail'"
    )
    assert "solution requirement" in lower, (
        f"{agent[-1]} does not route a ui_interaction_review gap through a solution requirement"
    )


@pytest.mark.parametrize("agent", [FRONTEND, INTEGRATION])
def test_agent_names_genuine_user_interaction_calls(
    plugin_root: Path, agent: tuple[str, ...]
) -> None:
    """The agent must name the genuine user-interaction calls a real flow uses."""
    content = _read(plugin_root, agent)
    present = [call for call in USER_INTERACTION_CALLS if call in content]
    assert "page.click" in content, (
        f"{agent[-1]} does not name page.click as a genuine user-interaction call"
    )
    assert len(present) >= 3, (
        f"{agent[-1]} names too few genuine user-interaction calls ({present}); "
        f"a genuine flow uses real page.click / page.fill / page.selectOption / etc."
    )
    assert "page.request" in content, (
        f"{agent[-1]} does not contrast a genuine flow against a page.request.* direct API call"
    )


# === Phase 7 coherence gaps — cross-slice consistency =======================


def test_system_architect_has_interaction_map_review_mode(plugin_root: Path) -> None:
    """GAP 1 — the Round-3 system-architect robustness review the
    interaction-completeness skill mandates must have a dedicated dispatch-mode
    section in the system-architect agent, alongside the other Round-3 modes,
    and the Hard rules must reference the interaction mode."""
    content = _read(plugin_root, SYSTEM_ARCHITECT)
    assert "## Interaction Map Review" in content, (
        "system-architect.md has no `## Interaction Map Review` dispatch-mode "
        "section — the interaction-completeness skill mandates a Round-3 "
        "system-architect robustness review with no agent-side instructions"
    )
    # The section must be modeled on the existing Round-3 robustness modes —
    # it carries the verdict-file path the architect writes.
    review_idx = content.index("## Interaction Map Review")
    next_section = content.index("## Visual Gap Synthesis")
    section = content[review_idx:next_section]
    assert ".architect-team/interaction/<feature-slug>/architect-review-pass" in section, (
        "the Interaction Map Review section does not state the architect-review "
        "verdict-file path under .architect-team/interaction/<feature-slug>/"
    )
    assert "interaction-completeness" in section, (
        "the Interaction Map Review section does not tie itself to the "
        "interaction-completeness skill"
    )
    # The Hard rules list (which already names the Diagnostic / Editability /
    # Visual modes) must name the interaction mode too.
    hard_rules = content[content.index("## Hard rules"):]
    assert "Interaction Map Review mode" in hard_rules, (
        "system-architect.md `## Hard rules` does not reference the "
        "Interaction Map Review dispatch mode alongside the other modes"
    )


def test_converged_interaction_map_path_is_consistent(plugin_root: Path) -> None:
    """GAP 2 — the converged-interaction-map path must agree across the
    producer side (interaction-completeness SKILL.md, interaction-reviewer.md)
    and the consumer side (test-completeness-verifier.md). All three must use
    the `.architect-team/interaction/<feature-slug>/converged-map-pass<P>-<ts>`
    form; the verifier must no longer reference the wrong `interaction-maps/`."""
    verifier = _read(plugin_root, TEST_COMPLETENESS_VERIFIER)
    skill = _read(plugin_root, INTERACTION_COMPLETENESS)
    reviewer = _read(plugin_root, INTERACTION_REVIEWER)

    converged_path_fragment = ".architect-team/interaction/<feature-slug>/converged-map-pass"

    # The verifier must read the converged map from the producer's real path.
    assert converged_path_fragment in verifier, (
        "test-completeness-verifier.md does not read the converged interaction "
        f"map from the producer path ({converged_path_fragment}...)"
    )
    # And must NOT reference the old, never-written `interaction-maps/` path.
    assert "interaction-maps/" not in verifier, (
        "test-completeness-verifier.md still references the stale "
        "`.architect-team/interaction-maps/<change>.json` path — the producer "
        "never writes there, so the cross-check would silently never find the map"
    )
    # The producer side must agree (and likewise never use `interaction-maps/`).
    assert converged_path_fragment in skill, (
        "interaction-completeness SKILL.md does not write the converged map to "
        f"the {converged_path_fragment}... path"
    )
    assert converged_path_fragment in reviewer, (
        "interaction-reviewer.md does not write the converged map to "
        f"the {converged_path_fragment}... path"
    )
    assert "interaction-maps/" not in skill and "interaction-maps/" not in reviewer, (
        "a producer-side file references the stale `interaction-maps/` path"
    )
