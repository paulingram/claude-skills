#!/usr/bin/env python3
"""Warehouse SQL-object mining engine (stdlib-only) — the deterministic machine
behind the `warehouse-sql-mining` skill (CT6 Run C; requirements SQL-MINING-1..N).

Reads SQL objects (stored-procedure / view / function definitions, from a
directory of `.sql` files or a supplied list) and extracts the shapes a
data-engineering exploration + a data dictionary actually consume:

* table-to-table **read/write** relationships (FROM/JOIN -> reads; INSERT/UPDATE/
  MERGE/DELETE -> writes),
* **join** shapes (`table.col = table.col`, aliases resolved),
* **filter** predicates (`column <op> value`),
* aggregate / ratio **metric** shapes (SUM / COUNT / AVG / MIN / MAX, and ratio
  expressions).

Three disciplines are load-bearing (they are what keeps CT6 from importing the
deng toolkit's fidelity problem along with its idea):

1. **Minimal vendored extractor, NOT a full parser (decision D6).** This is a
   regex/scan-based T-SQL/ANSI pattern extractor over SQL *text* — NOT an AST,
   NOT `sqlglot`, NOT any third-party parser. It recognizes ONLY the shapes the
   consumers use; everything it does not recognize is coverage-stat'd, never
   silently mis-parsed. It is import-clean stdlib so it lives cleanly in
   `scripts/` and adds no dependency.
2. **Parse-coverage honesty is a first-class output.** The artifact carries
   `{parsed, skipped:[{object,reason}], failed:[{object,reason}]}`. A
   dialect-specific / malformed / unparseable object lands in `skipped`/`failed`
   WITH a reason — never silently dropped, never silently mis-parsed — and a bad
   object never crashes the run.
3. **Corroboration is the gate.** Mined field/metric candidates enter the data
   dictionary at provenance `inference` (never stronger) and pass through
   `scripts/data_dictionary/data_dictionary.py::corroborate_definition`; a mined
   claim the data contradicts is flagged and confidence-downgraded, NOT accepted.
   Mined read/write relationships become `hooks/lineage_graph.py` `data_asset`
   node + `reads`/`writes` edge evidence — using ONLY the existing node/edge kinds.

The two reuse targets (`data_dictionary` corroboration + `lineage_graph`
identity/validation) are loaded by file path (the repo's `scripts/`/`hooks/` tiers
carry no package `__init__.py`), the same idiom `scripts/setup/install_*.py` use.
Both are stdlib-only leaf modules, so the load is side-effect-free.

CLI (mirrors `scripts/data_dictionary/data_dictionary.py`):
    python sql_mining.py mine <dir-or-files...> [--out <dir>]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Optional

ARTIFACT_NAME = "SQL_MINING_MAP.md"
SIDECAR_NAME = "sql-mining.json"
SCHEMA = "sql-mining/v1"

# The warn marker mirrors the data-dictionary serializer's conflict glyph. Written
# as a unicode escape so this module's SOURCE stays pure-ASCII (green under both
# Windows cp1252 and PYTHONUTF8=1); the rendered artifacts are always utf-8.
WARN_MARKER = "⚠"  # matches data_dictionary.py's conflict glyph; utf-8 source (PEP 3120)

# Mined content is NEVER stronger than this. The corroboration gate may only hold
# a candidate here or downgrade its confidence — it can never promote provenance.
MINED_PROVENANCE = "inference"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOADED: dict[str, Any] = {}


def _load(mod_name: str, rel_path: str) -> Any:
    """Load an in-repo stdlib leaf module by file path (cached).

    `scripts/` and `hooks/` carry no `__init__.py`, so a normal package import is
    unavailable; this is the same `spec_from_file_location` idiom the installers
    use. Both targets are pure-stdlib leaf modules with no import-time side
    effects, so loading them is safe and repeatable.
    """
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


def _data_dictionary() -> Any:
    return _load("ct6_sql_mining_dd", "scripts/data_dictionary/data_dictionary.py")


def _lineage_graph() -> Any:
    return _load("ct6_sql_mining_lg", "hooks/lineage_graph.py")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class SqlParseError(Exception):
    """Raised when an object is genuinely malformed (unterminated string /
    unbalanced parentheses). Callers route it to `failed` WITH the reason — the
    honest alternative to a silent half-parse."""


# --------------------------------------------------------------------------- #
# Scrub / mask (comment removal + string masking; the keyword-safety layer)
# --------------------------------------------------------------------------- #

# A qualified column reference `alias.column` (both bare identifiers).
_QUALCOL = r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*"
# A (optionally schema/db-qualified, optionally bracketed/quoted) table reference.
_IDENT = r'(?:\[[^\]]+\]|"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)'
_TABLEREF = rf"{_IDENT}(?:\.{_IDENT})*"

_AGG_FUNCS = ("SUM", "COUNT", "AVG", "MIN", "MAX")
# An aggregate call with a one-level-nested-paren-tolerant argument capture.
_AGG_ARG = r"[^()]*(?:\([^()]*\)[^()]*)*"
_AGG_CALL = rf"(?:{'|'.join(_AGG_FUNCS)})\s*\(\s*{_AGG_ARG}\s*\)"
# An actual aggregate CALL — an aggregate name at a WORD BOUNDARY followed by an
# open paren. Used to decide whether a division is a real ratio metric: a plain
# substring test ('count' in 'o.Discount / o.Total') is a false positive, so the
# `\b` anchor is load-bearing — 'count' inside 'Discount' is not a word-boundary
# match and therefore not a mined aggregate operand.
_AGG_CALL_PRESENT_RE = re.compile(rf"\b(?:{'|'.join(_AGG_FUNCS)})\s*\(", re.IGNORECASE)

# Alias-stop keywords: a bare word right after a table ref that is actually a
# clause keyword is NOT an alias.
_ALIAS_STOP = {
    "on", "where", "group", "order", "having", "join", "inner", "left", "right",
    "full", "cross", "outer", "union", "except", "intersect", "as", "with", "set",
    "values", "select", "and", "or", "using", "into", "from", "apply", "pivot",
    "unpivot", "for", "option", "go", "begin", "end",
}


def scrub_and_mask(sql: str) -> str:
    """Return `sql` with comments blanked and every string literal's interior
    masked, LENGTH-PRESERVING, so downstream keyword scans never match inside a
    string or comment while character positions still map 1:1 back to the raw
    text (object-header slicing relies on that mapping).

    Comment chars become spaces (newlines kept, so line structure survives); a
    string's interior + quotes-interior become `x` filler with the surrounding
    quotes preserved. A `(` inside a string therefore does not count toward the
    balance check, and a keyword inside a string never reads as a real clause.
    Raises :class:`SqlParseError` on an unterminated string or block comment, and
    on unbalanced parentheses — the genuine "this object is malformed" signals.
    """
    chars = list(sql)
    i, n = 0, len(chars)
    while i < n:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""
        # line comment: blank to end of line (keep the newline)
        if ch == "-" and nxt == "-":
            while i < n and chars[i] != "\n":
                chars[i] = " "
                i += 1
            continue
        # block comment: blank the whole span (keep newlines). T-SQL supports
        # NESTED block comments, so track DEPTH and only exit at depth 0 — stopping
        # at the FIRST `*/` would leak the tail (`... FROM PhantomTable */`) as real
        # SQL and mine a phantom, ungated relationship.
        if ch == "/" and nxt == "*":
            depth = 1
            k = i + 2
            while k < n and depth > 0:
                if chars[k] == "/" and k + 1 < n and chars[k + 1] == "*":
                    depth += 1
                    k += 2
                    continue
                if chars[k] == "*" and k + 1 < n and chars[k + 1] == "/":
                    depth -= 1
                    k += 2
                    continue
                k += 1
            if depth > 0:
                raise SqlParseError("unterminated block comment")
            for m in range(i, k):
                if chars[m] != "\n":
                    chars[m] = " "
            i = k
            continue
        # single-quoted string literal: keep the quotes, mask the interior to x
        if ch == "'":
            i += 1
            while i < n:
                if chars[i] == "'":
                    if i + 1 < n and chars[i + 1] == "'":  # escaped '' inside string
                        chars[i] = "x"
                        chars[i + 1] = "x"
                        i += 2
                        continue
                    break  # closing quote
                if chars[i] != "\n":
                    chars[i] = "x"
                i += 1
            else:
                raise SqlParseError("unterminated string literal")
            i += 1  # consume the closing quote
            continue
        i += 1
    masked = "".join(chars)
    if masked.count("(") != masked.count(")"):
        raise SqlParseError("unbalanced parentheses")
    return masked


def _normalize_table(ref: str) -> str:
    """Strip bracket/quote decoration from each segment of a table reference:
    `[dbo].[Order Details]` -> `dbo.Order Details`, `"raw"."Events"` -> `raw.Events`."""
    parts = []
    for seg in ref.split("."):
        seg = seg.strip()
        if len(seg) >= 2 and seg[0] == "[" and seg[-1] == "]":
            seg = seg[1:-1]
        elif len(seg) >= 2 and seg[0] == '"' and seg[-1] == '"':
            seg = seg[1:-1]
        parts.append(seg.strip())
    return ".".join(p for p in parts if p)


# --------------------------------------------------------------------------- #
# Object splitting
# --------------------------------------------------------------------------- #

_CREATE_HEADER_RE = re.compile(
    rf"\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(PROCEDURE|PROC|VIEW|FUNCTION|TRIGGER)\s+({_TABLEREF})",
    re.IGNORECASE,
)

_KIND_CANON = {"proc": "procedure", "procedure": "procedure", "view": "view",
               "function": "function", "trigger": "trigger"}


def split_objects(sql_text: str, source_stem: str) -> list[tuple[str, str, str]]:
    """Split a `.sql` file into `(object_name, kind, body)` tuples.

    Objects are delimited by `CREATE`/`ALTER (PROCEDURE|VIEW|FUNCTION|TRIGGER)`
    headers; a file with no such header is one `script` object named after the
    file. Header detection runs over the length-preserving masked text (so a
    `CREATE` inside a comment or string is not a boundary) and slices the RAW text
    by the same positions — the mask preserves character offsets exactly. Never
    raises: when the whole file is too malformed to mask, header detection falls
    back to the raw text so a declared object still keeps its real NAME (its
    malformed body surfaces as a per-object `failed`, never a dropped object).
    """
    try:
        header_text = scrub_and_mask(sql_text)  # positions map 1:1 to sql_text
    except SqlParseError:
        header_text = sql_text  # best-effort over raw for an un-maskable file

    headers = list(_CREATE_HEADER_RE.finditer(header_text))
    if not headers:
        return [(source_stem, "script", sql_text)]

    objects: list[tuple[str, str, str]] = []
    for idx, m in enumerate(headers):
        start = m.start()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(sql_text)
        raw_body = sql_text[start:end]
        name = _normalize_table(m.group(2))
        kind = _KIND_CANON.get(m.group(1).lower(), "object")
        objects.append((name, kind, raw_body))
    return objects


# --------------------------------------------------------------------------- #
# Per-object extraction
# --------------------------------------------------------------------------- #

_FROM_JOIN_RE = re.compile(rf"\b(?:FROM|JOIN)\s+({_TABLEREF})\s*(?:(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?", re.IGNORECASE)
_INSERT_RE = re.compile(rf"\bINSERT\s+(?:INTO\s+)?({_TABLEREF})", re.IGNORECASE)
_UPDATE_RE = re.compile(rf"\bUPDATE\s+({_TABLEREF})", re.IGNORECASE)
_MERGE_RE = re.compile(rf"\bMERGE\s+(?:INTO\s+)?({_TABLEREF})", re.IGNORECASE)
_DELETE_RE = re.compile(rf"\bDELETE\s+(?:FROM\s+)?({_TABLEREF})", re.IGNORECASE)
_JOIN_EQ_RE = re.compile(rf"({_QUALCOL})\s*=\s*({_QUALCOL})")
_AGG_RE = re.compile(rf"\b({'|'.join(_AGG_FUNCS)})\s*\(\s*({_AGG_ARG})\)\s*(?:AS\s+([A-Za-z_][A-Za-z0-9_]*))?", re.IGNORECASE)
# ratio: an expression with `/` where at least one operand is an aggregate call.
_RATIO_RE = re.compile(
    rf"((?:{_AGG_CALL}|{_QUALCOL}|[A-Za-z_][A-Za-z0-9_]*|[0-9.]+)\s*(?:\*\s*[0-9.]+\s*)?/\s*"
    rf"(?:{_AGG_CALL}|{_QUALCOL}|[A-Za-z_][A-Za-z0-9_]*|[0-9.]+))\s*(?:AS\s+([A-Za-z_][A-Za-z0-9_]*))?",
    re.IGNORECASE,
)
_FILTER_RE = re.compile(
    rf"({_QUALCOL})\s*(=|<>|!=|<=|>=|<|>|\bLIKE\b|\bIN\b|\bIS\b)\s*",
    re.IGNORECASE,
)


def _alias_map(masked: str) -> dict[str, str]:
    """Build `{alias: normalized_table}` from every FROM/JOIN clause."""
    amap: dict[str, str] = {}
    for m in _FROM_JOIN_RE.finditer(masked):
        table = _normalize_table(m.group(1))
        alias = m.group(2)
        if alias and alias.lower() not in _ALIAS_STOP:
            amap[alias] = table
        # a table with no alias is addressable by its own last segment too
        last = table.split(".")[-1]
        amap.setdefault(last, table)
    return amap


def _resolve(qualcol: str, amap: dict[str, str]) -> Optional[str]:
    """Resolve `alias.col` -> the alias's table (or None when unknown)."""
    prefix = qualcol.split(".")[0]
    return amap.get(prefix)


