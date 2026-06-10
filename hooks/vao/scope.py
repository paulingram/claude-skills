"""VAO implementation-scope-cut + unilateral-override family (2 tools)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _scan_markers, _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _scan_markers, _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _scan_markers, _utc_now_iso, _write_verdict


# v2.14.0 — Phrases the orchestrator scans for in the user's prompt to set
# scope_mandate.full_build_required: true. Case-insensitive substring match.
_FULL_BUILD_MANDATE_PHRASES: tuple[str, ...] = (
    "implement everything in full",
    "implement everything",
    "implement it all",
    "implement all of it",
    "build everything",
    "build the whole thing",
    "do everything in full",
    "do everything",
    "ship it all",
    "ship the whole thing",
    "entire build",
    "complete build",
    "full build",
)


# Forbidden agent-output phrases that signal an "Honest scope statement" cut
# — the agent unilaterally cuts to a foundation subset and frames the cut
# as virtuous. Case-insensitive substring match.
_HONEST_SCOPE_STATEMENT_MARKERS: tuple[tuple[str, str], ...] = (
    ("honest-scope-statement-header", "Honest scope statement"),
    ("warning-honest-scope", "⚠️ Honest scope"),
    ("scope-statement-framing", "scope statement"),
    ("shippable-and-true-hyphen", "shippable-and-true"),
    ("shippable-and-true-spaces", "shippable and true"),
    ("i-stopped-at-the-boundary", "I stopped at the"),
    ("stopped-at-boundary-deliberately", "stopped at the boundary deliberately"),
    ("stopped-deliberately", "stopped deliberately"),
    ("rather-than-half-land", "rather than half-land"),
    ("multi-agent-build-foundation", "multi-agent build on this foundation"),
    ("land-incrementally-without-rework", "land incrementally without rework"),
    ("complete-m0-foundation", "complete M0 foundation"),
    ("foundation-deployed-and-tested", "foundation, deployed and tested"),
)


# Phrases that frame a partial build as a complete "foundation" when the
# mandate was full-build. These are scope-narrowing tells.
_FOUNDATION_ONLY_FRAMING_MARKERS: tuple[tuple[str, str], ...] = (
    ("m0-foundation", "M0 foundation"),
    ("foundation-deployed", "foundation deployed"),
    ("foundation-laid", "foundation laid"),
    ("scaffolding-shipped", "scaffolding shipped"),
    ("skeleton-shipped", "skeleton shipped"),
    ("the-foundation-so-they", "the foundation so they"),
    ("incrementally-land", "incrementally land"),
    ("incremental-landing", "incremental landing"),
)


# Patterns that suggest the agent enumerated deferred milestones. v2.14.0
# uses simple substring matching for these; v2.14.x may upgrade to regex.
_MILESTONE_DEFERRAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("milestones-m1-m7", "milestones M1"),
    ("m0-boundary", "M0 boundary"),
    ("plans-08", "plans/08"),
    ("m1-build", "M1 is"),
    ("m1-through-m7", "M1 through M7"),
    ("m1-m7-dash", "M1–M7"),
    ("m1-m7-hyphen", "M1-M7"),
)


def _detect_honest_scope_statement_emitted(
    verification_artifact: dict[str, Any],
    scope_mandate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Final report contains an Honest scope statement / shippable-and-true /
    I-stopped-deliberately marker AND scope_mandate.full_build_required is true."""
    if not scope_mandate.get("full_build_required"):
        return []
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _HONEST_SCOPE_STATEMENT_MARKERS)
    gaps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for marker_id, pattern in hits:
        if marker_id in seen:
            continue
        seen.add(marker_id)
        gaps.append({
            "severity": "honest-scope-statement-emitted",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report contains Honest-scope-statement marker {pattern!r} "
                f"(marker_id={marker_id}) AND scope_mandate.full_build_required "
                f"is true (user's prompt named a full-build mandate)."
            ),
            "remediation": (
                "v2.14.0 No implementation-time scope cut discipline. The user's "
                "prompt named a full-build mandate; the agent unilaterally cut "
                "to a foundation subset and announced the cut as virtuous. The "
                "agent's run must (a) implement the full mandate, (b) route SRs "
                "with origin.kind=incomplete-implementation-scope-required for "
                "the unimplemented portions, OR (c) carry confirmed-stub entries "
                "with user_confirmed_at for them. Forbidden phrases: 'Honest "
                "scope statement', 'shippable-and-true', 'I stopped at the "
                "boundary deliberately', 'rather than half-land', 'multi-agent "
                "build on this foundation', 'land incrementally without rework'."
            ),
        })
    return gaps


