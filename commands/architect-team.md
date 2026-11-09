---
description: Spec-to-production multi-agent pipeline. Takes a requirements folder (OpenSpec, Superpowers, markdown) OR typed prose to build, fix, change, review or improve, and drives it to production. Commits, pushes, compacts on a Phase 8 pass unless --no-commit / --no-push / --no-compact.
argument-hint: "<requirements-folder | plain-language requirement> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first]"
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

**Raw arguments:** $ARGUMENTS

## Dispatch mode banner (v1.5.0) — runs first

Print the banner as the very first user-visible action, BEFORE the v1.3.0 auto-cleanup step and BEFORE argument parsing. It is **informational**, never a gate: a subprocess failure is a one-line note and the run continues (`skills/common-pipeline-conventions/references/dispatch-mode.md`).

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from teams_mode import format_dispatch_banner; print(format_dispatch_banner())" 2>&1 || echo "(dispatch banner unavailable; continuing.)"
```

## Commit identity (v3.67.0) — runs after the banner, before any git-mutating step

Resolve the checkout's recorded commit identity before any step below touches git (`common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)`; full procedure `skills/common-pipeline-conventions/references/git-commit-identity.md`):

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" resolve --json
```

- `"status": "recorded"` -> say *"Committing as `<name> <email>` (recorded for this checkout)"* and continue.
- `"status": "candidate"` -> a git-config name is a PROPOSAL, never adopted silently: confirm it via `AskUserQuestion`, then `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" set --name "<name>" --email "<email>" --source confirmed-local-git-config|confirmed-global-git-config` (`--source asked` when they typed a different one).
- `"status": "missing"` -> ask via `AskUserQuestion` (free text, *"Reply `Name <email>`"*), then `set ... --source asked`.

A **DOMAIN gate**: it fires regardless of `--proposal-first`, ONCE per checkout, never guesses a name and never writes the user's git config; every commit-authoring git command this run issues then carries the record (the `git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=` pair).

## Auto-cleanup of merged worktrees (v1.3.0) — runs first

Before argument parsing, sweep merged architect-team worktrees -- **best-effort**: a failure is a one-line note and the run continues.

1. `git fetch origin main 2>/dev/null || true`
2. ```bash
   python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || echo 'auto-cleanup: best-effort, continuing.'
   ```
3. Report the cleaned paths in a brief note (or that nothing was cleaned) and proceed.

The sweep never removes the current worktree (the v1.2.0 re-entry case); the full rule: `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md`.

## Startup branch reconciliation (v3.7.0) — runs after the v1.3.0 sweep

Enumerate stray unmerged `architect-team/*` branches (best-effort; a silent no-op when none):

```bash
python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import list_run_branches; print(json.dumps([b for b in list_run_branches() if not b['merged_into_main']]))" 2>&1 || echo '[]'
```

Non-empty -> ONE `AskUserQuestion` (a domain gate) with the three options **merge-all-clean + prune** (`merge_branch_to_main_and_prune`; conflicts reported, left untouched) / **prune-without-merge** (`cleanup_run_worktree(..., remove_branch=True)`) / **leave**, exactly as `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md` `### Startup branch reconciliation` states. Only `architect-team/*` branches are ever considered -- never the user's own, never this command's OWN run branch.

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the requirement.** Flags are independent (`--no-commit --no-compact` is valid); natural-language phrasings count as the matching flag -- opt-outs *"don't commit"* / *"no push"* / *"don't compact"* / *"leave it uncommitted"*; opt-in *"propose first"* / *"review before implementing"* / *"show me the plan first"* / *"stop after the proposal"* trigger `--proposal-first`.

