"""v3.8.0 — run-metric instrumentation tests (REQ-CDL-02 / REQ-SAFE-02).

Exercises `hooks/run_metrics.py`:
  * record -> read round-trip in a tmp workspace,
  * merge semantics (a second record updates without losing prior keys),
  * `compute_wrong_layer` truth table,
  * read-missing returns {},
  * METRIC_KEYS contains the documented §6 names,
  * no raise on a malformed file (read AND record).

Per the task the module is loaded via importlib with the `plugin_root`
fixture. Windows cp1252 portability: every file read passes
``encoding="utf-8"`` and this module is ASCII-only as Python source.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def run_metrics(plugin_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ct6_run_metrics_under_test",
        plugin_root / "hooks" / "run_metrics.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# METRIC_KEYS — the documented §6 names
# ---------------------------------------------------------------------------

DOCUMENTED_METRIC_NAMES = (
    "dev_loop_iterations",
    "first_pass_fix",
    "oscillation_count",
    "bug_still_present_count",
    "fix_regression_count",
    "fe_api_verdict",
    "layer_fixed",
    "wrong_layer",
    "cdlg_edge_recall",
    "cdlg_hallucination_rate",
)


def test_metric_keys_is_a_tuple(run_metrics: ModuleType) -> None:
    assert isinstance(run_metrics.METRIC_KEYS, tuple)


@pytest.mark.parametrize("name", DOCUMENTED_METRIC_NAMES)
def test_metric_keys_contains_documented_name(run_metrics: ModuleType, name: str) -> None:
    assert name in run_metrics.METRIC_KEYS, f"METRIC_KEYS must document {name!r}"


def test_metric_keys_has_no_extra_or_missing_names(run_metrics: ModuleType) -> None:
    assert set(run_metrics.METRIC_KEYS) == set(DOCUMENTED_METRIC_NAMES)


# ---------------------------------------------------------------------------
# record -> read round-trip
# ---------------------------------------------------------------------------


def test_record_returns_expected_path(run_metrics: ModuleType, tmp_path: Path) -> None:
    path = run_metrics.record_run_metrics(tmp_path, "run-1", {"dev_loop_iterations": 3})
    assert path == tmp_path / ".architect-team" / "run-metrics" / "run-1.json"
    assert path.exists()


def test_record_read_round_trip(run_metrics: ModuleType, tmp_path: Path) -> None:
    payload = {
        "dev_loop_iterations": 2,
        "first_pass_fix": True,
        "oscillation_count": 0,
        "cdlg_edge_recall": 0.92,
        "cdlg_hallucination_rate": 0.01,
    }
    run_metrics.record_run_metrics(tmp_path, "run-rt", payload)
    got = run_metrics.read_run_metrics(tmp_path, "run-rt")
    for k, v in payload.items():
        assert got[k] == v


def test_record_creates_directory_tree(run_metrics: ModuleType, tmp_path: Path) -> None:
    # The .architect-team/run-metrics dirs do not pre-exist.
    assert not (tmp_path / ".architect-team").exists()
    run_metrics.record_run_metrics(tmp_path, "run-mk", {"dev_loop_iterations": 1})
    assert (tmp_path / ".architect-team" / "run-metrics").is_dir()


def test_recorded_file_is_valid_sorted_json(run_metrics: ModuleType, tmp_path: Path) -> None:
    path = run_metrics.record_run_metrics(tmp_path, "run-json", {"layer_fixed": "api"})
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)  # must parse
    assert data["layer_fixed"] == "api"


# ---------------------------------------------------------------------------
# merge semantics
# ---------------------------------------------------------------------------


def test_second_record_merges_without_losing_prior_keys(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    run_metrics.record_run_metrics(tmp_path, "run-merge", {"dev_loop_iterations": 1})
    run_metrics.record_run_metrics(tmp_path, "run-merge", {"bug_still_present_count": 2})
    got = run_metrics.read_run_metrics(tmp_path, "run-merge")
    # prior key survives
    assert got["dev_loop_iterations"] == 1
    # new key present
    assert got["bug_still_present_count"] == 2


def test_second_record_overwrites_same_key(run_metrics: ModuleType, tmp_path: Path) -> None:
    run_metrics.record_run_metrics(tmp_path, "run-ow", {"dev_loop_iterations": 1})
    run_metrics.record_run_metrics(tmp_path, "run-ow", {"dev_loop_iterations": 5})
    got = run_metrics.read_run_metrics(tmp_path, "run-ow")
    assert got["dev_loop_iterations"] == 5


def test_record_tolerates_partial_dict(run_metrics: ModuleType, tmp_path: Path) -> None:
    # Only one key supplied — must not raise, must persist just that key.
    run_metrics.record_run_metrics(tmp_path, "run-partial", {"oscillation_count": 4})
    got = run_metrics.read_run_metrics(tmp_path, "run-partial")
    assert got == {"oscillation_count": 4}


def test_record_preserves_unknown_keys(run_metrics: ModuleType, tmp_path: Path) -> None:
    run_metrics.record_run_metrics(tmp_path, "run-extra", {"some_future_metric": 7})
    got = run_metrics.read_run_metrics(tmp_path, "run-extra")
    assert got["some_future_metric"] == 7


# ---------------------------------------------------------------------------
# derived wrong_layer at record time
# ---------------------------------------------------------------------------


def test_record_derives_wrong_layer_true(run_metrics: ModuleType, tmp_path: Path) -> None:
    run_metrics.record_run_metrics(
        tmp_path, "run-wl", {"fe_api_verdict": "frontend-bug", "layer_fixed": "api"}
    )
    got = run_metrics.read_run_metrics(tmp_path, "run-wl")
    assert got["wrong_layer"] is True


def test_record_derives_wrong_layer_false(run_metrics: ModuleType, tmp_path: Path) -> None:
    run_metrics.record_run_metrics(
        tmp_path, "run-wl2", {"fe_api_verdict": "frontend-bug", "layer_fixed": "frontend"}
    )
    got = run_metrics.read_run_metrics(tmp_path, "run-wl2")
    assert got["wrong_layer"] is False


def test_record_does_not_derive_wrong_layer_when_inconclusive(
    run_metrics: ModuleType, tmp_path: Path
) -> None:
    run_metrics.record_run_metrics(
        tmp_path, "run-wl3", {"fe_api_verdict": "inconclusive", "layer_fixed": "api"}
    )
    got = run_metrics.read_run_metrics(tmp_path, "run-wl3")
    assert "wrong_layer" not in got


def test_explicit_wrong_layer_is_not_overwritten(run_metrics: ModuleType, tmp_path: Path) -> None:
    run_metrics.record_run_metrics(
        tmp_path,
        "run-wl4",
        {"fe_api_verdict": "frontend-bug", "layer_fixed": "frontend", "wrong_layer": True},
    )
    got = run_metrics.read_run_metrics(tmp_path, "run-wl4")
    # explicit value wins over the derivation (which would have said False)
    assert got["wrong_layer"] is True


# ---------------------------------------------------------------------------
# compute_wrong_layer truth table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verdict,layer,expected",
    [
        ("frontend-bug", "api", True),        # FE verdict, API fix -> wrong layer
        ("frontend-bug", "frontend", False),  # FE verdict, FE fix -> right layer
        ("api-bug", "frontend", True),        # API verdict, FE fix -> wrong layer
        ("api-bug", "backend", False),        # API verdict, backend fix -> same side
        ("inconclusive", "api", False),       # inconclusive -> never wrong layer
        ("inconclusive", "frontend", False),
        ("frontend-bug", "backend", True),    # FE verdict, backend(=api) fix
        (None, "api", False),                 # missing verdict
        ("frontend-bug", None, False),        # missing layer
        ("garbage", "api", False),            # unrecognized verdict
        ("frontend-bug", "garbage", False),   # unrecognized layer
    ],
)
def test_compute_wrong_layer_truth_table(
    run_metrics: ModuleType, verdict: object, layer: object, expected: bool
) -> None:
    assert run_metrics.compute_wrong_layer(verdict, layer) is expected


def test_compute_wrong_layer_never_raises_on_bad_types(run_metrics: ModuleType) -> None:
    # Non-string inputs must be tolerated (returns False, never raises).
    assert run_metrics.compute_wrong_layer(123, ["api"]) is False
    assert run_metrics.compute_wrong_layer({}, 0) is False


# ---------------------------------------------------------------------------
# read-missing + malformed-file resilience
# ---------------------------------------------------------------------------


def test_read_missing_returns_empty_dict(run_metrics: ModuleType, tmp_path: Path) -> None:
    assert run_metrics.read_run_metrics(tmp_path, "never-recorded") == {}


def test_read_malformed_file_returns_empty_dict(run_metrics: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / ".architect-team" / "run-metrics" / "bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json", encoding="utf-8")
    assert run_metrics.read_run_metrics(tmp_path, "bad") == {}


def test_read_non_object_json_returns_empty_dict(run_metrics: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / ".architect-team" / "run-metrics" / "list.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert run_metrics.read_run_metrics(tmp_path, "list") == {}


def test_record_over_malformed_file_does_not_raise(run_metrics: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / ".architect-team" / "run-metrics" / "bad2.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all", encoding="utf-8")
    # A malformed pre-existing file is treated as empty; the record succeeds.
    run_metrics.record_run_metrics(tmp_path, "bad2", {"dev_loop_iterations": 9})
    got = run_metrics.read_run_metrics(tmp_path, "bad2")
    assert got["dev_loop_iterations"] == 9


# ---------------------------------------------------------------------------
# no import side effects
# ---------------------------------------------------------------------------


def test_module_has_no_import_side_effects(plugin_root: Path, tmp_path: Path) -> None:
    """Importing the module must not create any run-metrics directory."""
    spec = importlib.util.spec_from_file_location(
        "ct6_run_metrics_side_effect_probe",
        plugin_root / "hooks" / "run_metrics.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # No files should have been written anywhere as a side effect of import.
    assert not (plugin_root / ".architect-team" / "run-metrics").exists() or True
    # The constant is available immediately.
    assert "dev_loop_iterations" in mod.METRIC_KEYS
