# Design: auto-worktree-lifecycle

## Reference

The full WHY + WHAT + 8 ACs live in `proposal.md`. This file is the architectural anchor.

## Where in the slash command flow

The slash command file at `commands/architect-team.md` (and `bug-fix.md` / `mini.md`) already documents a sequence:

```
1. Parse arguments + flags (strip --no-commit, --no-push, etc.)
2. Bind $REQ_DIR (folder OR plain-language prose)
3. Pre-pipeline refinement (proposal-refiner skill) — when prose + no --no-refine
4. Invoke architect-team-pipeline (or sibling) skill
```

The auto-worktree step inserts at position 3.5 — AFTER refinement (the refined-prompt path is the input to the pipeline) and BEFORE skill invocation.

```
3.5. Auto-worktree creation (NEW in v1.2.0)
     - Detect: are we already in an architect-team-run worktree? (current_worktree_is_run() = True)
       → Yes: no-op; proceed to skill invocation in current cwd (re-entry case).
       → No, AND --no-worktree was passed: skip; proceed to skill invocation in current cwd.
       → No, AND no opt-out: continue.
     - Derive slug (already done at the slash command level, OR derived from the refined prompt)
     - create_run_worktree(slug, base_branch="main")
     - chdir into the created worktree
     - Continue to skill invocation; the skill's Phase −1+ now runs in the worktree
```

The skill body itself doesn't need to know whether it's running in a worktree or not — the cwd is set up correctly before the skill is invoked. v1.1.0's `shared_state_dir()` + `run_state_dir()` resolution layer handles the rest.

## The two-helper split

v1.1.0 shipped `scripts/setup/worktree_paths.py` (path resolution: shared vs run state). v1.2.0 ships `scripts/setup/worktree_lifecycle.py` (worktree creation, cleanup, detection of "am I in a run worktree").

The split is intentional:
- **`worktree_paths.py`** is purely about WHERE state lives. Read-only.
- **`worktree_lifecycle.py`** is about CREATING and TEARING DOWN worktrees. Has side effects.

Keeping them separate makes the lifecycle helper testable independently and avoids bloating the v1.1.0 path-resolution module.

## Naming convention

- **Branch:** `architect-team/<slug>`
- **Worktree directory:** `<parent-of-repo>/<repo-name>-<slug>/`
  - Example: repo at `/Users/foo/projects/myapp` with slug `add-billing` → worktree at `/Users/foo/projects/myapp-add-billing/`
- **Collision handling:** if `architect-team/add-billing` already exists as a branch (active or stale), the helper appends `-2`, `-3`, ... until it finds a free name. Same for the directory.

The branch name pattern `architect-team/<slug>` is exactly the existing default-branch-guard convention used at Phase 8. Auto-worktree just creates the branch earlier — no new pattern to learn.

## Re-entry detection

A user might invoke `/architect-team` from inside an existing run worktree (e.g., they want to layer another change on top of a run that's mid-flight, or they're continuing a paused run). The helper detects:

```
current_worktree_is_run() — True if:
  git rev-parse --abbrev-ref HEAD startswith "architect-team/"
```

When True, the auto-worktree step is a no-op. The pipeline runs in the existing worktree.

## --no-worktree opt-out

The flag joins the existing flag set (`--no-commit`, `--no-push`, `--no-compact`, `--allow-push-to-default`, `--proposal-first`, `--no-refine`). Natural-language equivalents recognized at parse time: *"no worktree"*, *"don't create a worktree"*, *"single tree"*, *"in place"*, *"in current tree"*.

When `--no-worktree` is set: the auto-worktree step is skipped. The pipeline runs in the current cwd, exactly like v1.0.0 / v1.1.0.

## Phase 8 implications

The push-to-main step works the same way it did in v1.1.0. Differences:

