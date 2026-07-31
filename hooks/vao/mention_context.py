"""VAO mention-vs-use context — v3.47.0.

The use/mention distinction for the report-claims families in ``deferral_b.py``.
A document that documents a rule has to quote the phrases the rule forbids —
this change's own release notes and CHANGELOG do exactly that — so a scanner
with no notion of mention flags the text explaining it.

Its own module because it is a coherent subsystem, not overflow: one question
("is this occurrence being quoted or asserted?"), one vocabulary, and one place
a future editor will look for it. Composition runs one way only:
``deferral.py -> deferral_b.py -> mention_context.py -> core.py``.

Judgement is PER-OCCURRENCE. hei-adversary-g3's B-15 showed why: judged per
window, a quoted mention shadowed an unquoted claim beside it, and the CT6
release-notes bullet for this very feature passed clean. A mention excuses
itself, never its neighbours.

Stdlib-only; no import-time side effects; every function is pure.
"""

from __future__ import annotations

import re
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _boundary_pattern, _first_token_present
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _boundary_pattern, _first_token_present
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _boundary_pattern, _first_token_present


# The severity ids this module owns. A window that NAMES one is documentation
# ABOUT the machinery, not a claim made with it.
_OWN_SEVERITY_IDS: tuple[str, ...] = (
    "uncited-completion-claim",
    "uncited-deploy-claim",
    "absence-claim-uncited",
    "stalled-agent-claim-uncited",
    "undeclared-gate-language",
)


# Cues that mark a quoted phrase as reported speech rather than assertion.
_MENTION_ATTRIBUTION_CUES: tuple[str, ...] = (
    # Rule-DOCUMENTATION phrases only. hei-adversary-g3 B-12: 'records',
    # 'documents', 'severity', 'marker' and 'detects' were cues AND ordinary
    # domain vocabulary — "The patient records module and the documents tab
    # both shipped" supplied two for free. A cue must be a phrase that only
    # appears when prose is TALKING ABOUT a rule.
    "postmortem",
    "fires on",
    "fires when",
    "fires only",
    "anti-pattern",
    "forbids",
    "forbidden",
    "detected by",
    "severity id",
    "marker id",
    "the rule",
    "this rule",
    "verbatim",
    "quoted above",
    "reads as mention",
    "not a claim",
)


# Opening/closing quote characters. Single quotes are deliberately EXCLUDED —
# an apostrophe would make `it's` look like an open quote.
_QUOTED_SPAN_RE = re.compile(r'["“”`]([^"“”`\n]{1,300})["“”`]')


def _span_is_quote_enclosed(text_lower: str, start: int, end: int) -> bool:
    """True when THIS occurrence — the span [start, end) — sits inside a
    quotation. Per-occurrence, so a quoted mention cannot vouch for an
    unquoted claim elsewhere in the same window (hei-adversary-g3 B-15)."""
    return any(
        q.start(1) <= start and end <= q.end(1)
        for q in _QUOTED_SPAN_RE.finditer(text_lower)
    )


def _marker_is_quote_enclosed(text_lower: str, pattern: str) -> bool:
    """True when ANY occurrence of the marker in this window sits inside a
    quotation.

    Any-occurrence rather than first-occurrence: the marker frequently appears
    twice in a documentation line — once inside the severity id itself
    (``stalled``-agent-claim-uncited) and once as the quoted term under
    discussion. Keying on the first hit read the id as an unquoted claim. The
    quoted form appearing at all is what makes the line a mention, and the cue
    and own-severity-id conditions carry the rest of the weight.
    """
    quoted_spans = [(q.start(1), q.end(1)) for q in _QUOTED_SPAN_RE.finditer(text_lower)]
    if not quoted_spans:
        return False
    return any(
        start <= match.start() and match.end() <= end
        for match in _boundary_pattern(pattern).finditer(text_lower)
        for start, end in quoted_spans
    )


def _span_is_inside_a_severity_id(text_lower: str, start: int, end: int) -> bool:
    """True when the span falls inside one of this module's severity ids.

    Per-occurrence judging (B-15) surfaced this: `stalled` occurs twice in
    ``- stalled-agent-claim-uncited: ... an agent "stalled" ...`` — once inside
    the id and once as the quoted term. The first is part of the machinery's
    NAME and asserts nothing about any agent.
    """
    for severity in _OWN_SEVERITY_IDS:
        at = text_lower.find(severity)
        while at != -1:
            if at <= start and end <= at + len(severity):
                return True
            at = text_lower.find(severity, at + 1)
    return False


def _is_mention_context(
    window: dict[str, Any],
    pattern: str,
    severity: str | None = None,
    span: tuple[int, int] | None = None,
) -> bool:
    """True when the marker is being MENTIONED rather than USED.

    The document that documents a rule has to quote the phrases the rule
    forbids — this change's own release notes do exactly that — so a scanner
    with no use/mention distinction flags the text explaining it.

    Mention requires ALL of:

    1. the marker occurrence is QUOTE-ENCLOSED. You mention a phrase by
       quoting it. This is non-negotiable and it is what makes the guard
       un-typeable: no bare tag can buy an exemption.
    2. the window carries an attribution cue (:data:`_MENTION_ATTRIBUTION_CUES`).
    3. the window is PROSE, or — if it is an ENUMERATED item — it also names
       THIS family's own severity id.

    Condition 3's per-family scoping matters: naming ``absence-claim-uncited``
    must not suppress the completion family in the same window.

    hei-adversary-g3's B-1 killed the first version of this guard, which
    returned True on any window merely CONTAINING a severity id, before the
    enumerated check and across all five families. Appending ``Not an
    uncited-completion-claim`` to every bullet made a report in which every
    claim was uncited return ``valid=true``. A guard a claimant can satisfy by
    typing is not a guard.

    Stated residual boundary: a deliberate three-part construction — quotation
    marks AND an attribution cue AND the exact severity id, in one enumerated
    item — still reads as mention. That is legible and anomalous rather than
    accidental, and closing it would require modelling intent.
    """
    lower = window["lower"]
    if span is not None and _span_is_inside_a_severity_id(lower, *span):
        return True
    quoted = (
        _span_is_quote_enclosed(lower, *span) if span is not None
        else _marker_is_quote_enclosed(lower, pattern)
    )
    if not quoted:
        return False
    if _first_token_present(lower, _MENTION_ATTRIBUTION_CUES) is None:
        return False
    if not window["enumerated"]:
        return True
    return bool(severity) and severity in lower
