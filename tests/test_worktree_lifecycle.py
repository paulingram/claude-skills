"""REQ-1: worktree-lifecycle helper (v1.2.0).

Exercises `scripts/setup/worktree_lifecycle.py`:
  - create_run_worktree(slug, base_branch="main", parent_dir=None) -> Path
  - cleanup_run_worktree(worktree_path, remove_branch=False) -> None
  - current_worktree_is_run() -> bool
  - current_run_slug() -> str | None

Test discipline matches `tests/test_worktree_state_resolution.py` (v1.1.0):
real `git init` + `git worktree add` subprocesses, no mocks of git. Paths
are .resolve()'d to handle macOS /private/var vs /var symlinks.
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
        "worktree_lifecycle_module", path
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- Test fixtures -----------------------------------------------------------


def _init_main_repo(repo_dir: Path) -> None:
    """Initialize a fresh git repo with one commit so worktrees can branch off."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repo_dir)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    (repo_dir / "README.md").write_text("# test repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo_dir), "add", "README.md"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    """A freshly-initialized git repo with one commit on `main`.

    Resolves the path so macOS /private/var vs /var symlinks don't trip
    equality checks downstream. The repo basename is `main-repo`; with a
    slug `add-billing`, the helper will compute the worktree path as
    `<tmp_path>/main-repo-add-billing`.
    """
    repo_dir = (tmp_path / "main-repo").resolve()
    _init_main_repo(repo_dir)
    return repo_dir


def _list_worktrees(repo_dir: Path) -> str:
    """Return `git worktree list --porcelain` output from inside the repo."""
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _branch_exists(repo_dir: Path, branch: str) -> bool:
    """Return True iff `branch` resolves as a local ref in the repo."""
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


def _cleanup_worktree(repo_dir: Path, worktree_path: Path) -> None:
    """Best-effort cleanup so a failing test does not poison the next one."""
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "worktree",
            "remove",
            "--force",
            str(worktree_path),
        ],
        check=False,
        capture_output=True,
    )


def _cleanup_branch(repo_dir: Path, branch: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_dir), "branch", "-D", branch],
        check=False,
        capture_output=True,
    )


# ---- REQ-1: create_run_worktree happy path ----------------------------------


def test_create_run_worktree_builds_expected_layout(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Spec scenario: create_run_worktree builds the expected layout."""
    monkeypatch.chdir(main_repo)

    container = (tmp_path.resolve() / ".main-repo-worktrees").resolve()
    expected_path = (container / "add-billing").resolve()
    expected_branch = "architect-team/add-billing"

    try:
        worktree_path = worktree_lifecycle_module.create_run_worktree(
            "add-billing"
        )
        worktree_path = worktree_path.resolve()

        # Path matches the new hidden-container convention (v3.6.0).
        assert worktree_path == expected_path, (
            f"expected {expected_path}, got {worktree_path}"
        )
        assert worktree_path.is_dir()

        # The hidden per-project container exists and is a directory.
        assert container.is_dir(), (
            f"expected container dir {container} to exist and be a directory"
        )

        # The new worktree is checked out on the run branch.
        current_branch = subprocess.run(
            [
                "git",
                "-C",
                str(worktree_path),
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert current_branch == expected_branch, (
            f"expected branch {expected_branch}, got {current_branch}"
        )

        # And the branch exists in the main repo's ref store.
        assert _branch_exists(main_repo, expected_branch)
    finally:
        _cleanup_worktree(main_repo, expected_path)
        _cleanup_branch(main_repo, expected_branch)


# ---- REQ-1: collision handling ----------------------------------------------


def test_create_run_worktree_handles_collision(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Spec scenario: collision handling appends `-2` (then `-3`, ...)."""
    monkeypatch.chdir(main_repo)

    # Pre-create the colliding branch so the first attempt at
    # `architect-team/add-billing` MUST bump to `-2`.
    subprocess.run(
        ["git", "-C", str(main_repo), "branch", "architect-team/add-billing"],
        check=True,
        capture_output=True,
    )

    first_path = (
        tmp_path.resolve() / ".main-repo-worktrees" / "add-billing-2"
    ).resolve()
    first_branch = "architect-team/add-billing-2"

    try:
        worktree_path = worktree_lifecycle_module.create_run_worktree(
            "add-billing"
        )
        worktree_path = worktree_path.resolve()

        assert worktree_path == first_path, (
            f"expected suffixed path {first_path}, got {worktree_path}"
        )

        current_branch = subprocess.run(
            [
                "git",
                "-C",
                str(worktree_path),
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert current_branch == first_branch, (
            f"expected suffixed branch {first_branch}, got {current_branch}"
        )
    finally:
        _cleanup_worktree(main_repo, first_path)
        _cleanup_branch(main_repo, first_branch)
        _cleanup_branch(main_repo, "architect-team/add-billing")


# ---- REQ-1: current_worktree_is_run -----------------------------------------


def test_current_worktree_is_run_true_in_run_worktree(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Spec scenario: True from inside an architect-team/* worktree."""
    worktree_path = (tmp_path.resolve() / "main-repo-foo").resolve()
    branch = "architect-team/foo"

    subprocess.run(
        [
            "git",
            "-C",
            str(main_repo),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
        ],
        check=True,
        capture_output=True,
    )
    try:
        monkeypatch.chdir(worktree_path)
        assert worktree_lifecycle_module.current_worktree_is_run() is True
    finally:
        _cleanup_worktree(main_repo, worktree_path)
        _cleanup_branch(main_repo, branch)


def test_current_worktree_is_run_false_on_main(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec scenario: False from the main checkout (branch=main)."""
    monkeypatch.chdir(main_repo)
    assert worktree_lifecycle_module.current_worktree_is_run() is False


# ---- REQ-1: current_run_slug ------------------------------------------------


def test_current_run_slug_extracts_slug(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Spec scenario: extracts `add-billing` from `architect-team/add-billing`."""
    worktree_path = (tmp_path.resolve() / "main-repo-add-billing").resolve()
    branch = "architect-team/add-billing"

    subprocess.run(
        [
            "git",
            "-C",
            str(main_repo),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
        ],
        check=True,
        capture_output=True,
    )
    try:
        monkeypatch.chdir(worktree_path)
        assert worktree_lifecycle_module.current_run_slug() == "add-billing"
    finally:
        _cleanup_worktree(main_repo, worktree_path)
        _cleanup_branch(main_repo, branch)


def test_current_run_slug_none_on_main(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec scenario: returns None on `main`."""
    monkeypatch.chdir(main_repo)
    assert worktree_lifecycle_module.current_run_slug() is None


# ---- REQ-1: cleanup_run_worktree --------------------------------------------


def test_cleanup_run_worktree_removes_worktree(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Spec scenario: cleanup_run_worktree removes the worktree."""
    monkeypatch.chdir(main_repo)

    # Create via the helper so the test exercises end-to-end behavior.
    worktree_path = worktree_lifecycle_module.create_run_worktree(
        "removeme"
    ).resolve()
    expected_branch = "architect-team/removeme"

    try:
        assert worktree_path.is_dir()
        assert worktree_path.as_posix() in _list_worktrees(main_repo)

        worktree_lifecycle_module.cleanup_run_worktree(worktree_path)

        assert not worktree_path.exists(), (
            f"worktree path {worktree_path} should have been removed"
        )
        # And it must no longer appear in the registry.
        listing = _list_worktrees(main_repo)
        assert worktree_path.as_posix() not in listing, (
            f"`git worktree list` still contains {worktree_path}: {listing}"
        )

        # Idempotency: a second call against the now-gone worktree is a no-op.
        worktree_lifecycle_module.cleanup_run_worktree(worktree_path)
    finally:
        _cleanup_worktree(main_repo, worktree_path)
        _cleanup_branch(main_repo, expected_branch)


def test_cleanup_run_worktree_with_remove_branch_removes_branch(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Spec scenario: remove_branch=True also deletes the run branch."""
    monkeypatch.chdir(main_repo)

    worktree_path = worktree_lifecycle_module.create_run_worktree(
        "deletebranch"
    ).resolve()
    expected_branch = "architect-team/deletebranch"

    try:
        assert _branch_exists(main_repo, expected_branch)

        worktree_lifecycle_module.cleanup_run_worktree(
            worktree_path, remove_branch=True
        )

        assert not worktree_path.exists()
        assert not _branch_exists(main_repo, expected_branch), (
            f"branch {expected_branch} should have been deleted"
        )
    finally:
        _cleanup_worktree(main_repo, worktree_path)
        _cleanup_branch(main_repo, expected_branch)
