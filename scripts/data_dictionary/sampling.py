#!/usr/bin/env python3
"""Sample-first iteration engine (stdlib-only) -- the deterministic machine behind
the `data-eng-pipeline` `## Sample-first iteration (v4.0.0)` section and its
reference `skills/data-eng-pipeline/references/sample-first.md`.

Before a change that targets a subset of a big table is implemented against the
full data, the lane profiles the subset from the data dictionary, stratifies on
the dimension the change depends on, sizes the smallest sample that covers every
stratum, materializes it into a sandbox, iterates with a before/after diff per
stratum, and only then scales. This module does the deterministic pieces:

* `plan(...)`        -- a `sample-plan/v1` dict from a `data-dictionary/v1` sidecar
                        entry: strata (partition columns + low-cardinality predicate
                        columns by value, the rest by hash bucket), edge rows (NULLs,
                        boundaries, duplicates, the exact rows a bug report named),
                        group-preserving keys for aggregate-level changes, the
                        smallest covering N (capped), the seed, the skip threshold,
                        and where the sample is materialized.
* `render_sql(...)`  -- readable SQL for postgres | bigquery | snowflake | sqlite:
                        deterministic stratified sampling by a hash of the key
                        columns modulo a bucket count, a UNION ALL of the edge-row
                        selects, and a group-preserving variant that samples
                        DISTINCT group keys first and joins back every row of each
                        kept group.
* `diff_report(...)` -- per-stratum row counts + key-set checksums (sha256 over the
                        sorted keys) + aggregate deltas for numeric columns, a pure
                        function over before/after row lists.
* `should_sample(...)` -- the skip decision with its reason: sampling is skipped
                        only when the dictionary POSITIVELY shows the table is small
                        (a measured `usage.row_volume`, a recorded `row_count`, or a
                        live sample that came back short of its limit). An unknown
                        row count keeps sampling ON -- the default is sample-first.

Dictionary inputs this engine reads (every one optional except `tables` + `grain`):
`tables[T].grain.declared_pk` / `inferred_key` (the key columns), `tables[T].usage.
row_volume` (R4, measured), `tables[T].partitions` (ADDITIVE: a list of partition
column names, or `{"column": ...}` dicts), and per field `sample_values` (ADDITIVE:
the distinct values a build observed; a column without them is bucket-stratified).
The `data-dictionary/v1` schema is unchanged; the additive fields are read when
present and never required.

The sample plan is a recorded artifact: the seed, the strata, and the rendered
query are what a reviewer reruns. A sample can hide a bug -- the full run stays
the gate; the sample makes the iteration cheap, it does not replace the gate.

CLI:
    python sampling.py plan --dictionary <sidecar|dir> --table T --predicate c1 c2
        --change-kind filter|aggregate|window|dedup|join [--reported-rows f.json]
        [--seed N] [--min-per-stratum K] [--max-rows M] [--out plan.json] --json
    python sampling.py sql --plan plan.json --dialect postgres [--variant auto|rows|groups]
    python sampling.py diff --before b.json --after a.json --plan plan.json --json
    python sampling.py should-sample --dictionary <sidecar|dir> --table T --json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PLAN_SCHEMA = "sample-plan/v1"
DIFF_SCHEMA = "sample-diff/v1"
DICTIONARY_SCHEMA = "data-dictionary/v1"

CHANGE_KINDS: tuple[str, ...] = ("filter", "aggregate", "window", "dedup", "join")
# A change whose semantics live at the group level: the sample must keep WHOLE
# groups (every row of a kept key) or windows, dedup, and joins silently change.
GROUP_PRESERVING_KINDS: tuple[str, ...] = ("aggregate", "window", "dedup", "join")

DIALECTS: tuple[str, ...] = ("postgres", "bigquery", "snowflake", "sqlite")
VARIANTS: tuple[str, ...] = ("auto", "rows", "groups")

DEFAULT_SEED = 42
DEFAULT_MIN_PER_STRATUM = 3
DEFAULT_MAX_ROWS = 10_000
# Below this many rows the full run is seconds; sampling is overhead. The plan
# records the threshold so the decision is auditable, never a prose default.
DEFAULT_THRESHOLD_ROWS = 100_000
# A predicate column with at most this many distinct sampled values is a stratum
# BY VALUE; more (or unknown) values are stratified by hash bucket.
LOW_CARDINALITY_MAX = 20
DEFAULT_COLUMN_BUCKETS = 4
# The hash-order modulus used to pick rows inside a stratum cell.
DEFAULT_HASH_BUCKETS = 100

_NUMERIC_TYPES = ("int", "integer", "bigint", "smallint", "numeric", "decimal",
                  "float", "double", "real", "number", "money")
_TEMPORAL_TYPES = ("date", "timestamp", "datetime", "time")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOADED: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# dictionary loading (reuses the data_dictionary engine's sidecar name)
# --------------------------------------------------------------------------- #

def _load(mod_name: str, rel_path: str) -> Any:
    """Load an in-repo stdlib leaf module by file path (cached) -- the same
    `spec_from_file_location` idiom `data_dictionary.py` uses, because `scripts/`
    carries no `__init__.py`. Loaded lazily so importing THIS module has no
    import-time side effects."""
    cached = _LOADED.get(mod_name)
    if cached is not None:
        return cached
    path = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {mod_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LOADED[mod_name] = module
    return module


def _engine() -> Any:
    return _load("ct6_sampling_dd", "scripts/data_dictionary/data_dictionary.py")


def load_dictionary(path: str | Path) -> dict[str, Any]:
    """Read a `data-dictionary/v1` sidecar. A directory resolves to the engine's
    `SIDECAR_NAME` inside it (the standard `docs/data-dictionary.json`). Raises
    `ValueError` when the file is not a dictionary sidecar."""
    p = Path(path)
    if p.is_dir():
        p = p / _engine().SIDECAR_NAME
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("tables"), dict):
        raise ValueError(f"{p} is not a data-dictionary sidecar (no 'tables' mapping)")
    schema = data.get("schema")
    if schema is not None and schema != DICTIONARY_SCHEMA:
        raise ValueError(f"{p}: unsupported dictionary schema {schema!r} (expected {DICTIONARY_SCHEMA})")
    return data


def _table_entry(dictionary: dict[str, Any], table: str) -> dict[str, Any]:
    tables = dictionary.get("tables") or {}
    if table not in tables:
        known = ", ".join(sorted(tables)) or "(none)"
        raise KeyError(f"table {table!r} is not in the dictionary (known: {known})")
    return tables[table]


def _field_map(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f.get("field"): f for f in (entry.get("fields") or []) if f.get("field")}


def _key_columns(entry: dict[str, Any]) -> tuple[list[str], str]:
    grain = entry.get("grain") or {}
    pks = list(grain.get("declared_pk") or [])
    if pks:
        return pks, "declared primary key"
    inferred = list(grain.get("inferred_key") or [])
    if inferred:
        hedge = " (small-sample inference - hedged)" if grain.get("small_sample_key") else ""
        return inferred, "inferred key" + hedge
    return [], "no key in the dictionary - every column is hashed"


def _partition_columns(entry: dict[str, Any]) -> list[str]:
    raw = entry.get("partitions") or entry.get("partition_columns") or []
    out: list[str] = []
    for item in raw:
        col = item.get("column") if isinstance(item, dict) else item
        if isinstance(col, str) and col and col not in out:
            out.append(col)
    return out


def _sample_values(field: dict[str, Any]) -> list[Any]:
    for key in ("sample_values", "sampled_values", "distinct_values"):
        vals = field.get(key)
        if isinstance(vals, list):
            uniq: list[Any] = []
            for v in vals:
                if v is not None and v not in uniq:
                    uniq.append(v)
            return uniq
    return []


def _is_numeric_or_temporal(field: dict[str, Any]) -> bool:
    t = str(field.get("type") or "").lower()
    return any(t.startswith(n) for n in _NUMERIC_TYPES) or any(t.startswith(n) for n in _TEMPORAL_TYPES)


# --------------------------------------------------------------------------- #
# row count + the skip decision
# --------------------------------------------------------------------------- #

def table_row_count(dictionary: dict[str, Any], table: str) -> tuple[int | None, str]:
    """The table's row count as the dictionary shows it, with its basis:

    1. `usage.row_volume` (R4 -- MEASURED from the engine's usage catalog);
    2. a recorded table-level `row_count` (additive, when a build wrote one);
    3. a live sample that came back SHORT of its limit -- the sampler asked for
       `sample_limit` rows and got fewer, so the whole table is that small;
    4. otherwise `None`: the dictionary cannot say how big the table is.
    """
    entry = _table_entry(dictionary, table)
    usage = entry.get("usage") or {}
    vol = usage.get("row_volume")
    if isinstance(vol, int) and not isinstance(vol, bool):
        return vol, "usage.row_volume (measured, live-data)"
    rc = entry.get("row_count")
    if isinstance(rc, int) and not isinstance(rc, bool):
        return rc, "table.row_count (recorded)"
    live = dictionary.get("live_inspection") or {}
    grain = entry.get("grain") or {}
    sampled = grain.get("sampled_rows")
    limit = live.get("sample_limit")
    if (live.get("ran") and isinstance(sampled, int) and isinstance(limit, int)
            and 0 <= sampled < limit):
        return sampled, f"live sample exhausted the table ({sampled} of a {limit}-row limit)"
    return None, "unknown - the dictionary carries no row count for this table"


def should_sample(
    dictionary: dict[str, Any], table: str, threshold_rows: int = DEFAULT_THRESHOLD_ROWS,
) -> dict[str, Any]:
    """Decide whether sampling pays for `table`, with the reason.

    Skip ONLY when the dictionary positively shows a small table (row count below
    `threshold_rows`). An unknown row count keeps sampling ON: the default is
    sample-first, and "we do not know it is small" is not "it is small".
    """
    count, basis = table_row_count(dictionary, table)
    if count is None:
        verdict, reason = True, (
            f"row count unknown ({basis}); sampling stays on - the dictionary cannot show "
            f"{table!r} is below the {threshold_rows}-row threshold"
        )
    elif count < threshold_rows:
        verdict, reason = False, (
            f"{table!r} has {count} row(s) per {basis}, below the {threshold_rows}-row "
            f"threshold - the full run is cheap; skip sampling"
        )
    else:
        verdict, reason = True, (
            f"{table!r} has {count} row(s) per {basis}, at or above the {threshold_rows}-row "
            f"threshold - iterate on a sample first"
        )
    return {
        "table": table, "should_sample": verdict, "reason": reason,
        "row_count": count, "row_count_basis": basis, "threshold_rows": threshold_rows,
    }


# --------------------------------------------------------------------------- #
# the plan
# --------------------------------------------------------------------------- #

def _normalize_reported(reported_rows: list[Any] | None, keys: list[str]) -> list[dict[str, Any]]:
    """Reported rows -> dicts keyed by the key columns. A dict is kept as given; a
    scalar binds to the first key; a list/tuple binds positionally."""
    out: list[dict[str, Any]] = []
    for row in reported_rows or []:
        if isinstance(row, dict):
            out.append(dict(row))
        elif isinstance(row, (list, tuple)):
            out.append({k: v for k, v in zip(keys, row)})
        elif keys:
            out.append({keys[0]: row})
        else:
            raise ValueError(f"reported row {row!r} cannot be keyed: the table has no key columns")
    return out


def plan(
    dictionary: dict[str, Any],
    table: str,
    predicate_columns: list[str],
    change_kind: str,
    reported_rows: list[Any] | None = None,
    seed: int = DEFAULT_SEED,
    min_per_stratum: int = DEFAULT_MIN_PER_STRATUM,
    max_rows: int = DEFAULT_MAX_ROWS,
    *,
    threshold_rows: int = DEFAULT_THRESHOLD_ROWS,
    group_keys: list[str] | None = None,
    allow_local_file: bool = False,
    column_buckets: int = DEFAULT_COLUMN_BUCKETS,
) -> dict[str, Any]:
    """Build the `sample-plan/v1` for a change against `table`.

    Strata come from the dictionary: every partition column, every predicate column
    with low-cardinality `sample_values` (stratified BY VALUE), and every other
    predicate column (stratified by `column_buckets` hash buckets). Edge rows are
    NULLs per stratum column, min/max boundaries per non-enumerated predicate
    column, duplicates on the key, and the reported rows. A group-preserving change
    kind keeps whole groups on `group_keys` (explicit) or the predicate columns.
    `n_target` is the smallest N giving every stratum cell + every edge select
    `min_per_stratum` rows, capped at `max_rows` (a cap is recorded, not hidden).
    """
    if change_kind not in CHANGE_KINDS:
        raise ValueError(f"change_kind {change_kind!r} not in {CHANGE_KINDS}")
    if min_per_stratum < 1:
        raise ValueError("min_per_stratum must be >= 1")
    if max_rows < 1:
        raise ValueError("max_rows must be >= 1")
    entry = _table_entry(dictionary, table)
    fields = _field_map(entry)
    predicate_columns = list(dict.fromkeys(predicate_columns or []))
    unknown = [c for c in predicate_columns if c not in fields]
    if unknown:
        raise ValueError(f"predicate column(s) not in the dictionary for {table!r}: {unknown}")
    for c in group_keys or []:
        if c not in fields:
            raise ValueError(f"group key {c!r} is not a column of {table!r} in the dictionary")

    keys, key_basis = _key_columns(entry)
    partitions = [c for c in _partition_columns(entry) if c in fields]

    # --- strata -----------------------------------------------------------
    strata: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    passes = [(c, "partition") for c in partitions] + [(c, "predicate") for c in predicate_columns]
    for col, basis in passes:
        if col in seen:
            if basis not in seen[col]["basis"]:
                seen[col]["basis"] = "partition+predicate"
            continue
        values = _sample_values(fields[col])
        stratum: dict[str, Any] = {"column": col, "basis": basis}
        if values and len(values) <= LOW_CARDINALITY_MAX:
            stratum["values"] = values
            stratum["cells"] = len(values)
        else:
            stratum["buckets"] = list(range(column_buckets))
            stratum["bucket_count"] = column_buckets
            stratum["cells"] = column_buckets
            stratum["why_buckets"] = (
                f"{len(values)} sampled values exceed the low-cardinality limit {LOW_CARDINALITY_MAX}"
                if values else "no sampled values in the dictionary for this column"
            )
        seen[col] = stratum
        strata.append(stratum)

    # --- edge rows --------------------------------------------------------
    null_cols = [s["column"] for s in strata]
    boundaries: list[dict[str, str]] = []
    for col in predicate_columns:
        if "values" in seen[col]:
            continue  # every value is already a stratum cell
        for edge in ("min", "max"):
            boundaries.append({"column": col, "edge": edge})
    if change_kind == "dedup":
        duplicates_on = predicate_columns or keys
    else:
        duplicates_on = keys or predicate_columns
    reported = _normalize_reported(reported_rows, keys)
    edge_rows = {
        "nulls": null_cols, "boundaries": boundaries,
        "duplicates_on": duplicates_on, "reported": reported,
    }

    # --- group preservation ----------------------------------------------
    if change_kind in GROUP_PRESERVING_KINDS:
        group_preserving_keys = list(group_keys or predicate_columns or keys)
    else:
        group_preserving_keys = []

    # --- sizing -----------------------------------------------------------
    cells = sum(int(s["cells"]) for s in strata)
    strata_rows = cells * min_per_stratum
    edge_count = (len(null_cols) + len(boundaries)) * min_per_stratum
    edge_count += (min_per_stratum * 2 if duplicates_on else 0) + len(reported)
    uncapped = strata_rows + edge_count
    n_target = min(uncapped, max_rows)

    threshold = should_sample(dictionary, table, threshold_rows)
    warnings: list[str] = []
    if not keys:
        warnings.append("no key column in the dictionary: rows are hashed over the predicate/strata "
                        "columns and duplicates are judged on them, not on a key")
    if uncapped > max_rows:
        warnings.append(f"n_target capped at {max_rows} (coverage needs {uncapped}); some cells get "
                        f"fewer than {min_per_stratum} rows - raise --max-rows or drop a stratum")
    for gk in group_preserving_keys:
        vals = _sample_values(fields[gk])
        if vals and len(vals) <= LOW_CARDINALITY_MAX:
            warnings.append(f"group key {gk!r} has only {len(vals)} distinct sampled value(s): keeping "
                            f"whole groups keeps most of the table - pass a finer --group-keys or "
                            f"accept that this sample is near full size")
    residency = (
        "local files allowed by the project's principles - still prefer the warehouse sandbox"
        if allow_local_file else
        "default: a sandbox inside the warehouse (temp table / scratch schema) under the "
        "read-only connection discipline; no local copy - PII and residency policy apply"
    )
    grain = entry.get("grain") or {}
    return {
        "schema": PLAN_SCHEMA,
        "table": table,
        "db_name": dictionary.get("db_name"),
        "dictionary_built_at": dictionary.get("built_at"),
        "change_kind": change_kind,
        "predicate_columns": predicate_columns,
        "grain": grain.get("grain"),
        "columns": list(fields),
        "keys": keys,
        "key_basis": key_basis,
        "partitions": partitions,
        "strata": strata,
        "edge_rows": edge_rows,
        "group_preserving_keys": group_preserving_keys,
        "n_target": n_target,
        "sizing": {
            "cells": cells, "min_per_stratum": min_per_stratum, "strata_rows": strata_rows,
            "edge_rows": edge_count, "uncapped": uncapped, "max_rows": max_rows,
            "capped": uncapped > max_rows,
        },
        "seed": int(seed),
        "hash_buckets": DEFAULT_HASH_BUCKETS,
        "threshold": {
            "skip_sampling_when_rows_below": threshold_rows,
            "basis": "dictionary row count",
            "row_count": threshold["row_count"],
            "row_count_basis": threshold["row_count_basis"],
            "should_sample": threshold["should_sample"],
            "reason": threshold["reason"],
        },
        "materialize": {
            "kind": "local-file" if allow_local_file else "temp-table",
            "target_name": f"ct6_sample_{table}",
            "residency_note": residency,
            "dedupe_on": keys or None,
        },
        "warnings": warnings,
        "source_query": None,  # the caller records the rendered query it actually ran
        "produced_by": "scripts/data_dictionary/sampling.py",
    }


# --------------------------------------------------------------------------- #
# SQL rendering
# --------------------------------------------------------------------------- #

class _Dialect:
    def __init__(self, name: str) -> None:
        if name not in DIALECTS:
            raise ValueError(f"dialect {name!r} not in {DIALECTS}")
        self.name = name
        self.quote_char = "`" if name == "bigquery" else '"'
        self.text_type = {"postgres": "TEXT", "bigquery": "STRING",
                          "snowflake": "VARCHAR", "sqlite": "TEXT"}[name]
        self.hash_fn = {"postgres": "hashtext", "bigquery": "FARM_FINGERPRINT",
                        "snowflake": "HASH", "sqlite": "ct6_hash"}[name]

    def ident(self, name: str) -> str:
        q = self.quote_char
        return q + str(name).replace(q, q + q) + q

    def col(self, alias: str, name: str) -> str:
        return f"{alias}.{self.ident(name)}"

    def literal(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return repr(value)
        return "'" + str(value).replace("'", "''") + "'"

    def as_text(self, expr: str) -> str:
        return f"COALESCE(CAST({expr} AS {self.text_type}), '')"

    def concat(self, parts: list[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        if self.name == "bigquery":
            return "CONCAT(" + ", '|', ".join(parts) + ")"
        return " || '|' || ".join(parts)

    def hash_of(self, alias: str, columns: list[str]) -> str:
        text = self.concat([self.as_text(self.col(alias, c)) for c in columns])
        return f"ABS({self.hash_fn}({text}))"

    def mod(self, expr: str, n: int) -> str:
        if self.name == "sqlite":
            return f"(({expr}) % {n})"
        return f"MOD({expr}, {n})"


def _ct6_hash(value: Any) -> int:
    """The deterministic SQLite hash the rendered `sqlite` SQL calls as `ct6_hash`:
    sha256 of the text, folded to a non-negative 61-bit integer (SQLite integers
    are signed 64-bit). Register it with `register_sqlite_hash(conn)`."""
    text = "" if value is None else str(value)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (1 << 61)


def register_sqlite_hash(conn: Any) -> None:
    """Register `ct6_hash` on a `sqlite3` connection. SQLite ships no stable hash
    builtin, so the sqlite dialect names this user function; an unregistered
    connection fails loudly ('no such function: ct6_hash'), never silently."""
    conn.create_function("ct6_hash", 1, _ct6_hash, deterministic=True)


def _proj(d: _Dialect, p: dict[str, Any], alias: str) -> str:
    """The explicit column list every UNION ALL branch projects (the dictionary's
    field list, recorded on the plan), so the branches agree on arity and the
    ROW_NUMBER helper column never leaks. A stale dictionary fails LOUDLY here."""
    cols = list(p.get("columns") or [])
    if not cols:
        return f"{alias}.*"
    return ", ".join(d.col(alias, c) for c in cols)


def _hash_columns(p: dict[str, Any]) -> list[str]:
    keys = list(p.get("keys") or [])
    if keys:
        return keys
    # no key: hash the predicate + strata columns (every column the plan knows)
    cols = list(p.get("predicate_columns") or [])
    for s in p.get("strata") or []:
        if s["column"] not in cols:
            cols.append(s["column"])
    return cols or ["*"]


def _order_expr(d: _Dialect, p: dict[str, Any], alias: str, columns: list[str]) -> str:
    seed = int(p.get("seed", DEFAULT_SEED))
    buckets = int(p.get("hash_buckets", DEFAULT_HASH_BUCKETS))
    h = d.hash_of(alias, columns) if columns != ["*"] else "0"
    tie = ", ".join(d.col(alias, c) for c in columns if c != "*")
    order = d.mod(f"{h} + {seed}", buckets)
    return f"{order}, {tie}" if tie else order


def _cell_expr(d: _Dialect, s: dict[str, Any], alias: str) -> str:
    if "values" in s:
        return d.col(alias, s["column"])
    n = int(s.get("bucket_count") or len(s.get("buckets") or []) or DEFAULT_COLUMN_BUCKETS)
    return d.mod(d.hash_of(alias, [s["column"]]), n)


def _stratum_filter(d: _Dialect, s: dict[str, Any], alias: str) -> str:
    if "values" in s:
        vals = ", ".join(d.literal(v) for v in s["values"])
        return f"{d.col(alias, s['column'])} IN ({vals})"
    return f"{d.col(alias, s['column'])} IS NOT NULL"


def _stratum_rows_select(d: _Dialect, p: dict[str, Any], s: dict[str, Any], k: int, idx: int) -> str:
    t = d.ident(p["table"])
    hcols = _hash_columns(p)
    label = f"{s['column']} ({s['basis']}; {'by value' if 'values' in s else 'by hash bucket'})"
    return (
        f"-- stratum {idx}: {label} -- {k} row(s) per cell\n"
        f"SELECT {_proj(d, p, 'ct6_s%d' % idx)} FROM (\n"
        f"  SELECT t.*, ROW_NUMBER() OVER (PARTITION BY {_cell_expr(d, s, 't')}"
        f" ORDER BY {_order_expr(d, p, 't', hcols)}) AS ct6_rn\n"
        f"  FROM {t} AS t\n"
        f"  WHERE {_stratum_filter(d, s, 't')}\n"
        f") AS ct6_s{idx} WHERE ct6_rn <= {k}"
    )


def _stratum_groups_select(d: _Dialect, p: dict[str, Any], s: dict[str, Any], k: int, idx: int) -> str:
    """Sample DISTINCT group keys per stratum cell, then join back EVERY row of each
    kept group -- the group-preserving form."""
    t = d.ident(p["table"])
    gkeys = list(p["group_preserving_keys"])
    distinct_cols = list(dict.fromkeys(gkeys + [s["column"]]))
    sel = ", ".join(d.col("t", c) for c in distinct_cols)
    on = " AND ".join(f"{d.col('t', c)} = {d.col('kept', c)}" for c in gkeys)
    label = f"{s['column']} ({s['basis']}; {'by value' if 'values' in s else 'by hash bucket'})"
    return (
        f"-- stratum {idx}: {label} -- {k} whole group(s) per cell, groups keyed on "
        f"{', '.join(gkeys)}\n"
        f"SELECT {_proj(d, p, 't')} FROM {t} AS t\n"
        f"JOIN (\n"
        f"  SELECT * FROM (\n"
        f"    SELECT g.*, ROW_NUMBER() OVER (PARTITION BY {_cell_expr(d, s, 'g')}"
        f" ORDER BY {_order_expr(d, p, 'g', gkeys)}) AS ct6_rn\n"
        f"    FROM (SELECT DISTINCT {sel} FROM {t} AS t WHERE {_stratum_filter(d, s, 't')}) AS g\n"
        f"  ) AS ct6_g{idx} WHERE ct6_rn <= {k}\n"
        f") AS kept ON {on}"
    )


def _wrap_groups(d: _Dialect, p: dict[str, Any], inner: str, label: str) -> str:
    """In group mode an edge select pulls the WHOLE groups of its edge rows."""
    t = d.ident(p["table"])
    gkeys = list(p["group_preserving_keys"])
    on = " AND ".join(f"{d.col('t', c)} = {d.col('e', c)}" for c in gkeys)
    return (
        f"-- {label} (whole groups)\n"
        f"SELECT {_proj(d, p, 't')} FROM {t} AS t JOIN (\n{inner}\n) AS e ON {on}"
    )


def _edge_selects(d: _Dialect, p: dict[str, Any], k: int, groups: bool) -> list[str]:
    t = d.ident(p["table"])
    hcols = _hash_columns(p)
    order = _order_expr(d, p, "t", hcols)
    gkeys = list(p.get("group_preserving_keys") or [])
    full = _proj(d, p, "t")
    proj = ", ".join(d.col("t", c) for c in gkeys) if groups else full
    out: list[str] = []
    edge = p.get("edge_rows") or {}

    def emit(label: str, body: str) -> None:
        if groups:
            out.append(_wrap_groups(d, p, body, label))
        else:
            out.append(f"-- {label}\n{body}")

    for col in edge.get("nulls") or []:
        if groups and col in gkeys:
            # a NULL group key can never join back to its group: select those rows directly
            out.append(f"-- edge: NULL {col} (a NULL group key has no group to keep whole)\n"
                       f"SELECT * FROM (SELECT {full} FROM {t} AS t WHERE {d.col('t', col)} IS NULL "
                       f"ORDER BY {order} LIMIT {k}) AS ct6_null_{_slug(col)}")
            continue
        emit(f"edge: NULL {col}",
             f"SELECT * FROM (SELECT {proj} FROM {t} AS t WHERE {d.col('t', col)} IS NULL "
             f"ORDER BY {order} LIMIT {k}) AS ct6_null_{_slug(col)}")
    for b in edge.get("boundaries") or []:
        direction = "ASC" if b["edge"] == "min" else "DESC"
        emit(f"edge: {b['edge']} {b['column']}",
             f"SELECT * FROM (SELECT {proj} FROM {t} AS t WHERE {d.col('t', b['column'])} IS NOT NULL "
             f"ORDER BY {d.col('t', b['column'])} {direction}, {order} LIMIT {k}) "
             f"AS ct6_{b['edge']}_{_slug(b['column'])}")
    dup_cols = list(edge.get("duplicates_on") or [])
    if dup_cols:
        gsel = ", ".join(d.ident(c) for c in dup_cols)
        on = " AND ".join(f"{d.col('t', c)} = {d.col('dup', c)}" for c in dup_cols)
        emit(f"edge: duplicates on {', '.join(dup_cols)}",
             f"SELECT * FROM (SELECT {proj} FROM {t} AS t JOIN (\n"
             f"  SELECT {gsel} FROM {t} GROUP BY {gsel} HAVING COUNT(*) > 1\n"
             f") AS dup ON {on} ORDER BY {order} LIMIT {k * 2}) AS ct6_dups")
    reported = edge.get("reported") or []
    if reported:
        clauses: list[str] = []
        skipped: list[str] = []
        for row in reported:
            preds = [f"{d.col('t', c)} = {d.literal(v)}" for c, v in sorted(row.items())
                     if c in (p.get("keys") or []) or not p.get("keys")]
            if preds:
                clauses.append("(" + " AND ".join(preds) + ")")
            else:
                skipped.append(json.dumps(row, sort_keys=True))
        if clauses:
            emit(f"edge: {len(clauses)} reported row(s) by key",
                 f"SELECT * FROM (SELECT {proj} FROM {t} AS t WHERE\n  "
                 + "\n  OR ".join(clauses) + ") AS ct6_reported")
        for s in skipped:
            out.append(f"-- reported row carries no key column, select it by hand: {s}")
    return out


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(name))


def render_sql(plan_dict: dict[str, Any], dialect: str, variant: str = "auto") -> str:
    """Render the sample query for `dialect`. `variant` is `rows` (per-row
    stratified pick), `groups` (DISTINCT group keys first, then join back whole
    groups), or `auto` (groups when the plan carries `group_preserving_keys`).
    Deterministic: the same plan + dialect + variant renders byte-identical SQL,
    and the same seed selects the same rows on the same data."""
    if variant not in VARIANTS:
        raise ValueError(f"variant {variant!r} not in {VARIANTS}")
    if plan_dict.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"not a {PLAN_SCHEMA} plan (schema={plan_dict.get('schema')!r})")
    d = _Dialect(dialect)
    gkeys = list(plan_dict.get("group_preserving_keys") or [])
    groups = (variant == "groups") or (variant == "auto" and bool(gkeys))
    if groups and not gkeys:
        raise ValueError("group-preserving variant requested but the plan has no group_preserving_keys")
    k = int(plan_dict["sizing"]["min_per_stratum"])
    hcols = _hash_columns(plan_dict)
    strata = plan_dict.get("strata") or []

    parts: list[str] = []
    for i, s in enumerate(strata, start=1):
        parts.append(_stratum_groups_select(d, plan_dict, s, k, i) if groups
                     else _stratum_rows_select(d, plan_dict, s, k, i))
    edges = _edge_selects(d, plan_dict, k, groups)
    selects = parts + [e for e in edges if not e.startswith("-- reported row carries")]
    notes = [e for e in edges if e.startswith("-- reported row carries")]

    header = [
        f"-- {PLAN_SCHEMA} :: table {plan_dict['table']} :: dialect {d.name} :: "
        f"variant {'groups' if groups else 'rows'} :: seed {plan_dict.get('seed')}",
        f"-- hash: {d.hash_fn} ({d.name}) over {', '.join(hcols)} -> "
        f"MOD(ABS(hash) + seed, {plan_dict.get('hash_buckets', DEFAULT_HASH_BUCKETS)}) orders the pick",
        f"-- strata: {len(strata)} ; edge selects: {len(selects) - len(strata)} ; "
        f"n_target {plan_dict.get('n_target')} ; {k} row(s) per cell",
        "-- branches may repeat a row; dedupe on the key columns when materializing",
    ]
    if d.name == "sqlite":
        header.append("-- sqlite: register ct6_hash on the connection first "
                      "(scripts/data_dictionary/sampling.py register_sqlite_hash)")
    if d.name == "snowflake":
        header.append("-- snowflake: double-quoted identifiers are case-sensitive")
    if groups:
        header.append(f"-- group-preserving: whole groups kept on {', '.join(gkeys)}")
    body = "\nUNION ALL\n".join(selects) if selects else "-- (no strata and no edge rows)"
    return "\n".join(header + [body] + notes) + "\n"


# --------------------------------------------------------------------------- #
# before/after diff
# --------------------------------------------------------------------------- #

def _stratum_label(row: dict[str, Any], strata_columns: list[str]) -> str:
    if not strata_columns:
        return "(all)"
    return "|".join(f"{c}={'NULL' if row.get(c) is None else row.get(c)}" for c in strata_columns)


def _key_of(row: dict[str, Any], key_columns: list[str]) -> str:
    if key_columns:
        return json.dumps([row.get(c) for c in key_columns], sort_keys=True, default=str)
    return json.dumps(row, sort_keys=True, default=str)


def _checksum(keys: list[str]) -> str:
    h = hashlib.sha256()
    for k in sorted(keys):
        h.update(k.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _numeric_columns(rows: list[dict[str, Any]], exclude: set[str]) -> list[str]:
    cols: dict[str, bool] = {}
    for r in rows:
        for c, v in r.items():
            if c in exclude or v is None:
                continue
            cols[c] = cols.get(c, True) and _is_number(v)
    return sorted(c for c, ok in cols.items() if ok)


def _sum(rows: list[dict[str, Any]], col: str) -> float | int:
    total: float | int = 0
    for r in rows:
        v = r.get(col)
        if _is_number(v):
            total += v
    return total


def _bucket(rows: list[dict[str, Any]], strata_columns: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(_stratum_label(r, strata_columns), []).append(r)
    return out


def _compare(before: list[dict[str, Any]], after: list[dict[str, Any]],
             key_columns: list[str], numeric_cols: list[str]) -> dict[str, Any]:
    bkeys = [_key_of(r, key_columns) for r in before]
    akeys = [_key_of(r, key_columns) for r in after]
    bset, aset = set(bkeys), set(akeys)
    return {
        "before_rows": len(before), "after_rows": len(after), "row_delta": len(after) - len(before),
        "before_key_checksum": _checksum(bkeys), "after_key_checksum": _checksum(akeys),
        "keys_identical": sorted(bkeys) == sorted(akeys),
        "keys_added": len(aset - bset), "keys_removed": len(bset - aset),
        "numeric": {
            c: {"before": _sum(before, c), "after": _sum(after, c),
                "delta": _sum(after, c) - _sum(before, c)}
            for c in numeric_cols
        },
    }


def diff_report(
    before_rows: list[dict[str, Any]], after_rows: list[dict[str, Any]],
    strata_columns: list[str], key_columns: list[str],
) -> dict[str, Any]:
    """Compare a sample before and after a change: per stratum (the tuple of
    `strata_columns` values) the row counts, sha256 key-set checksums (sorted keys,
    so order never matters), keys added/removed, and the sum deltas of every numeric
    column (key + strata columns excluded -- summing ids means nothing). Pure and
    deterministic; a stratum present on only one side reports the other as 0."""
    strata_columns = list(strata_columns or [])
    key_columns = list(key_columns or [])
    exclude = set(strata_columns) | set(key_columns)
    numeric_cols = _numeric_columns(list(before_rows) + list(after_rows), exclude)
    b_by, a_by = _bucket(list(before_rows), strata_columns), _bucket(list(after_rows), strata_columns)
    strata_out: list[dict[str, Any]] = []
    for label in sorted(set(b_by) | set(a_by)):
        cmp = _compare(b_by.get(label, []), a_by.get(label, []), key_columns, numeric_cols)
        cmp["stratum"] = label
        strata_out.append(cmp)
    totals = _compare(list(before_rows), list(after_rows), key_columns, numeric_cols)
    changed = (not totals["keys_identical"]
               or any(v["delta"] != 0 for v in totals["numeric"].values())
               or any(not s["keys_identical"] for s in strata_out))
    return {
        "schema": DIFF_SCHEMA,
        "strata_columns": strata_columns, "key_columns": key_columns,
        "numeric_columns": numeric_cols,
        "totals": totals, "strata": strata_out,
        "strata_changed": [s["stratum"] for s in strata_out
                           if not s["keys_identical"] or any(v["delta"] != 0 for v in s["numeric"].values())],
        "verdict": "changed" if changed else "unchanged",
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(obj: Any, as_json: bool, summary: str) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, sort_keys=True))
    else:
        print(summary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sample-first iteration engine (sample-plan/v1).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("plan", help="Build a sample plan from a data-dictionary sidecar.")
    pl.add_argument("--dictionary", required=True, help="data-dictionary.json (or the dir holding it)")
    pl.add_argument("--table", required=True)
    pl.add_argument("--predicate", nargs="*", default=[], help="the column(s) the change depends on")
    pl.add_argument("--change-kind", required=True, choices=list(CHANGE_KINDS))
    pl.add_argument("--reported-rows", default=None, help="JSON list of the rows a bug report named")
    pl.add_argument("--group-keys", nargs="*", default=None, help="explicit group keys to keep whole")
    pl.add_argument("--seed", type=int, default=DEFAULT_SEED)
    pl.add_argument("--min-per-stratum", type=int, default=DEFAULT_MIN_PER_STRATUM)
    pl.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    pl.add_argument("--threshold-rows", type=int, default=DEFAULT_THRESHOLD_ROWS)
    pl.add_argument("--allow-local-file", action="store_true",
                    help="the project's principles allow a local materialization")
    pl.add_argument("--out", default=None, help="write the plan JSON here")
    pl.add_argument("--json", action="store_true")

    sq = sub.add_parser("sql", help="Render the sample SQL for a dialect.")
    sq.add_argument("--plan", required=True)
    sq.add_argument("--dialect", required=True, choices=list(DIALECTS))
    sq.add_argument("--variant", default="auto", choices=list(VARIANTS))
    sq.add_argument("--out", default=None)

    df = sub.add_parser("diff", help="Diff a sample before/after a change, per stratum.")
    df.add_argument("--before", required=True, help="JSON list of rows")
    df.add_argument("--after", required=True, help="JSON list of rows")
    df.add_argument("--plan", default=None, help="strata + keys come from the plan")
    df.add_argument("--strata", nargs="*", default=None, help="override the strata columns")
    df.add_argument("--keys", nargs="*", default=None, help="override the key columns")
    df.add_argument("--json", action="store_true")

    ss = sub.add_parser("should-sample", help="Decide whether sampling pays, with the reason.")
    ss.add_argument("--dictionary", required=True)
    ss.add_argument("--table", required=True)
    ss.add_argument("--threshold-rows", type=int, default=DEFAULT_THRESHOLD_ROWS)
    ss.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "plan":
            dictionary = load_dictionary(args.dictionary)
            reported = _read_json(args.reported_rows) if args.reported_rows else None
            result = plan(
                dictionary, args.table, args.predicate, args.change_kind,
                reported_rows=reported, seed=args.seed, min_per_stratum=args.min_per_stratum,
                max_rows=args.max_rows, threshold_rows=args.threshold_rows,
                group_keys=args.group_keys, allow_local_file=args.allow_local_file,
            )
            if args.out:
                Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            _emit(result, args.json,
                  f"sample plan for {args.table}: {len(result['strata'])} strata, "
                  f"n_target {result['n_target']}, seed {result['seed']}, "
                  f"group keys {result['group_preserving_keys'] or 'none'}; "
                  f"{result['threshold']['reason']}")
            return 0
        if args.cmd == "sql":
            sql = render_sql(_read_json(args.plan), args.dialect, args.variant)
            if args.out:
                Path(args.out).write_text(sql, encoding="utf-8")
            print(sql, end="")
            return 0
        if args.cmd == "diff":
            strata, keys = args.strata, args.keys
            if args.plan:
                p = _read_json(args.plan)
                if strata is None:
                    strata = [s["column"] for s in p.get("strata") or []]
                if keys is None:
                    keys = list(p.get("keys") or [])
            report = diff_report(_read_json(args.before), _read_json(args.after), strata or [], keys or [])
            _emit(report, args.json,
                  f"sample diff: {report['verdict']} - {len(report['strata'])} strata, "
                  f"{len(report['strata_changed'])} changed, rows {report['totals']['before_rows']} -> "
                  f"{report['totals']['after_rows']}")
            return 0
        if args.cmd == "should-sample":
            dictionary = load_dictionary(args.dictionary)
            verdict = should_sample(dictionary, args.table, args.threshold_rows)
            _emit(verdict, args.json, f"should-sample {args.table}: {verdict['should_sample']} - {verdict['reason']}")
            return 0
    except (KeyError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
