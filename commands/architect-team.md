---
description: Spec-to-production multi-agent coding pipeline. Takes EITHER a requirements folder (OpenSpec / Superpowers / plain markdown) OR a plain-language requirement typed directly — a sentence or paragraph describing what to build, fix, change, review, or improve — and drives it end-to-end to tested, integrated production code. Auto-commits and pushes on a clean Phase 8 pass and emits a clear /compact prompt to free context for the next run, unless invoked with --no-commit / --no-push / --no-compact.
argument-hint: "<requirements-folder | plain-language requirement> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first]"
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

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
   (The v1.3.0 sweep already removed merged-worktree branches, so filter to the
   unmerged strays.)
2. If the list is EMPTY → silent no-op; proceed to argument parsing.
3. If non-empty → present ONE `AskUserQuestion` with three options:
   - **merge-all-clean + prune** → for each branch with `cleanly_mergeable:
     true`, call `merge_branch_to_main_and_prune(branch, worktree_path)` via the
     polyglot Python; report any branch returning `conflict: true` (left
     untouched).
   - **prune-without-merge** → `cleanup_run_worktree(Path(worktree_path),
     remove_branch=True)` per branch (discard the work).
   - **leave** → no-op.
4. Only `architect-team/*` branches are ever considered — never the user's own
   branches, never this command's OWN run branch.

Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`
for the canonical rule.

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the requirement.**

Flags (each independent — `--no-commit --no-compact` is valid; natural-language phrasings count as the matching flag — opt-outs: "don't commit" / "no push" / "don't compact" / "leave it uncommitted"; opt-in: "propose first" / "review before implementing" / "show me the plan first" / "stop after the proposal" trigger `--proposal-first`):

- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false`. (Default `true`.)
- `--allow-push-to-default` → `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`.) When false, the pipeline does NOT commit + push unreviewed work straight onto `main` / `master` — it commits to an `architect-team/<change-name>` feature branch and recommends a PR. Pass the flag only when a direct default-branch push is genuinely wanted.
- `--proposal-first` → `PROPOSAL_FIRST = true`. (Default `false`.) The pipeline runs Phase −1 → 1 (intake + the validated OpenSpec proposal / design / specs / tasks package), then PAUSES for the user to review before Phase 2 implementation begins. Resume Phases 2 → 8 when the user replies "proceed" (or revises). Default `false` — the pipeline drives end-to-end without asking. See the `architect-team-pipeline` skill's `## Default mode of operation` section. **Domain gates** — the Phase −1D bulk-verify of low-confidence interaction intuitions, the `editability-completeness` `ambiguous` attribute escalations, and the `interaction-completeness` `ambiguous` element escalations — fire regardless of this flag, since they are user-input steps that ARE the deliverable (not process interruptions to it).
- `--bug-fix` → forces `kind: bug` at the Phase −2 triage step; skips the `bug-classifier` agent and routes the run directly to the `bug-fix-pipeline` skill. Natural-language equivalents recognized at parse time: *"this is a bug"* / *"just fix the bug"* / *"it's a hotfix"* / *"bugfix"*. Equivalent to invoking `/architect-team:bug-fix` directly.
- `--feature-only` → forces `kind: feature` at Phase −2; skips the classifier and proceeds to the existing Phase −1 → 8 flow (the full pipeline). Natural-language equivalents: *"this is a feature"* / *"build this as a feature"* / *"feature, not a bug"*. Use when you want feature-pipeline rigor on what the classifier might call a small bug.
- `--no-refine` → skip the upstream `proposal-refiner` skill (v0.9.33). Default `false` — when `$REQ_DIR` is plain-language prose AND the input is not already a refined-prompt markdown, the pipeline invokes `proposal-refiner` FIRST to conversationally clarify the prompt with codebase-map grounding before Phase −2 (Triage). Pass `--no-refine` to bypass when the prose is already detailed enough. Domain gate per v0.9.21 — the user-confirmation step IS the deliverable, NOT a process gate that v0.9.20's "default to action" rule covers.
- `--no-worktree` → `AUTO_WORKTREE = false`. (Default `true`.) Skip the auto-worktree creation step; run the pipeline in the current checkout (v1.1.0 behavior). Natural-language equivalents: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- `--no-auto-merge` → `AUTO_MERGE_MAIN = false`. (Default `true`.) When true (the default), a clean Phase 8 run merges its `architect-team/<change-name>` branch into `main`, pushes, deletes the branch (local + remote), and removes the worktree — only when it merges cleanly (conflicts skipped + reported, never forced; branch protection always wins). `--no-auto-merge` restores today's feature-branch + recommend-a-PR + persistence-warning behavior. Natural-language equivalents: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*. See `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`.
- `--phenotype <label>` → bind `$PHENOTYPE = <label>` and seed the run from that phenotype (a pre-made, generalized, deployable architecture under `phenotypes/` — blueprint + scaffold; see `skills/phenotypes`). Natural-language equivalents recognized at parse time: *"use the `<label>` phenotype"* / *"use phenotypes"* (when the domain is unambiguous). When set, the pipeline loads the phenotype, confirms its variation points + scaffold parameters with the user (a domain gate), emits the scaffold as the starting point, and customizes it through the normal phases. Absent → no phenotype is seeded, though the pipeline may still PROPOSE a matching one during reuse-first design (never silently).
- `--appearance <strict|propose|innovate>` → `APPEARANCE_MODE = <mode>`. (Default `strict`.) Governs unsolicited frontend-appearance changes per `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`: `strict` (the default) forbids appearance-affecting changes beyond the explicit mandate — improvement ideas are recorded to `.architect-team/appearance-proposals/<run-id>.json`, never implemented; `propose` surfaces the recorded proposals at a user approval gate (a domain gate per v0.9.21 — only approved proposals are implemented); `innovate` authorizes appearance improvements, each logged with status `implemented-innovate` + `DESIGN_MAP.md`-reconciled. Natural-language equivalents recognized at parse time — propose: *"propose appearance changes"* / *"suggest UI improvements first"* / *"ask before changing the look"*; innovate: *"innovate on the UI"* / *"free rein on the design"* / *"do whatever you want with the front end"* / *"make it look better however you want"*.
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `AUTO_WORKTREE = true`, `AUTO_MERGE_MAIN = true`, `APPEARANCE_MODE = strict` (drive end-to-end; no unsolicited appearance changes). The Phase −2 triage runs and routes based on the classifier's verdict — bug-shaped requirements automatically route to the bug-fix pipeline; feature-shaped requirements continue to the existing Phase −1 → 8 flow; mixed requirements spawn both in parallel.

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

