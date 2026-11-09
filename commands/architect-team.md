---
description: Spec-to-production multi-agent pipeline. Takes a requirements folder (OpenSpec, Superpowers, markdown) OR typed prose to build, fix, change, review or improve, and drives it to production. Commits, pushes, compacts on a Phase 8 pass unless --no-commit / --no-push / --no-compact.
argument-hint: "<requirements-folder | plain-language requirement> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first]"
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

**Raw arguments:** $ARGUMENTS

## Dispatch mode banner (v1.5.0) — runs first

Print the dispatch-mode banner as the very first user-visible action, BEFORE the v1.3.0 auto-cleanup step and BEFORE argument parsing, so the user knows whether this run dispatches via Agent Teams or the subagents fallback (and, in the fallback case, WHY). The banner is purely **informational** -- observability, never a gate: a subprocess failure surfaces a one-line note and the run continues regardless. The selection rule itself (`is_teams_mode_available`: env + settings.json + `claude --version` + the `--no-teams` flag) is `skills/common-pipeline-conventions/references/dispatch-mode.md`.

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || echo "(dispatch banner unavailable; continuing.)"
```

## Commit identity (v3.67.0) — runs after the banner, before any git-mutating step

Resolve the checkout's recorded commit identity before any step below touches git (the rule and its rationale: `common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)`, full text `skills/common-pipeline-conventions/references/git-commit-identity.md`):

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" resolve --json
```

