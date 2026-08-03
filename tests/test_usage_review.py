"""Tests for Run E — usage-stats-review-roundtrip.

Three load-bearing disciplines, each an adversary target, pinned here:

1. **Usage is MEASURED, never fabricated (R4).** An injected `UsageStatsSource`
   attaches a per-table `usage` block (read/write recency + row volume) at
   provenance `live-data`. The named anti-pattern (deng's silently-single-target
   arm): **absent stats OMIT the block entirely — never zeros, never `{}`**. A
   dictionary built with NO source is byte-unchanged.
2. **The offline stakeholder review round-trip (R5).** `generate-review` emits a
   CSV of the fields most needing human eyes (low-confidence OR ⚠-conflict, sorted
   by R4 usage), redacted through the reused `logit.redact_evidence`; `apply-review`
   ingests each edited `proposed_definition` **through the corroboration gate** — a
   human correction is corroborated like any other, never transcribed. THE PINNED
   TEST (deng lacks it): generate -> edit one cell -> apply -> the correction lands
   on the EXACT table.field (no column drift) AND passed through
   `corroborate_definition`.
3. **The corroboration gate accepts a claim only when its EXACT field was checked**
   — the two logged same-class residuals closed here: sql-mining's
   `corroborate_mined_claim` per-field acceptance (R1), and the annotations
   `non_null_sampled == 0` text-family edge (F-A5). Both red-first.
"""
from __future__ import annotations

import ast
import csv
import json
import sqlite3
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
DD_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "data_dictionary.py"
ANN_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "annotations.py"
SM_PATH = REPO_ROOT / "scripts" / "sql_mining" / "sql_mining.py"

dd = load_module(DD_PATH, "ct6_dd_usage")
ann = load_module(ANN_PATH, "ct6_ann_usage")
sm = load_module(SM_PATH, "ct6_sm_usage")

WARN = "⚠"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_db(path: Path) -> None:
    """orders(order_id PK, status text, note all-NULL) + customers(id PK, email)."""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, status TEXT, note TEXT)")
        conn.executemany("INSERT INTO orders VALUES (?,?,?)",
                         [(1, "shipped", None), (2, "pending", None), (3, "cancelled", None)])
        conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT)")
        conn.executemany("INSERT INTO customers VALUES (?,?)", [(1, "a@x.com"), (2, "b@x.com")])
        conn.commit()
    finally:
        conn.close()


def _sample(db: Path, table: str, limit: int = 100) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return dd.sample_table(conn, table, limit)
    finally:
        conn.close()


def _field(built: dict, table: str, field: str) -> dict:
    return {f["field"]: f for f in built["tables"][table]["fields"]}[field]


def _built_with_conflict(tmp_path: Path):
    """A dictionary with a boolean-vs-text conflict on orders.status (low + ⚠), an
    all-NULL low-confidence orders.note, and usage on orders for sort ordering."""
    db = tmp_path / "s.sqlite"
    _make_db(db)
    provided = {"orders.status": {"definition": "a paid/unpaid boolean flag",
                                  "provenance": "direct-user-input", "expected_type": "boolean"}}
    src = dd.FakeUsageStatsSource({"orders": {"read_recency": "2026-08-01",
                                              "write_recency": "2026-07-01", "row_volume": 500}})
    built = dd.build_from_sqlite(db, provided_defs=provided, usage_stats=src, built_at="t")
    return db, built


def _edit_cell(csv_path: Path, *, table: str, field: str, new_proposed: str) -> None:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)
    hits = 0
    for row in rows:
        if row["table"] == table and row["field"] == field:
            row["proposed_definition"] = new_proposed
            hits += 1
    assert hits == 1, f"expected exactly one {table}.{field} row to edit, found {hits}"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


