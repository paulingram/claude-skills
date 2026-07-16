"""lineage P6 (REQ-CDL-11a + REQ-CDL-11b): squash-merge detection + task-aware
worktree heuristic.

Exercises the new behavior in `scripts/setup/worktree_lifecycle.py`:
  - _branch_is_squash_merged(toplevel, branch, against="origin/main") -> bool
  - _branch_is_merged_or_squash_merged(toplevel, branch, against="origin/main") -> bool
  - list_run_branches(..., include_squash_merged=False) -> list[dict] (now with
    a `squash_merged` field)
  - recommend_worktree(task_scope=None) -> {"use_worktree": bool, "reason": str}

Test discipline matches `tests/test_worktree_auto_cleanup.py` (v1.3.0) and
`tests/test_worktree_merge_finalize.py` (v3.6.0): real `git init` + self-remote
`origin/main` + `git worktree add` subprocesses, NO mocks of git. Each test
creates its own isolated git repo in `tmp_path`; paths are `.resolve()`'d for
macOS /private/var vs /var symlink safety; the module is loaded via importlib
against the `plugin_root` fixture; cwd is steered via `monkeypatch.chdir`.
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
    mod = load_module(path, "worktree_lifecycle_module_p6_squash")
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
    """Initialize a fresh git repo with one commit on `main` and origin/main.

    Self-remote: register the repo's own path as `origin` and fetch so
    `origin/main` becomes a valid remote-tracking ref without a network.
    """
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
    """Re-fetch `origin` so `origin/main` reflects the latest local `main`."""
    _run(["git", "-C", str(repo_dir), "fetch", "origin"])


def _create_worktree_on_branch(
    repo_dir: Path, worktree_path: Path, branch: str
) -> None:
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


def _commit_in_worktree(
    worktree_path: Path, message: str = "work", filename: str | None = None
) -> None:
    """Add a file in the worktree and commit it."""
    name = filename if filename is not None else f"{message}.txt"
    (worktree_path / name).write_text(f"{message}\n", encoding="utf-8")
    _run(["git", "-C", str(worktree_path), "add", "."])
    _run(["git", "-C", str(worktree_path), "commit", "-m", message])


def _squash_merge_into_main(repo_dir: Path, branch: str, message: str) -> None:
    """Squash-merge `branch` into `main` in the MAIN repo, then refresh origin.

    `git merge --squash` stages the branch's net diff WITHOUT recording the
    branch as a parent; the follow-up commit is a single new SHA on main that
    is NOT a descendant of the branch tip — exactly the case
    `merge-base --is-ancestor` misses.
    """
    _run(["git", "-C", str(repo_dir), "merge", "--squash", branch])
    _run(["git", "-C", str(repo_dir), "commit", "-m", message])
    _refresh_origin(repo_dir)


def _no_ff_merge_into_main(repo_dir: Path, branch: str) -> None:
    """`git merge --no-ff branch` into `main` in the main repo + refresh origin."""
    _run(
        ["git", "-C", str(repo_dir), "merge", "--no-ff", branch, "-m", f"merge {branch}"]
    )
    _refresh_origin(repo_dir)


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    """A freshly-initialized git repo with one commit on `main` and origin/main."""
    repo_dir = (tmp_path / "main-repo").resolve()
    _init_main_repo(repo_dir)
    return repo_dir


# ---- REQ-CDL-11a Scenario 1: squash-merge recognized ------------------------


def test_squash_merge_recognized_old_probe_misses(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A squash-merged branch is recognized by `_branch_is_squash_merged` AND
    is (correctly) NOT recognized by the old `_branch_is_merged_into` probe —
    proving the new predicate covers exactly the squash case the old one missed.
    """
    sq_path = (tmp_path / "main-repo-sq").resolve()
    branch = "architect-team/sq"

    _create_worktree_on_branch(main_repo, sq_path, branch)
    _commit_in_worktree(sq_path, "sq-work")

    # Squash-merge into main: stages the net diff as a brand-new single commit.
    _squash_merge_into_main(main_repo, branch, "squash sq")

    monkeypatch.chdir(main_repo)
    toplevel = worktree_lifecycle_module._git_show_toplevel()

    assert (
        worktree_lifecycle_module._branch_is_squash_merged(
            toplevel, branch, "origin/main"
        )
        is True
    ), "squash-merged branch must be recognized by _branch_is_squash_merged"

    assert (
        worktree_lifecycle_module._branch_is_merged_into(
            toplevel, branch, "origin/main"
        )
        is False
    ), (
        "the OLD merge-base --is-ancestor probe must NOT see the squash-merge "
        "(this is the gap REQ-CDL-11a closes)"
    )

    # The union predicate sees it as merged.
    assert (
        worktree_lifecycle_module._branch_is_merged_or_squash_merged(
            toplevel, branch, "origin/main"
        )
        is True
    ), "_branch_is_merged_or_squash_merged must be True for a squash-merge"


