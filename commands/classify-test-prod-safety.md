---
description: Mass-classify every Playwright / QA test file in a codebase as `@prod-safe` (only reads — safe against ANY deployed environment including production) or `@not-prod-safe` (contains mutations). Produces a per-file classification report at `<workspace>/.architect-team/test-prod-safety/classification-report-<ts>.json` listing every file's existing annotation, the auto-classifier verdict, and the detected mutation/read-only signatures. With `--write-annotations`, modifies files in-place to inject the top-of-file annotation comment. Default is `--dry-run`. Ambiguous classifications escalate to the user instead of silently guessing.
argument-hint: "[<glob | codebase-path>] [--write-annotations] [--dry-run]"
---

# /architect-team:classify-test-prod-safety — Mass-Classify Test Prod-Safety

You are running the test-prod-safety-classifier skill in Mode 1 (mass-classify). The user invoked this with `$ARGUMENTS` = optional glob pattern or codebase path + optional flags. Default behavior is `--dry-run` (report only); `--write-annotations` modifies files in-place to inject the top-of-file annotation.

## Dispatch mode banner — runs first

```!
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:classify-test-prod-safety"
```

## Auto-cleanup merged worktrees — runs before argument parsing

```!
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/worktree_lifecycle.py" cleanup-merged --against origin/main
```

## Argument parsing

Parse `$ARGUMENTS` into tokens.

- **First non-flag token** → glob pattern (`tests/**/*.spec.ts`) OR codebase path (a directory containing `tests/` or `e2e/`). Default if empty: scan `tests/**/*.spec.ts`, `tests/**/*.test.ts`, `tests/**/*.spec.js`, `tests/**/*.test.js`, `tests/**/*.py` (test_*.py), `spec/**/*_spec.rb` from the current working directory.

Flags (each independent — natural-language phrasings count as the matching flag — opt-outs: "don't write", "no write"; opt-in: "write annotations", "modify files"):

- `--write-annotations` (or "write annotations", "modify files") → `WRITE_ANNOTATIONS = true`. The skill modifies test files in-place to inject the top-of-file annotation comment.
- `--dry-run` (or "dry run", "report only") → `WRITE_ANNOTATIONS = false`. Default behavior. Produces the classification report at `<workspace>/.architect-team/test-prod-safety/classification-report-<ts>.json` without modifying any files.
- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false` (default `true`).

## Invoke the skill

Invoke the `test-prod-safety-classifier` skill from this plugin (use the Skill tool with `skill: test-prod-safety-classifier`). Pass the bound glob/path and the `WRITE_ANNOTATIONS` flag. The skill runs Mode 1 (mass-classify):

1. Enumerate test files matching the glob.
2. For each file: read contents → check for existing annotation → run auto-classifier (`_classify_test_file` from `hooks/vao_tools.py`) → emit per-file record.
3. Aggregate counts (prod-safe / not-prod-safe / ambiguous).
4. If `WRITE_ANNOTATIONS=true`: for each file with NO existing annotation AND auto-classification != ambiguous, inject the annotation as the FIRST non-shebang, non-blank line.
5. Surface ambiguous files to the user with a structured question for each.
6. Write the classification report to `<workspace>/.architect-team/test-prod-safety/classification-report-<ts>.json`.

## Summarize after the skill runs

- Total files scanned.
- Counts per classification (prod-safe / not-prod-safe / ambiguous).
- If `WRITE_ANNOTATIONS=true`: how many files were modified.
- Surfacing of every ambiguous file as a numbered list with the question: *"This file has no clear mutation or read-only signal. Please review and classify: (1) `@prod-safe`, (2) `@not-prod-safe`, (3) skip for now."*
- Per-file mismatch warnings (existing annotation says `@prod-safe` but auto-classifier says `not-prod-safe`, or vice versa). The annotation wins; the warning is flagged for human review.

## Default git behavior (when `AUTO_COMMIT = true` AND `WRITE_ANNOTATIONS = true`)

If files were modified:

1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add` ONLY the test files that gained an annotation + the classification report under `.architect-team/test-prod-safety/`.
2b. **Default-branch guard:** if on `main` / `master` AND `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/classify-test-prod-safety-<ts>`.
3. Commit:

```
classify-test-prod-safety: annotated <N> test files

- prod-safe: <N>
- not-prod-safe: <N>
- ambiguous (skipped, escalated): <N>
- Mismatch warnings: <N>
- Report: <path to .architect-team/test-prod-safety/classification-report-<ts>.json>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

4. `git push -u origin <branch>`.

If `AUTO_COMMIT = false` OR `WRITE_ANNOTATIONS = false`: skip steps 2-4; mention in the final report that the classification ran in dry-run mode (default) or that files were modified but left uncommitted.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true`, emit the canonical `/compact` block as the LAST thing the user sees.

## Safety rules (non-negotiable)

- NEVER force-push. NEVER skip git hooks. NEVER amend the previous commit.
- The classifier is READ-ONLY on test file contents UNLESS `--write-annotations` is passed.
- Ambiguous files are NEVER auto-annotated; they escalate to the user.
- Files that already have an annotation are NEVER overwritten (the annotation is the source of truth; mismatches are flagged but not corrected).
- NEVER schedule arbitrary wall-clock wakeups, cron jobs, or background timer tools from inside this command.

## Cross-references

- `skills/test-prod-safety-classifier/SKILL.md` — the canonical skill body (Modes 1 + 2).
- `skills/common-pipeline-conventions/SKILL.md` `## Prod-safe test classification discipline (v2.17.0)` — the canonical home of the rule.
- `hooks/vao_tools.py::verify_test_prod_safety_classification` — the 15th Layer 3 tool (Mode 2 gate).