# --------------------------------------------------------------------------- #
# 1. R4 — usage-grounded importance, MEASURED not fabricated
# --------------------------------------------------------------------------- #
def test_usage_block_attached_at_live_data_when_source_returns_stats(tmp_path: Path) -> None:
    db = tmp_path / "s.sqlite"
    _make_db(db)
    src = dd.FakeUsageStatsSource({"orders": {"read_recency": "2026-08-01",
                                              "write_recency": "2026-07-30", "row_volume": 120345}})
    built = dd.build_from_sqlite(db, usage_stats=src, built_at="2026-08-03T00:00:00Z")
    usage = built["tables"]["orders"]["usage"]
    assert usage["row_volume"] == 120345
    assert usage["read_recency"] == "2026-08-01" and usage["write_recency"] == "2026-07-30"
    assert usage["provenance"] == "live-data"   # it is MEASURED
    # a table the source has no stats for OMITS the block entirely
    assert "usage" not in built["tables"]["customers"]


def test_absent_stats_omit_block_never_zero_fill(tmp_path: Path) -> None:
    # THE deng anti-pattern: an unmeasured table is NOT a zero-usage table.
    db = tmp_path / "s.sqlite"
    _make_db(db)
    src = dd.FakeUsageStatsSource({})  # no stats for any table
    built = dd.build_from_sqlite(db, usage_stats=src, built_at="t")
    for t, tinfo in built["tables"].items():
        assert "usage" not in tinfo, f"{t} zero-filled/empty usage instead of omitting it"
    assert "usage" not in json.dumps(built)


def test_no_usage_source_is_byte_unchanged(tmp_path: Path) -> None:
    db = tmp_path / "s.sqlite"
    _make_db(db)
    built = dd.build_from_sqlite(db, built_at="t")
    # no table dict gains any key beyond the pre-Run-E {grain, fields}
    for tinfo in built["tables"].values():
        assert set(tinfo.keys()) == {"grain", "fields"}
    assert "usage" not in json.dumps(built)
    assert "Usage" not in dd.serialize_markdown(built)


def test_sqlite_usage_stats_is_honestly_none(tmp_path: Path) -> None:
    src = dd.SqliteUsageStats()
    assert src.table_usage("orders") is None  # SQLite exposes no usage catalog
    db = tmp_path / "s.sqlite"
    _make_db(db)
    built = dd.build_from_sqlite(db, usage_stats=src, built_at="t")
    assert all("usage" not in tinfo for tinfo in built["tables"].values())


def test_usage_source_conforms_to_runtime_protocol() -> None:
    assert isinstance(dd.SqliteUsageStats(), dd.UsageStatsSource)
    assert isinstance(dd.FakeUsageStatsSource(), dd.UsageStatsSource)


def test_engine_shapes_documented_for_sqlserver_and_postgres() -> None:
    text = DD_PATH.read_text(encoding="utf-8")
    assert "dm_db_index_usage_stats" in text and "dm_db_partition_stats" in text  # SQL Server
    assert "pg_stat_user_tables" in text  # Postgres


def test_provenance_vocabulary_unchanged_usage_rides_live_data() -> None:
    assert dd.PROVENANCE_TYPES == (
        "direct-user-input", "direct-code-comment", "inference", "live-data")


def test_usage_block_rendered_in_markdown_only_when_present(tmp_path: Path) -> None:
    db = tmp_path / "s.sqlite"
    _make_db(db)
    src = dd.FakeUsageStatsSource({"orders": {"read_recency": "r", "write_recency": "w",
                                              "row_volume": 987}})
    built = dd.build_from_sqlite(db, usage_stats=src, built_at="t")
    md = dd.serialize_markdown(built)
    assert "Usage" in md and "987" in md
    # customers has no usage -> no usage line under its OWN heading (isolate the
    # customers section up to the next table heading; tables render alphabetically)
    cust_section = md.split("## Table: `customers`")[1].split("## Table:")[0]
    assert "Usage" not in cust_section


