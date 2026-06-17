"""Tests for the v3.20.0 MCP output-contract engine (MCP-1 … MCP-3).

Covers the deterministic machine `scripts/mcp_design/output_contract.py`:
`build_output_contract` (closed JSON Schema + structured-output tool),
`validate_against_contract` (the runtime guarantee), `assess_contract` (best-in-class
completeness), the CLI, and the skill + agent contract surfaces.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "mcp_design" / "output_contract.py"

_spec = importlib.util.spec_from_file_location("output_contract", MODULE_PATH)
oc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oc)  # type: ignore[union-attr]


def _contract():
    return oc.build_output_contract(
        "extraction",
        [
            {"name": "title", "type": "string", "description": "the document title"},
            {"name": "pages", "type": "integer", "description": "page count"},
            {"name": "status", "type": "string", "description": "doc state",
             "enum": ["draft", "final"]},
            {"name": "tags", "type": "array", "description": "keywords", "items_type": "string"},
        ],
    )


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def test_build_produces_closed_schema_and_tool() -> None:
    c = _contract()
    schema = c["json_schema"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False  # closed (MCP-3)
    assert set(schema["required"]) == {"title", "pages", "status", "tags"}  # all required by default
    assert c["structured_output_tool"]["input_schema"] is schema  # the forced mechanism
    assert schema["properties"]["status"]["enum"] == ["draft", "final"]
    assert schema["properties"]["tags"]["items"] == {"type": "string"}


def test_build_rejects_bad_type() -> None:
    with pytest.raises(ValueError):
        oc.build_output_contract("x", [{"name": "a", "type": "datetime"}])


def test_build_rejects_enum_type_mismatch() -> None:
    # an enum whose values don't match the field type is unsatisfiable -> rejected
    with pytest.raises(ValueError):
        oc.build_output_contract("x", [{"name": "a", "type": "string", "enum": [1, 2, 3]}])


def test_build_empty_fields_is_valid_if_useless() -> None:
    c = oc.build_output_contract("empty", [])
    assert c["json_schema"]["properties"] == {}
    assert c["json_schema"]["additionalProperties"] is False
    assert oc.validate_against_contract({}, c)["valid"] is True
    assert oc.validate_against_contract({"x": 1}, c)["valid"] is False  # closed


def test_build_explicit_required_subset() -> None:
    c = oc.build_output_contract(
        "x", [{"name": "a", "type": "string"}, {"name": "b", "type": "string"}],
        required=["a"],
    )
    assert c["json_schema"]["required"] == ["a"]
    with pytest.raises(ValueError):
        oc.build_output_contract("x", [{"name": "a", "type": "string"}], required=["nope"])


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #

def test_validate_accepts_a_good_value() -> None:
    c = _contract()
    v = {"title": "Doc", "pages": 3, "status": "final", "tags": ["x", "y"]}
    assert oc.validate_against_contract(v, c) == {"valid": True, "errors": []}


def test_validate_flags_missing_required_and_extra() -> None:
    c = _contract()
    r = oc.validate_against_contract({"title": "Doc", "pages": 1, "status": "final",
                                      "tags": [], "surprise": 1}, c)
    assert r["valid"] is False
    assert any("unexpected field" in e for e in r["errors"])  # closed object


def test_validate_flags_wrong_type_and_bool_is_not_integer() -> None:
    c = _contract()
    r = oc.validate_against_contract({"title": "Doc", "pages": True, "status": "final", "tags": []}, c)
    # bool must NOT satisfy integer (Python bool is an int subclass — the engine guards it)
    assert r["valid"] is False
    assert any("pages" in e and "integer" in e for e in r["errors"])


def test_validate_flags_enum_and_array_item_type() -> None:
    c = _contract()
    r = oc.validate_against_contract({"title": "D", "pages": 1, "status": "bogus", "tags": [1]}, c)
    assert r["valid"] is False
    assert any("status" in e and "enum" in e for e in r["errors"])
    assert any("tags" in e and "[0]" in e for e in r["errors"])


def test_validate_non_object() -> None:
    assert oc.validate_against_contract("not an object", _contract())["valid"] is False


def test_number_accepts_int_rejects_bool() -> None:
    c = oc.build_output_contract("m", [{"name": "score", "type": "number", "description": "0..1"}])
    assert oc.validate_against_contract({"score": 1}, c)["valid"] is True     # int satisfies number
    assert oc.validate_against_contract({"score": 0.5}, c)["valid"] is True   # float too
    assert oc.validate_against_contract({"score": True}, c)["valid"] is False  # bool does NOT


def test_object_field_does_not_recurse_documented_limit() -> None:
    # the engine does NOT validate nested-object schemas (disclaimed in the skill)
    c = oc.build_output_contract("m", [{"name": "meta", "type": "object", "description": "blob"}])
    assert oc.validate_against_contract({"meta": {"anything": [1, 2]}}, c)["valid"] is True
    assert oc.validate_against_contract({"meta": "not-an-object"}, c)["valid"] is False


# --------------------------------------------------------------------------- #
# assess
# --------------------------------------------------------------------------- #

def test_assess_good_contract_is_standardized() -> None:
    assert oc.assess_contract(_contract())["is_standardized"] is True


def test_assess_flags_open_object_and_no_required() -> None:
    bad = {
        "json_schema": {"type": "object", "properties": {"a": {"type": "string"}},
                        "required": [], "additionalProperties": True},
        # no structured_output_tool
    }
    sigs = {s["signal"] for s in oc.assess_contract(bad)["signals"]}
    assert "open-object" in sigs
    assert "nothing-required" in sigs
    assert "no-structured-output-mechanism" in sigs


def test_assess_flags_missing_descriptions() -> None:
    c = oc.build_output_contract("x", [{"name": "a", "type": "string"}])  # no description
    sigs = {s["signal"] for s in oc.assess_contract(c)["signals"]}
    assert "fields-missing-description" in sigs


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_build_validate_assess(tmp_path: Path) -> None:
    cfile = tmp_path / "c.json"
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "build", "--name", "rec",
         "--field", "title:string:the title", "--field", "n:integer:a count",
         "--out", str(cfile)],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0 and cfile.exists()
    # assess the built contract
    res2 = subprocess.run(
        [sys.executable, str(MODULE_PATH), "assess", "--contract", str(cfile)],
        capture_output=True, text=True, timeout=60,
    )
    assert res2.returncode == 0  # built contract is standardized
    # validate a good value
    vfile = tmp_path / "v.json"
    vfile.write_text(json.dumps({"title": "t", "n": 2}), encoding="utf-8")
    res3 = subprocess.run(
        [sys.executable, str(MODULE_PATH), "validate", "--contract", str(cfile), "--value", str(vfile)],
        capture_output=True, text=True, timeout=60,
    )
    assert res3.returncode == 0
    # validate a bad value -> exit 1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"title": "t"}), encoding="utf-8")  # missing required n
    res4 = subprocess.run(
        [sys.executable, str(MODULE_PATH), "validate", "--contract", str(cfile), "--value", str(bad)],
        capture_output=True, text=True, timeout=60,
    )
    assert res4.returncode == 1


# --------------------------------------------------------------------------- #
# surfaces
# --------------------------------------------------------------------------- #

def test_skill_present_and_documents_mcp() -> None:
    body = (REPO_ROOT / "skills" / "mcp-output-contract-design" / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "output_contract.py" in body
    for tag in ("MCP-1", "MCP-2", "MCP-3"):
        assert tag in body
    assert "additionalProperties" in body  # the closed-schema best practice
    assert "verified-agent-output" in body  # reuse boundary


def test_agent_present() -> None:
    body = (REPO_ROOT / "agents" / "mcp-design-agent.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "output_contract.py" in body
    low = body.lower()
    assert "bounded" in low and ".architect-team/mcp-design" in body
