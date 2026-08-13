"""v3.47.0 report-claims citation gate — R2 / R4 / R5 / R9.

The banking-app postmortem (2026-07-30) recorded four report-level failure
shapes: completion statuses relayed with no evidence, a "deployed and verified"
claim made off HTTP status codes, absence findings manufactured from narrow
greps, and an agent characterized as stalled purely because it had not spoken.
A fifth shape — naming a release gate in prose that was never recorded — is the
report-side half of the declared-gates registry.

This module pins the five sibling marker families `verify-no-end-of-run-deferral`
gains (`hooks/vao/deferral.py`), the extended citation-token list they share, the
new OPTIONAL `progress_reports[]` input, and the delivery-manifest engine's
matching evidence-citation errors (`scripts/delivery/delivery_manifest.py`).

Every severity ships a FAILING and a PASSING case; the pre-v3.47.0 severities
and the inputs that passed before this change must behave identically.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def vao_tools(plugin_root: Path) -> ModuleType:
    return load_module(plugin_root / "hooks" / "vao_tools.py", "vao_tools")


@pytest.fixture(scope="module")
def eng() -> ModuleType:
    return load_module(REPO_ROOT / "scripts" / "delivery" / "delivery_manifest.py",
                       "delivery_manifest_module")


@pytest.fixture(scope="module")
def claims_fixture(plugin_root: Path) -> dict:
    path = plugin_root / "tests" / "fixtures" / "vao" / "uncited-report-claims.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _severities(verdict: dict) -> set[str]:
    return {g["severity"] for g in verdict["gaps"]}


# ═════════════════════════════════════════════════════════════════════════════
# uncited-completion-claim
# ═════════════════════════════════════════════════════════════════════════════

def test_uncited_completion_claim_fires_on_enumerated_item(vao_tools):
    """An enumerated item asserting completion with nothing cited is the
    task-board-`completed`-relayed-to-the-user failure shape."""
    report = (
        "Fix list status:\n"
        "- Column config: completed\n"
        "- Statement export: delivered and verified\n"
        "- Balance rounding: done\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)
    assert v["valid"] is False


def test_uncited_completion_claim_passes_with_commit_citation(vao_tools):
    report = (
        "Fix list status:\n"
        "- Column config: completed — commit-sha:a1b2c3d\n"
        "- Statement export: delivered — commit-sha:e4f5g6h\n"
        "- Balance rounding: done — commit-sha:i7j8k9l\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_uncited_completion_claim_passes_with_verdict_path_citation(vao_tools):
    """The v3.47.0 token extension — a Layer-3 verdict path is a citation."""
    report = (
        "Fix list status:\n"
        "- Column config: completed "
        "(.architect-team/vao-verdicts/fix-1-check-can-fail.json)\n"
        "- Statement export: verified (verdict_path: "
        ".architect-team/vao-verdicts/fix-2-live-verification.json)\n"
        "- Balance rounding: done (evidence: reviews/fix-3.json)\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_uncited_completion_claim_citation_may_sit_on_a_continuation_line(vao_tools):
    """The citation window is the item plus its contiguous continuation lines."""
    report = (
        "Fix list status:\n"
        "- Column config: completed\n"
        "  evidence: reviews/fix-1.json\n"
        "- Statement export: completed\n"
        "  evidence: reviews/fix-2.json\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_uncited_completion_claim_ignores_narrative_prose(vao_tools):
    """False-positive control — the family fires on ENUMERATED item claims,
    never on the report's narrative framing."""
    report = (
        "This run completed the fix list and the work is done. Everything the "
        "user asked for is delivered. The suite is all green.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_uncited_completion_claim_is_negation_guarded(vao_tools):
    """`not fixed yet` is not a completion claim — the tuning that keeps the
    family off the reports that honestly say an item is unfinished."""
    report = (
        "Run summary:\n"
        "- Bug #1: not fixed yet\n"
        "- Bug #2: never completed, still open\n"
        "- Bug #3: no verified behavior to report\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


@pytest.mark.parametrize("item", [
    "- Item alpha: unresolved after two attempts",
    "- Item beta: the extraction-completeness gap remains",
    "- Item gamma: the teammate abandoned this thread",
    "- Item delta: still unverified against the dev URL",
    "- Item epsilon: incomplete, carried into the next phase",
])
def test_completion_claim_markers_do_not_match_inside_longer_words(vao_tools, item):
    """False-positive control — a bare substring scan reads `unresolved` as
    `resolved`, `abandoned` as `done` and `extraction-completeness` as
    `complete`. Every one of these lines says the opposite of a completion."""
    report = f"Run summary:\n{item}\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v), (
        f"{item!r} was read as a completion claim"
    )


# ═════════════════════════════════════════════════════════════════════════════
# uncited-deploy-claim
# ═════════════════════════════════════════════════════════════════════════════

def test_uncited_deploy_claim_fires_when_only_status_codes_cited(vao_tools):
    """R2 — status codes are not screens."""
    report = (
        "Revision 47 deployed and verified: the service returned HTTP 200 on "
        "/health and every endpoint responded 200.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" in _severities(v)


def test_uncited_deploy_claim_records_the_status_code_only_basis(vao_tools):
    report = "Revision 47 deployed and verified — status code 200 from the health check.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    gap = next(g for g in v["gaps"] if g["severity"] == "uncited-deploy-claim")
    assert gap.get("status_code_only") is True
    assert "status" in gap["evidence"].lower()


def test_uncited_deploy_claim_fires_with_no_citation_at_all(vao_tools):
    report = "Revision 47 deployed and verified.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" in _severities(v)


def test_uncited_deploy_claim_passes_with_page_load_and_screenshot(vao_tools):
    report = (
        "Revision 47 deployed and verified: the accounts page loaded at the dev "
        "URL and the statement table rendered 24 rows "
        "(screenshot .architect-team/evidence/accounts-after-deploy.png).\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" not in _severities(v)


def test_uncited_deploy_claim_passes_with_semantic_assertion(vao_tools):
    report = (
        "Revision 47 deployed and verified — Playwright flow accounts.spec.ts "
        "asserted getByText('Statement ready') on the deployed page.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" not in _severities(v)


def test_deploy_without_a_verification_claim_does_not_fire(vao_tools):
    """A plain deploy statement makes no verification claim — nothing to cite."""
    report = "Revision 47 deployed to the dev environment at 14:02 UTC.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" not in _severities(v)


# ═════════════════════════════════════════════════════════════════════════════
# absence-claim-uncited
# ═════════════════════════════════════════════════════════════════════════════

def test_absence_claim_uncited_fires_when_only_a_grep_is_cited(vao_tools):
    """R4 — grep proves presence, never absence."""
    report = (
        "Coverage finding: no test exists for the statement-export path "
        "(grep -r 'statement_export' tests/ returned nothing).\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "absence-claim-uncited" in _severities(v)


def test_absence_claim_uncited_records_the_grep_basis(vao_tools):
    report = "The reconciliation hook is missing — rg 'reconcile' src/ found no hits.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    gap = next(g for g in v["gaps"] if g["severity"] == "absence-claim-uncited")
    assert gap.get("grep_only") is True


def test_absence_claim_passes_when_citing_the_collected_test_list(vao_tools):
    report = (
        "Coverage finding: no test exists for the statement-export path — "
        "pytest --collect-only over tests/ collected 5979 items and the "
        "enumeration carries no statement-export node "
        "(evidence: .architect-team/vao-verdicts/collect-only.txt).\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "absence-claim-uncited" not in _severities(v)


def test_absence_claim_without_an_absence_marker_does_not_fire(vao_tools):
    report = "The statement-export path is covered by tests/test_export.py.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "absence-claim-uncited" not in _severities(v)


# ═════════════════════════════════════════════════════════════════════════════
# stalled-agent-claim-uncited
# ═════════════════════════════════════════════════════════════════════════════

def test_stalled_agent_claim_uncited_fires_without_an_idle_or_handoff_citation(vao_tools):
    """R5 — silence is not a finding."""
    report = (
        "Team status: the frontend teammate stalled after the second dispatch "
        "and left the build broken.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" in _severities(v)


def test_stalled_agent_claim_passes_with_an_idle_event_citation(vao_tools):
    report = (
        "Team status: the frontend teammate stalled — TeammateIdle fired at "
        "03:14Z with no TaskUpdate since 02:51Z "
        "(.architect-team/teammates/frontend.json).\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" not in _severities(v)


def test_stalled_agent_claim_passes_with_a_handoff_citation(vao_tools):
    report = (
        "Team status: the backend teammate went idle; its last handoff record is "
        "handoffs/backend-2026-07-30T0314Z.json and nothing followed it.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" not in _severities(v)


@pytest.mark.parametrize("report", [
    "The deploy stalled at 40% and was retried.\n",
    "Progress on the migration stalled until the schema landed.\n",
    "The build went idle waiting on the registry.\n",
])
def test_stalled_family_needs_an_agent_in_the_window(vao_tools, report):
    """False-positive control — this family characterizes an AGENT's state.
    A stalled deploy, build, or migration is not a claim about an agent."""
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" not in _severities(v)


def test_ordinary_teammate_reporting_does_not_fire_stalled(vao_tools):
    report = "Team status: both teammates reported green and signalled readiness.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" not in _severities(v)


# ═════════════════════════════════════════════════════════════════════════════
# undeclared-gate-language
# ═════════════════════════════════════════════════════════════════════════════

_GATE_REPORT = (
    "Ship decision: the full Playwright suite against the live URL gates the "
    "release, and it is green.\n"
)


def _write_registry(tmp_path: Path, entries: list) -> Path:
    path = tmp_path / "declared-gates.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_undeclared_gate_language_fires_when_the_registry_has_no_entry(vao_tools, tmp_path):
    registry = _write_registry(tmp_path, [])
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": _GATE_REPORT}, declared_gates_path=registry,
    )
    assert "undeclared-gate-language" in _severities(v)


def test_undeclared_gate_language_fires_when_the_registry_names_a_different_gate(
    vao_tools, tmp_path,
):
    registry = _write_registry(tmp_path, [{
        "gate_id": "typecheck-clean",
        "declaration_text": "The commit gates on a clean typecheck.",
        "check_command_or_artifact": "tsc --noEmit",
        "declared_at": "2026-07-30T00:00:00Z",
    }])
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": _GATE_REPORT}, declared_gates_path=registry,
    )
    assert "undeclared-gate-language" in _severities(v)


def test_undeclared_gate_language_passes_with_a_matching_registry_entry(vao_tools, tmp_path):
    registry = _write_registry(tmp_path, [{
        "gate_id": "playwright-suite-live-url",
        "declaration_text": (
            "The release gates on the full Playwright suite run against the live URL."
        ),
        "check_command_or_artifact": "npx playwright test --reporter=line",
        "declared_at": "2026-07-30T00:00:00Z",
    }])
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": _GATE_REPORT}, declared_gates_path=registry,
    )
    assert "undeclared-gate-language" not in _severities(v)


def test_undeclared_gate_language_passes_when_the_gate_id_is_named(vao_tools, tmp_path):
    registry = _write_registry(tmp_path, [{
        "gate_id": "suite-zero-new-failures",
        "declaration_text": "Zero new failures versus the recorded baseline.",
        "check_command_or_artifact": "python -m pytest -q",
        "declared_at": "2026-07-30T00:00:00Z",
    }])
    report = "The suite-zero-new-failures release gate is satisfied.\n"
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": report}, declared_gates_path=registry,
    )
    assert "undeclared-gate-language" not in _severities(v)


def test_absent_registry_is_fail_open_for_the_gate_severity_only(vao_tools, tmp_path):
    """A run that never wrote a registry gets no gate findings — but the other
    four families are unaffected by the registry's absence."""
    missing = tmp_path / "nope" / "declared-gates.json"
    artifact = {
        "final_report": _GATE_REPORT + "- Column config: completed\n",
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact, declared_gates_path=missing)
    assert "undeclared-gate-language" not in _severities(v)
    assert "uncited-completion-claim" in _severities(v)


def test_no_registry_argument_at_all_is_fail_open(vao_tools):
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": _GATE_REPORT})
    assert "undeclared-gate-language" not in _severities(v)


def test_malformed_registry_is_fail_open(vao_tools, tmp_path):
    path = tmp_path / "declared-gates.json"
    path.write_text("{not json", encoding="utf-8")
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": _GATE_REPORT}, declared_gates_path=path,
    )
    assert "undeclared-gate-language" not in _severities(v)


def test_gate_language_naming_no_condition_does_not_fire(vao_tools, tmp_path):
    """False-positive control — the severity fires on gate language NAMING a
    condition. A window whose condition vocabulary is too thin to reach the
    match threshold against any entry cannot be judged unmatched."""
    registry = _write_registry(tmp_path, [])
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": "The release gate is green.\n"}, declared_gates_path=registry,
    )
    assert "undeclared-gate-language" not in _severities(v)


def test_inline_declared_gates_on_the_artifact_are_honored(vao_tools):
    """In-memory callers may pass the registry inline instead of by path."""
    artifact = {
        "final_report": _GATE_REPORT,
        "declared_gates": [],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    assert "undeclared-gate-language" in _severities(v)


# ═════════════════════════════════════════════════════════════════════════════
# progress_reports[] — the new OPTIONAL input
# ═════════════════════════════════════════════════════════════════════════════

def test_progress_reports_are_scanned_for_claims(vao_tools):
    artifact = {
        "final_report": "Run complete. Every item cited below.\n",
        "progress_reports": [
            "Mid-run update:\n- Column config: completed\n- Export: done\n",
        ],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    assert "uncited-completion-claim" in _severities(v)


def test_progress_report_findings_name_their_source(vao_tools):
    artifact = {
        "progress_reports": ["Update:\n- Column config: completed\n"],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    gap = next(g for g in v["gaps"] if g["severity"] == "uncited-completion-claim")
    assert gap["source"] == "progress_reports[0]"


def test_progress_reports_accept_dict_entries(vao_tools):
    artifact = {
        "progress_reports": [{"phase": "3", "text": "Update:\n- Export: delivered\n"}],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    assert "uncited-completion-claim" in _severities(v)


def test_absent_progress_reports_is_backwards_compatible(vao_tools):
    """Pre-v3.47.0 artifacts carry no progress_reports[] — unchanged behavior."""
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": "Run complete.\n"})
    assert v["valid"] is True
    assert v["gaps"] == []


def test_progress_reports_do_not_feed_the_pre_v3470_severities(vao_tools):
    """The three original severities scan `final_report` only — byte-identical
    behavior for every input that existed before this change."""
    artifact = {
        "progress_reports": [
            "⏳ Deferred — 7 bugs, 4 work-items. Want me to continue? Your call.\n"
        ],
    }
    v = vao_tools.verify_no_end_of_run_deferral(artifact)
    severities = _severities(v)
    assert "deferred-work-catalog" not in severities
    assert "followup-decision-question" not in severities
    assert "wrap-up-with-known-bugs" not in severities


# ═════════════════════════════════════════════════════════════════════════════
# the shared citation-token list
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("token", [
    ".architect-team/vao-verdicts/",
    "verdict_path:",
    "reviews/",
    "evidence:",
])
def test_citation_tokens_extended_with_verdict_and_evidence_paths(vao_tools, token):
    assert token in vao_tools._ITEM_DISPOSITION_CITATIONS


@pytest.mark.parametrize("token", [
    "commit-sha:", "SR-", "confirmed_stub", "implementing_commits",
    "playwright_test_runs", "per_persona_findings", "persona_id:", "tested green",
])
def test_citation_tokens_preserve_every_earlier_generation(vao_tools, token):
    assert token in vao_tools._ITEM_DISPOSITION_CITATIONS


def test_new_marker_family_constants_are_exported(vao_tools):
    for name in (
        "_COMPLETION_CLAIM_MARKERS",
        "_DEPLOY_VERIFIED_MARKERS",
        "_ABSENCE_CLAIM_MARKERS",
        "_STALLED_AGENT_MARKERS",
        "_GATE_LANGUAGE_MARKERS",
        "_POST_DEPLOY_VERIFICATION_CITATIONS",
        "_STATUS_CODE_ONLY_CITATIONS",
        "_ENUMERATION_EVIDENCE_CITATIONS",
        "_AGENT_STATE_CITATIONS",
    ):
        assert hasattr(vao_tools, name), f"{name} not re-exported by the facade"
        assert len(getattr(vao_tools, name)) >= 3, f"{name} is suspiciously thin"


# ═════════════════════════════════════════════════════════════════════════════
# use vs mention — a report that DOCUMENTS the rule must not self-flag
# ═════════════════════════════════════════════════════════════════════════════
#
# The document that documents the rule has to quote the phrases the rule
# forbids. This change's own Phase 8 report and CHANGELOG entry do exactly
# that. Two rungs decide mention: (a) the window NAMES one of this module's
# severity ids — documentation ABOUT the machinery; (b) the marker occurrence
# is quote-enclosed AND the window carries an attribution cue. Rung (b) alone
# can never excuse an ENUMERATED item, or the gate is evadable by typing two
# quotation marks.

_CLAIM_FAMILIES = (
    "uncited-completion-claim",
    "uncited-deploy-claim",
    "absence-claim-uncited",
    "stalled-agent-claim-uncited",
    "undeclared-gate-language",
)


def test_documentation_narrative_does_not_self_flag(vao_tools, claims_fixture):
    """The repro: this change's own release prose, which must quote every
    forbidden phrase to describe what the severities detect."""
    artifact = claims_fixture["_documentation_narrative_artifact"]
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": artifact["final_report"]})
    fired = _severities(v) & set(_CLAIM_FAMILIES)
    assert fired == set(), f"documentation prose self-flagged: {sorted(fired)}"


def test_documentation_narrative_still_fires_the_pre_existing_wrap_up(vao_tools, claims_fixture):
    """Scope pin — the mention rung covers the FIVE v3.47.0 families only. The
    v2.10.0 severities are untouched, so wrap-up-with-known-bugs still fires on
    this text exactly as it did before this change."""
    artifact = claims_fixture["_documentation_narrative_artifact"]
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": artifact["final_report"]})
    assert "wrap-up-with-known-bugs" in _severities(v)


def test_mention_rung_a_window_naming_a_severity_id(vao_tools):
    """A severity-reference bullet: quotes the term, carries a cue, names its
    own family. Before hei-adversary-g3's B-1 this passed on the severity id
    ALONE, which was the universal bypass — the quoting is now load-bearing."""
    report = (
        "Severity reference:\n"
        "- uncited-completion-claim: fires on an enumerated item marked \"completed\" "
        "with no citation token.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_mention_rung_b_quoted_marker_with_attribution_cue(vao_tools):
    """Rung (b) — quoted marker in prose, with an attribution cue."""
    report = (
        "The postmortem records a \"deployed and verified\" claim made off status "
        "codes, which is the shape this severity now detects.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" not in _severities(v)


def test_mention_rung_b_quoted_marker_without_a_cue_still_fires(vao_tools):
    """Failing fixture for rung (b) — quotation marks alone are not mention."""
    report = "Revision 47 was \"deployed and verified\" this afternoon.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" in _severities(v)


def test_quoted_marker_in_an_enumerated_item_still_fires(vao_tools, claims_fixture):
    """THE GAMING ATTEMPT — a real per-item completion claim dressed in
    quotation marks and an attribution cue. The enumerated-item hardening
    exists for exactly this: rung (b) alone must never excuse an item."""
    artifact = claims_fixture["_mention_gaming_attempt"]
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": artifact["final_report"]})
    assert "uncited-completion-claim" in _severities(v), (
        "quoting a claim bought it past the gate"
    )


def test_enumerated_item_is_mention_only_when_quoted_and_naming_its_family(vao_tools):
    """An enumerated item MAY be mention — but only when it QUOTES the phrase,
    carries an attribution cue, AND names its own family. This test previously
    pinned a weaker rule (severity id alone) and hei-adversary-g3's B-1 proved
    that rule was a universal bypass; a test can institutionalize a bug, and
    this one did."""
    report = (
        "Severity reference:\n"
        "- absence-claim-uncited: fires on absence markers such as "
        "\"no test exists\" whose only cited basis is a grep.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "absence-claim-uncited" not in _severities(v)


# ── hei-adversary-g3 breaks B-1 … B-11 ──────────────────────────────────────

def test_bare_severity_tag_does_not_exempt_any_claim(vao_tools, claims_fixture):
    """B-1 (high) — the adversary's H6-full-evasion: every claim uncited, every
    bullet tagged 'Not an <severity-id>'. Against the first mention guard this
    returned valid=true with gaps=[]."""
    artifact = claims_fixture["_severity_tag_evasion"]
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": artifact["final_report"], "declared_gates": []}
    )
    fired = _severities(v)
    for expected in artifact["expected_claim_family_severities"]:
        assert expected in fired, f"{expected} was bought off by a severity-id tag"


def test_severity_id_exemption_is_per_family(vao_tools):
    """B-1 — naming ONE family's id must not suppress the other four."""
    report = (
        "Status:\n"
        "- Column config: completed. See absence-claim-uncited for the absence rule.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)


def test_absence_claim_with_a_commit_disposition_does_not_fire(vao_tools):
    """B-4 (medium) — 'I found X missing and fixed it, here is the commit' is a
    DISPOSITIONED item, the most common sentence in a doc-currency report."""
    report = (
        "The CHANGELOG entry is missing the suite-total line; added it "
        "(commit-sha:aaa1111).\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "absence-claim-uncited" not in _severities(v)


@pytest.mark.parametrize("report", [
    "The integration suite stalled on a locked sqlite file.\n",
    "The backend container went dark after the OOM kill.\n",
    "The CI queue stalled for 20 minutes, so the dev environment redeploy was late.\n",
])
def test_infrastructure_prose_does_not_fire_stalled(vao_tools, report):
    """B-5 (medium) — 'integration' / 'backend' / 'dev' are ordinary infra
    nouns; they must not make infrastructure prose read as an agent claim."""
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" not in _severities(v)


@pytest.mark.parametrize("report,severity", [
    ("The deploy will be verified once the smoke run lands.\n", "uncited-deploy-claim"),
    ("Statement export must be deployed and verified before merge.\n", "uncited-deploy-claim"),
    ("- Column config: should be completed in the next pass\n", "uncited-completion-claim"),
])
def test_future_tense_plans_are_not_claims(vao_tools, report, severity):
    """B-6 (medium) — a next-actions section states obligations, not claims."""
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert severity not in _severities(v)


# The five B-16 regression inputs below are hei-adversary-g3's artifacts
# (R1 / R1b / R2 / R3 / R4), inlined VERBATIM from what used to be read out of
# .architect-team/adversarial/hei-group3/artifacts/<name>.json. That directory
# is gitignored runtime state, so loading it made these five tests the only
# ones in the suite that FAILED on a pristine checkout (close-the-open-items
# F3). Each artifact was a one-key {"final_report": ...} dict; the report
# string IS the artifact, and inlining it also makes the shape under test
# readable where the assertion is.


def test_a_citation_before_its_claim_in_the_same_item_counts(vao_tools):
    """B-17/W2 — forward-only citation scoping was too strict. 'In
    commit-sha:abc I completed the column config' has no earlier claim to have
    borrowed from; the citation is attached to the only claim there."""
    report = "- In commit-sha:a1b2c3d I completed the column config.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


@pytest.mark.parametrize("terminator", [".", ""])
def test_a_full_stop_does_not_decide_a_verification_outcome(vao_tools, terminator):
    """B-17/W3 — the sharpest of the three: a cited claim fired or passed
    depending on whether its line ended in a period. Nobody reasons about
    punctuation as load-bearing, and a gate that turns on it is the B-14 shape
    all over again. BOTH forms must read as cited."""
    report = f"- Column config: completed{terminator}\n  evidence: reviews/fix-1.json\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_a_dotted_version_number_is_not_a_claim_boundary(vao_tools):
    """B-17/W4 — `v3.47.0. commit-sha:abc`: the version's own `0. ` cut the
    citation off. This repo's reports are full of dotted versions."""
    report = "- Column config: completed in v3.47.0. commit-sha:a1b2c3d\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_a_multi_marker_claim_is_one_claim_not_two(vao_tools):
    """B-17 control — 'delivered and verified' matches two markers of the same
    family. Treating the second as a separate claim would truncate the first
    claim's citation scope."""
    report = "- Statement export: delivered and verified — commit-sha:e4f5g6h\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


def test_a_citation_is_not_borrowed_by_an_earlier_claim(vao_tools):
    """B-17 control, the mirror of R1 — the citation sits on the SECOND claim,
    so the first must still fire. Widening the scope backward must not let a
    claim reach forward past its sibling."""
    report = "- Column config: done. Statement export: completed (commit-sha:a1b2c3d).\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)


def test_a_citation_excuses_its_own_claim_not_a_sibling(vao_tools):
    """B-16 (medium) — claim detection went per-occurrence but the citation test
    stayed window-scoped, so a citation attached to claim 1 silently excused
    claim 2. Unlike truncation, the second claim was never reported on ANY
    re-run. hei-adversary-g3's R1 (R1-cited-claim-covers-uncited-sibling)."""
    report = (
        "Fix list:\n"
        "- Column config: completed (commit-sha:a1b2c3d). Statement export: also done.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)


def test_b16_control_the_sibling_alone_still_fires(vao_tools):
    """B-16 control (R1b-control-second-item-alone) — the uncited sibling with
    no cited neighbour to hide behind must fire on its own."""
    report = (
        "Fix list:\n"
        "- Statement export: also done.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)


def test_a_continuation_line_citation_does_not_cover_a_later_claim(vao_tools):
    """B-16 in the continuation-line shape (R2-continuation-line-uncited-sibling)
    — the `evidence:` line cites the claim above it, not the one below it."""
    report = (
        "Fix list:\n"
        "- Column config: completed\n"
        "  evidence: reviews/fix-1.json\n"
        "  Statement export: delivered, and the balance rounding is resolved.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)


def test_a_grep_only_absence_is_not_excused_by_its_enumerated_sibling(vao_tools):
    """B-16's sharpest instance (R3-absence-mixed-basis), and the Lead's first
    pin: two absence claims in one window, the first backed by a real
    --collect-only and the second a bare grep. The grep-only claim is the
    postmortem's R4 shape and `grep_only` exists to mark it — being silently
    excused by a sibling's enumeration is the failure this whole change exists
    to prevent."""
    report = (
        "Coverage review:\n"
        "- Reconcile: no test exists (pytest --collect-only output above, "
        "14 collected). The settlement handler was never built — grepped for "
        "it, nothing came back.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "absence-claim-uncited" in _severities(v)


def test_an_uncited_deploy_is_not_excused_by_a_cited_sibling(vao_tools):
    """B-16 for the deploy family (R4-deploy-mixed-citation) — one traced
    deploy silenced the rest."""
    report = (
        "Revision 00008 deployed and verified (playwright trace.zip, "
        "screenshot attached). Revision 00009 is also deployed and verified.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" in _severities(v)


def test_a_mention_excuses_itself_not_the_window(vao_tools):
    """B-15 (high) — the CT6 release-notes bullet for this very feature, which
    hei-adversary-g3 built naturally rather than constructed: it names the
    severity to identify itself, quotes the marker to document what fires,
    needs 'severity' as the cue, and appends the status a Phase-8 report
    appends. `completed` is quoted and IS a genuine mention; `Shipped this run`
    is neither quoted nor cited. Judging mention per-window let the first
    excuse the second — a mention must excuse only its own occurrence."""
    report = (
        "- uncited-completion-claim: this severity fires on any enumerated item "
        "whose status is \"completed\" with no citation. Shipped this run.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v), (
        "the quoted mention shadowed the unquoted claim in the same window"
    )


def test_the_quoted_occurrence_itself_still_reads_as_mention(vao_tools):
    """B-15 control — fixing the shadowing must not make quoting stop working.
    Same bullet with the trailing claim removed stays clean."""
    report = (
        "- uncited-completion-claim: this severity fires on any enumerated item "
        "whose status is \"completed\" with no citation.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" not in _severities(v)


@pytest.mark.parametrize("wrapper", ["`", '"', "'"])
def test_a_wrapped_bullet_is_still_a_bullet(vao_tools, wrapper):
    """B-13 (high) — wrapping a status bullet in backticks or quotes demoted it
    out of enumerated status, and that alone reopened the full evasion: the
    completion family is enumerated-only, so the line left its scope with no
    mention machinery involved at all."""
    report = f"Fix list:\n{wrapper}- Column config: completed{wrapper}\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v), (
        f"a {wrapper!r}-wrapped bullet escaped the enumerated scope"
    )


def test_wrapped_bullets_do_not_join_the_preceding_prose_window(vao_tools):
    """B-13's second consequence — demoted lines joined the prose window above
    them, so ONE cue word in a heading carried the whole block through."""
    report = (
        "Status (the rule below fires on uncited items):\n"
        "`- Column config: completed`\n"
        "`- Statement export: delivered`\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)


def test_ordinary_business_nouns_are_not_attribution_cues(vao_tools):
    """B-12 (high) — 'records', 'documents', 'severity' and 'marker' were cues
    AND ordinary domain vocabulary, so a sentence about a records module
    supplied two for free."""
    report = (
        "The patient records module and the documents tab were both "
        "\"deployed and verified\" this morning (http 200).\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-deploy-claim" in _severities(v)


def test_modality_is_clause_scoped_not_line_scoped(vao_tools):
    """B-6 control — the modal guard reads the CLAUSE, so a modal in an earlier
    clause must not suppress a genuine claim in a later one. Without clause
    scoping this whole family becomes evadable by writing 'must' anywhere."""
    report = "- Item 4: the migration must run first; now completed\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "uncited-completion-claim" in _severities(v)


def test_naming_an_unrelated_gate_id_does_not_cover_a_new_gate(vao_tools, tmp_path):
    """B-7 (medium) — the gate_id short-circuit answered 'is this id mentioned
    here', not 'is THIS gate that gate'."""
    registry = _write_registry(tmp_path, [{
        "gate_id": "suite-zero-new-failures",
        "declaration_text": "Zero new failures versus the recorded baseline.",
        "check_command_or_artifact": "python -m pytest -q",
        "declared_at": "2026-07-30T00:00:00Z",
    }])
    report = (
        "The end-to-end payment reconciliation run against the live tenant gates "
        "the release. Unrelated: see suite-zero-new-failures for the suite baseline.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral(
        {"final_report": report}, declared_gates_path=registry,
    )
    assert "undeclared-gate-language" in _severities(v)


def test_unreadable_registry_path_falls_back_to_the_inline_registry(vao_tools, tmp_path):
    """B-9 (low) — a typo'd path must not silently disable the severity when
    the caller also supplied the registry inline."""
    artifact = {"final_report": _GATE_REPORT, "declared_gates": []}
    v = vao_tools.verify_no_end_of_run_deferral(
        artifact, declared_gates_path=tmp_path / "nope" / "missing.json",
    )
    assert "undeclared-gate-language" in _severities(v)


def test_progress_reports_as_a_bare_string_is_scanned(vao_tools):
    """B-10 (low) — a wrong-shape value on a brand-new optional field must not
    be silently dropped."""
    v = vao_tools.verify_no_end_of_run_deferral({
        "progress_reports": "Update:\n- Column config: completed\n",
    })
    assert "uncited-completion-claim" in _severities(v)


def test_gaps_are_capped_per_family(vao_tools):
    """B-11 (low) — a runaway report must not write a verdict two orders of
    magnitude larger than itself."""
    report = "".join(f"- Item {i}: completed\n" for i in range(500))
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    completion = [g for g in v["gaps"] if g["severity"] == "uncited-completion-claim"]
    assert 0 < len(completion) <= vao_tools._MAX_GAPS_PER_FAMILY + 1
    assert any(g.get("truncated") for g in completion), "truncation must be visible"


def test_stalled_family_immunity_in_the_repro_was_accidental(vao_tools):
    """The repro's stalled sentence escaped only because it contained the
    literal `idle-event`, an _AGENT_STATE_CITATIONS token. Reworded as a
    genuine claim with nothing cited, the family fires — its silence there was
    an accident of vocabulary, never immunity."""
    report = "Team status: the frontend agent stalled with nothing cited at all.\n"
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" in _severities(v)


def test_stalled_documentation_sentence_is_a_mention(vao_tools):
    """The same sentence as documentation — quoting the term, carrying a cue,
    naming its own severity — is mention. Note the quoting is load-bearing
    after B-1: drop the quotation marks and this fires."""
    report = (
        "Severity reference:\n"
        "- stalled-agent-claim-uncited: fires when the report says an agent "
        "\"stalled\" with nothing cited at all.\n"
    )
    v = vao_tools.verify_no_end_of_run_deferral({"final_report": report})
    assert "stalled-agent-claim-uncited" not in _severities(v)


def test_mention_context_constants_are_exported(vao_tools):
    for name in ("_OWN_SEVERITY_IDS", "_MENTION_ATTRIBUTION_CUES", "_is_mention_context"):
        assert hasattr(vao_tools, name), f"{name} not re-exported by the facade"
    assert set(vao_tools._OWN_SEVERITY_IDS) == set(_CLAIM_FAMILIES)


# ═════════════════════════════════════════════════════════════════════════════
# Regression — the pre-v3.47.0 contract is untouched
# ═════════════════════════════════════════════════════════════════════════════

def test_corrected_deferral_fixture_stays_completely_clean(vao_tools, plugin_root):
    """The v2.10.0 corrected fixture is the canonical WELL-FORMED report. Five
    new severities must not find anything in it."""
    path = plugin_root / "tests" / "fixtures" / "vao" / "in-scope-deferral-cluster-list.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    v = vao_tools.verify_no_end_of_run_deferral(data["_corrected_verification_artifact"])
    assert v["valid"] is True, f"new severities fired on the corrected fixture: {v['gaps']}"
    assert v["gaps"] == []


def test_original_deferral_fixture_still_fires_its_three_severities(vao_tools, plugin_root):
    path = plugin_root / "tests" / "fixtures" / "vao" / "in-scope-deferral-cluster-list.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    v = vao_tools.verify_no_end_of_run_deferral(data["verification_artifact"])
    severities = _severities(v)
    assert "deferred-work-catalog" in severities
    assert "followup-decision-question" in severities
    assert "wrap-up-with-known-bugs" in severities


def test_empty_artifact_still_trivially_passes(vao_tools):
    assert vao_tools.verify_no_end_of_run_deferral({})["valid"] is True
    assert vao_tools.verify_no_end_of_run_deferral(None)["valid"] is True


def test_verdict_is_deterministic_modulo_timestamp(vao_tools, claims_fixture):
    artifact = claims_fixture["verification_artifact"]
    a = vao_tools.verify_no_end_of_run_deferral(artifact)
    b = vao_tools.verify_no_end_of_run_deferral(artifact)
    a.pop("verdict_at", None)
    b.pop("verdict_at", None)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ═════════════════════════════════════════════════════════════════════════════
# The canonical fixture + the CLI
# ═════════════════════════════════════════════════════════════════════════════

def test_fixture_has_the_house_meta_block(claims_fixture):
    assert "_meta" in claims_fixture
    assert claims_fixture["_meta"]["tool_targeted"] == "verify-no-end-of-run-deferral"


def test_fixture_bad_artifact_fires_every_new_severity(vao_tools, claims_fixture):
    v = vao_tools.verify_no_end_of_run_deferral(
        claims_fixture["verification_artifact"],
        declared_gates_path=None,
    )
    severities = _severities(v)
    for expected in (
        "uncited-completion-claim",
        "uncited-deploy-claim",
        "absence-claim-uncited",
        "stalled-agent-claim-uncited",
        "undeclared-gate-language",
    ):
        assert expected in severities, f"{expected} did not fire on the fixture"


def test_fixture_corrected_artifact_passes(vao_tools, claims_fixture):
    v = vao_tools.verify_no_end_of_run_deferral(
        claims_fixture["_corrected_verification_artifact"],
    )
    assert v["valid"] is True, f"corrected fixture produced gaps: {v['gaps']}"


def _run_cli(plugin_root: Path, artifact: dict, out: Path, registry: Path | None = None,
             tmp_path: Path | None = None) -> subprocess.CompletedProcess:
    art_path = (tmp_path or out.parent) / "artifact.json"
    art_path.write_text(json.dumps(artifact), encoding="utf-8")
    cmd = [
        sys.executable, str(plugin_root / "hooks" / "vao_tools.py"),
        "verify-no-end-of-run-deferral",
        "--artifact", str(art_path),
        "--out", str(out),
    ]
    if registry is not None:
        cmd += ["--declared-gates", str(registry)]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_cli_accepts_the_declared_gates_flag_and_exits_nonzero(
    plugin_root, claims_fixture, tmp_path,
):
    registry = _write_registry(tmp_path, [])
    out = tmp_path / "verdict.json"
    result = _run_cli(plugin_root, claims_fixture["verification_artifact"], out,
                      registry=registry, tmp_path=tmp_path)
    assert "error:" not in (result.stderr or ""), result.stderr
    assert result.returncode == 2
    verdict = json.loads(out.read_text(encoding="utf-8"))
    assert "undeclared-gate-language" in {g["severity"] for g in verdict["gaps"]}


def test_cli_exits_zero_on_the_corrected_fixture(plugin_root, claims_fixture, tmp_path):
    out = tmp_path / "verdict.json"
    result = _run_cli(plugin_root, claims_fixture["_corrected_verification_artifact"], out,
                      tmp_path=tmp_path)
    assert result.returncode == 0, out.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# delivery-manifest — the same citation bar, as blocking errors
# ═════════════════════════════════════════════════════════════════════════════

def _manifest() -> dict:
    """A minimal VALID manifest making no verified/completion claim — the
    regression baseline the citation errors must never touch."""
    return {
        "title": "Statement export",
        "delivery_type": "feature",
        "problem_statement": (
            "Support staff could not hand a customer their statements. They can "
            "now download them from the account page in one click."
        ),
        "validation_steps": [
            {"step": "Open any customer account page.",
             "expected": "An Export button appears next to the account header."},
        ],
        "elements": [
            {"location": "app/routes/export.ts", "name": "Export endpoint",
             "functionality": "Streams the customer's statements as a ZIP."},
        ],
    }


def test_manifest_without_claims_stays_valid(eng):
    """Regression — the pre-v3.47.0 valid manifest is still valid."""
    assert eng.errors_only(eng.validate_manifest(_manifest())) == []


def test_manifest_uncited_verified_claim_blocks(eng):
    data = _manifest()
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
    })
    findings = eng.errors_only(eng.validate_manifest(data))
    kinds = {f["kind"] for f in findings}
    assert "uncited-verified-claim" in kinds


def test_manifest_uncited_verified_claim_names_the_step(eng):
    data = _manifest()
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
    })
    finding = next(f for f in eng.validate_manifest(data)
                   if f["kind"] == "uncited-verified-claim")
    assert finding["severity"] == "error"
    assert "statements tab" in finding["detail"]


def test_manifest_verified_claim_passes_with_a_step_level_evidence_source(eng):
    data = _manifest()
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
        "evidence": ".architect-team/vao-verdicts/statements-live-verification.json",
    })
    assert eng.errors_only(eng.validate_manifest(data)) == []


def test_manifest_evidence_is_scoped_per_step(eng):
    """B-3 (high) — the spec says a step fires when the manifest carries no
    evidence source FOR IT. Whole-manifest scoping let evidence on step 1
    satisfy step 2, and let an unrelated field satisfy every step."""
    data = _manifest()
    data["validation_steps"][0]["evidence"] = "reviews/step-one.json"
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
    })
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "uncited-verified-claim" in kinds, "a sibling step's evidence covered this claim"


@pytest.mark.parametrize("junk", ["N/A", "n/a", "trust me, I checked", "none", "-"])
def test_manifest_evidence_value_must_look_like_a_citation(eng, junk):
    """B-2 (high) — the named failure mode of this task shape, realized
    literally: a citation bar satisfied by junk."""
    data = _manifest()
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
        "evidence": junk,
    })
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "uncited-verified-claim" in kinds, f"{junk!r} cleared the citation bar"


def test_manifest_ordinary_english_does_not_satisfy_the_bar(eng):
    """B-3 — EVIDENCE_CITATION_MARKERS were unanchored substrings, so the word
    'collected' in ordinary prose satisfied the whole manifest."""
    data = _manifest()
    data["problem_statement"] = (
        "The signup form collected the wrong postcode for two months."
    )
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
    })
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "uncited-verified-claim" in kinds


def test_manifest_verified_claim_passes_with_a_real_step_level_citation(eng):
    data = _manifest()
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
        "evidence": ".architect-team/vao-verdicts/statements-live-verification.json",
    })
    assert eng.errors_only(eng.validate_manifest(data)) == []


def test_manifest_uncited_element_completion_claim_blocks(eng):
    data = _manifest()
    data["elements"].append({
        "location": "app/components/StatementList.tsx",
        "name": "Statement list",
        "functionality": "Renders the statement rows — implementation complete and verified.",
    })
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "uncited-element-claim" in kinds


def test_manifest_element_status_field_is_a_completion_claim(eng):
    data = _manifest()
    data["elements"][0]["status"] = "delivered"
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_manifest(data))}
    assert "uncited-element-claim" in kinds


def test_manifest_element_claim_passes_with_a_citation(eng):
    data = _manifest()
    data["elements"].append({
        "location": "app/components/StatementList.tsx",
        "name": "Statement list",
        "functionality": "Renders the statement rows — implementation complete and verified.",
        "evidence": "reviews/statement-list.json",
    })
    assert eng.errors_only(eng.validate_manifest(data)) == []


def test_manifest_element_descriptive_prose_is_not_a_claim(eng):
    """False-positive control — describing what an element does is not a
    claim that it was verified."""
    data = _manifest()
    data["elements"].append({
        "location": "app/components/StatementList.tsx",
        "name": "Statement list",
        "functionality": "Shows a completed-statements filter and a working-copy toggle.",
    })
    assert eng.errors_only(eng.validate_manifest(data)) == []


def test_manifest_citation_markers_constant_exists(eng):
    assert hasattr(eng, "EVIDENCE_CITATION_MARKERS")
    blob = " ".join(eng.EVIDENCE_CITATION_MARKERS).lower()
    assert "vao-verdicts" in blob
    assert "screenshot" in blob


def test_manifest_cli_reports_the_citation_error(eng, tmp_path, capsys):
    data = _manifest()
    data["validation_steps"].append({
        "step": "Open the statements tab.",
        "expected": "The statement list is verified to load for every account type.",
    })
    src = tmp_path / "manifest.json"
    src.write_text(json.dumps(data), encoding="utf-8")
    assert eng.main(["validate", "--json", str(src)]) == 1
    assert "uncited-verified-claim" in capsys.readouterr().out
