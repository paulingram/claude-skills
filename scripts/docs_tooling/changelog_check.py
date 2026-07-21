# -*- coding: utf-8 -*-
"""Deterministic CHANGELOG conformance check (REQ-006).

Stdlib-only, no import-time side effects. Enforces the two mechanically-checkable
invariants of the house CHANGELOG shape documented in `docs/CHANGELOG_RUBRIC.md`:

  (a) the TOP `## [x.y.z]` entry's version equals `.claude-plugin/plugin.json`'s
      `version` — the manifest and the changelog head move together at release
      time, so a mismatch means a version bump landed without its changelog entry
      (or vice-versa);
  (b) the TOP entry carries a suite-total line matching `SUITE_TOTAL_RE` — the
      `Suite N passing + M skipped (K test files)` convention that every release
      entry states, so a green done-bar always carries its verified suite count.

Everything else in the rubric (verdict-first headline, verified-counts-only,
honest-divergence notes, per-release narrative, append-only history) is
LLM-judgment — this engine does not attempt to grade it.

Public surface::

    plugin_version(root)          -> str
    parse_top_entry(text)         -> (version | None, entry_text)
    check_changelog(root)         -> {"ok": bool, "violations": [str],
                                      "top_version": str | None, "plugin_version": str}

CLI:  changelog_check.py [<root>] [--json]   (exit non-zero, naming violations)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, Union

# A version header: `## [3.42.0] — ...`. Anchored at line start (MULTILINE) so a
# bracketed version mentioned mid-paragraph never registers as an entry head.
_VERSION_HEADER_RE = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.MULTILINE)

# The suite-total line. Accepts every attested house form:
#   Suite **5646 -> 5689 passing + 4 skipped** (202 test files ...)
#   Suite **5362 passing + 4 skipped** (198 test files ...)
#   - Suite: **5542 passing + 4 skipped, IDENTICAL to v3.40.0** (199 test files; ...)
# i.e. the word "Suite", an optional progression "<n> -> ", the "<n> passing +
# <n> skipped" core, then any trailing text before "(<n> test files". The arrow may
# be the unicode right-arrow or an ASCII "->". Counts may carry thousands commas.
SUITE_TOTAL_RE = re.compile(
    r"Suite\s*:?\s*\*{0,2}\s*"
    r"(?:[\d,]+\s*(?:->|→)\s*)?"
    r"[\d,]+\s+passing\s*\+\s*\d+\s+skipped"
    r"[^\n]*?test files"
)


def plugin_version(root: Union[str, Path]) -> str:
    """The `version` field of `.claude-plugin/plugin.json`."""
    data = json.loads(
        (Path(root) / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    return str(data["version"])


def parse_top_entry(text: str) -> tuple[Optional[str], str]:
    """Return (version, entry_text) for the FIRST `## [x.y.z]` block in `text`.

    `entry_text` runs from that header up to (but excluding) the next version
    header, or to end-of-file for the only/last entry. Returns (None, "") when the
    changelog carries no version entry at all.
    """
    m = _VERSION_HEADER_RE.search(text)
    if m is None:
        return None, ""
    version = m.group(1)
    nxt = _VERSION_HEADER_RE.search(text, m.end())
    end = nxt.start() if nxt else len(text)
    return version, text[m.start():end]


def check_changelog(root: Union[str, Path]) -> dict[str, Any]:
    """Check the top CHANGELOG entry against the two REQ-006 invariants."""
    root = Path(root)
    violations: list[str] = []

    pv = plugin_version(root)
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    top_version, entry = parse_top_entry(text)

    if top_version is None:
        violations.append(
            "CHANGELOG.md has no '## [x.y.z]' version entry — the changelog head "
            "cannot be checked"
        )
    elif top_version != pv:
        violations.append(
            f"top CHANGELOG entry version {top_version!r} != plugin.json version "
            f"{pv!r} — bump the changelog head and the manifest together at release"
        )

    if not SUITE_TOTAL_RE.search(entry):
        violations.append(
            "top CHANGELOG entry has no suite-total line — add the house "
            "'Suite <N> passing + <M> skipped (<K> test files)' line with this "
            "release's verified counts (see docs/CHANGELOG_RUBRIC.md)"
        )

    return {
        "ok": not violations,
        "violations": violations,
        "top_version": top_version,
        "plugin_version": pv,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: check the repo's CHANGELOG; exit non-zero naming any violation."""
    import argparse

    parser = argparse.ArgumentParser(description="CHANGELOG conformance check (REQ-006).")
    parser.add_argument("root", nargs="?", default=".", help="repo root (default: cwd)")
    parser.add_argument("--json", action="store_true", help="emit the full JSON result")
    args = parser.parse_args(argv)

    result = check_changelog(args.root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print(
            f"changelog-check: clean — top entry {result['top_version']} matches "
            f"plugin.json and carries a suite-total line."
        )
    else:
        print("changelog-check: violations —")
        for v in result["violations"]:
            print(f"  - {v}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
