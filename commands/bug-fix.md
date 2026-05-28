---
description: Faster bug-focused variant of /architect-team. Takes EITHER a requirements folder (with a bug report) OR a plain-language bug description typed directly — a sentence describing the symptom, what was expected, what actually happened — and drives it through a replicate → reproduce-test → propose → fix → QA-replay loop against the live dev environment. Replication-first; the artifact that reproduces the bug becomes the regression test; the architect rejects symptom-patches and demands generalized fixes (unless the user explicitly authorized a hotfix); the QA-replayer re-runs the artifacts against the deployed dev fix and only `bug-resolved end-to-end` closes the loop. Auto-commits and pushes on a clean Phase B8 pass and emits a /compact prompt to free context. Accepts the SAME two input forms as /architect-team — folder or plain-language prose, both first-class.
argument-hint: "<requirements-folder | bug description> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first] [--environment production] [--force-bug] [--no-deploy]"
---

# Bug-Fix Pipeline Orchestration

You are starting the architect-team bug-fix pipeline — a faster, bug-focused variant of `/architect-team`.

**Raw arguments:** $ARGUMENTS

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the requirement (the bug).**

Flags (each independent — `--no-commit --no-compact` is valid; natural-language phrasings count as the matching flag):

- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false`. (Default `true`.)
- `--allow-push-to-default` → `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`.) When false, the pipeline does NOT commit + push unreviewed work straight onto `main` / `master` — it commits to an `architect-team/<bug-slug>` feature branch and recommends a PR.
- `--proposal-first` → `PROPOSAL_FIRST = true`. (Default `false`.) Runs Phases B−1 → B3 (intake + replication + reproduction-test + the OpenSpec proposal package), then PAUSES for user review before Phase B4. **Domain gates** — the Phase B1 ambiguity-escalation question, the Phase B4 audit `needs-clarification`, the Phase B5 production-deploy escalation — fire regardless of this flag.
- `--environment production` → `TARGET_ENVIRONMENT = production`. Forces Phase B5 to escalate before deploying (production deploys are user decisions, never automatic).
- `--force-bug` → tells the Phase B0 classifier-warning to skip ("this looks like a feature, run /architect-team instead") and proceed anyway. Use when you know it IS a bug despite ambiguous wording.
- `--no-deploy` → skip Phase B5's auto-deploy step; QA replay (B6) runs against whatever is already deployed. Use when the dev environment is hand-managed.
- `--no-refine` → skip the upstream `proposal-refiner` skill (v0.9.33). Default `false` — when `$REQ_DIR` is plain-language prose AND the input is not already a refined-prompt markdown, the pipeline invokes `proposal-refiner` FIRST to conversationally clarify the bug description with codebase-map grounding (which dashboard? which row's delete button? which user role?) before Phase B−2 / B−1. Pass `--no-refine` when the bug description is already specific. Domain gate per v0.9.21 — the clarifying conversation IS the deliverable.
- `--no-worktree` → `AUTO_WORKTREE = false`. (Default `true`.) Skip the auto-worktree creation step; run the bug-fix pipeline in the current checkout (v1.1.0 behavior). Natural-language equivalents: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `TARGET_ENVIRONMENT = dev`, `AUTO_WORKTREE = true` (default — live dev environment).

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

| Form | What it is | Bind `$REQ_DIR` to |
|---|---|---|
| **Folder** | a filesystem path that resolves to an existing directory (holding a bug report, screenshots, prior diagnostic notes, or an OpenSpec brief) | the path |
| **Plain-language requirement** | prose — a phrase, sentence, or paragraph describing the bug (the symptom, what the user expected, what actually happened) | the **entire remaining string, verbatim** |

To tell them apart: if what remains after stripping flags is a single token that resolves to an existing directory → **Folder**. Otherwise → **Plain-language requirement**. **When unsure, it is a plain-language requirement** — a bug description in prose is the common case.

The pipeline's **Phase B0 normalizes a plain-language requirement into an OpenSpec change** — that branch exists precisely for this. A requirements folder is NOT required and never has been.

### Forbidden — the following are bugs, not correct behavior

These rules mirror `/architect-team` exactly (the v0.9.17 same-input-forms rules):

- **Treating the first word of a plain-language requirement as a path.** `no`, `the`, `fix`, `delete`, `clicking` are not directories — the *whole string* is the requirement.
- **Refusing to run** — or telling the user the pipeline "needs a folder" / "only drives a requirements folder" / "I won't run against a non-existent folder" — when given prose. The pipeline accepts a plain-language requirement directly; running it is correct.
- **Asking the user for a requirements folder.** The only thing you may ask for is the bug description itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty** — then ask: *"What bug should the bug-fix pipeline replicate and resolve?"*

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` — a folder path OR the verbatim plain-language requirement string — as the input to the `bug-fix-pipeline` skill, and substitute it for every `$REQ_DIR` reference in the skill body. When the requirement is plain-language prose, the codebase the bug applies to is the current working directory (a git repo) unless the prose names another path. Do NOT re-prompt.

