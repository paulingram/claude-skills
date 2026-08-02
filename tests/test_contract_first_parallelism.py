"""v3.48.0 contract-first parallelism — the architect's mock-first parallelism protocol.

Covers the deterministic engine (`scripts/contract/interface_contract.py`):
the contract approval gate, the forward-only ledger state machine, the
close-out retirement gate (a run cannot close on a surface still serving a
provisional payload), contract-drift adjudication, and the CLI — plus the
wiring pins (Phase 2 detection + Phase 8 gate, mini M4/M7, the two implementer
agents, the architect's approval mode, and the CPC canonical section).

The post-merge review pass added the assertions that make the gate's SAFETY
property real rather than advertised, since the ledger it reads is hand-written
JSON with no writer API in front of it:

* FAIL-CLOSED ledger reading — an unrecognized state, a non-mapping entry, and
  an unrecognized container shape each BLOCK with a named reason, and the
  summary carries an `unknown` bucket so no entry can vanish from the operator's
  one visibility line. A gate that reports the all-clear on input it could not
  parse is the failure mode these cover.
* The provisional marker as a MACHINE check (`contract_drift(..., retirement=True)`)
  rather than a convention no code path consumed.
* Nested binding — a declared `items` / `fields` shape is adjudicated by payload
  path, and a non-object payload is a clean named error instead of a crash.
* Registration of the retirement gate in the v3.47.0 declared-gates registry,
  asserted THROUGH the real Stop-hook arm rather than against a restatement of
  its rules.
* Vocabulary pins that bite: the required-field set and the HTTP-method set are
  pinned per member, and the contract doc's `New` column is asserted negatively
  as well as positively. Each was proven falsifiable against a scratch mutant —
  see `.architect-team/red-runs/rv-fixer/mutation-matrix.md`.
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


def test_the_required_field_set_is_the_documented_eight(eng: ModuleType) -> None:
    """The approval gate is advertised as blocking on missing required fields. Pin
    the whole vocabulary, so shrinking it cannot pass."""
    assert eng.REQUIRED_CONTRACT_FIELDS == (
        "contract_id", "shape", "method", "path", "consumer", "owner",
        "response_fields", "error_states",
    )


@pytest.mark.parametrize("field", ["contract_id", "shape", "method", "path", "consumer",
                                   "owner", "response_fields", "error_states"])
def test_every_required_field_is_individually_required(eng: ModuleType, field: str) -> None:
    """Dropping ANY one required field blocks and CITES that field — asserting
    only that some 'missing-field' fired is satisfied by a single surviving
    requirement, which is not what the gate claims to enforce."""
    c = _contract()
    del c[field]
    missing = [f for f in eng.errors_only(eng.validate_contract(c)) if f["kind"] == "missing-field"]
    assert any(field in f["detail"] for f in missing), (
        f"dropping {field!r} produced no missing-field naming it: {missing}"
    )


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_every_documented_method_validates_clean(eng: ModuleType, method: str) -> None:
    """A narrowed method vocabulary would reject real contracts — pin the set
    positively, not just the rejection of a bogus verb."""
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract({**_contract(), "method": method}))}
    assert "unknown-method" not in kinds


def test_untyped_response_field_blocks(eng: ModuleType) -> None:
    """The frontend cannot build against an untyped field — a blocker, not a nit."""
    c = _contract()
    c["response_fields"] = [{"name": "total", "meaning": "amount"}]
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "response-field-untyped" in kinds


@pytest.mark.parametrize("name", [{"a": 1}, {}, ["a"], [], 42, True, None])
def test_a_non_string_field_name_is_a_finding_not_a_crash(eng: ModuleType, name) -> None:
    """The contract is hand-authored JSON, so a field name can be any JSON value.
    Detecting duplicates by hashing it raises TypeError on objects and arrays, and
    the approval gate is the moment that must NAME the problem rather than die on
    it — a traceback blocks nothing and explains nothing."""
    c = _contract()
    c["response_fields"] = [{"name": name, "type": "string", "meaning": "m"}]
    assert "response-field-unnamed" in {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    # the same contract must not crash the drift check or the amend cross-check
    eng.contract_drift(c, {"id": "s1"})
    c["shape"] = "amend-surface"
    c["added_fields"] = ["whatever"]
    assert eng.errors_only(eng.validate_contract(c))


def test_a_non_string_nested_field_name_is_a_finding_not_a_crash(eng: ModuleType) -> None:
    c = _collection_contract()
    c["response_fields"][0]["items"] = [{"name": {"x": 1}, "type": "string"}]
    assert "response-field-unnamed" in {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    eng.contract_drift(c, {"items": [{"id": "s1"}], "meta": {"total_count": 1}})


def test_a_non_string_added_field_is_a_finding_not_a_crash(eng: ModuleType) -> None:
    c = {**_contract(), "shape": "amend-surface", "added_fields": [{"x": 1}, ["y"]]}
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "added-field-not-in-response-shape" in kinds


@pytest.mark.parametrize("value", [42, True, 0.5, "text", {"a": 1}])
def test_drift_survives_an_unreadable_response_fields_section(eng: ModuleType, value) -> None:
    """The same shape hazard on the drift path — `or []` does not catch a scalar,
    and iterating one raises. A contract whose response shape is unreadable was
    already refused at approval; drift adjudicates nothing rather than crashing."""
    assert eng.errors_only(eng.contract_drift({**_contract(), "response_fields": value},
                                              {"id": "s1"})) == []


def test_drift_ignores_an_unusably_named_declaration_rather_than_crashing(eng: ModuleType) -> None:
    """A declaration the engine cannot address by name is reported at APPROVAL;
    the drift check simply cannot adjudicate it, and must say nothing rather than
    invent a finding or crash."""
    c = _contract()
    c["response_fields"] = [{"name": {"x": 1}, "type": "string"}, {"name": "id", "type": "string"}]
    assert eng.errors_only(eng.contract_drift(c, {"id": "s1"})) == []


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


@pytest.mark.parametrize("key", ["response_fields", "error_states", "added_fields"])
@pytest.mark.parametrize("value", [42, True, 0.5, "text"])
def test_the_doc_renderer_survives_a_contract_the_gate_would_have_blocked(
        eng: ModuleType, key: str, value) -> None:
    """`doc` is a standalone CLI verb, so it can meet a contract that never passed
    validation — a scalar where a list belongs makes the section unreadable and
    iterating it raises. The gate is what REFUSES such a contract; the renderer's
    job is to render no rows for a section it cannot read, not to crash."""
    doc = eng.build_contract_doc({**_contract(), key: value})
    assert "## Response shape" in doc and "## Mock retirement" in doc


def test_contract_doc_does_not_mark_a_non_added_attribute_as_new(eng: ModuleType) -> None:
    """For an amend-surface contract the 'New' column is the artifact's one
    discriminating signal — a renderer that marks everything says nothing."""
    doc = eng.build_contract_doc({**_contract(), "shape": "amend-surface", "added_fields": ["paid"]})
    assert "| total | number | amount due |  |" in doc
    assert "| total | number | amount due | yes |" not in doc


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


@pytest.mark.parametrize("ledger", [42, True, 0.5, "mock-serving", {"contracts": []}, {}])
def test_a_ledger_that_is_not_an_array_blocks(eng: ModuleType, ledger) -> None:
    """`retirement_gate` is public API — a caller can reach it without going
    through `normalize_ledger` (passing the WRAPPER instead of the entries is the
    obvious mistake). Not-an-array must BLOCK: crashing explains nothing, and
    reading as empty is the silent green this whole pass exists to remove."""
    blocking = eng.errors_only(eng.retirement_gate(ledger))
    assert blocking and blocking[0]["kind"] == "malformed-ledger"
    assert sum(eng.ledger_summary(ledger).values()) == 0
    assert eng.unretired_mocks(ledger) == []


def test_unretired_mocks_lists_only_the_debt(eng: ModuleType) -> None:
    ledger = _ledger("mock-serving") + [{"contract_id": "b", "state": "live"}]
    assert [e["contract_id"] for e in eng.unretired_mocks(ledger)] == ["statements-list"]


def test_ledger_summary_reports_every_state(eng: ModuleType) -> None:
    summary = eng.ledger_summary(_ledger("mock-serving") + [{"contract_id": "b", "state": "live"}])
    assert summary == {"proposed": 0, "approved": 0, "mock-serving": 1, "live": 1, "unknown": 0}


# --------------------------------------------------------------------------- #
# CFP-6 — the gate reads a HAND-WRITTEN ledger, so it fails CLOSED on anything
# it cannot recognize. An unreadable entry is never evidence of a retired mock.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("state", ["mock_serving", "MOCK-SERVING", "retired", "done",
                                   "", "pending", None])
def test_an_unrecognized_ledger_state_blocks_the_close_out(eng: ModuleType, state) -> None:
    """A one-character typo is not a retirement. The gate cannot tell whether the
    mock is still serving, so it blocks and names the state it could not read."""
    ledger = _ledger("live")
    ledger[0]["state"] = state
    blocking = eng.errors_only(eng.retirement_gate(ledger))
    assert blocking, f"state {state!r} must block"
    assert blocking[0]["kind"] == "unknown-ledger-state"
    assert repr(state) in blocking[0]["detail"]


def test_a_malformed_ledger_entry_blocks(eng: ModuleType) -> None:
    """An entry the engine cannot even read is debt, not an absence of debt."""
    blocking = eng.errors_only(eng.retirement_gate(["mock-serving", 42, None]))
    assert len(blocking) == 3
    assert {f["kind"] for f in blocking} == {"malformed-ledger-entry"}


def test_unretired_mocks_counts_an_unrecognized_state_as_debt(eng: ModuleType) -> None:
    ledger = _ledger("mock_serving") + [{"contract_id": "b", "state": "live"}]
    assert [e["contract_id"] for e in eng.unretired_mocks(ledger)] == ["statements-list"]


@pytest.mark.parametrize("state", [{}, {"nested": 1}, ["live"], [], True, 3, 0.5])
def test_an_unhashable_or_non_string_state_is_counted_not_crashed_on(eng: ModuleType, state) -> None:
    """The ledger is hand-written JSON, so a state can be any JSON value — an
    object or an array included. Bucketing by dict-key lookup raises TypeError on
    exactly those, and a traceback is not a named reason: it is the same
    unhandled-shape failure the drift check had. Fail closed, out loud."""
    ledger = [{"contract_id": "c1", "state": state}]
    summary = eng.ledger_summary(ledger)
    assert summary[eng.UNKNOWN_STATE_BUCKET] == 1
    assert sum(summary.values()) == 1
    blocking = eng.errors_only(eng.retirement_gate(ledger))
    assert blocking and blocking[0]["kind"] == "unknown-ledger-state"


def test_a_state_literally_named_unknown_is_not_mistaken_for_a_real_state(eng: ModuleType) -> None:
    """`unknown` is the summary's bucket name, not a ledger state — an entry
    claiming it must not be able to launder itself into the counts."""
    ledger = [{"contract_id": "c1", "state": "unknown"}]
    assert eng.ledger_summary(ledger) == {"proposed": 0, "approved": 0, "mock-serving": 0,
                                          "live": 0, "unknown": 1}
    assert eng.errors_only(eng.retirement_gate(ledger))[0]["kind"] == "unknown-ledger-state"


def test_ledger_summary_surfaces_unknown_states_and_sums_to_the_ledger(eng: ModuleType) -> None:
    """The summary line is the operator's only visibility — an entry must never
    vanish from it."""
    ledger = (_ledger("mock_serving")
              + [{"contract_id": "b", "state": "live"}, {"contract_id": "c"}])
    summary = eng.ledger_summary(ledger)
    assert summary == {"proposed": 1, "approved": 0, "mock-serving": 0, "live": 1, "unknown": 1}
    assert sum(summary.values()) == len(ledger)


# --------------------------------------------------------------------------- #
# the ledger CONTAINER — checked as strictly as its entries
# --------------------------------------------------------------------------- #

def test_the_documented_ledger_shapes_normalize_clean(eng: ModuleType) -> None:
    bare = _ledger("mock-serving")
    assert eng.normalize_ledger(bare) == (bare, [])
    assert eng.normalize_ledger({"contracts": bare}) == (bare, [])


def test_an_unrecognized_ledger_wrapper_is_an_error_not_an_empty_pass(eng: ModuleType) -> None:
    """The engine ships no writer, so the agent hand-rolls the file. A wrapper key
    the engine does not know must not read as 'no contracts recorded'."""
    entries, findings = eng.normalize_ledger({"entries": _ledger("mock-serving")})
    assert entries == []
    assert {f["kind"] for f in eng.errors_only(findings)} == {"unrecognized-ledger-shape"}


@pytest.mark.parametrize("payload", ["mock-serving", 42, None, True])
def test_a_non_array_ledger_document_is_an_error(eng: ModuleType, payload) -> None:
    entries, findings = eng.normalize_ledger(payload)
    assert entries == []
    assert eng.errors_only(findings), payload


def test_the_wrapper_key_must_carry_an_array(eng: ModuleType) -> None:
    entries, findings = eng.normalize_ledger({"contracts": {"statements-list": "live"}})
    assert entries == []
    assert {f["kind"] for f in eng.errors_only(findings)} == {"malformed-ledger"}


def test_cli_gate_blocks_on_an_unrecognized_wrapper(eng: ModuleType, tmp_path: Path, capsys) -> None:
    led = tmp_path / "ledger.json"
    led.write_text(json.dumps({"entries": _ledger("mock-serving")}), encoding="utf-8")
    assert eng.main(["gate", "--ledger", str(led)]) == 1
    out = capsys.readouterr().out
    assert "unrecognized-ledger-shape" in out
    assert "proposed=0" not in out, (
        "an unreadable ledger must not also print a clean-looking all-zero count line"
    )


def test_cli_gate_blocks_on_a_typod_state(eng: ModuleType, tmp_path: Path, capsys) -> None:
    led = tmp_path / "ledger.json"
    led.write_text(json.dumps(_ledger("mock_serving")), encoding="utf-8")
    assert eng.main(["gate", "--ledger", str(led)]) == 1
    out = capsys.readouterr().out
    assert "unknown-ledger-state" in out and "unknown=1" in out


def test_cli_gate_treats_an_absent_ledger_as_a_clean_no_op(eng: ModuleType, tmp_path: Path, capsys) -> None:
    """Most runs create no contracts, and Phase 8 documents the absent case as
    benign — the command must agree with the instruction."""
    assert eng.main(["gate", "--ledger", str(tmp_path / "does-not-exist.json")]) == 0
    assert "no contracts recorded" in capsys.readouterr().out


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


def test_drift_on_a_json_array_payload_is_a_clean_error_not_a_crash(eng: ModuleType) -> None:
    """A collection endpoint is the ordinary REST shape; the drift check is the
    only confirmation the delivered surface still matches the approved one, so it
    must not die on it."""
    findings = eng.contract_drift(_contract(), [{"id": "s1", "total": 1.0}])
    assert [f["kind"] for f in eng.errors_only(findings)] == ["observed-payload-not-an-object"]
    assert "array" in findings[0]["detail"]


@pytest.mark.parametrize("payload", [["s1"], "s1", 12, None, True])
def test_drift_names_the_json_type_it_received(eng: ModuleType, payload) -> None:
    findings = eng.errors_only(eng.contract_drift(_contract(), payload))
    assert [f["kind"] for f in findings] == ["observed-payload-not-an-object"]


def test_cli_drift_on_an_array_payload_exits_cleanly(eng: ModuleType, tmp_path: Path, capsys) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")
    obs = tmp_path / "obs.json"
    obs.write_text(json.dumps([{"id": "s1", "total": 1.0}]), encoding="utf-8")
    assert eng.main(["drift", "--json", str(c), "--observed", str(obs)]) == 1
    assert "observed-payload-not-an-object" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CFP-4 — the provisional marker is a MACHINE check, not a convention
# --------------------------------------------------------------------------- #

def _served() -> dict:
    return {"id": "s1", "issued_at": "2026-07-01", "total": 1, "paid": True}


def test_retirement_drift_blocks_on_the_provisional_marker(eng: ModuleType) -> None:
    """A surface still serving its provisional envelope has not been retired,
    however the ledger describes it."""
    findings = eng.contract_drift(_contract(), {**_served(), "_mock": True}, retirement=True)
    blocking = eng.errors_only(findings)
    assert [f["kind"] for f in blocking] == ["provisional-marker-still-served"]
    assert "_mock" in blocking[0]["detail"]


def test_the_marker_stays_advisory_outside_retirement_mode(eng: ModuleType) -> None:
    """During CFP-5 the marker is EXPECTED — it only becomes a blocker at CFP-6."""
    assert eng.errors_only(eng.contract_drift(_contract(), {**_served(), "_mock": True})) == []


def test_a_retired_payload_passes_retirement_drift(eng: ModuleType) -> None:
    assert eng.contract_drift(_contract(), _served(), retirement=True) == []


def test_the_provisional_marker_is_configurable_per_contract(eng: ModuleType) -> None:
    c = {**_contract(), "provisional_marker": "__provisional"}
    kinds = {f["kind"] for f in eng.errors_only(
        eng.contract_drift(c, {**_served(), "__provisional": True}, retirement=True))}
    assert "provisional-marker-still-served" in kinds
    assert eng.provisional_marker(c) == "__provisional"
    assert eng.provisional_marker(_contract()) == eng.DEFAULT_PROVISIONAL_MARKER


def test_a_nested_provisional_marker_is_caught(eng: ModuleType) -> None:
    """The envelope can sit on the element, not only the top level."""
    c = _contract()
    c["response_fields"] = c["response_fields"] + [{"name": "meta", "type": "object", "meaning": "envelope"}]
    kinds = {f["kind"] for f in eng.errors_only(
        eng.contract_drift(c, {**_served(), "meta": {"_mock": True}}, retirement=True))}
    assert "provisional-marker-still-served" in kinds


def test_declaring_the_marker_as_a_response_field_blocks_approval(eng: ModuleType) -> None:
    """A contract that DECLARES its provisional marker would make the mock
    permanently legitimate — the retirement check could never fire."""
    c = _contract()
    c["response_fields"].append({"name": "_mock", "type": "boolean", "meaning": "provisional"})
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "provisional-marker-declared-as-field" in kinds


def test_cli_drift_carries_the_retirement_flag(eng: ModuleType, tmp_path: Path) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")
    obs = tmp_path / "obs.json"
    obs.write_text(json.dumps({**_served(), "_mock": True}), encoding="utf-8")
    assert eng.main(["drift", "--json", str(c), "--observed", str(obs)]) == 0
    assert eng.main(["drift", "--json", str(c), "--observed", str(obs), "--retirement"]) == 1


# --------------------------------------------------------------------------- #
# nested binding — the contract must bind the shape the protocol actually carries
# --------------------------------------------------------------------------- #

def _collection_contract() -> dict:
    return {
        **_contract(),
        "contract_id": "statements-collection",
        "response_fields": [
            {"name": "items", "type": "array", "meaning": "the statements",
             "items": [{"name": "id", "type": "string", "meaning": "statement id"},
                       {"name": "total", "type": "number", "meaning": "amount due"}]},
            {"name": "meta", "type": "object", "meaning": "paging",
             "fields": [{"name": "total_count", "type": "integer", "meaning": "row count"}]},
        ],
    }


def test_a_declared_element_shape_binds_the_payload(eng: ModuleType) -> None:
    """'Can the frontend build a finished interface against this' is false for a
    list-of-objects whose elements are unconstrained."""
    c = _collection_contract()
    assert eng.errors_only(eng.validate_contract(c)) == []
    assert eng.contract_drift(c, {"items": [{"id": "s1", "total": 1.0}],
                                  "meta": {"total_count": 1}}) == []
    findings = eng.contract_drift(c, {"items": [{"utterly": "wrong"}], "meta": {"nope": 1}})
    assert {f["kind"] for f in eng.errors_only(findings)} == {"contract-field-missing"}
    details = " ".join(f["detail"] for f in findings)
    assert "items[].id" in details and "meta.total_count" in details


def test_a_nested_type_mismatch_is_an_error(eng: ModuleType) -> None:
    findings = eng.errors_only(eng.contract_drift(
        _collection_contract(),
        {"items": [{"id": "s1", "total": "1.00"}], "meta": {"total_count": 1}}))
    assert [f["kind"] for f in findings] == ["contract-field-type-mismatch"]
    assert "items[].total" in findings[0]["detail"]


def test_an_empty_collection_does_not_violate_the_element_shape(eng: ModuleType) -> None:
    """An empty array cannot PROVE the element shape, but it does not contradict
    it either — the engine reports what it can see, not what it wishes it saw."""
    assert eng.errors_only(eng.contract_drift(
        _collection_contract(), {"items": [], "meta": {"total_count": 0}})) == []


def test_a_non_object_array_element_is_an_error(eng: ModuleType) -> None:
    kinds = {f["kind"] for f in eng.errors_only(eng.contract_drift(
        _collection_contract(), {"items": ["s1"], "meta": {"total_count": 1}}))}
    assert "contract-element-not-an-object" in kinds


def test_repeated_element_drift_is_reported_once_per_declared_path(eng: ModuleType) -> None:
    """A 200-row payload with one bad field is one finding, not 200."""
    payload = {"items": [{"id": "s1"} for _ in range(50)], "meta": {"total_count": 50}}
    findings = eng.errors_only(eng.contract_drift(_collection_contract(), payload))
    assert [f["kind"] for f in findings] == ["contract-field-missing"]


def test_an_unshaped_container_is_advisory_at_approval(eng: ModuleType) -> None:
    """The remaining gap is at least VISIBLE — an unshaped array/object does not
    block, but the architect is told the contract does not constrain it."""
    c = _contract()
    c["response_fields"] = [{"name": "items", "type": "array", "meaning": "rows"},
                            {"name": "meta", "type": "object", "meaning": "paging"}]
    findings = eng.validate_contract(c)
    assert eng.errors_only(findings) == []
    assert [f["kind"] for f in findings] == ["response-field-unshaped-container"] * 2


def test_nested_declarations_are_validated_like_top_level_ones(eng: ModuleType) -> None:
    c = _collection_contract()
    c["response_fields"][0]["items"] = [{"name": "id"}, {"name": "id", "type": "string"}]
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert {"response-field-untyped", "response-field-duplicated"} <= kinds


def test_a_malformed_nested_shape_blocks(eng: ModuleType) -> None:
    c = _collection_contract()
    c["response_fields"][0]["items"] = {"name": "id", "type": "string"}
    kinds = {f["kind"] for f in eng.errors_only(eng.validate_contract(c))}
    assert "malformed-nested-shape" in kinds


def test_the_contract_doc_renders_the_nested_rows(eng: ModuleType) -> None:
    doc = eng.build_contract_doc(_collection_contract())
    assert "| items[].id | string |" in doc
    assert "| meta.total_count | integer |" in doc


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
# CFP-4 — the retirement gate is REGISTERED in the v3.47.0 declared-gates
# registry, so the existing Stop-hook completion audit enforces it. "Non-closable"
# stops being prose the moment the machinery that already exists is told about it.
# --------------------------------------------------------------------------- #

def test_declared_gate_entry_carries_the_fields_the_stop_hook_requires(eng: ModuleType) -> None:
    entry = eng.declared_gate_entry(_contract(), declared_at="2026-08-01T00:00:00Z")
    assert set(entry) == {"gate_id", "declaration_text", "check_command_or_artifact", "declared_at"}
    assert entry["gate_id"] == "cfp-retirement-statements-list"
    assert entry["declared_at"] == "2026-08-01T00:00:00Z"
    assert "gate --ledger" in entry["check_command_or_artifact"]
    assert "live" in entry["declaration_text"]


def test_declare_gate_appends_once_per_contract(eng: ModuleType, tmp_path: Path) -> None:
    reg = tmp_path / "declared-gates.json"
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")
    assert eng.main(["declare-gate", "--json", str(c), "--registry", str(reg)]) == 0
    assert eng.main(["declare-gate", "--json", str(c), "--registry", str(reg)]) == 0
    assert [e["gate_id"] for e in json.loads(reg.read_text(encoding="utf-8"))] == [
        "cfp-retirement-statements-list"]


def test_declare_gate_preserves_gates_other_disciplines_recorded(eng: ModuleType, tmp_path: Path) -> None:
    """The registry is shared run state — CFP appends to it, never owns it."""
    reg = tmp_path / "declared-gates.json"
    reg.write_text(json.dumps([{"gate_id": "playwright-suite", "declaration_text": "x",
                                "check_command_or_artifact": "y", "declared_at": "z"}]),
                   encoding="utf-8")
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")
    assert eng.main(["declare-gate", "--json", str(c), "--registry", str(reg)]) == 0
    assert [e["gate_id"] for e in json.loads(reg.read_text(encoding="utf-8"))] == [
        "playwright-suite", "cfp-retirement-statements-list"]


def test_satisfy_gate_records_the_evidence_and_refuses_what_it_cannot_verify(
        eng: ModuleType, tmp_path: Path) -> None:
    reg = tmp_path / "declared-gates.json"
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")
    eng.main(["declare-gate", "--json", str(c), "--registry", str(reg)])
    evidence = tmp_path / "gate-out.txt"
    evidence.write_text("0 blocking finding(s), 0 advisory.\n", encoding="utf-8")

    assert eng.main(["satisfy-gate", "--gate-id", "nope",
                     "--evidence", str(evidence), "--registry", str(reg)]) == 1
    assert eng.main(["satisfy-gate", "--gate-id", "cfp-retirement-statements-list",
                     "--evidence", str(tmp_path / "absent.txt"), "--registry", str(reg)]) == 1
    assert eng.main(["satisfy-gate", "--gate-id", "cfp-retirement-statements-list",
                     "--evidence", str(evidence), "--registry", str(reg)]) == 0
    entry = json.loads(reg.read_text(encoding="utf-8"))[0]
    assert entry["evidence_path"] == str(evidence) and entry["satisfied_at"]


def test_satisfy_gate_refuses_a_blank_capture(eng: ModuleType, tmp_path: Path) -> None:
    """The audit rejects a whitespace-only capture as 'the paper version of a
    check that never ran'; the writer refuses to produce one."""
    reg = tmp_path / "declared-gates.json"
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")
    eng.main(["declare-gate", "--json", str(c), "--registry", str(reg)])
    blank = tmp_path / "blank.txt"
    blank.write_text("   \n", encoding="utf-8")
    assert eng.main(["satisfy-gate", "--gate-id", "cfp-retirement-statements-list",
                     "--evidence", str(blank), "--registry", str(reg)]) == 1


