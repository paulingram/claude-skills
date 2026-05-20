#!/usr/bin/env python3
"""SubagentStop hook for the architect-team plugin.

For architect-team teammates (those with a manifest at
.architect-team/teammates/<name>.json), verify that every task_id in
expected_review_evidence has a valid review-gate evidence file.

The evidence schema + validation logic live in `review_evidence_schema.py`
(a sibling module) so this hook and `review-gate-task.py` enforce the SAME
contract — before v0.9.9 they had drifted (8 fields here vs 11 there).

Exit codes:
- 0: this is not an architect-team teammate (no manifest), or all evidence is valid
- 2: required evidence missing or invalid (writes structured stderr describing gaps)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from review_evidence_schema import safe_id, validate_evidence


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as e:
        print(f"teammate-idle-check: malformed hook payload: {e}", file=sys.stderr)
        return 0  # do not block on hook-side decode errors

    name = _extract_subagent_name(payload)
    if not name:
        return 0  # nothing to check

    if safe_id(name) is None:
        print(
            f"teammate-idle-check: blocking SubagentStop: subagent name {name!r} contains "
            f"path-traversal characters and was rejected.",
            file=sys.stderr,
        )
        return 2

    manifest_path = Path.cwd() / ".architect-team" / "teammates" / f"{name}.json"
    if not manifest_path.exists():
        return 0  # not an architect-team teammate

    # The manifest path matches THIS subagent's name, so it IS an architect-team
    # teammate. A corrupt manifest here is an architect-team artifact failure —
    # block rather than fail open (a teammate must not escape the idle gate by
    # writing garbage to its own manifest).
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(
            f"teammate-idle-check: blocking idle of teammate {name!r}: its manifest at "
            f"{manifest_path} is not valid JSON ({e}). Repair the manifest before idling.",
            file=sys.stderr,
        )
        return 2

    expected = manifest.get("expected_review_evidence") or []
    if not isinstance(expected, list):
        print(
            f"teammate-idle-check: blocking idle of teammate {name!r}: manifest "
            f"expected_review_evidence is not a list.",
            file=sys.stderr,
        )
        return 2

    gaps: list[str] = []
    for task_id in expected:
        if safe_id(str(task_id)) is None:
            gaps.append(f"{task_id!r}: task_id contains path-traversal characters")
            continue
        path = Path.cwd() / ".architect-team" / "reviews" / f"{task_id}.json"
        if not path.exists():
            gaps.append(f"{task_id}: no review evidence at {path}")
            continue
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            gaps.append(f"{task_id}: evidence at {path} is not valid JSON")
            continue
        item_gaps = validate_evidence(evidence)
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


if __name__ == "__main__":
    sys.exit(main())
