# tasks — docs-currency-v3-39-1

## 1. Fix the living docs (the sweep)

- [ ] 1.1 `docs/CODEBASE_MAP.md`: re-lead the header blockquote with v3.39.1/v3.39.0 (current release first; prior narrative preserved below); System Overview "(current: v3.38.0)" → current; "As of v3.35.0 … 5362 pytest self-tests … 199 test files" → verified current inventory; directory-tree `tests/` count line → 5494 + 4 (200 files); `### Tests (5467 PASS + 4 SKIPPED)` heading + "live total as of v3.38.0" body → verified current totals; environment note stated as verified totals without invented per-OS variants.
- [ ] 1.2 `docs/INTEGRATION_MAP.md`: "Current inventory (v3.38.0)" → current version; "The 5467 pytest tests (+ 4 skipped, across 199 test files …)" → verified current totals.
- [ ] 1.3 `README.md`: badge `tests-5467%20passing` → `tests-5494%20passing`; the line-1475 current-suite summary count → current; the timeline current-marker row → v3.39.1/v3.39.0 as current (prior rows preserved as history).

## 2. Version machinery

- [ ] 2.1 `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` → `3.39.1`.
- [ ] 2.2 `CHANGELOG.md`: add the v3.39.1 docs-only PATCH entry at top (no historical entry edited).
- [ ] 2.3 `tests/test_dispatch_banner.py`: version pin 3.39.0 → 3.39.1 (docstring + both assertions).

## 3. Verify

- [ ] 3.1 Run `python tests/bug-fix-docs-currency-v3-39-1/check_docs_current.py` → exit 0, zero violations, exemptions dispositioned.
- [ ] 3.2 Full suite green under Windows cp1252: `python -m pytest -q`.
- [ ] 3.3 Full suite green under `PYTHONUTF8=1 python -m pytest -q`.
- [ ] 3.4 Write review-gate evidence (schema v7) at `.architect-team/reviews/<task-id>.json`.
