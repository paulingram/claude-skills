"""Tests for the v3.28.0 service-tier separation manifest (services/separation.py; REPO-1…4).

Covers the manifest shape/validation, the documented paid/closed pieces + seams, and
— the headline REPO-4 invariant — that every `services/**/*.py` is import-clean
(stdlib + in-repo only; all external/closed deps injected, never hard-imported).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


sep = _load("separation", "services/separation.py")


# --------------------------------------------------------------------------- #
# the manifest (REPO-1/2/3)
# --------------------------------------------------------------------------- #

def test_manifest_valid_and_documents_paid_pieces() -> None:
    assert sep.validate_manifest(sep.SEPARATION_MANIFEST)["valid"] is True
    # every service is separable (REPO-3)
    assert all(s["separable"] for s in sep.SEPARATION_MANIFEST["services"])
    # the two chargeable pieces (REPO-2) are named + each plugs into a real seam
    pieces = sep.SEPARATION_MANIFEST["paid_closed_pieces"]
    assert any("SEC-4" in p["piece"] for p in pieces)
    assert any("SMP-4" in p["piece"] or "phenotype" in p["piece"].lower() for p in pieces)
    seams = {s["seam"] for s in sep.SEPARATION_MANIFEST["seams"]}
    assert all(p["seam"] in seams for p in pieces)
    # the SEC-4 + SMP-4 seams are marked paid
    paid = {s["seam"] for s in sep.SEPARATION_MANIFEST["seams"] if s.get("paid")}
    assert {"attestation_verifier", "entitlements_for"} <= paid


def test_validate_manifest_catches_bad_shape() -> None:
    assert sep.validate_manifest("nope")["valid"] is False
    bad = json.loads(json.dumps(sep.SEPARATION_MANIFEST))
    bad["services"][0]["separable"] = False  # REPO-3 violation
    assert sep.validate_manifest(bad)["valid"] is False
    bad2 = json.loads(json.dumps(sep.SEPARATION_MANIFEST))
    bad2["paid_closed_pieces"][0]["seam"] = "no-such-seam"  # dangling seam
    assert sep.validate_manifest(bad2)["valid"] is False
    bad3 = json.loads(json.dumps(sep.SEPARATION_MANIFEST))
    del bad3["seams"]
    assert sep.validate_manifest(bad3)["valid"] is False


# --------------------------------------------------------------------------- #
# the REPO-4 separability invariant (the headline test)
# --------------------------------------------------------------------------- #

def test_services_are_import_clean_repo4() -> None:
    result = sep.check_separation()
    assert result["clean"] is True, f"non-separable hard imports found: {result['violations']}"
    assert result["checked"] >= 12  # all service modules across the tier were scanned


def test_check_flags_external_toplevel_import_but_not_lazy(tmp_path: Path) -> None:
    svc = tmp_path / "services" / "x"
    svc.mkdir(parents=True)
    # a TOP-LEVEL external import is a violation (must be injected via a seam)
    (svc / "bad.py").write_text("import requests\nimport json\n", encoding="utf-8")
    # a LAZY (in-function) external import is fine — that's how the core defers a dep
    (svc / "good.py").write_text(
        "import json\n\n\ndef f():\n    import requests\n    return requests\n", encoding="utf-8")
    result = sep.check_separation(repo_root=tmp_path)
    flagged = {(v["file"], v["module"]) for v in result["violations"]}
    assert ("bad.py", "requests") in flagged          # top-level external -> violation
    assert not any(f == "good.py" for f, _ in flagged)  # lazy import -> not flagged
    assert result["clean"] is False


def test_check_allows_inrepo_and_reuse_modules(tmp_path: Path) -> None:
    svc = tmp_path / "services" / "y"
    svc.mkdir(parents=True)
    # importing in-repo siblings + the two documented reuse points is clean
    (svc / "handshake.py").write_text("x = 1\n", encoding="utf-8")  # an in-repo sibling stem
    (svc / "uses.py").write_text(
        "import json\nimport handshake\nimport logit\nimport phenotypes\n", encoding="utf-8")
    result = sep.check_separation(repo_root=tmp_path)
    assert result["clean"] is True, result["violations"]


def test_check_catches_nested_module_load_imports(tmp_path: Path) -> None:
    # the v3.28.0 soundness fix: a module-load import nested in try/except, an if
    # block, or a class body EXECUTES at import time and must be flagged.
    svc = tmp_path / "services" / "z"
    svc.mkdir(parents=True)
    (svc / "tryimp.py").write_text(
        "import json\ntry:\n    import chromadb\nexcept Exception:\n    chromadb = None\n", encoding="utf-8")
    (svc / "ifimp.py").write_text(
        "import sys\nif sys.platform == 'linux':\n    import some_ext_pkg\n", encoding="utf-8")
    (svc / "clsimp.py").write_text("class C:\n    import requests\n", encoding="utf-8")
    # a deferred import inside a FUNCTION (even within a try) is NOT a module-load dep
    (svc / "lazy.py").write_text(
        "def f():\n    try:\n        import boto3\n    except Exception:\n        boto3 = None\n    return boto3\n",
        encoding="utf-8")
    result = sep.check_separation(repo_root=tmp_path)
    flagged = {(v["file"], v["module"]) for v in result["violations"]}
    assert ("tryimp.py", "chromadb") in flagged       # try/except module-load -> caught
    assert ("ifimp.py", "some_ext_pkg") in flagged    # if block -> caught
    assert ("clsimp.py", "requests") in flagged       # class body -> caught
    assert not any(f == "lazy.py" for f, _ in flagged)  # in-function (even in try) -> NOT flagged
    assert result["clean"] is False


def test_validate_manifest_tolerates_non_dict_items() -> None:
    # a validator must REPORT invalid, never crash, on malformed (non-dict) entries
    bad = json.loads(json.dumps(sep.SEPARATION_MANIFEST))
    bad["services"] = ["not-an-object"]
    v = sep.validate_manifest(bad)
    assert v["valid"] is False and any("not an object" in e for e in v["errors"])
    bad2 = json.loads(json.dumps(sep.SEPARATION_MANIFEST))
    bad2["paid_closed_pieces"] = ["nope"]
    assert sep.validate_manifest(bad2)["valid"] is False
    bad3 = json.loads(json.dumps(sep.SEPARATION_MANIFEST))
    bad3["seams"] = ["nope"]  # non-dict seams must not crash the seam-set comprehension
    assert isinstance(sep.validate_manifest(bad3), dict)