- `--no-commit` -> `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` -> `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` -> `AUTO_COMPACT_PROMPT = false`. (Default `true`.)
- `--allow-push-to-default` -> `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`: unreviewed work lands on an `architect-team/<change-name>` branch with a PR recommended, never straight onto `main` / `master` -- the default-branch guard in `skills/architect-team-pipeline/references/phase-8-commit.md`.)
- `--proposal-first` -> `PROPOSAL_FIRST = true`. (Default `false`.) Phase −1 → 1, PAUSE for review, resume Phases 2 → 8 on *"proceed"* (`skills/architect-team-pipeline/references/default-mode-of-operation.md`). **Domain gates** -- the Phase −1D bulk-verify of low-confidence interaction intuitions, the `editability-completeness` and `interaction-completeness` `ambiguous` escalations -- fire regardless of this flag: they ARE the deliverable.
- `--bug-fix` -> `kind: bug` at the Phase −2 triage step; skips the `bug-classifier` agent, routes to the `bug-fix-pipeline` skill (= `/architect-team:bug-fix`). Natural-language: *"this is a bug"* / *"just fix the bug"* / *"it's a hotfix"* / *"bugfix"*.
- `--feature-only` -> `kind: feature` at Phase −2; skips the classifier, runs the full Phase −1 → 8 flow. Natural-language: *"this is a feature"* / *"build this as a feature"* / *"feature, not a bug"*.
- `--data-eng` -> `kind: data-eng` at the Phase −2 triage step; skips the `bug-classifier` agent, routes to the `data-eng-pipeline` lane skill (v3.50.0; = `/architect-team:data-eng`; the lane wins at the front door). Natural-language: *"this is a data pipeline"* / *"data-eng"* / *"build the warehouse"* / *"design the dbt models"* / *"it's a data-engineering task"*.
- `--no-refine` -> skip the upstream `proposal-refiner` skill (v0.9.33; `## Pre-pipeline refinement` below). Default `false`.
- `--no-worktree` -> `AUTO_WORKTREE = false`. (Default `true`.) Natural-language: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- `--no-auto-merge` -> `AUTO_MERGE_MAIN = false`. (Default `true`: a clean Phase 8 run merges into `main`, pushes and prunes branch + worktree -- clean merges only, never forced; the opt-out keeps the feature-branch + PR behavior.) Natural-language: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. Rule: `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`.
- `--phenotype <label>` -> `$PHENOTYPE = <label>`: seed the run from that phenotype (blueprint + scaffold under `phenotypes/`; variation points confirmed with the user -- a domain gate -- then customized through the normal phases: `skills/phenotypes`, `skills/architect-team-pipeline/references/phase-1.md`). Natural-language: *"use the `<label>` phenotype"* / *"use phenotypes"*. Absent -> none is seeded, though reuse-first design may PROPOSE one (never silently).
- `--appearance <strict|propose|innovate>` -> `APPEARANCE_MODE = <mode>`. Default `strict` (no appearance change beyond the mandate; ideas recorded to `.architect-team/appearance-proposals/<run-id>.json`, never implemented); `propose` = a user approval gate (a domain gate); `innovate` = authorized, each logged `implemented-innovate` + `DESIGN_MAP.md`-reconciled. Natural-language -- propose: *"propose appearance changes"* / *"suggest UI improvements first"* / *"ask before changing the look"*; innovate: *"innovate on the UI"* / *"free rein on the design"* / *"do whatever you want with the front end"* / *"make it look better however you want"*. Policy: `skills/common-pipeline-conventions/references/appearance-change-policy-discipline.md`.
- No flags -> `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `AUTO_WORKTREE = true`, `AUTO_MERGE_MAIN = true`, `APPEARANCE_MODE = strict`; Phase −2 triage routes on the classifier's verdict (bug -> bug-fix pipeline, feature -> Phase −1 → 8, mixed -> both in parallel).

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

A **Folder** (a path resolving to an existing directory of OpenSpec artifacts, a Superpowers brief, or plain markdown) binds `$REQ_DIR` to the path; a **Plain-language requirement** (prose describing what to build, fix, change, review, or improve) binds `$REQ_DIR` to the **entire remaining string, verbatim**. A single remaining token that resolves to an existing directory is a Folder; anything else is prose -- **when unsure, it is a plain-language requirement**. Phase 0 normalizes prose into an OpenSpec change; a folder is NOT required and never has been (`skills/architect-team-pipeline/references/inputs.md`).

### Forbidden — the following are bugs, not correct behavior

Treating the **first word** of prose as a path (`no`, `review`, `add`, `fix`, `lets` are not directories); **refusing to run**, or saying the pipeline "needs a folder", when given prose; asking for a requirements folder -- ask only for the requirement itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty**: "What would you like the architect-team pipeline to build, fix, or change?"

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` (folder path OR verbatim prose) as the `architect-team-pipeline` skill's input, substituting it for every `$REQ_DIR` in the skill body; for prose the codebase is the current working directory unless the prose names another path. Do NOT re-prompt.

