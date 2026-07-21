# Auto-worktree lifecycle

> Reference block extracted from `skills/common-pipeline-conventions/SKILL.md` `## Auto-worktree lifecycle` (loaded on demand via the STOP pointer there). This is the full procedure; execute it in full.

v1.1.0 made the cross-session coordination layer worktree-aware; v1.2.0 makes worktree CREATION automatic. Every `/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini` invocation auto-creates a fresh worktree by default, so the user's main checkout stays on whatever branch they were on and each run is self-contained on its own branch in its own working tree. The user explicitly asked for this: *"always on when using architect team."* This section is the canonical home of the auto-worktree rules; the three slash command bodies reference it rather than re-explaining.

### When it fires

The auto-worktree step runs by default on every invocation of the three pipeline-driving slash commands — `/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`. It does NOT run on the read-mostly utility commands (`/architect-team:visual-qa`, `/architect-team:editability-audit`, `/architect-team:refine-prompt`, `/architect-team:memory`, `/architect-team:mempalace-install`, `/architect-team:architect-team-setup`, `/architect-team:mini-review-sweep`); those operate against the current checkout because their work is inspection / configuration / replay, not feature delivery.

The step fires AFTER argument parsing + the v0.9.33 pre-pipeline refinement step (so the refined-prompt slug, when present, is available for slug derivation) and BEFORE the pipeline skill is invoked. The cwd change happens at this boundary; every later phase of the pipeline runs with the new worktree as cwd.

### Detection logic — skip when in a run worktree (re-entry)

A user may invoke `/architect-team` from inside an existing architect-team-run worktree (continuing a paused run, layering a new change on top of a mid-flight run). The slash command MUST detect this and skip the auto-worktree step — nesting worktrees is incorrect.

The detection helper is `scripts/setup/worktree_lifecycle.py::current_worktree_is_run()`:

```python
def current_worktree_is_run() -> bool:
    # True iff git rev-parse --abbrev-ref HEAD startswith "architect-team/"
```

When True, the auto-worktree step is a no-op and the pipeline runs in the current cwd.

### Opt-out — `--no-worktree`

The `--no-worktree` flag joins the existing flag set (`--no-commit`, `--no-push`, `--no-compact`, `--allow-push-to-default`, `--proposal-first`, `--no-refine`). Natural-language equivalents recognized at parse time: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*. When `--no-worktree` is set, the auto-worktree step is skipped and the pipeline runs in the current cwd — exactly the v1.1.0 behavior, no functional difference.

### Path convention — `<parent-of-repo>/.<repo-name>-worktrees/<slug>/`

The worktree directory goes inside a single hidden per-project container next to the main repo, named `.<repo-name>-worktrees`, with the slug as the leaf:

- Repo at `/Users/foo/projects/myapp` with slug `add-billing` -> worktree at `/Users/foo/projects/.myapp-worktrees/add-billing/`
- Repo at `/Users/foo/myapp` with slug `fix-login` -> worktree at `/Users/foo/.myapp-worktrees/fix-login/`

All of a project's run worktrees collect in this single hidden folder, keeping the parent directory uncluttered while remaining co-located for easy `cd`-around discovery. The old flat `<repo>-<slug>` layout is still recognized by cleanup + slug-derivation for backward compatibility with pre-v3.6.0 on-disk worktrees.

### Branch convention — `architect-team/<slug>`

