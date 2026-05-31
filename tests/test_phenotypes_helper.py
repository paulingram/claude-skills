"""Unit tests for scripts/phenotypes/phenotypes.py (the phenotype engine).

Module loaded via importlib (matches the teams_mode / locks test pattern). Exercises discover /
validate / match / load / emit against a synthetic phenotypes dir AND the real user-management record.
"""
import importlib.util
import json
from pathlib import Path

import pytest


def _load_module(plugin_root: Path):
    path = plugin_root / "scripts" / "phenotypes" / "phenotypes.py"
    spec = importlib.util.spec_from_file_location("phenotypes_module_under_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ph(plugin_root: Path):
    return _load_module(plugin_root)


def _manifest(label, keywords, phrases=None, kind="pair"):
    return {
        "schema_version": 1,
        "label": label,
        "name": label.replace("-", " ").title(),
        "version": "1.0.0",
        "kind": kind,
        "summary": f"{label} phenotype summary, long enough to be meaningful.",
        "components": {"backend": {"language": "python"}},
        "match": {"keywords": keywords, "trigger_phrases": phrases or []},
        "provenance": {"absorbed_from": [], "absorbed_by": "human", "generalized": True},
        "blueprint": "blueprint.md",
    }


@pytest.fixture
def synthetic(tmp_path: Path) -> Path:
    """A two-record phenotypes dir; user-management carries an emittable scaffold."""
    base = tmp_path / "phenotypes"

    um = base / "user-management"
    (um / "scaffold").mkdir(parents=True)
    (um / "phenotype.json").write_text(
        json.dumps(_manifest("user-management", ["user management", "login", "rbac"],
                             ["i want a user management system"])
                   | {"scaffold": {"manifest": "scaffold/scaffold.manifest.json",
                                   "parameters": [{"name": "service_name", "required": True},
                                                  {"name": "db_name", "default": "appdb"}]}}),
        encoding="utf-8",
    )
    (um / "blueprint.md").write_text("## Overview\nuser mgmt\n", encoding="utf-8")
    (um / "scaffold" / "scaffold.manifest.json").write_text(
        json.dumps({
            "schema_version": 1,
            "parameters": [{"name": "service_name", "required": True},
                           {"name": "db_name", "default": "appdb"}],
            "files": [{"src": "app.py.tmpl", "dest": "{{service_name}}/app.py"}],
        }),
        encoding="utf-8",
    )
    (um / "scaffold" / "app.py.tmpl").write_text(
        "SERVICE = '{{service_name}}'\nDB = '{{db_name}}'\n", encoding="utf-8")

    cm = base / "config-mgmt"
    cm.mkdir(parents=True)
    (cm / "phenotype.json").write_text(
        json.dumps(_manifest("config-mgmt", ["config", "terraform", "opentofu"], kind="singleton")),
        encoding="utf-8",
    )
    (cm / "blueprint.md").write_text("## Overview\nconfig\n", encoding="utf-8")
    return base


# --- discovery + validation ------------------------------------------------

def test_discover_finds_records_sorted(ph, synthetic):
    labels = [p["label"] for p in ph.discover_phenotypes(synthetic)]
    assert labels == ["config-mgmt", "user-management"]


def test_validate_valid_record(ph):
    assert ph.validate_phenotype(_manifest("x", ["k"]), dirname="x") == []


def test_validate_label_dir_mismatch(ph):
    errs = ph.validate_phenotype(_manifest("x", ["k"]), dirname="y")
    assert any("does not match directory" in e for e in errs)


def test_validate_missing_required_key(ph):
    bad = _manifest("x", ["k"])
    del bad["match"]
    assert any("match" in e for e in ph.validate_phenotype(bad, dirname="x"))


def test_validate_bad_kind(ph):
    bad = _manifest("x", ["k"], kind="trio")
    assert any("kind" in e for e in ph.validate_phenotype(bad, dirname="x"))


def test_validate_empty_keywords(ph):
    bad = _manifest("x", [])
    assert any("keywords" in e for e in ph.validate_phenotype(bad, dirname="x"))


# --- matching --------------------------------------------------------------

def test_match_ranks_relevant_first(ph, synthetic):
    results = ph.match_phenotype("I want a user management system with login", dir=synthetic)
    proposable = [r for r in results if r["score"] > 0]
    assert proposable and proposable[0]["label"] == "user-management"
    assert "login" in proposable[0]["matched_keywords"]


def test_match_unrelated_scores_zero(ph, synthetic):
    results = ph.match_phenotype("render a real-time 3d physics simulation", dir=synthetic)
    assert all(r["score"] == 0 for r in results)


def test_match_is_deterministic(ph, synthetic):
    a = ph.match_phenotype("user management login", dir=synthetic)
    b = ph.match_phenotype("user management login", dir=synthetic)
    assert a == b


# --- load ------------------------------------------------------------------

def test_load_phenotype(ph, synthetic):
    rec = ph.load_phenotype("user-management", dir=synthetic)
    assert rec["label"] == "user-management"


def test_load_missing_raises(ph, synthetic):
    with pytest.raises(FileNotFoundError):
        ph.load_phenotype("does-not-exist", dir=synthetic)


# --- emit ------------------------------------------------------------------

def test_emit_dry_run_lists_without_writing(ph, synthetic, tmp_path):
    target = tmp_path / "out"
    written = ph.emit_scaffold("user-management", target, {"service_name": "svc"},
                               dir=synthetic, dry_run=True)
    assert len(written) == 1
    assert not target.exists()  # nothing written


def test_emit_substitutes_content_and_path(ph, synthetic, tmp_path):
    target = tmp_path / "out"
    ph.emit_scaffold("user-management", target, {"service_name": "svc"}, dir=synthetic)
    emitted = target / "svc" / "app.py"          # {{service_name}} substituted in the dest path
    assert emitted.exists()
    text = emitted.read_text(encoding="utf-8")
    assert "SERVICE = 'svc'" in text             # content substitution
    assert "DB = 'appdb'" in text                # default param applied
    assert "{{" not in text                      # no residual placeholders


def test_emit_missing_required_param_raises(ph, synthetic, tmp_path):
    with pytest.raises(ValueError):
        ph.emit_scaffold("user-management", tmp_path / "out", {}, dir=synthetic)


# --- against the REAL user-management record -------------------------------

def test_real_user_management_validates(ph, plugin_root):
    obj = json.loads(
        (plugin_root / "phenotypes" / "user-management" / "phenotype.json").read_text(encoding="utf-8"))
    assert ph.validate_phenotype(obj, dirname="user-management") == []


def test_real_user_management_matches(ph, plugin_root):
    results = ph.match_phenotype("I want a user management system",
                                 dir=plugin_root / "phenotypes")
    proposable = [r for r in results if r["score"] > 0]
    assert proposable and proposable[0]["label"] == "user-management"


def test_real_scaffold_emits_clean(ph, plugin_root, tmp_path):
    written = ph.emit_scaffold("user-management", tmp_path / "real",
                               {"service_name": "acme-users", "project_name": "acme"},
                               dir=plugin_root / "phenotypes", dry_run=True)
    assert len(written) >= 12  # representative scaffold across backend/frontend/deploy
