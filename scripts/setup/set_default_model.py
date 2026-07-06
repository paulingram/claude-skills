# -*- coding: utf-8 -*-
"""Uniform agent-model lever — rewrite every agents/*.md frontmatter ``model:`` field.

The v3.32.0 default ships all agents as ``model: fable`` (Fable 5, wherever it is
available). This stdlib-only CLI is the sanctioned, deterministic lever for that
field AND the IMPLEMENTED Opus-4.8 fallback for a harness that predates the fable
alias: ``python scripts/setup/set_default_model.py --model opus``.

Behaviour
---------
* ``--model fable|opus|sonnet|haiku`` rewrites ONLY the ``model:`` line in each
  agent's YAML frontmatter (bodies stay byte-identical; the change is idempotent).
  An unknown model is refused (exit 1) and touches nothing.
* ``--check`` prints the current model distribution + whether it is uniform (exit 0).
* ``--agents-dir`` overrides the target directory (default: the repo's agents/).

Exit codes: 0 on a successful flip or a ``--check`` report; 1 on a validation error
(unknown model); 2 when the agents directory does not exist.

Mirrors the house style of scripts/setup/sync_agent_boilerplate.py (line-ending
preservation, write-only-if-changed, argparse main). Stdlib-only.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Dict, List, Optional, Tuple

VALID_MODELS = ("fable", "opus", "sonnet", "haiku")


def _default_agents_dir() -> pathlib.Path:
    """Locate the repo's ``agents/`` directory relative to this file."""
    return pathlib.Path(__file__).resolve().parents[2] / "agents"


def _detect_newline(raw: bytes) -> str:
    """Return the dominant line-ending in ``raw`` (``"\\r\\n"`` or ``"\\n"``)."""
    crlf = raw.count(b"\r\n")
    bare_lf = raw.replace(b"\r\n", b"").count(b"\n")
    if crlf >= bare_lf and crlf > 0:
        return "\r\n"
    return "\n"


def _read(path: pathlib.Path) -> Tuple[str, str, bool]:
    """Read ``path`` -> (universal-newline text, newline style, trailing-newline)."""
    raw = path.read_bytes()
    newline = _detect_newline(raw)
    text_lf = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    trailing = text_lf.endswith("\n")
    return text_lf, newline, trailing


def _write_if_changed(path: pathlib.Path, new_text_lf: str, newline: str) -> bool:
    """Encode ``new_text_lf`` with ``newline`` and write only if the bytes differ."""
    if newline == "\n":
        encoded = new_text_lf.encode("utf-8")
    else:
        encoded = new_text_lf.replace("\n", newline).encode("utf-8")
    if path.read_bytes() == encoded:
        return False
    path.write_bytes(encoded)
    return True


def _frontmatter_bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Return ``(open_idx, close_idx)`` of the YAML frontmatter fence, or ``None``.

    The frontmatter is the block between the first ``---`` line (which must be the
    file's first line) and the next ``---`` line."""
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return (0, i)
    return None


def read_model_value(text_lf: str) -> Optional[str]:
    """Return the frontmatter ``model:`` value, or ``None`` if there is no model line."""
    lines = text_lf.split("\n")
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return None
    _, close = bounds
    for i in range(1, close):
        stripped = lines[i].lstrip()
        if stripped.startswith("model:"):
            return stripped[len("model:"):].strip().strip("\"'")
    return None


def rewrite_model_line(text_lf: str, new_model: str) -> Optional[str]:
    """Rewrite ONLY the frontmatter ``model:`` value to ``new_model``.

    Returns the new text, or ``None`` if there is no model line or it already reads
    ``new_model`` (idempotent)."""
    lines = text_lf.split("\n")
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return None
    _, close = bounds
    for i in range(1, close):
        stripped = lines[i].lstrip()
        if stripped.startswith("model:"):
            indent = lines[i][: len(lines[i]) - len(stripped)]
            new_line = f"{indent}model: {new_model}"
            if lines[i] == new_line:
                return None
            lines[i] = new_line
            return "\n".join(lines)
    return None


def set_model(agents_dir, new_model: str) -> List[str]:
    """Rewrite the model field across ``agents_dir/*.md``. Returns sorted changed stems."""
    agents_dir = pathlib.Path(agents_dir)
    changed: List[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, newline, trailing = _read(path)
        new = rewrite_model_line(text_lf, new_model)
        if new is None or new == text_lf:
            continue
        if trailing and not new.endswith("\n"):
            new += "\n"
        if _write_if_changed(path, new, newline):
            changed.append(path.stem)
    return sorted(changed)


def distribution(agents_dir) -> Dict[str, int]:
    """Return ``{model_value: count}`` across ``agents_dir/*.md``."""
    agents_dir = pathlib.Path(agents_dir)
    dist: Dict[str, int] = {}
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, _, _ = _read(path)
        model = read_model_value(text_lf) or "<none>"
        dist[model] = dist.get(model, 0) + 1
    return dist


def _print_distribution(agents_dir: pathlib.Path) -> None:
    dist = distribution(agents_dir)
    total = sum(dist.values())
    print(f"model distribution across {total} agent file(s) in {agents_dir}:")
    for model in sorted(dist):
        print(f"  {model}: {dist[model]}")
    if len(dist) == 1:
        only = next(iter(dist))
        print(f"uniform: yes ({only})")
    else:
        print("uniform: no")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set (or report) the uniform frontmatter model field across agents/*.md."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--model",
        default=None,
        help="Rewrite every agent's model field to this value ("
        + "/".join(VALID_MODELS)
        + ").",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="Report the current model distribution + whether it is uniform (writes nothing).",
    )
    parser.add_argument(
        "--agents-dir",
        default=None,
        help="Path to the agents/ directory (defaults to the repo's agents/).",
    )
    args = parser.parse_args(argv)

    agents_dir = pathlib.Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    if not agents_dir.is_dir():
        print(f"ERROR: agents directory not found: {agents_dir}", file=sys.stderr)
        return 2

    if args.check:
        _print_distribution(agents_dir)
        return 0

    if args.model not in VALID_MODELS:
        print(
            f"ERROR: unknown model {args.model!r} (valid: {', '.join(VALID_MODELS)})",
            file=sys.stderr,
        )
        return 1

    changed = set_model(agents_dir, args.model)
    if changed:
        print(f"Set model: {args.model} on {len(changed)} agent file(s):")
        for stem in changed:
            print(f"  - {stem}.md")
    else:
        print(f"0 files changed (all agents already model: {args.model}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
