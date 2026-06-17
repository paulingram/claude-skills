# data-dictionary Specification

## Purpose
TBD - created by archiving change data-dictionary-skill. Update Purpose after archive.
## Requirements
### Requirement: REQ-001 — Deterministic data-dictionary engine (DD-7 … DD-14)

`scripts/data_dictionary/data_dictionary.py` SHALL be a stdlib-only engine that, given a SQLite database, introspects its schema, samples roughly the first 100 rows per table (DD-9/10), infers each table's grain from the declared PK + sampled uniqueness (DD-11), infers each field's meaning from its name + declared type + sampled values (DD-12), stamps every field with a provenance from the FIXED vocabulary `direct-user-input` / `direct-code-comment` / `inference` / `live-data` (DD-13), corroborates EVERY provided definition against the data — both key claims and type claims (DD-14), builds the by-field/by-table reference map + the relational/blend map including non-DB code joins (DD-7), and serializes the standard `DATA_DICTIONARY_MAP.md` (+ `data-dictionary.json` sidecar) (DD-7/16).

#### Scenario: end-to-end build corroborates a false key claim and a non-DB join

- **WHEN** the engine builds a dictionary from a SQLite DB where a user claims `customers` keys on `customer_id` but the data keys on a hash, and code joins census onto customers on zip
- **THEN** the grain reflects the REAL key (the hash), the `customer_id` claim is flagged (`agrees == false`) with confidence downgraded to `low`, and the code-join appears in the relational map as a `code-join`

#### Scenario: a wrong claimed type on a non-key field is flagged

- **WHEN** a provided definition gives `expected_type: "boolean"` for a free-text column
- **THEN** `corroborate_definition` returns `agrees == false` with a conflict and the field's confidence is `low`

### Requirement: REQ-002 — The data-dictionary skill contract (DD-1 … DD-6, DD-15 … DD-18)

`skills/data-dictionary/SKILL.md` SHALL be the LLM-judgment contract over the engine: it SHALL branch by input type (code / documentation / direct user input) (DD-2), recursively follow objects that mask DB connections to find table references (DD-3/4), map documentation definitions onto the field list (DD-5), sequence AFTER codebase + integration mapping with the standard-name freshness check (DD-6/16), persist into MemPalace when available via `mempalace-integration` (DD-15), and carry a maintenance discipline mirroring `documentation-currency` (DD-17/18). It SHALL NOT re-implement the deterministic pieces in prose.

#### Scenario: the contract documents the vocabulary, sequencing, and maintenance

- **WHEN** the skill body is read
- **THEN** it names all four provenance values, the standard artifact `DATA_DICTIONARY_MAP.md`, the after-codebase/integration sequencing, and a maintenance discipline citing DD-17 and DD-18

### Requirement: REQ-003 — Honest live-DB boundary

Live inspection (DD-9/10) requires a reachable database. The engine SHALL provide a no-DB `build_from_inputs(...)` path that NEVER marks any field `live-data` and records `live_inspection.ran == false` in the artifact; `build_from_sqlite` SHALL only stamp `live-data` on a field for which a non-null value was actually sampled; and an INFERRED key seen in fewer than `MIN_KEY_SAMPLE` sampled rows SHALL be hedged in the grain string and never asserted above `medium` confidence.

#### Scenario: no-DB path never fabricates live data

- **WHEN** `build_from_inputs(...)` builds a dictionary with no database
- **THEN** no field has provenance `live-data`, the grain is "unknown (no live inspection)", and the rendered artifact states "Live inspection ... NOT run"

#### Scenario: an all-null sampled column is inference, not live-data

- **WHEN** a sampled table has a column whose sampled values are all NULL
- **THEN** that column's provenance is `inference` while a sibling column with real values is `live-data`

### Requirement: REQ-004 — Reuse-first + docs/version currency

The capability SHALL be built reuse-first against the existing `*-mapping` family (artifact fits the `docs/*_MAP.md` convention; complementary to — not duplicating — `data-lineage-mapping`), Python SHALL stay stdlib-only, and the release SHALL bring the documentation-currency inventory current and bump the version to 3.17.0 (`.claude-plugin/plugin.json` + `marketplace.json`).

#### Scenario: version + inventory current

- **WHEN** the version files + CLAUDE.md + CODEBASE_MAP + README are read
- **THEN** the version is 3.17.0 and the skill count is 42 with a `data-dictionary` entry

### Requirement: REQ-005 — Tests green both encodings

A new test file SHALL cover the deterministic units, the local-SQLite end-to-end dogfood (the customer_id-vs-hash + census-on-zip example), and the adversarial-review remediation pins (non-key corroboration, empty table, all-null column, small-sample hedge, populated reference-map render, the no-DB path, the live_inspection block, and the quoted-identifier crash); the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_data_dictionary.py` present
- **THEN** there are zero failures

