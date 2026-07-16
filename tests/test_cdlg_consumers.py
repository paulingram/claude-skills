"""Lineage roadmap P2–P5 — the CDLG consumers (WS-E).

These tests guard the consumer layer that sits ON TOP of the CDLG core
(`hooks/lineage_graph.py`, WS-D). They split into two kinds:

* **Structural** — each consumer skill/doc actually documents that it consumes
  the verified CDLG (so the discipline can't silently drift out of the prose):
    - P2  `diagnostic-research-team` consumes the verified CDLG + witness gate.
    - P3  `data-lineage-mapping` exists with valid frontmatter + the MANDATORY
          Reuse Decision vs `data-engineering-exploration` Stage 2/6.
    - P4  `team-spawning-and-review-gates` documents CDLG overlap (shared
          callees, not just files) + the canonical front→back traversal.
    - P5  `mempalace-integration` documents function-level records keyed by the
          `func://` nomenclature.

* **Real** — exercise the actual `hooks/locks.py::cdlg_overlap` helper (P4):
  a small graph where item A's function calls a function in item B's set returns
  overlap True + the shared subtree; disjoint sets return overlap False.

Source of truth: `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` REQ-DIAG-03/04 (P2),
REQ-DATA-01..04 (P3), REQ-PARA-01/02 (P4), REQ-MEM-01/02 (P5).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers import frontmatter
from tests.helpers.module_loader import load_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(plugin_root: Path, *parts: str) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def locks_module(plugin_root: Path) -> ModuleType:
    """Load hooks/locks.py via importlib (matches tests/test_locks.py)."""
    path = plugin_root / "hooks" / "locks.py"
    assert path.exists(), f"locks.py missing at {path}"
    mod = load_module(path, "locks_module_cdlg")
    return mod


# ===========================================================================
# P2 — diagnostic-research-team consumes the verified CDLG (REQ-DIAG-03/04)
# ===========================================================================

DRT = ("skills", "diagnostic-research-team", "SKILL.md")


def test_p2_diagnostic_team_documents_consuming_the_cdlg(plugin_root: Path) -> None:
    """The diagnostic researchers CONSUME the pre-built call-hierarchy instead of
    re-tracing from scratch — cite the CDLG / ENDPOINT_TRACE_MAP.md."""
    content = _read(plugin_root, *DRT)
    assert "CDLG" in content, "diagnostic-research-team does not name the CDLG"
    assert "ENDPOINT_TRACE_MAP.md" in content, (
        "diagnostic-research-team does not cite ENDPOINT_TRACE_MAP.md as its call-map input"
    )
    low = content.lower()
    assert "consume" in low, "diagnostic-research-team does not say it CONSUMES the CDLG"
    assert "instead of re-tracing" in low or "instead of retracing" in low or (
        "re-tracing" in low and "pre-built" in low
    ), "diagnostic-research-team does not say it consumes the pre-built map instead of re-tracing"


def test_p2_consumption_gated_on_witness_verification(plugin_root: Path) -> None:
    """Consumption is gated on the witness verification — witness_gate must pass,
    citing hooks/lineage_graph.py."""
    content = _read(plugin_root, *DRT)
    assert "witness_gate" in content, (
        "diagnostic-research-team does not gate consumption on witness_gate"
    )
    assert "hooks/lineage_graph.py" in content, (
        "diagnostic-research-team does not cite hooks/lineage_graph.py for the gate"
    )
    assert "reconcile_with_witness" in content, (
        "diagnostic-research-team does not reference reconcile_with_witness"
    )


def test_p2_data_source_check_cites_asset_node(plugin_root: Path) -> None:
    """The data-source existence check cites the asset:// node (REQ-DIAG-04)."""
    content = _read(plugin_root, *DRT)
    assert "asset://" in content, (
        "diagnostic-research-team's data-source check does not cite an asset:// node"
    )
    low = content.lower()
    assert "data-source existence check" in low, (
        "diagnostic-research-team does not name the data-source existence check"
    )


def test_p2_preserves_existing_loop_until_converged_prose(plugin_root: Path) -> None:
    """WS-A's loop-until-converged prose (Phase B unbounded loop) is preserved."""
    content = _read(plugin_root, *DRT)
    # the existing Phase B verdict/loop discipline must still be present
    assert "there is NO fixed cycle cap" in content, (
        "the existing loop-until-converged prose was removed"
    )
    assert "Unbounded solving discipline" in content, (
        "the reference to Unbounded solving discipline was removed"
    )


