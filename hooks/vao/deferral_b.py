"""VAO report-claims citation family — v3.47.0 (postmortem rules R2/R4/R5/R9).

The five claims-citation severities of ``verify-no-end-of-run-deferral``. That
tool is ONE tool composed of two modules: ``deferral.py`` owns the v2.10.0
severities, assembles the verdict, and is the public entry point; this module
owns the v3.47.0 claim families it also runs. The split exists to keep each
family module under the package's 900-line ceiling (see ``hooks/vao/__init__``)
— it is not a second tool, and there is no second CLI subcommand.

The shared report-scanning vocabulary (``_is_enumerated_line`` and
``_ITEM_DISPOSITION_CITATIONS``) lives in ``core.py`` so that the composition
runs one way only: deferral.py imports this module, this module imports core.

Stdlib-only; no import-time side effects; every function is pure (a gap list
in, a gap list out) — the verdict write stays in ``deferral.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import (
        _ITEM_DISPOSITION_CITATIONS,
        _boundary_pattern,
        _first_token_present,
        _is_enumerated_line,
    )
    from hooks.vao.mention_context import _is_mention_context
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import (
            _ITEM_DISPOSITION_CITATIONS,
            _boundary_pattern,
            _first_token_present,
            _is_enumerated_line,
        )
        from vao.mention_context import _is_mention_context
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import (
            _ITEM_DISPOSITION_CITATIONS,
            _boundary_pattern,
            _first_token_present,
            _is_enumerated_line,
        )
        from mention_context import _is_mention_context


# ---------------------------------------------------------------------------
# v3.47.0 — report-claims citation gate (postmortem rules R2 / R4 / R5 / R9)
# ---------------------------------------------------------------------------
# Four sibling marker families over the same scanning machinery the three
# v2.10.0 severities use, plus the declared-gates cross-check. Each family
# pairs a CLAIM vocabulary with the citation class that claim kind requires:
# a completion status needs a per-item disposition, a deploy-verified claim
# needs a citation naming a loaded page (a status code is not a screen), an
# absence claim needs an executed enumeration (grep proves presence, never
# absence), and a stalled-agent characterization needs an idle event or a
# handoff record (silence is not a finding).
#
# HONEST BOUNDARY: this scans PERSISTED report artifacts — `final_report` and
# the optional `progress_reports[]`. The orchestrator's mid-run conversational
# text is not a tool surface; it is governed by instruction (relay claims as
# claims, verdicts as facts), not by this scanner.


# Completion / delivery statuses attached to an enumerated item.
_COMPLETION_CLAIM_MARKERS: tuple[tuple[str, str], ...] = (
    ("status-completed", "completed"),
    ("status-complete", "complete"),
    ("status-done", "done"),
    ("status-delivered", "delivered"),
    ("status-verified", "verified"),
    ("status-shipped", "shipped"),
    ("status-implemented", "implemented"),
    ("status-all-green", "all green"),
    ("status-all-green-hyphen", "all-green"),
    ("status-tests-pass", "tests pass"),
    ("status-now-works", "now works"),
    ("status-resolved", "resolved"),
)


# "Deployed AND verified" — a deploy paired with a verification claim.
_DEPLOY_VERIFIED_MARKERS: tuple[tuple[str, str], ...] = (
    ("deployed-and-verified", "deployed and verified"),
    ("deployed-amp-verified", "deployed & verified"),
    ("deployed-plus-verified", "deployed + verified"),
    ("deployed-comma-verified", "deployed, verified"),
    ("redeployed-and-verified", "redeployed and verified"),
    ("deploy-verified", "deploy verified"),
    ("deployed-and-confirmed", "deployed and confirmed"),
    ("deployed-and-checked", "deployed and checked"),
    ("deployed-and-working", "deployed and working"),
    ("live-and-verified", "live and verified"),
    ("verified-in-dev", "verified in dev"),
    ("verified-on-the-deployed", "verified on the deployed"),
    ("verified-against-the-deployed", "verified against the deployed"),
    ("deploy-verified-end-to-end", "deployed and verified end-to-end"),
)


# Absence assertions — the class of claim a search command CANNOT establish.
_ABSENCE_CLAIM_MARKERS: tuple[tuple[str, str], ...] = (
    ("no-test-exists", "no test exists"),
    ("no-tests-exist", "no tests exist"),
    ("there-is-no-test", "there is no test"),
    ("never-implemented", "never implemented"),
    ("was-never-built", "was never built"),
    ("was-never-wired", "was never wired"),
    ("is-missing", "is missing"),
    ("are-missing", "are missing"),
    ("not-covered", "not covered"),
    ("no-coverage", "no coverage"),
    ("does-not-exist", "does not exist"),
    ("doesnt-exist", "doesn't exist"),
    ("no-implementation", "no implementation"),
    ("nowhere-in-the-codebase", "nowhere in the codebase"),
)


# Characterizations of another agent's state.
_STALLED_AGENT_MARKERS: tuple[tuple[str, str], ...] = (
    ("stalled", "stalled"),
    ("went-idle", "went idle"),
    ("gone-idle", "gone idle"),
    ("sitting-idle", "sitting idle"),
    ("left-the-build-broken", "left the build broken"),
    ("left-the-tree-broken", "left the tree broken"),
    ("never-reported", "never reported"),
    ("has-not-reported", "has not reported"),
    ("hasnt-reported", "hasn't reported"),
    ("went-dark", "went dark"),
    ("gave-up", "gave up"),
    ("abandoned-the", "abandoned the"),
    ("stopped-working-on", "stopped working on"),
    ("no-longer-responding", "no longer responding"),
)


# Release-gate language — a condition the report says gates ship / deploy /
# merge / completion. Naming one is declaring one (v3.47.0 declared-gates).
_GATE_LANGUAGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("gates-the-release", "gates the release"),
    ("release-gate", "release gate"),
    ("the-run-that-gates", "the run that gates"),
    ("gates-the-ship", "gates the ship"),
    ("gates-the-deploy", "gates the deploy"),
    ("gates-the-merge", "gates the merge"),
    ("gates-the-commit", "gates the commit"),
    ("gates-completion", "gates completion"),
)


# A deploy claim is cited only by evidence from the layer the USER experiences.
_POST_DEPLOY_VERIFICATION_CITATIONS: tuple[str, ...] = (
    "screenshot",
    ".png",
    ".jpg",
    "page loaded",
    "loaded the page",
    "page load",
    "rendered",
    "renders",
    "playwright",
    ".spec.ts",
    "tobevisible",
    "expect(page",
    "getbyrole",
    "getbytext",
    "semantic assertion",
    "asserted the text",
    "dom snapshot",
    "visual verification",
    "trace.zip",
    ".architect-team/vao-verdicts/",
    "verdict_path:",
)


# Status codes are NOT screens (R2). Recorded on the finding as the basis the
# claim actually rested on — never counted as a citation.
_STATUS_CODE_ONLY_CITATIONS: tuple[str, ...] = (
    "200 ok",
    "http 200",
    "status code",
    "status 200",
    "returned 200",
    "responded 200",
    "curl -i",
    "health check",
    "healthcheck",
    "/health",
    "2xx",
    "http status",
)


# An absence claim is cited only by an EXECUTED enumeration (R4).
_ENUMERATION_EVIDENCE_CITATIONS: tuple[str, ...] = (
    "collected",
    "collect-only",
    "--list",
    "test inventory",
    "inventory of",
    "enumerated",
    "coverage report",
    "suite output",
    "ran the suite",
    "asked the agent",
    ".architect-team/vao-verdicts/",
    "verdict_path:",
    "reviews/",
    "evidence:",
)


# A grep/search command — the basis that CANNOT establish absence.
_GREP_BASIS_TOKENS: tuple[str, ...] = (
    "grep",
    # Inflected forms: word-boundary matching means "grep" does not match
    # "grepped", and a finding that mislabels its own basis is the small
    # dishonesty this whole change is about (surfaced on hei-adversary-g3 R3,
    # which fired correctly but reported grep_only=False).
    "grepped",
    "grepping",
    "greps",
    "rg ",
    "ripgrep",
    "searched for",
    "search for",
    "codebase search",
    "found no hits",
    "returned nothing",
    "no matches",
)


# An agent-state claim is cited only by a knowable state record (R5).
_AGENT_STATE_CITATIONS: tuple[str, ...] = (
    "teammateidle",
    "subagentstop",
    "idle_event",
    "idle-event",
    ".architect-team/teammates/",
    "teammates/",
    "handoffs/",
    "handoff:",
    "handoff record",
    "last_message_at",
    "transcript:",
    "manifest:",
)


# The stalled family characterizes an AGENT's state, so the window must name
# one. Without this, "the deploy stalled at 40%" reads as an agent claim.
# Boundary: an agent referred to ONLY by bare name ("hei-claims stalled") is
# missed — a deliberate false-negative trade for precision.
_AGENT_CONTEXT_TOKENS: tuple[str, ...] = (
    "agent",
    "agents",
    "teammate",
    "teammates",
    "subagent",
    "reviewer",
    "implementer",
    "orchestrator",
    "worker",
    "researcher",
    "verifier",
    "replicator",
)
# hei-adversary-g3 B-5: 'backend', 'frontend', 'integration', 'dev', 'devs' and
# 'lead' were dropped. They are ordinary infrastructure nouns, and with them in
# the set 'The integration suite stalled on a locked sqlite file' read as a
# claim about an agent. An agent referred to ONLY by a role word that is also
# an infra noun is missed; that is the deliberate trade.


# Modal auxiliaries: "will be verified once the smoke run lands" is a PLAN.
# A next-actions section is a normal part of a run report (hei-adversary-g3 B-6).
_MODAL_WORDS: frozenset[str] = frozenset({
    "will", "must", "should", "would", "shall", "may", "might",
    "plan", "plans", "planned", "pending", "going",
})


# Words that flip a claim marker into its opposite ("not fixed yet" is not a
# completion claim). Checked against the 3 words preceding the marker.
_NEGATION_WORDS: frozenset[str] = frozenset({
    "not", "never", "no", "isn't", "wasn't", "aren't", "cannot", "can't",
    "without", "nothing", "none", "unverified", "incomplete",
})


# Gate-condition matching drops the gate vocabulary itself (every gate
# sentence shares it) and compares only the CONDITION words.
_GATE_STOPWORDS: frozenset[str] = frozenset({
    "gate", "gates", "gated", "gating", "release", "releases", "ship", "ships",
    "shipped", "deploy", "deploys", "deployed", "merge", "merges", "merged",
    "commit", "commits", "completion", "complete", "before", "after", "must",
    "will", "shall", "only", "when", "then", "which", "that", "this", "with",
    "from", "there", "their", "been", "have", "has", "does", "done", "also",
    "into", "over", "under", "every", "each", "runs", "run", "the", "and",
    "any", "all", "its", "our", "carries", "carry",
})


_GATE_CONDITION_TOKEN_OVERLAP_MIN = 2


_CLAIM_EXCERPT_MAX_CHARS = 220


# Per-family, per-report finding cap (hei-adversary-g3 B-11).
_MAX_GAPS_PER_FAMILY = 50


def _report_sources(verification_artifact: dict[str, Any]) -> list[tuple[str, str]]:
    """The PERSISTED report artifacts this gate binds: ``final_report`` plus
    the v3.47.0 OPTIONAL ``progress_reports[]`` (strings, or dicts carrying the
    text under ``text`` / ``report`` / ``body`` / ``content``)."""
    sources: list[tuple[str, str]] = []
    final_report = verification_artifact.get("final_report")
    if isinstance(final_report, str) and final_report:
        sources.append(("final_report", final_report))
    progress = verification_artifact.get("progress_reports")
    if isinstance(progress, str):
        progress = [progress]  # hei-adversary-g3 B-10: never silently dropped
    if isinstance(progress, list):
        for i, entry in enumerate(progress):
            text: str | None = None
            if isinstance(entry, str):
                text = entry
            elif isinstance(entry, dict):
                for key in ("text", "report", "body", "content"):
                    value = entry.get(key)
                    if isinstance(value, str) and value:
                        text = value
                        break
            if text:
                sources.append((f"progress_reports[{i}]", text))
    return sources


# Characters a claimant can wrap a line in to demote it out of enumerated
# status. `*` and `_` are NOT here: `* item` is itself a bullet glyph.
_WRAPPER_CHARS = "`\"'“”‘’"


def _unwrap(raw: str) -> str:
    """The line with surrounding quote/backtick wrappers removed.

    hei-adversary-g3 B-13: ``- Column config: completed`` is enumerated;
    ```- Column config: completed``` was not, and that alone reopened the full
    evasion — the completion family is enumerated-only, so a backtick-wrapped
    status bullet left its scope entirely, and the demoted line then joined the
    preceding PROSE window where one cue word in a heading carried the block.
    The enumeration test now runs on the unwrapped line. ``_is_enumerated_line``
    itself is untouched: the v2.10.0 wrap-up detector shares it and must stay
    byte-identical.
    """
    return raw.strip().strip(_WRAPPER_CHARS).strip()


def _claim_windows(text: str) -> list[dict[str, Any]]:
    """Split a report into CITATION WINDOWS — the unit inside which a claim and
    its citation must sit together.

    An ENUMERATED window is a bullet / numbered line plus its contiguous
    continuation lines (so a citation on the wrapped second line still counts);
    a PROSE window is a contiguous block of non-enumerated lines. A blank line
    closes the current window. This is the deferral tool's own bullet
    heuristic (:func:`_is_enumerated_line`) extended by one dimension.
    """
    windows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line_no, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            current = None
            continue
        if _is_enumerated_line(_unwrap(raw)):
            current = {"line": line_no, "enumerated": True, "lines": [stripped]}
            windows.append(current)
        elif current is not None:
            current["lines"].append(stripped)
        else:
            current = {"line": line_no, "enumerated": False, "lines": [stripped]}
            windows.append(current)
    for window in windows:
        window["text"] = "\n".join(window["lines"])
        window["lower"] = window["text"].lower()
    return windows


_CLAUSE_BOUNDARY_RE = re.compile(r"[;:.,—]")


def _is_negated(text_lower: str, index: int) -> bool:
    """True when the marker is negated, or stated as a PLAN rather than a claim.

    Both reads are CLAUSE-scoped, bounded by the nearest ``; : . ,`` or em dash.
    Negation binds tightly (the 3 words before the marker) but must not reach
    across the boundary — hei-adversary-g3 B-15 surfaced "with no citation.
    Shipped this run." reading the previous sentence's *no* as negating
    `shipped`. Modality reads the whole clause, because "must be deployed and
    verified" puts *must* four words back, while "the migration must run first;
    now completed" still fires (B-6).
    """
    clause_start = 0
    for boundary in _CLAUSE_BOUNDARY_RE.finditer(text_lower[:index]):
        clause_start = boundary.end()
    clause = text_lower[clause_start:index]
    clause_words = [w for w in re.split(r"[^a-z']+", clause) if w]
    if any(w in _NEGATION_WORDS for w in clause_words[-3:]):
        return True
    return any(w in _MODAL_WORDS for w in clause_words)


def _first_claim_marker(
    text_lower: str,
    markers: tuple[tuple[str, str], ...],
    negation_guarded: bool = True,
    is_mention=None,
) -> tuple[str, str, int] | None:
    """The first marker OCCURRENCE in ``text_lower`` that is a genuine claim —
    not matched inside a longer word, not negated by the words in front of it,
    and not a mention.

    Every occurrence is judged on its own. hei-adversary-g3 B-15: returning the
    first non-negated occurrence and then testing mention per WINDOW let a
    quoted mention shadow an unquoted claim beside it — "…whose status is
    'completed' with no citation. Shipped this run." went clean, because the
    quoted `completed` was (correctly) a mention and the unquoted `shipped` was
    never reached. A mention excuses itself, never its neighbours.
    """
    for marker_id, pattern in markers:
        for match in _boundary_pattern(pattern).finditer(text_lower):
            if negation_guarded and _is_negated(text_lower, match.start()):
                continue
            if is_mention is not None and is_mention(pattern, match.start(), match.end()):
                continue
            return marker_id, pattern, match.start()
    return None


def _excerpt(window: dict[str, Any]) -> str:
    text = " ".join(window["text"].split())
    if len(text) > _CLAIM_EXCERPT_MAX_CHARS:
        return text[:_CLAIM_EXCERPT_MAX_CHARS] + "…"
    return text


# Two occurrences of the same family are DIFFERENT claims when a claim
# separator lies between them — a sentence end or a line break. The digit
# lookbehind keeps `v3.47.0. commit-sha:abc` from reading the version's own
# `0. ` as a separator (hei-adversary-g3 B-17/W4).
_CLAIM_SEPARATOR_RE = re.compile(r"(?<!\d)[.!?](?=\s)|\n")


def _citation_scope(
    text_lower: str, index: int, markers: tuple[tuple[str, str], ...]
) -> str:
    """The span in which a citation counts for the claim at ``index``.

    Bounded by the claim's NEIGHBOURS, not by punctuation: it runs back to the
    previous same-family claim (or the start of the window when this is the
    first) and forward to the next same-family claim (or the end).

    That phrasing is the whole point. hei-adversary-g3 B-16 showed a
    window-scoped citation test silently excusing a sibling — the sharpest
    instance being a grep-only absence claim carried by its neighbour's real
    ``--collect-only``, the postmortem's own R4 shape. My first fix was
    forward-only from the claim, which stopped the borrowing but created B-17:
    ``In commit-sha:abc I completed the column config`` fired despite citing
    itself, and a claim cited on the next line fired or passed depending on
    whether its line ended in a full stop. A gate that turns on punctuation
    costs exactly the credibility it exists to create.

    Neighbour-bounding gives both properties at once: a citation can never be
    borrowed ACROSS a claim in either direction, and within a claim's own span
    it counts wherever it sits. Two markers of one claim ("delivered and
    verified") are not neighbours — they are separated by no sentence end or
    line break, so they do not truncate each other's scope.
    """
    positions = sorted({
        match.start()
        for _marker_id, pattern in markers
        for match in _boundary_pattern(pattern).finditer(text_lower)
    })

    def separated(left: int, right: int) -> bool:
        return _CLAIM_SEPARATOR_RE.search(text_lower, left, right) is not None

    has_earlier = any(p < index and separated(p, index) for p in positions)
    later = [p for p in positions if p > index and separated(index, p)]
    return text_lower[index if has_earlier else 0:later[0] if later else len(text_lower)]


def _claim_hits(
    verification_artifact: dict[str, Any],
    markers: tuple[tuple[str, str], ...],
    *,
    severity: str | None = None,
    enumerated_only: bool = False,
    negation_guarded: bool = True,
    citation_tokens: tuple[str, ...] | None = None,
):
    """Yield ``(source, window, marker_id, pattern)`` — at most one hit per
    window per family, so a report never emits N findings for one sentence.

    Stops after :data:`_MAX_GAPS_PER_FAMILY` hits and yields one final
    truncation marker, so a runaway report cannot write a verdict orders of
    magnitude larger than itself (hei-adversary-g3 B-11: a 5 MB report produced
    a 96 MB verdict). The v2.10.0 severities bound themselves with
    ``seen_ids``; this is the same idea keyed by count."""
    emitted = 0
    for source, text in _report_sources(verification_artifact):
        for window in _claim_windows(text):
            if enumerated_only and not window["enumerated"]:
                continue
            def _excused(pat: str, start: int, end: int) -> bool:
                if _is_mention_context(window, pat, severity, (start, end)):
                    return True  # quoted, not asserted
                if citation_tokens is None:
                    return False
                # B-16: the citation must sit in the CLAIM's own clause.
                return _first_token_present(
                    _citation_scope(window["lower"], start, markers), citation_tokens
                ) is not None

            hit = _first_claim_marker(
                window["lower"], markers, negation_guarded, is_mention=_excused,
            )
            if hit is None:
                continue  # every occurrence was negated, a plan, mention, or cited
            located = dict(window, claim_at=hit[2])
            if emitted >= _MAX_GAPS_PER_FAMILY:
                yield source, dict(located, truncated=True), hit[0], hit[1]
                return
            emitted += 1
            yield source, located, hit[0], hit[1]


def _claim_gap(
    severity: str,
    source: str,
    window: dict[str, Any],
    marker_id: str,
    marker: str,
    evidence: str,
    remediation: str,
    **extra: Any,
) -> dict[str, Any]:
    gap = {
        "severity": severity,
        "source": source,
        "line": window["line"],
        "marker_id": marker_id,
        "marker": marker,
        "excerpt": _excerpt(window),
        "evidence": evidence,
        "remediation": remediation,
    }
    if window.get("truncated"):
        gap["truncated"] = True
        gap["evidence"] = (
            f"{evidence}. FURTHER FINDINGS SUPPRESSED — this family hit its "
            f"per-report cap of {_MAX_GAPS_PER_FAMILY}; fix these and re-run to see the rest"
        )
    gap.update(extra)
    return gap


def _detect_uncited_completion_claim(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """An ENUMERATED item asserts completion / delivery / verification and the
    item cites nothing — a task-board status relayed as a fact (R2)."""
    gaps: list[dict[str, Any]] = []
    for source, window, marker_id, marker in _claim_hits(
        verification_artifact, _COMPLETION_CLAIM_MARKERS,
        severity="uncited-completion-claim", enumerated_only=True,
        citation_tokens=_ITEM_DISPOSITION_CITATIONS,
    ):
        gaps.append(_claim_gap(
            "uncited-completion-claim", source, window, marker_id, marker,
            evidence=(
                f"{source} line {window['line']} claims completion via {marker!r} "
                f"on an enumerated item with no citation from "
                f"_ITEM_DISPOSITION_CITATIONS in the item's citation window"
            ),
            remediation=(
                "v3.47.0 Report-claims citation gate. A completion status is a "
                "CLAIM until it cites the artifact that establishes it: the "
                "commit SHA that fixed it, the SR id that routed it, the "
                "confirmed-stub entry with user citation, the Layer-3 verdict "
                "path, or the review-evidence file. Relaying a task-board "
                "`completed` to the user is the failure this gate closes — "
                "cite per item, or report the item as unverified."
            ),
        ))
    return gaps


def _detect_uncited_deploy_claim(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """A deploy is called verified with no citation naming a loaded page, a
    screenshot, or a semantic assertion — status codes are not screens (R2)."""
    gaps: list[dict[str, Any]] = []
    for source, window, marker_id, marker in _claim_hits(
        verification_artifact, _DEPLOY_VERIFIED_MARKERS, severity="uncited-deploy-claim",
        citation_tokens=_POST_DEPLOY_VERIFICATION_CITATIONS,
    ):
        status_token = _first_token_present(
            _citation_scope(window["lower"], window["claim_at"], _DEPLOY_VERIFIED_MARKERS),
            _STATUS_CODE_ONLY_CITATIONS,
        )
        if status_token:
            basis = (
                f"the nearest citation is a status-code signal ({status_token!r}), "
                f"which reports that a server answered — not that the user's "
                f"screen rendered"
            )
        else:
            basis = "no post-deploy verification citation appears in the window at all"
        gaps.append(_claim_gap(
            "uncited-deploy-claim", source, window, marker_id, marker,
            evidence=(
                f"{source} line {window['line']} claims a verified deploy via "
                f"{marker!r}; {basis}"
            ),
            remediation=(
                "v3.47.0 Report-claims citation gate. A deploy is verified at "
                "the layer the user experiences: cite the loaded page, the "
                "screenshot, or the semantic assertion that ran against the "
                "deployed URL (a Playwright flow, a rendered-parity verdict). "
                "An HTTP 200 and a green health check prove the process is up, "
                "never that the feature works."
            ),
            status_code_only=bool(status_token),
        ))
    return gaps


def _detect_absence_claim_uncited(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """An absence is asserted with no executed enumeration behind it — grep
    proves presence, never absence (R4)."""
    gaps: list[dict[str, Any]] = []
    for source, window, marker_id, marker in _claim_hits(
        verification_artifact, _ABSENCE_CLAIM_MARKERS,
        severity="absence-claim-uncited", negation_guarded=False,
        citation_tokens=_ENUMERATION_EVIDENCE_CITATIONS + _ITEM_DISPOSITION_CITATIONS,
    ):
        grep_token = _first_token_present(
            _citation_scope(window["lower"], window["claim_at"], _ABSENCE_CLAIM_MARKERS),
            _GREP_BASIS_TOKENS,
        )
        if grep_token:
            basis = (
                f"its only cited basis is a search command ({grep_token!r}) — a "
                f"search that finds nothing proves the pattern was not matched, "
                f"not that the thing does not exist"
            )
        else:
            basis = "no enumeration evidence is cited in the window at all"
        gaps.append(_claim_gap(
            "absence-claim-uncited", source, window, marker_id, marker,
            evidence=(
                f"{source} line {window['line']} asserts absence via {marker!r}; "
                f"{basis}"
            ),
            remediation=(
                "v3.47.0 Report-claims citation gate. An absence claim requires "
                "an EXECUTED enumeration: the runner's collected-test list "
                "(pytest --collect-only, playwright test --list), a coverage "
                "report, an inventory cross-check, or the owning agent's own "
                "answer. Run it, ask the agent — do not infer absence from a "
                "grep that matched nothing."
            ),
            grep_only=bool(grep_token),
        ))
    return gaps


def _detect_stalled_agent_claim_uncited(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Another agent is characterized as stalled / idle / having left the build
    broken with no idle-event or handoff citation — silence is not a
    finding (R5)."""
    gaps: list[dict[str, Any]] = []
    for source, window, marker_id, marker in _claim_hits(
        verification_artifact, _STALLED_AGENT_MARKERS, severity="stalled-agent-claim-uncited",
        citation_tokens=_AGENT_STATE_CITATIONS,
    ):
        if not _first_token_present(window["lower"], _AGENT_CONTEXT_TOKENS):
            continue  # "the deploy stalled" is not a claim about an agent
        gaps.append(_claim_gap(
            "stalled-agent-claim-uncited", source, window, marker_id, marker,
            evidence=(
                f"{source} line {window['line']} characterizes an agent's state "
                f"via {marker!r} with no idle-event or handoff citation "
                f"(_AGENT_STATE_CITATIONS) in the window"
            ),
            remediation=(
                "v3.47.0 Report-claims citation gate. An agent that has not "
                "reported is IN-FLIGHT, not stalled. Three states are knowable "
                "and each has a record: idle (a TeammateIdle / SubagentStop "
                "event), handed-off (a handoffs/ record), and in-flight "
                "(neither). Cite the record or report the agent as in-flight — "
                "converting silence into a finding is the failure this closes."
            ),
        ))
    return gaps


def _condition_tokens(text: str) -> set[str]:
    """The CONDITION words of a gate sentence — the gate vocabulary itself is
    dropped so two unrelated gates never look alike."""
    tokens = {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 4}
    return tokens - _GATE_STOPWORDS


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")


def _sentence_around(text: str, marker: str) -> str:
    """The sentence containing ``marker`` — the unit a gate's CONDITION is
    stated in.

    hei-adversary-g3 B-7: scoping the condition to the whole window let an
    unrelated registered gate_id, dropped into a trailing sentence, lend its
    tokens to a brand-new gate declared in the first sentence. A gate is named
    in a sentence; compare that sentence.
    """
    lower_marker = marker.lower()
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if lower_marker in sentence.lower():
            return sentence
    return text


def _load_declared_gates(
    verification_artifact: dict[str, Any],
    declared_gates_path: Path | str | None,
) -> list[dict[str, Any]] | None:
    """Resolve the declared-gates registry. ``None`` means UNAVAILABLE — the
    fail-open state for the ``undeclared-gate-language`` severity ONLY (a run
    that never wrote a registry gets no gate findings; the other four families
    are untouched by the registry's absence)."""
    inline = verification_artifact.get("declared_gates")
    path = declared_gates_path
    if path is None:
        candidate = verification_artifact.get("declared_gates_path")
        if isinstance(candidate, str) and candidate:
            path = candidate
    raw: Any = None
    if path is not None:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # hei-adversary-g3 B-9: fall through to the inline registry rather
            # than let a typo'd path silently disable the severity for a caller
            # who supplied both.
            raw = None
    if raw is None and isinstance(inline, list):
        raw = inline
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = raw.get("gates") or raw.get("declared_gates")
    if not isinstance(raw, list):
        return None
    return [entry for entry in raw if isinstance(entry, dict)]


def _gate_entry_covers(entry: dict[str, Any], window_lower: str, condition: set[str]) -> bool:
    """Does THIS registry entry cover the gate this window names?

    hei-adversary-g3 B-7: a `gate_id in window` short-circuit answered "is this
    id mentioned here", not "is this gate that gate" — so a report declaring a
    brand-new gate escaped by mentioning an unrelated registered id in the same
    window. The id now contributes its TOKENS to the comparison (below) and
    earns no bypass of its own.
    """
    entry_text = " ".join(
        str(entry.get(key, ""))
        for key in ("declaration_text", "check_command_or_artifact", "gate_id")
    )
    overlap = condition & _condition_tokens(entry_text)
    return len(overlap) >= _GATE_CONDITION_TOKEN_OVERLAP_MIN


def _detect_undeclared_gate_language(
    verification_artifact: dict[str, Any],
    declared_gates_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """The report names a condition that gates the release with no matching
    entry in the declared-gates registry — a gate you name is a gate you
    record (R9)."""
    entries = _load_declared_gates(verification_artifact, declared_gates_path)
    if entries is None:
        return []
    gaps: list[dict[str, Any]] = []
    for source, window, marker_id, marker in _claim_hits(
        verification_artifact, _GATE_LANGUAGE_MARKERS,
        severity="undeclared-gate-language", negation_guarded=False,
    ):
        condition = _condition_tokens(_sentence_around(window["text"], marker))
        if len(condition) < _GATE_CONDITION_TOKEN_OVERLAP_MIN:
            # Gate vocabulary too thin to name a condition ("the release gate
            # is green"): it could not reach the overlap threshold against ANY
            # entry, so an unmatched result here says nothing about the
            # registry. The severity fires on gate language NAMING a
            # condition — precondition unmet, fail open.
            continue
        if any(_gate_entry_covers(e, window["lower"], condition) for e in entries):
            continue
        gaps.append(_claim_gap(
            "undeclared-gate-language", source, window, marker_id, marker,
            evidence=(
                f"{source} line {window['line']} uses release-gate language "
                f"({marker!r}) naming a condition with no matching entry among "
                f"the {len(entries)} declared-gates registry entries"
            ),
            remediation=(
                "v3.47.0 declared-gates registry. A gate you name is a gate you "
                "record: append {gate_id, declaration_text, "
                "check_command_or_artifact, declared_at} to "
                ".architect-team/declared-gates.json when you declare it, and "
                "{satisfied_at, evidence_path} when the check runs. An "
                "unrecorded gate is a claim — and the completion audit cannot "
                "hold a run to a gate it was never told about."
            ),
            declared_gate_count=len(entries),
        ))
    return gaps
