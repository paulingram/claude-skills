---
name: structure-optimization
description: Use when a codebase's structure needs an adversarially-verified restructure plan — the user asks to optimize / reorganize / restructure the directory layout, module placement, or file organization ("optimize the codebase structure", "clean up the layout", "propose a better file structure"), or /architect-team:optimize-structure is invoked. Produces a reference-closed movement plan (every file movement + every reference that must change + every forced refactor, in ordered verifiable batches) as RESTRUCTURE_PLAN.md + movements.json + an OpenSpec change — it PLANS the restructure; execution belongs to /architect-team driving the produced change.
---

# Structure Optimization

You are the **Structure Optimization orchestrator**. Drive the S0–S8 flow that converts a codebase (or a multi-codebase workspace) + an optional user objective into a converged, reference-closed, adversarially-verified restructure plan: `RESTRUCTURE_PLAN.md` + `movements.json` + an OpenSpec change authored via `openspec-propose`. Every convergence loop runs inside `ralph-loop:ralph-loop` with a completion-promise and NO iteration cap, per `common-pipeline-conventions` `## Unbounded solving discipline (v3.8.0)` and `## Uniform plugin usage (v3.9.0)`.

The role split is producer-cannot-be-its-own-checker (v0.9.13) at pipeline scale: `structure-analyst` ×3 design the structure; `reference-tracer` ×N close the reference set; `structure-adversary` ×3 refute both; `system-architect` (Restructure Plan Audit mode) independently evaluates the whole. No role verifies its own output.

## When this skill runs

1. **`/architect-team:optimize-structure`** — the explicit command entry point (see `commands/optimize-structure.md`).
2. **Direct invocation** — the user asks in prose for a codebase-structure optimization / reorganization / restructure plan.

## Inputs

The caller passes a structured `inputs` object:

```json
{
  "codebase_inputs": ["<absolute-path>", "..."],
  "objective": "<verbatim user optimization-objective prose or null>",
  "execute_after_plan": false,
  "auto_commit": true,
  "auto_push": true,
  "openspec_change_name": "<kebab-case-change-name>",
  "completion_promises": {
    "s3": "STRUCTURE PROPOSAL CONVERGED",
    "s5": "RESTRUCTURE PLAN VERIFIED",
    "s7": "OPENSPEC AUTHORING COMPLETE"
  }
}
```

`codebase_inputs` defaults to the workspace root's codebases (from `intake-state.json` when present, else the cwd repo). `objective: null` means general structural health. Scope rule: the analysts optimize toward the STATED objective; narrowing it (or substituting "what we'd rather fix") is forbidden per `common-pipeline-conventions` `## Scope discipline` — a scope-fidelity doubt is a DOMAIN gate surfaced to the user, not a silent reinterpretation.

## Stage S0 — Initialization + preconditions