## Pre-pipeline refinement (v0.9.33) — runs BEFORE Phase −2 when input is plain-language prose

After binding `$REQ_DIR` and BEFORE invoking the pipeline skill: **skip refinement** when `$REQ_DIR` resolves to an existing directory, OR to a markdown file with `refined-by: proposal-refiner` frontmatter, OR `--no-refine` was passed; **run it** otherwise -- set `$REFINER_MODE = "pipeline"` and invoke the `proposal-refiner` skill (Skill tool, `skill: proposal-refiner`) with the verbatim prose; it refines R1 → R6 (unbounded by default; `--max-iterations` is the user's lever) and writes `<cwd>/.architect-team/refined-prompts/<slug>-<ts>.md` (`skills/proposal-refiner/SKILL.md`). Then **rebind `$REQ_DIR` to that file's absolute path**; Phase 0 reads it like any plain-markdown source. A **DOMAIN gate** (the v0.9.21 carve-out), not a process gate: the user-confirmation step IS the deliverable; `--no-refine` is the documented opt-out.

## Auto-worktree creation (v1.2.0) — runs after refinement, before skill invocation

**Skip** when `--no-worktree` (or its natural-language opt-out) was passed, OR the current branch already starts with `architect-team/` (re-entry -- `scripts.setup.worktree_lifecycle.current_worktree_is_run()` is True; no nested worktrees). **Run** otherwise:

1. Derive `<slug>` from the refined-prompt frontmatter slug, else the OpenSpec change name, else a kebab-case derivation of the prompt's first 4-6 meaningful words.
2. Create the worktree with the detect-once invocation (`create_run_worktree` raises on collision exhaustion, which a `python3 X || python X` form would silently re-run):
   ```bash
   $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
   ```
   Capture the printed path as `$WORKTREE_PATH` (`<parent-of-repo>/.<repo-name>-worktrees/<slug>/`, branch `architect-team/<slug>`).
3. `chdir` into `$WORKTREE_PATH`; every later step, the Skill-tool invocation included, runs there (`shared_state_dir()` stays on the MAIN worktree, `run_state_dir()` is per-run).
4. Say in one line: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (`RuntimeError` with an actionable message) surface the error verbatim and STOP -- never silently fall back to the current checkout; the user re-runs with `--no-worktree`. Conventions, collisions, re-entry: `skills/common-pipeline-conventions/references/auto-worktree-lifecycle.md`; the Phase 8 `finalize_run_worktree` step: `skills/architect-team-pipeline/references/phase-8-commit.md`.

## Claude Design link detection

A `claude.ai/design/p/<id>` link and/or a `claude_design` MCP mention in the requirement is detected at Phase −1 intake (`scripts/claude_design/claude_design_import.py`) and routed through the `claude-design-import` skill, which materializes the design project locally for the interactive-mockup oracle path; no flag is needed, and an unavailable MCP falls back to the local/zip path so the run never dead-ends (`skills/intake-and-mapping/references/claude-design-offer-detection.md`).

## Invoke the pipeline

Invoke the `architect-team-pipeline` skill (Skill tool, `skill: architect-team-pipeline`) and follow it exactly against the requirement above -- a folder, a plain-language requirement, OR the refined-prompt markdown -- from Phase −1 (Intake & Mapping) through Phase 8 (Final Report). **Pass the `AUTO_COMMIT`, `AUTO_PUSH`, and `ALLOW_PUSH_TO_DEFAULT` flags to the skill**; Phase 8 reads them.

## Project email notifications (opt-in)

With `.architect-team-notify.json` in the target project's repository root, the pipeline emits **opt-in, best-effort, per-project email notifications** -- ten event types (`run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, `heartbeat`) via Gmail or SendGrid, each recipient choosing their events, every email informative (v3.34.0). The notifier always exits 0 and never blocks or alters a run; without the config it is a silent no-op. Config: `README.md` "Project email notifications"; wiring: `skills/architect-team-pipeline/references/notifications-per-project-email-events-opt-in-best-effort.md`.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase 8, after the final report emits "Spec `<change-name>` has been implemented." and the archive path (canonical procedure + commit-message template: `skills/architect-team-pipeline/references/phase-8-commit.md`):

0. **Run the completion audit FIRST:** `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` from the repo root (detect-once form). Non-zero -> the run is incomplete: do NOT commit; resolve the reported violations or escalate.
1. `git -C <repo-root> status --porcelain`.
2. `git -C <repo-root> add <files-the-pipeline-touched>` -- ONLY the pipeline's working set; never `git add -A`.
2b. **Default-branch guard:** on `main` / `master` with `ALLOW_PUSH_TO_DEFAULT` false, `git -C <repo-root> checkout -b architect-team/<change-name>` first.
3. Commit as the checkout's RECORDED person (v3.67.0): `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd <repo-root> git -- -C <repo-root> commit -m "<message>"` (the wrapper injects the recorded `-c user.name= -c user.email=` pair and REFUSES when there is none), or the explicit pair from `git_identity.py status --json`.
4. `git -C <repo-root> push -u origin <branch>` -- the branch the commit landed on.
5. Report the commit SHA and push range; a commit on `architect-team/<change-name>` is named as such with a PR recommended.

`AUTO_COMMIT = false` -> skip steps 2-5 and say so in the report. `AUTO_COMMIT = true` + `AUTO_PUSH = false` -> steps 1-3 only; say the commit was not pushed.

### Auto-merge to main (v3.7.0)

After the audit passes + the commit lands on `architect-team/<change-name>`, when `AUTO_MERGE_MAIN = true`, step 6: from the MAIN checkout probe clean-mergeability and, if clean, merge + prune:

```bash
python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1
```

`merged-and-pruned` -> report it; `conflict: true` -> keep the branch pushed, recommend a PR, emit the `finalize_run_worktree` persistence warning; `push-rejected` -> STOP, NEVER force. `AUTO_MERGE_MAIN = false` -> skip step 6. Flow + safety: `skills/common-pipeline-conventions/references/auto-merge-to-main-discipline.md`.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase 8 completed cleanly, end the turn with the `READY FOR /compact` block from `skills/architect-team-pipeline/references/phase-8-commit.md` `### Auto-compact prompt (after the final report; default on)`, verbatim, as the very last thing the user sees (the model cannot run `/compact` itself, so the literal command sits on its own line). `AUTO_COMPACT_PROMPT = false` -> skip it.

## Safety rules (non-negotiable)

- NEVER force-push; NEVER skip git hooks (`--no-verify`); NEVER amend -- a failing hook or push is surfaced, fixed, and followed by a NEW commit, never a destructive escalation. Pre-existing unstaged or staged user work is never swept into the pipeline's commit and is surfaced in the report (`skills/architect-team-pipeline/references/phase-8-commit.md`).
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools from inside the pipeline.** The pipeline is synchronous; a subagent dispatch blocks your turn. Never tell the user "I scheduled a wakeup for N minutes"; poll with a tight bounded in-turn poll (`skills/architect-team-pipeline/references/operating-rules.md`).

## In-flight clarification discipline (v2.5.0)

A user message that arrives AFTER the pipeline has begun (Phase −2 / B−1 / M0 onward), does NOT cancel the run and is NOT a fresh `/architect-team:<command>` invocation is a **clarification or scope amendment to the IN-FLIGHT run**, NOT a new task: append it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief and continue. Forbidden: solving it with tools directly (a pipeline bypass), answering conversationally without folding, spawning a sibling `/architect-team` invocation, or silently ignoring it. Full rule: `common-pipeline-conventions` `## In-flight clarification discipline (v2.5.0)`, `skills/common-pipeline-conventions/references/in-flight-clarification-discipline.md`.
