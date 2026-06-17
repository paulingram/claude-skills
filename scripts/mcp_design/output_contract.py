# -*- coding: utf-8 -*-
"""Deterministic output-contract engine (MCP design agents — MCP-1 … MCP-3).

Stdlib-only, no import-time side effects. The deterministic half of the
**mcp-output-contract-design** discipline: when an application embeds an LLM
agent and asks it to PRODUCE something, the output must be guaranteed consistent
and standardized (MCP-3). The best-in-class technique (MCP-1) is an explicit
output CONTRACT — a closed JSON Schema + a structured-output tool the model is
forced to call + validation of every returned value against the schema.

This module:
- `build_output_contract(name, fields, ...)` — assemble a contract: a closed JSON
  Schema, the structured-output tool description, and the required-field list.
- `validate_against_contract(value, contract)` — validate a produced value against
  the contract (the runtime guarantee).
- `assess_contract(contract)` — score a contract for best-in-class completeness
  and emit advisory signals.

It is the machine; `skills/mcp-output-contract-design/SKILL.md` + the
`mcp-design-agent` are the contract + the LLM-judgment design workflow.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

# JSON Schema primitive types we support for an output-contract field.
FIELD_TYPES: tuple[str, ...] = (
    "string", "integer", "number", "boolean", "array", "object",
)

# Python-value -> JSON-Schema-type check. bool is checked BEFORE int because in
# Python `bool` is a subclass of `int` (so `isinstance(True, int)` is True).
def _json_type_ok(value: Any, json_type: str) -> bool:
    if json_type == "boolean":
        return isinstance(value, bool)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "array":
        return isinstance(value, (list, tuple))
    if json_type == "object":
        return isinstance(value, dict)
    return False


def build_output_contract(
    name: str,
    fields: Iterable[dict[str, Any]],
    *,
    required: Optional[Iterable[str]] = None,
    description: str = "",
) -> dict[str, Any]:
    """Assemble a best-in-class output contract (MCP-1/MCP-3).

    `fields` — `[{name, type, description?, enum?, items_type?}, ...]` (`type` in
    FIELD_TYPES). `required` — names that MUST appear (default: ALL fields, the
    strict best-practice default). Returns a contract with a CLOSED JSON Schema
    (`additionalProperties: false`) + the structured-output tool the model is
    forced to call.
    """
    fields = list(fields)
    props: dict[str, Any] = {}
    field_names: list[str] = []
    for f in fields:
        fname = f["name"]
        ftype = f["type"]
        if ftype not in FIELD_TYPES:
            raise ValueError(f"field {fname!r}: unsupported type {ftype!r} (allowed: {FIELD_TYPES})")
        prop: dict[str, Any] = {"type": ftype}
        if f.get("description"):
            prop["description"] = f["description"]
        if f.get("enum") is not None:
            enum_vals = list(f["enum"])
            # best-in-class: an enum's values must match the field's own type, else
            # the field is UNSATISFIABLE (no produced value can pass both the type
            # check and the enum check). Catch that footgun at build time.
            if ftype in ("string", "integer", "number", "boolean"):
                bad = [v for v in enum_vals if not _json_type_ok(v, ftype)]
                if bad:
                    raise ValueError(
                        f"field {fname!r}: enum values {bad} do not match field type {ftype!r}"
                    )
            prop["enum"] = enum_vals
        if ftype == "array" and f.get("items_type"):
            if f["items_type"] not in FIELD_TYPES:
                raise ValueError(f"field {fname!r}: unsupported items_type {f['items_type']!r}")
            prop["items"] = {"type": f["items_type"]}
        props[fname] = prop
        field_names.append(fname)

    req = list(required) if required is not None else list(field_names)
    unknown_required = [r for r in req if r not in field_names]
    if unknown_required:
        raise ValueError(f"required names not in fields: {unknown_required}")

    schema = {
        "type": "object",
        "properties": props,
        "required": req,
        "additionalProperties": False,  # CLOSED object — no surprise fields (MCP-3)
    }
    desc = description or f"Return a single {name} object matching the schema exactly."
    structured_output_tool = {
        "name": name,
        "description": desc,
        "input_schema": schema,
    }
    return {
        "schema": "mcp-output-contract/v1",
        "name": name,
        "description": desc,
        "json_schema": schema,
        "structured_output_tool": structured_output_tool,
        "required": req,
        "fields": field_names,
    }


def validate_against_contract(value: Any, contract: dict[str, Any]) -> dict[str, Any]:
    """Validate a produced `value` against a contract's JSON Schema (the runtime
    guarantee — MCP-3). Returns `{valid, errors}`. Minimal stdlib validation:
    object-ness, required presence, closed-object extras, per-field type + enum."""
    schema = contract.get("json_schema", contract)
    errors: list[str] = []
    if not isinstance(value, dict):
        return {"valid": False, "errors": ["value is not a JSON object"]}

    props = schema.get("properties", {})
    for r in schema.get("required", []):
        if r not in value:
            errors.append(f"missing required field: {r}")
    if schema.get("additionalProperties") is False:
        for k in value:
            if k not in props:
                errors.append(f"unexpected field not in contract: {k}")
    for k, v in value.items():
        prop = props.get(k)
        if not prop:
            continue
        jt = prop.get("type")
        if jt and not _json_type_ok(v, jt):
            errors.append(f"field {k!r}: expected {jt}, got {type(v).__name__}")
        enum = prop.get("enum")
        if enum is not None and v not in enum:
            errors.append(f"field {k!r}: value {v!r} not in enum {enum}")
        if jt == "array" and isinstance(v, (list, tuple)):
            it = (prop.get("items") or {}).get("type")
            if it:
                for i, item in enumerate(v):
                    if not _json_type_ok(item, it):
                        errors.append(f"field {k!r}[{i}]: expected {it}, got {type(item).__name__}")
    return {"valid": not errors, "errors": errors}


def assess_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Score a contract for best-in-class output-standardization completeness
    (MCP-1). Advisory signals: `no-fields`, `open-object` (additionalProperties
    not false), `nothing-required`, `fields-missing-description`,
    `no-structured-output-mechanism`."""
    schema = contract.get("json_schema", {})
    props = schema.get("properties", {})
    signals: list[dict[str, Any]] = []

    if not props:
        signals.append({"signal": "no-fields", "severity": "high",
                        "detail": "the contract defines no fields — nothing is standardized"})
    if schema.get("additionalProperties") is not False:
        signals.append({"signal": "open-object", "severity": "high",
                        "detail": "additionalProperties is not false — surprise fields are allowed (not closed)"})
    if not schema.get("required"):
        signals.append({"signal": "nothing-required", "severity": "medium",
                        "detail": "no required fields — the model may omit everything"})
    missing_desc = [k for k, p in props.items() if not p.get("description")]
    if missing_desc:
        signals.append({"signal": "fields-missing-description", "severity": "low",
                        "detail": f"fields without a description (the model needs them): {sorted(missing_desc)}"})
    if not contract.get("structured_output_tool"):
        signals.append({"signal": "no-structured-output-mechanism", "severity": "high",
                        "detail": "no structured-output tool — the model is not FORCED to return the shape"})

    return {
        "schema": "mcp-contract-assessment/v1",
        "is_standardized": not signals,
        "signals": signals,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: build / validate / assess an output contract.

    Usage:
      output_contract.py build --name <n> --field name:type[:desc] [--field ...] [--out f]
      output_contract.py validate --contract <file> --value <json-file>
      output_contract.py assess --contract <file>
    """
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="MCP output-contract engine (MCP-1…3).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build")
    pb.add_argument("--name", required=True)
    pb.add_argument("--field", action="append", default=[],
                    help="name:type[:description] (type in %s)" % (FIELD_TYPES,))
    pb.add_argument("--out", default=None)

    pv = sub.add_parser("validate")
    pv.add_argument("--contract", required=True)
    pv.add_argument("--value", required=True)

    pa = sub.add_parser("assess")
    pa.add_argument("--contract", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "build":
        fields = []
        for spec in args.field:
            parts = spec.split(":", 2)
            f = {"name": parts[0], "type": parts[1] if len(parts) > 1 else "string"}
            if len(parts) > 2:
                f["description"] = parts[2]
            fields.append(f)
        contract = build_output_contract(args.name, fields)
        out = json.dumps(contract, indent=2, sort_keys=True)
        if args.out:
            Path(args.out).write_text(out, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(out)
        return 0

    if args.cmd == "validate":
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
        value = json.loads(Path(args.value).read_text(encoding="utf-8"))
        result = validate_against_contract(value, contract)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["valid"] else 1

    # assess
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    result = assess_contract(contract)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["is_standardized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
