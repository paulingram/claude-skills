---
description: Spec-to-production multi-agent coding pipeline — mini variant. Faster sibling to /architect-team for small-to-medium feature changes. Takes EITHER a requirements folder OR a plain-language requirement typed directly as prose. Single architect drafts the full 5-artifact OpenSpec bundle with a mandatory ## QA Guidance section, self-confirms to a fixed point (cap 3), dispatches backend + frontend devs in parallel (devs cross-review each other; no separate task-reviewer agent), runs a single mini-qa agent that executes unit + integration suites and 1–3 narrow Playwright flows tied to acceptance criteria against the live dev URL, and AUTO-MERGES TO MAIN on green. On red QA, the architect re-evaluates and the implement-test loop repeats until QA is green (no fixed cycle cap; it pauses only for required owner input); a genuinely stuck run escalates to the full /architect-team pipeline. Every commit carries a Mini-Run: <slug> trailer; /architect-team:mini-review-sweep replays the full heavyweight review gates across a batch of mini commits.
argument-hint: "<requirements-folder | plain-language requirement> [--no-merge] [--squash-merge] [--no-commit] [--no-push] [--no-compact]"
---

# /architect-team:mini

Drive a small-to-medium feature change end-to-end through the `mini-architect-team-pipeline` skill — intake, cached-maps freshness check, single-architect 5-artifact OpenSpec draft with mandatory `## QA Guidance`, self-confirm loop, parallel backend+frontend dev, single `mini-qa` agent (unit + integration + ≤3 Playwright flows on live dev URL), and **auto-merge to `main`** on green QA.

## Dispatch mode banner (v1.5.0) — runs first

As the very first user-visible action of the invocation, BEFORE the v1.3.0
auto-cleanup step and BEFORE argument parsing, print the dispatch-mode banner
so the user knows whether this run is dispatching via Agent Teams or the
subagents fallback (and, in the fallback case, WHY). This is purely
**informational** — the banner is observability, never a gate. A subprocess
failure surfaces a one-line note and the run continues regardless. The
dispatch-mode decision itself is unchanged from v1.0.0 (`is_teams_mode_available`
inspects env + settings.json + `claude --version` + the `--no-teams` flag).

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || echo "(dispatch banner unavailable; continuing.)"
```

The banner is informational, not gating. A subprocess failure surfaces a
one-line note and the run continues regardless. The dispatch-mode decision
itself is unchanged from v1.0.0.

## Auto-cleanup of merged worktrees (v1.3.0) — runs first

Before any argument parsing or pipeline invocation, sweep merged architect-team
worktrees. This is **best-effort** — failure surfaces a one-line note and the
new run continues regardless.

1. Refresh the origin ref so merge detection is current. Best-effort:
   ```bash
   git fetch origin main 2>/dev/null || true
   ```
2. Invoke the cleanup helper via the polyglot Python pattern per
   `common-pipeline-conventions` `## Cross-platform Python invocation`:
   ```bash
   python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || echo 'auto-cleanup: best-effort, continuing.'
   ```
3. Report any cleaned paths to the user as a brief note. If nothing was
   cleaned, say so in one line and proceed.

The cleanup defaults exclude the current worktree (safety: don't auto-remove
the cwd even if its branch is merged). This is the re-entry case from v1.2.0 —
the current run worktree is left alone. Note: the mini pipeline ALSO runs an
in-run cleanup at the end of Phase M7 after its own auto-merge to main — see
`mini-architect-team-pipeline` Phase M7 for the post-merge worktree removal.

Per `common-pipeline-conventions` `## Auto-worktree lifecycle` `### Auto-cleanup
(v1.3.0)` for the full rule including merged-branch detection mechanism
(`git merge-base --is-ancestor`) and the squash-merge limitation.

## Startup branch reconciliation (v3.7.0) — runs after the v1.3.0 sweep

After the merged-worktree sweep above, enumerate stray `architect-team/*`
branches and offer to reconcile them. Best-effort + a domain gate (one
question); silent no-op when there are none.

