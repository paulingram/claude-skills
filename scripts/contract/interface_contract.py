# -*- coding: utf-8 -*-
"""Deterministic interface-contract engine (v3.48.0) — the machine under the
`contract-first-parallelism` skill.

THE PROBLEM IT SOLVES. When a run needs backend surfaces AND a frontend that
visualizes them, the pre-v3.48.0 flow SERIALIZED: the frontend hit a missing
API, authored an SR, PAUSED that element, waited a full backend round trip,
then wired. The frontend sat blocked on backend build time it did not need to
wait for.

THE APPROACH. Both sides co-design the inbound surface FIRST, the architect
approves it, and the backend IMMEDIATELY provisions the endpoint AT ITS REAL
PATH serving a contract-conforming mock payload. The frontend then integrates
against a LIVE endpoint — real HTTP, real serialization, real error paths —
while the backend replaces the mock internals underneath. Neither waits.

WHY THIS IS NOT "FAKE DATA". The mock lives SERVER-SIDE behind the real
endpoint; the frontend carries no fixture, no `page.route` intercept, no
hardcoded shape. That is strictly MORE live-wired than the alternative. The
safety property is this engine's job: every provisioned mock is a TRACKED,
TEMPORARY scaffold recorded in a ledger, and `retirement_gate` makes a run
with any still-mock-serving surface non-closable. The abstraction buys
parallelism; the ledger guarantees it is repaid.

The engine:

* ``validate_contract(contract)``  — the approval gate: identity, both parties,
  the response shape with a type per field, the error states, and (for the
  amend shape) the named new attributes.
* ``build_contract_doc(contract)`` — the human-readable contract artifact.
* ``transition(entry, to_state)``  — the ledger state machine, forward-only:
  ``proposed -> approved -> mock-serving -> live``.
* ``retirement_gate(ledger)``      — THE GATE: every entry must have reached
  ``live``; anything still ``mock-serving`` (or earlier) blocks the close-out.
* ``contract_drift(contract, observed)`` — what the surface actually returns
  vs what was approved (missing fields, type mismatches, undeclared extras).

HONEST BOUNDARY: this engine never performs HTTP. `observed` payloads are
supplied by the caller (the agent that actually hit the live endpoint), the
same injected-observation convention as the rest of the deterministic tier —
the engine adjudicates shape, it does not witness it. Stdlib-only; no
import-time side effects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "interface-contract/v1"

# The two shapes the protocol covers. `new-surface` provisions an endpoint that
# does not exist; `amend-surface` adds attributes to one that does — the same
# protocol, because the frontend is equally blocked either way.
CONTRACT_SHAPES = ("new-surface", "amend-surface")

# The ledger state machine. FORWARD-ONLY: a surface never un-approves, and a
# live surface never silently reverts to serving a mock.
CONTRACT_STATES = ("proposed", "approved", "mock-serving", "live")
_STATE_ORDER = {state: i for i, state in enumerate(CONTRACT_STATES)}

# The terminal state. `live` means: the mock payload is GONE and the surface
# returns real data from the real source, verified end-to-end.
TERMINAL_STATE = "live"

# States that still owe work at close-out — the retirement gate's blockers.
UNRETIRED_STATES = ("proposed", "approved", "mock-serving")

# A field declaration needs a type; these are the recognized ones. `any` is
# permitted but flagged as an advisory — an unshaped field is a contract the
# frontend cannot actually build against.
FIELD_TYPES = ("string", "number", "integer", "boolean", "object", "array", "null", "any")

REQUIRED_CONTRACT_FIELDS = ("contract_id", "shape", "method", "path", "consumer", "owner",
                            "response_fields", "error_states")

_HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _err(kind: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "severity": "error", "detail": detail}


def _advise(kind: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "severity": "advisory", "detail": detail}


def errors_only(findings: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """The blocking subset of any findings list."""
    return [f for f in findings if f.get("severity") == "error"]


# --------------------------------------------------------------------------- #
# CFP-2/3 — the contract itself
# --------------------------------------------------------------------------- #

def validate_contract(contract: Dict[str, Any]) -> List[Dict[str, str]]:
    """The approval gate. Zero error-severity findings means the architect may
    approve and the backend may provision.

    The bar is "can the frontend build a finished interface against this
    without asking another question" — so a field without a type, or a surface
    without its error states, is a blocker, not a nit."""
    findings: List[Dict[str, str]] = []

    for field in REQUIRED_CONTRACT_FIELDS:
        if _is_blank(contract.get(field)) and not isinstance(contract.get(field), (list, dict)):
            findings.append(_err("missing-field", f"required contract field {field!r} is missing or blank"))

    shape = contract.get("shape")
    if shape and shape not in CONTRACT_SHAPES:
        findings.append(_err("unknown-shape", f"shape {shape!r} not in {CONTRACT_SHAPES}"))

    method = contract.get("method")
    if method and method not in _HTTP_METHODS:
        findings.append(_err("unknown-method", f"method {method!r} not in {_HTTP_METHODS}"))

    path = contract.get("path")
    if isinstance(path, str) and path and not path.startswith("/"):
        findings.append(_err("path-not-rooted", f"path {path!r} must start with '/' (the REAL path the "
                                                "frontend will call — the mock is served AT it, never beside it)"))

    fields = contract.get("response_fields")
    if not isinstance(fields, list) or not fields:
        if fields is not None:
            findings.append(_err("no-response-fields", "the contract must declare the response shape — "
                                 "the frontend cannot render an unshaped payload"))
    else:
        seen = set()
        for i, f in enumerate(fields, 1):
            if not isinstance(f, dict):
                findings.append(_err("malformed-response-field", f"response field {i} is not a mapping"))
                continue
            name = f.get("name")
            if _is_blank(name):
                findings.append(_err("response-field-unnamed", f"response field {i} has no name"))
            elif name in seen:
                findings.append(_err("response-field-duplicated", f"response field {name!r} declared twice"))
            else:
                seen.add(name)
            ftype = f.get("type")
            if _is_blank(ftype):
                findings.append(_err("response-field-untyped",
                                     f"response field {name or i!r} has no type — the frontend cannot "
                                     "build against an untyped field"))
            elif ftype not in FIELD_TYPES:
                findings.append(_err("response-field-bad-type",
                                     f"response field {name or i!r} type {ftype!r} not in {FIELD_TYPES}"))
            elif ftype == "any":
                findings.append(_advise("response-field-type-any",
                                        f"response field {name or i!r} is typed 'any' — it will not "
                                        "constrain the mock or the drift check"))

    errors = contract.get("error_states")
    if not isinstance(errors, list) or not errors:
        if errors is not None:
            findings.append(_err("no-error-states", "the contract must declare its error states — the "
                                 "frontend builds the error paths in the same pass as the happy path"))

    if shape == "amend-surface":
        added = contract.get("added_fields")
        if not isinstance(added, list) or not added:
            findings.append(_err("amend-without-added-fields",
                                 "an amend-surface contract must name the NEW attributes it adds"))
        else:
            declared = {f.get("name") for f in fields if isinstance(f, dict)} if isinstance(fields, list) else set()
            for name in added:
                if name not in declared:
                    findings.append(_err("added-field-not-in-response-shape",
                                         f"added attribute {name!r} is not present in response_fields"))

    return findings


def build_contract_doc(contract: Dict[str, Any]) -> str:
    """The human-readable contract artifact — what the architect approves and
    both agents build against."""
    lines: List[str] = []
    cid = contract.get("contract_id", "contract")
    lines.append(f"# Interface contract — {cid}")
    lines.append("")
    lines.append(f"- Shape: {contract.get('shape', '')}")
    lines.append(f"- Surface: `{contract.get('method', '')} {contract.get('path', '')}`")
    lines.append(f"- Consumer (frontend): {contract.get('consumer', '')}")
    lines.append(f"- Owner (backend): {contract.get('owner', '')}")
    lines.append(f"- State: {contract.get('state', 'proposed')}")
    if contract.get("approved_by"):
        lines.append(f"- Approved by: {contract['approved_by']}")
    lines.append("")
    if contract.get("purpose"):
        lines.append("## What the frontend renders with this")
        lines.append("")
        lines.append(str(contract["purpose"]).strip())
        lines.append("")
    lines.append("## Response shape")
    lines.append("")
    lines.append("| Field | Type | Meaning | New |")
    lines.append("|---|---|---|---|")
    added = set(contract.get("added_fields") or [])
    for f in contract.get("response_fields") or []:
        name = f.get("name", "")
        lines.append(
            f"| {name} | {f.get('type', '')} | {f.get('meaning', '')} | "
            f"{'yes' if name in added else ''} |"
        )
    lines.append("")
    lines.append("## Error states")
    lines.append("")
    for e in contract.get("error_states") or []:
        if isinstance(e, dict):
            lines.append(f"- `{e.get('status', '')}` — {e.get('meaning', '')}")
        else:
            lines.append(f"- {e}")
    lines.append("")
    lines.append("## Mock retirement")
    lines.append("")
    lines.append(
        "The mock payload served at this path is a TEMPORARY scaffold. This "
        "contract is not satisfied until the surface reaches state `live` — real "
        "data from the real source, verified end-to-end through this same path. "
        "The run cannot close while it is still `mock-serving`."
    )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CFP-4/5/6 — the ledger + the retirement gate
# --------------------------------------------------------------------------- #

def transition(entry: Dict[str, Any], to_state: str) -> Dict[str, Any]:
    """Advance a ledger entry. FORWARD-ONLY — returns a NEW dict; raises
    ``ValueError`` on an unknown or backward transition (a live surface must
    never silently fall back to serving its mock)."""
    if to_state not in CONTRACT_STATES:
        raise ValueError(f"unknown state {to_state!r} (valid: {CONTRACT_STATES})")
    current = entry.get("state", "proposed")
    if current not in CONTRACT_STATES:
        raise ValueError(f"entry carries unknown state {current!r}")
    if _STATE_ORDER[to_state] < _STATE_ORDER[current]:
        raise ValueError(
            f"backward transition {current!r} -> {to_state!r} refused: a provisioned "
            "surface only moves forward (re-mocking a live surface is a regression, "
            "not a state change)"
        )
    out = dict(entry)
    out["state"] = to_state
    return out


def unretired_mocks(ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every ledger entry that has NOT reached ``live`` — the outstanding debt
    the parallelism was borrowed against."""
    return [e for e in (ledger or []) if e.get("state", "proposed") in UNRETIRED_STATES]


