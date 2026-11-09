"""Converge-gate records -- declare before the loop, record after it (v4.1.0).

Why this exists. The retired ralph-loop plugin wrapped a prompt in a Stop hook
that re-fed the prompt until the model typed a completion promise. Its
strength was that the turn could not end while the loop was open; its weakness
was that the exit test was a string the model typed, compared by equality,
with nothing verifying it. ``ct6-converge`` keeps the first property and fixes
the second:

* ``declare`` appends gate ``converge:<kind>`` to the declared-gates registry
  (``<workspace>/.architect-team/declared-gates.json``). The Stop-hook arm
  ``_audit_declared_gates`` (hooks/pipeline-completion-audit.py) refuses to let
  the run end while a declared gate has no ``satisfied_at`` + non-empty
  ``evidence_path`` -- the same hold ralph-loop's Stop hook provided, enforced
  from disk rather than from the transcript.
* ``record`` takes the JSON the workflow returned, writes it to
  ``<workspace>/.architect-team/converge/<kind>-<ts>.json`` and satisfies the
  gate ONLY when ``converged`` is true, every reviewer returned in the final
  round and every one of them said ``ok``. A result that does not meet that
  exits 1 and leaves the gate open, so the Lead must run the loop again. A
  human-set ``maxRounds`` can pause the loop; it can never satisfy the gate.
* ``status`` lists the converge gates and whether each is satisfied.

The verdicts are what the exit condition reads, not a phrase. Stdlib-only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "ct6-converge/v1"
GATE_PREFIX = "converge:"
REGISTRY_RELATIVE = Path(".architect-team") / "declared-gates.json"
RECORDS_RELATIVE = Path(".architect-team") / "converge"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _registry_path(workspace: Path) -> Path:
    return Path(workspace) / REGISTRY_RELATIVE


def _read_registry(path: Path) -> List[Any]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a JSON array")
    return data


def _write_registry(path: Path, entries: List[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def gate_id_for(kind: str) -> str:
    return f"{GATE_PREFIX}{kind.strip()}"


def declare(workspace: Path, kind: str, promise: str, reviewers: int,
            artifacts: Optional[List[str]] = None) -> Tuple[str, bool]:
    """Append the convergence gate for ``kind``. Returns (gate_id, appended);
    re-declaring an existing gate is a no-op so a re-run never duplicates it."""
    if not kind.strip():
        raise ValueError("kind must be a non-empty label")
    if reviewers < 1:
        raise ValueError("reviewers must be >= 1")
    registry = _registry_path(workspace)
    entries = _read_registry(registry)
    gid = gate_id_for(kind)
    for existing in entries:
        if isinstance(existing, dict) and existing.get("gate_id") == gid:
            return gid, False
    entries.append({
        "gate_id": gid,
        "declaration_text": (
            f"{promise}: every one of {reviewers} independent reviewer(s) returned ok "
            f"for {kind}" + (f" over {', '.join(artifacts)}" if artifacts else "")
        ),
        "check_command_or_artifact": (
            f"ct6-converge workflow result recorded by scripts/converge/record.py "
            f"(.architect-team/converge/{kind}-<ts>.json with converged=true)"
        ),
        "declared_at": _utc_now_iso(),
        "kind": kind,
        "promise": promise,
        "reviewers": reviewers,
    })
    _write_registry(registry, entries)
    return gid, True


def evaluate(result: Dict[str, Any], expected_reviewers: Optional[int] = None) -> Tuple[bool, List[str]]:
    """Decide whether a workflow result proves convergence. Returns
    (converged, reasons). Every reason names the exact rule that failed."""
    reasons: List[str] = []
    if not isinstance(result, dict):
        return False, ["result is not a JSON object"]
    rec = result.get("record") if isinstance(result.get("record"), dict) else {}
    converged = result.get("converged", rec.get("converged"))
    if converged is not True:
        reasons.append("converged is not true")
    history = result.get("history") if isinstance(result.get("history"), list) else rec.get("history")
    reviewers = rec.get("reviewers", expected_reviewers)
    if expected_reviewers is not None and reviewers not in (None, expected_reviewers):
        reasons.append(f"record names {reviewers} reviewers, the gate was declared with {expected_reviewers}")
    n = expected_reviewers if expected_reviewers is not None else reviewers
    if not history:
        reasons.append("history is empty: no reviewer round was recorded")
    else:
        last = history[-1] if isinstance(history[-1], dict) else {}
        ok = last.get("ok")
        returned = last.get("reviewers_returned")
        if n is None:
            reasons.append("reviewer count unknown: neither the record nor the gate names it")
        else:
            if returned != n:
                reasons.append(f"final round: {returned} of {n} reviewers returned a verdict (silence is not ok)")
            if ok != n:
                reasons.append(f"final round: {ok} of {n} reviewers said ok")
    return (not reasons), reasons


def record(workspace: Path, kind: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Write the result as a converge record and satisfy the gate when the
    verdicts prove convergence. Returns a summary dict; ``satisfied`` is False
    with ``reasons`` when the gate stays open."""
    workspace = Path(workspace)
    registry = _registry_path(workspace)
    entries = _read_registry(registry)
    gid = gate_id_for(kind)
    entry = next((e for e in entries if isinstance(e, dict) and e.get("gate_id") == gid), None)
    expected = entry.get("reviewers") if isinstance(entry, dict) else None
    converged, reasons = evaluate(result, expected if isinstance(expected, int) else None)
    stamp = _utc_now_iso().replace(":", "").replace("-", "")
    out_dir = workspace / RECORDS_RELATIVE
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{kind}-{stamp}.json"
    k = 2
    while out.exists():
        out = out_dir / f"{kind}-{stamp}-{k}.json"
        k += 1
    payload = {
        "schema": SCHEMA,
        "kind": kind,
        "gate_id": gid,
        "recorded_at": _utc_now_iso(),
        "converged": converged,
        "reasons": reasons,
        "result": result,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    summary: Dict[str, Any] = {
        "gate_id": gid, "record_path": str(out), "converged": converged,
        "reasons": reasons, "declared": entry is not None, "satisfied": False,
    }
    if entry is None:
        summary["reasons"] = reasons + [f"gate {gid} was never declared; declare it before the loop"]
        return summary
    if not converged:
        return summary
    entry["satisfied_at"] = _utc_now_iso()
    entry["evidence_path"] = str(out)
    _write_registry(registry, entries)
    summary["satisfied"] = True
    return summary


def status(workspace: Path) -> List[Dict[str, Any]]:
    entries = _read_registry(_registry_path(workspace))
    out = []
    for e in entries:
        if isinstance(e, dict) and str(e.get("gate_id", "")).startswith(GATE_PREFIX):
            out.append({
                "gate_id": e.get("gate_id"), "kind": e.get("kind"), "reviewers": e.get("reviewers"),
                "declared_at": e.get("declared_at"), "satisfied_at": e.get("satisfied_at"),
                "evidence_path": e.get("evidence_path"),
                "satisfied": bool(e.get("satisfied_at")) and bool(e.get("evidence_path")),
            })
    return out


def _load_result(args: argparse.Namespace) -> Dict[str, Any]:
    if args.result_file:
        return json.loads(Path(args.result_file).read_text(encoding="utf-8"))
    if args.result:
        return json.loads(args.result)
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Converge-gate records: declare before the ct6-converge loop, record after it.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("declare", help="Declare the convergence gate for <kind> in the declared-gates registry.")
    d.add_argument("--workspace", required=True)
    d.add_argument("--kind", required=True)
    d.add_argument("--promise", required=True, help="The gate's label, e.g. 'CODEBASE MAP COMPLETE'.")
    d.add_argument("--reviewers", type=int, required=True)
    d.add_argument("--artifact", action="append", default=[], help="Repo-relative artifact the reviewers audit (repeatable).")
    r = sub.add_parser("record", help="Record the workflow's result; satisfies the gate only when the verdicts prove convergence.")
    r.add_argument("--workspace", required=True)
    r.add_argument("--kind", required=True)
    r.add_argument("--result", help="The JSON the workflow returned.")
    r.add_argument("--result-file", help="Path to a file holding that JSON (or pipe it on stdin).")
    s = sub.add_parser("status", help="List the converge gates and whether each is satisfied.")
    s.add_argument("--workspace", required=True)
    for sp in (d, r, s):
        sp.add_argument("--json", action="store_true", help="Emit JSON instead of a sentence.")
    args = parser.parse_args(argv)

    if args.cmd == "declare":
        gid, appended = declare(Path(args.workspace), args.kind, args.promise, args.reviewers, args.artifact or None)
        print(json.dumps({"gate_id": gid, "appended": appended}) if args.json else
              f"declared {gid}" if appended else f"{gid} already declared")
        return 0
    if args.cmd == "record":
        try:
            result = _load_result(args)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"record: could not read the result JSON: {exc}", file=sys.stderr)
            return 2
        summary = record(Path(args.workspace), args.kind, result)
        print(json.dumps(summary, indent=2) if args.json else
              (f"satisfied {summary['gate_id']} with {summary['record_path']}" if summary["satisfied"] else
               f"gate {summary['gate_id']} stays OPEN: " + "; ".join(summary["reasons"]) + f" (record {summary['record_path']})"))
        return 0 if summary["satisfied"] else 1
    if args.cmd == "status":
        rows = status(Path(args.workspace))
        print(json.dumps(rows, indent=2) if args.json else
              ("\n".join(f"{row['gate_id']}: {'satisfied' if row['satisfied'] else 'OPEN'}" for row in rows) or "(no converge gates declared)"))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