The branch the new worktree is checked out on. This is exactly the existing Phase 8 default-branch-guard convention — the guard already creates `architect-team/<change-name>` when a run is committing on `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false. v1.2.0 just creates the branch earlier — from the start of the run, rather than at the Phase 8 commit step. Same pattern; same downstream behavior.

### Collision handling — append `-2`, `-3`, ...

If EITHER the candidate path OR the candidate branch already exists, the helper appends a numeric suffix until both are free:

- `architect-team/add-billing` and `.myapp-worktrees/add-billing/` both free -> use them.
- `architect-team/add-billing` exists -> try `architect-team/add-billing-2` + `.myapp-worktrees/add-billing-2/`.
- `.myapp-worktrees/add-billing-2/` also exists -> try `-3`.
- ... bounded at 999 suffix attempts before raising.

A stale branch from a prior run that the user did not delete is the common case; the suffix bump silently handles it. No manual cleanup of stale branches is required to start a new run.

### Cleanup semantics — end-of-run merge check (v3.6.0)

At Phase 8 / B8 / M7 the pipeline calls `finalize_run_worktree(worktree_path, against="origin/main")`:

- **If the run branch is already merged into `origin/main`** -> the helper removes the worktree AND deletes the branch, returning `{removed: True, merged: True, reason: "merged-removed", warning: None}`. (If git refuses because the worktree is the current cwd, it degrades to `reason: "merge-detected-removal-deferred"` with a warning; the next run's sweep removes it.)
- **If the run branch is NOT yet merged** (the common full / bug-fix end-of-run state — branch just pushed, PR pending) -> the helper LEAVES the worktree on disk and returns `{removed: False, merged: False, reason: "unmerged-retained", warning: <text>}`. The orchestrator prints `warning` verbatim; it names the path, states the folder persists until the branch is merged (after which the next run's sweep removes it), and gives the manual command `git worktree remove <path> && git branch -d <branch>`.

Unmerged work is NEVER auto-deleted. The `cleanup_run_worktree` helper still exposes the raw remove operation programmatically (`cleanup_run_worktree(path, remove_branch=True)`), idempotent on a worktree that is already gone.

### Auto-cleanup (v1.3.0 + v3.6.0)

v1.2.0 left cleanup as a user action; the follow-up ask was *"we need auto cleanup so we resolve trees when branches are merged in."* Three automatic triggers:

- **Trigger 1 — start of every `/architect-team` family invocation.** Each slash command fires `cleanup_merged_worktrees()` as its FIRST action (after a best-effort `git fetch origin main`), removing every merged `architect-team/*` worktree; the user sees a one-line note. The cross-run sweep.
- **Trigger 2 — end of mini Phase M7 (after green merge).** After the M7 branch-delete, `cleanup_run_worktree(Path.cwd(), remove_branch=False)` cleans the mini's own (already-merged) worktree.
- **Trigger 3 — end-of-run merge check (v3.6.0).** At Phase 8 / B8 / M7 every pipeline calls `finalize_run_worktree(worktree_path)`: if merged into `origin/main`, removes worktree + branch immediately; if NOT merged, leaves the folder and returns an explicit `warning` (path + manual cleanup command) the orchestrator prints verbatim. The in-run counterpart to trigger 1.

**`exclude_current` safeguard.** `list_merged_architect_team_worktrees` defaults `exclude_current=True` (no override) so trigger 1 NEVER removes the cwd — avoiding *"the auto-cleanup ate the cwd I was just working in."* (Trigger 2 intentionally cleans the current worktree because M7 just merged it in THIS run.) **Unmerged work is never auto-deleted.**

**Merged-branch detection.** `git merge-base --is-ancestor <branch> <against>` (default `origin/main`; `--against <ref>` overrides). Keyed off the BRANCH not the on-disk location, so both old-flat and new-container layouts are recognized. **Squash-merge limitation:** `--is-ancestor` doesn't detect squash-merges (different SHA) — the safe trade-off (false negatives beat auto-deleting un-merged work); force-remove via `git worktree remove <path>` or `/architect-team:cleanup-worktrees`. **`--dry-run`** (`cleanup_merged_worktrees(dry_run=True)`) prints the candidate paths without touching the filesystem.

**Best-effort discipline.** Every auto-cleanup invocation is best-effort:
the helper swallows per-worktree failures and continues with the rest; the
slash commands surface the cleanup output as a one-line note and proceed to
the rest of their flow regardless of the cleanup's outcome. A cleanup
failure NEVER blocks the new run. This is the same discipline as v0.9.18's
notifier and v0.9.30's polyglot-Python fallback — observability without
gating.

**Helpers (v1.3.0).** The two new public functions in
`scripts/setup/worktree_lifecycle.py`:

- `list_merged_architect_team_worktrees(against="origin/main",
  exclude_current=True) -> list[Path]` — returns paths of merged
  `architect-team/*` worktrees, honoring `exclude_current`. Non-architect-team
  branches are NEVER included. Stdlib only.
- `cleanup_merged_worktrees(against="origin/main", dry_run=False) ->
  list[Path]` — removes the merged worktrees (or returns the candidate list
  verbatim on `dry_run=True`). Idempotent: vanished worktrees are skipped
  rather than raised on.

### Shell examples (default / re-entry / opt-out)

- **Default run:** from the main checkout, `/architect-team add a billing page` parses args, refines, derives slug `add-billing-page`, calls `create_run_worktree` → worktree at `<parent>/.myapp-worktrees/add-billing-page/` on branch `architect-team/add-billing-page`, chdir's in, runs Phase −1 → 8 there (main checkout untouched), commits + pushes on the branch, and the Phase 8 report names the worktree path + the manual cleanup command (per v3.7.0 a clean run auto-merges + prunes instead).
- **Re-entry:** invoking `/architect-team` from inside an existing `architect-team/*` worktree → `current_worktree_is_run()` is True → auto-worktree is a no-op; the run layers on the existing worktree.
- **Opt-out:** `/architect-team … --no-worktree` skips the auto-worktree step and runs in the current checkout (v1.1.0 behavior; the Phase 8 default-branch guard still applies).

### Opt-out shell example

```bash
# User wants v1.1.0 behavior — pipeline runs in the current checkout.
cd /Users/foo/projects/myapp
/architect-team add a billing page --no-worktree
# auto-worktree step skipped; the pipeline runs from /Users/foo/projects/myapp
# (and the Phase 8 default-branch guard still kicks in on main/master).
```

### Cross-references

- The 3 slash command bodies (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) reference this section for the canonical rules; each also fires `cleanup_merged_worktrees()` as its first action per v1.3.0.
- The explicit cleanup command is `commands/cleanup-worktrees.md` (v1.3.0) — `/architect-team:cleanup-worktrees [--dry-run] [--against <ref>]`. Manual invocation of the same helper the auto-cleanup uses.
- The lifecycle helper is `scripts/setup/worktree_lifecycle.py` — 6 public functions: `create_run_worktree(slug, base_branch="main", parent_dir=None) -> Path`, `cleanup_run_worktree(worktree_path, remove_branch=False) -> None`, `current_worktree_is_run() -> bool`, `current_run_slug() -> str | None`, and (v1.3.0) `list_merged_architect_team_worktrees(against="origin/main", exclude_current=True) -> list[Path]`, `cleanup_merged_worktrees(against="origin/main", dry_run=False) -> list[Path]`. Stdlib only.
- The path-resolution sibling is `scripts/setup/worktree_paths.py` (v1.1.0) — `shared_state_dir()` / `run_state_dir()` / `is_worktree()`. The lifecycle helper consumes git toplevel info; the resolution helper consumes the shared-vs-per-run split. Distinct responsibilities, distinct modules.
- `tests/test_worktree_lifecycle.py` (8 tests — happy path, collision handling, run-detection True/False, slug extraction True/None, cleanup with + without branch removal) exercises the v1.2.0 helpers against real `git init` + `git worktree add` fixtures, no mocks.
- `tests/test_worktree_auto_cleanup.py` (6 tests — merged-branch identification, exclude_current safeguard, non-architect-team branches ignored, cleanup removes filesystem, dry_run preview leaves filesystem untouched, end-to-end cleanup-only-removes-merged) exercises the v1.3.0 helpers against the same real-git fixtures with `origin/main` configured via a self-remote.
- **(v3.7.0)** When `AUTO_MERGE_MAIN` is true (the default), a clean Phase 8 / B8 / M7 run does NOT stop at the unmerged-branch persistence warning above — it merges the run branch into `main`, pushes, and prunes the branch + worktree via `merge_branch_to_main_and_prune`. See the canonical `## Auto-merge-to-main discipline (v3.7.0)` section below for the full flow, the conflict / branch-protection safety rules, and the `--no-auto-merge` opt-out that restores this section's feature-branch + PR persistence behavior verbatim.
