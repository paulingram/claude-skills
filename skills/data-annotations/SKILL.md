---
name: data-annotations
description: Use when a codebase's team knowledge about data objects (tables and fields) needs a durable, structured, git-shared home instead of only prose recall. The persistent per-user annotation store on data objects, anchored to table/table.field ids from docs/data-dictionary.json and typed with a fixed vocabulary (note, quality_flag, deprecation). The CT6 inversion is load-bearing — a FACTUAL annotation (an expected_type/claims_key/definition) is corroborated on ingest through corroborate_definition and flagged on conflict, never transcribed as truth; opinions are stored as authored but a quality_flag still travels with the served field. Per-user files never merge-conflict; the knowledge server merges annotations at query time with corroboration status; recall INFORMS but never skips a per-run gate. The engine lives in scripts/data_dictionary/annotations.py; this skill is its contract.
---

# Data Annotations (Run D — the persistent annotation channel on data objects)

A warehouse's analysts know things about its tables that the schema does not say:
"this column is sparse before 2024", "use `total_minor_units` now", "TRUSTED —
reporting joins fan out here". Today that knowledge lives in prose recall and
tribal memory. This skill's engine gives it a **durable, structured, queryable,
git-shared home** — an annotation STORE on data objects — under the one discipline
that keeps CT6 from importing the deng toolkit's fidelity problem along with its
idea: **a factual annotation is corroborated on ingest, never transcribed as
truth**, and **served memory INFORMS a gate, it never skips one.**

Source of truth for the deterministic machinery — the per-user store, the
vocabulary, the corroborate-on-ingest gate, the atomic write, and the CLI — is
**`scripts/data_dictionary/annotations.py`** (stdlib-only, unit-tested). This
skill is the *contract*; that module is the *machine*. Do not re-implement the
store or the corroboration in prose — call the module. (Same relationship
`scripts/data_dictionary/data_dictionary.py` has to `data-dictionary` and
`scripts/sql_mining/sql_mining.py` has to `warehouse-sql-mining`.)

## The store (D-D1 — per-user, never a merge conflict)

Each user writes their OWN file `docs/data-annotations/<user>.json` in the TARGET
repo (team-shared via git). Per-user files are the point: two teammates annotating
the same table touch two different files, so a git merge of both **never
conflicts** — deng's genuinely good pattern, adopted as-is. Each annotation is
anchored to a `table` or `table.field` id from `docs/data-dictionary.json` and
typed with deng's vocabulary, taken as-is:

- **`note`** — free text (an opinion).
- **`quality_flag`** — one of `TRUSTED` / `STALE` / `INCOMPLETE` / `EXPERIMENTAL`
  (an opinion that still TRAVELS with the served field).
- **`deprecation`** — a "use X instead" pointer (an opinion).

Writes are **validate-on-write** (a bad `quality_flag`, an empty or malformed
anchor, or an annotation with no payload is REJECTED) and **atomic** (a same-dir
temp file + `os.replace`, the house pattern from
`scripts/memory/recall_hygiene.py`) — never a partial file, never a torn read.
The `<user>` → file mapping is **injective**: a username must be a filesystem-safe
identifier (start/end alphanumeric, `.`/`_`/`-` in the middle), VALIDATED not
sanitized — a collision-prone or path-unsafe name (`alice.`, `a/b`, `team:lead`,
all-special) is REJECTED with an actionable error rather than silently collapsed
onto another user's file, so the never-merge-conflict guarantee actually holds.
The engine is CLI-driven; there is **no new agent**.

## The CT6 inversion — corroborate-on-ingest (D-D2, the load-bearing rule)

An annotation that carries a FACTUAL claim — an `expected_type`, a `claims_key`,
or a `definition` — is a CLAIM, not an opinion. It routes through
`scripts/data_dictionary/data_dictionary.py::corroborate_definition` on ingest
(the mandated composition, **never a re-implementation**):

- When sampled `rows` are available (a reachable DB, `--db`, or injected rows), the
  claim is checked against the real data. A claim the data contradicts (e.g.
  `expected_type: boolean` on a column whose sampled values are integers) is
  flagged **⚠**, its confidence downgraded to `low`, and marked **NOT accepted**.
- An optional corroborated-definitions map (derived from `docs/data-dictionary.json`
  via `corroborated_defs_from_dictionary`) checks a claim against the
  already-corroborated definition of **that exact field** — a type conflict is
  flagged even without live rows.
- Corroboration is **per-field**, never per-context. A claim counts as
  `corroborated` / `accepted` ONLY when rows actually checked THIS column OR a
  corroborated definition for THIS EXACT field was compared. Merely SUPPLYING a
  dictionary does not corroborate a field the dictionary lacks (or holds
  un-corroborated): a field absent from every source stays **uncorroborated**
  (`needs_corroboration: true`, `accepted: false`, `anchor_in_dictionary: false`),
  and the server surfaces it as `corroboration_status: 'uncorroborated'`, never as
  established truth. A factual claim is NEVER stronger than provenance `inference`
  until corroborated — the engine hard-codes this; the gate can only hold it here
  or downgrade it, never promote it.

