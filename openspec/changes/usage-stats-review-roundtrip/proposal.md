# Proposal: usage-stats-review-roundtrip (Run E)

## Why

Run E of `docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` §7.5 (R4 + R5 — "small enough to pair"). The data-dictionary now has content (Run C mining) and a team memory (Run D annotations). Two of deng-toolkit's remaining ideas, rebuilt to CT6 standards, make the catalog *importance-aware* and *human-correctable*:

- **R4 — usage-grounded importance.** The dictionary today infers volume/velocity; where a live engine exposes usage stats (SQL Server `dm_*`, Postgres `pg_stat_*`), those are MEASURED, not guessed. An optional per-engine `usage_stats` adapter attaches a per-table `usage` block (read/write recency, row volume) with provenance `live-data`. Stage 4 of `data-engineering-exploration` gets measured baselines, the knowledge server ranks by it, and R5's review rows sort by it. The named anti-pattern (deng's silently-single-target arm): **absent stats ≠ zero usage — the block is OMITTED, never zero-filled.**
- **R5 — the offline stakeholder review round-trip.** A `generate-review` / `apply-review` pair: emit a CSV of the fields that most need human eyes (low-confidence OR ⚠ corroboration-conflict, sorted by R4 usage), a stakeholder edits it offline, and the returned corrections ingest as `provided_defs` **through the existing corroboration gate** — a human claim is corroborated like any other, never transcribed. deng's round-trip is column-drifted on two of three sheets precisely because it lacks a pinned round-trip test; ours ships WITH one (write → edit → read → assert every column lands in the field it was written from).

**Hardening addendum (two logged corroboration follow-ups, same surface).** Run E touches the corroboration gate's consumers, so it also closes the two same-class "claim accepted without its exact field corroborated" residuals logged during Runs C/D: (1) sql-mining's `corroborate_mined_claim` per-field acceptance (the R1 residual), and (2) the annotations `non_null_sampled==0` text-family edge. Both are narrow and non-CLI-reachable, but they are exactly the class the corroboration inversion exists to prevent; closing them here keeps the discipline airtight.

## What Changes

- **R4:** an optional per-engine `usage_stats` adapter in `scripts/data_dictionary/data_dictionary.py` (following the `build_from_sqlite` adapter shape) — an injected `UsageStatsSource` seam with SQL Server / Postgres shapes described and a `SqliteUsageStats` that honestly returns none; a per-table `usage` block (read_recency / write_recency / row_volume) at provenance `live-data`, OMITTED (never zero-filled) when stats are absent.
- **R5:** `generate-review` / `apply-review` subcommands in the same engine — CSV via stdlib `csv`; row filter = fields with `low` confidence OR a ⚠ corroboration conflict, sorted by R4 `usage` when present; returned corrections ingest as `provided_defs` through `corroborate_definition`; redaction via `scripts/helpdesk/logit.py::redact_evidence`. A PINNED round-trip test.
- **Hardening:** per-field acceptance in `scripts/sql_mining/sql_mining.py::corroborate_mined_claim` (R1) + `non_null_sampled==0` treated as not-checked in `scripts/data_dictionary/annotations.py` (both red-first).
- **Docs:** `skills/data-dictionary/SKILL.md` gains the usage block + the review round-trip contract; version 3.52.0 → 3.53.0; the house doc-currency + CHANGELOG obligations.

## Impact

- Additive within `scripts/` (stdlib-only); NO new services module, NO new skill/command/agent — `check_separation` unaffected. Provenance vocabulary unchanged (`usage` rides `live-data`). A dictionary built without a usage source is byte-unchanged. Suite: zero NEW failures vs the 6926/0/6 baseline; +N tests. Live `dm_*`/`pg_stat_*` reads are an adapter boundary (SQLite has none) — the engine never fabricates `live-data` usage.
