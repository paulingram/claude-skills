"""Run F folded fast-follow F1 — `data_dictionary.py::_usage_block` OMITs the
block when every usage sub-value is None/absent (red-first).

The R4 usage block is MEASURED, never fabricated: an absent source table returns
`None` and the block is omitted. The F1 residual: a misbehaving adapter that
returns a NON-`None` but empty (or all-`None`) mapping for a table used to attach
an all-`None` `usage` block with provenance `live-data` — a fabricated "measured"
block carrying no measurement. F1 makes `_usage_block` OMIT the block whenever
`read_recency`, `write_recency`, and `row_volume` are all `None`/absent, so an
empty mapping behaves exactly as if the source returned `None`. Run E's usage
tests (`tests/test_usage_review.py`) stay green — a legitimate, populated block
still attaches unchanged.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
DD_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "data_dictionary.py"

dd = load_module(DD_PATH, "ct6_dd_usage_f1")


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, status TEXT)")
        conn.executemany("INSERT INTO orders VALUES (?,?)", [(1, "shipped"), (2, "pending")])
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# F1 — the red-first fast-follow
# --------------------------------------------------------------------------- #
def test_usage_block_all_none_omitted() -> None:
    # A NON-None but empty mapping ({}-style) carries no measurement — OMIT it,
    # exactly as if the source returned None (pre-fix it attached an all-None block).
    src = dd.FakeUsageStatsSource({"orders": {}})
    assert dd._usage_block(src, "orders") is None


def test_usage_block_all_none_values_omitted() -> None:
    # An explicit all-None mapping is the same non-measurement — OMIT it.
    src = dd.FakeUsageStatsSource(
        {"orders": {"read_recency": None, "write_recency": None, "row_volume": None}}
    )
    assert dd._usage_block(src, "orders") is None


def test_usage_block_partial_stats_still_attached() -> None:
    # keep-green counterpart — a single measured sub-value is a real measurement;
    # the block MUST still attach (the fix must not over-omit).
    src = dd.FakeUsageStatsSource({"orders": {"row_volume": 5}})
    block = dd._usage_block(src, "orders")
    assert block is not None
    assert block["row_volume"] == 5
    assert block["read_recency"] is None and block["write_recency"] is None
    assert block["provenance"] == "live-data"


def test_usage_block_absent_source_still_none() -> None:
    # unchanged behaviour — no source, or a table the source has no stats for, omits.
    assert dd._usage_block(None, "orders") is None
    assert dd._usage_block(dd.FakeUsageStatsSource({}), "orders") is None


def test_build_omits_usage_for_all_none_mapping(tmp_path: Path) -> None:
    # integration — a misbehaving adapter returning a non-None empty mapping must
    # NOT get an all-None usage block attached through build_from_sqlite.
    db = tmp_path / "s.sqlite"
    _make_db(db)
    src = dd.FakeUsageStatsSource({"orders": {}})
    built = dd.build_from_sqlite(db, usage_stats=src, built_at="t")
    assert "usage" not in built["tables"]["orders"]
    assert "usage" not in json.dumps(built)


def test_build_attaches_usage_for_populated_mapping(tmp_path: Path) -> None:
    # keep-green — a populated mapping still attaches at provenance live-data.
    db = tmp_path / "s.sqlite"
    _make_db(db)
    src = dd.FakeUsageStatsSource(
        {"orders": {"read_recency": "2026-08-01", "write_recency": "2026-07-30", "row_volume": 42}}
    )
    built = dd.build_from_sqlite(db, usage_stats=src, built_at="t")
    assert built["tables"]["orders"]["usage"]["row_volume"] == 42
    assert built["tables"]["orders"]["usage"]["provenance"] == "live-data"
