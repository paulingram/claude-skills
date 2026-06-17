# -*- coding: utf-8 -*-
"""The Librarian orchestration (LIB-1 … LIB-9) — stdlib + adapters.

A background curation/research service: it pulls data for user-defined topics
(LIB-4/5/9), reads + extracts each download (LIB-11/12 via `extract`), indexes the
keepers (LIB-8/13 via `LibraryIndex`), and writes metadata files agents look for
(LIB-6). It runs on the shared BG runtime (LIB-2/5 — scheduled, restartable) and
uses the shared configurable Claude API (LIB-1/3 via the injected `LLMClient`).

HONEST BOUNDARY: the actual data SOURCE (web scrape / an attached API endpoint,
LIB-6) and the MemPalace VECTOR store (LIB-9 preferred) are adapters — `Source`
here is an interface with `StaticSource` for tests; real fetching + the vector
store are the operator's to provide. The deterministic flow (fetch → extract →
index → metadata) + the file-folder body store (`body_dir`, LIB-8) + the sqlite
index are the testable core. NOT built here (design-stage): LIB-4's centralized
MemPalace curation ENDPOINT (topics are a local registry here, not a server-side
curation point) and LIB-7's global-MemPalace-install research/standardization.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any, Optional

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))                       # library_index, extract (siblings)
sys.path.insert(0, str(_here.parent / "common"))     # bg_runtime (shared substrate)
import extract as _extract  # noqa: E402
import library_index as _library_index  # noqa: E402
try:  # bg_runtime is optional at import time (scheduling is opt-in)
    import bg_runtime as _bg  # noqa: E402
except Exception:  # pragma: no cover
    _bg = None


def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(topic).lower()).strip("-") or "topic"


class Source:
    """Abstract content source (LIB-6). `fetch(topic)` returns
    `[{doc_id?, text, source?}, ...]`. Real web/API sources implement this; the
    Librarian's logic never assumes network."""

    def fetch(self, topic: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class StaticSource(Source):
    """Deterministic test/offline source: returns fixed documents per topic."""

    def __init__(self, docs_by_topic: dict[str, list[dict[str, Any]]]):
        self._docs = {k: list(v) for k, v in docs_by_topic.items()}

    def fetch(self, topic: str) -> list[dict[str, Any]]:
        return list(self._docs.get(topic, []))


class Librarian:
    """Ties the source + LLM + index together. `research_topic` is the core flow;
    `build_scheduler_tasks` registers it on the BG runtime (LIB-5 ongoing)."""

    def __init__(self, index: "_library_index.LibraryIndex", llm: Any, source: Source,
                 *, metadata_dir: Optional[str | pathlib.Path] = None,
                 body_dir: Optional[str | pathlib.Path] = None):
        self.index = index
        self.llm = llm
        self.source = source
        self.metadata_dir = pathlib.Path(metadata_dir) if metadata_dir else None
        # LIB-8 "file folder" mode: when set, full document bodies are stored on
        # disk here, with the sqlite index over them.
        self.body_dir = pathlib.Path(body_dir) if body_dir else None
        self.topics: set[str] = set()

    def register_topic(self, topic: str) -> str:
        """Register an ongoing research topic (LIB-4/9)."""
        self.topics.add(topic)
        return topic

    def research_topic(self, topic: str) -> dict[str, Any]:
        """Fetch the topic's documents, read+extract each (LIB-11/12), index the
        relevant keepers (LIB-8), and (when configured) write the metadata file
        agents look for (LIB-6). Returns a per-run summary."""
        fetched = self.source.fetch(topic)
        indexed: list[str] = []
        skipped: list[str] = []
        for d in fetched:
            rec = _extract.extract_record(
                d.get("text", ""), self.llm, topic=topic,
                doc_id=d.get("doc_id"), source=d.get("source", ""),
            )
            if rec["relevant"] and (rec["title"] or rec["summary"]):
                self.index.add_document(rec)
                indexed.append(rec["doc_id"])
                if self.body_dir is not None:  # LIB-8 file-folder body store
                    self._store_body(rec["doc_id"], d.get("text", ""))
            else:
                skipped.append(rec["doc_id"])
        if self.metadata_dir is not None:
            self._write_metadata(topic, indexed)
        return {"topic": topic, "fetched": len(fetched), "indexed": indexed, "skipped": skipped}

    def _write_metadata(self, topic: str, indexed_ids: list[str]) -> pathlib.Path:
        """Write the per-topic metadata file agents read (LIB-6)."""
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        docs = [self.index.get(i) for i in indexed_ids]
        path = self.metadata_dir / f"{_slug(topic)}.json"
        path.write_text(
            json.dumps({"topic": topic, "documents": docs}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def _store_body(self, doc_id: str, text: str) -> pathlib.Path:
        """LIB-8 — persist a full document body to the file folder. The filename
        is sanitized so an operator-supplied doc_id can't escape `body_dir`."""
        self.body_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(doc_id)) or "doc"
        path = self.body_dir / f"{safe}.txt"
        path.write_text(text or "", encoding="utf-8")
        return path

    def get_body(self, doc_id: str) -> Optional[str]:
        """Read a stored body back (LIB-8 file-folder mode), or None."""
        if self.body_dir is None:
            return None
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(doc_id)) or "doc"
        path = self.body_dir / f"{safe}.txt"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def build_scheduler_tasks(self, interval_seconds: int = 3600) -> list:
        """Return a BG `ServiceTask` per registered topic (LIB-5 — pull ongoing
        throughout the day). Register these on a `bg_runtime.Scheduler`."""
        if _bg is None:
            raise RuntimeError("bg_runtime is unavailable")
        return [
            _bg.ServiceTask(f"librarian:{_slug(t)}", interval_seconds,
                            fn=(lambda t=t: self.research_topic(t)))
            for t in sorted(self.topics)
        ]

    def install_descriptor(self, platform: str, command: str, **kwargs) -> dict[str, str]:
        """The per-OS boot/restart install descriptor for the librarian daemon
        (LIB-2/3), via the BG runtime."""
        if _bg is None:
            raise RuntimeError("bg_runtime is unavailable")
        return _bg.install_descriptor(platform, "ct6-librarian", command, **kwargs)
