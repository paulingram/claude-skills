---
description: Build/refresh a frontend codebase's persona-grouped Playwright suite (P0-P9) -- inventory specs, refresh the intuition map, author missing flows, register debug-flows from resolved bugs, classify tests dev or prod (default-deny), write suite-manifest.json. Commits on a P9 pass.
argument-hint: "[<frontend-codebase-path> | <target description>] [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first] [--no-worktree]"
---

# /architect-team:playwright-suite

Build the Playwright suite for a frontend codebase — the durable, persona-grouped
one, with a committed registry of which tests exist, which intuition-map elements
each covers, and which of them may ever run against production.

**Raw arguments:** $ARGUMENTS

## Dispatch mode banner — runs first

As the very first user-visible action, print the dispatch-mode banner so the user
knows whether this run dispatches via Agent Teams or the subagents fallback. The
interpreter is selected ONCE via `$(command -v python3 || command -v python)`
(the v2.16.0 detect-once form). Informational, never a gate — a subprocess
failure surfaces one line and the run continues.

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:playwright-suite"
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

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the
target.**

Flags (each independent):

- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false`.
- `--allow-push-to-default` → `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`.)
- `--proposal-first` → `PROPOSAL_FIRST = true`. Runs P0 → P4 (target resolution,
  inventory, map freshness, existing-test review, gap analysis), then PAUSES for
  user review before authoring gap-fill tests at P5 and reorganising the suite at
  P7. Domain gates (P2 bulk-verify, P4 unknown-persona escalation, P8 prod-mutation
  authorization) fire regardless.
- `--no-worktree` → `AUTO_WORKTREE = false`. (Default `true`.) Run in the current
  checkout. Natural-language equivalents — *"no worktree"* / *"in place"* /
  *"in current tree"*.
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`,
  `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `AUTO_WORKTREE = true`.

## Auto-cleanup of merged worktrees (v1.3.0) -- runs first

Before any argument parsing or pipeline invocation, sweep merged architect-team
worktrees, exactly as the other five lane commands do. Best-effort: a failure
surfaces a one-line note and the run continues.

1. Refresh the origin ref so merge detection is current (best-effort):
   ```bash
   git fetch origin main 2>/dev/null || true
   ```
2. Invoke the cleanup helper via the detect-once form:
   ```bash
   $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_merged_worktrees; [print(f'cleaned: {p}') for p in cleanup_merged_worktrees()]" 2>&1 || echo 'auto-cleanup: best-effort, continuing.'
   ```
3. Report any cleaned paths in one line; the current worktree is excluded by default.

## Auto-worktree creation — runs after argument parsing, before skill invocation

Mirrors `commands/ux-test.md`'s worktree wiring. After binding `$SUITE_TARGET` and
BEFORE invoking the skill, decide whether the auto-worktree step applies:

- **Skip the step** when EITHER holds:
  - `AUTO_WORKTREE` is false (`--no-worktree`, or a natural-language opt-out).
  - The current branch already starts with `architect-team/` (re-entry —
    `scripts.setup.worktree_lifecycle.current_worktree_is_run()` returns True). No
    nested worktrees; the existing run worktree IS the workspace.

- **Run the step** otherwise:
  1. Derive `<slug>` as `playwright-suite-<codebase-slug>` from the resolved target.
  2. Invoke the helper via the v2.16.0 detect-once form — the interpreter is
     selected ONCE and the snippet runs exactly once, because
     `create_run_worktree` raises on collision exhaustion and the older
     `python3 X || python X` form would silently re-run the whole creation on that
     meaningful failure:
     ```bash
     $(command -v python3 || command -v python) -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import create_run_worktree; print(create_run_worktree('<slug>'))"
     ```
     Capture the printed absolute path as `$WORKTREE_PATH`.
  3. `chdir` into `$WORKTREE_PATH`; every subsequent step, including the Skill
     invocation, runs with it as cwd.
  4. Surface a one-line note naming the path and branch, and that `--no-worktree`
     skips it next time.

On creation failure the helper raises `RuntimeError` with an actionable message —
surface it verbatim and STOP. Do NOT silently fall back to the current checkout:
the user asked for a worktree (the default), and failing without notice is the
anti-pattern this explicit error path exists to prevent.

Per `common-pipeline-conventions` `## Auto-worktree lifecycle` for the full rules.

### Binding the target

What remains after stripping flags binds to `$SUITE_TARGET`:

| Form | What it is | Bind `$SUITE_TARGET` to |
|---|---|---|
| **Path** | a directory that resolves on disk — the frontend codebase | the path |
| **Prose** | a description — *"the admin dashboard front end"* | the entire remaining string, verbatim |
| **Empty** | no argument | the workspace itself; P0 discovers the frontend codebases in scope |

