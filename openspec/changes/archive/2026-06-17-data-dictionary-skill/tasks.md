## 1. Implementation

- [x] 1.1 `scripts/data_dictionary/data_dictionary.py`: stdlib-only engine — introspection + ~100-row sampling, grain inference, field inference, fixed provenance vocabulary, value-level corroboration (key + type claims), reference/relational maps, `DATA_DICTIONARY_MAP.md` serializer + CLI (REQ-001)
- [x] 1.2 `skills/data-dictionary/SKILL.md`: the contract — branch-by-input, recursive code analysis, doc analysis, sequencing + freshness, MemPalace persistence, maintenance discipline (REQ-002)
- [x] 1.3 Honest live-DB boundary: `build_from_inputs(...)` no-DB path + `live_inspection` block + all-null→inference + `MIN_KEY_SAMPLE` small-sample-key hedge (REQ-003)

## 2. Tests

- [x] 2.1 `tests/test_data_dictionary.py`: deterministic units + local-SQLite end-to-end dogfood (customer_id-vs-hash + census-on-zip) (REQ-001, REQ-005)
- [x] 2.2 Adversarial-review remediation pins: non-key corroboration, empty table, all-null column, small-sample hedge, populated reference-map render, no-DB path, live_inspection block, quoted-identifier crash (REQ-003, REQ-005)
- [x] 2.3 Register the skill (EXPECTED_SKILLS) + README inventory count 41 → 42 (REQ-004)
- [x] 2.4 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.17.0 + `test_dispatch_banner.py` assertion + CHANGELOG entry (REQ-004)
- [x] 3.2 CLAUDE.md (counts + scripts entry + recent-release bullet) / CODEBASE_MAP (tree + counts + skill row + note ledger) / INTEGRATION_MAP (note ledger) / README (badge + grid) brought current (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST verdict remediated — DD-14 value-level corroboration, SQL-identifier `_q` escape, the no-DB path + live_inspection field, the small-sample hedge, and the gap-blessing test backfill (REQ-001, REQ-003, REQ-005)
- [x] 4.2 Real verification: local-SQLite CLI dogfood (emit → rendered artifact with live_inspection + grain + field inference), not described (REQ-005)
