"""Tests for the knowledge server's freshness contract (KS-4) — services/knowledge_server/freshness.py.

Every tool response carries a `{verdict: current|stale|unknowable, basis: [...]}`
envelope. Map freshness is computed by `hooks/lineage_graph.py::transitive_stale_nodes`
over paths changed since the stamp (+ `map_invalidated`); dictionary freshness is
reference-file drift since `built_at`, with DB-side currency honestly `unknowable`
absent a live connection. Never a fabricated `current`; never a bare wall clock.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX = REPO_ROOT / "tests" / "fixtures" / "knowledge_server"

fr = load_module(REPO_ROOT / "services" / "knowledge_server" / "freshness.py", "ct6_ks_freshness")


def _graph() -> dict:
    return json.loads((FIX / "lineage-graph.json").read_text(encoding="utf-8"))


ENDPOINT = "endpoint://GET/api/orders"
LIST_ORDERS = "func://shop/src/services/orders.py#list_orders"
REPO_FETCH = "func://shop/src/repo/order_repo.py#OrderRepo.fetch"
ASSET = "asset://pg/public/orders"


# --------------------------------------------------------------------------- #
# the envelope
# --------------------------------------------------------------------------- #

def test_envelope_shape_and_valid_verdicts() -> None:
    env = fr.envelope("current", ["nothing changed"])
    assert env == {"verdict": "current", "basis": ["nothing changed"]}
    assert fr.VALID_VERDICTS == {"current", "stale", "unknowable"}
    # basis is always a list even if a tuple/other iterable is passed
    assert fr.envelope("stale", ("a", "b"))["basis"] == ["a", "b"]


# --------------------------------------------------------------------------- #
# map freshness (transitive_stale_nodes)
# --------------------------------------------------------------------------- #

def test_map_freshness_stale_when_deep_callee_changed() -> None:
    # a callee-only change three levels down marks the ancestor endpoint stale
    env = fr.map_freshness(_graph(), changed_paths=["src/repo/order_repo.py"],
                           stamp="2026-08-01T10:30:00Z")
    assert env["verdict"] == "stale"
    joined = " ".join(env["basis"])
    assert REPO_FETCH in joined  # the actually-changed node is named in the basis


def test_map_freshness_current_when_nothing_changed() -> None:
    env = fr.map_freshness(_graph(), changed_paths=[], stamp="2026-08-01T10:30:00Z")
    assert env["verdict"] == "current"


def test_map_freshness_unknowable_when_changed_paths_none() -> None:
    # git-unavailable => we CANNOT know what changed; the honest verdict is
    # unknowable, never a fabricated current.
    env = fr.map_freshness(_graph(), changed_paths=None, stamp="2026-08-01T10:30:00Z")
    assert env["verdict"] == "unknowable"
    assert env["verdict"] != "current"


def test_map_freshness_invalidation_override_forces_stale() -> None:
    # an explicit map_invalidated override is stale even with no changed paths
    env = fr.map_freshness(_graph(), changed_paths=[], stamp="s",
                           map_invalidated=["route table rewired"])
    assert env["verdict"] == "stale"
    assert any("invalidat" in b.lower() for b in env["basis"])


def test_map_freshness_subtree_scoping() -> None:
    g = _graph()
    # changing ONLY the endpoint's own file leaves the list_orders subtree current
    subtree = {LIST_ORDERS, REPO_FETCH, ASSET}
    env_out = fr.map_freshness(g, changed_paths=["src/api/orders_route.py"],
                               stamp="s", subtree_node_ids=subtree)
    assert env_out["verdict"] == "current"
    # changing a file INSIDE the subtree makes that subtree stale
    env_in = fr.map_freshness(g, changed_paths=["src/repo/order_repo.py"],
                              stamp="s", subtree_node_ids=subtree)
    assert env_in["verdict"] == "stale"


# --------------------------------------------------------------------------- #
# dictionary freshness (reference-file drift + DB unknowable)
# --------------------------------------------------------------------------- #

_REF_FILES = ["src/models/customer.py", "src/models/order.py", "src/services/orders.py"]


def test_dictionary_freshness_stale_when_reference_file_changed() -> None:
    env = fr.dictionary_freshness(changed_paths=["src/services/orders.py"],
                                  built_at="2026-08-01T09:00:00Z", reference_files=_REF_FILES)
    assert env["verdict"] == "stale"
    assert any("orders.py" in b for b in env["basis"])


def test_dictionary_freshness_current_still_discloses_db_unknowable() -> None:
    env = fr.dictionary_freshness(changed_paths=["unrelated/thing.py"],
                                  built_at="2026-08-01T09:00:00Z", reference_files=_REF_FILES)
    assert env["verdict"] == "current"
    # even a 'current' repo-side verdict must disclose the DB caveat + built_at,
    # never claim the live DB is fresh
    joined = " ".join(env["basis"]).lower()
    assert "unknowable" in joined and "2026-08-01t09:00:00z" in joined


def test_dictionary_freshness_unknowable_when_changed_paths_none() -> None:
    env = fr.dictionary_freshness(changed_paths=None, built_at="2026-08-01T09:00:00Z",
                                  reference_files=_REF_FILES)
    assert env["verdict"] == "unknowable"


# --------------------------------------------------------------------------- #
# the git-drift provider (injected runner keeps it hermetic)
# --------------------------------------------------------------------------- #

def test_git_changed_paths_parses_runner_output() -> None:
    def fake_runner(args: list[str]) -> str:
        assert "log" in args and any(a.startswith("--since=") for a in args)
        return "src/a.py\nsrc/b.py\n\nsrc/a.py\n"
    got = fr.git_changed_paths("2026-08-01T00:00:00Z", str(REPO_ROOT), runner=fake_runner)
    assert got == ["src/a.py", "src/b.py"]  # sorted + de-duplicated


def test_git_changed_paths_none_on_failure() -> None:
    def boom(args: list[str]) -> str:
        raise OSError("git not found")
    assert fr.git_changed_paths("s", str(REPO_ROOT), runner=boom) is None
    # a None stamp cannot scope a window => unknowable, not "everything"
    assert fr.git_changed_paths(None, str(REPO_ROOT), runner=lambda a: "x") is None
