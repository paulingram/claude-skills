# -*- coding: utf-8 -*-
"""The Librarian's reference index + conceptual search (LIB-10 … LIB-13) — stdlib-only.

For everything the Librarian ingests it stores a title, a summary, strong
searchable keywords, and a "concept cloud" (the set of concepts the document is
useful for), and builds reference tables for lookup by keyword and by concept
(LIB-11/12). This is the deterministic store, backed by stdlib `sqlite3` — the
LIB-13 "local ephemeral store" (sqlite stands in for the suggested Postgres; the
service tier may swap in Postgres when separated). LIB-8's "file folder" mode
keeps document bodies on disk (the Librarian's `body_dir`) with THIS index over
them; the MemPalace vector store (LIB-9 preferred) is an adapter, not here.

Conceptual search (LIB-10): docs are ranked by the weighted overlap of the query
terms with each doc's concept cloud (weighted highest), keywords, and title/summary
tokens. This delivers related-concept retrieval ONLY to the extent the LLM
populated a rich concept cloud per doc (LIB-12) — it is overlap of unicode-folded
tokens, NOT semantic/synonym/stem expansion ("oncology" will not by itself match a
"cancer" concept, nor "patient" match "patients"). True semantic relatedness is
the LIB-9 vector-store adapter; this is the deterministic stdlib stand-in.
"""
from __future__ import annotations

import re
import sqlite3
import time
import unicodedata
from typing import Any, Optional

# concept matches weigh most (LIB-12 — what the doc is *useful for*), then
# keywords (LIB-11 strong searchable terms), then title/summary tokens.
_W_CONCEPT = 3
_W_KEYWORD = 2
_W_TEXT = 1


def _fold(s: Any) -> str:
    """Unicode-fold: strip combining marks (NFKD) so `café`/`Zürich` index + match
    by their base letters, and casefold for case-insensitive comparison."""
    decomposed = unicodedata.normalize("NFKD", str(s if s is not None else ""))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"\w+", _fold(s)))


def _norm(s: str) -> str:
    return _fold(s).strip()


class LibraryIndex:
    """A keyword / summary / concept-cloud reference index over the Librarian's
    documents (LIB-11/12/13), backed by stdlib sqlite (`:memory:` by default)."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents(
              doc_id TEXT PRIMARY KEY, title TEXT, summary TEXT, source TEXT, added_at INTEGER);
            CREATE TABLE IF NOT EXISTS keywords(doc_id TEXT, keyword TEXT);
            CREATE TABLE IF NOT EXISTS concepts(doc_id TEXT, concept TEXT);
            CREATE INDEX IF NOT EXISTS ix_kw ON keywords(keyword);
            CREATE INDEX IF NOT EXISTS ix_concept ON concepts(concept);
            """
        )
        self.conn.commit()

    def add_document(self, record: dict[str, Any], *, added_at: Optional[int] = None) -> str:
        """Index a document record `{doc_id, title, summary, keywords[], concepts[],
        source?}`. Re-adding the same `doc_id` replaces it (idempotent re-index)."""
        doc_id = record["doc_id"]
        ts = int(added_at if added_at is not None else time.time())
        c = self.conn
        c.execute(
            "INSERT OR REPLACE INTO documents(doc_id,title,summary,source,added_at) VALUES(?,?,?,?,?)",
            (doc_id, record.get("title", ""), record.get("summary", ""), record.get("source", ""), ts),
        )
        c.execute("DELETE FROM keywords WHERE doc_id=?", (doc_id,))
        c.execute("DELETE FROM concepts WHERE doc_id=?", (doc_id,))
        for kw in record.get("keywords", []) or []:
            if _norm(kw):
                c.execute("INSERT INTO keywords(doc_id,keyword) VALUES(?,?)", (doc_id, _norm(kw)))
        for cp in record.get("concepts", []) or []:
            if _norm(cp):
                c.execute("INSERT INTO concepts(doc_id,concept) VALUES(?,?)", (doc_id, _norm(cp)))
        c.commit()
        return doc_id

    def get(self, doc_id: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["keywords"] = [r["keyword"] for r in self.conn.execute(
            "SELECT keyword FROM keywords WHERE doc_id=? ORDER BY keyword", (doc_id,))]
        d["concepts"] = [r["concept"] for r in self.conn.execute(
            "SELECT concept FROM concepts WHERE doc_id=? ORDER BY concept", (doc_id,))]
        return d

    def summary(self, doc_id: str) -> Optional[str]:
        """LIB-11 — the summary an agent reads to decide whether to fetch the full doc."""
        row = self.conn.execute("SELECT summary FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        return row["summary"] if row else None

    def search_by_keyword(self, keyword: str) -> list[str]:
        kw = _norm(keyword)
        rows = self.conn.execute(
            "SELECT DISTINCT doc_id FROM keywords WHERE keyword=? OR keyword LIKE ? ORDER BY doc_id",
            (kw, f"%{kw}%"),
        )
        return [r["doc_id"] for r in rows]

    def search_by_concept(self, concept: str) -> list[str]:
        cp = _norm(concept)
        rows = self.conn.execute(
            "SELECT DISTINCT doc_id FROM concepts WHERE concept=? OR concept LIKE ? ORDER BY doc_id",
            (cp, f"%{cp}%"),
        )
        return [r["doc_id"] for r in rows]

    def conceptual_search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """LIB-10 conceptual search: rank documents by the weighted overlap of the
        query's terms with each doc's concept cloud (×3), keywords (×2), and
        title+summary tokens (×1). Returns ranked `{doc_id, title, summary, score,
        matched}` for docs with score > 0."""
        terms = _tokens(query)
        if not terms:
            return []
        results = []
        for row in self.conn.execute("SELECT doc_id, title, summary FROM documents"):
            doc_id = row["doc_id"]
            concepts = {r["concept"] for r in self.conn.execute(
                "SELECT concept FROM concepts WHERE doc_id=?", (doc_id,))}
            keywords = {r["keyword"] for r in self.conn.execute(
                "SELECT keyword FROM keywords WHERE doc_id=?", (doc_id,))}
            concept_tokens = {t for c in concepts for t in _tokens(c)}
            keyword_tokens = {t for k in keywords for t in _tokens(k)}
            text_tokens = _tokens(row["title"]) | _tokens(row["summary"])
            mc = terms & concept_tokens
            mk = terms & keyword_tokens
            mt = terms & text_tokens
            score = _W_CONCEPT * len(mc) + _W_KEYWORD * len(mk) + _W_TEXT * len(mt)
            if score > 0:
                results.append({
                    "doc_id": doc_id, "title": row["title"], "summary": row["summary"],
                    "score": score, "matched": sorted(mc | mk | mt),
                })
        results.sort(key=lambda r: (-r["score"], r["doc_id"]))
        return results[:top_k]

    def all_concepts(self) -> list[dict[str, Any]]:
        """The library-wide concept cloud: each concept + how many docs carry it."""
        rows = self.conn.execute(
            "SELECT concept, COUNT(DISTINCT doc_id) AS n FROM concepts GROUP BY concept ORDER BY n DESC, concept")
        return [{"concept": r["concept"], "documents": r["n"]} for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]

    def close(self) -> None:
        self.conn.close()
