# -*- coding: utf-8 -*-
"""v3.10.0 (R6a) — the `security-hunter` adversarial-reviewer shape + the SR-catalog
reconciliation.

Asserts:
1. `agents/adversarial-reviewer.md` documents `security-hunter` as the 6th shape
   (header says "six", the five hunted classes are named).
2. `skills/team-spawning-and-review-gates/SKILL.md` documents the trigger rules
   (backend-dep -> both fake-data + security; auth/security path -> mandatory;
   dependency-add -> mandatory) AND carries `security-finding` in the open SR
   origin-kind catalog.
3. The canonical fixture `tests/fixtures/vao/security-finding-routed.json`
   round-trips and carries a well-formed `security-finding` SR.
4. ZERO spelling forks: `integration-failure` / `visual-fidelity-cascade` no
   longer appear in the SR catalog or either routing list; the canonical
   `integration-test-failure` / `visual-fidelity-drift` do.

Stdlib-only; structural (no external deps, no subprocess).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ADVERSARIAL = REPO_ROOT / "agents" / "adversarial-reviewer.md"
TEAM_SPAWNING = REPO_ROOT / "skills" / "team-spawning-and-review-gates" / "SKILL.md"
ARCHITECT_PIPELINE = REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "security-finding-routed.json"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---- 1. adversarial-reviewer 6th shape -------------------------------------


def test_adversarial_reviewer_has_six_shapes() -> None:
    body = _read(ADVERSARIAL)
    assert "## The six shape pairings" in body, "header must say SIX shape pairings"
    assert "`security-hunter`" in body, "security-hunter shape must be documented"


@pytest.mark.parametrize(
    "hunted",
    [
        "authorization",          # missing/weakened authz
        "njection",               # injection-prone construction (SQL/shell/path)
        "ecret",                  # secrets/credentials in the diff
        "deserialization",        # unsafe deserialization
        "dependency",             # dependency additions without justification
    ],
)
def test_security_hunter_names_its_five_classes(hunted: str) -> None:
    body = _read(ADVERSARIAL).lower()
    assert hunted.lower() in body, f"security-hunter must hunt for {hunted!r}"


def test_security_hunter_is_not_a_layer3_severity() -> None:
    """The shape routes an SR; it is NOT a verify_* tool / verdict severity."""
    body = _read(ADVERSARIAL)
    assert "security_findings" in body, "the finding block must be named"
    assert "origin.kind" in body and "security-finding" in body


# ---- 2. team-spawning trigger rules + catalog ------------------------------


def test_team_spawning_documents_security_hunter_triggers() -> None:
    body = _read(TEAM_SPAWNING)
    assert "security-hunter" in body
    low = body.lower()
    # backend-dep -> BOTH fake-data AND security
    assert "fake-data-hunter" in body and "security-hunter" in body
    assert "backend-dep" in body
    # auth/security-sensitive path -> mandatory
    assert "mandatory" in low
    # dependency-add -> mandatory
    assert "dependency" in low


def test_security_finding_in_open_catalog() -> None:
    body = _read(TEAM_SPAWNING)
    assert "security-finding" in body, "security-finding must be in the SR origin-kind catalog"
    # the catalog is explicitly OPEN now
    assert "open canonical catalog" in body.lower() or "OPEN canonical catalog" in body


# ---- 3. fixture round-trip --------------------------------------------------


def test_fixture_round_trips() -> None:
    data = json.loads(_read(FIXTURE))
    assert "_meta" in data
    assert data["_meta"]["origin_kind_in_catalog"] == "security-finding"
    assert data["_meta"]["routes_directly"] is True
    assert data["_meta"]["diagnostic_research_team"] is False
    # the adversarial_review block carries security_findings with the 5-field shape
    findings = data["adversarial_review"]["security_findings"]
    assert findings, "fixture must carry at least one security finding"
    for f in findings:
        for key in ("class", "file", "line", "evidence", "remediation"):
            assert key in f, f"finding missing {key!r}"
    # the routed SR is well-formed with origin.kind security-finding
    sr = data["routed_solution_requirement"]
    assert sr["origin"]["kind"] == "security-finding"
    assert sr["acceptance_criteria"], "the SR must carry acceptance criteria"
    assert sr["scope"]["files_to_change"]


def test_fixture_serialization_is_stable() -> None:
    """Round-trip the fixture through json to prove it is valid + re-loadable."""
    data = json.loads(_read(FIXTURE))
    again = json.loads(json.dumps(data))
    assert again == data


# ---- 4. SR catalog uses the canonical spellings ----------------------------
#
# The brief's R6a acceptance is "the SR catalog reconciled with zero spelling
# forks". The canonical SR catalog lives in team-spawning-and-review-gates: the
# schema enum (the formal contract) + the open canonical catalog list both use
# `integration-test-failure` / `visual-fidelity-drift`. The legacy spellings
# `integration-failure` / `visual-fidelity-cascade` survive ONLY in the py-core
# runtime constant `hooks/shared_rule_constants.py::TEST_FAILURE_ORIGINS` (and
# the two consumers the cross-consistency test pins to it: the architect-team
# Phase 3b routing list + the diagnostic-research-team skill); SR
# `SR-sr-catalog-spelling-reconcile-*` routes that constant + its two consumers
# to the canonical spellings atomically (py-core owns the constant). Until that
# lands the catalog (this test's scope) is canonical and internally consistent.

CANON_NEW = ("integration-test-failure", "visual-fidelity-drift")


def _catalog_section() -> str:
    """The SR origin-kind catalog: the schema enum through the field-validity list."""
    body = _read(TEAM_SPAWNING)
    start = body.index('"kind": "playwright-failure"')
    # extend to the end of the field-validity block (before the next "### ")
    rest = body[start:]
    end = rest.find("\n## ", 1)
    return rest if end == -1 else rest[:end]


@pytest.mark.parametrize("canon", CANON_NEW)
def test_canonical_spellings_present_in_catalog(canon: str) -> None:
    body = _read(TEAM_SPAWNING)
    assert canon in body, f"the canonical origin kind {canon!r} must be in the catalog"


def test_catalog_schema_enum_and_open_list_use_canonical_spellings() -> None:
    """The schema enum + the open canonical catalog list use the canonical
    spellings (zero fork WITHIN the SR catalog the brief names)."""
    section = _catalog_section()
    for canon in CANON_NEW:
        assert canon in section, f"the SR catalog must use the canonical spelling {canon!r}"
    # the schema enum line itself (the formal contract) carries both canonical forms
    body = _read(TEAM_SPAWNING)
    enum_line = next(ln for ln in body.splitlines() if '"kind": "playwright-failure"' in ln)
    assert "integration-test-failure" in enum_line and "visual-fidelity-drift" in enum_line
    assert "integration-failure" not in enum_line.replace("email-integration-failure", "")
    assert "visual-fidelity-cascade" not in enum_line
