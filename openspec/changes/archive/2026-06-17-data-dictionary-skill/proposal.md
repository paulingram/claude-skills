## Why

CT6-6 (the Claude Team 6 program) §1 asks for a self-contextualizing **data dictionary** capability (DD-1 … DD-18): given code and/or documentation that reference data tables/databases, derive the data model, define every field, and record where each definition came from (provenance) plus whether it holds up against the real data (corroboration). The repo already has the `*-mapping` skill family + the `docs/*_MAP.md` artifact convention + `mempalace-integration`; this change adds the missing data-layer member reuse-first, with the deterministic parts as a stdlib-only engine and the LLM-judgment workflow as the skill contract (the same machine/contract split as `lineage_graph.py` ↔ `data-lineage-mapping`). This is component 1 of the in-repo CT6-6 tier.

## What Changes

- **New deterministic engine** — `scripts/data_dictionary/data_dictionary.py` (stdlib-only): SQLite introspection + ~100-row sampling (DD-9/10), grain inference (DD-11), field inference (DD-12), the FIXED provenance vocabulary `direct-user-input` / `direct-code-comment` / `inference` / `live-data` (DD-13), value-level corroboration of EVERY provided definition — key claims AND type claims (DD-14), the by-field/by-table reference map + the relational/blend map incl. non-DB code joins (DD-7), and the `DATA_DICTIONARY_MAP.md` (+ `data-dictionary.json`) serializer (DD-7/16). (REQ-001)
- **New skill contract** — `skills/data-dictionary/SKILL.md`: branch by input type (code / docs / direct input), recursive code analysis that follows objects masking DB connections, doc analysis, sequencing AFTER codebase + integration mapping with the standard-name freshness check, MemPalace persistence (DD-15), and the maintenance discipline mirroring `documentation-currency` (DD-17/18). (REQ-002)
- **Honest live-DB boundary** — live inspection needs a reachable DB; the no-DB `build_from_inputs(...)` path never marks a field `live-data`, the artifact's `live_inspection` block records `ran: false`, and a small-sample inferred key (`< MIN_KEY_SAMPLE`) is hedged below `high`. (REQ-003)
- **Reuse-first + docs/version currency** — modelled on the `*-mapping` family; complementary to `data-lineage-mapping`; version bump to 3.17.0 and the documentation-currency inventory brought current. (REQ-004)
- **Tests** — `tests/test_data_dictionary.py` (deterministic units + the local-SQLite end-to-end dogfood + the adversarial-review remediation pins); suite green both encodings. (REQ-005)

## Capabilities

### New Capabilities

- `data-dictionary` — build a self-contextualizing data dictionary (field definitions + provenance + corroboration + reference/relational maps) from code/docs/live DB, as a standard `DATA_DICTIONARY_MAP.md` artifact.

### Modified Capabilities

- None removed. The skill inventory grows by one (41 → 42) and the documentation-currency inventory + version metadata are brought current; no existing skill/agent/command behavior changes.
