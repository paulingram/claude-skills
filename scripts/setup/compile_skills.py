# -*- coding: utf-8 -*-
"""Marker-block compiler for the pipeline SKILL.md files.

The counterpart of ``scripts/setup/sync_agent_boilerplate.py`` for skills. Where
the agent sync tool keeps ``## ``-delimited boilerplate sections byte-identical to
their canonical source across ``agents/*.md``, this tool keeps FENCED blocks
byte-identical across the consuming ``skills/*/SKILL.md`` files.

A consuming skill opts in by placing a fence pair around a block::

    <!-- ct6:block:principles:begin -->
    ...content the tool owns...
    <!-- ct6:block:principles:end -->

``compile_skills.py --write`` rewrites ONLY the lines strictly between a matching
``begin`` / ``end`` pair to the canonical render of that block id; every other byte
of the file is left exactly as-is. ``--check`` writes nothing and exits non-zero if
any consuming file's fenced content differs from a fresh render (the drift guard a
hand-edit inside a fence trips). Output is deterministic and byte-stable — there
are NO timestamps and no ordering nondeterminism, so two consecutive ``--write``
runs produce identical bytes.

The canonical block sources are defined ONCE. ``principles`` renders the compact
operating-principles block whose single source of truth is
``scripts/setup/agent_boilerplate_blocks.PRINCIPLES`` — the same string the agent
sync tool injects — so a skill and an agent can never disagree about the text.

Stdlib-only; no third-party dependencies; no import-time side effects.

Usage
-----
    python scripts/setup/compile_skills.py            # rewrite + summary
    python scripts/setup/compile_skills.py --check     # report drift only
    python scripts/setup/compile_skills.py --skills-dir path/to/skills

``--check`` exits 0 when every consuming skill's fenced content matches a fresh
render and non-zero when any drift is found (it writes nothing). The plain form
(equivalently ``--write``) rewrites drifted files and prints the list of changed
files; exit code is 0.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Dict, List, Optional, Tuple

# Import the canonical-block module. Support both package import (repo root on
# sys.path, e.g. under pytest) and direct script execution — matches the
# sync_agent_boilerplate.py resolution dance.
try:  # pragma: no cover - exercised both ways across environments
    from scripts.setup import agent_boilerplate_blocks as blocks
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from scripts.setup import agent_boilerplate_blocks as blocks


# The canonical block sources, defined once. Each value is the exact text the tool
# writes between that block's fences. `principles` reuses the single source of
# truth in agent_boilerplate_blocks so skills and agents render identically.
BLOCKS: Dict[str, str] = {
    "principles": blocks.PRINCIPLES,
}

# Backwards-compatible alias used by tests asserting the single-source guarantee:
# the skill-side principles render IS the agent-side canonical string (same object).
PRINCIPLES_BLOCK = blocks.PRINCIPLES

# Fence markers. `<!-- ct6:block:<id>:begin -->` / `<!-- ct6:block:<id>:end -->`.
_FENCE_BEGIN_RE = re.compile(r"^<!--\s*ct6:block:([a-z0-9][a-z0-9-]*):begin\s*-->\s*$")
_FENCE_END_RE = re.compile(r"^<!--\s*ct6:block:([a-z0-9][a-z0-9-]*):end\s*-->\s*$")


def fence_begin(block_id: str) -> str:
    """The exact begin-marker line for ``block_id`` (no trailing newline)."""
    return f"<!-- ct6:block:{block_id}:begin -->"


def fence_end(block_id: str) -> str:
    """The exact end-marker line for ``block_id`` (no trailing newline)."""
    return f"<!-- ct6:block:{block_id}:end -->"


def render_block(block_id: str) -> str:
    """The canonical text for ``block_id`` (raises KeyError for an unknown id)."""
    return BLOCKS[block_id]


def _default_skills_dir() -> pathlib.Path:
    """Locate the repo's ``skills/`` directory relative to this file."""
    return pathlib.Path(__file__).resolve().parents[2] / "skills"


# Reuse the canonical newline-preserving rewrite trio (v3.35.1 consolidation) so a
# CRLF working tree round-trips byte-exactly, exactly as the agent sync tool does.
_read = blocks.read_preserving
_write_if_changed = blocks.write_if_changed


def find_fences(text_lf: str) -> List[Tuple[str, int, int]]:
    """Return ``(block_id, begin_idx, end_idx)`` for every fence pair in ``text_lf``.

    ``begin_idx`` / ``end_idx`` are 0-based line indices of the marker lines
    themselves. Fences are matched in document order; a ``begin`` whose id has no
    following matching ``end`` is reported via :class:`ValueError`, and a nested or
    mismatched pair is likewise rejected — a malformed fence is a fatal authoring
    error, not something to paper over.
    """
    lines = text_lf.split("\n")
    out: List[Tuple[str, int, int]] = []
    open_id: Optional[str] = None
    open_idx = -1
    for i, line in enumerate(lines):
        mb = _FENCE_BEGIN_RE.match(line)
        me = _FENCE_END_RE.match(line)
        if mb:
            if open_id is not None:
                raise ValueError(
                    f"nested ct6:block fence: '{mb.group(1)}:begin' opened while "
                    f"'{open_id}' still open (line {i + 1})"
                )
            open_id = mb.group(1)
            open_idx = i
        elif me:
            if open_id is None:
                raise ValueError(f"ct6:block '{me.group(1)}:end' with no open begin (line {i + 1})")
            if me.group(1) != open_id:
                raise ValueError(
                    f"ct6:block fence mismatch: '{open_id}:begin' closed by "
                    f"'{me.group(1)}:end' (line {i + 1})"
                )
            out.append((open_id, open_idx, i))
            open_id = None
    if open_id is not None:
        raise ValueError(f"unclosed ct6:block fence '{open_id}:begin' (line {open_idx + 1})")
    return out


