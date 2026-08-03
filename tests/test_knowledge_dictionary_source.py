"""Tests for DictionarySource (KS-2, KS-4, KS-5, KS-6) — services/knowledge_server/dictionary_source.py.

Serves search_dictionary / get_table_details / find_relations / get_dictionary_status
over a data-dictionary.json fixture (+ docs/data-annotations/ when present),
composing the Librarian's LibraryIndex for ranked search, with the two-arm
dictionary freshness (repo-side drift + DB-side unknowable). Read-only.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX = REPO_ROOT / "tests" / "fixtures" / "knowledge_server"

ds_mod = load_module(REPO_ROOT / "services" / "knowledge_server" / "dictionary_source.py",
                     "ct6_ks_dictionary_source")


def _source(*, changed=lambda stamp: [], annotations=True):
    return ds_mod.DictionarySource(
        str(FIX / "data-dictionary.json"),
        annotations_dir=str(FIX / "data-annotations") if annotations else None,
        changed_paths_provider=changed)


def _tools(src) -> dict:
    return {t.name: t for t in src.tools()}


def _call(src, name, **args) -> dict:
    return _tools(src)[name].handler(args)


# --------------------------------------------------------------------------- #
# tool registration + the seam
# --------------------------------------------------------------------------- #

def test_registers_the_four_dictionary_tools() -> None:
    names = set(_tools(_source()))
    assert names == {"search_dictionary", "get_table_details", "find_relations",
                     "get_dictionary_status"}


# --------------------------------------------------------------------------- #
# KS-5 — ranked search composes the Librarian's LibraryIndex (verify by import)
# --------------------------------------------------------------------------- #

def test_search_composes_library_index_and_ranks() -> None:
    src = _source()
    # the index IS the Librarian's class, reached by import — not re-implemented
    assert type(src.index).__name__ == "LibraryIndex"
    assert type(src.index).__module__ == "library_index"
    out = _call(src, "search_dictionary", query="email")
    assert out["count"] >= 1
    ids = [r["doc_id"] for r in out["results"]]
    assert "customers" in ids  # customers carries the email field
    # ranked by the index weighting: scores are non-increasing
    scores = [r["score"] for r in out["results"]]
    assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------- #
# KS-2 — table details + annotation merge; find_relations from the relation map
# --------------------------------------------------------------------------- #

def test_get_table_details_merges_annotations() -> None:
    src = _source()
    out = _call(src, "get_table_details", table="customers")
    assert out["found"] is True
    assert out["grain"]["grain"] == "one row per customer"
    assert {f["field"] for f in out["fields"]} == {"id", "email", "signup_zip"}
    # docs/data-annotations entries anchored to the table or its fields are merged
    anchors = {a["anchor"] for a in out["annotations"]}
    assert "customers" in anchors and "customers.signup_zip" in anchors


def test_get_table_details_not_found_is_honest() -> None:
    out = _call(_source(), "get_table_details", table="nope")
    assert out["found"] is False and out["fields"] == []


def test_find_relations_from_relation_map_both_directions() -> None:
    out = _call(_source(), "find_relations", table="customers")
    # the orders->customers FK and the code-join both touch customers
    kinds = {r["kind"] for r in out["relations"]}
    assert "db-fk" in kinds and "code-join" in kinds
    assert out["count"] == len(out["relations"]) >= 2


# --------------------------------------------------------------------------- #
# KS-4 — two-arm freshness (repo-side drift + DB-side unknowable)
# --------------------------------------------------------------------------- #

def test_status_stale_when_reference_file_changed() -> None:
    src = _source(changed=lambda stamp: ["src/services/orders.py"])
    out = _call(src, "get_dictionary_status")
    assert out["freshness"]["verdict"] == "stale"
    assert out["db_side"]["verdict"] == "unknowable"  # never fabricated current
    assert out["built_at"] == "2026-08-01T09:00:00Z"


def test_status_current_still_reports_db_unknowable() -> None:
    out = _call(_source(changed=lambda stamp: []), "get_dictionary_status")
    assert out["freshness"]["verdict"] == "current"
    assert out["db_side"]["verdict"] == "unknowable"


def test_every_dictionary_response_carries_freshness() -> None:
    src = _source()
    for name in ("search_dictionary", "get_table_details", "find_relations", "get_dictionary_status"):
        args = {"query": "x"} if name == "search_dictionary" else (
            {"table": "customers"} if name in ("get_table_details", "find_relations") else {})
        out = _call(src, name, **args)
        assert out["freshness"]["verdict"] in {"current", "stale", "unknowable"}


# --------------------------------------------------------------------------- #
# KS-6 — every emitted response validates against its closed contract
# --------------------------------------------------------------------------- #

def test_responses_validate_against_contracts() -> None:
    co = load_module(REPO_ROOT / "services" / "knowledge_server" / "contracts.py", "ct6_ks_co_dict")
    contracts = co.tool_contracts()
    src = _source()
    for tool in src.tools():
        args = {"query": "email"} if tool.name == "search_dictionary" else (
            {"table": "customers"} if tool.name in ("get_table_details", "find_relations") else {})
        payload = tool.handler(args)
        result = co.validate_payload(payload, contracts[tool.name])
        assert result["valid"] is True, f"{tool.name}: {result['errors']}"


# --------------------------------------------------------------------------- #
# KS-2 — read-only: no source artifact is written by any tool call
# --------------------------------------------------------------------------- #

def test_adapter_is_read_only(tmp_path: Path) -> None:
    work = tmp_path / "ks"
    shutil.copytree(FIX, work)
    dpath = work / "data-dictionary.json"
    before = (dpath.read_bytes(), dpath.stat().st_mtime_ns)
    src = ds_mod.DictionarySource(str(dpath), annotations_dir=str(work / "data-annotations"),
                                  changed_paths_provider=lambda stamp: [])
    for tool in src.tools():
        args = {"query": "email"} if tool.name == "search_dictionary" else (
            {"table": "customers"} if tool.name in ("get_table_details", "find_relations") else {})
        tool.handler(args)
    after = (dpath.read_bytes(), dpath.stat().st_mtime_ns)
    assert before == after  # not one byte, not the mtime, was touched