def test_the_registered_gate_is_enforced_by_the_real_completion_audit(
        eng: ModuleType, tmp_path: Path) -> None:
    """Not a restatement of the hook's rules — the entry is run THROUGH the
    v3.47.0 Stop-hook arm, which blocks until it is satisfied with evidence."""
    audit = load_module(REPO_ROOT / "hooks" / "pipeline-completion-audit.py",
                        "pipeline_completion_audit_for_cfp")
    at = tmp_path / ".architect-team"
    at.mkdir()
    reg = at / "declared-gates.json"
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_contract()), encoding="utf-8")

    assert audit._audit_declared_gates(at) == [], "no registry yet — nothing declared"
    eng.main(["declare-gate", "--json", str(c), "--registry", str(reg)])
    violations = audit._audit_declared_gates(at)
    assert violations and "cfp-retirement-statements-list" in violations[0]

    evidence = at / "gate-out.txt"
    evidence.write_text("0 blocking finding(s), 0 advisory.\n", encoding="utf-8")
    eng.main(["satisfy-gate", "--gate-id", "cfp-retirement-statements-list",
              "--evidence", str(evidence), "--registry", str(reg)])
    assert audit._audit_declared_gates(at) == []


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


def test_skill_reconciles_the_provisioned_mock_with_the_fake_data_sweep() -> None:
    """The mock handler is PRODUCTION backend code, which `verify-no-fake-data`
    sweeps. The compatibility claim has to address that, and the categories it
    names have to be the verifier's real ones."""
    body = (REPO_ROOT / "skills" / "contract-first-parallelism" / "SKILL.md").read_text(encoding="utf-8")
    section = body.split("## Relationship to the no-fake-data disciplines", 1)[1]
    assert "verify-no-fake-data" in section
    fake_data = (REPO_ROOT / "hooks" / "vao" / "fake_data.py").read_text(encoding="utf-8")
    for category in ("placeholder-name", "lorem-ipsum", "placeholder-money"):
        assert category in section, f"the skill must name the {category!r} category the mock must avoid"
        assert f'("{category}"' in fake_data, f"{category!r} is not a real verify-no-fake-data category"


