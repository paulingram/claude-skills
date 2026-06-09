#!/usr/bin/env python3
"""Code & Data Lineage Graph (CDLG) core — the deterministic, unit-tested heart
of the lineage roadmap P1 (WS-D / the CDLG foundation).

This module is the *machine* half of the `endpoint-trace-mapping` skill: the
agent does the live, polyglot, LLM-and-LSP-driven extraction at runtime; the
deterministic, testable pieces — the graph schema + validator, the `func://` /
`asset://` identity nomenclature (the load-bearing join key for MemPalace dedup
and graph diffing), runtime-witness reconciliation (the trust gate),
transitive freshness, and the cost-ceiling truncation — all live here so they
can be exercised in isolation by `tests/test_lineage_graph.py`.

Source of truth: `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` §4 (the CDLG) +
REQ-DOC-01 (schema), REQ-DOC-04 (transitive freshness), REQ-DOC-06 (the
runtime-witness trust gate), REQ-DOC-08 (cost ceiling), REQ-MEM-02 (stable
identity nomenclature).

Design constraints
------------------
* **Stdlib-only** (`hashlib` / `json` / `re` / `pathlib` are the permitted set;
  this module uses `hashlib` + `re` only). No third-party imports.
* **No import-time side effects** — importing this module does nothing but
  define names. Every function is pure given its inputs (no global mutable
  state, no I/O, no environment reads).
* **Reuse, don't rebuild:** the runtime execution witness
  (`code-path-witness.json`) ALREADY EXISTS in CT6 (v0.9.31/0.9.32). This module
  *consumes* that witness for grounding (`reconcile_with_witness`); it does NOT
  re-implement execution capture.

The graph shape (schema_version 1)
----------------------------------
::

    {
      "schema_version": 1,
      "nodes": [
        {"id": "func://...", "kind": "function", "path": "...", "name": "..."},
        {"id": "endpoint://...", "kind": "endpoint", ...},
        {"id": "asset://...", "kind": "data_asset", ...}
      ],
      "edges": [
        {"src": "<node id>", "dst": "<node id>", "kind": "calls",
         "executed": true, "match_basis": "...", "confidence": 0.9}
      ]
    }

* Node ``kind`` ∈ {"function", "endpoint", "data_asset"}.
* Edge ``kind`` ∈ {"calls", "reads", "writes", "modifies", "serves",
  "originates", "serves_route"}.
* ``serves_route`` edges (the FE→BE inter-service seam, REQ-DOC-07) MUST carry a
  ``match_basis`` — they are produced by route/contract matching, not call-graph
  traversal, so the basis (and a confidence) is load-bearing provenance.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

#: Valid node kinds (REQ-DOC-01 / §4 nodes).
NODE_KINDS = frozenset({"function", "endpoint", "data_asset"})

#: Valid edge kinds (REQ-DOC-01 / §4 edges).
EDGE_KINDS = frozenset(
    {"calls", "reads", "writes", "modifies", "serves", "originates", "serves_route"}
)

#: The subset of edge kinds that *assert execution* by default when an explicit
#: ``executed`` flag is absent — used by witness reconciliation (REQ-DOC-06).
#: ``calls`` / ``serves`` / ``serves_route`` describe control flow that, in the
#: bug subset, is expected to have fired; ``reads`` / ``writes`` / ``modifies``
#: / ``originates`` describe data relationships that are not directly witnessed
#: as control-flow edges, so they only count as executed when explicitly flagged.
EXECUTION_ASSERTING_EDGE_KINDS = frozenset({"calls", "serves", "serves_route"})

#: Edge kinds that traverse the call/serve tree for transitive-freshness and
#: staleness reachability (REQ-DOC-04). A node is stale if any node reachable
#: via these edges has a changed path.
REACHABILITY_EDGE_KINDS = frozenset({"calls", "serves"})

# ---------------------------------------------------------------------------
# Cost-ceiling constants (REQ-DOC-08)
# ---------------------------------------------------------------------------

#: Hard cap on the number of nodes a single mermaid render may contain. Past
#: this, the tree is depth/size-truncated with an explicit marker rather than
#: silently dropped (REQ-DOC-08 graceful degradation).
MERMAID_MAX_NODES = 60

#: Hard cap on call-tree depth a single mermaid render may show.
MERMAID_MAX_DEPTH = 6


# ---------------------------------------------------------------------------
# Schema + validator (REQ-DOC-01)
# ---------------------------------------------------------------------------


def validate_lineage_graph(graph: Any) -> list[str]:
    """Validate a CDLG document and return a list of human-readable error strings.

    An empty list means the graph is valid. The checks (each contributes a
    distinct error class):

    * top-level shape — ``graph`` is a dict carrying ``schema_version`` (== 1),
      ``nodes`` (list), and ``edges`` (list);
    * every node is a dict with a non-empty string ``id`` and a ``kind`` in
      :data:`NODE_KINDS`;
    * node ids are unique (no duplicates);
    * every edge is a dict with ``src`` / ``dst`` that resolve to declared node
      ids and a ``kind`` in :data:`EDGE_KINDS`;
    * every ``serves_route`` edge carries a non-empty ``match_basis`` (REQ-DOC-07
      — the inter-service seam's provenance is mandatory).

    Defensive against non-dict / malformed input: bad shapes yield error strings
    rather than raising.
    """
    errors: list[str] = []

    if not isinstance(graph, dict):
        return [f"graph must be a dict, got {type(graph).__name__}"]

    # --- top-level keys ----------------------------------------------------
    if "schema_version" not in graph:
        errors.append("missing top-level key: schema_version")
    elif graph["schema_version"] != SCHEMA_VERSION:
        errors.append(
            f"unsupported schema_version: {graph['schema_version']!r} "
            f"(expected {SCHEMA_VERSION})"
        )

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if "nodes" not in graph:
        errors.append("missing top-level key: nodes")
    elif not isinstance(nodes, list):
        errors.append(f"nodes must be a list, got {type(nodes).__name__}")
    if "edges" not in graph:
        errors.append("missing top-level key: edges")
    elif not isinstance(edges, list):
        errors.append(f"edges must be a list, got {type(edges).__name__}")

    # If the containers are unusable, stop here — per-item checks would be noise.
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return errors

    # --- nodes -------------------------------------------------------------
    node_ids: set[str] = set()
    seen_ids: set[str] = set()
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"node[{i}] must be a dict, got {type(node).__name__}")
            continue
        nid = node.get("id")
        if not isinstance(nid, str) or not nid:
            errors.append(f"node[{i}] missing a non-empty string 'id'")
        else:
            if nid in seen_ids:
                errors.append(f"duplicate node id: {nid!r}")
            seen_ids.add(nid)
            node_ids.add(nid)
        kind = node.get("kind")
        if kind not in NODE_KINDS:
            errors.append(
                f"node[{i}] (id={nid!r}) has invalid kind {kind!r}; "
                f"must be one of {sorted(NODE_KINDS)}"
            )

    # --- edges -------------------------------------------------------------
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"edge[{i}] must be a dict, got {type(edge).__name__}")
            continue
        src = edge.get("src")
        dst = edge.get("dst")
        kind = edge.get("kind")
        if kind not in EDGE_KINDS:
            errors.append(
                f"edge[{i}] has invalid kind {kind!r}; "
                f"must be one of {sorted(EDGE_KINDS)}"
            )
        if not isinstance(src, str) or not src:
            errors.append(f"edge[{i}] missing a non-empty string 'src'")
        elif src not in node_ids:
            errors.append(f"edge[{i}] src {src!r} is not a declared node id")
        if not isinstance(dst, str) or not dst:
            errors.append(f"edge[{i}] missing a non-empty string 'dst'")
        elif dst not in node_ids:
            errors.append(f"edge[{i}] dst {dst!r} is not a declared node id")
        if kind == "serves_route":
            basis = edge.get("match_basis")
            if not isinstance(basis, str) or not basis:
                errors.append(
                    f"edge[{i}] (serves_route) missing a non-empty 'match_basis' "
                    f"(the inter-service seam's provenance is mandatory, REQ-DOC-07)"
                )

    return errors


# ---------------------------------------------------------------------------
# ID nomenclature (REQ-MEM-02) — the load-bearing join key
# ---------------------------------------------------------------------------

# A func:// id is  func://<codebase>/<path>#<qualified_name>[~<disambiguator>]
# A asset:// id is asset://<store>/<schema>/<table>
#
# The disambiguator (separated by '~') disambiguates overloads, closures, and
# anonymous functions that would otherwise collide on (codebase, path,
# qualified_name). It is OPTIONAL — omitted for ordinary uniquely-named
# functions.

_FUNC_ID_RE = re.compile(
    r"^func://(?P<codebase>[^/]+)/(?P<path>.+)#(?P<rest>[^#]+)$"
)
_ASSET_ID_RE = re.compile(
    r"^asset://(?P<store>[^/]+)/(?P<schema>[^/]+)/(?P<table>[^/]+)$"
)


def make_func_id(
    codebase: str,
    path: str,
    qualified_name: str,
    disambiguator: Optional[str] = None,
) -> str:
    """Build a canonical ``func://`` id (REQ-MEM-02).

    Shape: ``func://<codebase>/<path>#<qualified_name>`` with an optional
    ``~<disambiguator>`` suffix appended to the qualified-name segment when a
    disambiguator is supplied (overloads, closures, anonymous functions).

    The id is the join key MemPalace dedups on and the graph diffs on, so it is
    constructed deterministically from its parts.

    Round-trip precondition (REQ-MEM-02): ``parse_func_id(make_func_id(**parts))
    == parts`` holds when each component is a normal identifier — i.e.
    ``codebase`` contains no ``/``, and ``qualified_name`` contains no ``#`` or
    ``~``. Those characters are the segment delimiters; a component that embeds
    one is NOT round-trip-safe (the parse splits on the delimiter and silently
    mis-attributes the boundary). In practice codebase slugs and qualified names
    are bare identifiers, so this is sound; callers that might see exotic names
    should slugify the component first. ``path`` may contain ``/`` (expected) but
    must not contain ``#``.
    """
    if disambiguator:
        tail = f"{qualified_name}~{disambiguator}"
    else:
        tail = qualified_name
    return f"func://{codebase}/{path}#{tail}"


def make_asset_id(store: str, schema: str, table: str) -> str:
    """Build a canonical ``asset://`` id: ``asset://<store>/<schema>/<table>``."""
    return f"asset://{store}/{schema}/{table}"


def parse_func_id(s: Any) -> Optional[dict]:
    """Parse a ``func://`` id back into its parts, or ``None`` if it does not match.

    Returns ``{"codebase", "path", "qualified_name", "disambiguator"}`` where
    ``disambiguator`` is ``None`` when absent. Round-trips
    ``parse_func_id(make_func_id(**parts)) == parts`` for normal-identifier
    components — see :func:`make_func_id` for the delimiter-character
    precondition (no ``/`` in codebase, no ``#``/``~`` in qualified_name).
    """
    if not isinstance(s, str):
        return None
    m = _FUNC_ID_RE.match(s)
    if not m:
        return None
    rest = m.group("rest")
    # Split the qualified-name segment on the FIRST '~' so a disambiguator may
    # itself contain '~' (rare, but the parse must be lossless for round-trips).
    if "~" in rest:
        qualified_name, disambiguator = rest.split("~", 1)
    else:
        qualified_name, disambiguator = rest, None
    return {
        "codebase": m.group("codebase"),
        "path": m.group("path"),
        "qualified_name": qualified_name,
        "disambiguator": disambiguator,
    }


def parse_asset_id(s: Any) -> Optional[dict]:
    """Parse an ``asset://`` id into ``{"store", "schema", "table"}`` or ``None``."""
    if not isinstance(s, str):
        return None
    m = _ASSET_ID_RE.match(s)
    if not m:
        return None
    return {
        "store": m.group("store"),
        "schema": m.group("schema"),
        "table": m.group("table"),
    }


def _normalize_source(source: str) -> str:
    """Normalize a function body for fingerprinting: strip per-line leading and
    trailing whitespace and drop blank lines.

    Two bodies that differ ONLY in surrounding whitespace (indentation,
    trailing spaces, blank-line layout) normalize identically — so they
    fingerprint identically. A body whose *tokens* differ normalizes
    differently.
    """
    lines = []
    for raw in source.splitlines():
        stripped = raw.strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def content_fingerprint(source: str) -> str:
    """Whitespace-invariant content fingerprint of a function body.

    Normalizes (per :func:`_normalize_source`) then returns the first 16 hex
    chars of the sha256 of the normalized text. Whitespace-only differences
    fingerprint identically; token differences do not.
    """
    normalized = _normalize_source(source)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def stable_func_key(qualified_name: str, source: str) -> str:
    """A rename-stable join key derived from the function's *body*, not its name.

    Returns ``"fp:<content_fingerprint(source)>"``. This is the **rename-stability
    fallback** (REQ-MEM-02): when a function is renamed but its body is
    unchanged, its content fingerprint — and therefore this key — is UNCHANGED,
    so MemPalace history and graph diffs follow the function across the rename
    instead of orphaning it. Conversely a function whose *body* changes (even
    keeping its name) gets a DIFFERENT key, because the work it does is no longer
    the same.

    ``qualified_name`` is accepted (and documented) so callers pass the full
    identity context, but the key is deliberately body-only: that is precisely
    what makes it survive a rename. (A name-sensitive key would defeat the
    purpose.)
    """
    return f"fp:{content_fingerprint(source)}"


# ---------------------------------------------------------------------------
# Witness reconciliation (REQ-DOC-06) — the trust gate
# ---------------------------------------------------------------------------


def _edge_pair(edge: dict) -> Optional[tuple]:
    """Return the (src, dst) tuple for an edge dict, or None if malformed."""
    src = edge.get("src")
    dst = edge.get("dst")
    if isinstance(src, str) and isinstance(dst, str) and src and dst:
        return (src, dst)
    return None


def _graph_executed_edges(graph: dict) -> set[tuple]:
    """The set of (src, dst) edges the graph CLAIMS executed.

    The rule (documented): an edge claims execution if it carries
    ``executed: true`` explicitly, OR — when it has no explicit ``executed``
    flag — its kind is one of :data:`EXECUTION_ASSERTING_EDGE_KINDS`
    (``calls`` / ``serves`` / ``serves_route``), the control-flow edges that in
    the bug subset are expected to have fired. An edge with ``executed: false``
    explicitly never counts, regardless of kind.
    """
    executed: set[tuple] = set()
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        pair = _edge_pair(edge)
        if pair is None:
            continue
        if "executed" in edge:
            if edge["executed"] is True:
                executed.add(pair)
        elif edge.get("kind") in EXECUTION_ASSERTING_EDGE_KINDS:
            executed.add(pair)
    return executed


def _normalize_witness(witness_executed_edges: Iterable) -> set[tuple]:
    """Coerce the witness's observed edges into a set of (src, dst) tuples.

    Accepts a set/list of 2-tuples/2-lists; ignores malformed entries.
    """
    out: set[tuple] = set()
    if not witness_executed_edges:
        return out
    for item in witness_executed_edges:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            src, dst = item[0], item[1]
            if isinstance(src, str) and isinstance(dst, str):
                out.add((src, dst))
    return out


def reconcile_with_witness(
    graph: dict, witness_executed_edges: Iterable
) -> dict:
    """Reconcile the graph's claimed-executed edges against the runtime witness.

    ``witness_executed_edges`` is the set/list of ``(src, dst)`` edges the
    runtime execution witness (``code-path-witness.json``) observed FIRING during
    replication. We compare it against the graph's claimed-executed edges
    (:func:`_graph_executed_edges`).

    Returns::

        {
          "edge_recall":          float,   # |witnessed ∩ graph| / |witnessed|
          "hallucination_rate":   float,   # |graph − witnessed| / |graph|
          "missing_edges":        [...],   # witnessed but absent from the graph
          "hallucinated_edges":   [...],   # graph-claimed but never witnessed
          "witnessed_count":      int,
          "graph_executed_count": int,
        }

    Edge cases (documented):

    * **Empty witness** — recall is ``1.0`` (nothing to miss); hallucination is
      computed normally (every claimed edge is unverifiable, so if the graph
      claims any executed edges the hallucination rate is ``1.0``).
    * **No graph-claimed edges** — hallucination is ``0.0`` (nothing claimed,
      nothing hallucinated).

    The two list fields are sorted for deterministic output.
    """
    witnessed = _normalize_witness(witness_executed_edges)
    graph_executed = _graph_executed_edges(graph)

    intersection = witnessed & graph_executed
    missing = witnessed - graph_executed
    hallucinated = graph_executed - witnessed

    if witnessed:
        edge_recall = len(intersection) / len(witnessed)
    else:
        edge_recall = 1.0

    if graph_executed:
        hallucination_rate = len(hallucinated) / len(graph_executed)
    else:
        hallucination_rate = 0.0

    return {
        "edge_recall": edge_recall,
        "hallucination_rate": hallucination_rate,
        "missing_edges": sorted(missing),
        "hallucinated_edges": sorted(hallucinated),
        "witnessed_count": len(witnessed),
        "graph_executed_count": len(graph_executed),
    }


def witness_gate(
    reconciliation: dict,
    recall_threshold: float = 0.9,
    hallucination_ceiling: float = 0.05,
) -> dict:
    """The trust gate: decide whether a reconciled subgraph may be consumed.

    Diagnosis MUST NOT consume a subgraph whose ``edge_recall`` is below
    ``recall_threshold`` OR whose ``hallucination_rate`` is above
    ``hallucination_ceiling`` (REQ-DOC-06). A failing gate means re-trace or
    escalate, never "trust it anyway."

    Returns ``{"passes": bool, "reasons": [...]}`` — ``reasons`` is empty on
    pass and enumerates each failed criterion on fail.
    """
    reasons: list[str] = []
    recall = reconciliation.get("edge_recall", 0.0)
    hallucination = reconciliation.get("hallucination_rate", 1.0)

    if recall < recall_threshold:
        reasons.append(
            f"edge recall {recall:.3f} below threshold {recall_threshold:.3f}"
        )
    if hallucination > hallucination_ceiling:
        reasons.append(
            f"hallucination rate {hallucination:.3f} above ceiling "
            f"{hallucination_ceiling:.3f}"
        )

    return {"passes": not reasons, "reasons": reasons}


# ---------------------------------------------------------------------------
# Transitive freshness (REQ-DOC-04)
# ---------------------------------------------------------------------------


def _node_index(graph: dict) -> dict:
    """Map node id -> node dict for the graph's nodes."""
    index: dict = {}
    for node in graph.get("nodes", []):
        if isinstance(node, dict):
            nid = node.get("id")
            if isinstance(nid, str) and nid:
                index[nid] = node
    return index


def _reachability_adjacency(graph: dict) -> dict:
    """Adjacency map (src -> set of dst) over the reachability edge kinds.

    Only ``calls`` / ``serves`` edges (:data:`REACHABILITY_EDGE_KINDS`) form the
    subtree we walk for staleness — an endpoint reaches its functions via
    ``serves`` and functions reach their callees via ``calls``.
    """
    adj: dict = {}
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        if edge.get("kind") not in REACHABILITY_EDGE_KINDS:
            continue
        pair = _edge_pair(edge)
        if pair is None:
            continue
        adj.setdefault(pair[0], set()).add(pair[1])
    return adj


def _changed(node: Optional[dict], changed_paths: Any) -> bool:
    """True if ``node`` carries a ``path`` that is in ``changed_paths``."""
    if not isinstance(node, dict):
        return False
    path = node.get("path")
    return isinstance(path, str) and path in set(changed_paths or [])


def is_node_stale(graph: dict, node_id: str, changed_paths: Any) -> bool:
    """True if ``node_id`` is stale w.r.t. ``changed_paths`` (REQ-DOC-04).

    A node is stale if its OWN ``path`` is in ``changed_paths`` OR any node
    reachable from it (via ``calls`` / ``serves`` edges, walking the subtree) has
    a changed path. A callee-only change three levels down marks the ancestor
    endpoint stale.
    """
    index = _node_index(graph)
    if node_id not in index:
        return False
    changed_set = set(changed_paths or [])
    if not changed_set:
        return False

    adj = _reachability_adjacency(graph)
    # DFS over the subtree rooted at node_id (including the root itself).
    stack = [node_id]
    seen: set[str] = set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if _changed(index.get(cur), changed_set):
            return True
        for nxt in adj.get(cur, ()):  # only reachability edges
            if nxt not in seen:
                stack.append(nxt)
    return False


def transitive_stale_nodes(graph: dict, changed_paths: Any) -> set:
    """The set of node ids that are stale under transitive freshness (REQ-DOC-04).

    A node is included if it is itself on a changed path, or any node reachable
    in its ``calls`` / ``serves`` subtree is. Returns a set of node ids (empty
    when ``changed_paths`` is empty).

    Single reverse-BFS — O(V+E): build the forward reachability adjacency once,
    seed the stale set with every node whose OWN path changed, then walk the
    INVERTED adjacency to mark every ancestor that can reach a changed node.
    (The earlier per-node ``is_node_stale`` loop rebuilt the index + adjacency
    once per node — O(V·(V+E)); this is equivalent but a single pass.)
    """
    index = _node_index(graph)
    changed_set = set(changed_paths or [])
    if not changed_set:
        return set()

    adj = _reachability_adjacency(graph)
    # Invert the forward adjacency: dst -> {srcs that reach it in one hop}.
    reverse: dict = {}
    for src, dsts in adj.items():
        for dst in dsts:
            reverse.setdefault(dst, set()).add(src)

    # Seed: every declared node whose own path is in changed_paths.
    stale: set = {nid for nid, node in index.items() if _changed(node, changed_set)}
    # Walk backwards: anything that reaches a stale node is itself stale. A
    # non-declared intermediate id still propagates staleness to its ancestors
    # but is itself filtered out of the result (matching the per-node contract,
    # which only ever returns declared nodes).
    stack = list(stale)
    while stack:
        cur = stack.pop()
        for prev in reverse.get(cur, ()):
            if prev not in stale:
                stale.add(prev)
                stack.append(prev)
    return {nid for nid in stale if nid in index}


# ---------------------------------------------------------------------------
# Cost ceiling + truncation (REQ-DOC-08)
# ---------------------------------------------------------------------------


def truncate_to_budget(node_ids: Any, max_nodes: int) -> tuple:
    """Truncate a node-id list to ``max_nodes``, MARKING truncation (REQ-DOC-08).

    Returns ``(kept_list, truncated_flag)``. When the input fits within budget
    the flag is ``False`` and the list is returned unchanged (order preserved).
    When it exceeds budget, the first ``max_nodes`` ids are kept and the flag is
    ``True`` — truncated subtrees are *marked*, never silently dropped.

    ``max_nodes`` <= 0 keeps nothing and flags truncation iff the input was
    non-empty.
    """
    items = list(node_ids or [])
    if max_nodes is None or max_nodes < 0:
        max_nodes = 0
    if len(items) <= max_nodes:
        return items, False
    return items[:max_nodes], True


__all__ = [
    # schema constants
    "SCHEMA_VERSION",
    "NODE_KINDS",
    "EDGE_KINDS",
    "EXECUTION_ASSERTING_EDGE_KINDS",
    "REACHABILITY_EDGE_KINDS",
    "MERMAID_MAX_NODES",
    "MERMAID_MAX_DEPTH",
    # validator
    "validate_lineage_graph",
    # identity
    "make_func_id",
    "make_asset_id",
    "parse_func_id",
    "parse_asset_id",
    "content_fingerprint",
    "stable_func_key",
    # witness reconciliation
    "reconcile_with_witness",
    "witness_gate",
    # freshness
    "is_node_stale",
    "transitive_stale_nodes",
    # cost ceiling
    "truncate_to_budget",
]
