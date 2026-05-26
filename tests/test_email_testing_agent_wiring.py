"""Cross-cutting wiring tests for v0.9.34 — email-testing skill + agent + pipeline references."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


def _read_body(plugin_root: Path, relpath: str) -> str:
    _, body = frontmatter.parse(plugin_root / relpath)
    return body


# ─── Agent sections ──────────────────────────────────────────────────────


AGENTS_WITH_EMAIL_SECTION = (
    "agents/bug-replicator.md",
    "agents/flow-executor.md",
    "agents/integration.md",
)


@pytest.mark.parametrize("agent_path", AGENTS_WITH_EMAIL_SECTION)
def test_agent_has_email_section(plugin_root: Path, agent_path: str) -> None:
    """Each consuming agent must have a v0.9.34 email-aware section."""
    body = _read_body(plugin_root, agent_path)
    body_lower = body.lower()
    assert "email" in body_lower and ("v0.9.34" in body or "email-testing" in body), (
        f"{agent_path} must contain a v0.9.34 email-aware section referencing the email-testing skill"
    )


@pytest.mark.parametrize("agent_path", AGENTS_WITH_EMAIL_SECTION)
def test_agent_references_email_testing_skill(plugin_root: Path, agent_path: str) -> None:
    """Each consuming agent must reference the `email-testing` skill by name."""
    body = _read_body(plugin_root, agent_path)
    assert "email-testing" in body, (
        f"{agent_path} must reference the `email-testing` skill"
    )


@pytest.mark.parametrize("agent_path", AGENTS_WITH_EMAIL_SECTION)
def test_agent_references_mailpit(plugin_root: Path, agent_path: str) -> None:
    """Each consuming agent must mention Mailpit."""
    body = _read_body(plugin_root, agent_path)
    assert "Mailpit" in body or "mailpit" in body.lower(), (
        f"{agent_path} must mention Mailpit provisioning"
    )


@pytest.mark.parametrize("agent_path", AGENTS_WITH_EMAIL_SECTION)
def test_agent_references_phase_e1(plugin_root: Path, agent_path: str) -> None:
    """Each consuming agent must reference Phase E1 (detection)."""
    body = _read_body(plugin_root, agent_path)
    assert "E1" in body, (
        f"{agent_path} must reference Phase E1 (email surface detection)"
    )


# ─── bug-replicator specifics ────────────────────────────────────────────


def test_bug_replicator_email_section_header(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "agents/bug-replicator.md")
    assert "## Email-aware reproduction" in body


def test_bug_replicator_email_as_regression_test(plugin_root: Path) -> None:
    """The email capture/link-follow persists in the .spec.ts replication artifact."""
    body = _read_body(plugin_root, "agents/bug-replicator.md")
    start = body.find("## Email-aware reproduction")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "regression test" in section.lower() or "qa-replayer" in section.lower(), (
        "bug-replicator email section must note that email steps persist as the regression test"
    )


def test_bug_replicator_template_reading(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "agents/bug-replicator.md")
    start = body.find("## Email-aware reproduction")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "template" in section.lower(), (
        "bug-replicator email section must mandate reading the email template source"
    )


# ─── flow-executor specifics ─────────────────────────────────────────────


def test_flow_executor_email_section_header(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "agents/flow-executor.md")
    assert "## Email flow execution" in body


def test_flow_executor_email_link_failure_verdict(plugin_root: Path) -> None:
    """An email link failure must force the flow's overall verdict to fail."""
    body = _read_body(plugin_root, "agents/flow-executor.md")
    start = body.find("## Email flow execution")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "fail" in section.lower() and "verdict" in section.lower(), (
        "flow-executor email section must state that email link failure forces fail verdict"
    )


