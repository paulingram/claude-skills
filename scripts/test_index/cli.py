# -*- coding: utf-8 -*-
"""Command-line surface over the test-index engine.

Mirrors the house engine+CLI split (`scripts/intuition_lifecycle/cli.py`):
the engine is the mechanism, this is the callable verb set the test-selection
reference names.

    python scripts/test_index/cli.py build  --workspace W [--e2e-dir D] \\
        [--lineage-graph P] [--witness P] [--json]
    python scripts/test_index/cli.py select --workspace W --phase 3 \\
        (--baseline SHA | --changed-files f1 f2 ...) \\
        [--changed-endpoints /api/x ...] [--changed-elements id ...] \\
        [--no-write] [--json]
    python scripts/test_index/cli.py stats  --workspace W [--json]
    python scripts/test_index/cli.py pins   --workspace W [--json]

Exit codes: ``0`` success, ``2`` a usage error (an unreadable workspace, a
``select`` with neither ``--baseline`` nor ``--changed-files``, a git failure
behind ``--baseline``), ``3`` an unexpected internal failure -- so a crash can
never be mistaken for an empty selection.

The engine is loaded by file path (the `scripts/` tier's house idiom), so this
CLI runs from any working directory without a package install.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ENGINE_PATH = Path(__file__).resolve().parent / "engine.py"


def _load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("ct6_test_index_engine", _ENGINE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load the engine from {_ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = _load_engine()


def _safe_print(text: str = "") -> None:
    """Print without dying on a console codec that cannot represent ``text``
    (a Windows cp1252 console and a non-ASCII path, for instance)."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


def _emit(payload: Dict[str, Any]) -> None:
    _safe_print(json.dumps(payload, indent=2, ensure_ascii=True))


def _workspace(args: argparse.Namespace) -> Path:
    ws = Path(args.workspace)
    if not ws.is_dir():
        raise SystemExit(f"usage: --workspace {ws} is not a directory")
    return ws


# --------------------------------------------------------------------------- #
# verbs
# --------------------------------------------------------------------------- #

def _cmd_build(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    index = engine.build(ws, e2e_dir=args.e2e_dir, lineage_graph=args.lineage_graph,
                         witness=args.witness)
    if args.json:
        _emit(index)
    else:
        st = engine.stats(index)
        _safe_print(f"test index: {st['total']} tests -> "
                    f"{engine.index_path(ws).as_posix()}")
        _safe_print(f"  by kind : {st['by_kind']}")
        _safe_print(f"  by trust: {st['by_trust']}")
        _safe_print(f"  sources : {index['sources']}")
        _safe_print(f"  pinned  : {st['always_run']}  unknown-mapping: {st['unknown_mapping']}")
    return 0


def _cmd_select(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    if not args.baseline and not args.changed_files:
        raise SystemExit("usage: select needs --baseline SHA or --changed-files f1 f2 ...")
    changed: List[str] = list(args.changed_files or [])
    if args.baseline:
        try:
            changed.extend(engine.changed_files_from_git(ws, args.baseline))
        except engine.GitError as exc:
            raise SystemExit(f"usage: {exc}")
    record = engine.select(ws, changed, args.phase,
                           changed_endpoints=args.changed_endpoints,
                           changed_elements=args.changed_elements,
                           baseline=args.baseline, write=not args.no_write)
    if args.json:
        _emit(record)
    else:
        label = "FULL SUITE" if record["full_suite"] else "selected"
        _safe_print(f"phase {record['phase']}: {label} {len(record['selected'])} of "
                    f"{record['index_tests']} tests ({record['skipped_count']} skipped)")
        for item in record["selected"]:
            _safe_print(f"  {item['id']}  <- {'; '.join(item['reasons'])}")
        if record.get("record_path"):
            _safe_print(f"evidence: {record['record_path']}")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    index = engine.load_index(ws)
    st = engine.stats(index)
    st["index_present"] = index is not None
    st["last_selection"] = engine.latest_selection(ws)
    if args.json:
        _emit(st)
    else:
        if index is None:
            _safe_print("no test index yet -- run `build` first")
        _safe_print(f"tests: {st['total']}  kinds: {st['by_kind']}  trust: {st['by_trust']}")
        _safe_print(f"pinned: {st['always_run']}  unknown-mapping: {st['unknown_mapping']}")
        _safe_print(f"last selection: {st['last_selection']}")
    return 0


def _cmd_pins(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    dc = engine._deploy_config_mod()
    payload = {
        "config": dc.DEPLOY_CONFIG_FILENAME,
        "config_present": (ws / dc.DEPLOY_CONFIG_FILENAME).is_file(),
        "always_run": dc.tests_always_run(ws),
        "full_suite_at": dc.tests_full_suite_at(ws),
        "full_suite_phases_effective": sorted(engine._full_suite_phases(ws)),
        "note": "human-owned pins; the pipeline and every agent may read them, "
                "never lower them. Phase 8 is always a full-suite phase.",
    }
    if args.json:
        _emit(payload)
    else:
        _safe_print(f"always_run    : {payload['always_run']}")
        _safe_print(f"full_suite_at : {payload['full_suite_at']} "
                    f"(effective phases: {payload['full_suite_phases_effective']})")
        _safe_print(f"source        : {payload['config']} "
                    f"({'present' if payload['config_present'] else 'absent -> defaults'})")
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="test_index",
                                     description="CT6 test index + impact-based selector")
    sub = parser.add_subparsers(dest="verb", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--workspace", required=True, help="the target repo root")
        p.add_argument("--json", action="store_true", help="machine-readable output")

    p = sub.add_parser("build", help="build <workspace>/.architect-team/test-index.json")
    _common(p)
    p.add_argument("--e2e-dir", default=None,
                   help="directory holding suite-manifest.json (default: search)")
    p.add_argument("--lineage-graph", default=None, help="path to lineage-graph.json")
    p.add_argument("--witness", default=None, help="path to test-witness.json")
    p.set_defaults(func=_cmd_build)

    p = sub.add_parser("select", help="select the tests a change set requires")
    _common(p)
    p.add_argument("--phase", required=True, help="the pipeline phase, e.g. 3, 5, 8")
    p.add_argument("--baseline", default=None, help="git revision to diff against")
    p.add_argument("--changed-files", nargs="*", default=None)
    p.add_argument("--changed-endpoints", nargs="*", default=None)
    p.add_argument("--changed-elements", nargs="*", default=None)
    p.add_argument("--no-write", action="store_true",
                   help="do not write the test-selection-<ts>.json evidence record")
    p.set_defaults(func=_cmd_select)

    p = sub.add_parser("stats", help="counts by kind / layer / trust + the last selection")
    _common(p)
    p.set_defaults(func=_cmd_stats)

    p = sub.add_parser("pins", help="print the human-owned always_run / full_suite_at pins")
    _common(p)
    p.set_defaults(func=_cmd_pins)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:
        if isinstance(exc.code, str):
            _safe_print(exc.code)
            return 2
        raise
    except Exception as exc:  # pragma: no cover - the crash-vs-gate distinction
        _safe_print(f"internal error: {type(exc).__name__}: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
