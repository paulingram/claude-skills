"""Structural tests for the `email-testing` skill (v0.9.34)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_NAME = "email-testing"
SKILL_PATH = f"skills/{SKILL_NAME}/SKILL.md"


def _read_body(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / SKILL_PATH)
    return body


# --- file + frontmatter ---


def test_skill_file_exists(plugin_root: Path) -> None:
    assert (plugin_root / SKILL_PATH).exists()


def test_skill_registered(plugin_root: Path) -> None:
    from tests.test_skills import EXPECTED_SKILLS
    assert SKILL_NAME in EXPECTED_SKILLS


def test_skill_frontmatter_valid(plugin_root: Path) -> None:
    fm, body = frontmatter.parse(plugin_root / SKILL_PATH)
    assert fm["name"] == SKILL_NAME
    assert isinstance(fm["description"], str) and len(fm["description"]) > 50
    assert body.strip()


# --- four phases present ---


REQUIRED_PHASE_HEADERS = (
    "## Phase E1",
    "## Phase E2",
    "## Phase E3",
    "## Phase E4",
)


@pytest.mark.parametrize("phase_header", REQUIRED_PHASE_HEADERS)
def test_phase_header_present(plugin_root: Path, phase_header: str) -> None:
    body = _read_body(plugin_root)
    assert phase_header in body, f"email-testing skill missing phase: {phase_header}"


# --- five non-negotiable rules ---


FIVE_RULES = (
    "Mailpit by default",
    "Every link gets tested",
    "Template source is read first",
    "Teardown is mandatory",
    "Credentials use env-var discipline",
)


@pytest.mark.parametrize("rule", FIVE_RULES)
def test_five_rules_named(plugin_root: Path, rule: str) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Five non-negotiable rules")
    assert start >= 0, "Five non-negotiable rules section must be present"
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert rule in section, f"rule `{rule}` not named in Five non-negotiable rules section"


# --- activation trigger documented ---


def test_activation_trigger_section_exists(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "## Activation trigger" in body or "activation trigger" in body.lower()


ACTIVATION_INDICATORS = (
    "file-path",
    "import",
    "function-call",
)


@pytest.mark.parametrize("indicator", ACTIVATION_INDICATORS)
def test_activation_indicator_documented(plugin_root: Path, indicator: str) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert indicator.lower() in body_lower, (
        f"Activation trigger must document `{indicator}` indicator kind"
    )


# --- E1 detection block ---


def test_e1_detection_block_schema(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E1")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for field in ("email_surface_detected", "indicators", "template_files", "email_service_files"):
        assert field in section, f"E1 detection block must document `{field}` field"


# --- E2 Mailpit provisioning ---


def test_e2_docker_provisioning(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "docker run" in section.lower(), "E2 must document Docker provisioning"
    assert "mailpit" in section.lower()
    assert "1025" in section, "E2 must use SMTP port 1025"
    assert "8025" in section, "E2 must use API port 8025"


def test_e2_binary_fallback(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "fallback" in section.lower() or "binary" in section.lower(), (
        "E2 must document a binary fallback when Docker is unavailable"
    )


def test_e2_teardown_mandatory(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    section_lower = section.lower()
    assert "teardown" in section_lower, "E2 must document mandatory teardown"
    assert "docker stop" in section_lower or "docker rm" in section_lower or "kill" in section_lower, (
        "E2 must document how to stop Mailpit"
    )


def test_e2_reachability_check(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "reachability" in section.lower() or "alive" in section.lower() or "health" in section.lower(), (
        "E2 must document a reachability check after provisioning"
    )


# --- E3 capture + template analysis ---


def test_e3_template_read_before_send(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    section_lower = section.lower()
    assert "read the template" in section_lower or "template source" in section_lower, (
        "E3 must mandate reading the template source before triggering the send"
    )


def test_e3_mailpit_api_polling(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "/api/v1/messages" in section, "E3 must document the Mailpit messages API"
    assert "poll" in section.lower() or "wait" in section.lower(), (
        "E3 must document polling/waiting for the email"
    )


def test_e3_link_classification_table(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for purpose in ("invite-accept", "password-reset", "email-verification", "unsubscribe",
                     "calendar-event", "destructive-action", "general-link"):
        assert purpose in section, f"E3 must classify `{purpose}` link purpose"


def test_e3_cross_check_template(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "cross-check" in section.lower() or "template_cross_check" in section, (
        "E3 must document cross-checking captured email against template"
    )


# --- E4 link follow + flow completion ---


def test_e4_link_follow(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "page.goto" in section.lower() or "navigate" in section.lower(), (
        "E4 must document Playwright navigation to each link"
    )


PURPOSE_FLOWS = (
    "invite-accept",
    "password-reset",
    "email-verification",
    "unsubscribe",
    "calendar-event",
    "destructive-action",
)


@pytest.mark.parametrize("purpose", PURPOSE_FLOWS)
def test_e4_purpose_specific_flow(plugin_root: Path, purpose: str) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert purpose in section, f"E4 must document flow completion for `{purpose}` links"


def test_e4_per_link_verdicts(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for verdict in ("pass", "fail", "env-failure"):
        assert verdict in section, f"E4 must document `{verdict}` per-link verdict"


def test_e4_result_schema(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for field in ("email_test_results", "links_tested", "links_passed", "links_failed",
                   "per_link_verdicts", "overall_verdict", "mailpit_teardown"):
        assert field in section, f"E4 result schema must include `{field}`"


# --- project-level configuration ---


def test_project_override_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "## Email Testing" in body or "design.md" in body, (
        "Skill must document the project-level design.md override mechanism"
    )


# --- hard rules ---


def test_hard_rules_section_exists(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "## Hard rules" in body


HARD_RULES_KEYWORDS = (
    "template source",
    "every",
    "teardown",
    "credential",
    "direct API",
    "footer link",
)


@pytest.mark.parametrize("keyword", HARD_RULES_KEYWORDS)
def test_hard_rule_keyword_present(plugin_root: Path, keyword: str) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Hard rules")
    assert start >= 0
    section = body[start:]
    assert keyword.lower() in section.lower(), (
        f"Hard rules must mention `{keyword}`"
    )


# --- integration points ---


CONSUMER_AGENTS = ("bug-replicator", "flow-executor", "integration")


@pytest.mark.parametrize("agent", CONSUMER_AGENTS)
def test_integration_point_documented(plugin_root: Path, agent: str) -> None:
    body = _read_body(plugin_root)
    assert agent in body, f"Skill must document integration with `{agent}` agent"


# --- does not create its own agent or command ---


def test_no_dedicated_agent(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "does not create its own agent" in body_lower or "no new agent" in body_lower or "not create" in body_lower


def test_no_dedicated_command(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "does not create its own" in body_lower or "no new command" in body_lower or "not create" in body_lower


# --- SMTP indicators documented ---


SMTP_INDICATORS = (
    "nodemailer",
    "sendgrid",
    "ses",
    "postmark",
    "mailgun",
    "resend",
)


@pytest.mark.parametrize("indicator", SMTP_INDICATORS)
def test_smtp_indicator_documented(plugin_root: Path, indicator: str) -> None:
    body = _read_body(plugin_root)
    assert indicator.lower() in body.lower(), (
        f"Skill must list `{indicator}` as an SMTP/transactional-email import indicator"
    )


# --- Mailpit API documented ---


def test_mailpit_api_base_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "localhost:8025" in body or "127.0.0.1:8025" in body, (
        "Skill must document the Mailpit API base URL"
    )


def test_waitforemail_helper_pattern(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "waitForEmail" in body, (
        "Skill must document the waitForEmail Playwright helper pattern"
    )
