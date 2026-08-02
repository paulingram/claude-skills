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
  the response shape with a type per field (nested element shapes included),
  the error states, and (for the amend shape) the named new attributes.
* ``build_contract_doc(contract)`` — the human-readable contract artifact.
* ``transition(entry, to_state)``  — the ledger state machine, forward-only:
  ``proposed -> approved -> mock-serving -> live``.
* ``normalize_ledger(payload)``    — the ledger CONTAINER check: a bare array,
  or an object wrapping it under ``contracts``. Nothing else.
* ``retirement_gate(ledger)``      — THE GATE: every entry must have reached
  ``live``; anything still ``mock-serving`` (or earlier) blocks the close-out.
* ``contract_drift(contract, observed, retirement=)`` — what the surface
  actually returns vs what was approved (missing fields, type mismatches,
  undeclared extras); in ``retirement`` mode the provisional marker is a
  blocker rather than an advisory.
* ``declared_gate_entry`` / ``declare_gate`` / ``satisfy_gate`` — registration
  of the retirement gate in the run's declared-gates registry, so the EXISTING
  Stop-hook completion audit is what makes the run non-closable. A gate that
  lives only in prose is a gate nothing enforces.

FAIL CLOSED ON THE LEDGER. The ledger is hand-written JSON: no writer API
guards it and no schema validator precedes it. So every arm that reads it
treats what it does not recognize as a BLOCKER, never as an absence — an
unknown state, a malformed entry, and an unrecognized container shape each
stop the close-out with a named reason. The polarity matters: a gate that goes
green on input it could not parse is worse than no gate, because it also
reports the all-clear.

HONEST BOUNDARY: this engine never performs HTTP. `observed` payloads are
supplied by the caller (the agent that actually hit the live endpoint), the
same injected-observation convention as the rest of the deterministic tier —
the engine adjudicates shape, it does not witness it. Stdlib-only; no
import-time side effects.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

# The summary bucket for a state the engine does not recognize. Present in every
# summary so the counts always sum to the ledger: an entry that vanishes from the
# operator's one visibility line is the evidence hiding itself.
UNKNOWN_STATE_BUCKET = "unknown"

# The only container the ledger file may use besides a bare JSON array.
LEDGER_WRAPPER_KEY = "contracts"

# A field declaration needs a type; these are the recognized ones. `any` is
# permitted but flagged as an advisory — an unshaped field is a contract the
# frontend cannot actually build against.
FIELD_TYPES = ("string", "number", "integer", "boolean", "object", "array", "null", "any")

# Nested shape declarations. An `array` field may declare the shape of its
# ELEMENTS under `items`; an `object` field may declare its MEMBERS under
# `fields`. Both take the same list-of-declarations form as `response_fields`,
# so the contract binds all the way down rather than stopping at the top level.
ARRAY_ITEMS_KEY = "items"
OBJECT_FIELDS_KEY = "fields"

REQUIRED_CONTRACT_FIELDS = ("contract_id", "shape", "method", "path", "consumer", "owner",
                            "response_fields", "error_states")

# The envelope key a provisioned mock carries so the retirement drift check can
# SEE that the surface is still serving its scaffold. A contract may name its
# own via `provisional_marker`.
DEFAULT_PROVISIONAL_MARKER = "_mock"

# The declared-gates registry this engine appends to, and the gate_id prefix it
# owns there (one gate per contract, so a gate names the debt it guards).
DECLARED_GATES_FILENAME = "declared-gates.json"
RETIREMENT_GATE_ID_PREFIX = "cfp-retirement-"

_HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _as_list(value: Any) -> List[Any]:
    """A list-shaped contract section, or an empty one. `or []` is not enough: a
    scalar where a list belongs is not falsy, and iterating it raises. Refusing
    such a contract is `validate_contract`'s job — the renderer's job is to show
    no rows for a section it cannot read."""
    return value if isinstance(value, list) else []


def _is_usable_name(value: Any) -> bool:
    """A field name must be a non-blank STRING — it becomes a payload key and is
    used as a dict/set key throughout. Anything else is unaddressable, and the
    unhashable ones would raise rather than report."""
    return isinstance(value, str) and bool(value.strip())


def _err(kind: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "severity": "error", "detail": detail}


def _advise(kind: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "severity": "advisory", "detail": detail}


