"""Tests for the v2.18.0 Layer 3 tool: verify_discipline_registry_current.

Covers the 3 named severities (`discipline-registry-missing`,
`discipline-not-applied`, `discipline-stale`), per-discipline detection
helpers, registry I/O round-trips, fixture round-trip, and determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.discipline_registry import (
    DISCIPLINE_CATALOG,
    REGISTRY_RELATIVE_PATH,
    SCHEMA_VERSION,
    freshness_check,
    read_registry,
    record_application,
    write_registry,
)
from hooks.vao_tools import verify_discipline_registry_current

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "discipline-registry-not-applied.json"


def _materialize(workspace: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# ---- module constants ----


def test_schema_version_is_1_0() -> None:
    assert SCHEMA_VERSION == "1.0"


def test_registry_path_is_under_architect_team() -> None:
    assert REGISTRY_RELATIVE_PATH.startswith(".architect-team/")
    assert REGISTRY_RELATIVE_PATH.endswith(".json")


def test_catalog_has_four_initial_entries() -> None:
    assert len(DISCIPLINE_CATALOG) == 4


def test_catalog_includes_prod_safe_test_classification() -> None:
    ids = {e["discipline"] for e in DISCIPLINE_CATALOG}
    assert "prod-safe-test-classification" in ids


def test_catalog_includes_three_sr_route_disciplines() -> None:
    sr_route = [e for e in DISCIPLINE_CATALOG if not e["auto_apply_safe"]]
    ids = {e["discipline"] for e in sr_route}
    assert ids == {"live-data-wiring", "multi-persona-path-coverage", "affordance-coverage"}


def test_only_one_discipline_is_auto_apply_safe_initially() -> None:
    auto = [e for e in DISCIPLINE_CATALOG if e["auto_apply_safe"]]
    assert len(auto) == 1
    assert auto[0]["discipline"] == "prod-safe-test-classification"


def test_each_catalog_entry_carries_required_keys() -> None:
    required = {"discipline", "ct6_version", "auto_apply_safe", "detect_fn", "summary_kind"}
    for entry in DISCIPLINE_CATALOG:
        assert required.issubset(set(entry.keys())), f"missing keys in {entry['discipline']!r}"


# ---- registry I/O ----


def test_read_registry_returns_empty_shell_when_missing(tmp_path: Path) -> None:
    reg = read_registry(tmp_path)
    assert reg["schema_version"] == SCHEMA_VERSION
    assert reg["disciplines_applied"] == []
    assert reg["ct6_version_last_seen"] is None


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    registry = {
        "schema_version": SCHEMA_VERSION,
        "ct6_version_last_seen": "2.17.0",
        "disciplines_applied": [],
        "last_freshness_check": None,
    }
    write_registry(tmp_path, registry)
    read = read_registry(tmp_path)
    assert read["ct6_version_last_seen"] == "2.17.0"


def test_record_application_appends_entry(tmp_path: Path) -> None:
    reg = record_application(
        tmp_path,
        "prod-safe-test-classification",
        ct6_version="2.17.0",
        artifact_path=".architect-team/test-prod-safety/foo.json",
        summary={"prod_safe": 12, "not_prod_safe": 4},
    )
    entries = [d for d in reg["disciplines_applied"] if d["discipline"] == "prod-safe-test-classification"]
    assert len(entries) == 1
    assert entries[0]["summary"]["prod_safe"] == 12


def test_record_application_replaces_prior_entry(tmp_path: Path) -> None:
    record_application(tmp_path, "prod-safe-test-classification", ct6_version="2.17.0", summary={"prod_safe": 1})
    record_application(tmp_path, "prod-safe-test-classification", ct6_version="2.17.0", summary={"prod_safe": 999})
    reg = read_registry(tmp_path)
    entries = [d for d in reg["disciplines_applied"] if d["discipline"] == "prod-safe-test-classification"]
    assert len(entries) == 1
    assert entries[0]["summary"]["prod_safe"] == 999


# ---- detector: prod-safe-test-classification ----


def test_no_tests_means_trivially_applied(tmp_path: Path) -> None:
    findings = freshness_check(tmp_path)
    discipline_findings = [f for f in findings if f["discipline"] == "prod-safe-test-classification"]
    assert discipline_findings == []  # no tests = applied


def test_unannotated_tests_trigger_not_applied(tmp_path: Path) -> None:
    _materialize(tmp_path, {
        "tests/foo.spec.ts": "test('a', async ({page}) => { await page.goto('/'); });"
    })
    findings = freshness_check(tmp_path)
    classifier_findings = [f for f in findings if f["discipline"] == "prod-safe-test-classification"]
    assert len(classifier_findings) == 1
    assert classifier_findings[0]["severity"] == "discipline-not-applied"
    assert classifier_findings[0]["auto_apply_safe"] is True


def test_annotated_tests_count_as_applied(tmp_path: Path) -> None:
    _materialize(tmp_path, {
        "tests/foo.spec.ts": "// @prod-safe\ntest('a', async ({page}) => { await page.goto('/'); });"
    })
    findings = freshness_check(tmp_path)
    assert all(f["discipline"] != "prod-safe-test-classification" for f in findings)


def test_partial_annotation_still_triggers_not_applied(tmp_path: Path) -> None:
    _materialize(tmp_path, {
        "tests/a.spec.ts": "// @prod-safe\ntest('a', () => {});",
        "tests/b.spec.ts": "test('b', () => {});",  # unannotated
    })
    findings = freshness_check(tmp_path)
    classifier_findings = [f for f in findings if f["discipline"] == "prod-safe-test-classification"]
    assert len(classifier_findings) == 1


# ---- detector: multi-persona-path-coverage ----


def test_no_persona_inventory_triggers_not_applied(tmp_path: Path) -> None:
    findings = freshness_check(tmp_path)
    persona_findings = [f for f in findings if f["discipline"] == "multi-persona-path-coverage"]
    assert len(persona_findings) == 1
    assert persona_findings[0]["auto_apply_safe"] is False
    assert persona_findings[0]["sr_origin_kind"] == "persona-inventory-required"


def test_populated_persona_inventory_counts_as_applied(tmp_path: Path) -> None:
    _materialize(tmp_path, {
        ".architect-team/persona-inventory.json": json.dumps({"personas": [{"persona_id": "u"}]})
    })
    findings = freshness_check(tmp_path)
    assert all(f["discipline"] != "multi-persona-path-coverage" for f in findings)


# ---- detector: affordance-coverage ----


def test_file_upload_signature_triggers_not_applied(tmp_path: Path) -> None:
    _materialize(tmp_path, {
        "src/Upload.tsx": '<input type="file" />'
    })
    findings = freshness_check(tmp_path)
    aff_findings = [f for f in findings if f["discipline"] == "affordance-coverage"]
    assert len(aff_findings) == 1
    assert aff_findings[0]["sr_origin_kind"] == "affordance-coverage-gap"


# ---- 16th Layer 3 tool ----


def test_tool_returns_standard_verdict_shape(tmp_path: Path) -> None:
    v = verify_discipline_registry_current(tmp_path)
    assert v["tool"] == "verify-discipline-registry-current"
    assert "valid" in v
    assert "gaps" in v
    assert "verdict_at" in v


def test_tool_fires_registry_missing_when_no_registry_AND_gaps(tmp_path: Path) -> None:
    # multi-persona-path-coverage finding fires by default
    v = verify_discipline_registry_current(tmp_path)
    sevs = {g["severity"] for g in v["gaps"]}
    assert "discipline-registry-missing" in sevs


def test_tool_does_not_fire_registry_missing_when_clean_workspace(tmp_path: Path) -> None:
    # Pre-populate persona inventory so no findings fire at all
    _materialize(tmp_path, {
        ".architect-team/persona-inventory.json": json.dumps({"personas": [{"persona_id": "u"}]})
    })
    v = verify_discipline_registry_current(tmp_path)
    sevs = {g["severity"] for g in v["gaps"]}
    assert "discipline-registry-missing" not in sevs
    assert v["valid"] is True


def test_tool_each_gap_carries_remediation(tmp_path: Path) -> None:
    v = verify_discipline_registry_current(tmp_path)
    for g in v["gaps"]:
        assert "remediation" in g
        assert "v2.18.0" in g["remediation"] or "discipline" in g["remediation"]


def test_tool_persists_to_out_path(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    verify_discipline_registry_current(tmp_path, out_path=str(out))
    assert out.exists()
    persisted = json.loads(out.read_text())
    assert persisted["tool"] == "verify-discipline-registry-current"


# ---- fixture round-trip ----


def test_canonical_fixture_bad_fires_expected_severities(tmp_path: Path) -> None:
    fx = json.loads(FIXTURE.read_text())
    _materialize(tmp_path, fx["workspace_synthetic_files"])
    v = verify_discipline_registry_current(tmp_path)
    sevs = {g["severity"] for g in v["gaps"]}
    expected = set(fx["_meta"]["expected_severities"])
    assert expected.issubset(sevs)
    disciplines = {g.get("discipline") for g in v["gaps"] if g.get("discipline")}
    assert set(fx["_meta"]["expected_disciplines_unapplied"]).issubset(disciplines)


def test_canonical_fixture_corrected_shape_passes(tmp_path: Path) -> None:
    fx = json.loads(FIXTURE.read_text())
    # Materialize all corrected files EXCEPT the meta-note "_note" key
    files = {k: v for k, v in fx["_corrected_workspace_files"].items() if k != "_note"}
    _materialize(tmp_path, files)
    v = verify_discipline_registry_current(tmp_path)
    # Affordance + live-data still SR-route, may or may not fire depending on
    # synthetic content. What MUST be true: prod-safe-test-classification +
    # multi-persona-path-coverage are applied (no longer fire).
    sevs_by_discipline = {g.get("discipline"): g["severity"] for g in v["gaps"]}
    assert "prod-safe-test-classification" not in sevs_by_discipline
    assert "multi-persona-path-coverage" not in sevs_by_discipline


# ---- determinism ----


def test_output_is_deterministic_on_stable_workspace(tmp_path: Path) -> None:
    # Pre-seed an empty registry so the second call sees the same state as
    # the first (the first call's side-effect of writing last_freshness_check
    # would otherwise differ).
    _materialize(tmp_path, {"tests/foo.spec.ts": "test('a', () => {});"})
    write_registry(tmp_path, {
        "schema_version": SCHEMA_VERSION,
        "ct6_version_last_seen": None,
        "disciplines_applied": [],
        "last_freshness_check": None,
    })
    a = verify_discipline_registry_current(tmp_path)
    b = verify_discipline_registry_current(tmp_path)
    a_sevs = sorted((g["severity"], g.get("discipline")) for g in a["gaps"])
    b_sevs = sorted((g["severity"], g.get("discipline")) for g in b["gaps"])
    assert a_sevs == b_sevs