- `"status": "recorded"` -> say *"Committing as `<name> <email>` (recorded for this checkout)"* in one line and continue.
- `"status": "candidate"` -> a name found in git config is a PROPOSAL, never adopted silently: confirm it via `AskUserQuestion` (*"Commit as `<name> <email>`?"* -- **Yes, record it for this checkout** / **No, I'll give a different name and email**), then `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" set --name "<name>" --email "<email>" --source confirmed-local-git-config|confirmed-global-git-config` (`--source asked` when they typed a different one).
- `"status": "missing"` -> ask via `AskUserQuestion` (free text, *"Reply `Name <email>`"*), then `set ... --source asked`.

A **DOMAIN gate**: it fires regardless of `--proposal-first`, ONCE per checkout, never guesses a name and never writes the user's git config; every commit-authoring git command this run issues then carries the record (the `git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=` pair).

## Auto-cleanup of merged worktrees (v1.3.0) — runs first

Before any argument parsing or pipeline invocation, sweep merged architect-team worktrees. **Best-effort**: a failure surfaces a one-line note and the new run continues regardless.

1. Refresh the origin ref so merge detection is current (best-effort): `git fetch origin main 2>/dev/null || true`
2. Invoke the cleanup helper via the polyglot Python pattern (`common-pipeline-conventions` `## Cross-platform Python invocation (polyglot pattern)`):
   ```bash
   python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || echo 'auto-cleanup: best-effort, continuing.'
   ```
3. Report any cleaned paths to the user as a brief note; if nothing was cleaned, say so in one line and proceed.

The sweep excludes the current worktree (the v1.2.0 re-entry case: the cwd is never auto-removed even if its branch is merged). The merged-branch detection (`git merge-base --is-ancestor`), the squash-merge limitation and the `exclude_current` safeguard: `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md`.

## Startup branch reconciliation (v3.7.0) — runs after the v1.3.0 sweep

After the sweep, enumerate stray `architect-team/*` branches and offer to reconcile them. Best-effort plus a domain gate (one question); a silent no-op when there are none.

1. Enumerate the unmerged run branches (the v1.3.0 sweep already removed the merged-worktree branches):
   ```bash
   python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || echo '[]'
   ```
2. EMPTY list -> silent no-op; proceed to argument parsing.
3. Non-empty -> ONE `AskUserQuestion` with three options: **merge-all-clean + prune** (for each branch with `cleanly_mergeable: true`, call `merge_branch_to_main_and_prune(branch, worktree_path)` via the polyglot Python; report any `conflict: true`, left untouched); **prune-without-merge** (`cleanup_run_worktree(Path(worktree_path), remove_branch=True)` per branch -- discards the work); **leave** (no-op).
4. Only `architect-team/*` branches are ever considered -- never the user's own branches, never this command's OWN run branch.

Canonical rule: `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`.

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the requirement.** Flags are independent (`--no-commit --no-compact` is valid) and natural-language phrasings count as the matching flag -- opt-outs: *"don't commit"* / *"no push"* / *"don't compact"* / *"leave it uncommitted"*; opt-in: *"propose first"* / *"review before implementing"* / *"show me the plan first"* / *"stop after the proposal"* trigger `--proposal-first`.

- `--no-commit` -> `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` -> `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` -> `AUTO_COMPACT_PROMPT = false`. (Default `true`.)
- `--allow-push-to-default` -> `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`: the pipeline never commits + pushes unreviewed work straight onto `main` / `master`; it commits to an `architect-team/<change-name>` feature branch and recommends a PR. Pass the flag only when a direct default-branch push is genuinely wanted.)
- `--proposal-first` -> `PROPOSAL_FIRST = true`. (Default `false`.) Run Phase −1 → 1 (intake + the validated OpenSpec proposal / design / specs / tasks package), PAUSE for the user's review, resume Phases 2 → 8 on *"proceed"* (or a revision); the default drives end-to-end without asking (`skills/architect-team-pipeline/references/default-mode-of-operation.md`). **Domain gates** -- the Phase −1D bulk-verify of low-confidence interaction intuitions, the `editability-completeness` `ambiguous` attribute escalations and the `interaction-completeness` `ambiguous` element escalations -- fire regardless of this flag: they are user-input steps that ARE the deliverable, not process interruptions to it.
- `--bug-fix` -> forces `kind: bug` at the Phase −2 triage step; skips the `bug-classifier` agent and routes the run directly to the `bug-fix-pipeline` skill (equivalent to `/architect-team:bug-fix`). Natural-language equivalents recognized at parse time: *"this is a bug"* / *"just fix the bug"* / *"it's a hotfix"* / *"bugfix"*.
- `--feature-only` -> forces `kind: feature` at Phase −2; skips the classifier and runs the full Phase −1 → 8 flow. Natural-language equivalents: *"this is a feature"* / *"build this as a feature"* / *"feature, not a bug"*. Use it for feature-pipeline rigor on what the classifier might call a small bug.
- `--data-eng` -> forces `kind: data-eng` at the Phase −2 triage step; skips the `bug-classifier` agent and routes the run directly to the `data-eng-pipeline` lane skill (the first-class data-engineering sibling lane, v3.50.0; equivalent to `/architect-team:data-eng`). The lane wins at the front door and never reaches the feature pipeline's Phase 0c. Natural-language equivalents recognized at parse time: *"this is a data pipeline"* / *"data-eng"* / *"build the warehouse"* / *"design the dbt models"* / *"it's a data-engineering task"*.
- `--no-refine` -> skip the upstream `proposal-refiner` skill (v0.9.33; `## Pre-pipeline refinement` below). Default `false`.
- `--no-worktree` -> `AUTO_WORKTREE = false`. (Default `true`.) Run in the current checkout (v1.1.0 behavior). Natural-language equivalents: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- `--no-auto-merge` -> `AUTO_MERGE_MAIN = false`. (Default `true`: a clean Phase 8 run merges its `architect-team/<change-name>` branch into `main`, pushes, deletes the branch (local + remote) and removes the worktree -- only when it merges cleanly; conflicts are skipped + reported, never forced; branch protection always wins.) The opt-out restores the feature-branch + recommend-a-PR + persistence-warning behavior. Natural-language equivalents: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. Rule: `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`.
- `--phenotype <label>` -> bind `$PHENOTYPE = <label>` and seed the run from that phenotype (a pre-made, generalized, deployable architecture under `phenotypes/` -- blueprint + scaffold; `skills/phenotypes`). Natural-language equivalents recognized at parse time: *"use the `<label>` phenotype"* / *"use phenotypes"* (when the domain is unambiguous). The pipeline loads the phenotype, confirms its variation points + scaffold parameters with the user (a domain gate), emits the scaffold as the starting point and customizes it through the normal phases (`skills/architect-team-pipeline/references/phase-1.md`). Absent -> no phenotype is seeded, though reuse-first design may still PROPOSE a matching one (never silently).
- `--appearance <strict|propose|innovate>` -> `APPEARANCE_MODE = <mode>`. (Default `strict`.) Governs unsolicited frontend-appearance changes: `strict` forbids appearance-affecting changes beyond the explicit mandate (improvement ideas are recorded to `.architect-team/appearance-proposals/<run-id>.json`, never implemented); `propose` surfaces the recorded proposals at a user approval gate (a domain gate -- only approved proposals are implemented); `innovate` authorizes appearance improvements, each logged `implemented-innovate` + `DESIGN_MAP.md`-reconciled. Natural-language equivalents recognized at parse time -- propose: *"propose appearance changes"* / *"suggest UI improvements first"* / *"ask before changing the look"*; innovate: *"innovate on the UI"* / *"free rein on the design"* / *"do whatever you want with the front end"* / *"make it look better however you want"*. Policy: `skills/common-pipeline-conventions/references/appearance-change-policy-discipline.md`.
- No flags -> `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `AUTO_WORKTREE = true`, `AUTO_MERGE_MAIN = true`, `APPEARANCE_MODE = strict` (drive end-to-end; no unsolicited appearance changes). Phase −2 triage routes on the classifier's verdict: bug-shaped requirements -> the bug-fix pipeline; feature-shaped -> the Phase −1 → 8 flow; mixed -> both in parallel.

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

A **Folder** (a filesystem path that resolves to an existing directory holding OpenSpec artifacts, a Superpowers brief, or plain markdown) binds `$REQ_DIR` to the path. A **Plain-language requirement** (prose -- a phrase, sentence, or paragraph describing what to build, fix, change, review, or improve) binds `$REQ_DIR` to the **entire remaining string, verbatim**. If what remains after stripping flags is a single token that resolves to an existing directory it is a Folder; otherwise it is a plain-language requirement -- **when unsure, it is a plain-language requirement**, since ad-hoc prose is the common case. The pipeline's **Phase 0 normalizes a plain-language requirement into an OpenSpec change**; a requirements folder is NOT required and never has been (`skills/architect-team-pipeline/references/inputs.md`).

### Forbidden — the following are bugs, not correct behavior

- **Treating the first word of a plain-language requirement as a path.** `no`, `review`, `add`, `fix`, `lets` are not directories -- the *whole string* is the requirement.
- **Refusing to run** -- or telling the user the pipeline "needs a folder" / "only drives a requirements folder" / "I won't run against a non-existent folder" -- when given prose. Running it is correct; refusing a sentence is the bug this section exists to prevent.
- **Asking the user for a requirements folder.** The only thing you may ask for is the requirement itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty** -- then ask: "What would you like the architect-team pipeline to build, fix, or change?"

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` -- a folder path OR the verbatim plain-language requirement string -- as the input to the `architect-team-pipeline` skill and substitute it for every `$REQ_DIR` reference in the skill body. For prose, the codebase the pipeline operates on is the current working directory (a git repo) unless the prose names another path. Do NOT re-prompt.

