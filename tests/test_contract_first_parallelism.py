"""v3.48.0 contract-first parallelism — the architect's mock-first parallelism protocol.

Covers the deterministic engine (`scripts/contract/interface_contract.py`):
the contract approval gate, the forward-only ledger state machine, the
close-out retirement gate (a run cannot close on a surface still serving a
provisional payload), contract-drift adjudication, and the CLI — plus the
wiring pins (Phase 2 detection + Phase 8 gate, mini M4/M7, the two implementer
agents, the architect's approval mode, and the CPC canonical section).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def eng() -> ModuleType:
    return load_module(REPO_ROOT / "scripts" / "contract" / "interface_contract.py",
                       "interface_contract_module")


def _contract() -> dict:
    return {
        "contract_id": "statements-list",
        "shape": "new-surface",
        "method": "GET",
        "path": "/api/customers/{id}/statements",
        "consumer": "frontend-account",
        "owner": "backend-billing",
        "purpose": "The account page renders a statement list with amounts and dates.",
        "response_fields": [
            {"name": "id", "type": "string", "meaning": "statement id"},
            {"name": "issued_at", "type": "string", "meaning": "ISO issue date"},
            {"name": "total", "type": "number", "meaning": "amount due"},
            {"name": "paid", "type": "boolean", "meaning": "settled flag"},
        ],
        "error_states": [
            {"status": 404, "meaning": "no such customer"},
            {"status": 403, "meaning": "not entitled to this customer"},
        ],
    }


# --------------------------------------------------------------------------- #
# CFP-3 — the approval gate
# --------------------------------------------------------------------------- #

def test_complete_contract_passes_the_approval_gate(eng: ModuleType) -> None:
    assert eng.errors_only(eng.validate_contract(_contract())) == []


def test_missing_required_fields_block(eng: ModuleType) -> None:
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract({"shape": "new-surface"}))}
    assert "missing-field" in kinds


def test_untyped_response_field_blocks(eng: ModuleType) -> None:
    """The frontend cannot build against an untyped field — a blocker, not a nit."""
    c = _contract()
    c["response_fields"] = [{"name": "total", "meaning": "amount"}]
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "response-field-untyped" in kinds


def test_unnamed_duplicated_and_bad_type_fields_block(eng: ModuleType) -> None:
    c = _contract()
    c["response_fields"] = [
        {"name": "", "type": "string"},
        {"name": "total", "type": "number"},
        {"name": "total", "type": "number"},
        {"name": "odd", "type": "decimal"},
    ]
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert {"response-field-unnamed", "response-field-duplicated", "response-field-bad-type"} <= kinds


def test_missing_error_states_block(eng: ModuleType) -> None:
    """Error paths are built in the same pass as the happy path."""
    c = _contract()
    c["error_states"] = []
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "no-error-states" in kinds


def test_relative_path_blocks(eng: ModuleType) -> None:
    """The frontend calls the REAL path — never a temporary one it must be
    re-pointed away from later."""
    c = _contract()
    c["path"] = "mock/statements"
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "path-not-rooted" in kinds


def test_any_typed_field_is_advisory_not_blocking(eng: ModuleType) -> None:
    c = _contract()
    c["response_fields"].append({"name": "meta", "type": "any", "meaning": "passthrough"})
    findings = eng.validate_contract(c)
    assert eng.errors_only(findings) == []
    assert any(f["kind"] == "response-field-type-any" for f in findings)


def test_amend_surface_requires_named_added_fields(eng: ModuleType) -> None:
    """The existing-surface-new-attributes case is the same protocol, and it
    must name what it adds."""
    c = _contract()
    c["shape"] = "amend-surface"
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "amend-without-added-fields" in kinds

    c["added_fields"] = ["not_declared"]
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "added-field-not-in-response-shape" in kinds

    c["added_fields"] = ["paid"]
    assert eng.errors_only(eng.validate_contract(c)) == []


def test_unknown_shape_and_method_block(eng: ModuleType) -> None:
    c = _contract()
    c["shape"] = "vibes"
    c["method"] = "FETCH"
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert {"unknown-shape", "unknown-method"} <= kinds


def test_contract_doc_carries_shape_errors_and_the_retirement_clause(eng: ModuleType) -> None:
    doc = eng.build_contract_doc({**_contract(), "state": "approved", "approved_by": "system-architect"})
    assert "GET /api/customers/{id}/statements" in doc
    assert "## Response shape" in doc and "| total | number |" in doc
    assert "## Error states" in doc and "404" in doc
    assert "## Mock retirement" in doc and "cannot close" in doc


def test_contract_doc_marks_added_attributes(eng: ModuleType) -> None:
    c = {**_contract(), "shape": "amend-surface", "added_fields": ["paid"]}
    doc = eng.build_contract_doc(c)
    assert "| paid | boolean | settled flag | yes |" in doc


# --------------------------------------------------------------------------- #
# CFP-4/5 — the ledger state machine
# --------------------------------------------------------------------------- #

def test_states_are_the_documented_four(eng: ModuleType) -> None:
    assert eng.CONTRACT_STATES == ("proposed", "approved", "mock-serving", "live")
    assert eng.TERMINAL_STATE == "live"


def test_forward_transitions_are_allowed(eng: ModuleType) -> None:
    e = {"contract_id": "x", "state": "proposed"}
    for nxt in ("approved", "mock-serving", "live"):
        e = eng.transition(e, nxt)
        assert e["state"] == nxt


def test_backward_transition_is_refused(eng: ModuleType) -> None:
    """A live surface never silently reverts to serving its mock."""
    with pytest.raises(ValueError):
        eng.transition({"contract_id": "x", "state": "live"}, "mock-serving")


def test_transition_does_not_mutate_the_input(eng: ModuleType) -> None:
    entry = {"contract_id": "x", "state": "approved"}
    eng.transition(entry, "live")
    assert entry["state"] == "approved"


def test_unknown_state_is_refused(eng: ModuleType) -> None:
    with pytest.raises(ValueError):
        eng.transition({"state": "approved"}, "retired-ish")


# --------------------------------------------------------------------------- #
# CFP-6 — the retirement gate
# --------------------------------------------------------------------------- #

def _ledger(state: str) -> list:
    return [{"contract_id": "statements-list", "method": "GET",
             "path": "/api/customers/{id}/statements", "state": state}]


@pytest.mark.parametrize("state", ["proposed", "approved", "mock-serving"])
def test_any_unretired_state_blocks_the_close_out(eng: ModuleType, state: str) -> None:
    findings = eng.retirement_gate(_ledger(state))
    blocking = eng.errors_only(findings)
    assert blocking, f"{state} must block"
    assert blocking[0]["kind"] == "mock-not-retired"


def test_live_with_evidence_clears_the_gate(eng: ModuleType) -> None:
    ledger = _ledger("live")
    ledger[0]["verified_by"] = "tests/e2e/statements.spec.ts — real payload observed"
    assert eng.retirement_gate(ledger) == []


def test_live_without_evidence_is_advisory_only(eng: ModuleType) -> None:
    """The engine cannot witness the endpoint, so it points rather than pretends."""
    findings = eng.retirement_gate(_ledger("live"))
    assert eng.errors_only(findings) == []
    assert any(f["kind"] == "retirement-unverified" for f in findings)


def test_empty_ledger_is_a_no_op(eng: ModuleType) -> None:
    """A run that created no contracts skips the gate — absent is not failure."""
    assert eng.retirement_gate([]) == []
    assert eng.retirement_gate(None) == []


def test_unretired_mocks_lists_only_the_debt(eng: ModuleType) -> None:
    ledger = _ledger("mock-serving") + [{"contract_id": "b", "state": "live"}]
    assert [e["contract_id"] for e in eng.unretired_mocks(ledger)] == ["statements-list"]


def test_ledger_summary_reports_every_state(eng: ModuleType) -> None:
    summary = eng.ledger_summary(_ledger("mock-serving") + [{"contract_id": "b", "state": "live"}])
    assert summary == {"proposed": 0, "approved": 0, "mock-serving": 1, "live": 1}


# --------------------------------------------------------------------------- #
# drift — approved shape vs what the surface actually returns
# --------------------------------------------------------------------------- #

def test_conforming_payload_has_no_drift(eng: ModuleType) -> None:
    observed = {"id": "s1", "issued_at": "2026-07-01", "total": 12.5, "paid": False}
    assert eng.contract_drift(_contract(), observed) == []


def test_missing_and_mistyped_fields_are_errors(eng: ModuleType) -> None:
    observed = {"id": "s1", "issued_at": "2026-07-01", "total": "12.50"}
    kinds = {f["kind"] for f in eng.errors_only(eng.contract_drift(_contract(), observed))}
    assert {"contract-field-missing", "contract-field-type-mismatch"} <= kinds


def test_integer_satisfies_a_number_field(eng: ModuleType) -> None:
    observed = {"id": "s1", "issued_at": "2026-07-01", "total": 12, "paid": True}
    assert eng.errors_only(eng.contract_drift(_contract(), observed)) == []


def test_undeclared_extra_field_is_advisory(eng: ModuleType) -> None:
    observed = {"id": "s1", "issued_at": "2026-07-01", "total": 1, "paid": True, "_mock": True}
    findings = eng.contract_drift(_contract(), observed)
    assert eng.errors_only(findings) == []
    assert any(f["kind"] == "undeclared-field" for f in findings)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_validate_exit_codes(eng: ModuleType, tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_contract()), encoding="utf-8")
    assert eng.main(["validate", "--json", str(good)]) == 0
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**_contract(), "error_states": []}), encoding="utf-8")
    assert eng.main(["validate", "--json", str(bad)]) == 1


def test_cli_gate_blocks_on_an_unretired_ledger(eng: ModuleType, tmp_path: Path, capsys) -> None:
    led = tmp_path / "ledger.json"
    led.write_text(json.dumps(_ledger("mock-serving")), encoding="utf-8")
    assert eng.main(["gate", "--ledger", str(led)]) == 1
    out = capsys.readouterr().out
    assert "mock-not-retired" in out and "mock-serving=1" in out

    led.write_text(json.dumps([{**_ledger("live")[0], "verified_by": "e2e run"}]), encoding="utf-8")
    assert eng.main(["gate", "--ledger", str(led)]) == 0


def test_cli_gate_accepts_the_wrapped_ledger_shape(eng: ModuleType, tmp_path: Path) -> None:
    led = tmp_path / "ledger.json"
    led.write_text(json.dumps({"contracts": _ledger("mock-serving")}), encoding="utf-8")
    assert eng.main(["gate", "--ledger", str(led)]) == 1


def test_cli_doc_writes_the_artifact(eng: ModuleType, tmp_path: Path) -> None:
    src = tmp_path / "c.json"
    src.write_text(json.dumps(_contract()), encoding="utf-8")
    out = tmp_path / "contracts" / "c.md"
    assert eng.main(["doc", "--json", str(src), "--out", str(out)]) == 0
    assert "## Mock retirement" in out.read_text(encoding="utf-8")


def test_cli_drift_exit_codes(eng: ModuleType, tmp_path: Path) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")
    obs = tmp_path / "obs.json"
    obs.write_text(json.dumps({"id": "s1", "issued_at": "x", "total": 1, "paid": True}), encoding="utf-8")
    assert eng.main(["drift", "--json", str(c), "--observed", str(obs)]) == 0
    obs.write_text(json.dumps({"id": "s1"}), encoding="utf-8")
    assert eng.main(["drift", "--json", str(c), "--observed", str(obs)]) == 1


# --------------------------------------------------------------------------- #
# wiring pins
# --------------------------------------------------------------------------- #

def test_skill_contract_carries_the_six_phases_and_the_boundary() -> None:
    body = (REPO_ROOT / "skills" / "contract-first-parallelism" / "SKILL.md").read_text(encoding="utf-8")
    for phase in ("CFP-1", "CFP-2", "CFP-3", "CFP-4", "CFP-5", "CFP-6"):
        assert phase in body, phase
    assert "new-surface" in body and "amend-surface" in body
    assert "scripts/contract/interface_contract.py" in body
    assert "## Relationship to the no-fake-data disciplines" in body
    assert "## Honest boundary" in body


def test_main_pipeline_detects_at_phase_2_and_gates_at_phase_8() -> None:
    body = (REPO_ROOT / "skills" / "architect-team-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    phase2 = body.split("## Phase 2 —", 1)[1].split("## Phase 3 —", 1)[0]
    assert "contract-first-parallelism" in phase2, "Phase 2 must engage the protocol before spawn"
    assert "interface_contract.py" in phase2
    assert "### Mock-retirement gate" in body
    gate = body.split("### Mock-retirement gate", 1)[1][:2000]
    assert "gate --ledger" in gate
    assert "does not close" in gate


def test_mini_pipeline_wires_m4_and_m7() -> None:
    body = (REPO_ROOT / "skills" / "mini-architect-team-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    m4 = body.split("## Phase M4 —", 1)[1].split("## Phase M5", 1)[0]
    assert "contract-first-parallelism" in m4
    m7 = body.split("## Phase M7 —", 1)[1]
    assert "interface_contract.py" in m7 and "gate --ledger" in m7


def test_cpc_carries_the_canonical_statement() -> None:
    body = (REPO_ROOT / "skills" / "common-pipeline-conventions" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Contract-first parallelism (v3.48.0 — the canonical statement)" in body
    section = body.split("## Contract-first parallelism", 1)[1].split("## Frontend missing-API discipline", 1)[0]
    assert "SERVER-SIDE" in section
    assert "forward-only" in section


def test_backend_agent_owns_provisioning_and_retirement() -> None:
    body = (REPO_ROOT / "agents" / "backend.md").read_text(encoding="utf-8")
    assert "## Contract-first provisioning" in body
    section = body.split("## Contract-first provisioning", 1)[1].split("## Missing-API SR intake", 1)[0]
    assert "REAL path" in section
    assert "ledger.json" in section
    assert "mock-serving" in section and "live" in section


def test_frontend_agent_builds_against_live_and_holds_no_fallback() -> None:
    body = (REPO_ROOT / "agents" / "frontend.md").read_text(encoding="utf-8")
    assert "## Contract-first parallelism" in body
    section = body.split("## Contract-first parallelism", 1)[1].split("## Missing-API discipline", 1)[0]
    assert "no `page.route` intercept" in section or "page.route" in section
    assert "LIVE endpoint" in section or "live surface" in section


def test_missing_api_discipline_is_scoped_to_uncontracted_surfaces() -> None:
    """The SR-and-pause path remains — narrowed to the surface the architect
    has NOT contracted, so the two rules cannot contradict each other."""
    import re

    for rel, heading in (("agents/frontend.md", "## Missing-API discipline"),
                         ("skills/common-pipeline-conventions/SKILL.md",
                          "## Frontend missing-API discipline")):
        body = (REPO_ROOT / rel).read_text(encoding="utf-8")
        # Anchor at line start — a cross-REFERENCE to the heading elsewhere in
        # the body must not be mistaken for the section itself.
        m = re.search(r"^" + re.escape(heading) + r"$", body, re.M)
        assert m, f"{rel}: {heading!r} section not found"
        head = body[m.start():m.start() + 900]
        assert "no contract-first protocol is running" in head, rel


def test_architect_carries_the_approval_mode() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text(encoding="utf-8")
    assert "## Interface Contract Approval" in body
    assert "TEN distinct modes" in body
    section = body.split("## Interface Contract Approval", 1)[1]
    assert "interface_contract.py validate" in section
    assert "reuse" in section.lower()
    assert "binding" in section.lower() or "binds" in section.lower()
