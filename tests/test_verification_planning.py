"""v3.66.0 -- verification is a CHOICE among venues, never a lookup of one.

Root cause (review 2026-08-28, from the field report "it says 'I need to wait
before deploying to prod' when there are better ways to test"): across 120
instruction files no rule asked an agent to ENUMERATE the ways a claim could be
verified and pick the cheapest faithful one; ~10 rules named a mandatory venue
for one gate, the expensive path was the only one the gates could see, and the
system pre-named five "I am stuck until the environment changes" verdicts
(`cannot-verify-without-deploy`, `env-failure`, `blocked`, ...) with no
counterpart meaning "I found a cheaper faithful method". The one corrective
(v3.57.0) sat at line 2311 of a 2348-line file.

This module pins the closure: a `verification-planning` skill (the enumerate-
and-choose primitive + the `cheaper-faithful-method-found` counterpart), the
pointers from every venue-deciding surface, a `## Read this first` section at
the TOP of common-pipeline-conventions, and a Layer-3 detector that refuses a
`cannot-verify-without-deploy` verdict carrying no verification plan.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface, surface_read

from pathlib import Path

from hooks.vao.live_verification import verify_target_element_measured

SKILL = ("skills", "verification-planning", "SKILL.md")
CONVENTIONS = ("skills", "common-pipeline-conventions", "SKILL.md")

VENUES = ("local run", "dev environment", "replay", "seeded fixture", "production")


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
        return skill_surface(parts[1], root=plugin_root)
    if len(parts) == 2 and parts[0] == "agents" and parts[1].endswith(".md"):
        return agent_surface(parts[1], root=plugin_root)
    return surface_read(target)


def _section(body: str, heading: str) -> str:
    start = body.find(heading)
    assert start >= 0, f"heading {heading!r} missing"
    nxt = body.find("\n## ", start + len(heading))
    return body[start:nxt] if nxt > 0 else body[start:]


def _description_value(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("description:"):
            return line[len("description:"):].strip()
    raise AssertionError("frontmatter has no description")


# ---------------------------------------------------------------------------
# 1. The skill exists and states the primitive
# ---------------------------------------------------------------------------


def test_skill_exists_with_clean_frontmatter(plugin_root: Path) -> None:
    body = _read(plugin_root, *SKILL)
    assert body.startswith("---\nname: verification-planning\n") or body.startswith("---\r\nname: verification-planning")
    desc = _description_value(body)
    assert desc, "description must be non-empty"
    inner = desc.strip('"')
    assert ": " not in inner, "the house frontmatter rule: no colon-space inside the description"


def test_skill_enumerates_every_venue(plugin_root: Path) -> None:
    low = _read(plugin_root, *SKILL).lower()
    for venue in VENUES:
        assert venue in low, f"the venue menu must name {venue!r}"


def test_skill_requires_cheapest_faithful_choice_with_a_recorded_plan(plugin_root: Path) -> None:
    body = _read(plugin_root, *SKILL)
    low = body.lower()
    assert "cheapest faithful" in low
    for field in ("venues_considered", "chosen_venue", "why_cheaper_venues_cannot_exhibit"):
        assert field in body, f"the verification_plan artifact must carry {field}"
    assert "verification_plan" in body


def test_skill_names_the_counterpart_verdict(plugin_root: Path) -> None:
    body = _read(plugin_root, *SKILL)
    assert "cheaper-faithful-method-found" in body
    assert "cannot-verify-without-deploy" in body, (
        "the skill must position the counterpart against the stuck verdict it answers"
    )


def test_skill_forbids_waiting_when_the_run_can_provide_the_venue(plugin_root: Path) -> None:
    low = _read(plugin_root, *SKILL).lower()
    assert "local-dev-test-discipline" in low, "must point at the v3.57.0 discipline"
    assert "wait" in low and "provide" in low
    assert "self-imposed" in low, "the no-self-imposed-limits rule applies to the search for venues too"


# ---------------------------------------------------------------------------
# 2. Every venue-deciding surface points at it
# ---------------------------------------------------------------------------


def test_playwright_user_flows_points_at_verification_planning(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "playwright-user-flows", "SKILL.md")
    assert "verification-planning" in body


def test_dev_api_integration_testing_points_at_verification_planning(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "dev-api-integration-testing", "SKILL.md")
    assert "verification-planning" in body


def test_integration_agent_no_longer_forbids_the_cheaper_method_outright(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "integration.md")
    assert "you do NOT substitute static analysis" not in body, (
        "the blanket 'escalate blocked' instruction is the defect"
    )
    assert "verification-planning" in body
    assert "local-dev-test-discipline" in body or "provide" in body.lower()


def test_qa_replayer_requires_a_plan_behind_cannot_verify_without_deploy(plugin_root: Path) -> None:
    body = _read(plugin_root, "agents", "qa-replayer.md")
    assert "verification_plan" in body
    assert "cheaper-faithful-method-found" in body


def test_expensive_verification_debugging_fires_at_planning_time(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "expensive-verification-debugging", "SKILL.md")
    assert "verification-planning" in body
    low = body.lower()
    assert "planning time" in low or "before the first cycle" in low


def test_bug_fix_pipeline_points_at_verification_planning(plugin_root: Path) -> None:
    body = _read(plugin_root, "skills", "bug-fix-pipeline", "SKILL.md")
    assert "verification-planning" in body


# ---------------------------------------------------------------------------
# 3. The conventions file: read-first section at the TOP, accurate preamble
# ---------------------------------------------------------------------------


def test_conventions_carries_a_read_first_section_near_the_top(plugin_root: Path) -> None:
    body = _read(plugin_root, *CONVENTIONS)
    idx = body.find("## Read this first")
    assert idx >= 0, "common-pipeline-conventions must open with a ranked read-first section"
    assert idx < 12000, f"the read-first section must sit at the TOP of the file (found at byte {idx})"
    section = _section(body, "## Read this first")
    low = section.lower()
    for name in ("verification-planning", "self-imposed", "local-dev-test-discipline",
                 "unbounded solving", "evidence before assertion"):
        assert name in low, f"the read-first section must name {name!r}"


def test_conventions_preamble_no_longer_claims_four_conventions(plugin_root: Path) -> None:
    body = _read(plugin_root, *CONVENTIONS)
    head = body[:6000].lower()
    assert "share four cross-cutting disciplines" not in head
    assert "the four conventions:" not in head


def test_conventions_operating_rules_are_labelled_as_authoring_rules(plugin_root: Path) -> None:
    body = _read(plugin_root, *CONVENTIONS)
    section = _section(body, "## Operating rules (non-negotiable)")
    low = section.lower()
    assert "authoring rules" in low, (
        "the section must say it governs AUTHORING this file, and point at '## Read this first'"
    )
    assert "read this first" in low


def test_conventions_defines_the_no_self_imposed_limits_discipline(plugin_root: Path) -> None:
    body = _read(plugin_root, *CONVENTIONS)
    section = _section(body, "## No self-imposed limits discipline")
    low = section.lower()
    assert "explicitly" in low and "user" in low
    for token in ("turn", "budget", "cycle", "time"):
        assert token in low, f"the discipline must name the {token} form of self-rationing"


# ---------------------------------------------------------------------------
# 4. The detector: a stuck verdict with no plan is a gap
# ---------------------------------------------------------------------------


def _stuck_artifact(**extra) -> dict:
    base = {
        "verdict": "cannot-verify",
        "reachability_status": "cannot-verify-without-deploy",
        "target_element_selector": "[data-testid=archive]",
        "measured_element_selector": None,
    }
    base.update(extra)
    return base


def _plan() -> dict:
    return {
        "venues_considered": [
            {"venue": "local run", "unique_provides": "nothing this claim needs",
             "faithful": False, "why_not": "the route needs the deployed auth proxy"},
            {"venue": "dev environment", "unique_provides": "deployed auth proxy",
             "faithful": True, "why_not": None},
        ],
        "chosen_venue": "dev environment",
        "why_cheaper_venues_cannot_exhibit": "the 401 is produced by the auth proxy that only exists deployed",
    }


def test_stuck_verdict_without_a_plan_is_a_gap() -> None:
    verdict = verify_target_element_measured(_stuck_artifact())
    sev = [g["severity"] for g in verdict["gaps"]]
    assert "stuck-without-verification-plan" in sev, verdict


def test_stuck_verdict_with_a_real_plan_is_not_flagged_for_the_plan() -> None:
    verdict = verify_target_element_measured(_stuck_artifact(verification_plan=_plan()))
    sev = [g["severity"] for g in verdict["gaps"]]
    assert "stuck-without-verification-plan" not in sev, verdict


def test_a_plan_with_a_single_venue_is_not_a_plan() -> None:
    plan = _plan()
    plan["venues_considered"] = plan["venues_considered"][1:]
    verdict = verify_target_element_measured(_stuck_artifact(verification_plan=plan))
    sev = [g["severity"] for g in verdict["gaps"]]
    assert "stuck-without-verification-plan" in sev, "one venue enumerated is a lookup, not a choice"


def test_reached_verdict_is_untouched_by_the_plan_rule() -> None:
    verdict = verify_target_element_measured({
        "verdict": "pass", "reachability_status": "reached",
        "target_element_selector": "[data-testid=archive]",
        "measured_element_selector": "[data-testid=archive]",
        "target_element_semantic_label": "archive", "measured_element_semantic_label": "archive",
    })
    sev = [g["severity"] for g in verdict["gaps"]]
    assert "stuck-without-verification-plan" not in sev