1. Resolve `<workspace>` via `git -C <cwd> rev-parse --show-toplevel` (cwd fallback).
2. MemPalace wake-up per `common-pipeline-conventions` `## MemPalace wake-up precondition` (prior structure work on this workspace is prior context, not a constraint).
3. Superpowers pre-flight per `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)` — hard-blocking presence check before any stage runs.
4. Allocate `<slug>` as `structure-optimization-<YYYY-MM-DD-HHMMSS>-<6-char-rand>`; the orchestrator creates the run directories via `mkdir -p` (Bash): `mkdir -p <workspace>/.architect-team/structure-optimization/<slug>/{drafts,reference-closure,adversarial}/` (the agents have bounded Write into their own output paths but do not create the tree — the orchestrator does, once, here).
5. Persist `scope.json` (verbatim `inputs` + the resolved codebase list + each codebase's `BASELINE_SHA` via `git rev-parse HEAD`).

## Stage S1 — Maps current (delegates to cartographer-team)

For EACH codebase in scope, invoke the existing map machinery — never re-implement it. Use the Skill tool with `skill: cartographer-team` and:

```json
{
  "codebase_path": "<absolute-path>",
  "classification": "<frontend|backend|fullstack|library|infra|data-pipeline>",
  "output_path": "<codebase>/docs/CODEBASE_MAP.md",
  "produce_route_map": true,
  "route_map_output_path": "<codebase>/docs/ROUTE_MAP.md",
  "frontend_read_only": false,
  "freshness_check": true,
  "completion_promise": "CODEBASE MAP COMPLETE"
}
```

`freshness_check: true` short-circuits on an already-fresh map, so this stage costs nothing when the maps are current — and produces them when they don't exist (the cartographer-team skill wraps the external cartographer plugin with the ×3-reviewer audit). For multi-codebase workspaces, additionally ensure `INTEGRATION_MAP.md` is current per `intake-and-mapping`'s integration-mapping step — moved boundary files (shared schemas, HTTP clients, contract files) cannot be reference-closed without it.

**Per-codebase freshness pipelining (axis: wall-clock; the invariant preserved: every in-scope codebase still has a freshness-verified map before its analysts run — pipelining changes WHEN each codebase's analysts start, never WHETHER its map was verified):** the orchestrator freshness-checks ALL codebases FIRST, then RELEASES each codebase's S2 analyst inputs the moment THAT codebase's maps are confirmed fresh — it does not block the whole workspace on the slowest cold-map codebase. A fresh-map codebase's analysts begin S2 immediately; a cold-map codebase holds only its OWN portion until its (re-)mapping completes.

**Stage-S1 checklist:** every in-scope codebase has a fresh `CODEBASE_MAP.md`; frontends have `ROUTE_MAP.md`; multi-codebase workspaces have a fresh `INTEGRATION_MAP.md`; each codebase's analyst inputs released as soon as its maps are fresh.

## Stage S2 — Independent structure drafts (×3 structure-analyst)

**Orchestrator-precomputed file universe (axes: wall-clock, tokens; the invariant preserved: every analyst partitions against the same `git ls-files` universe — precomputing it once removes three redundant derivations, never changes the universe each analyst sees):** before dispatching, the orchestrator runs `git ls-files` ONCE per codebase plus a per-directory file-count histogram, and hands that canonical file universe to all three analysts. The analysts work FROM this shared universe instead of each re-running `git ls-files` and re-bucketing it — the file set is identical for all three, so deriving it three times is pure waste.

The orchestrator (Lead) dispatches 3 `structure-analyst` agents in parallel via a single Agent-tool batch (subagents mode) OR creates 3 analyst tasks in the shared list (teams mode). Each analyst receives the maps, the codebase paths, the precomputed file universe, the `objective` from `scope.json`, and its output path `drafts/analyst-<N>.json`. Each consults `superpowers:brainstorming` discipline before committing to an approach (≥2 candidate structures considered, the choice argued from the maps), then drafts independently — Round 1 has no cross-talk.

Each draft MUST carry the full file partition: every `git ls-files` tracked file appears in the draft's movement table OR its explicit `stays` list, with a passing `partition_self_check`. A draft with orphans or duplicates is returned to its analyst, not aggregated.

**Front-loaded partition check — per draft (axis: convergence; the invariant preserved: the convergence-gate partition run at S3 is UNCHANGED and still gates the promise — front-loading ADDS earlier checks, it does not replace the gate):** the orchestrator runs the deterministic partition check on EACH draft as it lands and returns that draft's orphan/duplicate list to its analyst immediately — so a partition hole is caught and fixed at draft time, not discovered three rounds into convergence. This is the same orchestrator-run check (never the analyst's self-check); it just runs earlier and more often.

**Stage-S2 checklist:** 3 drafts present; each has a passing partition self-check AND a passing orchestrator-run per-draft partition check; each movement has a one-line rationale; ≥2 approaches considered per draft.

## Stage S3 — Convergence + the deterministic partition check

Round-robin convergence: each analyst reads the other two drafts and revises toward ONE shared proposal, arguing with evidence until all three sign the identical movement table + stays list. Wrap the loop in the canonical flag form:

`/ralph-loop "<stage-3 convergence prompt>" --completion-promise "STRUCTURE PROPOSAL CONVERGED"`

— loops until the promise fires; no iteration cap (v3.8.0 unbounded solving).

**Structured agree-set / dispute-set protocol (axis: convergence; the invariant preserved: the final gated table is the FULL table all three analysts sign — freezing agreed rows narrows what each PASS re-argues, never what the final partition check gates):** each round-robin pass, every analyst emits three things — its **agreed-set** (the movements it now accepts as-is), its **disputed movements** (each with a one-line decisive argument), and **one proposed resolution per dispute**. The orchestrator FREEZES the rows all three agree on between passes and re-dispatches ONLY the dispute set to the next pass — analysts stop re-litigating settled rows and spend each pass on the shrinking disagreement. **Frozen rows remain part of the final gated table** (they are agreed, not dropped). **Completion criterion (explicit):** the convergence promise fires when all three analysts sign the IDENTICAL FULL table (frozen agreed rows + resolved former-disputes) AND the orchestrator-run partition check passes on that full table.

**Front-loaded partition check — per revision (axis: convergence; the invariant preserved: the convergence-gate run still gates the promise):** the orchestrator re-runs the deterministic partition check on EVERY revision and attaches the resulting orphan/duplicate delta to the next round-robin brief, so each pass starts from a fresh partition fact. The convergence-gate run below is unchanged and remains the thing that gates the promise.

**The deterministic partition check gates the promise.** Before the convergence promise may be emitted, the orchestrator runs the check ITSELF (never trusts the analysts' self-checks) using the detect-once polyglot invocation (per `common-pipeline-conventions` `## Cross-platform Python invocation (polyglot pattern)`):

```bash
$(command -v python3 || command -v python) -c "
import json, os.path, pathlib, subprocess, sys
run_dir = pathlib.Path(sys.argv[1]); codebase = sys.argv[2]
prop = json.loads((run_dir / 'converged-proposal.json').read_text(encoding='utf-8'))
# .splitlines() (NOT .split()) keeps space-bearing filenames intact; one entry per line.
tracked = {os.path.normcase(p) for p in subprocess.run(['git', '-C', codebase, 'ls-files'], capture_output=True, text=True, encoding='utf-8').stdout.splitlines() if p}
# normcase BOTH sides so a case-insensitive filesystem can't hide an orphan/duplicate.
moved = [os.path.normcase(p) for m in prop['movements'] for p in m['from']]
stays = [os.path.normcase(s) for s in prop['stays']]
def covered(f):
    return any(f == s or (s.endswith(os.path.normcase('/')) and f.startswith(s)) for s in stays)
dup_moves = sorted({p for p in moved if moved.count(p) > 1})
both = sorted([p for p in set(moved) if covered(p)])
orphans = sorted([f for f in tracked if f not in set(moved) and not covered(f)])
result = {'tracked_files': len(tracked), 'moved': len(set(moved)), 'orphans': orphans, 'duplicates': dup_moves + both, 'passed': not (orphans or dup_moves or both)}
(run_dir / 'partition-check.json').write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
print(json.dumps({k: result[k] for k in ('tracked_files', 'moved', 'passed')}))
sys.exit(0 if result['passed'] else 1)
" "<run-dir>" "<codebase-path>"
```

The rule the check enforces: **every tracked file appears in exactly one of the movement table / the stays list** — zero `orphans` (a tracked file in neither) and zero `duplicates` (a file in both, or in two movements). A failing check returns the proposal to the analysts with the orphan/duplicate list; the promise may not be emitted until the check passes. This converts "we crawled the codebase" from a claim into a checkable fact.

**The check runs once per codebase in scope.** For a multi-codebase workspace the orchestrator invokes the snippet once per codebase — each codebase's movements/stays are evaluated against its OWN `git -C <codebase> ls-files`; the partition is per-codebase total, never a cross-codebase merge. **Any duplicate is recoverable, not terminal:** a path appearing in two movements, or in a movement AND the stays list, routes the proposal back to the analysts for revision through S3 (the convergence loop re-runs, the gate re-checks) — a duplicate fails the gate but never aborts the run.

Output: `converged-proposal.json` (movement table + stays + rationale + the orchestrator-run `partition_check` block).

**Stage-S3 checklist:** all 3 analysts signed the identical proposal; the orchestrator-run partition check passed; every movement carries kind + rationale.

## Stage S4 — Reference closure (sharded reference-tracer)

Shard the converged movement table into non-overlapping `movement_id` subsets. **Shard policy — balance by ESTIMATED reference surface (the invariant preserved: every movement is closed by exactly one tracer, completely, with file:line evidence — sharding changes who closes what, never the closure obligation):** before sharding, the orchestrator pre-estimates each movement's fan-in from the maps + a quick basename `grep -c` reference count across the tree. Each top-fan-in file gets its OWN shard (a singleton, because its closure dominates the shard's cost); low-fan-in leaf movements batch together (rough heuristic: N ≈ `ceil(total_movements / 8)` shards, minimum 3 movements per shard EXCEPT the singleton high-fan-in shards). This balances tracer wall-clock — no shard carries two reference-heavy files while another carries only trivia. The orchestrator (Lead) then dispatches one `reference-tracer` per shard in parallel via a single Agent-tool batch (subagents mode) OR creates the tracer tasks in the shared list (teams mode). Each tracer closes its shard — `references_in` (kinds: `import` / `require` / `include` / `config` / `build` / `ci` / `docs` / `string-path` / `test`), `references_out_relative`, `refactors` (each `mechanical` or `semantic`), all with `file:line` evidence + verbatim current/required snippets + a mandatory `search_log`.

**Per-shard tracer brief (axis: tokens — the invariant preserved: the tracer closes its shard completely against the live tree; trimming the brief removes redundant prose, never any movement or any file):** each tracer's brief carries ONLY what it needs — the shard's movement slice (the `from`/`to`/kind/rationale for its `movement_id`s) + the relevant map sections for navigation. It does NOT carry the other analysts' drafts, the full convergence rationale, or sibling shards — those are noise to a mechanical closure and cost tokens without changing a single reference found.

The orchestrator assembles the shards + the converged proposal into **`movements.json`** (the machine sidecar, schema v1.0). **Assembly validation (the invariant preserved: zero unclaimed and zero double-claimed movement_ids — the shard partition is itself total and non-overlapping):** the orchestrator merges the shard files into `movements.json` and VALIDATES that every `movement_id` from `converged-proposal.json` appears in EXACTLY ONE shard — a missing id (no tracer closed it) or a duplicated id (two tracers closed it) fails assembly and re-dispatches the affected shard before `movements.json` is finalized.

```json
{
  "schema_version": "1.0",
  "generated_at": "<ISO-8601 UTC>",
  "objective": "<verbatim or null>",
  "codebases": [{"path": "<abs>", "baseline_sha": "<sha>"}],
  "movements": [
    {
      "movement_id": "mv-001",
      "kind": "move" | "rename" | "split" | "merge" | "delete-dead",
      "from": ["<repo-relative>"], "to": ["<repo-relative>"],
      "rationale": "<one-line>",
      "references_in": [{"file": "<repo-relative>", "line": 41, "kind": "import", "current": "<snippet>", "required_change": "<snippet>"}],
      "references_out_relative": [{"line": 3, "current": "<snippet>", "required_change": "<snippet>"}],
      "refactors": [{"refactor_id": "rf-001", "kind": "mechanical", "description": "<one-line>", "evidence": "<file:line>"}],
      "batch": 1
    }
  ],
  "stays": ["<path-or-dir-prefix/>"],
  "partition_check": {"tracked_files": 0, "moved": 0, "stayed": 0, "orphans": [], "duplicates": [], "passed": true},
  "batches": [{"batch": 1, "movements": ["mv-001"], "verification": ["<command>"], "parallel_safe": true}],
  "adversarial_rounds": [{"round": 1, "findings_count": 0, "clean": true}]
}
```

`kind` semantics: `move`/`rename` are 1→1; `split` is 1→N; `merge` is N→1; `delete-dead` is 1→0 — it carries `"to": []` (an empty target list is the tombstone marker) and is admissible ONLY with zero inbound references confirmed by the tracers AND re-confirmed by the adversaries — every `delete-dead` is additionally surfaced verbatim in the final report. The `batches` block orders movements into migration steps such that no intermediate state is broken; each batch names its verification commands (build / test / lint invocations that must stay green after the batch).

**Stage-S4 checklist:** every movement has a closure (zero unclaimed movement_ids); every reference entry carries file:line + snippets; every shard has a search_log; `movements.json` assembled and valid against the schema above.

## Stage S5 — Adversarial verification (×3 structure-adversary per round)

The orchestrator (Lead) dispatches 3 `structure-adversary` agents per round in parallel via a single Agent-tool batch (subagents mode) OR creates 3 adversary tasks in the shared list (teams mode). Their mandate is refutation: independent search modalities the tracers did not log, a from-scratch re-run of the partition check, migration-order attacks, tooling-breakage attacks, runtime-only-reference hunts, and alive-checks on every `delete-dead`. Wrap the loop in the canonical flag form:

`/ralph-loop "<stage-5 adversarial prompt>" --completion-promise "RESTRUCTURE PLAN VERIFIED"`

— loops until the promise fires; no iteration cap (v3.8.0 unbounded solving).

Routing per round: `missed-reference` / `dead-file-alive` findings → the owning `reference-tracer` re-traces; `partition-orphan` / `partition-duplicate` / structural findings → the analysts revise `converged-proposal.json` (and S3's orchestrator-run partition check re-gates); `order-hazard` / `tooling-breakage` findings → the batch plan is reordered/repaired. After EVERY revision, the next adversarial round starts fresh.

**Per-round partition recompute — dedup (axis: tokens; the invariant preserved: the partition is recomputed from scratch EVERY round, just by deterministic orchestrator code instead of three redundant LLM re-derivations):** the orchestrator runs the canonical from-scratch deterministic partition recompute (the S3 snippet) ONCE per round, per codebase in scope — consistent with S3's once-per-codebase invocation — publishing one artifact per codebase at `adversarial/round-<R>/partition-check-<codebase-slug>.json` (a single-codebase run may omit the slug and publish the bare `partition-check.json`). The three adversaries CONSUME the published artifact(s) for the orphan/duplicate dimension and spend their opus budget on the judgment surfaces (missed references, migration order, tooling, runtime-only references, delete-dead alive-checks) — the surfaces deterministic code cannot cover. The from-scratch-every-round property is fully preserved; it just runs as sub-second orchestrator code, not three opus re-runs of the same arithmetic.

**Per-round adversary brief (axis: tokens; the invariant preserved: the adversary still attacks every movement — the brief carries the facts it attacks, not the prose it doesn't need):** each round's adversary brief carries the reference closures + the tracers' `search_log`s + the migration `batches` + the `stays` list + a fan-in-ordered movement manifest (highest fan-in first, so the adversary spends first on the riskiest). It does NOT carry the analysts' convergence rationale prose — refutation attacks the closure and the layout, not the argument that produced them.

**Warm-start across rounds (axis: all three — wall-clock, tokens, convergence; the invariant preserved: the exit rule is UNTOUCHED — warm-start changes work INSIDE a round, never the exit condition):** after round N, the orchestrator computes the **round delta** — the `movement_id`s whose closure or partition state changed since the prior round — and carries forward each adversary's `modalities_run` + its clean per-movement evidence. Round N+1 then: (a) re-runs every modality on the DELTA movements (the ones that actually changed), (b) runs any modality NOT yet in the carried union across ALL movements (new coverage everywhere), and (c) re-confirms the carried clean evidence for unchanged movements — a cheap re-confirm, not a from-scratch re-derivation. **RESTATED invariants (verbatim-strength, unchanged):** any revision resets the two-consecutive-clean streak to zero; BOTH exit rounds are all-clean across all three adversaries with non-empty `modalities_run`; the carried modality union only ever GROWS (a modality once run is never dropped). Warm-start makes the second clean round cheap; it never makes one clean round sufficient.

**The 3-adversary width is a FLOOR on every round** — including the two confirming clean rounds. Warm-start trims the per-round WORK (delta-scoped re-runs, carried evidence), never the adversary COUNT: three independent refuters attack every round, first to last, because two clean rounds at width-3 is the evidence the plan survives hostile judgment — narrowing the panel on a "probably clean" round is exactly the luck the two-round rule exists to refuse.

**Exit rule:** the promise may be emitted ONLY after **two consecutive all-clean rounds** — all three adversaries returning `verdict: "clean"` with non-empty `modalities_run`, twice in a row with no revision between. One clean round is luck; two consecutive is evidence. A `clean` verdict with an empty modality log is rejected as not-having-looked, and the round does not count.

**Stage-S5 checklist:** `adversarial_rounds` history recorded in `movements.json`; the per-round, per-codebase `partition-check[-<codebase-slug>].json` published and consumed; final two rounds clean across all 3 adversaries; the orchestrator-run partition check green in both final rounds.

## Stage S6 — Architect evaluation + plan assembly

Dispatch `system-architect` in **Restructure Plan Audit** mode (see `agents/system-architect.md` `## Restructure Plan Audit (structure-optimization Stage S6)`). The architect independently re-confirms the partition check, spot-checks the reference closure with modalities the logs don't contain, walks every batch for migration-order soundness, and judges objective fidelity + reuse-first fit. Verdict at `architect-verdict.json`; any `fail` routes back and S5 re-runs after the revision — the audit is a gate, not a formality.

**Per-failure-kind re-execution boundaries (the invariant preserved: every routing ends in the FULL S5 two-consecutive-clean loop — scoping the re-run to the affected work never lets a revision skip re-verification):**

| Architect failure kind | Re-execution boundary (what re-runs, in order) |
|---|---|
| objective / structural fail | S3 re-convergence (the agree/dispute loop, gate re-checked) → S4 re-trace of the affected movements → **full S5** (two consecutive all-clean rounds). |
| closure fail | S4 re-trace of the NAMED movements (only the ones whose closure the architect faulted) → **full S5**. |
| migration-order fail | batch-plan repair (reorder / split the faulted batches) → **full S5**. |

Every row ends in the full S5 loop — a revision of any size resets the two-consecutive-clean streak, so the plan re-earns its clean verdict after each fix. The boundary scopes the EXPENSIVE re-derivation (which movements re-trace, whether S3 re-runs) to the failure; it never scopes down the S5 re-verification.

On `overall: "pass"`, assemble **`RESTRUCTURE_PLAN.md`** per `superpowers:writing-plans` conventions — the full plan an engineer (or the architect-team pipeline) can execute without re-deriving anything:

1. **Header** — goal, objective fidelity statement, codebases + baseline SHAs.
2. **Target structure** — the to-be tree with one-line purpose per top-level directory.
3. **Movement table** — every movement: `from` → `to`, kind, rationale, reference counts.
4. **Migration batches** — ordered; per batch: the `git mv` set, every reference edit (file:line, current → required), every forced refactor, and the exact verification commands that must pass before the next batch. Bite-sized, independently verifiable steps; no placeholders.
5. **Risk register** — adversary-named hazards and how the batch order disarms each.
6. **Rollback note** — per batch (`git revert` boundary; never destructive rewrites).

**Stage-S6 checklist:** architect verdict `pass`; `RESTRUCTURE_PLAN.md` complete (every movement appears in exactly one batch; every batch has verification commands); every `delete-dead` listed in the plan's risk register.

## Stage S7 — OpenSpec authoring

Author the OpenSpec change via `openspec-propose` (use the Skill tool — NEVER hand-write the change files), consuming `RESTRUCTURE_PLAN.md` + `movements.json`. **The mapping is mechanical (axis: convergence/tokens; the invariant preserved: every movement, every reference, and every batch is transcribed — the mapping is deterministic, so nothing in the verified plan is lost or re-argued at authoring time):**

- `proposal.md` — the restructure summary: objective, movement count, batch count, risk highlights.
- `specs/` — **each movement → one spec REQ keyed by its `movement_id`**; **each `references_in` entry → one acceptance criterion** under that REQ (the implementing pipeline's coverage map inherits them verbatim).
- `design.md` — target-tree rationale + **the analyst drafts' `approaches_considered` lifted VERBATIM** (the rejected alternatives + their `rejected_because`, copied, not re-summarized) + reuse-first decisions per `reuse-first-design`.
- `tasks.md` — **each `batch` → one task group, in batch order**, each carrying its verification commands.

Gate: `openspec validate --all --strict --json` must pass (per `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)` — the validate gate is uniform regardless of authoring path). Wrap the authoring + validation loop in the canonical flag form:

`/ralph-loop "<stage-7 authoring prompt>" --completion-promise "OPENSPEC AUTHORING COMPLETE"`

— loops until the promise fires; no iteration cap (v3.8.0 unbounded solving).

**Stage-S7 checklist:** change validates strict; every movement_id appears in a spec REQ; every batch is a task group; design.md cites the analyst alternatives.

## Stage S8 — Return + handoff

1. Consult `superpowers:verification-before-completion` — before ANY done-claim, re-verify the evidence chain: partition check green (orchestrator-run), two consecutive clean adversarial rounds recorded, architect verdict `pass`, openspec strict-validate output captured.
2. Mine `RESTRUCTURE_PLAN.md` + `movements.json` to MemPalace per `mempalace-integration` (orchestrator-serialized mining).
3. Best-effort notify per `common-pipeline-conventions` `## Notifications wiring convention` (`phase_complete` event — the canonical terminal event in `scripts/notify/notify.py`; offline/no-config = silent no-op).
4. Return the verdict to the caller:

```json
{
  "slug": "<...>",
  "artifacts": {
    "restructure_plan_path": "<...>/RESTRUCTURE_PLAN.md",
    "movements_path": "<...>/movements.json",
    "architect_verdict_path": "<...>/architect-verdict.json",
    "openspec_change_path": "openspec/changes/<change-name>/"
  },
  "summary": {"movements_count": 0, "references_to_change": 0, "refactors_count": 0, "batches_count": 0, "adversarial_rounds": 0, "delete_dead_count": 0}
}
```

5. **Handoff.** Default (`execute_after_plan: false`): report that the plan is execution-ready and that running `/architect-team` with the produced change implements it under the full review-gate machinery. When `execute_after_plan: true`: invoke the `architect-team-pipeline` skill with the produced OpenSpec change as the requirements input — the restructure is then executed, tested, and committed under the normal Phase 2–8 gates.

This skill NEVER executes movements itself — not even "just the easy renames." The plan is the deliverable; execution belongs to the implementing pipeline's review gates.

## Disciplines this skill respects

- `## Uniform plugin usage (v3.9.0)` — ralph-loop canonical flag form, superpowers pre-flight + invocation map (brainstorming at S2, writing-plans at S6, verification-before-completion at S8), openspec SKILL authoring path + uniform strict-validate gate.
- `## Unbounded solving discipline (v3.8.0)` — every loop runs to its completion promise; no iteration cap, no give-up ceiling; heartbeat tick on >30-min stages per the `### Heartbeat discipline (v3.10.0)` subsection.
- `## Scope discipline` — the stated objective is the fidelity baseline; narrowing is a DOMAIN gate, never silent.
- `## MemPalace wake-up precondition` — wake-up before S0 work; mining at S8.
- `## Cross-platform Python invocation (polyglot pattern)` — the partition check runs in the detect-once polyglot form.
- v0.9.13 producer-cannot-be-its-own-checker — analysts design, tracers close, adversaries refute, the architect audits; the orchestrator runs the deterministic checks itself.
- v1.6.0 teammate git discipline — every agent here is read-only on source with bounded Write to run artifacts; baseline verification via `$BASELINE_SHA`, never stashing.
- v3.0.0 unilateral-override — no stage may be skipped, no gate self-waived; `--execute` is the only sanctioned path that continues into implementation.

## Optimization guardrails

These four are PERMANENTLY-REJECTED optimization anti-candidates. They look like savings; each one trades away an accuracy guarantee this pipeline exists to provide. A future tuning round MUST NOT re-adopt any of them — the rationale is recorded here so the rejection does not have to be rediscovered.

- **(a) Trusting the analysts' partition self-checks at the gate.** REJECTED. v0.9.13 producer-cannot-be-its-own-checker: a producer cannot be its own checker. The orchestrator-run partition recompute is sub-second; "the analyst said it partitions" is a claim, the recompute is a fact. The self-check stays a draft-time convenience; the GATE is always the orchestrator's own run.
- **(b) Exiting S5 after ONE clean round.** REJECTED. One clean round is luck — a single panel that happened to find nothing on a single pass. Two consecutive clean rounds is evidence — the plan survived a hostile panel twice with no revision between. Warm-start already makes the second round cheap (delta-scoped re-runs + carried clean evidence), so the cost argument for a one-round exit is gone; only the accuracy loss remains.
- **(c) Downgrading the structure-adversary to sonnet.** REJECTED. Refutation is open-ended hostile judgment — inventing the search modality the tracers did not run, reasoning about a migration order that breaks only at the new layout — not pattern-matching. That is opus work. The MECHANICAL slice (the from-scratch partition recompute) is offloaded to deterministic orchestrator code instead, which is both cheaper AND more reliable than a cheaper model.
- **(d) Dropping the mandatory `search_log` / `modalities_run`.** REJECTED. They are how the adversary knows what was NOT run, and how a `clean` verdict is distinguished from not-having-looked. Warm-start DEPENDS on them — the carried `modalities_run` union is exactly what lets round N+1 run only new modalities everywhere instead of re-running all of them. Drop the logs and warm-start collapses and the clean verdict becomes unfalsifiable.

## What this skill is NOT

- **Not an executor** — it produces the verified plan + OpenSpec change; it never runs a `git mv`, never edits a source file, never "just applies the small ones." Execution is `/architect-team` driving the produced change (or the user, by hand, batch by batch).
- Not a code-quality reviewer — it optimizes placement and boundaries; the only refactors it plans are those movements force (import rewrites, path constants, barrels) plus boundary extractions that make a movement clean. Feature work and implementation cleanups route through the normal pipelines.
- Not a maps producer — it consumes `cartographer-team` / `intake-and-mapping` output and triggers freshness-checked re-mapping; it never re-implements mapping.
- Not a fix loop — adversarial findings route to the producing role inside the run; it files no SRs of its own. Post-execution drift is the implementing pipeline's territory.
- Not bounded — there is no "good enough after N rounds." The exit conditions are evidence (partition green, two consecutive clean adversarial rounds, architect pass, strict validate), nothing else.
