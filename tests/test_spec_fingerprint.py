# -*- coding: utf-8 -*-
"""Tests for hooks/spec_fingerprint.py (v3.47.0 — spec-currency-mid-run).

The fingerprint answers one question deterministically: *is the spec state a
teammate was briefed against still the spec state on disk?* It is stamped into
every teammate manifest at dispatch (`spec_fingerprint`) and recomputed by the
Stop-audit arm `_audit_spec_currency`, so the two MUST agree bit-for-bit across
platforms — hence the pinned framing (posix relpath + NUL + raw content + SOH,
files sorted by posix relpath) and the separator-independence tests below.

Fail-open by construction: a missing / non-directory change dir yields None, so
a pre-upgrade or non-openspec workspace can never be flagged stale.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hooks.spec_fingerprint import compute_spec_fingerprint, spec_files


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def change_dir(tmp_path: Path) -> Path:
    """A miniature openspec change directory."""
    d = tmp_path / "openspec" / "changes" / "some-change"
    _write(d / "proposal.md", "# Proposal\n\nWhy.\n")
    _write(d / "tasks.md", "- [ ] 1.1 do the thing\n")
    _write(d / "specs" / "cap-a" / "spec.md", "## ADDED Requirements\n")
    return d


# --------------------------------------------------------------------------- #
# stability + sensitivity
# --------------------------------------------------------------------------- #

def test_fingerprint_is_content_stable(change_dir: Path) -> None:
    """Scenario: fingerprint is content-stable — two computes, one value."""
    assert compute_spec_fingerprint(change_dir) == compute_spec_fingerprint(change_dir)


def test_fingerprint_is_a_sha256_hexdigest(change_dir: Path) -> None:
    fp = compute_spec_fingerprint(change_dir)
    assert isinstance(fp, str) and len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_moves_on_amendment(change_dir: Path) -> None:
    """Scenario: fingerprint moves on amendment — the whole point of the gate."""
    before = compute_spec_fingerprint(change_dir)
    _write(change_dir / "proposal.md", "# Proposal\n\nWhy, amended.\n")
    assert compute_spec_fingerprint(change_dir) != before


def test_fingerprint_moves_on_one_character_amendment(change_dir: Path) -> None:
    before = compute_spec_fingerprint(change_dir)
    p = change_dir / "specs" / "cap-a" / "spec.md"
    p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert compute_spec_fingerprint(change_dir) != before


def test_fingerprint_moves_on_added_file(change_dir: Path) -> None:
    before = compute_spec_fingerprint(change_dir)
    _write(change_dir / "design.md", "# Design\n")
    assert compute_spec_fingerprint(change_dir) != before


def test_fingerprint_moves_on_removed_file(change_dir: Path) -> None:
    before = compute_spec_fingerprint(change_dir)
    (change_dir / "tasks.md").unlink()
    assert compute_spec_fingerprint(change_dir) != before


def test_fingerprint_moves_when_content_moves_between_files(change_dir: Path) -> None:
    """The relpath is part of the hashed material — identical bytes at a
    different path is a different spec state."""
    before = compute_spec_fingerprint(change_dir)
    body = (change_dir / "tasks.md").read_text(encoding="utf-8")
    (change_dir / "tasks.md").unlink()
    _write(change_dir / "specs" / "tasks.md", body)
    assert compute_spec_fingerprint(change_dir) != before


def test_fingerprint_ignores_mtime(change_dir: Path) -> None:
    """Content-addressed, not stat-addressed: rewriting identical bytes (a new
    mtime) must NOT move the fingerprint, or every no-op save would look like an
    amendment."""
    before = compute_spec_fingerprint(change_dir)
    p = change_dir / "proposal.md"
    p.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    assert compute_spec_fingerprint(change_dir) == before


def test_fingerprint_ignores_creation_order(tmp_path: Path) -> None:
    """Files are sorted by posix relpath before hashing, so the order the
    directory happens to enumerate them in cannot change the value."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write(a / "proposal.md", "P\n")
    _write(a / "specs" / "x" / "spec.md", "S\n")
    _write(b / "specs" / "x" / "spec.md", "S\n")
    _write(b / "proposal.md", "P\n")
    assert compute_spec_fingerprint(a) == compute_spec_fingerprint(b)


# --------------------------------------------------------------------------- #
# separator independence + the pinned framing
# --------------------------------------------------------------------------- #

def test_fingerprint_matches_the_documented_framing(tmp_path: Path) -> None:
    """The algorithm is pinned: for each file in posix-relpath order,
    ``relpath.encode() + b"\\x00" + content_bytes + b"\\x01"``; SHA-256 hexdigest.

    Nested paths are hashed with FORWARD slashes on every platform — that is
    what makes a Windows-stamped manifest comparable to a POSIX recompute.

    Written as BYTES, not text: text mode would translate ``\\n`` to ``\\r\\n``
    on Windows and the expected material below would no longer be what is on
    disk. (That the two differ is itself the contract — line endings are part of
    the content.)"""
    d = tmp_path / "change"
    (d / "specs" / "cap").mkdir(parents=True)
    (d / "proposal.md").write_bytes(b"P\n")
    (d / "specs" / "cap" / "spec.md").write_bytes(b"S\n")

    h = hashlib.sha256()
    for rel, content in (
        ("proposal.md", b"P\n"),
        ("specs/cap/spec.md", b"S\n"),
    ):
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(content)
        h.update(b"\x01")
    assert compute_spec_fingerprint(d) == h.hexdigest()