def _detect_foundation_only_framing(
    verification_artifact: dict[str, Any],
    scope_mandate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Final report contains foundation-only framing AND full-build mandate
    was set AND no SR/confirmed-stub covers the unimplemented portion."""
    if not scope_mandate.get("full_build_required"):
        return []
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _FOUNDATION_ONLY_FRAMING_MARKERS)
    if not hits:
        return []
    # Check whether SRs OR confirmed-stubs cover the unimplemented portion.
    srs = verification_artifact.get("solution_requirements_created") or []
    confirmed_stubs = verification_artifact.get("confirmed_stubs") or []
    has_scope_cut_disposition = False
    for sr in srs:
        if isinstance(sr, dict):
            origin = sr.get("origin") or {}
            kind = origin.get("kind") if isinstance(origin, dict) else None
            if isinstance(kind, str) and kind == "incomplete-implementation-scope-required":
                has_scope_cut_disposition = True
                break
    for stub in confirmed_stubs:
        if isinstance(stub, dict):
            scope_cut = stub.get("scope_cut_kind") or stub.get("incomplete_scope")
            if scope_cut:
                has_scope_cut_disposition = True
                break
    if has_scope_cut_disposition:
        return []

    seen: set[str] = set()
    gaps: list[dict[str, Any]] = []
    for marker_id, pattern in hits:
        if marker_id in seen:
            continue
        seen.add(marker_id)
        gaps.append({
            "severity": "foundation-only-framing-with-full-build-mandate",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report frames partial work as a complete 'foundation' "
                f"(marker {pattern!r}, marker_id={marker_id}) AND "
                f"scope_mandate.full_build_required is true AND no SR with "
                f"origin.kind=incomplete-implementation-scope-required was "
                f"routed AND no confirmed-stub entry covers the unimplemented "
                f"portion."
            ),
            "remediation": (
                "v2.14.0 No implementation-time scope cut discipline. The "
                "foundation framing is only valid when the user explicitly "
                "asked for a foundation. Under a full-build mandate the run "
                "must route SRs for the unimplemented milestones OR carry "
                "confirmed-stubs with user_confirmed_at."
            ),
        })
    return gaps


def _detect_unilateral_implementation_scope_cut(
    verification_artifact: dict[str, Any],
    scope_mandate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Final report enumerates deferred milestones (M1–M7 / plans/08 / etc.)
    AND no SR routes them AND scope_mandate.full_build_required is true."""
    if not scope_mandate.get("full_build_required"):
        return []
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _MILESTONE_DEFERRAL_PATTERNS)
    if not hits:
        return []
    # Check whether SRs with the canonical origin.kind exist.
    srs = verification_artifact.get("solution_requirements_created") or []
    has_scope_cut_sr = False
    for sr in srs:
        if isinstance(sr, dict):
            origin = sr.get("origin") or {}
            kind = origin.get("kind") if isinstance(origin, dict) else None
            if isinstance(kind, str) and kind == "incomplete-implementation-scope-required":
                has_scope_cut_sr = True
                break
    if has_scope_cut_sr:
        return []

    return [{
        "severity": "unilateral-implementation-scope-cut",
        "deferred_milestone_markers": sorted({m for m, _ in hits}),
        "evidence": (
            f"final_report enumerates deferred milestones (markers: "
            f"{sorted({m for m, _ in hits})!r}) AND scope_mandate.full_build_required "
            f"is true AND no SR with "
            f"origin.kind=incomplete-implementation-scope-required was routed."
        ),
        "remediation": (
            "v2.14.0 No implementation-time scope cut discipline. The user "
            "asked for the full build. The agent enumerated deferred milestones "
            "but never routed an SR for them. Either implement the milestones "
            "in this change OR route SRs with "
            "origin.kind=incomplete-implementation-scope-required so the "
            "orchestrator dispatches the right team in a follow-up run OR "
            "carry confirmed-stub entries with user_confirmed_at."
        ),
    }]


