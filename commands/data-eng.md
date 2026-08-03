---
description: Data-engineering lane variant of /architect-team (v3.50.0) — the first-class sibling lane for data-engineering work. Takes EITHER a requirements folder OR a plain-language data-engineering requirement typed directly — a sentence describing the warehouse, pipeline, dbt models, or data dictionary to build, design, or refresh — and drives it through the data-eng-pipeline orchestrator (phases D−1 through D8), which reuses the main pipeline's evidence stack, dispatches data-engineering-exploration verbatim, and adds the warm-catalog-first check plus the catalog-refresh discipline. Auto-commits and pushes on a clean Phase D8 pass and emits a /compact prompt to free context. Accepts the SAME two input forms as /architect-team — folder or plain-language prose, both first-class.
argument-hint: "<requirements-folder | data-engineering requirement> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first] [--no-refine] [--no-worktree] [--no-auto-merge] [--appearance strict|propose|innovate]"
---

# Data-Engineering Lane Orchestration

You are starting the architect-team data-engineering lane — the first-class
data-engineering sibling to `/architect-team` (v3.50.0). A data-eng-primary ask
(build the warehouse dbt models, design a streaming pipeline, mine the stored
procedures into a data dictionary) routes to a purpose-built lane at the front
door rather than being handled as a generic feature. The lane is the third
documented caller of `data-engineering-exploration`; it reuses the main
pipeline's structural points and adds exactly two new disciplines — the D−1
warm-catalog-first check and the D7 catalog-refresh.

**Raw arguments:** $ARGUMENTS

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
the current run worktree is left alone.

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

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the requirement (the data-engineering ask).**

Flags (each independent — `--no-commit --no-compact` is valid; natural-language phrasings count as the matching flag):

- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false`. (Default `true`.)
- `--allow-push-to-default` → `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`.) When false, the lane does NOT commit + push unreviewed work straight onto `main` / `master` — it commits to an `architect-team/<change-slug>` feature branch and recommends a PR.
- `--proposal-first` → `PROPOSAL_FIRST = true`. (Default `false`.) Runs Phases D−1 → D1 (intake + the warm-catalog-first check + the validated OpenSpec plan), then PAUSES for user review before Phase D2 implementation. **Domain gates** — the interaction-intuition bulk-verify, the `editability-completeness` / `interaction-completeness` `ambiguous` escalations — fire regardless of this flag.
- `--no-refine` → skip the upstream `proposal-refiner` skill (v0.9.33). Default `false` — when `$REQ_DIR` is plain-language prose AND the input is not already a refined-prompt markdown, the lane invokes `proposal-refiner` FIRST to conversationally clarify the data-engineering ask with codebase-map grounding (which warehouse? which domain's models? read-from or write-to?) before Phase D−1. Pass `--no-refine` when the ask is already specific. Domain gate per v0.9.21 — the clarifying conversation IS the deliverable.
- `--no-worktree` → `AUTO_WORKTREE = false`. (Default `true`.) Skip the auto-worktree creation step; run the lane in the current checkout (v1.1.0 behavior). Natural-language equivalents: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- `--no-auto-merge` → `AUTO_MERGE_MAIN = false`. (Default `true`.) When true (the default), a clean Phase D8 run merges its `architect-team/<change-slug>` branch into `main`, pushes, deletes the branch (local + remote), and removes the worktree — only when it merges cleanly (conflicts skipped + reported, never forced; branch protection always wins). `--no-auto-merge` restores the feature-branch + recommend-a-PR + persistence-warning behavior. Natural-language equivalents: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. See `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`.
- `--appearance <strict|propose|innovate>` → `APPEARANCE_MODE = <mode>`. (Default `strict`.) A data-engineering lane is `strict` by nature — the mandate is the named data surface, and any dashboard/UI that surfaces the data is only what the requirement asks for; restyling beyond it is not in scope. Improvement ideas surfaced during the run are recorded to `.architect-team/appearance-proposals/<run-id>.json`, never implemented; pass `propose` / `innovate` to widen explicitly. Per `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`.
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `AUTO_WORKTREE = true`, `AUTO_MERGE_MAIN = true`, `APPEARANCE_MODE = strict`.

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

| Form | What it is | Bind `$REQ_DIR` to |
|---|---|---|
| **Folder** | a filesystem path that resolves to an existing directory (holding an OpenSpec brief, a data-model description, DDL, prior dictionary output, or notes) | the path |
| **Plain-language requirement** | prose — a phrase, sentence, or paragraph describing the data-engineering work (the warehouse / pipeline / models / dictionary to build, design, or refresh) | the **entire remaining string, verbatim** |

To tell them apart: if what remains after stripping flags is a single token that resolves to an existing directory → **Folder**. Otherwise → **Plain-language requirement**. **When unsure, it is a plain-language requirement** — a data-engineering ask in prose is the common case.

The lane's **Phase D−1 / D0 normalizes a plain-language requirement into an OpenSpec change** — that branch exists precisely for this. A requirements folder is NOT required and never has been.

### Forbidden — the following are bugs, not correct behavior

These rules mirror `/architect-team` exactly (the v0.9.17 same-input-forms rules):

- **Treating the first word of a plain-language requirement as a path.** `build`, `design`, `mine`, `refresh`, `the` are not directories — the *whole string* is the requirement.
- **Refusing to run** — or telling the user the lane "needs a folder" / "only drives a requirements folder" / "I won't run against a non-existent folder" — when given prose. The lane accepts a plain-language requirement directly; running it is correct.
- **Asking the user for a requirements folder.** The only thing you may ask for is the data-engineering ask itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty** — then ask: *"What data-engineering work should the data-eng lane build, design, or refresh?"*

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` — a folder path OR the verbatim plain-language requirement string — as the input to the `data-eng-pipeline` skill, and substitute it for every `$REQ_DIR` reference in the skill body. When the requirement is plain-language prose, the codebase the work applies to is the current working directory (a git repo) unless the prose names another path. Do NOT re-prompt.