## Pre-pipeline refinement (v0.9.33) — runs BEFORE Phase B−1 when input is plain-language prose

After binding `$REQ_DIR` and BEFORE invoking the `bug-fix-pipeline` skill, determine whether refinement applies:

- **Skip refinement** when ANY of these holds:
  - `$REQ_DIR` resolves to an existing directory on disk.
  - `$REQ_DIR` resolves to a markdown file with `refined-by: proposal-refiner` frontmatter.
  - The `--no-refine` flag was passed.
- **Run refinement** otherwise. Set `$REFINER_MODE = "pipeline"` and invoke the `proposal-refiner` skill from this plugin (use the Skill tool with `skill: proposal-refiner`) passing `$REQ_DIR` (the verbatim bug-description prose) as the input. The skill runs phases R1 → R6 — codebase-map loading (especially `INTERACTION_INTUITION_MAP.md` for frontend bugs, where the wired-vs-stub status of every interactive element is already cataloged), multi-axis grading, conversational refinement (5-iteration ceiling — *"the prompt says 'the delete button doesn't work' but ROUTE_MAP has 7 delete buttons across 4 routes; which one?"*), and final markdown output.

After `proposal-refiner` exits in pipeline mode, **rebind `$REQ_DIR` to the absolute path of the refined-prompt markdown file**. The bug-fix-pipeline's Phase B−1 / B0 intake then operates on the refined brief.

The refiner is a DOMAIN gate per v0.9.21 — the user-confirmation step IS the deliverable. The bug-fix-pipeline's existing Phase B1 ambiguity-escalation question (the canonical *"how did you experience the bug?"* prompt) still fires when needed; the refiner reduces — but does not eliminate — those mid-pipeline escalations by clarifying upstream.

## Auto-worktree creation (v1.2.0) — runs after refinement, before skill invocation

After binding `$REQ_DIR` and completing any refinement, AND BEFORE invoking the `bug-fix-pipeline` skill, determine whether the auto-worktree step applies:

- **Skip the step** when ANY of these holds:
  - `--no-worktree` (or a natural-language opt-out — *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*) was passed.
  - The current branch already starts with `architect-team/` (re-entry case — `scripts.setup.worktree_lifecycle.current_worktree_is_run()` returns True). No nested worktrees; the existing run worktree IS the workspace.