def verify_no_implementation_scope_cut(
    verification_artifact: dict[str, Any] | None = None,
    scope_mandate: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.14.0 Layer-3 tool — verify the agent did NOT unilaterally cut to a
    foundation subset and announce the cut as virtuous when the user's
    prompt named a full-build mandate.

    Three named severities:
      1. honest-scope-statement-emitted — final report contains an "Honest
         scope statement" / "shippable-and-true" / "I stopped deliberately"
         marker AND scope_mandate.full_build_required is true.
      2. foundation-only-framing-with-full-build-mandate — final report
         frames partial work as a complete "foundation" AND no SR/
         confirmed-stub covers the unimplemented portion.
      3. unilateral-implementation-scope-cut — final report enumerates
         deferred milestones AND no SR routes them.

    Trivially passes when scope_mandate is empty OR
    scope_mandate.full_build_required is false (backwards-compat with
    runs against partial mandates).
    """
    artifact = verification_artifact or {}
    mandate = scope_mandate or {}
    gaps: list[dict[str, Any]] = []
    gaps += _detect_honest_scope_statement_emitted(artifact, mandate)
    gaps += _detect_foundation_only_framing(artifact, mandate)
    gaps += _detect_unilateral_implementation_scope_cut(artifact, mandate)

    verdict = {
        "tool": "verify-no-implementation-scope-cut",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


def verify_no_unilateral_override(
    text: str = "",
    text_sources: dict[str, str] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v3.0.0 META Layer-3 tool — unified unilateral-override + virtue-framed-
    confession detector.

    Consolidates the marker-text detection halves of v2.10.0 / v2.14.0 /
    v2.20.0 / v2.21.0 / v2.22.0 disciplines into a single detector. Fires
    on the pattern: virtue-framed opener + element-of-bypass admission in
    the same text.

    Inputs:
      - `text`: a single text artifact (e.g., final_report). Convenience
        shorthand; equivalent to text_sources={"text": text}.
      - `text_sources`: dict mapping source-name → text. Use this when you
        want per-source breakdown (e.g., {"final_report": "...",
        "verification_text": "...", "verification_notes": "..."}).

    Trivially passes when all sources are empty / non-string — fully
    backwards-compatible.

    Single severity:
      - `unilateral-override-with-virtue-framed-confession` — fires per
        source. Per-gap fields include source name + matched openers +
        matched admissions + high_confidence boolean.
    """
    # Dual-form import (mirrors lines 61-68) so
    # `python hooks/vao_tools.py verify-no-unilateral-override` works under the
    # bare-module sys.path the hook-runner uses.
    try:  # package shape: repo root on sys.path
        from hooks.override_markers import detect_virtue_framed_override
    except ImportError:  # bare-module shape: hooks/ dir on sys.path
        from override_markers import detect_virtue_framed_override

    sources: dict[str, str] = {}
    if text:
        sources["text"] = text
    if text_sources:
        for k, v in text_sources.items():
            if isinstance(v, str) and v.strip():
                sources[k] = v

    gaps: list[dict[str, Any]] = []
    for source_name, source_text in sources.items():
        result = detect_virtue_framed_override(source_text)
        if not result["fires"]:
            continue
        gaps.append({
            "severity": "unilateral-override-with-virtue-framed-confession",
            "source": source_name,
            "openers_matched": result["openers_matched"][:8],
            "admissions_matched": result["admissions_matched"][:8],
            "high_confidence": result["high_confidence"],
            "evidence": (
                f"source {source_name!r} contains both a virtue-framed "
                f"opener (e.g., {result['openers_matched'][0]!r}) AND "
                f"{len(result['admissions_matched'])} element-of-bypass "
                f"admission(s) (e.g., {result['admissions_matched'][0]!r}). "
                f"The agent unilaterally overrode the user's explicit "
                f"choice and is now post-hoc confessing with virtuous "
                f"framing. {('HIGH-CONFIDENCE — ≥ 2 distinct admissions.' if result['high_confidence'] else 'Low-confidence — 1 admission.')}"
            ),
            "remediation": (
                "v3.0.0 unilateral-override discipline (META). The right "
                "behavior is to NOT unilaterally override in the first "
                "place. If the user's request is genuinely impossible or "
                "ambiguous, halt-and-disclose BEFORE acting: 'I am not "
                "going to [X] because [verbatim user authorization or "
                "structural blocker]. Want [X] anyway? Reply ...'. After "
                "the fact, virtuous-confession framing is forbidden — "
                "either the work is correct (commit it) or it is not "
                "(revert and re-run). Re-invoke the pipeline against the "
                "same user prompt; do not commit the confession-laden "
                "artifact."
            ),
        })

    verdict = {
        "tool": "verify-no-unilateral-override",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "sources_inspected": list(sources.keys()),
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
