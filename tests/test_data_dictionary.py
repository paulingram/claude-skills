"""Tests for the v3.17.0 Data Dictionary engine (skills/data-dictionary; DD-1..18).

Covers the deterministic machine `scripts/data_dictionary/data_dictionary.py`:
introspection + ~100-row sampling (DD-9/10), grain inference (DD-11), field
inference (DD-12), the fixed provenance vocabulary (DD-13), corroboration
(DD-14), the reference + relational maps (DD-7), and the serializer + the
standard artifact name (DD-7/16). The headline test is the end-to-end dogfood
against a local SQLite DB that reproduces the requirements doc's own example: a
`customers` table a user *claims* keys on `customer_id` but actually keys on a
hash, plus a `census_by_zip` table joined onto customers on zip *in code*.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "data_dictionary.py"

_spec = importlib.util.spec_from_file_location("data_dictionary", MODULE_PATH)
dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dd)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# fixtures — a local SQLite DB modelling the requirements doc's example
# --------------------------------------------------------------------------- #

def _make_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE customers ("
            "  customer_hash TEXT PRIMARY KEY,"  # the REAL unique key
            "  customer_id INTEGER,"             # NOT unique (one per store-location)
            "  store_location TEXT,"
            "  email TEXT,"
            "  address1 TEXT,"
            "  zip5 TEXT)"
        )
        conn.execute(
            "CREATE TABLE census_by_zip ("
            "  zip5 TEXT PRIMARY KEY,"
            "  median_income INTEGER,"
            "  population INTEGER)"
        )
        # customer_id repeats across store locations -> customer_id is NOT a key
        rows = [
            ("h001", 1, "NYC", "a@x.com", "1 Main St", "10001"),
            ("h002", 1, "LA", "a@x.com", "2 Oak Ave", "90001"),   # same customer_id 1
            ("h003", 2, "SF", "b@x.com", "3 Pine Rd", "94101"),
        ]
        conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", rows)
        conn.executemany(
            "INSERT INTO census_by_zip VALUES (?,?,?)",
            [("10001", 90000, 21000), ("90001", 55000, 57000), ("94101", 130000, 28000)],
        )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# deterministic units
# --------------------------------------------------------------------------- #

def test_provenance_vocabulary_is_fixed() -> None:
    assert dd.PROVENANCE_TYPES == (
        "direct-user-input", "direct-code-comment", "inference", "live-data",
    )


def test_introspect_sqlite_reads_schema(tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    info = dd.introspect_sqlite(db)
    assert info["db_name"] == "shop"
    assert set(info["tables"]) == {"customers", "census_by_zip"}
    cust_cols = {c["name"] for c in info["tables"]["customers"]}
    assert {"customer_hash", "customer_id", "zip5"} <= cust_cols
    assert any(c["name"] == "customer_hash" and c["pk"] for c in info["tables"]["customers"])


def test_sample_table_caps_rows(tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = dd.sample_table(conn, "customers", limit=2)
        assert len(rows) == 2
        assert "customer_hash" in rows[0]
    finally:
        conn.close()


def test_infer_grain_unique_vs_fact() -> None:
    cols = [{"name": "customer_hash", "pk": True}, {"name": "customer_id", "pk": False}]
    rows = [{"customer_hash": "h1", "customer_id": 1}, {"customer_hash": "h2", "customer_id": 1}]
    grain = dd.infer_grain("customers", cols, rows)
    assert "customer_hash" in grain["grain"]
    assert grain["declared_pk"] == ["customer_hash"]
    # customer_id is not unique in the sample
    assert grain["uniqueness_ratios"]["customer_id"] < 1.0


def test_infer_field_heuristics() -> None:
    assert dd.infer_field("customers", "zip5", ["10001", "90001"])["inferred_meaning"] == "5-digit ZIP code"
    assert "identifier" in dd.infer_field("orders", "customer_id", [1, 2])["inferred_meaning"]
    assert dd.infer_field("c", "email", ["a@x.com"])["inferred_meaning"] == "email address"
    assert dd.infer_field("c", "address1", ["1 Main St"])["inferred_meaning"] == "address line 1"


def test_corroborate_key_claim_flags_conflict() -> None:
    rows = [{"customer_id": 1}, {"customer_id": 1}, {"customer_id": 2}]  # not unique
    verdict = dd.corroborate_key_claim(rows, "customers", "customer_id")
    assert verdict["agrees"] is False
    assert verdict["conflict"] is not None
    # a genuinely-unique column agrees
    rows2 = [{"customer_hash": "h1"}, {"customer_hash": "h2"}]
    assert dd.corroborate_key_claim(rows2, "customers", "customer_hash")["agrees"] is True


def test_reference_and_relation_maps() -> None:
    rm = dd.build_reference_map([
        {"file": "etl.py", "line": 12, "table": "customers", "field": "zip5"},
        {"file": "etl.py", "line": 30, "table": "customers", "field": None},
    ])
    assert "customers.zip5" in rm["by_field"]
    assert "customers" in rm["by_table"]
    rels = dd.build_relation_map(
        [{"from_table": "orders", "from_col": "customer_hash", "to_table": "customers", "to_col": "customer_hash"}],
        code_joins=[{"from_table": "customers", "from_col": "zip5", "to_table": "census_by_zip",
                     "to_col": "zip5", "note": "census merged onto customers on zip in code"}],
    )
    kinds = {r["kind"] for r in rels}
    assert kinds == {"db-fk", "code-join"}


# --------------------------------------------------------------------------- #
# end-to-end dogfood (the live-inspection path against a real local SQLite DB)
# --------------------------------------------------------------------------- #

def test_build_from_sqlite_end_to_end(tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    # first-pass context (DD-8): the user claims customers keys on customer_id
    provided = {"customers.customer_id": {
        "definition": "unique customer key", "provenance": "direct-user-input", "claims_key": True,
    }}
    code_joins = [{"from_table": "customers", "from_col": "zip5", "to_table": "census_by_zip",
                   "to_col": "zip5", "note": "census merged onto customers on zip in code"}]
    built = dd.build_from_sqlite(db, provided_defs=provided, code_joins=code_joins,
                                 built_at="2026-06-16T00:00:00Z")

    cust = built["tables"]["customers"]
    # grain inferred from the REAL key (the hash), not the claimed customer_id
    assert "customer_hash" in cust["grain"]["grain"]
    by_field = {f["field"]: f for f in cust["fields"]}
    # DD-14: the claimed-key conflict is caught + confidence downgraded
    cid = by_field["customer_id"]
    assert cid["provenance"] == "direct-user-input"
    assert cid["corroboration"] is not None and cid["corroboration"]["agrees"] is False
    assert cid["confidence"] == "low"
    # DD-12: zip5 inferred as a 5-digit ZIP, sourced from live data
    assert by_field["zip5"]["definition"] == "5-digit ZIP code"
    assert by_field["zip5"]["provenance"] == "live-data"
    # DD-7e: the code-join (census on zip) is in the relational map
    assert any(r["kind"] == "code-join" for r in built["relational_map"])
    assert built["provenance_vocabulary"] == list(dd.PROVENANCE_TYPES)


def test_serialize_and_write_artifact(tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    built = dd.build_from_sqlite(
        db,
        provided_defs={"customers.customer_id": {"definition": "claimed key", "claims_key": True}},
        built_at="2026-06-16T00:00:00Z",
    )
    md = dd.serialize_markdown(built)
    assert "# Data Dictionary — shop" in md
    assert "## Table: `customers`" in md
    assert "⚠" in md  # the corroboration conflict surfaces in the rendered table
    assert "Provenance vocabulary (DD-13)" in md

    md_path, js_path = dd.write_artifact(built, tmp_path / "out")
    assert md_path.name == dd.ARTIFACT_NAME == "DATA_DICTIONARY_MAP.md"
    assert js_path.name == dd.SIDECAR_NAME == "data-dictionary.json"
    reloaded = json.loads(js_path.read_text(encoding="utf-8"))
    assert reloaded["schema"] == "data-dictionary/v1"


def test_cli_build_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    out = tmp_path / "cli-out"
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "build-sqlite", str(db), "--out", str(out)],
        capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0, res.stderr
    assert (out / "DATA_DICTIONARY_MAP.md").exists()
    assert (out / "data-dictionary.json").exists()


# --------------------------------------------------------------------------- #
# skill + agent presence (the contract surfaces exist)
# --------------------------------------------------------------------------- #

def test_skill_and_agent_present() -> None:
    skill = REPO_ROOT / "skills" / "data-dictionary" / "SKILL.md"
    assert skill.exists()
    body = skill.read_text(encoding="utf-8")
    assert body.startswith("---")  # frontmatter
    assert "DATA_DICTIONARY_MAP.md" in body  # standard artifact name (DD-16)
    # the live-DB honesty boundary is stated
    assert "credential" in body.lower() or "reachable" in body.lower()


def test_skill_documents_provenance_and_maintenance() -> None:
    body = (REPO_ROOT / "skills" / "data-dictionary" / "SKILL.md").read_text(encoding="utf-8")
    for prov in dd.PROVENANCE_TYPES:
        assert prov in body  # DD-13 vocabulary documented in the contract
    assert "maintenance discipline" in body.lower()  # DD-17/18
    assert "DD-17" in body and "DD-18" in body


# --------------------------------------------------------------------------- #
# remediation coverage — adversarial-review findings (v3.17.0)
# the green suite must pin exactly the edges the review flagged, not bless them
# --------------------------------------------------------------------------- #

def test_corroborate_definition_flags_nonkey_type_conflict() -> None:
    """DD-14 fires for ANY provided definition, not only key claims: a claimed
    type that the sampled data contradicts is flagged."""
    rows = [{"status": "shipped"}, {"status": "pending"}, {"status": "cancelled"}]
    bad = dd.corroborate_definition(rows, "orders", "status", claimed_type="boolean")
    assert bad["checked"] is True and bad["agrees"] is False and bad["conflict"] is not None
    good = dd.corroborate_definition(rows, "orders", "status", claimed_type="text")
    assert good["agrees"] is True and good["conflict"] is None


def test_build_corroborates_nonkey_provided_def(tmp_path: Path) -> None:
    """A non-key provided definition with a wrong expected_type is corroborated
    against live data and downgraded (the gap the review caught)."""
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    provided = {"customers.email": {
        "definition": "a yes/no opt-in flag", "provenance": "direct-user-input",
        "expected_type": "boolean",  # email column is actually free text
    }}
    built = dd.build_from_sqlite(db, provided_defs=provided, built_at="2026-06-16T00:00:00Z")
    email = {f["field"]: f for f in built["tables"]["customers"]["fields"]}["email"]
    assert email["corroboration"]["agrees"] is False
    assert email["confidence"] == "low"


def test_empty_table_never_claims_live_data(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE blanks (a INTEGER, b TEXT)")  # no rows inserted
        conn.commit()
    finally:
        conn.close()
    built = dd.build_from_sqlite(db, built_at="2026-06-16T00:00:00Z")
    fields = built["tables"]["blanks"]["fields"]
    assert all(f["provenance"] == "inference" for f in fields)  # never live-data
    assert all(f["confidence"] == "low" for f in fields)
    assert built["live_inspection"]["ran"] is True
    assert built["live_inspection"]["rows_sampled_total"] == 0


def test_all_null_column_is_inference_not_live_data(tmp_path: Path) -> None:
    db = tmp_path / "nulls.sqlite"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE t (a INTEGER, notes TEXT)")
        conn.executemany("INSERT INTO t VALUES (?,?)", [(1, None), (2, None), (3, None)])
        conn.commit()
    finally:
        conn.close()
    built = dd.build_from_sqlite(db, built_at="2026-06-16T00:00:00Z")
    by = {f["field"]: f for f in built["tables"]["t"]["fields"]}
    assert by["a"]["provenance"] == "live-data"     # a had real values
    assert by["notes"]["provenance"] == "inference"  # never observed a value


def test_small_sample_inferred_key_is_hedged(tmp_path: Path) -> None:
    db = tmp_path / "tiny.sqlite"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE t (label TEXT, val INTEGER)")  # no declared PK
        conn.executemany("INSERT INTO t VALUES (?,?)", [("x", 1), ("y", 1), ("z", 1)])
        conn.commit()
    finally:
        conn.close()
    provided = {"t.label": {"definition": "the label", "claims_key": True}}
    built = dd.build_from_sqlite(db, provided_defs=provided, built_at="2026-06-16T00:00:00Z")
    t = built["tables"]["t"]
    assert t["grain"]["small_sample_key"] is True
    assert "INFERRED from only 3 sampled row" in t["grain"]["grain"]
    # the claimed key agrees on the sample but is hedged below "high"
    label = {f["field"]: f for f in t["fields"]}["label"]
    assert label["confidence"] == "medium"


def test_reference_map_serialization_renders_populated(tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    built = dd.build_from_sqlite(
        db, code_refs=[{"file": "etl.py", "line": 12, "table": "customers", "field": "zip5"}],
        built_at="2026-06-16T00:00:00Z",
    )
    md = dd.serialize_markdown(built)
    assert "etl.py:12" in md and "customers" in md
    assert "(no code references supplied)" not in md


def test_build_from_inputs_no_db_path() -> None:
    """DD-2 no-DB path: built from code/docs only — never live-data, and the
    artifact records that live inspection did not run."""
    built = dd.build_from_inputs(
        "warehouse",
        {"users": ["user_id", "email", "status"]},
        provided_defs={"users.email": {"definition": "contact email",
                                       "provenance": "direct-user-input"}},
        built_at="2026-06-16T00:00:00Z",
    )
    assert built["live_inspection"]["ran"] is False
    fields = built["tables"]["users"]["fields"]
    assert all(f["provenance"] != "live-data" for f in fields)
    by = {f["field"]: f for f in fields}
    assert by["email"]["provenance"] == "direct-user-input"
    assert built["tables"]["users"]["grain"]["grain"] == "unknown (no live inspection)"
    md = dd.serialize_markdown(built)
    assert "Live inspection (DD-9/10): NOT run" in md


def test_live_inspection_block_present_and_rendered(tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    _make_db(db)
    built = dd.build_from_sqlite(db, built_at="2026-06-16T00:00:00Z")
    li = built["live_inspection"]
    assert li["ran"] is True and li["engine"] == "sqlite"
    assert li["rows_sampled_total"] == 6  # 3 customers + 3 census rows
    assert "Live inspection (DD-9/10): ran against sqlite" in dd.serialize_markdown(built)


def test_odd_identifier_does_not_crash(tmp_path: Path) -> None:
    """A table whose name legally contains a double-quote must not break the
    interpolated PRAGMA / SELECT statements (the _q escape)."""
    db = tmp_path / "odd.sqlite"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute('CREATE TABLE "we""ird" (x INTEGER, y TEXT)')
        conn.execute('INSERT INTO "we""ird" VALUES (1, ?)', ("v",))
        conn.commit()
    finally:
        conn.close()
    built = dd.build_from_sqlite(db, built_at="2026-06-16T00:00:00Z")
    assert 'we"ird' in built["tables"]
