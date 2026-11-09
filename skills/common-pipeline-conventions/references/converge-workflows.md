# Converge workflows — reviewer convergence as code (v4.0.0)

> **STOP.** Before running any "N reviewers loop until all ok" gate, Read this
> chapter and run the gate as DECLARE → `ct6-converge` workflow → RECORD, exactly
> as written below, instead of describing the loop in prose or reaching for the
> retired ralph-loop plugin.

## What it is

`workflows/ct6-converge.js` is a Workflow-tool script shipped with the plugin.
It dispatches N independent reviewers in parallel (each blind to the others),
collects typed verdicts (`{status: ok|deficient, deficiencies[]}`), briefs one
fixer with every deficiency, and loops until every reviewer returns `ok`. There
is no self-imposed round cap: the only ceiling is a human-set `maxRounds`
argument, and reaching it returns `converged: false` with the history, never a
silent pass. A reviewer that returns nothing is "not yet verified", never ok.

The workflow is the middle of three steps. A convergence gate is DECLARED before
the workflow runs and RECORDED after it, and the Stop audit holds the run until
the record says converged. The record script is `record.py` under
`scripts/converge/` (stdlib; `declare` and `record` verbs).

## The protocol — declare, run, record

1. **Declare first.**

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" declare --workspace <ws> --kind <kind> --promise "<PROMISE>" --reviewers <N>
   ```

   appends the gate `converge:<kind>` to `<ws>/.architect-team/declared-gates.json`
   (the declared-gates discipline, `references/declared-gates-discipline.md`);
   `_audit_declared_gates` in `hooks/pipeline-completion-audit.py` refuses the Stop
   until that gate is satisfied with evidence.

2. **Run the workflow.** `Workflow({ name: "ct6-converge", args: { kind: "<kind>",
   promise: "<PROMISE>", artifacts: [...], reviewerAgent: "...", fixerAgent: "...",
   reviewers: <N>, maxRounds: <human-set only> } })`. It returns JSON with
   `converged`, `rounds`, `history[]` and `record`.

3. **Record after.**

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" record --workspace <ws> --kind <kind> --result '<the workflow's JSON>'
   ```

   (or `--result-file <path>`) writes `<ws>/.architect-team/converge/<kind>-<ts>.json`
   and satisfies the gate ONLY when `converged` is true and the final round's `ok`
   count equals the reviewer count; otherwise it exits 1, the gate stays open, and
   the Lead re-runs the workflow. A human-set `maxRounds` that was reached PAUSES
   the gate (the record carries `converged: false`); it never satisfies it.

The promise string (`CODEBASE MAP COMPLETE`, `MASTER REVIEW COMPLETE`, …) is the
gate's LABEL: it names the gate in the declaration, in the record and in the
evidence file. It is not the exit test. The exit condition is the verdicts
recorded on disk — no agent "emits the promise to exit the loop", and an agent
that types the string has changed nothing.

## Presets

| Gate | kind | promise (label) | reviewerAgent | fixerAgent | reviewers (tier) |
|---|---|---|---|---|---|
| Phase −1B codebase map | `codebase-map` | `CODEBASE MAP COMPLETE` | `architect-team:codebase-map-reviewer` | `architect-team:route-mapper` (frontend) or the mapper that produced the map | 3 (tier 3) |
| Phase −1C integration map | `integration-map` | `INTEGRATION MAP COMPLETE` | `architect-team:integration-explorer` | `architect-team:master-synthesizer` | 3 (tier 3) |
| Editability completeness | `editability` | `EDITABILITY COMPLETE` | `architect-team:editability-reviewer` | the owning teammate | 3 at the Phase 7 sweep (tier 3); 1 per slice at Phase 3 / Phase 5 (tier 2) |
| Interaction completeness | `interaction` | `INTERACTION COMPLETE` | `architect-team:interaction-reviewer` | the owning frontend teammate | 3 at the Phase 7 sweep (tier 3); 1 per slice at Phase 3 / Phase 5 (tier 2) |
| Phase 7 master review | `master-review` | `MASTER REVIEW COMPLETE` | `architect-team:task-reviewer` | the Lead re-enters Phase 2 (fixerPrompt says so) | 3 (tier 3) |

`artifacts` carries the repo-relative paths the reviewers audit. `reviewers`
follows the review-tier table (`skills/team-spawning-and-review-gates/references/review-tiers.md`):
three for a tier-3 gate, one paired reviewer for tier 2 (a tier-2 disagreement
escalates to a second independent verdict, recorded in the same `history[]`).
Other skills declare their own kinds the same way (`structure-proposal`,
`restructure-plan`, `domain-research`, `stage-<n>` for the exploration stages,
`openspec-authoring`): any kind is valid as long as it is declared before and
recorded after.

## Fallback when the Workflow tool is unavailable

When `CLAUDE_CODE_DISABLE_WORKFLOWS=1` is set (or the Workflow tool is otherwise
absent from the session), the Lead runs the same rounds by hand with the Agent
tool — N reviewers in parallel, one fixer per round, verdicts in the typed shape
— and records the SAME JSON shape (`converged`, `rounds`, `history[]`, `record`)
through `record.py record`. The declaration and the record are identical; only
the dispatcher differs. A by-hand loop that was never recorded has not
converged.

## Why this is stronger than ralph-loop

The retired ralph-loop held the turn with a Stop hook until a literal promise
string appeared in the transcript. This protocol keeps the Stop hook holding the
turn — the declared gate blocks the completion audit — but the exit is a
verified record rather than a string the model types: `converged: true` with
every reviewer `ok` in the final round, written by the record script from the
workflow's own return value. Silence is never ok (a reviewer that returns
nothing is not yet verified), a round cap is a human's `maxRounds` and pauses
rather than passes, and `history[]` is evidence the master review and the
homepage can read.

## Why a workflow and not a loop in prose

The loop is deterministic control flow: fan out, collect, decide, repeat. In
prose it drifted (round caps appeared, reviewers were sometimes asked to spawn
each other, silence was read as ok). In a script those are structurally
impossible, the verdicts are typed, and the history is returned as evidence.

## Honest boundary

The workflow proves the reviewers returned `ok`; it does not make them right.
Evidence rules apply inside each reviewer. The record proves the loop converged
and was written down; it cannot prove the artifacts are good — that is what the
tier table's independent reviewers are for.

## From the constitution stub (moved v4.1.2)

Every reviewer-convergence gate runs as DECLARE → `ct6-converge` workflow → RECORD: the gate `converge:<kind>` is declared into `declared-gates.json` first, `workflows/ct6-converge.js` dispatches N blind reviewers in parallel with one fixer per round and no self-imposed round cap, and the record script writes `.architect-team/converge/<kind>-<ts>.json` and satisfies the gate only when `converged` is true and the final round's `ok` count equals the reviewer count. The promise string is the gate's label, never the exit test; `ralph-loop` is retired. Reviewer counts follow `skills/team-spawning-and-review-gates/references/review-tiers.md` (three for a tier-3 gate, one paired reviewer for tier 2).