## Pre-pipeline refinement (v0.9.33) — runs BEFORE Phase −2 when input is plain-language prose

After binding `$REQ_DIR` and BEFORE invoking the `architect-team-pipeline` skill:

- **Skip refinement** when ANY holds: `$REQ_DIR` resolves to an existing directory on disk (the brief's existence satisfies the step's purpose); `$REQ_DIR` resolves to a markdown file with `refined-by: proposal-refiner` frontmatter (already refined); the `--no-refine` flag was passed.
- **Run refinement** otherwise: set `$REFINER_MODE = "pipeline"` and invoke the `proposal-refiner` skill from this plugin (Skill tool, `skill: proposal-refiner`) with the verbatim prose as input. It runs R1 → R6 -- codebase-map loading, multi-axis grading, conversational refinement with the user (unbounded by default: until the user is satisfied or the grade is A; `--max-iterations` is the user's explicit lever) -- and writes `<cwd>/.architect-team/refined-prompts/<slug>-<ts>.md`.

After it exits, **rebind `$REQ_DIR` to the absolute path of the refined-prompt markdown file**; the pipeline's Phase 0 treats it like any other plain-markdown source. The refiner is a **DOMAIN gate** (the v0.9.21 carve-out), not a process gate: the user-confirmation step IS the deliverable, the user invoking `/architect-team` with prose IS the invocation channel, and `--no-refine` is the documented opt-out.

## Auto-worktree creation (v1.2.0) — runs after refinement, before skill invocation

- **Skip the step** when `--no-worktree` (or a natural-language opt-out) was passed, OR the current branch already starts with `architect-team/` (re-entry: `scripts.setup.worktree_lifecycle.current_worktree_is_run()` returns True -- no nested worktrees, the existing run worktree IS the workspace).
- **Run the step** otherwise:
  1. Derive `<slug>` from the refined-prompt markdown's frontmatter slug (if present), else the OpenSpec change name (`$REQ_DIR` under `openspec/changes/<change-name>/`), else a kebab-case derivation of the prompt's first 4-6 meaningful words.
  2. Create the worktree with the detect-once Python invocation (the v2.16.0 form: the interpreter is selected ONCE via `$(command -v python3 || command -v python)` and the snippet runs exactly once -- `create_run_worktree` raises on collision exhaustion, and a `python3 X || python X` form would silently re-run the whole creation on that meaningful failure):
     ```bash
     $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
     ```
     The worktree lands at `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` (the hidden per-project container, v3.6.0) on branch `architect-team/<slug>` (collisions append `-2`, `-3`, ...). Capture the printed absolute path as `$WORKTREE_PATH`.
  3. `chdir` into `$WORKTREE_PATH`. Every subsequent step -- the Skill-tool invocation included -- runs there: `shared_state_dir()` keeps the lock layer and MemPalace on the MAIN worktree, `run_state_dir()` keeps reviews / teammates / handoffs / per-run OpenSpec in the run worktree.
  4. Surface one line: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (parent dir not writable, base branch missing, slug exhausted -- the helper raises `RuntimeError` with an actionable message), surface the error verbatim and STOP. Do NOT silently fall back to the current checkout: the user asked for a worktree (the default), and failing without notice is the v0.9.20 anti-pattern this explicit error path exists to prevent; they re-run with `--no-worktree` for single-tree mode. The path / branch convention, collision handling and re-entry detection: `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md`; the Phase 8 `finalize_run_worktree` step (removes a merged worktree + branch, otherwise prints the persistence `warning`; unmerged work is never auto-deleted): `skills/architect-team-pipeline/references/phase-8-commit.md`.

## Claude Design link detection

If the requirement carries a Claude Design offer -- a `claude.ai/design/p/<id>` link and/or a `claude_design` MCP mention -- the pipeline's Phase −1 intake detects it (`scripts/claude_design/claude_design_import.py`) and routes it through the `claude-design-import` skill, which materializes the design project locally and hands it to the existing interactive-mockup oracle path. No special flag is needed; when the `claude_design` MCP is unavailable the skill instructs connecting it plus running `/design-login` and auto-falls-back to the local/zip design-input path so the run never dead-ends. Procedure: `skills/intake-and-mapping/references/claude-design-offer-detection.md`.

## Invoke the pipeline

Invoke the `architect-team-pipeline` skill from this plugin (Skill tool, `skill: architect-team-pipeline`) and follow its pipeline exactly against the requirement above -- a folder OR a plain-language requirement OR the refined-prompt markdown the upstream `proposal-refiner` step produced; all three are valid. The skill begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report). **Pass the `AUTO_COMMIT`, `AUTO_PUSH`, and `ALLOW_PUSH_TO_DEFAULT` flags to the skill**; its Phase 8 reads them to decide whether to auto-commit, push, and whether it may push straight to a default branch.