def test_spec_files_returns_sorted_posix_relpaths(change_dir: Path) -> None:
    assert spec_files(change_dir) == [
        "proposal.md",
        "specs/cap-a/spec.md",
        "tasks.md",
    ]


def test_spec_files_of_missing_dir_is_empty(tmp_path: Path) -> None:
    assert spec_files(tmp_path / "nope") == []


def test_identical_trees_in_different_parents_match(tmp_path: Path) -> None:
    """Only the paths RELATIVE to the change dir are hashed — the absolute
    location (a worktree vs the main checkout) must not matter."""
    a = tmp_path / "wt-one" / "openspec" / "changes" / "c"
    b = tmp_path / "another" / "place" / "c"
    for root in (a, b):
        _write(root / "proposal.md", "P\n")
        _write(root / "specs" / "cap" / "spec.md", "S\n")
    assert compute_spec_fingerprint(a) == compute_spec_fingerprint(b)


# --------------------------------------------------------------------------- #
# fail-open + robustness
# --------------------------------------------------------------------------- #

def test_missing_dir_returns_none(tmp_path: Path) -> None:
    assert compute_spec_fingerprint(tmp_path / "does-not-exist") is None


def test_file_instead_of_dir_returns_none(tmp_path: Path) -> None:
    f = tmp_path / "proposal.md"
    f.write_text("not a directory\n", encoding="utf-8")
    assert compute_spec_fingerprint(f) is None


def test_none_input_returns_none() -> None:
    assert compute_spec_fingerprint(None) is None


def test_empty_dir_returns_the_empty_digest(tmp_path: Path) -> None:
    """An existing-but-empty change dir is a real (degenerate) state, not an
    error: it hashes deterministically to the digest of no material."""
    d = tmp_path / "empty"
    d.mkdir()
    assert compute_spec_fingerprint(d) == hashlib.sha256().hexdigest()


def test_non_utf8_bytes_do_not_raise(tmp_path: Path) -> None:
    """Spec dirs can carry an image or a binary fixture; the fingerprint reads
    bytes, never text, so an undecodable file is just more material."""
    d = tmp_path / "change"
    d.mkdir()
    (d / "proposal.md").write_text("P\n", encoding="utf-8")
    (d / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\xfd")
    assert isinstance(compute_spec_fingerprint(d), str)


def test_accepts_a_string_path(change_dir: Path) -> None:
    assert compute_spec_fingerprint(str(change_dir)) == compute_spec_fingerprint(change_dir)


# --------------------------------------------------------------------------- #
# B8 (adversarial, low): a blank path must fail open, not fingerprint the CWD
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
def test_blank_string_returns_none(blank: str) -> None:
    """`Path("")` is `Path(".")`, whose is_dir() is True — so a blank argument
    silently walked the CURRENT WORKING DIRECTORY. From a repo root that is both
    a wrong answer and an unbounded walk inside a hook with no timeout."""
    assert compute_spec_fingerprint(blank) is None


def test_blank_string_spec_files_is_empty() -> None:
    assert spec_files("") == []


# --------------------------------------------------------------------------- #
# B7 (adversarial, low): an unreadable file must not hash like a deleted one
# --------------------------------------------------------------------------- #

def test_unreadable_file_differs_from_a_deleted_file(tmp_path: Path) -> None:
    """The OSError branch skipped the file entirely — dropping its PATH as well
    as its bytes — so deleting a file that was locked at stamp time was an
    invisible amendment. Simulated here by monkeypatching the read, since a
    portable exclusive lock is not available on every platform."""
    d = tmp_path / "change"
    _write(d / "proposal.md", "P\n")
    _write(d / "locked.md", "L\n")

    real_read_bytes = Path.read_bytes

    def _boom(self: Path, *a, **kw):
        if self.name == "locked.md":
            raise OSError("locked by another process")
        return real_read_bytes(self, *a, **kw)

    import hooks.spec_fingerprint as sf
    original = sf.Path.read_bytes
    try:
        sf.Path.read_bytes = _boom  # type: ignore[assignment]
        with_unreadable = compute_spec_fingerprint(d)
    finally:
        sf.Path.read_bytes = original  # type: ignore[assignment]

    (d / "locked.md").unlink()
    with_deleted = compute_spec_fingerprint(d)
    assert with_unreadable != with_deleted


def test_spec_files_lists_only_what_was_hashed(change_dir: Path) -> None:
    """The docstring promises the list names exactly what the fingerprint was
    computed over; every listed file must be readable material."""
    listed = spec_files(change_dir)
    for rel in listed:
        assert (change_dir / rel).is_file()


# --------------------------------------------------------------------------- #
# P2 (adversarial, adjacent): the walk must not follow reparse points
# --------------------------------------------------------------------------- #

def test_symlinked_directory_is_not_absorbed(tmp_path: Path) -> None:
    """A link inside the change dir must not pull outside material into the
    fingerprint, and a self-referential one must not recurse. Skipped where the
    platform will not create the link without elevation."""
    d = tmp_path / "change"
    _write(d / "proposal.md", "P\n")
    outside = tmp_path / "outside"
    _write(outside / "secret.md", "S\n")
    before = compute_spec_fingerprint(d)
    try:
        (d / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create a directory symlink on this platform/account")
    assert compute_spec_fingerprint(d) == before
