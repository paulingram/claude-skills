# Proposal: worktree-state-resolution (v1.1.0)

## Why

v1.0.0 shipped two cross-session coordination primitives — the `.architect-team/locks/` JSON lock layer and MemPalace context-recall. Both assume "the workspace" is the directory where `git rev-parse --show-toplevel` resolves. When a user runs two `/architect-team` sessions in **git worktrees**, that command resolves to each worktree's own path — so each worktree gets its own locks dir + its own MemPalace, completely defeating cross-session coordination.

Worktrees are the right primitive for filesystem isolation between concurrent sessions: each session edits/tests/commits in its own working tree without clobbering the other, on its own branch. But the v1.0.0 cross-session coordination layers need to resolve to the **shared** main worktree, not the per-worktree directory.

This change introduces a small worktree-aware path resolution helper + threads it through the load-bearing call sites (the lock layer, the MemPalace integration, the run-state-dir convention). The result: users can run two `/architect-team` sessions in two worktrees in parallel, get true filesystem isolation, AND retain shared lock arbitration + shared MemPalace context.

## What changes

1. **New helper `scripts/setup/worktree_paths.py`** — exposes `shared_state_dir()`, `run_state_dir()`, `is_worktree()`. Resolves shared state to the main worktree (via `git rev-parse --git-common-dir` + parent traversal) and run state to the current worktree.
2. **`hooks/locks.py` updated** to use `shared_state_dir() / 'locks'` — the lock layer now coordinates across worktrees as intended.
3. **MemPalace integration documentation updated** — the wake-up convention now resolves the palace path via `shared_state_dir() / '.mempalace' / 'palace'` instead of the worktree-local fallback.
4. **`common-pipeline-conventions/SKILL.md` gains a `## Running in parallel sessions` section** documenting:
   - When to use worktrees (concurrent `/architect-team` runs on independent scopes)
   - The 3-layer model (filesystem isolation = worktrees; architectural coordination = locks; context sharing = MemPalace)
   - The shared vs run state split (review-evidence, teammate manifests, per-run OpenSpec stays per-worktree; locks + MemPalace + run history resolve to shared)
   - Pointer to the `superpowers:using-git-worktrees` skill for worktree mechanics
5. **6 new tests** covering: `is_worktree()` detection, `shared_state_dir()` resolution from a worktree vs main, `run_state_dir()` correctness in both, lock acquisition across worktrees, MemPalace path resolution from a worktree.
6. **Version bump to 1.1.0** in `plugin.json` + `marketplace.json` + CHANGELOG + CLAUDE.md + README + CODEBASE_MAP + INTEGRATION_MAP.

## QA Guidance

### Acceptance Criteria

- [AC-1] `scripts/setup/worktree_paths.py` exposes `shared_state_dir() -> Path`, `run_state_dir() -> Path`, `is_worktree() -> bool`. Functions use stdlib only (subprocess for git invocations, pathlib for path math).
- [AC-2] `hooks/locks.py`'s `acquire_lock` / `release_lock` / `detect_stale` resolve their default `locks_dir` via `shared_state_dir() / 'locks'`. Existing `locks_dir=` parameter is preserved for test isolation.
- [AC-3] When invoked from a worktree, `shared_state_dir()` returns the **main worktree's** `.architect-team/` path; from a non-worktree clone it returns the cwd's `.architect-team/`.
- [AC-4] `common-pipeline-conventions/SKILL.md` carries a `## Running in parallel sessions` section explicitly documenting the 3-layer model + the shared-vs-run state split.
- [AC-5] All existing tests pass (1688 baseline) PLUS the 6 new tests in `tests/test_worktree_state_resolution.py`. Target: 1694 / 1 skipped.
- [AC-6] Existing v1.0.0 lock tests (`tests/test_locks.py`) still pass — the new resolution path is backwards-compatible (functions accept `locks_dir=` parameter, defaulting to the worktree-aware resolution).
- [AC-7] Version reference is `1.1.0` consistently across `plugin.json`, `marketplace.json`, CHANGELOG top entry, README banner + badge, CLAUDE.md overview.

### Unit Test Targets

- `scripts/setup/worktree_paths.py:is_worktree`: returns True from a worktree, False from the main checkout
- `scripts/setup/worktree_paths.py:shared_state_dir`: identical resolution from main + from a worktree (both point at main's `.architect-team/`)
- `scripts/setup/worktree_paths.py:run_state_dir`: returns per-worktree `.architect-team/` (different paths between main and worktree)
- `hooks/locks.py:acquire_lock` with default `locks_dir`: writes to `shared_state_dir() / 'locks'`

### Integration Test Targets

- End-to-end: create a worktree, acquire a lock from it, attempt to acquire an intersecting lock from main → blocked. Confirms shared coordination across sessions.

### Playwright Flows

- N/A (no UI surface).

### Out of Scope

- **Splitting the 7-mode `system-architect`** (SR-audit-eff-002) — still deferred per the audit's own recommendation; large effort, separate change record.
- **Worktree lifecycle automation** — creating/tearing down worktrees from inside the pipeline. The `superpowers:using-git-worktrees` skill already handles this; not in scope here.
- **Cross-worktree dispatch coordination** — if session A wants to dispatch a teammate that session B should claim, that's a v1.2+ idea. v1.1.0 only fixes the state-resolution gap.
- **Renaming `.architect-team/`** — kept as-is; the worktree-aware resolution is internal.

## Impact

- **New:** 1 helper (`scripts/setup/worktree_paths.py`), 1 test file (`tests/test_worktree_state_resolution.py`), 1 self-referential OpenSpec change folder.
- **Modified:** `hooks/locks.py` (use shared resolution by default), `skills/common-pipeline-conventions/SKILL.md` (new section), `skills/mempalace-integration/SKILL.md` (note shared resolution), CHANGELOG, CLAUDE.md, README, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `plugin.json`, `marketplace.json`.
- **Test count:** 1688 → ~1694 (1688 + 6 new).
- **Version:** v1.0.0 → **v1.1.0**.
- **Backwards-compatible:** existing single-session users see no behavior change. Worktree users gain shared coordination automatically.
