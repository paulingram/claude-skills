---
name: project-principles
description: Lane-callable discipline for a project's codified principles — the rules that outlive any one run ("every service owns its own tables", "no new ORM", "test names say the behaviour"). Four verbs over one register — extract (at intake, from the project's documents, confirmed with the user before anything binds), add (the user says "codify this"), show, check (before any design, contract, diff or option set is presented, a verdict for every confirmed principle). Carries the confirmed principles in every architect and teammate brief exactly as appearance_mode is carried, tags every design option fits / violates P-xx, lets an autonomous run choose a fitting option and continue, and stops with escalation-pending.md only when every option violates. The deterministic engine lives under scripts/principles/ and this skill is its contract.
user-invocable: false
---

# project-principles

A project's principles are the rules that hold across runs. Before this skill they
lived in whichever agent happened to remember them, were re-derived in every
lane, and were silently dropped the moment a brief did not mention them. This
skill gives them a register with two twins — the machine twin
`<workspace>/.architect-team/principles.json` and the human twin
`<workspace>/docs/PROJECT_PRINCIPLES.md` rendered from it — and four cheap verbs
any lane calls. It is deliberately small: a register, a binding rule, a check.

The engine is `scripts/principles/principles.py` with the CLI
`scripts/principles/cli.py`; the Layer-3 tool is `hooks/vao/principles.py`
(`verify-principles-respected`). The field reference is
`references/principles-schema.md`. The human twin is NEVER hand-edited — every
change, by a human or an agent, goes through the CLI, which re-renders it.

## Precedence (the one rule above the others)

**The user's explicit instruction in this run > confirmed principles > CT6 defaults.**

A confirmed principle binds every agent in the run. The user's explicit
instruction in THIS run outranks it — the deviation is recorded, never argued.
CT6's own defaults (the reuse-first ladder, the testing disciplines) sit below
both: they fill the gaps a project's principles leave, they never override one.

## The four verbs

| Verb | When | What happens | User round-trip |
|---|---|---|---|
| **extract** | intake (Phase −1 / B0 / M0 / D0 / U0), once per project | candidates from the project's documents; the user confirms | ONE `AskUserQuestion` |
| **add** | the user says "codify this" / "from now on always ..." | `add` writes a user-stated, confirmed principle | none — saying it IS the confirmation |
| **show** | any lane needing the binding list; every spawn brief | the confirmed list (`brief` is the spawn-brief form) | none |
| **check** | before a design / contract / diff / option set is PRESENTED | a `principles-verdicts/v1` sidecar + `verify-principles-respected` | none, except the hard stop |

### extract — at intake, confirmed before anything binds

1. Run `scripts/principles/cli.py default-set --workspace <ws>` so the register is
   never empty: the reuse-first ladder lands as PROPOSED `P-R1`..`P-R4`.
2. Find the project's own rule-bearing documents (`CONTRIBUTING`, `ARCHITECTURE`,
   `docs/*CONVENTIONS*`, ADRs, the README's standards section) and run
   `scripts/principles/cli.py extract-candidates <file>` on each. The heuristic
   is deterministic — modal sentences (must / never / always / shall / should /
   only) and list items under principle / standard / convention / rule /
   guideline headings — and it WRITES NOTHING. Each candidate carries the
   verbatim quote and its line number.
3. `Read` the document around every candidate. The heuristic finds sentences;
   YOU judge which are principles (a durable rule of the project) and which are
   instructions, examples or prose. Draft one statement per real principle with
   its scope and keep the verbatim quote as its source.
4. ONE `AskUserQuestion` domain gate listing the drafted statements (and the
   `P-R*` defaults): confirm all / confirm some / none. The question quotes each
   source. Nothing becomes confirmed silently — a candidate the user did not
   confirm stays `proposed`, and a proposed principle does not bind.
5. `propose` each confirmed-by-user candidate with `--source extracted --file
   <path> --quote "<verbatim>"`, then `confirm` it. Record what the user said in
   the run's clarifications log.

### add — "codify this"

`scripts/principles/cli.py add --statement "<their rule>" --scope <scope> --quote
"<their words>"`. The principle is confirmed immediately: the user stating it is
the confirmation, so no second question is asked. Repeat it back in one line.

### show — and the binding rule

