## ADDED Requirements

### Requirement: REQ-001 — Output-contract engine (MCP-1/MCP-3)

`scripts/mcp_design/output_contract.py` SHALL be a stdlib-only engine providing `build_output_contract(name, fields, ...)` — which assembles a CLOSED JSON Schema (typed fields, a required set, enums type-checked against the field type, `additionalProperties: false`) plus the structured-output tool the model is forced to call — `validate_against_contract(value, contract)` — which validates a produced value (object-ness, required, closed-object extras, per-field type + enum + array-item type, with `bool` not satisfying `integer`/`number`) — and `assess_contract(contract)` — which emits best-in-class completeness signals.

#### Scenario: a closed contract validates conforming and rejects non-conforming values

- **WHEN** a contract is built and a conforming object is validated
- **THEN** validation passes; an object with a missing required field, an extra field, a wrong type, a bad enum value, or a wrong array-item type is rejected with errors

### Requirement: REQ-002 — The design skill + worker agent (MCP-1/MCP-2)

`skills/mcp-output-contract-design/SKILL.md` SHALL document the best-in-class pattern (a closed output contract + a forced structured-output mechanism + validation + retry-on-mismatch) and that it applies whenever an agent is embedded INSIDE an application (MCP-2). `agents/mcp-design-agent.md` SHALL be the worker that enumerates an app's producer points and designs a contract per point, with Write bounded to `.architect-team/mcp-design/` and never writing the app's code.

#### Scenario: the skill + agent state the pattern and the bound

- **WHEN** the skill + agent bodies are read
- **THEN** the skill names MCP-1…MCP-3 + the four-part pattern + the embedded-in-app framing; the agent is bounded to `.architect-team/mcp-design/` and states it never writes the app's code

### Requirement: REQ-003 — Honest boundary

The skill SHALL state that the engine guarantees REJECTION of a non-conforming value but NOT production of a conforming one (the forced-tool mechanism + retry loop is the app's runtime), and that the validator is minimal stdlib (no `format` / `pattern` / range / nested-object schemas), with the contract's `json_schema` being standard JSON Schema for a fuller validator in the app.

#### Scenario: the honest boundary is stated

- **WHEN** the skill's honest-boundary section is read
- **THEN** it distinguishes reject-vs-produce AND names the validator's limits

### Requirement: REQ-004 — Reuse-first + currency

The capability SHALL be built reuse-first with a clean boundary vs `verified-agent-output` (VAO is for CT6's own agents; this is the outward-facing counterpart for the user's app); Python SHALL stay stdlib-only; the release SHALL bump the version to 3.20.0 and bring the counts current (45 skills, 39 agents).

#### Scenario: version + counts current + clean boundary

- **WHEN** the version files + README + CLAUDE.md + CODEBASE_MAP + the skill are read
- **THEN** the version is 3.20.0, the inventories say 45 skills + 39 agents, and the skill names the VAO reuse boundary

### Requirement: REQ-005 — Tests green both encodings

A new test file SHALL cover build/validate/assess, the JSON-type guards (`bool` not integer, `int` is number, no array-items crash, empty fields, enum-type mismatch rejected, object no-recurse), and the CLI build→validate→assess round-trip; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_mcp_design.py` present
- **THEN** there are zero failures
