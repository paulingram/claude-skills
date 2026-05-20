---
description: Spec-to-production multi-agent coding pipeline. Takes a requirements folder (OpenSpec / Superpowers / plain markdown) and drives it end-to-end to tested, integrated production code. Auto-commits and pushes on a clean Phase 8 pass and emits a clear /compact prompt to free context for the next run, unless invoked with --no-commit / --no-push / --no-compact.
argument-hint: "<path-to-requirements-folder> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default]"
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

**Raw arguments:** $ARGUMENTS

## Argument parsing (do this first, before binding `$REQ_DIR`)

Parse `$ARGUMENTS` into a path component and zero or more flags. Whitespace-separated tokens:

- The FIRST non-flag token is the requirements folder path. Bind it as `$REQ_DIR`.
- `--no-commit` flag → set `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` flag → set `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` flag → set `AUTO_COMPACT_PROMPT = false`. (Default `true`.)
- `--allow-push-to-default` flag → set `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`.) When false, the pipeline will NOT commit + push unreviewed work straight onto a `main` / `master` branch — it commits to an `architect-team/<change-name>` feature branch instead and tells you to open a PR. Pass this flag only when pushing the pipeline's output directly to the default branch is genuinely what you want.
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`.

Flags are independent of each other (e.g., `--no-commit --no-compact` is valid — skips both).

Also accept natural-language opt-outs in the user's message: phrases like "don't commit", "skip the commit", "no push", "no compact", "don't compact", "leave the changes uncommitted" — treat these as equivalent to the corresponding flag. When in doubt about a natural-language opt-out, default to opting out (safer) and tell the user which interpretation you took.

If `$REQ_DIR` resolves to an empty string after parsing, ask the user for the requirements folder path. Do nothing else until they provide it.

**IMPORTANT — path binding:** The Claude Code harness does NOT propagate command `$ARGUMENTS` into skill bodies automatically. You MUST treat the bound `$REQ_DIR` value as the input to every reference to `$REQ_DIR` in the `architect-team-pipeline` skill. Before invoking the skill, substitute this value wherever the skill body refers to `$REQ_DIR` or "the requirements folder". Do NOT re-prompt the user for it when the skill body's own placeholder appears empty — you already have it.

## Invoke the pipeline

Invoke the `architect-team-pipeline` skill from this plugin (use the Skill tool with `skill: architect-team-pipeline`) and follow its pipeline exactly against the requirements folder above. The skill begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report).

**Pass the `AUTO_COMMIT`, `AUTO_PUSH`, and `ALLOW_PUSH_TO_DEFAULT` flags to the skill.** The skill's Phase 8 reads these to decide whether to auto-commit, push, and whether it may push straight to a default branch.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase 8, after the final report emits "Spec `<change-name>` has been implemented." and the archive path:

0. **Run the completion audit FIRST:** `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` from the repo root. If it exits non-zero, the run is incomplete — do NOT commit; resolve the reported violations or escalate. Only an exit-0 audit proceeds.
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