# --------------------------------------------------------------------------- #
# 2. R5 — the offline stakeholder review round-trip
# --------------------------------------------------------------------------- #
def test_generate_review_filters_low_and_conflict_fields(tmp_path: Path) -> None:
    db, built = _built_with_conflict(tmp_path)
    out = tmp_path / "review.csv"
    rows = dd.generate_review(built, out)
    keys = {(r["table"], r["field"]) for r in rows}
    assert ("orders", "status") in keys   # conflict + low
    assert ("orders", "note") in keys      # all-NULL -> inference/low
    assert ("orders", "order_id") not in keys  # live-data medium — not surfaced
    assert ("customers", "email") not in keys  # live-data medium — not surfaced
    # the CSV header is the fixed 7 columns, in order
    with out.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header == ["table", "field", "current_definition", "confidence",
                      "conflict", "usage_volume", "proposed_definition"]
    # proposed_definition is blank for the stakeholder to fill
    assert all(r["proposed_definition"] == "" for r in rows)


def test_generate_review_sorted_by_usage_volume_desc_no_usage_last(tmp_path: Path) -> None:
    db = tmp_path / "multi.sqlite"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE a (id INTEGER PRIMARY KEY, flag TEXT)")
        conn.executemany("INSERT INTO a VALUES (?,?)", [(1, "x"), (2, "y")])
        conn.execute("CREATE TABLE b (id INTEGER PRIMARY KEY, flag TEXT)")
        conn.executemany("INSERT INTO b VALUES (?,?)", [(1, "x"), (2, "y")])
        conn.execute("CREATE TABLE c (id INTEGER PRIMARY KEY, oldcol TEXT)")
        conn.executemany("INSERT INTO c VALUES (?,?)", [(1, None), (2, None)])  # all-NULL low, no usage
        conn.commit()
    finally:
        conn.close()
    provided = {
        "a.flag": {"definition": "d", "provenance": "direct-user-input", "expected_type": "boolean"},
        "b.flag": {"definition": "d", "provenance": "direct-user-input", "expected_type": "boolean"},
    }
    src = dd.FakeUsageStatsSource({
        "a": {"read_recency": "r", "write_recency": "w", "row_volume": 50},
        "b": {"read_recency": "r", "write_recency": "w", "row_volume": 9000},
        # c intentionally absent -> no usage
    })
    built = dd.build_from_sqlite(db, provided_defs=provided, usage_stats=src, built_at="t")
    rows = dd.generate_review(built, tmp_path / "r.csv")
    vols = [r["usage_volume"] for r in rows]
    assert rows[0]["table"] == "b"  # highest volume first
    numeric = [int(v) for v in vols if v != ""]
    assert numeric == sorted(numeric, reverse=True)  # descending by volume
    # the no-usage row sorts strictly last
    assert rows[-1]["table"] == "c" and vols[-1] == ""


def test_review_roundtrip_correction_lands_on_exact_field_no_drift(tmp_path: Path) -> None:
    # THE PINNED TEST — deng lacks it.
    db, built = _built_with_conflict(tmp_path)
    csv_path = tmp_path / "review.csv"
    dd.generate_review(built, csv_path)
    rows_by_table = {"orders": _sample(db, "orders")}
    original_status_def = _field(built, "orders", "status")["definition"]

    # edit exactly ONE proposed_definition cell — the note row
    _edit_cell(csv_path, table="orders", field="note",
               new_proposed="internal fulfillment note (free text)")
    updated, applied = dd.apply_review(built, csv_path, rows_by_table=rows_by_table)

    # the correction landed on the EXACT table.field (no column drift)
    assert len(applied) == 1
    assert applied[0]["table"] == "orders" and applied[0]["field"] == "note"
    note = _field(updated, "orders", "note")
    assert note["definition"] == "internal fulfillment note (free text)"
    assert note["provenance"] == "direct-user-input"
    # it PASSED THROUGH corroborate_definition (the engine's verdict fields present)
    assert note["corroboration"] is not None
    assert set(note["corroboration"]) >= {"checked", "agrees", "actual_type"}
    # no other field drifted — status keeps its original definition (its blank
    # proposed_definition was NOT applied; no row/column misalignment)
    assert _field(updated, "orders", "status")["definition"] == original_status_def


