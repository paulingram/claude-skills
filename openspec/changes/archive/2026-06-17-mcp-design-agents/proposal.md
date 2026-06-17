## Why

CT6-6 §4 (MCP-1…MCP-3) asks for "MCP design agents" that encapsulate best-in-class techniques for standardizing LLM output — invoked whenever an agent is embedded inside an application, so that for every case where the agent produces something the output is guaranteed consistent and standardized via clear, specific output contracts / return formats. The repo has `verified-agent-output` (verifying CT6's OWN agents); this adds the outward-facing discipline for output contracts in the USER's embedded-agent application. Component 4 of the in-repo CT6-6 tier.

## What Changes

- **New deterministic engine** — `scripts/mcp_design/output_contract.py` (stdlib-only): `build_output_contract` (a CLOSED JSON Schema + the structured-output tool the model is forced to call), `validate_against_contract` (the runtime guarantee), `assess_contract` (best-in-class completeness signals). (REQ-001)
- **New skill + agent** — `skills/mcp-output-contract-design/SKILL.md` (the MCP-1…3 pattern + the embedded-in-application framing) + `agents/mcp-design-agent.md` (the worker that enumerates producer points and designs a contract per point, bounded to `.architect-team/mcp-design/`). (REQ-002)
- **Honest boundary** — the engine guarantees REJECTION of a non-conforming value, not PRODUCTION of a conforming one (the forced-tool + retry is the app's runtime); it is a minimal stdlib validator (no format/range/nested-object). (REQ-003)
- **Reuse-first + currency** — clean boundary vs `verified-agent-output`; Python stdlib-only; version bump to 3.20.0; skill 44→45, agent 38→39. (REQ-004)
- **Tests** — `tests/test_mcp_design.py` (build/validate/assess + type guards + CLI round-trip); suite green both encodings. (REQ-005)

## Capabilities

### New Capabilities

- `mcp-output-contract-design` — design a best-in-class output contract (closed schema + forced structured-output + validation + retry) for an LLM agent embedded in an application, with a builder/validator/assessor engine and a design-worker agent.

### Modified Capabilities

- None removed. The skill + agent inventories each grow by one; no new command/Layer-3 tool.
