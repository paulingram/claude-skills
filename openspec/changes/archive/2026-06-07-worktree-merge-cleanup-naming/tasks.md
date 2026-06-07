# Tasks

## 1. Code — worktree_lifecycle.py (REQ-001, REQ-002, REQ-003)

- [x] 1.1 Add `_container_dir(parent_dir, repo_name) -> Path` returning `parent_dir / f".{repo_name}-worktrees"`.
- [x] 1.2 `create_run_worktree`: compute candidate path under the container; `mkdir(parents=True, exist_ok=True)` the container before `git worktree add`.
- [x] 1.3 `_resolve_collision`: operate on `<container>/<slug>` paths; keep the `-2`/`-3` suffix-bump and the 999 bound.
- [x] 1.4 `_slug_from_worktree_path`: dual-layout (new `.<repo>-worktrees/<slug>` first, then old `<repo>-<slug>`, then existing fallback).
- [x] 1.5 Add `finalize_run_worktree(worktree_path=None, against="origin/main", branch=None) -> dict` per design D3 (merged→remove, unmerged→warn, non-run→no-op, best-effort try/except).
- [x] 1.6 Update the module docstring `Naming conventions` block + public-API list to include the container layout and `finalize_run_worktree`.

## 2. Tests (REQ-001, REQ-002, REQ-003)

- [x] 2.1 Update `tests/test_worktree_lifecycle.py` create + collision tests to assert the new `.main-repo-worktrees/<slug>` layout.
- [x] 2.2 Add `tests/test_worktree_merge_finalize.py`: finalize removes-when-merged; finalize warns-when-unmerged (folder intact, warning text names path + command); finalize no-op on non-run branch; `_slug_from_worktree_path` dual-layout; sweep removes BOTH an old-flat and a new-nested merged worktree (backward-compat).

## 3. Docs + commands (REQ-004, REQ-005)

- [x] 3.1 `skills/common-pipeline-conventions/SKILL.md` `## Auto-worktree lifecycle`: rewrite path convention to the hidden container; add end-of-run merge-check (Trigger 3) + dual-layout note; update collision examples + cleanup-semantics warning.
- [x] 3.2 `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`: update the auto-worktree path note; wire the Phase 8 / B8 / M7 `finalize_run_worktree` call + warning print.
- [x] 3.3 `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md`: Phase 8 / B8 / M7 finalize + explicit warning/cleaned messaging.
- [x] 3.4 `commands/cleanup-worktrees.md`: dual-layout recognition note; new layout in description/out-of-scope.
- [x] 3.5 `worktree_lifecycle.py` docstring already covered in 1.6.

## 4. Release (REQ-005)

- [x] 4.1 Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to 3.6.0.
- [x] 4.2 `CHANGELOG.md` v3.6.0 entry.
- [x] 4.3 `README.md` + `CLAUDE.md` currency (worktree lifecycle description + counts/version).
- [x] 4.4 Full `python -m pytest` green (Windows cp1252 + `PYTHONUTF8=1`).