def test_conflicting_correction_is_corroborated_not_blindly_accepted(tmp_path: Path) -> None:
    db, built = _built_with_conflict(tmp_path)
    csv_path = tmp_path / "review.csv"
    dd.generate_review(built, csv_path)
    rows_by_table = {"orders": _sample(db, "orders")}
    # correct the status field, whose boolean type claim the text data contradicts:
    # re-corroborated under that claim -> flagged + downgraded, NOT accepted
    _edit_cell(csv_path, table="orders", field="status",
               new_proposed="still asserting a boolean paid flag")
    updated, applied = dd.apply_review(built, csv_path, rows_by_table=rows_by_table)
    status_app = next(a for a in applied if a["field"] == "status")
    assert status_app["accepted"] is False
    assert status_app["flag"] == WARN
    assert status_app["confidence"] == "low"
    assert status_app["corroboration"]["agrees"] is False


def test_default_summary_redaction_drops_sample_derived_detail(tmp_path: Path) -> None:
    db, built = _built_with_conflict(tmp_path)
    summ = tmp_path / "summary.csv"
    full = tmp_path / "full.csv"
    dd.generate_review(built, summ)                       # default summary
    dd.generate_review(built, full, privacy_level="full")
    summ_text = summ.read_text(encoding="utf-8")
    full_text = full.read_text(encoding="utf-8")
    # the sample-derived conflict detail (which names the observed sampled type) is
    # present under full and DROPPED under the default summary allow-list
    assert "does not match the sampled data" in full_text
    assert "does not match the sampled data" not in summ_text
    # both still flag the conflict row (the ⚠ fact survives) and carry the field
    assert WARN in summ_text and "status" in summ_text


def test_generate_review_reuses_logit_redact_evidence() -> None:
    # the privacy engine is REUSED (loaded by path), never re-implemented
    text = DD_PATH.read_text(encoding="utf-8")
    assert "redact_evidence" in text and "logit" in text.lower()


def test_apply_review_uncorroborated_when_no_rows_supplied(tmp_path: Path) -> None:
    # honest boundary: with no rows/db, a correction is applied but NOT presented
    # as corroborated truth (needs_corroboration), never blindly accepted
    db, built = _built_with_conflict(tmp_path)
    csv_path = tmp_path / "review.csv"
    dd.generate_review(built, csv_path)
    _edit_cell(csv_path, table="orders", field="note", new_proposed="a note")
    updated, applied = dd.apply_review(built, csv_path)  # no rows_by_table, no db
    app = applied[0]
    assert app["needs_corroboration"] is True
    assert app["accepted"] is False
    assert _field(updated, "orders", "note")["definition"] == "a note"  # still lands


# --------------------------------------------------------------------------- #
# 3. Hardening R1 — sql_mining.corroborate_mined_claim is PER-FIELD (red-first)
# --------------------------------------------------------------------------- #
def test_mined_claim_absent_from_defs_with_no_rows_stays_not_accepted() -> None:
    # R1 residual: corroborated_defs supplied but the candidate's field is ABSENT
    # and rows=None -> nothing checked THIS field -> must stay inference/not-accepted
    # (pre-fix `ran = rows is not None or bool(corroborated_defs)` stamped it accepted).
    candidate = {"table": "dbo.Summary", "column": "ghost_col", "claimed_type": "numeric",
                 "confidence": "medium", "provenance": "inference", "kind": "metric"}
    other_defs = {"dbo.Summary.real_col": {"type": "integer", "corroborated": True}}
    result = sm.corroborate_mined_claim(candidate, rows=None, corroborated_defs=other_defs)
    assert result["provenance"] == "inference"    # never promoted
    assert result["accepted"] is False            # nothing checked this field
    assert result["corroborated"] is False
    assert result["needs_corroboration"] is True


def test_mined_claim_present_but_uncorroborated_def_not_accepted() -> None:
    # present in the map but NOT corroborated + rows=None -> still not-accepted
    candidate = {"table": "dbo.Summary", "column": "total", "claimed_type": "integer",
                 "confidence": "medium", "provenance": "inference", "kind": "metric"}
    defs = {"dbo.Summary.total": {"type": "integer", "corroborated": False}}
    result = sm.corroborate_mined_claim(candidate, rows=None, corroborated_defs=defs)
    assert result["corroborated"] is False and result["accepted"] is False
    assert result["needs_corroboration"] is True