def test_flow_executor_email_origin_kind(plugin_root: Path) -> None:
    """Email flow failures should route as origin.kind: email-flow-failure."""
    body = _read_body(plugin_root, "agents/flow-executor.md")
    assert "email-flow-failure" in body or "email-link-broken" in body, (
        "flow-executor must document the email failure origin kind or failure reason"
    )


# ─── integration agent specifics ─────────────────────────────────────────


def test_integration_email_section_header(plugin_root: Path) -> None:
    body = _read_body(plugin_root, "agents/integration.md")
    assert "## Email integration testing" in body


def test_integration_coverage_map_requirement(plugin_root: Path) -> None:
    """Email-sending requirements must include email-flow verification in acceptance criteria."""
    body = _read_body(plugin_root, "agents/integration.md")
    start = body.find("## Email integration testing")
    assert start >= 0
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "coverage map" in section.lower() or "acceptance criteria" in section.lower(), (
        "integration email section must link email testing to coverage map acceptance criteria"
    )


def test_integration_email_origin_kind(plugin_root: Path) -> None:
    """Email integration failures route as email-integration-failure."""
    body = _read_body(plugin_root, "agents/integration.md")
    assert "email-integration-failure" in body


# ─── Pipeline skill wiring ───────────────────────────────────────────────


PIPELINE_SKILLS = (
    "skills/bug-fix-pipeline/SKILL.md",
    "skills/architect-team-pipeline/SKILL.md",
    "skills/ux-test-builder/SKILL.md",
)


@pytest.mark.parametrize("skill_path", PIPELINE_SKILLS)
def test_pipeline_skill_references_email_testing(plugin_root: Path, skill_path: str) -> None:
    """Each pipeline skill must reference the email-testing skill."""
    body = _read_body(plugin_root, skill_path)
    assert "email-testing" in body, (
        f"{skill_path} must reference the `email-testing` skill"
    )


@pytest.mark.parametrize("skill_path", PIPELINE_SKILLS)
def test_pipeline_skill_mentions_mailpit(plugin_root: Path, skill_path: str) -> None:
    """Each pipeline skill must mention Mailpit."""
    body = _read_body(plugin_root, skill_path)
    assert "Mailpit" in body or "mailpit" in body.lower(), (
        f"{skill_path} must mention Mailpit"
    )


def test_bug_fix_pipeline_phase_b2_email_wiring(plugin_root: Path) -> None:
    """Bug-fix-pipeline's Phase B2 section must wire email testing."""
    body = _read_body(plugin_root, "skills/bug-fix-pipeline/SKILL.md")
    # Find Phase B2 section
    b2_start = body.find("## Phase B2")
    assert b2_start >= 0
    b3_start = body.find("## Phase B3")
    section = body[b2_start:b3_start] if b3_start > 0 else body[b2_start:]
    assert "email" in section.lower(), (
        "Phase B2 must wire email-aware reproduction"
    )


def test_architect_team_pipeline_phase_5_email_wiring(plugin_root: Path) -> None:
    """architect-team-pipeline's Phase 5 must wire email integration testing."""
    body = _read_body(plugin_root, "skills/architect-team-pipeline/SKILL.md")
    phase5_start = body.find("## Phase 5")
    assert phase5_start >= 0
    phase6_start = body.find("## Phase 6")
    section = body[phase5_start:phase6_start] if phase6_start > 0 else body[phase5_start:]
    assert "email" in section.lower(), (
        "Phase 5 must wire email integration testing"
    )


def test_ux_test_builder_phase_u5_email_wiring(plugin_root: Path) -> None:
    """ux-test-builder's Phase U5 must wire email-aware flow authoring."""
    body = _read_body(plugin_root, "skills/ux-test-builder/SKILL.md")
    u5_start = body.find("## Phase U5")
    assert u5_start >= 0
    u6_start = body.find("## Phase U6")
    section = body[u5_start:u6_start] if u6_start > 0 else body[u5_start:]
    assert "email" in section.lower(), (
        "Phase U5 must wire email-aware flow authoring"
    )
