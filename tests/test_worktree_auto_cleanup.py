"""REQ-1 (v1.3.0): auto-cleanup of merged architect-team worktrees.

Exercises the two new helpers in `scripts/setup/worktree_lifecycle.py`:
  - list_merged_architect_team_worktrees(against="origin/main", exclude_current=True) -> list[Path]
  - cleanup_merged_worktrees(against="origin/main", dry_run=False) -> list[Path]

Test discipline matches `tests/test_worktree_lifecycle.py` (v1.2.0) and
`tests/test_worktree_state_resolution.py` (v1.1.0): real `git init` +
`git worktree add` subprocesses, no mocks of git. Each test creates its own
isolated git repo in `tmp_path`; paths are `.resolve()`'d for macOS
/private/var vs /var symlink safety.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from tests.helpers.module_loader import load_module


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def worktree_lifecycle_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/worktree_lifecycle.py via importlib."""
    path = plugin_root / "scripts" / "setup" / "worktree_lifecycle.py"
    assert path.exists(), f"worktree_lifecycle.py missing at {path}"
    mod = load_module(path, "worktree_lifecycle_module_v13")
    return mod


# ---- Test fixtures -----------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a subprocess synchronously, capturing output, raising on non-zero."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_main_repo(repo_dir: Path) -> None:
    """Initialize a fresh git repo with one commit on `main`.

    Also creates a local `origin/main` ref pointing at the initial commit so
    `git merge-base --is-ancestor <branch> origin/main` works without a real
    network remote. We achieve this by adding `.` itself as the `origin`
    remote and fetching — git happily resolves a local path as a remote URL.
    """
    repo_dir.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--initial-branch=main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test User"])
    (repo_dir / "README.md").write_text("# test repo\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "init"])
    # Self-remote: register the repo's own path as `origin` and fetch so
    # `origin/main` becomes a valid remote-tracking ref.
    _run(["git", "-C", str(repo_dir), "remote", "add", "origin", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "fetch", "origin"])


def _refresh_origin(repo_dir: Path) -> None:
    """Re-fetch `origin` so `origin/main` reflects the latest local `main`."""
    _run(["git", "-C", str(repo_dir), "fetch", "origin"])


def _create_worktree_on_branch(
    repo_dir: Path, worktree_path: Path, branch: str
) -> None:
    """Create a new branch + worktree off `main`."""
    _run(
        [
            "git",
            "-C",
            str(repo_dir),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
            "main",
        ]
    )


def _merge_branch_into_main(repo_dir: Path, branch: str) -> None:
    """Fast-forward (or merge-commit) `branch` into `main` in the main repo.

    Adds a commit on the branch first so `main` actually advances, then
    fast-forwards. Refreshes `origin/main` afterward so the merge-base
    probe sees the new tip.
    """
    # Make a commit on the branch's worktree so it's strictly ahead of main.
    # We do this in the main repo by checking the branch out for a moment
    # is not safe (it's checked out in a worktree). Use `git -C` against the
    # worktree directly.
    # We don't know the worktree path here; the caller arranges to commit on
    # the branch BEFORE calling this helper. This helper just does the
    # fast-forward in the main repo.
    _run(["git", "-C", str(repo_dir), "merge", "--no-ff", branch, "-m", f"merge {branch}"])
    _refresh_origin(repo_dir)


def _commit_in_worktree(worktree_path: Path, message: str = "work") -> None:
    """Add a file in the worktree and commit it."""
    (worktree_path / f"{message}.txt").write_text(f"{message}\n", encoding="utf-8")
    _run(["git", "-C", str(worktree_path), "add", "."])
    _run(["git", "-C", str(worktree_path), "commit", "-m", message])


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    """A freshly-initialized git repo with one commit on `main` and origin/main."""
    repo_dir = (tmp_path / "main-repo").resolve()
    _init_main_repo(repo_dir)
    return repo_dir


# ---- REQ-1 Scenario 1: merged identification --------------------------------


def test_list_merged_returns_only_merged_branches(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Two worktrees on architect-team/foo (un-merged) and architect-team/bar
    (merged) -> list_merged returns only bar's path."""
    foo_path = (tmp_path / "main-repo-foo").resolve()
    bar_path = (tmp_path / "main-repo-bar").resolve()

    _create_worktree_on_branch(main_repo, foo_path, "architect-team/foo")
    _create_worktree_on_branch(main_repo, bar_path, "architect-team/bar")

    # Add work on both branches so they're each strictly ahead of main.
    _commit_in_worktree(foo_path, "foo-work")
    _commit_in_worktree(bar_path, "bar-work")

    # Merge ONLY bar into main; refresh origin/main.
    _merge_branch_into_main(main_repo, "architect-team/bar")

    # Run helper from the main repo (so it's not "current" for any worktree).
    monkeypatch.chdir(main_repo)
    merged = worktree_lifecycle_module.list_merged_architect_team_worktrees()
    merged_resolved = {p.resolve() for p in merged}

    assert bar_path in merged_resolved, (
        f"expected {bar_path} in merged list, got {merged_resolved}"
    )
    assert foo_path not in merged_resolved, (
        f"un-merged {foo_path} should NOT be in merged list, got {merged_resolved}"
    )


# ---- REQ-1 Scenario 2: exclude_current safeguard ----------------------------


def test_exclude_current_excludes_or_includes_correctly(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """exclude_current=True excludes current worktree (even if its branch IS
    merged); exclude_current=False includes it."""
    current_path = (tmp_path / "main-repo-current").resolve()
    _create_worktree_on_branch(main_repo, current_path, "architect-team/current")
    _commit_in_worktree(current_path, "current-work")
    _merge_branch_into_main(main_repo, "architect-team/current")

    # cwd INSIDE the current worktree (which IS merged).
    monkeypatch.chdir(current_path)

    excluded = worktree_lifecycle_module.list_merged_architect_team_worktrees(
        exclude_current=True
    )
    excluded_resolved = {p.resolve() for p in excluded}
    assert current_path not in excluded_resolved, (
        f"exclude_current=True must omit current worktree {current_path}; "
        f"got {excluded_resolved}"
    )

    included = worktree_lifecycle_module.list_merged_architect_team_worktrees(
        exclude_current=False
    )
    included_resolved = {p.resolve() for p in included}
    assert current_path in included_resolved, (
        f"exclude_current=False must include the merged current worktree "
        f"{current_path}; got {included_resolved}"
    )


# ---- REQ-1 Scenario 3: non-architect-team branches ignored ------------------


def test_non_architect_team_branches_ignored(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A non-architect-team branch (e.g., feature/x) is ignored regardless of
    merge state."""
    feature_path = (tmp_path / "main-repo-feature").resolve()
    _create_worktree_on_branch(main_repo, feature_path, "feature/x")
    _commit_in_worktree(feature_path, "feature-work")
    _merge_branch_into_main(main_repo, "feature/x")

    monkeypatch.chdir(main_repo)
    merged = worktree_lifecycle_module.list_merged_architect_team_worktrees()
    merged_resolved = {p.resolve() for p in merged}

    assert feature_path not in merged_resolved, (
        f"non-architect-team branch worktree {feature_path} must NEVER appear "
        f"in the merged list (even when merged into origin/main); got "
        f"{merged_resolved}"
    )


# ---- REQ-1 Scenario 4: cleanup actually removes the merged worktree ---------


def test_cleanup_merged_worktrees_removes_filesystem(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """cleanup_merged_worktrees actually removes the merged worktree from the
    filesystem (and returns its path)."""
    merged_path = (tmp_path / "main-repo-merged").resolve()
    _create_worktree_on_branch(main_repo, merged_path, "architect-team/merged")
    _commit_in_worktree(merged_path, "merged-work")
    _merge_branch_into_main(main_repo, "architect-team/merged")

    assert merged_path.is_dir(), "precondition: merged worktree exists on disk"

    monkeypatch.chdir(main_repo)
    cleaned = worktree_lifecycle_module.cleanup_merged_worktrees()
    cleaned_resolved = {p.resolve() for p in cleaned}

    assert merged_path in cleaned_resolved, (
        f"expected {merged_path} in cleaned list, got {cleaned_resolved}"
    )
    assert not merged_path.exists(), (
        f"cleanup_merged_worktrees should have removed {merged_path} from disk"
    )


# ---- REQ-1 Scenario 5: dry_run preview leaves filesystem untouched ----------


def test_cleanup_merged_worktrees_dry_run_does_not_touch_filesystem(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """cleanup_merged_worktrees(dry_run=True) returns the candidate list but
    leaves the filesystem untouched."""
    merged_path = (tmp_path / "main-repo-dry-merged").resolve()
    _create_worktree_on_branch(main_repo, merged_path, "architect-team/dry-merged")
    _commit_in_worktree(merged_path, "dry-merged-work")
    _merge_branch_into_main(main_repo, "architect-team/dry-merged")

    assert merged_path.is_dir(), "precondition: merged worktree exists on disk"

    monkeypatch.chdir(main_repo)
    preview = worktree_lifecycle_module.cleanup_merged_worktrees(dry_run=True)
    preview_resolved = {p.resolve() for p in preview}

    assert merged_path in preview_resolved, (
        f"dry_run preview must include {merged_path}; got {preview_resolved}"
    )
    assert merged_path.is_dir(), (
        f"dry_run=True must NOT remove {merged_path} from disk; it should "
        f"still exist after the call"
    )


# ---- REQ-1 Scenario 6: end-to-end integration -------------------------------


def test_end_to_end_cleanup_only_removes_merged(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end: create 2 worktrees, merge one to main, call cleanup, assert
    only the merged one is gone (covers list + cleanup + isolation)."""
    keep_path = (tmp_path / "main-repo-keep").resolve()
    drop_path = (tmp_path / "main-repo-drop").resolve()

    _create_worktree_on_branch(main_repo, keep_path, "architect-team/keep")
    _create_worktree_on_branch(main_repo, drop_path, "architect-team/drop")

    _commit_in_worktree(keep_path, "keep-work")
    _commit_in_worktree(drop_path, "drop-work")

    # Merge ONLY the drop branch.
    _merge_branch_into_main(main_repo, "architect-team/drop")

    monkeypatch.chdir(main_repo)
    cleaned = worktree_lifecycle_module.cleanup_merged_worktrees()
    cleaned_resolved = {p.resolve() for p in cleaned}

    # Only the dropped worktree should have been cleaned.
    assert cleaned_resolved == {drop_path}, (
        f"expected exactly {{{drop_path}}} cleaned, got {cleaned_resolved}"
    )
    # Filesystem assertions.
    assert not drop_path.exists(), (
        f"merged worktree {drop_path} should have been removed"
    )
    assert keep_path.is_dir(), (
        f"un-merged worktree {keep_path} must remain on disk"
    )
