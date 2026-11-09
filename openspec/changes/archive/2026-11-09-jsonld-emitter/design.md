# Design: jsonld-emitter (Run F)

## Context

Run F of the proposal (§7.6, R6) + the two Run E corroboration fast-follows. Constraints: additive within `scripts/data_dictionary/` (a new `jsonld_export.py` + two small hardening edits to `data_dictionary.py` and `sql_mining.py`), stdlib-only (`json` only — no `rdflib`, no `pyld`), suite zero-new-failures (baseline 6955/0/6), the house instruction-compliance + doc-currency gates, the evidence stack (schema v7 paired review). No new `services/` module → `check_separation` unaffected. The D7 conditionality is resolved to build-with-boundary (see proposal); the honest boundary is a first-class deliverable.

## Decisions

- **F-D1 — standard, stdlib-only JSON-LD; no 3rd-party.** JSON-LD is just JSON with an `@context`; the emitter builds the dict and serializes with stdlib `json`. NO `rdflib` / `pyld` (would break `check_separation` if it were a services module; here it's scripts-tier, but stdlib-only keeps the CT6 discipline). The `@context` maps prefixes to the real vocabulary URLs (`schema: https://schema.org/`, `dcat: http://www.w3.org/ns/dcat#`, `prov: http://www.w3.org/ns/prov#`, `ct6:` for the CT6-specific provenance/confidence annotations that have no standard term).
- **F-D2 — catalog → schema.org/DCAT, lineage → PROV-O.** Dictionary tables → `schema:Dataset` (a `dcat:Catalog` wraps them); each field → `schema:variableMeasured` → a `PropertyValue` with `propertyID` = the field name, `description` = the definition, and `ct6:provenance` / `ct6:confidence` for the CT6 fidelity metadata (usage blocks, when present, ride as `ct6:usage`). Lineage → PROV-O: a `data_asset` node → `prov:Entity`, a `function`/`endpoint` node → `prov:Activity`; a `reads` edge → the activity `prov:used` the entity; a `writes` edge → the entity `prov:wasGeneratedBy` the activity. ONLY edges present in the graph are emitted (a poisoned/absent edge yields no triple) — the same walk-only-what-exists discipline the knowledge server's `find_call_paths` uses. `calls`/`serves`/`modifies`/`originates`/`serves_route` map to documented PROV/`ct6:` relations; an unknown edge kind is skipped-with-note, never invented.
- **F-D3 — structural validation + round-trip is the correctness bar (no live consumer).** `validate_jsonld(doc)` asserts: a resolvable `@context` (a mapping or list), every `@graph` node carries an `@id` + `@type`, `@id`s are unique, and every referenced `@id` (edge endpoints, `variableMeasured` refs) resolves to a node in the graph (referential closure). A round-trip test (`json.dumps → json.loads → re-derive the source facts`) proves no data is lost or fabricated. This is the honest substitute for a live-consumer ingestion — the emitter is verified against the SHAPES, and the boundary says so.
- **F-D4 — emit only what the sidecars contain.** No triple is emitted that isn't grounded in a dictionary field or a lineage node/edge. Provenance/confidence travel verbatim. An empty/absent dictionary or graph yields an empty (but valid) `@graph`, never fabricated content. This is the emitter's analogue of the corroboration discipline.
- **F-D5 — the two hardening fixes are red-first, per-field.** (F1) `_usage_block`: return `None` when `read_recency`, `write_recency`, and `row_volume` are all `None`/absent, so a non-`None` empty stats mapping OMITs the block (engine-enforced, not only adapter-enforced). (F2) `corroborate_mined_claim` rows-path: when the sampled rows give `non_null_sampled == 0` for the candidate's column, treat it as not-checked (the guard its two siblings — annotations F-A5, `_corroborate_correction` — now carry). Both ship with a red-first test that fails on the pre-fix code; Run E's + Run D's + Run C's tests stay green.

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| `jsonld_export.py` | **build-new** | New serialization surface; no existing JSON-LD emitter |
| the input shapes | **reuse** `data_dictionary.py`'s dict output + `hooks/lineage_graph.py`'s node/edge vocabulary | The sidecars are machine-complete; the emitter reads, never re-derives |
| the walk-only-present-edges discipline | **compose** the pattern `services/knowledge_server/map_source.py::find_call_paths` established | Same "never invent an edge" rule |
| the two hardening fixes | **extend** the per-field `checked` shape (Run D F1 / Run E) | Established template |
| fixtures | **build-new** minimal `data-dictionary.json` + `lineage-graph.json` under `tests/fixtures/jsonld/` | The CT6 repo ships no sidecars (Run A's honest boundary) |

## Risks / Trade-offs

- [Fabricated triples not in the sidecars] → F-D4 + a test: every emitted node/edge traces to a source field/node/edge; an empty input yields an empty valid `@graph`.
- [Invalid JSON-LD a consumer would reject] → F-D3 `validate_jsonld` (context + @id/@type + referential closure) + round-trip.
- [Over-claiming a live integration] → the boundary: shapes validated, NO consumer wired/verified; the CHANGELOG + skill state it.
- [check_separation] → additive within `scripts/`, no new module; the run confirms it green (26).

## Migration Plan

Additive: a new `scripts/` module + two small hardening edits + a skill note. Version 3.53.0 → 3.54.0. Rollback = git revert. Nothing else consumes the emitter yet, so removing it affects nothing.

## Open Questions

None blocking — the shapes are standard (schema.org/DCAT/PROV-O); the no-consumer posture is the resolved D7 boundary.
