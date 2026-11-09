# Design: data-annotations (Run D)

## Context

Run D of the proposal (§3b R3 + §7.4). The design is specified there; this binds it to the build. Constraints: additive-only (a repo with no annotations behaves identically), suite zero-new-failures (baseline 6878/0/6), the house instruction-compliance + doc-currency gates, the evidence stack (schema v7 paired review). The knowledge-server change is additive within DictionarySource (which already reads `docs/data-annotations/` from Run A) — no new `services/` module, so `check_separation` is unaffected. Decision D5 (user-delegated): data objects first; interaction/bulk-verify confirmations as a documented-but-deferred second step.

## Decisions

- **D-D1 — per-user files, deng's vocabulary as-is.** `docs/data-annotations/<user>.json`, typed `note` / `quality_flag ∈ {TRUSTED, STALE, INCOMPLETE, EXPERIMENTAL}` / `deprecation`, anchored to `table` / `table.field` ids. Per-user = never-merge-conflict (deng's genuinely good pattern, adopted). Validate-on-write + atomic write (the house pattern from `data_dictionary.py`).
- **D-D2 — corroborate factual claims, store opinions as-is (the CT6 inversion).** An annotation with a `claims_key` / `expected_type` / definition is a CLAIM → `corroborate_definition` on ingest (⚠ + downgrade on conflict). A `note` / `quality_flag` / `deprecation` is an OPINION → stored as-authored, but a `quality_flag` still TRAVELS with the served data. This is the line that keeps the store from accumulating confidently-wrong tribal knowledge.
- **D-D3 — merge-at-query in the server, additive.** `dictionary_source.py::get_table_details` (and `search_dictionary`) merge the annotations into the response with corroboration status + `quality_flag`; the freshness envelope still applies. A no-annotations repo is byte-unchanged.
- **D-D4 — a dedicated `data-annotations` skill (skills 52→53).** Consistent with `warehouse-sql-mining` being a skill-as-engine-contract; cleaner capability boundary + discoverability than folding into `data-dictionary`. It carries the gate-integrity rule (served memory INFORMS, never SKIPS a gate) and the deferred-second-step note.
- **D-D5 — gate integrity is the load-bearing invariant.** Served/recalled annotation memory must INFORM a per-run gate, never auto-satisfy it. A test pins this: an annotation cannot flip a gate to satisfied. This is the leg-2-generalization safety rule reviewable in isolation (why D5 does data objects first).

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| `scripts/data_dictionary/annotations.py` | **build-new** (the store engine), **compose** `corroborate_definition` | The store is new; the corroboration inversion exists and is reused, never re-implemented |
| the annotations dir + fixture | **reuse** `docs/data-annotations/` (already read by DictionarySource) + the Run A fixture `tests/fixtures/knowledge_server/data-annotations/analyst.json` | The read path exists from Run A; Run D adds write + corroborate + merge-surface |
| server merge-at-query | **extend** `services/knowledge_server/dictionary_source.py` (additive) | The source already reads the dir; the merge into the tool responses is the addition |
| recall | **compose** `skills/mempalace-integration` mine path | Mining exists; annotations ride it |
| `data-annotations` skill | **build-new** on the skill-as-engine-contract shape | New capability surface |

## Risks / Trade-offs

- [A factual annotation bypasses corroboration] → D-D2 + a test: a conflicting factual claim is flagged ⚠, not accepted. This is the adversary's #1 target (same class as Run C's corroboration gate).
- [Served memory silently satisfies a gate] → D-D5 + a test pinning that annotation memory informs, never skips, a gate.
- [Merge-at-query changes a no-annotations response] → D-D3 additive; a test asserts byte-unchanged behavior with no annotations.
- [check_separation] → additive within DictionarySource, no new module; the run confirms it green.

## Migration Plan

Additive: a new `scripts/` engine module + a new skill + an additive server merge. Version 3.51.0 → 3.52.0. Rollback = git revert of the release commit. A repo with no annotations behaves identically.

## Open Questions

None blocking — §3b R3 specifies the store; D5 resolves the scope (data objects first, confirmations deferred).
