## 1. Implementation

- [x] 1.1 `services/separation.py`: `SEPARATION_MANIFEST` (open-core-vs-paid plan + adapter seams + paid/closed pieces) + `validate_manifest` (REQ-001)
- [x] 1.2 `services/separation.py`: `check_separation()` — the REPO-4 import-clean invariant over every `services/**/*.py`, recursing through load-time compound statements but not function bodies (REQ-002)
- [x] 1.3 `services/SEPARATION_MANIFEST.md`: the human two-repo plan + seam table + separate-out procedure (REQ-001)

## 2. Tests

- [x] 2.1 `tests/test_services_separation.py`: manifest validate + documented paid pieces/seams; malformed-manifest guard incl. non-dict entries (REQ-001, REQ-003)
- [x] 2.2 The REPO-4 import-clean assertion over the real tree + scanner edges (external top-level vs lazy in-function; in-repo + reuse-name allow; nested try/if/class-body catch) (REQ-002, REQ-003)
- [x] 2.3 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-003)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.28.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-003)
- [x] 3.2 README (badge + NEW IN) / CLAUDE.md (Stack + Structure + counts + recent-release) / CODEBASE_MAP (tree + tests + note) / INTEGRATION_MAP (note) / services/README (separation plan) brought current; skill/agent/command counts unchanged (REQ-003)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST → remediated 3 (a CRITICAL scanner soundness hole — nested module-load imports were invisible; validate_manifest crash on non-dict; a Python-3.10+ guard) (REQ-002, REQ-003)
- [x] 4.2 Real verification: the nested-`try`/class-body import-catch + the in-function allow exercised in-process, not described (REQ-003)
