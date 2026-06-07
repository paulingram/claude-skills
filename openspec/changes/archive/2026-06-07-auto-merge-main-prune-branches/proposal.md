## Why

Autonomous architect-team runs currently leave a feature branch + worktree behind on every run (the Phase 8 default is `ALLOW_PUSH_TO_DEFAULT=false` → commit on `architect-team/<change-name>`, push, recommend a PR). Across many autonomous runs this accumulates excess branches and worktrees the user must prune by hand. The user wants: by default, once a run passes its tests/audit, merge it straight into `main`, push, and delete the branch + worktree — with a per-workstream opt-out — plus a startup prompt that offers to reconcile any stray `architect-team/*` branches.

## What Changes

- **Add** `AUTO_MERGE_MAIN` (default `true`): on a clean Phase 8 (completion audit exit 0), the run branch is merged `--no-ff` into `main`, `main` is pushed (when `AUTO_PUSH`), the branch is deleted (local + remote), and the worktree removed via `finalize_run_worktree`. Only when the branch merges cleanly; conflicts are skipped + reported, never forced. Branch protection always wins. (REQ-001)
- **Add** `--no-auto-merge` opt-out flag (+ natural language: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*). When set, the run uses today's behavior verbatim — feature branch + push + PR recommendation + worktree-persistence warning. (REQ-002)
- **Add** a startup branch-reconciliation prompt on `/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`: after the v1.3.0 merged-worktree sweep, enumerate stray `architect-team/*` branches and (if any) present ONE `AskUserQuestion` offering merge-all-clean+prune / prune-without-merge / leave. Only cleanly-mergeable branches are merged; conflicts reported; non-`architect-team/*` branches never touched; zero stray branches = silent no-op. (REQ-003)
- **Add** two stdlib-only helpers to `scripts/setup/worktree_lifecycle.py`: `list_run_branches(against, remote)` (every local `architect-team/*` branch with merged/cleanly-mergeable status) and `merge_branch_to_main_and_prune(branch, worktree_path, against, remote, push)` (clean-merge → push → delete branch → remove worktree; conflict → abort, change nothing). (REQ-004)
- **Document & release** as v3.7.0 — the new `## Auto-merge-to-main discipline` canonical section, the 3 command bodies, the 3 pipeline skill bodies' Phase 8/B8/M7, the `worktree_lifecycle.py` docstring, README, CHANGELOG, CLAUDE.md, version bump. (REQ-005)

Reverses the prior "never push unreviewed work to main" default for autonomous tidiness, as explicitly requested; the `--no-auto-merge` opt-out preserves the safe path per workstream. Never force-merges, never auto-resolves conflicts, never bypasses branch protection.

## Capabilities

### New Capabilities

- `auto-merge-main-prune-branches`: a clean Phase 8 run auto-merges its branch into `main` and prunes its branch + worktree by default (`--no-auto-merge` opts out per workstream); at activation, the command offers to reconcile any stray `architect-team/*` branches — merging the cleanly-mergeable ones into `main` and pruning the rest, never touching non-`architect-team/*` branches and never force-merging.

### Modified Capabilities

None. The v1.2.0 create / v1.3.0 sweep / v3.6.0 finalize semantics are preserved and composed; no existing spec's requirements change.

## Impact

**Affected files:**

- `scripts/setup/worktree_lifecycle.py` — MODIFIED. New `list_run_branches`, `merge_branch_to_main_and_prune`; docstring.
- `skills/common-pipeline-conventions/SKILL.md` — MODIFIED. New `## Auto-merge-to-main discipline` section + cross-ref.
- `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md` — MODIFIED. `--no-auto-merge` flag, the Phase 8/B8/M7 auto-merge branch, the startup branch-reconciliation section.
- `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md` — MODIFIED. Phase 8/B8/M7 auto-merge step.
- `tests/test_auto_merge_main.py` — NEW. helpers (real-git) + flag parsing + structural doc/command tests.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `README.md`, `CLAUDE.md` — MODIFIED. v3.7.0.
