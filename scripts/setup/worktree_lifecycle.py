#!/usr/bin/env python3
"""Worktree-lifecycle helper for the architect-team plugin (v1.2.0 + v1.3.0).

v1.1.0 shipped `scripts/setup/worktree_paths.py` — the worktree-aware
state-resolution sibling that answers WHERE state lives (shared vs. per-run).
v1.2.0 ships THIS module — the side-effecting lifecycle helper that CREATES,
DETECTS, and TEARS DOWN architect-team-run worktrees, so the three pipeline
slash commands (`/architect-team`, `/architect-team:bug-fix`,
`/architect-team:mini`) can auto-create a worktree by default before invoking
the pipeline skill. v1.3.0 extends the module with two auto-cleanup helpers
(`list_merged_architect_team_worktrees`, `cleanup_merged_worktrees`) so the
same slash commands can sweep merged-and-forgotten worktrees from prior runs
as their first action.

The split is intentional: `worktree_paths.py` is pure read-only resolution
(no side effects); `worktree_lifecycle.py` runs `git worktree add` /
`git worktree remove` / `git branch -d` subprocesses. Keeping the two
responsibilities in separate modules preserves the v1.1.0 path-resolution
module's pure-resolution contract and keeps the lifecycle helper independently
testable.

Public API — six stdlib-only functions:

  create_run_worktree(slug, base_branch="main", parent_dir=None) -> Path
      Create `<parent>/<repo-name>-<slug>/` on a fresh branch
      `architect-team/<slug>`. Handles slug/branch collisions by appending
      `-2`, `-3`, ... Returns the absolute path to the new worktree.

  cleanup_run_worktree(worktree_path, remove_branch=False) -> None
      `git worktree remove <path>` (idempotent). When `remove_branch=True`,
      also `git branch -d architect-team/<slug>` (slug derived from the path
      basename's trailing suffix).

  current_worktree_is_run() -> bool
      True iff `git rev-parse --abbrev-ref HEAD` starts with
      `architect-team/`. Used by the slash commands' re-entry detection so
      they do not double-nest a worktree when invoked from inside an
      existing run worktree.

  current_run_slug() -> str | None
      The part after `architect-team/` of the current branch name when in a
      run worktree, else None.

  list_merged_architect_team_worktrees(against="origin/main", exclude_current=True) -> list[Path]
      (v1.3.0) Return paths of architect-team/* worktrees whose branch is
      merged into <against>. Excludes the current worktree by default
      (safety: don't auto-remove the cwd even if its branch happens to be
      merged). Branches NOT starting with `architect-team/` are never
      considered.

  cleanup_merged_worktrees(against="origin/main", dry_run=False) -> list[Path]
      (v1.3.0) Remove all merged architect-team/* worktrees. Returns paths
      cleaned (or that would-be-cleaned in dry_run mode). Idempotent on a
      worktree that disappears between list and remove.

Naming conventions
------------------

- Branch: `architect-team/<slug>` (matches the existing Phase 8
  default-branch-guard convention).
- Worktree directory: `<parent-of-repo>/<repo-name>-<slug>/` (e.g. repo at
  `/Users/foo/projects/myapp` with slug `add-billing` -> worktree at
  `/Users/foo/projects/myapp-add-billing/`).
- Collision handling: if EITHER the path OR the branch already exists, the
  helper appends `-2`, then `-3`, ... until both are free.

Reuse Decision: RD-1 (build-new — no existing equivalent). Stdlib only,
matching the convention used by `scripts/setup/worktree_paths.py` (the
sibling resolution helper) and `scripts/setup/teams_mode.py` (the existing
setup helper this module sits alongside).

References:
  - openspec/changes/auto-worktree-lifecycle/proposal.md
  - openspec/changes/auto-worktree-lifecycle/design.md (the two-helper split)
  - openspec/changes/auto-worktree-lifecycle/specs/auto-worktree-lifecycle/spec.md
  - skills/common-pipeline-conventions/SKILL.md `## Auto-worktree lifecycle`
  - scripts/setup/worktree_paths.py (the sibling path-resolution helper)
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional


# ---- Constants ---------------------------------------------------------------

# The branch-name prefix that identifies an architect-team-created run
# worktree. Matches the existing Phase 8 default-branch-guard convention.
_BRANCH_PREFIX = "architect-team/"

# Slug sanitization — slash-command-derived slugs are kept conservative; only
# letters, digits, dashes, and underscores survive. The pipeline upstream
# normalizes free-text into kebab-case before passing it here, so this is a
# defensive sweep, not the primary normalizer.
_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


# ---- Public API --------------------------------------------------------------


def create_run_worktree(
    slug: str,
    base_branch: str = "main",
    parent_dir: Optional[Path] = None,
) -> Path:
    """Create an architect-team-run worktree and return its absolute path.

    Resolves `parent_dir` to the parent of `git rev-parse --show-toplevel`
    when not provided. Derives the repo name from that toplevel's basename.
    The candidate worktree path is `<parent_dir>/<repo-name>-<slug>/`; the
    candidate branch is `architect-team/<slug>`. If EITHER already exists
    (path on disk OR branch in `git branch --list`), the helper appends
    `-2`, then `-3`, ... until both are free.

    Then runs `git worktree add -b <branch> <path> <base_branch>` and
    returns the absolute path.

    Raises RuntimeError with an actionable message when:
      - the current directory is not inside a git repo,
      - the parent directory is not writable,
      - the base branch does not exist,
      - `git worktree add` fails for any other reason.
    """
    safe_slug = _sanitize_slug(slug)
    if not safe_slug:
        raise RuntimeError(
            f"create_run_worktree: slug {slug!r} contains no usable "
            f"characters after sanitization (only A-Za-z0-9_- survive)."
        )

    # Resolve the toplevel so we can name the repo and (when needed) default
    # the parent dir to its sibling.
    toplevel = _git_show_toplevel()
    if toplevel is None:
        raise RuntimeError(
            "create_run_worktree: current directory is not inside a git "
            "repository. Run `/architect-team --no-worktree ...` to skip "
            "the auto-worktree step, or `cd` into the project repo first."
        )

    repo_name = toplevel.name
    if parent_dir is None:
        parent_dir = toplevel.parent
    parent_dir = Path(parent_dir).resolve()
    if not parent_dir.is_dir():
        raise RuntimeError(
            f"create_run_worktree: parent directory {parent_dir} does not "
            f"exist. Pass an explicit parent_dir or `--no-worktree` to "
            f"skip the auto-worktree step."
        )

    # Verify the base branch resolves to a real ref BEFORE we start trying
    # to create the worktree — surfaces the actionable failure mode early.
    if not _git_branch_exists(base_branch):
        raise RuntimeError(
            f"create_run_worktree: base branch {base_branch!r} does not "
            f"exist in this repo. Pass --no-worktree to skip, or specify "
            f"an existing base branch."
        )

    # Resolve collisions: bump the suffix until BOTH the path AND the branch
    # are free.
    chosen_slug, worktree_path, branch_name = _resolve_collision(
        parent_dir=parent_dir,
        repo_name=repo_name,
        slug=safe_slug,
    )

    # Run `git worktree add -b <branch> <path> <base>` from the toplevel
    # so the new worktree is properly registered against the main repo.
    result = subprocess.run(
        [
            "git",
            "-C",
            str(toplevel),
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            base_branch,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"create_run_worktree: `git worktree add` failed for "
            f"branch={branch_name!r} path={worktree_path}. "
            f"stderr={result.stderr.strip()!r}. "
            f"Pass --no-worktree to skip the auto-worktree step."
        )

    return worktree_path.resolve()


def cleanup_run_worktree(
    worktree_path: Path,
    remove_branch: bool = False,
) -> None:
    """Remove a run worktree and (optionally) its branch.

    Runs `git worktree remove <path>`. When `remove_branch=True`, also runs
    `git branch -d architect-team/<slug>` where `<slug>` is derived from the
    worktree directory's basename suffix (`<repo>-<slug>` -> `<slug>`).

    Idempotent: a worktree that has already been removed (or never existed)
    is a no-op — subprocess errors that mean "not a worktree" are caught and
    swallowed.
    """
    worktree_path = Path(worktree_path)

    # Run from outside the worktree (the worktree may not exist; we need a
    # cwd that is still a valid git repo). The main repo's toplevel works.
    toplevel = _git_show_toplevel()
    cwd: Optional[str] = str(toplevel) if toplevel is not None else None

    cmd = ["git"]
    if cwd is not None:
        cmd.extend(["-C", cwd])
    cmd.extend(["worktree", "remove", str(worktree_path)])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").lower()
        # "is not a working tree" / "is not a registered" -> already gone;
        # treat as success per the idempotency contract.
        idempotent_markers = (
            "is not a working tree",
            "is not a registered",
            "no such file or directory",
            "not found",
        )
        if not any(marker in stderr for marker in idempotent_markers):
            # An unexpected failure — try `--force` once before giving up,
            # which handles the "locked / dirty worktree" cases users hit
            # after a crash.
            force_cmd = list(cmd) + ["--force"]
            force_result = subprocess.run(
                force_cmd, capture_output=True, text=True, check=False
            )
            if force_result.returncode != 0:
                raise RuntimeError(
                    f"cleanup_run_worktree: `git worktree remove` failed for "
                    f"{worktree_path}. stderr={result.stderr.strip()!r} "
                    f"(force-retry stderr={force_result.stderr.strip()!r})."
                )

    if not remove_branch:
        return

    slug = _slug_from_worktree_path(worktree_path)
    if slug is None:
        # No derivable slug -> nothing to delete; treat as no-op (still
        # idempotent).
        return

    branch_name = f"{_BRANCH_PREFIX}{slug}"
    branch_cmd = ["git"]
    if cwd is not None:
        branch_cmd.extend(["-C", cwd])
    branch_cmd.extend(["branch", "-d", branch_name])
    branch_result = subprocess.run(
        branch_cmd, capture_output=True, text=True, check=False
    )
    if branch_result.returncode != 0:
        stderr = (branch_result.stderr or "").lower()
        # "not found" / "no such branch" -> already gone; idempotent.
        # "not fully merged" -> the branch has unmerged work; surface it.
        if "not fully merged" in stderr:
            raise RuntimeError(
                f"cleanup_run_worktree: branch {branch_name!r} is not "
                f"fully merged into its upstream. Refusing to delete. "
                f"Use `git branch -D {branch_name}` manually if you are "
                f"sure the work is discardable."
            )
        if "not found" not in stderr and "no such branch" not in stderr:
            # Unexpected failure — but per the idempotency contract for the
            # worktree itself, branch deletion failures from "already gone"
            # are swallowed. Any other failure is silenced too (the worktree
            # is the primary artifact; branch hygiene is a courtesy).
            pass


def current_worktree_is_run() -> bool:
    """Return True iff the current branch starts with `architect-team/`.

    Used by the slash commands to detect re-entry — when invoked from
    inside an existing architect-team-run worktree, the auto-worktree step
    is a no-op (no nested worktrees). Best-effort: any subprocess failure
    (not in a git repo, git missing, detached HEAD that returns `HEAD`)
    returns False.
    """
    branch = _git_current_branch()
    if branch is None:
        return False
    return branch.startswith(_BRANCH_PREFIX)


def current_run_slug() -> Optional[str]:
    """Return the slug from the current branch name when in a run worktree.

    Returns the part after `architect-team/` when
    `git rev-parse --abbrev-ref HEAD` reports a branch matching the run
    pattern; returns None on a non-run branch (main, feature/foo, detached
    HEAD) or when git resolution fails.
    """
    branch = _git_current_branch()
    if branch is None:
        return None
    if not branch.startswith(_BRANCH_PREFIX):
        return None
    slug = branch[len(_BRANCH_PREFIX):]
    return slug if slug else None


# ---- v1.3.0 auto-cleanup helpers --------------------------------------------


def list_merged_architect_team_worktrees(
    against: str = "origin/main",
    exclude_current: bool = True,
) -> list[Path]:
    """Return paths of `architect-team/*` worktrees merged into `<against>`.

    Walks `git worktree list --porcelain` to get (path, branch) pairs, then
    for each worktree on a branch starting with `architect-team/` checks
    `git merge-base --is-ancestor <branch> <against>` — if the branch tip is
    reachable from `<against>` (exit 0), it's a merged worktree and its path
    is included in the result.

    When `exclude_current=True` (the default), the current worktree is
    omitted even if its branch is merged. This is the safety guard the slash
    commands rely on — auto-cleanup MUST NOT remove the cwd you're working
    in, even on a re-entry case where the current run's branch happened to
    be merged earlier.

    Non-`architect-team/*` branches are NEVER considered (the user's own
    worktrees stay untouched, regardless of merge state).

    Best-effort: any subprocess failure / not-in-a-git-repo / malformed
    porcelain returns an empty list rather than raising.
    """
    toplevel = _git_show_toplevel()
    if toplevel is None:
        return []

    current_worktree: Optional[Path] = None
    if exclude_current:
        # `git rev-parse --show-toplevel` from the cwd returns the CURRENT
        # worktree's path (not the main repo's path). That's exactly the
        # excluded-worktree value the safeguard needs.
        current_worktree = toplevel

    pairs = _parse_worktree_list_porcelain(toplevel)
    merged: list[Path] = []
    for worktree_path, branch in pairs:
        if not branch or not branch.startswith(_BRANCH_PREFIX):
            continue
        if exclude_current and current_worktree is not None:
            try:
                if worktree_path.resolve() == current_worktree.resolve():
                    continue
            except (OSError, RuntimeError):
                # Resolution failure -> err on the safe side, skip this path.
                continue
        if _branch_is_merged_into(toplevel, branch, against):
            merged.append(worktree_path)
    return merged


def cleanup_merged_worktrees(
    against: str = "origin/main",
    dry_run: bool = False,
) -> list[Path]:
    """Remove all merged `architect-team/*` worktrees and return their paths.

    Calls `list_merged_architect_team_worktrees(against=against,
    exclude_current=True)` under the hood — the current worktree is ALWAYS
    excluded; v1.3.0 does not expose an override.

    On `dry_run=True`, no filesystem change is made; the candidate list is
    returned verbatim (the paths that WOULD be cleaned).

    Otherwise calls `cleanup_run_worktree(path, remove_branch=True)` on each
    candidate, collects successes, and returns the list of paths actually
    cleaned. Idempotent: if a worktree disappears between list and remove
    (concurrent cleanup, manual `git worktree remove`), the helper skips
    that path gracefully and continues with the rest.
    """
    candidates = list_merged_architect_team_worktrees(
        against=against, exclude_current=True
    )
    if dry_run:
        return candidates

    cleaned: list[Path] = []
    for worktree_path in candidates:
        try:
            cleanup_run_worktree(worktree_path, remove_branch=True)
        except RuntimeError:
            # Per the idempotency contract, a vanished worktree is not a
            # failure — but a hard failure (locked, dirty, permission) IS
            # surfaced by cleanup_run_worktree. We swallow it here so one
            # bad worktree doesn't block cleanup of the others; the caller
            # sees a shorter `cleaned` list as the signal.
            continue
        cleaned.append(worktree_path)
    return cleaned


# ---- Internals ---------------------------------------------------------------


def _sanitize_slug(slug: str) -> str:
    """Strip slug characters that would confuse filesystem / git ref rules.

    Keeps `[A-Za-z0-9_-]`; collapses everything else into nothing. The
    pipeline upstream is responsible for the primary kebab-case
    normalization; this is a defensive sweep so the helper never tries to
    create `architect-team/foo bar/baz` or similar.
    """
    cleaned = _SAFE_SLUG_RE.sub("", slug or "").strip("-_")
    return cleaned


def _resolve_collision(
    parent_dir: Path,
    repo_name: str,
    slug: str,
) -> tuple[str, Path, str]:
    """Find an unused (slug, path, branch_name) triple.

    Tries `slug`, then `slug-2`, `slug-3`, ... until BOTH the candidate path
    AND the candidate branch are free. Bounded at 1000 attempts to avoid an
    infinite loop on a degenerately-cluttered repo.
    """
    suffix = 1
    while suffix < 1000:
        candidate_slug = slug if suffix == 1 else f"{slug}-{suffix}"
        candidate_path = parent_dir / f"{repo_name}-{candidate_slug}"
        candidate_branch = f"{_BRANCH_PREFIX}{candidate_slug}"
        if not candidate_path.exists() and not _git_branch_exists(
            candidate_branch
        ):
            return candidate_slug, candidate_path, candidate_branch
        suffix += 1
    raise RuntimeError(
        f"_resolve_collision: could not find a free slug after 999 "
        f"suffix attempts starting from {slug!r}. Manually clean up "
        f"stale worktrees / branches at {parent_dir}/{repo_name}-* and "
        f"branches matching {_BRANCH_PREFIX}{slug}-*."
    )


def _slug_from_worktree_path(worktree_path: Path) -> Optional[str]:
    """Derive the run slug from a worktree directory's basename.

    The worktree-naming convention is `<repo-name>-<slug>`. We split on the
    LAST hyphen by looking up the toplevel's basename and stripping the
    `<repo-name>-` prefix when it matches.

    Returns None when the basename does not match the convention (the
    caller treats this as "no derivable slug" -> branch cleanup is skipped).
    """
    basename = worktree_path.name
    toplevel = _git_show_toplevel()
    if toplevel is None:
        # No git context — fall back to a heuristic: everything after the
        # first hyphen is the slug. Better than nothing for cleanup ergonomics.
        if "-" in basename:
            return basename.split("-", 1)[1]
        return None
    repo_name = toplevel.name
    prefix = f"{repo_name}-"
    if basename.startswith(prefix):
        slug = basename[len(prefix):]
        return slug if slug else None
    # No match — be conservative and return None rather than guessing.
    return None


def _git_show_toplevel() -> Optional[Path]:
    """Return the repo's toplevel path, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    out = (result.stdout or "").strip()
    if not out:
        return None
    return Path(out).resolve()


