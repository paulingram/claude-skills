---
description: Produce an adversarially-verified codebase-restructure PLAN — analyze the code + codebase maps (producing them via cartographer-team if missing/stale), converge ×3 independent structure-analyst drafts gated by a deterministic every-file partition check, close every movement's reference-impact set (imports / configs / CI / docs / string paths, file:line evidence), refute the whole via ×3 structure-adversary rounds until two consecutive all-clean rounds, architect-audit it, and ship RESTRUCTURE_PLAN.md + movements.json + a strict-validated OpenSpec change. Plan-only by default — execution belongs to /architect-team driving the produced change (--execute hands off immediately). Commits the produced artifacts (never source moves) unless --no-commit; emits a /compact prompt unless --no-compact.
argument-hint: "[codebase-path | --all] [--objective \"<prose>\"] [--execute] [--no-commit] [--no-push] [--no-compact]"
---

# /architect-team:optimize-structure — Codebase Structure Optimization (plan, verify, hand off)

You are running the structure-optimization pipeline. The user invoked this with `$ARGUMENTS` = an optional codebase path + optional flags. This command is the explicit entry point for the `structure-optimization` skill (v3.11.0): it produces the verified restructure PLAN; it **never moves a single source file** — execution is `/architect-team` driving the OpenSpec change this run produces.

## Dispatch mode banner — runs first

As the very first user-visible action, print the dispatch-mode banner (Agent Teams vs subagents fallback) so the user knows which dispatch primitive will drive the ×3 analyst / ×3 adversary convergence loops. Best-effort — subprocess failure surfaces a one-line note and the run continues.

```!
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:optimize-structure"
```

## Argument parsing

Parse `$ARGUMENTS` into tokens:

- **First non-flag token** → the codebase path. Resolve to absolute; assert it is a directory (and `git -C <path> rev-parse --is-inside-work-tree` succeeds — the partition check is defined over `git ls-files`, so a non-git directory is a structured error: tell the user to `git init` or point at a repo).
- **`--all`** → every codebase recorded in `<workspace>/.architect-team/intake-state.json`; if none recorded, fall back to the current repo root.
- **If `$ARGUMENTS` is empty** → default to the current repo root (`git rev-parse --show-toplevel`).

Flags (natural-language phrasings count — "don't commit", "no push", "skip the compact prompt", "and then implement it" / "execute the plan" → `--execute`):

- `--objective "<prose>"` → the optimization objective, passed VERBATIM into `scope.json` and every analyst/adversary brief. Omitted → general structural health. Per `common-pipeline-conventions` `## Scope discipline`, the pipeline never narrows this prose silently — a scope-fidelity doubt surfaces as a question.
- `--execute` → `EXECUTE_AFTER_PLAN = true` (default `false`). When true, Stage S8 hands the produced OpenSpec change straight to the `architect-team-pipeline` skill for implementation under the full review gates. Default is plan-only: the user reviews the plan, then runs `/architect-team` when ready.
- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false` (default `true`).
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `EXECUTE_AFTER_PLAN = false`.

## Invoke the pipeline

Invoke the `structure-optimization` skill from this plugin (use the Skill tool with `skill: structure-optimization`). Pass:

```json
{
  "codebase_inputs": ["<resolved-path>", "..."],
  "objective": "<--objective prose or null>",
  "execute_after_plan": false,
  "auto_commit": true,
  "auto_push": true,
  "openspec_change_name": "restructure-<repo-name>-<YYYY-MM-DD>"
}
```

The skill drives Stages S0–S8: maps current via `cartographer-team` (freshness-checked; produced if missing) → ×3 `structure-analyst` independent drafts → ralph-loop convergence gated by the deterministic partition check (`STRUCTURE PROPOSAL CONVERGED`) → sharded `reference-tracer` closure into `movements.json` → ×3 `structure-adversary` refutation rounds until two consecutive all-clean rounds (`RESTRUCTURE PLAN VERIFIED`) → `system-architect` Restructure Plan Audit → `RESTRUCTURE_PLAN.md` assembly → `openspec-propose` authoring + `openspec validate --all --strict --json` (`OPENSPEC AUTHORING COMPLETE`) → return + handoff.

Follow the skill exactly — including the partition-check gate, the two-consecutive-clean-rounds exit rule, and the producer/checker role separation.

## Report

Emit a structured summary: movements (by kind, with every `delete-dead` listed verbatim), references-to-change count, forced-refactor count, batches + their verification commands, adversarial rounds run, architect verdict, artifact paths (`RESTRUCTURE_PLAN.md`, `movements.json`, `openspec/changes/<name>/`). Then the handoff line: plan-only runs end with *"execution-ready — run `/architect-team` with the produced change to implement it under the full review gates"*; `--execute` runs continue straight into the implementing pipeline.

## Default git behavior (when `AUTO_COMMIT = true`)

At the end of Stage S8 (plan produced, validate green):

1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add` ONLY the produced artifacts: `.architect-team/structure-optimization/<slug>/`, `openspec/changes/<name>/`, and any refreshed maps (`docs/CODEBASE_MAP.md` / `ROUTE_MAP.md` / `INTEGRATION_MAP.md`). Do NOT use `git add -A`.
3. **Default-branch guard:** if the current branch is `main` / `master`, `git -C <repo-root> checkout -b architect-team/optimize-structure-<slug>` before committing.
4. Commit:

