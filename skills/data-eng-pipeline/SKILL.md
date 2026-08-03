---
name: data-eng-pipeline
description: Use when a data-engineering ask should be driven end-to-end as a first-class lane — build the warehouse dbt models, mine the stored procedures into a data dictionary, design the Airflow pipeline — faster than the full architect-team-pipeline but with the same rigor where it matters. A sibling orchestrator playbook (like bug-fix-pipeline) whose phases D−1 through D8 reuse the main pipeline's structural points rather than duplicating them; D0 dispatches data-engineering-exploration verbatim (the lane is its third caller), D2–D6 run Phases 2–6 verbatim (the full evidence stack), and the two new disciplines are the D−1 warm-catalog-first check (query the Run A knowledge server plus its freshness verdict before a rebuild) and the D7 catalog-refresh (rebuild the dictionary, re-index the server, mine to MemPalace, leaving the catalog warm). Accepts the same two input forms as architect-team — a requirements folder OR plain-language prose typed directly.
---

# data-eng-pipeline

The `architect-team-pipeline` is excellent for greenfield features and substantial new capability work; the `bug-fix-pipeline` is the tight replicate→propose→fix→replay loop for a known defect. Neither is shaped for the *data plane* — a warehouse to model, a dbt project to build, a set of stored procedures to mine into a data dictionary, a streaming pipeline to design and validate. Those asks have their own front-door discipline (check the warm catalog before you rebuild it) and their own close-out discipline (leave the catalog warm for the next run), and a warehouse transformation's acceptance bar (every transformation ships its validation rule and its lineage emission) is not a feature's bar.

The `data-eng-pipeline` is the first-class **data-engineering lane** — a sibling to `bug-fix-pipeline`, reached at the front door when the Phase −2 classifier returns `kind: data-eng` (or via `/architect-team:data-eng` / `--data-eng`). It keeps the discipline that matters (maps must be fresh; the plan must validate; the evidence stack is non-negotiable; docs ship current) and adds exactly **two new disciplines** — the D−1 warm-catalog-first check and the D7 catalog-refresh — wired to the Run A knowledge server (`services/knowledge_server/`, installed via `/architect-team:knowledge-install`) and the `scripts/data_dictionary/data_dictionary.py` engine.

You are the **Team Lead** for the data-engineering variant. Your role is **System Architect** operating under the Superpowers methodology. You coordinate the D−1…D8 flow that takes a data-engineering ask — a folder of artifacts OR a plain-language description typed directly — and drives it to tested, integrated, catalog-warm production code.

<!-- ct6:block:principles:begin -->
## Operating principles

CT6 work is governed by seven load-bearing principles. The full statements — each with its named anti-pattern — live in `docs/ETHOS.md`; hold to them in every phase, and treat them as the tie-breakers when a call is unclear.

- **Reuse before build.** Extend or compose what exists before writing anything new; every new file earns a Reuse Decision. Anti-pattern: the greenfield reflex.
- **The producer is never its own checker.** Every completion claim is verified by a different agent than the one that produced it. Anti-pattern: self-attestation.
- **Honest boundary.** Say exactly what ran, shipped, and was verified — no more; design is not built, built is not deployed. Anti-pattern: the overclaim.
- **Unbounded solving.** Loop until the gate is green; never hand back a half-finished run on an iteration count. Anti-pattern: the arbitrary stop.
- **Default to action.** Gates are opt-in; on reversible work, pick the sensible default and proceed. Anti-pattern: permission-seeking.
- **Documentation currency.** Docs ship current or the run does not ship. Anti-pattern: the stale grid.
- **Evidence before assertion.** State a result only after running the check and reading its output. Grep proves presence, never absence; silence is not a finding; relay claims as claims, verdicts as facts. Anti-pattern: the unverified "should work".

See `docs/ETHOS.md` for the full text.
<!-- ct6:block:principles:end -->

## Plugin prerequisites (v3.9.0)

