#!/usr/bin/env python3
"""Decisions ledger -- the single append-only record of what a run decided.

Stdlib-only; library + CLI. Triage verdicts, reuse decisions, contract
approvals, appearance-mode bindings, principle verdicts, solution-requirement
routing and any option-choice already happen in their own phases and their own
artifacts; nothing summarised them. Each deciding phase now ALSO appends one
line here, and the project homepage renders the ledger as its Decisions panel.

The ledger: ``<workspace>/.architect-team/decisions.jsonl`` -- one JSON object
per line::

    {"schema": "decision/v1", "at", "run_id", "phase",
     "kind": "triage" | "reuse" | "contract-approval" | "appearance" |
             "principles" | "sr-routing" | "option-choice" | "other",
     "summary", "chosen", "rejected": [{"label", "why"}], "refs": [paths]}

``run_id`` / ``phase`` default from ``intake-state.json`` when the caller
does not pass them (read-only, best effort). A line is never edited or
removed: a reversed decision is a NEW line whose summary says so.

CLI::

    python hooks/decisions_ledger.py add --workspace W --kind K --summary S \\
        [--chosen C] [--rejected label=why ...] [--ref path ...] \\
        [--run-id R] [--phase P] [--json]
    python hooks/decisions_ledger.py list --workspace W [--kind K] [--limit N] [--json]

Exit codes: 0 ok, 2 usage / validation error (an unknown kind is refused, not
coerced -- a typo must not become ``other`` silently).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:  # package shape (repo root on sys.path)
    from hooks.shared_util import _utc_now_iso, read_jsonl
    from hooks.run_metrics import _read_intake_state
except ImportError:  # bare-module shape (hooks/ on sys.path, or loaded by path)
    _HERE = str(Path(__file__).resolve().parent)
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from shared_util import _utc_now_iso, read_jsonl
    from run_metrics import _read_intake_state

SCHEMA = "decision/v1"
DECISIONS_RELATIVE_PATH = ".architect-team/decisions.jsonl"
KINDS = (
    "triage", "reuse", "contract-approval", "appearance", "principles",
    "sr-routing", "option-choice", "other",
)
RECORD_FIELDS = ("schema", "at", "run_id", "phase", "kind", "summary", "chosen",
                 "rejected", "refs")


def ledger_path(workspace: Path | str) -> Path:
    return Path(workspace) / DECISIONS_RELATIVE_PATH


def _first_str(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_rejected(rejected: Any) -> list[dict[str, str]]:
    """``[{"label", "why"}]`` from dicts, ``"label=why"`` strings, or bare
    labels (``why`` then empty). Non-string noise is dropped."""
    out: list[dict[str, str]] = []
    if rejected is None:
        return out
    if isinstance(rejected, (str, dict)):
        rejected = [rejected]
    if not isinstance(rejected, (list, tuple)):
        return out
    for item in rejected:
        if isinstance(item, dict):
            label = item.get("label")
            why = item.get("why")
            if isinstance(label, str) and label.strip():
                out.append({"label": label.strip(),
                            "why": why.strip() if isinstance(why, str) else ""})
        elif isinstance(item, str) and item.strip():
            label, sep, why = item.partition("=")
            out.append({"label": label.strip(), "why": why.strip() if sep else ""})
    return out


def normalize_refs(refs: Any) -> list[str]:
    if refs is None:
        return []
    if isinstance(refs, str):
        refs = [refs]
    if not isinstance(refs, (list, tuple)):
        return []
    return [r.strip() for r in refs if isinstance(r, str) and r.strip()]


def make_record(*, kind: str, summary: str, chosen: Any = None, rejected: Any = None,
                refs: Any = None, run_id: Any = None, phase: Any = None,
                at: Any = None) -> dict[str, Any]:
    """Validate + shape one decision line. Raises ``ValueError`` on an unknown
    kind or a blank summary."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}; got {kind!r}")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary must be a non-blank string")
    return {
        "schema": SCHEMA,
        "at": at if isinstance(at, str) and at.strip() else _utc_now_iso(),
        "run_id": run_id if isinstance(run_id, str) and run_id.strip() else None,
        "phase": phase if isinstance(phase, str) and phase.strip() else None,
        "kind": kind,
        "summary": summary.strip(),
        "chosen": chosen.strip() if isinstance(chosen, str) and chosen.strip() else None,
        "rejected": normalize_rejected(rejected),
        "refs": normalize_refs(refs),
    }


