## 1. Implementation

- [x] 1.1 `scripts/mcp_design/output_contract.py`: stdlib-only `build_output_contract` (closed JSON Schema + structured-output tool + build-time enum-type guard) + `validate_against_contract` + `assess_contract` + CLI (REQ-001)
- [x] 1.2 `skills/mcp-output-contract-design/SKILL.md`: the MCP-1…3 pattern + embedded-in-app framing (REQ-002)
- [x] 1.3 `agents/mcp-design-agent.md`: the design worker (bounded to `.architect-team/mcp-design/`; never the app's code) + boilerplate sync (REQ-002)
- [x] 1.4 Honest boundary: reject-not-produce + minimal-validator limits (REQ-003)

## 2. Tests

- [x] 2.1 `tests/test_mcp_design.py`: build/validate/assess + CLI round-trip (REQ-001, REQ-005)
- [x] 2.2 JSON-type guards: bool-not-integer, int-is-number, no array-items crash, empty fields, enum-type-mismatch rejected, object no-recurse (REQ-001, REQ-005)
- [x] 2.3 Register skill (EXPECTED_SKILLS 44→45) + agent (EXPECTED_AGENTS 38→39, boilerplate standard set) (REQ-004)
- [x] 2.4 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.20.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN + inventory grid: skills 45 + agents 39) / CLAUDE.md / CODEBASE_MAP / INTEGRATION_MAP brought current (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); SHIP verdict — remediated the two minor items (build-time enum-type guard; softened "guaranteed" claim) + added the recommended type-guard tests (REQ-001, REQ-003, REQ-005)
- [x] 4.2 Real verification: CLI build → validate → assess dogfood, not described (REQ-005)
