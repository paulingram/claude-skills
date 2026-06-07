"""REQ-004 (v3.7.0): auto-merge-to-main + prune for clean run branches.

Exercises the two new public helpers + the internal clean-mergeability probe
in `scripts/setup/worktree_lifecycle.py`:
  - list_run_branches(against="main", remote="origin") -> list[dict]
  - merge_branch_to_main_and_prune(branch, worktree_path=None, against="main",
        remote="origin", push=True) -> dict

Test discipline mirrors `tests/test_worktree_auto_cleanup.py` EXACTLY: real
`git init` + a self-remote `origin/main` (via `git remote add origin <repo>`
+ fetch); real `git worktree add`; no mocks of git. Each test creates its own
isolated git repo in `tmp_path`; paths are `.resolve()`'d for macOS
/private/var vs /var symlink safety. The module is loaded via importlib + the
`plugin_root` fixture; the helper is invoked with `monkeypatch.chdir` into the
repo so `git rev-parse --show-toplevel` resolves to the test repo.
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
        "worktree_lifecycle_module_v37", path
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- Helpers (mirror test_worktree_auto_cleanup.py) -------------------------


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
    """Initialize a fresh git repo with one commit on `main` + a self-remote.

    The repo's own path is registered as `origin` and fetched so `origin/main`
    is a valid remote-tracking ref AND `git push origin main` from the same
    repo updates it without a network.
    """
    repo_dir.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--initial-branch=main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test User"])
    # Allow pushing to the currently-checked-out branch of the self-remote
    # (origin == this same repo); without this, `git push origin main` is
    # refused because main is checked out.
    _run(
        [
            "git",
            "-C",
            str(repo_dir),
            "config",
            "receive.denyCurrentBranch",
            "updateInstead",
        ]
    )
    (repo_dir / "README.md").write_text("# test repo\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "init"])
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


def _commit_in_worktree(
    worktree_path: Path, name: str, filename: str | None = None, content: str | None = None
) -> None:
    """Add/modify a file in the worktree and commit it."""
    fname = filename if filename is not None else f"{name}.txt"
    body = content if content is not None else f"{name}\n"
    (worktree_path / fname).write_text(body, encoding="utf-8")
    _run(["git", "-C", str(worktree_path), "add", "."])
    _run(["git", "-C", str(worktree_path), "commit", "-m", name])


def _merge_branch_into_main(repo_dir: Path, branch: str) -> None:
    """Merge `branch` into `main` in the main repo; refresh origin/main."""
    _run(["git", "-C", str(repo_dir), "merge", "--no-ff", branch, "-m", f"merge {branch}"])
    _refresh_origin(repo_dir)


def _commit_on_main(repo_dir: Path, name: str, filename: str, content: str) -> None:
    """Commit a file directly on `main` in the main repo; refresh origin/main."""
    (repo_dir / filename).write_text(content, encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "."])
    _run(["git", "-C", str(repo_dir), "commit", "-m", name])
    _refresh_origin(repo_dir)


def _head_sha(repo_dir: Path, ref: str = "HEAD") -> str:
    return _run(["git", "-C", str(repo_dir), "rev-parse", ref]).stdout.strip()


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    """A freshly-initialized git repo with one commit on `main` and origin/main."""
    repo_dir = (tmp_path / "main-repo").resolve()
    _init_main_repo(repo_dir)
    return repo_dir


# ---- list_run_branches -------------------------------------------------------


def test_list_run_branches_reports_merge_state_and_excludes_others(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One merged + one unmerged architect-team/* branch + a feature/x branch:
    the two architect-team branches appear with correct merged_into_main;
    feature/x never appears."""
    merged_path = (tmp_path / "wt-merged").resolve()
    unmerged_path = (tmp_path / "wt-unmerged").resolve()
    feature_path = (tmp_path / "wt-feature").resolve()

    _create_worktree_on_branch(main_repo, merged_path, "architect-team/merged")
    _create_worktree_on_branch(main_repo, unmerged_path, "architect-team/unmerged")
    _create_worktree_on_branch(main_repo, feature_path, "feature/x")

    _commit_in_worktree(merged_path, "merged-work", filename="merged.txt")
    _commit_in_worktree(unmerged_path, "unmerged-work", filename="unmerged.txt")
    _commit_in_worktree(feature_path, "feature-work", filename="feature.txt")

    # Merge ONLY the merged branch into main.
    _merge_branch_into_main(main_repo, "architect-team/merged")

    monkeypatch.chdir(main_repo)
    descriptors = worktree_lifecycle_module.list_run_branches()

    by_branch = {d["branch"]: d for d in descriptors}

    assert "architect-team/merged" in by_branch
    assert "architect-team/unmerged" in by_branch
    assert "feature/x" not in by_branch, (
        f"feature/x must NEVER appear in list_run_branches; got {list(by_branch)}"
    )

    assert by_branch["architect-team/merged"]["merged_into_main"] is True
    assert by_branch["architect-team/unmerged"]["merged_into_main"] is False

    # worktree_path is reported (non-None) for both.
    assert by_branch["architect-team/merged"]["worktree_path"] is not None
    assert by_branch["architect-team/unmerged"]["worktree_path"] is not None

    # Each descriptor carries all four keys.
    for d in descriptors:
        assert set(d) == {
            "branch",
            "worktree_path",
            "merged_into_main",
            "cleanly_mergeable",
        }


