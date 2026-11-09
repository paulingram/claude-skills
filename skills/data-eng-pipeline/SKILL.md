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

**superpowers is a CONDITIONAL plugin (v4.0.0; it was a hard dependency from v3.9.0 to v3.67.0).** A pre-flight check still runs as the very first action of this pipeline and resolves availability either way: (a) `~/.claude/plugins/installed_plugins.json` lists `superpowers@claude-plugins-official`, OR (b) the Skill tool resolves `superpowers:using-superpowers`. When it is present the lane uses the superpowers skills named below. When it is absent the lane does NOT abort: it prints one line naming the gap and the install remediation (`/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`), records `methodology: native` in `intake-state.json`, and runs the same disciplines in their native form per `skills/common-pipeline-conventions/references/native-methodology.md`. The same rule covers `cartographer` (native mapping fallback in that chapter) and the retired `ralph-loop`, whose job the `ct6-converge` workflow does (`skills/common-pipeline-conventions/references/converge-workflows.md`). The canonical source of truth is `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)`.

## Inputs

`$REQ_DIR` (bound by `/architect-team:data-eng`, or routed in from the main pipeline's Phase −2 when the classifier returns `kind: data-eng`) is the **data-engineering ask**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to `/architect-team`:

1. **A requirements folder** — a filesystem path resolving to a directory holding a data brief, source schemas, a business glossary, a data contract, or an OpenSpec change.
2. **A plain-language requirement** — prose typed directly: *"build the analytics warehouse dbt models"*, *"mine the billing stored procedures into a data dictionary"*. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — do NOT refuse plain-language prose, do NOT treat the first word of a sentence as a path, do NOT ask the user for a folder when prose was given. Detect the form: a single token resolving to an existing directory → form 1; otherwise → form 2. When unsure, it is form 2. The codebase the ask applies to is the cwd (a git repo) unless the prose names another path.

**Flags the `/architect-team:data-eng` command binds and this lane reads.** `--proposal-first` (pause after D1), `--appearance` (strict by nature), the commit / push / merge flags D8 reads, and — v4.0.0 — **`--full-data`**: sample-first iteration is OFF for the run. Absent the flag (the default), a transformation that targets a subset of a large table is iterated on the stratified sample plan at D2 (the Sample-first iteration section below); with it, every data step runs against the full table, no sample plan is produced or referenced, and the D8 report records the opt-out. A project principle that forbids sampling has the same effect and is named in the report.

## Dispatch mode

Per `common-pipeline-conventions` `## Dispatch mode (v1.0.0)`, the selection is computed ONCE — at the top of Phase D−1 — and persisted as `dispatch_mode` to `<workspace>/.architect-team/intake-state.json` (this lane reuses the main pipeline's `intake-state.json`); every later phase reads it to branch between teams mode and subagents mode. The primitives of each mode, the hook branching, and the Lead-only dispatch rule are spelled out in the canonical section — do not re-explain them inline.

## Cross-cutting disciplines (canonical homes, not re-explained here)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/cross-cutting-disciplines-canonical-homes-not-re-explained-h.md` and execute it in full. Do not work from memory.

- **Notifications** — the ten recognized events via `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`, opt-in (gated on `.architect-team-notify.json`) and best-effort, per `common-pipeline-conventions` `## Notifications wiring convention`. `run_start` fires once the D1 plan validates; `run_complete` is the final notification at D8.
- **In-flight clarification handling (v2.5.0)** — a mid-run user message that does not cancel and is not a fresh `/architect-team:<command>` invocation is a clarification / scope amendment to THIS run; fold it in per `common-pipeline-conventions` `## In-flight clarification discipline (v2.5.0)`. Never bypass the lane to answer it directly.
- **Phase-boundary inbox check (v2.19.0)** — at the start of every D-phase AND after every background-dispatch return, drain `<workspace>/.architect-team/inbox/<run-id>.jsonl`; D8 invokes `verify-inflight-clarifications-processed`.
- **Discipline freshness (v2.18.0)** — after the wake-up and before D−1, run the `verify-discipline-registry-current` check, auto-apply safe disciplines, route the rest as SRs. Best-effort; never blocks.
- **Background-agent resume (v1.5.0)** — route every background Agent dispatch result through `wrap_agent_result()` from `scripts/setup/agent_resume.py` before treating the work as complete.
- **Augment-never-replace precedence (v3.63.0)** — when a run arms an optional third-party capability, the armed skill operates INSIDE this lane's mandates rather than in place of them; the rule, the D0 verbatim-dispatch example, the skill-to-phase binding, and the narrow platform-safety carve-out all live in `common-pipeline-conventions` `## Augment-never-replace discipline (v3.63.0)`.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

Per `common-pipeline-conventions` `## MemPalace wake-up precondition` (which points at the canonical rule in `mempalace-integration` `## Phase A — Wake-up at pipeline start`): when this lane is invoked DIRECTLY via `/architect-team:data-eng` (not routed in from the main pipeline's Phase −2), the unscoped wake-up runs as the earliest action of this lane — before any subagent dispatch, including the D−1 intake-and-mapping flow. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback), then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. Include the wake-up output verbatim — the lane benefits from prior-context recall (past data-model explorations, past catalog rebuilds, past validation-rule verdicts). When this lane is reached via the main pipeline's Phase −2 routing, the unscoped wake-up has ALREADY run there — this section is a no-op in that case. A SECOND, wing-scoped wake-up runs from inside Phase D−1A once the wing name is discovered, regardless of entry path.

## Phase D−1 — Intake & warm-catalog-first check (REQUIRED, runs before Phase D0)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d-1.md` and execute it in full. Do not work from memory.

Two parts. **Part A (intake & mapping)** follows the `intake-and-mapping` skill verbatim — same codebase discovery (`$REQ_DIR/codebases.json` → frontmatter → cwd → ask user), same per-codebase `ct6-converge` workflow with cartographer + route-mapper + the tier-3 reviewer convergence (the `codebase-map` and `integration-map` presets, declared before and recorded after), same map-freshness rules, same integration mapping, same wing-scoped MemPalace wake-up + mining. The freshness pre-scan is non-negotiable; a data plan proposed against a stale map is worth as little as a bug fix proposed without a replication.

## Phase D0 — Exploration (dispatch `data-engineering-exploration` VERBATIM)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d0.md` and execute it in full. Do not work from memory.

The exploration is a solved problem. Dispatch the `data-engineering-exploration` skill **verbatim** — name it and invoke it (Skill tool, `skill: data-engineering-exploration`); do NOT duplicate or re-implement its 7-stage flow here. **The lane is that skill's THIRD documented caller** (alongside Phase 0c dispatch and mixed-mode); the skill runs its Stage 1–7 convergence (domain context → conceptual data model → service design → volume/velocity → data security → the mandatory validation/lineage/observability stage → OpenSpec authoring) and returns the OpenSpec change + the six `*_MAP.md` artifacts.

## Phase D1 — Planning validation (Phase 1 semantics)

Run the main pipeline's **Phase 1** planning-validation gate against the OpenSpec change the exploration authored, at the same bar as any other openspec input — `openspec validate --all --strict` reports valid, every artifact is `done`, the coverage map reaches 100% source-requirement coverage, and Reuse Decisions cite `reuse-first-design`. The data-specific binding from Phase 0c applies verbatim: **the Stage 6 validation rules become explicit acceptance criteria in the coverage map** (one acceptance criterion per validation rule per transformation), and a transformation missing its validation criterion or its lineage emission is a Phase 1 loop-failure condition. The `dev-api-integration-testing` criteria are primary for any analytics-API surface. The Phase 1 architect brief carries the confirmed project principles block (`python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace <ws>`, v4.0.0) and the plan's options are checked against the register before the plan is presented. The gate loops until green; there is no iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`). Auto-mine the validated coverage map to MemPalace, and emit the `run_start` notification once the plan validates.

## Sample-first iteration (v4.0.0)

A data change that targets a subset of a large table — a filter, a partition, an entity type, a date range, an aggregate per key — is iterated on a **stratified sample first** and run against the full data last. Default on; when `--full-data` was passed (or a project principle forbids sampling) D2 references no sample plan — every data step runs in full — and the D8 report records the opt-out and its source. Absent the flag, before the D2 implementation of such a transformation:

- **Decide** — `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/data_dictionary/sampling.py" should-sample --dictionary docs/data-dictionary.json --table <T> --json`; skip only when the dictionary POSITIVELY shows the table is small (an unknown row count keeps sampling on).
- **Plan** — `plan --table <T> --predicate <the columns the change depends on> --change-kind filter|aggregate|window|dedup|join [--reported-rows rows.json] --out <workspace>/.architect-team/data-eng/<slug>/sample-plan.json`; aggregate-level kinds keep whole groups (`group_preserving_keys`).
- **Materialize + iterate** — `sql --plan ... --dialect <engine>` into a sandbox inside the warehouse, implement against the sample, then `diff --before b.json --after a.json --plan ...` per stratum (row counts, key checksums, numeric deltas).
- **Scale** — only when the sample passes; the sample's result is the expectation the full run is checked against, and the full run stays the gate.

The rule in full — the six steps, the group-preserving rule, the opt-outs, the residency default, the honest boundaries (a sample can hide a bug; the pick is seeded and the query recorded so a reviewer reruns it) — is `references/sample-first.md`; read it before the first sample-first transformation of a run. The plan is evidence: cite it in the Phase 3 review-gate record like any other artifact. `verification-planning` lists the stratified sample as a venue, and the bug-fix lane uses the same plan for a data defect.

## Phase D2–D6 — Implement, review, and verify (Phases 2–6 verbatim)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d2.md` and execute it in full. Do not work from memory.

Phases **D2 through D6 are the main pipeline's Phases 2–6 run verbatim** — the parallel team spawn (Phase 2), the Phase 3 paired review gate, Phase 4 reconciliation, and Phase 5 cross-layer integration + Phase 6 verification. Nothing about the evidence stack is relaxed for a data-engineering slice:

## Phase D7 — Catalog refresh (the second new discipline)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d7.md` and execute it in full. Do not work from memory.

After the transformation lands and passes D2–D6, refresh the catalog so the next run starts warm. This is the symmetric partner of D−1's warm-catalog-first check — D−1 reads the catalog, D7 rewrites it.

## Phase D8 — Close-out (Phase 8 verbatim)

> **STOP.** Before acting under this section, Read `skills/data-eng-pipeline/references/phase-d8.md` and execute it in full. Do not work from memory.

Phase **D8 is the main pipeline's Phase 8 close-out run verbatim** — the documentation-currency gate FIRST (the `doc-updater` agent dispatch + the independent `system-architect` Documentation Currency Audit per `documentation-currency`; the audit verdict, not a self-report, gates the commit), then the completion-audit gate, the default-branch guard, the delivery manifest (the bill of sale, per `delivery-manifest`), the commit with the standard message template, and the push. Auto-merge to main (`--no-auto-merge` opts out) when the completion audit passed and the work is on `architect-team/<slug>`; a conflict falls back to a PR, never `--force`. The human-authored `.architect-team-deploy.json` dev→test→prod opt-in is honored exactly as the main pipeline honors it (and is immutable to agents). Mark the run complete via `hooks/run_continuity.py --mark-complete` as the last state action, emit `run_complete` with the delivery manifest embedded, and emit the auto-compact prompt (unless `--no-compact`).

## Relationship to other skills

- `architect-team-pipeline` (sibling) — same orchestration discipline; the lane reuses Phases 1, 2–6, and 8 by reference. Reached via `/architect-team:data-eng` (explicit), `--data-eng`, or the main pipeline's Phase −2 triage when the classifier returns `kind: data-eng`. See `architect-team-pipeline` `## Data-eng lane precedence` for how the front-door lane and Phase 0c mid-flow dispatch interact.
- `bug-fix-pipeline` (sibling) — the template this lane is built on; same "reuse the main pipeline's structural points rather than duplicating them" shape.
- `data-engineering-exploration` (Phase D0) — dispatched verbatim; the lane is its third documented caller.
- `intake-and-mapping` (Phase D−1A) — reused verbatim. Same maps, same freshness rules.
- `data-dictionary` (Phase D−1B, D7) — the deterministic dictionary engine's contract; consulted at D−1 (via the knowledge server) and rebuilt at D7.
- `data-lineage-mapping` (Phase D2–D6) — every transformation's lineage emission traces to this discipline.
- `documentation-currency` (Phase D8) — the doc-currency gate before the auto-commit, same as the main pipeline. The D8 commit is authored as the checkout's RECORDED person per `common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)` (the `git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=` pair) — never a default author.

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