def test_skill_documents_the_exact_ledger_shape_it_reads() -> None:
    """The root cause of a silently-green gate was a hand-written file whose
    shape the skill never documented — so the agent invented one."""
    import re

    body = (REPO_ROOT / "skills" / "contract-first-parallelism" / "SKILL.md").read_text(encoding="utf-8")
    # Whitespace-normalized: the claim must hold, not its line wrapping.
    flat = re.sub(r"\s+", " ", body).lower()
    assert '"contracts"' in flat
    assert "fails closed" in flat


def test_the_retirement_gate_is_registered_not_merely_asserted() -> None:
    """`non-closable` is only true if some machinery knows about the gate."""
    skill = (REPO_ROOT / "skills" / "contract-first-parallelism" / "SKILL.md").read_text(encoding="utf-8")
    assert "declared-gates.json" in skill and "cfp-retirement-" in skill
    assert "declare-gate" in skill
    backend = (REPO_ROOT / "agents" / "backend.md").read_text(encoding="utf-8")
    assert "declare-gate" in backend


def test_architect_carries_the_approval_mode() -> None:
    body = (REPO_ROOT / "agents" / "system-architect.md").read_text(encoding="utf-8")
    assert "## Interface Contract Approval" in body
    assert "TEN distinct modes" in body
    section = body.split("## Interface Contract Approval", 1)[1]
    assert "interface_contract.py validate" in section
    assert "reuse" in section.lower()
    assert "binding" in section.lower() or "binds" in section.lower()
