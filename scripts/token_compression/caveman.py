# -*- coding: utf-8 -*-
"""Deterministic "caveman" token-compression engine (TC-1 … TC-3).

Stdlib-only, no import-time side effects. The deterministic, always-available
half of the **token-compression** discipline: reduce the verbosity of agents'
INTERNAL communication ("talk like a caveman") to lower token consumption (TC-2),
WITHOUT harming external output quality (TC-1 — never run this on output to users
or other systems).

This is a conservative, MEANING-PRESERVING compressor: it drops pure filler
(articles, politeness, intensifiers/hedges) and a few wordy phrases, and it
preserves all content words, identifiers, numbers, line structure, AND fenced /
inline code verbatim. It is a lossy-of-FILLER heuristic, NOT a semantic ML
compressor — TC-3's "evaluate available token-compression packages" (e.g.
LLMLingua) is a heavier, third-party option the skill documents plugging in; this
stdlib baseline needs no package and is the floor.

This module:
- `compress(text)` — the caveman transform.
- `estimate_tokens(text)` — a rough token estimate (~4 chars/token).
- `compression_stats(text)` — original/compressed sizes + the savings ratio.

It is the machine; `skills/token-compression/SKILL.md` is the contract (incl. the
hard internal-only boundary).
"""
from __future__ import annotations

import re
import string
from typing import Any, Optional

# Pure filler dropped under caveman compression — articles, politeness, and
# intensifiers/hedges that carry emphasis but NOT content. Matched case-insensitively
# with surrounding punctuation stripped. Prepositions / conjunctions / copulas are
# DELIBERATELY kept (they carry meaning) so the compressed text stays understandable.
FILLER_WORDS: frozenset[str] = frozenset({
    "a", "an", "the",
    "please", "kindly", "thanks", "thank",
    "just", "really", "very", "actually", "basically", "simply", "literally",
    "essentially", "quite", "rather", "somewhat", "fairly", "pretty", "truly",
    "definitely", "certainly", "obviously", "clearly", "honestly", "frankly",
})

# Wordy phrases -> shorter meaning-preserving equivalents (applied before token drop).
PHRASE_SUBS: tuple[tuple[str, str], ...] = (
    ("in order to", "to"),
    ("due to the fact that", "because"),
    ("at this point in time", "now"),
    ("at this time", "now"),
    ("in the event that", "if"),
    ("for the purpose of", "for"),
    ("a large number of", "many"),
    ("the majority of", "most"),
    ("in spite of the fact that", "although"),
    ("with regard to", "re"),
    ("in terms of", "for"),
    ("make sure to", "ensure"),
    ("be sure to", "ensure"),
)

_CODE_SPLIT_RE = re.compile(r"(```.*?```|`[^`]*`)", re.DOTALL)


def _compress_prose(seg: str) -> str:
    """Compress a non-code prose segment: phrase subs + filler drop, preserving
    line structure (newlines) and collapsing intra-line whitespace. A single
    boundary space is preserved at the segment edges so prose words do not glue to
    an adjacent code segment when the parts are rejoined (e.g. ``run `cmd` now``)."""
    if not seg:
        return seg
    lead = " " if seg[:1] in " \t" else ""
    trail = " " if seg[-1:] in " \t" else ""
    for a, b in PHRASE_SUBS:
        seg = re.sub(rf"\b{re.escape(a)}\b", b, seg, flags=re.IGNORECASE)
    out_lines = []
    for line in seg.split("\n"):
        kept = [
            tok for tok in line.split()
            if tok.lower().strip(string.punctuation) not in FILLER_WORDS
        ]
        out_lines.append(" ".join(kept))
    body = "\n".join(out_lines)
    if not body:
        return " " if (lead or trail) else ""
    return lead + body + trail


def compress(text: str) -> str:
    """Caveman-compress INTERNAL prose (TC-2). Fenced (```…```) and inline (`…`)
    code is preserved VERBATIM; only prose segments are compressed. Content words,
    identifiers, numbers, and line structure are preserved — only filler is dropped.

    DO NOT run this on external output (TC-1) — it is for internal agent
    communication only; the skill enforces that boundary."""
    text = text or ""
    parts = _CODE_SPLIT_RE.split(text)
    out = []
    for i, seg in enumerate(parts):
        # odd indices are the captured code groups -> verbatim; even are prose
        out.append(seg if i % 2 == 1 else _compress_prose(seg))
    return "".join(out)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token — a common heuristic). 0 for empty."""
    text = text or ""
    if not text.strip():
        return 0
    return max(1, round(len(text) / 4))


def compression_stats(text: str) -> dict[str, Any]:
    """Compress `text` and report the size delta + savings (TC-2 measurement)."""
    text = text or ""
    compressed = compress(text)
    o = estimate_tokens(text)
    c = estimate_tokens(compressed)
    return {
        "schema": "token-compression-stats/v1",
        "original_chars": len(text),
        "compressed_chars": len(compressed),
        "original_tokens_est": o,
        "compressed_tokens_est": c,
        "ratio": round(c / o, 4) if o else 1.0,
        "saved_pct": round(100 * (1 - c / o), 1) if o else 0.0,
        "compressed_text": compressed,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: caveman-compress text, or report compression stats.

    Usage:
      caveman.py compress [--input <file>]   # reads stdin if no --input
      caveman.py stats   [--input <file>] [--json]
    """
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Caveman token-compression engine (TC-1…3).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("compress", "stats"):
        p = sub.add_parser(name)
        p.add_argument("--input", default=None, help="input file (default: stdin)")
        if name == "stats":
            p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()

    if args.cmd == "compress":
        sys.stdout.write(compress(text))
        return 0

    stats = compression_stats(text)
    if getattr(args, "json", False):
        print(json.dumps(stats, indent=2, sort_keys=True))
    else:
        print(f"tokens (est): {stats['original_tokens_est']} -> "
              f"{stats['compressed_tokens_est']} ({stats['saved_pct']}% saved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