# ===========================================================================
# P3 — data-lineage-mapping skill (REQ-DATA-01..04)
# ===========================================================================

DLM = ("skills", "data-lineage-mapping", "SKILL.md")


def test_p3_skill_exists_with_valid_frontmatter(plugin_root: Path) -> None:
    path = plugin_root / "skills" / "data-lineage-mapping" / "SKILL.md"
    assert path.exists(), "data-lineage-mapping/SKILL.md does not exist"
    fm, body = frontmatter.parse(path)
    assert fm.get("name") == "data-lineage-mapping", "frontmatter name mismatch"
    assert isinstance(fm.get("description"), str) and len(fm["description"]) > 20, (
        "data-lineage-mapping description must be a substantive string"
    )
    assert body.strip(), "data-lineage-mapping body is empty"


def test_p3_has_mandatory_reuse_decision_vs_data_eng(plugin_root: Path) -> None:
    """MANDATORY Reuse Decision subsection vs data-engineering-exploration Stage 2/6,
    making the reuse-first decision explicit."""
    content = _read(plugin_root, *DLM)
    assert "Reuse Decision" in content, (
        "data-lineage-mapping lacks a Reuse Decision subsection"
    )
    assert "data-engineering-exploration" in content, (
        "data-lineage-mapping Reuse Decision does not reference data-engineering-exploration"
    )
    assert "Stage 2" in content and "Stage 6" in content, (
        "data-lineage-mapping Reuse Decision does not cite Stage 2/6"
    )
    low = content.lower()
    # the explicit reuse-first decision: extend/reuse, not duplicate
    assert "extend" in low and ("duplicate" in low or "duplicat" in low), (
        "data-lineage-mapping does not make the extend-not-duplicate decision explicit"
    )
    # the layer distinction: this is the bug/feature-flow asset-lineage layer;
    # data-eng is the warehouse-design layer
    assert "warehouse" in low, (
        "data-lineage-mapping does not distinguish the warehouse-design layer (data-eng)"
    )
    assert "asset-lineage" in low or "asset lineage" in low, (
        "data-lineage-mapping does not name itself the asset-lineage layer"
    )


def test_p3_documents_asset_edges_and_artifacts(plugin_root: Path) -> None:
    """Producing DATA_LINEAGE_MAP.md + the asset edges in lineage-graph.json."""
    content = _read(plugin_root, *DLM)
    assert "DATA_LINEAGE_MAP.md" in content, (
        "data-lineage-mapping does not produce DATA_LINEAGE_MAP.md"
    )
    assert "lineage-graph.json" in content, (
        "data-lineage-mapping does not write the asset edges into lineage-graph.json"
    )
    for edge_kind in ("reads", "writes", "modifies", "originates"):
        assert edge_kind in content, (
            f"data-lineage-mapping does not document the {edge_kind!r} asset edge"
        )


def test_p3_documents_population_tracking_and_bugflow_availability(plugin_root: Path) -> None:
    """Per-asset population tracking (which functions populate each asset) +
    data-model decomposition available in the bug-fix flow (not just Phase 0c)."""
    content = _read(plugin_root, *DLM)
    low = content.lower()
    assert "population" in low, (
        "data-lineage-mapping does not document per-asset population tracking"
    )
    assert "func://" in content, (
        "data-lineage-mapping does not key population sources to func:// nodes"
    )
    assert "bug-fix" in low or "bug flow" in low or "bug-flow" in low, (
        "data-lineage-mapping does not say decomposition is available in the bug-fix flow"
    )
    assert "phase 0c" in low, (
        "data-lineage-mapping does not contrast with the Phase 0c data-eng path"
    )


# ===========================================================================
# P4 — overlap + canonical traversal docs (REQ-PARA-01/02)
# ===========================================================================

TSR = ("skills", "team-spawning-and-review-gates", "SKILL.md")


def test_p4_documents_cdlg_overlap_shared_callees(plugin_root: Path) -> None:
    """The parallel-execution graph + locks consult CDLG overlap (shared callees,
    not just files)."""
    content = _read(plugin_root, *TSR)
    assert "cdlg_overlap" in content, (
        "team-spawning-and-review-gates does not reference the cdlg_overlap helper"
    )
    low = content.lower()
    assert "shared callee" in low, (
        "team-spawning-and-review-gates does not document shared-callee overlap"
    )
    assert "not just" in low and "file" in low, (
        "team-spawning-and-review-gates does not contrast call-graph overlap with file-path overlap"
    )
    assert "hooks/locks.py" in content, (
        "team-spawning-and-review-gates does not cite hooks/locks.py for overlap"
    )


