# -*- coding: utf-8 -*-
"""Command-line surface over the project-principles engine.

Mirrors the house engine+CLI split (`scripts/intuition_lifecycle/cli.py`): the
engine is the mechanism, this is the verb set the `project-principles` skill and
the `/architect-team:principles` command name. Every workspace verb loads the
register, applies the verb, and writes BOTH twins (`.architect-team/principles.json`
+ `docs/PROJECT_PRINCIPLES.md`); `extract-candidates` and `check` write nothing.

    python scripts/principles/cli.py show      [--workspace W] [--json]
    python scripts/principles/cli.py propose   --statement S --scope X \\
        [--source document|extracted|user-stated] [--file F] [--quote Q] \\
        [--added-by WHO] [--workspace W] [--json]
    python scripts/principles/cli.py confirm   P-01 [--workspace W] [--json]
    python scripts/principles/cli.py add       --statement S --scope X [--quote Q] \\
        [--added-by WHO] [--workspace W] [--json]
    python scripts/principles/cli.py retire    P-01 --reason R [--workspace W] [--json]
    python scripts/principles/cli.py default-set [--workspace W] [--json]
    python scripts/principles/cli.py render    [--workspace W]
    python scripts/principles/cli.py brief     [--workspace W]
    python scripts/principles/cli.py extract-candidates <markdown-file> [--json]
    python scripts/principles/cli.py check     --verdicts <sidecar.json> [--workspace W] [--json]

Exit codes: ``0`` clean, ``1`` a refused verb (unknown id, missing source,
duplicate statement) or blocking ``check`` findings, ``2`` a usage / payload /
unreadable-register error, ``3`` an unexpected internal failure. A ``check``
with findings exits ``1`` because it needs the agent (or the user) to act; ``3``
exists so a crash can never be mistaken for that.

The engine is loaded by file path (the `scripts/` tier's house idiom) so this
CLI runs from any working directory without a package install.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ENGINE_PATH = Path(__file__).resolve().parent / "principles.py"


def _load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("ct6_principles_engine", _ENGINE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load the engine from {_ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = _load_engine()


def _safe_print(text: str = "") -> None:
    """Print without dying on a console codec that cannot represent ``text``
    (a verbatim quote may carry any character; a cp1252 console cannot)."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


def _emit(payload: Dict[str, Any], as_json: bool, lines: List[str]) -> None:
    if as_json:
        _safe_print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for line in lines:
            _safe_print(line)


def _warning_lines(warnings: List[Dict[str, Any]]) -> List[str]:
    return [f"WARNING {w['severity']}: {w['evidence']}" for w in warnings]


def _principle_line(p: Dict[str, Any]) -> str:
    return f"{p['id']:6s} {p['status']:9s} [{p['scope']}] {p['statement']}"


def _load(args: argparse.Namespace) -> Dict[str, Any]:
    return engine.load_registry(args.workspace)


def _save(args: argparse.Namespace, registry: Dict[str, Any]) -> Dict[str, str]:
    return engine.save_registry(args.workspace, registry)


# --------------------------------------------------------------------------- #
# Verbs
# --------------------------------------------------------------------------- #

def _cmd_show(args: argparse.Namespace) -> int:
    report = engine.show(_load(args))
    lines = [
        f"schema: {report['schema']}   soft_cap: {report['soft_cap']}",
        f"precedence: {report['precedence']}",
        f"confirmed: {report['counts']['confirmed']}  proposed: {report['counts']['proposed']}  "
        f"retired: {report['counts']['retired']}",
        "",
    ]
    lines += [_principle_line(p) for p in report["confirmed"]]
    lines += [_principle_line(p) for p in report["proposed"]]
    if report["retired_ids"]:
        lines.append("retired: " + ", ".join(report["retired_ids"]))
    lines += _warning_lines(report["warnings"])
    _emit(report, args.json, lines)
    return 0