## Pre-pipeline refinement (v0.9.33) — runs BEFORE Phase D−1 when input is plain-language prose

After binding `$REQ_DIR` and BEFORE invoking the `data-eng-pipeline` skill, determine whether refinement applies:

- **Skip refinement** when ANY of these holds:
  - `$REQ_DIR` resolves to an existing directory on disk.
  - `$REQ_DIR` resolves to a markdown file with `refined-by: proposal-refiner` frontmatter.
  - The `--no-refine` flag was passed.
- **Run refinement** otherwise. Set `$REFINER_MODE = "pipeline"` and invoke the `proposal-refiner` skill from this plugin (use the Skill tool with `skill: proposal-refiner`) passing `$REQ_DIR` (the verbatim data-engineering prose) as the input. The skill runs phases R1 → R6 — codebase-map loading, multi-axis grading, conversational refinement (5-iteration ceiling), and final markdown output.

After `proposal-refiner` exits in pipeline mode, **rebind `$REQ_DIR` to the absolute path of the refined-prompt markdown file**. The lane's Phase D−1 intake then operates on the refined brief.

The refiner is a DOMAIN gate per v0.9.21 — the user-confirmation step IS the deliverable.

## Auto-worktree creation (v1.2.0) — runs after refinement, before skill invocation

After binding `$REQ_DIR` and completing any refinement, AND BEFORE invoking the `data-eng-pipeline` skill, determine whether the auto-worktree step applies:

- **Skip the step** when ANY of these holds:
  - `--no-worktree` (or a natural-language opt-out — *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*) was passed.
  - The current branch already starts with `architect-team/` (re-entry case — `scripts.setup.worktree_lifecycle.current_worktree_is_run()` returns True). No nested worktrees; the existing run worktree IS the workspace.

