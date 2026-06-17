---
name: data-dictionary
description: Use when a codebase consumes data tables/databases and you need a self-contextualizing data dictionary — given code and/or documentation that reference data, derive the data model, define every field, and record provenance + corroboration. Branches by input type (code / documentation / direct user input); recursively follows objects that mask DB connections to find table references; when context is exhausted and a database is REACHABLE, performs live inspection (schema read + ~100-row sampling) to infer grain + field meaning; produces the standard artifact DATA_DICTIONARY_MAP.md (+ data-dictionary.json sidecar) with a by-field/by-table reference map and a relational/blend map. Runs during initial codebase exploration (after codebase + integration mapping) and is kept current whenever agents do database development. The deterministic pieces live in scripts/data_dictionary/data_dictionary.py; this skill is the contract.
---

# Data Dictionary (DD-1 … DD-18)

When an application consumes data, "what does this field mean, where does it come
from, and which code touches it" is the question this skill answers. It builds a
**data dictionary** by self-contextualizing from whatever inputs exist — code,
documentation, direct user statements — and, when a database is reachable,
confirming everything against the live data itself.

Source of truth for the deterministic machinery — SQLite introspection, ~100-row
sampling, grain/field inference, the fixed provenance vocabulary, corroboration,
the reference/relational map builders, and the serializer — is
**`scripts/data_dictionary/data_dictionary.py`** (stdlib-only, unit-tested). This
skill is the *contract + the LLM-judgment workflow*; that module is the *machine*.
Do not re-implement the deterministic pieces in prose — call the module.

## The standard artifact (DD-7, DD-16)

The skill always writes ONE standard-named pair so that initialization can check
whether it already exists:

- `docs/DATA_DICTIONARY_MAP.md` — the human view (`last_built` frontmatter).
- `docs/data-dictionary.json` — the machine sidecar (`schema: data-dictionary/v1`).

The artifact contains: the DB name (when known), the schema name (when
inferable), every table with its inferred **grain**, every field with a
**definition + type + provenance + confidence + corroboration**, an **extensive
by-field / by-table reference map** (which code calls which tables/fields), and a
**relational / blend map** — including non-DB relations expressed only in code
(e.g. census data merged onto individuals on zip code).

## Sequencing (DD-6, DD-16)

Run AFTER codebase mapping and integration mapping: **map the codebase →
map the integrations → build the data dictionary** for the data the application
consumes. During initial codebase exploration (Phase −1 of the pipeline), check
whether `docs/DATA_DICTIONARY_MAP.md` already exists and is fresh before
rebuilding (same freshness discipline as the other `*_MAP.md` artifacts).

## Workflow

### Step 1 — Branch by input type (DD-2)

- **Code present** → Step 2 (code analysis).
- **Documentation present** → Step 3 (doc analysis).
- **Direct user input** (the user states definitions) → seed the field list with
  those definitions as provenance `direct-user-input` (still corroborated in
  Step 4).
Any combination is valid — run every applicable step and merge.

### Step 2 — Code analysis (DD-3, DD-4)

Find table references by searching the code **iteratively and recursively**:
follow objects that mask/wrap database connections (ORM models, query builders,
repository/DAO layers, connection factories) until you reach where queries or
data-access calls are actually generated — that is where the data model lives.
When the code alone is insufficient, read the code itself, README files, and
inline comments to infer which fields and tables are pulled (provenance
`direct-code-comment` for anything a comment states). Record every site as a code
reference `{file, line, table, field}` — these become the by-field/by-table
reference map via `build_reference_map(...)`. Capture code-only joins (e.g. a
merge on zip) as `code_joins` for the relational/blend map.

### Step 3 — Documentation analysis (DD-5)

Examine provided documentation, documentation found in the codebase, and
user-provided inputs for field information. Map any definitions found onto the
current field list, **extending** the list where new fields are discovered.

### Step 4 — Field definition: two passes + corroboration (DD-8 … DD-14)

1. **First pass — provided context (DD-8).** Start from any directly supplied
   definitions (user input / code comments). Pass these to the engine as
   `provided_defs` (`{"table.field": {definition, provenance, claims_key?, expected_type?}}`).