1. Enumerate run branches via the polyglot Python pattern:
   ```bash
   python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || echo '[]'
   ```
2. If the list is EMPTY → silent no-op; proceed to argument parsing.
3. If non-empty → present ONE `AskUserQuestion` with three options:
   - **merge-all-clean + prune** → for each branch with `cleanly_mergeable:
     true`, call `merge_branch_to_main_and_prune(branch, worktree_path)` via the
     polyglot Python; report any branch returning `conflict: true`.
   - **prune-without-merge** → `cleanup_run_worktree(Path(worktree_path),
     remove_branch=True)` per branch (discard the work).
   - **leave** → no-op.
4. Only `architect-team/*` branches are ever considered — never the user's own
   branches, never this command's OWN run branch.

Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`
for the canonical rule.

## Inputs (same two forms as /architect-team)

`$ARGUMENTS` is either:

1. **A requirements folder** — a filesystem path resolving to an existing directory holding requirement artifacts.
2. **A plain-language requirement** — prose typed directly. The prose IS the requirement; it is NOT a path.

Never refuse plain-language prose. Never treat the first word of a sentence as a path. Ask only when `$ARGUMENTS` is genuinely empty.

## Flags (each independent — `--no-merge --no-compact` is valid)

- `--no-merge` → skip the M7 auto-merge. The commit and push still happen on the working branch; the user merges manually. Falls back to `/architect-team` semantics.
- `--squash-merge` → squash-merge instead of fast-forward at M7. The architect/dev/QA commit chain becomes one commit on `main`.
- `--no-commit` → skip the M7 commit step entirely (and therefore push + merge). Used for dry runs.
- `--no-push` → commit but do not push or merge.
- `--no-compact` → suppress the trailing `/compact` prompt. Default `true`.
- `--no-worktree` → `AUTO_WORKTREE = false`. (Default `true`.) Skip the auto-worktree creation step; run the mini pipeline in the current checkout (v1.1.0 behavior). Natural-language equivalents: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- `--no-auto-merge` → `AUTO_MERGE_MAIN = false`. (Default `true`.) When true (the default), Phase M7's clean green-QA merge to `main` ALSO prunes via `merge_branch_to_main_and_prune` — branch deleted (local + remote) and worktree removed after the merge + push (conflicts skipped + reported, never forced; branch protection always wins). `--no-auto-merge` (equivalent to `--no-merge` here) restores today's feature-branch + recommend-a-PR + persistence-warning behavior. Natural-language equivalents: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. See `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`.

Natural-language phrasings count as the matching flag — "don't merge" / "don't push" / "leave it uncommitted" / "don't compact" / "no worktree" / "in place" / "keep the branch" / "PR only" / "don't merge to main" / "no auto-merge".

## When to use mini vs full pipeline

Use `/architect-team:mini` when:
- The change is bounded (≤ 5 acceptance criteria).
- The codebase maps already cover the affected codebases.
- The change does not span multiple codebases that touch each other through `INTEGRATION_MAP.md`'s contract surface.
- You're comfortable with auto-merge to `main` on green QA, or you'll pass `--no-merge`.

Use `/architect-team` (full) when:
- The change is larger or unknown in shape.
- The maps are stale and the change crosses codebases.
- The change requires the heavyweight review gates (interaction-completeness, editability-completeness, visual-fidelity-reconciliation) up front, not deferred.

## Auto-worktree creation (v1.2.0) — runs after argument parsing, before skill invocation

After binding `$REQ_DIR` and parsing the flags, AND BEFORE invoking the `mini-architect-team-pipeline` skill, determine whether the auto-worktree step applies:

- **Skip the step** when ANY of these holds:
  - `--no-worktree` (or a natural-language opt-out — *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*) was passed.
  - The current branch already starts with `architect-team/` (re-entry case — `scripts.setup.worktree_lifecycle.current_worktree_is_run()` returns True). No nested worktrees; the existing run worktree IS the workspace.

- **Run the step** otherwise:
  1. Derive a `<slug>` from the change name / refined-prompt slug / a kebab-case derivation of the prompt's first 4-6 meaningful words. The mini pipeline's existing `Mini-Run: <slug>` trailer convention informs the slug — the same `<slug>` flows from the worktree branch through the trailer.
  2. Invoke the helper via Bash — detect-once Python invocation (the v2.16.0 form): the interpreter is selected ONCE via `$(command -v python3 || command -v python)` and the snippet runs exactly once. `create_run_worktree` raises (a non-zero exit) on collision exhaustion, and the old `python3 X || python X` form would silently re-run the whole creation on that meaningful failure; detect-once invokes it exactly once. Per `common-pipeline-conventions` `## Cross-platform Python invocation`:
     ```bash
     $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
     ```
     The helper creates the worktree at `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` (the hidden per-project container, v3.6.0) on branch `architect-team/<slug>` (collision handling appends `-2`, `-3`, ... when either path or branch is taken). Capture the printed absolute path as `$WORKTREE_PATH`.
  3. `chdir` into `$WORKTREE_PATH`. Every subsequent step — including the Skill-tool invocation of `mini-architect-team-pipeline` — runs with `$WORKTREE_PATH` as cwd. The Phase M7 auto-merge-to-main behavior is unchanged: the mini pipeline fast-forwards `main` (in the MAIN worktree) to the run-branch tip from inside the run worktree.
  4. Surface a one-line note to the user: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (parent dir not writable, base branch missing, slug exhausted — the helper raises `RuntimeError` with an actionable message), surface the error verbatim and STOP. Do NOT silently fall back to the current checkout. The user re-runs with `--no-worktree` if they want single-tree mode.

