# Proposal: auto-worktree-lifecycle (v1.2.0)

## Why

v1.1.0 made the shared-state coordination layer worktree-aware. But it left worktree CREATION as a manual user action. The user's follow-up request: **every `/architect-team` family invocation should auto-create a worktree by default**, so:

- Concurrent runs are filesystem-isolated by default — no setup
- The user's main checkout stays on whatever branch they were on
- Each run is self-contained on its own branch in its own worktree
- v1.1.0's shared lock + MemPalace coordination keeps everything in sync without configuration

This is the cleaner workflow even for solo users: the existing `architect-team/<change-name>` default-branch guard at commit time becomes a worktree from the start. Same isolation, applied at the filesystem layer rather than only at the commit layer.

## What changes

1. **New helper `scripts/setup/worktree_lifecycle.py`** — exposes:
   - `create_run_worktree(slug: str, base_branch: str = "main", parent_dir: Path | None = None) -> Path` — creates `<parent>/<repo-name>-<slug>/` on a fresh branch `architect-team/<slug>`; returns the absolute path; handles slug/branch collisions by appending `-2`, `-3`, etc.
   - `cleanup_run_worktree(worktree_path: Path, remove_branch: bool = False) -> None` — removes the worktree (and optionally the branch) after a run completes
   - `current_worktree_is_run() -> bool` — detects whether we're already in an architect-team-created worktree (branch name pattern `architect-team/*`)
   - `current_run_slug() -> str | None` — returns the slug from the current branch name if in a run worktree, else None
2. **Three slash commands updated** (`commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`) to:
   - Run worktree-init AFTER argument parsing + refinement and BEFORE skill invocation
   - Detect "already in an architect-team-run worktree" → no-op (re-entry case; don't double-nest)
   - Auto-create the worktree, chdir into it, then invoke the skill with the worktree's cwd
   - Add a `--no-worktree` flag for opt-out (single-tree mode, matching v1.0.0 / v1.1.0 behavior)
   - Natural-language opt-out phrasings: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"*
3. **`common-pipeline-conventions/SKILL.md` gains a `## Auto-worktree lifecycle` section** documenting:
   - When the auto-worktree fires (every `/architect-team` family invocation, by default)
   - The detection logic (skip if already in a run worktree)
   - The opt-out (`--no-worktree`)
   - The path convention (`<parent>/<repo-name>-<slug>/` with collision handling)
   - The branch convention (`architect-team/<slug>`)
   - The cleanup semantics (default: keep on success so user can inspect/merge; explicit cleanup helper available)
4. **Phase 8 auto-merge updates** in the 3 pipeline skills: after a successful merge to main, the orchestrator notes the worktree's location and recommends `git worktree remove <path>` for cleanup (does NOT auto-remove — the user may want to inspect).
5. **8 new tests** covering: collision handling, branch naming, re-entry detection, --no-worktree opt-out, slug derivation, cleanup helper, current_run_slug extraction.
6. **Version bump to v1.2.0** in `plugin.json` + `marketplace.json` + CHANGELOG + CLAUDE.md + README + CODEBASE_MAP + INTEGRATION_MAP.

## QA Guidance

### Acceptance Criteria

- [AC-1] `scripts/setup/worktree_lifecycle.py` exposes `create_run_worktree`, `cleanup_run_worktree`, `current_worktree_is_run`, `current_run_slug` — stdlib only.
- [AC-2] By default (no `--no-worktree` flag), each `/architect-team` family slash command creates a worktree on `architect-team/<slug>` branch at `<parent-of-repo>/<repo-name>-<slug>/`, chdirs into it, and invokes the pipeline skill from there.
- [AC-3] `--no-worktree` (or its natural-language equivalents) skips the worktree creation; the pipeline runs in the current checkout (v1.0.0 / v1.1.0 behavior).
- [AC-4] If invoked from inside an existing `architect-team/*` worktree (re-entry case), the helper detects this and does NOT create a nested worktree.
- [AC-5] On slug or branch collision (`architect-team/foo` already exists), the helper appends `-2`, `-3`, etc., to find an available name.
- [AC-6] `common-pipeline-conventions/SKILL.md` carries a `## Auto-worktree lifecycle` section documenting the rules above.
- [AC-7] All existing tests pass (1694 baseline) PLUS the 8 new lifecycle tests. Target: 1702 / 1 skipped.
- [AC-8] Version `1.2.0` is consistent across plugin.json, marketplace.json, CHANGELOG, README, CLAUDE.md.

### Unit Test Targets

- `worktree_lifecycle.py:create_run_worktree`: creates the worktree at the expected path on the expected branch
- `worktree_lifecycle.py:create_run_worktree`: collision handling — appends `-2` when `architect-team/foo` exists
- `worktree_lifecycle.py:current_worktree_is_run`: True from a `architect-team/*` worktree, False elsewhere
- `worktree_lifecycle.py:current_run_slug`: extracts slug from branch name
- `worktree_lifecycle.py:cleanup_run_worktree`: removes worktree (and optionally branch)

### Integration Test Targets

- End-to-end: simulate a `/architect-team` invocation; verify the worktree is created, the working tree of the test moves into it, the pipeline operates in the new cwd.

### Playwright Flows

- N/A (no UI surface).

### Out of Scope

- **Auto-cleanup after Phase 8 merge** — out. The pipeline reports the worktree path + recommends cleanup, but the user decides when to remove (they may want to inspect). A future v1.3+ could add an `--auto-cleanup` flag.
- **Multi-worktree dispatch** — having the pipeline spawn teammates into DIFFERENT worktrees. Stays as a v1.3+ idea; v1.2.0 is one worktree per RUN, not per teammate.
- **Worktree creation for the `/architect-team:visual-qa`, `/architect-team:editability-audit`, `/architect-team:refine-prompt`** commands. These are read-mostly utility commands; they don't need worktrees. Limit auto-worktree to the 3 pipeline-driving commands.
- **Splitting the 7-mode `system-architect`** (SR-audit-eff-002) — still deferred to v1.x+.

## Impact

- **New:** 1 helper (`scripts/setup/worktree_lifecycle.py`), 1 test file (`tests/test_worktree_lifecycle.py`), 1 self-referential OpenSpec change folder.
- **Modified:** 3 slash command bodies, 1 cross-cutting skill, CHANGELOG, CLAUDE.md, README, 2 maps, 2 plugin metadata files.
- **Test count:** 1694 → ~1702.
- **Version:** v1.1.0 → **v1.2.0**.
- **Backwards-compatible:** existing v1.1.0 users can pass `--no-worktree` to keep the v1.1.0 behavior verbatim.
