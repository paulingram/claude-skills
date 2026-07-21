# -*- coding: utf-8 -*-
"""Idempotent regenerator for the three duplicated agent boilerplate blocks.

This tool keeps the ``## Forbidden git operations``, ``## Checkpoint discipline``
and ``## Operating context (v1.0.0)`` sections in every *standard* agent file
byte-identical to the canonical text in
``scripts/setup/agent_boilerplate_blocks.py`` (the single source of truth).

Behaviour
---------
* For ``equals``-mode blocks (git, checkpoint) the entire extracted block is
  replaced with the canonical text.
* For the ``prefix``-mode block (operating-context) ONLY the canonical leading
  paragraph is rewritten; any role-specific text an agent appends after it is
  preserved untouched.
* ``variant_agents`` (adversarial-reviewer, interaction-observer,
  oracle-deriver) are NEVER modified -- they carry deliberately role-specific
  forms.
* The file's existing line-ending style (CRLF in this repo's working tree under
  ``core.autocrlf=true``, or LF) is preserved, and a file is only rewritten when
  its bytes actually change. Running against an already-in-sync tree therefore
  makes ZERO changes (idempotent).

Usage
-----
    python scripts/setup/sync_agent_boilerplate.py            # rewrite + summary
    python scripts/setup/sync_agent_boilerplate.py --check    # report drift only
    python scripts/setup/sync_agent_boilerplate.py --agents-dir path/to/agents

``--check`` exits 0 when every standard agent is in sync and non-zero when any
drift is found (it writes nothing). The plain form rewrites drifted standard
agents and prints the list of changed files; exit code is 0.

Stdlib-only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import List, Optional, Tuple

# Import the canonical-block module. Support both package import (when the repo
# root is on sys.path, e.g. under pytest) and direct script execution.
try:  # pragma: no cover - exercised both ways across environments
    from scripts.setup import agent_boilerplate_blocks as blocks
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from scripts.setup import agent_boilerplate_blocks as blocks


def _default_agents_dir() -> pathlib.Path:
    """Locate the repo's ``agents/`` directory relative to this file."""
    return pathlib.Path(__file__).resolve().parents[2] / "agents"


# The newline-preserving rewrite trio lives canonically in
# agent_boilerplate_blocks (v3.35.1 consolidation); thin aliases keep this
# module's call sites and test surface unchanged.
_detect_newline = blocks.detect_newline
_read = blocks.read_preserving
_write_if_changed = blocks.write_if_changed


def _replace_equals_block(text_lf: str, heading: str, canonical: str) -> Optional[str]:
    """Replace the full ``heading`` block with ``canonical`` (LF form).

    Returns the new text, or ``None`` if the heading is absent or already exact.
    """
    lines = text_lf.split("\n")
    start = None
    end = None  # exclusive: index of next "## " heading (or len(lines))
    for i, line in enumerate(lines):
        if start is None:
            if line.rstrip() == heading:
                start = i
            continue
        if line.startswith("## ") and line.rstrip() != heading:
            end = i
            break
    if start is None:
        return None
    if end is None:
        end = len(lines)
    # Trim trailing blank lines inside the block so we replace [start, last-content+1)
    last = end
    while last - 1 > start and lines[last - 1].strip() == "":
        last -= 1
    current = "\n".join(lines[start:last])
    if current == canonical:
        return None
    canon_lines = canonical.split("\n")
    new_lines = lines[:start] + canon_lines + lines[last:]
    return "\n".join(new_lines)


def _replace_prefix_block(text_lf: str, heading: str, canonical: str) -> Optional[str]:
    """Rewrite ONLY the canonical leading paragraph of a prefix-mode block.

    The canonical prefix is the ``heading`` line through the first paragraph.
    Any role-specific text the agent appends after the prefix is preserved.
    Returns the new text, or ``None`` if the heading is absent or the prefix is
    already exact.
    """
    block = blocks.extract_block(text_lf, heading)
    if block is None:
        return None
    if block == canonical or block.startswith(canonical + "\n"):
        # already correct prefix -> nothing to do unless the canonical itself
        # differs from the present prefix span; detect a same-length prefix diff
        present_prefix = block[: len(canonical)]
        if present_prefix == canonical:
            return None
    # Locate the block span in lines and rebuild prefix + preserved remainder.
    lines = text_lf.split("\n")
    start = None
    end = None
    for i, line in enumerate(lines):
        if start is None:
            if line.rstrip() == heading:
                start = i
            continue
        if line.startswith("## ") and line.rstrip() != heading:
            end = i
            break
    if start is None:
        return None
    if end is None:
        end = len(lines)
    last = end
    while last - 1 > start and lines[last - 1].strip() == "":
        last -= 1
    block_lines = lines[start:last]
    block_text = "\n".join(block_lines)
    canon_lines = canonical.split("\n")
    n = len(canon_lines)
    # The remainder is everything after the canonical-prefix lines.
    remainder = block_lines[n:]
    new_block_lines = canon_lines + remainder
    new_block_text = "\n".join(new_block_lines)
    if new_block_text == block_text:
        return None
    new_lines = lines[:start] + new_block_lines + lines[last:]
    return "\n".join(new_lines)


