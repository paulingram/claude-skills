#!/usr/bin/env python3
"""Data Dictionary engine (stdlib-only) — the deterministic machine behind the
`data-dictionary` skill (CT6 v3.17.0; requirements DD-1 … DD-18).

Builds a data dictionary from a reachable database (live inspection, DD-9/DD-10)
plus code/doc-supplied context (DD-8), producing the standard artifact
`DATA_DICTIONARY_MAP.md` + a machine sidecar `data-dictionary.json` (DD-7, DD-16).

Like `hooks/lineage_graph.py` is to `data-lineage-mapping`, this module is the
DETERMINISTIC machine and the skill body is the contract: only the deterministic
pieces live here — SQLite schema introspection, ~100-row sampling (DD-10),
grain/dimensionality inference (DD-11), field inference (DD-12), the FIXED
provenance vocabulary (DD-13), corroboration (DD-14), the by-field/by-table
reference map + the relational/blend map (DD-7), and the serializer. The
LLM-judgment pieces (recursive code analysis that follows objects masking DB
connections — DD-3/DD-4 — doc analysis — DD-5 — and prose field definitions) are
the SKILL BODY's job; this module never guesses prose, it computes from data.

Live-inspection adapter: SQLite via stdlib `sqlite3`. Other engines
(Postgres/MySQL/…) follow the same shape but need their own driver + credentials,
which the skill body documents — they are deliberately NOT bundled (the plugin's
stdlib-only contract). DD-9/DD-10 against a production DB therefore require the
caller to supply a reachable connection; this module is exercised end-to-end
against a local SQLite stand-in.

CLI:
    python data_dictionary.py build-sqlite <db.sqlite> [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ARTIFACT_NAME = "DATA_DICTIONARY_MAP.md"
SIDECAR_NAME = "data-dictionary.json"

# DD-13 — the FIXED provenance vocabulary. A field's value is sourced as exactly
# one of these. Extend HERE (nowhere else) if a new source type is ever needed.
PROVENANCE_TYPES: tuple[str, ...] = (
    "direct-user-input",   # the user told us this definition
    "direct-code-comment", # a code comment / README stated it
    "inference",           # inferred from name/columns/structure
    "live-data",           # read from the live database (sampling)
)

CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low")

# Below this many sampled rows, an INFERRED unique key (no declared PK) is not
# trustworthy — N distinct values in N rows is coincidence, not proof of a key.
# Such keys are hedged in the grain string and never asserted above "medium".
MIN_KEY_SAMPLE = 20

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")
_ZIP5_RE = re.compile(r"^\d{5}$")


def _q(identifier: str) -> str:
    """Quote a SQL identifier, DOUBLING embedded double-quotes so a table or
    column legally named e.g. `a"b` cannot break the statement. The `.sqlite`
    file is untrusted input (the caller points the tool at an arbitrary DB whose
    author controls the identifier names), so escaping — not trust — is what
    keeps the interpolated PRAGMA / SELECT statements safe."""
    return '"' + str(identifier).replace('"', '""') + '"'


# --------------------------------------------------------------------------- #
# Live inspection (DD-9) + sampling (DD-10) — SQLite adapter
# --------------------------------------------------------------------------- #

def introspect_sqlite(db_path: str | Path) -> dict[str, Any]:
    """Read the schema of a SQLite DB: tables, columns (name/type/pk/notnull),
    and declared foreign keys. Identifier names are quote-escaped via `_q`
    before interpolation (the DB file is untrusted; see `_q`)."""
    p = Path(db_path)
    conn = sqlite3.connect(str(p))
    try:
        conn.row_factory = sqlite3.Row
        tables: dict[str, list[dict[str, Any]]] = {}
        foreign_keys: list[dict[str, Any]] = []
        names = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        for t in names:
            cols: list[dict[str, Any]] = []
            for row in conn.execute(f'PRAGMA table_info({_q(t)})'):
                cols.append({
                    "name": row["name"],
                    "type": (row["type"] or "").strip(),
                    "pk": bool(row["pk"]),
                    "notnull": bool(row["notnull"]),
                })
            tables[t] = cols
            for row in conn.execute(f'PRAGMA foreign_key_list({_q(t)})'):
                foreign_keys.append({
                    "from_table": t, "from_col": row["from"],
                    "to_table": row["table"], "to_col": row["to"], "kind": "db-fk",
                })
        return {"db_name": p.stem, "tables": tables, "foreign_keys": foreign_keys}
    finally:
        conn.close()


def sample_table(conn: sqlite3.Connection, table: str, limit: int = 100) -> list[dict[str, Any]]:
    """DD-10 — sample roughly the first `limit` (default 100) rows of `table`."""
    cur = conn.execute(f'SELECT * FROM {_q(table)} LIMIT ?', (int(limit),))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# --------------------------------------------------------------------------- #
# Inference (DD-11 grain, DD-12 field) + corroboration (DD-14)
# --------------------------------------------------------------------------- #

def _uniqueness(rows: list[dict[str, Any]], col: str) -> float:
    """Fraction of distinct non-null values for `col` in the sample (0..1)."""
    non_null = [r.get(col) for r in rows if r.get(col) is not None]
    if not non_null:
        return 0.0
    return len(set(non_null)) / len(non_null)


def infer_grain(table: str, columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """DD-11 — infer the grain (one-row-per-what) from declared PK + sampled
    column uniqueness."""
    col_names = [c["name"] for c in columns]
    pks = [c["name"] for c in columns if c.get("pk")]
    ratios = {c: round(_uniqueness(rows, c), 4) for c in col_names}
    unique_cols = [c for c in col_names if rows and ratios[c] == 1.0]
    small_sample_key = False
    if pks:
        grain = f"one row per {'+'.join(pks)} (declared primary key)"
        key = pks
    elif len(unique_cols) == 1:
        key = unique_cols
        grain = f"one row per {unique_cols[0]} (inferred unique key)"
    elif unique_cols:
        idlike = [c for c in unique_cols if c.lower() == "id" or c.lower().endswith("_id")]
        key = [idlike[0]] if idlike else [unique_cols[0]]
        grain = (f"one row per {key[0]} (one of several unique columns in the "
                 f"sample: {', '.join(unique_cols)})")
    else:
        grain = "non-unique grain (fact/event level — no single unique column in the sample)"
        key = []
    # An INFERRED key (no declared PK) from a tiny sample is coincidence, not
    # proof — N distinct values in N rows proves nothing. Hedge it honestly.
    if key and not pks and len(rows) < MIN_KEY_SAMPLE:
        small_sample_key = True
        grain += (f" — INFERRED from only {len(rows)} sampled row(s); "
                  f"uniqueness on a small sample is NOT proof of a key")
    return {
        "grain": grain, "inferred_key": key, "declared_pk": pks,
        "uniqueness_ratios": ratios, "sampled_rows": len(rows),
        "small_sample_key": small_sample_key,
    }


def _infer_dtype(values: list[Any]) -> str:
    if not values:
        return "unknown"
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "integer"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "numeric"
    if all(isinstance(v, (bytes, bytearray)) for v in values):
        return "blob"
    return "text"


def infer_field(table: str, column: str, sample_values: list[Any], declared_type: str = "") -> dict[str, Any]:
    """DD-12 — infer a field's meaning + type from its name, declared type, and
    sampled values. Returns the inferred meaning + the evidence used."""
    name = column.lower()
    non_null = [v for v in sample_values if v is not None]
    as_str = [str(v) for v in non_null]
    ftype = declared_type or _infer_dtype(non_null)
    evidence: list[str] = []

    if name == "id":
        meaning, why = "row identifier (primary key candidate)", "name is 'id'"
    elif name.endswith("_id"):
        meaning, why = f"identifier — foreign-key reference to '{name[:-3]}'", "name ends with '_id'"
    elif "zip" in name and as_str and all(_ZIP5_RE.match(x) for x in as_str):
        meaning, why = "5-digit ZIP code", "every sampled value is a 5-digit string"
    elif "email" in name or (as_str and all(_EMAIL_RE.match(x) for x in as_str)):
        meaning, why = "email address", "name/values match an email pattern"
    elif name.endswith("_at") or "date" in name or (as_str and all(_ISO_DATE_RE.match(x) for x in as_str)):
        meaning, why = "date / timestamp", "name or sampled values look like a date"
    elif re.match(r"^address\d+$", name):
        meaning, why = f"address line {name[-1]}", "name is 'addressN'"
    elif "address" in name:
        meaning, why = "address component", "name contains 'address'"
    elif "hash" in name:
        meaning, why = "hash key / surrogate identifier", "name contains 'hash'"
    else:
        meaning, why = column.replace("_", " ").strip().capitalize(), "inferred from the column name"
    evidence.append(why)
    return {"inferred_meaning": meaning, "inferred_type": ftype, "evidence": evidence}


def corroborate_key_claim(rows: list[dict[str, Any]], table: str, claimed_key_col: str) -> dict[str, Any]:
    """DD-14 — verify a claimed key against the actual sampled data. Flags the
    doc's example (user says it keys on customer_id, but it actually keys on a
    hash/name) by checking the claimed column's uniqueness vs. the real unique
    columns."""
    ratio = _uniqueness(rows, claimed_key_col) if rows else 0.0
    agrees = bool(rows) and ratio == 1.0
    actual_unique = [c for c in (rows[0].keys() if rows else []) if _uniqueness(rows, c) == 1.0]
    conflict = None
    if not agrees:
        conflict = (
            f"claimed key {claimed_key_col!r} is NOT unique in the sample "
            f"(uniqueness {ratio:.2f}); the actual unique column(s) are "
            f"{actual_unique or 'none in the sample'}"
        )
    return {
        "claimed_key": claimed_key_col, "agrees": agrees, "uniqueness": round(ratio, 4),
        "actual_unique_columns": actual_unique, "conflict": conflict,
    }


def corroborate_definition(
    rows: list[dict[str, Any]], table: str, column: str, *,
    claimed_type: str | None = None, claims_key: bool = False,
) -> dict[str, Any]:
    """DD-14 — corroborate ANY provided definition against the sampled data, not
    only key claims. A key claim delegates to `corroborate_key_claim`; a type
    claim checks the sampled values' actual dtype/format and flags a mismatch
    (e.g. user says a free-text column is a boolean flag); with neither, it still
    records that the values WERE inspected (the provided definition is not
    contradicted by an obvious type/format conflict)."""
    if claims_key:
        v = corroborate_key_claim(rows, table, column)
        v["checked"] = True
        return v
    non_null = [r.get(column) for r in rows if r.get(column) is not None] if rows else []
    actual_type = _infer_dtype(non_null)
    as_str = [str(x) for x in non_null]
    agrees = True
    conflict = None
    if claimed_type:
        ct = claimed_type.strip().lower()
        agrees = bool(
            (ct in ("int", "integer") and actual_type == "integer")
            or (ct in ("float", "numeric", "number", "decimal") and actual_type in ("integer", "numeric"))
            or (ct in ("bool", "boolean") and actual_type == "boolean")
            or (ct in ("str", "string", "text", "varchar", "char") and actual_type in ("text", "unknown"))
            or (ct in ("blob", "bytes") and actual_type == "blob")
            or (ct in ("date", "datetime", "timestamp") and as_str and all(_ISO_DATE_RE.match(x) for x in as_str))
            or (ct in ("email",) and as_str and all(_EMAIL_RE.match(x) for x in as_str))
        )
        if not agrees:
            conflict = (
                f"claimed type {claimed_type!r} for {table}.{column} does not match the "
                f"sampled data (actual type looks like {actual_type!r}"
                f"{'; no non-null values sampled' if not non_null else ''})"
            )
    return {
        "checked": True, "claimed_type": claimed_type, "agrees": agrees,
        "actual_type": actual_type, "non_null_sampled": len(non_null), "conflict": conflict,
    }


# --------------------------------------------------------------------------- #
# Reference map (DD-7d) + relational/blend map (DD-7e)
# --------------------------------------------------------------------------- #

def build_reference_map(code_refs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """DD-7d — given code references [{file,line,table,field}], build the
    by-table and by-field reference maps (which code touches which table/field)."""
    by_table: dict[str, list[dict[str, Any]]] = {}
    by_field: dict[str, list[dict[str, Any]]] = {}
    for ref in code_refs or []:
        t, f = ref.get("table"), ref.get("field")
        loc = {"file": ref.get("file"), "line": ref.get("line")}
        if t:
            by_table.setdefault(t, []).append({**loc, "field": f})
        if t and f:
            by_field.setdefault(f"{t}.{f}", []).append(loc)
    return {"by_table": by_table, "by_field": by_field}


def build_relation_map(
    foreign_keys: list[dict[str, Any]] | None,
    code_joins: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """DD-7e — merge declared DB foreign keys with code-inferred joins (e.g.
    census data merged onto individuals on zip code — a relation that exists in
    CODE, not in the DB schema)."""
    rels: list[dict[str, Any]] = []
    for fk in foreign_keys or []:
        rels.append({**fk, "kind": fk.get("kind", "db-fk")})
    for j in code_joins or []:
        rels.append({
            "from_table": j.get("from_table"), "from_col": j.get("from_col"),
            "to_table": j.get("to_table"), "to_col": j.get("to_col"),
            "kind": "code-join", "note": j.get("note", ""),
        })
    return rels


# --------------------------------------------------------------------------- #
# End-to-end build (DD-7 .. DD-14) + serialization (DD-7, DD-16)
# --------------------------------------------------------------------------- #

def build_from_sqlite(
    db_path: str | Path,
    *,
    code_refs: list[dict[str, Any]] | None = None,
    code_joins: list[dict[str, Any]] | None = None,
    provided_defs: dict[str, dict[str, Any]] | None = None,
    sample_limit: int = 100,
    built_at: str | None = None,
) -> dict[str, Any]:
    """Build the full data dictionary from a SQLite DB.

    `provided_defs` is the FIRST-PASS context (DD-8): a map
    "table.field" -> {definition, provenance, claims_key?}. Provided definitions
    win over inference but are corroborated against the data (DD-14); a claimed
    key that the data contradicts is flagged and downgraded to low confidence.
    """
    info = introspect_sqlite(db_path)
    provided_defs = provided_defs or {}
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        tables_out: dict[str, Any] = {}
        rows_total = 0
        for table, columns in info["tables"].items():
            rows = sample_table(conn, table, sample_limit)
            rows_total += len(rows)
            grain = infer_grain(table, columns, rows)
            # an inferred key from a tiny sample is hedged — don't assert it "high"
            small_key_cols = set(grain.get("inferred_key") or []) if grain.get("small_sample_key") else set()
            fields: list[dict[str, Any]] = []
            for c in columns:
                col = c["name"]
                sample_values = [r[col] for r in rows]
                has_value = any(v is not None for v in sample_values)
                inf = infer_field(table, col, sample_values, c.get("type", ""))
                key = f"{table}.{col}"
                pv = provided_defs.get(key)
                if pv:
                    definition = pv.get("definition", inf["inferred_meaning"])
                    provenance = pv.get("provenance", "direct-user-input")
                    if provenance not in PROVENANCE_TYPES:
                        provenance = "direct-user-input"
                    # DD-14: corroborate EVERY provided definition against the data,
                    # not only key claims (a claimed type that the data contradicts
                    # is flagged exactly like a bad key claim).
                    corro = corroborate_definition(
                        rows, table, col,
                        claimed_type=pv.get("expected_type"),
                        claims_key=bool(pv.get("claims_key")),
                    )
                    confidence = "high" if corro.get("agrees") else "low"
                else:
                    definition = inf["inferred_meaning"]
                    # only claim live-data when a non-null value was actually read;
                    # an all-null / empty column was never observed → inference.
                    provenance = "live-data" if has_value else "inference"
                    corro = None
                    confidence = "medium" if has_value else "low"
                # hedge a field that is the small-sample inferred key (never "high")
                if col in small_key_cols and confidence == "high":
                    confidence = "medium"
                fields.append({
                    "field": col, "type": inf["inferred_type"], "definition": definition,
                    "provenance": provenance, "confidence": confidence,
                    "inference_evidence": inf["evidence"], "corroboration": corro,
                })
            tables_out[table] = {"grain": grain, "fields": fields}
        return {
            "schema": "data-dictionary/v1",
            "db_name": info["db_name"],
            "schema_name": None,  # SQLite has no schema namespace
            "built_at": built_at,
            "tables": tables_out,
            "reference_map": build_reference_map(code_refs),
            "relational_map": build_relation_map(info["foreign_keys"], code_joins),
            "provenance_vocabulary": list(PROVENANCE_TYPES),
            "live_inspection": {
                "ran": True, "engine": "sqlite",
                "tables_sampled": len(info["tables"]),
                "rows_sampled_total": rows_total,
                "sample_limit": sample_limit,
            },
        }
    finally:
        conn.close()


def build_from_inputs(
    db_name: str,
    tables_spec: dict[str, list[str]] | None,
    *,
    provided_defs: dict[str, dict[str, Any]] | None = None,
    code_refs: list[dict[str, Any]] | None = None,
    code_joins: list[dict[str, Any]] | None = None,
    foreign_keys: list[dict[str, Any]] | None = None,
    built_at: str | None = None,
    reason: str = "no reachable database — built from code + docs + provided context",
) -> dict[str, Any]:
    """DD-2 no-DB path: build a dictionary WITHOUT live inspection, from a
    code/doc-derived `tables_spec` (`{table: [col, ...]}`) + `provided_defs`. No
    field is ever marked `live-data` and `live_inspection.ran` is False — the
    honest counterpart to `build_from_sqlite` for when no DB is reachable."""
    provided_defs = provided_defs or {}
    tables_out: dict[str, Any] = {}
    for table, cols in (tables_spec or {}).items():
        fields: list[dict[str, Any]] = []
        for col in cols:
            inf = infer_field(table, col, [], "")
            pv = provided_defs.get(f"{table}.{col}")
            if pv:
                definition = pv.get("definition", inf["inferred_meaning"])
                provenance = pv.get("provenance", "direct-user-input")
                if provenance not in PROVENANCE_TYPES:
                    provenance = "direct-user-input"
                confidence = "medium"
            else:
                definition = inf["inferred_meaning"]
                provenance = "inference"  # never live-data without a live read
                confidence = "low"
            fields.append({
                "field": col, "type": inf["inferred_type"], "definition": definition,
                "provenance": provenance, "confidence": confidence,
                "inference_evidence": inf["evidence"], "corroboration": None,
            })
        tables_out[table] = {
            "grain": {
                "grain": "unknown (no live inspection)", "inferred_key": [],
                "declared_pk": [], "uniqueness_ratios": {}, "sampled_rows": 0,
                "small_sample_key": False,
            },
            "fields": fields,
        }
    return {
        "schema": "data-dictionary/v1",
        "db_name": db_name,
        "schema_name": None,
        "built_at": built_at,
        "tables": tables_out,
        "reference_map": build_reference_map(code_refs),
        "relational_map": build_relation_map(foreign_keys, code_joins),
        "provenance_vocabulary": list(PROVENANCE_TYPES),
        "live_inspection": {
            "ran": False, "engine": None, "tables_sampled": 0,
            "rows_sampled_total": 0, "reason": reason,
        },
    }


def serialize_markdown(dd: dict[str, Any]) -> str:
    """DD-7 — render the data dictionary as `DATA_DICTIONARY_MAP.md`."""
    out = [
        "---",
        f"last_built: {dd.get('built_at') or 'unknown'}",
        f"db_name: {dd.get('db_name')}",
        f"schema_name: {dd.get('schema_name')}",
        "artifact: DATA_DICTIONARY_MAP",
        "---",
        "",
        f"# Data Dictionary — {dd.get('db_name')}",
        "",
        f"Provenance vocabulary (DD-13): {', '.join(dd['provenance_vocabulary'])}.",
        "",
    ]
    li = dd.get("live_inspection") or {}
    if li.get("ran"):
        out.append(
            f"Live inspection (DD-9/10): ran against {li.get('engine')} — "
            f"{li.get('tables_sampled')} table(s), {li.get('rows_sampled_total')} "
            f"row(s) sampled (limit {li.get('sample_limit')})."
        )
    else:
        out.append(
            "Live inspection (DD-9/10): NOT run "
            f"({li.get('reason', 'no database inspected')}) — every field is from "
            "code / docs / inference, never `live-data`."
        )
    out.append("")
    for table, tinfo in dd["tables"].items():
        out.append(f"## Table: `{table}`")
        out.append(f"- **Grain:** {tinfo['grain']['grain']}")
        out.append("")
        out.append("| Field | Type | Definition | Provenance | Confidence | Corroboration |")
        out.append("|---|---|---|---|---|---|")
        for f in tinfo["fields"]:
            corro = f.get("corroboration")
            corro_s = "ok" if (corro is None or corro.get("agrees")) else f"⚠ {corro.get('conflict')}"
            out.append(
                f"| `{f['field']}` | {f['type']} | {f['definition']} | "
                f"{f['provenance']} | {f['confidence']} | {corro_s} |"
            )
        out.append("")
    out.append("## Reference map (code → tables/fields)")
    by_table = dd["reference_map"]["by_table"]
    if by_table:
        for t, refs in by_table.items():
            for r in refs:
                field = f".{r['field']}" if r.get("field") else ""
                out.append(f"- `{t}{field}` ← {r.get('file')}:{r.get('line')}")
    else:
        out.append("- (no code references supplied)")
    out.append("")
    out.append("## Relational / blend map")
    if dd["relational_map"]:
        for rel in dd["relational_map"]:
            note = f" — {rel['note']}" if rel.get("note") else ""
            out.append(
                f"- `{rel['from_table']}.{rel['from_col']}` → "
                f"`{rel['to_table']}.{rel['to_col']}` ({rel['kind']}){note}"
            )
    else:
        out.append("- (no relations detected)")
    out.append("")
    return "\n".join(out)


def write_artifact(dd: dict[str, Any], out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / ARTIFACT_NAME
    js_path = out / SIDECAR_NAME
    md_path.write_text(serialize_markdown(dd), encoding="utf-8")
    js_path.write_text(json.dumps(dd, indent=2, sort_keys=True), encoding="utf-8")
    return md_path, js_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Data Dictionary engine (DD-1..18).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-sqlite", help="Build a data dictionary from a SQLite DB.")
    b.add_argument("db", help="Path to the SQLite database file.")
    b.add_argument("--out", default="docs", help="Output directory (default: docs).")
    b.add_argument("--sample", type=int, default=100, help="Rows to sample per table (default 100).")
    args = parser.parse_args(argv)
    if args.cmd == "build-sqlite":
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        dd = build_from_sqlite(args.db, sample_limit=args.sample, built_at=ts)
        md, js = write_artifact(dd, args.out)
        print(f"wrote {md} + {js} ({len(dd['tables'])} tables)")
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
