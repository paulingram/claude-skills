---
description: A persona-driven UX test orchestrator. Takes EITHER a requirements folder (containing a UX brief — persona, objectives, target site, credentials env-var reference) OR a plain-language requirement typed directly as prose. Maps the target site (fresh or freshness-checked via the existing intake-and-mapping skill), drafts a literal Playwright flow matching the user's request, dispatches 3 flow-explorer agents to propose 10-15 additional adjacent flows each, distills to a unique set, authors one .spec.ts per flow, dispatches 3 flow-executor agents to run every flow in parallel against the live target, resolves verdict disagreements via loop-until-converged convergence (no fixed cycle cap), documents bugs, and auto-routes them through the existing /architect-team:bug-fix pipeline for resolution. Auto-commits and pushes on a clean Phase U9 pass; emits a /compact prompt to free context.
argument-hint: "<requirements-folder | UX brief prose> [--site URL | --dev] [--credentials ENV_VAR_NAME] [--persona description] [--objectives text] [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first]"
---

# UX-Test-Builder Orchestration

You are starting the architect-team UX test builder — a persona-driven Playwright flow discovery + execution + bug-routing capability.

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

Flags (each independent):

- `--site <URL>` → set `TARGET_KIND = url`, `TARGET_URL = <URL>`. The site the persona will be tested against.
- `--dev` → set `TARGET_KIND = dev`. The orchestrator resolves the target from the project's `design.md` `## Dev Environment` section at Phase U0.
- `--credentials <ENV_VAR_NAME>` → the env-var NAME holding the auth secret. **NEVER the secret itself.** Example: `--credentials UX_TEST_PASSWORD`.
- `--persona <description>` → the persona description. May also be read from the prose requirement.
- `--objectives <text>` → what the persona is trying to do. May also be read from the prose requirement.
- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false`.
- `--allow-push-to-default` → `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`.)
- `--proposal-first` → `PROPOSAL_FIRST = true`. Runs Phase U0 → U4 (intake + site mapping + literal flow + expansion + distillation), then PAUSES for user review before authoring + executing the Playwright flows at U5/U6. Domain gates (U0 vague-input, U7 consensus-cannot-converge, `--environment production` escalation) fire regardless.
- `--environment production` → `TARGET_ENVIRONMENT = production`. Forces U6 execution to escalate before running against production (production testing is a user decision, never automatic).
- `--no-refine` → skip the upstream `proposal-refiner` skill (v0.9.33). Default `false` — when `$REQ_DIR` is plain-language prose (persona description + objectives) AND not already a refined-prompt markdown, the pipeline invokes `proposal-refiner` FIRST to clarify the persona's role, the objectives, and the target with codebase / site-map grounding before Phase U0. Pass `--no-refine` when the prose already specifies persona + objectives + target + credentials env-var explicitly. Domain gate per v0.9.21 — the clarifying conversation IS the deliverable.
- `--no-worktree` → `AUTO_WORKTREE = false`. (Default `true`.) Skip the auto-worktree creation step; run the UX-test pipeline in the current checkout (v1.1.0 behavior). Natural-language equivalents: *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*.
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `TARGET_ENVIRONMENT = dev`, `AUTO_WORKTREE = true` (default).

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

| Form | What it is | Bind `$REQ_DIR` to |
|---|---|---|
| **Folder** | a filesystem path holding a UX brief (persona description, objectives, target reference, credentials reference) | the path |
| **Plain-language requirement** | prose — e.g., *"a secretary uploading and checking files, against https://app.example.com, credentials in $UX_TEST_PASSWORD"* | the **entire remaining string, verbatim** |

To tell them apart: if what remains after stripping flags is a single token that resolves to an existing directory → **Folder**. Otherwise → **Plain-language requirement**. **When unsure, it is a plain-language requirement** — prose is the common case for UX briefs.

The pipeline's **Phase U0 normalizes a plain-language requirement** into a structured intake record (parsing the persona + objectives + target + credentials reference from the prose, when the corresponding flags aren't passed). A requirements folder is NOT required.

### Forbidden — the following are bugs, not correct behavior

These rules mirror `/architect-team` exactly (the v0.9.17 same-input-forms rules):

- **Treating the first word of a plain-language requirement as a path.** `a`, `the`, `as`, `for`, `secretary`, `uploading` are not directories — the *whole string* is the requirement.
- **Refusing to run** — or telling the user the pipeline "needs a folder" / "only drives a requirements folder" / "I won't run against a non-existent folder" — when given prose. The UX test builder accepts a plain-language requirement directly; running it is correct.
- **Asking the user for a requirements folder.** The only thing you may ask for is the UX brief itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty** AND the `--persona` / `--objectives` flags are also absent — then ask: *"What persona, objectives, target site, and credentials env-var should the UX test builder use?"*

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` — a folder path OR the verbatim plain-language requirement string — as the input to the `ux-test-builder` skill, and substitute it for every `$REQ_DIR` reference in the skill body. When the requirement is plain-language prose, the workspace codebase (the cwd, a git repo) provides the maps for Phase U1.