def fenced_content(text_lf: str, block_id: str) -> Optional[str]:
    """Return the current content between ``block_id``'s fences (LF, no markers).

    ``None`` when the file carries no fence for ``block_id``.
    """
    for bid, b, e in find_fences(text_lf):
        if bid == block_id:
            return "\n".join(text_lf.split("\n")[b + 1:e])
    return None


def _rewrite(text_lf: str) -> Tuple[str, List[str]]:
    """Rewrite every recognized fence's content to its canonical render.

    Returns ``(new_text_lf, drifted_block_ids)`` where ``drifted_block_ids`` names
    the blocks whose content actually changed. Unknown block ids raise — a fence
    citing a block the tool does not define is an authoring error.
    """
    fences = find_fences(text_lf)
    if not fences:
        return text_lf, []
    lines = text_lf.split("\n")
    drifted: List[str] = []
    # Rebuild left-to-right; process fences in order (find_fences is ordered).
    result: List[str] = []
    cursor = 0
    for block_id, b, e in fences:
        if block_id not in BLOCKS:
            raise KeyError(f"ct6:block fence cites unknown block id '{block_id}'")
        result.extend(lines[cursor:b + 1])  # up to and including the begin marker
        canon_lines = render_block(block_id).split("\n")
        current = lines[b + 1:e]
        if current != canon_lines:
            drifted.append(block_id)
        result.extend(canon_lines)
        result.append(lines[e])  # the end marker
        cursor = e + 1
    result.extend(lines[cursor:])
    return "\n".join(result), drifted


def _process_file(path: pathlib.Path, dry_run: bool) -> bool:
    """Compile one skill file. Returns True if it changed (or would, in dry-run)."""
    text_lf, newline, trailing = _read(path)
    new_text, drifted = _rewrite(text_lf)
    if not drifted or new_text == text_lf:
        return False
    if trailing and not new_text.endswith("\n"):
        new_text += "\n"
    if dry_run:
        return True
    return _write_if_changed(path, new_text, newline)


def _consuming_files(skills_dir: pathlib.Path) -> List[pathlib.Path]:
    """Every ``skills/*/SKILL.md`` that carries at least one ct6:block fence."""
    out: List[pathlib.Path] = []
    for d in sorted(pathlib.Path(skills_dir).glob("*")):
        sk = d / "SKILL.md"
        if not sk.exists():
            continue
        text_lf, _, _ = _read(sk)
        if find_fences(text_lf):
            out.append(sk)
    return out


def find_drift(skills_dir: pathlib.Path) -> List[str]:
    """Return the sorted skill dir-names whose fenced content is out of sync."""
    drifted: List[str] = []
    for sk in _consuming_files(skills_dir):
        if _process_file(sk, dry_run=True):
            drifted.append(sk.parent.name)
    return sorted(drifted)


def compile_skills(skills_dir: pathlib.Path) -> List[str]:
    """Rewrite drifted consuming skills in place. Returns sorted changed dir-names."""
    changed: List[str] = []
    for sk in _consuming_files(skills_dir):
        if _process_file(sk, dry_run=False):
            changed.append(sk.parent.name)
    return sorted(changed)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile fenced boilerplate blocks in skills/*/SKILL.md to their canonical source."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift without writing; exit non-zero if any consuming skill is out of sync.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the canonical render to every fence (the default action).",
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Path to the skills/ directory (defaults to the repo's skills/).",
    )
    args = parser.parse_args(argv)

    skills_dir = pathlib.Path(args.skills_dir) if args.skills_dir else _default_skills_dir()
    if not skills_dir.is_dir():
        print(f"ERROR: skills directory not found: {skills_dir}", file=sys.stderr)
        return 2

    if args.check:
        drifted = find_drift(skills_dir)
        if drifted:
            print(f"DRIFT: {len(drifted)} skill(s) out of sync with the canonical fenced blocks:")
            for name in drifted:
                print(f"  - {name}/SKILL.md")
            print("Run `python scripts/setup/compile_skills.py --write` to fix.")
            return 1
        print(f"IN SYNC: all fenced skill blocks match the canonical source ({skills_dir}).")
        return 0

    changed = compile_skills(skills_dir)
    if changed:
        print(f"Compiled {len(changed)} skill file(s) to match the canonical fenced blocks:")
        for name in changed:
            print(f"  - {name}/SKILL.md")
    else:
        print("0 files changed (already in sync).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