At Phase M7 the mini pipeline auto-merges its branch to main and cleans its own worktree. When `AUTO_MERGE_MAIN = true` (the default; `--no-auto-merge` / `--no-merge` opts out), M7 routes the clean green-QA merge through `merge_branch_to_main_and_prune('architect-team/<slug>', $WORKTREE_PATH, push=<AUTO_PUSH>)` (v3.7.0) — which merges + pushes `main`, deletes the branch (local + remote), and removes the worktree in one helper call. A conflict (`conflict: true`) or a rejected push (`reason: "push-rejected"`, branch protection) STOPS, reports, and leaves the branch + worktree recoverable — never forced. This subsumes the v3.6.0 `finalize_run_worktree` cleanup on the clean path (finalize is then a no-op since the worktree is already gone); on the `--no-auto-merge` / unmerged path the v3.6.0 `finalize_run_worktree($WORKTREE_PATH)` behavior applies and prints the returned `warning`. Unmerged work is never auto-deleted. Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`.

Per `common-pipeline-conventions` `## Auto-worktree lifecycle` for the full rules including the path/branch convention, collision handling, the end-of-run merge check emitted at Phase M7 success, and the re-entry detection logic.

## What this command runs

This command invokes the `mini-architect-team-pipeline` skill. Read the skill for the full nine-phase (M0–M8) playbook. The mini variant explicitly excludes proposal-refiner Q&A, Phase −2 bug-classifier triage, ×3 reviewer convergence, task-reviewer, test-completeness-verifier at gate time, and visual/editability/interaction reviewers at runtime — all of those are deferred to `/architect-team:mini-review-sweep` for batched review.

## In-flight clarification discipline (v2.5.0)

If you receive a user message AFTER the pipeline has begun executing (Phase −2 / B−1 / M0 onward) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, treat the message as a **clarification or scope amendment to the IN-FLIGHT run**, NOT as a new standalone task. Append the message verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief (re-run Phase 0/1 if scope materially shifted; otherwise fold into the next phase's inputs), and continue the pipeline. Forbidden: solving the clarification with tools directly (bypasses the pipeline), answering conversationally without folding, spawning a sibling `/architect-team` invocation, or silently ignoring. The canonical rules — 3 detection signals + 4 forbidden anti-patterns + cancellation channel — live in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.
