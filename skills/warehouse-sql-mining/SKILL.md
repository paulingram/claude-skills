---
name: warehouse-sql-mining
description: Use when a data-engineering ask includes SQL objects — stored procedures, views, or functions — and you need the join, filter, and metric shapes plus the table read/write relationships latent in that SQL as corroboration-gated evidence for the data dictionary, the lineage graph, and the data-engineering exploration. A deterministic, stdlib-only vendored T-SQL/ANSI pattern extractor (NOT sqlglot, NOT a full parser) with honest parse-coverage stats so a dialect-specific or malformed object is reported, never silently dropped or mis-parsed. Mined candidates enter at provenance inference and are corroborated through corroborate_definition when sampled data is available — uncorroborated candidates are machine-marked not-accepted, never presented as established truth; the engine lives in scripts/sql_mining/sql_mining.py and this skill is its contract.
---

# Warehouse SQL Mining (SQL-MINING-1 … N)

A warehouse's stored procedures and views encode most of what its analysts know:
which tables feed which, how they join, what gets filtered, and which
aggregate/ratio metrics are computed. This skill's engine **mines that latent
structure from SQL text** so the data-engineering lane's exploration and the data
dictionary have *evidence* instead of guesses — and it does so under a discipline
that keeps CT6 from importing the deng toolkit's fidelity problem along with its
idea: **nothing mined is presented as stronger than `inference` until it passes
corroboration, and parse-coverage is surfaced honestly, never assumed.**

Source of truth for the deterministic machinery — the vendored extractor, the
coverage stats, the corroboration wiring, the lineage emission, and the serializer
— is **`scripts/sql_mining/sql_mining.py`** (stdlib-only, unit-tested). This skill
is the *contract*; that module is the *machine*. Do not re-implement the
extraction in prose — call the module. (Same relationship
`scripts/data_dictionary/data_dictionary.py` has to `data-dictionary`, and
`hooks/lineage_graph.py` has to `data-lineage-mapping`.)

## The standard artifact

