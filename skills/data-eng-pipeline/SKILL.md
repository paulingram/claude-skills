---
name: data-eng-pipeline
description: Use when a data-engineering ask should be driven end-to-end as a first-class lane — build the warehouse dbt models, mine the stored procedures into a data dictionary, design the Airflow pipeline — faster than the full architect-team-pipeline but with the same rigor where it matters. A sibling orchestrator playbook (like bug-fix-pipeline) whose phases D−1 through D8 reuse the main pipeline's structural points rather than duplicating them; D0 dispatches data-engineering-exploration verbatim (the lane is its third caller), D2–D6 run Phases 2–6 verbatim (the full evidence stack), and the two new disciplines are the D−1 warm-catalog-first check (query the Run A knowledge server plus its freshness verdict before a rebuild) and the D7 catalog-refresh (rebuild the dictionary, re-index the server, mine to MemPalace, leaving the catalog warm). Accepts the same two input forms as architect-team — a requirements folder OR plain-language prose typed directly.
user-invocable: false
---

# data-eng-pipeline

The `architect-team-pipeline` is excellent for greenfield features and substantial new capability work; the `bug-fix-pipeline` is the tight replicate→propose→fix→replay loop for a known defect. Neither is shaped for the *data plane* — a warehouse to model, a dbt project to build, a set of stored procedures to mine into a data dictionary, a streaming pipeline to design and validate. Those asks have their own front-door discipline (check the warm catalog before you rebuild it) and their own close-out discipline (leave the catalog warm for the next run), and a warehouse transformation's acceptance bar (every transformation ships its validation rule and its lineage emission) is not a feature's bar.

The `data-eng-pipeline` is the first-class **data-engineering lane** — a sibling to `bug-fix-pipeline`, reached at the front door when the Phase −2 classifier returns `kind: data-eng` (or via `/architect-team:data-eng` / `--data-eng`). It keeps the discipline that matters (maps must be fresh; the plan must validate; the evidence stack is non-negotiable; docs ship current) and adds exactly **two new disciplines** — the D−1 warm-catalog-first check and the D7 catalog-refresh — wired to the Run A knowledge server (`services/knowledge_server/`, installed via `/architect-team:knowledge-install`) and the `scripts/data_dictionary/data_dictionary.py` engine.

You are the **Team Lead** for the data-engineering variant. Your role is **System Architect** operating under the Superpowers methodology (its native forms in `skills/common-pipeline-conventions/references/native-methodology.md` when that CONDITIONAL plugin is absent). You coordinate the D−1…D8 flow that takes a data-engineering ask — a folder of artifacts OR a plain-language description typed directly — and drives it to tested, integrated, catalog-warm production code.

<!-- ct6:block:principles:begin -->
## Operating principles

CT6 work is governed by eight load-bearing principles. The full statements — each with its named anti-pattern — live in `docs/ETHOS.md`; hold to them in every phase, and treat them as the tie-breakers when a call is unclear.

- **Reuse before build.** Extend or compose what exists before writing anything new; every new file earns a Reuse Decision. Anti-pattern: the greenfield reflex.
- **The producer is never its own checker.** Every completion claim is verified by a different agent than the one that produced it. Anti-pattern: self-attestation.
- **Honest boundary.** Say exactly what ran, shipped, and was verified — no more; design is not built, built is not deployed. Anti-pattern: the overclaim.
- **Unbounded solving.** Loop until the gate is green; never hand back a half-finished run on an iteration count. Anti-pattern: the arbitrary stop.
- **Default to action.** Gates are opt-in; on reversible work, pick the sensible default and proceed. Anti-pattern: permission-seeking.
- **Documentation currency.** Docs ship current or the run does not ship. Anti-pattern: the stale grid.
- **Evidence before assertion.** State a result only after running the check and reading its output. Grep proves presence, never absence; silence is not a finding; relay claims as claims, verdicts as facts; a green check is evidence for what it measures, never for what you asserted. Anti-pattern: the unverified "should work".
- **Understand before acting.** Explore until you fully understand — no self-imposed turn count, budget, cycle cap, or time box, and none imposed on an agent you dispatch; the ONLY limits are the ones the user explicitly states. Anti-pattern: the self-rationed investigation.

