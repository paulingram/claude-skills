"""Tests for the warehouse-sql-mining engine (Run C; SQL-MINING-1..N).

Covers the deterministic stdlib extractor `scripts/sql_mining/sql_mining.py`:

* extraction correctness over fixture `.sql` objects — joins (`table.col=table.col`),
  aggregate + ratio metric shapes, filter predicates, and table read/write
  relationships;
* parse-coverage honesty — a mixed directory yields accurate
  `{parsed, skipped:[{object,reason}], failed:[{object,reason}]}` stats, a
  deliberately-unparseable object lands in `failed` WITH a reason, an exotic /
  dialect-specific object lands in `skipped` WITH a reason, nothing is silently
  dropped, and the run never crashes on a bad object;
* corroboration is the gate — mined field/metric candidates enter at provenance
  `inference` (never stronger) and pass through
  `scripts/data_dictionary/data_dictionary.py::corroborate_definition`; a mined
  claim the data contradicts is flagged and confidence-downgraded, NOT accepted;
* lineage emission uses ONLY the existing `hooks/lineage_graph.py` `data_asset`
  node kind + `reads`/`writes` edge kinds — no invented kinds.

The engine is `scripts/`-tier stdlib and imports NO third-party parser (no
`sqlglot`) — asserted structurally so a full-parser dependency cannot creep in.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "sql_mining" / "sql_mining.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sql_mining"

sm = load_module(MODULE_PATH, name="sql_mining")
lg = load_module(REPO_ROOT / "hooks" / "lineage_graph.py", name="lineage_graph")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _object(artifact: dict, name_substr: str) -> dict:
    for obj in artifact["objects"]:
        if name_substr.lower() in obj["object"].lower():
            return obj
    raise AssertionError(f"no parsed object matching {name_substr!r} in {[o['object'] for o in artifact['objects']]}")


def _mine_all() -> dict:
    return sm.mine_dir(FIXTURES)


# --------------------------------------------------------------------------- #
# 1. Extraction correctness — joins + metrics (SQL-MINING scenario 1)
# --------------------------------------------------------------------------- #
def test_join_extracted_with_both_sides_as_table_col():
    art = _mine_all()
    obj = _object(art, "OrderSummary")
    assert obj["joins"], "expected at least one join in usp_OrderSummary"
    # both sides recorded as qualified columns; tables resolved from the aliases
    sides = {(j["left"], j["right"]) for j in obj["joins"]}
    assert ("o.CustomerId", "c.Id") in sides or ("c.Id", "o.CustomerId") in sides
    j = obj["joins"][0]
    assert j["left_table"] and j["right_table"]
    assert {j["left_table"], j["right_table"]} == {"dbo.Orders", "dbo.Customers"}


def test_sum_and_ratio_metric_shapes_extracted():
    art = _mine_all()
    obj = _object(art, "OrderSummary")
    funcs = {m.get("func") for m in obj["metrics"]}
    shapes = {m.get("shape") for m in obj["metrics"]}
    assert "SUM" in funcs, f"expected a SUM aggregate metric, got {obj['metrics']}"
    assert "ratio" in shapes, f"expected a ratio metric shape, got {obj['metrics']}"
    # the SUM aggregate carries its argument + (where present) its alias
    sum_metric = next(m for m in obj["metrics"] if m.get("func") == "SUM")
    assert "Amount" in (sum_metric.get("arg") or "")
    ratio_metric = next(m for m in obj["metrics"] if m.get("shape") == "ratio")
    assert "/" in (ratio_metric.get("expr") or "")


def test_filter_predicate_extracted():
    art = _mine_all()
    obj = _object(art, "OrderSummary")
    cols = {f.get("column") for f in obj["filters"]}
    assert "o.Status" in cols, f"expected a filter on o.Status, got {obj['filters']}"


# --------------------------------------------------------------------------- #
# 2. Read/write relationships (SQL-MINING scenario 2)
# --------------------------------------------------------------------------- #
def test_read_source_and_write_target_extracted():
    art = _mine_all()
    obj = _object(art, "DailyRollup") if any("DailyRollup" in o["object"] for o in art["objects"]) \
        else _object(art, "etl_copy_a_to_b")
    assert "raw.Events" in obj["reads"], f"expected read of raw.Events, got {obj['reads']}"
    assert "analytics.DailyRollup" in obj["writes"], f"expected write of analytics.DailyRollup, got {obj['writes']}"


def test_proc_reads_both_join_tables_and_writes_summary():
    art = _mine_all()
    obj = _object(art, "OrderSummary")
    assert set(obj["reads"]) >= {"dbo.Orders", "dbo.Customers"}
    assert "dbo.OrderSummary" in obj["writes"]


# --------------------------------------------------------------------------- #
# 3. Parse-coverage honesty (the deng fidelity lesson, made structural)
# --------------------------------------------------------------------------- #
def test_coverage_arms_populate_and_nothing_is_dropped():
    art = _mine_all()
    cov = art["coverage"]
    counts = cov["counts"]
    # 5 fixture objects: 3 parseable, 1 exotic (skipped), 1 malformed (failed)
    assert counts["total"] == counts["parsed"] + counts["skipped"] + counts["failed"]
    n_files = len(list(FIXTURES.glob("*.sql")))
    assert counts["total"] == n_files, "every object must be accounted for — nothing silently dropped"
    assert counts["parsed"] >= 3
    assert counts["skipped"] >= 1
    assert counts["failed"] >= 1


def test_unparseable_object_lands_in_failed_with_a_reason():
    art = _mine_all()
    failed = art["coverage"]["failed"]
    assert failed, "the malformed fixture must land in failed"
    entry = failed[0]
    assert entry["object"], "a failed entry names its object"
    assert isinstance(entry["reason"], str) and entry["reason"].strip(), "a failed entry states a reason"
    assert "Broken" in " ".join(e["object"] for e in failed)


def test_exotic_object_lands_in_skipped_with_a_reason():
    art = _mine_all()
    skipped = art["coverage"]["skipped"]
    assert skipped, "the exotic dynamic-SQL fixture must land in skipped"
    entry = skipped[0]
    assert isinstance(entry["reason"], str) and entry["reason"].strip()
    assert "Dynamic" in " ".join(e["object"] for e in skipped)


def test_run_does_not_crash_on_the_bad_object_directory():
    # The whole point: mining a directory that contains malformed + exotic objects
    # completes and returns an artifact rather than raising.
    art = _mine_all()
    assert art["schema"] == sm.SCHEMA
    assert isinstance(art["objects"], list)


def test_no_keyword_match_inside_a_string_literal():
    # The exotic object's dynamic SQL contains `FROM Ledger` / `SUM(Amount)` INSIDE a
    # string literal; the extractor must NOT mis-parse those as real shapes.
    art = _mine_all()
    parsed_names = {o["object"] for o in art["objects"]}
    assert not any("Dynamic" in n for n in parsed_names), (
        "dynamic SQL inside a string must not be parsed as a real object"
    )
    # and Ledger (only ever named inside the string) is never a mined read anywhere
    for obj in art["objects"]:
        assert "Ledger" not in obj["reads"], "matched a table name inside a string literal"


# --------------------------------------------------------------------------- #
# 4. Corroboration is the gate (SQL-MINING corroboration scenario)
# --------------------------------------------------------------------------- #
def test_mined_candidates_enter_at_provenance_inference():
    art = _mine_all()
    assert art["dictionary_candidates"], "the parseable objects yield metric/field candidates"
    for cand in art["dictionary_candidates"]:
        assert cand["provenance"] == "inference", (
            "mined content must NEVER enter at a provenance stronger than inference"
        )


def test_conflicting_mined_claim_is_flagged_and_downgraded_not_accepted():
    # A mined numeric metric candidate corroborated against sampled data that is
    # actually free text -> corroborate_definition disagrees -> flag + downgrade.
    candidate = {
        "object": "usp_OrderSummary",
        "table": "dbo.OrderSummary",
        "column": "TotalAmount",
        "definition": "SUM(o.Amount) — mined aggregate metric",
        "provenance": "inference",
        "confidence": "medium",
        "claimed_type": "numeric",
        "kind": "metric",
    }
    rows = [{"TotalAmount": "pending"}, {"TotalAmount": "n/a"}, {"TotalAmount": "TBD"}]
    result = sm.corroborate_mined_claim(candidate, rows=rows)
    assert result["provenance"] == "inference", "still inference — never promoted by corroboration"
    assert result["flagged"] is True
    assert result["accepted"] is False, "a conflicting mined claim is NOT accepted"
    assert result["confidence"] == "low", "confidence downgraded on conflict"
    assert result["corroboration"] is not None and result["corroboration"]["agrees"] is False
    assert result["conflict"], "the conflict reason is surfaced"


def test_corroborated_mined_claim_that_agrees_is_kept_but_stays_inference():
    candidate = {
        "object": "usp_OrderSummary",
        "table": "dbo.OrderSummary",
        "column": "TotalAmount",
        "definition": "SUM(o.Amount) — mined aggregate metric",
        "provenance": "inference",
        "confidence": "medium",
        "claimed_type": "numeric",
        "kind": "metric",
    }
    rows = [{"TotalAmount": 100}, {"TotalAmount": 250}, {"TotalAmount": 90}]
    result = sm.corroborate_mined_claim(candidate, rows=rows)
    assert result["flagged"] is False
    assert result["accepted"] is True
    assert result["provenance"] == "inference", "agreement never promotes above inference"
    assert result["confidence"] == "medium"


def test_corroboration_uses_the_real_data_dictionary_engine():
    # The gate composes data_dictionary.corroborate_definition (not a re-implementation):
    # its verdict dict carries the engine's fields.
    candidate = {"table": "T", "column": "c", "claimed_type": "integer", "confidence": "medium",
                 "provenance": "inference", "kind": "field"}
    rows = [{"c": 1}, {"c": 2}]
    result = sm.corroborate_mined_claim(candidate, rows=rows)
    corro = result["corroboration"]
    assert set(corro) >= {"checked", "agrees", "actual_type"}, corro


# --------------------------------------------------------------------------- #
# 5. Lineage emission uses ONLY existing node/edge kinds (no invented kinds)
# --------------------------------------------------------------------------- #
def test_lineage_fragment_validates_and_uses_only_existing_kinds():
    art = _mine_all()
    graph = art["lineage"]
    assert lg.validate_lineage_graph(graph) == [], "the emitted lineage graph must be schema-valid"
    node_kinds = {n["kind"] for n in graph["nodes"]}
    edge_kinds = {e["kind"] for e in graph["edges"]}
    assert node_kinds <= lg.NODE_KINDS, f"invented node kind(s): {node_kinds - lg.NODE_KINDS}"
    assert edge_kinds <= lg.EDGE_KINDS, f"invented edge kind(s): {edge_kinds - lg.EDGE_KINDS}"
    # concretely: only data_asset + function nodes, only reads/writes edges
    assert node_kinds <= {"data_asset", "function"}
    assert edge_kinds <= {"reads", "writes"}


def test_lineage_records_reads_and_writes_attributed_to_the_object():
    art = _mine_all()
    graph = art["lineage"]
    reads = {(e["src"], e["dst"]) for e in graph["edges"] if e["kind"] == "reads"}
    writes = {(e["src"], e["dst"]) for e in graph["edges"] if e["kind"] == "writes"}
    assert reads, "expected reads edges"
    assert writes, "expected writes edges"
    # the ETL object reads raw.Events and writes analytics.DailyRollup as data_asset nodes
    asset_names = {n["id"]: n.get("name") for n in graph["nodes"] if n["kind"] == "data_asset"}
    assert any(v == "raw.Events" for v in asset_names.values())
    assert any(v == "analytics.DailyRollup" for v in asset_names.values())


def test_data_asset_ids_are_canonical_asset_uris():
    art = _mine_all()
    graph = art["lineage"]
    for n in graph["nodes"]:
        if n["kind"] == "data_asset":
            assert lg.parse_asset_id(n["id"]) is not None, f"not a canonical asset:// id: {n['id']}"


# --------------------------------------------------------------------------- #
# 6. Stdlib-only — no third-party parser dependency may creep in
# --------------------------------------------------------------------------- #
_STDLIB_IMPORT_ROOTS = {
    "__future__", "argparse", "json", "re", "importlib", "pathlib", "typing", "datetime",
    "dataclasses", "collections", "sys", "os",
}
_FORBIDDEN = {"sqlglot", "sqlparse", "pandas", "numpy", "antlr4", "moz_sql_parser", "sqlalchemy"}


def test_engine_imports_only_stdlib_no_third_party_parser():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    assert roots & _FORBIDDEN == set(), f"third-party parser import crept in: {roots & _FORBIDDEN}"
    assert roots <= _STDLIB_IMPORT_ROOTS, f"unexpected non-stdlib import root(s): {roots - _STDLIB_IMPORT_ROOTS}"


# --------------------------------------------------------------------------- #
# 7. CLI (mirrors data_dictionary.py's shape) + artifact write
# --------------------------------------------------------------------------- #
def test_cli_mine_writes_artifact(tmp_path):
    rc = sm.main(["mine", str(FIXTURES), "--out", str(tmp_path)])
    assert rc == 0
    js = tmp_path / sm.SIDECAR_NAME
    md = tmp_path / sm.ARTIFACT_NAME
    assert js.exists() and md.exists()
    art = json.loads(js.read_text(encoding="utf-8"))
    assert art["schema"] == sm.SCHEMA
    assert art["coverage"]["counts"]["total"] >= 5
    # the human view names the coverage stats
    text = md.read_text(encoding="utf-8")
    assert "parsed" in text.lower() and "skipped" in text.lower() and "failed" in text.lower()


def test_artifact_carries_all_required_sections():
    art = _mine_all()
    for key in ("schema", "objects", "coverage", "dictionary_candidates", "lineage"):
        assert key in art, f"artifact missing {key}"
    for key in ("parsed", "skipped", "failed", "counts"):
        assert key in art["coverage"]


# --------------------------------------------------------------------------- #
# 8. Review-finding regressions (independent review — both fix-forward)
# --------------------------------------------------------------------------- #
def test_undecodable_encodings_route_to_failed_without_crash(tmp_path):
    # FINDING 1 (BLOCKING) — a UTF-16 .sql (SSMS's default script-export encoding)
    # or a cp1252 file with an accented char is NOT valid utf-8. It MUST land in
    # `failed` with a reason, never raise UnicodeDecodeError and kill the run —
    # the load-bearing "never crashes the run" claim must hold for this mainstream
    # T-SQL input class.
    u16 = tmp_path / "ssms_utf16.sql"
    u16.write_text("CREATE PROCEDURE dbo.usp_U16 AS SELECT SUM(x) FROM T;\n", encoding="utf-16")
    cp = tmp_path / "cp1252_accent.sql"
    cp.write_bytes("CREATE PROCEDURE dbo.usp_Cafe AS SELECT 1 AS r\xe9sultat;\n".encode("cp1252"))
    art = sm.mine_paths([u16, cp])  # must NOT raise
    failed_objs = {e["object"] for e in art["coverage"]["failed"]}
    assert "ssms_utf16.sql" in failed_objs, failed_objs
    assert "cp1252_accent.sql" in failed_objs, failed_objs
    for e in art["coverage"]["failed"]:
        assert isinstance(e["reason"], str) and e["reason"].strip()
        assert "utf-8" in e["reason"].lower() or "decod" in e["reason"].lower(), e["reason"]


def test_utf8_bom_file_still_parses():
    # BOM tolerance regression: a utf-8-with-BOM file (utf-8-sig) must still parse
    # cleanly — the encoding hardening must not break ordinary UTF-8-BOM exports.
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as d:
        p = _P(d) / "bom.sql"
        p.write_text("CREATE VIEW dbo.vBom AS SELECT a.x FROM dbo.A a;\n", encoding="utf-8-sig")
        art = sm.mine_paths([p])
        assert any("vBom" in o["object"] for o in art["objects"]), art["coverage"]
        obj = next(o for o in art["objects"] if "vBom" in o["object"])
        assert "dbo.A" in obj["reads"]


def test_ratio_false_positive_on_substring_aggregate_name(tmp_path):
    # FINDING 2 — 'count' is a substring of 'Discount'. A word-boundary aggregate
    # check must NOT mine `o.Discount / o.Total` as a ratio metric (there is no
    # real aggregate operand) — that would be the silent mis-parse the recognition
    # rule forbids. The read of dbo.Orders must still be extracted.
    f = tmp_path / "discount_rate.sql"
    f.write_text(
        "CREATE VIEW dbo.vDiscountRate AS\n"
        "SELECT o.Discount / o.Total AS DiscountRate\n"
        "FROM dbo.Orders o;\n",
        encoding="utf-8",
    )
    art = sm.mine_paths([f])
    obj = next(o for o in art["objects"] if "vDiscountRate" in o["object"])
    ratios = [m for m in obj["metrics"] if m.get("shape") == "ratio"]
    assert ratios == [], f"Discount/Total wrongly mined as a ratio metric: {ratios}"
    assert obj["metrics"] == [], f"no aggregate operand exists — expected no metrics, got {obj['metrics']}"
    assert "dbo.Orders" in obj["reads"], "real read extraction must be preserved"


def test_real_ratio_with_aggregate_operand_still_mined(tmp_path):
    # The counterpart guard: a genuine aggregate ratio MUST still be mined, so the
    # word-boundary fix does not over-correct into dropping real ratio metrics.
    f = tmp_path / "avg_ticket.sql"
    f.write_text(
        "CREATE VIEW dbo.vAvgTicket AS\n"
        "SELECT SUM(o.Amount) / COUNT(o.OrderId) AS AvgTicket\n"
        "FROM dbo.Orders o;\n",
        encoding="utf-8",
    )
    art = sm.mine_paths([f])
    obj = next(o for o in art["objects"] if "vAvgTicket" in o["object"])
    assert any(m.get("shape") == "ratio" for m in obj["metrics"]), obj["metrics"]


def test_utf16_committed_fixture_lands_in_failed_not_crash():
    # The committed SSMS-default UTF-16 fixture: the whole-directory mine completes
    # (no crash) and routes it to `failed` with a reason — the real-world scenario
    # of a mixed-encoding warehouse export directory.
    art = _mine_all()
    failed = {e["object"]: e["reason"] for e in art["coverage"]["failed"]}
    u16 = next((o for o in failed if "utf16" in o.lower()), None)
    assert u16 is not None, f"utf16 fixture not routed to failed: {list(failed)}"
    assert "utf-8" in failed[u16].lower() or "decod" in failed[u16].lower(), failed[u16]


def test_nested_block_comment_does_not_leak_a_phantom_table(tmp_path):
    # FINDING 1 (BLOCKING) — T-SQL supports NESTED block comments. In
    # `/* outer /* inner */ SELECT x FROM PhantomTable */` the WHOLE span is a
    # comment; an extractor that stops at the FIRST `*/` leaks `FROM PhantomTable`
    # as a real read — flipping the object skipped->parsed AND injecting a false,
    # ungated phantom lineage edge. scrub_and_mask must track comment DEPTH.
    f = tmp_path / "nested_comment.sql"
    f.write_text(
        "CREATE PROCEDURE dbo.usp_Nested AS\n"
        "BEGIN\n"
        "    /* outer /* inner */ SELECT x FROM PhantomTable */\n"
        "    DECLARE @x INT = 1;\n"
        "END\n",
        encoding="utf-8",
    )
    art = sm.mine_paths([f])
    # PhantomTable (named ONLY inside the nested comment) is never a mined read
    for obj in art["objects"]:
        assert "PhantomTable" not in obj["reads"], f"phantom table leaked: {obj['reads']}"
    # the object has no real shape -> honestly skipped, not flipped to parsed
    assert not any("Nested" in o["object"] for o in art["objects"]), "phantom read flipped skipped->parsed"
    assert any("Nested" in e["object"] for e in art["coverage"]["skipped"]), art["coverage"]
    # and no phantom data_asset node leaked into the lineage graph
    asset_names = {n.get("name") for n in art["lineage"]["nodes"] if n["kind"] == "data_asset"}
    assert not any("PhantomTable" in (nm or "") for nm in asset_names), asset_names


def test_deeply_nested_and_unterminated_block_comments():
    # depth tracking, both directions: a 3-level nested comment is fully masked;
    # an unterminated (depth never returns to 0) comment is a SqlParseError -> failed.
    masked = sm.scrub_and_mask("SELECT 1 /* a /* b /* c */ d */ e */ , 2")
    assert "FROM" not in masked  # nothing leaks
    import pytest as _pt
    with _pt.raises(sm.SqlParseError):
        sm.scrub_and_mask("SELECT 1 /* a /* b */ still open")


def test_uncorroborated_candidates_are_machine_marked_not_accepted():
    # FINDING 2 (OVERCLAIM) — the no-context (text-only) mine path emits candidates
    # that never passed corroborate_definition. The provenance invariant holds
    # (they stay 'inference', never promoted), but they MUST be machine-marked as
    # uncorroborated + not-accepted so the skill's claim matches reality; a bare
    # 'medium' with no marker is the overclaim.
    art = _mine_all()
    assert art["dictionary_candidates"]
    for cand in art["dictionary_candidates"]:
        assert cand["provenance"] == "inference", "never promoted above inference"
        assert cand.get("corroborated") is False, f"uncorroborated candidate not marked: {cand}"
        assert cand.get("accepted") is False, f"uncorroborated candidate must not be accepted: {cand}"
        assert cand.get("needs_corroboration") is True, cand


def test_candidates_are_corroborated_when_context_is_supplied(tmp_path):
    # The counterpart: when corroboration context IS supplied to mine_paths, the
    # candidates pass through corroborate_definition and are marked corroborated
    # (accepted iff the data agrees) — so the claim is TRUE when it is made.
    f = tmp_path / "m.sql"
    f.write_text("INSERT INTO dbo.Summary (Total) SELECT SUM(o.Amount) AS Total FROM dbo.Orders o;", encoding="utf-8")
    rows = {"dbo.Summary": [{"Total": 100}, {"Total": 250}, {"Total": 90}]}
    art = sm.mine_paths([f], corroboration_rows=rows)
    totals = [c for c in art["dictionary_candidates"] if c["column"] == "Total"]
    assert totals, art["dictionary_candidates"]
    c = totals[0]
    assert c["corroborated"] is True
    assert c.get("needs_corroboration") is False
    assert c["accepted"] is True  # numeric claim agrees with numeric sampled data
    assert c["provenance"] == "inference"
