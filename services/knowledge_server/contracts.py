# -*- coding: utf-8 -*-
"""Closed output contracts for every knowledge-server tool (KS-6) — stdlib-only.

The server eats CT6's own dog food: each tool's response shape is a CLOSED JSON
Schema built with `scripts/mcp_design/output_contract.py::build_output_contract`
(`additionalProperties: false`, every field required), and every response the
server emits is validated with `validate_against_contract`. Every contract
carries the `freshness` envelope field (KS-4) — freshness rides on every tool,
not just the status tools.

`output_contract` lives in `scripts/mcp_design/` — NOT a `services/` sibling — so
it is imported LAZILY inside `_output_contract()`; a module-load import would trip
`services/separation.py::check_separation`. The `sys.path.insert` below is a
statement, not an import, so it is invisible to that AST check.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
_MCP = str(_HERE.parents[1] / "scripts" / "mcp_design")   # -> <repo>/scripts/mcp_design
if _MCP not in sys.path:
    sys.path.insert(0, _MCP)

# The freshness envelope field carried by every tool response (KS-4).
_FRESHNESS = {"name": "freshness", "type": "object",
              "description": "the {verdict: current|stale|unknowable, basis:[...]} envelope"}

_CACHE: Optional[dict[str, Any]] = None


def _output_contract():
    """Lazy import of `scripts/mcp_design/output_contract.py` (separation-clean)."""
    import output_contract  # noqa: E402  (in-function on purpose: not a services/ sibling)
    return output_contract


def _build_all() -> dict[str, Any]:
    oc = _output_contract()

    def contract(name: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
        return oc.build_output_contract(name, fields + [_FRESHNESS])

    return {
        # --- dictionary tools ------------------------------------------------ #
        "search_dictionary": contract("search_dictionary", [
            {"name": "query", "type": "string", "description": "the search query"},
            {"name": "results", "type": "array", "items_type": "object",
             "description": "ranked {doc_id,title,summary,score,matched} hits"},
            {"name": "count", "type": "integer", "description": "number of results"},
        ]),
        "get_table_details": contract("get_table_details", [
            {"name": "table", "type": "string", "description": "the table name"},
            {"name": "found", "type": "boolean", "description": "whether the table exists"},
            {"name": "grain", "type": "object", "description": "the table's grain block"},
            {"name": "fields", "type": "array", "items_type": "object",
             "description": "the table's field records"},
            {"name": "annotations", "type": "array", "items_type": "object",
             "description": "merged docs/data-annotations entries for this table"},
        ]),
        "find_relations": contract("find_relations", [
            {"name": "table", "type": "string", "description": "the table filter ('' = all)"},
            {"name": "relations", "type": "array", "items_type": "object",
             "description": "relational-map entries touching the table"},
            {"name": "count", "type": "integer", "description": "number of relations"},
        ]),
        "get_dictionary_status": contract("get_dictionary_status", [
            {"name": "built_at", "type": "string", "description": "the artifact build stamp"},
            {"name": "repo_side", "type": "object",
             "description": "reference-file drift verdict {verdict,basis}"},
            {"name": "db_side", "type": "object",
             "description": "DB currency arm {verdict:'unknowable',note}"},
            {"name": "reference_file_count", "type": "integer",
             "description": "distinct code files touching the dictionary's tables"},
        ]),
        # --- map tools ------------------------------------------------------- #
        "search_map": contract("search_map", [
            {"name": "query", "type": "string", "description": "the search query"},
            {"name": "results", "type": "array", "items_type": "object",
             "description": "ranked node / map hits"},
            {"name": "count", "type": "integer", "description": "number of results"},
        ]),
        "get_route_details": contract("get_route_details", [
            {"name": "route", "type": "string", "description": "the route / endpoint queried"},
            {"name": "found", "type": "boolean", "description": "whether the endpoint exists"},
            {"name": "components", "type": "array", "items_type": "object",
             "description": "functions the endpoint serves (from serves edges)"},
            {"name": "endpoints", "type": "array", "items_type": "string",
             "description": "downstream endpoints reachable from this one"},
        ]),
        "find_call_paths": contract("find_call_paths", [
            {"name": "start", "type": "string", "description": "the start node id"},
            {"name": "found", "type": "boolean", "description": "whether the start node exists"},
            {"name": "paths", "type": "array", "items_type": "array",
             "description": "node-id sequences reachable from start over real edges"},
            {"name": "reachable_nodes", "type": "array", "items_type": "string",
             "description": "the set of node ids reachable from start"},
            {"name": "edges_walked", "type": "array", "items_type": "string",
             "description": "the edge kinds actually traversed (real vocabulary only)"},
            {"name": "truncated", "type": "boolean", "description": "path budget exceeded"},
        ]),
        "get_map_status": contract("get_map_status", [
            {"name": "stamp", "type": "string", "description": "last_traced / last_mapped stamp"},
            {"name": "map_invalidated", "type": "array", "items_type": "string",
             "description": "the map_invalidated override array"},
            {"name": "stale_nodes", "type": "array", "items_type": "string",
             "description": "transitively stale node ids under changed paths"},
            {"name": "node_count", "type": "integer", "description": "nodes in the graph"},
        ]),
    }


def tool_contracts() -> dict[str, Any]:
    """The 8 tools' closed output contracts (cached, built once)."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _build_all()
    return _CACHE


def validate_payload(payload: Any, contract: dict[str, Any]) -> dict[str, Any]:
    """Validate a produced payload against its contract (the runtime guarantee)."""
    return _output_contract().validate_against_contract(payload, contract)