See `docs/ETHOS.md` for the full text.
<!-- ct6:block:principles:end -->

## Plugin prerequisites (v3.9.0)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/plugin-prerequisites.md` and execute it in full. Do not work from memory.

`superpowers` and `cartographer` are CONDITIONAL plugins: the pre-flight check runs first and resolves availability, and an absent plugin degrades to the native forms in `skills/common-pipeline-conventions/references/native-methodology.md` instead of aborting the run.

## Inputs

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/inputs.md` and execute it in full. Do not work from memory.

`$REQ_DIR` is the data-engineering ask in ONE of two first-class forms -- a requirements folder OR plain-language prose -- never refused, never read as a path, never traded for a folder; the chapter also names the flags this lane reads, including `--full-data`.

## Dispatch mode

Per `common-pipeline-conventions` `## Dispatch mode (v1.0.0)`, the selection is computed ONCE — at the top of Phase D−1 — and persisted as `dispatch_mode` to `<workspace>/.architect-team/intake-state.json` (this lane reuses the main pipeline's `intake-state.json`); every later phase reads it to branch between teams mode and subagents mode. The primitives of each mode, the hook branching, and the Lead-only dispatch rule are spelled out in the canonical section — do not re-explain them inline.

## Cross-cutting disciplines (canonical homes, not re-explained here)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/cross-cutting-disciplines-canonical-homes-not-re-explained-h.md` and execute it in full. Do not work from memory.

Notifications, in-flight clarification handling, the phase-boundary inbox check, discipline freshness, background-agent resume and augment-never-replace all apply to this lane from their canonical homes in `common-pipeline-conventions`.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` and execute it in full. Do not work from memory.

When this lane is invoked DIRECTLY via `/architect-team:data-eng`, the unscoped `mempalace wake-up` runs as its earliest action, before any subagent dispatch; routed in from Phase -2 it has already run, and a wing-scoped wake-up follows inside Phase D-1A either way.

## Phase D−1 — Intake & warm-catalog-first check (REQUIRED, runs before Phase D0)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d-1.md` and execute it in full. Do not work from memory.

Part A follows `intake-and-mapping` verbatim (the tier-3 `ct6-converge` map convergence, declared before and recorded after); Part B queries the warm catalog and its freshness verdict before any rebuild.

## Phase D0 — Exploration (dispatch `data-engineering-exploration` VERBATIM)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d0.md` and execute it in full. Do not work from memory.

Dispatch the `data-engineering-exploration` skill verbatim (Skill tool, `skill: data-engineering-exploration`); the lane is its third documented caller and never re-implements its 7-stage flow.

## Phase D1 — Planning validation (Phase 1 semantics)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d1.md` and execute it in full. Do not work from memory.

Run the main pipeline's Phase 1 planning-validation gate against the exploration's OpenSpec change, with every Stage 6 validation rule bound as an explicit acceptance criterion; the gate loops until green.

## Sample-first iteration (v4.0.0)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/sample-first.md` and execute it in full. Do not work from memory.

A data change that targets a subset of a large table is iterated on a stratified sample first and run against the full data last; `--full-data` (or a forbidding project principle) turns it off and the D8 report records the opt-out. Before the D2 implementation of such a transformation:

