"""Tests for Run F — the stdlib JSON-LD emitter (`scripts/data_dictionary/jsonld_export.py`).

The emitter serializes the two machine-complete CT6 sidecars —
`docs/data-dictionary.json` (the catalog) + `lineage-graph.json` (the lineage) —
as JSON-LD for the external catalog / lineage ecosystems (schema.org / DCAT /
PROV-O). The correctness bar is STRUCTURAL validation + a round-trip (no live
consumer is wired — that honest boundary is stated in the skill + CHANGELOG).

Pinned disciplines:

* a dictionary table -> a `schema:Dataset` whose `variableMeasured` PropertyValues
  carry each field's definition / provenance / confidence PRESERVED VERBATIM
  (AC-R6-1);
* a lineage `reads` edge -> `prov:used`, a `writes` edge -> `prov:wasGeneratedBy`,
  walking ONLY edges present in the graph; an edge kind absent from the graph
  yields NO relation (AC-R6-2);
* the combined document validates + round-trips with no loss / no fabrication
  (AC-R6-3);
* an empty/absent input yields an empty but VALID `@graph` — no invented nodes
  (AC-R6-4);
* the module is stdlib-only (`json`) and imports no third-party JSON-LD library.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "jsonld_export.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "jsonld"

jl = load_module(MODULE_PATH, name="jsonld_export")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _dict_fixture() -> dict:
    return json.loads((FIXTURES / "data-dictionary.json").read_text(encoding="utf-8"))


def _graph_fixture() -> dict:
    return json.loads((FIXTURES / "lineage-graph.json").read_text(encoding="utf-8"))


def _by_id(doc: dict) -> dict:
    return {n["@id"]: n for n in doc["@graph"]}


def _refs(value) -> list:
    """Every @id referenced (as a `{"@id": ...}` marker) inside a property value."""
    return jl._iter_refs(value)  # the module's own reference walker


# --------------------------------------------------------------------------- #
# 1. AC-R6-1 — a dictionary table becomes a schema:Dataset with its fields
# --------------------------------------------------------------------------- #
def test_dictionary_table_becomes_dataset() -> None:
    doc = jl.export_dictionary_jsonld(_dict_fixture())
    assert jl.validate_jsonld(doc) == [], "the dictionary export must be valid JSON-LD"

    datasets = jl.nodes_by_type(doc, "schema:Dataset")
    names = {d.get("schema:name") for d in datasets}
    assert names == {"orders", "customers"}, "every table -> exactly one schema:Dataset"

    orders = next(d for d in datasets if d.get("schema:name") == "orders")
    by_id = _by_id(doc)
    # variableMeasured is a list of references that resolve to PropertyValue nodes
    field_nodes = [by_id[r["@id"]] for r in orders["schema:variableMeasured"]]
    assert all(f["@type"] == "schema:PropertyValue" for f in field_nodes)
    by_prop = {f["schema:propertyID"]: f for f in field_nodes}
    assert set(by_prop) == {"order_id", "status"}

    # definition / provenance / confidence PRESERVED VERBATIM
    status = by_prop["status"]
    assert status["schema:description"] == "Order lifecycle status (shipped/pending/cancelled)"
    assert status["ct6:provenance"] == "inference"
    assert status["ct6:confidence"] == "medium"

    # the usage block (table-level in the sidecar) rides the Dataset as ct6:usage
    assert orders["ct6:usage"]["row_volume"] == 120345
    assert orders["ct6:usage"]["provenance"] == "live-data"
    # a table WITHOUT a usage block gets NO ct6:usage (never zero-filled)
    customers = next(d for d in datasets if d.get("schema:name") == "customers")
    assert "ct6:usage" not in customers

    # a dcat:Catalog wraps the datasets and references each by @id
    catalog = jl.nodes_by_type(doc, "dcat:Catalog")
    assert len(catalog) == 1
    catalog_refs = {r["@id"] for r in catalog[0]["dcat:dataset"]}
    assert catalog_refs == {d["@id"] for d in datasets}


# --------------------------------------------------------------------------- #
# 2. AC-R6-2 — a lineage reads/writes edge becomes a PROV-O relation
# --------------------------------------------------------------------------- #
def test_lineage_reads_writes_become_prov() -> None:
    doc = jl.export_lineage_jsonld(_graph_fixture())
    assert jl.validate_jsonld(doc) == [], "the lineage export must be valid JSON-LD"
    by_id = _by_id(doc)

    # data_asset -> prov:Entity ; function/endpoint -> prov:Activity
    assert by_id["asset://raw/orders_csv"]["@type"] == "prov:Entity"
    assert by_id["asset://db/orders"]["@type"] == "prov:Entity"
    assert by_id["func://etl/load_orders"]["@type"] == "prov:Activity"
    assert by_id["endpoint://api/GET/orders"]["@type"] == "prov:Activity"

    # a reads edge -> the activity prov:used the entity
    fn = by_id["func://etl/load_orders"]
    assert "asset://raw/orders_csv" in _refs(fn["prov:used"])

    # a writes edge -> the written entity prov:wasGeneratedBy the activity
    written = by_id["asset://db/orders"]
    assert "func://etl/load_orders" in _refs(written["prov:wasGeneratedBy"])

    # calls / serves ride documented ct6 relations
    ep = by_id["endpoint://api/GET/orders"]
    assert "func://etl/load_orders" in _refs(ep["ct6:calls"])
    assert "asset://db/orders" in _refs(ep["ct6:serves"])

    # AN EDGE KIND ABSENT FROM THE GRAPH YIELDS NO RELATION — the fixture has no
    # `originates` and no `serves_route` edge, so no node carries their relations.
    serialized = json.dumps(doc)
    assert "ct6:originates" not in serialized
    assert "ct6:servesRoute" not in serialized


# --------------------------------------------------------------------------- #
# 3. AC-R6-3 — the combined document validates and round-trips
# --------------------------------------------------------------------------- #
def test_combined_validates_and_roundtrips() -> None:
    doc = jl.export_combined(_dict_fixture(), _graph_fixture())
    assert jl.validate_jsonld(doc) == []

    # @context binds the REAL vocabulary URLs
    ctx = doc["@context"]
    assert ctx["schema"] == "https://schema.org/"
    assert ctx["dcat"] == "http://www.w3.org/ns/dcat#"
    assert ctx["prov"] == "http://www.w3.org/ns/prov#"
    assert ctx["ct6"].startswith("http")

    # round-trip: serialize with stdlib json, re-parse — no loss
    rt = jl.roundtrip(doc)
    assert rt == doc
    assert jl.validate_jsonld(rt) == []

    # re-derive the source facts from the re-parsed document (no loss, no fabrication)
    by_id = _by_id(rt)
    status = next(
        n for n in rt["@graph"]
        if n.get("@type") == "schema:PropertyValue" and n.get("schema:propertyID") == "status"
    )
    assert status["schema:description"] == "Order lifecycle status (shipped/pending/cancelled)"
    assert "func://etl/load_orders" in _refs(by_id["asset://db/orders"]["prov:wasGeneratedBy"])


def test_combined_emits_only_source_content_no_fabrication() -> None:
    dict_json = _dict_fixture()
    graph_json = _graph_fixture()
    doc = jl.export_combined(dict_json, graph_json)

    # every schema:Dataset traces to a source table; no invented dataset
    source_tables = set(dict_json["tables"])
    emitted_tables = {d["schema:name"] for d in jl.nodes_by_type(doc, "schema:Dataset")}
    assert emitted_tables == source_tables

    # every PropertyValue traces to a source field of its table
    source_fields = {
        (t, f["field"]) for t, tinfo in dict_json["tables"].items() for f in tinfo["fields"]
    }
    emitted_fields = {
        (pv["@id"].split("/")[-2], pv["schema:propertyID"])
        for pv in jl.nodes_by_type(doc, "schema:PropertyValue")
    }
    assert emitted_fields == source_fields

    # every lineage @id traces to a source node id (no invented node)
    source_node_ids = {n["id"] for n in graph_json["nodes"]}
    emitted_prov_ids = {
        n["@id"] for n in doc["@graph"] if n["@type"] in ("prov:Entity", "prov:Activity")
    }
    assert emitted_prov_ids == source_node_ids


# --------------------------------------------------------------------------- #
# 4. AC-R6-4 — an empty catalog yields an empty valid graph
# --------------------------------------------------------------------------- #
def test_empty_input_empty_valid_graph() -> None:
    for doc in (
        jl.export_combined({}, {}),
        jl.export_combined(None, None),
        jl.export_dictionary_jsonld({"tables": {}}),
        jl.export_lineage_jsonld({"nodes": [], "edges": []}),
        jl.export_dictionary_jsonld({}),
        jl.export_lineage_jsonld({}),
    ):
        assert jl.validate_jsonld(doc) == [], "an empty export must still be valid JSON-LD"
        assert doc["@graph"] == [], "an empty input must invent NO nodes"
        assert isinstance(doc["@context"], dict)


# --------------------------------------------------------------------------- #
# 5. The walk-only-what-exists discipline (never invent a node or an edge kind)
# --------------------------------------------------------------------------- #
def test_unknown_edge_kind_is_skipped_not_invented() -> None:
    graph = {
        "nodes": [
            {"id": "func://f", "kind": "function", "name": "f"},
            {"id": "asset://a", "kind": "data_asset", "name": "a"},
        ],
        "edges": [
            {"src": "func://f", "dst": "asset://a", "kind": "reads"},
            {"src": "func://f", "dst": "asset://a", "kind": "frobnicates"},  # unknown
        ],
    }
    doc = jl.export_lineage_jsonld(graph)
    assert jl.validate_jsonld(doc) == []
    # the known reads edge is emitted; the unknown kind is skipped and NOTED
    fn = _by_id(doc)["func://f"]
    assert "asset://a" in _refs(fn["prov:used"])
    assert "frobnicates" not in json.dumps(doc)
    notes = jl.export_notes(graph)
    assert any("frobnicates" in note for note in notes), "an unknown edge kind must be noted"


def test_edge_to_missing_node_is_skipped_referential_closure_preserved() -> None:
    graph = {
        "nodes": [{"id": "func://f", "kind": "function", "name": "f"}],
        "edges": [{"src": "func://f", "dst": "asset://ghost", "kind": "reads"}],  # ghost dst
    }
    doc = jl.export_lineage_jsonld(graph)
    # the emitter must NOT invent the ghost node, and the dangling edge is dropped
    assert jl.validate_jsonld(doc) == [], "closure must hold — no dangling reference"
    assert "asset://ghost" not in json.dumps(doc)
    assert "prov:used" not in _by_id(doc)["func://f"]


def test_vocabulary_matches_lineage_graph_single_source() -> None:
    # the emitter recognizes EXACTLY the node/edge vocabulary the graph sidecar
    # defines — never inventing a kind, never silently missing one. Pinned so a
    # future lineage_graph vocabulary change reds here until the emitter maps it.
    lg = load_module(REPO_ROOT / "hooks" / "lineage_graph.py", name="lineage_graph_vocab")
    assert set(jl._NODE_TYPE) == set(lg.NODE_KINDS)
    assert set(jl._EDGE_MAP) == set(lg.EDGE_KINDS)


def test_unknown_node_kind_is_skipped() -> None:
    graph = {
        "nodes": [
            {"id": "func://f", "kind": "function", "name": "f"},
            {"id": "weird://w", "kind": "quasar", "name": "w"},  # unknown node kind
        ],
        "edges": [],
    }
    doc = jl.export_lineage_jsonld(graph)
    assert jl.validate_jsonld(doc) == []
    ids = {n["@id"] for n in doc["@graph"]}
    assert ids == {"func://f"}, "an unknown node kind must be skipped, never mapped"


# --------------------------------------------------------------------------- #
# 6. validate_jsonld actually BITES (an invalid document a consumer would reject)
# --------------------------------------------------------------------------- #
def test_validate_flags_missing_context() -> None:
    assert any("@context" in e for e in jl.validate_jsonld({"@graph": []}))


def test_validate_flags_node_missing_type() -> None:
    doc = {"@context": jl.CONTEXT, "@graph": [{"@id": "ct6:x"}]}  # no @type
    assert any("@type" in e for e in jl.validate_jsonld(doc))


def test_validate_flags_node_missing_id() -> None:
    doc = {"@context": jl.CONTEXT, "@graph": [{"@type": "schema:Dataset"}]}  # no @id
    assert any("@id" in e for e in jl.validate_jsonld(doc))


def test_validate_flags_duplicate_id() -> None:
    doc = {
        "@context": jl.CONTEXT,
        "@graph": [
            {"@id": "ct6:dup", "@type": "schema:Dataset"},
            {"@id": "ct6:dup", "@type": "schema:Dataset"},
        ],
    }
    assert any("duplicate" in e.lower() for e in jl.validate_jsonld(doc))


def test_validate_flags_dangling_reference() -> None:
    doc = {
        "@context": jl.CONTEXT,
        "@graph": [
            {"@id": "ct6:catalog", "@type": "dcat:Catalog",
             "dcat:dataset": [{"@id": "ct6:dataset/missing"}]},
        ],
    }
    assert any("resolve" in e.lower() for e in jl.validate_jsonld(doc))


# --------------------------------------------------------------------------- #
# 7. The emitter is stdlib-only (no third-party JSON-LD library)
# --------------------------------------------------------------------------- #
def test_emitter_imports_are_stdlib_only() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    forbidden = {"rdflib", "pyld", "jsonld", "requests", "sqlglot"}
    assert not (roots & forbidden), f"third-party import leaked in: {roots & forbidden}"


# --------------------------------------------------------------------------- #
# 8. The CLI produces a valid document
# --------------------------------------------------------------------------- #
def test_cli_export_jsonld_writes_valid_document(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonld"
    rc = jl.main([
        "export-jsonld",
        "--dictionary", str(FIXTURES / "data-dictionary.json"),
        "--graph", str(FIXTURES / "lineage-graph.json"),
        "--out", str(out),
    ])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert jl.validate_jsonld(doc) == []
    assert jl.nodes_by_type(doc, "schema:Dataset")
    assert jl.nodes_by_type(doc, "prov:Activity")


def test_cli_absent_sidecars_yield_empty_valid_graph(tmp_path: Path) -> None:
    out = tmp_path / "empty.jsonld"
    rc = jl.main([
        "export-jsonld",
        "--dictionary", str(tmp_path / "nope-dict.json"),
        "--graph", str(tmp_path / "nope-graph.json"),
        "--out", str(out),
    ])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert jl.validate_jsonld(doc) == []
    assert doc["@graph"] == []
