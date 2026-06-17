---
name: mcp-output-contract-design
description: Use when designing or reviewing an application that embeds an LLM agent and you need the agent's output to be guaranteed consistent and standardized. Encapsulates best-in-class output-standardization techniques (MCP-1…3) — an explicit output contract (a closed JSON Schema), a structured-output mechanism the model is FORCED to call, validation of every produced value against the contract, and retry-on-mismatch. Applies whenever an embedded agent is asked to produce something, so its outputs are reliable to parse and consume. The deterministic contract builder + validator + completeness assessor live in scripts/mcp_design/output_contract.py; this skill is the contract and the mcp-design-agent is the worker.
---

# MCP Output-Contract Design (MCP-1 … MCP-3)

When an application embeds an LLM agent and asks it to PRODUCE something — parse a
document, classify an input, extract fields, return a decision — the output is
worthless if it is not reliably shaped. Free-text or best-effort JSON breaks the
consuming code intermittently. The best-in-class fix is an explicit **output
contract**, and this discipline is how you design one.

The deterministic pieces — the contract builder, the validator, and the
completeness assessor — live in **`scripts/mcp_design/output_contract.py`**
(stdlib-only, unit-tested). This skill is the contract + the design workflow; the
**`mcp-design-agent`** is the worker that produces a contract for a given use
case. Do not re-implement the deterministic pieces in prose — call the module.

## The best-in-class pattern (MCP-1, MCP-3)

For EVERY place an embedded agent produces something, apply ALL of:

1. **A closed output contract (JSON Schema).** Every field typed; every field the
   consumer needs marked `required`; `additionalProperties: false` so the model
   cannot smuggle in surprise fields; an `enum` wherever the value is one of a
   fixed set. `build_output_contract(name, fields, ...)` assembles this.
2. **A structured-output MECHANISM the model is forced to use.** Do not ask for
   "JSON in your reply" and hope — bind the contract to a structured-output tool
   (the model MUST call it) or the provider's response-format/JSON-mode. The
   contract carries a `structured_output_tool` for exactly this.
3. **Validation of every produced value (MCP-3).** Validate each output against
   the contract with `validate_against_contract(value, contract)` BEFORE the app
   consumes it. A value is not trusted until it validates.
4. **Retry-on-mismatch.** On a validation failure, re-prompt the model WITH the
   specific errors and the schema, bounded to a small retry count; escalate after
   the bound rather than consuming an invalid value. (This runtime loop is the
   app's; the engine gives you the deterministic validate step it turns on.)

## When this fires (MCP-2)

Whenever agents are leveraged INSIDE an application — an agent embedded in the
product, a background agent, a sub-agent the app spawns — every "the agent
produces X" point gets an output contract. It is not for one-off interactive
chat; it is for the programmatic producer points the app's code depends on.

## Workflow

### Step 1 — Enumerate the producer points

For the app under design, list every place an embedded agent produces a value the
code then consumes. Each is a contract.

### Step 2 — Design each contract

For each producer point, define the fields (name + JSON type + a description the
MODEL will read + an enum where the value set is fixed) and which are required,
then build it:

```bash
$(command -v python3 || command -v python) scripts/mcp_design/output_contract.py \
  build --name extraction --field "title:string:the document title" \
        --field "confidence:number:0..1 model confidence" --out contract.json
```

Or call `build_output_contract(...)` directly. Spawn the **`mcp-design-agent`** to
do this design for a use case end to end.

### Step 3 — Assess for best-in-class completeness

```bash
$(command -v python3 || command -v python) scripts/mcp_design/output_contract.py assess --contract contract.json
```

Resolve every signal — `open-object` (close it), `nothing-required` (mark the
consumer's needs required), `fields-missing-description` (the model needs them),
`no-structured-output-mechanism` (bind the tool).

### Step 4 — Wire validation + retry

In the app, validate every produced value against the contract before use, and
retry-on-mismatch with the errors fed back. The contract + validator are the
guarantee; the retry loop is the app's runtime.

## Honest boundary

The engine GUARANTEES that a non-conforming value is REJECTED
(`validate_against_contract` returns `valid: false`) — it does NOT, by itself,
guarantee the model PRODUCES a conforming value. That production guarantee comes
from the forced structured-output mechanism + the retry-on-mismatch loop, which
is the app's runtime and is provider-dependent. "Guaranteed consistent" means:
the app never CONSUMES a value that fails the contract.

The validator is minimal stdlib (object-ness, required, closed-object extras,
per-field type + enum + array-item type; enum values are type-checked against the
field type at build time). It is not a full JSON-Schema validator (no `format`,
`pattern`, `minimum`/`maximum`, nested-object schemas) — for those, the contract's
`json_schema` is standard JSON Schema and can be handed to a full validator in
the app. The completeness assessor's signals are heuristics for the common
best-practice gaps, not a proof of a perfect contract.

## Cross-references

- `scripts/mcp_design/output_contract.py` — the deterministic builder + validator + assessor (the machine).
- `agents/mcp-design-agent` — the worker that designs a contract for a given embedded-agent use case.
- `skills/verified-agent-output` — the CT6-internal VAO framework (verifying THIS plugin's own agent output); `mcp-output-contract-design` is the outward-facing counterpart for output contracts in the USER's embedded-agent application.