def _cmd_propose(args: argparse.Namespace) -> int:
    registry = _load(args)
    principle = engine.propose(
        registry, args.statement, args.scope, source_kind=args.source,
        source_file=args.file, quote=args.quote, added_by=args.added_by,
    )
    paths = _save(args, registry)
    payload = {"verb": "propose", "principle": principle, "paths": paths, "warnings": []}
    _emit(payload, args.json, [f"proposed {principle['id']} [{principle['scope']}] "
                               f"{principle['statement']}",
                               f"wrote {paths['json_path']} + {paths['md_path']}",
                               "status: proposed -- confirm it with the user before it binds"])
    return 0


def _cmd_confirm(args: argparse.Namespace) -> int:
    registry = _load(args)
    result = engine.confirm(registry, args.id)
    paths = _save(args, registry)
    payload = {"verb": "confirm", "principle": result["principle"], "changed": result["changed"],
               "warnings": result["warnings"], "paths": paths}
    verb = "confirmed" if result["changed"] else "already confirmed"
    _emit(payload, args.json, [f"{verb} {args.id}", f"wrote {paths['json_path']} + {paths['md_path']}"]
          + _warning_lines(result["warnings"]))
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    registry = _load(args)
    result = engine.add(registry, args.statement, args.scope, added_by=args.added_by,
                        quote=args.quote)
    paths = _save(args, registry)
    p = result["principle"]
    payload = {"verb": "add", "principle": p, "warnings": result["warnings"], "paths": paths}
    _emit(payload, args.json, [f"added + confirmed {p['id']} [{p['scope']}] {p['statement']}",
                               f"wrote {paths['json_path']} + {paths['md_path']}"]
          + _warning_lines(result["warnings"]))
    return 0


def _cmd_retire(args: argparse.Namespace) -> int:
    registry = _load(args)
    p = engine.retire(registry, args.id, args.reason)
    paths = _save(args, registry)
    payload = {"verb": "retire", "principle": p, "paths": paths, "warnings": []}
    _emit(payload, args.json, [f"retired {p['id']}: {p['retire_reason']}",
                               f"wrote {paths['json_path']} + {paths['md_path']}"])
    return 0


def _cmd_default_set(args: argparse.Namespace) -> int:
    registry = _load(args)
    result = engine.default_set(registry)
    paths = _save(args, registry)
    payload = {"verb": "default-set", "added": result["added"], "skipped": result["skipped"],
               "paths": paths, "warnings": []}
    _emit(payload, args.json, [f"added (proposed): {', '.join(result['added']) or '(none)'}",
                               f"skipped (already present): {', '.join(result['skipped']) or '(none)'}",
                               f"wrote {paths['json_path']} + {paths['md_path']}",
                               "nothing is confirmed by this verb -- confirm each with the user"])
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    registry = _load(args)
    target = engine.write_markdown(args.workspace, registry)
    _safe_print(f"wrote {target}")
    return 0


def _cmd_brief(args: argparse.Namespace) -> int:
    _safe_print(engine.binding_brief(_load(args)))
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    try:
        candidates = engine.extract_candidates_from_file(args.file)
    except (OSError, UnicodeDecodeError) as exc:
        _safe_print(f"cannot read {args.file}: {exc}")
        return 2
    if args.json:
        _safe_print(json.dumps({"file": str(args.file), "candidates": candidates}, indent=2))
        return 0
    for c in candidates:
        hint = f" scope-hint={c['scope_hint']}" if c["scope_hint"] else ""
        _safe_print(f"L{c['line']:<5d} [{c['kind']}]{hint} \"{c['quote']}\"")
    _safe_print(f"{len(candidates)} candidate(s); nothing written -- judge, then propose/confirm "
                "with the user.")
    return 0


