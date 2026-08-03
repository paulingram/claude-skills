"""Tests for the knowledge server's closed output contracts (KS-6) —
services/knowledge_server/contracts.py.

Each tool's response shape is a CLOSED contract built with
`scripts/mcp_design/output_contract.py::build_output_contract` and every emitted
response validates with `validate_against_contract`. The falsifiability guard
(the whole point of KS-6) proves a malformed response FAILS validation.
"""
from __future__ import annotations

from pathlib import Path

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]

co = load_module(REPO_ROOT / "services" / "knowledge_server" / "contracts.py", "ct6_ks_contracts")

EXPECTED_TOOLS = {
    "search_dictionary", "get_table_details", "find_relations", "get_dictionary_status",
    "search_map", "get_route_details", "find_call_paths", "get_map_status",
}


def _dummy_from_schema(schema: dict) -> dict:
    """A minimal TYPE-VALID payload for a closed contract schema — one value per
    property matching its declared JSON type (contracts carry no top-level enums)."""
    by_type = {"string": "x", "integer": 0, "number": 0.0, "boolean": False,
               "array": [], "object": {}}
    return {name: by_type[prop["type"]] for name, prop in schema["properties"].items()}


def test_every_tool_has_a_closed_contract_requiring_freshness() -> None:
    contracts = co.tool_contracts()
    assert set(contracts) == EXPECTED_TOOLS
    for name, contract in contracts.items():
        schema = contract["json_schema"]
        assert schema["additionalProperties"] is False, f"{name} contract is not closed"
        assert "freshness" in schema["properties"], f"{name} missing freshness field"
        assert "freshness" in schema["required"], f"{name} does not require freshness"
        # eats CT6's own dog food: the structured-output tool mechanism is present
        assert contract["structured_output_tool"]["input_schema"] is schema


def test_wellformed_payload_validates_for_every_tool() -> None:
    for name, contract in co.tool_contracts().items():
        payload = _dummy_from_schema(contract["json_schema"])
        result = co.validate_payload(payload, contract)
        assert result["valid"] is True, f"{name}: {result['errors']}"


def test_malformed_response_fails_validation_falsifiable() -> None:
    # KS-6: the check MUST be able to go red — prove each failure mode fails.
    contract = co.tool_contracts()["search_map"]
    good = _dummy_from_schema(contract["json_schema"])
    assert co.validate_payload(good, contract)["valid"] is True

    missing_freshness = {k: v for k, v in good.items() if k != "freshness"}
    assert co.validate_payload(missing_freshness, contract)["valid"] is False

    extra_field = {**good, "surprise": 1}  # closed object rejects surprise fields
    assert co.validate_payload(extra_field, contract)["valid"] is False

    wrong_type = {**good, "freshness": "not-an-object"}
    assert co.validate_payload(wrong_type, contract)["valid"] is False