def _git_current_branch() -> Optional[str]:
    """Return `git rev-parse --abbrev-ref HEAD`, or None on failure.

    Returns None when not in a git repo or on a detached HEAD (`HEAD`).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    out = (result.stdout or "").strip()
    if not out or out == "HEAD":
        return None
    return out


def _parse_worktree_list_porcelain(
    toplevel: Path,
) -> list[tuple[Path, Optional[str]]]:
    """Run `git worktree list --porcelain` and return (path, branch) pairs.

    The porcelain format groups each worktree as a block of `key value` lines
    terminated by a blank line. The relevant keys for v1.3.0 are:

      worktree <absolute path>
      branch refs/heads/<branch-name>           # only present when checked out
      detached                                  # alternative to branch

    Returns a list of (path, branch_name_or_None) pairs in the order git
    reports them. Branch is None for detached-HEAD worktrees. Best-effort:
    subprocess / parse errors return an empty list.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(toplevel),
                "worktree",
                "list",
                "--porcelain",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []

    pairs: list[tuple[Path, Optional[str]]] = []
    current_path: Optional[Path] = None
    current_branch: Optional[str] = None
    for raw_line in (result.stdout or "").splitlines():
        line = raw_line.rstrip()
        if not line:
            # Block terminator -> flush.
            if current_path is not None:
                pairs.append((current_path, current_branch))
            current_path = None
            current_branch = None
            continue
        if line.startswith("worktree "):
            # New block starts -> flush any previous one defensively (no
            # blank-line terminator at EOF).
            if current_path is not None:
                pairs.append((current_path, current_branch))
                current_branch = None
            current_path = Path(line[len("worktree "):]).resolve()
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            if ref.startswith("refs/heads/"):
                current_branch = ref[len("refs/heads/"):]
            else:
                current_branch = ref
        elif line == "detached":
            current_branch = None
    if current_path is not None:
        pairs.append((current_path, current_branch))
    return pairs


def _branch_is_merged_into(toplevel: Path, branch: str, against: str) -> bool:
    """Return True iff `<branch>` tip is reachable from `<against>`.

    Runs `git merge-base --is-ancestor <branch> <against>`:
      - exit 0 -> branch is fully merged (fast-forward or merge-commit) -> True
      - exit 1 -> branch is not an ancestor -> False (un-merged, or merged via
        squash where the SHA differs)
      - any other exit / subprocess failure -> False (safe default; don't
        auto-clean on an ambiguous probe)
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(toplevel),
                "merge-base",
                "--is-ancestor",
                branch,
                against,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _git_branch_exists(branch: str) -> bool:
    """Return True iff the named branch (or ref) resolves locally.

    Uses `git rev-parse --verify --quiet refs/heads/<branch>` for local
    branches; falls back to `git rev-parse --verify --quiet <branch>` for
    refs (tags, remote-tracking branches) so a base-branch named `origin/main`
    still resolves cleanly.
    """
    # First try as a local branch.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode == 0:
        return True
    # Fall back to the general ref form (covers tags, remote-tracking
    # branches, abbreviated SHA, etc.).
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", branch],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
