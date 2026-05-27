"""Extracts the Mini-Run: <slug> commit trailer used by /architect-team:mini.

Trailer convention — a deliberate subset of Git interpret-trailers semantics:
- The trailer block is the contiguous block of single-line "Token: value"
  entries at the END of the commit message, separated from the rest by a
  blank line.
- A non-trailer line at the very end of the message clears the block — a
  stray prose line at the tail disqualifies what's above it.
- Mentions of "Mini-Run:" in prose (not in the trailer block) are ignored.
- When multiple Mini-Run: trailers exist in the block, the LAST one wins.

What this subset does NOT support (intentionally): `key=value` separator,
continuation lines, multi-line trailer values. The mini pipeline produces
trailers in the canonical `Token: value\\n` form so the simpler grammar
is sufficient.
"""
from __future__ import annotations

import re
from collections import defaultdict

_SLUG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*$")
_TRAILER_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s+.*$")
_MINI_RUN_RE = re.compile(r"^Mini-Run:\s*(\S+)\s*$")


def _trailer_block(message: str) -> list[str]:
    """Return the lines of the commit's trailer block (may be empty)."""
    lines = message.rstrip("\n").splitlines()
    block: list[str] = []
    for line in reversed(lines):
        if line.strip() == "":
            break
        if _TRAILER_LINE_RE.match(line):
            block.append(line)
        else:
            block.clear()
            break
    return list(reversed(block))


def extract(message: str) -> str | None:
    """Return the slug from the Mini-Run: trailer, or None if absent.

    When multiple Mini-Run: trailers exist in the trailer block, the
    LAST one wins — matches Git interpret-trailers convention for
    repeated tokens.
    """
    slug: str | None = None
    for line in _trailer_block(message):
        m = _MINI_RUN_RE.match(line)
        if m:
            slug = m.group(1)
    return slug


def is_valid_slug(slug: str) -> bool:
    """Return True if `slug` matches `YYYY-MM-DD-<lowercase-kebab>`.

    Syntactic check only — does NOT validate that the date is a real
    calendar date (e.g. `2026-13-99-foo` is syntactically valid).
    The slug is produced by the mini pipeline itself, not parsed from
    untrusted input, so a syntactic check is sufficient.
    """
    return bool(_SLUG_RE.match(slug))


def group_by_slug(commits: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Group `(sha, message)` tuples by their Mini-Run: slug.

    Commits without a trailer are dropped.
    """
    out: dict[str, list[str]] = defaultdict(list)
    for sha, msg in commits:
        slug = extract(msg)
        if slug is not None:
            out[slug].append(sha)
    return dict(out)
