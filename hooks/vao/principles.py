"""VAO principles family (1 tool) -- ``verify-principles-respected``.

The 25th Layer-3 tool. It answers one question about a design, a contract, a
diff or an option set before it is PRESENTED: *was every confirmed project
principle considered, and was a verdict with a cause recorded for each?*

The originating gap: a project's principles ("every service owns its own
tables", "no new ORM") lived in an agent's working memory and were re-derived,
re-argued or silently dropped between lanes. ``scripts/principles/principles.py``
gives them a register (``<workspace>/.architect-team/principles.json``, rendered
to ``docs/PROJECT_PRINCIPLES.md``); this tool is the check that an artifact was
HELD to that register rather than merely produced beside it.

It reads the register from ``--workspace`` and a ``principles-verdicts/v1``
sidecar (written by the architect / teammate beside the artifact) and returns
``{valid, gaps[], warnings[]}``. Hard gaps (``valid`` false):

  * ``principle-without-verdict`` -- a confirmed principle has no verdict.
    "Not considered" is not a verdict.
  * ``violated-without-cause`` -- a ``violated`` verdict lacks ``why`` or
    ``where``. A violation without a location cannot be fixed.
  * ``principle-violated`` -- a confirmed principle is violated with cause and
    no ``user_override`` quoting the user's explicit instruction in this run
    (precedence: user instruction > confirmed principles > CT6 defaults).
  * ``chosen-option-violates`` -- in an autonomous run (``auto_mode`` true) the
    chosen option violates a principle while a fitting option exists.
  * ``chosen-option-missing`` / ``chosen-option-unknown`` -- auto mode, a
    fitting option exists, and nothing (or a non-option) was chosen.
  * ``all-options-violate`` -- every option violates a confirmed principle:
    the hard stop. The run writes ``escalation-pending.md`` and asks which
    principle to relax; it never picks one silently.
  * ``verdict-for-unknown-principle`` / ``invalid-verdict-value`` /
    ``duplicate-verdict`` / ``option-malformed`` / ``sidecar-schema-unknown``
    -- the sidecar does not say what it claims to say.

Warnings (reported, never block): ``principles-cap-exceeded`` (more confirmed
principles than the soft cap), ``no-confirmed-principles``,
``verdict-for-inactive-principle``, ``principle-overridden-by-user``, and
``chosen-option-violates`` when the USER chose (``auto_mode`` false).

Sidecar contract::

    {"schema": "principles-verdicts/v1",
     "subject": {"kind": "design" | "contract" | "diff" | "options", "ref": "..."},
     "verdicts": [{"id": "P-01", "verdict": "respected" | "violated" | "not-applicable",
                   "why": "...", "where": "...", "user_override": "<optional quote>"}],
     "options": [{"label": "A", "fits": true, "violates": [], "why": "..."}],
     "chosen": "A", "auto_mode": true}

HONEST BOUNDARY: the tool proves every confirmed principle was CONSIDERED and a
verdict RECORDED with a cause; it cannot prove a judgment is right. A wrong
"respected" passes. That is the independent reviewer's job (``docs/ETHOS.md``
principle 2), and this verdict is the input they read, not a substitute.

Deterministic, stdlib-only; the only write is the verdict file. The check logic
is the engine's ``check_verdicts`` (loaded by file path from
``scripts/principles/principles.py`` so the two surfaces can never disagree).
Exit codes of ``main``: ``0`` valid, ``2`` gaps (the facade's convention),
``3`` an unreadable register or sidecar -- so an input error is never mistaken
for a verdict.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":  # a direct run: the repo root makes the package shape resolve
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _utc_now_iso, _write_verdict


TOOL_NAME = "verify-principles-respected"

# The engine is a scripts/-tier module two directories up from this file; the
# plugin ships hooks/ and scripts/ side by side, so the relative path is stable
# in every install shape.
_ENGINE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "principles" / "principles.py"
_ENGINE: Any = None


def _engine() -> Any:
    """Load (once) the principles engine by file path."""
    global _ENGINE
    if _ENGINE is None:
        spec = importlib.util.spec_from_file_location("ct6_vao_principles_engine", _ENGINE_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load the principles engine from {_ENGINE_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ENGINE = module
    return _ENGINE


def verify_principles_respected(
    registry: dict[str, Any] | None = None,
    sidecar: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Layer-3 tool -- verify a ``principles-verdicts/v1`` sidecar records a
    verdict for every confirmed principle in ``registry``, that every violation
    carries its cause, and that an autonomous option choice fits.

    Returns ``{tool, valid, gaps[], warnings[], confirmed_count, verdict_count,
    chosen, auto_mode, checked_at}``; ``valid`` is ``len(gaps) == 0``.
    """
    eng = _engine()
    report = eng.check_verdicts(registry if registry is not None else eng.empty_registry(),
                                sidecar if sidecar is not None else {})
    verdict = {
        "tool": TOOL_NAME,
        "valid": report["valid"],
        "gaps": report["findings"],
        "warnings": report["warnings"],
        "confirmed_count": report["confirmed_count"],
        "verdict_count": report["verdict_count"],
        "chosen": report["chosen"],
        "auto_mode": report["auto_mode"],
        "checked_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


def _default_out(workspace: str, sidecar_path: str) -> Path:
    return Path(workspace) / ".architect-team" / "vao-verdicts" / f"{Path(sidecar_path).stem}-{TOOL_NAME}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Layer 3 of VAO -- verify every confirmed project principle has a recorded verdict.",
    )
    parser.add_argument("--workspace", required=True,
                        help="The target codebase root holding .architect-team/principles.json.")
    parser.add_argument("--verdicts", required=True, help="Path to the principles-verdicts/v1 sidecar JSON.")
    parser.add_argument("--out", default=None,
                        help="Where to write the verdict JSON (default: "
                             "<workspace>/.architect-team/vao-verdicts/<sidecar-stem>-verify-principles-respected.json).")
    parser.add_argument("--json", action="store_true", help="Print the verdict as JSON.")
    args = parser.parse_args(argv)

    eng = _engine()
    try:
        registry = eng.load_registry(args.workspace)
    except eng.RegistryError as exc:
        print(f"register error: {exc}")
        return 3
    try:
        sidecar = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print(f"cannot read verdict sidecar {args.verdicts}: {exc}")
        return 3

    out = args.out or _default_out(args.workspace, args.verdicts)
    verdict = verify_principles_respected(registry, sidecar, out_path=out)
    if args.json:
        print(json.dumps(verdict, indent=2, sort_keys=True))
    else:
        for gap in verdict["gaps"]:
            print(f"[gap] {gap['severity']}: {gap['principle_id']} -- {gap['evidence']}")
        for warning in verdict["warnings"]:
            print(f"[warning] {warning['severity']}: {warning['principle_id']} -- {warning['evidence']}")
        print(f"{TOOL_NAME}: valid={verdict['valid']} gaps={len(verdict['gaps'])} "
              f"warnings={len(verdict['warnings'])} confirmed={verdict['confirmed_count']} "
              f"verdict={out}")
    return 0 if verdict["valid"] else 2


__all__ = ["TOOL_NAME", "verify_principles_respected", "main"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