def test_p4_documents_canonical_front_to_back_traversal(plugin_root: Path) -> None:
    """Canonical front→back traversal: UI element → endpoint → function tree →
    data_asset, built on the REQ-DOC-07 seam."""
    content = _read(plugin_root, *TSR)
    low = content.lower()
    assert "ui element" in low, "no UI element start to the traversal"
    assert "endpoint" in low, "no endpoint hop in the traversal"
    assert "function tree" in low, "no function-tree hop in the traversal"
    assert "data_asset" in content, "no data_asset terminus in the traversal"
    assert "serves_route" in content, (
        "the traversal does not name the serves_route (REQ-DOC-07) seam it is built on"
    )
    assert "REQ-DOC-07" in content, (
        "the traversal does not cite the REQ-DOC-07 seam it is built on"
    )


# ===========================================================================
# P5 — MemPalace function-level records (REQ-MEM-01/02)
# ===========================================================================

MEM = ("skills", "mempalace-integration", "SKILL.md")


def test_p5_documents_function_level_records_keyed_by_func_id(plugin_root: Path) -> None:
    """A func:// lookup returns upstream callers / downstream callees / data-sources;
    records bounded to the mapped subset; keyed by the func:// nomenclature; mined
    from lineage-graph.json."""
    content = _read(plugin_root, *MEM)
    assert "function-level lineage record" in content.lower() or (
        "function-level" in content.lower() and "record" in content.lower()
    ), "mempalace-integration does not document a function-level lineage record type"
    assert "func://" in content, "function-level records are not keyed by func://"
    low = content.lower()
    assert "upstream caller" in low, "func:// lookup does not return upstream callers"
    assert "downstream callee" in low, "func:// lookup does not return downstream callees"
    assert "data source" in low or "data-source" in low, (
        "func:// lookup does not return data sources"
    )
    assert "lineage-graph.json" in content, (
        "function-level records are not mined from lineage-graph.json"
    )
    assert "hooks/lineage_graph.py" in content, (
        "function-level records do not cite the func:// nomenclature's source module"
    )
    assert "bounded to the" in low and "subset" in low, (
        "records are not documented as bounded to the mapped subset"
    )


# ===========================================================================
# REAL — hooks/locks.py::cdlg_overlap (P4 / REQ-PARA-01)
# ===========================================================================


def _graph(nodes, edges):
    return {
        "schema_version": 1,
        "nodes": [
            {"id": nid, "kind": "function", "path": f"{nid}.py", "name": nid}
            for nid in nodes
        ],
        "edges": edges,
    }


def _calls(src, dst):
    return {"src": src, "dst": dst, "kind": "calls"}


def test_cdlg_overlap_signature_and_keys(locks_module: ModuleType) -> None:
    """cdlg_overlap(graph, funcs_a, funcs_b) -> dict with the three documented keys."""
    out = locks_module.cdlg_overlap(_graph([], []), [], [])
    assert set(out.keys()) == {"overlap", "shared_functions", "shared_subtree"}, out
    assert out["overlap"] is False
    assert out["shared_functions"] == []
    assert out["shared_subtree"] == []


def test_cdlg_overlap_transitive_calls_edge_flags_overlap(locks_module: ModuleType) -> None:
    """Item A's function calls a function in item B's set → overlap True + shared subtree.

    Graph:  A_fn --calls--> shared --calls--> deeper
    Item A owns A_fn (edits one file); Item B owns `shared` (edits a DIFFERENT
    file). They overlap because A reaches `shared` via a calls edge — the exact
    blind spot file-path locks miss.
    """
    g = _graph(
        ["A_fn", "shared", "deeper", "B_only"],
        [_calls("A_fn", "shared"), _calls("shared", "deeper")],
    )
    out = locks_module.cdlg_overlap(g, ["A_fn"], ["shared", "B_only"])
    assert out["overlap"] is True, out
    assert "shared" in out["shared_subtree"], out
    # they do NOT share a node directly (A_fn vs {shared, B_only})
    assert out["shared_functions"] == [], out


def test_cdlg_overlap_deep_transitive_reach(locks_module: ModuleType) -> None:
    """Reachability is transitive across multiple calls edges, not one hop."""
    g = _graph(
        ["A_fn", "mid", "deep_shared"],
        [_calls("A_fn", "mid"), _calls("mid", "deep_shared")],
    )
    out = locks_module.cdlg_overlap(g, ["A_fn"], ["deep_shared"])
    assert out["overlap"] is True, out
    assert "deep_shared" in out["shared_subtree"], out