## Project email notifications (opt-in)

If the target project's repository root contains a `.architect-team-notify.json` config file, the pipeline emits **opt-in, per-project email notifications** as a run progresses -- ten event types (`run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, `heartbeat`) via Gmail or SendGrid to a configured recipient list, each recipient choosing their events. The emails are **informative, not just status** (v3.34.0: `--details` / `--progress` / `--next-step` on every event; `run_start` embeds the architecture + solution plan; `waiting_on_agents` / `agents_complete` bracket every dispatch; `run_complete` is the what-shipped email). Strictly **best-effort**: the notifier always exits 0 and a failure never blocks, fails, or alters a run; with no config file it is a silent no-op. Config schema and provider setup: the "Project email notifications" section of `README.md`; wiring: `skills/architect-team-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md`.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase 8, after the final report emits "Spec `<change-name>` has been implemented." and the archive path (the canonical procedure, including the `Dispatch-Mode:` trailer and the `git_commit` notification: `skills/architect-team-pipeline/references/phase-8-commit.md`):

0. **Run the completion audit FIRST:** `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` from the repo root -- the detect-once form (interpreter chosen once, script run exactly once; the old `python3 X --check || python X --check` polyglot double-executed it and double-printed the BLOCKED message). A non-zero exit means the run is incomplete: do NOT commit; resolve the reported violations or escalate. Only an exit-0 audit proceeds.
1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add <files-the-pipeline-touched>` -- stage ONLY the files the pipeline created or modified (the coverage map's `implementing_commits` working set + `openspec/changes/<change-name>/` + any updated CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP files). Do NOT use `git add -A`.
2b. **Default-branch guard:** if the current branch is `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/<change-name>` before committing; otherwise commit on the current branch.
3. Commit with this message, authored as the checkout's RECORDED person (v3.67.0, resolved at the front door above): `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd <repo-root> git -- -C <repo-root> commit -m "<message>"` (the wrapper injects the recorded `-c user.name= -c user.email=` pair and REFUSES when there is none), or the explicit pair from `git_identity.py status --json`.
   ```
   <change-name>: <one-line summary from Phase 8 final-statement>

   - Requirements implemented: <REQ-001, REQ-002, ...> (N total)
   - Tests added: <unit / integration / e2e counts; all passing>
   - Coverage map: fully green
   - Phases −1 → 8 complete; openspec archive landed at <archive-path>

   Co-Authored-By: Claude <noreply@anthropic.com>
   ```
4. `git -C <repo-root> push -u origin <branch>` -- the branch the commit landed on (the current branch, or the step-2b `architect-team/<change-name>` branch).
5. Report the commit SHA and push range in the final user-facing report; if the commit went to an `architect-team/<change-name>` feature branch, the report MUST say so and recommend opening a PR.

If `AUTO_COMMIT = false`: skip steps 2-5 and say the changes were left uncommitted at the user's request. If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: steps 1-3 only, and say the commit was made locally but not pushed at the user's request.

### Auto-merge to main (v3.7.0)

After the completion audit passes + the commit lands on `architect-team/<change-name>`, when `AUTO_MERGE_MAIN = true` (the default):

6. Probe clean-mergeability and, if clean, merge + prune via the polyglot Python (run from / chdir to the MAIN checkout first, since the merge runs `git checkout main` there):
   ```bash
   python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1
   ```
   - `reason: "merged-and-pruned"` -> report: merged into `main`, pushed, branch deleted (local + remote), worktree removed.
   - `conflict: true` (`reason: "conflict"` / `"conflict-on-merge"`) -> the merge changed nothing; keep the branch pushed, recommend a PR, emit the v3.6.0 `finalize_run_worktree` persistence warning.
   - `reason: "push-rejected"` (branch protection / non-fast-forward) -> STOP, report the rejection, leave the branch + worktree recoverable. NEVER force.

When `AUTO_MERGE_MAIN = false` (`--no-auto-merge`): skip step 6; the feature-branch + recommend-a-PR + persistence-warning behavior runs verbatim. Canonical flow + safety rules: `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase 8 completed cleanly (with or without commit / push), emit this block AFTER the final report, as the very last thing the user sees in this turn. The model cannot execute `/compact` -- slash commands are user-typed REPL events, not tools -- so the block ends your reply with the literal command on its own line for a copy or a one-keystroke confirmation. If `AUTO_COMPACT_PROMPT = false`: skip the block entirely.

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Pipeline complete. Context is now full of build state.        ║
║  Run /compact NOW to free space for the next architect-team    ║
║  invocation. Type exactly:                                     ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

