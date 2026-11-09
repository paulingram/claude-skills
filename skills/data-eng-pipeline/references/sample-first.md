> **STOP.** Before implementing a change against a big table, read this and run `scripts/data_dictionary/sampling.py`. The canonical summary is `skills/data-eng-pipeline/SKILL.md` `## Sample-first iteration (v4.0.0)`; this file is the rule in full. Do not work from memory.

# Sample-first iteration (v4.0.0) — full text

## The defect this closes

Sampling existed in CT6 for *discovery* only — `data-dictionary` reads ~100 rows to infer grain and types, `warehouse-sql-mining` reads sampled rows — never for *development*. The data-eng lane built like the main lane: implement against the full data, run the full transformation to see whether the change is right, repeat. On a 2.5-million-row table every iteration of a filter, an aggregate, or a dedup was a full run. `expensive-verification-debugging` says "when the cycle is expensive, audit the pathway and batch the fixes" — it never said *make the cycle cheap by shrinking the data*. This reference makes that the default move for data changes.

## The six steps

The deterministic pieces are the engine's; the judgment pieces (which dimension the change depends on, which rows a bug report names) are yours.

1. **Profile** — read the subset's structure from the data dictionary: grain, key columns (`declared_pk` / `inferred_key`), partition columns, sampled values, and the row count (`usage.row_volume`). `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/data_dictionary/sampling.py" should-sample --dictionary docs/data-dictionary.json --table <T> --json` answers *does sampling pay here* with its reason. The dictionary is the profile; if it is stale, refresh it first (D7's engine, not a guess).
2. **Stratify** — on the dimension the change depends on. `plan --predicate <cols>` turns every partition column and every predicate column into a stratum: a low-cardinality column (sampled values known, at most 20) is stratified **by value**, anything else by **hash bucket**. Edge rows are always included: a NULL per stratum column, the min and max of each non-enumerated predicate column, duplicates on the key, and **the exact rows a bug report named** (`--reported-rows rows.json`).
3. **Size** — `n_target` is the smallest N giving every stratum cell and every edge select `--min-per-stratum` rows (default 3), capped at `--max-rows`; a cap is recorded in `sizing.capped` and `warnings`, never hidden. Write the plan: `plan ... --out .architect-team/data-eng/<slug>/sample-plan.json`. It carries the strata, N, the seed, the threshold, the materialization target, and the columns — the artifact a reviewer reruns.
4. **Materialize** — `sql --plan sample-plan.json --dialect postgres|bigquery|snowflake|sqlite` renders the query: per stratum a deterministic pick ordered by `MOD(ABS(hash(keys)) + seed, 100)` (the hash is named per dialect — `hashtext`, `FARM_FINGERPRINT`, `HASH`, and `ct6_hash` for sqlite, registered via `register_sqlite_hash`), then a `UNION ALL` of the edge-row selects. Run it under the read-only connection discipline into the sandbox named by `materialize.target_name` (a temp table in the warehouse), and record the rendered query on the plan as `source_query`.
5. **Iterate** — implement the change against the sample. Capture the sample's rows before and after, then `diff --before b.json --after a.json --plan sample-plan.json --json`: per stratum the row counts, the sha256 checksums of the sorted key sets, keys added and removed, and the sum deltas of every numeric column. The diff is what you reason about — a stratum that changed when the change should not touch it is a bug found in seconds, not after a full run.
6. **Scale** — only when the sample passes. Run the full transformation, and use the sample's after-rows as the **expectation** for the same keys in the full result: the sample is the oracle the full run is checked against, and the full run remains the gate.

## The group-preserving rule

When the change's semantics live at the group level — `aggregate`, `window`, `dedup`, `join` — a row-level sample silently changes the answer (a window over half a customer's orders is a different window). For those change kinds the plan records `group_preserving_keys` (explicit `--group-keys`, else the predicate columns) and `render_sql` emits the **group-preserving variant**: it samples DISTINCT group keys per stratum cell first, then joins back **every row of each kept group**; edge-row selects pull whole groups too, and a NULL group key (which has no group to keep) is selected directly. The plan warns when a group key is low-cardinality — keeping whole groups on a 3-value column keeps most of the table, which is not a sample.

## Where it plugs in

