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

A THIRD invariant is available opt-in (v3.60.0), `check_measurement_backing`:

  (c) the suite count the TOP entry states must be backed by a recorded
      bracket artifact under `docs/measurements/` (or the gitignored runtime
      `.architect-team/measurements/`). It composes with (b) rather than
      duplicating it: (b) forces the entry to STATE a count, and (c) forces the
      stated count to have been MEASURED — so "just don't publish a number" is
      already closed by the invariant next door. Kept as a separate function so
      `check_changelog`'s dict contract is byte-compatible; the CLI exposes it
      behind `--require-measurements`.

Public surface::

    plugin_version(root)          -> str
    parse_top_entry(text)         -> (version | None, entry_text)
    check_changelog(root)         -> {"ok": bool, "violations": [str],
                                      "top_version": str | None, "plugin_version": str}
    check_measurement_backing(root)
                                  -> {"ok": bool, "findings": [str],
                                      "claims": [...], "artifacts_seen": int}

CLI:  changelog_check.py [<root>] [--json] [--require-measurements]
      (exit non-zero, naming violations)
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
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


#: The measurement engine, loaded by path — `scripts/` is not an importable
#: package, and resolving from `__file__` keeps the lookup independent of cwd.
_MEASURE_PATH = Path(__file__).resolve().parents[1] / "measure" / "suite_measurement.py"


