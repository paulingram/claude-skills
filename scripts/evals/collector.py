# -*- coding: utf-8 -*-
"""Per-run eval result collection + run-to-run comparison.

Stdlib-only, ASCII-safe, NO import-time side effects.

A "run" is one execution of the eval tier - a set of named evals, each with a
verdict and resource metrics (turns, tool calls, cost, duration). Results are
written as one JSON file per run under
``<workspace>/.architect-team/eval-runs/<UTC-ts>.json`` so consecutive runs can
be diffed for behavioral drift and budget regressions.

Filenames are UTC timestamps with a compact, colon-free, lexicographically
sortable shape, so "the previous run" is just the next filename down the sorted
list.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Metric keys carried per eval; the source of truth for what a run records.
_METRIC_KEYS = ("turns", "tool_calls", "cost_usd", "duration_s")


def sum_costs(*values: Any) -> float:
    """None-safe sum of cost/metric values.

    A ``Transcript`` can carry ``cost_usd``/``num_turns`` present-with-``None``
    (a run that timed out or produced no terminal ``result`` event). A plain
    ``metric or default`` guard is not enough when the value comes from a dict
    whose key EXISTS with a ``None`` value (``d.get(key, 0.0)`` returns the
    ``None``, not the default). This helper coalesces every ``None`` or
    non-numeric input to 0 so a missing cost never turns a clean verdict into a
    ``TypeError``. Used wherever eval costs aggregate across transcripts.
    """
    total = 0.0
    for value in values:
        try:
            total += float(value)
        except (TypeError, ValueError):
            continue
    return total


def eval_runs_dir(workspace: Any) -> Path:
    """Return (without creating) the eval-runs directory for ``workspace``."""
    return Path(workspace) / ".architect-team" / "eval-runs"


def utc_stamp(now: Optional[datetime] = None) -> str:
    """A filesystem-safe, sortable UTC timestamp (no colons)."""
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def _normalise_eval(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce one eval record to the canonical {name, verdict, metrics} shape."""
    out: Dict[str, Any] = {
        "name": str(entry.get("name", "")),
        "verdict": str(entry.get("verdict", "unknown")),
    }
    for key in _METRIC_KEYS:
        value = entry.get(key)
        if value is None:
            out[key] = None
            continue
        try:
            out[key] = int(value) if key in ("turns", "tool_calls") else float(value)
        except (TypeError, ValueError):
            out[key] = None
    return out


def build_run(evals: Sequence[Dict[str, Any]], *, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Assemble a run record (evals + totals) from per-eval entries."""
    normalised = [_normalise_eval(e) for e in evals]
    passed = sum(1 for e in normalised if e["verdict"] == "pass")
    failed = sum(1 for e in normalised if e["verdict"] == "fail")
    total_cost = sum(e["cost_usd"] or 0.0 for e in normalised)
    total_tools = sum(e["tool_calls"] or 0 for e in normalised)
    total_turns = sum(e["turns"] or 0 for e in normalised)
    return {
        "timestamp": timestamp or utc_stamp(),
        "evals": normalised,
        "totals": {
            "n_evals": len(normalised),
            "passed": passed,
            "failed": failed,
            "total_cost_usd": round(total_cost, 6),
            "total_tool_calls": total_tools,
            "total_turns": total_turns,
        },
    }


def write_run(
    evals: Sequence[Dict[str, Any]],
    workspace: Any,
    *,
    timestamp: Optional[str] = None,
) -> Path:
    """Write a run record to ``<workspace>/.architect-team/eval-runs/<ts>.json``.

    Returns the path written. Creates the directory tree as needed.
    """
    run = build_run(evals, timestamp=timestamp)
    out_dir = eval_runs_dir(workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run['timestamp']}.json"
    path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_run(path: Any) -> Dict[str, Any]:
    """Load a run record from ``path``."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def list_runs(workspace: Any) -> List[Path]:
    """All run files under the eval-runs dir, oldest-first by filename."""
    out_dir = eval_runs_dir(workspace)
    if not out_dir.is_dir():
        return []
    return sorted(p for p in out_dir.glob("*.json") if p.is_file())


def find_previous_run(workspace: Any, current: Any = None) -> Optional[Path]:
    """Return the newest run file that is not ``current``.

    With ``current`` set to the just-written run, this yields the run before
    it. With ``current`` unset, it yields the newest run overall (useful for
    "compare a fresh in-memory run against the last persisted one").
    """
    runs = list_runs(workspace)
    if not runs:
        return None
    current_path = Path(current).resolve() if current is not None else None
    for path in reversed(runs):
        if current_path is not None and path.resolve() == current_path:
            continue
        return path
    return None


def _index_by_name(run: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {e.get("name", ""): e for e in run.get("evals", []) if isinstance(e, dict)}


def compare(current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    """Per-eval deltas between two run records.

    For every eval present in BOTH runs, report the prior/now/delta of each
    metric plus any verdict change. Evals present in only one run are listed
    under ``added`` / ``removed``.
    """
    cur = _index_by_name(current)
    prev = _index_by_name(previous)
    per_eval: Dict[str, Any] = {}
    for name in sorted(set(cur) & set(prev)):
        c, p = cur[name], prev[name]
        metrics: Dict[str, Any] = {}
        for key in _METRIC_KEYS:
            now = c.get(key)
            prior = p.get(key)
            delta: Optional[float] = None
            if isinstance(now, (int, float)) and isinstance(prior, (int, float)):
                delta = now - prior
            metrics[key] = {"prior": prior, "now": now, "delta": delta}
        per_eval[name] = {
            "verdict": {"prior": p.get("verdict"), "now": c.get("verdict")},
            "metrics": metrics,
        }
    return {
        "per_eval": per_eval,
        "added": sorted(set(cur) - set(prev)),
        "removed": sorted(set(prev) - set(cur)),
    }
