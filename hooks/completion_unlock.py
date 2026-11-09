"""Release a completion hold on the USER's explicit word (v4.1.0).

Why this exists. Two field reports. (1) The completion lock, the continuation
guard and the declared-gates arm kept refusing a stop long after the work was
genuinely done -- a harness task nobody closed, an ask-ledger entry the
transcript never resolved, a `converge:<kind>` gate whose record was never
written -- and the agent had no sanctioned way to clear state it was not the
author of. (2) The user had said "that's good enough, move on with what you
have", which is exactly the human decision the gates exist to wait for, and
nothing turned those words into released state.

What this is. ONE verb, ``release``, that closes every source the Stop hook
reads, under a durable record of the user's words:

* harness tasks still open for the session are RETIRED through
  ``open_work.py``'s operator verb (``--force``: the human said the list is
  done), so the store stays registered and every task carries the reason;
* open ask-ledger entries are RESOLVED with the release record as evidence;
* declared gates (including ``converge:<kind>``) that were never satisfied are
  WAIVED -- ``waived_at`` / ``waived_by: user`` / ``evidence_path`` -> the
  release record -- never faked as satisfied; the Stop arm accepts a waiver
  only when its evidence is a real release record;
* the active run marker is STOOD DOWN (``run_continuity.stand_down`` writes
  ``pipeline-stand-down.md`` with the user's words) and the guard state cleared;
* one line goes to the decisions ledger, so the homepage shows that the hold
  was released, by whom, and why.

What this is NOT. It is not a kill-switch and not an exit an agent may reach
for. The ``release`` verb is sanctioned ONLY inside the user's own
``/architect-team:unlock`` command turn: the PreToolUse gate (Arm 5 of
``hooks/pretool_skill_gate.py``) refuses the verb unless the latest genuine
user prompt carries that command marker, the command itself is
``disable-model-invocation: true`` so the model cannot invoke it, and no Stop
hold text names it. ``inspect`` and ``status`` are read-only and always
allowed -- an agent may always SHOW the user what holds the turn.

HONEST BOUNDARY. Bash can reach this module in forms the arm's command-text
match does not see, and a hand-written release record is indistinguishable
from a real one on disk: the same NAMED residual every filesystem gate in this
repo carries. The record, the decisions-ledger line and the stand-down
artifact make a misuse a deliberate act on a named surface, visible after the
fact; they do not make it impossible. Stdlib-only; no import-time side
effects.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - exercised by both import paths
    from hooks import open_work as _ow
    from hooks import run_continuity as _rc
    from hooks import decisions_ledger as _dl
    from hooks.shared_util import _utc_now_iso
except ImportError:  # pragma: no cover - bare-module fallback
    import open_work as _ow  # type: ignore[no-redef]
    import run_continuity as _rc  # type: ignore[no-redef]
    import decisions_ledger as _dl  # type: ignore[no-redef]
    from shared_util import _utc_now_iso  # type: ignore[no-redef]

SCHEMA = "ct6-unlock/v1"
COMMAND = "/architect-team:unlock"
STATE_DIRNAME = ".architect-team"
RELEASES_DIRNAME = "releases"
DECLARED_GATES_FILENAME = "declared-gates.json"
WAIVED_BY_USER = "user"
SCOPES = ("tasks", "asks", "gates", "run")


def _at(root: Path) -> Path:
    return Path(root) / STATE_DIRNAME


def releases_dir(root: Path) -> Path:
    return _at(root) / RELEASES_DIRNAME


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


# --- what holds the turn ------------------------------------------------------

def _gate_state(entry: Dict[str, Any]) -> str:
    if isinstance(entry.get("satisfied_at"), str) and entry.get("satisfied_at").strip() \
            and isinstance(entry.get("evidence_path"), str) and entry.get("evidence_path").strip():
        return "satisfied"
    if isinstance(entry.get("waived_at"), str) and entry.get("waived_at").strip():
        return "waived"
    return "open"


def _read_gates(root: Path) -> Optional[List[Any]]:
    path = _at(root) / DECLARED_GATES_FILENAME
    if not path.exists():
        return []
    data = _read_json(path)
    return data if isinstance(data, list) else None


def resolve_session(root: Path, explicit: Optional[str], tasks_root: Optional[str]) -> Dict[str, Any]:
    """Which harness task list the hold reads. Precedence: the explicit flag,
    the active run marker's recorded session, the environment, then -- when the
    task root holds exactly one session dir with open work -- that one."""
    if isinstance(explicit, str) and explicit.strip():
        return {"session_id": explicit.strip(), "source": "flag"}
    marker = _rc.read_marker(root)
    if isinstance(marker, dict) and isinstance(marker.get("session_id"), str) and marker["session_id"].strip():
        return {"session_id": marker["session_id"].strip(), "source": "run-marker"}
    env = _rc.resolve_session_id(None)
    if env:
        return {"session_id": env, "source": "environment"}
    try:
        troot = _ow.tasks_root(tasks_root)
        candidates = []
        if troot.is_dir():
            for d in sorted(p for p in troot.iterdir() if p.is_dir()):
                sid = d.name[len("session-"):] if d.name.startswith("session-") else d.name
                read = _ow.read_harness_tasks(sid, tasks_root)
                if _ow.open_task_items(read.get("items") or []):
                    candidates.append(sid)
        if len(candidates) == 1:
            return {"session_id": candidates[0], "source": "only-session-with-open-work"}
        return {"session_id": None, "source": "unresolved", "candidates": candidates}
    except Exception as exc:  # the store is not this module's to crash on
        return {"session_id": None, "source": "unresolved", "error": str(exc)}


def inspect_holds(root: Path, session_id: Optional[str] = None,
                  tasks_root: Optional[str] = None) -> Dict[str, Any]:
    """Read-only: everything on disk the Stop hook would hold the turn on."""
    root = Path(root)
    at = _at(root)
    session = resolve_session(root, session_id, tasks_root)
    sid = session.get("session_id")

    tasks: Dict[str, Any] = {"live": [], "stale": [], "dir": None, "unavailable": None, "unreadable": []}
    if sid:
        read = _ow.read_harness_tasks(sid, tasks_root)
        tasks["dir"] = read.get("dir")
        tasks["unavailable"] = read.get("unavailable")
        tasks["unreadable"] = [e.get("path") for e in (read.get("unreadable") or [])]
        live, stale = _ow.partition_stale_tasks(_ow.open_task_items(read.get("items") or []))
        tasks["live"] = [{"id": str(t.get("id")), "subject": t.get("subject"), "status": t.get("status")} for t in live]
        tasks["stale"] = [{"id": str(t.get("id")), "subject": t.get("subject"), "status": t.get("status")} for t in stale]

    try:
        asks = [{"id": e.get("id"), "text": e.get("text")} for e in _ow.open_ledger_entries(root)]
        asks_unreadable = None
    except Exception as exc:
        asks, asks_unreadable = [], str(exc)

    gates_raw = _read_gates(root)
    gates: Dict[str, Any] = {"open": [], "waived": [], "satisfied": [], "unreadable": gates_raw is None}
    for e in gates_raw or []:
        if isinstance(e, dict):
            gates[_gate_state(e)].append(str(e.get("gate_id") or "?"))

    marker = _rc.read_marker(root)
    run = None
    if isinstance(marker, dict):
        run = {k: marker.get(k) for k in ("status", "skill", "slug", "phase", "session_id", "updated_at")}
        run["stale"] = bool(_rc.marker_is_stale(marker)) if marker.get("status") == "active" else None

    releases = sorted(p.name for p in releases_dir(root).glob("unlock-*.json")) if releases_dir(root).is_dir() else []
    holds = []
    if tasks["live"]:
        holds.append(f"{len(tasks['live'])} live open task(s)")
    if tasks["unreadable"]:
        holds.append(f"{len(tasks['unreadable'])} unreadable task file(s)")
    if asks:
        holds.append(f"{len(asks)} unresolved ask(s)")
    if gates["open"]:
        holds.append(f"{len(gates['open'])} open declared gate(s)")
    if gates["unreadable"]:
        holds.append("an unreadable declared-gates ledger")
    if run and run.get("status") == "active" and not run.get("stale"):
        holds.append("an active run marker")
    return {
        "root": str(root), "session": session, "tasks": tasks, "asks": asks,
        "asks_unreadable": asks_unreadable, "gates": gates, "run": run,
        "markers": {
            "escalation_pending": (at / "escalation-pending.md").exists(),
            "in_progress": (at / "in-progress.md").exists(),
        },
        "releases": releases, "holds": holds, "held": bool(holds),
    }


# --- the release --------------------------------------------------------------

def _waive_gates(root: Path, reason: str, evidence_rel: str) -> Dict[str, Any]:
    path = _at(root) / DECLARED_GATES_FILENAME
    entries = _read_gates(root)
    if entries is None:
        return {"waived": [], "error": f"{DECLARED_GATES_FILENAME} is unreadable; repair it by hand"}
    waived = []
    now = _utc_now_iso()
    for e in entries:
        if isinstance(e, dict) and _gate_state(e) == "open":
            e["waived_at"] = now
            e["waived_by"] = WAIVED_BY_USER
            e["waiver_reason"] = reason
            e["evidence_path"] = evidence_rel
            waived.append(str(e.get("gate_id") or "?"))
    if waived:
        _write_json(path, entries)
    return {"waived": waived}


def _resolve_asks(root: Path, evidence_rel: str) -> Dict[str, Any]:
    try:
        ids = [e.get("id") for e in _ow.open_ledger_entries(root)]
        for i in ids:
            _ow.resolve_ledger_entry(root, str(i), f"released by the user: {evidence_rel}")
        return {"resolved": [str(i) for i in ids]}
    except Exception as exc:
        return {"resolved": [], "error": str(exc)}


def _retire_tasks(sid: Optional[str], reason: str, tasks_root: Optional[str]) -> Dict[str, Any]:
    if not sid:
        return {"retired": [], "skipped": "no session id could be resolved; pass --session-id"}
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        code = _ow._cmd_retire(sid, reason, [], tasks_root, force=True)
    try:
        parsed = json.loads(buf_out.getvalue() or "null")
    except json.JSONDecodeError:
        parsed = None
    out = {"retired": [], "exit": code}
    if isinstance(parsed, dict):
        out.update({k: parsed.get(k) for k in ("store", "retired", "write_failed", "unreadable") if k in parsed})
    note = buf_err.getvalue().strip()
    if note:
        out["note"] = note
    return out


def _stand_down(root: Path, reason: str) -> Dict[str, Any]:
    marker = _rc.read_marker(root)
    if not (isinstance(marker, dict) and marker.get("status") == "active"):
        _rc.clear_guard_state(root)
        return {"stood_down": False, "why": "no active run marker"}
    _rc.stand_down(root, f"{COMMAND}: {reason}")
    _rc.clear_guard_state(root)
    return {"stood_down": True, "slug": marker.get("slug"), "phase": marker.get("phase")}


def release(root: Path, reason: str, session_id: Optional[str] = None,
            tasks_root: Optional[str] = None, scope: Optional[List[str]] = None,
            dry_run: bool = False) -> Dict[str, Any]:
    """Close every hold in ``scope`` (default: all) under one release record.
    Raises ``ValueError`` on a blank reason: the record IS the user's words."""
    root = Path(root)
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("a release needs the user's own words as --reason")
    scope = [s for s in (scope or list(SCOPES)) if s in SCOPES] or list(SCOPES)
    before = inspect_holds(root, session_id, tasks_root)
    sid = before["session"].get("session_id")
    stamp = _utc_now_iso().replace(":", "").replace("-", "")
    out_dir = releases_dir(root)
    record_path = out_dir / f"unlock-{stamp}.json"
    k = 2
    while record_path.exists():
        record_path = out_dir / f"unlock-{stamp}-{k}.json"
        k += 1
    record: Dict[str, Any] = {
        "schema": SCHEMA, "command": COMMAND, "at": _utc_now_iso(), "reason": reason,
        "session_id": sid, "session_source": before["session"].get("source"), "scope": scope,
        "authorized_by": "the user's explicit command; no agent decision",
        "before": {"holds": before["holds"], "tasks_live": before["tasks"]["live"],
                   "asks": before["asks"], "gates_open": before["gates"]["open"], "run": before["run"]},
        "actions": {}, "dry_run": dry_run,
    }
    if dry_run:
        return {"record_path": None, "would_release": before["holds"], "scope": scope, "record": record}
    # The record first: the waivers and the resolved asks cite it as evidence,
    # and the Stop arm checks that the cited file exists before it honours them.
    _write_json(record_path, record)
    rel = _rel(root, record_path)
    actions: Dict[str, Any] = {}
    if "gates" in scope:
        actions["gates"] = _waive_gates(root, reason, rel)
    if "asks" in scope:
        actions["asks"] = _resolve_asks(root, rel)
    if "tasks" in scope:
        actions["tasks"] = _retire_tasks(sid, f"{COMMAND}: {reason}", tasks_root)
    if "run" in scope:
        actions["run"] = _stand_down(root, reason)
    try:
        _dl.append(root, kind="other", summary=f"The user released the completion hold: {reason}",
                   chosen=COMMAND, refs=[rel])
        actions["decision_recorded"] = True
    except Exception as exc:
        actions["decision_recorded"] = False
        actions["decision_error"] = str(exc)
    record["actions"] = actions
    after = inspect_holds(root, sid, tasks_root)
    record["after"] = {"holds": after["holds"]}
    _write_json(record_path, record)
    problems = [a.get("error") or a.get("skipped") for a in actions.values() if isinstance(a, dict) and (a.get("error") or a.get("skipped"))]
    return {"record_path": str(record_path), "released": before["holds"], "remaining": after["holds"],
            "actions": actions, "problems": problems, "scope": scope}


