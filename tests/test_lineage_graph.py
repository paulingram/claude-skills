"""Unit tests for the CDLG core — ``hooks/lineage_graph.py`` (lineage roadmap P1).

The deterministic heart of the lineage upgrade. These tests pin:

* the graph validator (happy path + each distinct error class);
* the ``func://`` / ``asset://`` ID make/parse round-trips, incl. the optional
  disambiguator and the asset shape;
* whitespace-invariant ``content_fingerprint``;
* the **rename-stability fallback** ``stable_func_key`` (rename keeps the key;
  a body change alters it) — the REQ-MEM-02 join-key requirement;
* witness reconciliation recall/hallucination math (REQ-DOC-06) on a hand-built
  graph + witness, including the empty-witness and perfect-match cases;
* ``witness_gate`` pass/fail at thresholds;
* transitive freshness (REQ-DOC-04) — a deep callee change marks the ancestor
  stale; an unrelated change does not;
* the cost-ceiling ``truncate_to_budget`` truncation marker (REQ-DOC-08).

Loaded via importlib + ``plugin_root`` (``hooks`` is not an installed package),
matching ``tests/test_vao_tools.py``.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from tests.helpers.module_loader import load_module


@pytest.fixture(scope="module")
def lg(plugin_root: Path):
    mod = load_module(plugin_root / "hooks" / "lineage_graph.py", "lineage_graph")
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_graph(lg):
    """A small, fully-valid graph reused across several tests."""
    f1 = lg.make_func_id("svc", "api/users.py", "list_users")
    f2 = lg.make_func_id("svc", "db/users.py", "query_users")
    ep = "endpoint://svc/GET /api/users"
    asset = lg.make_asset_id("pg", "public", "users")
    return {
        "schema_version": 1,
        "nodes": [
            {"id": ep, "kind": "endpoint", "name": "GET /api/users"},
            {"id": f1, "kind": "function", "path": "api/users.py", "name": "list_users"},
            {"id": f2, "kind": "function", "path": "db/users.py", "name": "query_users"},
            {"id": asset, "kind": "data_asset", "name": "users"},
        ],
        "edges": [
            {"src": ep, "dst": f1, "kind": "serves", "executed": True},
            {"src": f1, "dst": f2, "kind": "calls", "executed": True},
            {"src": f2, "dst": asset, "kind": "reads"},
        ],
    }, f1, f2, ep, asset


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------


def test_schema_constants(lg):
    assert lg.SCHEMA_VERSION == 1
    assert lg.NODE_KINDS == frozenset({"function", "endpoint", "data_asset"})
    assert lg.EDGE_KINDS == frozenset(
        {"calls", "reads", "writes", "modifies", "serves", "originates", "serves_route"}
    )
    assert "calls" in lg.EXECUTION_ASSERTING_EDGE_KINDS
    assert "serves" in lg.EXECUTION_ASSERTING_EDGE_KINDS
    assert "serves_route" in lg.EXECUTION_ASSERTING_EDGE_KINDS
    # data edges do NOT assert execution by default
    assert "reads" not in lg.EXECUTION_ASSERTING_EDGE_KINDS
    assert isinstance(lg.MERMAID_MAX_NODES, int) and lg.MERMAID_MAX_NODES > 0
    assert isinstance(lg.MERMAID_MAX_DEPTH, int) and lg.MERMAID_MAX_DEPTH > 0


# ---------------------------------------------------------------------------
# validate_lineage_graph — happy path + each error class
# ---------------------------------------------------------------------------


def test_validate_happy_path(lg):
    graph, *_ = _valid_graph(lg)
    assert lg.validate_lineage_graph(graph) == []


def test_validate_non_dict_input(lg):
    errs = lg.validate_lineage_graph(["not", "a", "dict"])
    assert errs and "must be a dict" in errs[0]
    # also robust to None / scalar
    assert lg.validate_lineage_graph(None)
    assert lg.validate_lineage_graph(42)


def test_validate_missing_top_level_keys(lg):
    errs = lg.validate_lineage_graph({})
    joined = " ".join(errs)
    assert "schema_version" in joined
    assert "nodes" in joined
    assert "edges" in joined


def test_validate_wrong_schema_version(lg):
    graph, *_ = _valid_graph(lg)
    graph["schema_version"] = 2
    errs = lg.validate_lineage_graph(graph)
    assert any("schema_version" in e for e in errs)


def test_validate_nodes_not_a_list(lg):
    errs = lg.validate_lineage_graph(
        {"schema_version": 1, "nodes": {"id": "x"}, "edges": []}
    )
    assert any("nodes must be a list" in e for e in errs)


def test_validate_node_missing_id(lg):
    graph = {
        "schema_version": 1,
        "nodes": [{"kind": "function", "path": "a.py"}],
        "edges": [],
    }
    errs = lg.validate_lineage_graph(graph)
    assert any("missing a non-empty string 'id'" in e for e in errs)


def test_validate_node_invalid_kind(lg):
    graph = {
        "schema_version": 1,
        "nodes": [{"id": "func://a/b#c", "kind": "widget"}],
        "edges": [],
    }
    errs = lg.validate_lineage_graph(graph)
    assert any("invalid kind" in e for e in errs)


def test_validate_duplicate_node_ids(lg):
    nid = "func://svc/a.py#f"
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": nid, "kind": "function"},
            {"id": nid, "kind": "function"},
        ],
        "edges": [],
    }
    errs = lg.validate_lineage_graph(graph)
    assert any("duplicate node id" in e for e in errs)


def test_validate_edge_invalid_kind(lg):
    nid = "func://svc/a.py#f"
    graph = {
        "schema_version": 1,
        "nodes": [{"id": nid, "kind": "function"}],
        "edges": [{"src": nid, "dst": nid, "kind": "frobnicates"}],
    }
    errs = lg.validate_lineage_graph(graph)
    assert any("invalid kind" in e for e in errs)


def test_validate_edge_dangling_src_dst(lg):
    nid = "func://svc/a.py#f"
    graph = {
        "schema_version": 1,
        "nodes": [{"id": nid, "kind": "function"}],
        "edges": [{"src": "func://svc/ghost.py#g", "dst": nid, "kind": "calls"}],
    }
    errs = lg.validate_lineage_graph(graph)
    assert any("is not a declared node id" in e for e in errs)


def test_validate_serves_route_requires_match_basis(lg):
    fe = "func://web/App.tsx#fetchUsers"
    ep = "endpoint://svc/GET /api/users"
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": fe, "kind": "function"},
            {"id": ep, "kind": "endpoint"},
        ],
        # serves_route WITHOUT a match_basis -> error
        "edges": [{"src": fe, "dst": ep, "kind": "serves_route", "confidence": 0.8}],
    }
    errs = lg.validate_lineage_graph(graph)
    assert any("match_basis" in e for e in errs)
    # adding a match_basis fixes it
    graph["edges"][0]["match_basis"] = "route-pattern:/api/users"
    assert lg.validate_lineage_graph(graph) == []


def test_validate_edge_not_a_dict(lg):
    nid = "func://svc/a.py#f"
    graph = {
        "schema_version": 1,
        "nodes": [{"id": nid, "kind": "function"}],
        "edges": ["not-a-dict"],
    }
    errs = lg.validate_lineage_graph(graph)
    assert any("edge[0] must be a dict" in e for e in errs)


# ---------------------------------------------------------------------------
# ID nomenclature — make/parse round-trips (REQ-MEM-02)
# ---------------------------------------------------------------------------


def test_make_func_id_shape(lg):
    fid = lg.make_func_id("svc", "api/users.py", "UserService.list")
    assert fid == "func://svc/api/users.py#UserService.list"


def test_func_id_round_trip_no_disambiguator(lg):
    parts = {
        "codebase": "svc",
        "path": "api/users.py",
        "qualified_name": "UserService.list",
        "disambiguator": None,
    }
    fid = lg.make_func_id(
        parts["codebase"], parts["path"], parts["qualified_name"], parts["disambiguator"]
    )
    assert lg.parse_func_id(fid) == parts


def test_func_id_round_trip_with_disambiguator(lg):
    parts = {
        "codebase": "svc",
        "path": "handlers.py",
        "qualified_name": "handle",
        "disambiguator": "overload2",
    }
    fid = lg.make_func_id(
        parts["codebase"], parts["path"], parts["qualified_name"], parts["disambiguator"]
    )
    assert fid.endswith("#handle~overload2")
    assert lg.parse_func_id(fid) == parts


def test_func_id_path_with_slashes_round_trips(lg):
    fid = lg.make_func_id("svc", "a/b/c/deep.py", "f")
    parsed = lg.parse_func_id(fid)
    assert parsed["path"] == "a/b/c/deep.py"
    assert parsed["qualified_name"] == "f"


def test_parse_func_id_rejects_non_func(lg):
    assert lg.parse_func_id("asset://pg/public/users") is None
    assert lg.parse_func_id("not an id") is None
    assert lg.parse_func_id(None) is None
    assert lg.parse_func_id(123) is None


def test_make_asset_id_shape_and_round_trip(lg):
    aid = lg.make_asset_id("pg", "public", "users")
    assert aid == "asset://pg/public/users"
    assert lg.parse_asset_id(aid) == {
        "store": "pg",
        "schema": "public",
        "table": "users",
    }


def test_parse_asset_id_rejects_non_asset(lg):
    assert lg.parse_asset_id("func://svc/a.py#f") is None
    assert lg.parse_asset_id("asset://only/two") is None
    assert lg.parse_asset_id(None) is None


# ---------------------------------------------------------------------------
# content_fingerprint — whitespace invariance
# ---------------------------------------------------------------------------


def test_content_fingerprint_is_16_hex(lg):
    fp = lg.content_fingerprint("def f():\n    return 1\n")
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


def test_content_fingerprint_whitespace_invariant(lg):
    a = "def f():\n    return 1\n"
    b = "def f():\n        return 1   \n\n\n"  # extra indent, trailing ws, blank lines
    c = "   def f():\n\treturn 1\n"
    assert lg.content_fingerprint(a) == lg.content_fingerprint(b) == lg.content_fingerprint(c)


def test_content_fingerprint_token_change_differs(lg):
    a = "def f():\n    return 1\n"
    b = "def f():\n    return 2\n"
    assert lg.content_fingerprint(a) != lg.content_fingerprint(b)


# ---------------------------------------------------------------------------
# stable_func_key — the rename-stability fallback (REQ-MEM-02)
# ---------------------------------------------------------------------------


def test_stable_func_key_prefix(lg):
    key = lg.stable_func_key("f", "def f():\n    return 1\n")
    assert key.startswith("fp:")
    assert key == "fp:" + lg.content_fingerprint("def f():\n    return 1\n")


def test_stable_func_key_survives_rename(lg):
    """A function renamed but body-unchanged keeps the SAME stable key.

    ``stable_func_key`` is body-only by design — it fingerprints the operative
    body, not the name — which is exactly what makes the join key survive a
    rename. Callers pass the body span (the def-line identifier is not part of
    the key).
    """
    body = "    return x + 1\n"
    before = lg.stable_func_key("f", body)
    after = lg.stable_func_key("renamed_f", body)
    assert before == after, "rename with unchanged body must keep the same key"
    # The key ignores the qualified_name entirely (documented body-only contract).
    assert lg.stable_func_key("totally_different_name", body) == before


def test_stable_func_key_body_change_alters_key(lg):
    """A body change (even keeping the name) yields a DIFFERENT stable key."""
    before = lg.stable_func_key("f", "def f():\n    return 1\n")
    after = lg.stable_func_key("f", "def f():\n    return 99\n")
    assert before != after


def test_stable_func_key_rename_and_move_round_trip(lg):
    """The §REQ-MEM-02 'rename + a move' demonstration.

    Move (path change) + rename (name change), body unchanged: the func:// id
    changes (path + name are in the id), but the stable_func_key — the fallback
    join key — is invariant, so history follows the function.
    """
    body = "    rows = db.query('SELECT * FROM users')\n    return rows\n"
    id_before = lg.make_func_id("svc", "api/users.py", "list_users")
    id_after = lg.make_func_id("svc", "api/v2/people.py", "list_people")
    assert id_before != id_after  # the id moved
    assert lg.stable_func_key("list_users", body) == lg.stable_func_key(
        "list_people", body
    )  # but the join key is stable


# ---------------------------------------------------------------------------
# Witness reconciliation (REQ-DOC-06)
# ---------------------------------------------------------------------------


def test_reconcile_perfect_match(lg):
    graph, f1, f2, ep, asset = _valid_graph(lg)
    # graph executed edges: (ep,f1) serves + (f1,f2) calls  (reads not asserting)
    witness = [(ep, f1), (f1, f2)]
    rec = lg.reconcile_with_witness(graph, witness)
    assert rec["edge_recall"] == 1.0
    assert rec["hallucination_rate"] == 0.0
    assert rec["missing_edges"] == []
    assert rec["hallucinated_edges"] == []
    assert rec["witnessed_count"] == 2
    assert rec["graph_executed_count"] == 2


def test_reconcile_partial_recall(lg):
    graph, f1, f2, ep, asset = _valid_graph(lg)
    # witness saw an extra edge the graph is missing -> recall drops
    extra = (f2, "func://svc/db/users.py#open_conn")
    witness = [(ep, f1), (f1, f2), extra]
    rec = lg.reconcile_with_witness(graph, witness)
    assert rec["edge_recall"] == pytest.approx(2 / 3)
    assert list(rec["missing_edges"]) == [extra]
    # graph claimed nothing the witness didn't see
    assert rec["hallucination_rate"] == 0.0


def test_reconcile_hallucination(lg):
    graph, f1, f2, ep, asset = _valid_graph(lg)
    # add a claimed-executed edge the witness never saw
    ghost = "func://svc/api/users.py#unused_helper"
    graph["nodes"].append({"id": ghost, "kind": "function", "path": "api/users.py"})
    graph["edges"].append({"src": f1, "dst": ghost, "kind": "calls", "executed": True})
    witness = [(ep, f1), (f1, f2)]
    rec = lg.reconcile_with_witness(graph, witness)
    # 3 graph-executed edges, 1 hallucinated
    assert rec["graph_executed_count"] == 3
    assert rec["hallucination_rate"] == pytest.approx(1 / 3)
    assert (f1, ghost) in rec["hallucinated_edges"]
    # all witnessed edges present -> recall 1.0
    assert rec["edge_recall"] == 1.0


def test_reconcile_empty_witness(lg):
    graph, *_ = _valid_graph(lg)
    rec = lg.reconcile_with_witness(graph, [])
    # nothing to miss -> recall 1.0; every claimed edge is unverifiable -> 1.0 hallucination
    assert rec["edge_recall"] == 1.0
    assert rec["witnessed_count"] == 0
    assert rec["hallucination_rate"] == 1.0  # 2 graph-executed, 0 witnessed


def test_reconcile_empty_graph_executed(lg):
    # graph with only data edges (none assert execution) + empty witness
    asset = lg.make_asset_id("pg", "public", "users")
    f = lg.make_func_id("svc", "db.py", "q")
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": f, "kind": "function", "path": "db.py"},
            {"id": asset, "kind": "data_asset"},
        ],
        "edges": [{"src": f, "dst": asset, "kind": "reads"}],
    }
    rec = lg.reconcile_with_witness(graph, [])
    assert rec["graph_executed_count"] == 0
    assert rec["hallucination_rate"] == 0.0  # nothing claimed -> nothing hallucinated
    assert rec["edge_recall"] == 1.0


def test_reconcile_executed_false_excluded(lg):
    graph, f1, f2, ep, asset = _valid_graph(lg)
    # explicitly mark the calls edge NOT executed -> drops out of graph_executed
    for e in graph["edges"]:
        if e["kind"] == "calls":
            e["executed"] = False
    rec = lg.reconcile_with_witness(graph, [(ep, f1)])
    assert rec["graph_executed_count"] == 1  # only the serves edge
    assert rec["edge_recall"] == 1.0


def test_reconcile_serves_route_counts_without_explicit_flag(lg):
    fe = "func://web/App.tsx#fetchUsers"
    ep = "endpoint://svc/GET /api/users"
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": fe, "kind": "function", "path": "App.tsx"},
            {"id": ep, "kind": "endpoint"},
        ],
        "edges": [
            {"src": fe, "dst": ep, "kind": "serves_route", "match_basis": "route:/api/users"}
        ],
    }
    rec = lg.reconcile_with_witness(graph, [(fe, ep)])
    assert rec["graph_executed_count"] == 1  # serves_route asserts execution
    assert rec["edge_recall"] == 1.0
    assert rec["hallucination_rate"] == 0.0


def test_reconcile_ignores_malformed_witness_entries(lg):
    graph, f1, f2, ep, asset = _valid_graph(lg)
    # only the two well-formed 2-tuples survive; the 1-tuple, the int, and the
    # 3-element list are all rejected by the normalizer.
    witness = [(ep, f1), ("only-one",), (f1, f2), 42, ["a", "b", "c"]]
    rec = lg.reconcile_with_witness(graph, witness)
    assert rec["witnessed_count"] == 2  # (ep,f1) and (f1,f2)


# ---------------------------------------------------------------------------
# witness_gate
# ---------------------------------------------------------------------------


def test_witness_gate_passes_at_threshold(lg):
    rec = {"edge_recall": 0.95, "hallucination_rate": 0.02}
    gate = lg.witness_gate(rec, recall_threshold=0.9, hallucination_ceiling=0.05)
    assert gate["passes"] is True
    assert gate["reasons"] == []


def test_witness_gate_fails_low_recall(lg):
    rec = {"edge_recall": 0.80, "hallucination_rate": 0.0}
    gate = lg.witness_gate(rec)
    assert gate["passes"] is False
    assert any("recall" in r for r in gate["reasons"])


def test_witness_gate_fails_high_hallucination(lg):
    rec = {"edge_recall": 1.0, "hallucination_rate": 0.20}
    gate = lg.witness_gate(rec)
    assert gate["passes"] is False
    assert any("hallucination" in r for r in gate["reasons"])


def test_witness_gate_boundary_exact_pass(lg):
    # recall exactly at threshold passes (>=); hallucination exactly at ceiling passes (<=)
    rec = {"edge_recall": 0.9, "hallucination_rate": 0.05}
    assert lg.witness_gate(rec)["passes"] is True


def test_witness_gate_custom_thresholds(lg):
    rec = {"edge_recall": 0.7, "hallucination_rate": 0.1}
    assert lg.witness_gate(rec, recall_threshold=0.6, hallucination_ceiling=0.15)["passes"]
    assert not lg.witness_gate(rec, recall_threshold=0.8, hallucination_ceiling=0.15)["passes"]


# ---------------------------------------------------------------------------
# Transitive freshness (REQ-DOC-04)
# ---------------------------------------------------------------------------


def _deep_chain_graph(lg):
    """endpoint -> f1 -> f2 -> f3 (three levels of calls) + an unrelated f9."""
    ep = "endpoint://svc/GET /x"
    f1 = lg.make_func_id("svc", "h.py", "handler")
    f2 = lg.make_func_id("svc", "svc.py", "service")
    f3 = lg.make_func_id("svc", "repo.py", "repo")
    f9 = lg.make_func_id("svc", "unrelated.py", "other")
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": ep, "kind": "endpoint", "path": "routes.py"},
            {"id": f1, "kind": "function", "path": "h.py"},
            {"id": f2, "kind": "function", "path": "svc.py"},
            {"id": f3, "kind": "function", "path": "repo.py"},
            {"id": f9, "kind": "function", "path": "unrelated.py"},
        ],
        "edges": [
            {"src": ep, "dst": f1, "kind": "serves"},
            {"src": f1, "dst": f2, "kind": "calls"},
            {"src": f2, "dst": f3, "kind": "calls"},
        ],
    }
    return graph, ep, f1, f2, f3, f9


def test_deep_callee_change_marks_ancestor_stale(lg):
    graph, ep, f1, f2, f3, f9 = _deep_chain_graph(lg)
    # change the deepest file (repo.py, 3 levels down)
    assert lg.is_node_stale(graph, ep, {"repo.py"}) is True
    assert lg.is_node_stale(graph, f1, {"repo.py"}) is True
    assert lg.is_node_stale(graph, f2, {"repo.py"}) is True
    assert lg.is_node_stale(graph, f3, {"repo.py"}) is True


def test_own_path_change_marks_node_stale(lg):
    graph, ep, f1, f2, f3, f9 = _deep_chain_graph(lg)
    assert lg.is_node_stale(graph, f1, {"h.py"}) is True


def test_unrelated_change_does_not_mark_stale(lg):
    graph, ep, f1, f2, f3, f9 = _deep_chain_graph(lg)
    # unrelated.py is not reachable from ep -> ep not stale
    assert lg.is_node_stale(graph, ep, {"unrelated.py"}) is False
    # f9 itself IS stale (its own path changed)
    assert lg.is_node_stale(graph, f9, {"unrelated.py"}) is True


def test_transitive_stale_nodes_set(lg):
    graph, ep, f1, f2, f3, f9 = _deep_chain_graph(lg)
    stale = lg.transitive_stale_nodes(graph, {"repo.py"})
    # ep, f1, f2, f3 all reach repo.py; f9 does not
    assert stale == {ep, f1, f2, f3}
    assert f9 not in stale


def test_transitive_stale_empty_changed_paths(lg):
    graph, *_ = _deep_chain_graph(lg)
    assert lg.transitive_stale_nodes(graph, set()) == set()
    assert lg.transitive_stale_nodes(graph, None) == set()


def test_is_node_stale_unknown_node(lg):
    graph, *_ = _deep_chain_graph(lg)
    assert lg.is_node_stale(graph, "func://nope/x.py#g", {"h.py"}) is False


def test_reads_edge_does_not_propagate_staleness(lg):
    # a data 'reads' edge is NOT a reachability edge; a changed asset path
    # should not flow back up through it.
    ep = "endpoint://svc/GET /x"
    f1 = lg.make_func_id("svc", "h.py", "handler")
    asset = lg.make_asset_id("pg", "public", "users")
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": ep, "kind": "endpoint", "path": "routes.py"},
            {"id": f1, "kind": "function", "path": "h.py"},
            {"id": asset, "kind": "data_asset", "path": "schema.sql"},
        ],
        "edges": [
            {"src": ep, "dst": f1, "kind": "serves"},
            {"src": f1, "dst": asset, "kind": "reads"},
        ],
    }
    # schema.sql change reaches asset, but 'reads' isn't a reachability edge,
    # so f1 / ep are NOT marked stale by it.
    assert lg.is_node_stale(graph, f1, {"schema.sql"}) is False
    assert lg.is_node_stale(graph, asset, {"schema.sql"}) is True


# ---------------------------------------------------------------------------
# Cost ceiling + truncation (REQ-DOC-08)
# ---------------------------------------------------------------------------


def test_truncate_within_budget_no_flag(lg):
    ids = ["a", "b", "c"]
    kept, truncated = lg.truncate_to_budget(ids, 5)
    assert kept == ids
    assert truncated is False


def test_truncate_exact_budget_no_flag(lg):
    ids = ["a", "b", "c"]
    kept, truncated = lg.truncate_to_budget(ids, 3)
    assert kept == ids
    assert truncated is False


def test_truncate_over_budget_marks_truncation(lg):
    ids = ["a", "b", "c", "d", "e"]
    kept, truncated = lg.truncate_to_budget(ids, 3)
    assert kept == ["a", "b", "c"]
    assert truncated is True


def test_truncate_zero_budget(lg):
    kept, truncated = lg.truncate_to_budget(["a"], 0)
    assert kept == []
    assert truncated is True
    # empty input at zero budget -> no truncation
    kept2, truncated2 = lg.truncate_to_budget([], 0)
    assert kept2 == []
    assert truncated2 is False


def test_truncate_negative_budget_treated_as_zero(lg):
    kept, truncated = lg.truncate_to_budget(["a", "b"], -1)
    assert kept == []
    assert truncated is True


def test_truncate_none_input(lg):
    kept, truncated = lg.truncate_to_budget(None, 5)
    assert kept == []
    assert truncated is False


# ---------------------------------------------------------------------------
# Determinism / purity
# ---------------------------------------------------------------------------


def test_reconcile_is_deterministic(lg):
    graph, f1, f2, ep, asset = _valid_graph(lg)
    witness = [(ep, f1), (f1, f2)]
    a = lg.reconcile_with_witness(graph, witness)
    b = lg.reconcile_with_witness(graph, witness)
    assert a == b


def test_no_import_side_effects(lg):
    # __all__ is the public surface; importing did not raise and the module
    # exposes the documented API.
    for name in (
        "validate_lineage_graph",
        "make_func_id",
        "parse_func_id",
        "make_asset_id",
        "parse_asset_id",
        "content_fingerprint",
        "stable_func_key",
        "reconcile_with_witness",
        "witness_gate",
        "is_node_stale",
        "transitive_stale_nodes",
        "truncate_to_budget",
    ):
        assert hasattr(lg, name), f"missing public API: {name}"
