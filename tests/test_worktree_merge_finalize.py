"""REQ-1 (v3.6.0): end-of-run merge check + dual-layout slug derivation.

Exercises the new behavior in `scripts/setup/worktree_lifecycle.py`:
  - finalize_run_worktree(worktree_path=None, against="origin/main", branch=None) -> dict
  - _slug_from_worktree_path dual-layout (old flat + new hidden container)
  - cleanup_merged_worktrees backward-compat across both layouts

Test discipline matches `tests/test_worktree_auto_cleanup.py` (v1.3.0): real
`git init` + self-remote `origin/main` + `git worktree add` subprocesses, no
mocks. Paths are `.resolve()`'d for macOS /private/var vs /var symlink safety;
the helper resolves paths so comparisons are resolved-vs-resolved.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def worktree_lifecycle_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/worktree_lifecycle.py via importlib."""
    path = plugin_root / "scripts" / "setup" / "worktree_lifecycle.py"
    assert path.exists(), f"worktree_lifecycle.py missing at {path}"
    spec = importlib.util.spec_from_file_location(
        "worktree_lifecycle_module_v36", path
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- Test fixtures -----------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_main_repo(repo_dir: Path) -> None:
    """Initialize a fresh git repo with one commit on `main` and origin/main."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--initial-branch=main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test User"])
    (repo_dir / "README.md").write_text("# test repo\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "init"])
    _run(["git", "-C", str(repo_dir), "remote", "add", "origin", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "fetch", "origin"])


def _refresh_origin(repo_dir: Path) -> None:
    _run(["git", "-C", str(repo_dir), "fetch", "origin"])


def _add_worktree(repo_dir: Path, worktree_path: Path, branch: str) -> None:
    """`git worktree add -b <branch> <path> main` (creates leaf + parents)."""
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


def _commit_in_worktree(worktree_path: Path, message: str = "work") -> None:
    (worktree_path / f"{message}.txt").write_text(f"{message}\n", encoding="utf-8")
    _run(["git", "-C", str(worktree_path), "add", "."])
    _run(["git", "-C", str(worktree_path), "commit", "-m", message])


def _merge_branch_into_main(repo_dir: Path, branch: str) -> None:
    _run(["git", "-C", str(repo_dir), "merge", "--no-ff", branch, "-m", f"merge {branch}"])
    _refresh_origin(repo_dir)


def _branch_exists(repo_dir: Path, branch: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
        ],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    """A freshly-initialized git repo with one commit on `main` and origin/main.

    The repo basename is `main-repo`; the new hidden container is therefore
    `<tmp_path>/.main-repo-worktrees/`.
    """
    repo_dir = (tmp_path / "main-repo").resolve()
    _init_main_repo(repo_dir)
    return repo_dir


# ---- finalize_run_worktree: merged -> removes worktree + branch -------------


def test_finalize_removes_merged_worktree_and_branch(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A merged worktree, finalized from the MAIN repo (not inside it), is
    removed from disk and its branch is deleted."""
    container = (tmp_path / ".main-repo-worktrees").resolve()
    worktree_path = (container / "billing").resolve()
    branch = "architect-team/billing"

    _add_worktree(main_repo, worktree_path, branch)
    _commit_in_worktree(worktree_path, "billing-work")
    _merge_branch_into_main(main_repo, branch)

    assert worktree_path.is_dir(), "precondition: merged worktree exists on disk"

    monkeypatch.chdir(main_repo)
    result = worktree_lifecycle_module.finalize_run_worktree(
        worktree_path=worktree_path
    )

    assert result["removed"] is True, result
    assert result["merged"] is True, result
    assert result["reason"] == "merged-removed", result
    assert not worktree_path.exists(), (
        f"finalize should have removed {worktree_path} from disk"
    )
    assert not _branch_exists(main_repo, branch), (
        f"finalize should have deleted branch {branch}"
    )


# ---- finalize_run_worktree: unmerged -> warns, does not remove --------------


def test_finalize_warns_on_unmerged_worktree(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An un-merged worktree, finalized from the main repo, is retained with a
    warning naming the path and the manual remove command."""
    container = (tmp_path / ".main-repo-worktrees").resolve()
    worktree_path = (container / "unmerged").resolve()
    branch = "architect-team/unmerged"

    _add_worktree(main_repo, worktree_path, branch)
    _commit_in_worktree(worktree_path, "unmerged-work")
    # Deliberately DO NOT merge.

    monkeypatch.chdir(main_repo)
    result = worktree_lifecycle_module.finalize_run_worktree(
        worktree_path=worktree_path
    )

    assert result["removed"] is False, result
    assert result["merged"] is False, result
    assert result["reason"] == "unmerged-retained", result
    assert worktree_path.is_dir(), (
        f"un-merged worktree {worktree_path} must remain on disk"
    )
    warning = result["warning"]
    assert isinstance(warning, str) and warning, "warning must be a non-empty str"
    assert str(worktree_path) in warning, "warning must name the worktree path"
    assert "git worktree remove" in warning, (
        "warning must include the manual `git worktree remove` command"
    )


# ---- finalize_run_worktree: no-op on non-architect-team branch --------------


def test_finalize_noop_on_non_run_branch(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A worktree on a non-architect-team branch (feature/x) is a no-op."""
    worktree_path = (tmp_path / "feature-wt").resolve()
    branch = "feature/x"

    _add_worktree(main_repo, worktree_path, branch)

    monkeypatch.chdir(main_repo)
    result = worktree_lifecycle_module.finalize_run_worktree(
        worktree_path=worktree_path
    )

    assert result["removed"] is False, result
    assert result["reason"] == "not-a-run-worktree", result
    assert worktree_path.is_dir(), "non-run worktree must be left untouched"


# ---- _slug_from_worktree_path: dual-layout ----------------------------------


def test_slug_from_worktree_path_dual_layout(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """_slug_from_worktree_path returns the slug for BOTH the new hidden
    container layout and the old flat layout (repo basename `main-repo`)."""
    monkeypatch.chdir(main_repo)

    new_layout = tmp_path / ".main-repo-worktrees" / "add-billing"
    old_layout = tmp_path / "main-repo-add-billing"

    assert (
        worktree_lifecycle_module._slug_from_worktree_path(new_layout)
        == "add-billing"
    ), "new container layout slug derivation"
    assert (
        worktree_lifecycle_module._slug_from_worktree_path(old_layout)
        == "add-billing"
    ), "old flat layout slug derivation"


# ---- cleanup_merged_worktrees: dual-layout backward compat -------------------


def test_cleanup_merged_sweeps_both_layouts(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A merged worktree under the OLD flat path AND one under the NEW hidden
    container path are BOTH swept by cleanup_merged_worktrees."""
    old_flat = (tmp_path / "main-repo-oldflat").resolve()
    new_nested = (tmp_path / ".main-repo-worktrees" / "newnested").resolve()

    _add_worktree(main_repo, old_flat, "architect-team/oldflat")
    _add_worktree(main_repo, new_nested, "architect-team/newnested")

    _commit_in_worktree(old_flat, "oldflat-work")
    _commit_in_worktree(new_nested, "newnested-work")

    _merge_branch_into_main(main_repo, "architect-team/oldflat")
    _merge_branch_into_main(main_repo, "architect-team/newnested")

    assert old_flat.is_dir() and new_nested.is_dir(), "precondition: both exist"

    monkeypatch.chdir(main_repo)
    cleaned = worktree_lifecycle_module.cleanup_merged_worktrees()
    cleaned_resolved = {p.resolve() for p in cleaned}

    assert old_flat in cleaned_resolved, (
        f"old-flat worktree {old_flat} must be swept; got {cleaned_resolved}"
    )
    assert new_nested in cleaned_resolved, (
        f"new-container worktree {new_nested} must be swept; got {cleaned_resolved}"
    )
    assert not old_flat.exists(), f"{old_flat} should be gone from disk"
    assert not new_nested.exists(), f"{new_nested} should be gone from disk"
