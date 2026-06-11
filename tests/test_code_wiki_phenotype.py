"""Structural + engine-gate tests for the code-wiki phenotype (absorbed from deepwiki-open).

ASCII-only source; every file read with encoding="utf-8". Mirrors the phenotype test family
(tests/test_phenotype_subsystem.py + tests/test_phenotypes_helper.py): importlib-loads the engine for
in-process checks AND drives the engine CLI as a subprocess (like tests/test_vao_glue_execution.py)
for the REQ-003 / REQ-005 gates that the spec phrases as CLI behavior ("prints code-wiki: OK").

Covers REQ-002 (blueprint 10 sections + documented deltas), REQ-003 (manifest validates + hosting
variation + deploy.via cross-seed + provenance), REQ-004 (scaffold integrity + secret sweep),
REQ-005 / REQ-008 (engine validate / match gates). The executed demo (REQ-006) + cloud static
validation (REQ-007) are run artifacts checked by the review gates, not unit-testable here.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

LABEL = "code-wiki"
DEEPWIKI_URL = "https://github.com/AsyncFuncAI/deepwiki-open.git"

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

# Secret-shaped strings that must NEVER appear in a generalized record (per the absorption rubric).
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),          # OpenAI-style secret key
    re.compile(r"AKIA[0-9A-Z]{12,}"),            # AWS access key id
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # PEM private key
    re.compile(r"(?i)\bpassword\s*=\s*['\"][^'\"]+['\"]"),  # password=literal
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),      # Google API key
    re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"),  # Slack token
]
# Concrete account-id / domain shapes the rubric strips. (12-digit AWS account ids, the deepwiki
# cache key prefix, the source's branded names.) The provenance URL is the one allowed deepwiki ref.
FORBIDDEN_LITERALS = [
    "deepwiki_cache_",   # the source's filesystem cache key prefix (renamed neutrally)
    ".dkr.ecr.",         # a concrete ECR registry host fragment with an account id
    "amazonaws.com/",    # a baked AWS account/registry domain (not the generic service host)
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _record_dir(plugin_root: Path) -> Path:
    return plugin_root / "phenotypes" / LABEL


def _load_engine(plugin_root: Path):
    path = plugin_root / "scripts" / "phenotypes" / "phenotypes.py"
    spec = importlib.util.spec_from_file_location("phenotypes_engine_codewiki", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _engine_cli(plugin_root: Path, args, timeout=60):
    """Run the engine CLI as a subprocess from the repo root (the REQ-003/REQ-005 gate shape)."""
    engine = plugin_root / "scripts" / "phenotypes" / "phenotypes.py"
    env = dict(os.environ)
    env.pop("PHENOTYPES_DIR", None)  # use the real repo phenotypes/ dir
    return subprocess.run(
        [sys.executable, str(engine), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(plugin_root), env=env, timeout=timeout,
    )


# --- record presence -------------------------------------------------------

def test_record_files_present(plugin_root: Path):
    rec = _record_dir(plugin_root)
    assert (rec / "phenotype.json").exists(), "code-wiki/phenotype.json missing"
    assert (rec / "blueprint.md").exists(), "code-wiki/blueprint.md missing"
    assert (rec / "scaffold" / "scaffold.manifest.json").exists(), "scaffold manifest missing"


# --- REQ-003: manifest validates (in-process + CLI gate) -------------------

def test_manifest_validates_in_process(plugin_root: Path):
    mod = _load_engine(plugin_root)
    obj = json.loads(_read(_record_dir(plugin_root) / "phenotype.json"))
    assert mod.validate_phenotype(obj, dirname=LABEL) == []


def test_validate_cli_prints_ok(plugin_root: Path):
    """REQ-003 / REQ-005 gate: `validate code-wiki` exits 0 and prints 'code-wiki: OK'."""
    r = _engine_cli(plugin_root, ["validate", LABEL])
    assert r.returncode == 0, f"validate exited {r.returncode}: {r.stdout}\n{r.stderr}"
    assert "Traceback (most recent call last)" not in (r.stderr or ""), r.stderr
    assert f"{LABEL}: OK" in r.stdout, f"expected '{LABEL}: OK', got: {r.stdout!r}"


def test_manifest_core_fields(plugin_root: Path):
    obj = json.loads(_read(_record_dir(plugin_root) / "phenotype.json"))
    assert obj["label"] == LABEL
    assert obj["kind"] == "singleton"  # the P2 SINGLETON verdict
    assert obj["version"] == "1.0.0"
    assert isinstance(obj["match"]["keywords"], list) and obj["match"]["keywords"]
    # "code wiki" forms present in keywords
    kw_blob = " ".join(str(k).lower() for k in obj["match"]["keywords"])
    assert "code wiki" in kw_blob or "codebase wiki" in kw_blob
    assert isinstance(obj["match"].get("trigger_phrases"), list) and obj["match"]["trigger_phrases"]


def test_manifest_hosting_variation_point(plugin_root: Path):
    obj = json.loads(_read(_record_dir(plugin_root) / "phenotype.json"))
    vps = {vp["id"]: vp for vp in obj.get("variation_points", [])}
    assert "hosting" in vps, "missing hosting variation point"
    hosting = vps["hosting"]
    assert hosting["options"] == ["local", "aws", "gcp"]
    assert hosting["default"] == "local"


def test_manifest_deploy_via_cross_seed(plugin_root: Path):
    obj = json.loads(_read(_record_dir(plugin_root) / "phenotype.json"))
    via = obj["components"]["deploy"]["via"]
    assert "config-management" in via.lower(), f"deploy.via must reference config-management: {via!r}"


def test_manifest_provenance(plugin_root: Path):
    obj = json.loads(_read(_record_dir(plugin_root) / "phenotype.json"))
    prov = obj["provenance"]
    assert DEEPWIKI_URL in prov["absorbed_from"], f"absorbed_from must list the deepwiki URL: {prov}"
    assert prov["absorbed_by"] == "absorb-tool"
    assert prov.get("generalized") is True


def test_manifest_contract_surface_present(plugin_root: Path):
    obj = json.loads(_read(_record_dir(plugin_root) / "phenotype.json"))
    cs = obj.get("contract_surface")
    assert isinstance(cs, dict) and cs, "contract_surface must document the maps/content contract"
    blob = json.dumps(cs).lower()
    assert "codebases.json" in blob
    assert "wiki_content_dir" in blob


# --- REQ-002: blueprint -----------------------------------------------------

def test_blueprint_has_all_ten_sections(plugin_root: Path):
    body = _read(_record_dir(plugin_root) / "blueprint.md")
    for heading in REQUIRED_BLUEPRINT_SECTIONS:
        assert heading in body, f"blueprint missing required section {heading!r}"


def test_blueprint_documents_required_topics(plugin_root: Path):
    body = _read(_record_dir(plugin_root) / "blueprint.md").lower()
    # stripped-LLM delta
    assert "llm" in body and ("strip" in body or "stripped" in body)
    # maps-ingestion contract
    assert "codebases.json" in body
    assert "_map.md" in body or "*_map.md" in body
    # the three hosting values
    assert "local" in body and "aws" in body and "gcp" in body
    # config-management cross-seed
    assert "config-management" in body


def test_blueprint_cites_pattern_sources(plugin_root: Path):
    """The blueprint must cite the absorbed pattern sources (per the brief)."""
    body = _read(_record_dir(plugin_root) / "blueprint.md")
    assert "Mermaid" in body
    assert "Markdown" in body
    assert "WikiTreeView" in body


# --- REQ-004: scaffold integrity -------------------------------------------

def test_scaffold_manifest_parses_and_params_well_formed(plugin_root: Path):
    rec = _record_dir(plugin_root)
    manifest = json.loads(_read(rec / "scaffold" / "scaffold.manifest.json"))
    assert manifest["schema_version"] == 1
    params = manifest["parameters"]
    by_name = {p["name"]: p for p in params}
    # wiki_name required; port defaulted
    assert by_name["wiki_name"].get("required") is True
    assert "default" in by_name["port"]
    # every parameter has a name and is either required or carries a default
    for p in params:
        assert "name" in p
        assert p.get("required") is True or "default" in p, f"param underspecified: {p}"


def test_scaffold_every_src_exists(plugin_root: Path):
    rec = _record_dir(plugin_root)
    root = rec / "scaffold"
    manifest = json.loads(_read(root / "scaffold.manifest.json"))
    assert manifest["files"], "scaffold has no files[]"
    for entry in manifest["files"]:
        assert (root / entry["src"]).exists(), f"manifest references missing src: {entry['src']}"
        assert "dest" in entry and entry["dest"], f"files[] entry missing dest: {entry}"


def test_scaffold_post_emit_notes_cover_required_steps(plugin_root: Path):
    rec = _record_dir(plugin_root)
    manifest = json.loads(_read(rec / "scaffold" / "scaffold.manifest.json"))
    notes_blob = " ".join(manifest.get("post_emit_notes", [])).lower()
    assert "codebases.json" in notes_blob
    assert "npm install" in notes_blob
    assert "config-management" in notes_blob  # emit config-management for cloud hosting


def test_scaffold_has_nextjs_ingestion_docker_and_both_iac(plugin_root: Path):
    root = _record_dir(plugin_root) / "scaffold"
    srcs = {e["src"] for e in json.loads(_read(root / "scaffold.manifest.json"))["files"]}
    blob = " ".join(srcs)
    # Next.js starter signals
    assert "package.json.tmpl" in blob
    assert "layout" in blob.lower()
    assert "globals.css" in blob.lower()
    # ingestion layer
    assert "maps-loader" in blob.lower() or "maps_loader" in blob.lower()
    # docker
    assert "Dockerfile.tmpl" in blob
    assert "docker-compose" in blob.lower()
    # both iac dirs
    assert any(s.startswith("iac/aws/") for s in srcs), "missing iac/aws templates"
    assert any(s.startswith("iac/gcp/") for s in srcs), "missing iac/gcp templates"
    # Mermaid + Markdown + tree components
    assert "Mermaid" in blob
    assert "Markdown" in blob


def test_scaffold_no_secret_shaped_strings(plugin_root: Path):
    """REQ-004 secret sweep: zero secret-shaped strings / baked account ids across the scaffold."""
    root = _record_dir(plugin_root) / "scaffold"
    offenders = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = _read(path)
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                offenders.append(f"{path.name}: secret-shaped {m.group(0)!r}")
        low = text.lower()
        for lit in FORBIDDEN_LITERALS:
            if lit.lower() in low:
                offenders.append(f"{path.name}: forbidden literal {lit!r}")
    assert not offenders, "secret/account-id sweep found:\n" + "\n".join(offenders)


def test_emitted_app_uses_wiki_name_not_source_branding(plugin_root: Path):
    """The EMITTED app's user-facing strings must carry the {{wiki_name}} brand, not the source's
    product branding. Per the absorption rubric, branding is stripped from the GENERATED SCAFFOLD;
    the record's documentation (blueprint.md / phenotype.json / README provenance) may NAME the
    absorbed source as provenance (the seed phenotypes do exactly that). So this scopes the check:
    the app-shell templates parameterize the title via {{wiki_name}}, and no scaffold file embeds a
    DeepWiki/Grok product-TITLE literal in user-facing copy (source-crediting comments + the README
    MIT attribution are correct practice and permitted)."""
    scaffold = _record_dir(plugin_root) / "scaffold"
    layout = _read(scaffold / "app" / "layout.tsx.tmpl")
    page = _read(scaffold / "app" / "page.tsx.tmpl")
    # The app title/heading is parameterized, not a hardcoded source brand.
    assert "{{wiki_name}}" in layout, "layout must title the app via {{wiki_name}}"
    assert "{{wiki_name}}" in page, "index page must brand via {{wiki_name}}"
    # No source product-TITLE literal in any user-facing app string. The product names are 'DeepWiki'
    # and 'Grok-Wiki'; the package/source slug 'deepwiki-open' (in comments/README/provenance) is fine.
    product_title_literals = ["DeepWiki Open", "Grok-Wiki", "Deepwiki Open Source"]
    for path in scaffold.rglob("*"):
        if not path.is_file():
            continue
        text = _read(path)
        for lit in product_title_literals:
            assert lit not in text, f"{path.name} carries source product title {lit!r}"


def test_record_documents_provenance_source_name(plugin_root: Path):
    """Positive: the record SHOULD name the absorbed source as provenance (blueprint + manifest)."""
    bp = _read(_record_dir(plugin_root) / "blueprint.md")
    manifest = json.loads(_read(_record_dir(plugin_root) / "phenotype.json"))
    assert "deepwiki-open" in bp.lower(), "blueprint should credit the absorbed source"
    assert DEEPWIKI_URL in manifest["provenance"]["absorbed_from"]


# --- REQ-005 / REQ-008: match ranking --------------------------------------

def test_match_ranks_code_wiki_in_process(plugin_root: Path):
    mod = _load_engine(plugin_root)
    results = mod.match_phenotype(
        "launch a code wiki for my codebases hosted locally", dir=plugin_root / "phenotypes")
    by_label = {r["label"]: r for r in results}
    assert LABEL in by_label, "code-wiki not among matched phenotypes"
    assert by_label[LABEL]["score"] > 0, f"code-wiki scored 0: {by_label[LABEL]}"


def test_match_ranks_code_wiki_cli(plugin_root: Path):
    """REQ-005 gate via the CLI: match lists code-wiki for a representative request."""
    r = _engine_cli(plugin_root, ["match", "host the codebase maps in a visually appealing way"])
    assert r.returncode == 0, f"match exited {r.returncode}: {r.stderr}"
    assert LABEL in r.stdout, f"match did not surface {LABEL}: {r.stdout!r}"


def test_match_documentation_site_phrase(plugin_root: Path):
    mod = _load_engine(plugin_root)
    results = mod.match_phenotype(
        "spin up a documentation wiki from the maps", dir=plugin_root / "phenotypes")
    by_label = {r["label"]: r for r in results}
    assert by_label.get(LABEL, {}).get("score", 0) > 0


def test_emit_dry_run_lists_scaffold_cli(plugin_root: Path, tmp_path: Path):
    """REQ-005 gate: emit --dry-run lists the scaffold files (exit 0, lists package.json)."""
    target = tmp_path / "emit-out"
    r = _engine_cli(plugin_root, [
        "emit", LABEL, str(target), "--param", "wiki_name=demo", "--dry-run"])
    assert r.returncode == 0, f"emit exited {r.returncode}: {r.stderr}"
    assert "package.json" in r.stdout, f"emit dry-run did not list package.json: {r.stdout!r}"
    assert not target.exists(), "dry-run wrote files"
