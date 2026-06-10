"""VAO end-of-run-deferral + standing-red family (2 tools)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _looks_like_test_path, _scan_markers, _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _looks_like_test_path, _scan_markers, _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _looks_like_test_path, _scan_markers, _utc_now_iso, _write_verdict


_STANDING_RED_MARKERS: tuple[tuple[str, str], ...] = (
    ("comment-standing-red", "// standing red"),
    ("comment-standing-red-block", "/* standing red"),
    ("comment-will-go-green-when", "will go green when"),
    ("comment-will-go-green-once", "will go green once"),
    ("comment-documents-the-gap", "documents the gap"),
    ("comment-known-broken", "known broken"),
    ("comment-known-bug", "known bug"),
    ("comment-not-yet-fixed", "not yet fixed"),
    ("comment-red-regression", "// red regression"),
    ("comment-standing-failure", "standing failure"),
    ("test-fixme-fn", "test.fixme("),
    ("it-fixme-fn", "it.fixme("),
    ("test-fail-fn", "test.fail("),
    ("it-fail-fn", "it.fail("),
    ("pytest-xfail", "@pytest.mark.xfail"),
    ("pytest-xfail-raw", "pytest.xfail("),
)


_CROSS_LAYER_SR_ORIGIN_KINDS: frozenset[str] = frozenset({
    "cross-layer-backend-required",
    "cross-layer-frontend-required",
})


def _detect_standing_red_committed(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """A newly-added test file contains a standing-red marker AND is not
    covered by a confirmed_stubs[] entry → fire."""
    diff_files = verification_artifact.get("diff_files") or []
    touched = verification_artifact.get("touched_file_contents") or {}
    confirmed_stubs = verification_artifact.get("confirmed_stubs") or []
    # Confirmed-stub entries can be strings (path) or dicts ({path, reason, user_confirmed_at}).
    confirmed_paths: set[str] = set()
    for stub in confirmed_stubs:
        if isinstance(stub, str):
            confirmed_paths.add(stub)
        elif isinstance(stub, dict):
            p = stub.get("path") or stub.get("test_path")
            if isinstance(p, str):
                confirmed_paths.add(p)

    gaps: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    def scan_text(path: str, text: str) -> None:
        if not _looks_like_test_path(path):
            return
        if path in confirmed_paths:
            return
        text_lower = text.lower()
        for marker_id, pattern in _STANDING_RED_MARKERS:
            if pattern.lower() in text_lower:
                key = (path, marker_id)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                gaps.append({
                    "severity": "standing-red-committed",
                    "test_path": path,
                    "marker_id": marker_id,
                    "marker": pattern,
                    "evidence": (
                        f"test file {path!r} contains standing-red marker {pattern!r} "
                        f"(marker_id={marker_id}); not covered by a confirmed_stubs[] entry"
                    ),
                    "remediation": (
                        "v2.8.0 No standing-red discipline. Replace the failing test "
                        "with a real fix that makes the test pass, OR route the unfixed "
                        "layer via a solution requirement (origin.kind: "
                        "cross-layer-backend-required / cross-layer-frontend-required), "
                        "OR mark this test as a confirmed_stub with explicit user "
                        "confirmation. A failing test committed as documentation is "
                        "the failure mode this discipline closes."
                    ),
                })

    for df in diff_files:
        if not isinstance(df, dict):
            continue
        path = df.get("path")
        if not isinstance(path, str):
            continue
        # Scan added_lines first (the change introduced the marker).
        added = df.get("added_lines") or []
        if added:
            scan_text(path, "\n".join(a for a in added if isinstance(a, str)))
        # Also scan the file's current contents if provided.
        content = touched.get(path)
        if isinstance(content, str):
            scan_text(path, content)

    # Test files in touched_file_contents that weren't in the diff (the agent
    # may have authored a test in this change without listing it in diff_files).
    for path, content in touched.items():
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        scan_text(path, content)

    return gaps


def _detect_cross_layer_fix_not_routed(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """When the agent's cross-layer diagnosis names an unfixed layer AND a
    standing-red test was committed AND no SR of cross-layer-* origin kind
    was created → fire."""
    diagnosis = verification_artifact.get("cross_layer_diagnosis") or {}
    if not isinstance(diagnosis, dict):
        return []
    unfixed_layer = diagnosis.get("unfixed_layer")
    if not isinstance(unfixed_layer, str) or not unfixed_layer:
        return []

    # Was a standing-red test committed for this diagnosis?
    standing_red_gaps = _detect_standing_red_committed(verification_artifact)
    if not standing_red_gaps:
        return []

    # Was an SR of cross-layer-* origin kind created?
    srs = verification_artifact.get("solution_requirements_created") or []
    routed = False
    for sr in srs:
        if not isinstance(sr, dict):
            continue
        origin = sr.get("origin") or {}
        kind = origin.get("kind") if isinstance(origin, dict) else None
        if isinstance(kind, str) and kind in _CROSS_LAYER_SR_ORIGIN_KINDS:
            routed = True
            break

    if routed:
        return []

    return [{
        "severity": "cross-layer-fix-not-routed",
        "unfixed_layer": unfixed_layer,
        "evidence": (
            f"cross_layer_diagnosis names {unfixed_layer!r} as the unfixed layer; "
            f"{len(standing_red_gaps)} standing-red test(s) committed for the "
            f"diagnosed bug; no SR with origin.kind in {sorted(_CROSS_LAYER_SR_ORIGIN_KINDS)!r} "
            f"was created."
        ),
        "remediation": (
            "v2.8.0 No standing-red discipline. The diagnosis correctly identified "
            "a cross-layer bug. Route the unfixed layer via a solution requirement "
            "with origin.kind=cross-layer-backend-required (or "
            "cross-layer-frontend-required) so the orchestrator dispatches the right "
            "team in the same run. The committed standing-red test is documentation "
            "of the gap, NOT a substitute for the fix."
        ),
    }]


def verify_no_standing_red(
    verification_artifact: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.8.0 Layer-3 tool — verify the agent did NOT commit a failing test
    as documentation of a known bug.

    Checks the verification artifact against the 2 named severities:
      1. standing-red-committed — a newly-added test contains a standing-red
         marker AND is not covered by a confirmed_stubs[] entry
      2. cross-layer-fix-not-routed — cross_layer_diagnosis names an unfixed
         layer AND a standing-red test was committed AND no SR of
         cross-layer-* origin kind was created

    Args:
      verification_artifact: dict with diff_files[], touched_file_contents{},
        confirmed_stubs[], cross_layer_diagnosis{}, solution_requirements_created[].
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-no-standing-red",
          "valid": bool,
          "gaps": [{"severity", "test_path"|"unfixed_layer", "evidence", "remediation"}],
          "verdict_at": "<ISO 8601 UTC>"
        }

    Trivially passes when no standing-red markers AND no cross_layer_diagnosis
    — fully backwards-compatible with pre-v2.8.0 artifacts.

    Deterministic / bit-stable output for given inputs (sorted-keys + indent=2).
    """
    artifact = verification_artifact or {}
    gaps: list[dict[str, Any]] = []

    gaps += _detect_standing_red_committed(artifact)
    gaps += _detect_cross_layer_fix_not_routed(artifact)

    verdict = {
        "tool": "verify-no-standing-red",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# Phrases that signal an end-of-run "Deferred" catalog. Each entry is matched
# case-insensitively as a substring against the agent's final_report text.
# Keep the list tight: false positives (legitimate uses of "deferred" in
# architectural decision documentation, etc.) are mitigated by requiring
# a marker AND by allowing the artifact to declare a per-item disposition
# (SR or confirmed-stub) — see _detect_wrap_up_with_known_bugs.
_DEFERRAL_CATALOG_MARKERS: tuple[tuple[str, str], ...] = (
    ("hourglass-deferred", "⏳ Deferred"),
    ("hourglass-emoji-deferred", "⏳ deferred"),
    ("deferred-em-dash", "Deferred — "),
    ("deferred-en-dash", "Deferred – "),
    ("deferred-N-bug", "deferred 7 bug"),
    ("deferred-N-bug-variant", "deferred N bug"),
    ("cluster-by-cluster", "cluster-by-cluster"),
    ("a-arrow-b-arrow-c", "A → B → C"),
    ("a-arrow-b-arrow-c-ascii", "A -> B -> C"),
    ("each-a-real-change", "each a real change"),
    ("not-a-one-liner", "not a one-liner"),
    ("i-would-take-them", "I'd take them"),
    ("defer-future-change", "Defer to a future change"),
    ("punt-to-later", "punt to later"),
    ("pick-up-next-time", "pick up next time"),
    ("out-of-scope-this-session", "out of scope for this session"),
)


# Phrases that signal an end-of-run followup-decision question. The agent
# is asking the user to decide what to do next AFTER the run claims to be
# complete — the v0.9.20 forbidden "do you want me to proceed?" gate.
_FOLLOWUP_QUESTION_MARKERS: tuple[tuple[str, str], ...] = (
    ("want-me-to-continue", "Want me to continue"),
    ("your-call", "Your call"),
    ("ideally-fresh-context", "ideally in a fresh context"),
    ("say-the-word", "say the word"),
    ("let-me-know-if", "let me know if"),
    ("shall-i-proceed", "Shall I proceed"),
    ("do-you-want-me-to", "Do you want me to"),
    ("should-i-take", "Should I take"),
    ("is-it-ok-if-i", "Is it OK if I"),
    ("if-youd-like", "If you'd like"),
)


# An item in the final report is considered "dispositioned" when it carries
# at least one of these citations to a sanctioned channel.
_ITEM_DISPOSITION_CITATIONS: tuple[str, ...] = (
    "commit-sha:",
    "SR-",  # solution requirement id (SR-101 / SR-B23-101 / etc.)
    "confirmed_stub",
    "confirmed-stub",
    "implementing_commits",
    # v2.12.0 — v2.11.0 per-persona coverage IS a sanctioned disposition channel.
    # Without these tokens, a legitimate v2.11.0 final report (per-persona
    # findings + Playwright run citations) trips v2.10.0's wrap-up gate.
    "playwright_test_runs",
    "per_persona_findings",
    "persona_id:",
    "tested green",
    "tested-green",
    "entry_point:",
)


def _detect_deferred_work_catalog(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """The final report names items as 'deferred' / clusters them under
    A→B→C→D framing / uses any of the canonical deferral-catalog markers."""
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _DEFERRAL_CATALOG_MARKERS)
    gaps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for marker_id, pattern in hits:
        if marker_id in seen_ids:
            continue
        seen_ids.add(marker_id)
        gaps.append({
            "severity": "deferred-work-catalog",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report contains deferral-catalog marker {pattern!r} "
                f"(marker_id={marker_id})"
            ),
            "remediation": (
                "v2.10.0 No end-of-run deferral discipline. Every in-scope item "
                "must reach one of three dispositions by run-end: (a) fixed in "
                "this change, (b) routed via a solution requirement with a "
                "canonical origin.kind, OR (c) explicit confirmed-stub with "
                "user-citation. Cataloguing items as 'Deferred' with a clustered "
                "follow-up offer is the failure mode this discipline closes."
            ),
        })
    return gaps


