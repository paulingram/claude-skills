# Augment-never-replace discipline (v3.63.0)

The canonical home of the conditional-capability precedence rule. `common-pipeline-conventions` `## Augment-never-replace discipline (v3.63.0)` carries the operative statement; this file carries the full rules, the reviewed skill-to-phase binding, and the conflict record. Work from this file, never from memory.

## The rule

**A conditionally-armed third-party skill runs INSIDE a CT6 mandate, never instead of it.** CT6 can arm an optional external capability for a run when the target project's trait says it applies — today that is the `bauplan` plugin's six lakehouse skills, armed off the `bauplan_project.yml` marker that `_has_bauplan_markers` detects in `hooks/discipline_registry.py`, with the plugin itself reported (never gated) by the conditional-dependency tier in `scripts/setup/setup.py`. Arming changes what a phase **reaches for**. It never changes what a phase **requires**.

## The canonical example — the D0 verbatim dispatch survives

`skills/data-eng-pipeline/SKILL.md:74` (Phase D0) dispatches `data-engineering-exploration` **VERBATIM**. On an armed Bauplan run that dispatch is unchanged: the exploration still runs its Stage 1–7 convergence and still returns the OpenSpec change plus its `*_MAP.md` artifacts. An armed bauplan skill *enriches* that dispatch — real lakehouse schemas in its `codebase_inputs`, real branch state in its Stage 2 conceptual model, the Stage 6 blocker rule emitted as executable `expectations.py` — and it never stands in for it. *"The bauplan skill already explored the data"* is not a reason to skip the dispatch; it is the reason the dispatch has better inputs.

## No gate is relaxed, in either direction

The evidence an armed run produces is identical in shape to an unarmed one: the Phase 3 paired review gate still requires all 17 schema v7 fields plus the independent `independent_review` and `adversarial_review` verdicts; the D2–D6 data acceptance bar (≥ 1 blocker-severity validation rule + a lineage emission per transformation) still holds; the Phase 8 / B8 / D8 close-out gates still run. A conditional capability that would only pay off if a CT6 check were waived is not paying off — route the tension as a solution requirement and let the normal loop settle it, per `## No pipeline-bypass discipline (v2.22.0)`.

## Platform safety rules win on their own operations — and the conflict is recorded

Where an armed platform's safety rules conflict with a CT6 default on an operation belonging to that platform — a lakehouse write, a branch-and-merge publish, an ingestion commit — **the platform's rule governs**. Bauplan's *never write or import directly to `main`; branch and merge to publish* beats any CT6 default that would write straight through, because the CT6 default was written without knowledge of the platform's write model and the platform's rule is the one protecting real data.

The precedence is deliberately narrow: it covers the platform's own operations, **never CT6's process gates**. A bauplan skill cannot override the review gate, the completion audit, or the documentation-currency gate — those are not lakehouse operations.

Every such conflict is **recorded, not silently resolved** — appended as a `precedence_conflicts[]` entry to the run's Bauplan dispatch record (`<workspace>/.architect-team/data-eng/<slug>/bauplan-dispatches.json` in the data-eng lane; `<workspace>/.architect-team/bug-fix/<bug-slug>/bauplan-dispatches.json` in the bug-fix lane) and surfaced in the final report:

```json
{
  "conflict_id": "PC-1",
  "ct6_default": "<the CT6 default the run would otherwise have applied>",
  "platform_rule": "<the platform safety rule that governs instead>",
  "operation": "<the lakehouse operation the conflict arose on>",
  "resolution": "platform-rule-governs",
  "phase": "<D2-D6 | B5 | ...>",
  "timestamp": "<ISO 8601 UTC>"
}
```

An unrecorded precedence override is the `## Unilateral-override discipline (v3.0.0) — META` failure mode wearing a platform's name: the run made a call the user cannot see. Recording it costs one append.

## The skill-to-phase binding (the reviewed injection surface)

Injection happens at the **lane** level, not in the agents. The agent-boilerplate compiler (`scripts/setup/sync_agent_boilerplate.py`) is unconditional by construction, so a Bauplan block there would ship lakehouse instructions into all 39 agents on every run, Bauplan or not — context pollution in the overwhelming majority of runs, and the wrong altitude besides (an agent file is a role definition; *how to work with a particular data platform* is not a property of the backend role). A lane body is loaded only when its lane runs, so a pointer there is already conditional at the coarse level, and the arming check makes it conditional at the fine level. The phase structure is also what carries the *mapping* — a bauplan skill is right at a **specific phase**, not in general.