- **Decide** -- `scripts/data_dictionary/sampling.py should-sample --dictionary docs/data-dictionary.json --table <T> --json`; an unknown row count keeps sampling on.
- **Plan** -- `plan --table <T> --predicate <cols> --change-kind filter|aggregate|window|dedup|join --out <ws>/.architect-team/data-eng/<slug>/sample-plan.json`; aggregate kinds keep whole groups (`group_preserving_keys`).
- **Materialize + iterate** -- `sql --plan ... --dialect <engine>` into a warehouse sandbox, implement against the sample, then `diff --before b.json --after a.json --plan ...` per stratum.
- **Scale** -- only when the sample passes; the full run stays the gate, and the plan is cited as evidence in the Phase 3 review-gate record.

## Phase D2–D6 — Implement, review, and verify (Phases 2–6 verbatim)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d2.md` and execute it in full. Do not work from memory.

Phases D2 through D6 are the main pipeline's Phases 2-6 run verbatim; nothing about the evidence stack is relaxed for a data-engineering slice.

## Phase D7 — Catalog refresh (the second new discipline)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d7.md` and execute it in full. Do not work from memory.

After the transformation lands, rebuild the dictionary, re-index the knowledge server and mine to MemPalace so the next run starts warm -- the symmetric partner of D-1.

## Phase D8 — Close-out (Phase 8 verbatim)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d8.md` and execute it in full. Do not work from memory.

Phase D8 is the main pipeline's Phase 8 close-out run verbatim: the doc-currency gate first, the completion audit, the delivery manifest, the full suite once, the recorded-identity commit, the push, and the auto-merge.

## Relationship to other skills

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/relationship-to-other-skills.md` and execute it in full. Do not work from memory.

This lane reuses `architect-team-pipeline` Phases 1, 2-6 and 8 by reference, `bug-fix-pipeline`'s shape, `data-engineering-exploration` at D0, `intake-and-mapping` at D-1A, `data-dictionary` at D-1B / D7, `data-lineage-mapping` at D2-D6, and `documentation-currency` at D8.

## Same input forms as architect-team-pipeline

This lane's input rules are IDENTICAL to `architect-team-pipeline`'s — folder OR plain-language prose, both first-class; never refuse prose; never treat the first word of a sentence as a path; ask only when input is genuinely empty (*"What data-engineering work should the lane build?"* — NOT *"give me a requirements folder"*). When the input is plain-language prose, the codebase the ask applies to is the cwd unless the prose names another path.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Cross-cutting disciplines (canonical homes, not re-explained here)` | `skills/data-eng-pipeline/references/cross-cutting-disciplines-canonical-homes-not-re-explained-h.md` | on demand |
| `Phase D−1 — Intake & warm-catalog-first check (REQUIRED, runs before Phase D0)` | `skills/data-eng-pipeline/references/phase-d-1.md` | on demand |
| `Phase D0 — Exploration (dispatch `data-engineering-exploration` VERBATIM)` | `skills/data-eng-pipeline/references/phase-d0.md` | on demand |
| `Phase D2–D6 — Implement, review, and verify (Phases 2–6 verbatim)` | `skills/data-eng-pipeline/references/phase-d2.md` | on demand |
| `Phase D7 — Catalog refresh (the second new discipline)` | `skills/data-eng-pipeline/references/phase-d7.md` | on demand |
| `Phase D8 — Close-out (Phase 8 verbatim)` | `skills/data-eng-pipeline/references/phase-d8.md` | on demand |
| `Sample-first iteration (v4.0.0)` | `skills/data-eng-pipeline/references/sample-first.md` | on demand |
| `Plugin prerequisites (v3.9.0)` | `skills/data-eng-pipeline/references/plugin-prerequisites.md` | on demand |
| `Inputs` | `skills/data-eng-pipeline/references/inputs.md` | on demand |
| `MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)` | `skills/data-eng-pipeline/references/mempalace-wake-up-required-runs-before-any-subagent-dispatch.md` | on demand |
| `Phase D1 — Planning validation (Phase 1 semantics)` | `skills/data-eng-pipeline/references/phase-d1.md` | on demand |
| `Relationship to other skills` | `skills/data-eng-pipeline/references/relationship-to-other-skills.md` | on demand |
