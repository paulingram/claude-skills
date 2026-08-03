"""Tests for the data-annotations engine (Run D) — the per-user, git-shared
annotation store on data objects + the additive knowledge-server merge-at-query.

Two load-bearing disciplines are the adversary's attack surface and are pinned
here explicitly:

1. **Corroborate-on-ingest (the CT6 inversion).** A FACTUAL annotation (a
   `claims_key` / `expected_type` / definition) routes through
   `scripts/data_dictionary/data_dictionary.py::corroborate_definition` on
   ingest — a conflict with a corroborated definition is flagged ⚠ +
   confidence-downgraded, NEVER silently accepted as truth. Non-factual
   annotations (note / quality_flag / deprecation) are stored as authored
   opinions, but a quality_flag still travels with the served field.
2. **Gate integrity (the D5 leg-2 safety invariant).** Served / recalled
   annotation memory INFORMS a per-run gate; it can NEVER skip or auto-satisfy
   one — a test pins that an annotation cannot flip a gate to satisfied.

Additive: a repo with NO annotations behaves EXACTLY as before (byte-unchanged).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
ANN_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "annotations.py"
DD_PATH = REPO_ROOT / "scripts" / "data_dictionary" / "data_dictionary.py"
DS_PATH = REPO_ROOT / "services" / "knowledge_server" / "dictionary_source.py"
KS_FIX = REPO_ROOT / "tests" / "fixtures" / "knowledge_server"
ANN_FIX = REPO_ROOT / "tests" / "fixtures" / "data_annotations"

ann = load_module(ANN_PATH, "ct6_annotations")
dd = load_module(DD_PATH, "ct6_dd_for_ann")
ds_mod = load_module(DS_PATH, "ct6_ds_for_ann")

# Sampled rows whose `total_cents` are integers — the ground truth a factual
# `boolean` claim on that field must be corroborated against (and contradicted by).
INT_ROWS = [{"id": 1, "total_cents": 500}, {"id": 2, "total_cents": 1299},
            {"id": 3, "total_cents": 75}]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _dictionary() -> dict:
    return json.loads((KS_FIX / "data-dictionary.json").read_text(encoding="utf-8"))


def _corroborated_defs() -> dict:
    return ann.corroborated_defs_from_dictionary(_dictionary())


def _source(annotations_dir, *, changed=lambda stamp: []):
    return ds_mod.DictionarySource(
        str(KS_FIX / "data-dictionary.json"),
        annotations_dir=str(annotations_dir) if annotations_dir else None,
        changed_paths_provider=changed)


def _tool(src, name):
    return {t.name: t for t in src.tools()}[name]


def _call(src, name, **args):
    return _tool(src, name).handler(args)


# --------------------------------------------------------------------------- #
# 1. The store — write / read-back / validate / atomic (task 1.1/1.2)
# --------------------------------------------------------------------------- #
def test_vocabulary_constants_are_dengs_as_is() -> None:
    assert ann.QUALITY_FLAGS == ("TRUSTED", "STALE", "INCOMPLETE", "EXPERIMENTAL")


def test_write_and_read_back_anchored_per_user(tmp_path: Path) -> None:
    entry = ann.add_annotation("analyst", "orders.total_cents", quality_flag="STALE",
                               note="superseded by total_minor_units", annotations_root=tmp_path)
    assert entry["anchor"] == "orders.total_cents"
    path = ann.user_file(tmp_path, "analyst")
    assert path.name == "analyst.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    got = [a for a in doc["annotations"] if a["anchor"] == "orders.total_cents"]
    assert got and got[0]["quality_flag"] == "STALE" and got[0]["note"]


def test_add_accumulates_in_one_user_file(tmp_path: Path) -> None:
    ann.add_annotation("analyst", "orders", note="hourly reporting reads this",
                       annotations_root=tmp_path)
    ann.add_annotation("analyst", "customers.email", quality_flag="TRUSTED",
                       annotations_root=tmp_path)
    doc = json.loads(ann.user_file(tmp_path, "analyst").read_text(encoding="utf-8"))
    anchors = {a["anchor"] for a in doc["annotations"]}
    assert {"orders", "customers.email"} <= anchors


def test_write_is_atomic_no_partial_and_no_tmp_leftover(tmp_path: Path, monkeypatch) -> None:
    # a first good write establishes the file
    ann.add_annotation("analyst", "orders", note="v1", annotations_root=tmp_path)
    path = ann.user_file(tmp_path, "analyst")
    original = path.read_bytes()

    # a failure at the os.replace step must leave the ORIGINAL file intact and
    # never leave a partial temp file behind (the house atomic-write guarantee)
    def _boom(*a, **k):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(ann.os, "replace", _boom)
    with pytest.raises(OSError):
        ann.add_annotation("analyst", "customers", note="v2 never lands",
                           annotations_root=tmp_path)
    assert path.read_bytes() == original  # untouched — no partial write
    leftovers = [p for p in Path(tmp_path).iterdir() if p.suffix == ".tmp" or ".tmp." in p.name]
    assert not leftovers, f"atomic write left a temp file behind: {leftovers}"


def test_invalid_quality_flag_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ann.add_annotation("analyst", "orders.total_cents", quality_flag="BOGUS",
                           annotations_root=tmp_path)


def test_every_valid_quality_flag_accepted(tmp_path: Path) -> None:
    for i, flag in enumerate(ann.QUALITY_FLAGS):
        ann.add_annotation("analyst", f"t{i}.f", quality_flag=flag, annotations_root=tmp_path)
    doc = json.loads(ann.user_file(tmp_path, "analyst").read_text(encoding="utf-8"))
    assert {a["quality_flag"] for a in doc["annotations"]} == set(ann.QUALITY_FLAGS)


def test_empty_anchor_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ann.add_annotation("analyst", "   ", note="x", annotations_root=tmp_path)


def test_annotation_with_no_payload_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ann.add_annotation("analyst", "orders", annotations_root=tmp_path)


def test_existing_fixture_file_validates(tmp_path: Path) -> None:
    doc = json.loads((ANN_FIX / "analyst.json").read_text(encoding="utf-8"))
    kinds = {k for a in doc["annotations"] for k in a if k != "anchor"}
    assert {"note", "quality_flag", "deprecation", "claim"} <= kinds
    # the fixture's factual claim is a flagged (not-accepted) conflict
    claim = next(a["claim"] for a in doc["annotations"] if "claim" in a)
    assert claim["accepted"] is False and claim["flag"] == ann.WARN_MARKER


# --------------------------------------------------------------------------- #
# 2. Corroborate-on-ingest — the CT6 inversion (task 1.2; the adversary's #1 target)
# --------------------------------------------------------------------------- #
def test_conflicting_factual_claim_flagged_and_downgraded_via_rows(tmp_path: Path) -> None:
    entry = ann.add_annotation(
        "analyst", "orders.total_cents", definition="a paid / unpaid flag",
        expected_type="boolean", rows=INT_ROWS, annotations_root=tmp_path)
    claim = entry["claim"]
    # it routed through data_dictionary.corroborate_definition (that call's shape)
    assert set(claim["corroboration"]) >= {"checked", "agrees", "actual_type", "conflict"}
    assert claim["corroboration"]["agrees"] is False
    assert claim["corroboration"]["actual_type"] == "integer"
    # flagged, downgraded, NOT accepted, never promoted above inference
    assert claim["flag"] == ann.WARN_MARKER
    assert claim["accepted"] is False
    assert claim["confidence"] == "low"
    assert claim["provenance"] == "inference"


def test_agreeing_factual_claim_accepted_via_rows(tmp_path: Path) -> None:
    entry = ann.add_annotation(
        "analyst", "orders.total_cents", expected_type="integer",
        rows=INT_ROWS, annotations_root=tmp_path)
    claim = entry["claim"]
    assert claim["corroboration"]["agrees"] is True
    assert claim["flag"] == "ok" and claim["accepted"] is True
    assert claim["provenance"] == "inference"  # still never stronger than inference


def test_conflicting_claim_flagged_against_corroborated_dictionary_defs(tmp_path: Path) -> None:
    # no live rows — corroborate against the dictionary's already-corroborated def
    entry = ann.add_annotation(
        "analyst", "orders.total_cents", expected_type="boolean",
        corroborated_defs=_corroborated_defs(), annotations_root=tmp_path)
    claim = entry["claim"]
    assert claim["flag"] == ann.WARN_MARKER and claim["accepted"] is False
    assert "conflicts with the corroborated definition" in (claim["conflict"] or "")


def test_uncorroborated_factual_claim_is_not_presented_as_truth(tmp_path: Path) -> None:
    # neither rows nor corroborated defs — the claim stays honestly uncorroborated
    entry = ann.add_annotation(
        "analyst", "orders.total_cents", expected_type="boolean", annotations_root=tmp_path)
    claim = entry["claim"]
    assert claim["needs_corroboration"] is True
    assert claim["corroborated"] is False
    assert claim["accepted"] is False  # never accepted without corroboration


def test_opinion_stored_as_authored_and_quality_flag_travels(tmp_path: Path) -> None:
    entry = ann.add_annotation("analyst", "orders.total_cents", quality_flag="EXPERIMENTAL",
                               note="derived in the v2 backfill", annotations_root=tmp_path)
    assert "claim" not in entry                     # an opinion is not a claim
    assert entry["quality_flag"] == "EXPERIMENTAL"  # travels with the field
    assert entry["note"] == "derived in the v2 backfill"


# --------------------------------------------------------------------------- #
# 3. Per-user files never merge-conflict (task 1.1)
# --------------------------------------------------------------------------- #
def test_per_user_files_are_independent_and_never_conflict(tmp_path: Path) -> None:
    ann.add_annotation("alice", "orders.total_cents", quality_flag="STALE", annotations_root=tmp_path)
    ann.add_annotation("bob", "orders.total_cents", quality_flag="TRUSTED", annotations_root=tmp_path)
    fa, fb = ann.user_file(tmp_path, "alice"), ann.user_file(tmp_path, "bob")
    assert fa != fb and fa.name == "alice.json" and fb.name == "bob.json"
    # each file carries only its own author's annotation — no shared file to conflict on
    da = json.loads(fa.read_text(encoding="utf-8"))
    db = json.loads(fb.read_text(encoding="utf-8"))
    assert da["author"] == "alice" and db["author"] == "bob"
    assert da["annotations"][0]["quality_flag"] == "STALE"
    assert db["annotations"][0]["quality_flag"] == "TRUSTED"


# --------------------------------------------------------------------------- #
# 4. Server merge-at-query — additive; corroboration status surfaced (task 2.1)
# --------------------------------------------------------------------------- #
def test_get_table_details_surfaces_annotations_with_corroboration_status(tmp_path: Path) -> None:
    ann.add_annotation("analyst", "orders.total_cents", quality_flag="STALE",
                       note="use total_minor_units", annotations_root=tmp_path)
    ann.add_annotation("analyst", "orders.total_cents", expected_type="boolean",
                       definition="paid / unpaid flag", rows=INT_ROWS, annotations_root=tmp_path)
    out = _call(_source(tmp_path), "get_table_details", table="orders")
    by_status: dict[str, list] = {}
    for a in out["annotations"]:
        by_status.setdefault(a["corroboration_status"], []).append(a)
    # the opinion surfaces as an opinion (quality_flag travels) ...
    assert any(a.get("quality_flag") == "STALE" for a in by_status.get("opinion", []))
    # ... and the conflicting factual claim surfaces as CONFLICTING, not truth
    assert by_status.get("conflicting"), "the flagged factual claim must surface as conflicting"
    assert out["freshness"]["verdict"] in {"current", "stale", "unknowable"}


def test_search_surfaces_annotations_on_matched_result(tmp_path: Path) -> None:
    ann.add_annotation("analyst", "customers.email", quality_flag="TRUSTED",
                       note="canonical contact", annotations_root=tmp_path)
    out = _call(_source(tmp_path), "search_dictionary", query="email")
    hit = next(r for r in out["results"] if r["doc_id"] == "customers")
    assert "annotations" in hit and hit["annotations"]
    assert any(a.get("quality_flag") == "TRUSTED" for a in hit["annotations"])


def test_no_annotations_response_is_byte_unchanged() -> None:
    src = _source(None)  # a repo with NO annotations
    details = _call(src, "get_table_details", table="orders")
    assert details["annotations"] == []  # empty, exactly as before Run D
    search = _call(src, "search_dictionary", query="email")
    # NO result gains an annotations key when the repo has no annotations
    assert all("annotations" not in r for r in search["results"])
    # the top-level shapes are exactly the pre-Run-D key sets (nothing added)
    assert set(details) == {"table", "found", "grain", "fields", "annotations", "freshness"}
    assert set(search) == {"query", "results", "count", "freshness"}


def test_no_annotations_response_validates_against_closed_contracts() -> None:
    co = load_module(REPO_ROOT / "services" / "knowledge_server" / "contracts.py", "ct6_co_ann")
    contracts = co.tool_contracts()
    src = _source(None)
    for tool in src.tools():
        args = {"query": "email"} if tool.name == "search_dictionary" else (
            {"table": "orders"} if tool.name in ("get_table_details", "find_relations") else {})
        result = co.validate_payload(tool.handler(args), contracts[tool.name])
        assert result["valid"] is True, f"{tool.name}: {result['errors']}"


def test_server_merge_adds_no_new_import_separation_stays_clean() -> None:
    from services.separation import check_separation
    rep = check_separation()
    assert rep["clean"] is True


# --------------------------------------------------------------------------- #
# 5. Gate integrity — the D5 load-bearing invariant (task 2.3)
# --------------------------------------------------------------------------- #
def test_annotation_cannot_flip_a_gate_to_satisfied() -> None:
    gate = {"gate_id": "review-gate", "satisfied": False}
    # adversarial memory that TRIES to look like satisfaction in every way
    adversarial = [
        {"anchor": "orders", "satisfied": True, "quality_flag": "TRUSTED"},
        {"anchor": "orders.total_cents",
         "claim": {"accepted": True, "corroborated": True, "flag": "ok"}},
    ]
    informed = ann.inform_gate(gate, adversarial)
    assert informed["satisfied"] is False               # NEVER flipped by memory
    assert informed["informing_annotations"] == adversarial  # memory only INFORMS


def test_inform_gate_preserves_the_gates_own_state_both_ways() -> None:
    assert ann.inform_gate({"satisfied": True}, [])["satisfied"] is True
    assert ann.inform_gate({"satisfied": False}, [{"anchor": "x", "note": "y"}])["satisfied"] is False


# --------------------------------------------------------------------------- #
# 6. Mine wiring (task 1.3) + structural reuse / stdlib discipline
# --------------------------------------------------------------------------- #
def test_mine_wiring_documented_in_skill() -> None:
    body = (REPO_ROOT / "skills" / "data-annotations" / "SKILL.md").read_text(encoding="utf-8")
    assert "mempalace" in body and "mine" in body
    assert "docs/data-annotations" in body  # annotations are mined alongside the dictionary


def test_engine_exposes_the_annotations_dir_path() -> None:
    d = ann.annotations_dir("/repo")
    assert Path(d).name == "data-annotations" and Path(d).parent.name == "docs"


def test_engine_is_stdlib_only_and_composes_corroborate_definition() -> None:
    tree = ast.parse(ANN_PATH.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    stdlib = {"__future__", "argparse", "importlib", "json", "os", "re",
              "pathlib", "typing", "sqlite3", "datetime"}
    assert roots <= stdlib, f"non-stdlib import in annotations.py: {sorted(roots - stdlib)}"
    # the corroboration inversion is COMPOSED, never re-implemented
    assert "corroborate_definition" in ANN_PATH.read_text(encoding="utf-8")


def test_no_import_time_side_effects(tmp_path: Path) -> None:
    # importing the engine writes nothing (no annotations dir created on import)
    fresh = load_module(ANN_PATH, "ct6_annotations_reimport")
    assert hasattr(fresh, "add_annotation")


# --------------------------------------------------------------------------- #
# 7. Review remediation — corroboration is PER-FIELD (F1/F3) + injective users (F2)
# --------------------------------------------------------------------------- #
# F1 (BLOCKING): supplying a corroborated_defs MAP is not "this claim was
# corroborated". A claim whose field is ABSENT from every source — or PRESENT but
# un-corroborated — with no rows must stay honestly uncorroborated + NOT accepted,
# never stamped corroborated=true just because a map was passed.
def test_factual_claim_on_field_absent_from_defs_is_not_accepted(tmp_path: Path) -> None:
    entry = ann.add_annotation(
        "analyst", "ghost.col", expected_type="text",
        corroborated_defs=_corroborated_defs(), annotations_root=tmp_path)  # non-empty map, field absent
    claim = entry["claim"]
    assert claim["accepted"] is False
    assert claim["needs_corroboration"] is True
    assert claim["corroborated"] is False
    assert claim["confidence"] == "low"


def test_factual_claim_against_uncorroborated_def_is_not_accepted(tmp_path: Path) -> None:
    defs = {"orders.total_cents": {"type": "integer", "corroborated": False}}  # present but NOT corroborated
    entry = ann.add_annotation(
        "analyst", "orders.total_cents", expected_type="integer",
        corroborated_defs=defs, annotations_root=tmp_path)
    claim = entry["claim"]
    assert claim["accepted"] is False and claim["needs_corroboration"] is True
    assert claim["corroborated"] is False


def test_factual_claim_agreeing_with_corroborated_def_is_accepted(tmp_path: Path) -> None:
    # the honest positive: a claim compared against a CORROBORATED def for THIS
    # exact field, agreeing, IS accepted (guards the fix doesn't over-correct)
    entry = ann.add_annotation(
        "analyst", "orders.total_cents", expected_type="integer",
        corroborated_defs=_corroborated_defs(), annotations_root=tmp_path)
    claim = entry["claim"]
    assert claim["accepted"] is True and claim["corroborated"] is True and claim["flag"] == "ok"


def test_server_surfaces_uncorroborated_absent_field_claim_not_as_truth(tmp_path: Path) -> None:
    # the CLI-reachable bypass, end-to-end: an absent-field factual claim must
    # NEVER surface as corroboration_status='corroborated'
    ann.add_annotation("analyst", "ghost.col", expected_type="text",
                       corroborated_defs=_corroborated_defs(), annotations_root=tmp_path)
    out = _call(_source(tmp_path), "get_table_details", table="ghost")
    statuses = {a["corroboration_status"] for a in out["annotations"]}
    assert "uncorroborated" in statuses
    assert "corroborated" not in statuses


# F3 — a factual claim anchored to a field ABSENT from the supplied dictionary is
# marked honestly (anchor_in_dictionary False), closing F1's worst case at the door.
def test_absent_anchor_marked_not_in_dictionary(tmp_path: Path) -> None:
    entry = ann.add_annotation(
        "analyst", "ghost.col", expected_type="text",
        corroborated_defs=_corroborated_defs(), annotations_root=tmp_path)
    assert entry["claim"]["anchor_in_dictionary"] is False


# F2 — per-user files are INJECTIVE: two distinct usernames NEVER map to one file,
# and a username that would collide or is filesystem-unsafe is REJECTED, not
# silently collapsed (which would break the never-merge-conflict guarantee).
def test_distinct_valid_usernames_map_to_distinct_files(tmp_path: Path) -> None:
    users = ["alice", "bob", "first.last", "a-b", "a_b", "analyst9"]
    paths = {str(ann.user_file(tmp_path, u)) for u in users}
    assert len(paths) == len(users)  # injective — no two share a file


@pytest.mark.parametrize("bad", ["alice.", ".alice", "a/b", "a\\b", "team:lead",
                                 "@@@", "..", ".", "", "  ", "a b"])
def test_ambiguous_or_unsafe_username_is_rejected(bad: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ann.user_file(tmp_path, bad)


def test_previously_colliding_usernames_can_no_longer_share_a_file(tmp_path: Path) -> None:
    # 'alice' is valid; 'alice.' used to sanitize to the SAME 'alice.json' — now rejected
    ann.user_file(tmp_path, "alice")            # ok
    with pytest.raises(ValueError):
        ann.user_file(tmp_path, "alice.")       # would have collided → refused
