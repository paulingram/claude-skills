# -*- coding: utf-8 -*-
"""Server-side triage: two-stage review, the quarantine rule, resolution tracking,
and recurrence (EVAL-5/6/7/11/12/13) — stdlib-only.

The local agent emits issues; on the server, a collection point is reviewed and
broken into common core issues (EVAL-5). As resolutions land they are logged so the
review can flag "this may already be fixed" (EVAL-6). The MOST IMPORTANT piece is
the QUARANTINE RULE (EVAL-11/12): an issue first seen on an OLD version may already
have been fixed by an intermediate release the reporter simply hasn't upgraded to —
hold it in quarantine and verify whether it actually recurs FROM the fixed version
onward (EVAL-7), attaching occurrences as evidence (EVAL-13).

The version logic is deterministic here; the "agents judge it already fixed" signal
(EVAL-12) is an INPUT (`judged_already_fixed`) — an honest boundary between the
deterministic classifier and the LLM judgment that feeds it.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# triage statuses
OPEN = "open"
QUARANTINED = "quarantined"


def parse_version(v: Any) -> tuple[int, ...]:
    """Parse a dotted version ("3.12", "3.13.1", "v3.15") into a comparable tuple of
    ints, so `3.10 > 3.9` orders numerically (not as strings). Non-numeric junk is
    ignored; an unparseable/empty version sorts as (0,). NOTE: a prerelease like
    `3.13-rc1` is treated as its base numeric release (3,13,1) — the plugin uses
    plain X.Y.Z versions, so prereleases are not exercised in practice; if the
    project ever ships them, order them below the base release explicitly."""
    nums = re.findall(r"\d+", str(v if v is not None else ""))
    return tuple(int(n) for n in nums) or (0,)


def classify_issue(
    issue: dict[str, Any],
    *,
    current_version: str,
    similar_fix_versions: Optional[list[str]] = None,
    issue_fix_versions: Optional[list[str]] = None,
    judged_already_fixed: Optional[bool] = None,
) -> dict[str, Any]:
    """Classify a freshly-raised issue (EVAL-11/12). Returns `{status, reason, verify_from?}`.

    Inputs:
    - `current_version` — the latest package edition.
    - `similar_fix_versions` — versions where a fix for a SIMILAR problem landed.
    - `issue_fix_versions` — versions where THIS issue was directly addressed.
    - `judged_already_fixed` — the agents' judgment (EVAL-12) when there is no
      similar fix to anchor on; None = no judgment available.

    EVAL-11 (most important): the issue is raised for the first time and no fix has
    been attempted on the current/any later version FOR THIS ISSUE, but a SIMILAR fix
    landed in an INTERMEDIATE version (after the version the reporter saw it on, up to
    current) → QUARANTINE and verify from that fixed version onward (the reporter may
    simply not have upgraded).
    EVAL-12 (first-occurrence): first time seen, never addressed at any version, no
    similar fix to anchor on → evaluate the latest package; if the agents judge it
    already (incidentally) fixed, QUARANTINE; else OPEN.
    """
    seen = parse_version(issue.get("version"))
    current = parse_version(current_version)
    similar = sorted(((sv, parse_version(sv)) for sv in (similar_fix_versions or [])),
                     key=lambda kv: kv[1])
    issue_fixes = [parse_version(fv) for fv in (issue_fix_versions or [])]

    # A direct fix for THIS issue at/after the version it was observed on means it's
    # already being handled DIRECTLY — so it is not a candidate for the quarantine
    # rule, which is specifically about issues NOT directly addressed that a SIMILAR
    # fix may have caught incidentally. Boundary is `>= seen` (not `>= current`): any
    # direct fix from the observed version onward takes it out of "incidental-fix"
    # quarantine and into OPEN, where `RecurrenceTracker` confirms whether it holds.
    this_issue_fixed_after_seen = any(fv >= seen for fv in issue_fixes)

    # EVAL-11: an intermediate SIMILAR fix strictly after the seen version, up to current.
    intermediate = [(sv, ver) for sv, ver in similar if seen < ver <= current]
    if not this_issue_fixed_after_seen and intermediate:
        first_fix = intermediate[0][0]
        return {
            "status": QUARANTINED,
            "reason": (f"a similar fix landed in {first_fix} (after the reporting version "
                       f"{issue.get('version')}); the reporter may not have upgraded — "
                       f"verify the issue still occurs from {first_fix} onward (EVAL-11)"),
            "verify_from": first_fix,
        }

    # EVAL-12: first occurrence, never addressed, no similar fix — lean on the judgment.
    if not this_issue_fixed_after_seen and not similar and judged_already_fixed is True:
        return {
            "status": QUARANTINED,
            "reason": ("first occurrence, never addressed; the latest package is judged to "
                       f"have incidentally fixed it — verify from {current_version} onward "
                       "(EVAL-12)"),
            "verify_from": current_version,
        }

    return {"status": OPEN, "reason": "no anchoring fix; tracked as an open issue"}


class ResolutionLog:
    """EVAL-6: as issues are resolved, log the resolution (fingerprint → versions it
    was resolved in) so the review can flag incoming issues that may already be fixed."""

    def __init__(self) -> None:
        self._resolved: dict[str, list[str]] = {}

    def record_resolution(self, fingerprint: str, version: str) -> None:
        self._resolved.setdefault(fingerprint, [])
        if version not in self._resolved[fingerprint]:
            self._resolved[fingerprint].append(version)

    def maybe_already_fixed(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Flag whether a resolution was logged at/after the issue's version
        (EVAL-6 — "this may already be fixed")."""
        versions = self._resolved.get(issue.get("fingerprint"), [])
        seen = parse_version(issue.get("version"))
        later = sorted((v for v in versions if parse_version(v) >= seen), key=parse_version)
        return {"may_already_be_fixed": bool(later), "resolved_in": later}


