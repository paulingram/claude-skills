# Tasks: jsonld-emitter (Run F)

TDD throughout (red-first, captured under `.architect-team/red-runs/jsonld/`); stdlib-only (`json` only — no rdflib/pyld); both encodings green; instruction-compliance zero findings; no `": "` in any new frontmatter.

## 1. The JSON-LD emitter (owner: jsonld teammate)

- [ ] 1.1 Red-first tests + fixtures: minimal `tests/fixtures/jsonld/data-dictionary.json` (a table with fields carrying definition/provenance/confidence, one with a `usage` block) + `tests/fixtures/jsonld/lineage-graph.json` (a `function` that `reads` one `data_asset` and `writes` another, plus a `calls`/`serves` edge). Assert: a table → `schema:Dataset` with `variableMeasured` per field (definition/provenance/confidence preserved); a `reads` → `prov:used`, a `writes` → `prov:wasGeneratedBy`; an edge kind absent from the graph yields NO relation; an empty input → empty valid `@graph`. Capture the reds.
- [ ] 1.2 Implement `scripts/data_dictionary/jsonld_export.py` (stdlib `json`): `export_dictionary_jsonld` / `export_lineage_jsonld` / `export_combined` (`@context` + `@graph`), `validate_jsonld` (resolvable @context; every node @id + @type; unique @ids; referential closure), a round-trip helper, and the `export-jsonld` CLI. Only-emit-what-exists; no fabricated triples; provenance/confidence verbatim. NO 3rd-party import; NO new services module.

## 2. The two folded corroboration fast-follows (owner: jsonld teammate)

- [ ] 2.1 Red-first (F1): `scripts/data_dictionary/data_dictionary.py::_usage_block` returns `None` when read_recency + write_recency + row_volume are all `None`/absent → the block is OMITTED (not an all-`None` block). Capture the red (a non-`None` empty mapping attaches an all-None block pre-fix), then fix. Run E's usage tests stay green.
- [ ] 2.2 Red-first (F2): `scripts/sql_mining/sql_mining.py::corroborate_mined_claim` rows-path treats `non_null_sampled == 0` as not-checked. Capture the red (a text candidate on an all-NULL column with rows supplied is accepted pre-fix), then fix. Run C's 29 sql-mining + Run E's tests stay green.

## 3. Docs, review, release (orchestrator + reviewers)

- [ ] 3.1 `skills/data-dictionary/SKILL.md` gains a short "JSON-LD export" note (the emitter, the shapes, the no-consumer boundary). Extend; NO new skill/command/agent (R6 moves no count except tests). Valid frontmatter, no `": "`.
- [ ] 3.2 Paired review (independent task-reviewer + adversarial — attack: a fabricated triple not in the sidecars; invalid JSON-LD (missing @context/@id/@type, a dangling @id reference); an invented edge kind; an over-claim of a live consumer integration; a hardening fix that doesn't bite). Producer != checker, evidence-schema-v7, `validate_evidence` 0 gaps.
- [ ] 3.3 Full suite zero-new-failures vs baseline 6955/0/6 (both encodings); `check_separation` green (unchanged, 26); a demo captured (dictionary+lineage fixtures → valid JSON-LD → validate + round-trip; empty input → empty valid graph; both hardening reds). check-can-fail verdict for the new test file.
- [ ] 3.4 Version 3.53.0 → 3.54.0 (plugin + marketplace JSONs); dispatch-banner pin lockstep; CHANGELOG entry per rubric (suite-total line); README spotlight-swap to v3.54.0 + RELEASE_HISTORY append + timeline; CLAUDE.md (header + recent-releases digest, drop v3.51.0 to keep top-3) + CODEBASE_MAP + INTEGRATION_MAP + CAPABILITY_INDEX current.
- [ ] 3.5 completion audit exit 0; commit (author override Paul Ingram); merge --no-ff to main per deploy config; mark complete. FINAL run report: Runs A–F all shipped; the D7 no-consumer boundary stated plainly for the user to veto/defer if desired.