2. **Second pass — live inspection (DD-9, DD-10).** When provided context is
   exhausted AND a database is **reachable**, connect and read the schemas/tables;
   sample roughly the first 100 records per table and examine the data row-wise.
   The engine's SQLite adapter (`build_from_sqlite`) does this end-to-end; other
   engines follow the same shape with their own driver + credentials.
3. **Dimensionality / grain inference (DD-11).** `infer_grain(...)` derives the
   grain (one-row-per-what) from the declared PK + sampled uniqueness (e.g. a
   "Customers" table: hypothesize customer-level, read the columns, conclude the
   true grain — customer vs. customer/store-location level).
4. **Field inference (DD-12).** `infer_field(...)` reasons from name + declared
   type + sampled values (e.g. `address1/2/3` → address lines; `zip5` whose values
   are all 5-digit → "5-digit ZIP code"; `*_id` → identifier). Surface the
   evidence used.
5. **Provenance (DD-13).** Every field stores a sourcing indicator from the
   FIXED vocabulary — `direct-user-input`, `direct-code-comment`, `inference`,
   `live-data` — defined once in `PROVENANCE_TYPES`. Extend it only in the engine.
6. **Corroboration (DD-14).** EVERY provided definition is verified against the
   real data, not only key claims. `corroborate_definition(...)` checks each
   `provided_defs` entry: a `claims_key` entry routes to `corroborate_key_claim(...)`
   (the classic conflict — the user says a table keys on `customer_id`, but the
   data shows it keys on a hash/name, so the dictionary reflects the REAL field),
   and an `expected_type` entry is checked against the sampled values' actual
   dtype/format (e.g. "this column is a boolean flag" on a free-text column is
   flagged). Any conflict surfaces (⚠) and downgrades confidence to low.

### Step 5 — Persist (DD-15)

`write_artifact(...)` writes the standard pair into `docs/`. If **MemPalace is
available**, mine the artifact into it per `mempalace-integration`
(`mempalace --palace <palace> mine docs/DATA_DICTIONARY_MAP.md --wing <wing>`),
and include it in the documentation set. MemPalace-absent → the on-disk artifact
is the deliverable; persistence is best-effort.

## Maintenance discipline (DD-17, DD-18)

Whenever an agent does **database development** — any operation that adds/modifies
tables, data types, column names, or relations — it MUST update
`DATA_DICTIONARY_MAP.md` in the same change (rebuild the affected tables via the
engine, re-corroborate). And every agent verifies, before claiming done, that its
documentation — including the data dictionary — is up to date. This is the data
counterpart of the existing `documentation-currency` discipline.

## Honest boundary — live inspection needs a reachable DB (DD-9/DD-10)

Live schema read + 100-row sampling require a database that is actually
**reachable** with valid credentials. When no database is reachable, build with
`build_from_inputs(...)` (the no-DB path) from code + docs + provided context
only: every field is marked `inference` / `direct-*` (never `live-data`), and the
artifact's `live_inspection` block records `ran: false` with the reason — the
serializer renders this as a "Live inspection: NOT run" line so the artifact
itself states that live inspection did not run. Do NOT fabricate sampled data or
claim `live-data` provenance for a database that was never connected — an
un-inspected field is honestly `inference`, not a guess dressed as fact. Likewise
an inferred key seen in only a handful of sampled rows (`< MIN_KEY_SAMPLE`) is
hedged in the grain string and never asserted above `medium` confidence — N
distinct values in N rows is not proof of a key.

## Cross-references

- `scripts/data_dictionary/data_dictionary.py` — the deterministic engine (the machine).
- `skills/data-lineage-mapping` — the CDLG asset-lineage layer (functions ↔ data assets); complementary: this skill defines the FIELDS, that one traces who reads/writes them.
- `skills/intake-and-mapping` — Phase −1 sequencing (codebase → integration → data dictionary).
- `skills/mempalace-integration` — the persistence hook (DD-15).
- `skills/documentation-currency` — the sibling currency discipline the maintenance rule (DD-17/18) mirrors.
