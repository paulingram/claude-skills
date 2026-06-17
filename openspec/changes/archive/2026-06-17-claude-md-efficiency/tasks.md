## 1. Implementation

- [x] 1.1 `scripts/claude_md/claude_md_efficiency.py`: stdlib-only `assess_claude_md` (pointer-shape + byte budget + signals) + `generate_pointer_claude_md` (wake-up + standards + customizations) + CLI (REQ-001)
- [x] 1.2 `skills/claude-md-efficiency/SKILL.md`: the CMD-1…CMD-4 contract; CMD-1 precondition (only when MemPalace installed) delegating detection to `mempalace-integration` (REQ-002)
- [x] 1.3 Honest boundary: heuristic disclaimer + the no-delete-unstored-context rule (REQ-003)

## 2. Tests

- [x] 2.1 `tests/test_claude_md_efficiency.py`: assessor (container vs pointer), generate→assess round-trip, CLI assess/generate (REQ-001, REQ-005)
- [x] 2.2 Boundary pins: empty/None input, exactly-at-budget off-by-one, multi-byte byte counting (REQ-001, REQ-005)
- [x] 2.3 Register the skill (EXPECTED_SKILLS 43→44) (REQ-004)
- [x] 2.4 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.19.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN + inventory grid) / CLAUDE.md (counts + scripts entry + recent-release) / CODEBASE_MAP (tree + counts + skill row + note ledger) / INTEGRATION_MAP (note ledger) brought current (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); SHIP verdict — added the recommended empty / at-budget / byte-counting boundary tests (REQ-001, REQ-005)
- [x] 4.2 Real verification: CLI generate → assess dogfood (a 680-byte pointer CLAUDE.md, assessor passes), not described (REQ-005)