## Pre-pipeline refinement (v0.9.33) — runs BEFORE Phase U0 when input is plain-language prose

After binding `$REQ_DIR` and BEFORE invoking the `ux-test-builder` skill, determine whether refinement applies:

- **Skip refinement** when ANY of these holds:
  - `$REQ_DIR` resolves to an existing directory on disk.
  - `$REQ_DIR` resolves to a markdown file with `refined-by: proposal-refiner` frontmatter.
  - The `--no-refine` flag was passed.
- **Run refinement** otherwise. Set `$REFINER_MODE = "pipeline"` and invoke the `proposal-refiner` skill from this plugin (use the Skill tool with `skill: proposal-refiner`) passing `$REQ_DIR` (the verbatim UX-brief prose) as the input. The refiner's clarifying questions are particularly valuable for UX briefs — vague persona descriptions (*"a user uploading files"*) get sharpened (*"a secretary uploading invoices via the admin dashboard"*), implicit objectives become explicit, the credentials env-var NAME is confirmed (never the secret itself), and the target environment (URL vs. `--dev`) is settled before site-mapping at U1.

After `proposal-refiner` exits in pipeline mode, **rebind `$REQ_DIR` to the absolute path of the refined-prompt markdown file**. The ux-test-builder's Phase U0 intake then operates on the refined brief — the `--persona` / `--objectives` / `--site` / `--credentials` derivation reads from the refined brief's structured sections.

The refiner is a DOMAIN gate per v0.9.21 — the user-confirmation step IS the deliverable. The credentials-discipline (env-var NAME only, never raw secrets) is enforced in BOTH the refiner and the ux-test-builder — a refined brief that contains a raw secret in any section is rejected at U0 with the same discipline as the bare command rejection.

## Auto-worktree creation (v1.2.0) — runs after refinement, before skill invocation

After binding `$REQ_DIR` and completing any refinement, AND BEFORE invoking the `ux-test-builder` skill, determine whether the auto-worktree step applies:

- **Skip the step** when ANY of these holds:
  - `--no-worktree` (or a natural-language opt-out — *"no worktree"* / *"don't create a worktree"* / *"single tree"* / *"in place"* / *"in current tree"*) was passed.
  - The current branch already starts with `architect-team/` (re-entry case — `scripts.setup.worktree_lifecycle.current_worktree_is_run()` returns True). No nested worktrees; the existing run worktree IS the workspace.

