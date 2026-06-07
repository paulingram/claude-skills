## Context

`scripts/setup/worktree_lifecycle.py` already owns worktree create / cleanup / detect. This change extends it; it does NOT introduce a new module. Reuse Decision: **RD-EXTEND** — extend the existing lifecycle helper (the canonical home for these subprocesses) rather than build a sibling. Grounded in `docs/CODEBASE_MAP.md` → `scripts/setup/worktree_lifecycle.py` and the module's own docstring.

## Key decisions

### D1 — Hidden container layout, branch-keyed sweep stays location-agnostic

New worktree path = `parent_dir / f".{repo_name}-worktrees" / slug`. A new internal `_container_dir(parent_dir, repo_name) -> Path` centralizes the computation. `create_run_worktree` `mkdir(parents=True, exist_ok=True)` the container before `git worktree add`.

The v1.3.0 sweep (`list_merged_architect_team_worktrees`) keys merge detection off the **branch** (`git merge-base --is-ancestor architect-team/<slug> origin/main`), read from `git worktree list --porcelain`. Branch detection is therefore independent of where the worktree lives on disk — old-flat and new-nested worktrees are both recognized with zero change to the merge probe. Only `_slug_from_worktree_path` (used by `cleanup_run_worktree` to delete the branch) needs dual-layout awareness.

### D2 — `_slug_from_worktree_path` dual-layout

Order of checks:
1. If `worktree_path.parent.name == f".{repo_name}-worktrees"` → slug = `worktree_path.name` (new layout).
2. Else if `basename.startswith(f"{repo_name}-")` → slug = basename after the prefix (old layout).
3. Else fall back to the existing first-hyphen heuristic (no git context) / return None.

This keeps both the v1.2.0 tests (old layout, updated to new) and pre-existing on-disk old-flat worktrees working.

### D3 — `finalize_run_worktree` — the end-of-run merge-check

```
finalize_run_worktree(worktree_path=None, against="origin/main", branch=None) -> dict
```
- `worktree_path` defaults to `Path.cwd()`; `branch` defaults to the worktree's current branch (`git -C <worktree_path> rev-parse --abbrev-ref HEAD`).
- If `branch` does not start with `architect-team/` → `{removed: False, merged: False, reason: "not-a-run-worktree", warning: None, ...}`.
- Else probe `_branch_is_merged_into(toplevel, branch, against)`:
  - merged → `cleanup_run_worktree(worktree_path, remove_branch=True)`; return `{removed: True, merged: True, reason: "merged-removed", warning: None, branch, worktree_path}`. Wrapped in try/except — if git refuses (e.g. cwd is inside the worktree), fall through to the warning path with `reason: "merge-detected-removal-deferred"`.
  - not merged → return `{removed: False, merged: False, reason: "unmerged-retained", warning: <text>, branch, worktree_path}` where `<text>` names the path, states it persists until merged, and gives the manual cleanup command.

Best-effort: the orchestrator calls this at Phase 8 / B8 / M7 and prints `result["warning"]` (or the cleaned-note) verbatim. For full + bug-fix the dominant end-of-run state is unmerged (branch just pushed, PR pending) → the warning path; merged-removal is the mini / already-merged case.

### D4 — No git post-merge hook

Explicitly out of scope per the user's choice. True merge-moment removal would require writing into `.git/hooks`; the sweep + end-of-run check covers the need non-invasively.

## Reuse Decision Log

| Item | Decision | Rationale |
|---|---|---|
| End-of-run merge check | RD-EXTEND `worktree_lifecycle.py` | The module already owns `_branch_is_merged_into` + `cleanup_run_worktree`; finalize composes them. |
| Container path | RD-EXTEND `create_run_worktree` / `_resolve_collision` | Same compute path; only the parent dir changes. |
| Dual-layout slug | RD-MODIFY `_slug_from_worktree_path` | Single function already responsible for slug derivation. |
| Sweep recognition | RD-REUSE (no change) | Branch-keyed detection is already layout-agnostic. |

## Risks

- **Removing the cwd worktree.** `git worktree remove` refuses to remove the worktree that is the process cwd. finalize's merged-removal path is wrapped in try/except and degrades to the warning; the next-run sweep (run from the main checkout) then removes it. Acceptable.
- **Existing tests asserting flat layout.** `tests/test_worktree_lifecycle.py` create/collision tests are updated to the new layout; a new test asserts old-flat worktrees are still swept (backward-compat is explicitly covered, not just assumed).