class RecurrenceTracker:
    """EVAL-7/13: track whether a (quarantined) issue actually recurs FROM a given
    version onward — the evidence that decides whether a fix really worked."""

    def __init__(self) -> None:
        self._occurrences: dict[str, list[tuple]] = {}  # fp -> [(parsed_version, raw)]

    def record_occurrence(self, fingerprint: str, version: str) -> None:
        self._occurrences.setdefault(fingerprint, []).append((parse_version(version), version))

    def occurrences(self, fingerprint: str) -> list[str]:
        return [raw for _pv, raw in self._occurrences.get(fingerprint, [])]

    def recurs_from(self, fingerprint: str, verify_from: str) -> bool:
        """True if the issue was observed at or after `verify_from` — so a fix at
        `verify_from` did NOT resolve it (release it from quarantine to OPEN)."""
        floor = parse_version(verify_from)
        return any(pv >= floor for pv, _ in self._occurrences.get(fingerprint, []))


def two_stage_review(collection: list[dict[str, Any]]) -> dict[str, Any]:
    """EVAL-5 stage 2: break a collection of raised issues into common CORE issues.
    Groups by fingerprint, one core issue per group with its count + contributing
    versions, most-frequent first."""
    groups: dict[str, dict[str, Any]] = {}
    for iss in collection:
        fp = iss.get("fingerprint")
        if not fp:
            continue  # skip a malformed/fingerprint-less item rather than KeyError
        g = groups.setdefault(fp, {"fingerprint": fp, "category": iss.get("category"),
                                   "what": iss.get("what"), "count": 0, "versions": []})
        g["count"] += 1
        v = iss.get("version")
        if v and v not in g["versions"]:
            g["versions"].append(v)
    core = sorted(groups.values(), key=lambda g: (-g["count"], g["fingerprint"]))
    for g in core:
        g["versions"] = sorted(g["versions"], key=parse_version)
    return {"core_issues": core, "raw_count": len(collection)}