- **Run the step** otherwise:
  1. Derive a `<slug>` from the refined-prompt slug (if present in the refined-prompt markdown's frontmatter), the persona-slug used downstream by `ux-test-builder`, or a kebab-case derivation of the persona description's first 4-6 meaningful words.
  2. Invoke the helper via Bash — detect-once Python invocation (the v2.16.0 form): the interpreter is selected ONCE via `$(command -v python3 || command -v python)` and the snippet runs exactly once. `create_run_worktree` raises (a non-zero exit) on collision exhaustion, and the old `python3 X || python X` form would silently re-run the whole creation on that meaningful failure; detect-once invokes it exactly once. Per `common-pipeline-conventions` `## Cross-platform Python invocation`:
     ```bash
     $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
     ```
     The helper creates the worktree at `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` (the hidden per-project container, v3.6.0) on branch `architect-team/<slug>` (collision handling appends `-2`, `-3`, ... when either path or branch is taken). Capture the printed absolute path as `$WORKTREE_PATH`.
  3. `chdir` into `$WORKTREE_PATH`. Every subsequent step — including the Skill-tool invocation of `ux-test-builder` — runs with `$WORKTREE_PATH` as cwd. v1.1.0's `shared_state_dir()` resolution keeps the lock layer and MemPalace pointed at the MAIN worktree; `run_state_dir()` resolves per-worktree so the UX-test artifacts / reviews / handoffs live in the run worktree.
  4. Surface a one-line note to the user: *"Auto-worktree: created `<WORKTREE_PATH>` on branch `architect-team/<slug>`. Pass `--no-worktree` next time to skip."*

On creation failure (parent dir not writable, base branch missing, slug exhausted — the helper raises `RuntimeError` with an actionable message), surface the error verbatim and STOP. Do NOT silently fall back to the current checkout — the user asked for a worktree (default), and failing without notice is the v0.9.20 anti-pattern this explicit error path exists to prevent. The user re-runs with `--no-worktree` if they want single-tree mode.

At Phase U9 success the pipeline calls `finalize_run_worktree($WORKTREE_PATH)` (v3.6.0): it removes the worktree + branch if the branch is already merged into `origin/main`, otherwise it leaves the folder and prints the returned `warning` (which names the path + the manual cleanup command). Unmerged work is never auto-deleted.

Per `common-pipeline-conventions` `## Auto-worktree lifecycle` for the full rules including the path/branch convention, collision handling, the end-of-run merge check emitted at Phase U9 success, and the re-entry detection logic.

## Claude Design link detection

If the UX brief references a Claude Design link (`claude.ai/design/p/<id>`) or the `claude_design` MCP, the pipeline routes it through the `claude-design-import` skill to materialize the design project locally, so the persona's flows can be authored against the intended screens (per `scripts/claude_design/claude_design_import.py`). When the MCP is unavailable it instructs connecting it plus running `/design-login` and auto-falls-back to the local/zip design-input path.

## Invoke the pipeline

Invoke the `ux-test-builder` skill from this plugin (use the Skill tool with `skill: ux-test-builder`) and follow its pipeline exactly against the requirement above (a folder OR a UX brief in prose OR the refined-prompt markdown that the upstream `proposal-refiner` step produced). The skill begins at Phase U0 (Intake) and proceeds through Phase U9 (Final Report).

**Pass the `AUTO_COMMIT`, `AUTO_PUSH`, `AUTO_COMPACT_PROMPT`, `ALLOW_PUSH_TO_DEFAULT`, `PROPOSAL_FIRST`, `TARGET_KIND`, `TARGET_URL`, `TARGET_ENVIRONMENT`, and the credentials env-var NAME to the skill.** The skill's Phase U0 + Phase U6 read these to compose the intake record + execute against the right target.

## Project email notifications (opt-in)

If the target project's repository root contains a `.architect-team-notify.json` config file, the UX-test pipeline emits **opt-in, per-project email notifications** as the run progresses (v3.34.0 — parity with `/architect-team`): informative `phase_start` / `phase_complete` at every U-phase boundary, a `run_start` kickoff email at U4 embedding the distilled flow catalog (the run's test plan) in one email, `waiting_on_agents` / `agents_complete` bracketing the U3 explorer and U6 executor dispatches, `issue_discovered` per bug routed at U8, `git_commit` after the U9 report commit, and a final `run_complete` summary. Strictly best-effort — the notifier always exits 0 and never blocks, fails, or alters the run; with no `.architect-team-notify.json` present it is a silent no-op. Wiring lives in the `ux-test-builder` skill's `## Notifications` section; config schema in `README.md`.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase U9, after the final report emits **"UX test plan for persona `<persona-slug>` against `<target>` executed. ..."** and the bug-fix-pipeline dispatch references:

