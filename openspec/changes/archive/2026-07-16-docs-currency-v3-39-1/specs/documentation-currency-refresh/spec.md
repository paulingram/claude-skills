# documentation-currency-refresh — delta (docs-currency-v3-39-1)

## ADDED Requirements

### Requirement: Current-state assertion currency

Every CURRENT-STATE assertion in the living doc set — the current version, the current suite totals (passing / skipped / test-file count), and the current inventory counts (skills / agents / commands) — SHALL match the shipped release's verified facts, and the match SHALL be checkable by a deterministic executable scan that (a) detects stale current-state assertions, (b) EXEMPTS historical narrative (delta phrasing such as "5467 → 5494", version-history tables/timelines, Recent-releases bullets, CHANGELOG entries below the top entry), and (c) prints every exempted hit with its disposition. Frozen-historical docs and archives are outside the scan's living set and are never rewritten.

#### Scenario: stale current-state assertion is detected and fails the scan

- **WHEN** a living doc asserts a prior release's fact as current (e.g. a `tests-5467` badge, a "current: v3.38.0" overview line, an "As of v3.35.0 … 5362 tests" inventory sentence) and the executable scan runs
- **THEN** the scan exits non-zero listing each violation with file, line, and excerpt

#### Scenario: historical narrative is exempt and dispositioned

- **WHEN** a living doc's history section legitimately mentions a prior count or version (delta phrasing, timeline rows below the current marker, Recent-releases bullets)
- **THEN** the scan does NOT count it as a violation
- **AND** the scan prints the hit with its `EXEMPT — historical` disposition so the exemption is auditable

#### Scenario: clean docs pass the scan after a refresh

- **WHEN** a documentation-currency refresh brings every current-state assertion to the shipped release's verified facts and the executable scan re-runs
- **THEN** the scan exits 0 with zero violations
- **AND** the stated current counts match the verified suite totals and inventory counts exactly