- **`data-eng-pipeline` Phase D2** — before implementation, for any transformation that targets a subset (a filter, a partition, an entity type, a date range) of a table the dictionary shows is large. The plan lands beside the run's other artifacts and is cited in the Phase 3 evidence like any other check.
- **`bug-fix-pipeline` when the defect is a data defect** — B1 replicates on the sample (the reported rows are edge rows by construction, so the replication includes them), B6 replays on the sample first and on the full data second; the sample diff is the replay's evidence.
- **`verification-planning`** — "stratified sample" is a venue in the menu, usually the cheapest faithful one for a data claim: it exhibits the claim's failure on real rows (including the reported ones) in seconds, where the full run takes the cycle this reference exists to shrink.

## Opt-outs

- `--full-data` on the lane invocation turns sample-first off for the run; the final report records that it was turned off.
- A project principle that forbids sampling (or forbids materializing data outside a named store) turns it off for the project; the plan is not produced and the report names the principle.
- `should-sample` returning false — the dictionary shows the table is small (a measured `usage.row_volume`, a recorded `row_count`, or a live sample that came back short of its limit). The threshold (`--threshold-rows`, default 100000) is recorded on the plan, not asserted in prose. An **unknown** row count keeps sampling on: not knowing a table is small is not the same as knowing it is.

## Residency

Default to a sandbox **inside the warehouse** — a temp table or scratch schema the dictionary already knows how to reach, under the read-only connection discipline (`materialize.kind: temp-table`). A local file (`--allow-local-file`, `materialize.kind: local-file`) is permitted only when the project's principles allow it; PII, residency policy, and the anonymized-model principle apply to a sample exactly as they apply to the table it came from. The plan's `residency_note` states which applies.

## Honest boundaries

- **A sample can hide a bug.** Stratifying on the change's own predicate and including the reported rows reduces that; it does not remove it. The full run stays the gate, so a miss costs time, not correctness — never report a sample pass as the transformation's verification.
- **Sampling code is code.** The pick is seeded and the rendered query is recorded on the plan so a reviewer reruns it and gets the same rows; a plan without its `source_query` is a plan nobody can check.
- **The dictionary is the profile, and it can be stale.** Strata by value come from `sample_values` a build observed; a column without them is bucket-stratified and the plan says so (`why_buckets`). The column list every branch projects is the dictionary's — a stale dictionary fails the query loudly rather than sampling the wrong shape.
- **The engine renders SQL; it does not run it.** The four dialects are rendered deterministically and the sqlite dialect is executed in the self-tests against a real database; postgres / bigquery / snowflake syntax is rendered against documented builtins and is not executed in this repo's tests. The first run against a live warehouse is yours to read.
- **Branches may overlap.** A row can satisfy several strata or edge selects and appear more than once in the `UNION ALL`; dedupe on the key columns (`materialize.dedupe_on`) when materializing.

## The lane's procedure in brief (from the data-eng-pipeline body)

A data change that targets a subset of a large table — a filter, a partition, an entity type, a date range, an aggregate per key — is iterated on a **stratified sample first** and run against the full data last. Default on; when `--full-data` was passed (or a project principle forbids sampling) D2 references no sample plan — every data step runs in full — and the D8 report records the opt-out and its source. Absent the flag, before the D2 implementation of such a transformation:

- **Decide** — `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/data_dictionary/sampling.py" should-sample --dictionary docs/data-dictionary.json --table <T> --json`; skip only when the dictionary POSITIVELY shows the table is small (an unknown row count keeps sampling on).
- **Plan** — `plan --table <T> --predicate <the columns the change depends on> --change-kind filter|aggregate|window|dedup|join [--reported-rows rows.json] --out <workspace>/.architect-team/data-eng/<slug>/sample-plan.json`; aggregate-level kinds keep whole groups (`group_preserving_keys`).
- **Materialize + iterate** — `sql --plan ... --dialect <engine>` into a sandbox inside the warehouse, implement against the sample, then `diff --before b.json --after a.json --plan ...` per stratum (row counts, key checksums, numeric deltas).
- **Scale** — only when the sample passes; the sample's result is the expectation the full run is checked against, and the full run stays the gate.

The rule in full — the six steps, the group-preserving rule, the opt-outs, the residency default, the honest boundaries (a sample can hide a bug; the pick is seeded and the query recorded so a reviewer reruns it) — is `references/sample-first.md`; read it before the first sample-first transformation of a run. The plan is evidence: cite it in the Phase 3 review-gate record like any other artifact. `verification-planning` lists the stratified sample as a venue, and the bug-fix lane uses the same plan for a data defect.
