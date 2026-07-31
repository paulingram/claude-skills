# -*- coding: utf-8 -*-
"""Spec fingerprint — the v3.47.0 mid-run spec-currency seam.

The orchestrator owns spec currency WHILE agents read it. A teammate briefed at
Phase 2 dispatch reads `openspec/changes/<slug>/`; if the orchestrator amends an
artifact afterwards, the teammate is building against a superseded spec and
nothing today notices. This module is the one seam that makes the question
decidable: a content-addressed fingerprint of the change directory, stamped into
each teammate manifest at dispatch (`spec_fingerprint`) and recomputed by the
Stop-audit arm `_audit_spec_currency` in `hooks/pipeline-completion-audit.py`.

The algorithm is PINNED, because a Windows-stamped manifest must compare equal
to a POSIX recompute of identical content:

  * every file under the change dir, recursively, sorted by its POSIX-style
    path relative to the change dir (forward slashes on every platform);
  * per file, the hash absorbs
    ``relpath.encode("utf-8") + b"\\x00" + <raw file bytes> + b"\\x01"``;
  * the result is the SHA-256 hexdigest.

Content-addressed, not stat-addressed: rewriting identical bytes does not move
the value (a no-op save is not an amendment), while any content, path, addition,
or deletion change does. Bytes are hashed raw — never decoded — so a binary
artifact in the change dir is just more material, and line endings are part of
the content (a checkout whose EOLs differ IS a different byte state).

Fail-open by construction: an absent or non-directory path yields ``None``, so a
pre-upgrade workspace, a non-openspec run, or a deleted change dir can never be
flagged stale. Stdlib-only; no import-time side effects; never writes.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List, Optional

#: Framing bytes between a file's relative path and its content, and between
#: consecutive files. They make the concatenation unambiguous — without them,
#: `a/b` + `c` and `a` + `b/c` would hash identically.
_PATH_CONTENT_SEP = b"\x00"
_FILE_SEP = b"\x01"

#: Absorbed in place of a file's bytes when they cannot be read, so an
#: unreadable file and a DELETED one produce different fingerprints.
_UNREADABLE_SENTINEL = b"\x02<unreadable>"


def _as_dir(change_dir) -> Optional[Path]:
    """The change dir as a Path, or None when it is absent / not a directory.

    A BLANK string is absent, not the current directory (B8, adversarial):
    ``Path("")`` is ``Path(".")``, whose ``is_dir()`` is True — so a caller
    passing an unset value silently fingerprinted the whole working tree, which
    from a repo root is both a wrong answer and an unbounded walk inside a hook
    with no timeout."""
    if change_dir is None:
        return None
    if isinstance(change_dir, str) and not change_dir.strip():
        return None
    try:
        path = Path(change_dir)
        return path if path.is_dir() else None
    except (TypeError, ValueError, OSError):
        return None


def _is_reparse_point(path: Path) -> bool:
    """True for a symlink or a Windows junction/reparse point.

    The walk must not follow these: a link inside a change dir would pull
    outside material into the fingerprint, and a self-referential one recursed
    until MAX_PATH stopped it rather than by design (P2, adversarial). POSIX
    symlinks are caught by ``islink``; Windows junctions are not, so the
    reparse-tag on ``lstat`` is consulted where the platform exposes it."""
    try:
        if path.is_symlink():
            return True
        return bool(getattr(path.lstat(), "st_reparse_tag", 0))
    except OSError:
        return False


def spec_files(change_dir) -> List[str]:
    """The change dir's files as POSIX-style relative paths, sorted.

    The deterministic file list the fingerprint WALKS — exposed so an audit
    message or a doc can name what was covered. A file listed here whose bytes
    turn out to be unreadable still contributes to the fingerprint (as its path
    plus an unreadable sentinel), so the list is the walk's inventory rather
    than a promise that every entry's contents were absorbed. Returns ``[]`` for
    a missing / unreadable directory (fail-open, same posture as
    :func:`compute_spec_fingerprint`).

    Symlinked / junctioned subdirectories are NOT descended into (see
    :func:`_is_reparse_point`).
    """
    root = _as_dir(change_dir)
    if root is None:
        return []
    rels: List[str] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune reparse points in place so the walk never leaves the tree.
            dirnames[:] = sorted(
                d for d in dirnames if not _is_reparse_point(Path(dirpath) / d)
            )
            for name in filenames:
                entry = Path(dirpath) / name
                if _is_reparse_point(entry):
                    continue
                try:
                    rels.append(entry.relative_to(root).as_posix())
                except ValueError:  # pragma: no cover - relative_to cannot fail here
                    continue
    except OSError:
        return []
    return sorted(rels)


def compute_spec_fingerprint(change_dir) -> Optional[str]:
    """SHA-256 fingerprint of an OpenSpec change directory's content.

    Returns the 64-character hexdigest, or ``None`` when ``change_dir`` is
    missing / not a directory / unreadable — the fail-open value every caller
    treats as "cannot judge currency, do not flag".

    An existing-but-empty directory is a real (degenerate) state and hashes to
    the digest of no material rather than ``None``.
    """
    root = _as_dir(change_dir)
    if root is None:
        return None
    digest = hashlib.sha256()
    for rel in spec_files(root):
        digest.update(rel.encode("utf-8"))
        digest.update(_PATH_CONTENT_SEP)
        try:
            digest.update((root / rel).read_bytes())
        except OSError:
            # A file that vanished mid-walk or is locked cannot contribute its
            # BYTES — but its PATH still must (B7, adversarial). Skipping the
            # whole entry made an unreadable file hash identically to a deleted
            # one, so deleting a file that happened to be locked at stamp time
            # was an invisible amendment. The sentinel keeps the two states
            # distinct while the fingerprint still degrades rather than raising
            # inside a Stop hook.
            digest.update(_UNREADABLE_SENTINEL)
        digest.update(_FILE_SEP)
    return digest.hexdigest()


def fingerprints_match(stamped: object, current: object) -> bool:
    """True when a manifest's stamped fingerprint equals the current one.

    Only two real strings can match: a missing / non-string stamp (a pre-upgrade
    manifest) or an uncomputable current value never compares equal, so the
    caller's fail-open branch is a plain ``not fingerprints_match(...)`` guard
    only after it has confirmed both values exist.
    """
    if not isinstance(stamped, str) or not isinstance(current, str):
        return False
    return stamped.strip() == current.strip() and bool(stamped.strip())