| Form | What it is | Bind `$REQ_DIR` to |
|---|---|---|
| **Folder** | a filesystem path that resolves to an existing directory (holding OpenSpec artifacts, a Superpowers brief, or plain markdown) | the path |
| **Plain-language requirement** | prose — a phrase, sentence, or paragraph describing what to build, fix, change, review, or improve | the **entire remaining string, verbatim** |

To tell them apart: if what remains after stripping flags is a single token that resolves to an existing directory → **Folder**. Otherwise → **Plain-language requirement**. **When unsure, it is a plain-language requirement** — ad-hoc prose is the common case.

The pipeline's **Phase 0 normalizes a plain-language requirement into an OpenSpec change** — that branch exists precisely for this. A requirements folder is NOT required and never has been.

### Forbidden — the following are bugs, not correct behavior

- **Treating the first word of a plain-language requirement as a path.** `no`, `review`, `add`, `fix`, `lets` are not directories — the *whole string* is the requirement.
- **Refusing to run** — or telling the user the pipeline "needs a folder" / "only drives a requirements folder" / "I won't run against a non-existent folder" — when given prose. The pipeline accepts a plain-language requirement directly; running it is correct. Refusing a sentence is the bug this section exists to prevent.
- **Asking the user for a requirements folder.** The only thing you may ask for is the requirement itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty** — then ask: "What would you like the architect-team pipeline to build, fix, or change?"

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` — a folder path OR the verbatim plain-language requirement string — as the input to the `architect-team-pipeline` skill, and substitute it for every `$REQ_DIR` reference in the skill body. When the requirement is plain-language prose, the codebase the pipeline operates on is the current working directory (a git repo) unless the prose names another path. Do NOT re-prompt.

## Pre-pipeline refinement (v0.9.33) — runs BEFORE Phase −2 when input is plain-language prose

After binding `$REQ_DIR` (folder path OR plain-language requirement string), and BEFORE invoking the `architect-team-pipeline` skill, determine whether refinement applies:

- **Skip refinement** when ANY of these holds:
  - `$REQ_DIR` resolves to an existing directory on disk (OpenSpec / Superpowers / markdown brief — the refinement step's purpose is satisfied by the brief's existence).
  - `$REQ_DIR` resolves to a markdown file with `refined-by: proposal-refiner` frontmatter (the refiner already ran on this prompt previously).
  - The `--no-refine` flag was passed (explicit opt-out).
- **Run refinement** otherwise (plain-language prose, no prior refinement). Set `$REFINER_MODE = "pipeline"` and invoke the `proposal-refiner` skill from this plugin (use the Skill tool with `skill: proposal-refiner`). Pass `$REQ_DIR` (the verbatim prose) as the input. The skill runs phases R1 → R6 — codebase-map loading, multi-axis grading, conversational refinement with the user (5-iteration ceiling), and final markdown output at `<cwd>/.architect-team/refined-prompts/<slug>-<ts>.md`.

After `proposal-refiner` exits in pipeline mode, **rebind `$REQ_DIR` to the absolute path of the refined-prompt markdown file**. The architect-team-pipeline then operates on the refined brief — its Phase 0 normalization treats the markdown like any other plain-markdown source (`$REQ_DIR` resolves to a file, the pipeline reads it).

The refiner is a **DOMAIN gate** (per the v0.9.21 carve-out), not a process gate — the user-confirmation step IS the deliverable. The v0.9.20 "gates are opt-in" rule does NOT apply here because the user explicitly invoked `/architect-team` with prose, which IS the invocation channel; `--no-refine` is the documented opt-out.

## Auto-worktree creation (v1.2.0) — runs after refinement, before skill invocation

After binding `$REQ_DIR` and completing any refinement, AND BEFORE invoking the `architect-team-pipeline` skill, determine whether the auto-worktree step applies:

- **Skip the step** when ANY of these holds:
  - `--no-worktree` (or a natural-language opt-out — *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*) was passed.
  - The current branch already starts with `architect-team/` (re-entry case — `scripts.setup.worktree_lifecycle.current_worktree_is_run()` returns True). No nested worktrees; the existing run worktree IS the workspace.

- **Run the step** otherwise:
  1. Derive a `<slug>` from the refined-prompt slug (if present in the refined-prompt markdown's frontmatter), the OpenSpec change name (if `$REQ_DIR` resolves to a `openspec/changes/<change-name>/` folder), or a kebab-case derivation of the prompt's first 4-6 meaningful words.
  2. Invoke the helper via Bash — detect-once Python invocation (the v2.16.0 form): the interpreter is selected ONCE via `$(command -v python3 || command -v python)` and the snippet runs exactly once. `create_run_worktree` raises (a non-zero exit) on collision exhaustion, and the old `python3 X || python X` form would silently re-run the whole creation on that meaningful failure; detect-once invokes it exactly once. Per `common-pipeline-conventions` `## Cross-platform Python invocation`:
     ```bash
     $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
     ```
     The helper creates the worktree at `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` (the hidden per-project container, v3.6.0) on branch `architect-team/<slug>` (collision handling appends `-2`, `-3`, ... when either path or branch is taken). Capture the printed absolute path as `$WORKTREE_PATH`.
  3. `chdir` into `$WORKTREE_PATH`. Every subsequent step — including the Skill-tool invocation of `architect-team-pipeline` — runs with `$WORKTREE_PATH` as cwd. v1.1.0's `shared_state_dir()` resolution keeps the lock layer and MemPalace pointed at the MAIN worktree; `run_state_dir()` resolves per-worktree so reviews / teammates / handoffs / per-run OpenSpec live in the run worktree.
  4. Surface a one-line note to the user: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (parent dir not writable, base branch missing, slug exhausted — the helper raises `RuntimeError` with an actionable message), surface the error verbatim and STOP. Do NOT silently fall back to the current checkout — the user asked for a worktree (default), and failing without notice is the v0.9.20 anti-pattern this section's explicit error path exists to prevent. The user re-runs with `--no-worktree` if they want single-tree mode.