def test_cdlg_overlap_shared_hot_callee_in_neither_set(locks_module: ModuleType) -> None:
    """REQ-PARA-01 AC: two items that edit DIFFERENT files but both call a common
    callee (in NEITHER set) overlap. This is the headline acceptance criterion —
    "share a hot callee" — and the case a naive 'A reaches B's node' rule misses.

    Graph:  A_fn --calls--> hot ; B_fn --calls--> hot   (hot is in neither set)
    """
    g = _graph(
        ["A_fn", "B_fn", "hot"],
        [_calls("A_fn", "hot"), _calls("B_fn", "hot")],
    )
    out = locks_module.cdlg_overlap(g, ["A_fn"], ["B_fn"])
    assert out["overlap"] is True, out
    assert "hot" in out["shared_subtree"], out
    # neither set directly shares a node
    assert out["shared_functions"] == [], out


def test_cdlg_overlap_direct_shared_node(locks_module: ModuleType) -> None:
    """A func:// node present in BOTH sets is a direct overlap (shared_functions)."""
    g = _graph(["x", "y", "z"], [])
    out = locks_module.cdlg_overlap(g, ["x", "y"], ["y", "z"])
    assert out["overlap"] is True, out
    assert out["shared_functions"] == ["y"], out


def test_cdlg_overlap_disjoint_sets_no_overlap(locks_module: ModuleType) -> None:
    """Disjoint function sets with no connecting calls edge → overlap False."""
    g = _graph(
        ["A_fn", "A_callee", "B_fn", "B_callee"],
        [_calls("A_fn", "A_callee"), _calls("B_fn", "B_callee")],
    )
    out = locks_module.cdlg_overlap(g, ["A_fn"], ["B_fn"])
    assert out["overlap"] is False, out
    assert out["shared_functions"] == [], out
    assert out["shared_subtree"] == [], out


def test_cdlg_overlap_reverse_direction_symmetric(locks_module: ModuleType) -> None:
    """Overlap is symmetric: if B reaches a function A owns, that is overlap too."""
    g = _graph(["B_fn", "shared", "A_only"], [_calls("B_fn", "shared")])
    # B reaches `shared`; A owns `shared`.
    out = locks_module.cdlg_overlap(g, ["shared", "A_only"], ["B_fn"])
    assert out["overlap"] is True, out
    assert "shared" in out["shared_subtree"], out


def test_cdlg_overlap_only_calls_edges_count(locks_module: ModuleType) -> None:
    """A non-`calls` edge (e.g. reads) between the sets does NOT create call-graph
    overlap — only the calls-edge reachability does."""
    g = {
        "schema_version": 1,
        "nodes": [
            {"id": "A_fn", "kind": "function", "path": "a.py", "name": "A_fn"},
            {"id": "tbl", "kind": "data_asset", "path": "", "name": "tbl"},
            {"id": "B_fn", "kind": "function", "path": "b.py", "name": "B_fn"},
        ],
        "edges": [
            {"src": "A_fn", "dst": "tbl", "kind": "reads"},
            {"src": "B_fn", "dst": "tbl", "kind": "reads"},
        ],
    }
    # A_fn and B_fn both read the same asset but neither CALLS the other; as
    # function sets they do not overlap on call-graph reachability.
    out = locks_module.cdlg_overlap(g, ["A_fn"], ["B_fn"])
    assert out["overlap"] is False, out


def test_cdlg_overlap_handles_malformed_graph_gracefully(locks_module: ModuleType) -> None:
    """A malformed/None graph degrades to the shared-node check (no crash)."""
    # None graph: no calls edges, so only direct sharing can flag overlap.
    out = locks_module.cdlg_overlap(None, ["x"], ["x"])
    assert out["overlap"] is True and out["shared_functions"] == ["x"], out
    out2 = locks_module.cdlg_overlap(None, ["x"], ["y"])
    assert out2["overlap"] is False, out2


def test_cdlg_overlap_file_path_lock_logic_intact(locks_module: ModuleType) -> None:
    """cdlg_overlap ADDS a signal — the existing file-path lock API is untouched."""
    for fn in ("acquire_lock", "release_lock", "detect_stale", "globs_intersect"):
        assert hasattr(locks_module, fn), f"locks.py lost its {fn} API"
    # globs_intersect still works exactly as before
    assert locks_module.globs_intersect("src/auth/**", "src/auth/login/**") is True
    assert locks_module.globs_intersect("src/auth/**", "src/billing/**") is False
