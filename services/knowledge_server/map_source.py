# -*- coding: utf-8 -*-
"""MapSource (KS-2/3/4/5) — the read-only map / lineage-graph source adapter.

Serves `search_map` / `get_route_details` / `find_call_paths` / `get_map_status`
over a `lineage-graph.json` (the CDLG sidecar per `skills/endpoint-trace-mapping`)
plus the `*_MAP.md` frontmatter (for the `last_traced` / `last_mapped` stamps and
the `map_invalidated` override). `find_call_paths` is the generalization of
deng-toolkit's `find_join_paths` — it walks ONLY the real edge vocabulary
(`calls` / `reads` / `writes` / `modifies` / `serves` / `originates` /
`serves_route`), so an invented edge is impossible: it walks the graph the
pipeline already produces. Freshness is change-driven via
`hooks/lineage_graph.py::transitive_stale_nodes`. Read-only.

Sibling-import bootstrap: the `sys.path.insert` below is a statement, not an
import; `lineage_graph` (in `hooks/`, not a `services/` sibling) is imported
LAZILY so `check_separation` stays green. Package + `services/` siblings import by
bare name at module load.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

_HERE = Path(__file__).resolve().parent
for _rel in (_HERE, _HERE.parent / "librarian", _HERE.parents[1] / "hooks"):
    _s = str(_rel)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import adapter_base  # noqa: E402
import contracts as _contracts  # noqa: E402
import freshness as _freshness  # noqa: E402
import library_index  # noqa: E402

_UNSET = object()
_MAX_DEPTH = 16
_MAX_PATHS = 500


def _parse_frontmatter(text: str) -> dict:
    """Minimal YAML-frontmatter reader for the keys the map source needs
    (`last_traced` / `last_mapped` / `map_invalidated` / `scope_subset`). Supports
    `key: value` and inline `key: [a, b]` lists — the shape the map artifacts use.
    `str.partition(':')` keeps colons in the VALUE (timestamps survive)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            out[key] = [item.strip().strip('"').strip("'")
                        for item in inner.split(",") if item.strip()]
        else:
            out[key] = value.strip('"').strip("'")
    return out


