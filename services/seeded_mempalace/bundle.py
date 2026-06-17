# -*- coding: utf-8 -*-
"""The seeded-MemPalace bundle schema + merge (SMP-3 / SMP-5) — stdlib-only.

SMP-3: the seeded MemPalace ships with a CLEAR DEFINED SCHEMA plus additional
curated content, while LEAVING ROOM for the user's own projects. SMP-5: it carries
the latest research documentation + synthesis so "best-in-class practice" requests
rely on continually-updated content, not the LLM's training cutoff.

This module defines the bundle shape, validates it, and MERGES a freshly-downloaded
bundle into a local MemPalace WITHOUT clobbering the user's own namespace — so a
re-download (SMP-5 freshness) refreshes the seeded sections but never touches the
user's projects.

HONEST BOUNDARY: the real MemPalace is a ChromaDB vector store; this is the
deterministic bundle CONTRACT + merge logic. Writing the merged result into the
actual ChromaDB is the operator's adapter.
"""
from __future__ import annotations

import copy
from typing import Any, Optional

SCHEMA = "seeded-mempalace/v1"
# SMP-3: the user's own projects live under this reserved namespace; a seeded
# bundle merge replaces the seeded sections but NEVER touches this key.
USER_NAMESPACE = "user-projects"
REQUIRED_SECTIONS = ("schema", "curated", "phenotype_catalog", "research_synthesis")


def build_bundle(
    *,
    schema: dict[str, Any],
    curated: Optional[list] = None,
    phenotype_catalog: Optional[dict[str, Any]] = None,
    research_synthesis: Optional[dict[str, Any]] = None,
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    """Assemble a seeded-MemPalace bundle (SMP-3). `schema` is the defined record
    schema; `curated` the curated content; `phenotype_catalog` the SMP-4 catalog;
    `research_synthesis` the SMP-5 latest-research section (`{last_updated, entries}`)."""
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "generated_at": generated_at,
        "user_namespace": USER_NAMESPACE,
        "sections": {
            "schema": schema or {},
            "curated": list(curated or []),
            "phenotype_catalog": phenotype_catalog or {"schema": "phenotype-catalog/v1", "entries": []},
            "research_synthesis": research_synthesis or {"last_updated": None, "entries": []},
        },
    }


def validate_bundle(bundle: Any) -> dict[str, Any]:
    """Validate a bundle's shape (SMP-3/5). Returns `{valid, errors}`."""
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return {"valid": False, "errors": ["bundle is not an object"]}
    if bundle.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    if bundle.get("user_namespace") != USER_NAMESPACE:
        errors.append(f"user_namespace must be {USER_NAMESPACE!r} (room for the user's own projects)")
    sections = bundle.get("sections")
    if not isinstance(sections, dict):
        errors.append("sections must be an object")
    else:
        for s in REQUIRED_SECTIONS:
            if s not in sections:
                errors.append(f"missing section: {s}")
        rs = sections.get("research_synthesis")
        if isinstance(rs, dict) and "last_updated" not in rs:
            errors.append("research_synthesis must carry last_updated (SMP-5 freshness)")
    return {"valid": not errors, "errors": errors}


def merge_into_local(local: Optional[dict[str, Any]], bundle: dict[str, Any]) -> dict[str, Any]:
    """Merge a downloaded bundle into a local MemPalace (SMP-3). ONLY the seeded keys
    (`schema` / `sections` / `seeded_from`) are refreshed from the bundle (so a
    re-download updates them, SMP-5); EVERY other top-level key in `local` — the
    reserved user namespace AND any other namespace / collection / metadata the user
    stored — is PRESERVED untouched, so the seeded load never clobbers the user's own
    projects. (A real MemPalace has arbitrary collection names, not just the two this
    bundle knows about.) The seeded `sections` are deep-copied so later mutation of
    the bundle can't corrupt the merged store."""
    merged = dict(local or {})                              # preserve ALL existing keys
    merged["schema"] = SCHEMA
    merged["sections"] = copy.deepcopy(bundle.get("sections", {}))   # seeded sections refreshed
    merged["seeded_from"] = bundle.get("generated_at")
    merged.setdefault(USER_NAMESPACE, {})                  # ensure the user namespace exists
    return merged
