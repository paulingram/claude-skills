"""v4.0.0 -- sample-first iteration for data changes (proposal change 13).

Before a change against a big table is implemented on the full data, the data
lanes profile the subset from the data dictionary, stratify on the dimension the
change depends on (edge rows always included), size the smallest covering sample,
materialize it in a warehouse sandbox, iterate with a before/after diff per
stratum, and scale only when the sample passes. The deterministic machine is
`scripts/data_dictionary/sampling.py` (plan / render_sql / diff_report /
should_sample + CLI); the rule is `skills/data-eng-pipeline/references/
sample-first.md`; four skills point at both.

These tests pin the engine over the fixture dictionary at
`tests/fixtures/sampling/data-dictionary.json`, EXECUTE the rendered sqlite SQL
against a real in-memory database (the other three dialects are rendered, not
executed -- the honest boundary the reference states), and pin the appended
skill sections structurally.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "sampling.py"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sampling"
FIXTURE = FIXTURE_DIR / "data-dictionary.json"
REFERENCE = REPO_ROOT / "skills" / "data-eng-pipeline" / "references" / "sample-first.md"
LANE = REPO_ROOT / "skills" / "data-eng-pipeline" / "SKILL.md"
VPLAN = REPO_ROOT / "skills" / "verification-planning" / "SKILL.md"
EVD = REPO_ROOT / "skills" / "expensive-verification-debugging" / "SKILL.md"
EXPLORATION = REPO_ROOT / "skills" / "data-engineering-exploration" / "SKILL.md"

ORDER_COLUMNS = ["id", "customer_id", "region", "status", "order_date", "total_cents"]


@pytest.fixture(scope="module")
def sampling():
    return load_module(MODULE_PATH, "ct6_sampling_under_test")


@pytest.fixture(scope="module")
def dictionary(sampling):
    return sampling.load_dictionary(FIXTURE)


@pytest.fixture()
def filter_plan(sampling, dictionary):
    return sampling.plan(dictionary, "orders", ["status", "order_date"], "filter",
                         reported_rows=[{"id": 17}, 23, [99]])


@pytest.fixture()
def aggregate_plan(sampling, dictionary):
    return sampling.plan(dictionary, "orders", ["customer_id"], "aggregate")


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(MODULE_PATH), *args],
                          capture_output=True, text=True, encoding="utf-8")


def _section(body: str, heading: str) -> str:
    """The section under `heading`, cut at the next `## ` heading OR at the first
    `skill_surface` splice marker (a pointed-at chapter is spliced in right after
    the line that cites it, and its own `## ` headings are not this section's)."""
    start = body.find(heading)
    assert start >= 0, f"heading {heading!r} missing"
    ends = [i for i in (body.find("\n## ", start + len(heading)),
                        body.find("\n<!-- surface:", start + len(heading))) if i > 0]
    return body[start:min(ends)] if ends else body[start:]


# ---------------------------------------------------------------------------
# 1. loading + the skip decision
# ---------------------------------------------------------------------------


def test_load_dictionary_accepts_a_sidecar_or_its_directory(sampling) -> None:
    by_file = sampling.load_dictionary(FIXTURE)
    by_dir = sampling.load_dictionary(FIXTURE_DIR)
    assert by_file == by_dir
    assert by_file["schema"] == "data-dictionary/v1"


def test_load_dictionary_rejects_a_non_dictionary(sampling, tmp_path: Path) -> None:
    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"rows": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        sampling.load_dictionary(bad)
    wrong = tmp_path / "y.json"
    wrong.write_text(json.dumps({"schema": "something/v9", "tables": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        sampling.load_dictionary(wrong)


def test_should_sample_true_on_a_measured_large_table(sampling, dictionary) -> None:
    v = sampling.should_sample(dictionary, "orders")
    assert v["should_sample"] is True
    assert v["row_count"] == 2500000
    assert "row_volume" in v["row_count_basis"]
    assert v["threshold_rows"] == sampling.DEFAULT_THRESHOLD_ROWS


def test_should_sample_false_on_a_measured_small_table(sampling, dictionary) -> None:
    v = sampling.should_sample(dictionary, "customers")
    assert v["should_sample"] is False
    assert v["row_count"] == 1200
    assert "skip" in v["reason"]


def test_should_sample_false_when_the_live_sample_exhausted_the_table(sampling, dictionary) -> None:
    """No usage block, but the sampler asked for 100 rows and got 7: the table IS 7 rows."""
    v = sampling.should_sample(dictionary, "regions")
    assert v["should_sample"] is False
    assert v["row_count"] == 7
    assert "exhausted" in v["row_count_basis"]


def test_should_sample_stays_on_when_the_row_count_is_unknown(sampling, dictionary) -> None:
    v = sampling.should_sample(dictionary, "events")
    assert v["should_sample"] is True
    assert v["row_count"] is None
    assert "unknown" in v["reason"]


def test_should_sample_threshold_is_a_parameter(sampling, dictionary) -> None:
    assert sampling.should_sample(dictionary, "customers", threshold_rows=1000)["should_sample"] is True
    assert sampling.should_sample(dictionary, "orders", threshold_rows=3_000_000)["should_sample"] is False


def test_should_sample_unknown_table_raises(sampling, dictionary) -> None:
    with pytest.raises(KeyError):
        sampling.should_sample(dictionary, "nope")


# ---------------------------------------------------------------------------
# 2. the plan
# ---------------------------------------------------------------------------


def test_plan_identity_grain_keys_columns(filter_plan) -> None:
    assert filter_plan["schema"] == "sample-plan/v1"
    assert filter_plan["table"] == "orders"
    assert filter_plan["grain"].startswith("one row per id")
    assert filter_plan["keys"] == ["id"]
    assert filter_plan["key_basis"] == "declared primary key"
    assert filter_plan["columns"] == ORDER_COLUMNS
    assert filter_plan["partitions"] == ["region"]
    assert filter_plan["seed"] == 42
    assert filter_plan["change_kind"] == "filter"
    assert filter_plan["predicate_columns"] == ["status", "order_date"]


def test_plan_strata_from_partitions_and_predicate_values(filter_plan) -> None:
    by_col = {s["column"]: s for s in filter_plan["strata"]}
    assert list(by_col) == ["region", "status", "order_date"], "partition first, then predicates in order"
    assert by_col["region"]["basis"] == "partition"
    assert by_col["region"]["values"] == ["EU", "US", "APAC"]
    assert by_col["status"]["basis"] == "predicate"
    # the fixture repeats 'open' in sample_values; the stratum dedupes it
    assert by_col["status"]["values"] == ["open", "shipped", "cancelled"]
    assert by_col["status"]["cells"] == 3
    # no sampled values -> hash buckets, and the plan says why
    assert by_col["order_date"]["buckets"] == [0, 1, 2, 3]
    assert by_col["order_date"]["bucket_count"] == 4
    assert "no sampled values" in by_col["order_date"]["why_buckets"]


def test_plan_edge_rows(filter_plan) -> None:
    edge = filter_plan["edge_rows"]
    assert edge["nulls"] == ["region", "status", "order_date"]
    # boundaries only for the NON-enumerated predicate column
    assert edge["boundaries"] == [{"column": "order_date", "edge": "min"},
                                  {"column": "order_date", "edge": "max"}]
    assert edge["duplicates_on"] == ["id"]
    # reported rows normalise: dict kept, scalar bound to the key, list bound positionally
    assert edge["reported"] == [{"id": 17}, {"id": 23}, {"id": 99}]


def test_plan_n_target_is_the_smallest_covering_n(filter_plan) -> None:
    sizing = filter_plan["sizing"]
    # cells: region 3 + status 3 + order_date 4 buckets = 10 ; x3 per cell = 30
    assert sizing["cells"] == 10 and sizing["strata_rows"] == 30
    # edges: 3 null cols x3 + 2 boundaries x3 + duplicates 2x3 + 3 reported = 24
    assert sizing["edge_rows"] == 24
    assert sizing["uncapped"] == 54 and filter_plan["n_target"] == 54
    assert sizing["capped"] is False
    assert filter_plan["warnings"] == []


def test_plan_cap_is_recorded_not_hidden(sampling, dictionary) -> None:
    p = sampling.plan(dictionary, "orders", ["status"], "filter", max_rows=10)
    assert p["n_target"] == 10
    assert p["sizing"]["capped"] is True
    assert any("capped" in w for w in p["warnings"])


def test_plan_threshold_block(filter_plan) -> None:
    th = filter_plan["threshold"]
    assert th["skip_sampling_when_rows_below"] == 100_000
    assert th["basis"] == "dictionary row count"
    assert th["row_count"] == 2500000 and th["should_sample"] is True


def test_plan_materialize_defaults_to_a_warehouse_sandbox(sampling, dictionary, filter_plan) -> None:
    assert filter_plan["materialize"]["kind"] == "temp-table"
    assert filter_plan["materialize"]["target_name"] == "ct6_sample_orders"
    assert "warehouse" in filter_plan["materialize"]["residency_note"]
    assert filter_plan["materialize"]["dedupe_on"] == ["id"]
    local = sampling.plan(dictionary, "orders", ["status"], "filter", allow_local_file=True)
    assert local["materialize"]["kind"] == "local-file"
    assert "principles" in local["materialize"]["residency_note"]


def test_plan_no_group_keys_for_a_row_level_change(filter_plan) -> None:
    assert filter_plan["group_preserving_keys"] == []


@pytest.mark.parametrize("kind", ["aggregate", "window", "dedup", "join"])
def test_plan_group_preserving_kinds_keep_whole_groups(sampling, dictionary, kind: str) -> None:
    p = sampling.plan(dictionary, "orders", ["customer_id"], kind)
    assert p["group_preserving_keys"] == ["customer_id"]
    explicit = sampling.plan(dictionary, "orders", ["status"], kind, group_keys=["customer_id"])
    assert explicit["group_preserving_keys"] == ["customer_id"], "an explicit group key wins"


def test_plan_dedup_judges_duplicates_on_the_predicate_columns(sampling, dictionary) -> None:
    p = sampling.plan(dictionary, "orders", ["customer_id", "status"], "dedup")
    assert p["edge_rows"]["duplicates_on"] == ["customer_id", "status"]
    f = sampling.plan(dictionary, "orders", ["customer_id", "status"], "filter")
    assert f["edge_rows"]["duplicates_on"] == ["id"], "a row-level change judges duplicates on the key"


def test_plan_partition_that_is_also_a_predicate_is_one_stratum(sampling, dictionary) -> None:
    p = sampling.plan(dictionary, "orders", ["region"], "filter")
    assert [s["column"] for s in p["strata"]] == ["region"]
    assert p["strata"][0]["basis"] == "partition+predicate"
    assert p["edge_rows"]["boundaries"] == []


def test_plan_no_key_table_hashes_the_known_columns_and_warns(sampling, dictionary) -> None:
    p = sampling.plan(dictionary, "events", ["kind"], "dedup")
    assert p["keys"] == []
    assert "no key" in p["key_basis"]
    assert any("no key column" in w for w in p["warnings"])
    # a low-cardinality group key makes "whole groups" most of the table -- say so
    assert any("group key 'kind'" in w for w in p["warnings"])
    assert p["edge_rows"]["duplicates_on"] == ["kind"]


def test_plan_low_cardinality_strata_limit(sampling, dictionary) -> None:
    dd = json.loads(json.dumps(dictionary))
    field = next(f for f in dd["tables"]["orders"]["fields"] if f["field"] == "status")
    field["sample_values"] = [f"s{i}" for i in range(sampling.LOW_CARDINALITY_MAX + 1)]
    p = sampling.plan(dd, "orders", ["status"], "filter")
    s = p["strata"][1]
    assert "buckets" in s and "exceed the low-cardinality limit" in s["why_buckets"]


def test_plan_rejects_bad_inputs(sampling, dictionary) -> None:
    with pytest.raises(KeyError):
        sampling.plan(dictionary, "nope", ["x"], "filter")
    with pytest.raises(ValueError, match="predicate column"):
        sampling.plan(dictionary, "orders", ["colour"], "filter")
    with pytest.raises(ValueError, match="change_kind"):
        sampling.plan(dictionary, "orders", ["status"], "truncate")
    with pytest.raises(ValueError, match="group key"):
        sampling.plan(dictionary, "orders", ["status"], "aggregate", group_keys=["nope"])
    with pytest.raises(ValueError):
        sampling.plan(dictionary, "orders", ["status"], "filter", min_per_stratum=0)


def test_plan_is_deterministic_and_json_serialisable(sampling, dictionary) -> None:
    a = sampling.plan(dictionary, "orders", ["status"], "filter", seed=9)
    b = sampling.plan(dictionary, "orders", ["status"], "filter", seed=9)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["seed"] == 9


# ---------------------------------------------------------------------------
# 3. SQL rendering
# ---------------------------------------------------------------------------

HASH_FN = {"postgres": "hashtext", "bigquery": "FARM_FINGERPRINT", "snowflake": "HASH", "sqlite": "ct6_hash"}
QUOTE = {"postgres": '"orders"', "bigquery": "`orders`", "snowflake": '"orders"', "sqlite": '"orders"'}


@pytest.mark.parametrize("dialect", ["postgres", "bigquery", "snowflake", "sqlite"])
def test_render_sql_rows_variant_per_dialect(sampling, filter_plan, dialect: str) -> None:
    sql = sampling.render_sql(filter_plan, dialect)
    assert HASH_FN[dialect] in sql, "the hash function is named per dialect"
    assert QUOTE[dialect] in sql, "identifiers are quoted per dialect"
    assert f"dialect {dialect}" in sql and "variant rows" in sql
    for i in (1, 2, 3):
        assert f"-- stratum {i}:" in sql
    assert "ROW_NUMBER() OVER (PARTITION BY" in sql
    assert "IN ('EU', 'US', 'APAC')" in sql, "a by-value stratum filters on its values"
    assert sql.count("UNION ALL") >= 9, "strata + every edge-row select are unioned"
    for label in ("-- edge: NULL region", "-- edge: NULL status", "-- edge: NULL order_date",
                  "-- edge: min order_date", "-- edge: max order_date",
                  "-- edge: duplicates on id", "-- edge: 3 reported row(s) by key"):
        assert label in sql, label
    assert "= 17" in sql and "= 23" in sql and "= 99" in sql
    assert "+ 42" in sql, "the seed enters the hash order"
    assert "HAVING COUNT(*) > 1" in sql
    # every branch projects the dictionary's columns; the ROW_NUMBER helper never leaks
    assert "SELECT ct6_s1." in sql or f"SELECT ct6_s1.{QUOTE[dialect][0]}" in sql
    assert "ct6_rn <= 3" in sql
    assert sql == sampling.render_sql(filter_plan, dialect), "rendering is deterministic"


@pytest.mark.parametrize("dialect", ["postgres", "bigquery", "snowflake", "sqlite"])
def test_render_sql_group_preserving_variant(sampling, aggregate_plan, dialect: str) -> None:
    sql = sampling.render_sql(aggregate_plan, dialect)  # auto -> groups
    assert "variant groups" in sql
    assert "group-preserving: whole groups kept on customer_id" in sql
    assert "SELECT DISTINCT" in sql, "distinct group keys are sampled first"
    assert "kept ON" in sql, "then every row of each kept group is joined back"
    assert "whole group(s) per cell" in sql
    assert "(whole groups)" in sql, "edge rows pull whole groups too"
    assert "a NULL group key has no group to keep whole" in sql
    rows = sampling.render_sql(aggregate_plan, dialect, variant="rows")
    assert "variant rows" in rows and "kept ON" not in rows


def test_render_sql_variant_rules(sampling, filter_plan, aggregate_plan) -> None:
    with pytest.raises(ValueError, match="group_preserving_keys"):
        sampling.render_sql(filter_plan, "postgres", variant="groups")
    with pytest.raises(ValueError, match="dialect"):
        sampling.render_sql(filter_plan, "mysql")
    with pytest.raises(ValueError, match="variant"):
        sampling.render_sql(filter_plan, "postgres", variant="half")
    with pytest.raises(ValueError, match="sample-plan/v1"):
        sampling.render_sql({"schema": "nope"}, "postgres")


def test_render_sql_multi_column_key_concatenation_per_dialect(sampling, dictionary) -> None:
    dd = json.loads(json.dumps(dictionary))
    dd["tables"]["orders"]["grain"]["declared_pk"] = ["id", "customer_id"]
    p = sampling.plan(dd, "orders", ["status"], "filter")
    pg = sampling.render_sql(p, "postgres")
    bq = sampling.render_sql(p, "bigquery")
    assert "|| '|' ||" in pg and "CONCAT(" not in pg
    assert "CONCAT(" in bq and ", '|', " in bq
    assert "COALESCE(CAST(t.`customer_id` AS STRING), '')" in bq


def test_sqlite_modulo_is_precedence_safe(sampling) -> None:
    d = sampling._Dialect("sqlite")
    assert d.mod("h + 42", 100) == "((h + 42) % 100)"
    assert sampling._Dialect("postgres").mod("h + 42", 100) == "MOD(h + 42, 100)"


# ---------------------------------------------------------------------------
# 4. the sqlite dialect EXECUTES against a real database
# ---------------------------------------------------------------------------


def _orders_db(sampling) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    sampling.register_sqlite_hash(conn)
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, region TEXT, "
                 "status TEXT, order_date TEXT, total_cents INTEGER)")
    regions = ["EU", "US", "APAC", None]
    statuses = ["open", "shipped", "cancelled", None]
    rows = []
    for i in range(1, 241):
        rows.append((
            i,
            (i % 37) if i % 53 else None,
            regions[i % 4] if i % 7 else None,
            statuses[i % 4] if i % 11 else None,
            f"2026-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}" if i % 13 else None,
            i * 100,
        ))
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", rows)
    return conn


def _run(conn: sqlite3.Connection, sql: str) -> tuple[list[str], list[tuple]]:
    cur = conn.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def test_sqlite_rows_variant_executes_and_includes_the_reported_rows(sampling, filter_plan) -> None:
    conn = _orders_db(sampling)
    cols, rows = _run(conn, sampling.render_sql(filter_plan, "sqlite"))
    assert cols == ORDER_COLUMNS, "every UNION ALL branch projects the dictionary's columns"
    ids = {r[0] for r in rows}
    assert {17, 23, 99} <= ids, "the reported rows are in the sample by construction"
    assert any(r[2] is None for r in rows), "a NULL-region edge row is present"
    assert 0 < len(rows) <= filter_plan["n_target"] + 0, "the branches respect their per-cell limits"
    # the sample covers every by-value stratum cell
    assert {"EU", "US", "APAC"} <= {r[2] for r in rows}
    assert {"open", "shipped", "cancelled"} <= {r[3] for r in rows}


def test_sqlite_same_seed_same_rows_different_seed_different_rows(sampling, dictionary) -> None:
    conn = _orders_db(sampling)
    p42 = sampling.plan(dictionary, "orders", ["status"], "filter", seed=42)
    p07 = sampling.plan(dictionary, "orders", ["status"], "filter", seed=7)
    _, a = _run(conn, sampling.render_sql(p42, "sqlite"))
    _, b = _run(conn, sampling.render_sql(p42, "sqlite"))
    _, c = _run(conn, sampling.render_sql(p07, "sqlite"))
    assert a == b, "a rerun with the same seed returns the same rows in the same order"
    assert sorted(a) != sorted(c), "a different seed picks different rows"


def test_sqlite_group_variant_keeps_whole_groups(sampling, aggregate_plan) -> None:
    conn = _orders_db(sampling)
    cols, rows = _run(conn, sampling.render_sql(aggregate_plan, "sqlite"))
    assert cols == ORDER_COLUMNS
    sampled_ids = {r[0] for r in rows}
    kept_customers = {r[1] for r in rows if r[1] is not None}
    assert kept_customers, "some customers were kept"
    every = conn.execute("SELECT id, customer_id FROM orders").fetchall()
    for cid in kept_customers:
        group = {i for i, c in every if c == cid}
        assert group <= sampled_ids, f"customer {cid}: rows {group - sampled_ids} missing from its group"
    assert any(r[1] is None for r in rows), "NULL group-key rows are selected directly, not lost"


def test_sqlite_no_key_table_executes(sampling, dictionary) -> None:
    conn = sqlite3.connect(":memory:")
    sampling.register_sqlite_hash(conn)
    conn.execute("CREATE TABLE events (order_id INTEGER, kind TEXT, at TEXT)")
    conn.executemany("INSERT INTO events VALUES (?,?,?)",
                     [(i % 50, ["created", "paid", "shipped"][i % 3], f"2026-01-01T00:{i % 60:02d}:00")
                      for i in range(300)])
    p = sampling.plan(dictionary, "events", ["kind"], "filter")
    cols, rows = _run(conn, sampling.render_sql(p, "sqlite"))
    assert cols == ["order_id", "kind", "at"]
    assert {"created", "paid", "shipped"} <= {r[1] for r in rows}


def test_sqlite_without_the_registered_hash_fails_loudly(sampling, filter_plan) -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, region TEXT, "
                 "status TEXT, order_date TEXT, total_cents INTEGER)")
    with pytest.raises(sqlite3.OperationalError, match="ct6_hash"):
        conn.execute(sampling.render_sql(filter_plan, "sqlite"))


def test_ct6_hash_is_deterministic_and_fits_sqlite_integers(sampling) -> None:
    assert sampling._ct6_hash("abc") == sampling._ct6_hash("abc")
    assert sampling._ct6_hash("abc") != sampling._ct6_hash("abd")
    assert 0 <= sampling._ct6_hash(None) < (1 << 61)
    assert sampling._ct6_hash(None) == sampling._ct6_hash("")


# ---------------------------------------------------------------------------
# 5. diff_report
# ---------------------------------------------------------------------------

BEFORE = [
    {"id": 1, "region": "EU", "total_cents": 100, "flag": True},
    {"id": 2, "region": "US", "total_cents": 200, "flag": False},
    {"id": 3, "region": "EU", "total_cents": 50, "flag": True},
]


def test_diff_report_unchanged_when_rows_identical_in_any_order(sampling) -> None:
    shuffled = [BEFORE[2], BEFORE[0], BEFORE[1]]
    r = sampling.diff_report(BEFORE, shuffled, ["region"], ["id"])
    assert r["schema"] == "sample-diff/v1"
    assert r["verdict"] == "unchanged"
    assert r["strata_changed"] == []
    assert r["totals"]["before_key_checksum"] == r["totals"]["after_key_checksum"]
    assert r["totals"]["keys_identical"] is True
    assert [s["stratum"] for s in r["strata"]] == ["region=EU", "region=US"]


def test_diff_report_arithmetic_and_checksums(sampling) -> None:
    after = [
        {"id": 1, "region": "EU", "total_cents": 100, "flag": True},
        {"id": 2, "region": "US", "total_cents": 250, "flag": False},   # numeric delta
        {"id": 4, "region": "EU", "total_cents": 50, "flag": True},     # key 3 -> 4
    ]
    r = sampling.diff_report(BEFORE, after, ["region"], ["id"])
    assert r["verdict"] == "changed"
    assert r["numeric_columns"] == ["total_cents"], "key + strata columns and booleans are not aggregated"
    assert r["totals"]["numeric"]["total_cents"] == {"before": 350, "after": 400, "delta": 50}
    by = {s["stratum"]: s for s in r["strata"]}
    eu, us = by["region=EU"], by["region=US"]
    assert eu["before_rows"] == 2 and eu["after_rows"] == 2 and eu["row_delta"] == 0
    assert eu["keys_identical"] is False and eu["keys_added"] == 1 and eu["keys_removed"] == 1
    assert eu["numeric"]["total_cents"]["delta"] == 0
    assert us["keys_identical"] is True and us["numeric"]["total_cents"]["delta"] == 50
    assert r["strata_changed"] == ["region=EU", "region=US"]
    # the checksum is sha256 over the sorted JSON-encoded key tuples, newline-terminated
    expected = hashlib.sha256()
    for k in sorted(json.dumps([i]) for i in (1, 2, 3)):
        expected.update(k.encode("utf-8"))
        expected.update(b"\n")
    assert r["totals"]["before_key_checksum"] == expected.hexdigest()


def test_diff_report_stratum_present_on_one_side_only(sampling) -> None:
    after = [{"id": 9, "region": "APAC", "total_cents": 1}]
    r = sampling.diff_report(BEFORE, after, ["region"], ["id"])
    by = {s["stratum"]: s for s in r["strata"]}
    assert by["region=APAC"]["before_rows"] == 0 and by["region=APAC"]["after_rows"] == 1
    assert by["region=EU"]["after_rows"] == 0
    assert r["totals"]["row_delta"] == -2


def test_diff_report_null_stratum_and_no_strata(sampling) -> None:
    rows = [{"id": 1, "region": None, "v": 2}]
    r = sampling.diff_report(rows, rows, ["region"], ["id"])
    assert r["strata"][0]["stratum"] == "region=NULL"
    flat = sampling.diff_report(rows, rows, [], ["id"])
    assert flat["strata"][0]["stratum"] == "(all)"
    # without key columns the whole row is the key
    nokey = sampling.diff_report(rows, [{"id": 1, "region": None, "v": 3}], [], [])
    assert nokey["verdict"] == "changed" and nokey["totals"]["keys_identical"] is False


# ---------------------------------------------------------------------------
# 6. CLI round trips
# ---------------------------------------------------------------------------


def test_cli_plan_json_round_trips(sampling, dictionary, tmp_path: Path) -> None:
    reported = tmp_path / "reported.json"
    reported.write_text(json.dumps([{"id": 17}, 23, [99]]), encoding="utf-8")
    out = tmp_path / "plan.json"
    res = _run_cli("plan", "--dictionary", str(FIXTURE), "--table", "orders",
                   "--predicate", "status", "order_date", "--change-kind", "filter",
                   "--reported-rows", str(reported), "--out", str(out), "--json")
    assert res.returncode == 0, res.stderr
    printed = json.loads(res.stdout)
    written = json.loads(out.read_text(encoding="utf-8"))
    expected = sampling.plan(dictionary, "orders", ["status", "order_date"], "filter",
                             reported_rows=[{"id": 17}, 23, [99]])
    assert printed == written == expected


def test_cli_plan_human_summary_and_flags(tmp_path: Path) -> None:
    res = _run_cli("plan", "--dictionary", str(FIXTURE_DIR), "--table", "orders",
                   "--predicate", "customer_id", "--change-kind", "aggregate",
                   "--seed", "5", "--min-per-stratum", "2", "--max-rows", "20")
    assert res.returncode == 0, res.stderr
    assert "sample plan for orders" in res.stdout and "seed 5" in res.stdout
    assert "group keys ['customer_id']" in res.stdout


def test_cli_sql_renders_from_a_plan_file(tmp_path: Path) -> None:
    out = tmp_path / "plan.json"
    assert _run_cli("plan", "--dictionary", str(FIXTURE), "--table", "orders", "--predicate",
                    "customer_id", "--change-kind", "aggregate", "--out", str(out)).returncode == 0
    for dialect, fn in HASH_FN.items():
        res = _run_cli("sql", "--plan", str(out), "--dialect", dialect)
        assert res.returncode == 0, res.stderr
        assert res.stdout.startswith("-- sample-plan/v1 :: table orders :: dialect " + dialect)
        assert fn in res.stdout and "variant groups" in res.stdout
    rows = _run_cli("sql", "--plan", str(out), "--dialect", "postgres", "--variant", "rows")
    assert "variant rows" in rows.stdout
    sql_out = tmp_path / "sample.sql"
    assert _run_cli("sql", "--plan", str(out), "--dialect", "sqlite", "--out", str(sql_out)).returncode == 0
    assert sql_out.read_text(encoding="utf-8") == _run_cli("sql", "--plan", str(out), "--dialect", "sqlite").stdout


def test_cli_diff_json_uses_the_plan_strata_and_keys(tmp_path: Path) -> None:
    out = tmp_path / "plan.json"
    assert _run_cli("plan", "--dictionary", str(FIXTURE), "--table", "orders", "--predicate",
                    "status", "--change-kind", "filter", "--out", str(out)).returncode == 0
    before = tmp_path / "b.json"
    after = tmp_path / "a.json"
    before.write_text(json.dumps(BEFORE), encoding="utf-8")
    after.write_text(json.dumps(BEFORE[:2] + [{"id": 3, "region": "EU", "total_cents": 75, "flag": True}]),
                     encoding="utf-8")
    res = _run_cli("diff", "--before", str(before), "--after", str(after), "--plan", str(out), "--json")
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["strata_columns"] == ["region", "status"] and report["key_columns"] == ["id"]
    assert report["verdict"] == "changed"
    assert report["totals"]["numeric"]["total_cents"]["delta"] == 25
    human = _run_cli("diff", "--before", str(before), "--after", str(after), "--strata", "region", "--keys", "id")
    assert human.returncode == 0 and human.stdout.startswith("sample diff: changed")


def test_cli_should_sample_json_both_ways() -> None:
    yes = _run_cli("should-sample", "--dictionary", str(FIXTURE), "--table", "orders", "--json")
    no = _run_cli("should-sample", "--dictionary", str(FIXTURE), "--table", "customers", "--json")
    assert yes.returncode == 0 and no.returncode == 0
    assert json.loads(yes.stdout)["should_sample"] is True
    assert json.loads(no.stdout)["should_sample"] is False
    human = _run_cli("should-sample", "--dictionary", str(FIXTURE), "--table", "regions")
    assert human.stdout.startswith("should-sample regions: False")


def test_cli_errors_exit_2_with_a_message() -> None:
    res = _run_cli("plan", "--dictionary", str(FIXTURE), "--table", "nope", "--change-kind", "filter")
    assert res.returncode == 2 and "not in the dictionary" in res.stderr
    res = _run_cli("plan", "--dictionary", str(FIXTURE), "--table", "orders", "--predicate", "colour",
                   "--change-kind", "filter")
    assert res.returncode == 2 and "colour" in res.stderr


# ---------------------------------------------------------------------------
# 7. the reference + the appended skill sections
# ---------------------------------------------------------------------------


def test_reference_exists_opens_with_stop_and_stays_short() -> None:
    assert REFERENCE.exists()
    text = REFERENCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("> **STOP.**"), "the reference begins with the STOP line"
    assert len(lines) < 150


def test_reference_states_the_six_steps_and_the_rules() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    low = text.lower()
    for step in ("**profile**", "**stratify**", "**size**", "**materialize**", "**iterate**", "**scale**"):
        assert step in low, step
    assert "group-preserving" in low and "whole group" in low
    for plug in ("phase d2", "b1", "b6", "verification-planning"):
        assert plug in low, plug
    assert "--full-data" in text and "principle" in low
    assert "residency" in low and "inside the warehouse" in low
    assert "honest boundaries" in low and "hide a bug" in low and "full run stays the gate" in low
    assert "seed" in low and "source_query" in text
    assert "scripts/data_dictionary/sampling.py" in text
    for cmd in ("should-sample", "plan ", "sql --plan", "diff --before"):
        assert cmd in text, cmd


def test_lane_skill_carries_the_sample_first_section_before_d2() -> None:
    body = skill_surface("data-eng-pipeline")
    idx = body.find("## Sample-first iteration (v4.0.0)")
    d1 = body.find("## Phase D1")
    d2 = body.find("## Phase D2")
    assert idx >= 0 and d1 >= 0 and d2 >= 0
    assert d1 < idx < d2, "the section sits between D1 and D2 - before implementation"
    section = _section(body, "## Sample-first iteration (v4.0.0)")
    assert "references/sample-first.md" in section
    assert "scripts/data_dictionary/sampling.py" in section
    assert "--full-data" in section and "should-sample" in section and "--change-kind" in section
    assert "group_preserving_keys" in section
    assert 6 <= len([ln for ln in section.splitlines() if ln.strip()]) <= 10


def test_verification_planning_lists_the_stratified_sample_venue() -> None:
    body = skill_surface("verification-planning")
    menu = _section(body, "## The venue menu")
    rows = [ln for ln in menu.splitlines() if ln.startswith("| **Stratified sample**")]
    assert len(rows) == 1, "exactly one venue row for the stratified sample"
    assert "sampling.py" in rows[0]
    assert "cheapest faithful venue for a data claim" in menu
    assert "skills/data-eng-pipeline/references/sample-first.md" in menu, (
        "the venue section points at the chapter (below the table, so the splice never lands mid-table)"
    )
    assert "<!-- surface:" not in menu, "the chapter is spliced after the sentence, not inside the table"
    # the original five venues are untouched
    for venue in ("Local run**", "Replay**", "Seeded fixture**", "Dev environment**", "Production ("):
        assert f"| **{venue}" in menu, venue


def test_expensive_verification_debugging_opens_by_asking_about_sampling() -> None:
    body = skill_surface("expensive-verification-debugging")
    after_fm = body.split("---", 2)[2]
    non_blank = [ln for ln in after_fm.splitlines() if ln.strip()]
    assert non_blank[0].startswith("# "), "the H1 is still the first body line"
    opener = non_blank[1]
    assert opener.startswith("**Before batching fixes for an expensive cycle")
    assert "sampling" in opener.lower()
    assert "sample-first.md" in opener and "scripts/data_dictionary/sampling.py" in opener
    assert "verification-planning" in opener


def test_exploration_links_the_profile_to_the_sample_plan() -> None:
    body = skill_surface("data-engineering-exploration")
    stage4 = body.split("## Stage 4", 1)[1].split("\n## ", 1)[0]
    assert "Sample-first hand-off (v4.0.0)" in stage4
    assert "sample-plan.json" in stage4 and "scripts/data_dictionary/sampling.py" in stage4
    assert "current_rows" in stage4


def test_engine_and_this_module_are_ascii_only() -> None:
    for path in (MODULE_PATH, Path(__file__)):
        raw = path.read_bytes()
        assert all(b < 128 for b in raw), f"{path} carries non-ASCII bytes"


def test_engine_has_no_import_side_effects(sampling) -> None:
    """Importing the module must not load the data_dictionary engine; only
    `load_dictionary` (directory resolution) reaches for it, lazily."""
    fresh = load_module(MODULE_PATH, "ct6_sampling_fresh")
    assert fresh._LOADED == {}
    fresh.load_dictionary(FIXTURE_DIR)
    assert "ct6_sampling_dd" in fresh._LOADED