- **Run the step** otherwise:
  1. Derive a `<slug>` from the refined-prompt slug (if present in the refined-prompt markdown's frontmatter), the bug-slug used downstream by `bug-fix-pipeline`, or a kebab-case derivation of the bug description's first 4-6 meaningful words.
  2. Invoke the helper via Bash — polyglot Python invocation per `common-pipeline-conventions` `## Cross-platform Python invocation`:
     ```bash
     python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))" \
       || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
     ```
     The helper creates the worktree at `<parent-of-repo>/<repo-name>-<slug>/` on branch `architect-team/<slug>` (collision handling appends `-2`, `-3`, ... when either path or branch is taken). Capture the printed absolute path as `$WORKTREE_PATH`.
  3. `chdir` into `$WORKTREE_PATH`. Every subsequent step — including the Skill-tool invocation of `bug-fix-pipeline` — runs with `$WORKTREE_PATH` as cwd. v1.1.0's `shared_state_dir()` resolution keeps the lock layer and MemPalace pointed at the MAIN worktree; `run_state_dir()` resolves per-worktree so bug-fix verdict files / reviews / teammates / handoffs live in the run worktree.
  4. Surface a one-line note to the user: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (parent dir not writable, base branch missing, slug exhausted — the helper raises `RuntimeError` with an actionable message), surface the error verbatim and STOP. Do NOT silently fall back to the current checkout. The user re-runs with `--no-worktree` if they want single-tree mode.

Per `common-pipeline-conventions` `## Auto-worktree lifecycle` for the full rules including the path/branch convention, collision handling, the cleanup recommendation emitted at Phase B8 success, and the re-entry detection logic.

## Invoke the pipeline

Invoke the `bug-fix-pipeline` skill from this plugin (use the Skill tool with `skill: bug-fix-pipeline`) and follow its pipeline exactly against the requirement above (a folder OR the refined-prompt markdown that the upstream `proposal-refiner` step produced). The skill begins at Phase B−1 (Intake & Mapping) and proceeds through Phase B8 (Commit + Push).

**Pass the `AUTO_COMMIT`, `AUTO_PUSH`, `AUTO_COMPACT_PROMPT`, `ALLOW_PUSH_TO_DEFAULT`, `PROPOSAL_FIRST`, `TARGET_ENVIRONMENT`, `--no-deploy`, and `--force-bug` flag values to the skill.** The skill's Phase B5 reads `TARGET_ENVIRONMENT` to decide deploy behavior; Phase B0 reads `--force-bug` to skip the classifier warning; Phase B5 reads `--no-deploy` to skip the auto-deploy step; Phase B8 reads the rest for commit / push behavior.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase B8, after the final report emits **"Bug `<bug-slug>` has been resolved."** and the archive path:

0. **Run the completion audit FIRST:** `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check || python "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` from the repo root. The `|| python ...` fallback handles default Windows python.org installs where only `python` is on PATH (`python3` triggers the Microsoft Store shim there); on Unix the first form succeeds and the fallback never fires. If the final exit is non-zero, the run is incomplete — do NOT commit. Resolve violations or escalate.
1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add <files-the-pipeline-touched>` — stage ONLY the files the pipeline created or modified (the openspec change folder, the reproduction artifacts, the fix's source-code changes, any updated maps). Do NOT use `git add -A`.
2b. **Default-branch guard:** if the current branch is `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/<bug-slug>` before committing.
3. `git -C <repo-root> commit -m "<commit message per the bug-fix-pipeline skill's Phase B8 template>"` — using the repo's local git config.
4. `git -C <repo-root> push -u origin <branch>` — push the branch the commit landed on.
5. Report the commit SHA and push range in the final user-facing report. If the commit landed on `architect-team/<bug-slug>`, the report MUST say so and recommend opening a PR.

If `AUTO_COMMIT = false`: skip steps 2-5; mention in the report that changes were left uncommitted.

If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-3 only; mention in the report that the commit was made locally but not pushed.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase B8 completed cleanly, emit the standard `/compact` prompt block as the very last thing the user sees:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Bug-fix complete. Context is now full of build state.         ║
║  Run /compact NOW to free space for the next bug-fix or        ║
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
- Pre-existing unstaged or staged changes are the user's in-progress work — do NOT include them in the pipeline's commit; surface them in the final report.
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools from inside the pipeline.** The pipeline is synchronous; subagent dispatches block your turn. Do NOT tell the user "I scheduled a wakeup for N minutes." For external polling (dev server health after deploy), use a tight bounded in-turn `until` loop.

## Production-environment rule (the one exception to live-by-default)

**`TARGET_ENVIRONMENT` defaults to `dev`.** Phase B5 deploys to the dev environment (per the target project's `design.md` `## Dev Environment` section) and Phase B6 tests against the deployed dev fix. This is the default and the path the pipeline is optimized for.

When `--environment production` is set (or the user's prose names production as the target), Phase B5 does NOT auto-deploy. The orchestrator escalates a structured question to the user — "production deploys are your decision; (a) deploy to production now, (b) deploy to staging first, (c) hold for manual review" — and waits for an answer. This is a domain gate; it fires regardless of `--proposal-first`.