def _load_suite_measurement() -> ModuleType:
    """Load `scripts/measure/suite_measurement.py`. Raises if it is missing."""
    spec = importlib.util.spec_from_file_location("ct6_suite_measurement", _MEASURE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - unreachable in-repo
        raise ImportError(f"cannot load the measurement engine at {_MEASURE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_measurement_backing(root: Union[str, Path]) -> dict[str, Any]:
    """Invariant (c): the top entry's suite count must have a recorded bracket.

    Scoped to the TOP entry — the current release's claim. Historical counts in
    older entries are NOT retroactively demanded; no artifact can be produced for
    a tree that no longer exists, and a gate that demands the impossible gets
    disabled rather than satisfied.

    Fails CLOSED: if the measurement engine cannot be loaded, that is an unknown
    state, not a pass.
    """
    root = Path(root)
    try:
        measure = _load_suite_measurement()
    except Exception as exc:  # noqa: BLE001 - unknown state must block, not pass
        return {
            "ok": False,
            "findings": [f"the measurement engine could not be loaded ({exc})"],
            "claims": [],
            "artifacts_seen": 0,
        }

    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    _, entry = parse_top_entry(text)
    result = measure.verify_measurement_claim(
        entry, [root / d for d in measure.MEASUREMENT_SEARCH_DIRS]
    )

    # Release-time only: a genuine measurement of a tree that has since moved is
    # an honest record cited for the wrong tree. Undecidable currency is reported,
    # never assumed in either direction.
    findings = list(result["findings"])
    for claim in result["claims"]:
        if not claim.get("backed"):
            continue
        try:
            artifact = json.loads(Path(claim["artifact"]).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            findings.append(f"{claim['artifact']}: became unreadable ({exc})")
            continue
        current, detail = measure.measurement_is_current(artifact, root)
        claim["current"] = current
        claim["currency_detail"] = detail
        if current is False:
            findings.append(
                f"the artifact backing '{claim['passed']} passing' is STALE: {detail}. "
                f"Re-run the measurement as the last act before committing."
            )
        elif current is None:
            findings.append(f"currency of {Path(claim['artifact']).name} is undecidable: {detail}")

    result = dict(result)
    result["findings"] = findings
    result["ok"] = not findings
    return result


def check_release_measurement_present(root: Union[str, Path]) -> dict[str, Any]:
    """The CONVERGENT half of invariant (c), safe to enforce inside the suite.

    When the top entry publishes a suite count, a measurement artifact recorded
    FOR this release (matching `plugin.json`'s version) with a closed bracket must
    exist. Count agreement and green-ness are NOT checked here — a whole-suite
    count compared against an artifact produced by that same suite cannot be
    bootstrapped from inside it (see `suite_measurement`'s "self-reference
    constraint"); `check_measurement_backing` does that at release time.

    Fails CLOSED on an unloadable engine.
    """
    root = Path(root)
    try:
        measure = _load_suite_measurement()
    except Exception as exc:  # noqa: BLE001 - unknown state must block, not pass
        return {
            "ok": False,
            "findings": [f"the measurement engine could not be loaded ({exc})"],
            "claims": [],
            "artifacts_seen": 0,
        }

    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    _, entry = parse_top_entry(text)
    claims = measure.parse_suite_claims(entry)
    if not claims:
        return {"ok": True, "findings": [], "claims": [], "artifacts_seen": 0}

    version = plugin_version(root)
    dirs = [root / d for d in measure.MEASUREMENT_SEARCH_DIRS]
    matching, reasons = measure.find_release_artifacts(dirs, version)
    findings: list[str] = []

    # (i) ALWAYS: an artifact labelled for this release that cannot be used is a
    # lie already committed to a durable location. `reasons` is populated only
    # for artifacts that ARE labelled for this version, so a non-empty list means
    # a bad one exists — never merely that none was found.
    for reason in reasons:
        findings.append(
            f"an artifact labelled for v{version} cannot back its release — {reason}"
        )

    # (ii) ALWAYS: a usable release artifact must AGREE with the published count.
    for artifact in matching:
        counts = measure.artifact_counts(artifact) or {}
        if counts.get("passed") != claims[0].passed or counts.get("skipped") != claims[0].skipped:
            findings.append(
                f"the recorded measurement for v{version} says "
                f"{counts.get('passed')} passed / {counts.get('skipped')} skipped, but the "
                f"CHANGELOG publishes {claims[0].passed} passing + {claims[0].skipped} skipped"
            )

    # (iii) CONDITIONALLY: demand that a measurement EXIST only when the tree is
    # clean. A release measurement can only be taken on a release tree, so
    # demanding one mid-development demands something that cannot exist yet, and
    # a gate that demands the impossible gets deleted rather than satisfied. On a
    # fresh clone and in CI the tree IS clean, which is exactly where a published
    # count with no artifact behind it must not pass.
    tree = measure.tree_digest(root)
    if not matching and tree.get("dirty") is False:
        findings.append(
            f"the top CHANGELOG entry publishes a suite count "
            f"('{claims[0].passed} passing + {claims[0].skipped} skipped') and the tree is "
            f"clean, but no bracketed measurement was recorded for v{version}. Run: "
            f"python scripts/measure/suite_measurement.py --label v{version}"
        )

    return {
        "ok": not findings,
        "findings": findings,
        "claims": [{"passed": c.passed, "skipped": c.skipped, "text": c.text} for c in claims],
        "artifacts_seen": len(matching),
        "tree_dirty": tree.get("dirty"),
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: check the repo's CHANGELOG; exit non-zero naming any violation."""
    import argparse

    parser = argparse.ArgumentParser(description="CHANGELOG conformance check (REQ-006).")
    parser.add_argument("root", nargs="?", default=".", help="repo root (default: cwd)")
    parser.add_argument("--json", action="store_true", help="emit the full JSON result")
    parser.add_argument(
        "--require-measurements",
        action="store_true",
        help="also require the top entry's suite count to have a bracket artifact",
    )
    args = parser.parse_args(argv)

    result = check_changelog(args.root)
    backing: Optional[dict[str, Any]] = None
    if args.require_measurements:
        backing = check_measurement_backing(args.root)
        result = dict(result)
        result["measurement_backing"] = backing

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

    if backing is not None and not args.json:
        if backing["ok"]:
            print(
                f"changelog-check: {len(backing['claims'])} suite claim(s) backed by "
                f"a recorded bracket."
            )
        else:
            print("changelog-check: unbacked suite claims —")
            for f in backing["findings"]:
                print(f"  - {f}")

    ok = result["ok"] and (backing is None or backing["ok"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