# ---- merge_branch_to_main_and_prune: CLEAN path ------------------------------


def test_merge_and_prune_clean_path(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Clean architect-team/foo merges into main, pushes (self-remote), and is
    pruned (branch gone, worktree gone, main contains the commit)."""
    foo_path = (tmp_path / "wt-foo").resolve()
    _create_worktree_on_branch(main_repo, foo_path, "architect-team/foo")
    # Non-conflicting commit (new file, untouched on main).
    _commit_in_worktree(foo_path, "foo-feature", filename="foo_feature.txt")

    assert foo_path.is_dir(), "precondition: worktree exists"

    monkeypatch.chdir(main_repo)
    result = worktree_lifecycle_module.merge_branch_to_main_and_prune(
        "architect-team/foo", worktree_path=str(foo_path), push=True
    )

    assert result["merged"] is True, result
    assert result["pushed"] is True, result
    assert result["branch_deleted"] is True, result
    assert result["worktree_removed"] is True, result
    assert result["conflict"] is False, result
    assert result["reason"] == "merged-and-pruned", result

    # Branch gone.
    branch_list = _run(
        ["git", "-C", str(main_repo), "branch", "--list", "architect-team/foo"]
    ).stdout.strip()
    assert branch_list == "", f"branch should be deleted; got {branch_list!r}"

    # Worktree dir gone.
    assert not foo_path.exists(), "worktree dir should be removed"

    # main contains the branch's file.
    assert (main_repo / "foo_feature.txt").exists(), (
        "main should contain the merged branch's file"
    )


# ---- merge_branch_to_main_and_prune: CONFLICT path ---------------------------


def test_merge_and_prune_conflict_path(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """architect-team/bar and main edit the SAME file to different content:
    the helper reports conflict, merges nothing, and leaves main + branch +
    worktree intact."""
    bar_path = (tmp_path / "wt-bar").resolve()
    _create_worktree_on_branch(main_repo, bar_path, "architect-team/bar")

    # Conflicting edits to the SAME file on both branch and main.
    _commit_in_worktree(
        bar_path, "bar-edit", filename="conflict.txt", content="from-bar\n"
    )
    _commit_on_main(
        main_repo, "main-edit", filename="conflict.txt", content="from-main\n"
    )

    main_head_before = _head_sha(main_repo, "main")

    monkeypatch.chdir(main_repo)
    result = worktree_lifecycle_module.merge_branch_to_main_and_prune(
        "architect-team/bar", worktree_path=str(bar_path), push=True
    )

    assert result["conflict"] is True, result
    assert result["merged"] is False, result
    assert result["reason"] in ("conflict", "conflict-on-merge"), result

    # main unchanged.
    assert _head_sha(main_repo, "main") == main_head_before, "main HEAD must be unchanged"

    # branch still exists.
    branch_list = _run(
        ["git", "-C", str(main_repo), "branch", "--list", "architect-team/bar"]
    ).stdout.strip()
    assert "architect-team/bar" in branch_list, "branch must still exist"

    # worktree still on disk.
    assert bar_path.is_dir(), "worktree must remain on disk after a conflict"


# ---- merge_branch_to_main_and_prune: non-run-branch guard --------------------


def test_merge_and_prune_non_run_branch_guard(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-architect-team branch is rejected before any git action."""
    monkeypatch.chdir(main_repo)
    result = worktree_lifecycle_module.merge_branch_to_main_and_prune("feature/x")

    assert result["merged"] is False, result
    assert result["reason"] == "not-a-run-branch", result
    # Guaranteed dict shape.
    assert set(result) >= {
        "merged",
        "pushed",
        "branch_deleted",
        "worktree_removed",
        "conflict",
        "reason",
        "branch",
        "worktree_path",
    }
