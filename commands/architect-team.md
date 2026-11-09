---
description: Spec-to-production multi-agent pipeline. Takes a requirements folder (OpenSpec, Superpowers, markdown) OR typed prose to build, fix, change, review or improve, and drives it to production. Commits, pushes, compacts on a Phase 8 pass unless --no-commit / --no-push / --no-compact.
argument-hint: "<requirements-folder | plain-language requirement> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first]"
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

**Raw arguments:** $ARGUMENTS

## Dispatch mode banner (v1.5.0) — runs first

Print the dispatch-mode banner as the very first user-visible action, BEFORE the v1.3.0 auto-cleanup step and BEFORE argument parsing. It is **informational**, never a gate: a subprocess failure surfaces a one-line note and the run continues (selection rule + banner contract: `skills/common-pipeline-conventions/references/dispatch-mode.md`).

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || echo "(dispatch banner unavailable; continuing.)"
```

## Commit identity (v3.67.0) — runs after the banner, before any git-mutating step

Resolve the checkout's recorded commit identity before any step below touches git (`common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)`; full procedure `skills/common-pipeline-conventions/references/git-commit-identity.md`):

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" resolve --json
```

- `"status": "recorded"` -> say *"Committing as `<name> <email>` (recorded for this checkout)"* and continue.
- `"status": "candidate"` -> a git-config name is a PROPOSAL, never adopted silently: confirm via `AskUserQuestion` (**Yes, record it for this checkout** / **No, I'll give a different name and email**), then `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" set --name "<name>" --email "<email>" --source confirmed-local-git-config|confirmed-global-git-config` (`--source asked` when they typed a different one).
- `"status": "missing"` -> ask via `AskUserQuestion` (free text, *"Reply `Name <email>`"*), then `set ... --source asked`.

A **DOMAIN gate**: it fires regardless of `--proposal-first`, ONCE per checkout, never guesses a name and never writes the user's git config; every commit-authoring git command this run issues then carries the record (the `git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=` pair).

## Auto-cleanup of merged worktrees (v1.3.0) — runs first

Before argument parsing, sweep merged architect-team worktrees -- **best-effort**: a failure is a one-line note and the run continues.

1. `git fetch origin main 2>/dev/null || true` (so merge detection is current).
2. ```bash
   python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || echo 'auto-cleanup: best-effort, continuing.'
   ```
3. Report the cleaned paths in a brief note (or that nothing was cleaned) and proceed.

The sweep never removes the current worktree (the v1.2.0 re-entry case); detection, the squash-merge limitation and `exclude_current`: `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md`.

## Startup branch reconciliation (v3.7.0) — runs after the v1.3.0 sweep

Enumerate stray unmerged `architect-team/*` branches -- best-effort plus ONE domain-gate question; a silent no-op when there are none:

```bash
python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || echo '[]'
```

EMPTY -> proceed to argument parsing. Non-empty -> ONE `AskUserQuestion` with three options: **merge-all-clean + prune** (`merge_branch_to_main_and_prune(branch, worktree_path)` per `cleanly_mergeable: true` branch; `conflict: true` is reported and left untouched), **prune-without-merge** (`cleanup_run_worktree(Path(worktree_path), remove_branch=True)` -- discards the work), **leave** (no-op). Only `architect-team/*` branches are ever considered -- never the user's own, never this command's OWN run branch (`skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`).

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the requirement.** Flags are independent (`--no-commit --no-compact` is valid); natural-language phrasings count as the matching flag -- opt-outs *"don't commit"* / *"no push"* / *"don't compact"* / *"leave it uncommitted"*; opt-in *"propose first"* / *"review before implementing"* / *"show me the plan first"* / *"stop after the proposal"* trigger `--proposal-first`.

- `--no-commit` -> `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` -> `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` -> `AUTO_COMPACT_PROMPT = false`. (Default `true`.)
- `--allow-push-to-default` -> `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`: unreviewed work never goes straight onto `main` / `master`; it lands on an `architect-team/<change-name>` branch with a PR recommended -- the default-branch guard in `skills/architect-team-pipeline/references/phase-8-commit.md`.)
- `--proposal-first` -> `PROPOSAL_FIRST = true`. (Default `false`.) Phase −1 → 1, PAUSE for the user's review, resume Phases 2 → 8 on *"proceed"* (`skills/architect-team-pipeline/references/default-mode-of-operation.md`). **Domain gates** -- the Phase −1D bulk-verify of low-confidence interaction intuitions, the `editability-completeness` and `interaction-completeness` `ambiguous` escalations -- fire regardless of this flag: they ARE the deliverable.
- `--bug-fix` -> `kind: bug` at the Phase −2 triage step; skips the `bug-classifier` agent, routes to the `bug-fix-pipeline` skill (= `/architect-team:bug-fix`). Natural-language: *"this is a bug"* / *"just fix the bug"* / *"it's a hotfix"* / *"bugfix"*.
- `--feature-only` -> `kind: feature` at Phase −2; skips the classifier, runs the full Phase −1 → 8 flow. Natural-language: *"this is a feature"* / *"build this as a feature"* / *"feature, not a bug"*.
- `--data-eng` -> `kind: data-eng` at the Phase −2 triage step; skips the `bug-classifier` agent, routes to the `data-eng-pipeline` lane skill (v3.50.0; = `/architect-team:data-eng`; the lane wins at the front door and never reaches Phase 0c). Natural-language: *"this is a data pipeline"* / *"data-eng"* / *"build the warehouse"* / *"design the dbt models"* / *"it's a data-engineering task"*. Routing: `skills/architect-team-pipeline/references/phase--2.md`.
- `--no-refine` -> skip the upstream `proposal-refiner` skill (v0.9.33; `## Pre-pipeline refinement` below). Default `false`.
- `--no-worktree` -> `AUTO_WORKTREE = false`. (Default `true`; run in the current checkout.) Natural-language: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- `--no-auto-merge` -> `AUTO_MERGE_MAIN = false`. (Default `true`: a clean Phase 8 run merges its branch into `main`, pushes, deletes the branch and removes the worktree -- only on a clean merge, never forced.) The opt-out keeps the feature-branch + recommend-a-PR + persistence-warning behavior. Natural-language: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. Rule: `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`.
- `--phenotype <label>` -> `$PHENOTYPE = <label>`: seed the run from that phenotype (blueprint + scaffold under `phenotypes/`; its variation points + scaffold parameters are confirmed with the user -- a domain gate -- then customized through the normal phases: `skills/phenotypes`, `skills/architect-team-pipeline/references/phase-1.md`). Natural-language: *"use the `<label>` phenotype"* / *"use phenotypes"*. Absent -> none is seeded, though reuse-first design may PROPOSE one (never silently).
- `--appearance <strict|propose|innovate>` -> `APPEARANCE_MODE = <mode>`. Default `strict` (no appearance-affecting change beyond the explicit mandate; ideas are recorded to `.architect-team/appearance-proposals/<run-id>.json`, never implemented); `propose` surfaces them at a user approval gate (a domain gate); `innovate` authorizes them, each logged `implemented-innovate` + `DESIGN_MAP.md`-reconciled. Natural-language -- propose: *"propose appearance changes"* / *"suggest UI improvements first"* / *"ask before changing the look"*; innovate: *"innovate on the UI"* / *"free rein on the design"* / *"do whatever you want with the front end"* / *"make it look better however you want"*. Policy: `skills/common-pipeline-conventions/references/appearance-change-policy-discipline.md`.
- No flags -> `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `AUTO_WORKTREE = true`, `AUTO_MERGE_MAIN = true`, `APPEARANCE_MODE = strict`. Phase −2 triage routes on the classifier's verdict: bug-shaped -> bug-fix pipeline; feature-shaped -> Phase −1 → 8; mixed -> both in parallel.

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

A **Folder** (a path resolving to an existing directory of OpenSpec artifacts, a Superpowers brief, or plain markdown) binds `$REQ_DIR` to the path; a **Plain-language requirement** (prose describing what to build, fix, change, review, or improve) binds `$REQ_DIR` to the **entire remaining string, verbatim**. A single remaining token that resolves to an existing directory is a Folder; anything else is prose -- **when unsure, it is a plain-language requirement**. Phase 0 normalizes prose into an OpenSpec change; a requirements folder is NOT required and never has been (`skills/architect-team-pipeline/references/inputs.md`).

### Forbidden — the following are bugs, not correct behavior

Treating the **first word** of prose as a path (`no`, `review`, `add`, `fix`, `lets` are not directories -- the *whole string* is the requirement); **refusing to run**, or saying the pipeline "needs a folder", when given prose; asking for a requirements folder -- ask only for the requirement itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty**: "What would you like the architect-team pipeline to build, fix, or change?"

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` (folder path OR verbatim prose) as the `architect-team-pipeline` skill's input, substituting it for every `$REQ_DIR` in the skill body; for prose the codebase is the current working directory unless the prose names another path. Do NOT re-prompt.