At Phase 8 success the pipeline now calls `finalize_run_worktree($WORKTREE_PATH)` (v3.6.0): it removes the worktree + branch if the branch is already merged into `origin/main`, otherwise it leaves the folder and prints the returned `warning` (which names the path + the manual cleanup command). Unmerged work is never auto-deleted.

Per `common-pipeline-conventions` `## Auto-worktree lifecycle` for the full rules including the path/branch convention, collision handling, the end-of-run merge check emitted at Phase 8 success, and the re-entry detection logic.

## Claude Design link detection

If the requirement carries a Claude Design offer — a `claude.ai/design/p/<id>` link and/or a `claude_design` MCP mention — the pipeline's Phase −1 intake detects it (via `scripts/claude_design/claude_design_import.py`) and routes it through the `claude-design-import` skill, which materializes the design project locally and hands it to the existing interactive-mockup oracle path. No special flag is needed. When the `claude_design` MCP is unavailable, `claude-design-import` instructs connecting it plus running `/design-login` and auto-falls-back to the local/zip design-input path so the run never dead-ends.

## Invoke the pipeline

Invoke the `architect-team-pipeline` skill from this plugin (use the Skill tool with `skill: architect-team-pipeline`) and follow its pipeline exactly against the requirement above (a folder OR a plain-language requirement OR the refined-prompt markdown that the upstream `proposal-refiner` step produced — all three are valid). The skill begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report).

