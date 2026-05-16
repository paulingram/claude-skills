#!/usr/bin/env python3
"""SubagentStop hook for the architect-team plugin.

For architect-team teammates (those with a manifest at
.architect-team/teammates/<name>.json), verify that every task_id in
expected_review_evidence has a valid review-gate evidence file.

Exit codes:
- 0: this is not an architect-team teammate (no manifest), or all evidence is valid
- 2: required evidence missing or invalid (writes structured stderr describing gaps)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_EVIDENCE_FIELDS = {
    "task_id",
    "spec_review",
    "quality_review",
    "real_not_stubbed",
    "tests",
    "demo_artifact",
    "files_changed",
    "reuse_compliance",
}


def _safe_id(value: str) -> str | None:
    """Return value if safe for use in a filesystem path component, else None.

    Rejects empty strings, values containing '/' or '\\', values starting with
    '.', and the exact string '..'.  These cover every path-traversal vector
    for the controlled identifier sets (subagent names like 'backend-auth',
    'frontend-dashboard') that the hooks handle.
    """
    if not value:
        return None
    if "/" in value or "\\" in value:
        return None
    if value.startswith("."):
        return None
    if value == "..":
        return None
    return value


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as e:
        print(f"teammate-idle-check: malformed hook payload: {e}", file=sys.stderr)
        return 0  # do not block on hook-side decode errors

    name = _extract_subagent_name(payload)
    if not name:
        return 0  # nothing to check

    if _safe_id(name) is None:
        print(
            f"teammate-idle-check: blocking SubagentStop: subagent name {name!r} contains "
            f"path-traversal characters and was rejected.",
            file=sys.stderr,
        )
        return 2

    manifest_path = Path.cwd() / ".architect-team" / "teammates" / f"{name}.json"
    if not manifest_path.exists():
        return 0  # not an architect-team teammate

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(
            f"teammate-idle-check: manifest at {manifest_path} is invalid JSON: {e}",
            file=sys.stderr,
        )
        return 0  # don't block on a corrupt manifest

    expected = manifest.get("expected_review_evidence") or []
    if not isinstance(expected, list):
        print(
            f"teammate-idle-check: manifest expected_review_evidence is not a list",
            file=sys.stderr,
        )
        return 0

    gaps: list[str] = []
    for task_id in expected:
        path = Path.cwd() / ".architect-team" / "reviews" / f"{task_id}.json"
        if not path.exists():
            gaps.append(f"{task_id}: no review evidence at {path}")
            continue
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            gaps.append(f"{task_id}: evidence at {path} is not valid JSON")
            continue
        item_gaps = _validate(evidence)
        if item_gaps:
            gaps.append(f"{task_id}: " + "; ".join(item_gaps))

    if gaps:
        print(
            f"teammate-idle-check: blocking idle of teammate {name!r}: review-gate gaps:\n  - "
            + "\n  - ".join(gaps),
            file=sys.stderr,
        )
        return 2

    return 0


def _extract_subagent_name(payload: dict[str, Any]) -> str | None:
    sub = payload.get("subagent")
    if isinstance(sub, dict):
        n = sub.get("name")
        if isinstance(n, str) and n:
            return n
    # tolerate flatter payload shapes the harness may emit
    n = payload.get("subagent_name")
    if isinstance(n, str) and n:
        return n
    return None


def _validate(evidence: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    missing = REQUIRED_EVIDENCE_FIELDS - evidence.keys()
    if missing:
        return [f"missing fields: {sorted(missing)}"]

    if evidence.get("spec_review") != "pass":
        gaps.append(f"spec_review={evidence.get('spec_review')!r}")
    if evidence.get("quality_review") != "pass":
        gaps.append(f"quality_review={evidence.get('quality_review')!r}")
    if evidence.get("real_not_stubbed") is not True:
        gaps.append("real_not_stubbed not true")
    if evidence.get("reuse_compliance") != "ok":
        gaps.append(f"reuse_compliance={evidence.get('reuse_compliance')!r}")

    tests = evidence.get("tests")
    if not isinstance(tests, dict):
        gaps.append("tests is not an object")
    else:
        added, passing = tests.get("added"), tests.get("passing")
        if not isinstance(added, int) or not isinstance(passing, int):
            gaps.append("tests.added/passing not integers")
        elif added < 1 or added != passing:
            gaps.append(f"tests.added={added} passing={passing}")

    demo = evidence.get("demo_artifact")
    if not isinstance(demo, str) or not demo.strip():
        gaps.append("demo_artifact empty")

    files = evidence.get("files_changed")
    if not isinstance(files, list) or not files:
        gaps.append("files_changed empty")

    return gaps


if __name__ == "__main__":
    sys.exit(main())