**superpowers is a HARD dependency** — the same pre-flight check the other pipelines run fires as the very first action of this lane, BEFORE the MemPalace wake-up, and ABORTS the run if superpowers is unavailable (resolve via `~/.claude/plugins/installed_plugins.json` OR the Skill tool resolving `superpowers:using-superpowers`). The canonical rule is `common-pipeline-conventions/SKILL.md` `## Uniform plugin usage (v3.9.0)` — do not silently degrade to a methodology-by-hand fallback. This lane concretely invokes `superpowers:brainstorming` (D1 planning), `superpowers:test-driven-development` (D2–D6 implement), `superpowers:systematic-debugging` (D2–D6 diagnosis), and `superpowers:verification-before-completion` (D2–D6 review + D8 close-out). User `CLAUDE.md` / `AGENTS.md` instructions take precedence over any superpowers default.

## Inputs

`$REQ_DIR` (bound by `/architect-team:data-eng`, or routed in from the main pipeline's Phase −2 when the classifier returns `kind: data-eng`) is the **data-engineering ask**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to `/architect-team`:

1. **A requirements folder** — a filesystem path resolving to a directory holding a data brief, source schemas, a business glossary, a data contract, or an OpenSpec change.
2. **A plain-language requirement** — prose typed directly: *"build the analytics warehouse dbt models"*, *"mine the billing stored procedures into a data dictionary"*. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — do NOT refuse plain-language prose, do NOT treat the first word of a sentence as a path, do NOT ask the user for a folder when prose was given. Detect the form: a single token resolving to an existing directory → form 1; otherwise → form 2. When unsure, it is form 2. The codebase the ask applies to is the cwd (a git repo) unless the prose names another path.

## Dispatch mode

Per `common-pipeline-conventions` `## Dispatch mode (v1.0.0)`, the selection is computed ONCE — at the top of Phase D−1 — and persisted as `dispatch_mode` to `<workspace>/.architect-team/intake-state.json` (this lane reuses the main pipeline's `intake-state.json`); every later phase reads it to branch between teams mode and subagents mode. The primitives of each mode, the hook branching, and the Lead-only dispatch rule are spelled out in the canonical section — do not re-explain them inline.

## Cross-cutting disciplines (canonical homes, not re-explained here)

- **Notifications** — the ten recognized events via `${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py`, opt-in (gated on `.architect-team-notify.json`) and best-effort, per `common-pipeline-conventions` `## Notifications wiring convention`. `run_start` fires once the D1 plan validates; `run_complete` is the final notification at D8.
- **In-flight clarification handling (v2.5.0)** — a mid-run user message that does not cancel and is not a fresh `/architect-team:<command>` invocation is a clarification / scope amendment to THIS run; fold it in per `common-pipeline-conventions` `## In-flight clarification discipline (v2.5.0)`. Never bypass the lane to answer it directly.
- **Phase-boundary inbox check (v2.19.0)** — at the start of every D-phase AND after every background-dispatch return, drain `<workspace>/.architect-team/inbox/<run-id>.jsonl`; D8 invokes `verify-inflight-clarifications-processed`.
- **Discipline freshness (v2.18.0)** — after the wake-up and before D−1, run the `verify-discipline-registry-current` check, auto-apply safe disciplines, route the rest as SRs. Best-effort; never blocks.
- **Background-agent resume (v1.5.0)** — route every background Agent dispatch result through `wrap_agent_result()` from `scripts/setup/agent_resume.py` before treating the work as complete.

## MemPalace wake-up (REQUIRED — runs before ANY subagent dispatch)

Per `common-pipeline-conventions` `## MemPalace wake-up precondition` (which points at the canonical rule in `mempalace-integration` `## Phase A — Wake-up at pipeline start`): when this lane is invoked DIRECTLY via `/architect-team:data-eng` (not routed in from the main pipeline's Phase −2), the unscoped wake-up runs as the earliest action of this lane — before any subagent dispatch, including the D−1 intake-and-mapping flow. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback), then `mempalace --palace "<workspace>/.mempalace/palace" wake-up`. Include the wake-up output verbatim — the lane benefits from prior-context recall (past data-model explorations, past catalog rebuilds, past validation-rule verdicts). When this lane is reached via the main pipeline's Phase −2 routing, the unscoped wake-up has ALREADY run there — this section is a no-op in that case. A SECOND, wing-scoped wake-up runs from inside Phase D−1A once the wing name is discovered, regardless of entry path.

## Phase D−1 — Intake & warm-catalog-first check (REQUIRED, runs before Phase D0)

Two parts. **Part A (intake & mapping)** follows the `intake-and-mapping` skill verbatim — same codebase discovery (`$REQ_DIR/codebases.json` → frontmatter → cwd → ask user), same per-codebase ralph loop with cartographer + route-mapper + 3-reviewer convergence, same map-freshness rules, same integration mapping, same wing-scoped MemPalace wake-up + mining. The freshness pre-scan is non-negotiable; a data plan proposed against a stale map is worth as little as a bug fix proposed without a replication.

**Part B (the warm-catalog-first check — the first new discipline).** BEFORE considering a data-dictionary rebuild, query the Run A knowledge server (`services/knowledge_server/`, installed via `/architect-team:knowledge-install`) for the dictionary and its freshness verdict. Call the server's `get_dictionary_status` tool — it returns `built_at`, a `repo_side` reference-file drift verdict, a `db_side` currency arm, `reference_file_count`, and the `freshness` envelope (`{verdict: current | stale | unknowable, basis: [...]}`). Record the returned verdict into the run's inputs at `<workspace>/.architect-team/data-eng/<slug>/warm-catalog-check.json`.

This is deng's *"check the catalog, not the database"* discipline — but with a precise division of authority: **the server's freshness verdict INFORMS; the per-run gate DECIDES.** A `current` verdict is a strong signal the existing dictionary can be reused as-is (skip the rebuild, cite the warm catalog as the model of record); a `stale` verdict is a strong signal a D7 rebuild is warranted; but neither the server verdict alone decides — the D1 plan's own acceptance criteria (does THIS ask touch tables the dictionary already covers, at the grain it records?) make the final call. The server never overrides the run; it saves the run from rebuilding a catalog that is already warm.

**No-connection honesty (carried from Run A).** If the knowledge server is not installed or not reachable, degrade gracefully: record `freshness: {verdict: unknowable}` and proceed to build the dictionary from scratch at D7. And regardless of connection, the DB-currency arm is `unknowable` without a live database connection — the reference-file (repo-side) drift arm can say the code touching the dictionary's tables changed, but whether the underlying data itself drifted is **unknowable** without a live connection. State that boundary plainly in the warm-catalog-check record and in the final report; never imply the catalog is verified current against the live database when only the repo side was checked.

## Phase D0 — Exploration (dispatch `data-engineering-exploration` VERBATIM)

The exploration is a solved problem. Dispatch the `data-engineering-exploration` skill **verbatim** — name it and invoke it (Skill tool, `skill: data-engineering-exploration`); do NOT duplicate or re-implement its 7-stage flow here. **The lane is that skill's THIRD documented caller** (alongside Phase 0c dispatch and mixed-mode); the skill runs its Stage 1–7 convergence (domain context → conceptual data model → service design → volume/velocity → data security → the mandatory validation/lineage/observability stage → OpenSpec authoring) and returns the OpenSpec change + the six `*_MAP.md` artifacts.

Pass the structured `inputs` object the exploration expects (`request_summary`, `codebase_inputs`, `doc_inputs`, `upstream_api_contract_path`, `output_dir`, `openspec_change_name`, `data_eng_classification`, `completion_promise`), populated from the D−1 intake + the warm-catalog-check record. On return, the exploration's Stage 6 validation rules and its lineage plan are binding inputs to D1 — every validation rule becomes a Phase 1 acceptance criterion, every transformation carries its lineage emission.

**SQL-object mining (additive — runs only when SQL objects are in scope).** When the ask's scope includes stored procedures / views / functions — a warehouse to mine, procs named in the brief, `.sql` files in `$REQ_DIR` or the codebase — invoke the `warehouse-sql-mining` engine (`scripts/sql_mining/sql_mining.py mine <dir-or-files>`) BEFORE the exploration converges its conceptual model, and supply the mined join / filter / metric evidence and the table read/write relationships as `data-engineering-exploration` Stage 2–3 input so those stages reason over real extracted shapes rather than guesses. Every mined field/metric candidate is corroboration-gated — it enters the dictionary at provenance `inference` and passes `corroborate_definition` (`scripts/data_dictionary/data_dictionary.py`); the mined relationships are `data_asset` + `reads`/`writes` lineage evidence using only existing kinds (`hooks/lineage_graph.py`). Record the miner's parse-coverage stats (parsed / skipped / failed, each with a reason) in the run inputs — a skipped or failed object is surfaced, never assumed away, and the contract is `warehouse-sql-mining`. **A data-eng run with no SQL objects in scope is unchanged** — this step is a no-op when there is nothing to mine, and the exploration dispatch proceeds exactly as before.

## Phase D1 — Planning validation (Phase 1 semantics)

Run the main pipeline's **Phase 1** planning-validation gate against the OpenSpec change the exploration authored, at the same bar as any other openspec input — `openspec validate --all --strict` reports valid, every artifact is `done`, the coverage map reaches 100% source-requirement coverage, and Reuse Decisions cite `reuse-first-design`. The data-specific binding from Phase 0c applies verbatim: **the Stage 6 validation rules become explicit acceptance criteria in the coverage map** (one acceptance criterion per validation rule per transformation), and a transformation missing its validation criterion or its lineage emission is a Phase 1 loop-failure condition. The `dev-api-integration-testing` criteria are primary for any analytics-API surface. The gate loops until green; there is no iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`). Auto-mine the validated coverage map to MemPalace, and emit the `run_start` notification once the plan validates.

## Phase D2–D6 — Implement, review, and verify (Phases 2–6 verbatim)

Phases **D2 through D6 are the main pipeline's Phases 2–6 run verbatim** — the parallel team spawn (Phase 2), the Phase 3 paired review gate, Phase 4 reconciliation, and Phase 5 cross-layer integration + Phase 6 verification. Nothing about the evidence stack is relaxed for a data-engineering slice:

- **Phase 2 — parallel implementation.** The Lead spawns backend / data teammates with non-overlapping file scope per `team-spawning-and-review-gates`. Transformations (dbt models, Airflow tasks, stream processors, warehouse DDL) are implemented against the design the exploration produced and D1 approved.
- **Phase 3 — the paired review gate.** Every teammate writes the schema v7 review-gate evidence (the 17 required fields including `real_not_stubbed`, `tests`, `integration_testing_review`, `test_completeness_review`, `reuse_compliance`, and the 5 Verified Agent Output fields) to `.architect-team/reviews/<task-id>.json`; an independent `task-reviewer` writes the `independent_review` block and a paired adversarial reviewer writes `adversarial_review`. Only both-pass opens the gate. Same gate as the main pipeline — data work does not skip review-gate evidence.
- **Phases 5–6 — integration + verification.** Integration tests run against the live dev API with real dev data per `dev-api-integration-testing` (real backend, no mocks); any analytics-API surface is exercised front-to-back.

**The data-specific acceptance bar (non-negotiable).** Every transformation ships **≥ 1 blocker-severity validation rule** (the Stage 6 mandate, now implemented and executed — a transformation with zero blocker rules fails the gate) AND its **lineage emission** (the record is end-to-end traceable, per the exploration's lineage plan and `data-lineage-mapping`). Aggregate and per-endpoint metrics are wired per the Stage 6 observability plan. These are verified in the Phase 3 evidence and re-confirmed at Phase 5–6, not asserted.

The D2→D6 loop is unbounded — it runs until the slice is green end-to-end, never aborting on an iteration count; a failing check escalates as a solution requirement that the normal fix loop acts on.

## Phase D7 — Catalog refresh (the second new discipline)

After the transformation lands and passes D2–D6, refresh the catalog so the next run starts warm. This is the symmetric partner of D−1's warm-catalog-first check — D−1 reads the catalog, D7 rewrites it.

1. **Rebuild the affected data-dictionary tables** via `scripts/data_dictionary/data_dictionary.py` — re-run the engine over the tables the transformation created or changed (SQLite introspection + ~100-row sampling, grain/field inference, the fixed provenance vocabulary), producing a refreshed `DATA_DICTIONARY_MAP.md` per the `data-dictionary` skill contract.
2. **Re-corroborate.** Re-run the value-level corroboration + the reference / relational maps against the new tables, so the dictionary's provenance and relationships reflect the shipped change rather than the pre-change state.
3. **Refresh the knowledge server's index.** Re-index the Run A knowledge server (`services/knowledge_server/`) so its `search_dictionary` / `get_table_details` / `get_dictionary_status` tools serve the rebuilt dictionary — the warm catalog the NEXT run's D−1 will consult.
4. **Mine the artifact to MemPalace** per `mempalace-integration` — the refreshed `DATA_DICTIONARY_MAP.md` and the run's transformation summary land in the palace for prior-context recall.

**No-connection honesty (carried from Run A).** The rebuilt dictionary's DB-currency verdict remains `unknowable` without a live database connection — the D7 rebuild refreshes the reference-file (repo-side) view and the sampled snapshot, but it cannot certify the live data is current. State that boundary in the D7 output and the final report exactly as D−1 does; the catalog is left *warm*, not *proven live-current*. If the knowledge server is not installed, D7 still rebuilds the dictionary + mines to MemPalace and notes the server re-index was skipped (with the `/architect-team:knowledge-install` remediation).

## Phase D8 — Close-out (Phase 8 verbatim)

Phase **D8 is the main pipeline's Phase 8 close-out run verbatim** — the documentation-currency gate FIRST (the `doc-updater` agent dispatch + the independent `system-architect` Documentation Currency Audit per `documentation-currency`; the audit verdict, not a self-report, gates the commit), then the completion-audit gate, the default-branch guard, the delivery manifest (the bill of sale, per `delivery-manifest`), the commit with the standard message template, and the push. Auto-merge to main (`--no-auto-merge` opts out) when the completion audit passed and the work is on `architect-team/<slug>`; a conflict falls back to a PR, never `--force`. The human-authored `.architect-team-deploy.json` dev→test→prod opt-in is honored exactly as the main pipeline honors it (and is immutable to agents). Mark the run complete via `hooks/run_continuity.py --mark-complete` as the last state action, emit `run_complete` with the delivery manifest embedded, and emit the auto-compact prompt (unless `--no-compact`).

## Relationship to other skills

- `architect-team-pipeline` (sibling) — same orchestration discipline; the lane reuses Phases 1, 2–6, and 8 by reference. Reached via `/architect-team:data-eng` (explicit), `--data-eng`, or the main pipeline's Phase −2 triage when the classifier returns `kind: data-eng`. See `architect-team-pipeline` `## Data-eng lane precedence` for how the front-door lane and Phase 0c mid-flow dispatch interact.
- `bug-fix-pipeline` (sibling) — the template this lane is built on; same "reuse the main pipeline's structural points rather than duplicating them" shape.
- `data-engineering-exploration` (Phase D0) — dispatched verbatim; the lane is its third documented caller.
- `intake-and-mapping` (Phase D−1A) — reused verbatim. Same maps, same freshness rules.
- `data-dictionary` (Phase D−1B, D7) — the deterministic dictionary engine's contract; consulted at D−1 (via the knowledge server) and rebuilt at D7.
- `data-lineage-mapping` (Phase D2–D6) — every transformation's lineage emission traces to this discipline.
- `documentation-currency` (Phase D8) — the doc-currency gate before the auto-commit, same as the main pipeline.

## Same input forms as architect-team-pipeline

This lane's input rules are IDENTICAL to `architect-team-pipeline`'s — folder OR plain-language prose, both first-class; never refuse prose; never treat the first word of a sentence as a path; ask only when input is genuinely empty (*"What data-engineering work should the lane build?"* — NOT *"give me a requirements folder"*). When the input is plain-language prose, the codebase the ask applies to is the cwd unless the prose names another path.
