# -*- coding: utf-8 -*-
"""DictionarySource (KS-2/4/5) — the read-only data-dictionary source adapter.

Serves `search_dictionary` / `get_table_details` / `find_relations` /
`get_dictionary_status` over a `data-dictionary.json` sidecar (the artifact
`scripts/data_dictionary/data_dictionary.py` produces) plus `docs/data-annotations/`
when present. Ranked search COMPOSES the Librarian's `LibraryIndex` (concept×3 /
keyword×2 / text×1) — not a re-implementation. Freshness is the two honest arms:
repo-side reference-file drift since `built_at`, and DB-side currency reported
`unknowable` without a live connection. Read-only: no tool writes the sidecar.

Sibling-import bootstrap (the pattern `services/librarian/daemon.py` uses): the
`sys.path.insert` below is a statement, not an import, so it is invisible to
`check_separation`; every bare import here is a `services/` sibling or a package
sibling (all import-clean). `bg_runtime` is imported lazily in `scheduler_task`.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

_HERE = Path(__file__).resolve().parent
for _rel in (_HERE, _HERE.parent / "librarian"):     # package siblings + library_index
    _s = str(_rel)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import adapter_base  # noqa: E402
import contracts as _contracts  # noqa: E402
import freshness as _freshness  # noqa: E402
import library_index  # noqa: E402  (the Librarian's index — composed, not forked)


class DictionarySource(adapter_base.SourceAdapter):
    """A read-only adapter over `data-dictionary.json` (+ `data-annotations/`)."""

    name = "dictionary"

    def __init__(
        self,
        dictionary_path: str,
        *,
        annotations_dir: Optional[str] = None,
        repo_root: Optional[str] = None,
        changed_paths_provider: Optional[Callable[[Any], Optional[list]]] = None,
    ) -> None:
        self.path = str(dictionary_path)
        self.annotations_dir = annotations_dir
        self.index: Optional[library_index.LibraryIndex] = None
        if changed_paths_provider is not None:
            self._changed_paths_provider = changed_paths_provider
        elif repo_root:
            self._changed_paths_provider = (
                lambda stamp: _freshness.git_changed_paths(stamp, repo_root))
        else:  # no repo root => drift is honestly unknowable (never a fake current)
            self._changed_paths_provider = lambda stamp: None
        self._load_and_index()
        self._hash = self._content_hash()

    # -- loading + indexing ---------------------------------------------------- #

    def _load_and_index(self) -> None:
        data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        self.built_at = data.get("built_at")
        self.tables = data.get("tables", {}) or {}
        self.reference_map = data.get("reference_map", {}) or {}
        self.relational_map = data.get("relational_map", []) or []
        if self.index is not None:
            self.index.close()
        index = library_index.LibraryIndex(":memory:")
        for table, tinfo in self.tables.items():
            fields = tinfo.get("fields", []) or []
            names = [f.get("field", "") for f in fields]
            types = [f.get("type", "") for f in fields]
            defs = [f.get("definition", "") for f in fields]
            provenances = sorted({f.get("provenance", "") for f in fields if f.get("provenance")})
            grain = (tinfo.get("grain") or {}).get("grain", "")
            summary = grain + " | " + "; ".join(f"{n}: {d}" for n, d in zip(names, defs))
            index.add_document({
                "doc_id": table, "title": table, "summary": summary,
                "keywords": names + types,
                "concepts": [table] + names + provenances,
                "source": "data-dictionary",
            })
        self.index = index

    def _content_hash(self) -> str:
        return hashlib.sha256(Path(self.path).read_bytes()).hexdigest()

    def refresh(self) -> bool:
        current = self._content_hash()
        if current == self._hash:
            return False
        self._load_and_index()
        self._hash = current
        return True

    def scheduler_task(self, interval_seconds: int = 300):
        import bg_runtime  # noqa: E402  (services/common sibling — lazy)
        return bg_runtime.ServiceTask(f"knowledge-reindex-{self.name}", interval_seconds, self.refresh)

    # -- freshness ------------------------------------------------------------- #

    def _reference_files(self) -> list:
        files: set = set()
        for section in ("by_table", "by_field"):
            for entries in (self.reference_map.get(section, {}) or {}).values():
                for entry in entries or []:
                    ref = entry.get("file")
                    if ref:
                        files.add(ref)
        return sorted(files)

    def _dictionary_freshness(self) -> dict:
        changed = self._changed_paths_provider(self.built_at)
        return _freshness.dictionary_freshness(
            changed_paths=changed, built_at=self.built_at,
            reference_files=self._reference_files())

    def _annotations_for(self, table: str) -> list:
        if not self.annotations_dir:
            return []
        directory = Path(self.annotations_dir)
        if not directory.is_dir():
            return []
        prefix = table + "."
        merged: list = []
        for annotation_file in sorted(directory.glob("*.json")):
            try:
                doc = json.loads(annotation_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for entry in doc.get("annotations", []) or []:
                anchor = str(entry.get("anchor", ""))
                if anchor == table or anchor.startswith(prefix):
                    merged.append(entry)
        return merged

    # -- tool handlers --------------------------------------------------------- #

    def _search(self, args: dict) -> dict:
        query = str(args.get("query", ""))
        top_k = int(args.get("top_k", 10) or 10)
        results = self.index.conceptual_search(query, top_k=top_k)
        return {"query": query, "results": results, "count": len(results),
                "freshness": self._dictionary_freshness()}

    def _table_details(self, args: dict) -> dict:
        table = str(args.get("table", ""))
        tinfo = self.tables.get(table)
        return {"table": table, "found": tinfo is not None,
                "grain": (tinfo or {}).get("grain", {}) or {},
                "fields": (tinfo or {}).get("fields", []) or [],
                "annotations": self._annotations_for(table),
                "freshness": self._dictionary_freshness()}

    def _find_relations(self, args: dict) -> dict:
        table = str(args.get("table", "") or "")
        relations = [r for r in self.relational_map
                     if not table or r.get("from_table") == table or r.get("to_table") == table]
        return {"table": table, "relations": relations, "count": len(relations),
                "freshness": self._dictionary_freshness()}

    def _status(self, args: dict) -> dict:
        fresh = self._dictionary_freshness()
        return {
            "built_at": str(self.built_at or "unknown"),
            "repo_side": fresh,
            "db_side": {"verdict": "unknowable",
                        "note": "DB-side currency requires a live connection; not attempted (read path)"},
            "reference_file_count": len(self._reference_files()),
            "freshness": fresh,
        }

    def tools(self) -> list:
        contracts = _contracts.tool_contracts()
        return [
            adapter_base.Tool(
                "search_dictionary",
                "Ranked keyword search over the data dictionary (composes the Librarian index).",
                {"type": "object", "properties": {"query": {"type": "string"},
                                                  "top_k": {"type": "integer"}},
                 "required": ["query"]},
                self._search, output_contract=contracts["search_dictionary"]),
            adapter_base.Tool(
                "get_table_details",
                "A table's grain + fields, with docs/data-annotations merged at query time.",
                {"type": "object", "properties": {"table": {"type": "string"}},
                 "required": ["table"]},
                self._table_details, output_contract=contracts["get_table_details"]),
            adapter_base.Tool(
                "find_relations",
                "Relational-map entries (DB FKs + code joins) touching a table.",
                {"type": "object", "properties": {"table": {"type": "string"}}},
                self._find_relations, output_contract=contracts["find_relations"]),
            adapter_base.Tool(
                "get_dictionary_status",
                "Two-arm freshness: reference-file drift since built_at + DB-side unknowable.",
                {"type": "object", "properties": {}},
                self._status, output_contract=contracts["get_dictionary_status"]),
        ]
