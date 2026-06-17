# -*- coding: utf-8 -*-
"""The tally queue: batch + count duplicate issues; promote recurring ones to a
longer-lasting backlog (EVAL-4 / EVAL-10) — stdlib-only.

Many issues are systemic, so the same fingerprint (`issue.fingerprint`) arrives
repeatedly. The tally queue collapses duplicates into ONE entry carrying a count +
a representative + the versions it was seen on, so the open-ask list can't grow
uncontrollably (EVAL-4). Entries whose count crosses a threshold are promoted to
the backlog — the triage process (EVAL-10).

In-memory + deterministic (the real server persists to Postgres — the separated
tier's own dependency, REPO-4; this is the testable core).
"""
from __future__ import annotations

from typing import Any, Optional

DEFAULT_BACKLOG_THRESHOLD = 3


class TallyQueue:
    """fingerprint -> {count, representative, category, what, versions} (EVAL-4)."""

    def __init__(self, *, backlog_threshold: int = DEFAULT_BACKLOG_THRESHOLD):
        self.backlog_threshold = backlog_threshold
        self._entries: dict[str, dict[str, Any]] = {}

    def add(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Add an issue, batching by fingerprint (EVAL-4). Returns the entry.
        Raises a clear `ValueError` (not a bare `KeyError`) on a fingerprint-less
        issue, for callers that bypass the server's own guard."""
        fp = issue.get("fingerprint")
        if not fp:
            raise ValueError("issue is missing 'fingerprint' (build it via issue.make_issue)")
        entry = self._entries.get(fp)
        if entry is None:
            entry = {
                "fingerprint": fp,
                "count": 0,
                "representative": issue,
                "category": issue.get("category"),
                "what": issue.get("what"),
                "versions": [],
            }
            self._entries[fp] = entry
        entry["count"] += 1
        ver = issue.get("version")
        if ver and ver not in entry["versions"]:
            entry["versions"].append(ver)
        return entry

    def tally(self, fingerprint: str) -> int:
        e = self._entries.get(fingerprint)
        return e["count"] if e else 0

    def summary(self) -> list[dict[str, Any]]:
        """The batched open-ask list (EVAL-4): one row per fingerprint with its
        count + a short representative, most-frequent first."""
        rows = [
            {"fingerprint": e["fingerprint"], "category": e["category"],
             "what": e["what"], "count": e["count"], "versions": sorted(e["versions"])}
            for e in self._entries.values()
        ]
        rows.sort(key=lambda r: (-r["count"], r["fingerprint"]))
        return rows

    def backlog(self, threshold: Optional[int] = None) -> list[dict[str, Any]]:
        """The longer-lasting backlog (EVAL-10): entries whose count >= threshold."""
        t = self.backlog_threshold if threshold is None else threshold
        return [r for r in self.summary() if r["count"] >= t]

    def __len__(self) -> int:
        return len(self._entries)