def test_mined_claim_present_and_corroborated_in_defs_is_checked() -> None:
    # the honest positive (guards against over-correction): EXACT field present +
    # corroborated + no type conflict -> checked/accepted
    candidate = {"table": "dbo.Summary", "column": "total", "claimed_type": "integer",
                 "confidence": "medium", "provenance": "inference", "kind": "metric"}
    defs = {"dbo.Summary.total": {"type": "integer", "corroborated": True}}
    result = sm.corroborate_mined_claim(candidate, rows=None, corroborated_defs=defs)
    assert result["corroborated"] is True and result["accepted"] is True
    assert result["provenance"] == "inference"


def test_mined_claim_present_and_conflicting_in_defs_flagged_not_accepted() -> None:
    candidate = {"table": "dbo.Summary", "column": "total", "claimed_type": "text",
                 "confidence": "medium", "provenance": "inference", "kind": "metric"}
    defs = {"dbo.Summary.total": {"type": "integer", "corroborated": True}}
    result = sm.corroborate_mined_claim(candidate, rows=None, corroborated_defs=defs)
    assert result["flagged"] is True and result["accepted"] is False
    assert result["confidence"] == "low"


def test_mined_rows_path_still_accepts_agreeing_claim() -> None:
    # the rows path is unchanged by the fix — an agreeing claim via rows is accepted
    candidate = {"table": "T", "column": "c", "claimed_type": "integer", "confidence": "medium",
                 "provenance": "inference", "kind": "field"}
    result = sm.corroborate_mined_claim(candidate, rows=[{"c": 1}, {"c": 2}])
    assert result["corroborated"] is True and result["accepted"] is True


# --------------------------------------------------------------------------- #
# 4. Hardening F-A5 — annotations non_null_sampled==0 is not-checked (red-first)
# --------------------------------------------------------------------------- #
def test_annotation_text_claim_on_all_null_column_is_not_checked() -> None:
    # F-A5: a TEXT-family factual claim on an all-NULL sampled column must NOT be
    # accepted — zero non-null values corroborate nothing (a 'text' claim reads
    # actual_type 'unknown' and vacuously "agrees" in corroborate_definition).
    all_null = [{"notes": None}, {"notes": None}, {"notes": None}]
    claim = ann.corroborate_annotation_claim(
        {"expected_type": "text", "claims_key": False, "definition": "free-text notes"},
        table="orders", column="notes", rows=all_null)
    assert claim["corroboration"]["non_null_sampled"] == 0   # composed engine confirms zero
    assert claim["accepted"] is False                        # NOT accepted on zero evidence
    assert claim["corroborated"] is False
    assert claim["needs_corroboration"] is True
    assert claim["confidence"] == "low"


def test_annotation_text_claim_on_populated_column_still_checked() -> None:
    # counterpart guard — the fix must NOT over-correct a genuinely-sampled column
    rows = [{"notes": "hello"}, {"notes": "world"}]
    claim = ann.corroborate_annotation_claim(
        {"expected_type": "text", "claims_key": False, "definition": "free-text notes"},
        table="orders", column="notes", rows=rows)
    assert claim["corroboration"]["non_null_sampled"] == 2
    assert claim["corroborated"] is True and claim["accepted"] is True


def test_annotation_text_claim_on_column_absent_from_sampled_table_not_accepted() -> None:
    # F-A5 (complete) — a TEXT claim on a GHOST column (absent from the sampled
    # table) via --db must be served uncorroborated + anchor_in_dictionary=false,
    # never corroborated (the composed corroborate_definition vacuously agrees on
    # zero evidence). The Lead's fuller characterization: cover column-absent, not
    # only all-NULL; and set the F3 anchor-existence signal on the --db path too.
    rows = [{"id": 1, "total_cents": 500}, {"id": 2, "total_cents": 1299}]  # no 'ghost_dollars'
    claim = ann.corroborate_annotation_claim(
        {"expected_type": "text", "claims_key": False, "definition": "a dollar column"},
        table="orders", column="ghost_dollars", rows=rows)
    assert claim["accepted"] is False
    assert claim["corroborated"] is False
    assert claim["needs_corroboration"] is True
    assert claim["anchor_in_dictionary"] is False   # F3 on the --db path


