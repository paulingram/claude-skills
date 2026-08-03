# usage-stats-review-roundtrip

## ADDED Requirements

### Requirement: Usage-grounded importance is measured, never fabricated
`scripts/data_dictionary/data_dictionary.py` SHALL accept an optional injected `UsageStatsSource` and attach a per-table `usage` block (`read_recency`, `write_recency`, `row_volume`) to the dictionary at provenance `live-data` — because it is MEASURED. SQL Server (`dm_*`) and Postgres (`pg_stat_*`) shapes SHALL be described; SQLite SHALL honestly return none. When the source has no stats for a table, the `usage` block SHALL be OMITTED — never zero-filled or emitted as `{}`.

#### Scenario: A table with live usage stats carries a measured usage block
- **WHEN** a `UsageStatsSource` returns read/write recency + row volume for a table
- **THEN** the dictionary's entry for that table carries a `usage` block with those values at provenance `live-data`

#### Scenario: Absent stats omit the block, never zero-fill
- **WHEN** the usage source returns `None` for a table (e.g. SQLite, or a table with no recorded activity)
- **THEN** the table's entry has NO `usage` key at all — not zeros, not an empty object

### Requirement: The dictionary supports an offline stakeholder review round-trip
`scripts/data_dictionary/data_dictionary.py` SHALL provide `generate-review` and `apply-review` subcommands. `generate-review` SHALL write a CSV (stdlib `csv`) of the fields most needing human review — `confidence == "low"` OR a corroboration conflict flag — sorted by R4 `usage.row_volume` when present, redacted through `scripts/helpdesk/logit.py::redact_evidence` (default `summary`). `apply-review` SHALL read the edited CSV and ingest each non-blank proposed definition as a `provided_defs` entry routed through `corroborate_definition` — a human correction is corroborated, not transcribed.

#### Scenario: The round-trip preserves every column (the pinned test)
- **WHEN** a review CSV is generated, one `proposed_definition` cell is edited, and `apply-review` is run
- **THEN** the correction lands on the EXACT `table.field` it was written from (no column drift) and passes through `corroborate_definition`

#### Scenario: A conflicting correction is corroborated, not blindly accepted
- **WHEN** an applied `proposed_definition` conflicts with a corroborated definition
- **THEN** it is flagged ⚠ and confidence-downgraded through `corroborate_definition`, NOT accepted as truth

#### Scenario: Review rows are redacted by default
- **WHEN** `generate-review` runs without `--privacy full`
- **THEN** the CSV carries only the allow-listed structured fields (sample data dropped) under the `summary` privacy level

### Requirement: The corroboration gate accepts a claim only when its exact field was checked
`scripts/sql_mining/sql_mining.py::corroborate_mined_claim` and `scripts/data_dictionary/annotations.py` SHALL accept a factual claim as corroborated ONLY when that exact field was inspected. A mined candidate whose field is absent from the corroborated-defs map with `rows=None` SHALL stay `inference`/not-accepted. An annotation whose composed corroboration reports `non_null_sampled == 0` SHALL be treated as not-checked (an all-NULL column does not corroborate a claim).

#### Scenario: A mined candidate not in the map with no rows is not accepted
- **WHEN** `corroborate_mined_claim` is called with a `corroborated_defs` map that lacks the candidate's field and `rows=None`
- **THEN** the candidate remains provenance `inference` / not-accepted (no per-map-presence bypass)

#### Scenario: A zero-non-null sample does not corroborate an annotation claim
- **WHEN** an annotation factual claim is corroborated against a column whose sample has `non_null_sampled == 0`
- **THEN** the claim is treated as not-checked (not accepted as corroborated truth)
