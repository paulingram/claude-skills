## 1. Implementation

- [x] 1.1 `scripts/token_compression/caveman.py`: stdlib-only `compress` (meaning-preserving filler-drop + phrase-subs + code/structure preservation + boundary-space) + `estimate_tokens` + `compression_stats` + CLI (REQ-001)
- [x] 1.2 `skills/token-compression/SKILL.md`: the caveman style (TC-2) + the hard internal-only boundary (TC-1) (REQ-002, REQ-003)
- [x] 1.3 TC-3 framing: heavier ML package as a documented 3rd-party app-layer option over the stdlib floor (REQ-003)
- [x] 1.4 Honest boundary: lossy-of-filler heuristic + estimate disclaimers + the content-homograph note (REQ-004)

## 2. Tests

- [x] 2.1 `tests/test_token_compression.py`: filler drop + content/preposition retention + code + line structure + phrase subs (REQ-001, REQ-005)
- [x] 2.2 Edges: boundary-space-around-code, unbalanced backticks, compress-to-nothing ratio, empty/None (REQ-001, REQ-005)
- [x] 2.3 CLI compress (stdin) + stats --json (REQ-001, REQ-005)
- [x] 2.4 Register skill (EXPECTED_SKILLS 46→47) (REQ-004)
- [x] 2.5 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-005)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.22.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN + grid: skills 47) / CLAUDE.md / CODEBASE_MAP / INTEGRATION_MAP brought current; the in-repo CT6-6 tier completion noted (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); SHIP verdict — remediated the two minor findings (prose↔code boundary-space glue; broadened content-homograph disclaimer) + added the recommended edge tests (REQ-001, REQ-005)
- [x] 4.2 Real verification: CLI compress + stats dogfood (~30% saving on realistic internal text), not described (REQ-005)