An empty argument is NOT an error and never earns a clarifying question — a
single-frontend repo is the common case and P0 resolves it. When P0 finds more
than one frontend codebase and the target does not disambiguate, the skill asks
once, naming the candidates it found. One manifest is built per codebase, so
"all of them" is a valid answer.

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into
skill bodies. Pass the bound `$SUITE_TARGET` — a path, the verbatim prose, or the
workspace — as the input to the skill, along with `AUTO_COMMIT`, `AUTO_PUSH`,
`AUTO_COMPACT_PROMPT`, `ALLOW_PUSH_TO_DEFAULT`, and `PROPOSAL_FIRST`. The skill's
P5 and P7 read `PROPOSAL_FIRST` to decide whether to pause after P4.

## Invoke the pipeline

Use the `Skill` tool with `skill: playwright-suite-builder` and follow its phases
exactly against the bound target. The skill begins at Phase P0 (target + e2e-dir
resolution) and proceeds through Phase P9 (manifest write + report).

Two of its phases can pause for the user, and both are domain gates that fire
regardless of any process-gate setting:

- **P2 bulk-verify** — a refreshed intuition map produced new `low` / `unknown`
  items. The user resolves them as one numbered list before authoring proceeds.
- **P4 unknown persona** — the persona behind a coverage gap cannot be cited from
  the existing user-intent maps, research outputs, or intake records. It
  escalates per `playwright-user-flows` Step 0; it is never guessed.

A third pause is possible at P8 — a mutating test proposed for the prod project
needs the user's explicit authorization, and there is no default that grants it.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase P9, after the run report:

0. **Run the completion audit FIRST:**
   `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check`.
   The substitution detects the interpreter once and invokes the script exactly
   once. A non-zero exit means the run is incomplete — do NOT commit; resolve the
   violations or escalate.
1. `git -C <repo-root> status --porcelain` — enumerate what changed.
2. `git -C <repo-root> add <files-the-run-touched>` — the suite specs, the
   `suite-manifest.json`, the Playwright config changes, and the refreshed
   intuition map. Nothing else.
2b. **Default-branch guard:** if the current branch is `main` / `master` AND
   `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/playwright-suite-<codebase-slug>`
   before committing.
3. Commit as the checkout's RECORDED person (v3.67.0, resolved at the front door):
   `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd <repo-root> git -- -C <repo-root> commit -m "<commit message>"`
   (the wrapper injects the recorded `-c user.name= -c user.email=` pair and
   REFUSES when there is none), or the explicit pair from `git_identity.py status --json`.
4. `git -C <repo-root> push -u origin <branch>`.
5. Report the commit SHA and the push range. If the commit landed on a feature
   branch, say so and recommend opening a PR.

If `AUTO_COMMIT = false`: skip steps 2-5 and say in the report that the suite was
left uncommitted. If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-3
only and say the commit is local.

The manifest is a committed artifact of the TARGET repo by design — it is the
registry a full-integration run and CI both read. Leaving it uncommitted leaves
the suite unregistered.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase P9 completed cleanly, emit the
standard `/compact` prompt block as the very last thing the user sees:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Playwright suite built. Context is now full of spec files     ║
║  and coverage analysis. Run /compact NOW to free space for     ║
║  the next architect-team invocation. Type exactly:             ║
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
- If `git push` fails, surface the error clearly and stop — never escalate to
  force-push.
- Pre-existing unstaged or staged changes are the user's in-progress work — do
  NOT include them; surface them in the final report.
- **NEVER run the prod project against a production URL as part of this command.**
  The command BUILDS the prod smoke suite; running it is a separate, deliberate
  act via `/architect-team:monitor-tests` or the project's own scheduler.
- **NEVER schedule arbitrary wall-clock wakeups, cron jobs, or background timer
  tools.** The pipeline is synchronous; subagent dispatches block your turn.

## Production-safety rule

P8 is default-deny. A test that mutates data enters the prod project ONLY through
a `prod_exceptions[]` entry carrying the user's recorded authorization (who,
when, why), the `it-<prefix>` test-only data tag, and mandatory teardown. There is
no flag on this command that grants that authorization — it is asked for, in
context, per test, or it does not happen.

## Cross-references

- `skills/playwright-suite-builder/SKILL.md` — the canonical P0-P9 contract.
- `skills/intuition-map-lifecycle/SKILL.md` — the `ensure` and `bug-path-upsert`
  verbs P2 and P6 call.
- `skills/playwright-user-flows/SKILL.md` — Step 0 personas, Phase C coverage
  math, and the full authoring discipline P5 applies.
- `skills/test-prod-safety-classifier/SKILL.md` — the P8 verdict source.
- `scripts/playwright_suite/manifest.py` — the manifest schema engine and the
  `verify-suite-manifest` ship check P9 gates on.