Every architect brief and every backend / frontend / integration / data-eng
spawn brief carries the confirmed principles, exactly as `appearance_mode` is
carried: the orchestrator runs `scripts/principles/cli.py brief --workspace <ws>`
and pastes the block verbatim under a `Confirmed project principles` heading. A
brief without the block is incomplete; `(none confirmed)` is written out, never
omitted. A teammate that finds a principle missing from its brief asks the Lead
rather than guessing.

### check — before anything is presented

Before a design, an interface contract, a diff or a set of options is presented
to the user or handed to the next lane, the producing agent writes a
`principles-verdicts/v1` sidecar beside the artifact — one verdict per confirmed
principle (`respected` / `violated` / `not-applicable`), each `violated` with
`why` and `where` — and runs:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/vao/principles.py" --workspace "<ws>" --verdicts "<sidecar>" --json
```

Exit `0` is valid, `2` is a gap list to act on, `3` is an unreadable input. The
review-gate evidence cites the verdict in the optional `principles_review` field
(`hooks/review_evidence_schema.py`: `pass` must cite the verdict path; `fail`
blocks; `n/a` with a note when the workspace has no confirmed principles).

## The option-tagging rule

When the work offers alternatives — a design with two viable shapes, an API that
could live in either service, a migration done two ways — every option is tagged
in the sidecar's `options[]`: `fits: true` or `fits: false` with `violates:
["P-xx"]` and a one-line `why`. An option is not "the cleaner one"; it fits the
confirmed principles or it names which one it breaks.

## The autonomous-run rule

In an autonomous run (`auto_mode: true`) the agent chooses a FITTING option and
continues — it does not stop to ask when an option respects every principle
(`docs/ETHOS.md` principle 5, default to action). It stops ONLY when every option
violates a confirmed principle: then it writes `escalation-pending.md` naming the
options and the principle each breaks, and asks which to relax. The tool makes
this mechanical: `chosen-option-violates` and `chosen-option-missing` are gaps,
`all-options-violate` is the hard stop. When the user chose (`auto_mode: false`),
a violating choice is theirs to make and is reported as a warning, not a gap.

A knowing violation in a design or diff is a gap (`principle-violated`) unless
the verdict quotes the user's explicit instruction in this run in
`user_override` — the precedence rule, recorded rather than remembered.

## The soft cap and retirement

The register's `soft_cap` is 15. Confirming a 16th principle SUCCEEDS and emits
`principles-cap-exceeded` in the verb's output, the check's warnings and the
rendered markdown. Fifteen rules a team can hold in its head; thirty is a policy
manual nobody consults. When the warning appears, propose merges or retirements
to the user. `retire P-xx --reason "<why>"` is the only removal — a retired
principle keeps its id and its reason, is listed by id in the markdown, and
stops binding; it is never deleted from the JSON.

## Hard rules (non-negotiable)

- Nothing becomes `confirmed` without the user: `extract` confirms through one
  `AskUserQuestion`; `add` confirms because the user stated it; `default-set`
  only proposes.
- Every architect and teammate brief carries the confirmed principles block.
- Every design / contract / diff / option set presented has a sidecar with a
  verdict for EVERY confirmed principle; a `violated` verdict has `why` + `where`.
- An autonomous run never picks a violating option while a fitting one exists,
  and never picks silently when all violate — it escalates.
- `<workspace>/docs/PROJECT_PRINCIPLES.md` is changed only through the engine CLI.
- The user's explicit instruction in this run outranks a confirmed principle;
  the deviation is recorded in `user_override`, never argued and never hidden.

## Honest boundary

The tool proves every confirmed principle was CONSIDERED and a verdict RECORDED
with a cause. It cannot prove a judgment is right: a wrong `respected` passes
`verify-principles-respected`. Catching that is the independent reviewer's job
(`docs/ETHOS.md` principle 2 — the producer is never its own checker); the
verdict sidecar is the input they read, not a substitute for reading the design.
The extraction heuristic finds sentences, not principles — the judgment is the
agent's and the confirmation is the user's.

## Relationship to other skills

- `skills/reuse-first-design` — the source of the default `P-R1`..`P-R4` set;
  a project's own principles sit above it in precedence.
- `skills/contract-first-parallelism` — the interface contract is one of the
  four `check` subjects (`kind: contract`).
- `skills/common-pipeline-conventions` — the spawn-brief manifest this skill's
  block rides in, beside `appearance_mode` and `deploy_mandate`.
- `skills/verified-agent-output` — `verify-principles-respected` is a Layer-3
  tool; `principles_review` is its review-gate field.
