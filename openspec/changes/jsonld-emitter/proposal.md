# Proposal: jsonld-emitter (Run F)

## Why

Run F of `docs/proposals/DATA_ENG_LANE_AND_CROSS_POLLINATION.md` §7.6 (R6) — the last run of the data-engineering lane build sequence. R6 is a pure stdlib serializer that emits the two machine-complete sidecars CT6 already produces — `docs/data-dictionary.json` (the catalog) + `lineage-graph.json` (the lineage) — as **JSON-LD** for the external catalog / lineage ecosystems Stage 6 of `data-engineering-exploration` names (OpenLineage / Marquez / DataHub / dbt).

**The D7 conditional, adjudicated.** The proposal marks R6 "build ONLY when a named external consumer exists; otherwise it stays in the backlog deliberately." No external consumer is wired in this repo. It is built here anyway because the run directive is to complete every run of the proposal; it ships with that boundary stated PLAINLY (below), not hidden. The emitter is low-effort and pure/deterministic, so the cost of building-now vs deferring is small, and a wired consumer later needs only to point at the output.

**Two folded corroboration fast-follows.** Run E's adversary logged two same-class "claim accepted without its exact field checked" residuals, both non-blocking and unreachable via shipped code. Run F closes them so the marathon ends with no known corroboration edges open: (F1) `data_dictionary.py::_usage_block` should return `None` (→ OMIT) when every usage sub-value is `None`, so a misbehaving adapter returning a non-`None` empty mapping can't attach an all-`None` `usage` block; (F2) `sql_mining.py::corroborate_mined_claim`'s rows-path should carry the `non_null_sampled == 0` guard its two sibling gates now have.

## What Changes

- **R6:** a new `scripts/data_dictionary/jsonld_export.py` — pure stdlib. `export_dictionary_jsonld` maps each dictionary table to a `schema:Dataset` (fields → `schema:variableMeasured` `PropertyValue`s carrying the definition + provenance + confidence); `export_lineage_jsonld` maps the lineage graph to **PROV-O** (`data_asset` → `prov:Entity`; `function`/`endpoint` → `prov:Activity`; `reads` → `prov:used`, `writes` → `prov:wasGeneratedBy`, walking ONLY edges present in the graph); `export_combined` emits one JSON-LD document (`@context` + `@graph`). Structural validators (`validate_jsonld`: a resolvable `@context`, every node `@id` + `@type`, unique + referentially-closed `@id`s) + a round-trip (`serialize → parse → semantic equivalence`). A CLI (`export-jsonld`).
- **Hardening:** the F1 + F2 one-line per-field fixes, each red-first.
- **Docs:** `skills/data-dictionary/SKILL.md` gains a short JSON-LD-export note (extend; NO new skill/command/agent — R6 "moves no count except tests"). Version 3.53.0 → 3.54.0; the house doc-currency + CHANGELOG obligations.

## Impact

- Additive within `scripts/` (stdlib-only, `json` only); NO new services module / skill / command / agent — `check_separation` unaffected. Suite: zero NEW failures vs the 6955/0/6 baseline; +N tests (a new `test_jsonld_export.py` + fixtures under `tests/fixtures/jsonld/`, since the CT6 repo ships no sidecars). HONEST BOUNDARY: the emitter produces JSON-LD conforming to the schema.org / DCAT / PROV-O SHAPES, structurally validated + round-trip-parsed — **no live external-consumer ingestion (OpenLineage/Marquez/DataHub) is verified; none is wired.** It emits only what the sidecars contain — no fabricated triples, provenance preserved.
