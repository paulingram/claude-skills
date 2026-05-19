---
description: Spec-to-production multi-agent coding pipeline. Takes a requirements folder (OpenSpec / Superpowers / plain markdown) and drives it end-to-end to tested, integrated production code. Auto-commits and pushes on a clean Phase 8 pass and emits a clear /compact prompt to free context for the next run, unless invoked with --no-commit / --no-push / --no-compact.
argument-hint: "<path-to-requirements-folder> [--no-commit] [--no-push] [--no-compact]"
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
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`.

Flags are independent of each other (e.g., `--no-commit --no-compact` is valid — skips both).

Also accept natural-language opt-outs in the user's message: phrases like "don't commit", "skip the commit", "no push", "no compact", "don't compact", "leave the changes uncommitted" — treat these as equivalent to the corresponding flag. When in doubt about a natural-language opt-out, default to opting out (safer) and tell the user which interpretation you took.

If `$REQ_DIR` resolves to an empty string after parsing, ask the user for the requirements folder path. Do nothing else until they provide it.

**IMPORTANT — path binding:** The Claude Code harness does NOT propagate command `$ARGUMENTS` into skill bodies automatically. You MUST treat the bound `$REQ_DIR` value as the input to every reference to `$REQ_DIR` in the `architect-team-pipeline` skill. Before invoking the skill, substitute this value wherever the skill body refers to `$REQ_DIR` or "the requirements folder". Do NOT re-prompt the user for it when the skill body's own placeholder appears empty — you already have it.

## Invoke the pipeline

Invoke the `architect-team-pipeline` skill from this plugin (use the Skill tool with `skill: architect-team-pipeline`) and follow its pipeline exactly against the requirements folder above. The skill begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report).

**Pass the `AUTO_COMMIT` and `AUTO_PUSH` flags to the skill.** The skill's Phase 8 reads these to decide whether to auto-commit and push at the terminal step.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase 8, after the final report emits "Spec `<change-name>` has been implemented." and the archive path:

1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add <files-the-pipeline-touched>` — stage ONLY the files the pipeline created or modified (read from the coverage-map's `implementing_commits`'s working set + `openspec/changes/<change-name>/` + any updated CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP files). Do NOT use `git add -A` — that risks sweeping in unrelated files.
3. `git -C <repo-root> commit -m "$(cat <<'EOF'
<change-name>: <one-line summary from Phase 8 final-statement>

- Requirements implemented: <REQ-001, REQ-002, ...> (N total)
- Tests added: <unit / integration / e2e counts; all passing>
- Coverage map: fully green
- Phases −1 → 8 complete; openspec archive landed at <archive-path>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"` — use the repo's local git config (no `-c user.name=` override here; that override is specific to repos with mis-configured local config).
4. `git -C <repo-root> push origin <current-branch>` — push to the current branch's upstream.
5. Report the commit SHA and push range in the final user-facing report.

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
