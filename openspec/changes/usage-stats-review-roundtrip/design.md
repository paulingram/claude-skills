# Design: usage-stats-review-roundtrip (Run E)

## Context

Run E of the proposal (§7.5, R4 + R5). Constraints: additive within `scripts/data_dictionary/data_dictionary.py` (+ two small hardening edits to `sql_mining.py` and `annotations.py`), stdlib-only, suite zero-new-failures (baseline 6926/0/6), the house instruction-compliance + doc-currency gates, the evidence stack (schema v7 paired review). No new `services/` module → `check_separation` unaffected. The live `dm_*`/`pg_stat_*` reads are an adapter boundary; SQLite honestly has none.

## Decisions

- **E-D1 — usage as an injected adapter, `live-data` provenance, OMIT-not-zero.** A `UsageStatsSource` protocol (`table_usage(table) -> {read_recency, write_recency, row_volume} | None`) injected into the builder, mirroring how the LLM/DB adapters are injected elsewhere. Concrete shapes DESCRIBED for SQL Server (`sys.dm_db_index_usage_stats` + `sys.dm_db_partition_stats`) and Postgres (`pg_stat_user_tables`); `SqliteUsageStats` returns `None` for every table (honest — SQLite exposes no such catalog). The per-table `usage` block is attached ONLY when the source returns a non-None mapping; provenance `live-data` because it IS measured. **Absent → the key is omitted, never `{}` or zeros** (the deng anti-pattern). A `FakeUsageStatsSource` drives the tests offline.
- **E-D2 — the review round-trip is two subcommands over existing fields.** `generate-review` writes a CSV whose rows are the dictionary fields with `confidence == "low"` OR a corroboration `⚠`/conflict flag, each row carrying `table, field, current_definition, confidence, conflict, usage_volume, proposed_definition` (the last blank for the stakeholder). Rows sort by R4 `usage.row_volume` desc when present (fields without usage sort last, stable). `apply-review` reads the edited CSV, takes each non-blank `proposed_definition` as a `provided_defs["table.field"] = {definition, provenance: "direct-user-input"}` and re-runs `corroborate_definition` — a human correction is corroborated exactly like any other provided definition (⚠ + downgrade on conflict, never blindly accepted).
- **E-D3 — redaction is REUSE, not new.** `generate-review` routes every row through `scripts/helpdesk/logit.py::redact_evidence(rows, level)` before writing — default `summary` (allow-list; sample values dropped), `full` only on explicit `--privacy full`. The CSV is a triage-shaped artifact; the privacy engine is done.
- **E-D4 — the pinned round-trip test is the non-negotiable.** `test_review_roundtrip`: build a dictionary → `generate-review` to a CSV → programmatically edit one `proposed_definition` cell → `apply-review` → assert the correction landed on the EXACT `table.field` it was written from (no column drift) AND passed through `corroborate_definition` (a conflicting correction is ⚠/downgraded). This is the test deng lacks.
- **E-D5 — the two hardening fixes are red-first and per-field.** (1) `corroborate_mined_claim` (sql_mining.py): accept a candidate as corroborated ONLY when its exact field was compared against a corroborated def OR rows for it were inspected — the same per-field `checked` shape Run D's F1 fix established; a candidate with `corroborated_defs` supplied but its field absent + `rows=None` stays not-accepted (`inference`). (2) `annotations.py`: when the composed `corroborate_definition` reports `non_null_sampled == 0`, treat the field as not-checked (a TEXT-family claim on an all-NULL column is not corroborated by zero rows). Both shipped with a red-first test that fails on the pre-fix code.

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| usage adapter | **build-new** seam, **compose** `build_from_sqlite`'s provided-def/confidence derivation | The builder exists; usage is an additive sidecar block on it |
| corroboration on R5 corrections | **compose** `corroborate_definition` | Human corrections are provided_defs — the gate already handles them |
| R5 redaction | **reuse** `scripts/helpdesk/logit.py::redact_evidence` | The privacy engine is done (HD-2 / EVAL-16) |
| CSV I/O | **reuse** stdlib `csv` | No new dep; openpyxl is a future adapter boundary if Excel is wanted |
| the two hardening fixes | **extend** existing per-field `checked` shape | Run D's F1 fix is the template |

## Risks / Trade-offs

- [Usage zero-fills instead of omitting] → E-D1 + a test: a table with no stats has NO `usage` key (not zeros).
- [A human correction bypasses corroboration] → E-D2 + a test: a conflicting `proposed_definition` is ⚠/downgraded through `corroborate_definition`, not accepted.
- [Column drift in the round-trip] → E-D4 pinned test.
- [Redaction leak of sample data in the review CSV] → E-D3 default `summary` allow-list + a test.
- [check_separation] → additive within `scripts/`, no new module; the run confirms it green (26).

## Migration Plan

Additive: engine subcommands + an injected adapter + two small per-field hardening edits. Version 3.52.0 → 3.53.0. Rollback = git revert of the release commit. A dictionary built without a usage source, and a repo that never runs the review, are byte-unchanged.

## Open Questions

None blocking — §3b R4/R5 specify the shapes; SQLite-has-none resolves the test posture (FakeUsageStatsSource offline).