def retirement_gate(ledger: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """THE close-out gate. Any surface still short of ``live`` is an error-severity
    blocker: the run borrowed parallelism against a mock and has not repaid it.

    A `live` entry that never recorded its verification is an advisory — the
    engine cannot witness the endpoint, so it points rather than pretends."""
    findings: List[Dict[str, str]] = []
    for entry in ledger or []:
        state = entry.get("state", "proposed")
        cid = entry.get("contract_id", "<unnamed>")
        surface = f"{entry.get('method', '')} {entry.get('path', '')}".strip()
        if state in UNRETIRED_STATES:
            findings.append(_err(
                "mock-not-retired",
                f"contract {cid!r} ({surface}) is still {state!r} — the surface has not "
                "reached 'live'. The run cannot close while a provisioned mock is still "
                "serving synthetic data to the frontend."
            ))
        elif state == TERMINAL_STATE and _is_blank(entry.get("verified_by")):
            findings.append(_advise(
                "retirement-unverified",
                f"contract {cid!r} ({surface}) is marked live but records no verified_by "
                "evidence (the end-to-end check that saw real data through this path)."
            ))
    return findings


def ledger_summary(ledger: List[Dict[str, Any]]) -> Dict[str, int]:
    """``{state: count}`` across the ledger, every state key present."""
    summary = {state: 0 for state in CONTRACT_STATES}
    for entry in ledger or []:
        state = entry.get("state", "proposed")
        if state in summary:
            summary[state] += 1
    return summary


def contract_drift(contract: Dict[str, Any], observed: Dict[str, Any]) -> List[Dict[str, str]]:
    """What the surface ACTUALLY returns vs what was approved.

    ``observed`` is a payload the caller obtained by hitting the live endpoint
    (the engine performs no HTTP — see the module honest boundary). Missing or
    type-mismatched declared fields are errors; undeclared extras are advisories
    (additive drift breaks nobody, but the contract should say so)."""
    findings: List[Dict[str, str]] = []
    declared = {f.get("name"): f.get("type") for f in (contract.get("response_fields") or [])
                if isinstance(f, dict) and f.get("name")}
    for name, ftype in declared.items():
        if name not in (observed or {}):
            findings.append(_err("contract-field-missing",
                                 f"approved field {name!r} is absent from the observed payload"))
            continue
        if ftype in (None, "any"):
            continue
        if not _type_matches(observed[name], ftype):
            findings.append(_err(
                "contract-field-type-mismatch",
                f"field {name!r} was approved as {ftype!r} but the payload carries "
                f"{_json_type(observed[name])!r}"
            ))
    for name in (observed or {}):
        if name not in declared:
            findings.append(_advise("undeclared-field",
                                    f"the payload carries {name!r}, which the contract does not declare"))
    return findings


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _type_matches(value: Any, declared: str) -> bool:
    actual = _json_type(value)
    if actual == declared:
        return True
    # An integer satisfies `number`; nothing else widens.
    return declared == "number" and actual == "integer"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _report(findings: List[Dict[str, str]]) -> int:
    for f in findings:
        print(f"[{f['severity']:8s}] {f['kind']}: {f['detail']}")
    blocking = errors_only(findings)
    print(f"{len(blocking)} blocking finding(s), {len(findings) - len(blocking)} advisory.")
    return 1 if blocking else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Interface contracts + the mock-retirement gate (contract-first parallelism)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Approval gate over one contract JSON.")
    v.add_argument("--json", required=True)

    d = sub.add_parser("doc", help="Render the contract artifact.")
    d.add_argument("--json", required=True)
    d.add_argument("--out", default=None)

    g = sub.add_parser("gate", help="Close-out retirement gate over the ledger JSON.")
    g.add_argument("--ledger", required=True)

    dr = sub.add_parser("drift", help="Approved contract vs an observed payload.")
    dr.add_argument("--json", required=True)
    dr.add_argument("--observed", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "validate":
        return _report(validate_contract(_load(args.json)))

    if args.cmd == "gate":
        ledger = _load(args.ledger)
        if isinstance(ledger, dict):
            ledger = ledger.get("contracts", [])
        summary = ledger_summary(ledger)
        print("ledger: " + ", ".join(f"{k}={v}" for k, v in summary.items()))
        return _report(retirement_gate(ledger))

    if args.cmd == "drift":
        return _report(contract_drift(_load(args.json), _load(args.observed)))

    doc = build_contract_doc(_load(args.json))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(doc, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