## Safety rules (non-negotiable)

- NEVER force-push.
- NEVER skip git hooks (`--no-verify`). If a pre-commit hook fails, surface the failure, fix the underlying issue, and re-commit as a NEW commit.
- NEVER amend the previous commit; always create a new commit.
- If `git push` fails (non-fast-forward / network / auth), surface the error clearly and stop -- do NOT escalate to force-push or other destructive operations.
- If the working tree had unstaged changes BEFORE the pipeline started, treat them as the user's in-progress work -- do NOT stage them in the pipeline's commit. Surface their presence in the final report.
- If staged-but-not-yet-committed work existed BEFORE the pipeline started, surface that too and do NOT lump it into the pipeline's commit.
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools from inside the pipeline.** The pipeline is synchronous and runs in one continuous flow; subagent dispatches block your turn at the harness level, so no manual timer is needed. Do NOT tell the user "I scheduled a wakeup for N minutes" or "I'll come back to this in ~X minutes" -- that is a pipeline-discipline failure. To poll an external resource (dev server ready, deploy live), use a tight bounded in-turn poll, never a scheduled wakeup that ends the turn (`skills/architect-team-pipeline/references/operating-rules.md`).

## In-flight clarification discipline (v2.5.0)

A user message that arrives AFTER the pipeline has begun executing (Phase −2 / B−1 / M0 onward), does NOT explicitly cancel the run and is NOT a fresh `/architect-team:<command>` invocation is a **clarification or scope amendment to the IN-FLIGHT run**, NOT a new standalone task: append it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief (re-run Phase 0/1 if scope materially shifted; otherwise fold it into the next phase's inputs), and continue the pipeline. Forbidden: solving the clarification with tools directly (bypasses the pipeline), answering conversationally without folding, spawning a sibling `/architect-team` invocation, or silently ignoring it. The canonical rules -- 3 detection signals + 4 forbidden anti-patterns + the cancellation channel -- live in `common-pipeline-conventions` `## In-flight clarification discipline (v2.5.0)`, full text `skills/common-pipeline-conventions/references/in-flight-clarification-discipline.md`.