| bauplan skill | CT6 phase | Why this phase |
|---|---|---|
| `bauplan-explore-data` | data-eng D−1 (intake) / D0 (exploration) | Read-only lakehouse inspection is exactly what exploration needs; it replaces guessing at schemas with reading them |
| `bauplan-data-assessment` | data-eng D0 (exploration), D1 (planning validation) | *"Can this question be answered with the available data"* is a feasibility input to the plan, owed BEFORE commitments are made |
| `bauplan-data-pipeline` | data-eng D2–D6 (implement) | Project scaffolding and model authoring is implementation work; it is also the greenfield path, reachable on stated intent when no marker can yet exist |
| `bauplan-safe-ingestion` | data-eng D2–D6 (implement) | Ingestion is a transformation; write-audit-publish is how it lands safely |
| `bauplan-data-quality-checks` | data-eng D0 **Stage 6**, D2–D6 (implement) | Stage 6 already mandates ≥ 1 blocker-severity validation rule per transformation; this skill emits exactly that as `expectations.py`. The strongest single fit in the surface — the standing requirement and its emitter meet |
| `bauplan-debug-and-fix-pipeline` | bug-fix B1 (replicate) → B6 (QA replay) | Its own contract is evidence-first — pin the data state, collect evidence, minimal fix, rerun — which is the bug-fix lane's shape already |

**Every pointer is gated on the arming result.** An unarmed run reads no Bauplan instruction at all: each pointer's guard is the arming verdict recorded at intake, and when that verdict is not armed the phase proceeds exactly as it does today. That conditionality is the whole point — a pointer written as unconditional prose is a defect, not a shortcut.

## Warn and degrade — never silently

**When the project is Bauplan-shaped but the plugin is absent, the run degrades and SAYS SO.** Proceed on the generic CT6 path, and name the missed capability plus its remediation (`/plugin marketplace add BauplanLabs/bauplan-skills`, then `/plugin install bauplan@bauplan-skills`) in the run report. Silence is the failure — a degraded run that reads like a correctly-scoped one is exactly the honest-boundary violation this stack exists to prevent.

The lakehouse safety context still reaches the target project on this path: its guidance block keys on the project marker rather than on plugin presence (`scripts/setup/guidance_blocks.py`), precisely because those rules matter most when the plugin that would otherwise enforce them is missing.

## Cross-references

- `skills/data-eng-pipeline/SKILL.md` — the D−1 Part C arming check and the D0 / D2–D6 pointers.
- `skills/data-engineering-exploration/SKILL.md` `## Stage 6` — the quality-checks pointer, framed as the emitter of the blocker rule Stage 6 already mandates.
- `skills/bug-fix-pipeline/SKILL.md` `## Phase B1` — the replicate/diagnose pointer.
- `hooks/discipline_registry.py` — `_has_bauplan_markers`, the deterministic marker detector.
- `scripts/bauplan/arming.py` — `resolve_bauplan_arming`, the pure arming decision returning `{armed, signal, requires_confirmation, disposition}`. The confirmation it reports on the inferred path is a DOMAIN gate: it fires regardless of any process-gate opt-out, because the user's answer determines what gets built.

## The arming verdict vocabulary

`armed` is the gate — a pointer fires **iff** `armed` is true. `requires_confirmation` true means the run still owes the user its one confirmation **before the first bauplan-specific dispatch**. The two are never both true: a run is either cleared to dispatch or still owes the question. A detected marker arms **silently** whatever the stated intent says — no confirmation is ever surfaced on that path, so no answer carried in from elsewhere can disarm a trait proven on disk.

| field | values |
|---|---|
| `armed` | `true` / `false` — the gate every lane pointer reads |
| `signal` | `marker` / `intent` / `none` (constants `SIGNAL_MARKER` / `SIGNAL_INTENT` / `SIGNAL_NONE`) |
| `requires_confirmation` | `true` / `false` — the run owes one confirmation before any bauplan dispatch |
| `disposition` | `armed-by-marker` / `awaiting-confirmation` / `armed-by-confirmed-intent` / `declined` / `not-armed-no-signal` (constants `DISPOSITION_*`) |

`disposition` is what the run report prints verbatim, so a declined or degraded run always names what happened rather than staying silent.
- `scripts/setup/setup.py` — the conditional-dependency tier: detected, reported, remediated, never a gate.
- `scripts/setup/guidance_blocks.py` — the trait-keyed safety-context block (marker, not plugin presence).
