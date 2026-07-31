"""VAO core — verdict-write + shared cross-module helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# R1a (v3.10.0) — _utc_now_iso has a single definition in hooks/shared_util.py.
# Import it (dual-form) and re-expose it here so the family modules' existing
# `from hooks.vao.core import _utc_now_iso` imports keep resolving unchanged.
try:  # package shape: repo root on sys.path
    from hooks.shared_util import _utc_now_iso  # noqa: F401  (re-exported for vao siblings)
except ImportError:  # bare-module shape: hooks/ dir on sys.path
    from shared_util import _utc_now_iso  # noqa: F401  (re-exported for vao siblings)


# ---------------------------------------------------------------------------
# Common output helpers
# ---------------------------------------------------------------------------


def _write_verdict(verdict: dict[str, Any], out_path: Path | str | None) -> dict[str, Any]:
    """Persist the verdict JSON to disk (if ``out_path`` is given) and return it.

    Sort-keys + indent=2 makes output byte-stable for given inputs — the
    determinism contract.
    """
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8")
    return verdict


def _is_test_path(file_path: str) -> bool:
    """v2.12.0 — UNIFIED test-path detector. Recognizes the UNION of all
    test-file heuristics across the plugin (v2.0.0 fake-data audit + v2.8.0
    standing-red audit + future detectors). A file path is a TEST file if:

      - It lives under a recognized test directory: ``tests/``, ``__tests__/``,
        ``__mocks__/``, ``test/``, ``fixtures/``, ``mocks/``.
      - It has a ``.test.`` or ``.spec.`` infix in its basename.
      - Its basename starts with ``test_`` (pytest convention).
      - Its basename ends with ``_test.py`` / ``test.py`` (Go-pytest convention).
      - Its basename ends with ``_spec.rb`` (Ruby rspec convention).

    Test files may legitimately contain fake data, standing-red markers, and
    other patterns the production-code audits forbid; this function lets
    every Layer 3 tool exclude them consistently. Returns ``False`` for
    non-string input rather than raising.
    """
    if not isinstance(file_path, str) or not file_path:
        return False
    fp = file_path.lower().replace("\\", "/")
    # Path-anchored test-directory markers — startswith OR contains as `/.../`.
    test_dir_markers = ("tests/", "__tests__/", "__mocks__/", "test/", "fixtures/", "mocks/")
    if any(fp.startswith(m) or f"/{m}" in fp for m in test_dir_markers):
        return True
    # Filename-infix markers — .test. / .spec.
    if ".test." in fp or ".spec." in fp:
        return True
    # Basename-based markers.
    base = fp.rsplit("/", 1)[-1]
    if base.startswith("test_"):
        return True
    if base.endswith("_test.py") or base.endswith("test.py"):
        return True
    if base.endswith("_spec.rb"):
        return True
    return False


def _looks_like_test_path(path: str) -> bool:
    """Deprecated alias for :func:`_is_test_path` — preserved for v2.8.0 call
    sites until they migrate. v2.12.0 unified the two detectors after the
    audit found they diverged on 3 of 8 test paths (``fixtures/`` and
    ``__mocks__/`` were test paths for v2.6.0 but not v2.8.0; ``_test.py``
    suffix was a test path for v2.8.0 but not v2.6.0). New code should call
    :func:`_is_test_path` directly.
    """
    return _is_test_path(path)


def _scan_markers(text: str, markers: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    """Return the list of (marker_id, pattern) found in `text` (case-insensitive)."""
    if not isinstance(text, str) or not text:
        return []
    lower = text.lower()
    hits: list[tuple[str, str]] = []
    for marker_id, pattern in markers:
        if pattern.lower() in lower:
            hits.append((marker_id, pattern))
    return hits


# ---------------------------------------------------------------------------
# Report-scanning shared helpers
# ---------------------------------------------------------------------------
# v3.47.0 relocated these two from ``deferral.py``. They are the shared
# vocabulary of report scanning: ``deferral.py`` (the v2.10.0 severities) and
# ``deferral_b.py`` (the v3.47.0 claims-citation families) both need them, and
# one tool composes both modules — so core.py, the established shared-helpers
# home, is the only placement that does not create an import cycle. Behavior is
# unchanged; every prior ``from ...deferral import`` name still resolves,
# because deferral.py imports them straight back out of here.


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
    # v3.47.0 — a Layer-3 verdict file and a review-evidence file are the two
    # artifacts the framework itself produces; citing either is citing a
    # machine-written record, which is a STRONGER disposition than prose.
    ".architect-team/vao-verdicts/",
    "verdict_path:",
    "reviews/",
    "evidence:",
)


def _is_enumerated_line(stripped: str) -> bool:
    """True for a bullet / numbered report line (leading whitespace already
    stripped). The v2.10.0 wrap-up heuristic, lifted verbatim so the v3.47.0
    claim families enumerate items exactly the way this tool always has."""
    return (
        stripped.startswith("- ")
        or stripped.startswith("* ")
        or stripped.startswith("• ")
        or (len(stripped) >= 2 and stripped[0].isdigit() and stripped[1] in ".)")
        or (len(stripped) >= 3 and stripped[:2].isdigit() and stripped[2] in ".)")
    )
