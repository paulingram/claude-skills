"""Tests for email-testing skill's template analysis + link classification + flow completion rules (v0.9.34)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_PATH = "skills/email-testing/SKILL.md"


def _read_body(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / SKILL_PATH)
    return body


# ─── Template file extension indicators ──────────────────────────────────


TEMPLATE_EXTENSIONS = ("html", "mjml", "ejs", "hbs", "pug", "liquid", "jinja2")


@pytest.mark.parametrize("ext", TEMPLATE_EXTENSIONS)
def test_template_extension_listed(plugin_root: Path, ext: str) -> None:
    body = _read_body(plugin_root)
    assert f"*.{ext}" in body or f".{ext}" in body, (
        f"Skill must list `*.{ext}` as an email template file extension"
    )


# ─── Path keywords for template detection ────────────────────────────────


TEMPLATE_PATH_KEYWORDS = (
    "email", "mail", "template", "notification",
    "invite", "welcome", "reset", "verify", "confirm",
)


@pytest.mark.parametrize("keyword", TEMPLATE_PATH_KEYWORDS)
def test_template_path_keyword_listed(plugin_root: Path, keyword: str) -> None:
    body = _read_body(plugin_root)
    assert keyword in body.lower(), (
        f"Skill must list `{keyword}` as a path keyword for template detection"
    )


# ─── Function-call indicators ────────────────────────────────────────────


FUNCTION_INDICATORS = (
    "sendMail",
    "sendEmail",
    "send_mail",
    "send_email",
    "deliver",
    "notify",
    "sendNotification",
    "send_notification",
    "sendInvite",
    "send_invite",
    "sendVerification",
    "sendPasswordReset",
    "sendWelcome",
)


@pytest.mark.parametrize("func", FUNCTION_INDICATORS)
def test_function_indicator_listed(plugin_root: Path, func: str) -> None:
    body = _read_body(plugin_root)
    assert func in body, (
        f"Skill must list `{func}` as a function-call indicator"
    )


# ─── Link classification completeness ───────────────────────────────────


LINK_URL_PATTERNS = {
    "invite": "invite-accept",
    "accept": "invite-accept",
    "reset": "password-reset",
    "password": "password-reset",
    "verify": "email-verification",
    "confirm": "email-verification",
    "unsubscribe": "unsubscribe",
    "calendar": "calendar-event",
    "delete": "destructive-action",
    "remove": "destructive-action",
    "cancel": "destructive-action",
    "opt-out": "unsubscribe",
    "preferences": "unsubscribe",
    "decline": "destructive-action",
}


@pytest.mark.parametrize("url_pattern,purpose", sorted(LINK_URL_PATTERNS.items()))
def test_url_pattern_mapped_to_purpose(plugin_root: Path, url_pattern: str, purpose: str) -> None:
    body = _read_body(plugin_root)
    # Both the URL pattern and its purpose must appear in the classification table area
    assert f"/{url_pattern}" in body or url_pattern in body, (
        f"Skill must map URL pattern `/{url_pattern}` in the link classification"
    )
    assert purpose in body, (
        f"Skill must define purpose `{purpose}` in the link classification"
    )


# ─── Non-testable link types ─────────────────────────────────────────────


def test_mailto_links_skipped(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "mailto" in body.lower(), "Skill must handle mailto: links"
    # mailto links should not be navigated
    assert "not-testable" in body.lower() or "skip" in body.lower() or "not a web link" in body.lower(), (
        "Skill must classify mailto: links as not testable"
    )


# ─── Flow completion assertions per purpose ──────────────────────────────


def test_invite_flow_includes_signup(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "sign-up" in body_lower or "signup" in body_lower or "create" in body_lower, (
        "invite-accept flow must include account sign-up / creation"
    )
    assert "fill" in body_lower, "invite-accept flow must include filling form fields"
    assert "submit" in body_lower, "invite-accept flow must include form submission"
    assert "success" in body_lower or "dashboard" in body_lower or "welcome" in body_lower, (
        "invite-accept flow must assert success state"
    )


def test_password_reset_flow_includes_new_password(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "new password" in body_lower or "new-password" in body_lower, (
        "password-reset flow must include setting a new password"
    )
    assert "fill" in body_lower, "password-reset flow must include filling form fields"
    assert "submit" in body_lower, "password-reset flow must include form submission"
    assert "success" in body_lower or "confirmation" in body_lower or "login" in body_lower, (
        "password-reset flow must assert success state"
    )


def test_calendar_flow_includes_ics_validation(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert ".ics" in body, "calendar-event flow must validate .ics file"
    body_lower = body.lower()
    for field in ("summary", "dtstart", "dtend", "organizer"):
        assert field.lower() in body_lower, (
            f"calendar-event flow must validate iCalendar field `{field}`"
        )


def test_destructive_flow_includes_confirmation(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "confirm" in body_lower, (
        "destructive-action flow must include a confirmation step"
    )
    assert "click" in body_lower, "destructive-action flow must include clicking confirm"
    assert "removed" in body_lower or "cancelled" in body_lower or "canceled" in body_lower, (
        "destructive-action flow must assert resource was removed/cancelled"
    )


# ─── Template cross-check rules ─────────────────────────────────────────


def test_missing_links_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "missing link" in body_lower or "missing" in body_lower, (
        "Skill must document the handling of links in template but missing from rendered email"
    )


def test_unexpected_links_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "unexpected link" in body_lower or "unexpected" in body_lower, (
        "Skill must document the handling of links in rendered email but not in template"
    )


# ─── UI interaction discipline (no direct API email sends) ───────────────


def test_no_direct_api_email_sends(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "direct api" in body_lower or "page.click" in body_lower, (
        "Skill must mandate email sends triggered via Playwright UI interaction, not direct API"
    )


# ─── Polling configuration documented ───────────────────────────────────


def test_polling_timeout_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "30000" in body or "30s" in body.lower() or "30 second" in body.lower(), (
        "Skill must document the email polling timeout (30s default)"
    )


def test_polling_interval_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "1000" in body or "1s" in body.lower() or "1 second" in body.lower(), (
        "Skill must document the email polling interval (1s default)"
    )


# ─── Overall verdict rules ──────────────────────────────────────────────


def test_overall_verdict_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    assert "overall_verdict" in body, "Skill must document the overall_verdict field"


def test_overall_verdict_values(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    for verdict in ("pass", "fail", "env-failure"):
        assert verdict in body, f"overall_verdict must include `{verdict}` value"


# ─── Env-var credential discipline in email flows ────────────────────────


def test_env_var_discipline_for_email_flows(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    body_lower = body.lower()
    assert "env" in body_lower and ("var" in body_lower or "variable" in body_lower), (
        "Skill must mandate env-var discipline for credentials in email-linked flows"
    )
    assert "never" in body_lower and ("hardcoded" in body_lower or "hardcode" in body_lower or "hard-coded" in body_lower), (
        "Skill must prohibit hardcoded credentials"
    )


# ─── E3 template analysis schema + purpose identification ──────────────


def test_e3_template_purpose_identification(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    section_lower = section.lower()
    assert "subject" in section_lower, "E3 must document purpose identification via subject line"
    assert "cta" in section_lower or "primary" in section_lower, (
        "E3 must document purpose identification via CTA or primary link"
    )


def test_e3_link_pre_extraction(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "{{" in section or "${" in section or "<%" in section, (
        "E3 must document pre-extracting link patterns from template variables"
    )


def test_e3_template_analysis_schema(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for field in ("template_path", "purpose", "subject_pattern", "expected_links"):
        assert field in section, f"E3 template analysis schema must include `{field}`"


def test_e3_fragment_anchor_skip(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    section_lower = section.lower()
    assert "fragment" in section_lower or "anchor" in section_lower, (
        "E3 must document fragment-only (#) anchors as non-navigable"
    )


def test_e3_link_analysis_schema(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for field in ("email_id", "subject", "from", "to", "links", "template_cross_check"):
        assert field in section, f"E3 link analysis schema must include `{field}`"


# ─── E4 uncovered flow types ───────────────────────────────────────────


def test_e4_email_verification_flow(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    section_lower = section.lower()
    assert "confirmation" in section_lower or "verified" in section_lower, (
        "E4 email-verification flow must document confirmation page + status"
    )


def test_e4_unsubscribe_flow(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    section_lower = section.lower()
    assert "unsubscribe" in section_lower, "E4 must document unsubscribe flow"
    assert "confirmation" in section_lower or "success" in section_lower, (
        "E4 unsubscribe flow must assert success state"
    )


def test_e4_general_link_handling(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase E4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    section_lower = section.lower()
    assert "general" in section_lower or "general-link" in section_lower, (
        "E4 must document general-link handling"
    )
    assert "page-loaded" in section_lower or "not blank" in section_lower or "2xx" in section_lower or "not empty" in section_lower or "sufficient" in section_lower, (
        "E4 general-link must assert page loaded successfully"
    )
