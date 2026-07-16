# docs-currency-v3-39-1 — living docs stale-current-state fix (docs-only PATCH v3.39.1)

## Why

The repo shipped v3.39.0 (one-call external-LLM setup, merge `cd6de14`), but the living docs still assert v3.38-era CURRENT-STATE facts. The executed B1 replication (`tests/bug-fix-docs-currency-v3-39-1/check_docs_current.py`, exit 1, full output at `.architect-team/bug-fix/docs-currency-v3-39-1/b1-failing-output.txt`) found **11 violations** across 3 living docs:

```
DOCS CURRENT-STATE CHECK: FAIL
Expected current suite: 5494 passing + 4 skipped (200 test files)
Violations: 11
- README.md:41 [stale-tests-badge] ![tests](...badge/tests-5467%20passing...)
- README.md:1475 [stale-current-suite-summary] "...the v3.31.0 instruction-compliance lint..." (5467-as-current)
- README.md:1606 [stale-current-timeline-summary] "◆ v3.38.0 ─ setup asks for missing keys..." (timeline current-marker row)
- docs/CODEBASE_MAP.md:10 [header-blockquote-version-mismatch] leads "v3.35.0 (2026-07-14)" != plugin.json v3.39.0
- docs/CODEBASE_MAP.md:16 [stale-system-overview-version] "(current: v3.38.0)"
- docs/CODEBASE_MAP.md:20 [stale-system-overview-inventory] "As of **v3.35.0** ... 5362 pytest self-tests ... 199 test files"
- docs/CODEBASE_MAP.md:156 [stale-directory-test-count] "tests/ # 5467 pytest self-tests + 4 skipped (199 test files...)"
- docs/CODEBASE_MAP.md:393 [stale-tests-heading] "### Tests (5467 PASS + 4 SKIPPED)"
- docs/CODEBASE_MAP.md:395 [stale-live-test-total] "live total as of **v3.38.0 is 5467 passing + 4 skipped** (199 test files...)"
- docs/INTEGRATION_MAP.md:20 [stale-current-inventory-version] "Current inventory (v3.38.0): ..."
- docs/INTEGRATION_MAP.md:487 [stale-automated-suite-total] "The 5467 pytest tests (+ 4 skipped, across 199 test files ...)"
```

28 additional hits were dispositioned as legitimate historical narrative (delta phrasing like "5467 → 5494") and are EXEMPT per the user's iteration-2 authorization. A stale current-state doc ships a lie; the repo's convention (v3.31.1 / v3.35.1 precedent) is a versioned docs-only PATCH.

## What Changes

- Fix all 11 stale current-state assertions to the verified v3.39.0 reality: suite **5494 passing + 4 skipped**, **200 test files**, **48 skills / 39 agents / 23 commands**, current version **v3.39.1**.
- `docs/CODEBASE_MAP.md`: header blockquote re-led with the current release; System Overview "current:" + "As of" inventory brought current; directory-tree test count, Tests-section heading + live-total body brought current (the environment note's cross-encoding figures stated as the verified totals — per-OS variants not re-invented).
- `docs/INTEGRATION_MAP.md`: "Current inventory" version + the automated-suite total brought current.
- `README.md`: tests badge → `tests-5494%20passing`; the stale current-suite summary line and the timeline current-marker row brought current.
- Version machinery: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` → **3.39.1**; new CHANGELOG **v3.39.1** entry (added at top — no historical entry edited); `tests/test_dispatch_banner.py` version pin → 3.39.1.
- The B1/B2 replication artifact `tests/bug-fix-docs-currency-v3-39-1/check_docs_current.py` ships as the permanent regression check (standalone script, never pytest-collected).
- HISTORICAL narrative in living docs is NOT rewritten (user-authorized exemption); frozen docs (`docs/superpowers/*`, `docs/archive/INDEX.md`, per-phenotype records, openspec archives) untouched.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `documentation-currency-refresh`: adds the **current-state assertion currency** requirement — living docs' CURRENT-STATE assertions (version, suite totals, inventory counts) must match the shipped release's verified facts, checkable by a deterministic executable scan that exempts historical narrative; a refresh run records every exempted hit's disposition.

## Impact

- Affected files: `README.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md` (new entry only), `tests/test_dispatch_banner.py` (pin only), `tests/bug-fix-docs-currency-v3-39-1/check_docs_current.py` (new artifact).
- No source-code behavior change; no skill/agent/command/hook surface change (counts stay 48/39/23).
- Suite impact: the banner-pin bump keeps the suite green; expected totals remain 5494 passing + 4 skipped under both encodings.