def test_annotation_boolean_ghost_claim_still_flagged_not_silently_uncorroborated() -> None:
    # the Lead's keep-working requirement — a boolean/integer/date claim on a
    # ghost/all-NULL column genuinely DISAGREES (vs actual_type 'unknown'), so it
    # stays FLAGGED (⚠), NOT swept to uncorroborated. Guards against an over-broad
    # non_null==0 gate that would un-flag a real contradiction.
    rows = [{"id": 1, "total_cents": 5}, {"id": 2, "total_cents": 9}]  # no 'paid' column
    claim = ann.corroborate_annotation_claim(
        {"expected_type": "boolean", "claims_key": False, "definition": "a paid flag"},
        table="orders", column="paid", rows=rows)
    assert claim["flag"] == ann.WARN_MARKER   # genuinely contradicted -> flagged
    assert claim["accepted"] is False
    assert claim["corroborated"] is True      # it WAS checked (a real disagreement)


def test_annotation_text_all_null_sets_anchor_in_dictionary_true_when_present() -> None:
    # counterpart: an all-NULL column that DOES exist in the sampled table is marked
    # anchor_in_dictionary=true (present), still not accepted (zero evidence)
    rows = [{"notes": None}, {"notes": None}]
    claim = ann.corroborate_annotation_claim(
        {"expected_type": "text", "claims_key": False, "definition": "notes"},
        table="orders", column="notes", rows=rows)
    assert claim["anchor_in_dictionary"] is True
    assert claim["accepted"] is False


def test_annotation_key_claim_on_all_null_column_still_flagged() -> None:
    # a KEY claim is genuinely checked by uniqueness even on all-NULL data (0 distinct
    # -> not unique -> contradicted); it must NOT be swept into the non_null gate
    all_null = [{"kid": None}, {"kid": None}]
    claim = ann.corroborate_annotation_claim(
        {"expected_type": None, "claims_key": True, "definition": "the key"},
        table="t", column="kid", rows=all_null)
    assert claim["corroborated"] is True         # uniqueness WAS checked
    assert claim["accepted"] is False and claim["flag"] == ann.WARN_MARKER


def test_run_d_annotation_suite_still_green_on_key_paths(tmp_path: Path) -> None:
    # a smoke re-verification that the Run D corroborate-on-ingest behavior the 44
    # annotation tests pin is unchanged by the hardening (non-all-NULL rows).
    int_rows = [{"id": 1, "total_cents": 500}, {"id": 2, "total_cents": 1299}]
    agree = ann.corroborate_annotation_claim(
        {"expected_type": "integer", "claims_key": False, "definition": "cents"},
        table="orders", column="total_cents", rows=int_rows)
    assert agree["accepted"] is True and agree["flag"] == "ok"
    conflict = ann.corroborate_annotation_claim(
        {"expected_type": "boolean", "claims_key": False, "definition": "a flag"},
        table="orders", column="total_cents", rows=int_rows)
    assert conflict["accepted"] is False and conflict["flag"] == ann.WARN_MARKER


# --------------------------------------------------------------------------- #
# 5. Additive discipline — stdlib-only, no new services module
# --------------------------------------------------------------------------- #
def test_data_dictionary_stays_stdlib_only() -> None:
    # logit is REUSED by path (not top-level imported), keeping the engine stdlib-only
    tree = ast.parse(DD_PATH.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    stdlib = {"__future__", "argparse", "json", "re", "sqlite3", "pathlib", "typing",
              "importlib", "csv", "datetime", "os"}
    assert roots <= stdlib, f"non-stdlib import crept into data_dictionary.py: {sorted(roots - stdlib)}"


def test_check_separation_stays_clean() -> None:
    from services.separation import check_separation
    rep = check_separation()
    assert rep["clean"] is True