- **Run the step** otherwise:
  1. Derive a `<slug>` from the refined-prompt slug (if present in the refined-prompt markdown's frontmatter), the OpenSpec change name, or a kebab-case derivation of the requirement's first 4-6 meaningful words.
  2. Invoke the helper via Bash — detect-once Python invocation (the v2.16.0 form): the interpreter is selected ONCE via `$(command -v python3 || command -v python)` and the snippet runs exactly once. `create_run_worktree` raises (a non-zero exit) on collision exhaustion, and the old `python3 X || python X` form would silently re-run the whole creation on that meaningful failure; detect-once invokes it exactly once. Per `common-pipeline-conventions` `## Cross-platform Python invocation`:
     ```bash
     $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
     ```
     The helper creates the worktree at `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` (the hidden per-project container, v3.6.0) on branch `architect-team/<slug>` (collision handling appends `-2`, `-3`, ... when either path or branch is taken). Capture the printed absolute path as `$WORKTREE_PATH`.
  3. `chdir` into `$WORKTREE_PATH`. Every subsequent step — including the Skill-tool invocation of `data-eng-pipeline` — runs with `$WORKTREE_PATH` as cwd. v1.1.0's `shared_state_dir()` resolution keeps the lock layer and MemPalace pointed at the MAIN worktree; `run_state_dir()` resolves per-worktree so the lane's verdict files / reviews / teammates / handoffs live in the run worktree.
  4. Surface a one-line note to the user: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (parent dir not writable, base branch missing, slug exhausted — the helper raises `RuntimeError` with an actionable message), surface the error verbatim and STOP. Do NOT silently fall back to the current checkout. The user re-runs with `--no-worktree` if they want single-tree mode.

At Phase D8 success the lane calls `finalize_run_worktree($WORKTREE_PATH)` (v3.6.0): it removes the worktree + branch if the branch is already merged into `origin/main`, otherwise it leaves the folder and prints the returned `warning` (which names the path + the manual cleanup command). Unmerged work is never auto-deleted.

Per `common-pipeline-conventions` `## Auto-worktree lifecycle` for the full rules.

## Invoke the pipeline

Invoke the `data-eng-pipeline` skill from this plugin (use the Skill tool with `skill: data-eng-pipeline`) and follow its pipeline exactly against the requirement above (a folder OR the refined-prompt markdown that the upstream `proposal-refiner` step produced). The skill begins at Phase D−1 (Intake & warm-catalog-first check) and proceeds through Phase D8 (Commit + Push), dispatching `data-engineering-exploration` verbatim at D0 and refreshing the catalog at D7.

**Pass the `AUTO_COMMIT`, `AUTO_PUSH`, `AUTO_COMPACT_PROMPT`, `ALLOW_PUSH_TO_DEFAULT`, `PROPOSAL_FIRST`, `AUTO_MERGE_MAIN`, and `APPEARANCE_MODE` flag values to the skill.** The skill's Phase D8 reads the commit / push / merge flags for its close-out behavior.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase D8, after the final report emits **"Data-engineering change `<change-slug>` has been implemented."** and the archive path:

0. **Run the completion audit FIRST:** `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` from the repo root. The `$(command -v python3 || command -v python)` substitution detects whichever Python interpreter is on PATH (Unix: `python3`; default Windows python.org: `python`) and invokes the script **exactly once**. If the final exit is non-zero, the run is incomplete — do NOT commit. Resolve violations or escalate.
1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add <files-the-lane-touched>` — stage ONLY the files the lane created or modified (the openspec change folder, the data-model / dbt / pipeline source, the refreshed dictionary artifacts, any updated maps). Do NOT use `git add -A`.
2b. **Default-branch guard:** if the current branch is `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/<change-slug>` before committing.
3. `git -C <repo-root> commit -m "<commit message per the data-eng-pipeline skill's Phase D8 template>"` — using the repo's local git config.
4. `git -C <repo-root> push -u origin <branch>` — push the branch the commit landed on.
5. Report the commit SHA and push range in the final user-facing report. If the commit landed on `architect-team/<change-slug>`, the report MUST say so and recommend opening a PR.

If `AUTO_COMMIT = false`: skip steps 2-5; mention in the report that changes were left uncommitted.

If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-3 only; mention in the report that the commit was made locally but not pushed.

### Auto-merge to main (v3.7.0)

After the completion audit passes + the commit lands on `architect-team/<change-slug>`, and when `AUTO_MERGE_MAIN = true` (the default):

6. Probe clean-mergeability and, if clean, merge + prune via the polyglot Python (run from / chdir to the MAIN checkout first):
   ```bash
   python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-slug>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-slug>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1
   ```
   - On `reason: "merged-and-pruned"` → report: merged into `main`, pushed, branch deleted (local + remote), worktree removed.
   - On `conflict: true` → the merge changed nothing; fall back to the feature-branch behavior: keep the branch pushed, recommend a PR, emit the v3.6.0 persistence warning.
   - On `reason: "push-rejected"` (branch protection) → STOP, report, leave recoverable. NEVER force.

When `AUTO_MERGE_MAIN = false` (`--no-auto-merge`): skip step 6 entirely; keep the feature-branch + recommend-a-PR + persistence-warning behavior verbatim.

Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase D8 completed cleanly, emit the standard `/compact` prompt block as the very last thing the user sees:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Data-eng lane complete. Context is now full of build state.   ║
║  Run /compact NOW to free space for the next data-eng or       ║
║  architect-team invocation. Type exactly:                      ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

If `AUTO_COMPACT_PROMPT = false`: skip the block.

## Safety rules (non-negotiable)

All the same safety rules as `/architect-team`:

- NEVER force-push.
- NEVER skip git hooks (`--no-verify`). Fix the underlying issue and re-commit.
- NEVER amend the previous commit; always create a new commit.
- If `git push` fails, surface the error clearly and stop — never escalate to force-push.
- Pre-existing unstaged or staged changes are the user's in-progress work — do NOT include them in the lane's commit; surface them in the final report.
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools from inside the lane.** The lane is synchronous; subagent dispatches block your turn. Do NOT tell the user "I scheduled a wakeup for N minutes." For external polling (a dev DB / knowledge server becoming ready), use a tight bounded in-turn `until` loop.

## In-flight clarification discipline (v2.5.0)

If you receive a user message AFTER the lane has begun executing (Phase D−1 onward) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, treat the message as a **clarification or scope amendment to the IN-FLIGHT run**, NOT as a new standalone task. Append the message verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief (re-run Phase D0/D1 if scope materially shifted; otherwise fold into the next phase's inputs), and continue the lane. Forbidden: solving the clarification with tools directly (bypasses the lane), answering conversationally without folding, spawning a sibling `/architect-team` invocation, or silently ignoring. The canonical rules — 3 detection signals + 4 forbidden anti-patterns + cancellation channel — live in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.
