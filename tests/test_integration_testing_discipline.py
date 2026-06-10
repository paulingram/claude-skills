"""v0.9.5 — Real-backend-by-default discipline structural tests.

The dominant greenfield failure mode: the pipeline builds a frontend + backend,
runs Playwright, says "tested" — but the Playwright run talked to a mocked /
fake backend, so the two layers were never exercised together. v0.9.5 closes
this with four enforcement layers:

  1. playwright-user-flows — a 4th top-level discipline + a "Real backend by
     default" section naming the forbidden mock patterns.
  2. coverage-mapping — every `both`-layer requirement gets a default
     front-to-back integration criterion at planning time.
  3. test-completeness-verifier — a backend-integration audit (Step 3b/3c)
     that greps for mock-backend patterns and emits integration_testing_review.
  4. review-gate hook — a new `integration_testing_review` evidence field
     (pass / n/a / fail), schema v3 -> v4, blocking `fail`.

These tests assert the contract across every doc so the discipline cannot
silently regress.
"""
from pathlib import Path

import pytest

PLAYWRIGHT_SKILL = ("skills", "playwright-user-flows", "SKILL.md")
COVERAGE_SKILL = ("skills", "coverage-mapping", "SKILL.md")
PIPELINE_SKILL = ("skills", "architect-team-pipeline", "SKILL.md")
TEAM_SPAWN_SKILL = ("skills", "team-spawning-and-review-gates", "SKILL.md")
DIAGNOSTIC_SKILL = ("skills", "diagnostic-research-team", "SKILL.md")
VERIFIER_AGENT = ("agents", "test-completeness-verifier.md")
FRONTEND_AGENT = ("agents", "frontend.md")
INTEGRATION_AGENT = ("agents", "integration.md")
# v0.9.9: the evidence schema + validation moved into the shared module that
# both review-gate-task.py and teammate-idle-check.py import.
HOOK = ("hooks", "review_evidence_schema.py")


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


# --- Hook enforcement -------------------------------------------------------

def test_hook_requires_integration_testing_review_field(plugin_root: Path) -> None:
    content = _read(plugin_root, HOOK)
    assert '"integration_testing_review"' in content, (
        "review-gate hook does not require the integration_testing_review field"
    )
    assert "VALID_INTEGRATION_TESTING_VALUES" in content, (
        "review-gate hook does not define the valid-values set for integration_testing_review"
    )


def test_hook_blocks_integration_testing_fail(plugin_root: Path) -> None:
    content = _read(plugin_root, HOOK)
    # The fail branch must mention real backend / mock so the message is actionable.
    assert 'itr == "fail"' in content, "hook has no integration_testing_review=='fail' branch"
    assert "real" in content.lower() and "backend" in content.lower(), (
        "hook fail-branch message does not reference the real-backend requirement"
    )


def test_hook_requires_note_for_integration_testing_na(plugin_root: Path) -> None:
    content = _read(plugin_root, HOOK)
    assert "integration_testing_review_note" in content, (
        "hook does not require integration_testing_review_note when value is n/a"
    )


# --- playwright-user-flows skill -------------------------------------------

def test_playwright_skill_has_fourth_discipline(plugin_root: Path) -> None:
    content = _read(plugin_root, PLAYWRIGHT_SKILL)
    assert "four disciplines" in content, (
        "playwright-user-flows still says 'three disciplines' — the real-backend "
        "discipline was not promoted to top-level"
    )
    assert "Test against the real backend, not fake data" in content, (
        "playwright-user-flows is missing the 4th discipline statement"
    )


def test_playwright_skill_has_real_backend_section(plugin_root: Path) -> None:
    content = _read(plugin_root, PLAYWRIGHT_SKILL)
    assert "Real backend by default" in content, (
        "playwright-user-flows is missing the 'Real backend by default' section"
    )


@pytest.mark.parametrize("forbidden_pattern", ["MSW", "json-server", "miragejs", "page.route"])
def test_playwright_skill_names_forbidden_mock_patterns(
    plugin_root: Path, forbidden_pattern: str
) -> None:
    """The skill must explicitly name the mock-backend patterns it forbids as
    happy-path substitutes."""
    content = _read(plugin_root, PLAYWRIGHT_SKILL)
    assert forbidden_pattern in content, (
        f"playwright-user-flows does not name forbidden mock pattern {forbidden_pattern!r}"
    )


def test_playwright_skill_has_tell_tale_signs(plugin_root: Path) -> None:
    content = _read(plugin_root, PLAYWRIGHT_SKILL)
    assert "Tell-tale signs the tests are running on fake data" in content, (
        "playwright-user-flows is missing the fake-data tell-tale-signs section"
    )


def test_playwright_skill_documents_phase_3_to_5_deferral(plugin_root: Path) -> None:
    content = _read(plugin_root, PLAYWRIGHT_SKILL)
    assert "DEFERRED TO PHASE 5" in content, (
        "playwright-user-flows does not document the Phase 3 -> Phase 5 deferral mechanism"
    )


# --- coverage-mapping skill -------------------------------------------------

def test_coverage_mapping_adds_default_integration_criterion(plugin_root: Path) -> None:
    content = _read(plugin_root, COVERAGE_SKILL)
    assert "front-to-back integration criterion" in content, (
        "coverage-mapping does not add a default front-to-back integration criterion "
        "for both-layer requirements"
    )
    assert "mock_testing_authorized" in content, (
        "coverage-mapping does not define the mock_testing_authorized opt-out field"
    )


# --- pipeline skill ---------------------------------------------------------

def test_pipeline_phase_1_gates_both_layer_integration_criterion(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL)
    assert "front-to-back integration test criterion" in content, (
        "pipeline Phase 1 loop does not gate on the both-layer integration criterion"
    )


