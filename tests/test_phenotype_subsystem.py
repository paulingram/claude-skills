"""Structural tests for the phenotype subsystem — dir layout, the seed record, the skill, and the
trigger wiring across commands/skills."""
import importlib.util
import json
from pathlib import Path

REQUIRED_BLUEPRINT_SECTIONS = [
    "## Overview",
    "## Architecture",
    "## Components",
    "## Data model",
    "## Contract / API surface",
    "## How the parts interrelate",
    "## Deployment",
    "## Variation points",
    "## When to use / When NOT",
    "## Reuse-Decision hooks",
]


def _load_helper(plugin_root: Path):
    path = plugin_root / "scripts" / "phenotypes" / "phenotypes.py"
    spec = importlib.util.spec_from_file_location("phenotypes_mod_struct", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- subsystem layout ------------------------------------------------------

def test_phenotypes_dir_and_docs(plugin_root: Path):
    base = plugin_root / "phenotypes"
    assert base.is_dir()
    assert (base / "README.md").exists()
    assert (base / "SCHEMA.md").exists()


def test_helper_module_exists(plugin_root: Path):
    assert (plugin_root / "scripts" / "phenotypes" / "phenotypes.py").exists()


# --- the seed record -------------------------------------------------------

def test_user_management_record_present(plugin_root: Path):
    rec = plugin_root / "phenotypes" / "user-management"
    assert (rec / "phenotype.json").exists()
    assert (rec / "blueprint.md").exists()
    assert (rec / "scaffold" / "scaffold.manifest.json").exists()


def test_user_management_validates(plugin_root: Path):
    mod = _load_helper(plugin_root)
    obj = json.loads(_read(plugin_root / "phenotypes" / "user-management" / "phenotype.json"))
    assert mod.validate_phenotype(obj, dirname="user-management") == []


def test_blueprint_has_required_sections(plugin_root: Path):
    body = _read(plugin_root / "phenotypes" / "user-management" / "blueprint.md")
    for heading in REQUIRED_BLUEPRINT_SECTIONS:
        assert heading in body, f"blueprint missing required section {heading!r}"


def test_scaffold_manifest_srcs_all_exist(plugin_root: Path):
    rec = plugin_root / "phenotypes" / "user-management"
    manifest = json.loads(_read(rec / "scaffold" / "scaffold.manifest.json"))
    root = rec / "scaffold"
    for entry in manifest["files"]:
        assert (root / entry["src"]).exists(), f"manifest references missing src: {entry['src']}"


def test_no_secrets_or_real_account_ids_in_record(plugin_root: Path):
    """Generalized record must not embed real secrets / account-specifics (placeholders only)."""
    rec = plugin_root / "phenotypes" / "user-management"
    for path in rec.rglob("*"):
        if path.is_file():
            text = _read(path).lower()
            # The reference's concrete IdP / cloud-project bindings must have been stripped.
            assert "platform-488105" not in text          # the source GCP project id
            assert "auth0.com" not in text                 # concrete IdP tenant host


# --- the skill -------------------------------------------------------------

def test_phenotypes_skill_present_and_named(plugin_root: Path):
    skill = plugin_root / "skills" / "phenotypes" / "SKILL.md"
    assert skill.exists()
    assert "name: phenotypes" in _read(skill)


def test_skill_documents_absorb_capability(plugin_root: Path):
    assert "absorb" in _read(plugin_root / "skills" / "phenotypes" / "SKILL.md").lower()


# --- trigger wiring --------------------------------------------------------

def test_phenotype_flag_documented(plugin_root: Path):
    assert "--phenotype" in _read(plugin_root / "commands" / "architect-team.md")


def test_reuse_first_documents_phenotype_rung(plugin_root: Path):
    body = _read(plugin_root / "skills" / "reuse-first-design" / "SKILL.md").lower()
    assert "phenotype" in body


def test_pipeline_references_phenotype_seeding(plugin_root: Path):
    body = _read(plugin_root / "skills" / "architect-team-pipeline" / "SKILL.md").lower()
    assert "phenotype" in body


def test_mempalace_documents_phenotype_recall(plugin_root: Path):
    body = _read(plugin_root / "skills" / "mempalace-integration" / "SKILL.md").lower()
    assert "phenotype" in body


# --- every phenotype validates (auto-covers all records) -------------------

def test_all_phenotypes_validate(plugin_root: Path):
    mod = _load_helper(plugin_root)
    records = mod.discover_phenotypes(plugin_root / "phenotypes")
    assert records, "no phenotypes discovered"
    for rec in records:
        label = rec["_label_dir"]
        errs = mod.validate_phenotype(rec, dirname=label)
        assert errs == [], f"{label} fails validation: {errs}"


# --- the absorb capability -------------------------------------------------

def test_absorb_skill_present(plugin_root: Path):
    skill = plugin_root / "skills" / "phenotype-absorption" / "SKILL.md"
    assert skill.exists()
    body = _read(skill)
    assert "name: phenotype-absorption" in body
    assert "validate" in body.lower()          # documents the validate gate
    assert "read-only" in body.lower()         # the read-only-on-source guardrail


def test_absorb_command_present(plugin_root: Path):
    cmd = plugin_root / "commands" / "absorb-phenotype.md"
    assert cmd.exists()
    body = _read(cmd)
    assert "--label" in body
    assert "phenotype-absorption" in body      # the command invokes the skill


# --- every blueprint is well-formed (auto-covers all phenotype records) -----

def test_all_blueprints_have_required_sections(plugin_root: Path):
    blueprints = sorted((plugin_root / "phenotypes").glob("*/blueprint.md"))
    assert blueprints, "no phenotype blueprints found"
    for bp in blueprints:
        body = _read(bp)
        for heading in REQUIRED_BLUEPRINT_SECTIONS:
            assert heading in body, f"{bp.parent.name}/blueprint.md missing section {heading!r}"


def test_expected_seed_phenotypes_present(plugin_root: Path):
    present = {p.parent.name for p in (plugin_root / "phenotypes").glob("*/phenotype.json")}
    assert {"user-management", "config-management", "ai-management"} <= present
