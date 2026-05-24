"""Structural tests for the `ux-test-builder` skill (v0.9.29)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import frontmatter


SKILL_NAME = "ux-test-builder"
SKILL_PATH = f"skills/{SKILL_NAME}/SKILL.md"


def _read_body(plugin_root: Path) -> str:
    _, body = frontmatter.parse(plugin_root / SKILL_PATH)
    return body


REQUIRED_PHASE_HEADERS = (
    "## Phase U0",
    "## Phase U1",
    "## Phase U2",
    "## Phase U3",
    "## Phase U4",
    "## Phase U5",
    "## Phase U6",
    "## Phase U7",
    "## Phase U8",
    "## Phase U9",
)

FIVE_DISCIPLINES = (
    "Real-site testing",
    "3-agent convergence",
    "Literal-first-then-expand",
    "Bug-route-not-just-document",
    "Explorer-expansion-is-context-aware",
)


def test_skill_file_exists(plugin_root: Path) -> None:
    assert (plugin_root / SKILL_PATH).exists()


def test_skill_registered(plugin_root: Path) -> None:
    from tests.test_skills import EXPECTED_SKILLS
    assert SKILL_NAME in EXPECTED_SKILLS


@pytest.mark.parametrize("phase_header", REQUIRED_PHASE_HEADERS)
def test_phase_header_present(plugin_root: Path, phase_header: str) -> None:
    body = _read_body(plugin_root)
    assert phase_header in body, f"ux-test-builder skill missing phase: {phase_header}"


@pytest.mark.parametrize("discipline", FIVE_DISCIPLINES)
def test_five_disciplines_named(plugin_root: Path, discipline: str) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Five non-negotiable disciplines")
    assert start >= 0, "Five disciplines section must be present"
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert discipline in section, f"discipline `{discipline}` not named in Five disciplines section"


def test_intake_schema_documented(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U0")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    for field in ("schema_version", "persona_slug", "persona_description", "objectives", "target", "credentials", "env_var", "auth_flow"):
        assert field in section, f"intake schema must document field `{field}`"


def test_credentials_env_var_only_rule(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U0")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "NEVER persisted" in section or "never persisted" in section, "U0 must state secrets are never persisted"
    assert "env_var" in section.lower(), "U0 must document env-var-name-only handling"


def test_u1_reuses_intake_and_mapping(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U1")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "intake-and-mapping" in section


def test_u2_literal_is_flow_1(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U2")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "flow #1" in section, "U2 must state the literal flow becomes flow #1"
    assert "playwright-user-flows" in section


def test_u3_documents_3_explorers_independent(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U3")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "3 `flow-explorer`" in section or "three" in section.lower() or "PARALLEL" in section
    assert "10-15" in section, "U3 must specify the 10-15 additional flows range"
    assert "do NOT consult" in section or "do not consult" in section.lower(), "U3 must state explorers do not consult each other"
    assert "rephrase" in section.lower(), "U3 must forbid rephrasing the literal"


def test_u4_semantic_dedup(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U4")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "semantic" in section.lower() or "SEMANTICALLY" in section, "U4 must mandate semantic dedup"
    assert "source_explorers" in section, "U4 must document source_explorers attribution"


def test_u6_documents_3_executors_redundant(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U6")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "3 `flow-executor`" in section or "three" in section.lower()
    for verdict in ("pass", "fail", "flaky", "env-failure"):
        assert verdict in section, f"U6 must name verdict `{verdict}`"
    assert "redundancy" in section.lower() or "3 executors" in section, "U6 must state the 3-executor redundancy"


def test_u7_3_cycle_bounded_convergence(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U7")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "3 re-examination cycles" in section or "3-cycle" in section.lower() or "bounded at 3" in section.lower()
    assert "domain gate" in section.lower(), "U7 escalation must be named as a domain gate"


def test_u8_ux_flow_failure_routing(plugin_root: Path) -> None:
    body = _read_body(plugin_root)
    start = body.find("## Phase U8")
    next_h2 = body.find("\n## ", start + 1)
    section = body[start:next_h2] if next_h2 > 0 else body[start:]
    assert "ux-flow-failure" in section, "U8 must name origin.kind: ux-flow-failure"
    assert "bug-fix-pipeline" in section, "U8 must route bugs to bug-fix-pipeline"
    assert "does NOT block" in section or "does not block" in section.lower(), "U8 must state UX test does not block on bug fixes"