def append(workspace: Path | str, **fields: Any) -> dict[str, Any]:
    """Append one decision. ``run_id`` / ``phase`` default from
    ``intake-state.json`` when absent. Returns the written record."""
    if fields.get("run_id") is None or fields.get("phase") is None:
        intake = _read_intake_state(Path(workspace))
        if fields.get("run_id") is None:
            fields["run_id"] = _first_str(intake, "run_id", "runId", "slug")
        if fields.get("phase") is None:
            fields["phase"] = _first_str(intake, "phase")
    rec = make_record(**fields)
    path = ledger_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def read_all(workspace: Path | str) -> list[dict[str, Any]]:
    """Every decision line in file order (malformed lines skipped)."""
    return [r for r in read_jsonl(ledger_path(workspace)) if isinstance(r.get("kind"), str)]


def by_kind(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in records:
        kind = rec.get("kind")
        if isinstance(kind, str):
            counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _format_line(rec: dict[str, Any]) -> str:
    parts = [str(rec.get("at") or "-"), f"[{rec.get('kind')}]",
             str(rec.get("phase") or "-"), str(rec.get("summary") or "")]
    if rec.get("chosen"):
        parts.append(f"=> {rec['chosen']}")
    rejected = rec.get("rejected") or []
    if rejected:
        parts.append("(rejected: " + "; ".join(
            f"{r.get('label')}: {r.get('why')}" if r.get("why") else str(r.get("label"))
            for r in rejected if isinstance(r, dict)) + ")")
    return " ".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="decisions_ledger.py",
                                     description="Append-only run decisions ledger.")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="append one decision")
    add.add_argument("--workspace", required=True)
    add.add_argument("--kind", required=True, choices=KINDS)
    add.add_argument("--summary", required=True)
    add.add_argument("--chosen")
    add.add_argument("--rejected", action="append", default=[], metavar="LABEL=WHY")
    add.add_argument("--ref", action="append", default=[], dest="refs", metavar="PATH")
    add.add_argument("--run-id", dest="run_id")
    add.add_argument("--phase")
    add.add_argument("--json", action="store_true")

    lst = sub.add_parser("list", help="list recorded decisions")
    lst.add_argument("--workspace", required=True)
    lst.add_argument("--kind", choices=KINDS)
    lst.add_argument("--limit", type=int, default=0, help="newest N only (0 = all)")
    lst.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0

    if args.command == "add":
        try:
            rec = append(args.workspace, kind=args.kind, summary=args.summary,
                         chosen=args.chosen, rejected=args.rejected, refs=args.refs,
                         run_id=args.run_id, phase=args.phase)
        except (ValueError, OSError) as exc:
            print(f"decisions_ledger: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(rec, sort_keys=True) if args.json else
              f"recorded -> {ledger_path(args.workspace)}: {_format_line(rec)}")
        return 0

    records = read_all(args.workspace)
    if args.kind:
        records = [r for r in records if r.get("kind") == args.kind]
    if args.limit and args.limit > 0:
        records = records[-args.limit:]
    if args.json:
        print(json.dumps({"schema": SCHEMA, "path": str(ledger_path(args.workspace)),
                          "count": len(records), "by_kind": by_kind(records),
                          "decisions": records}, sort_keys=True, indent=2))
    elif not records:
        print(f"(no decisions recorded at {ledger_path(args.workspace)})")
    else:
        for rec in records:
            print(_format_line(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
