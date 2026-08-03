"""Tests for MapSource (KS-2, KS-3, KS-4, KS-5, KS-6) — services/knowledge_server/map_source.py.

Serves search_map / get_route_details / find_call_paths / get_map_status over a
lineage-graph.json + *_MAP.md frontmatter fixture. find_call_paths generalizes
deng's find_join_paths over the real edge vocabulary (calls/reads/writes/modifies/
serves/originates/serves_route); it never invents an edge. get_map_status computes
change-driven staleness via transitive_stale_nodes.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX = REPO_ROOT / "tests" / "fixtures" / "knowledge_server"

ms_mod = load_module(REPO_ROOT / "services" / "knowledge_server" / "map_source.py",
                     "ct6_ks_map_source")

ENDPOINT = "endpoint://GET/api/orders"
LIST_ORDERS = "func://shop/src/services/orders.py#list_orders"
REPO_FETCH = "func://shop/src/repo/order_repo.py#OrderRepo.fetch"
ASSET = "asset://pg/public/orders"


def _source(*, changed=lambda stamp: []):
    return ms_mod.MapSource(str(FIX / "lineage-graph.json"),
                            map_files=[str(FIX / "ENDPOINT_TRACE_MAP.md")],
                            changed_paths_provider=changed)


def _tools(src) -> dict:
    return {t.name: t for t in src.tools()}


def _call(src, name, **args) -> dict:
    return _tools(src)[name].handler(args)


def test_registers_the_four_map_tools() -> None:
    assert set(_tools(_source())) == {"search_map", "get_route_details",
                                      "find_call_paths", "get_map_status"}


# --------------------------------------------------------------------------- #
# KS-5 — search composes LibraryIndex over the node inventory
# --------------------------------------------------------------------------- #

def test_search_map_composes_library_index() -> None:
    src = _source()
    assert type(src.index).__name__ == "LibraryIndex"
    assert type(src.index).__module__ == "library_index"
    out = _call(src, "search_map", query="OrderRepo")
    ids = [r["doc_id"] for r in out["results"]]
    assert REPO_FETCH in ids


# --------------------------------------------------------------------------- #
# KS-3 — find_call_paths walks the REAL edge vocabulary; invented edges impossible
# --------------------------------------------------------------------------- #

def test_find_call_paths_returns_reachable_path_over_real_edges() -> None:
    out = _call(_source(), "find_call_paths", start=ENDPOINT)
    assert out["found"] is True
    # the asset is reached via serves -> calls -> reads (a non-reachability edge),
    # proving the full vocabulary is walked, not just calls/serves
    assert ASSET in out["reachable_nodes"]
    assert {"serves", "calls", "reads"} <= set(out["edges_walked"])
    assert any(p[0] == ENDPOINT and p[-1] == ASSET for p in out["paths"])


def test_find_call_paths_invents_no_edges() -> None:
    # every consecutive hop in every returned path MUST be a real edge in the graph
    graph = json.loads((FIX / "lineage-graph.json").read_text(encoding="utf-8"))
    real = {(e["src"], e["dst"]) for e in graph["edges"]}
    out = _call(_source(), "find_call_paths", start=ENDPOINT)
    for path in out["paths"]:
        for a, b in zip(path, path[1:]):
            assert (a, b) in real, f"invented edge {a} -> {b}"


def test_find_call_paths_filters_to_the_edge_vocabulary(tmp_path: Path) -> None:
    # an edge whose kind is outside the lineage vocabulary is NOT traversed
    poisoned = {
        "schema_version": 1,
        "nodes": [
            {"id": "func://a#a", "kind": "function", "path": "a.py", "name": "a"},
            {"id": "func://b#b", "kind": "function", "path": "b.py", "name": "b"},
            {"id": "func://z#z", "kind": "function", "path": "z.py", "name": "z"},
        ],
        "edges": [
            {"src": "func://a#a", "dst": "func://b#b", "kind": "calls"},
            {"src": "func://a#a", "dst": "func://z#z", "kind": "teleports"},  # not real vocab
        ],
    }
    gpath = tmp_path / "lineage-graph.json"
    gpath.write_text(json.dumps(poisoned), encoding="utf-8")
    src = ms_mod.MapSource(str(gpath), map_files=[], changed_paths_provider=lambda s: [])
    out = _call(src, "find_call_paths", start="func://a#a")
    assert "func://b#b" in out["reachable_nodes"]      # the real 'calls' edge is walked
    assert "func://z#z" not in out["reachable_nodes"]  # the invented 'teleports' edge is not
    assert "teleports" not in out["edges_walked"]


def test_find_call_paths_unknown_start_is_honest() -> None:
    out = _call(_source(), "find_call_paths", start="func://does/not#exist")
    assert out["found"] is False and out["reachable_nodes"] == []


# --------------------------------------------------------------------------- #
# KS-2 — route details from the endpoint's served functions
# --------------------------------------------------------------------------- #

def test_get_route_details_from_endpoint_node() -> None:
    out = _call(_source(), "get_route_details", route="GET /api/orders")
    assert out["found"] is True
    served = {c["id"] for c in out["components"]}
    assert LIST_ORDERS in served  # the endpoint serves list_orders


# --------------------------------------------------------------------------- #
# KS-4 — change-driven map freshness (transitive_stale_nodes)
# --------------------------------------------------------------------------- #

def test_map_status_stale_when_subtree_changed() -> None:
    src = _source(changed=lambda stamp: ["src/repo/order_repo.py"])
    out = _call(src, "get_map_status")
    assert out["freshness"]["verdict"] == "stale"
    assert REPO_FETCH in out["stale_nodes"]
    assert ENDPOINT in out["stale_nodes"]  # transitive: the ancestor is stale too


def test_map_status_current_when_nothing_changed() -> None:
    out = _call(_source(changed=lambda stamp: []), "get_map_status")
    assert out["freshness"]["verdict"] == "current"
    assert out["stale_nodes"] == []
    assert out["stamp"] == "2026-08-01T10:30:00Z"  # from the map frontmatter


def test_map_status_unknowable_without_git() -> None:
    out = _call(_source(changed=lambda stamp: None), "get_map_status")
    assert out["freshness"]["verdict"] == "unknowable"


def test_find_call_paths_freshness_is_subtree_scoped() -> None:
    # changing the endpoint's own file leaves a query STARTING at list_orders current
    src = _source(changed=lambda stamp: ["src/api/orders_route.py"])
    out = _call(src, "find_call_paths", start=LIST_ORDERS)
    assert out["freshness"]["verdict"] == "current"


def test_every_map_response_carries_freshness() -> None:
    src = _source()
    for name, args in (("search_map", {"query": "orders"}),
                       ("get_route_details", {"route": "GET /api/orders"}),
                       ("find_call_paths", {"start": ENDPOINT}),
                       ("get_map_status", {})):
        out = _call(src, name, **args)
        assert out["freshness"]["verdict"] in {"current", "stale", "unknowable"}


# --------------------------------------------------------------------------- #
# KS-6 — responses validate against contracts
# --------------------------------------------------------------------------- #

def test_map_responses_validate_against_contracts() -> None:
    co = load_module(REPO_ROOT / "services" / "knowledge_server" / "contracts.py", "ct6_ks_co_map")
    contracts = co.tool_contracts()
    src = _source()
    for name, args in (("search_map", {"query": "orders"}),
                       ("get_route_details", {"route": "GET /api/orders"}),
                       ("find_call_paths", {"start": ENDPOINT}),
                       ("get_map_status", {})):
        payload = _call(src, name, **args)
        result = co.validate_payload(payload, contracts[name])
        assert result["valid"] is True, f"{name}: {result['errors']}"


# --------------------------------------------------------------------------- #
# KS-2 — read-only
# --------------------------------------------------------------------------- #

def test_map_adapter_is_read_only(tmp_path: Path) -> None:
    work = tmp_path / "ks"
    shutil.copytree(FIX, work)
    gpath = work / "lineage-graph.json"
    mpath = work / "ENDPOINT_TRACE_MAP.md"
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (gpath, mpath)}
    src = ms_mod.MapSource(str(gpath), map_files=[str(mpath)], changed_paths_provider=lambda s: [])
    for name, args in (("search_map", {"query": "orders"}),
                       ("get_route_details", {"route": "GET /api/orders"}),
                       ("find_call_paths", {"start": ENDPOINT}),
                       ("get_map_status", {})):
        _call(src, name, **args)
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (gpath, mpath)}
    assert before == after