def _insert_block_after(text_lf: str, anchor_heading: str, canonical: str) -> Optional[str]:
    """Insert ``canonical`` as a new block immediately after the anchor block.

    Places the canonical block (separated by a single blank line) right after the
    ``anchor_heading`` block's last content line, preserving whatever followed it.
    Returns the new text, or ``None`` if the anchor heading is absent (the caller
    then leaves the file untouched rather than guessing a location).
    """
    lines = text_lf.split("\n")
    start = None
    end = None  # exclusive: index of the next "## " heading (or len(lines))
    for i, line in enumerate(lines):
        if start is None:
            if line.rstrip() == anchor_heading:
                start = i
            continue
        if line.startswith("## ") and line.rstrip() != anchor_heading:
            end = i
            break
    if start is None:
        return None
    if end is None:
        end = len(lines)
    # Trim trailing blank lines of the anchor block so we insert right after its
    # last content line, then re-introduce exactly one blank separator.
    last = end
    while last - 1 > start and lines[last - 1].strip() == "":
        last -= 1
    canon_lines = canonical.split("\n")
    new_lines = lines[:last] + [""] + canon_lines + lines[last:]
    return "\n".join(new_lines)


def _process_file(path: pathlib.Path, dry_run: bool) -> bool:
    """Sync all standard blocks in a single (standard) agent file.

    Returns ``True`` if the file changed (or, in ``dry_run``, would change).
    """
    text_lf, newline, trailing = _read(path)
    stem = path.stem
    changed = False
    for block_id, spec in blocks.BLOCKS.items():
        if stem not in spec["standard_agents"]:
            continue  # variant or not-applicable -> never touch
        heading = spec["heading"]
        canonical = spec["canonical"]
        present = blocks.extract_block(text_lf, heading) is not None
        anchor = spec.get("insert_after_heading")
        if not present and anchor:
            # A standard agent that lacks an insert-mode block gets it placed after
            # the named anchor. Once present, subsequent runs take the replace path
            # below and find it already exact (idempotent).
            new = _insert_block_after(text_lf, anchor, canonical)
        elif spec["match"] == blocks.MATCH_PREFIX:
            new = _replace_prefix_block(text_lf, heading, canonical)
        else:
            new = _replace_equals_block(text_lf, heading, canonical)
        if new is not None and new != text_lf:
            text_lf = new
            changed = True
    if not changed:
        return False
    # preserve trailing-newline state
    if trailing and not text_lf.endswith("\n"):
        text_lf += "\n"
    if dry_run:
        return True
    return _write_if_changed(path, text_lf, newline)


def find_drift(agents_dir: pathlib.Path) -> List[str]:
    """Return the sorted stems of standard agents whose blocks are out of sync."""
    drifted = []
    for path in sorted(pathlib.Path(agents_dir).glob("*.md")):
        if _process_file(path, dry_run=True):
            drifted.append(path.stem)
    return sorted(drifted)


def sync(agents_dir: pathlib.Path) -> List[str]:
    """Rewrite drifted standard agents in place. Returns sorted changed stems."""
    changed = []
    for path in sorted(pathlib.Path(agents_dir).glob("*.md")):
        if _process_file(path, dry_run=False):
            changed.append(path.stem)
    return sorted(changed)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync duplicated agent boilerplate blocks to the canonical source of truth."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift without writing; exit non-zero if any standard agent is out of sync.",
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
        drifted = find_drift(agents_dir)
        if drifted:
            print(f"DRIFT: {len(drifted)} standard agent file(s) out of sync with the canonical blocks:")
            for stem in drifted:
                print(f"  - {stem}.md")
            print("Run `python scripts/setup/sync_agent_boilerplate.py` to fix.")
            return 1
        print(f"IN SYNC: all standard agents match the canonical blocks ({agents_dir}).")
        return 0

    changed = sync(agents_dir)
    if changed:
        print(f"Rewrote {len(changed)} agent file(s) to match the canonical blocks:")
        for stem in changed:
            print(f"  - {stem}.md")
    else:
        print("0 files changed (already in sync).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
