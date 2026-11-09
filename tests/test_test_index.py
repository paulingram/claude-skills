"""Tests for the test index + impact-based selector (`scripts/test_index/`).

The engine builds `<workspace>/.architect-team/test-index.json` (which test
exercises which files / func:// nodes / endpoints / elements, with a trust
level) and selects, from a change set and a phase, the tests that must run:
the dependents of what changed, plus the human pins, plus every test whose
mapping is unknown -- and EVERYTHING at Phase 8 (or any phase the human lists
in `tests.full_suite_at`). The selection is written as evidence.

THE FIXTURE TREE IS MATERIALIZED, NOT COMMITTED UNDER ITS REAL NAMES.
`tests/fixtures/test_index/repo/` stores its python test files as
`test_*.py.tmpl` and its Playwright specs as `*.spec.ts.tmpl`, and
`_materialize()` copies the tree into tmp_path stripping the suffix. Two
reasons, each pinned below: `pytest.ini` recurses `tests/` for `test_*.py`,
so a fixture test file at rest would be COLLECTED into this suite and fail on
its `fixpkg` import; and `hooks/discipline_registry.py` globs `**/*.spec.ts`
repo-wide, so a committed spec would flip this plugin repo to "unclassified QA
tests" (the lesson `tests/test_suite_manifest.py` records).

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG = REPO_ROOT / "scripts" / "test_index"
ENGINE_PATH = PKG / "engine.py"
CLI_PATH = PKG / "cli.py"
WITNESS_PLUGIN_PATH = PKG / "pytest_witness.py"
FIX = REPO_ROOT / "tests" / "fixtures" / "test_index"
FIX_REPO = FIX / "repo"
LINEAGE_FIXTURE = FIX / "lineage-graph.json"
REFERENCE = REPO_ROOT / "skills" / "common-pipeline-conventions" / "references" / "test-selection.md"
EXAMPLE_DEPLOY = REPO_ROOT / ".architect-team-deploy.example.json"

TMPL = ".tmpl"

PY_TEST_IDS = {
    "tests/test_models.py::test_parse_item",
    "tests/test_models.py::TestItem::test_equality",
    "tests/test_pricing.py::test_price_for",
    "tests/integration/test_api_integration.py::test_checkout_total",
    "tests/test_unmapped.py::test_json_roundtrip",
}
E2E_IDS = {
    "e2e/personas/shopper/checkout.spec.ts::shopper completes a card checkout",
    "e2e/personas/shopper/checkout.spec.ts::shopper sees the order in their history",
    "e2e/personas/ops/health.spec.ts::ops sees the health badge",
}
UNMAPPED = "tests/test_unmapped.py::test_json_roundtrip"
API_TEST = "tests/integration/test_api_integration.py::test_checkout_total"
PRICING_TEST = "tests/test_pricing.py::test_price_for"
MODELS_TEST = "tests/test_models.py::test_parse_item"
HEALTH_E2E = "e2e/personas/ops/health.spec.ts::ops sees the health badge"
CHECKOUT_E2E_1 = "e2e/personas/shopper/checkout.spec.ts::shopper completes a card checkout"


@pytest.fixture(scope="module")
def eng() -> ModuleType:
    return load_module(ENGINE_PATH, "ct6_test_index_engine_under_test")


@pytest.fixture(scope="module")
def deploy_config() -> ModuleType:
    return load_module(REPO_ROOT / "hooks" / "deploy_config.py", "ct6_test_index_deploy_config")


def _materialize(tmp_path: Path) -> Path:
    ws = tmp_path / "repo"
    for src in sorted(FIX_REPO.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(FIX_REPO)
        name = rel.name[:-len(TMPL)] if rel.name.endswith(TMPL) else rel.name
        dst = ws / rel.parent / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    return ws


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    return _materialize(tmp_path)


def _by_id(index: dict) -> dict:
    return {t["id"]: t for t in index["tests"]}


def _selected_ids(record: dict) -> set:
    return {s["id"] for s in record["selected"]}


def _reasons(record: dict, test_id: str) -> list:
    return next(s["reasons"] for s in record["selected"] if s["id"] == test_id)


def _write_deploy(ws: Path, tests_block) -> None:
    (ws / ".architect-team-deploy.json").write_text(
        json.dumps({"prod_deploy": {"enabled": False}, "tests": tests_block}),
        encoding="utf-8")


# --------------------------------------------------------------------------- #
# 0. The fixture is stored safely
# --------------------------------------------------------------------------- #

def test_fixture_tree_holds_no_collectable_or_qa_shaped_files_at_rest() -> None:
    """The lesson this module's docstring records: nothing under the fixture
    dir may match pytest's `test_*.py` or discipline_registry's `*.spec.ts`."""
    offenders = [
        p.relative_to(FIX).as_posix() for p in FIX.rglob("*")
        if p.is_file() and (
            (p.name.startswith("test_") and p.name.endswith(".py"))
            or p.name.endswith((".spec.ts", ".test.ts", ".spec.js", ".test.js"))
        )
    ]
    assert offenders == [], offenders
    assert sum(1 for p in FIX_REPO.rglob("*.py.tmpl")) == 4
    assert sum(1 for p in FIX_REPO.rglob("*.spec.ts.tmpl")) == 2


def test_materialized_tree_has_the_real_names(ws: Path) -> None:
    assert (ws / "tests" / "test_models.py").is_file()
    assert (ws / "e2e" / "personas" / "ops" / "health.spec.ts").is_file()
    assert not list(ws.rglob("*.tmpl"))


# --------------------------------------------------------------------------- #
# 1. build -- static discovery
# --------------------------------------------------------------------------- #

def test_build_discovers_python_and_manifest_tests_with_stable_ids(eng, ws) -> None:
    index = eng.build(ws)
    assert index["schema"] == "test-index/v1"
    assert index["workspace_root_rel"] == "."
    assert set(_by_id(index)) == PY_TEST_IDS | E2E_IDS
    assert index["sources"] == {
        "static": True, "witness": None, "lineage_graph": None,
        "suite_manifest": "e2e/suite-manifest.json",
    }
    assert [t["id"] for t in index["tests"]] == sorted(t["id"] for t in index["tests"])


def test_build_classifies_kind_and_layer(eng, ws) -> None:
    tests = _by_id(eng.build(ws, write=False))
    assert tests[MODELS_TEST]["kind"] == "unit"
    assert tests[MODELS_TEST]["layer"] == "backend"
    assert tests[API_TEST]["kind"] == "integration"
    assert tests[HEALTH_E2E]["kind"] == "e2e"
    assert tests[HEALTH_E2E]["layer"] == "frontend"
    for t in tests.values():
        assert t["kind"] in eng.KINDS and t["layer"] in eng.LAYERS
        assert t["trust"] in eng.TRUST_LEVELS
        assert t["duration_s"] is None and t["always_run"] is False


def test_build_resolves_imports_one_level_beyond_the_direct_import(eng, ws) -> None:
    """A test's files = the modules it imports + one level of THEIR imports.
    Every module's own package ``__init__.py`` is one of its imports (Python
    runs it first), so it rides along at that level."""
    tests = _by_id(eng.build(ws, write=False))
    assert tests[MODELS_TEST]["files"] == ["fixpkg/__init__.py", "fixpkg/models.py"]
    # test_pricing imports pricing only; pricing imports models -> one level in
    assert tests[PRICING_TEST]["files"] == ["fixpkg/__init__.py", "fixpkg/models.py",
                                            "fixpkg/pricing.py"]
    # api imports pricing + models through RELATIVE imports; both resolve
    assert tests[API_TEST]["files"] == ["fixpkg/__init__.py", "fixpkg/api.py",
                                        "fixpkg/models.py", "fixpkg/pricing.py"]
    for tid in (MODELS_TEST, PRICING_TEST, API_TEST):
        assert tests[tid]["trust"] == "static"


def test_build_records_the_source_import_graph(eng, ws) -> None:
    graph = eng.build(ws, write=False)["import_graph"]
    assert graph["fixpkg/__init__.py"] == []
    assert graph["fixpkg/models.py"] == ["fixpkg/__init__.py"]
    assert graph["fixpkg/pricing.py"] == ["fixpkg/__init__.py", "fixpkg/models.py"]
    assert graph["fixpkg/api.py"] == ["fixpkg/__init__.py", "fixpkg/models.py", "fixpkg/pricing.py"]
    assert not any(k.startswith("tests/") for k in graph), "test files are not graph nodes"


def test_path_literals_map_by_path_loading(eng, ws) -> None:
    """This repo's own tests load modules by file path (`load_module(HOOKS /
    "deploy_config.py")`), which no import graph sees. A string constant that
    names a repo file -- exact repo-relative path, or a unique bare file name --
    is a dependency; an ambiguous bare name resolves only to the one candidate
    in the referrer's own directory, else to nothing."""
    (ws / "tools").mkdir()
    (ws / "tools" / "engine.py").write_text("X = 1\n", encoding="utf-8")
    (ws / "tools" / "runner.py").write_text(
        "from pathlib import Path\nENGINE = Path(__file__).parent / 'engine.py'\n",
        encoding="utf-8")
    (ws / "other").mkdir()
    (ws / "other" / "engine.py").write_text("Y = 2\n", encoding="utf-8")
    (ws / "tests" / "test_by_path.py").write_text(
        "import importlib.util\nfrom pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "def test_loads():\n"
        "    exact = ROOT / 'fixpkg/pricing.py'\n"
        "    unique = ROOT / 'fixpkg' / 'api.py'\n"
        "    ambiguous = ROOT / 'engine.py'\n"
        "    manifest = 'e2e/suite-manifest.json'\n"
        "    assert exact and unique and ambiguous and manifest\n",
        encoding="utf-8")
    index = eng.build(ws, write=False)
    tests = _by_id(index)
    by_path = tests["tests/test_by_path.py::test_loads"]
    assert by_path["trust"] == "static"
    # exact path + unique basename + a non-python repo file; the ambiguous
    # 'engine.py' (two candidates, neither in tests/) resolves to nothing;
    # pricing's and api's own imports ride along one level
    assert by_path["files"] == ["e2e/suite-manifest.json", "fixpkg/__init__.py",
                                "fixpkg/api.py", "fixpkg/models.py", "fixpkg/pricing.py"]
    # a source module naming a sibling by bare name resolves within its own dir
    assert index["import_graph"]["tools/runner.py"] == ["tools/engine.py"]
    # and the selector follows the literal edge like any other
    record = eng.select(ws, ["e2e/suite-manifest.json"], "3", index, write=False)
    assert "tests/test_by_path.py::test_loads" in _selected_ids(record)
    assert "touches e2e/suite-manifest.json" in _reasons(record, "tests/test_by_path.py::test_loads")


def test_from_package_import_symbol_resolves_to_the_package_init(eng, ws) -> None:
    """``from fixpkg import Item``-style symbol imports depend on the package
    init, while ``from fixpkg import pricing`` depends on the submodule."""
    (ws / "tests" / "test_symbol.py").write_text(
        "from fixpkg import PRICES\n\ndef test_symbol():\n    assert PRICES\n", encoding="utf-8")
    tests = _by_id(eng.build(ws, write=False))
    assert tests["tests/test_symbol.py::test_symbol"]["files"] == ["fixpkg/__init__.py"]


def test_unmapped_test_is_unknown_trust_with_no_files(eng, ws) -> None:
    tests = _by_id(eng.build(ws, write=False))
    assert tests[UNMAPPED]["files"] == []
    assert tests[UNMAPPED]["trust"] == "unknown"


def test_manifest_join_carries_elements_and_spec_endpoints(eng, ws) -> None:
    tests = _by_id(eng.build(ws, write=False))
    checkout = tests[CHECKOUT_E2E_1]
    assert checkout["file"] == "e2e/personas/shopper/checkout.spec.ts"
    assert checkout["files"] == ["e2e/personas/shopper/checkout.spec.ts"]
    assert checkout["elements"] == ["cart__summary__checkout__1", "checkout__form__pay__1"]
    assert checkout["endpoints"] == ["/api/checkout", "/api/items"]
    assert checkout["persona"] == "shopper" and checkout["safety"] == "dev"
    health = tests[HEALTH_E2E]
    assert health["endpoints"] == ["/api/health"]  # a template literal counts
    assert health["elements"] == ["home__status__badge__1"]
    assert health["safety"] == "prod"


def test_build_honours_an_explicit_e2e_dir_and_reports_a_missing_one(eng, ws) -> None:
    assert eng.build(ws, e2e_dir="e2e", write=False)["sources"]["suite_manifest"] \
        == "e2e/suite-manifest.json"
    no_manifest = eng.build(ws, e2e_dir="nope", write=False)
    assert no_manifest["sources"]["suite_manifest"] is None
    assert set(_by_id(no_manifest)) == PY_TEST_IDS


def test_build_writes_the_index_to_the_state_dir(eng, ws) -> None:
    eng.build(ws)
    path = ws / ".architect-team" / "test-index.json"
    assert path.is_file()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["schema"] == "test-index/v1"
    assert eng.load_index(ws)["tests"] == on_disk["tests"]
    assert path.read_text(encoding="utf-8").isascii()


# --------------------------------------------------------------------------- #
# 2. build -- the joins
# --------------------------------------------------------------------------- #

def test_lineage_join_attaches_func_ids_by_node_path(eng, ws) -> None:
    index = eng.build(ws, lineage_graph=str(LINEAGE_FIXTURE), write=False)
    assert index["sources"]["lineage_graph"].endswith("lineage-graph.json")
    assert "lineage_graph_errors" not in index["sources"]
    tests = _by_id(index)
    assert tests[PRICING_TEST]["funcs"] == [
        "func://fixture/fixpkg/models.py#parse_item",
        "func://fixture/fixpkg/pricing.py#price_for",
    ]
    assert tests[API_TEST]["funcs"] == [
        "func://fixture/fixpkg/api.py#checkout_total",
        "func://fixture/fixpkg/models.py#parse_item",
        "func://fixture/fixpkg/pricing.py#price_for",
    ]
    assert tests[UNMAPPED]["funcs"] == []
    assert tests[HEALTH_E2E]["funcs"] == []
    # the endpoint:// node is never a func
    assert not any("endpoint://" in f for t in tests.values() for f in t["funcs"])


def test_lineage_join_default_location_is_the_state_dir(eng, ws) -> None:
    (ws / ".architect-team").mkdir()
    shutil.copy(LINEAGE_FIXTURE, ws / ".architect-team" / "lineage-graph.json")
    index = eng.build(ws, write=False)
    assert index["sources"]["lineage_graph"] == ".architect-team/lineage-graph.json"
    assert _by_id(index)[MODELS_TEST]["funcs"] == ["func://fixture/fixpkg/models.py#parse_item"]


def test_malformed_lineage_graph_joins_nothing_and_is_reported(eng, ws) -> None:
    bad = ws / "bad-graph.json"
    bad.write_text(json.dumps({"schema_version": 1, "nodes": [{"id": "x"}], "edges": []}),
                   encoding="utf-8")
    index = eng.build(ws, lineage_graph=str(bad), write=False)
    assert index["sources"]["lineage_graph_errors"] >= 1
    assert all(t["funcs"] == [] for t in index["tests"])


def test_witness_merge_upgrades_trust_and_replaces_the_static_files(eng, ws) -> None:
    witness = {
        "schema": "test-witness/v1",
        "tests": {
            PRICING_TEST: {"files": ["fixpkg/pricing.py", "fixpkg/models.py",
                                     "fixpkg/dynamic_plugin.py"], "duration_s": 0.5},
            # parametrized variants aggregate onto the base id
            MODELS_TEST + "[a]": {"files": ["fixpkg/models.py"], "duration_s": 0.1},
            MODELS_TEST + "[b]": {"files": ["fixpkg/models.py", "fixpkg/pricing.py"],
                                  "duration_s": 0.2},
            UNMAPPED: {"files": [], "duration_s": 0.01},
        },
    }
    wpath = ws / "witness.json"
    wpath.write_text(json.dumps(witness), encoding="utf-8")
    index = eng.build(ws, witness=str(wpath), write=False)
    assert index["sources"]["witness"] == "witness.json"
    assert index["witnessed_count"] == 2
    tests = _by_id(index)
    pricing = tests[PRICING_TEST]
    assert pricing["trust"] == "runtime-witnessed"
    assert pricing["files"] == ["fixpkg/dynamic_plugin.py", "fixpkg/models.py", "fixpkg/pricing.py"]
    assert pricing["duration_s"] == 0.5
    models = tests[MODELS_TEST]
    assert models["trust"] == "runtime-witnessed"
    assert models["files"] == ["fixpkg/models.py", "fixpkg/pricing.py"]
    assert models["duration_s"] == pytest.approx(0.3)
    # an EMPTY observation is not evidence: the static mapping and trust stay,
    # only the duration lands (the selector still runs this one -- no files)
    assert tests[UNMAPPED]["trust"] == "unknown"
    assert tests[UNMAPPED]["files"] == []
    assert tests[UNMAPPED]["duration_s"] == 0.01
    # untouched tests keep their static mapping
    assert tests[API_TEST]["trust"] == "static"
    assert tests[API_TEST]["duration_s"] is None


def test_empty_witness_observation_keeps_a_static_mapping(eng, ws) -> None:
    witness = {"schema": "test-witness/v1",
               "tests": {MODELS_TEST: {"files": [], "duration_s": 0.2}}}
    wpath = ws / "w.json"
    wpath.write_text(json.dumps(witness), encoding="utf-8")
    index = eng.build(ws, witness=str(wpath), write=False)
    assert index["witnessed_count"] == 0
    models = _by_id(index)[MODELS_TEST]
    assert models["trust"] == "static"
    assert models["files"] == ["fixpkg/__init__.py", "fixpkg/models.py"]
    assert models["duration_s"] == 0.2


def test_witness_only_test_is_added_only_when_its_file_exists(eng, ws) -> None:
    witness = {"schema": "test-witness/v1", "tests": {
        "tests/test_models.py::test_generated": {"files": ["fixpkg/models.py"], "duration_s": 0.1},
        "tests/test_gone.py::test_x": {"files": ["fixpkg/models.py"], "duration_s": 0.1},
    }}
    wpath = ws / ".architect-team" / "test-witness.json"
    wpath.parent.mkdir()
    wpath.write_text(json.dumps(witness), encoding="utf-8")
    tests = _by_id(eng.build(ws, write=False))  # the default witness location
    assert "tests/test_models.py::test_generated" in tests
    assert tests["tests/test_models.py::test_generated"]["trust"] == "runtime-witnessed"
    assert "tests/test_gone.py::test_x" not in tests


def test_malformed_witness_changes_nothing(eng, ws) -> None:
    wpath = ws / "w.json"
    wpath.write_text("{ not json", encoding="utf-8")
    index = eng.build(ws, witness=str(wpath), write=False)
    assert index["witnessed_count"] == 0
    assert all(t["trust"] in ("static", "unknown") for t in index["tests"])


def test_always_run_pins_come_from_the_deploy_config(eng, ws) -> None:
    _write_deploy(ws, {"always_run": ["tests/test_unmapped.py::*", "*health*",
                                      "tests/test_pricing.py::test_price_for"]})
    index = eng.build(ws, write=False)
    tests = _by_id(index)
    assert index["pins"]["always_run"] == ["tests/test_unmapped.py::*", "*health*",
                                           "tests/test_pricing.py::test_price_for"]
    pinned = {tid for tid, t in tests.items() if t["always_run"]}
    assert pinned == {UNMAPPED, HEALTH_E2E, PRICING_TEST}


def test_no_deploy_config_means_no_pins(eng, ws) -> None:
    index = eng.build(ws, write=False)
    assert index["pins"] == {"always_run": []}
    assert not any(t["always_run"] for t in index["tests"])


# --------------------------------------------------------------------------- #
# 3. select
# --------------------------------------------------------------------------- #

def test_select_one_source_change_selects_only_its_dependents_plus_unknown(eng, ws) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["fixpkg/api.py"], "3", index, write=False)
    assert record["schema"] == "test-selection/v1"
    assert record["full_suite"] is False
    python_selected = {s for s in _selected_ids(record) if s in PY_TEST_IDS}
    assert python_selected == {API_TEST, UNMAPPED}
    assert _reasons(record, API_TEST) == ["touches fixpkg/api.py"]
    assert _reasons(record, UNMAPPED) == ["unknown-mapping"]
    # api.py carries '/api/items' + '/api/checkout' literals -> the checkout flow
    # is selected by endpoint; the health flow is not
    assert record["changed_endpoints"] == ["/api/checkout", "/api/items"]
    assert CHECKOUT_E2E_1 in _selected_ids(record)
    assert _reasons(record, CHECKOUT_E2E_1) == ["endpoint /api/checkout changed",
                                                "endpoint /api/items changed"]
    assert HEALTH_E2E not in _selected_ids(record)
    assert record["skipped_count"] == len(index["tests"]) - len(record["selected"])
    assert record["skipped_count"] >= 3


def test_select_leaf_change_walks_the_reverse_import_closure(eng, ws) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["fixpkg/models.py"], "phase-3", index, write=False)
    assert record["affected_files"] == ["fixpkg/api.py", "fixpkg/models.py", "fixpkg/pricing.py"]
    python_selected = {s for s in _selected_ids(record) if s in PY_TEST_IDS}
    assert python_selected == PY_TEST_IDS  # every mapped test depends on models + the unknown one
    assert _reasons(record, MODELS_TEST) == ["touches fixpkg/models.py"]
    assert "touches fixpkg/pricing.py (depends on fixpkg/models.py)" in _reasons(record, PRICING_TEST)
    assert "touches fixpkg/models.py" in _reasons(record, PRICING_TEST)
    # models.py has no /api literal -> no e2e selected by endpoint, none by frontend
    assert not (_selected_ids(record) & E2E_IDS)


def test_select_package_init_change_reaches_every_module_of_the_package(eng, ws) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["fixpkg/__init__.py"], "3", index, write=False)
    assert record["affected_files"] == ["fixpkg/__init__.py", "fixpkg/api.py",
                                        "fixpkg/models.py", "fixpkg/pricing.py"]
    assert {s for s in _selected_ids(record) if s in PY_TEST_IDS} == PY_TEST_IDS


def test_select_unrelated_change_selects_only_unknown_and_pins(eng, ws) -> None:
    _write_deploy(ws, {"always_run": ["*health*"]})
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["README.md"], "3", index, write=False)
    assert _selected_ids(record) == {UNMAPPED, HEALTH_E2E}
    assert _reasons(record, HEALTH_E2E) == ["always_run"]


def test_select_frontend_change_without_elements_is_coarse(eng, ws) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["web/src/components/Cart.tsx"], "5", index, write=False)
    assert record["frontend_files"] == ["web/src/components/Cart.tsx"]
    assert _selected_ids(record) == E2E_IDS | {UNMAPPED}
    for tid in E2E_IDS:
        assert _reasons(record, tid) == ["frontend-change-coarse-mapping"]


def test_select_frontend_change_with_elements_is_precise(eng, ws) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["web/src/components/Cart.tsx"], "5", index,
                        changed_elements=["cart__summary__checkout__1"], write=False)
    e2e_selected = _selected_ids(record) & E2E_IDS
    assert e2e_selected == {
        "e2e/personas/shopper/checkout.spec.ts::shopper completes a card checkout",
        "e2e/personas/shopper/checkout.spec.ts::shopper sees the order in their history",
    }
    assert _reasons(record, CHECKOUT_E2E_1) == ["element cart__summary__checkout__1 touched"]
    assert HEALTH_E2E not in _selected_ids(record)


def test_select_explicit_changed_endpoint_selects_the_consuming_flow(eng, ws) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, [], "5", index, changed_endpoints=["api/health/"], write=False)
    assert record["changed_endpoints"] == ["/api/health"]
    assert _selected_ids(record) & E2E_IDS == {HEALTH_E2E}
    assert _reasons(record, HEALTH_E2E) == ["endpoint /api/health changed"]


def test_select_spec_file_change_selects_that_flow(eng, ws) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["e2e/personas/ops/health.spec.ts"], "3", index, write=False)
    assert HEALTH_E2E in _selected_ids(record)
    assert "touches e2e/personas/ops/health.spec.ts" in _reasons(record, HEALTH_E2E)


@pytest.mark.parametrize("phase", ["8", "phase-8", "Phase 8", "PHASE_8"])
def test_select_phase_8_returns_everything_as_full_suite(eng, ws, phase) -> None:
    index = eng.build(ws, write=False)
    record = eng.select(ws, [], phase, index, write=False)
    assert record["full_suite"] is True
    assert _selected_ids(record) == PY_TEST_IDS | E2E_IDS
    assert record["skipped_count"] == 0
    for s in record["selected"]:
        assert s["reasons"][0] == "full-suite-phase"


def test_select_phase_8_is_not_narrowable_by_config(eng, ws) -> None:
    _write_deploy(ws, {"full_suite_at": []})
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["fixpkg/api.py"], "8", index, write=False)
    assert record["full_suite"] is True
    assert record["skipped_count"] == 0


def test_select_honours_config_full_suite_at(eng, ws) -> None:
    _write_deploy(ws, {"full_suite_at": ["phase-5", "phase-8"]})
    index = eng.build(ws, write=False)
    assert eng.select(ws, ["fixpkg/api.py"], "5", index, write=False)["full_suite"] is True
    assert eng.select(ws, ["fixpkg/api.py"], "Phase 5", index, write=False)["full_suite"] is True
    assert eng.select(ws, ["fixpkg/api.py"], "3", index, write=False)["full_suite"] is False


def test_select_pins_are_always_selected(eng, ws) -> None:
    _write_deploy(ws, {"always_run": ["tests/test_pricing.py::test_price_for"]})
    index = eng.build(ws, write=False)
    record = eng.select(ws, ["README.md"], "3", index, write=False)
    assert PRICING_TEST in _selected_ids(record)
    assert _reasons(record, PRICING_TEST) == ["always_run"]


def test_select_writes_the_evidence_record(eng, ws) -> None:
    eng.build(ws)
    record = eng.select(ws, ["fixpkg/pricing.py"], "3", baseline="abc123")
    rel = record["record_path"]
    assert rel.startswith(".architect-team/test-selection-") and rel.endswith(".json")
    on_disk = json.loads((ws / rel).read_text(encoding="utf-8"))
    assert on_disk["schema"] == "test-selection/v1"
    assert on_disk["phase"] == "3" and on_disk["baseline"] == "abc123"
    assert on_disk["changed_files"] == ["fixpkg/pricing.py"]
    assert on_disk["selected"] == record["selected"]
    assert "record_path" not in on_disk
    assert set(on_disk) >= {"at", "selected", "skipped_count", "full_suite", "changed_files"}
    # a second selection in the same second gets its own file
    second = eng.select(ws, ["fixpkg/pricing.py"], "3")
    assert second["record_path"] != rel
    summary = eng.latest_selection(ws)
    assert summary["path"] == second["record_path"]
    assert summary["phase"] == "3" and summary["full_suite"] is False
    assert summary["selected_count"] == len(second["selected"])


def test_select_without_an_index_builds_one(eng, ws) -> None:
    assert eng.load_index(ws) is None
    record = eng.select(ws, ["fixpkg/api.py"], "3", write=False)
    assert API_TEST in _selected_ids(record)
    assert eng.load_index(ws) is not None  # the bootstrap build was written


def test_select_rejects_a_string_change_set(eng, ws) -> None:
    index = eng.build(ws, write=False)
    with pytest.raises(TypeError):
        eng.select(ws, "fixpkg/api.py", "3", index, write=False)


def test_normalize_phase_forms(eng) -> None:
    assert eng.normalize_phase("Phase 8") == "8"
    assert eng.normalize_phase("phase-8") == "8"
    assert eng.normalize_phase(" 8 ") == "8"
    assert eng.normalize_phase("B8") == "b8"
    assert eng.normalize_phase(None) == ""


# --------------------------------------------------------------------------- #
# 4. stats
# --------------------------------------------------------------------------- #

def test_stats_counts_by_kind_layer_trust(eng, ws) -> None:
    _write_deploy(ws, {"always_run": ["*health*"]})
    index = eng.build(ws, write=False)
    st = eng.stats(index)
    assert st["schema"] == "test-index-stats/v1"
    assert st["total"] == 8
    assert st["by_kind"] == {"unit": 4, "integration": 1, "e2e": 3, "unknown": 0}
    assert st["by_layer"] == {"backend": 5, "frontend": 3, "unknown": 0}
    assert st["by_trust"] == {"static": 7, "runtime-witnessed": 0, "unknown": 1}
    assert st["always_run"] == 1 and st["unknown_mapping"] == 1
    assert st["with_duration"] == 0 and st["total_duration_s"] is None
    assert eng.stats(None)["total"] == 0


# --------------------------------------------------------------------------- #
# 5. changed_files_from_git on a real temp repo
# --------------------------------------------------------------------------- #

def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=f@x.test",
         *args], capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_changed_files_from_git_unions_committed_and_uncommitted(eng, tmp_path) -> None:
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.py").write_text("A = 1\n", encoding="utf-8")
    (repo / "b.py").write_text("B = 1\n", encoding="utf-8")
    (repo / "keep.py").write_text("K = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("A = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "change a")
    (repo / "b.py").write_text("B = 2\n", encoding="utf-8")          # modified, uncommitted
    (repo / "new.py").write_text("N = 1\n", encoding="utf-8")        # untracked
    (repo / "sub").mkdir()
    (repo / "sub" / "deep.py").write_text("D = 1\n", encoding="utf-8")  # untracked, nested
    assert eng.changed_files_from_git(repo, base) == ["a.py", "b.py", "new.py", "sub/deep.py"]
    assert eng.changed_files_from_git(repo, base, include_uncommitted=False) == ["a.py"]


def test_changed_files_from_git_reports_renames_and_bad_baselines(eng, tmp_path) -> None:
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "old.py").write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", "old.py", "new.py")  # staged rename
    assert eng.changed_files_from_git(repo, base) == ["new.py", "old.py"]
    with pytest.raises(eng.GitError):
        eng.changed_files_from_git(repo, "not-a-revision")
    with pytest.raises(eng.GitError):
        eng.changed_files_from_git(repo, "")
    with pytest.raises(eng.GitError):
        eng.changed_files_from_git(tmp_path / "not-a-repo", base)


# --------------------------------------------------------------------------- #
# 6. the CLI round-trips
# --------------------------------------------------------------------------- #

def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI_PATH), *args], capture_output=True,
                          encoding="utf-8", errors="replace", timeout=120)


def test_cli_build_stats_select_pins_round_trip(ws) -> None:
    _write_deploy(ws, {"always_run": ["*health*"], "full_suite_at": ["phase-8"]})
    built = _cli("build", "--workspace", str(ws), "--json")
    assert built.returncode == 0, built.stderr
    index = json.loads(built.stdout)
    assert index["schema"] == "test-index/v1" and len(index["tests"]) == 8
    assert (ws / ".architect-team" / "test-index.json").is_file()

    st = _cli("stats", "--workspace", str(ws), "--json")
    assert st.returncode == 0, st.stderr
    stats = json.loads(st.stdout)
    assert stats["total"] == 8 and stats["index_present"] is True
    assert stats["last_selection"] is None

    sel = _cli("select", "--workspace", str(ws), "--phase", "3",
               "--changed-files", "fixpkg/api.py", "--json")
    assert sel.returncode == 0, sel.stderr
    record = json.loads(sel.stdout)
    assert record["schema"] == "test-selection/v1"
    assert {API_TEST, UNMAPPED, HEALTH_E2E} <= _selected_ids(record)
    assert record["record_path"].startswith(".architect-team/test-selection-")
    assert (ws / record["record_path"]).is_file()

    again = json.loads(_cli("stats", "--workspace", str(ws), "--json").stdout)
    assert again["last_selection"]["path"] == record["record_path"]

    pins = _cli("pins", "--workspace", str(ws), "--json")
    assert pins.returncode == 0, pins.stderr
    payload = json.loads(pins.stdout)
    assert payload["always_run"] == ["*health*"]
    assert payload["full_suite_at"] == ["phase-8"]
    assert payload["full_suite_phases_effective"] == ["8"]
    assert payload["config_present"] is True


def test_cli_select_with_a_git_baseline(ws) -> None:
    _git(ws, "init", "-q", "-b", "main")
    _git(ws, "add", ".")
    _git(ws, "commit", "-q", "-m", "base")
    base = _git(ws, "rev-parse", "HEAD")
    (ws / "fixpkg" / "pricing.py").write_text(
        (ws / "fixpkg" / "pricing.py").read_text(encoding="utf-8") + "\nTAX = 1\n",
        encoding="utf-8")
    sel = _cli("select", "--workspace", str(ws), "--phase", "3", "--baseline", base, "--json")
    assert sel.returncode == 0, sel.stderr
    record = json.loads(sel.stdout)
    assert record["baseline"] == base
    assert record["changed_files"] == ["fixpkg/pricing.py"]
    assert {PRICING_TEST, API_TEST, UNMAPPED} <= _selected_ids(record)
    assert MODELS_TEST not in _selected_ids(record)


def test_cli_human_output_and_usage_errors(ws) -> None:
    human = _cli("build", "--workspace", str(ws))
    assert human.returncode == 0, human.stderr
    assert "test index: 8 tests" in human.stdout
    assert human.stdout.isascii()
    no_changes = _cli("select", "--workspace", str(ws), "--phase", "3")
    assert no_changes.returncode == 2
    assert "usage" in no_changes.stdout
    bad_ws = _cli("stats", "--workspace", str(ws / "missing"), "--json")
    assert bad_ws.returncode == 2
    bad_baseline = _cli("select", "--workspace", str(ws), "--phase", "3",
                        "--baseline", "deadbeef", "--json")
    assert bad_baseline.returncode == 2
    full = _cli("select", "--workspace", str(ws), "--phase", "8", "--changed-files",
                "fixpkg/api.py", "--no-write")
    assert full.returncode == 0 and "FULL SUITE 8 of 8" in full.stdout
    assert not list((ws / ".architect-team").glob("test-selection-*.json"))


def test_cli_pins_defaults_when_no_config(ws) -> None:
    pins = json.loads(_cli("pins", "--workspace", str(ws), "--json").stdout)
    assert pins == {
        "config": ".architect-team-deploy.json", "config_present": False,
        "always_run": [], "full_suite_at": ["phase-8"],
        "full_suite_phases_effective": ["8"], "note": pins["note"],
    }
    assert "never lower" in pins["note"]


# --------------------------------------------------------------------------- #
# 7. the pytest witness plugin, for real
# --------------------------------------------------------------------------- #

def test_pytest_witness_records_executed_files_and_upgrades_the_index(eng, ws) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["CT6_TEST_INDEX_WORKSPACE"] = str(ws)
    env.pop("PYTEST_ADDOPTS", None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "scripts.test_index.pytest_witness",
         "-p", "no:cacheprovider", "tests"],
        cwd=str(ws), env=env, capture_output=True, encoding="utf-8", errors="replace",
        timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    wpath = ws / ".architect-team" / "test-witness.json"
    assert wpath.is_file()
    witness = json.loads(wpath.read_text(encoding="utf-8"))
    assert witness["schema"] == "test-witness/v1"
    assert set(witness["tests"]) == PY_TEST_IDS
    # The witness is TIGHTER than the static graph: test_price_for never runs a
    # line of models.py (the dataclass __init__ it calls is exec-generated code
    # with no file), so only pricing.py is attributed. The static mapping said
    # models.py too -- a hypothesis the witness narrows.
    assert witness["tests"][PRICING_TEST]["files"] == ["fixpkg/pricing.py"]
    assert witness["tests"][API_TEST]["files"] == ["fixpkg/api.py", "fixpkg/models.py",
                                                   "fixpkg/pricing.py"]
    assert witness["tests"][MODELS_TEST]["files"] == ["fixpkg/models.py"]
    # a test that touches ONLY exec-generated code attributes nothing
    assert witness["tests"]["tests/test_models.py::TestItem::test_equality"]["files"] == []
    assert witness["tests"][UNMAPPED]["files"] == []
    for rec in witness["tests"].values():
        assert isinstance(rec["duration_s"], float) and rec["duration_s"] >= 0
        assert not any(f.startswith("tests/") for f in rec["files"])

    index = eng.build(ws, write=False)  # the default witness location
    tests = _by_id(index)
    assert index["sources"]["witness"] == ".architect-team/test-witness.json"
    for tid in (PRICING_TEST, API_TEST, MODELS_TEST):
        assert tests[tid]["trust"] == "runtime-witnessed", tid
    assert tests[PRICING_TEST]["files"] == ["fixpkg/pricing.py"]
    # the two empty observations keep their static / unknown mapping
    assert tests["tests/test_models.py::TestItem::test_equality"]["trust"] == "static"
    assert tests["tests/test_models.py::TestItem::test_equality"]["files"] == [
        "fixpkg/__init__.py", "fixpkg/models.py"]
    assert tests[UNMAPPED]["trust"] == "unknown"
    for tid in PY_TEST_IDS:
        assert tests[tid]["duration_s"] is not None, tid
    assert tests[HEALTH_E2E]["trust"] == "static"
    st = eng.stats(index)
    assert st["by_trust"] == {"static": 4, "runtime-witnessed": 3, "unknown": 1}
    assert st["with_duration"] == 5


def test_pytest_witness_merges_into_an_existing_record(ws) -> None:
    wpath = ws / ".architect-team" / "test-witness.json"
    wpath.parent.mkdir()
    wpath.write_text(json.dumps({"schema": "test-witness/v1", "tests": {
        "tests/test_other.py::test_kept": {"files": ["fixpkg/models.py"], "duration_s": 1.0}}}),
        encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.pop("PYTEST_ADDOPTS", None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "scripts.test_index.pytest_witness",
         "-p", "no:cacheprovider", "--ct6-witness-workspace", str(ws),
         "--ct6-witness-out", str(wpath), "tests/test_pricing.py"],
        cwd=str(ws), env=env, capture_output=True, encoding="utf-8", errors="replace",
        timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    witness = json.loads(wpath.read_text(encoding="utf-8"))
    assert set(witness["tests"]) == {"tests/test_other.py::test_kept", PRICING_TEST}
    assert witness["tests"]["tests/test_other.py::test_kept"]["duration_s"] == 1.0


# --------------------------------------------------------------------------- #
# 8. deploy_config -- the new readers
# --------------------------------------------------------------------------- #

def test_deploy_config_test_pins_default_when_absent(deploy_config, tmp_path) -> None:
    assert deploy_config.tests_always_run(tmp_path) == []
    assert deploy_config.tests_full_suite_at(tmp_path) == ["phase-8"]
    assert deploy_config.DEFAULT_FULL_SUITE_AT == ("phase-8",)


def test_deploy_config_test_pins_read_the_block(deploy_config, tmp_path) -> None:
    _write_deploy(tmp_path, {"always_run": ["tests/test_billing*", " e2e/prod-checks/* ", 3, ""],
                             "full_suite_at": ["phase-5", "phase-8"]})
    assert deploy_config.tests_always_run(tmp_path) == ["tests/test_billing*", "e2e/prod-checks/*"]
    assert deploy_config.tests_full_suite_at(tmp_path) == ["phase-5", "phase-8"]


def test_deploy_config_test_pins_fail_safe_on_malformed_shapes(deploy_config, tmp_path) -> None:
    _write_deploy(tmp_path, "not-a-dict")
    assert deploy_config.tests_always_run(tmp_path) == []
    assert deploy_config.tests_full_suite_at(tmp_path) == ["phase-8"]
    _write_deploy(tmp_path, {"always_run": "tests/*", "full_suite_at": "phase-5"})
    assert deploy_config.tests_always_run(tmp_path) == []
    assert deploy_config.tests_full_suite_at(tmp_path) == ["phase-8"]
    (tmp_path / ".architect-team-deploy.json").write_text("{ broken", encoding="utf-8")
    assert deploy_config.tests_always_run(tmp_path) == []
    assert deploy_config.tests_full_suite_at(tmp_path) == ["phase-8"]
    # an explicit empty list is the human's statement and is returned as such
    _write_deploy(tmp_path, {"full_suite_at": []})
    assert deploy_config.tests_full_suite_at(tmp_path) == []


def test_deploy_config_readers_never_write(deploy_config, tmp_path) -> None:
    deploy_config.tests_always_run(tmp_path)
    deploy_config.tests_full_suite_at(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_example_template_carries_the_tests_block_and_the_never_lower_sentence() -> None:
    data = json.loads(EXAMPLE_DEPLOY.read_text(encoding="utf-8"))
    assert data["tests"] == {"always_run": [], "full_suite_at": ["phase-8"]}
    comment = data["_comment"].lower()
    assert "tests.always_run" in comment and "tests.full_suite_at" in comment
    assert "never lower" in comment
    assert "human-owned" in comment


# --------------------------------------------------------------------------- #
# 9. the reference + source hygiene
# --------------------------------------------------------------------------- #

def test_reference_exists_starts_with_stop_and_stays_short() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("> **STOP.**")
    assert len(lines) < 150, f"reference is {len(lines)} lines; the budget is under 150"
    low = text.lower()
    for needle in ("phase 3", "phase 5", "phase 8", "scripts/test_index/cli.py",
                   "unknown mapping means run", "never lowered", "test-selection-",
                   "full-suite-phase", "not selectable", "entire dev suite", "reversed",
                   "pytest_witness", "dynamic dispatch", "coarser"):
        assert needle in low, f"reference lacks {needle!r}"
    assert "## Honest boundaries" in text
    assert "## Bootstrapping" in text


@pytest.mark.parametrize("path", [PKG / "__init__.py", ENGINE_PATH, CLI_PATH, WITNESS_PLUGIN_PATH])
def test_module_sources_are_ascii_and_parse(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.isascii(), f"{path.name} carries non-ASCII source"
    ast.parse(text)
    assert "import yaml" not in text and "import requests" not in text


def test_engine_has_no_import_time_side_effects(eng) -> None:
    assert not (REPO_ROOT / ".architect-team" / "test-index.json").exists()
    assert set(eng.__all__) >= {"build", "select", "stats", "changed_files_from_git"}