Non-factual annotations (`note` / `quality_flag` / `deprecation`) are stored
**as authored** — they are opinions, not claims, and are not corroborated. This is
the line that keeps the store from accumulating confidently-wrong tribal knowledge
the way an un-gated annotation channel can. NEVER let a factual annotation be
presented as established truth without corroboration.

## Server merge-at-query (D-D3 — additive)

`services/knowledge_server/`'s `get_table_details` (and `search_dictionary`, on a
matched hit) **merge** the per-user annotations at query time — surfacing, per
table/field, the merged `note` / `quality_flag` / `deprecation` AND an explicit
**`corroboration_status`** (`opinion` / `corroborated` / `conflicting` /
`uncorroborated`) read from the claim the engine corroborated on ingest. The
existing `{verdict, basis}` freshness envelope still applies. The server never
re-corroborates (no data-dictionary import — `check_separation` stays clean); it
reads the status the engine already computed. The merge is **additive**: a repo
with **no** `docs/data-annotations/` files behaves EXACTLY as before —
`get_table_details` returns an empty `annotations` list and no search hit gains an
`annotations` key, so the response is byte-unchanged.

## Recall — mined to MemPalace (D-D5, and the gate-integrity rule)

Annotations are mined to MemPalace **alongside the dictionary artifact**, reusing
the `data-dictionary` mine path (`skills/mempalace-integration`), so the durable
structured memory is recallable across runs:

```
mempalace --palace "<workspace>/.mempalace/palace" mine docs/data-annotations --wing "<wing>"
```

(mined right after `docs/DATA_DICTIONARY_MAP.md`, the same orchestrator-serialized
mine; MemPalace-absent → the on-disk files are the deliverable, persistence is
best-effort.)

**GATE INTEGRITY — the D5 load-bearing invariant.** Served or recalled annotation
memory **INFORMS** a per-run gate; it can **NEVER** skip or auto-satisfy one.
`annotations.py::inform_gate(gate, annotations)` makes this executable: it attaches
the annotations to the gate as advisory `informing_annotations` context, but the
gate's `satisfied` state is preserved EXACTLY as the gate's own evidence set it —
no annotation, however it is phrased (even one literally carrying `satisfied:
true`, or an `accepted` claim), can flip the gate. Durable annotation memory is a
lens onto a per-run gate, never a key that opens it. This is the leg-2
generalization's safety rule, reviewable in isolation — which is why decision D5
does data objects FIRST.

## Deferred — the second D5 step (documented, NOT built)

Run D ships the DATA-OBJECT annotation store. The SECOND D5 step — persisting
interaction / bulk-verify **domain-gate confirmations** (from
`interaction-intuition` / `interactive-mockup-discovery`) as annotations — is
deliberately **deferred**. It is a hook, not built here, so the gate-integrity
question stays reviewable in isolation: a confirmation persisted as memory would
still, under the D5 rule above, only INFORM a future gate, never auto-satisfy it.
Do not build it in this run.

## CLI

Mirrors `scripts/data_dictionary/data_dictionary.py`'s shape:

```
python scripts/data_dictionary/annotations.py annotate --user <u> --anchor <table[.field]> \
    [--note <t>] [--quality-flag TRUSTED|STALE|INCOMPLETE|EXPERIMENTAL] [--deprecation <t>] \
    [--expected-type <t>] [--claims-key] [--definition <t>] \
    [--dictionary docs/data-dictionary.json] [--db <sqlite>] [--root <repo>]
python scripts/data_dictionary/annotations.py list --user <u> [--root <repo>]
python scripts/data_dictionary/annotations.py show --anchor <table[.field]> [--root <repo>]
```

A factual claim (`--expected-type` / `--claims-key` / `--definition`) is
corroborated on ingest — against real data when `--db` samples a reachable
database, otherwise against the corroborated definitions in `--dictionary`.

## Honest boundary

Run D ships the DATA-OBJECT annotation store + corroborate-on-ingest + the additive
server merge (the D5 first step). Annotations are git-shared TEXT files; nothing is
"deployed". A factual annotation is never presented as established truth until
corroborated. The interaction/bulk-verify → annotation persistence (D5 step two) is
documented above as a hook, not built.

## Cross-references

- `scripts/data_dictionary/annotations.py` — the deterministic engine (the machine).
- `scripts/data_dictionary/data_dictionary.py` — the corroboration engine the
  factual claims compose (`corroborate_definition`, the `docs/data-dictionary.json`
  anchor), never re-implemented.
- `services/knowledge_server/dictionary_source.py` — the DictionarySource whose
  `get_table_details` / `search_dictionary` merge the annotations at query time.
- `skills/data-dictionary` — defines the FIELDS this store annotates; the mine path
  annotations ride is its Step 5.
- `skills/warehouse-sql-mining` — the sibling corroboration-gated engine-contract
  skill this one mirrors.
- `skills/mempalace-integration` — the recall / mine path (annotations are mined
  alongside the dictionary artifact).