## Pre-pipeline refinement (v0.9.33) — runs BEFORE Phase −2 when input is plain-language prose

After binding `$REQ_DIR` and BEFORE invoking the pipeline skill: **skip refinement** when `$REQ_DIR` resolves to an existing directory, OR to a markdown file with `refined-by: proposal-refiner` frontmatter, OR `--no-refine` was passed; **run it** otherwise -- set `$REFINER_MODE = "pipeline"` and invoke the `proposal-refiner` skill (Skill tool, `skill: proposal-refiner`) with the verbatim prose; it runs R1 → R6 (unbounded by default; `--max-iterations` is the user's lever) and writes `<cwd>/.architect-team/refined-prompts/<slug>-<ts>.md` (`skills/proposal-refiner/SKILL.md`). Then **rebind `$REQ_DIR` to that file's absolute path**; Phase 0 reads it like any plain-markdown source. The refiner is a **DOMAIN gate** (the v0.9.21 carve-out), not a process gate: the user-confirmation step IS the deliverable; `--no-refine` is the documented opt-out.

## Auto-worktree creation (v1.2.0) — runs after refinement, before skill invocation

**Skip** when `--no-worktree` (or its natural-language opt-out) was passed, OR the current branch already starts with `architect-team/` (re-entry -- `scripts.setup.worktree_lifecycle.current_worktree_is_run()` is True; no nested worktrees). **Run** otherwise:

1. Derive `<slug>` from the refined-prompt frontmatter slug, else the OpenSpec change name, else a kebab-case derivation of the prompt's first 4-6 meaningful words.
2. Create the worktree with the detect-once invocation (interpreter selected ONCE, snippet run exactly once -- `create_run_worktree` raises on collision exhaustion, which a `python3 X || python X` form would silently re-run):
   ```bash
   $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
   ```
   It lands at `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` on branch `architect-team/<slug>` (collisions append `-2`, `-3`, ...). Capture the printed path as `$WORKTREE_PATH`.
3. `chdir` into `$WORKTREE_PATH`; every later step, the Skill-tool invocation included, runs there (`shared_state_dir()` keeps locks + MemPalace on the MAIN worktree; `run_state_dir()` keeps reviews / teammates / handoffs / per-run OpenSpec in the run worktree).
4. Say in one line: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (the helper raises `RuntimeError` with an actionable message) surface the error verbatim and STOP -- never silently fall back to the current checkout; the user re-runs with `--no-worktree`. Path / branch convention, collisions, re-entry: `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md`; the Phase 8 `finalize_run_worktree` step (unmerged work is never auto-deleted): `skills/architect-team-pipeline/references/phase-8-commit.md`.

## Claude Design link detection

A `claude.ai/design/p/<id>` link and/or a `claude_design` MCP mention in the requirement is detected at Phase −1 intake (`scripts/claude_design/claude_design_import.py`) and routed through the `claude-design-import` skill, which materializes the design project locally and hands it to the interactive-mockup oracle path; no flag is needed, and an unavailable MCP falls back to the local/zip path (after asking the user to connect it and run `/design-login`) so the run never dead-ends. Procedure: `skills/intake-and-mapping/references/claude-design-offer-detection.md`.

## Invoke the pipeline

Invoke the `architect-team-pipeline` skill (Skill tool, `skill: architect-team-pipeline`) and follow it exactly against the requirement above -- a folder, a plain-language requirement, OR the refined-prompt markdown -- from Phase −1 (Intake & Mapping) through Phase 8 (Final Report). **Pass the `AUTO_COMMIT`, `AUTO_PUSH`, and `ALLOW_PUSH_TO_DEFAULT` flags to the skill**; Phase 8 reads them.

## Project email notifications (opt-in)

With `.architect-team-notify.json` in the target project's repository root, the pipeline emits **opt-in, per-project email notifications** -- ten event types (`run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, `heartbeat`) via Gmail or SendGrid, each recipient choosing their events, every email informative (v3.34.0). Strictly **best-effort**: the notifier always exits 0 and never blocks or alters a run; without the config it is a silent no-op. Config schema: the "Project email notifications" section of `README.md`; wiring: `skills/architect-team-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md`.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase 8, after the final report emits "Spec `<change-name>` has been implemented." and the archive path (canonical procedure, commit-message template included: `skills/architect-team-pipeline/references/phase-8-commit.md`):

0. **Run the completion audit FIRST:** `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` from the repo root (detect-once: interpreter chosen once, script run exactly once). Non-zero -> the run is incomplete: do NOT commit; resolve the reported violations or escalate. Only an exit-0 audit proceeds.
1. `git -C <repo-root> status --porcelain`.
2. `git -C <repo-root> add <files-the-pipeline-touched>` -- ONLY the pipeline's working set (the coverage map's `implementing_commits` + `openspec/changes/<change-name>/` + updated CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP files). Never `git add -A`.
2b. **Default-branch guard:** on `main` / `master` with `ALLOW_PUSH_TO_DEFAULT` false, `git -C <repo-root> checkout -b architect-team/<change-name>` first; otherwise commit on the current branch.
3. Commit (message per the chapter's template -- `<change-name>: <summary>`, requirements implemented, tests added, coverage map green, phases complete + archive path, `Co-Authored-By: Claude <noreply@anthropic.com>`) as the checkout's RECORDED person (v3.67.0, resolved at the front door): `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd <repo-root> git -- -C <repo-root> commit -m "<message>"` (the wrapper injects the recorded `-c user.name= -c user.email=` pair and REFUSES when there is none), or the explicit pair from `git_identity.py status --json`.
4. `git -C <repo-root> push -u origin <branch>` -- the branch the commit landed on.
5. Report the commit SHA and push range; if the commit went to an `architect-team/<change-name>` branch, say so and recommend a PR.

`AUTO_COMMIT = false` -> skip steps 2-5 and say the changes were left uncommitted at the user's request. `AUTO_COMMIT = true` + `AUTO_PUSH = false` -> steps 1-3 only; say the commit was not pushed.

### Auto-merge to main (v3.7.0)

After the audit passes + the commit lands on `architect-team/<change-name>`, when `AUTO_MERGE_MAIN = true` (the default), step 6: from the MAIN checkout (the helper runs `git checkout main` there) probe clean-mergeability and, if clean, merge + prune:

```bash
python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1
```

`reason: "merged-and-pruned"` -> report merged into `main`, pushed, branch deleted (local + remote), worktree removed. `conflict: true` -> nothing changed; keep the branch pushed, recommend a PR, emit the v3.6.0 `finalize_run_worktree` persistence warning. `reason: "push-rejected"` -> STOP, report it, leave branch + worktree recoverable; NEVER force. `AUTO_MERGE_MAIN = false` -> skip step 6 (feature-branch + PR + persistence warning verbatim). Flow + safety: `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase 8 completed cleanly, end the turn with the `READY FOR /compact` block from `skills/architect-team-pipeline/references/phase-8-commit.md` `### Auto-compact prompt (after the final report; default on)`, emitted verbatim as the very last thing the user sees: the model cannot run `/compact` itself (a user-typed REPL event, not a tool), so the literal command sits on its own line for a one-keystroke confirmation. `AUTO_COMPACT_PROMPT = false` -> skip the block.

## Safety rules (non-negotiable)

- NEVER force-push; NEVER skip git hooks (`--no-verify`) -- a failing pre-commit hook is surfaced, fixed, and followed by a NEW commit; NEVER amend the previous commit; a failed `git push` is surfaced and stops the run, never escalated to a destructive operation.
- Unstaged or staged work that existed BEFORE the pipeline started is the user's: never stage it in the pipeline's commit; surface its presence in the final report.
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools from inside the pipeline.** The pipeline is synchronous; a subagent dispatch blocks your turn at the harness level. Never tell the user "I scheduled a wakeup for N minutes"; poll an external resource with a tight bounded in-turn poll, never a wakeup that ends the turn (`skills/architect-team-pipeline/references/operating-rules.md`).

## In-flight clarification discipline (v2.5.0)

A user message that arrives AFTER the pipeline has begun (Phase −2 / B−1 / M0 onward), does NOT explicitly cancel the run and is NOT a fresh `/architect-team:<command>` invocation is a **clarification or scope amendment to the IN-FLIGHT run**, NOT a new task: append it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief (re-run Phase 0/1 if scope materially shifted, else fold it into the next phase's inputs) and continue. Forbidden: solving it with tools directly (a pipeline bypass), answering conversationally without folding, spawning a sibling `/architect-team` invocation, or silently ignoring it. Detection signals, anti-patterns and the cancellation channel: `common-pipeline-conventions` `## In-flight clarification discipline (v2.5.0)`, full text `skills/common-pipeline-conventions/references/in-flight-clarification-discipline.md`.