**Pass the `AUTO_COMMIT`, `AUTO_PUSH`, and `ALLOW_PUSH_TO_DEFAULT` flags to the skill.** The skill's Phase 8 reads these to decide whether to auto-commit, push, and whether it may push straight to a default branch.

## Project email notifications (opt-in)

If the target project's repository root contains a `.architect-team-notify.json` config file, the pipeline emits **opt-in, per-project email notifications** as a run progresses — ten event types (`run_start`, `phase_start`, `phase_complete`, `waiting_on_agents`, `agents_complete`, `issue_discovered`, `git_commit`, `deploy`, `run_complete`, `heartbeat`) delivered via Gmail or SendGrid to a configured recipient list, each recipient choosing which events they receive. The v3.34.0 emails are **informative, not just status**: every event carries what is about to start / where the run stands / what was completed (`--details` / `--progress` / `--next-step`), the `run_start` kickoff email embeds the architecture + solution plan itself (proposal / design / tasks in ONE email), `waiting_on_agents` / `agents_complete` bracket every agent dispatch so recipients know when the run is waiting and when the wait ended, and `run_complete` is the final what-shipped email. Notifications are strictly **best-effort**: the notifier always exits 0, and a notification failure never blocks, fails, or alters a pipeline run. With no `.architect-team-notify.json` present the notifier is a silent no-op and the pipeline behaves exactly as before. See the "Project email notifications" section of `README.md` for the config schema and provider setup; the wiring lives in the `architect-team-pipeline` skill's `## Notifications` section.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase 8, after the final report emits "Spec `<change-name>` has been implemented." and the archive path:

0. **Run the completion audit FIRST:** `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` from the repo root. The `$(command -v python3 || command -v python)` substitution detects whichever Python interpreter is on PATH (Unix: `python3`; default Windows python.org: `python`) and invokes the script **exactly once** — the v2.16.0 fix replacing the prior `python3 X --check || python X --check` polyglot which double-executed the script (and double-printed the BLOCKED message) when the script returned a meaningful non-zero exit code. If the final exit is non-zero, the run is incomplete — do NOT commit; resolve the reported violations or escalate. Only an exit-0 audit proceeds.
1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add <files-the-pipeline-touched>` — stage ONLY the files the pipeline created or modified (read from the coverage-map's `implementing_commits`'s working set + `openspec/changes/<change-name>/` + any updated CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP files). Do NOT use `git add -A` — that risks sweeping in unrelated files.
2b. **Default-branch guard:** if the current branch is `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/<change-name>` before committing — the pipeline does not commit unreviewed work straight onto a default branch. Otherwise commit on the current branch.
3. `git -C <repo-root> commit -m "$(cat <<'EOF'
<change-name>: <one-line summary from Phase 8 final-statement>