def status(root: Path) -> List[Dict[str, Any]]:
    rows = []
    d = releases_dir(Path(root))
    if not d.is_dir():
        return rows
    for p in sorted(d.glob("unlock-*.json")):
        data = _read_json(p)
        if isinstance(data, dict):
            rows.append({"path": str(p), "at": data.get("at"), "reason": data.get("reason"),
                         "released": (data.get("before") or {}).get("holds"),
                         "remaining": (data.get("after") or {}).get("holds")})
        else:
            rows.append({"path": str(p), "unreadable": True})
    return rows


# --- CLI -----------------------------------------------------------------------

def _render_inspect(rep: Dict[str, Any]) -> str:
    lines = [f"held: {'yes' if rep['held'] else 'no'}" + (" -- " + "; ".join(rep["holds"]) if rep["holds"] else "")]
    s = rep["session"]
    lines.append(f"session: {s.get('session_id') or '(unresolved)'} ({s.get('source')})")
    for t in rep["tasks"]["live"]:
        lines.append(f"  task [{t['id']}] {t.get('status')}: {t.get('subject')}")
    for t in rep["tasks"]["stale"]:
        lines.append(f"  stale task [{t['id']}] (inherited debt, not blocking): {t.get('subject')}")
    for a in rep["asks"]:
        lines.append(f"  ask [{a.get('id')}]: {a.get('text')}")
    for g in rep["gates"]["open"]:
        lines.append(f"  open gate: {g}")
    for g in rep["gates"]["waived"]:
        lines.append(f"  waived gate: {g}")
    if rep["run"]:
        r = rep["run"]
        lines.append(f"  run marker: {r.get('status')} {r.get('slug') or ''} {r.get('phase') or ''}".rstrip()
                     + (" (stale)" if r.get("stale") else ""))
    if rep["releases"]:
        lines.append(f"  prior releases: {', '.join(rep['releases'])}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Release a completion hold on the user's explicit word (the /architect-team:unlock command).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect", help="Read-only: what holds the turn right now.")
    r = sub.add_parser("release", help="Close every hold under a release record of the user's words. "
                                       "Sanctioned ONLY inside the user's /architect-team:unlock command turn.")
    r.add_argument("--reason", required=True, help="The user's own words, verbatim.")
    r.add_argument("--scope", action="append", choices=SCOPES, default=None,
                   help="Limit the release (repeatable). Default: every scope.")
    r.add_argument("--dry-run", action="store_true", help="Report what would be released; change nothing.")
    s = sub.add_parser("status", help="List the release records.")
    for sp in (i, r):
        sp.add_argument("--session-id", default=None, help="The harness session whose task list holds the work.")
        sp.add_argument("--tasks-root", default=None, help="Override the harness task root (tests).")
    for sp in (i, r, s):
        sp.add_argument("--root", default=".", help="workspace root (default: .)")
        sp.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.cmd == "inspect":
        rep = inspect_holds(root, args.session_id, args.tasks_root)
        print(json.dumps(rep, indent=2, sort_keys=True) if args.json else _render_inspect(rep))
        return 0
    if args.cmd == "status":
        rows = status(root)
        print(json.dumps(rows, indent=2) if args.json else
              ("\n".join(f"{row.get('at')}: {row.get('reason')} ({row['path']})" for row in rows) or "(no releases recorded)"))
        return 0
    if args.cmd == "release":
        try:
            summary = release(root, args.reason, args.session_id, args.tasks_root, args.scope, args.dry_run)
        except ValueError as exc:
            print(f"release: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True, default=str))
        elif args.dry_run:
            print("dry run -- would release: " + ("; ".join(summary["would_release"]) or "nothing holds the turn"))
        else:
            print(f"released: {'; '.join(summary['released']) or 'nothing was holding the turn'}")
            print(f"record: {summary['record_path']}")
            if summary["remaining"]:
                print("still held: " + "; ".join(summary["remaining"]))
            for p in summary["problems"]:
                print(f"problem: {p}")
        return 1 if summary.get("problems") or summary.get("remaining") else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
