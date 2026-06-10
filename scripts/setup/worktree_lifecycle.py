#!/usr/bin/env python3
"""Worktree-lifecycle helper for the architect-team plugin (v1.2.0 + v1.3.0 + v3.6.0).

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

  list_merged_architect_team_worktrees(against="origin/main", exclude_current=True, include_squash_merged=False) -> list[Path]
      (v1.3.0) Return paths of architect-team/* worktrees whose branch is
      merged into <against>. Excludes the current worktree by default
      (safety: don't auto-remove the cwd even if its branch happens to be
      merged). Branches NOT starting with `architect-team/` are never
      considered. (lineage P6 / REQ-CDL-11a) When `include_squash_merged=True`,
      the squash-aware predicate `_branch_is_merged_or_squash_merged` is used so
      squash-merged branches are also recognized; default False keeps the
      conservative `merge-base --is-ancestor` behavior (the documented v1.3.0
      safe false-negative for squash merges).

  cleanup_merged_worktrees(against="origin/main", dry_run=False, include_squash_merged=False) -> list[Path]
      (v1.3.0) Remove all merged architect-team/* worktrees. Returns paths
      cleaned (or that would-be-cleaned in dry_run mode). Idempotent on a
      worktree that disappears between list and remove. (lineage P6 /
      REQ-CDL-11a) `include_squash_merged=True` opts in to squash-merge
      detection via `_branch_is_merged_or_squash_merged`; default False
      preserves today's plain-ancestor-only behavior.

  finalize_run_worktree(worktree_path=None, against="origin/main", branch=None) -> dict
      (v3.6.0) End-of-run merge check: remove the run's worktree + branch
      when its `architect-team/<slug>` branch is already merged into
      <against>; otherwise leave the worktree intact and return a persistence
      warning naming the path + the manual cleanup command. Best-effort: any
      subprocess failure is reflected in the returned dict rather than raised.

  list_run_branches(against="origin/main", remote="origin", include_squash_merged=False) -> list[dict]
      (v3.7.0 auto-merge-to-main) Enumerate every local `architect-team/*`
      branch and, for each, report `{branch, worktree_path, merged_into_main,
      squash_merged, cleanly_mergeable}`. Powers the startup
      branch-reconciliation prompt. Non-`architect-team/*` branches are never
      included; best-effort `[]`. (lineage P6 / REQ-CDL-11a) The `squash_merged`
      field is always populated (`_branch_is_squash_merged`); when
      `include_squash_merged=True` a branch counts as merged-for-cleanup if it is
      EITHER a plain ancestor OR squash-merged, default False keeps the
      conservative plain-ancestor-only treatment.

  recommend_worktree(task_scope=None) -> dict
      (lineage P6 / REQ-CDL-11b) Advisory-only heuristic returning
      `{"use_worktree": bool, "reason": str}` for whether the auto-worktree
      default should fire for a task of the given scope. Tiny / trivial /
      doc-only / single-file scopes recommend False; small..large / feature /
      multi-file / None recommend True. ADVISORY ONLY — `--no-worktree` is
      always honored regardless of this recommendation, and the default when
      `task_scope` is None stays True (today's behavior).

  merge_branch_to_main_and_prune(branch, worktree_path=None, against="main", remote="origin", push=True) -> dict
      (v3.7.0 auto-merge-to-main) Merge a cleanly-mergeable
      `architect-team/<slug>` branch into <against>, push, delete the branch
      (local + remote), and remove its worktree — ONLY when it merges cleanly.
      Conflicts are skipped + reported (never forced); a rejected push (branch
      protection) stops pruning and leaves the work recoverable (never
      --force). Best-effort: returns a dict, never raises.

Squash-merge detection (lineage P6 / REQ-CDL-11a)
-------------------------------------------------

The default merged-probe `_branch_is_merged_into` uses
`git merge-base --is-ancestor`, which MISSES squash-merges: a squash merge
replays the branch's net diff as a SINGLE NEW commit on <against>, so the
original branch tip is never an ancestor of <against>. The opt-in
`include_squash_merged=True` flag (on `list_run_branches`,
`cleanup_merged_worktrees`, and `list_merged_architect_team_worktrees`) swaps
in the squash-aware predicate `_branch_is_merged_or_squash_merged`.

`_branch_is_squash_merged` is deliberately CONSERVATIVE — it must never flag a
branch that still has genuinely-unmerged work. A branch counts as
squash-merged iff (a) it has >= 1 commit beyond the merge-base with <against>
(otherwise there is nothing to judge) AND (b) it is NOT already a plain
ancestor (that is the normal-merge path; this predicate strictly ADDS the
squash case) AND (c) the branch's net diff is already fully present in
<against>, probed via `git diff --quiet <against>..<branch>` exiting 0 (the
branch tip tree contributes no net change over <against>). The probe is the
two-dot tip-vs-tip form, not three-dot: after a squash merge the branch's
merge-base with <against> is unchanged, so three-dot `<against>...<branch>`
would still show the branch's own changes and false-negative every squash —
exactly the case this exists to catch. Any subprocess error returns False — on
ambiguity we never delete unmerged work. The default
(`include_squash_merged=False`) keeps today's plain-ancestor-only behavior, the
documented v1.3.0 safe false-negative.

Naming conventions
------------------

- Branch: `architect-team/<slug>` (matches the existing Phase 8
  default-branch-guard convention).
- Worktree directory (v3.6.0): `<parent-of-repo>/.<repo-name>-worktrees/<slug>/`
  — a single hidden per-project container collects every run worktree (e.g.
  repo at `/Users/foo/projects/myapp` with slug `add-billing` -> worktree at
  `/Users/foo/projects/.myapp-worktrees/add-billing/`). The old flat layout
  `<parent>/<repo-name>-<slug>/` is still recognized by cleanup +
  slug-derivation for backward compatibility with pre-v3.6.0 on-disk
  worktrees.
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

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---- Constants ---------------------------------------------------------------

# The branch-name prefix that identifies an architect-team-created run
# worktree. Matches the existing Phase 8 default-branch-guard convention.
_BRANCH_PREFIX = "architect-team/"

# (A7 review-remediation) Bounded timeouts for git subprocess calls. Local git
# ops are fast; the network push ops can hang forever on a credential prompt —
# the headline fix. A TimeoutExpired is routed into the SAME best-effort failure
# path each call already takes on a non-zero return code (never raised to the
# top). Template: scripts/setup/install_mempalace.py:71-78.
_LOCAL_GIT_TIMEOUT = 60  # seconds — status / rev-parse / branch / worktree / merge
_NETWORK_GIT_TIMEOUT = 300  # seconds — git push / git push --delete

# Slug sanitization — slash-command-derived slugs are kept conservative; only
# letters, digits, dashes, and underscores survive. The pipeline upstream
# normalizes free-text into kebab-case before passing it here, so this is a
# defensive sweep, not the primary normalizer.
_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")

# (lineage P6 / REQ-CDL-11b) Task scopes for which the auto-worktree default is
# NOT recommended — a worktree's filesystem-isolation overhead isn't worth it
# for a tiny / single-file / doc-only change. `recommend_worktree` is ADVISORY
# only; `--no-worktree` is honored independently and None still defaults to True.
_NO_WORKTREE_SCOPES = frozenset({"tiny", "trivial", "doc-only", "single-file"})
# Scopes for which the auto-worktree default SHOULD fire. (None also -> True.)
_WORKTREE_SCOPES = frozenset(
    {"small", "medium", "large", "feature", "multi-file"}
)


# ---- Subprocess helper (A7 review-remediation) -------------------------------


def _git_run(
    cmd: list[str],
    *,
    timeout: int = _LOCAL_GIT_TIMEOUT,
) -> subprocess.CompletedProcess:
    """Run a git subprocess with explicit UTF-8 decoding + a bounded timeout.

    (A7 review-remediation) Every text-mode subprocess call in this module goes
    through here so that:

      - `encoding="utf-8", errors="replace"` replaces the implicit locale codec
        (`text=True` alone), which mojibakes / `UnicodeDecodeError`s on a
        non-ASCII branch or worktree path under cp1252. Template:
        scripts/setup/install_mempalace.py:71-78.
      - a bounded `timeout=` guarantees forward progress; the network push ops
        (which can hang forever on a credential prompt) pass
        `_NETWORK_GIT_TIMEOUT`, local ops the default `_LOCAL_GIT_TIMEOUT`.
      - `subprocess.TimeoutExpired` is routed into the SAME best-effort failure
        path every caller already takes on a non-zero return code: a synthetic
        `CompletedProcess` with returncode 124 (the conventional timeout code)
        is returned instead of letting the exception escape to the top. Callers
        wrapped in `except (OSError, subprocess.SubprocessError)` would catch a
        timeout too (TimeoutExpired ⊂ SubprocessError), but returning the
        synthetic result makes the routing uniform for the unwrapped public-API
        callers (create / cleanup / merge) as well.

    `OSError` (e.g. git binary missing) is NOT swallowed here — callers that
    already wrap their call in `except (OSError, ...)` rely on it propagating to
    their own handler; the unwrapped public-API callers historically let an
    OSError surface (a missing git is a genuinely fatal environment error), and
    A7 does not change that contract.
    """
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=124,
            stdout="",
            stderr=f"timed out after {timeout}s",
        )


# ---- Public API --------------------------------------------------------------


def create_run_worktree(
    slug: str,
    base_branch: str = "main",
    parent_dir: Optional[Path] = None,
) -> Path:
    """Create an architect-team-run worktree and return its absolute path.

    Resolves `parent_dir` to the parent of `git rev-parse --show-toplevel`
    when not provided. Derives the repo name from that toplevel's basename.
    The candidate worktree path is
    `<parent_dir>/.<repo-name>-worktrees/<slug>/` (the hidden per-project
    container, v3.6.0); the candidate branch is `architect-team/<slug>`. If
    EITHER already exists (path on disk OR branch in `git branch --list`),
    the helper appends `-2`, then `-3`, ... until both are free.

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

    # Ensure the hidden per-project container exists before `git worktree add`
    # (v3.6.0). `git worktree add` creates leaf + parents on its own, but we
    # create the container explicitly so its existence is unambiguous and so
    # collision-resolution above can stat candidate paths inside it.
    container = _container_dir(parent_dir, repo_name)
    container.mkdir(parents=True, exist_ok=True)

    # Run `git worktree add -b <branch> <path> <base>` from the toplevel
    # so the new worktree is properly registered against the main repo.
    result = _git_run(
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

    result = _git_run(cmd)
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
            force_result = _git_run(force_cmd)
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
    branch_result = _git_run(branch_cmd)
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
    include_squash_merged: bool = False,
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

    (lineage P6 / REQ-CDL-11a) When `include_squash_merged=True`, the
    squash-aware predicate `_branch_is_merged_or_squash_merged` is used so a
    branch whose net diff has been squash-merged into `<against>` (no longer a
    plain ancestor) is also recognized. The default `False` keeps the
    conservative `merge-base --is-ancestor` behavior — the documented v1.3.0
    safe false-negative for squash merges.

    Non-`architect-team/*` branches are NEVER considered (the user's own
    worktrees stay untouched, regardless of merge state).

    Best-effort: any subprocess failure / not-in-a-git-repo / malformed
    porcelain returns an empty list rather than raising.
    """
    predicate = (
        _branch_is_merged_or_squash_merged
        if include_squash_merged
        else _branch_is_merged_into
    )
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
        if predicate(toplevel, branch, against):
            merged.append(worktree_path)
    return merged


def cleanup_merged_worktrees(
    against: str = "origin/main",
    dry_run: bool = False,
    include_squash_merged: bool = False,
) -> list[Path]:
    """Remove all merged `architect-team/*` worktrees and return their paths.

    Calls `list_merged_architect_team_worktrees(against=against,
    exclude_current=True)` under the hood — the current worktree is ALWAYS
    excluded; v1.3.0 does not expose an override.

    (lineage P6 / REQ-CDL-11a) `include_squash_merged=True` is forwarded to
    `list_merged_architect_team_worktrees`, opting in to squash-merge detection
    via `_branch_is_merged_or_squash_merged`; default `False` preserves today's
    plain-ancestor-only behavior.

    On `dry_run=True`, no filesystem change is made; the candidate list is
    returned verbatim (the paths that WOULD be cleaned).

    Otherwise calls `cleanup_run_worktree(path, remove_branch=True)` on each
    candidate, collects successes, and returns the list of paths actually
    cleaned. Idempotent: if a worktree disappears between list and remove
    (concurrent cleanup, manual `git worktree remove`), the helper skips
    that path gracefully and continues with the rest.
    """
    candidates = list_merged_architect_team_worktrees(
        against=against,
        exclude_current=True,
        include_squash_merged=include_squash_merged,
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


# ---- v3.6.0 end-of-run merge check ------------------------------------------


def finalize_run_worktree(
    worktree_path: Optional[Path] = None,
    against: str = "origin/main",
    branch: Optional[str] = None,
) -> dict:
    """End-of-run worktree disposition (v3.6.0).

    If the run's architect-team/<slug> branch is already merged into <against>,
    remove the worktree + branch and return {removed: True, ...}. Otherwise
    leave the worktree intact and return a persistence warning. A no-op (no
    removal) when the worktree is not on an architect-team/* branch.

    Best-effort: any subprocess failure is reflected in the returned dict
    rather than raised. Returns a dict with keys:
      removed (bool), merged (bool), reason (str), warning (str|None),
      branch (str|None), worktree_path (str).
    """
    worktree_path = Path(worktree_path) if worktree_path is not None else Path.cwd()
    base = {
        "removed": False,
        "merged": False,
        "reason": "",
        "warning": None,
        "branch": branch,
        "worktree_path": str(worktree_path),
    }

    # Resolve the branch from the worktree's HEAD when not supplied.
    if branch is None:
        branch = _git_branch_for_worktree(worktree_path)
    base["branch"] = branch

    if branch is None or not branch.startswith(_BRANCH_PREFIX):
        return {**base, "reason": "not-a-run-worktree"}

    toplevel = _git_show_toplevel()
    if toplevel is None:
        return {**base, "reason": "no-git-context"}

    merged = _branch_is_merged_into(toplevel, branch, against)
    if merged:
        try:
            cleanup_run_worktree(worktree_path, remove_branch=True)
        except RuntimeError:
            deferred = (
                f"Worktree {worktree_path} (branch {branch}) is merged into "
                f"{against} but could not be auto-removed (likely because it "
                f"is the current directory). The next run's sweep "
                f"(cleanup_merged_worktrees) will remove it. To remove it "
                f"now: git worktree remove {worktree_path} && "
                f"git branch -d {branch}"
            )
            return {
                **base,
                "merged": True,
                "reason": "merge-detected-removal-deferred",
                "warning": deferred,
            }
        return {
            **base,
            "removed": True,
            "merged": True,
            "reason": "merged-removed",
        }

    warning = (
        f"Worktree {worktree_path} (branch {branch}) was NOT removed: its "
        f"branch is not yet merged into {against}. The folder will persist "
        f"on disk until the branch is merged (then the next run's sweep "
        f"removes it). To remove it now: git worktree remove {worktree_path} "
        f"&& git branch -d {branch}"
    )
    return {**base, "reason": "unmerged-retained", "warning": warning}


# ---- v3.7.0 auto-merge-to-main ----------------------------------------------


def list_run_branches(
    against: str = "origin/main",
    remote: str = "origin",
    include_squash_merged: bool = False,
) -> list[dict]:
    """Return one descriptor per local `architect-team/*` branch (v3.7.0).

    `against` defaults to `origin/main` (v3.8.0 — was `main`) so the
    "already-merged?" judgments here AGREE with the v1.3.0 sweep
    (`cleanup_merged_worktrees` / `list_merged_architect_team_worktrees`,
    also `origin/main`): the startup reconciliation filters this list against
    the SAME published ref the sweep prunes against, and a branch already
    landed on `origin/main` via a GitHub PR merge is correctly seen as merged
    (a stale local `main` would have missed it). This is the deliberate split
    in the module's API: the "is it already merged / safe to prune?" checks
    (`list_run_branches`, the sweep, `finalize_run_worktree`) judge against the
    PUBLISHED `origin/main`, whereas `merge_branch_to_main_and_prune` /
    `_branch_cleanly_mergeable` operate against LOCAL `main` because that is the
    ref `git checkout main && git merge` actually integrates into. Callers run
    `git fetch origin main` first (the startup sweep does), so the two refs are
    in sync at decision time; pass `against="main"` explicitly to judge against
    the local checkout instead.

    Enumerates local branches via
    `git branch --list 'architect-team/*' --format '%(refname:short)'`, maps
    each to its checked-out worktree (from `git worktree list --porcelain`),
    and computes `merged_into_main`, `squash_merged`
    (`_branch_is_squash_merged`), and `cleanly_mergeable`
    (`_branch_cleanly_mergeable`).

    Each element is a dict:
      {"branch": <name>,
       "worktree_path": <str path or None>,
       "merged_into_main": <bool>,
       "squash_merged": <bool>,
       "cleanly_mergeable": <bool>}

    `squash_merged` is ALWAYS populated for transparency. (lineage P6 /
    REQ-CDL-11a) By default `merged_into_main` reflects ONLY plain
    `_branch_is_merged_into` (the conservative v1.3.0 behavior); when
    `include_squash_merged=True`, `merged_into_main` is the squash-aware
    `_branch_is_merged_or_squash_merged` so a squash-merged branch is reported
    as merged.

    Non-`architect-team/*` branches are NEVER included. Best-effort: any
    subprocess failure / not-in-a-git-repo returns an empty list.
    """
    toplevel = _git_show_toplevel()
    if toplevel is None:
        return []

    try:
        result = _git_run(
            [
                "git",
                "-C",
                str(toplevel),
                "branch",
                "--list",
                f"{_BRANCH_PREFIX}*",
                "--format",
                "%(refname:short)",
            ],
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []

    branches = [
        line.strip()
        for line in (result.stdout or "").splitlines()
        if line.strip().startswith(_BRANCH_PREFIX)
    ]

    # Build branch -> worktree_path from the porcelain listing.
    worktree_for_branch: dict[str, Path] = {}
    for worktree_path, branch in _parse_worktree_list_porcelain(toplevel):
        if branch and branch.startswith(_BRANCH_PREFIX):
            worktree_for_branch[branch] = worktree_path

    descriptors: list[dict] = []
    for branch in branches:
        wt = worktree_for_branch.get(branch)
        plain_merged = _branch_is_merged_into(toplevel, branch, against)
        squash_merged = _branch_is_squash_merged(toplevel, branch, against)
        merged_into_main = (
            (plain_merged or squash_merged)
            if include_squash_merged
            else plain_merged
        )
        descriptors.append(
            {
                "branch": branch,
                "worktree_path": str(wt) if wt is not None else None,
                "merged_into_main": merged_into_main,
                "squash_merged": squash_merged,
                "cleanly_mergeable": _branch_cleanly_mergeable(
                    toplevel, branch, against
                ),
            }
        )
    return descriptors


def merge_branch_to_main_and_prune(
    branch: str,
    worktree_path: Optional[str] = None,
    against: str = "main",
    remote: str = "origin",
    push: bool = True,
) -> dict:
    """Merge a clean run-branch into <against>, push, and prune (v3.7.0).

    Only acts on cleanly-mergeable `architect-team/*` branches. The flow:
      1. Guard: branch must start with `architect-team/`.
      2. Probe clean-mergeability (no working-tree mutation). Conflict ->
         change nothing, return conflict.
      3. `git checkout <against>` then `git merge --no-ff <branch>`. An
         unexpected merge conflict aborts and returns conflict.
      4. When `push`: `git push <remote> <against>`. A rejected push (branch
         protection) STOPS pruning and leaves the work recoverable — NEVER
         --force.
      5. Delete the branch (local `-d`, and remote when pushed) and remove the
         worktree (`cleanup_run_worktree`, branch already deleted).

    The returned dict ALWAYS carries the keys: merged, pushed, branch_deleted,
    worktree_removed, conflict, reason, branch, worktree_path. Best-effort —
    never raises.
    """
    base = {
        "merged": False,
        "pushed": False,
        "branch_deleted": False,
        "worktree_removed": False,
        "conflict": False,
        "reason": "",
        "branch": branch,
        "worktree_path": worktree_path,
    }

    if not isinstance(branch, str) or not branch.startswith(_BRANCH_PREFIX):
        return {**base, "reason": "not-a-run-branch"}

    toplevel = _git_show_toplevel()
    if toplevel is None:
        return {**base, "reason": "no-git-context"}

    # Capture the worktree path up front (from porcelain) so pruning still
    # works after the merge, even though the merge runs from <against>.
    if worktree_path is None:
        for wt, wt_branch in _parse_worktree_list_porcelain(toplevel):
            if wt_branch == branch:
                worktree_path = str(wt)
                break
        base["worktree_path"] = worktree_path

    if not _branch_cleanly_mergeable(toplevel, branch, against):
        return {**base, "conflict": True, "reason": "conflict"}

    # Check out <against> in the MAIN worktree.
    checkout = _git_run(
        ["git", "-C", str(toplevel), "checkout", against],
    )
    if checkout.returncode != 0:
        return {**base, "reason": "checkout-failed"}

    # Merge --no-ff. An unexpected conflict aborts and changes nothing.
    merge = _git_run(
        [
            "git",
            "-C",
            str(toplevel),
            "merge",
            "--no-ff",
            branch,
            "-m",
            f"Merge {branch}",
        ],
    )
    if merge.returncode != 0:
        _git_run(
            ["git", "-C", str(toplevel), "merge", "--abort"],
        )
        return {**base, "conflict": True, "reason": "conflict-on-merge"}

    merged = {**base, "merged": True}

    pushed = False
    if push:
        # Network op — the headline A7 fix: bounded timeout so a hung
        # credential prompt cannot hang the run forever; TimeoutExpired routes
        # to the push-rejected best-effort branch via _git_run's returncode 124.
        push_result = _git_run(
            ["git", "-C", str(toplevel), "push", remote, against],
            timeout=_NETWORK_GIT_TIMEOUT,
        )
        if push_result.returncode != 0:
            # Branch protection / non-fast-forward rejection: STOP pruning,
            # leave the branch + worktree recoverable. NEVER --force.
            return {
                **merged,
                "pushed": False,
                "reason": "push-rejected",
            }
        pushed = True

    merged = {**merged, "pushed": pushed}

    # Remove the worktree FIRST — git refuses to delete a branch that is still
    # checked out in a worktree. cleanup_run_worktree(remove_branch=False) so
    # we control the branch deletion explicitly below.
    worktree_removed = False
    if worktree_path:
        try:
            cleanup_run_worktree(Path(worktree_path), remove_branch=False)
            worktree_removed = True
        except RuntimeError:
            worktree_removed = False

    # Delete the local branch (it's merged, so `-d` succeeds).
    branch_deleted = False
    del_local = _git_run(
        ["git", "-C", str(toplevel), "branch", "-d", branch],
    )
    if del_local.returncode == 0:
        branch_deleted = True

    if pushed:
        # Best-effort remote delete; ignore "remote ref does not exist".
        # Network op — bounded timeout (A7).
        _git_run(
            ["git", "-C", str(toplevel), "push", remote, "--delete", branch],
            timeout=_NETWORK_GIT_TIMEOUT,
        )

    return {
        **merged,
        "branch_deleted": branch_deleted,
        "worktree_removed": worktree_removed,
        "reason": "merged-and-pruned",
    }


# ---- lineage P6 task-aware worktree heuristic (REQ-CDL-11b) -----------------


def recommend_worktree(task_scope: Optional[str] = None) -> dict:
    """Advise whether the auto-worktree default should fire for a task.

    (lineage P6 / REQ-CDL-11b) ADVISORY ONLY. Returns
    `{"use_worktree": bool, "reason": str}`.

    Mapping:
      - `task_scope` in {tiny, trivial, doc-only, single-file}
        -> `{use_worktree: False, ...}` (filesystem isolation isn't worth the
        overhead for a change this small).
      - `task_scope` in {small, medium, large, feature, multi-file} OR None
        -> `{use_worktree: True, ...}` (the safe default — keeps the user's
        main checkout put and isolates the run).
      - any other / unrecognized scope -> `{use_worktree: True, ...}` (lean
        toward the isolating default rather than guessing the task is trivial).

    This recommendation NEVER overrides the user: `--no-worktree` (and its
    natural-language equivalents) is always honored regardless of what this
    returns, and the default when `task_scope` is None stays True — today's
    v1.2.0 behavior. The caller may use this as an additional hint (e.g. to
    skip the worktree for an obviously doc-only ask) but the flag wins.
    """
    scope = task_scope.strip().lower() if isinstance(task_scope, str) else task_scope

    if scope in _NO_WORKTREE_SCOPES:
        return {
            "use_worktree": False,
            "reason": (
                f"task_scope={scope!r} is small enough (tiny / trivial / "
                f"doc-only / single-file) that a dedicated worktree's "
                f"isolation overhead is not warranted; advisory only — "
                f"--no-worktree is honored regardless."
            ),
        }

    if scope is None:
        return {
            "use_worktree": True,
            "reason": (
                "task_scope unspecified -> default to a worktree (today's "
                "v1.2.0 behavior); advisory only — --no-worktree is honored "
                "regardless."
            ),
        }

    if scope in _WORKTREE_SCOPES:
        return {
            "use_worktree": True,
            "reason": (
                f"task_scope={scope!r} is substantial enough (small..large / "
                f"feature / multi-file) to warrant filesystem isolation via a "
                f"dedicated worktree; advisory only — --no-worktree is honored "
                f"regardless."
            ),
        }

    return {
        "use_worktree": True,
        "reason": (
            f"task_scope={scope!r} is unrecognized -> lean toward the "
            f"isolating worktree default rather than assuming the task is "
            f"trivial; advisory only — --no-worktree is honored regardless."
        ),
    }


# ---- Internals ---------------------------------------------------------------


def _container_dir(parent_dir: Path, repo_name: str) -> Path:
    """The hidden per-project worktree container: <parent>/.<repo>-worktrees/."""
    return parent_dir / f".{repo_name}-worktrees"


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
    container = _container_dir(parent_dir, repo_name)
    suffix = 1
    while suffix < 1000:
        candidate_slug = slug if suffix == 1 else f"{slug}-{suffix}"
        candidate_path = container / candidate_slug
        candidate_branch = f"{_BRANCH_PREFIX}{candidate_slug}"
        if not candidate_path.exists() and not _git_branch_exists(
            candidate_branch
        ):
            return candidate_slug, candidate_path, candidate_branch
        suffix += 1
    raise RuntimeError(
        f"_resolve_collision: could not find a free slug after 999 "
        f"suffix attempts starting from {slug!r}. Manually clean up "
        f"stale worktrees / branches at {container}/* and "
        f"branches matching {_BRANCH_PREFIX}{slug}-*."
    )


def _slug_from_worktree_path(worktree_path: Optional[Path]) -> Optional[str]:
    """Derive the run slug from a worktree directory's path (dual-layout).

    Two layouts are recognized (v3.6.0):
      - NEW container layout: `<parent>/.<repo>-worktrees/<slug>/` — the slug
        is the basename and the parent dir is `.<repo>-worktrees`.
      - OLD flat layout: `<parent>/<repo>-<slug>/` — the slug is the basename
        after the `<repo>-` prefix.

    Returns None when neither layout matches (the caller treats this as "no
    derivable slug" -> branch cleanup is skipped). Defensive against a None /
    pathless input.
    """
    if worktree_path is None:
        return None
    worktree_path = Path(worktree_path)
    basename = worktree_path.name
    parent_name = worktree_path.parent.name if worktree_path.parent is not None else ""

    toplevel = _git_show_toplevel()
    if toplevel is not None:
        repo_name = toplevel.name
        # NEW layout: parent dir is the hidden container `.<repo>-worktrees`.
        if parent_name == f".{repo_name}-worktrees":
            return basename or None
        # OLD layout: basename is `<repo>-<slug>`.
        prefix = f"{repo_name}-"
        if basename.startswith(prefix):
            slug = basename[len(prefix):]
            return slug if slug else None
        # No match — be conservative and return None rather than guessing.
        return None

    # No git context — fall back to heuristics.
    # NEW layout heuristic: parent dir looks like `.<something>-worktrees`.
    if parent_name.startswith(".") and parent_name.endswith("-worktrees"):
        return basename or None
    # OLD layout heuristic: everything after the first hyphen is the slug.
    if "-" in basename:
        return basename.split("-", 1)[1]
    return None


def _git_show_toplevel() -> Optional[Path]:
    """Return the repo's toplevel path, or None if not in a git repo."""
    try:
        result = _git_run(
            ["git", "rev-parse", "--show-toplevel"],
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
        result = _git_run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    out = (result.stdout or "").strip()
    if not out or out == "HEAD":
        return None
    return out


def _git_branch_for_worktree(worktree_path: Path) -> Optional[str]:
    """Return the current branch of the worktree at `<worktree_path>`.

    Runs `git -C <worktree_path> rev-parse --abbrev-ref HEAD`. Returns None
    when the path is not a git worktree, on a detached HEAD (`HEAD`), or on
    any subprocess failure.
    """
    try:
        result = _git_run(
            [
                "git",
                "-C",
                str(worktree_path),
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
            ],
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
        result = _git_run(
            [
                "git",
                "-C",
                str(toplevel),
                "worktree",
                "list",
                "--porcelain",
            ],
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
        result = _git_run(
            [
                "git",
                "-C",
                str(toplevel),
                "merge-base",
                "--is-ancestor",
                branch,
                against,
            ],
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _branch_is_squash_merged(
    toplevel: Path, branch: str, against: str = "origin/main"
) -> bool:
    """Return True iff `<branch>` has been SQUASH-merged into `<against>`.

    (lineage P6 / REQ-CDL-11a) A squash merge replays the branch's net diff as
    a single new commit on `<against>`, so the branch tip is NOT an ancestor of
    `<against>` and `_branch_is_merged_into` returns False even though the work
    is fully present. This predicate fills exactly that gap, and ONLY that gap.

    Conservative — must never flag a branch that still has genuinely-unmerged
    work. A branch is squash-merged iff ALL of:
      (a) it has >= 1 commit beyond the merge-base with `<against>` (otherwise
          there is nothing to judge -> False);
      (b) it is NOT already a plain ancestor of `<against>` (that is the
          normal-merge path; this predicate strictly ADDS the squash case
          -> False when already a plain ancestor);
      (c) the branch's net diff is already fully present in `<against>` —
          probed via `git diff --quiet <against>..<branch>` (a direct
          tip-tree-vs-tip-tree comparison). Exit 0 means the branch tip tree
          contributes NO net change over `<against>` -> nothing left to merge
          -> effectively merged (incl. squash). Exit 1 means there IS un-merged
          work -> False.

    Implementation note on (c): the requirement framed this as "the net diff
    the branch would contribute is already present in <against>". The two-dot
    `<against>..<branch>` form is the probe that actually expresses this in
    git's model. After a squash merge, the branch tip is NOT a descendant of
    `<against>` and their merge-base is the ORIGINAL pre-squash commit, so the
    three-dot `<against>...<branch>` form still shows the branch's own changes
    (its merge-base hasn't moved) and would FALSE-NEGATIVE every squash — i.e.
    it never detects the case this function exists to detect. Two-dot compares
    the two tip trees directly, so it is empty exactly when the branch's work is
    already reflected in `<against>` (the squash-merge signature). Guard (a)
    keeps an all-revert / no-op branch from being mistaken for squash-merged by
    requiring real commits beyond the merge-base; guard (b) reserves the plain-
    ancestor case for the normal-merge predicate.

    Any subprocess error / indeterminate probe returns False — on ambiguity we
    never treat a branch as merged (so we never delete unmerged work).
    """
    if not isinstance(branch, str) or not branch:
        return False

    # (b) Already a plain ancestor? Then it's the normal-merge path, not the
    # squash case this predicate is responsible for.
    if _branch_is_merged_into(toplevel, branch, against):
        return False

    # (a) Must have >= 1 commit beyond the merge-base, else nothing to judge.
    merge_base = _git_merge_base(toplevel, against, branch)
    if merge_base is None:
        return False
    try:
        ahead = _git_run(
            [
                "git",
                "-C",
                str(toplevel),
                "rev-list",
                "--count",
                f"{merge_base}..{branch}",
            ],
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if ahead.returncode != 0:
        return False
    count_str = (ahead.stdout or "").strip()
    try:
        if int(count_str) < 1:
            return False
    except ValueError:
        return False

    # (c) Is the branch's net diff already in <against>? Two-dot
    # `<against>..<branch>` compares the two tip trees directly; `--quiet` exits
    # 0 when there is NO diff (the branch contributes nothing new -> merged,
    # incl. squash) and 1 when there IS a diff (real un-merged work). Any other
    # exit code (e.g. 128 on a bad ref) is treated as indeterminate -> not
    # squash-merged. (See the docstring for why two-dot, not three-dot.)
    try:
        diff = _git_run(
            [
                "git",
                "-C",
                str(toplevel),
                "diff",
                "--quiet",
                f"{against}..{branch}",
            ],
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return diff.returncode == 0


def _branch_is_merged_or_squash_merged(
    toplevel: Path, branch: str, against: str = "origin/main"
) -> bool:
    """True iff `<branch>` is a plain-merged OR squash-merged into `<against>`.

    (lineage P6 / REQ-CDL-11a) The squash-aware union predicate the opt-in
    `include_squash_merged=True` paths use: `_branch_is_merged_into(...)` OR
    `_branch_is_squash_merged(...)`.
    """
    return _branch_is_merged_into(
        toplevel, branch, against
    ) or _branch_is_squash_merged(toplevel, branch, against)


def _branch_cleanly_mergeable(
    toplevel: Path, branch: str, against: str = "main"
) -> bool:
    """Return True iff `<branch>` merges into `<against>` without conflict.

    Probes with `git merge-tree --write-tree <against> <branch>` (git >= 2.38)
    — a pure in-memory merge that NEVER touches the working tree. Clean iff
    the command exits 0 AND the output contains no `CONFLICT` / `<<<<<<<`
    markers.

    Defensive fallback for old git / OSError: try the legacy 3-arg
    `git merge-tree <merge-base> <against> <branch>` form (also read-only) and
    treat the presence of conflict markers as not-clean. When the probe is
    truly indeterminate, return False (safer: don't claim clean). NEVER
    mutates the working tree.
    """
    # Primary: `--write-tree` form (git >= 2.38).
    try:
        result = _git_run(
            [
                "git",
                "-C",
                str(toplevel),
                "merge-tree",
                "--write-tree",
                against,
                branch,
            ],
        )
    except (OSError, subprocess.SubprocessError):
        result = None

    if result is not None:
        out = result.stdout or ""
        # `--write-tree` is a recognized option iff stderr doesn't complain
        # about an unknown/usage option. If it IS unknown, fall through to the
        # legacy form rather than trusting this exit code.
        stderr = (result.stderr or "").lower()
        unknown_option = (
            "unknown option" in stderr
            or "usage:" in stderr
            and "--write-tree" in stderr
        )
        if not unknown_option:
            if result.returncode != 0:
                return False
            if "CONFLICT" in out or "<<<<<<<" in out:
                return False
            return True

    # Fallback: legacy 3-arg `git merge-tree <base> <against> <branch>`.
    merge_base = _git_merge_base(toplevel, against, branch)
    if merge_base is None:
        # Indeterminate -> don't claim clean.
        return False
    try:
        legacy = _git_run(
            [
                "git",
                "-C",
                str(toplevel),
                "merge-tree",
                merge_base,
                against,
                branch,
            ],
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if legacy.returncode != 0:
        return False
    out = legacy.stdout or ""
    if "<<<<<<<" in out or "CONFLICT" in out:
        return False
    return True


def _git_merge_base(toplevel: Path, a: str, b: str) -> Optional[str]:
    """Return the merge-base SHA of `<a>` and `<b>`, or None on failure."""
    try:
        result = _git_run(
            ["git", "-C", str(toplevel), "merge-base", a, b],
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    out = (result.stdout or "").strip()
    return out or None


def _git_branch_exists(branch: str) -> bool:
    """Return True iff the named branch (or ref) resolves locally.

    Uses `git rev-parse --verify --quiet refs/heads/<branch>` for local
    branches; falls back to `git rev-parse --verify --quiet <branch>` for
    refs (tags, remote-tracking branches) so a base-branch named `origin/main`
    still resolves cleanly.
    """
    # First try as a local branch.
    try:
        result = _git_run(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode == 0:
        return True
    # Fall back to the general ref form (covers tags, remote-tracking
    # branches, abbreviated SHA, etc.).
    try:
        result = _git_run(
            ["git", "rev-parse", "--verify", "--quiet", branch],
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


# ---- A6: minimal argparse CLI (review-remediation) ---------------------------


def main(argv: list[str] | None = None) -> int:
    """Minimal CLI entry point for the v1.3.0 merged-worktree cleanup.

    The two `worktree_lifecycle.py cleanup-merged --against origin/main`
    command invocations (visual-to-api / classify-test-prod-safety) reach here.
    Per the v1.3.0 never-block rule, a cleanup error prints a one-line note and
    returns 0 — cleanup must never block the run. An UNKNOWN subcommand, by
    contrast, is rejected by argparse with a nonzero exit (the E1 "not a silent
    no-op" contract): a typo in a command file should surface, not vanish.
    """
    p = argparse.ArgumentParser(
        prog="worktree_lifecycle.py",
        description="Architect-team worktree lifecycle helper (v1.3.0 cleanup).",
    )
    sub = p.add_subparsers(dest="cmd")
    cm = sub.add_parser(
        "cleanup-merged",
        help="Remove architect-team/* worktrees whose branch is merged.",
    )
    cm.add_argument("--against", default="origin/main",
                    help="The ref to test merged-ness against (default origin/main).")
    cm.add_argument("--dry-run", action="store_true",
                    help="Report what WOULD be cleaned without removing anything.")
    args = p.parse_args(argv)

    if args.cmd == "cleanup-merged":
        try:
            removed = cleanup_merged_worktrees(
                against=args.against, dry_run=args.dry_run
            )
            print(
                f"cleanup-merged: {len(removed)} worktree(s) "
                f"{'would be ' if args.dry_run else ''}removed"
            )
        except Exception as e:  # noqa: BLE001 - v1.3.0: cleanup never blocks the run
            print(f"cleanup-merged: skipped ({e})")
        return 0

    # No subcommand at all -> clean exit 0 (nothing to do). Unknown subcommands
    # never reach here — argparse rejects an invalid choice with exit 2.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
