"""End-to-end tests for the knowledge server (KS-1, KS-2, KS-7) —
the real entry point over both source adapters against the fixtures.

Drives `server.main(...)` (the MCP registration's program target) with StringIO
stdin/stdout so the ENTRY POINT itself is exercised — a launch-dead main would be
caught here. Also proves KS-7: a `bg_runtime.Scheduler` tick re-indexes a changed
sidecar so a warm server reflects it without a restart.
"""
from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX = REPO_ROOT / "tests" / "fixtures" / "knowledge_server"

srv = load_module(REPO_ROOT / "services" / "knowledge_server" / "server.py", "ct6_ks_server_e2e")


def _drive_main(argv, requests) -> dict:
    stdin = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
    stdout = io.StringIO()
    rc = srv.main(argv, stdin=stdin, stdout=stdout)
    assert rc == 0
    responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    return {r.get("id"): r for r in responses}


def test_entry_point_serves_both_sources_end_to_end() -> None:
    argv = [
        "--dictionary", str(FIX / "data-dictionary.json"),
        "--annotations", str(FIX / "data-annotations"),
        "--graph", str(FIX / "lineage-graph.json"),
        "--map", str(FIX / "ENDPOINT_TRACE_MAP.md"),
    ]
    by_id = _drive_main(argv, [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "search_dictionary", "arguments": {"query": "email"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "find_call_paths",
                    "arguments": {"start": "endpoint://GET/api/orders"}}},
    ])
    # both sources mounted -> all 8 tools
    tool_names = {t["name"] for t in by_id[2]["result"]["tools"]}
    assert tool_names == {
        "search_dictionary", "get_table_details", "find_relations", "get_dictionary_status",
        "search_map", "get_route_details", "find_call_paths", "get_map_status",
    }
    # a real dictionary tools/call round-trip, carrying a freshness verdict
    dict_call = by_id[3]["result"]["structuredContent"]
    assert dict_call["freshness"]["verdict"] in {"current", "stale", "unknowable"}
    assert any(r["doc_id"] == "customers" for r in dict_call["results"])
    # a real map tools/call round-trip reaches the asset over the real edges
    map_call = by_id[4]["result"]["structuredContent"]
    assert "asset://pg/public/orders" in map_call["reachable_nodes"]


def test_reindex_on_sidecar_change_via_scheduler_tick(tmp_path: Path) -> None:
    work = tmp_path / "ks"
    shutil.copytree(FIX, work)
    dpath = work / "data-dictionary.json"

    ds_mod = load_module(REPO_ROOT / "services" / "knowledge_server" / "dictionary_source.py",
                         "ct6_ks_ds_reindex")
    src = ds_mod.DictionarySource(str(dpath), changed_paths_provider=lambda stamp: [])

    # a term that is absent before the change
    before = src.tools_by_name()["search_dictionary"].handler({"query": "widgets"})
    assert before["count"] == 0

    # rewrite the sidecar to add a 'widgets' table
    data = json.loads(dpath.read_text(encoding="utf-8"))
    data["tables"]["widgets"] = {
        "grain": {"grain": "one row per widget", "inferred_key": ["sku"], "declared_pk": ["sku"],
                  "uniqueness_ratios": {"sku": 1.0}, "sampled_rows": 5, "small_sample_key": False},
        "fields": [{"field": "sku", "type": "string", "definition": "widget stock keeping unit",
                    "provenance": "live-data", "confidence": "high",
                    "inference_evidence": [], "corroboration": None}],
    }
    dpath.write_text(json.dumps(data), encoding="utf-8")

    # a scheduler tick re-indexes the changed sidecar (KS-7)
    scheduler = srv.build_scheduler([src], interval_seconds=60)
    ran = scheduler.run_due(now=1000)
    assert ran and all(v == "ok" for v in ran.values())

    after = src.tools_by_name()["search_dictionary"].handler({"query": "widgets"})
    assert after["count"] >= 1
    assert any(r["doc_id"] == "widgets" for r in after["results"])


def test_refresh_is_noop_when_hash_unchanged(tmp_path: Path) -> None:
    work = tmp_path / "ks"
    shutil.copytree(FIX, work)
    ds_mod = load_module(REPO_ROOT / "services" / "knowledge_server" / "dictionary_source.py",
                         "ct6_ks_ds_noop")
    src = ds_mod.DictionarySource(str(work / "data-dictionary.json"),
                                  changed_paths_provider=lambda stamp: [])
    assert src.refresh() is False  # nothing changed -> no re-index
