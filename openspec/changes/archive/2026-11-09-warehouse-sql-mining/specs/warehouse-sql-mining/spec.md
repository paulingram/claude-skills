# warehouse-sql-mining

## ADDED Requirements

### Requirement: A deterministic stdlib SQL-object mining engine exists
A new `scripts/sql_mining/sql_mining.py` SHALL ship a deterministic, stdlib-only engine that reads SQL objects (stored-procedure / view definitions, from a directory of `.sql` files or a supplied list) and extracts, via a minimal vendored T-SQL/ANSI pattern extractor (NOT a `sqlglot` dependency — decision D6): table-to-table read/write relationships, join shapes (`table.col = table.col`), filter predicates, and aggregate/ratio metric shapes (SUM / COUNT / AVG / ratio expressions). It SHALL be import-clean (stdlib only) so it lives cleanly in the `scripts/` tier and adds no dependency. It SHALL be CLI-driven like `scripts/data_dictionary/data_dictionary.py` (no new agent).

#### Scenario: Joins and metrics are extracted from a stored procedure
- **WHEN** the engine mines a fixture `.sql` object containing a join and a SUM/ratio metric
- **THEN** its output records the join (both sides as `table.col`) and the metric shape, each tagged with the source object

#### Scenario: Table read/write relationships are extracted
- **WHEN** the engine mines an object that SELECTs from table A and INSERTs/UPDATEs table B
- **THEN** it records a `reads` relationship on A and a `writes` relationship on B, attributed to the object

### Requirement: Parse-coverage stats are surfaced honestly
The engine's artifact SHALL carry parse-coverage statistics — objects **parsed** / **skipped** / **failed** — with a reason per skipped or failed object. A dialect-specific or malformed object that the vendored extractor cannot handle SHALL land in `skipped`/`failed` with its reason, NEVER be silently dropped or silently mis-parsed. This is the deng fidelity lesson made structural.

#### Scenario: An unparseable object is reported, not dropped
- **WHEN** the engine mines a directory containing a deliberately-unparseable / exotic-dialect object
- **THEN** that object appears in the `failed` (or `skipped`) list with a stated reason, the coverage stats reflect it, and the run does not crash or silently omit it

### Requirement: Every mined claim is corroboration-gated
Mined field / metric candidates SHALL enter the data dictionary as provenance **`inference`** (never anything stronger) and SHALL pass through `scripts/data_dictionary/data_dictionary.py::corroborate_definition` before any claim survives — flagged ⚠ and confidence-downgraded on conflict, exactly like a provided definition. Mined table-to-table read/write relationships SHALL become lineage **`data_asset`** node + `reads`/`writes` edge evidence via `hooks/lineage_graph.py` (using the existing node/edge kinds — no invented kinds). Nothing mined SHALL be presented as stronger than `inference` until corroborated.

#### Scenario: A mined claim conflicting with a corroborated definition is flagged, not accepted
- **WHEN** a mined field definition conflicts with an existing corroborated definition
- **THEN** the mined claim is flagged ⚠ and confidence-downgraded through `corroborate_definition`, NOT silently accepted as truth

#### Scenario: Mined relationships use only real lineage kinds
- **WHEN** mined read/write relationships are emitted as lineage evidence
- **THEN** they use only the existing `data_asset` node kind and `reads`/`writes` edge kinds present in `hooks/lineage_graph.py` — no invented node or edge kinds

### Requirement: A warehouse-sql-mining skill is the engine's contract
A new `skills/warehouse-sql-mining/SKILL.md` SHALL be the engine's contract — documenting what it extracts, the corroboration-gating rule, the parse-coverage-honesty rule, the CLI surface, and how the lane's D0 invokes it and feeds its output to `data-engineering-exploration` Stages 2–3. It SHALL carry the compiled boilerplate/principles blocks and valid frontmatter (no `": "` in the description).

#### Scenario: The skill documents the corroboration + fidelity rules
- **WHEN** `skills/warehouse-sql-mining/SKILL.md` is read
- **THEN** it states that mined content enters as `inference` and passes `corroborate_definition`, and that parse-coverage stats are surfaced and nothing is silently dropped

### Requirement: The lane's D0 wires the mining engine
`skills/data-eng-pipeline/SKILL.md` D0 SHALL be extended (additively) so that, when SQL objects are in scope, it invokes `scripts/sql_mining/sql_mining.py` and feeds the mined join/filter/metric evidence into `data-engineering-exploration`'s Stage 2–3 inputs — the R2-feeds-the-exploration wiring the proposal describes. This SHALL be additive prose; a data-eng run with no SQL objects behaves as before.

#### Scenario: D0 invokes mining when SQL objects are present
- **WHEN** the lane reaches D0 for an ask whose scope includes stored procedures / views
- **THEN** it invokes the mining engine and supplies the mined evidence as exploration Stage 2–3 input; when no SQL objects are in scope, D0 is unchanged
