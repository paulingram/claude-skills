"""A6 (review-remediation): scripts/setup/worktree_lifecycle.py exposes a
minimal argparse `__main__` with a `cleanup-merged` subcommand so the two
`worktree_lifecycle.py cleanup-merged --against origin/main` command
invocations (visual-to-api.md, classify-test-prod-safety.md) actually run
instead of silently no-opping (the module previously had no CLI).

Acceptance (REQUIREMENTS A6 / coverage-map A6):
  - `worktree_lifecycle.py cleanup-merged --against origin/main --dry-run`
    prints a one-line summary.
  - The CLI exits 0 even on a cleanup error (v1.3.0 never-block rule).
  - The subcommand delegates to cleanup_merged_worktrees(against=, dry_run=).

These run the module as a real subprocess from a temp cwd that is NOT a git
repo, so the cleanup helper hits its best-effort empty-list path — the CLI must
still print a clean one-line summary and exit 0.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKTREE_LIFECYCLE = REPO_ROOT / "scripts" / "setup" / "worktree_lifecycle.py"


def _run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WORKTREE_LIFECYCLE), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )


def test_module_file_exists() -> None:
    assert WORKTREE_LIFECYCLE.exists(), f"{WORKTREE_LIFECYCLE} missing"


def test_cleanup_merged_dry_run_prints_summary_and_exits_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        # td is NOT a git repo -> cleanup_merged_worktrees returns [] best-effort.
        r = _run(["cleanup-merged", "--against", "origin/main", "--dry-run"], cwd=td)
    assert r.returncode == 0, f"expected exit 0, got {r.returncode}; stderr={r.stderr!r}"
    assert "Traceback" not in (r.stderr or ""), f"traceback: {r.stderr!r}"
    out = (r.stdout or "")
    assert "cleanup-merged" in out, f"missing one-line summary: stdout={out!r}"
    # Dry-run mode wording per the design's main() template.
    assert "would be" in out.lower() or "0 worktree" in out.lower(), (
        f"dry-run summary not recognizable: {out!r}"
    )


def test_cleanup_merged_default_against_exits_zero() -> None:
    """The exact two-command-file invocation (no --dry-run) also exits 0 cleanly
    from a non-repo cwd — the never-block rule."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(["cleanup-merged", "--against", "origin/main"], cwd=td)
    assert r.returncode == 0, f"expected exit 0, got {r.returncode}; stderr={r.stderr!r}"
    assert "Traceback" not in (r.stderr or ""), f"traceback: {r.stderr!r}"
    assert "cleanup-merged" in (r.stdout or ""), f"no summary: {r.stdout!r}"


def test_cli_exits_zero_even_when_cleanup_raises(monkeypatch) -> None:
    """Best-effort: a cleanup-helper exception must NOT propagate to a nonzero
    exit. Monkeypatch the helper to raise and assert main() still returns 0."""
    sys.path.insert(0, str(WORKTREE_LIFECYCLE.parent))
    try:
        import worktree_lifecycle  # type: ignore

        def _boom(*a, **k):
            raise RuntimeError("cleanup exploded")

        monkeypatch.setattr(worktree_lifecycle, "cleanup_merged_worktrees", _boom)
        rc = worktree_lifecycle.main(["cleanup-merged", "--against", "origin/main"])
        assert rc == 0, f"main() must return 0 even when cleanup raises; got {rc}"
    finally:
        sys.path.remove(str(WORKTREE_LIFECYCLE.parent))


def test_cli_delegates_to_cleanup_with_against_and_dry_run(monkeypatch) -> None:
    """The subcommand must call cleanup_merged_worktrees(against=, dry_run=)."""
    sys.path.insert(0, str(WORKTREE_LIFECYCLE.parent))
    try:
        import worktree_lifecycle  # type: ignore

        seen = {}

        def _spy(against="origin/main", dry_run=False, **k):
            seen["against"] = against
            seen["dry_run"] = dry_run
            return []

        monkeypatch.setattr(worktree_lifecycle, "cleanup_merged_worktrees", _spy)
        rc = worktree_lifecycle.main(
            ["cleanup-merged", "--against", "develop", "--dry-run"]
        )
        assert rc == 0
        assert seen.get("against") == "develop", f"against not forwarded: {seen}"
        assert seen.get("dry_run") is True, f"dry_run not forwarded: {seen}"
    finally:
        sys.path.remove(str(WORKTREE_LIFECYCLE.parent))


def test_unknown_subcommand_is_not_a_silent_noop() -> None:
    """argparse must reject an unknown subcommand (exit nonzero) — the E1
    'not a silent no-op' contract."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(["bogus-subcommand"], cwd=td)
    assert r.returncode != 0, (
        f"unknown subcommand silently accepted (exit {r.returncode}); "
        f"stdout={r.stdout!r} stderr={r.stderr!r}"
    )
