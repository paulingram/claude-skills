#!/usr/bin/env python3
"""Worktree-aware state-resolution helper for the architect-team plugin (v1.1.0).

v1.0.0 shipped two cross-session coordination primitives — the
`.architect-team/locks/` JSON lock layer and MemPalace context-recall. Both
assumed "the workspace" was the directory where `git rev-parse --show-toplevel`
resolves. When two `/architect-team` sessions run in **git worktrees** (the
right primitive for filesystem isolation between concurrent sessions: each
session edits/tests/commits in its own working tree on its own branch), that
command resolves to each worktree's own path — so each worktree gets its own
locks dir and its own MemPalace, completely defeating the cross-session
coordination intent.

This module is the worktree-aware path-resolution primitive that closes the
gap. It distinguishes three layers and resolves each correctly:

  Layer                       | Concern                         | Resolution
  ----------------------------|---------------------------------|------------
  Filesystem isolation        | Two sessions can't clobber each | Worktrees
                              | other's working tree, index, or |
                              | branch                          |
  ----------------------------|---------------------------------|------------
  Architectural coordination  | Two sessions can't both decide  | shared_state_dir()
                              | to refactor the same scope-glob | -> main worktree's
                              | (the `.architect-team/locks/`   | .architect-team/
                              | JSON lock layer from v1.0.0)    |
  ----------------------------|---------------------------------|------------
  Context sharing             | Session B sees what session A   | shared_state_dir()
                              | produced (MemPalace context     | -> main worktree's
                              | recall)                         | .architect-team/.mempalace/
  ----------------------------|---------------------------------|------------
  Per-run state               | reviews/, teammates/,           | run_state_dir()
                              | handoffs/, this-run's OpenSpec  | -> current
                              | change folder                   | worktree's
                              |                                 | .architect-team/

Resolution semantics
--------------------

`shared_state_dir() -> Path`
    Used for: locks/, .mempalace/, run-history/.
    Resolution: parent(git rev-parse --git-common-dir) / ".architect-team".
    In a worktree:           main worktree's .architect-team
    In a non-worktree clone: cwd's .architect-team (degenerate — same as
                             run_state_dir)
    In a non-git directory:  cwd's .architect-team (best-effort fallback)

`run_state_dir() -> Path`
    Used for: reviews/, teammates/, handoffs/, this-run's openspec/changes/<slug>/,
              this-run's audit findings + refined-prompts.
    Resolution: cwd / ".architect-team" (always per-worktree).

`is_worktree() -> bool`
    Utility for downstream callers that want to know.
    Resolution: git rev-parse --git-common-dir != git rev-parse --git-dir
    (both resolved to absolute paths before comparison).

Backwards compatibility
-----------------------

Single-session users (no worktrees) see ZERO behavior change. In a non-worktree
clone, shared_state_dir() and run_state_dir() resolve to the SAME path; the
lock layer reads/writes the same location it always did in v1.0.0. The fix is
transparent — no env vars, no flags, no opt-in.

Reuse Decision: RD-2 (build-new — no existing equivalent). Stdlib only per
NF-2, matching the convention used by scripts/setup/teams_mode.py (the
existing setup helper this module sits alongside).

References:
  - openspec/changes/worktree-state-resolution/proposal.md
  - openspec/changes/worktree-state-resolution/design.md (the 3-layer model)
  - openspec/changes/worktree-state-resolution/specs/worktree-state-resolution/spec.md
  - skills/common-pipeline-conventions/SKILL.md `## Running in parallel sessions`
    (the consumer-facing documentation)
"""
from __future__ import annotations

import subprocess
from pathlib import Path


# ---- Constants ---------------------------------------------------------------

# The state directory name is fixed across both shared + run resolution. It is
# the same directory name v1.0.0 used; v1.1.0 only changes WHERE the directory
# is rooted (shared vs. per-worktree).
_STATE_DIR_NAME = ".architect-team"


# ---- Public API --------------------------------------------------------------


def is_worktree() -> bool:
    """Return True iff the current working directory is inside a git worktree.

    A worktree is detected by comparing `git rev-parse --git-dir` (the
    worktree-specific .git directory) against `git rev-parse --git-common-dir`
    (the main repo's .git directory shared by all worktrees). In the main
    checkout these resolve to the SAME path; in a worktree they differ.

    Both subprocess invocations are best-effort — any failure (not a git repo,
    git not installed, broken repo metadata) returns False, never raises. This
    matches the discipline used by `scripts/setup/teams_mode.py`'s git probes.
    """
    git_dir = _run_git_rev_parse("--git-dir")
    if git_dir is None:
        return False
    common_dir = _run_git_rev_parse("--git-common-dir")
    if common_dir is None:
        return False
    return git_dir.resolve() != common_dir.resolve()


def shared_state_dir() -> Path:
    """Return the `.architect-team/` path that should hold SHARED state.

    Shared state = anything two concurrent sessions need to coordinate on:
    locks/, .mempalace/, run-history/. The path always points at the MAIN
    worktree's `.architect-team/` directory, so two worktree-based sessions
    see the same lock files and the same MemPalace.

    Resolution: parent(git rev-parse --git-common-dir) / ".architect-team".
    Fallback: cwd / ".architect-team" when git resolution fails (non-git
    directory, broken repo metadata) — the degenerate single-session case.

    Never raises — every probe is wrapped to fall back to cwd.
    """
    common_dir = _run_git_rev_parse("--git-common-dir")
    if common_dir is None:
        return Path.cwd() / _STATE_DIR_NAME
    return common_dir.resolve().parent / _STATE_DIR_NAME


def run_state_dir() -> Path:
    """Return the `.architect-team/` path that should hold PER-RUN state.

    Per-run state = anything that belongs to THIS local run: reviews/,
    teammates/, handoffs/, this-run's openspec/changes/<slug>/, this-run's
    audit findings + refined-prompts. The path always points at the CURRENT
    worktree's `.architect-team/` directory, so each worktree owns its own
    run state independently.

    Resolution: cwd / ".architect-team". No git probe — per-run state is
    always relative to where the run was launched.
    """
    return Path.cwd() / _STATE_DIR_NAME


# ---- Internals ---------------------------------------------------------------


def _run_git_rev_parse(flag: str) -> Path | None:
    """Run `git rev-parse <flag>` and return the result as a Path, or None.

    Returns None on any subprocess failure: non-git directory, git not on
    PATH, non-zero exit, empty stdout. The caller treats None as the
    "fall back to cwd" signal.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", flag],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    out = (result.stdout or "").strip()
    if not out:
        return None

    return Path(out)