# ---- REQ-CDL-11a Scenario 2: no false positive on genuinely-unmerged work ---


def test_no_false_positive_on_unmerged_branch(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A branch with a real un-merged diff is NEVER flagged squash-merged (no
    false positive) and the union predicate is False too."""
    open_path = (tmp_path / "main-repo-open").resolve()
    branch = "architect-team/open"

    _create_worktree_on_branch(main_repo, open_path, branch)
    _commit_in_worktree(open_path, "open-work")
    # Deliberately DO NOT merge in any form — main never sees this diff.

    monkeypatch.chdir(main_repo)
    toplevel = worktree_lifecycle_module._git_show_toplevel()

    assert (
        worktree_lifecycle_module._branch_is_squash_merged(
            toplevel, branch, "origin/main"
        )
        is False
    ), "a branch with genuinely-unmerged work must NOT be flagged squash-merged"

    assert (
        worktree_lifecycle_module._branch_is_merged_or_squash_merged(
            toplevel, branch, "origin/main"
        )
        is False
    ), "the union predicate must be False for genuinely-unmerged work"


def test_no_squash_flag_when_no_commits_beyond_merge_base(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A branch with NO commits beyond the merge-base (nothing to judge) is
    NOT flagged squash-merged — the guard against a vacuous empty-diff match."""
    fresh_path = (tmp_path / "main-repo-fresh").resolve()
    branch = "architect-team/fresh"

    # Branch off main with zero additional commits: diff against main is empty,
    # but there's nothing to judge, so it must NOT be called squash-merged.
    _create_worktree_on_branch(main_repo, fresh_path, branch)

    monkeypatch.chdir(main_repo)
    toplevel = worktree_lifecycle_module._git_show_toplevel()

    assert (
        worktree_lifecycle_module._branch_is_squash_merged(
            toplevel, branch, "origin/main"
        )
        is False
    ), (
        "a branch with no commits beyond the merge-base has nothing to judge "
        "and must NOT be flagged squash-merged (guard (a))"
    )


# ---- REQ-CDL-11a Scenario 3: normal (--no-ff) merge via union predicate ------


def test_no_ff_merge_recognized_by_union_predicate(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A normally (--no-ff) merged branch is recognized by
    `_branch_is_merged_or_squash_merged` (via the plain-ancestor arm). The
    squash arm returns False because the branch is already a plain ancestor."""
    nf_path = (tmp_path / "main-repo-nf").resolve()
    branch = "architect-team/nf"

    _create_worktree_on_branch(main_repo, nf_path, branch)
    _commit_in_worktree(nf_path, "nf-work")
    _no_ff_merge_into_main(main_repo, branch)

    monkeypatch.chdir(main_repo)
    toplevel = worktree_lifecycle_module._git_show_toplevel()

    assert (
        worktree_lifecycle_module._branch_is_merged_or_squash_merged(
            toplevel, branch, "origin/main"
        )
        is True
    ), "a --no-ff-merged branch must be recognized by the union predicate"

    # And the plain probe sees it (it IS an ancestor).
    assert (
        worktree_lifecycle_module._branch_is_merged_into(
            toplevel, branch, "origin/main"
        )
        is True
    ), "a --no-ff-merged branch is a plain ancestor"

    # The squash predicate strictly ADDS the squash case -> False here because
    # the branch is already a plain ancestor (guard (b)).
    assert (
        worktree_lifecycle_module._branch_is_squash_merged(
            toplevel, branch, "origin/main"
        )
        is False
    ), (
        "_branch_is_squash_merged must return False for an already-plain-"
        "ancestor branch (it strictly adds the squash case, guard (b))"
    )


# ---- REQ-CDL-11a Scenario 4: list_run_branches opt-in + squash_merged field --


def test_list_run_branches_squash_field_and_opt_in(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """list_run_branches(include_squash_merged=True) includes the squash-merged
    branch with squash_merged=True AND merged_into_main=True; the default
    (False) reports squash_merged=True but treats it as NOT merged
    (merged_into_main=False)."""
    sq_path = (tmp_path / "main-repo-sqlist").resolve()
    branch = "architect-team/sqlist"

    _create_worktree_on_branch(main_repo, sq_path, branch)
    _commit_in_worktree(sq_path, "sqlist-work")
    _squash_merge_into_main(main_repo, branch, "squash sqlist")

    monkeypatch.chdir(main_repo)

    # --- Opt-in: include_squash_merged=True ---
    opted = worktree_lifecycle_module.list_run_branches(include_squash_merged=True)
    by_branch_opt = {d["branch"]: d for d in opted}
    assert branch in by_branch_opt, (
        f"{branch} must appear in list_run_branches output; got "
        f"{list(by_branch_opt)}"
    )
    desc_opt = by_branch_opt[branch]
    assert desc_opt["squash_merged"] is True, (
        f"squash_merged must be True for the squash-merged branch; got {desc_opt}"
    )
    assert desc_opt["merged_into_main"] is True, (
        f"with include_squash_merged=True, merged_into_main must be True for a "
        f"squash-merged branch; got {desc_opt}"
    )

    # --- Default: include_squash_merged=False (conservative) ---
    default = worktree_lifecycle_module.list_run_branches()
    by_branch_def = {d["branch"]: d for d in default}
    desc_def = by_branch_def[branch]
    # The squash_merged field is ALWAYS populated for transparency...
    assert desc_def["squash_merged"] is True, (
        f"squash_merged field must always be populated; got {desc_def}"
    )
    # ...but with the default, the branch is treated as NOT merged (the
    # documented v1.3.0 safe false-negative).
    assert desc_def["merged_into_main"] is False, (
        f"with the default (include_squash_merged=False), merged_into_main "
        f"must be False for a squash-merged branch (conservative); got {desc_def}"
    )


def test_list_run_branches_squash_not_in_default_cleanup(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A squash-merged worktree is NOT swept by the default cleanup
    (include_squash_merged defaults False), but IS swept when opted in."""
    sq_path = (tmp_path / "main-repo-sqclean").resolve()
    branch = "architect-team/sqclean"

    _create_worktree_on_branch(main_repo, sq_path, branch)
    _commit_in_worktree(sq_path, "sqclean-work")
    _squash_merge_into_main(main_repo, branch, "squash sqclean")

    monkeypatch.chdir(main_repo)

    # Default dry-run: squash-merged worktree must NOT be a candidate.
    default_preview = worktree_lifecycle_module.cleanup_merged_worktrees(
        dry_run=True
    )
    default_resolved = {p.resolve() for p in default_preview}
    assert sq_path not in default_resolved, (
        f"default cleanup must NOT flag squash-merged {sq_path}; got "
        f"{default_resolved}"
    )

    # Opt-in dry-run: now it IS a candidate.
    opt_preview = worktree_lifecycle_module.cleanup_merged_worktrees(
        dry_run=True, include_squash_merged=True
    )
    opt_resolved = {p.resolve() for p in opt_preview}
    assert sq_path in opt_resolved, (
        f"include_squash_merged=True cleanup must flag squash-merged {sq_path}; "
        f"got {opt_resolved}"
    )
    # Dry-run leaves the filesystem untouched.
    assert sq_path.is_dir(), "dry_run must not remove the worktree from disk"


def test_list_merged_worktrees_opt_in_includes_squash(
    worktree_lifecycle_module: ModuleType,
    main_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """list_merged_architect_team_worktrees(include_squash_merged=True) includes
    a squash-merged worktree the default call omits."""
    sq_path = (tmp_path / "main-repo-sqwt").resolve()
    branch = "architect-team/sqwt"

    _create_worktree_on_branch(main_repo, sq_path, branch)
    _commit_in_worktree(sq_path, "sqwt-work")
    _squash_merge_into_main(main_repo, branch, "squash sqwt")

    monkeypatch.chdir(main_repo)

    default = worktree_lifecycle_module.list_merged_architect_team_worktrees()
    assert sq_path not in {p.resolve() for p in default}, (
        "default list must omit a squash-merged worktree"
    )

    opted = worktree_lifecycle_module.list_merged_architect_team_worktrees(
        include_squash_merged=True
    )
    assert sq_path in {p.resolve() for p in opted}, (
        "include_squash_merged=True must include the squash-merged worktree"
    )


# ---- REQ-CDL-11b: task-aware worktree heuristic -----------------------------


def test_recommend_worktree_tiny_scope_false(
    worktree_lifecycle_module: ModuleType,
) -> None:
    """A `tiny` task scope recommends NOT creating a worktree."""
    rec = worktree_lifecycle_module.recommend_worktree("tiny")
    assert isinstance(rec, dict)
    assert rec["use_worktree"] is False, rec
    assert isinstance(rec["reason"], str) and rec["reason"], rec


@pytest.mark.parametrize("scope", ["tiny", "trivial", "doc-only", "single-file"])
def test_recommend_worktree_small_scopes_false(
    worktree_lifecycle_module: ModuleType, scope: str
) -> None:
    """Every small/doc-only/single-file scope recommends use_worktree=False."""
    rec = worktree_lifecycle_module.recommend_worktree(scope)
    assert rec["use_worktree"] is False, f"{scope}: {rec}"


def test_recommend_worktree_none_defaults_true(
    worktree_lifecycle_module: ModuleType,
) -> None:
    """task_scope=None defaults to use_worktree=True (today's behavior)."""
    rec = worktree_lifecycle_module.recommend_worktree(None)
    assert rec["use_worktree"] is True, rec
    assert isinstance(rec["reason"], str) and rec["reason"], rec


def test_recommend_worktree_default_arg_is_true(
    worktree_lifecycle_module: ModuleType,
) -> None:
    """Calling with NO argument (default None) also recommends True."""
    rec = worktree_lifecycle_module.recommend_worktree()
    assert rec["use_worktree"] is True, rec


@pytest.mark.parametrize(
    "scope", ["small", "medium", "large", "feature", "multi-file"]
)
def test_recommend_worktree_substantial_scopes_true(
    worktree_lifecycle_module: ModuleType, scope: str
) -> None:
    """Every substantial scope (incl. `feature`) recommends use_worktree=True."""
    rec = worktree_lifecycle_module.recommend_worktree(scope)
    assert rec["use_worktree"] is True, f"{scope}: {rec}"


def test_recommend_worktree_unknown_scope_leans_true(
    worktree_lifecycle_module: ModuleType,
) -> None:
    """An unrecognized scope leans toward the isolating default (True)."""
    rec = worktree_lifecycle_module.recommend_worktree("banana")
    assert rec["use_worktree"] is True, rec


def test_recommend_worktree_is_advisory_no_worktree_honored(
    worktree_lifecycle_module: ModuleType,
) -> None:
    """The function is ADVISORY ONLY: its docstring + every reason string
    document that `--no-worktree` is honored regardless of the recommendation."""
    # Docstring documents the advisory + --no-worktree-honored contract.
    doc = worktree_lifecycle_module.recommend_worktree.__doc__ or ""
    assert "ADVISORY" in doc.upper(), "docstring must state it is advisory only"
    assert "--no-worktree" in doc, (
        "docstring must state --no-worktree is honored regardless"
    )

    # And the contract surfaces in the returned reason for representative
    # scopes (so a caller logging the reason sees the advisory note).
    for scope in (None, "tiny", "feature", "banana"):
        rec = worktree_lifecycle_module.recommend_worktree(scope)
        assert "--no-worktree" in rec["reason"], (
            f"reason for scope={scope!r} must note --no-worktree is honored; "
            f"got {rec['reason']!r}"
        )