def _print_findings(items: List[Dict[str, Any]], label: str) -> None:
    for f in items:
        _safe_print(f"[{label}] {f['severity']}: {f['principle_id']} -- {f['evidence']}")


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        sidecar = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        _safe_print(f"cannot read verdict sidecar {args.verdicts}: {exc}")
        return 2
    report = engine.check_verdicts(_load(args), sidecar)
    if args.json:
        _safe_print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_findings(report["findings"], "finding")
        _print_findings(report["warnings"], "warning")
        _safe_print(f"{len(report['findings'])} blocking finding(s), "
                    f"{len(report['warnings'])} warning(s); confirmed principles checked: "
                    f"{report['confirmed_count']}; valid: {report['valid']}")
    return 0 if report["valid"] else 1


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #

def _add_workspace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default=".",
                        help="The target codebase root (default: cwd).")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Codified project principles: propose, confirm, add, retire, show, "
                    "extract-candidates, check, default-set.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    show = sub.add_parser("show", help="List the register (read-only).")
    _add_workspace(show)

    propose = sub.add_parser("propose", help="Add a PROPOSED principle from a source.")
    propose.add_argument("--statement", required=True)
    propose.add_argument("--scope", required=True, choices=list(engine.SCOPES))
    propose.add_argument("--source", default="document", choices=list(engine.SOURCE_KINDS))
    propose.add_argument("--file", default=None, help="Source document (required unless user-stated).")
    propose.add_argument("--quote", default=None, help="Verbatim quote (required unless user-stated).")
    propose.add_argument("--added-by", default="agent")
    _add_workspace(propose)

    confirm = sub.add_parser("confirm", help="Confirm a proposed principle (after the user said so).")
    confirm.add_argument("id")
    _add_workspace(confirm)

    add = sub.add_parser("add", help="A user-stated principle, confirmed immediately.")
    add.add_argument("--statement", required=True)
    add.add_argument("--scope", required=True, choices=list(engine.SCOPES))
    add.add_argument("--quote", default=None, help="The user's verbatim words (optional).")
    add.add_argument("--added-by", default="user")
    _add_workspace(add)

    retire = sub.add_parser("retire", help="Retire a principle with a reason.")
    retire.add_argument("id")
    retire.add_argument("--reason", required=True)
    _add_workspace(retire)

    default = sub.add_parser("default-set", help="Seed the reuse-first ladder as PROPOSED P-R1..P-R4.")
    _add_workspace(default)

    render = sub.add_parser("render", help="Re-render docs/PROJECT_PRINCIPLES.md from the JSON twin.")
    _add_workspace(render)

    brief = sub.add_parser("brief", help="Print the confirmed-principles block a spawn brief carries.")
    _add_workspace(brief)

    extract = sub.add_parser("extract-candidates",
                             help="Print candidate statements from a markdown file (writes nothing).")
    extract.add_argument("file")
    extract.add_argument("--json", action="store_true")

    check = sub.add_parser("check", help="Validate a principles-verdicts/v1 sidecar against the register.")
    check.add_argument("--verdicts", required=True, help="Path to the sidecar JSON.")
    _add_workspace(check)
    return parser


_DISPATCH = {
    "show": _cmd_show,
    "propose": _cmd_propose,
    "confirm": _cmd_confirm,
    "add": _cmd_add,
    "retire": _cmd_retire,
    "default-set": _cmd_default_set,
    "render": _cmd_render,
    "brief": _cmd_brief,
    "extract-candidates": _cmd_extract,
    "check": _cmd_check,
}


def main(argv: Optional[List[str]] = None) -> int:
    """Exit 0 clean, 1 a refused verb or blocking check findings, 2 a usage /
    payload / register error, 3 an unexpected internal failure."""
    args = build_parser().parse_args(argv)
    try:
        return _DISPATCH[args.cmd](args)
    except engine.RegistryError as exc:
        _safe_print(f"register error: {exc}")
        return 2
    except engine.PrinciplesError as exc:
        _safe_print(f"refused: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - NOTHING escapes as 1
        _safe_print(f"internal error: {type(exc).__name__}: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
