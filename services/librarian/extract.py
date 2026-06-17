# -*- coding: utf-8 -*-
"""Document extraction for the Librarian (LIB-11 / LIB-12) — stdlib + an LLM adapter.

For everything it downloads, the Librarian reads it, confirms it is relevant, and
extracts a title, a summary (so an agent can decide whether to read the full
doc), strong searchable keywords, and a concept cloud (the concepts the doc is
useful for). The LLM does the reading/judgment via an injected `LLMClient`
(`services/common/service_config.py`); the prompt + the robust JSON parse here are
deterministic and testable with `FakeLLMClient`.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


def build_extraction_prompt(text: str, topic: Optional[str] = None) -> str:
    """The extraction prompt (LIB-11/12). Asks for a single JSON object so the
    output is machine-parseable (the same structured-output discipline as the MCP
    tier). A `relevant` flag lets the Librarian drop off-topic downloads."""
    head = f"Research topic: {topic}\n\n" if topic else ""
    return (
        head
        + "Read the following document. First decide whether it is RELEVANT to the "
        "topic and worth keeping. Then extract: a concise title; a summary written so "
        "a reader can decide whether to read the full document; strong, specific, "
        "searchable keywords; and the CONCEPT CLOUD — the set of concepts/uses the "
        "document is good for (e.g. a radiation-therapy paper is useful for medical "
        "researchers, cancer patients, comorbidity statistics, uses of radiation).\n"
        'Respond with ONLY a JSON object of the form: {"relevant": true, '
        '"title": "...", "summary": "...", "keywords": ["..."], "concepts": ["..."]}\n\n'
        "DOCUMENT:\n" + (text or "")
    )


def parse_extraction(output: str) -> dict[str, Any]:
    """Parse the LLM's JSON reply robustly. Uses the stdlib STRING-AWARE
    `JSONDecoder.raw_decode` (so a `{`/`}` inside a string VALUE — e.g. a summary
    reading "use } here" — does not miscount and truncate the object) starting at
    each `{` until one decodes to a dict. An unparseable reply yields a
    not-relevant record (the Librarian skips it) rather than raising."""
    data: dict[str, Any] = {}
    text = output or ""
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            parsed, _end = decoder.raw_decode(text, idx)
            if isinstance(parsed, dict):
                data = parsed
                break
        except ValueError:
            pass
        idx = text.find("{", idx + 1)

    def _strlist(v: Any) -> list[str]:
        if not isinstance(v, (list, tuple)):
            return []
        return [str(x).strip() for x in v if str(x).strip()]

    return {
        "relevant": bool(data.get("relevant", False)),
        "title": str(data.get("title", "")).strip(),
        "summary": str(data.get("summary", "")).strip(),
        "keywords": _strlist(data.get("keywords")),
        "concepts": _strlist(data.get("concepts")),
    }


def _stable_doc_id(text: str) -> str:
    return "doc-" + hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def extract_record(
    text: str,
    llm: Any,
    *,
    topic: Optional[str] = None,
    doc_id: Optional[str] = None,
    source: str = "",
) -> dict[str, Any]:
    """Read `text` via `llm` and return an index record `{doc_id, title, summary,
    keywords, concepts, relevant, source}`. `doc_id` defaults to a stable hash of
    the text (so re-ingesting the same document is idempotent)."""
    parsed = parse_extraction(llm.complete(build_extraction_prompt(text, topic)))
    parsed["doc_id"] = doc_id or _stable_doc_id(text)
    parsed["source"] = source
    return parsed