0. **Run the completion audit FIRST:** `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check`. The `$(command -v python3 || command -v python)` substitution detects whichever Python interpreter is on PATH and invokes the script **exactly once** — the v2.16.0 fix replacing the prior `python3 X || python X` polyglot which double-executed the script when it returned a meaningful non-zero exit code. If the final exit is non-zero, the run is incomplete — do NOT commit; resolve violations or escalate.
1. `git -C <repo-root> status --porcelain` — enumerate what changed.
2. `git -C <repo-root> add <files-the-pipeline-touched>` — stage ONLY the pipeline-touched files (the `.architect-team/ux-tests/<persona-slug>/` artifacts + any SR files written; do NOT include the bug-fix-pipeline's own work — those are queued in separate bug-fix runs).
2b. **Default-branch guard:** if the current branch is `main` / `master` AND `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/ux-test-<persona-slug>` before committing.
3. `git -C <repo-root> commit -m "<commit message>"` using the repo's local git config (no `-c user.name=` override).
4. `git -C <repo-root> push -u origin <branch>` — push the branch the commit landed on.
5. Report the commit SHA and push range. If the commit landed on `architect-team/ux-test-<persona-slug>`, the report MUST say so and recommend opening a PR.

If `AUTO_COMMIT = false`: skip steps 2-5; mention in the final report that changes were left uncommitted.

If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-3 only; mention in the final report that the commit was made locally but not pushed.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase U9 completed cleanly, emit the standard `/compact` prompt block as the very last thing the user sees:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  UX test complete. Context is now full of execution traces.    ║
║  Run /compact NOW to free space for the next architect-team    ║
║  invocation. Type exactly:                                     ║
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
- Pre-existing unstaged or staged changes are the user's in-progress work — do NOT include them; surface them in the final report.
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools.** The pipeline is synchronous; subagent dispatches block your turn. Do NOT tell the user "I scheduled a wakeup for N minutes."

## Production-environment rule (the one exception to live-by-default)

**`TARGET_ENVIRONMENT` defaults to `dev`.** Phase U6 runs against the dev environment (per the project's `design.md` `## Dev Environment` section) when `--dev` was passed, or against the URL when `--site` was passed.

When `--environment production` is set (or the user's prose names production as the target), Phase U6 does NOT auto-execute. The orchestrator escalates: *"This run is targeting production. Production UX testing affects real users (auth attempts, possible side effects, possible cost). Please confirm: (a) execute against production now, (b) re-run against staging instead, (c) hold for manual review."* Domain gate; pause for the user.

## Credential discipline (non-negotiable)

The `--credentials <ENV_VAR_NAME>` flag carries the env-var NAME ONLY. The secret VALUE is read from `process.env[<name>]` at Playwright runtime (by the `flow-executor` agents at U6). It is NEVER persisted to:
- the intake JSON,
- the literal flow's metadata,
- the explorers' proposals,
- the distilled-flow set,
- the Playwright `.spec.ts` files (they reference `process.env[<name>]`, not the literal value),
- the executors' verdict files,
- the captured traces,
- the captured screenshots (be careful with screenshots that may include password fields with autocomplete — use `--mask-credentials` Playwright option if available),
- the final U9 report.

If the user's prose tries to include the raw secret inline (e.g., *"login with paul@example.com / hunter2"*), the orchestrator REJECTS it: *"For credential safety, the raw password / token cannot be passed inline. Set it in an env var and pass `--credentials <ENV_VAR_NAME>` instead. The orchestrator will read the secret at Playwright runtime; it will never be persisted in any artifact."* The run does not proceed until the user complies.

## In-flight clarification discipline (v2.5.0)

If you receive a user message AFTER the pipeline has begun executing (Phase U0 onward) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, treat the message as a **clarification or scope amendment to the IN-FLIGHT run**, NOT as a new standalone task. Append the message verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief (re-run Phase U0 intake if the persona / objectives / target materially shifted; otherwise fold into the next phase's inputs), and continue the pipeline. Forbidden: solving the clarification with tools directly (bypasses the pipeline), answering conversationally without folding, spawning a sibling `/architect-team` invocation, or silently ignoring. The canonical rules — 3 detection signals + 4 forbidden anti-patterns + cancellation channel — live in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.