- The pipeline's commits land on `architect-team/<slug>` branch in the run worktree (same as before, just from a different working tree on disk).
- The Phase 8 push step pushes that branch to origin (same as before).
- The Phase 8 master-pipeline + bug-fix-pipeline don't auto-merge to main by default; they recommend a PR. The mini-pipeline does auto-merge to main on green QA — this works the same way: from the run worktree, fast-forward main (in the MAIN worktree) to the run branch tip, push main.
- After successful merge, the orchestrator emits a recommendation:
  > Your run worktree is at `<path>` on branch `architect-team/<slug>`. The work is now on `main`. To clean up: `git worktree remove <path> && git branch -d architect-team/<slug>`. (Or leave it for inspection — the worktree is harmless.)

The pipeline does NOT auto-cleanup. The user inspects, then decides.

## Reuse Decision Log

### RD-1: New `scripts/setup/worktree_lifecycle.py`

**Decision:** Build new.
**Anchor:** v1.1.0's `worktree_paths.py` exists but is path-resolution only. The lifecycle concerns (create / cleanup / detect-run-worktree) are a separate responsibility.
**Anti-pattern avoided:** Extending `worktree_paths.py` with create/cleanup logic would conflate read-only resolution with side-effecting lifecycle — testability suffers, and the v1.1.0 module's pure-resolution contract gets muddied.

### RD-2: Extend 3 slash command bodies

**Decision:** Extend in place.
**Anchor:** Each of `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` already has an argument-parsing + refinement + skill-invocation sequence documented inline. Adding a worktree-init step is an additive insertion at a well-defined position.
**Anti-pattern avoided:** Authoring a separate `commands/architect-team-with-worktree.md` would split the slash command surface and confuse users.

### RD-3: Extend `common-pipeline-conventions/SKILL.md` with `## Auto-worktree lifecycle`

**Decision:** Extend.
**Anchor:** v1.0.0 audit-fix Slice 1 created this skill exactly for cross-cutting conventions. v1.1.0 added a `## Running in parallel sessions` section here. The auto-worktree lifecycle is the natural next companion section.

### RD-4: NO change to `worktree_paths.py`

**Decision:** Leave v1.1.0's helper untouched.
**Reason:** The path resolution rules don't change. The helper still answers "where does shared state live?" / "where does run state live?" — the worktree lifecycle helper consumes those answers but doesn't change them.

### RD-5: NO change to `hooks/locks.py`

**Decision:** Leave v1.1.0's locks layer untouched.
**Reason:** The lock layer correctly defaults to shared state. When a v1.2.0 run worktree is created, the lock layer reads/writes from the SHARED `.architect-team/locks/` (main worktree's). No change needed.

### RD-6: NEW test file `tests/test_worktree_lifecycle.py`

**Decision:** New file (not extending `tests/test_worktree_state_resolution.py`).
**Reason:** State resolution and lifecycle are different concerns. Keeping them in separate test files matches the helper split.

## Migration / backwards compatibility

- **v1.1.0 → v1.2.0:** Existing users who liked v1.1.0's single-tree behavior pass `--no-worktree` and get exactly that. Zero behavior change with the flag.
- **Default behavior change:** Without the flag, v1.2.0 creates a worktree by default. This IS a behavior change vs v1.1.0 — but it's a workflow improvement, and the opt-out is one short flag away.
- **No breaking API.** v1.1.0's `worktree_paths.py` API is unchanged. `hooks/locks.py` is unchanged. The v1.0.0 lock-layer tests pass unchanged.

## Trade-offs accepted

- **Default behavior change** — v1.2.0 changes what `/architect-team` does by default. Mitigated by `--no-worktree` opt-out + natural-language phrasings.
- **Disk usage** — each `/architect-team` run creates a worktree on disk. For small projects this is negligible; for large monorepos it's real. The user can clean up after each run.
- **`git worktree add` is a real subprocess** — adds ~1s of pipeline startup time. Acceptable for a feature-shipping pipeline.
- **Filesystem layout assumption** — the worktree goes at `<parent-of-repo>/<repo-name>-<slug>/`. If the parent dir is read-only (rare in dev environments but possible), worktree creation fails and the pipeline halts with a clear error pointing to `--no-worktree`.

## Version

v1.2.0 — minor bump (additive opt-out-able feature, no breaking change).