def _detect_followup_decision_question(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """The final report ends with a 'Want me to continue?' / 'Your call' /
    'ideally in a fresh context' style follow-up question that bounces the
    work decision back to the user."""
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _FOLLOWUP_QUESTION_MARKERS)
    gaps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for marker_id, pattern in hits:
        if marker_id in seen_ids:
            continue
        seen_ids.add(marker_id)
        gaps.append({
            "severity": "followup-decision-question",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report contains followup-question marker {pattern!r} "
                f"(marker_id={marker_id})"
            ),
            "remediation": (
                "v2.10.0 No end-of-run deferral discipline. Run-end is forward "
                "motion (per v0.9.20 default-mode-of-operation), not a checkpoint "
                "where the user picks which clusters to authorize next. Either "
                "the work was done OR the work was routed via SR — never "
                "bounced back as a 'Want me to continue?' decision question."
            ),
        })
    return gaps


def _detect_wrap_up_with_known_bugs(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """The final report enumerates ≥ 3 in-scope items AND none of them has
    a sanctioned per-item disposition (commit-sha / SR / confirmed-stub)."""
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []

    # Heuristic: count bullets / numbered items in the report.
    bullet_lines = 0
    for line in final_report.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        if (
            stripped.startswith("- ")
            or stripped.startswith("* ")
            or stripped.startswith("• ")
            or (len(stripped) >= 2 and stripped[0].isdigit() and stripped[1] in ".)")
            or (len(stripped) >= 3 and stripped[:2].isdigit() and stripped[2] in ".)")
        ):
            bullet_lines += 1

    if bullet_lines < 3:
        return []

    # Are any per-item dispositions cited?
    srs = verification_artifact.get("solution_requirements_created") or []
    confirmed_stubs = verification_artifact.get("confirmed_stubs") or []
    implementing_commits = verification_artifact.get("implementing_commits") or []
    # v2.12.0 — v2.11.0 per-persona path-coverage is a sanctioned disposition
    # channel. A run that lists per-persona test outcomes IS dispositioned
    # (the playwright_test_runs[] array is the citation).
    playwright_runs = verification_artifact.get("playwright_test_runs") or []
    per_persona_findings = verification_artifact.get("per_persona_findings") or {}
    has_dispositions = bool(
        srs or confirmed_stubs or implementing_commits
        or playwright_runs or per_persona_findings
    )

    # Also accept inline citations in the report text.
    has_inline_citation = any(
        citation in final_report for citation in _ITEM_DISPOSITION_CITATIONS
    )

    if has_dispositions or has_inline_citation:
        return []

    return [{
        "severity": "wrap-up-with-known-bugs",
        "bullet_count": bullet_lines,
        "evidence": (
            f"final_report enumerates {bullet_lines} bulleted / numbered items "
            f"with no per-item disposition citation (no solution_requirements_created, "
            f"no confirmed_stubs, no implementing_commits, no inline commit-sha/SR/"
            f"confirmed-stub references in the report text)."
        ),
        "remediation": (
            "v2.10.0 No end-of-run deferral discipline. Every enumerated in-scope "
            "item must cite ONE of: (a) the commit SHA range that fixed it, "
            "(b) the SR ID with origin.kind that routed it, OR (c) the confirmed-stub "
            "entry with user-citation. An enumerated list with no per-item disposition "
            "is the wrap-up-with-known-bugs failure mode."
        ),
    }]


def verify_no_end_of_run_deferral(
    verification_artifact: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.10.0 Layer-3 tool — verify the agent did NOT end the run by
    cataloguing in-scope work as 'Deferred' and bouncing the unfixed items
    back to the user as a 'Want me to continue?' decision question.

    Checks the verification artifact against the 3 named severities:
      1. deferred-work-catalog — final report contains a canonical
         deferral-catalog marker (12-pattern allowlist)
      2. followup-decision-question — final report contains a canonical
         followup-question marker (10-pattern allowlist)
      3. wrap-up-with-known-bugs — final report enumerates ≥ 3 in-scope
         items AND no per-item disposition (commit-sha / SR / confirmed-stub)
         is cited

    Args:
      verification_artifact: dict with final_report (str — the agent's
        verbatim user-facing run-end report), solution_requirements_created[]
        (the SRs the run routed), confirmed_stubs[] (entries with
        user_confirmed_at), implementing_commits[] (commit SHA ranges).
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-no-end-of-run-deferral",
          "valid": bool,
          "gaps": [{"severity", "marker_id"|"bullet_count", "evidence", "remediation"}],
          "verdict_at": "<ISO 8601 UTC>"
        }

    Trivially passes when final_report is empty / absent — fully
    backwards-compatible with pre-v2.10.0 artifacts.

    Deterministic / bit-stable output for given inputs (sorted-keys + indent=2).
    """
    artifact = verification_artifact or {}
    gaps: list[dict[str, Any]] = []

    gaps += _detect_deferred_work_catalog(artifact)
    gaps += _detect_followup_decision_question(artifact)
    gaps += _detect_wrap_up_with_known_bugs(artifact)

    verdict = {
        "tool": "verify-no-end-of-run-deferral",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