class MapSource(adapter_base.SourceAdapter):
    """A read-only adapter over `lineage-graph.json` + `*_MAP.md` frontmatter."""

    name = "map"

    def __init__(
        self,
        graph_path: str,
        *,
        map_files: Optional[list] = None,
        repo_root: Optional[str] = None,
        changed_paths_provider: Optional[Callable[[Any], Optional[list]]] = None,
    ) -> None:
        self.graph_path = str(graph_path)
        self.map_files = [str(m) for m in (map_files or [])]
        self.index: Optional[library_index.LibraryIndex] = None
        if changed_paths_provider is not None:
            self._changed_paths_provider = changed_paths_provider
        elif repo_root:
            self._changed_paths_provider = (
                lambda stamp: _freshness.git_changed_paths(stamp, repo_root))
        else:
            self._changed_paths_provider = lambda stamp: None
        self._load_and_index()
        self._hash = self._content_hash()

    # -- lazy hooks import ----------------------------------------------------- #

    @staticmethod
    def _lineage_graph():
        import lineage_graph  # noqa: E402  (hooks/ — not a services/ sibling: lazy)
        return lineage_graph

    def _valid_edge_kinds(self) -> set:
        return set(self._lineage_graph().EDGE_KINDS)

    # -- loading + indexing ---------------------------------------------------- #

    def _load_and_index(self) -> None:
        graph = json.loads(Path(self.graph_path).read_text(encoding="utf-8"))
        self.graph = graph
        self.nodes = {n["id"]: n for n in graph.get("nodes", [])
                      if isinstance(n, dict) and n.get("id")}
        self.edges = [e for e in graph.get("edges", []) if isinstance(e, dict)]

        self.stamp: Optional[str] = None
        self.map_invalidated: list = []
        frontmatters: list = []
        for map_file in self.map_files:
            path = Path(map_file)
            fm = _parse_frontmatter(path.read_text(encoding="utf-8")) if path.exists() else {}
            if self.stamp is None:
                self.stamp = fm.get("last_traced") or fm.get("last_mapped")
            invalidated = fm.get("map_invalidated")
            if isinstance(invalidated, list):
                self.map_invalidated += [str(x) for x in invalidated]
            frontmatters.append((path.name, fm))

        if self.index is not None:
            self.index.close()
        index = library_index.LibraryIndex(":memory:")
        for nid, node in self.nodes.items():
            name = node.get("name", "") or nid
            path_val = node.get("path", "") or ""
            kind = node.get("kind", "") or ""
            index.add_document({
                "doc_id": nid, "title": name, "summary": f"{kind} at {path_val}",
                "keywords": [name, path_val, kind] + [p for p in path_val.split("/") if p],
                "concepts": [kind, name] + [p for p in path_val.split("/") if p],
                "source": "lineage-graph",
            })
        for fname, fm in frontmatters:
            index.add_document({
                "doc_id": f"map:{fname}", "title": fname,
                "summary": f"map file {fname}",
                "keywords": [fname] + list(fm.get("scope_subset") or []),
                "concepts": ["map", fname],
                "source": "map-file",
            })
        self.index = index

    def _content_hash(self) -> str:
        digest = hashlib.sha256()
        digest.update(Path(self.graph_path).read_bytes())
        for map_file in self.map_files:
            path = Path(map_file)
            if path.exists():
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def refresh(self) -> bool:
        current = self._content_hash()
        if current == self._hash:
            return False
        self._load_and_index()
        self._hash = current
        return True

    def scheduler_task(self, interval_seconds: int = 300):
        import bg_runtime  # noqa: E402  (services/common sibling — lazy)
        return bg_runtime.ServiceTask(f"knowledge-reindex-{self.name}", interval_seconds, self.refresh)

    # -- graph traversal ------------------------------------------------------- #

    def _adjacency(self) -> dict:
        """src -> sorted [(dst, kind)] over ONLY the real edge vocabulary. An edge
        whose kind is outside the vocabulary is dropped — invented edges cannot be
        walked."""
        valid = self._valid_edge_kinds()
        adj: dict = {}
        for edge in self.edges:
            kind = edge.get("kind")
            if kind not in valid:
                continue
            src, dst = edge.get("src"), edge.get("dst")
            if not src or not dst:
                continue
            adj.setdefault(src, []).append((dst, kind))
        for src in adj:
            adj[src].sort(key=lambda pair: (pair[1], pair[0]))
        return adj

    def _reachable(self, start: str) -> set:
        adj = self._adjacency()
        seen: set = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            for dst, _kind in adj.get(cur, ()):
                if dst not in seen:
                    seen.add(dst)
                    stack.append(dst)
        return seen

    # -- freshness ------------------------------------------------------------- #

    def _map_freshness(self, *, subtree_node_ids=None, changed=_UNSET) -> dict:
        if changed is _UNSET:
            changed = self._changed_paths_provider(self.stamp)
        return _freshness.map_freshness(
            self.graph, changed_paths=changed, stamp=self.stamp,
            map_invalidated=self.map_invalidated, subtree_node_ids=subtree_node_ids)

    # -- tool handlers --------------------------------------------------------- #

    def _search(self, args: dict) -> dict:
        query = str(args.get("query", ""))
        top_k = int(args.get("top_k", 10) or 10)
        results = self.index.conceptual_search(query, top_k=top_k)
        return {"query": query, "results": results, "count": len(results),
                "freshness": self._map_freshness()}

    def _route_details(self, args: dict) -> dict:
        route = str(args.get("route", ""))
        matched_id = None
        for nid, node in self.nodes.items():
            if node.get("kind") != "endpoint":
                continue
            name = node.get("name", "") or ""
            if route in (name, nid) or route in name or route in nid:
                matched_id = nid
                break
        found = matched_id is not None
        components: list = []
        endpoints: list = []
        subtree = None
        if found:
            for edge in self.edges:
                if edge.get("src") == matched_id and edge.get("kind") == "serves":
                    dst = edge.get("dst")
                    components.append(self.nodes.get(dst, {"id": dst}))
            reach = self._reachable(matched_id)
            endpoints = sorted(n for n in reach
                               if self.nodes.get(n, {}).get("kind") == "endpoint")
            subtree = reach | {matched_id}
        return {"route": route, "found": found, "components": components,
                "endpoints": endpoints,
                "freshness": self._map_freshness(subtree_node_ids=subtree)}

    def _find_call_paths(self, args: dict) -> dict:
        start = str(args.get("start", ""))
        found = start in self.nodes
        adj = self._adjacency()
        paths: list = []
        reachable: set = set()
        edges_walked: set = set()
        truncated = [False]

        def dfs(node: str, trail: list, visited: set) -> None:
            if len(paths) >= _MAX_PATHS:
                truncated[0] = True
                return
            extensions = [(dst, kind) for (dst, kind) in adj.get(node, [])
                          if dst not in visited]
            if not extensions or len(trail) >= _MAX_DEPTH:
                if len(trail) > 1:
                    paths.append(list(trail))
                if extensions and len(trail) >= _MAX_DEPTH:
                    truncated[0] = True
                return
            for dst, kind in extensions:
                edges_walked.add(kind)
                reachable.add(dst)
                dfs(dst, trail + [dst], visited | {dst})
                if len(paths) >= _MAX_PATHS:
                    truncated[0] = True
                    break

        dfs(start, [start], {start})
        return {"start": start, "found": found, "paths": paths,
                "reachable_nodes": sorted(reachable),
                "edges_walked": sorted(edges_walked), "truncated": truncated[0],
                "freshness": self._map_freshness(subtree_node_ids=reachable | {start})}

    def _map_status(self, args: dict) -> dict:
        changed = self._changed_paths_provider(self.stamp)
        stale = (sorted(self._lineage_graph().transitive_stale_nodes(self.graph, changed))
                 if changed is not None else [])
        return {"stamp": str(self.stamp or "unknown"),
                "map_invalidated": list(self.map_invalidated),
                "stale_nodes": stale, "node_count": len(self.nodes),
                "freshness": self._map_freshness(changed=changed)}

    def tools(self) -> list:
        contracts = _contracts.tool_contracts()
        return [
            adapter_base.Tool(
                "search_map",
                "Ranked keyword search over the lineage-graph node inventory (composes the Librarian index).",
                {"type": "object", "properties": {"query": {"type": "string"},
                                                  "top_k": {"type": "integer"}},
                 "required": ["query"]},
                self._search, output_contract=contracts["search_map"]),
            adapter_base.Tool(
                "get_route_details",
                "An endpoint's served functions + downstream endpoints from the lineage graph.",
                {"type": "object", "properties": {"route": {"type": "string"}},
                 "required": ["route"]},
                self._route_details, output_contract=contracts["get_route_details"]),
            adapter_base.Tool(
                "find_call_paths",
                "Path queries over the real edge vocabulary (the find_join_paths generalization).",
                {"type": "object", "properties": {"start": {"type": "string"}},
                 "required": ["start"]},
                self._find_call_paths, output_contract=contracts["find_call_paths"]),
            adapter_base.Tool(
                "get_map_status",
                "Change-driven map freshness via transitive_stale_nodes + stamps + map_invalidated.",
                {"type": "object", "properties": {}},
                self._map_status, output_contract=contracts["get_map_status"]),
        ]
