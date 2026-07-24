# -*- coding: utf-8 -*-
"""Frontend-impact detection — the trigger for the v3.44.0 end-to-end gate.

A change has "frontend impact" when EITHER signal fires (the broadest, either-OR
reading the owner chose 2026-07-24):

  (a) the change set touches a frontend file (by extension, or by living under a
      clear frontend directory hint), OR
  (b) a changed backend endpoint/contract is consumed by a frontend route — i.e.
      one of the changed endpoints appears in a frontend map (ROUTE_MAP.md's API
      catalog or INTEGRATION_MAP.md's cross-codebase consumption record).

When impact is present, the review gate makes a real-frontend end-to-end
Playwright verdict MANDATORY before "done" — a passing unit test can never
satisfy it (see hooks/review_evidence_schema.py `frontend_impact_e2e_review`).

This is the canonical frontend-file extension set for CT6 (nothing defined it
before). Pure, stdlib-only, no I/O: the caller supplies the changed file list,
the changed-endpoint list (derived from the backend diff), and the map texts.
"""
from __future__ import annotations

import posixpath
from typing import Any, Dict, List, Optional, Sequence

# Canonical frontend-file extensions. Mirrors the surface the review-gate's
# visual_fidelity_review already treats as "a frontend file"
# (hooks/review_evidence_schema.py) — kept here as the single importable source.
FRONTEND_FILE_EXTENSIONS = frozenset({
    ".tsx", ".jsx", ".vue", ".svelte", ".astro",
    ".css", ".scss", ".sass", ".less", ".styl",
    ".html", ".htm",
})

# Ambiguous extensions (could be backend Node/tooling) that count as frontend
# ONLY when the path also carries a frontend directory hint.
_AMBIGUOUS_EXTENSIONS = frozenset({".ts", ".js", ".mjs", ".cjs"})

# Directory-name hints that mark a path as frontend even for an ambiguous ext.
_FRONTEND_DIR_HINTS = (
    "/components/", "/pages/", "/views/", "/screens/", "/layouts/",
    "/src/app/", "/app/", "/ui/", "/webapp/", "/frontend/", "/client/",
)


def _normalize(path: str) -> str:
    """Forward-slash, lowercased path with a leading slash for hint matching."""
    p = str(path).replace("\\", "/").strip().lower()
    return "/" + p.lstrip("/")


def _is_frontend_file(path: str) -> bool:
    norm = _normalize(path)
    ext = posixpath.splitext(norm)[1]
    if ext in FRONTEND_FILE_EXTENSIONS:
        return True
    if ext in _AMBIGUOUS_EXTENSIONS and any(h in norm for h in _FRONTEND_DIR_HINTS):
        return True
    return False


def changed_files_touch_frontend(changed_files: Sequence[str]) -> List[str]:
    """Signal (a): the subset of ``changed_files`` that are frontend files,
    preserving input order."""
    if isinstance(changed_files, (str, bytes)):
        raise TypeError("changed_files must be a sequence of paths, not a string")
    return [f for f in changed_files if _is_frontend_file(f)]


def backend_contract_consumed_by_frontend(
    changed_endpoints: Optional[Sequence[str]],
    integration_map_text: Optional[str],
    route_map_text: Optional[str],
) -> List[Dict[str, str]]:
    """Signal (b): the changed endpoints that a frontend route consumes.

    An endpoint is "consumed by a frontend route" when its literal path appears
    in ROUTE_MAP.md's API catalog or INTEGRATION_MAP.md's consumption record —
    those maps document exactly the frontend→backend edges, so a hit is
    evidence the frontend depends on the changed contract. Returns one entry per
    hit: ``{"endpoint": <path>, "source": "route-map" | "integration-map"}``.
    """
    if not changed_endpoints:
        return []
    hits: List[Dict[str, str]] = []
    route_l = (route_map_text or "").lower()
    integ_l = (integration_map_text or "").lower()
    for ep in changed_endpoints:
        token = str(ep).strip().lower()
        if not token:
            continue
        if token in route_l:
            hits.append({"endpoint": ep, "source": "route-map"})
        elif token in integ_l:
            hits.append({"endpoint": ep, "source": "integration-map"})
    return hits


def detect_frontend_impact(
    changed_files: Sequence[str],
    *,
    changed_endpoints: Optional[Sequence[str]] = None,
    integration_map_text: Optional[str] = None,
    route_map_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the frontend-impact verdict for a change set.

    Result shape (stable)::

        {
          "impacted": bool,
          "frontend_files": [<path>, ...],        # signal (a)
          "backend_contract_hits": [{endpoint, source}, ...],  # signal (b)
          "signals": ["frontend-files"?, "backend-contract-consumed-by-frontend"?],
          "reason": "<human-readable>",
        }

    ``impacted`` is the OR of the two signals — either alone is sufficient. A
    non-sequence ``changed_files`` raises ``TypeError`` (a gate must not silently
    treat malformed input as "no impact").
    """
    frontend_files = changed_files_touch_frontend(changed_files)
    contract_hits = backend_contract_consumed_by_frontend(
        changed_endpoints, integration_map_text, route_map_text
    )

    signals: List[str] = []
    if frontend_files:
        signals.append("frontend-files")
    if contract_hits:
        signals.append("backend-contract-consumed-by-frontend")

    impacted = bool(signals)
    if not impacted:
        reason = "no frontend impact — no frontend files changed and no changed backend endpoint is consumed by a frontend route"
    else:
        parts: List[str] = []
        if frontend_files:
            parts.append(f"{len(frontend_files)} frontend file(s) changed")
        if contract_hits:
            eps = ", ".join(h["endpoint"] for h in contract_hits)
            parts.append(f"changed backend endpoint(s) consumed by a frontend route: {eps}")
        reason = "frontend impact — " + "; ".join(parts)

    return {
        "impacted": impacted,
        "frontend_files": frontend_files,
        "backend_contract_hits": contract_hits,
        "signals": signals,
        "reason": reason,
    }