```
structure-optimization: <one-line objective or "general structural health">

- movements: <N> (move=<N> rename=<N> split=<N> merge=<N> delete-dead=<N>)
- references to change: <N> across <N> files; forced refactors: <N>
- partition check: <tracked> tracked files, 0 orphans, 0 duplicates
- adversarial rounds: <N> (final two all-clean); architect verdict: pass
- artifacts: RESTRUCTURE_PLAN.md + movements.json + openspec/changes/<name>/

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

5. If `AUTO_PUSH = true`: `git push -u origin <branch>`. If the push fails, surface the error and stop — never escalate.

If `AUTO_COMMIT = false`: skip steps 2–5 and note the artifacts are uncommitted at user request.

## Auto-compact prompt (after the report)

When `AUTO_COMPACT_PROMPT = true`, emit this block as the very last thing the user sees in this turn:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Structure-optimization plan complete. Context holds the       ║
║  full convergence + adversarial state. Run /compact NOW to     ║
║  free space before executing the plan. Type exactly:           ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

The model cannot programmatically execute `/compact` — it is a user-typed REPL command. If `AUTO_COMPACT_PROMPT = false`, skip the block.

## Safety rules (non-negotiable)

- This command plans; it **never moves a single source file**, never edits source, never runs `git mv`. "Just applying the two easy renames" is the forbidden first bite of unreviewed execution — the implementing pipeline owns every movement.
- NEVER force-push. NEVER skip git hooks. NEVER amend the previous commit.
- If the working tree had unstaged changes BEFORE this command ran, treat them as the user's in-progress work; do NOT stage them.
- NEVER schedule arbitrary wall-clock wakeups, cron jobs, or background timer tools from inside the pipeline (v0.9.2 pipeline-discipline rule). The run is synchronous.
- Every `delete-dead` movement is surfaced verbatim in the report — deletion never hides inside a summary count.

## Cross-references

- `skills/structure-optimization/SKILL.md` — the canonical skill body (stages S0–S8, the partition check, the movements.json schema, the adversarial exit rule).
- `agents/structure-analyst.md` / `agents/reference-tracer.md` / `agents/structure-adversary.md` — the three new roles; `agents/system-architect.md` `## Restructure Plan Audit` — the Stage S6 gate.
- `skills/cartographer-team/SKILL.md` — the reused map machinery (Stage S1).
- `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)` — the ralph-loop / openspec / superpowers invocation contracts this pipeline follows.
- `commands/architect-team.md` — the implementing pipeline the produced change hands off to.