- Requirements implemented: <REQ-001, REQ-002, ...> (N total)
- Tests added: <unit / integration / e2e counts; all passing>
- Coverage map: fully green
- Phases −1 → 8 complete; openspec archive landed at <archive-path>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"` — use the repo's local git config (no `-c user.name=` override here; that override is specific to repos with mis-configured local config).
4. `git -C <repo-root> push -u origin <branch>` — push the branch the commit landed on (the current branch, or the `architect-team/<change-name>` branch from step 2b).
5. Report the commit SHA and push range in the final user-facing report. If the commit went to an `architect-team/<change-name>` feature branch, the report MUST say so and recommend opening a PR.

If `AUTO_COMMIT = false`: skip steps 2-5 entirely; mention in the final report that changes were left uncommitted at the user's request.

If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-3 only; mention in the final report that the commit was made locally but not pushed at the user's request.

### Auto-merge to main (v3.7.0)

After the completion audit passes + the commit lands on `architect-team/<change-name>`, and when `AUTO_MERGE_MAIN = true` (the default):

6. Probe clean-mergeability and, if clean, merge + prune via the polyglot Python (the orchestrator runs from / chdir's to the MAIN checkout first, since the merge runs `git checkout main` there):
   ```bash
   python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1 || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '$WORKTREE_PATH', push=<AUTO_PUSH>)))" 2>&1
   ```
   - On `reason: "merged-and-pruned"` → report: merged into `main`, pushed, branch deleted (local + remote), worktree removed.
   - On `conflict: true` (`reason: "conflict"` / `"conflict-on-merge"`) → the merge changed nothing; fall back to today's behavior: keep the `architect-team/<change-name>` branch pushed, recommend a PR, emit the v3.6.0 `finalize_run_worktree` persistence warning.
   - On `reason: "push-rejected"` (branch protection / non-fast-forward) → STOP, report the rejection, leave the branch + worktree recoverable. NEVER force.

When `AUTO_MERGE_MAIN = false` (`--no-auto-merge`): skip step 6 entirely; keep today's feature-branch + recommend-a-PR + persistence-warning behavior verbatim (the v3.6.0 `finalize_run_worktree` warning).

Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)` for the canonical flow + safety rules.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase 8 completed cleanly (with or without commit / push depending on the other flags), emit a clearly-marked final block AFTER the final report, as the very last thing the user sees in this turn:

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

The model cannot programmatically execute `/compact` — slash commands are user-typed REPL events, not tools the model can invoke. This block is the maximum-effort prompt: it ends your final reply, places the literal command on its own line for easy copy or one-keystroke confirmation, and the user runs it.

If `AUTO_COMPACT_PROMPT = false`: skip the block entirely.

## Safety rules (non-negotiable)

- NEVER force-push.
- NEVER skip git hooks (`--no-verify`). If a pre-commit hook fails, surface the failure, fix the underlying issue, and re-commit as a NEW commit.
- NEVER amend the previous commit; always create a new commit.
- If `git push` fails (non-fast-forward / network / auth), surface the error clearly and stop — do NOT escalate to force-push or other destructive operations.
- If the working tree had unstaged changes BEFORE the pipeline started, treat them as the user's in-progress work — do NOT stage them in the pipeline's commit. Surface their presence in the final report.
- If staged-but-not-yet-committed work existed BEFORE the pipeline started, surface that too and do NOT lump it into the pipeline's commit.
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools from inside the pipeline.** The pipeline is synchronous and runs in one continuous flow. Subagent dispatches block your turn at the harness level — no manual timer is needed. Do NOT tell the user "I scheduled a wakeup for N minutes" or "I'll come back to this in ~X minutes" — that is a pipeline-discipline failure. If you genuinely need to poll an external resource (dev server ready, deploy live), use a tight bounded in-turn poll, not a scheduled wakeup that ends the turn.

## In-flight clarification discipline (v2.5.0)

If you receive a user message AFTER the pipeline has begun executing (Phase −2 / B−1 / M0 onward) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, treat the message as a **clarification or scope amendment to the IN-FLIGHT run**, NOT as a new standalone task. Append the message verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief (re-run Phase 0/1 if scope materially shifted; otherwise fold into the next phase's inputs), and continue the pipeline. Forbidden: solving the clarification with tools directly (bypasses the pipeline), answering conversationally without folding, spawning a sibling `/architect-team` invocation, or silently ignoring. The canonical rules — 3 detection signals + 4 forbidden anti-patterns + cancellation channel — live in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.
