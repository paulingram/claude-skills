"""Tests for the v3.27.0 Seeded MemPalace service (services/seeded_mempalace; SMP-1…5).

Covers the bundle schema + merge (`bundle.py` — SMP-3/5), the phenotype catalog
reusing the existing phenotype store (`catalog.py` — SMP-4), the authenticated
download client (`client.py` — SMP-1/2), and the SEC-handshake server skeleton
(`server.py` — SMP-2/4), incl. an end-to-end client↔server flow.
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


bundle = _load("smp_bundle", "services/seeded_mempalace/bundle.py")
catalog = _load("smp_catalog", "services/seeded_mempalace/catalog.py")
client = _load("smp_client", "services/seeded_mempalace/client.py")
server = _load("smp_server", "services/seeded_mempalace/server.py")
ed25519 = _load("smp_ed25519", "services/common/ed25519.py")
handshake = _load("smp_handshake", "services/common/handshake.py")


_PHENO = [
    {"label": "user-management", "name": "User Mgmt", "version": "1.0.0", "kind": "pair",
     "summary": "auth + rbac", "components": {"backend": {"framework": "fastapi"}}},
    {"label": "code-wiki", "name": "Code Wiki", "version": "1.0.0", "kind": "singleton",
     "summary": "docs wiki"},
]


def _master_bundle(owned=()):
    cat = catalog.build_catalog(_PHENO, owned=owned)
    return bundle.build_bundle(
        schema={"record": {"id": "str", "text": "str"}},
        curated=[{"id": "c1", "text": "curated note"}],
        phenotype_catalog=cat,
        research_synthesis={"last_updated": "2026-06-17", "entries": [{"topic": "rag", "synthesis": "..."}]},
        generated_at="2026-06-17",
    )


# --------------------------------------------------------------------------- #
# bundle (SMP-3/5)
# --------------------------------------------------------------------------- #

def test_build_and_validate_bundle() -> None:
    b = _master_bundle()
    assert b["schema"] == "seeded-mempalace/v1" and b["user_namespace"] == "user-projects"
    assert set(b["sections"]) == {"schema", "curated", "phenotype_catalog", "research_synthesis"}
    assert bundle.validate_bundle(b)["valid"] is True


def test_validate_bundle_catches_shape_errors() -> None:
    assert bundle.validate_bundle("nope")["valid"] is False
    bad = _master_bundle()
    del bad["sections"]["research_synthesis"]
    v = bundle.validate_bundle(bad)
    assert v["valid"] is False and any("research_synthesis" in e for e in v["errors"])
    bad2 = _master_bundle()
    bad2["sections"]["research_synthesis"] = {"entries": []}  # missing last_updated (SMP-5)
    assert bundle.validate_bundle(bad2)["valid"] is False
    bad3 = _master_bundle()
    bad3["user_namespace"] = "wrong"
    assert bundle.validate_bundle(bad3)["valid"] is False


def test_merge_preserves_user_namespace_smp3() -> None:
    local = {"user-projects": {"my-app": {"notes": "keep me"}}, "sections": {"stale": True}}
    merged = bundle.merge_into_local(local, _master_bundle())
    # seeded sections refreshed from the bundle...
    assert "phenotype_catalog" in merged["sections"] and "stale" not in merged["sections"]
    # ...but the user's own projects are PRESERVED untouched (SMP-3)
    assert merged["user-projects"] == {"my-app": {"notes": "keep me"}}


# --------------------------------------------------------------------------- #
# catalog (SMP-4) — reuse the existing phenotype store
# --------------------------------------------------------------------------- #

def test_build_catalog_marks_entitlement_and_keeps_records() -> None:
    cat = catalog.build_catalog(_PHENO, owned=["user-management"])
    by = {e["label"]: e for e in cat["entries"]}
    assert by["user-management"]["entitlement"] == "owned" and by["user-management"]["record"]
    assert by["code-wiki"]["entitlement"] == "purchasable"
    # the MASTER catalog keeps the full record on every entry (gating happens at serve)
    assert by["code-wiki"]["record"] is not None
    # browse metadata present for all
    assert by["code-wiki"]["summary"] == "docs wiki"


def test_gate_catalog_strips_records_for_non_entitled() -> None:
    cat = catalog.build_catalog(_PHENO)
    gated = catalog.gate_catalog(cat, entitlements=["user-management"])
    by = {e["label"]: e for e in gated["entries"]}
    assert by["user-management"]["entitlement"] == "owned" and by["user-management"]["record"] is not None
    assert by["code-wiki"]["entitlement"] == "purchasable" and by["code-wiki"]["record"] is None  # browse only
    assert catalog.entitled_labels(gated) == ["user-management"]


def test_catalog_from_store_reuses_real_phenotypes() -> None:
    cat = catalog.catalog_from_store()
    labels = {e["label"] for e in cat["entries"]}
    # the four seeded phenotypes are discovered via the reused engine
    assert {"user-management", "config-management", "ai-management", "code-wiki"} <= labels


# --------------------------------------------------------------------------- #
# client (SMP-1/2)
# --------------------------------------------------------------------------- #

def test_build_download_request_is_signed_and_verifiable() -> None:
    seed, public = ed25519.generate_keypair(bytes(range(32)))
    env = client.build_download_request("acme", seed, public)
    verdict = handshake.verify_envelope(env)
    assert verdict["valid"] is True
    payload = json.loads(verdict["payload"].decode("utf-8"))
    assert payload["action"] == "download-seeded-mempalace" and payload["requester"] == "acme"


def test_install_merges_on_authorized_and_reports_failures() -> None:
    seed, public = ed25519.generate_keypair(bytes(range(32)))
    b = _master_bundle()
    # authorized transport -> installed + merged, user namespace preserved
    local = {"user-projects": {"keep": 1}}
    ok = client.install_seeded_mempalace(
        local, lambda env: {"authorized": True, "bundle": b}, "acme", seed, public)
    assert ok["installed"] is True and ok["local"]["user-projects"] == {"keep": 1}
    # unauthorized -> not installed, local unchanged
    no = client.install_seeded_mempalace(
        local, lambda env: {"authorized": False, "reason": "bad signature"}, "acme", seed, public)
    assert no["installed"] is False and no["reason"] == "bad signature"
    # invalid bundle -> not installed
    bad = client.install_seeded_mempalace(
        local, lambda env: {"authorized": True, "bundle": {"nope": 1}}, "acme", seed, public)
    assert bad["installed"] is False and "invalid bundle" in bad["reason"]


# --------------------------------------------------------------------------- #
# server (SMP-2/4)
# --------------------------------------------------------------------------- #

def test_server_authorizes_signed_and_gates_catalog() -> None:
    seed, public = ed25519.generate_keypair(bytes(range(32)))
    env = client.build_download_request("acme", seed, public)
    master = _master_bundle()
    # acme owns only user-management
    resp = server.handle_bundle_request(
        env, master_bundle=master, entitlements_for=lambda r, pub: ["user-management"])
    assert resp["authorized"] is True
    served = {e["label"]: e for e in resp["bundle"]["sections"]["phenotype_catalog"]["entries"]}
    assert served["user-management"]["record"] is not None      # entitled -> full record
    assert served["code-wiki"]["record"] is None                 # not entitled -> browse only


def test_server_rejects_tampered_request() -> None:
    seed, public = ed25519.generate_keypair(bytes(range(32)))
    env = client.build_download_request("acme", seed, public)
    import base64
    env["payload"] = base64.b64encode(b'{"action":"download-seeded-mempalace","requester":"evil"}').decode("ascii")
    resp = server.handle_bundle_request(env, master_bundle=_master_bundle(), entitlements_for=lambda r, pub: [])
    assert resp["authorized"] is False and resp["bundle"] is None


def test_end_to_end_client_server_install() -> None:
    seed, public = ed25519.generate_keypair(bytes(range(32)))
    master = _master_bundle()
    seen: set = set()

    def transport(env):
        return server.handle_bundle_request(
            env, master_bundle=master, entitlements_for=lambda r, pub: ["code-wiki"],
            seen_nonces=seen)

    local = {"user-projects": {"mine": True}}
    result = client.install_seeded_mempalace(local, transport, "acme", seed, public)
    assert result["installed"] is True
    merged = result["local"]
    assert merged["user-projects"] == {"mine": True}  # SMP-3 preserved end-to-end
    entries = {e["label"]: e for e in merged["sections"]["phenotype_catalog"]["entries"]}
    assert entries["code-wiki"]["record"] is not None and entries["user-management"]["record"] is None
    # SMP-5 research synthesis carried through
    assert merged["sections"]["research_synthesis"]["last_updated"] == "2026-06-17"


# --------------------------------------------------------------------------- #
# remediation edge cases (adversarial-review v3.27.0)
# --------------------------------------------------------------------------- #

def test_impersonation_is_defeated_entitlements_keyed_on_public_key() -> None:
    # alice's real key + an attacker's OWN key (both produce valid signatures)
    alice_seed, alice_pub = ed25519.generate_keypair(bytes(range(32)))
    atk_seed, atk_pub = ed25519.generate_keypair(bytes(range(1, 33)))
    master = _master_bundle()
    # entitlements resolved by the AUTHENTICATED public key, NOT the requester string
    owned_by_key = {alice_pub.hex(): ["user-management"]}
    ents = lambda requester, public: owned_by_key.get(public, [])

    alice_env = client.build_download_request("alice", alice_seed, alice_pub)
    a = {e["label"]: e for e in server.handle_bundle_request(
        alice_env, master_bundle=master, entitlements_for=ents)["bundle"]["sections"]["phenotype_catalog"]["entries"]}
    assert a["user-management"]["record"] is not None  # alice gets her record

    # the attacker signs with THEIR key but claims requester="alice"
    atk_env = client.build_download_request("alice", atk_seed, atk_pub)
    atk_resp = server.handle_bundle_request(atk_env, master_bundle=master, entitlements_for=ents)
    b = {e["label"]: e for e in atk_resp["bundle"]["sections"]["phenotype_catalog"]["entries"]}
    assert atk_resp["authorized"] is True              # their signature IS valid...
    assert b["user-management"]["record"] is None      # ...but they get NO entitled records (keyed on key)


def test_merge_preserves_all_user_top_level_keys_smp3() -> None:
    local = {"user-projects": {"a": 1}, "my-custom-namespace": {"x": 2}, "metadata": {"installed": True}}
    merged = bundle.merge_into_local(local, _master_bundle())
    assert merged["user-projects"] == {"a": 1}
    assert merged["my-custom-namespace"] == {"x": 2}      # not dropped
    assert merged["metadata"] == {"installed": True}      # not dropped
    assert "phenotype_catalog" in merged["sections"]      # seeded sections still refreshed


def test_gate_catalog_does_not_alias_master() -> None:
    master = catalog.build_catalog(_PHENO, owned=["user-management"])
    gated = catalog.gate_catalog(master, entitlements=["user-management"])
    gated_rec = next(e["record"] for e in gated["entries"] if e["label"] == "user-management")
    gated_rec["summary"] = "MUTATED-BY-CALLER"
    master_rec = next(e["record"] for e in master["entries"] if e["label"] == "user-management")
    assert master_rec["summary"] != "MUTATED-BY-CALLER"  # master untouched (deep-copied)


def test_served_record_has_no_internal_path_keys() -> None:
    cat = catalog.catalog_from_store()
    for e in cat["entries"]:
        assert "_dir" not in e["record"] and "_label_dir" not in e["record"]  # no operator path leak
