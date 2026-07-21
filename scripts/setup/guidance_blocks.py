#!/usr/bin/env python3
"""guidance_blocks.py — capability-gated, self-removing CLAUDE.md guidance blocks.

A small stdlib-only helper the installers (`install_mempalace.py` /
`install_librarian.py` / `install_gateway.py`) use to write a short, fenced
"how to use this capability" block into a target project's CLAUDE.md when the
capability is verified installed, and to remove exactly that block again when
the capability is uninstalled, purged, or a capability check finds it absent.

The block is delimited by an HTML-comment fence pair keyed on the capability:

    <!-- ct6:guidance:<capability>:begin -->
    ...guidance body...
    <!-- ct6:guidance:<capability>:end -->

Contract:
  * upsert_block  — replaces an existing block IN PLACE (byte-preserving every
    byte outside the fences), or appends a new block; creates CLAUDE.md only
    when create=True. Idempotent: re-running with the same body writes nothing.
  * remove_block  — deletes exactly the fenced block (both fences inclusive)
    plus a single trailing-newline normalization, byte-preserving everything
    else. A missing file or missing block is a no-op.
  * Writes are atomic (tmp file + os.replace) and byte-exact (binary I/O, so a
    file's existing CRLF / trailing-whitespace bytes are never rewritten).
  * ASCII-safe: the emitted fences + wrapper are ASCII; the capability slug is
    validated to a conservative ASCII token so it can never break a fence.

Nothing here imports anything outside the standard library and the module has
no import-time side effects.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Union

# A conservative ASCII slug: lowercase letters / digits / hyphen / underscore,
# starting with an alphanumeric. This is validated (never silently rewritten)
# so a caller-supplied capability can never inject a broken/partial fence.
_CAPABILITY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

PathLike = Union[str, "os.PathLike[str]"]


def _validate_capability(capability: str) -> None:
    if not isinstance(capability, str) or not _CAPABILITY_RE.match(capability):
        raise ValueError(
            f"invalid capability slug {capability!r}: expected an ASCII token "
            f"matching {_CAPABILITY_RE.pattern}"
        )


def block_fences(capability: str) -> tuple[str, str]:
    """Return the (begin, end) HTML-comment fences for a capability slug."""
    _validate_capability(capability)
    return (
        f"<!-- ct6:guidance:{capability}:begin -->",
        f"<!-- ct6:guidance:{capability}:end -->",
    )


def _read_text(path: Path) -> Optional[str]:
    """Return the file's decoded text, or None if it does not exist. Binary read
    + explicit utf-8 decode so newline bytes (CRLF included) are preserved
    verbatim — universal-newline text mode would rewrite them."""
    try:
        return path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return None


def _atomic_write(path: Path, text: str) -> None:
    """Write text to path atomically (tmp file in the same dir + os.replace).
    Encodes utf-8 with no newline translation, so only the bytes we constructed
    are written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".ct6tmp"
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _find_block(text: str, begin: str, end: str) -> Optional[tuple[int, int]]:
    """Return the (start, stop) character span of a well-formed block — from the
    first character of the begin fence through the last character of the end
    fence — or None. A begin without a following end (or an end without a
    preceding begin) is treated as absent, never as a partial block."""
    start = text.find(begin)
    if start == -1:
        return None
    end_start = text.find(end, start + len(begin))
    if end_start == -1:
        return None
    return start, end_start + len(end)


def _render_block(begin: str, body: str, end: str) -> str:
    """Wrap the body between the fences on their own lines. Leading/trailing
    blank lines in the body are trimmed so the block shape is deterministic;
    internal structure is preserved."""
    inner = body.strip("\n")
    return f"{begin}\n{inner}\n{end}"


def upsert_block(
    claude_md_path: PathLike,
    capability: str,
    body: str,
    *,
    create: bool = False,
) -> bool:
    """Insert or replace the capability's guidance block in claude_md_path.

    If the block already exists it is replaced IN PLACE — every byte outside the
    fence pair is preserved exactly. Otherwise the block is appended, separated
    from any existing content by one blank line. When the file does not exist it
    is created only if create=True (else this is a no-op).

    Returns True iff the file was written (created or changed); False when no
    write was needed — a missing file with create=False, or an idempotent
    re-upsert whose result is byte-identical to what is already on disk.
    """
    begin, end = block_fences(capability)
    path = Path(claude_md_path)
    text = _read_text(path)
    block = _render_block(begin, body, end)

    if text is None:
        if not create:
            return False
        _atomic_write(path, block + "\n")
        return True

    span = _find_block(text, begin, end)
    if span is not None:
        new_text = text[: span[0]] + block + text[span[1]:]
    elif text == "":
        new_text = block + "\n"
    elif text.endswith("\n"):
        new_text = text + "\n" + block + "\n"
    else:
        new_text = text + "\n\n" + block + "\n"

    if new_text == text:
        return False
    _atomic_write(path, new_text)
    return True


def remove_block(claude_md_path: PathLike, capability: str) -> bool:
    """Remove the capability's guidance block from claude_md_path.

    Deletes exactly the fenced block (both fences inclusive) plus a single
    trailing newline immediately after the end fence, byte-preserving every
    other byte. A missing file, or a file with no such block, is a no-op.

    Returns True iff a block was removed (the file was written); False otherwise.
    """
    begin, end = block_fences(capability)
    path = Path(claude_md_path)
    text = _read_text(path)
    if text is None:
        return False

    span = _find_block(text, begin, end)
    if span is None:
        return False

    before = text[: span[0]]
    after = text[span[1]:]
    # One trailing-newline normalization: drop a single newline that immediately
    # follows the end fence (the boundary newline the block sat on) so removal
    # does not leave a dangling blank line where the block used to be.
    if after.startswith("\n"):
        after = after[1:]
    new_text = before + after
    if new_text == text:
        return False
    _atomic_write(path, new_text)
    return True