`mine` writes one standard-named pair (like the data dictionary's):

- `docs/SQL_MINING_MAP.md` — the human view (`last_mined` frontmatter): the
  parse-coverage summary, the per-object shapes, the corroboration-gated
  dictionary candidates, and a lineage summary.
- `docs/sql-mining.json` — the machine sidecar (`schema: sql-mining/v1`): the full
  `objects` / `coverage` / `dictionary_candidates` / `lineage` structure.

## What the extractor recognizes (the extraction surface)

Over each SQL object (split on `CREATE`/`ALTER (PROCEDURE|VIEW|FUNCTION|TRIGGER)`
headers; a header-less file is one `script` object) the engine extracts ONLY:

- **Read sources** — every `FROM` / `JOIN` table reference.
- **Write targets** — every `INSERT [INTO]` / `UPDATE` / `MERGE [INTO]` /
  `DELETE [FROM]` target.
- **Join shapes** — every `table.col = table.col` equality (in `ON` or `WHERE`),
  both sides recorded as qualified columns and each side's table resolved from the
  `FROM`/`JOIN` alias map.
- **Filter predicates** — every `column <op> value` predicate (`=`, `<>`, `<`,
  `>`, `<=`, `>=`, `LIKE`, `IN`, `IS`); a `col = col` equality is a join, not a
  filter, and is not double-counted.
- **Metric shapes** — every `SUM` / `COUNT` / `AVG` / `MIN` / `MAX` aggregate
  (with its argument + alias) and every **ratio** (a division where at least one
  operand is an aggregate); an aggregate that is a ratio's operand is captured as
  part of the ratio, not separately.

This is a MINIMAL vendored extractor by design (decision D6). It is **not** a full
SQL parser, **not** an AST, **not** `sqlglot` or any third-party dependency — it
recognizes only the shapes above; **everything else is coverage-stat'd, not
parsed.** Do not extend it toward a general parser — extend the coverage stats
instead, and let the corroboration gate contain any mis-read.

## Parse-coverage honesty (the fidelity rule — non-negotiable)

The artifact's `coverage` block is a first-class output, not a log line:

```
"coverage": {
  "parsed":  ["<object>", ...],
  "skipped": [{"object": "<name>", "reason": "<why>"}, ...],
  "failed":  [{"object": "<name>", "reason": "<why>"}, ...],
  "counts":  {"parsed": P, "skipped": S, "failed": F, "total": P+S+F}
}
```

Every object MUST be accounted for. An object with no recognizable shape (exotic /
dialect-specific construct, dynamic SQL inside a string literal, pure control-flow,
DDL-only) lands in **`skipped`** WITH a reason. A genuinely malformed object
(unterminated string literal, unbalanced parentheses) lands in **`failed`** WITH a
reason. A file that is not valid UTF-8 — a UTF-16 SSMS script export, or a cp1252
file with an accented character — likewise lands in **`failed`** with an
`undecodable file (not utf-8)` reason rather than crashing the run (`utf-8-sig` is
tried first, so a UTF-8 BOM is tolerated). A bad object is NEVER silently dropped,
NEVER silently mis-parsed, and NEVER crashes the run — any unexpected extraction
error is caught and reported as `failed`. Keyword scans run over a length-preserving
mask, so a keyword or table name that appears only INSIDE a string literal is never
mistaken for a real shape.

## Corroboration is the gate

Mined field/metric candidates are the dictionary's, and they enter under the same
inversion the dictionary already enforces:

- Every candidate enters at provenance **`inference`** — NEVER `live-data`,
  `direct-code-comment`, or `direct-user-input`. The engine hard-codes this; the
  corroboration gate can only *hold* a candidate here or downgrade its confidence,
  never promote it.
- `corroborate_mined_claim(candidate, rows=…, corroborated_defs=…)` routes each
  candidate through
  `scripts/data_dictionary/data_dictionary.py::corroborate_definition` (the
  mandated composition, not a re-implementation). When sampled `rows` are
  available, a claim the data contradicts (e.g. a mined `numeric` metric whose
  column actually holds free text) is flagged ⚠, downgraded to `low` confidence,
  and marked **NOT accepted** — exactly as a provided definition would be. An
  optional `corroborated_defs` map additionally flags a mined claim that conflicts
  with an already-corroborated definition.

A mined claim never survives as truth just because the SQL said so. The lane
supplies the corroboration `rows` from its live inspection at D0, and each
candidate is then run through the gate inline. Absent that data (the CLI /
text-only path), the candidates stay honestly uncorroborated at `inference` and
are machine-marked `corroborated: false` / `accepted: false` /
`needs_corroboration: true` — so an uncorroborated inference is never read as an
established claim, and the "corroborated when a dictionary is available" statement
matches exactly what the code does. When the gate does run, a corroborated
candidate is marked `corroborated: true` and `accepted` iff the data agrees.

## Lineage emission (existing kinds only — no invented kinds)

Mined table-to-table relationships become `hooks/lineage_graph.py` evidence:
`emit_lineage(objects, …)` returns a schema-valid CDLG fragment where each object
is a **`function`** node, each read/write table is a **`data_asset`** node
(`asset://<store>/<schema>/<table>`), and edges are **`reads`** / **`writes`**,
each attributed to its object via `match_basis` + `evidence`. Only the node kinds
(`function`, `data_asset`) and edge kinds (`reads`, `writes`) that already exist in
`hooks/lineage_graph.py` are used — the engine invents **no** node or edge kinds,
and the emitted graph validates clean against `validate_lineage_graph`.

## CLI

Mirrors `scripts/data_dictionary/data_dictionary.py`'s shape:

```
python scripts/sql_mining/sql_mining.py mine <dir-or-files...> [--out docs] \
    [--store warehouse] [--schema dbo] [--codebase warehouse]
```

`mine` collects every `.sql` file under each directory argument (plus any file
arguments), mines them, and writes the standard artifact pair, printing the
coverage line (`N objects: P parsed / S skipped / F failed`). No new agent — the
lane's D0 invokes the engine directly, exactly as it invokes the data dictionary.

## Wiring — mining → dictionary / lineage / exploration

- **→ data dictionary.** Mined candidates feed `corroborate_definition` at
  provenance `inference`; the corroborated survivors extend
  `DATA_DICTIONARY_MAP.md` at D7 (`data-dictionary`).
- **→ lineage graph.** The emitted `data_asset` + `reads`/`writes` fragment merges
  into the CDLG the lineage disciplines maintain (`data-lineage-mapping`).
- **→ exploration.** The mined join/filter/metric evidence is supplied as
  `data-engineering-exploration` Stage 2–3 input — the conceptual-model and
  service-design stages reason over real extracted shapes rather than guesses.
- **→ the lane.** `skills/data-eng-pipeline` D0 invokes the miner when SQL objects
  are in scope and hands its evidence to the exploration; a data-eng run without
  SQL objects is unchanged.

## Honest boundary

Run C ships the ENGINE + its corroboration-gated wiring. It is **T-SQL-first**
(ANSI shapes covered; dialect-specific exotica land in `skipped` with a reason —
never silently mis-parsed). It mines SQL **text** (stored-procedure / view
definitions); it does NOT connect to a live warehouse, and execution-stats mining
(usage frequency) is out of scope. Nothing mined is presented as stronger than
`inference` until corroborated against real data.

## Cross-references

- `scripts/sql_mining/sql_mining.py` — the deterministic engine (the machine).
- `scripts/data_dictionary/data_dictionary.py` — the corroboration engine the
  mined candidates compose (`corroborate_definition`, the `inference` provenance).
- `hooks/lineage_graph.py` — the CDLG node/edge kinds the mined relationships emit
  evidence in (`data_asset`, `reads`, `writes`).
- `skills/data-dictionary` — defines the FIELDS; this skill supplies mined,
  corroboration-gated field/metric candidates for it.
- `skills/data-lineage-mapping` — the asset-lineage layer the mined `reads`/`writes`
  evidence extends.
- `skills/data-engineering-exploration` — consumes the mined join/filter/metric
  evidence as Stage 2–3 input.
- `skills/data-eng-pipeline` — the lane whose D0 invokes this engine when SQL
  objects are in scope.
