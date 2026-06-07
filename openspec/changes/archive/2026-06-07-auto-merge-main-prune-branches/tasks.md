# Tasks

## 1. Code — worktree_lifecycle.py (REQ-004)

- [x] 1.1 Add `_branch_cleanly_mergeable(toplevel, branch, against="main") -> bool` using `git merge-tree --write-tree <against> <branch>` (exit 0 + no CONFLICT) with a safe fallback; never mutates the working tree.
- [x] 1.2 Add `list_run_branches(against="main", remote="origin") -> list[dict]` — each local `architect-team/*` branch → `{branch, worktree_path, merged_into_main, cleanly_mergeable}`; non-architect-team branches excluded; best-effort `[]`.
- [x] 1.3 Add `merge_branch_to_main_and_prune(branch, worktree_path=None, against="main", remote="origin", push=True) -> dict` per design D2 (guard non-run-branch; conflict→abort+change-nothing; merge --no-ff; push w/ rejection detection, no force; delete branch local+remote; remove worktree; best-effort dict).
- [x] 1.4 Update the module docstring (public-API list + a short "auto-merge to main" note).

## 2. Tests (REQ-001..REQ-004)

- [x] 2.1 Add `tests/test_auto_merge_main.py` (real git, self-remote origin/main, no mocks): list_run_branches (merged + unmerged + non-architect-team ignored + worktree path); merge_branch_to_main_and_prune clean path (merged into main, branch gone, worktree gone, push to self-remote); conflict path (returns conflict, main unchanged, branch+worktree intact); non-run-branch guard.
- [x] 2.2 Flag-parsing structural tests: `--no-auto-merge` + the 4 natural-language phrases documented in the 3 command bodies.
- [x] 2.3 Structural tests: the `## Auto-merge-to-main discipline` canonical section exists; the 3 command bodies document the startup reconcile + the Phase 8/B8/M7 auto-merge branch.

## 3. Docs + commands (REQ-001..REQ-003, REQ-005)

- [x] 3.1 `skills/common-pipeline-conventions/SKILL.md`: new `## Auto-merge-to-main discipline (v3.7.0)` canonical section (AUTO_MERGE_MAIN default, the clean-merge+prune flow, conflict/branch-protection safety, the startup reconcile, the `--no-auto-merge` opt-out, reconciliation with `--allow-push-to-default`).
- [x] 3.2 `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`: add `--no-auto-merge` to the flag list (+ NL); add a `## Startup branch reconciliation (v3.7.0)` section after the v1.3.0 sweep; update the `## Default git behavior` section with the auto-merge-to-main branch + conflict/branch-protection safety.
- [x] 3.3 `skills/architect-team-pipeline/SKILL.md` (Phase 8), `skills/bug-fix-pipeline/SKILL.md` (B8), `skills/mini-architect-team-pipeline/SKILL.md` (M7): wire the auto-merge step after the completion audit + commit, gated on AUTO_MERGE_MAIN + clean-mergeability; opt-out path documented.

## 4. Release (REQ-005)

- [x] 4.1 Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to 3.7.0.
- [x] 4.2 `CHANGELOG.md` v3.7.0 entry.
- [x] 4.3 README + CLAUDE.md currency (orchestrator Phase 8 doc step — leave to orchestrator except the README banner version token if a structural test requires it).
- [x] 4.4 Full `python -m pytest` green (Windows cp1252 + PYTHONUTF8=1).