def errors_only(findings: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """The blocking subset of any findings list."""
    return [f for f in findings if f.get("severity") == "error"]


def provisional_marker(contract: Dict[str, Any]) -> str:
    """The envelope key that marks this surface's payload as still provisional.

    Defaults to ``_mock``; a project with its own convention names it on the
    contract. Configuring one REPLACES the default — a payload is provisional in
    exactly one documented way, not two."""
    declared = contract.get("provisional_marker")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    return DEFAULT_PROVISIONAL_MARKER


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        _validate_field_list(fields, findings, marker=provisional_marker(contract))

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
            declared = ({f["name"] for f in fields if isinstance(f, dict) and _is_usable_name(f.get("name"))}
                        if isinstance(fields, list) else set())
            for name in added:
                if not _is_usable_name(name) or name not in declared:
                    findings.append(_err("added-field-not-in-response-shape",
                                         f"added attribute {name!r} is not present in response_fields"))

    return findings


def _flatten_fields(fields: List[Any], prefix: str = "") -> List[Tuple[str, Dict[str, Any]]]:
    """``(payload path, declaration)`` for every declared field, nested ones
    included — so the rendered artifact shows the shape the frontend consumes
    rather than stopping at the container."""
    rows: List[Tuple[str, Dict[str, Any]]] = []
    for f in fields:
        if not isinstance(f, dict):
            continue
        label = f"{prefix}{f.get('name', '')}"
        rows.append((label, f))
        ftype = f.get("type")
        nested_key = ARRAY_ITEMS_KEY if ftype == "array" else OBJECT_FIELDS_KEY if ftype == "object" else None
        nested = f.get(nested_key) if nested_key else None
        if isinstance(nested, list):
            rows.extend(_flatten_fields(nested, f"{label}[]." if ftype == "array" else f"{label}."))
    return rows


def _validate_field_list(fields: List[Any], findings: List[Dict[str, str]],
                         marker: str, prefix: str = "") -> None:
    """Validate one list of field declarations, recursing into declared element
    and member shapes. ``prefix`` names the position in the payload the
    declarations describe (``items[].`` / ``meta.``), so a nested finding points
    at the field the frontend would actually consume."""
    seen = set()
    for i, f in enumerate(fields, 1):
        if not isinstance(f, dict):
            findings.append(_err("malformed-response-field", f"response field {prefix}{i} is not a mapping"))
            continue
        # A name is only usable if it is a non-blank STRING: it becomes a payload
        # key, and everything downstream (duplicate detection, the drift lookup,
        # the added_fields cross-check) addresses the field by it. Hashing an
        # object or array here raises TypeError, and a traceback out of the
        # approval gate blocks nothing and explains nothing.
        name = f.get("name") if _is_usable_name(f.get("name")) else None
        label = f"{prefix}{name}" if name is not None else f"{prefix}{i}"
        if name is None:
            findings.append(_err(
                "response-field-unnamed",
                f"response field {prefix}{i} has no usable name — a name must be a non-empty "
                f"string, and this one is a JSON {_json_type(f.get('name'))}"))
        elif name in seen:
            findings.append(_err("response-field-duplicated", f"response field {label!r} declared twice"))
        else:
            seen.add(name)
        if name == marker:
            findings.append(_err(
                "provisional-marker-declared-as-field",
                f"response field {label!r} is the contract's provisional marker — declaring it as "
                "part of the approved shape would make the mock envelope permanently legitimate, "
                "and the retirement check could never fire"))

        ftype = f.get("type")
        if _is_blank(ftype):
            findings.append(_err("response-field-untyped",
                                 f"response field {label!r} has no type — the frontend cannot "
                                 "build against an untyped field"))
            continue
        if ftype not in FIELD_TYPES:
            findings.append(_err("response-field-bad-type",
                                 f"response field {label!r} type {ftype!r} not in {FIELD_TYPES}"))
            continue
        if ftype == "any":
            findings.append(_advise("response-field-type-any",
                                    f"response field {label!r} is typed 'any' — it will not "
                                    "constrain the mock or the drift check"))
            continue

        # A container binds its contents only if it declares them. Declared =>
        # recurse; undeclared => advisory, so the remaining gap is at least
        # visible to the architect at approval time.
        nested_key = ARRAY_ITEMS_KEY if ftype == "array" else OBJECT_FIELDS_KEY if ftype == "object" else None
        if nested_key is None:
            continue
        nested = f.get(nested_key)
        if nested is None:
            findings.append(_advise(
                "response-field-unshaped-container",
                f"response field {label!r} is typed {ftype!r} but declares no {nested_key!r} shape — "
                f"the contract does not constrain what it contains, so the frontend is building "
                f"against a promise about the container only"))
        elif not isinstance(nested, list) or not nested:
            findings.append(_err(
                "malformed-nested-shape",
                f"response field {label!r} declares {nested_key!r} as "
                f"{_json_type(nested)!r} — it must be a non-empty list of field declarations, "
                f"the same shape as response_fields"))
        else:
            child_prefix = f"{label}[]." if ftype == "array" else f"{label}."
            _validate_field_list(nested, findings, marker, child_prefix)


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
    added = {n for n in _as_list(contract.get("added_fields")) if _is_usable_name(n)}
    for name, f in _flatten_fields(_as_list(contract.get("response_fields"))):
        lines.append(
            f"| {name} | {f.get('type', '')} | {f.get('meaning', '')} | "
            f"{'yes' if name in added else ''} |"
        )
    lines.append("")
    lines.append("## Error states")
    lines.append("")
    for e in _as_list(contract.get("error_states")):
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


def normalize_ledger(payload: Any) -> Tuple[List[Any], List[Dict[str, str]]]:
    """``(entries, findings)`` for a loaded ledger document.

    The ledger's CONTAINER is checked as strictly as its entries, because the
    file is hand-written and the engine ships no writer for it: a bare JSON
    array, or an object wrapping that array under ``contracts``. Anything else
    is an error finding — an unrecognized wrapper is not an empty ledger, it is
    a ledger the engine could not read, and reporting those two the same way is
    what lets an unretired mock pass as a clean run."""
    if isinstance(payload, list):
        return payload, []
    if isinstance(payload, dict):
        if LEDGER_WRAPPER_KEY not in payload:
            return [], [_err(
                "unrecognized-ledger-shape",
                f"the ledger object declares {sorted(str(k) for k in payload)!r} but none of them is "
                f"{LEDGER_WRAPPER_KEY!r}. The ledger is either a JSON array of entries or an object "
                f"wrapping that array under {LEDGER_WRAPPER_KEY!r}; an unrecognized wrapper reads as "
                f"zero entries, which is indistinguishable from a clean run, so it blocks instead.")]
        entries = payload[LEDGER_WRAPPER_KEY]
        if not isinstance(entries, list):
            return [], [_err(
                "malformed-ledger",
                f"ledger key {LEDGER_WRAPPER_KEY!r} carries {_json_type(entries)!r}, not an array "
                f"of entries")]
        return entries, []
    return [], [_err(
        "unrecognized-ledger-shape",
        f"the ledger document is a JSON {_json_type(payload)} — expected an array of entries, or "
        f"an object wrapping that array under {LEDGER_WRAPPER_KEY!r}")]


def unretired_mocks(ledger: List[Dict[str, Any]]) -> List[Any]:
    """Every ledger entry that has NOT reached ``live`` — the outstanding debt
    the parallelism was borrowed against.

    An entry whose state the engine does not recognize counts as debt, and a
    malformed entry is returned as-is: an entry that cannot be read is never
    evidence that its mock was retired."""
    return [e for e in _as_list(ledger)
            if not isinstance(e, dict) or e.get("state", "proposed") != TERMINAL_STATE]


def retirement_gate(ledger: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """THE close-out gate. Any surface still short of ``live`` is an error-severity
    blocker: the run borrowed parallelism against a mock and has not repaid it.

    A `live` entry that never recorded its verification is an advisory — the
    engine cannot witness the endpoint, so it points rather than pretends.

    Anything else the entry might say — an unrecognized state, a shape that is
    not even a mapping — is a BLOCKER. Note the polarity a fail-open reader gets
    backwards: an entry with no state at all defaults to ``proposed`` and blocks,
    so an entry with a present-but-unreadable state must block too."""
    findings: List[Dict[str, str]] = []
    if ledger is not None and not isinstance(ledger, list):
        # Public API: a caller can reach this without going through
        # `normalize_ledger` — passing the WRAPPER object instead of its entries
        # is the obvious mistake. Not-an-array blocks; reading it as empty would
        # be the silent green this gate exists to prevent.
        return [_err(
            "malformed-ledger",
            f"the ledger is a JSON {_json_type(ledger)}, not an array of entries. If it is the "
            f"ledger DOCUMENT, take its entries through normalize_ledger first; the gate cannot "
            f"report on a ledger it cannot read, so it blocks.")]
    for index, entry in enumerate(ledger or [], 1):
        if not isinstance(entry, dict):
            findings.append(_err(
                "malformed-ledger-entry",
                f"ledger entry #{index} is a JSON {_json_type(entry)}, not an object — the engine "
                "cannot tell which surface it describes or whether that surface was retired, so "
                "it blocks the close-out."
            ))
            continue
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
        elif state == TERMINAL_STATE:
            if _is_blank(entry.get("verified_by")):
                findings.append(_advise(
                    "retirement-unverified",
                    f"contract {cid!r} ({surface}) is marked live but records no verified_by "
                    "evidence (the end-to-end check that saw real data through this path)."
                ))
        else:
            findings.append(_err(
                "unknown-ledger-state",
                f"contract {cid!r} ({surface}) carries state {state!r}, which is not one of "
                f"{CONTRACT_STATES}. The engine cannot tell whether its mock was retired, so it "
                "blocks the close-out — a typo'd state is an unreadable entry, not a retired "
                "surface."
            ))
    return findings


def ledger_summary(ledger: List[Dict[str, Any]]) -> Dict[str, int]:
    """``{state: count}`` across the ledger, every state key present plus an
    ``unknown`` bucket, so the counts always sum to ``len(ledger)`` and no entry
    can disappear from the operator's one visibility line."""
    summary = {state: 0 for state in CONTRACT_STATES}
    summary[UNKNOWN_STATE_BUCKET] = 0
    for entry in _as_list(ledger):
        state = entry.get("state", "proposed") if isinstance(entry, dict) else None
        # Bucket by VALUE, not by dict-key lookup: hand-written JSON can carry an
        # object or an array here, and `state in summary` raises TypeError on
        # exactly those. A traceback is not a named reason.
        known = isinstance(state, str) and state in CONTRACT_STATES
        summary[state if known else UNKNOWN_STATE_BUCKET] += 1
    return summary


def contract_drift(contract: Dict[str, Any], observed: Any,
                   retirement: bool = False) -> List[Dict[str, str]]:
    """What the surface ACTUALLY returns vs what was approved.

    ``observed`` is a payload the caller obtained by hitting the live endpoint
    (the engine performs no HTTP — see the module honest boundary). Missing or
    type-mismatched declared fields are errors; undeclared extras are advisories
    (additive drift breaks nobody, but the contract should say so). Declared
    element and member shapes are adjudicated too, so a list-of-objects response
    is bound below its container.

    ``retirement=True`` is the CFP-6 reading of the same payload: the surface is
    claimed to be live, so the provisional marker it was provisioned with must be
    GONE. Present, at any depth, it is a blocker — that check is what makes the
    marker a machine-enforced promise rather than a convention."""
    if not isinstance(observed, dict):
        return [_err(
            "observed-payload-not-an-object",
            f"the observed payload is a JSON {_json_type(observed)}, not an object, so it carries "
            "no named fields to adjudicate against the approved shape. Model a collection response "
            f"as a declared field of type 'array' with an {ARRAY_ITEMS_KEY!r} element shape, and "
            "capture the payload from the wrapping object the endpoint returns.")]

    findings: List[Dict[str, str]] = []
    seen: set = set()
    marker = provisional_marker(contract)
    _drift_mapping(_as_list(contract.get("response_fields")), observed, "", findings, seen)
    if retirement:
        _detect_provisional_marker(observed, marker, "", findings, seen)
    return findings


def _record(findings: List[Dict[str, str]], seen: set, finding: Dict[str, str], path: str) -> None:
    """Append a finding once per (kind, payload path). A 200-row collection with
    one bad element field is one defect, not two hundred findings."""
    key = (finding["kind"], path)
    if key in seen:
        return
    seen.add(key)
    findings.append(finding)


def _drift_mapping(declarations: List[Any], observed: Dict[str, Any], prefix: str,
                   findings: List[Dict[str, str]], seen: set) -> None:
    """Adjudicate one mapping payload against a list of field declarations,
    recursing into declared element and member shapes."""
    # Only usably-named declarations can be adjudicated — an unaddressable one is
    # reported at APPROVAL (`response-field-unnamed`), and the drift check says
    # nothing about it rather than inventing a finding or raising on the lookup.
    declared: Dict[str, Dict[str, Any]] = {}
    for f in declarations:
        if isinstance(f, dict) and _is_usable_name(f.get("name")) and f["name"] not in declared:
            declared[f["name"]] = f

    for name, decl in declared.items():
        path = f"{prefix}{name}"
        if name not in observed:
            _record(findings, seen, _err(
                "contract-field-missing",
                f"approved field {path!r} is absent from the observed payload"), path)
            continue
        value = observed[name]
        ftype = decl.get("type")
        if ftype in (None, "any"):
            continue
        if not _type_matches(value, ftype):
            _record(findings, seen, _err(
                "contract-field-type-mismatch",
                f"field {path!r} was approved as {ftype!r} but the payload carries "
                f"{_json_type(value)!r}"), path)
            continue
        if ftype == "object" and isinstance(decl.get(OBJECT_FIELDS_KEY), list):
            _drift_mapping(decl[OBJECT_FIELDS_KEY], value, f"{path}.", findings, seen)
        elif ftype == "array" and isinstance(decl.get(ARRAY_ITEMS_KEY), list):
            for element in value:
                if not isinstance(element, dict):
                    _record(findings, seen, _err(
                        "contract-element-not-an-object",
                        f"field {path!r} declares an element shape but the payload carries a "
                        f"{_json_type(element)} element"), f"{path}[]")
                    continue
                _drift_mapping(decl[ARRAY_ITEMS_KEY], element, f"{path}[].", findings, seen)

    for name in observed:
        if name not in declared:
            path = f"{prefix}{name}"
            _record(findings, seen, _advise(
                "undeclared-field",
                f"the payload carries {path!r}, which the contract does not declare"), path)


def _detect_provisional_marker(value: Any, marker: str, path: str,
                               findings: List[Dict[str, str]], seen: set) -> None:
    """Walk the payload for the provisional envelope key. It is checked at every
    depth because a mock envelope is as easily left on an element as on the
    top-level response."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == marker:
                _record(findings, seen, _err(
                    "provisional-marker-still-served",
                    f"the payload still carries the provisional marker {child_path!r} — this "
                    "surface is serving its scaffold, not real data, so it has not been retired "
                    "however the ledger describes it"), child_path)
                continue
            _detect_provisional_marker(child, marker, child_path, findings, seen)
    elif isinstance(value, list):
        for element in value:
            _detect_provisional_marker(element, marker, f"{path}[]", findings, seen)


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
# CFP-4 — registering the retirement gate with the machinery that enforces it
# --------------------------------------------------------------------------- #

def declared_gate_entry(contract: Dict[str, Any], declared_at: Optional[str] = None) -> Dict[str, str]:
    """The declared-gates registry entry for one contract's retirement.

    v3.47.0 built `.architect-team/declared-gates.json` so that a gate a run
    NAMES is a gate the Stop-hook completion audit refuses to let it ship
    without. Provisioning a mock names exactly such a gate, so provisioning
    records one. This is what makes "the run cannot close" a property of the
    machinery rather than a sentence in a skill."""
    cid = str(contract.get("contract_id") or "<unnamed>")
    surface = f"{contract.get('method', '')} {contract.get('path', '')}".strip()
    return {
        "gate_id": f"{RETIREMENT_GATE_ID_PREFIX}{cid}",
        "declaration_text": (
            f"contract {cid!r} ({surface}) is provisioned with a mock payload at its real path; "
            f"the run may not complete until the surface reaches 'live' — real data verified "
            f"end-to-end through this same path — and the retirement gate reports no blocking "
            f"finding."
        ),
        "check_command_or_artifact": (
            f"python scripts/contract/interface_contract.py gate "
            f"--ledger <workspace>/.architect-team/contracts/ledger.json"
        ),
        "declared_at": declared_at or _utc_now_iso(),
    }


def _read_registry(path: Path) -> List[Any]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a JSON array of gate entries (parsed as "
                         f"{type(data).__name__})")
    return data


def _write_registry(path: Path, entries: List[Any]) -> None:
    # Key order is preserved rather than sorted: the registry is shared run
    # state, and rewriting another discipline's entry — even cosmetically — is
    # not this engine's business.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def declare_gate(contract: Dict[str, Any], registry: Path,
                 declared_at: Optional[str] = None) -> Tuple[str, bool]:
    """Append this contract's retirement gate to the registry. Returns
    ``(gate_id, appended)`` — re-declaring an existing gate is a no-op, so
    provisioning is safe to re-run, and every gate another discipline recorded is
    left exactly as it was."""
    entry = declared_gate_entry(contract, declared_at)
    entries = _read_registry(registry)
    for existing in entries:
        if isinstance(existing, dict) and existing.get("gate_id") == entry["gate_id"]:
            return entry["gate_id"], False
    entries.append(entry)
    _write_registry(registry, entries)
    return entry["gate_id"], True


def satisfy_gate(gate_id: str, evidence: Path, registry: Path,
                 satisfied_at: Optional[str] = None) -> None:
    """Record the gate's satisfaction with the captured output of the check it
    named. Raises ``ValueError`` when the gate is unknown or the evidence is
    absent or blank — the audit rejects a blank capture as "the paper version of
    a check that never ran", so the writer never produces one."""
    entries = _read_registry(registry)
    if not evidence.is_file():
        raise ValueError(f"evidence file does not exist: {evidence}")
    if not evidence.read_text(encoding="utf-8", errors="replace").strip():
        raise ValueError(f"evidence file is blank: {evidence} — a gate is satisfied by the "
                         "executed check's captured output, not by an empty file")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("gate_id") == gate_id:
            entry["satisfied_at"] = satisfied_at or _utc_now_iso()
            entry["evidence_path"] = str(evidence)
            _write_registry(registry, entries)
            return
    raise ValueError(f"no declared gate {gate_id!r} in {registry}")


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
    dr.add_argument("--retirement", action="store_true",
                    help="CFP-6 reading: the provisional marker must be GONE, not merely undeclared.")

    dg = sub.add_parser("declare-gate",
                        help="Record this contract's retirement gate in the declared-gates registry.")
    dg.add_argument("--json", required=True)
    dg.add_argument("--registry", default=str(Path(".architect-team") / DECLARED_GATES_FILENAME))

    sg = sub.add_parser("satisfy-gate",
                        help="Record a retirement gate as satisfied, citing the check's captured output.")
    sg.add_argument("--gate-id", required=True)
    sg.add_argument("--evidence", required=True)
    sg.add_argument("--registry", default=str(Path(".architect-team") / DECLARED_GATES_FILENAME))

    args = parser.parse_args(argv)

    if args.cmd == "validate":
        return _report(validate_contract(_load(args.json)))

    if args.cmd == "gate":
        # An absent ledger is the COMMON case (most runs create no contracts) and
        # the pipeline documents it as benign — so it is an explicit clean no-op,
        # not a traceback the orchestrator learns to ignore.
        if not Path(args.ledger).exists():
            print(f"no contracts recorded at {args.ledger} — nothing to retire.")
            return 0
        entries, shape_findings = normalize_ledger(_load(args.ledger))
        if shape_findings:
            print(f"ledger: UNREADABLE — {len(shape_findings)} shape finding(s); no entry count "
                  f"can be trusted")
        else:
            print("ledger: " + ", ".join(f"{k}={v}" for k, v in ledger_summary(entries).items()))
        return _report(shape_findings + retirement_gate(entries))

    if args.cmd == "drift":
        return _report(contract_drift(_load(args.json), _load(args.observed),
                                      retirement=args.retirement))

    if args.cmd == "declare-gate":
        gate_id, appended = declare_gate(_load(args.json), Path(args.registry))
        print(f"{'declared' if appended else 'already declared'}: {gate_id} -> {args.registry}")
        return 0

    if args.cmd == "satisfy-gate":
        try:
            satisfy_gate(args.gate_id, Path(args.evidence), Path(args.registry))
        except ValueError as e:
            print(f"[error   ] satisfy-gate: {e}")
            return 1
        print(f"satisfied: {args.gate_id} (evidence {args.evidence})")
        return 0

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
