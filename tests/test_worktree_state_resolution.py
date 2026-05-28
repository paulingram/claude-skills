"""REQ-1, REQ-2, REQ-6: worktree-aware state resolution (v1.1.0).

Exercises `scripts/setup/worktree_paths.py`:
  - is_worktree() -> bool
  - shared_state_dir() -> Path  (main worktree's .architect-team/)
  - run_state_dir() -> Path     (current worktree's .architect-team/)

Plus the integration check that `hooks/locks.py`'s default `locks_dir`
resolves through `shared_state_dir()` — so a lock acquired from a worktree
is visible to (and blocks) an intersecting acquire from the main checkout.

Scenarios from spec.md REQ-1 + REQ-2:
  - is_worktree False in a main checkout
  - is_worktree True in a worktree
  - shared_state_dir returns main's .architect-team/ from main checkout
  - shared_state_dir returns main's .architect-team/ from a worktree
  - run_state_dir is per-worktree (different paths between main + worktree)
  - lock acquired from a worktree blocks an intersecting acquire from main
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def worktree_paths_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/worktree_paths.py via importlib (matches teams_mode pattern)."""
    path = plugin_root / "scripts" / "setup" / "worktree_paths.py"
    assert path.exists(), f"worktree_paths.py missing at {path}"
    spec = importlib.util.spec_from_file_location("worktree_paths_module", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def locks_module_for_worktrees(plugin_root: Path) -> ModuleType:
    """Load hooks/locks.py for the cross-worktree integration test."""
    path = plugin_root / "hooks" / "locks.py"
    assert path.exists(), f"locks.py missing at {path}"
    spec = importlib.util.spec_from_file_location("locks_module_for_worktrees", path)
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
    # Per-repo identity so the commit works regardless of global config.
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
    # One initial commit so `git worktree add` can branch off main.
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
    """A freshly-initialized git repo with one commit. Resolves the path to handle
    macOS /private/var vs /var symlinks (tmp_path resolves to the real path)."""
    repo_dir = (tmp_path / "main-repo").resolve()
    _init_main_repo(repo_dir)
    return repo_dir


@pytest.fixture
def worktree(main_repo: Path, tmp_path: Path) -> Path:
    """A worktree branched off the main repo, on a new branch.

    Cleanup: the worktree is removed via `git worktree remove --force` after
    the test so the main repo's worktree registry stays clean.
    """
    worktree_dir = (tmp_path / "wt").resolve()
    subprocess.run(
        [
            "git",
            "-C",
            str(main_repo),
            "worktree",
            "add",
            "-b",
            "feature-branch",
            str(worktree_dir),
        ],
        check=True,
        capture_output=True,
    )
    yield worktree_dir
    # Best-effort cleanup — the test may have already removed it.
    subprocess.run(
        [
            "git",
            "-C",
            str(main_repo),
            "worktree",
            "remove",
            "--force",
            str(worktree_dir),
        ],
        check=False,
        capture_output=True,
    )


# ---- REQ-1: is_worktree() ----------------------------------------------------


def test_is_worktree_false_in_main_checkout(
    worktree_paths_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From the main repo's working directory, is_worktree() returns False."""
    monkeypatch.chdir(main_repo)
    assert worktree_paths_module.is_worktree() is False


def test_is_worktree_true_in_worktree(
    worktree_paths_module: ModuleType,
    worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From inside a `git worktree add`-created worktree, is_worktree() returns True."""
    monkeypatch.chdir(worktree)
    assert worktree_paths_module.is_worktree() is True


# ---- REQ-1: shared_state_dir() resolution -----------------------------------


def test_shared_state_dir_from_main_is_main_dot_architect_team(
    worktree_paths_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From the main checkout, shared_state_dir() returns the main repo's
    .architect-team/ — same path run_state_dir() would return there."""
    monkeypatch.chdir(main_repo)
    expected = (main_repo / ".architect-team").resolve()
    assert worktree_paths_module.shared_state_dir().resolve() == expected
    # Degenerate case: shared and run resolve to the same path in main.
    assert (
        worktree_paths_module.shared_state_dir().resolve()
        == worktree_paths_module.run_state_dir().resolve()
    )


def test_shared_state_dir_from_worktree_resolves_to_main(
    worktree_paths_module: ModuleType,
    main_repo: Path,
    worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From a worktree, shared_state_dir() returns the MAIN worktree's
    .architect-team/ — NOT the worktree's own. This is the v1.1.0 fix."""
    monkeypatch.chdir(worktree)
    expected_main = (main_repo / ".architect-team").resolve()
    assert worktree_paths_module.shared_state_dir().resolve() == expected_main
    # And it MUST NOT be the worktree's own .architect-team/.
    worktree_own = (worktree / ".architect-team").resolve()
    assert worktree_paths_module.shared_state_dir().resolve() != worktree_own


# ---- REQ-1: run_state_dir() is per-worktree ----------------------------------


def test_run_state_dir_is_per_worktree(
    worktree_paths_module: ModuleType,
    main_repo: Path,
    worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_state_dir() returns the current cwd's .architect-team/, so main and
    worktree see different paths."""
    monkeypatch.chdir(main_repo)
    main_run = worktree_paths_module.run_state_dir().resolve()

    monkeypatch.chdir(worktree)
    worktree_run = worktree_paths_module.run_state_dir().resolve()

    assert main_run == (main_repo / ".architect-team").resolve()
    assert worktree_run == (worktree / ".architect-team").resolve()
    assert main_run != worktree_run


# ---- REQ-2: cross-worktree lock coordination --------------------------------


def test_lock_acquired_from_worktree_visible_to_main(
    worktree_paths_module: ModuleType,
    locks_module_for_worktrees: ModuleType,
    main_repo: Path,
    worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: acquire a lock from a worktree with the DEFAULT locks_dir
    (which resolves through shared_state_dir()); then from the main checkout
    attempt to acquire an intersecting scope with the default locks_dir.

    Expected: the second acquire is `blocked` because both default to the
    same shared `.architect-team/locks/` directory under the main repo. This
    is the REQ-2 cross-worktree coordination guarantee.
    """
    # Session 1: acquire from the worktree, default locks_dir.
    monkeypatch.chdir(worktree)
    acquire_a = locks_module_for_worktrees.acquire_lock(
        scope_glob="src/auth/**",
        ttl_seconds=14400,
        run_id="run-A-worktree",
    )
    assert acquire_a["status"] == "acquired", acquire_a

    # The lock file MUST land in the MAIN repo's shared locks dir, not the
    # worktree's own. Verify this directly so we know what we tested.
    shared_locks_dir = (main_repo / ".architect-team" / "locks").resolve()
    lock_file = shared_locks_dir / f"{acquire_a['lock_id']}.json"
    assert lock_file.is_file(), (
        f"acquire from worktree should write to main repo's shared locks "
        f"dir, but {lock_file} was not found. Contents of "
        f"{shared_locks_dir}: "
        f"{list(shared_locks_dir.iterdir()) if shared_locks_dir.is_dir() else 'dir-missing'}"
    )

    # Session 2: from the main checkout, attempt an intersecting scope with
    # the same default locks_dir. The shared resolution means it sees the
    # worktree's lock and blocks.
    monkeypatch.chdir(main_repo)
    acquire_b = locks_module_for_worktrees.acquire_lock(
        scope_glob="src/auth/login/**",
        ttl_seconds=14400,
        run_id="run-B-main",
    )
    assert acquire_b["status"] == "blocked", acquire_b
    assert acquire_b["held_by"] == "run-A-worktree"

    # Cleanup: release the lock so the test leaves no shared-state residue.
    locks_module_for_worktrees.release_lock(acquire_a["lock_id"])
