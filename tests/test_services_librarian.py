"""Tests for the v3.24.0 Librarian service (services/librarian; LIB-1 … LIB-13).

Covers the reference index + conceptual search (`library_index.py` — LIB-10…13),
the LLM-driven extraction (`extract.py` — LIB-11/12), and the orchestration
(`librarian.py` — fetch → extract → index → metadata, LIB-1…9).
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


li = _load("library_index", "services/librarian/library_index.py")
ex = _load("extract", "services/librarian/extract.py")
cfg = _load("service_config", "services/common/service_config.py")
lb = _load("librarian", "services/librarian/librarian.py")


_RAD = {
    "doc_id": "d-rad", "title": "Radiation Oncology Review",
    "summary": "A review of radiation therapy for cancer.",
    "keywords": ["radiotherapy", "dosimetry"],
    "concepts": ["cancer treatment", "radiation therapy", "comorbidity statistics"],
    "source": "jstor",
}
_COOK = {
    "doc_id": "d-cook", "title": "Sourdough Basics",
    "summary": "How to bake bread.",
    "keywords": ["baking", "bread"], "concepts": ["home cooking"], "source": "blog",
}


# --------------------------------------------------------------------------- #
# LibraryIndex (LIB-11/12/13) + conceptual search (LIB-10)
# --------------------------------------------------------------------------- #

def test_add_get_roundtrip_and_count() -> None:
    ix = li.LibraryIndex(":memory:")
    ix.add_document(_RAD, added_at=1000)
    got = ix.get("d-rad")
    assert got["title"] == "Radiation Oncology Review"
    assert set(got["keywords"]) == {"radiotherapy", "dosimetry"}
    assert "radiation therapy" in got["concepts"]
    assert ix.count() == 1
    assert ix.summary("d-rad").startswith("A review")
    ix.close()


def test_idempotent_reindex() -> None:
    ix = li.LibraryIndex(":memory:")
    ix.add_document(_RAD)
    ix.add_document(dict(_RAD, title="Updated"))  # same doc_id -> replace
    assert ix.count() == 1
    assert ix.get("d-rad")["title"] == "Updated"
    ix.close()


def test_keyword_and_concept_search() -> None:
    ix = li.LibraryIndex(":memory:")
    ix.add_document(_RAD)
    ix.add_document(_COOK)
    assert ix.search_by_keyword("radiotherapy") == ["d-rad"]
    assert ix.search_by_keyword("bread") == ["d-cook"]
    assert ix.search_by_concept("radiation therapy") == ["d-rad"]
    assert ix.search_by_concept("cooking") == ["d-cook"]  # substring match on "home cooking"
    ix.close()


def test_conceptual_search_ranks_by_concept_then_keyword_then_text() -> None:
    ix = li.LibraryIndex(":memory:")
    ix.add_document(_RAD)   # "cancer" is a CONCEPT token (cancer treatment)
    ix.add_document(_COOK)
    # a conceptual query that isn't an exact keyword still finds the radiation doc
    res = ix.conceptual_search("cancer")
    assert res and res[0]["doc_id"] == "d-rad"
    assert "cancer" in res[0]["matched"]
    # cooking query returns the cooking doc, not the radiation doc
    res2 = ix.conceptual_search("bread baking")
    assert [r["doc_id"] for r in res2] == ["d-cook"]
    # concept hit outranks a mere text hit: add a doc that only mentions 'cancer' in summary
    ix.add_document({"doc_id": "d-weak", "title": "Misc", "summary": "mentions cancer once",
                     "keywords": [], "concepts": []})
    ranked = ix.conceptual_search("cancer")
    assert ranked[0]["doc_id"] == "d-rad"  # concept (×3) beats text (×1)
    assert ranked[0]["score"] > ranked[-1]["score"]
    ix.close()


def test_all_concepts_cloud() -> None:
    ix = li.LibraryIndex(":memory:")
    ix.add_document(_RAD)
    ix.add_document(_COOK)
    cloud = {c["concept"]: c["documents"] for c in ix.all_concepts()}
    assert cloud["radiation therapy"] == 1 and cloud["home cooking"] == 1
    ix.close()


# --------------------------------------------------------------------------- #
# extract (LIB-11/12)
# --------------------------------------------------------------------------- #

def test_build_prompt_and_parse() -> None:
    p = ex.build_extraction_prompt("body text", topic="oncology")
    assert "oncology" in p and "concept" in p.lower() and "DOCUMENT:" in p
    # valid JSON embedded in prose is parsed
    out = 'Sure! {"relevant": true, "title": "T", "summary": "S", "keywords": ["k"], "concepts": ["c"]} done'
    rec = ex.parse_extraction(out)
    assert rec["relevant"] is True and rec["title"] == "T" and rec["keywords"] == ["k"]
    # unparseable -> not relevant (skipped), never raises
    assert ex.parse_extraction("no json here")["relevant"] is False


def test_extract_record_uses_llm_and_stable_id() -> None:
    fake = cfg.FakeLLMClient(lambda p: '{"relevant": true, "title": "X", "summary": "Y", "keywords": [], "concepts": ["z"]}')
    r1 = ex.extract_record("hello world", fake)
    r2 = ex.extract_record("hello world", fake)
    assert r1["doc_id"] == r2["doc_id"]  # stable hash id
    assert r1["title"] == "X" and r1["concepts"] == ["z"]


# --------------------------------------------------------------------------- #
# Librarian orchestration (LIB-1…9)
# --------------------------------------------------------------------------- #

def _topic_llm():
    # relevant for the radiation doc, not relevant for the cooking doc
    def responder(prompt: str) -> str:
        if "RADIATION" in prompt:
            return ('{"relevant": true, "title": "Rad", "summary": "rad sum", '
                    '"keywords": ["radiotherapy"], "concepts": ["cancer treatment"]}')
        return '{"relevant": false}'
    return cfg.FakeLLMClient(responder)


def test_research_topic_indexes_relevant_and_skips_rest(tmp_path: Path) -> None:
    ix = li.LibraryIndex(":memory:")
    source = lb.StaticSource({"med": [
        {"doc_id": "d1", "text": "RADIATION therapy study", "source": "jstor"},
        {"doc_id": "d2", "text": "how to bake bread", "source": "blog"},
    ]})
    lib = lb.Librarian(ix, _topic_llm(), source, metadata_dir=tmp_path / "meta")
    lib.register_topic("med")
    res = lib.research_topic("med")
    assert res["fetched"] == 2 and res["indexed"] == ["d1"] and res["skipped"] == ["d2"]
    assert ix.get("d1") is not None and ix.get("d2") is None
    # LIB-6: a metadata file agents look for was written
    meta = json.loads((tmp_path / "meta" / "med.json").read_text(encoding="utf-8"))
    assert meta["topic"] == "med" and meta["documents"][0]["doc_id"] == "d1"
    ix.close()


def test_build_scheduler_tasks_and_install_descriptor() -> None:
    ix = li.LibraryIndex(":memory:")
    lib = lb.Librarian(ix, _topic_llm(), lb.StaticSource({"a": [], "b": []}))
    lib.register_topic("a")
    lib.register_topic("b")
    tasks = lib.build_scheduler_tasks(interval_seconds=3600)
    assert {t.name for t in tasks} == {"librarian:a", "librarian:b"}
    d = lib.install_descriptor("linux", "/usr/bin/python -m librarian")
    assert d["kind"] == "systemd" and "Restart=always" in d["content"]
    ix.close()


# --------------------------------------------------------------------------- #
# remediation edge cases (adversarial-review v3.24.0)
# --------------------------------------------------------------------------- #

def test_parse_handles_braces_in_string_value() -> None:
    # a } / { inside a JSON string value must NOT truncate the object (string-aware)
    out = '{"relevant": true, "title": "Keep", "summary": "use } and { here", "keywords": [], "concepts": []}'
    rec = ex.parse_extraction(out)
    assert rec["relevant"] is True and rec["title"] == "Keep" and "}" in rec["summary"]
    # a stray brace pair before the real JSON object is skipped to the valid one
    out2 = 'note {x} then {"relevant": true, "title": "T", "summary": "s", "keywords": [], "concepts": []}'
    assert ex.parse_extraction(out2)["title"] == "T"


def test_conceptual_search_empty_and_unicode_fold() -> None:
    ix = li.LibraryIndex(":memory:")
    ix.add_document({"doc_id": "c1", "title": "Cafés", "summary": "",
                     "keywords": [], "concepts": ["café culture"]})
    assert ix.conceptual_search("") == []           # empty query -> no results, no crash
    assert ix.conceptual_search("cafe")             # diacritic-folded match (cafe ~ café)
    assert ix.search_by_concept("cafe")             # folded keyword/concept lookup too
    ix.close()


def test_relevant_but_empty_title_and_summary_is_skipped() -> None:
    ix = li.LibraryIndex(":memory:")
    fake = cfg.FakeLLMClient(lambda p: '{"relevant": true, "title": "", "summary": "", "keywords": [], "concepts": []}')
    lib = lb.Librarian(ix, fake, lb.StaticSource({"t": [{"doc_id": "e1", "text": "x"}]}))
    lib.register_topic("t")
    res = lib.research_topic("t")
    assert res["indexed"] == [] and res["skipped"] == ["e1"]  # the (title or summary) gate
    ix.close()


def test_file_folder_body_storage_and_path_safety(tmp_path: Path) -> None:
    ix = li.LibraryIndex(":memory:")
    source = lb.StaticSource({"med": [{"doc_id": "weird/../id", "text": "RADIATION body", "source": "x"}]})
    lib = lb.Librarian(ix, _topic_llm(), source, body_dir=tmp_path / "bodies")
    lib.register_topic("med")
    lib.research_topic("med")
    assert lib.get_body("weird/../id") == "RADIATION body"  # round-trips via sanitized name
    files = list((tmp_path / "bodies").glob("*.txt"))
    assert len(files) == 1 and files[0].parent == (tmp_path / "bodies")  # no traversal escape
    ix.close()


def test_scheduler_tasks_bind_per_topic() -> None:
    ix = li.LibraryIndex(":memory:")
    source = lb.StaticSource({
        "a": [{"doc_id": "a1", "text": "RADIATION a"}],
        "b": [{"doc_id": "b1", "text": "RADIATION b"}],
    })
    lib = lb.Librarian(ix, _topic_llm(), source)
    lib.register_topic("a")
    lib.register_topic("b")
    tasks = {t.name: t for t in lib.build_scheduler_tasks()}
    tasks["librarian:a"].fn()  # must research ONLY topic 'a' (per-topic closure binding)
    assert ix.get("a1") is not None and ix.get("b1") is None
    ix.close()
