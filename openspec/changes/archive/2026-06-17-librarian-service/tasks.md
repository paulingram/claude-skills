## 1. Implementation

- [x] 1.1 `services/librarian/library_index.py`: stdlib `sqlite3` keyword/summary/concept-cloud reference index + LIB-10 conceptual search (weighted overlap over unicode-folded tokens) (REQ-001)
- [x] 1.2 `services/librarian/extract.py`: extraction prompt + string-aware JSON parse (`JSONDecoder.raw_decode`) + stable sha256 doc id (REQ-002)
- [x] 1.3 `services/librarian/librarian.py`: fetch→extract→index→metadata orchestration on `bg_runtime` + LIB-8 file-folder body store (path-safe filename) + `Source`/`StaticSource` + `LLMClient` adapters (REQ-003)
- [x] 1.4 `services/README.md`: Librarian promoted from "landing next" to a landed Layout block (REQ-004)

## 2. Tests

- [x] 2.1 `tests/test_services_librarian.py`: index round-trip/idempotent-reindex/keyword+concept search/conceptual ranking/concept-cloud; prompt + string-aware parse (incl. brace-in-string) (REQ-001, REQ-002, REQ-005)
- [x] 2.2 Orchestration: relevant-keep-vs-skip + metadata write + scheduler tasks + install descriptor; remediation edges (unicode fold, relevant-but-no-title gate, file-folder body store + path safety, per-topic closure binding) (REQ-003, REQ-005)
- [x] 2.3 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.24.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN) / CLAUDE.md (Stack + Structure + counts + recent-release) / CODEBASE_MAP (tree + tests + note) / INTEGRATION_MAP (note) / services/README brought current; skill/agent/command counts unchanged (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST → remediated 4 (string-unaware brace parser → `JSONDecoder.raw_decode`; missing LIB-8 body store → added; over-claimed LIB-10 → hedged to overlap-not-semantic; ASCII-only tokenizer → NFKD unicode-fold) (REQ-001, REQ-002, REQ-003, REQ-005)
- [x] 4.2 Real verification: index round-trip, brace-in-string parse, unicode fold, body-store round-trip + path safety exercised in-process, not described (REQ-005)
