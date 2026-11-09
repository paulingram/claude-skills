# Converge workflows — reviewer convergence as code (v4.0.0)

> **STOP.** Before running any "N reviewers loop until all ok" gate, Read this
> chapter and run the `ct6-converge` workflow instead of describing the loop in
> prose or reaching for the retired the `ct6-converge` workflow plugin.

## What it is

`workflows/ct6-converge.js` is a Workflow-tool script shipped with the plugin.
It dispatches N independent reviewers in parallel (each blind to the others),
collects typed verdicts (`{status: ok|deficient, deficiencies[]}`), briefs one
fixer with every deficiency, and loops until every reviewer returns `ok`. There
is no self-imposed round cap: the only ceiling is a human-set `maxRounds`
argument, and reaching it returns `converged: false` with the history, never a
silent pass. A reviewer that returns nothing is "not yet verified", never ok.

Run it with the Workflow tool: `Workflow({ name: "ct6-converge", args: {...} })`.

## Presets

| Gate | kind | promise | reviewerAgent | fixerAgent | reviewers |
|---|---|---|---|---|---|
| Phase −1B codebase map | `codebase-map` | `CODEBASE MAP COMPLETE` | `architect-team:codebase-map-reviewer` | `architect-team:route-mapper` (frontend) or the mapper that produced the map | 3 |
| Phase −1C integration map | `integration-map` | `INTEGRATION MAP COMPLETE` | `architect-team:integration-explorer` | `architect-team:master-synthesizer` | 3 |
| Editability completeness | `editability` | `EDITABILITY COMPLETE` | `architect-team:editability-reviewer` | the owning teammate | 3 at Phase 7, 1 per slice at Phase 3 |
| Interaction completeness | `interaction` | `INTERACTION COMPLETE` | `architect-team:interaction-reviewer` | the owning frontend teammate | 3 at Phase 7, 1 per slice at Phase 3 |
| Phase 7 master review | `master-review` | `MASTER REVIEW COMPLETE` | `architect-team:task-reviewer` | the Lead re-enters Phase 2 (fixerPrompt says so) | 3 |

`artifacts` carries the repo-relative paths the reviewers audit. `reviewers`
follows the review-tier table (`skills/team-spawning-and-review-gates/references/review-tiers.md`).

## Why a workflow and not a loop in prose

The loop is deterministic control flow: fan out, collect, decide, repeat. In
prose it drifted (round caps appeared, reviewers were sometimes asked to spawn
each other, silence was read as ok). In a script those are structurally
impossible, the verdicts are typed, and the history is returned as evidence.

## Honest boundary

The workflow proves the reviewers returned `ok`; it does not make them right.
Evidence rules apply inside each reviewer. In a `-p` session the Workflow tool
is available; in a session where it is disabled (`CLAUDE_CODE_DISABLE_WORKFLOWS=1`)
run the same loop by hand with the Agent tool and record each round's verdicts
in the evidence file.
