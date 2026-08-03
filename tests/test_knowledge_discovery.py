"""Tests for --repo-root conventional-sidecar auto-discovery (adjudicated seam fix).

When no explicit --dictionary/--graph/--map is given, the server discovers the
conventional CT6 sidecars under the repo root — docs/data-dictionary.json,
lineage-graph.json (repo root), docs/*_MAP.md (+ docs/data-annotations/) — and
serves whichever exist, reporting absent ones honestly (omission, not a crash).
Explicit paths override/augment discovery, per source. With neither explicit
paths nor a discoverable sidecar, the clear no-source ValueError stands. This is
what makes the installer's registration portable: `server.py --repo-root <repo>`.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX = REPO_ROOT / "tests" / "fixtures" / "knowledge_server"

srv = load_module(REPO_ROOT / "services" / "knowledge_server" / "server.py", "ct6_ks_server_disc")
sep = load_module(REPO_ROOT / "services" / "separation.py", "ct6_ks_sep_disc")


def _make_repo(root: Path, *, dictionary=True, graph=True, mapfile=True, annotations=True) -> Path:
    """Lay out the conventional CT6 sidecars under `root` from the fixtures."""
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    if dictionary:
        (docs / "data-dictionary.json").write_text(
            (FIX / "data-dictionary.json").read_text(encoding="utf-8"), encoding="utf-8")
    if annotations:
        ann = docs / "data-annotations"
        ann.mkdir(exist_ok=True)
        (ann / "analyst.json").write_text(
            (FIX / "data-annotations" / "analyst.json").read_text(encoding="utf-8"), encoding="utf-8")
    if graph:
        (root / "lineage-graph.json").write_text(
            (FIX / "lineage-graph.json").read_text(encoding="utf-8"), encoding="utf-8")
    if mapfile:
        (docs / "ENDPOINT_TRACE_MAP.md").write_text(
            (FIX / "ENDPOINT_TRACE_MAP.md").read_text(encoding="utf-8"), encoding="utf-8")
    return root


def _drive_main(argv, requests) -> dict:
    stdin = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
    stdout = io.StringIO()
    rc = srv.main(argv, stdin=stdin, stdout=stdout)
    assert rc == 0
    responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    return {r.get("id"): r for r in responses}


# --------------------------------------------------------------------------- #
# discover_sidecars — the conventional layout, honest about absence
# --------------------------------------------------------------------------- #

def test_discover_sidecars_finds_conventional_layout(tmp_path: Path) -> None:
    root = _make_repo(tmp_path / "repo")
    found = srv.discover_sidecars(str(root))
    assert Path(found["dictionary"]) == root / "docs" / "data-dictionary.json"
    assert Path(found["graph"]) == root / "lineage-graph.json"
    assert [Path(m) for m in found["map_files"]] == [root / "docs" / "ENDPOINT_TRACE_MAP.md"]
    assert Path(found["annotations"]) == root / "docs" / "data-annotations"


def test_discover_reports_absent_sources_by_omission(tmp_path: Path) -> None:
    # dictionary present, graph + map absent -> absent ones simply not in the dict
    root = _make_repo(tmp_path / "repo", graph=False, mapfile=False, annotations=False)
    found = srv.discover_sidecars(str(root))
    assert "dictionary" in found
    assert "graph" not in found and "map_files" not in found and "annotations" not in found


def test_discover_empty_root_is_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert srv.discover_sidecars(str(empty)) == {}
    assert srv.discover_sidecars(None) == {}


# --------------------------------------------------------------------------- #
# main --repo-root — the portable installer registration
# --------------------------------------------------------------------------- #

def test_main_serves_both_sources_from_repo_root_only(tmp_path: Path) -> None:
    root = _make_repo(tmp_path / "repo")
    by_id = _drive_main(["--repo-root", str(root)], [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "get_dictionary_status", "arguments": {}}},
    ])
    tool_names = {t["name"] for t in by_id[2]["result"]["tools"]}
    assert tool_names == {
        "search_dictionary", "get_table_details", "find_relations", "get_dictionary_status",
        "search_map", "get_route_details", "find_call_paths", "get_map_status",
    }
    status = by_id[3]["result"]["structuredContent"]
    assert status["freshness"]["verdict"] in {"current", "stale", "unknowable"}


def test_repo_root_with_no_sidecars_raises_clear_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError) as exc:
        srv.main(["--repo-root", str(empty)], stdin=io.StringIO(""), stdout=io.StringIO())
    assert "no source" in str(exc.value).lower()


# --------------------------------------------------------------------------- #
# explicit paths override discovery per source; discovery augments the rest
# --------------------------------------------------------------------------- #

def test_explicit_path_overrides_discovered_and_augments(tmp_path: Path) -> None:
    root = _make_repo(tmp_path / "repo")  # conventional dictionary + graph both present
    alt = tmp_path / "alt-dictionary.json"
    alt.write_text((FIX / "data-dictionary.json").read_text(encoding="utf-8"), encoding="utf-8")

    adapters = srv.build_adapters_from_paths(dictionary=str(alt), repo_root=str(root))
    by_name = {a.name: a for a in adapters}
    # explicit dictionary wins over the discovered docs/data-dictionary.json
    assert Path(by_name["dictionary"].path) == alt
    # the graph was still auto-discovered under repo_root (augment)
    assert "map" in by_name
    assert Path(by_name["map"].graph_path) == root / "lineage-graph.json"


def test_explicit_paths_alone_do_not_trigger_discovery(tmp_path: Path) -> None:
    # no repo_root => no discovery; only the explicitly-named source mounts
    adapters = srv.build_adapters_from_paths(dictionary=str(FIX / "data-dictionary.json"))
    assert {a.name for a in adapters} == {"dictionary"}


def test_discovery_keeps_check_separation_green() -> None:
    result = sep.check_separation()
    assert result["clean"] is True, f"non-separable imports: {result['violations']}"
