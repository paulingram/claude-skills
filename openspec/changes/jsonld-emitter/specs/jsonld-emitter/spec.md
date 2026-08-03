# jsonld-emitter

## ADDED Requirements

### Requirement: A stdlib JSON-LD emitter serializes the dictionary + lineage sidecars
A new `scripts/data_dictionary/jsonld_export.py` (stdlib-only, `json`) SHALL emit `docs/data-dictionary.json` + `lineage-graph.json` as JSON-LD. Dictionary tables SHALL map to `schema:Dataset` nodes (fields → `schema:variableMeasured` `PropertyValue`s carrying the definition + `ct6:provenance` + `ct6:confidence`); the lineage graph SHALL map to PROV-O (`data_asset` → `prov:Entity`, `function`/`endpoint` → `prov:Activity`, `reads` → `prov:used`, `writes` → `prov:wasGeneratedBy`). The `@context` SHALL bind the real vocabulary URLs. Only edges present in the graph SHALL be emitted; an unknown edge kind SHALL be skipped, never invented.

#### Scenario: A dictionary table becomes a schema:Dataset with its fields
- **WHEN** `export_dictionary_jsonld` runs on a dictionary with a table and fields
- **THEN** the output `@graph` has a `schema:Dataset` node for the table whose `variableMeasured` lists each field with its definition, provenance, and confidence preserved

#### Scenario: A lineage reads/writes edge becomes a PROV-O relation
- **WHEN** `export_lineage_jsonld` runs on a graph with a `function` that `reads` a `data_asset` and `writes` another
- **THEN** the output has the function as a `prov:Activity` with `prov:used` the read entity and the written entity `prov:wasGeneratedBy` the activity — and no relation for an edge kind absent from the graph

### Requirement: The emitted JSON-LD is structurally valid and round-trips without fabrication
`jsonld_export.py` SHALL provide `validate_jsonld(doc)` asserting a resolvable `@context`, every `@graph` node carries an `@id` and `@type`, `@id`s are unique, and every referenced `@id` resolves to a node (referential closure). The emitter SHALL emit only content grounded in the sidecars — an empty/absent input yields an empty but valid `@graph`, never fabricated triples. A round-trip SHALL preserve the source facts.

#### Scenario: The emitted document validates and round-trips
- **WHEN** a combined export is validated and re-parsed
- **THEN** `validate_jsonld` returns no errors and the re-parsed document yields back the same tables/fields/lineage facts (no loss, no fabrication)

#### Scenario: An empty catalog yields an empty valid graph
- **WHEN** the dictionary and graph are empty or absent
- **THEN** the output is a valid JSON-LD document with an empty `@graph` (no invented nodes)

### Requirement: The corroboration gate accepts a claim only when its exact field was checked (folded fast-follows)
`scripts/data_dictionary/data_dictionary.py::_usage_block` SHALL return `None` when every usage sub-value is `None`/absent (so an empty stats mapping OMITs the block, not attaches an all-`None` one). `scripts/sql_mining/sql_mining.py::corroborate_mined_claim`'s rows-path SHALL treat a candidate column with `non_null_sampled == 0` as not-checked (the guard its sibling gates carry).

#### Scenario: An all-None usage mapping omits the block
- **WHEN** a usage source returns a mapping whose read/write recency and row volume are all `None`
- **THEN** no `usage` block is attached (the table entry is as if the source returned `None`)

#### Scenario: A mined claim on a zero-non-null sampled column is not accepted
- **WHEN** `corroborate_mined_claim` is given rows for a candidate whose column has `non_null_sampled == 0`
- **THEN** the candidate is treated as not-checked (not accepted as corroborated)
