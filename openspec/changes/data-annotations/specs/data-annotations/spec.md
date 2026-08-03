# data-annotations

## ADDED Requirements

### Requirement: A per-user, git-shared annotation store on data objects exists
A new `scripts/data_dictionary/annotations.py` engine SHALL manage per-user annotation files `docs/data-annotations/<user>.json` in the target repo — team-shared via git, per-user so they never merge-conflict. Each annotation SHALL be anchored to a `table` or `table.field` id (from `docs/data-dictionary.json`) and typed with deng's vocabulary: `note` (free text), `quality_flag ∈ {TRUSTED, STALE, INCOMPLETE, EXPERIMENTAL}`, or `deprecation`. Writes SHALL be validate-on-write + atomic (the house pattern). The engine SHALL be CLI-driven (no new agent).

#### Scenario: A per-user annotation is written and read back
- **WHEN** a user annotates `dbo.Orders.Total` with `quality_flag: STALE` and a note
- **THEN** it is written atomically to `docs/data-annotations/<user>.json`, validated against the vocabulary, and reads back anchored to that field

#### Scenario: Per-user files do not merge-conflict
- **WHEN** two users each annotate different (or the same) objects in their own files
- **THEN** their files are independent (`<userA>.json`, `<userB>.json`) and a git merge of both does not conflict

### Requirement: Factual annotation claims are corroborated on ingest, not transcribed
An annotation that carries a FACTUAL claim (a `claims_key` / `expected_type` / a definition) SHALL route through `scripts/data_dictionary/data_dictionary.py::corroborate_definition` on ingest — flagged ⚠ and confidence-downgraded on conflict with a corroborated definition, exactly like a provided definition. Non-factual annotations (`note`, `quality_flag`, `deprecation`) SHALL be stored as authored (opinions, not claims). The store SHALL never present a factual annotation as established truth until corroborated.

#### Scenario: A conflicting factual annotation is flagged, not accepted
- **WHEN** a factual annotation claims a field's type/definition that conflicts with an existing corroborated definition
- **THEN** it is flagged ⚠ and confidence-downgraded through `corroborate_definition`, NOT silently accepted as truth

#### Scenario: A quality_flag travels with the data as an opinion
- **WHEN** a field is annotated `quality_flag: EXPERIMENTAL`
- **THEN** the flag is stored as-authored (not corroborated — it is an opinion) and travels with the served field

### Requirement: The knowledge server merges annotations at query time
`services/knowledge_server/`'s `get_table_details` (and `search_dictionary` where relevant) SHALL MERGE the per-user annotations at query time — surfacing, per table/field, the merged `note`s / `quality_flag`s / `deprecation`s AND the corroboration status of any factual annotation — with the existing `{verdict, basis}` freshness envelope still applied. A repo with no annotations SHALL behave exactly as before (additive).

#### Scenario: get_table_details surfaces merged annotations
- **WHEN** `get_table_details` is called for a table whose fields carry annotations
- **THEN** the response includes the merged annotations (with quality_flag + corroboration status) alongside the table details, and still carries its freshness verdict

#### Scenario: No annotations means unchanged behavior
- **WHEN** a repo has no `docs/data-annotations/` files
- **THEN** `get_table_details` / `search_dictionary` return exactly what they returned before this change

### Requirement: A data-annotations skill is the engine's contract, and served memory informs the gate
A new `skills/data-annotations/SKILL.md` SHALL be the engine's contract — the store shape + the vocabulary, the corroborate-on-ingest inversion, the server merge-at-query, the mine-to-MemPalace recall path, and the GATE-INTEGRITY rule: served/recalled annotation memory INFORMS a per-run gate, it NEVER skips or auto-satisfies it (the D5 rule). It SHALL carry the compiled boilerplate/principles blocks + valid frontmatter (no `": "` in the description) → skills 52 → 53. The SECOND D5 step (persisting interaction/bulk-verify domain-gate confirmations as annotations) SHALL be documented as a deferred hook, not built.

#### Scenario: The skill states the gate-integrity rule
- **WHEN** `skills/data-annotations/SKILL.md` is read
- **THEN** it states that annotation memory informs but never skips a per-run gate, and that factual annotations are corroborated (not transcribed)

#### Scenario: Annotations are mined for recall
- **WHEN** the dictionary artifact is mined to MemPalace
- **THEN** the annotations are mined alongside it (recallable across runs), and the skill documents that recalled annotations inform, never auto-satisfy, a gate
