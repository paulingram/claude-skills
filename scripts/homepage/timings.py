# -*- coding: utf-8 -*-
"""Timing-log statistics and estimates -- the numbers behind "how long will it
take?" and the homepage's Performance panel.

Reads the ledger `hooks/timings_log.py` writes
(``<workspace>/.architect-team/run-history/timings.jsonl``; one closed
interval per line, schema ``timing/v1``) and answers two questions:

* ``stats(records, group_by=("lane", "phase", "agent"))`` -- per group:
  sample count, median, p90, mean, and a trend (the last 5 runs against the
  runs before them).
* ``estimate(records, lane=..., phase=..., agent=..., size_bucket=..., min_n=5)``
  -- the same numbers for one question. Below ``min_n`` samples the answer is
  ``"no basis yet"``; every answer carries ``"note": "history, not a promise"``.

Rules the numbers follow:

* A heartbeat line (``outcome: "heartbeat"``) is a liveness point, not an
  interval -- excluded. A line without a numeric ``duration_s`` is excluded.
* Percentiles use the nearest-rank method (deterministic, no interpolation).
* The trend compares the median of the most recent 5 distinct ``run_id``s
  with the median of every earlier run; fewer than one run on either side is
  ``"insufficient"``, never a fabricated direction.
* ``--also-user-level`` merges ``~/.architect-team/timings.jsonl`` (the mirror
  `hooks/timings_log.py` writes under ``CT6_TIMINGS_USER_MIRROR=1``;
  ``CT6_TIMINGS_USER_MIRROR_PATH`` overrides the location), de-duplicated by
  content so a project line mirrored to the user log counts once.

CLI::

    python scripts/homepage/timings.py stats    --workspace W [--group-by lane,phase] \\
        [--also-user-level] [--json]
    python scripts/homepage/timings.py estimate --workspace W [--lane L] [--phase P] \\
        [--agent A] [--size S] [--kind K] [--min-n 5] [--also-user-level] [--json]

Exit codes: 0 ok (including "no basis yet" -- a refusal is a correct answer),
2 usage error.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA = "timing/v1"
STATS_SCHEMA = "timing-stats/v1"
ESTIMATE_SCHEMA = "timing-estimate/v1"
TIMINGS_RELATIVE_PATH = ".architect-team/run-history/timings.jsonl"
USER_MIRROR_PATH_ENV = "CT6_TIMINGS_USER_MIRROR_PATH"

OUTCOME_HEARTBEAT = "heartbeat"
DEFAULT_GROUP_BY: Tuple[str, ...] = ("lane", "phase", "agent")
DEFAULT_MIN_N = 5
RECENT_RUNS = 5
#: A trend direction needs at least this much relative movement to be called.
TREND_THRESHOLD_PCT = 10.0

NO_BASIS = "no basis yet"
NOTE = "history, not a promise"


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #

def timings_path(workspace: Any) -> Path:
    return Path(workspace) / TIMINGS_RELATIVE_PATH


def user_mirror_path() -> Path:
    override = os.environ.get(USER_MIRROR_PATH_ENV, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".architect-team" / "timings.jsonl"


def read_jsonl(path: Any) -> List[Dict[str, Any]]:
    """Tolerant JSONL reader: missing file -> []; bad lines skipped."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _dedupe(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for rec in records:
        key = json.dumps(rec, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def load_records(workspace: Any, also_user_level: bool = False,
                 user_path: Any = None) -> List[Dict[str, Any]]:
    """The workspace ledger, optionally merged with the user-level mirror."""
    records = read_jsonl(timings_path(workspace))
    if also_user_level:
        records = records + read_jsonl(user_path if user_path is not None else user_mirror_path())
    return _dedupe(records)


# --------------------------------------------------------------------------- #
# arithmetic
# --------------------------------------------------------------------------- #

def _duration(rec: Dict[str, Any]) -> Optional[float]:
    if rec.get("outcome") == OUTCOME_HEARTBEAT:
        return None
    value = rec.get("duration_s")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if math.isnan(value) or value < 0:
        return None
    return float(value)


def usable(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Records that carry a usable duration (heartbeats and null durations out)."""
    return [r for r in records if _duration(r) is not None]


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile; None on an empty input."""
    if not values:
        return None
    ordered = sorted(values)
    rank = int(math.ceil((pct / 100.0) * len(ordered)))
    rank = min(max(rank, 1), len(ordered))
    return float(ordered[rank - 1])


def median(values: Sequence[float]) -> Optional[float]:
    """The conventional median (mean of the two middle values when even)."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 1)


def summarize(values: Sequence[float]) -> Dict[str, Any]:
    vals = list(values)
    return {
        "n": len(vals),
        "median_s": _round(median(vals)),
        "p90_s": _round(percentile(vals, 90)),
        "mean_s": _round(sum(vals) / len(vals)) if vals else None,
        "min_s": _round(min(vals)) if vals else None,
        "max_s": _round(max(vals)) if vals else None,
    }


def _run_order(records: Iterable[Dict[str, Any]]) -> List[str]:
    """Distinct run ids ordered by their earliest started_at (then id)."""
    first_seen: Dict[str, str] = {}
    for rec in records:
        run_id = rec.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        started = rec.get("started_at") if isinstance(rec.get("started_at"), str) else ""
        if run_id not in first_seen or (started and started < first_seen[run_id]):
            first_seen[run_id] = started
    return [rid for rid, _ in sorted(first_seen.items(), key=lambda kv: (kv[1], kv[0]))]


def trend(records: Iterable[Dict[str, Any]], recent_runs: int = RECENT_RUNS) -> Dict[str, Any]:
    """The last ``recent_runs`` distinct runs against every earlier run."""
    recs = usable(records)
    order = _run_order(recs)
    recent_ids = set(order[-recent_runs:]) if order else set()
    prior_ids = set(order[:-recent_runs]) if len(order) > recent_runs else set()
    recent = [_duration(r) for r in recs if r.get("run_id") in recent_ids]
    prior = [_duration(r) for r in recs if r.get("run_id") in prior_ids]
    recent_med = median([v for v in recent if v is not None])
    prior_med = median([v for v in prior if v is not None])
    out: Dict[str, Any] = {
        "recent_runs": len(recent_ids),
        "prior_runs": len(prior_ids),
        "recent_median_s": _round(recent_med),
        "prior_median_s": _round(prior_med),
        "delta_pct": None,
        "direction": "insufficient",
    }
    if recent_med is None or prior_med is None or prior_med <= 0:
        return out
    delta = (recent_med - prior_med) / prior_med * 100.0
    out["delta_pct"] = round(delta, 1)
    if delta <= -TREND_THRESHOLD_PCT:
        out["direction"] = "faster"
    elif delta >= TREND_THRESHOLD_PCT:
        out["direction"] = "slower"
    else:
        out["direction"] = "flat"
    return out


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #

def stats(records: Iterable[Dict[str, Any]],
          group_by: Sequence[str] = DEFAULT_GROUP_BY) -> Dict[str, Any]:
    """Per-(kind, *group_by) sample count / median / p90 / mean / trend, plus
    overall and per-kind summaries."""
    all_records = list(records)
    recs = usable(all_records)
    fields = tuple(group_by)
    groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for rec in recs:
        key = (rec.get("kind"),) + tuple(rec.get(f) for f in fields)
        groups.setdefault(key, []).append(rec)
    rendered: List[Dict[str, Any]] = []
    for key in sorted(groups.keys(), key=lambda k: tuple(str(x) for x in k)):
        members = groups[key]
        values = [_duration(r) for r in members]
        entry = {"kind": key[0], "key": {f: key[i + 1] for i, f in enumerate(fields)}}
        entry.update(summarize([v for v in values if v is not None]))
        entry["trend"] = trend(members)
        rendered.append(entry)
    by_kind: Dict[str, Any] = {}
    for rec in recs:
        by_kind.setdefault(str(rec.get("kind")), []).append(_duration(rec))
    return {
        "schema": STATS_SCHEMA,
        "group_by": list(fields),
        "n_records": len(all_records),
        "n_usable": len(recs),
        "n_runs": len(_run_order(recs)),
        "overall": dict(summarize([v for v in (_duration(r) for r in recs) if v is not None]),
                        trend=trend(recs)),
        "by_kind": {k: summarize([v for v in vs if v is not None])
                    for k, vs in sorted(by_kind.items())},
        "groups": rendered,
        "note": NOTE,
    }


# --------------------------------------------------------------------------- #
# estimate
# --------------------------------------------------------------------------- #

def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _match(rec_value: Any, wanted: Optional[str]) -> bool:
    if wanted is None:
        return True
    return isinstance(rec_value, str) and rec_value.strip().lower() == wanted.strip().lower()


def estimate(records: Iterable[Dict[str, Any]], lane: Optional[str] = None,
             phase: Optional[str] = None, agent: Optional[str] = None,
             size_bucket: Optional[str] = None, min_n: int = DEFAULT_MIN_N,
             kind: Optional[str] = None) -> Dict[str, Any]:
    """The estimate for one question. ``kind`` defaults to ``agent`` when an
    agent is named, ``phase`` when a phase is named, else ``run``."""
    if kind is None:
        kind = "agent" if agent else ("phase" if phase else "run")
    hits = [r for r in usable(records)
            if r.get("kind") == kind and _match(r.get("lane"), lane)
            and _match(r.get("phase"), phase) and _match(r.get("agent"), agent)
            and _match(r.get("size_bucket"), size_bucket)]
    values = [v for v in (_duration(r) for r in hits) if v is not None]
    n = len(values)
    out: Dict[str, Any] = {
        "schema": ESTIMATE_SCHEMA,
        "kind": kind,
        "filters": {"lane": lane, "phase": phase, "agent": agent, "size_bucket": size_bucket},
        "min_n": int(min_n),
        "basis_n": n,
        "basis_runs": len(_run_order(hits)),
        "median_s": None,
        "p90_s": None,
        "mean_s": None,
        "answer": NO_BASIS,
        "note": NOTE,
    }
    if n < int(min_n):
        out["answer"] = NO_BASIS
        out["reason"] = (f"{n} recorded {kind} interval(s) match; at least {int(min_n)} are "
                         f"needed before a number is offered")
        return out
    summary = summarize(values)
    out.update({"median_s": summary["median_s"], "p90_s": summary["p90_s"],
                "mean_s": summary["mean_s"]})
    out["answer"] = (f"about {format_duration(summary['median_s'])} (median), up to "
                     f"{format_duration(summary['p90_s'])} (p90), from {n} recorded "
                     f"{kind} interval(s) across {out['basis_runs']} run(s)")
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:  # pragma: no cover - console codec fallback
        print(text.encode("ascii", "replace").decode("ascii"))


def _render_stats(result: Dict[str, Any]) -> str:
    lines = [f"timing stats: {result['n_usable']} usable interval(s) of {result['n_records']} "
             f"line(s), {result['n_runs']} run(s); grouped by {', '.join(result['group_by'])}"]
    header = ("kind", *result["group_by"], "n", "median", "p90", "mean", "trend")
    lines.append(" | ".join(header))
    for g in result["groups"]:
        key = [str(g["key"].get(f) or "-") for f in result["group_by"]]
        tr = g["trend"]
        tr_text = tr["direction"] if tr["delta_pct"] is None else f"{tr['direction']} ({tr['delta_pct']:+.1f}%)"
        lines.append(" | ".join([str(g["kind"]), *key, str(g["n"]), format_duration(g["median_s"]),
                                 format_duration(g["p90_s"]), format_duration(g["mean_s"]), tr_text]))
    if not result["groups"]:
        lines.append("(no usable intervals recorded yet)")
    lines.append(result["note"])
    return "\n".join(lines)


def _render_estimate(result: Dict[str, Any]) -> str:
    filters = ", ".join(f"{k}={v}" for k, v in result["filters"].items() if v)
    lines = [f"estimate ({result['kind']}{'; ' + filters if filters else ''}): {result['answer']}",
             f"basis: {result['basis_n']} sample(s), minimum {result['min_n']}"]
    if result.get("reason"):
        lines.append(result["reason"])
    lines.append(result["note"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timings.py",
                                     description="Timing-log statistics and estimates.")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("stats")
    st.add_argument("--workspace", required=True)
    st.add_argument("--group-by", default=",".join(DEFAULT_GROUP_BY),
                    help="comma-separated record fields (default lane,phase,agent)")
    st.add_argument("--also-user-level", action="store_true")
    st.add_argument("--user-path", help=argparse.SUPPRESS)
    st.add_argument("--json", action="store_true")
    es = sub.add_parser("estimate")
    es.add_argument("--workspace", required=True)
    es.add_argument("--lane")
    es.add_argument("--phase")
    es.add_argument("--agent")
    es.add_argument("--size", dest="size_bucket")
    es.add_argument("--kind", choices=("agent", "task", "phase", "run"))
    es.add_argument("--min-n", dest="min_n", type=int, default=DEFAULT_MIN_N)
    es.add_argument("--also-user-level", action="store_true")
    es.add_argument("--user-path", help=argparse.SUPPRESS)
    es.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    records = load_records(args.workspace, also_user_level=args.also_user_level,
                           user_path=args.user_path)
    if args.command == "stats":
        fields = tuple(f.strip() for f in args.group_by.split(",") if f.strip()) or DEFAULT_GROUP_BY
        result = stats(records, group_by=fields)
        _safe_print(json.dumps(result, sort_keys=True, indent=2) if args.json else _render_stats(result))
        return 0
    result = estimate(records, lane=args.lane, phase=args.phase, agent=args.agent,
                      size_bucket=args.size_bucket, min_n=args.min_n, kind=args.kind)
    _safe_print(json.dumps(result, sort_keys=True, indent=2) if args.json else _render_estimate(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
