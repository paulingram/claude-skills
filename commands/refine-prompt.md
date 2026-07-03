---
description: Refine a free-text prompt with codebase-grounded clarity-grading + conversational dialogue, without running any downstream pipeline. Produces a structured refined-prompt markdown under .architect-team/refined-prompts/ that can later be fed to /architect-team, /architect-team:bug-fix, or /architect-team:ux-test.
allowed-tools: Skill, Read, Glob, Grep, LS, Bash, Write, AskUserQuestion, TodoWrite, Agent
---

# Proposal Refiner — Standalone Invocation

You are starting the `proposal-refiner` skill in **STANDALONE** mode against a free-text prompt. The skill grades the prompt across six axes (clarity, scope, acceptance, codebase grounding, conflict, scope-fidelity), generates codebase-anchored clarifying questions, iterates with you up to 5 cycles or until you confirm `ship it`, and writes the refined version to a markdown file. No downstream pipeline runs in this mode — that's the difference from `/architect-team` with free-text input (which runs the refiner THEN the architect-team-pipeline).

## Argument parsing (do this first, before invoking the skill)

Parse `$ARGUMENTS` into a free-text prompt and optional flags:

- The non-flag content (everything except recognized flags) is the prompt. Bind it as `$PROMPT`.
- `--out <path>` → override the default output path (`<cwd>/.architect-team/refined-prompts/<slug>-<ts>.md`). The path must be an absolute path or a path relative to `<cwd>`.
- `--codebases <comma-separated-paths>` → explicit codebase paths to ground refinement against. Default: auto-discover from `<cwd>/.architect-team/intake-state.json`'s prior codebase list, or `<cwd>/codebases.json`, or — when neither exists and the prompt mentions code — prompt the user once during Phase R1.
- `--no-mempalace` → skip the read-only MemPalace wake-up at Phase R1 (default: include it when the palace exists).
- `--max-iterations <integer>` → override the default iteration ceiling of 5. Min 1, max 10.

Whitespace-separated tokens. Flags are independent.

If `$PROMPT` resolves to an empty string after parsing, ask the user for it:

> *"What prompt would you like refined? Paste your free-text prose and I'll grade it, surface clarifying questions grounded in the codebase, and produce a refined markdown brief."*

Do nothing else until they provide it.

If `$PROMPT` resolves to a path that exists on disk and is either (a) a directory, OR (b) a markdown file with `refined-by: proposal-refiner` frontmatter, refuse with: *"The argument resolves to an already-refined or already-structured input. Refinement skipped. To run a pipeline on it: `/architect-team <path>` (or `:bug-fix` / `:ux-test`)."* Stop without invoking the skill.

## Invoke the skill

Set `$REFINER_MODE = "standalone"`. Invoke the `proposal-refiner` skill from this plugin (use the Skill tool with `skill: proposal-refiner`) and follow it through phases R1 → R6 exactly. The skill's own body handles codebase-map loading, multi-axis grading, the dialogue loop, and the final markdown output.

Pass the parsed flags through to the skill's working state:

- `$REFINER_OUT_PATH = <from --out, or default>`
- `$REFINER_CODEBASES = <from --codebases, or auto-discover>`
- `$REFINER_USE_MEMPALACE = <true unless --no-mempalace>`
- `$REFINER_MAX_ITERATIONS = <from --max-iterations, or 5>`

## After the skill exits

The skill writes `<refined-prompt-path>.md` and returns its absolute path. Print a one-line summary to the user:

```
Refined prompt landed at <path>. Final grade: <letter> (<score>/100), <iterations> iteration(s), exit: <reason>.

To run a downstream pipeline on this brief:
  /architect-team <path>              — full spec-to-production pipeline
  /architect-team:bug-fix <path>      — bug-fix pipeline (only if the brief describes a bug)
  /architect-team:ux-test <path>      — UX test orchestrator (only if the brief describes a UX testing run)
```

Stop. No further work. This command is intentionally a single-shot refiner — its purpose is to give you a refined markdown you can review, version-control, or hand off without running implementation.

## What this command does NOT do

- **Does NOT trigger Phase −2 (Triage) or any other downstream phase.** That is the difference from `/architect-team` (free-text input runs the refiner THEN proceeds to Phase −2). Standalone exits after R6.
- **Does NOT auto-commit.** The output is a single markdown file under `.architect-team/refined-prompts/` (gitignored by default — runtime state). To version-control a refined brief, the user moves / commits it manually OR re-runs `/architect-team <path>` which carries the file through normal pipeline-driven commit.
- **Does NOT modify source code, tests, OpenSpec artifacts, plugin metadata, or anything outside `<cwd>/.architect-team/refined-prompts/`.** The `prompt-refiner` agent's bounded Write scope is enforced.
- **Does NOT skip the dialogue loop** unless the initial grade is A AND the user immediately confirms. A high initial grade still gets a one-iteration confirmation pass — you read the grade, you say "ship it", the file lands. That confirmation is non-skippable in standalone mode.
- **Does NOT route to a fix team, an architect, or any other downstream agent.** The refiner is a single-purpose grader + dialogue manager.

## Safety rules (non-negotiable)

- **Never invent codebase entities.** When grounding the refinement against codebase maps, every cited route / endpoint / file / function MUST trace to a map entry. A fabricated citation defeats the purpose of grounding and the agent body explicitly forbids it.
- **Never run any tool that produces irreversible state** (deploys, pushes, commits, package installs, file deletions outside `.architect-team/refined-prompts/`). Standalone mode is a thinking step.
- **Never schedule wall-clock wakeups (`ScheduleWakeup`), cron jobs, or background timers.** The skill runs synchronously through Phase R1 → R6 in a single turn (modulo the user-dialogue loop, which is the harness's natural pause point).