def _read_sources(masked: str) -> list[str]:
    reads: list[str] = []
    for m in _FROM_JOIN_RE.finditer(masked):
        t = _normalize_table(m.group(1))
        if t and t not in reads:
            reads.append(t)
    return reads


def _write_targets(masked: str) -> list[str]:
    writes: list[str] = []
    for rx in (_INSERT_RE, _UPDATE_RE, _MERGE_RE, _DELETE_RE):
        for m in rx.finditer(masked):
            t = _normalize_table(m.group(1))
            # ignore an UPDATE/DELETE that targets a bare alias resolved elsewhere:
            # still record it — the consumer treats a write target honestly.
            if t and t not in writes:
                writes.append(t)
    return writes


def _joins(masked: str, amap: dict[str, str]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    joins: list[dict[str, Any]] = []
    for m in _JOIN_EQ_RE.finditer(masked):
        left, right = m.group(1), m.group(2)
        key = tuple(sorted((left, right)))
        if key in seen:
            continue
        seen.add(key)
        joins.append({
            "left": left, "right": right,
            "left_table": _resolve(left, amap), "right_table": _resolve(right, amap),
        })
    return joins


def _metrics(masked: str) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    ratio_spans: list[tuple[int, int]] = []
    # ratio metrics first; record each ratio's expression span so the aggregates
    # that are its OPERANDS are not also emitted as standalone metrics (and do not
    # mis-attribute the ratio's trailing alias to an inner aggregate).
    for m in _RATIO_RE.finditer(masked):
        expr = re.sub(r"\s+", " ", m.group(1)).strip()
        if not _AGG_CALL_PRESENT_RE.search(expr):
            # a division with no real aggregate CALL operand is not a metric shape
            # we mine. Word-boundary matched so 'count' inside 'Discount'
            # (o.Discount / o.Total) is NOT a false-positive ratio.
            continue
        ratio_spans.append((m.start(1), m.end(1)))
        alias = m.group(2)
        key = ("ratio", expr, alias or "")
        if key in seen:
            continue
        seen.add(key)
        metrics.append({"func": "ratio", "shape": "ratio", "expr": expr, "alias": alias, "arg": None})
    for m in _AGG_RE.finditer(masked):
        if any(s <= m.start() < e for s, e in ratio_spans):
            continue  # this aggregate is an operand of a ratio, already captured
        func = m.group(1).upper()
        arg = re.sub(r"\s+", " ", m.group(2)).strip()
        alias = m.group(3)
        key = (func, arg, alias or "")
        if key in seen:
            continue
        seen.add(key)
        metrics.append({"func": func, "shape": "aggregate", "expr": f"{func}({arg})", "arg": arg, "alias": alias})
    return metrics


def _filters(masked: str, join_cols: set[str]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for m in _FILTER_RE.finditer(masked):
        col, op = m.group(1), m.group(2).strip()
        # a `col = col` equality is a join, already captured — don't double-count.
        tail = masked[m.end():m.end() + 64]
        if op == "=" and re.match(rf"\s*{_QUALCOL}", tail):
            continue
        key = (col, op)
        if key in seen:
            continue
        seen.add(key)
        filters.append({"column": col, "op": op})
    return filters


def extract_object(name: str, kind: str, body: str, source: str) -> dict[str, Any]:
    """Extract the shapes of ONE object. Raises :class:`SqlParseError` when the
    body is genuinely malformed (unterminated string / unbalanced parens)."""
    masked = scrub_and_mask(body)  # raises SqlParseError on malformed input
    amap = _alias_map(masked)
    reads = _read_sources(masked)
    writes = _write_targets(masked)
    # a write target that is only an alias (T-SQL `UPDATE a ... FROM t a`) resolves
    # to its real table; keep the real table when the alias maps.
    writes = [amap.get(w, w) for w in writes]
    writes = list(dict.fromkeys(writes))
    joins = _joins(masked, amap)
    metrics = _metrics(masked)
    join_cols = {j["left"] for j in joins} | {j["right"] for j in joins}
    filters = _filters(masked, join_cols)
    return {
        "object": name, "kind": kind, "source": source,
        "reads": reads, "writes": writes,
        "joins": joins, "filters": filters, "metrics": metrics,
    }


def _has_shape(obj: dict[str, Any]) -> bool:
    """A recognizable object has at least one read/write/join/metric shape."""
    return bool(obj["reads"] or obj["writes"] or obj["joins"] or obj["metrics"])


# --------------------------------------------------------------------------- #
# Dictionary candidates (corroboration-gated) — provenance `inference`
# --------------------------------------------------------------------------- #

def _candidates_for(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Emit mined field/metric candidates for one object, ALL at provenance
    `inference`. Metrics -> numeric metric candidates; join keys -> field
    candidates (type unknown). The (table, column) pair is what
    `corroborate_definition` later checks against sampled data."""
    table = obj["writes"][0] if obj["writes"] else obj["object"]
    out: list[dict[str, Any]] = []
    for i, m in enumerate(obj["metrics"]):
        column = m.get("alias") or f"{(m.get('func') or 'metric')}_{i}"
        out.append({
            "object": obj["object"], "table": table, "column": column,
            "definition": f"{m['expr']} — mined {m['shape']} metric from {obj['object']}",
            "provenance": MINED_PROVENANCE, "confidence": "medium",
            "claimed_type": "numeric", "kind": "metric",
        })
    for j in obj["joins"]:
        for side, tbl in (("left", j.get("left_table")), ("right", j.get("right_table"))):
            col = j[side]
            out.append({
                "object": obj["object"], "table": tbl or obj["object"], "column": col.split(".")[-1],
                "definition": f"join key {col} — mined from {obj['object']}",
                "provenance": MINED_PROVENANCE, "confidence": "low",
                "claimed_type": None, "kind": "field",
            })
    # Every RAW candidate is machine-marked uncorroborated + not-accepted. It has
    # NOT passed corroborate_definition yet (the no-context / text-only path has no
    # data to check against), so it must never read as an accepted claim — the
    # honest counterpart to the corroborate_mined_claim gate, so the skill's
    # corroboration claim matches what the code actually does.
    for cand in out:
        cand.setdefault("corroborated", False)
        cand.setdefault("accepted", False)
        cand.setdefault("needs_corroboration", True)
    return out


def _definition_conflict(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    """A mined definition conflicts with an existing corroborated one when their
    stated types differ (a coarse but honest text-level check — the miner has no
    data, so it can only compare the claim, and the data-level check via
    `corroborate_definition` is the primary gate)."""
    ct = (candidate.get("claimed_type") or "").strip().lower()
    et = (existing.get("type") or existing.get("claimed_type") or "").strip().lower()
    return bool(ct and et and ct != et)


def corroborate_mined_claim(
    candidate: dict[str, Any],
    *,
    rows: Optional[list[dict[str, Any]]] = None,
    corroborated_defs: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Route a mined candidate through the data-dictionary corroboration gate.

    The invariant: mined content is NEVER promoted above `inference`. When sampled
    `rows` are available they are checked via
    `data_dictionary.corroborate_definition` (the mandated composition, not a
    re-implementation); a disagreement flags the claim, downgrades its confidence
    to `low`, and marks it NOT accepted. An optional `corroborated_defs` map
    (`{"table.col": {type/definition, corroborated: True}}`) additionally flags a
    mined claim that conflicts with an already-corroborated definition. Acceptance
    is PER-FIELD: a candidate is corroborated/accepted ONLY when rows checked its
    exact column OR a corroborated def for that exact field was compared — a field
    merely absent from (or un-corroborated in) the supplied map, with no rows,
    stays uncorroborated + not-accepted, still `inference`.
    """
    dd = _data_dictionary()
    table = candidate.get("table")
    column = candidate.get("column")
    claimed_type = candidate.get("claimed_type")

    out = dict(candidate)
    out["provenance"] = MINED_PROVENANCE  # hard invariant — never stronger
    # `checked` is PER-FIELD, not "was some context supplied": a mined claim counts
    # as corroborated ONLY when rows actually inspected THIS candidate's column, OR
    # a CORROBORATED def for THIS EXACT field was compared against it. Merely
    # PASSING a corroborated_defs map that lacks the field — or holds it
    # un-corroborated — is NOT corroboration; the candidate stays uncorroborated +
    # not-accepted (the R1 residual, closed the same per-field way annotations.py's
    # F1 fix established). The old `ran = rows is not None or bool(corroborated_defs)`
    # was the bypass: it stamped a candidate whose field was absent from the map as
    # accepted/corroborated though nothing checked it.
    checked = False
    corro: Optional[dict[str, Any]] = None
    flagged = False
    conflict: Optional[str] = None

    if rows is not None:
        claims_key = bool(candidate.get("claims_key"))
        corro = dd.corroborate_definition(
            rows, table, column,
            claimed_type=claimed_type,
            claims_key=claims_key,
        )
        # F2 — mirror annotations' F-A5 and data_dictionary._corroborate_correction:
        # a rows check with ZERO non-null evidence for THIS column (an all-NULL
        # column, or a ghost column absent from the sampled rows) inspected nothing.
        # A TEXT-family claim reads actual_type 'unknown' and vacuously "agrees" on
        # that zero evidence — that vacuous agreement is NOT corroboration, so it is
        # treated as not-checked (stays uncorroborated, never accepted). A genuine
        # DISAGREEMENT (boolean/integer/date vs 'unknown') or a key claim (whose
        # verdict carries no non_null_sampled) is a real signal and keeps working.
        column_present = any(isinstance(r, dict) and column in r for r in rows)
        zero_evidence = (corro.get("non_null_sampled") == 0) or (not column_present)
        vacuous_agreement = zero_evidence and corro.get("agrees", True) and not claims_key
        if not vacuous_agreement:
            checked = True  # corroborate_definition genuinely inspected THIS column's data
            if not corro.get("agrees", True):
                flagged = True
                conflict = corro.get("conflict")

    if corroborated_defs:
        existing = corroborated_defs.get(f"{table}.{column}")
        if existing and existing.get("corroborated"):
            checked = True  # a CORROBORATED def for THIS EXACT field to compare against
            if _definition_conflict(candidate, existing):
                flagged = True
                conflict = conflict or (
                    f"mined definition of {table}.{column} conflicts with the corroborated "
                    f"definition (mined type {claimed_type!r} vs corroborated "
                    f"{existing.get('type') or existing.get('claimed_type')!r})"
                )

    base_conf = candidate.get("confidence", "medium")
    out["corroboration"] = corro
    out["flagged"] = flagged
    out["flag"] = WARN_MARKER if flagged else "ok"
    out["conflict"] = conflict
    out["confidence"] = "low" if flagged else base_conf
    # A claim is corroborated/accepted ONLY when its exact field was checked — rows
    # inspected it, OR a corroborated def for THIS field was compared. An unchecked
    # call stays not-accepted + needs_corroboration — the same honest marker the raw
    # candidates carry.
    out["corroborated"] = checked
    out["needs_corroboration"] = not checked
    out["accepted"] = checked and not flagged
    return out


# --------------------------------------------------------------------------- #
# Lineage emission — data_asset nodes + reads/writes edges (existing kinds only)
# --------------------------------------------------------------------------- #

def _asset_id(lg: Any, store: str, default_schema: str, table: str) -> str:
    """Build a canonical `asset://<store>/<schema>/<table>` id from a table ref."""
    parts = _normalize_table(table).split(".")
    if len(parts) >= 3:
        schema, tbl = parts[-2], parts[-1]
    elif len(parts) == 2:
        schema, tbl = parts[0], parts[1]
    else:
        schema, tbl = default_schema, parts[0]
    return lg.make_asset_id(store, schema or default_schema, tbl)


def emit_lineage(
    objects: list[dict[str, Any]],
    *,
    store: str = "warehouse",
    codebase: str = "warehouse",
    default_schema: str = "dbo",
) -> dict[str, Any]:
    """Emit a CDLG fragment for the mined objects using ONLY existing kinds: each
    object is a `function` node; each read/write table is a `data_asset` node;
    edges are `reads` / `writes`, attributed (via `match_basis`/`evidence`) to the
    object. The returned graph validates clean against
    `hooks/lineage_graph.py::validate_lineage_graph`."""
    lg = _lineage_graph()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def _asset_node(table: str) -> str:
        aid = _asset_id(lg, store, default_schema, table)
        nodes.setdefault(aid, {"id": aid, "kind": "data_asset", "name": _normalize_table(table)})
        return aid

    for obj in objects:
        fid = lg.make_func_id(codebase, obj["source"], obj["object"])
        nodes.setdefault(fid, {"id": fid, "kind": "function", "path": obj["source"], "name": obj["object"]})
        for t in obj.get("reads", []):
            edges.append({
                "src": fid, "dst": _asset_node(t), "kind": "reads",
                "executed": False, "confidence": 0.6,
                "match_basis": f"mined FROM/JOIN in {obj['source']}",
                "evidence": f"{obj['object']} reads {_normalize_table(t)}",
            })
        for t in obj.get("writes", []):
            edges.append({
                "src": fid, "dst": _asset_node(t), "kind": "writes",
                "executed": False, "confidence": 0.6,
                "match_basis": f"mined INSERT/UPDATE/MERGE in {obj['source']}",
                "evidence": f"{obj['object']} writes {_normalize_table(t)}",
            })
    return {"schema_version": lg.SCHEMA_VERSION, "nodes": list(nodes.values()), "edges": edges}


# --------------------------------------------------------------------------- #
# End-to-end mining
# --------------------------------------------------------------------------- #

def mine_paths(
    paths: list[Any],
    *,
    store: str = "warehouse",
    codebase: str = "warehouse",
    default_schema: str = "dbo",
    corroboration_rows: Optional[dict[str, list[dict[str, Any]]]] = None,
    corroborated_defs: Optional[dict[str, dict[str, Any]]] = None,
    mined_at: Optional[str] = None,
) -> dict[str, Any]:
    """Mine a list of `.sql` file paths into the full artifact.

    Every object is accounted for: successfully-extracted objects populate
    `objects` + `coverage.parsed`; an object with no recognizable shape populates
    `coverage.skipped` WITH a reason; a genuinely malformed object populates
    `coverage.failed` WITH a reason. A bad object never crashes the run — any
    unexpected error is caught and reported as `failed`.

    `corroboration_rows` / `corroborated_defs` are optional corroboration context
    (from the lane's live inspection); when supplied, each mined candidate is run
    through :func:`corroborate_mined_claim` inline.
    """
    objects: list[dict[str, Any]] = []
    parsed: list[str] = []
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    for path in paths:
        p = Path(path)
        try:
            # utf-8-sig tolerates a leading UTF-8 BOM (common in exported .sql). A
            # non-utf-8 file — a UTF-16 SSMS script export, or a cp1252 file with an
            # accented char — raises UnicodeDecodeError, which is a `ValueError`, NOT
            # an `OSError`; catch BOTH so a bad-encoding object lands in `failed`
            # with a reason instead of crashing the whole run (the deng fidelity
            # discipline: never silently dropped, never a crash).
            text = p.read_text(encoding="utf-8-sig")
        except OSError as exc:  # unreadable file -> failed, never a crash
            failed.append({"object": p.name, "reason": f"unreadable file: {exc}"})
            continue
        except UnicodeDecodeError as exc:  # not utf-8 -> failed, never a crash
            failed.append({"object": p.name, "reason": f"undecodable file (not utf-8): {exc}"})
            continue
        for name, kind, body in split_objects(text, p.stem):
            try:
                obj = extract_object(name, kind, body, p.name)
            except SqlParseError as exc:
                failed.append({"object": name, "reason": str(exc)})
                continue
            except Exception as exc:  # defensive: a bad object never crashes the run
                failed.append({"object": name, "reason": f"unexpected extraction error: {exc}"})
                continue
            if not _has_shape(obj):
                skipped.append({
                    "object": name,
                    "reason": ("no recognizable read/write/join/metric shape "
                               "(dialect-specific or unsupported construct; e.g. dynamic "
                               "SQL inside a string literal, pure control-flow, or DDL-only)"),
                })
                continue
            objects.append(obj)
            parsed.append(name)

    candidates: list[dict[str, Any]] = []
    for obj in objects:
        for cand in _candidates_for(obj):
            if corroboration_rows is not None or corroborated_defs is not None:
                rows = (corroboration_rows or {}).get(cand["table"])
                cand = corroborate_mined_claim(cand, rows=rows, corroborated_defs=corroborated_defs)
            candidates.append(cand)

    return {
        "schema": SCHEMA,
        "mined_at": mined_at,
        "objects": objects,
        "coverage": {
            "parsed": parsed,
            "skipped": skipped,
            "failed": failed,
            "counts": {
                "parsed": len(parsed), "skipped": len(skipped),
                "failed": len(failed), "total": len(parsed) + len(skipped) + len(failed),
            },
        },
        "dictionary_candidates": candidates,
        "lineage": emit_lineage(objects, store=store, codebase=codebase, default_schema=default_schema),
    }


def mine_dir(directory: Any, **kwargs: Any) -> dict[str, Any]:
    """Mine every `*.sql` file (sorted) under `directory`."""
    d = Path(directory)
    paths = sorted(d.glob("*.sql"))
    return mine_paths(paths, **kwargs)


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #

def serialize_markdown(art: dict[str, Any]) -> str:
    cov = art["coverage"]
    c = cov["counts"]
    out = [
        "---",
        f"last_mined: {art.get('mined_at') or 'unknown'}",
        f"schema: {art.get('schema')}",
        "artifact: SQL_MINING_MAP",
        "---",
        "",
        "# SQL Mining Map",
        "",
        ("Deterministic, stdlib-only mining of SQL objects (stored procedures / views / "
         "functions). Mined content enters the data dictionary at provenance `inference` "
         "and is corroboration-gated; parse-coverage is surfaced honestly (nothing dropped)."),
        "",
        "## Parse coverage",
        "",
        f"- **parsed:** {c['parsed']}",
        f"- **skipped:** {c['skipped']}",
        f"- **failed:** {c['failed']}",
        f"- **total:** {c['total']}",
        "",
    ]
    if cov["skipped"]:
        out.append("### Skipped (with reason)")
        for e in cov["skipped"]:
            out.append(f"- `{e['object']}` — {e['reason']}")
        out.append("")
    if cov["failed"]:
        out.append("### Failed (with reason)")
        for e in cov["failed"]:
            out.append(f"- `{e['object']}` — {e['reason']}")
        out.append("")

    out.append("## Mined objects")
    out.append("")
    for obj in art["objects"]:
        out.append(f"### `{obj['object']}` ({obj['kind']}) — {obj['source']}")
        out.append(f"- **reads:** {', '.join(f'`{t}`' for t in obj['reads']) or '(none)'}")
        out.append(f"- **writes:** {', '.join(f'`{t}`' for t in obj['writes']) or '(none)'}")
        for j in obj["joins"]:
            out.append(f"- **join:** `{j['left']}` = `{j['right']}` "
                       f"({j.get('left_table')} <-> {j.get('right_table')})")
        for m in obj["metrics"]:
            out.append(f"- **metric ({m['shape']}):** `{m['expr']}`"
                       + (f" AS `{m['alias']}`" if m.get("alias") else ""))
        for f in obj["filters"]:
            out.append(f"- **filter:** `{f['column']} {f['op']} ...`")
        out.append("")

    out.append("## Dictionary candidates (provenance: inference — corroboration-gated)")
    out.append("")
    out.append("| Object | Table | Column | Kind | Provenance | Confidence | Corroboration |")
    out.append("|---|---|---|---|---|---|---|")
    for cand in art["dictionary_candidates"]:
        corro = cand.get("corroboration")
        if cand.get("flagged"):
            corro_s = f"{WARN_MARKER} {cand.get('conflict')}"
        elif corro is None:
            corro_s = "(uncorroborated — no live data)"
        else:
            corro_s = "ok"
        out.append(
            f"| `{cand['object']}` | `{cand['table']}` | `{cand['column']}` | "
            f"{cand.get('kind')} | {cand['provenance']} | {cand.get('confidence')} | {corro_s} |"
        )
    out.append("")

    graph = art["lineage"]
    out.append("## Lineage (data_asset nodes + reads/writes edges)")
    out.append(f"- nodes: {len(graph['nodes'])}, edges: {len(graph['edges'])}")
    out.append("")
    return "\n".join(out)


def write_artifact(art: dict[str, Any], out_dir: Any) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / ARTIFACT_NAME
    js_path = out / SIDECAR_NAME
    md_path.write_text(serialize_markdown(art), encoding="utf-8")
    js_path.write_text(json.dumps(art, indent=2, sort_keys=True), encoding="utf-8")
    return md_path, js_path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _collect_sql_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.sql")))
        elif p.is_file():
            paths.append(p)
    return paths


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Warehouse SQL-object mining engine (SQL-MINING-1..N).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mine", help="Mine SQL objects from a directory or file list into an artifact.")
    m.add_argument("inputs", nargs="+", help="One or more directories and/or .sql files to mine.")
    m.add_argument("--out", default="docs", help="Output directory (default: docs).")
    m.add_argument("--store", default="warehouse", help="Lineage store namespace (default: warehouse).")
    m.add_argument("--schema", default="dbo", help="Default schema for un-schema-qualified tables.")
    m.add_argument("--codebase", default="warehouse", help="Lineage codebase namespace (default: warehouse).")
    args = parser.parse_args(argv)

    if args.cmd == "mine":
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        paths = _collect_sql_paths(args.inputs)
        art = mine_paths(paths, store=args.store, codebase=args.codebase,
                         default_schema=args.schema, mined_at=ts)
        md, js = write_artifact(art, args.out)
        c = art["coverage"]["counts"]
        print(f"wrote {md} + {js} "
              f"({c['total']} objects: {c['parsed']} parsed / {c['skipped']} skipped / {c['failed']} failed)")
        return 0
    return 1  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
