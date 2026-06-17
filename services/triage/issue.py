# -*- coding: utf-8 -*-
"""The triage Issue record + de-duplication fingerprint (EVAL-8/9/14) — stdlib-only.

Every logged issue — whether from the automatic evaluator (EVAL-1) or the manual
helpdesk path (HD-1) — is normalized to one record shape so the server-side triage
treats both identically (HD-3). The record captures what the issue is, what
happened, the version + metadata (EVAL-8/9), and the (privacy-redacted) evidence
needed to reproduce it (EVAL-14, subject to EVAL-15…17). A stable `fingerprint`
(normalized category + what) is the dedup key the tally queue batches on (EVAL-4).

Privacy is NOT reinvented here: evidence is redacted by REUSING the helpdesk engine
`scripts/helpdesk/logit.py` (`redact_evidence` + its allow-list), so the automatic
and manual paths share ONE privacy implementation (EVAL-15…17).
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys
from typing import Any, Optional

# reuse the helpdesk privacy engine (EVAL-15…17) instead of reinventing it
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts" / "helpdesk"))
import logit as _logit  # noqa: E402

VALID_SOURCES = ("auto", "manual-helpdesk")


def fingerprint(category: str, what: str) -> str:
    """The dedup key (EVAL-4): a stable hash of the normalized category + what.
    Case/whitespace-insensitive so near-identical reports collapse to one tally.

    The two fields are joined with a NUL (`\\x00`) sentinel — NUL is NOT matched by
    `\\s`, so the field boundary SURVIVES whitespace-collapse and distinct
    `(category, what)` pairs can't alias to the same key (e.g. `("drift","loop")`
    vs `("drift loop","")`)."""
    def _n(s: str) -> str:
        return re.sub(r"\s+", " ", str(s).strip().lower())
    norm = _n(category) + "\x00" + _n(what)
    return "iss-" + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def make_issue(
    category: str,
    what: str,
    what_happened: str,
    *,
    version: str,
    source: str = "auto",
    fix_just_deployed: bool = False,
    prior_occurrence: bool = False,
    evidence: Optional[list[dict[str, Any]]] = None,
    privacy_level: str = "off",
    issue_id: Optional[str] = None,
    ts: Optional[int] = None,
) -> dict[str, Any]:
    """Build a normalized issue record (EVAL-8/9/14).

    `version` is REQUIRED (EVAL-8). `evidence` is redacted by the shared helpdesk
    privacy engine at the given `privacy_level` (EVAL-15…17) — under `summary` no
    identifiable data is carried, and under `off` NONE is. The default is `off`
    (default-deny — EVAL-17: logging is OFF by default on every new installation; a
    caller that wants evidence shared must opt in to `summary`/`full`). `fingerprint`
    is the dedup key (EVAL-4). Raises on a missing version / bad privacy / bad source.
    """
    if not version:
        raise ValueError("an issue must record the version (EVAL-8)")
    if privacy_level not in _logit.PRIVACY_LEVELS:
        raise ValueError(f"invalid privacy_level {privacy_level!r} (allowed: {_logit.PRIVACY_LEVELS})")
    if source not in VALID_SOURCES:
        raise ValueError(f"invalid source {source!r} (allowed: {VALID_SOURCES})")
    fp = fingerprint(category, what)
    redacted = [] if privacy_level == "off" else _logit.redact_evidence(evidence, privacy_level)
    return {
        "schema": "triage-issue/v1",
        "issue_id": issue_id or fp,
        "fingerprint": fp,
        "category": category,
        "what": what,
        "what_happened": what_happened,
        "version": version,                              # EVAL-8
        "source": source,                               # auto (EVAL-1) or manual-helpdesk (HD-3)
        "fix_just_deployed": bool(fix_just_deployed),    # EVAL-9
        "prior_occurrence": bool(prior_occurrence),      # EVAL-9
        "privacy_level": privacy_level,
        "evidence": redacted,                            # EVAL-14 subject to EVAL-15…17
        "ts": ts,
    }