def test_pipeline_phase_5_mandates_real_backend(plugin_root: Path) -> None:
    content = _read(plugin_root, PIPELINE_SKILL)
    assert "Front-to-back integration is the entire point of Phase 5" in content, (
        "pipeline Phase 5 does not mandate the real-backend run / settle the deferral debt"
    )


# --- diagnostic-research-team skill -----------------------------------------

def test_diagnostic_skill_includes_integration_testing_failure_origin(plugin_root: Path) -> None:
    content = _read(plugin_root, DIAGNOSTIC_SKILL)
    assert "integration-testing-failure" in content, (
        "diagnostic-research-team does not fire on the integration-testing-failure origin"
    )


# --- team-spawning skill ----------------------------------------------------

def test_team_spawn_documents_integration_testing_review_field(plugin_root: Path) -> None:
    content = _read(plugin_root, TEAM_SPAWN_SKILL)
    assert "integration_testing_review" in content, (
        "team-spawning skill does not document the integration_testing_review evidence field"
    )
    # v0.9.5 introduced integration_testing_review at schema v4; v0.9.13 bumped
    # the schema to v5 (the independent_review block); v2.0.0 bumped it to v7 (the
    # 5 VAO fields). The field must still be documented at v4-or-later. The C1
    # (review-remediation) update replaced the v6 example with the design-provided
    # v7 example, which deliberately OMITS a `schema_version` literal (it is not a
    # `REQUIRED_EVIDENCE_FIELDS` member), so v4+-ness is accepted via a
    # `schema_version` literal OR a textual `vN` schema reference (the body now
    # documents `Schema (v7 — …`). The exact current version (v7) is asserted by
    # test_independent_review::test_team_spawning_schema_is_v5_or_later.
    assert (
        any(f'schema_version": {n}' in content for n in (4, 5, 6, 7, 8, 9))
        or any(f"v{n}" in content for n in (4, 5, 6, 7, 8, 9))
    ), "team-spawning skill evidence schema not at v4 or later"


def test_team_spawn_lists_integration_testing_failure_origin(plugin_root: Path) -> None:
    content = _read(plugin_root, TEAM_SPAWN_SKILL)
    assert "integration-testing-failure" in content, (
        "team-spawning SR origin.kind enum does not include integration-testing-failure"
    )


# --- test-completeness-verifier agent ---------------------------------------

def test_verifier_has_backend_integration_audit(plugin_root: Path) -> None:
    content = _read(plugin_root, VERIFIER_AGENT)
    assert "Backend-integration audit" in content, (
        "test-completeness-verifier is missing the Step 3b backend-integration audit"
    )
    assert "backend_integration_audit" in content, (
        "test-completeness-verifier verdict JSON is missing backend_integration_audit"
    )
    assert "integration_testing_review" in content, (
        "test-completeness-verifier does not compute integration_testing_review"
    )


def test_verifier_documents_phase_5_debt(plugin_root: Path) -> None:
    content = _read(plugin_root, VERIFIER_AGENT)
    assert "phase_5_integration_debt" in content, (
        "test-completeness-verifier does not track the phase_5_integration_debt"
    )


# --- frontend + integration agents ------------------------------------------

def test_frontend_agent_forbids_mock_backed_playwright(plugin_root: Path) -> None:
    content = _read(plugin_root, FRONTEND_AGENT)
    assert "real running backend" in content, (
        "frontend agent does not mandate the real running backend for both-layer features"
    )
    assert "integration_testing_review" in content, (
        "frontend agent does not document setting integration_testing_review"
    )


def test_integration_agent_mandates_real_backend(plugin_root: Path) -> None:
    content = _read(plugin_root, INTEGRATION_AGENT)
    assert "Real backend, not fake data" in content, (
        "integration agent is missing the real-backend Phase 5 mandate section"
    )


# --- v0.9.32 — code-path execution witness for feature tests ----------------


def test_integration_agent_has_code_path_witness(plugin_root: Path) -> None:
    """v0.9.32 — integration agent must document the code-path execution witness for feature tests."""
    content = _read(plugin_root, INTEGRATION_AGENT)
    assert "code-path execution witness" in content.lower(), (
        "integration agent must declare the 'code-path execution witness' step"
    )
    # The witness reads the coverage map's implementing_commits to identify feature handlers
    assert "implementing_commits" in content or "implementing_handlers" in content, (
        "integration agent must derive feature handlers from the coverage map's `implementing_commits[]`"
    )


def test_integration_agent_names_four_fingerprint_kinds(plugin_root: Path) -> None:
    """The four fingerprint kinds must be named (parallel to qa-replayer's discipline)."""
    content = _read(plugin_root, INTEGRATION_AGENT)
    for kind in ("network_request", "api_access_log", "dom_state_change", "console_sentinel"):
        assert kind in content, (
            f"integration agent must name the '{kind}' fingerprint kind (parallel to qa-replayer's v0.9.31 witness)"
        )


def test_integration_agent_names_feature_test_verdict(plugin_root: Path) -> None:
    """The new verdict for feature tests that didn't exercise implementation must be named."""
    content = _read(plugin_root, INTEGRATION_AGENT)
    assert "feature-tests-did-not-exercise-implementation" in content, (
        "integration agent must name the 'feature-tests-did-not-exercise-implementation' verdict"
    )


def test_integration_agent_mandates_selector_witness(plugin_root: Path) -> None:
    """v0.9.32 — integration agent's Playwright authoring must require selector witness assertions."""
    content = _read(plugin_root, INTEGRATION_AGENT)
    assert "selector witness" in content.lower(), (
        "integration agent must require the v0.9.32 selector witness on every action-call selector"
    )
