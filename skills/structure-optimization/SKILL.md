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
4. Allocate `<slug>` as `structure-optimization-<YYYY-MM-DD-HHMMSS>-<6-char-rand>`; create `<workspace>/.architect-team/structure-optimization/<slug>/{drafts,reference-closure,adversarial}/`.
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

**Stage-S1 checklist:** every in-scope codebase has a fresh `CODEBASE_MAP.md`; frontends have `ROUTE_MAP.md`; multi-codebase workspaces have a fresh `INTEGRATION_MAP.md`.

## Stage S2 — Independent structure drafts (×3 structure-analyst)

The orchestrator (Lead) dispatches 3 `structure-analyst` agents in parallel via a single Agent-tool batch (subagents mode) OR creates 3 analyst tasks in the shared list (teams mode). Each analyst receives the maps, the codebase paths, the `objective` from `scope.json`, and its output path `drafts/analyst-<N>.json`. Each consults `superpowers:brainstorming` discipline before committing to an approach (≥2 candidate structures considered, the choice argued from the maps), then drafts independently — Round 1 has no cross-talk.

Each draft MUST carry the full file partition: every `git ls-files` tracked file appears in the draft's movement table OR its explicit `stays` list, with a passing `partition_self_check`. A draft with orphans or duplicates is returned to its analyst, not aggregated.

**Stage-S2 checklist:** 3 drafts present; each has a passing partition self-check; each movement has a one-line rationale; ≥2 approaches considered per draft.

## Stage S3 — Convergence + the deterministic partition check

Round-robin convergence: each analyst reads the other two drafts and revises toward ONE shared proposal, arguing with evidence until all three sign the identical movement table + stays list. Wrap the loop in the canonical flag form:

`/ralph-loop "<stage-3 convergence prompt>" --completion-promise "STRUCTURE PROPOSAL CONVERGED"`

— loops until the promise fires; no iteration cap (v3.8.0 unbounded solving).

**The deterministic partition check gates the promise.** Before the convergence promise may be emitted, the orchestrator runs the check ITSELF (never trusts the analysts' self-checks) using the detect-once polyglot invocation (per `common-pipeline-conventions` `## Cross-platform Python invocation (polyglot pattern)`):

```bash
$(command -v python3 || command -v python) -c "
import json, pathlib, subprocess, sys
run_dir = pathlib.Path(sys.argv[1]); codebase = sys.argv[2]
prop = json.loads((run_dir / 'converged-proposal.json').read_text(encoding='utf-8'))
tracked = set(subprocess.run(['git', '-C', codebase, 'ls-files'], capture_output=True, text=True, encoding='utf-8').stdout.split())
moved = [p for m in prop['movements'] for p in m['from']]
stays = prop['stays']
def covered(f):
    return any(f == s or (s.endswith('/') and f.startswith(s)) for s in stays)
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

Output: `converged-proposal.json` (movement table + stays + rationale + the orchestrator-run `partition_check` block).

**Stage-S3 checklist:** all 3 analysts signed the identical proposal; the orchestrator-run partition check passed; every movement carries kind + rationale.

## Stage S4 — Reference closure (sharded reference-tracer)

Shard the converged movement table into non-overlapping `movement_id` subsets (high-fan-in files get small shards). The orchestrator (Lead) dispatches one `reference-tracer` per shard in parallel via a single Agent-tool batch (subagents mode) OR creates the tracer tasks in the shared list (teams mode). Each tracer closes its shard — `references_in` (kinds: `import` / `require` / `include` / `config` / `build` / `ci` / `docs` / `string-path` / `test`), `references_out_relative`, `refactors` (each `mechanical` or `semantic`), all with `file:line` evidence + verbatim current/required snippets + a mandatory `search_log`.

The orchestrator assembles the shards + the converged proposal into **`movements.json`** (the machine sidecar, schema v1.0):

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

`kind` semantics: `move`/`rename` are 1→1; `split` is 1→N; `merge` is N→1; `delete-dead` is 1→0 and is admissible ONLY with zero inbound references confirmed by the tracers AND re-confirmed by the adversaries — every `delete-dead` is additionally surfaced verbatim in the final report. The `batches` block orders movements into migration steps such that no intermediate state is broken; each batch names its verification commands (build / test / lint invocations that must stay green after the batch).

**Stage-S4 checklist:** every movement has a closure (zero unclaimed movement_ids); every reference entry carries file:line + snippets; every shard has a search_log; `movements.json` assembled and valid against the schema above.

## Stage S5 — Adversarial verification (×3 structure-adversary per round)

The orchestrator (Lead) dispatches 3 `structure-adversary` agents per round in parallel via a single Agent-tool batch (subagents mode) OR creates 3 adversary tasks in the shared list (teams mode). Their mandate is refutation: independent search modalities the tracers did not log, a from-scratch re-run of the partition check, migration-order attacks, tooling-breakage attacks, runtime-only-reference hunts, and alive-checks on every `delete-dead`. Wrap the loop in the canonical flag form:

`/ralph-loop "<stage-5 adversarial prompt>" --completion-promise "RESTRUCTURE PLAN VERIFIED"`

— loops until the promise fires; no iteration cap (v3.8.0 unbounded solving).

Routing per round: `missed-reference` / `dead-file-alive` findings → the owning `reference-tracer` re-traces; `partition-orphan` / `partition-duplicate` / structural findings → the analysts revise `converged-proposal.json` (and S3's orchestrator-run partition check re-gates); `order-hazard` / `tooling-breakage` findings → the batch plan is reordered/repaired. After EVERY revision, the next adversarial round starts fresh.

**Exit rule:** the promise may be emitted ONLY after **two consecutive all-clean rounds** — all three adversaries returning `verdict: "clean"` with non-empty `modalities_run`, twice in a row with no revision between. One clean round is luck; two consecutive is evidence. A `clean` verdict with an empty modality log is rejected as not-having-looked, and the round does not count.

**Stage-S5 checklist:** `adversarial_rounds` history recorded in `movements.json`; final two rounds clean across all 3 adversaries; the orchestrator-run partition check green in both final rounds.

## Stage S6 — Architect evaluation + plan assembly

Dispatch `system-architect` in **Restructure Plan Audit** mode (see `agents/system-architect.md` `## Restructure Plan Audit (structure-optimization Stage S6)`). The architect independently re-confirms the partition check, spot-checks the reference closure with modalities the logs don't contain, walks every batch for migration-order soundness, and judges objective fidelity + reuse-first fit. Verdict at `architect-verdict.json`; any `fail` routes back (structure → S3, closure → S4, order → the batch plan) and S5 re-runs after the revision — the audit is a gate, not a formality.

On `overall: "pass"`, assemble **`RESTRUCTURE_PLAN.md`** per `superpowers:writing-plans` conventions — the full plan an engineer (or the architect-team pipeline) can execute without re-deriving anything:

1. **Header** — goal, objective fidelity statement, codebases + baseline SHAs.
2. **Target structure** — the to-be tree with one-line purpose per top-level directory.
3. **Movement table** — every movement: `from` → `to`, kind, rationale, reference counts.
4. **Migration batches** — ordered; per batch: the `git mv` set, every reference edit (file:line, current → required), every forced refactor, and the exact verification commands that must pass before the next batch. Bite-sized, independently verifiable steps; no placeholders.
5. **Risk register** — adversary-named hazards and how the batch order disarms each.
6. **Rollback note** — per batch (`git revert` boundary; never destructive rewrites).

**Stage-S6 checklist:** architect verdict `pass`; `RESTRUCTURE_PLAN.md` complete (every movement appears in exactly one batch; every batch has verification commands); every `delete-dead` listed in the plan's risk register.

## Stage S7 — OpenSpec authoring

Author the OpenSpec change via `openspec-propose` (use the Skill tool — NEVER hand-write the change files), consuming `RESTRUCTURE_PLAN.md` + `movements.json`:

- `proposal.md` — the restructure summary: objective, movement count, batch count, risk highlights.
- `specs/` — every movement becomes a REQ citing its `movement_id`; every reference closure becomes an acceptance criterion (the implementing pipeline's coverage map inherits them).
- `design.md` — target-tree rationale, approaches considered (from the analyst drafts), reuse-first decisions per `reuse-first-design`.
- `tasks.md` — one task group per migration batch, in batch order, each carrying its verification commands.

Gate: `openspec validate --all --strict --json` must pass (per `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)` — the validate gate is uniform regardless of authoring path). Wrap the authoring + validation loop in the canonical flag form:

`/ralph-loop "<stage-7 authoring prompt>" --completion-promise "OPENSPEC AUTHORING COMPLETE"`

— loops until the promise fires; no iteration cap (v3.8.0 unbounded solving).

**Stage-S7 checklist:** change validates strict; every movement_id appears in a spec REQ; every batch is a task group; design.md cites the analyst alternatives.

## Stage S8 — Return + handoff

1. Consult `superpowers:verification-before-completion` — before ANY done-claim, re-verify the evidence chain: partition check green (orchestrator-run), two consecutive clean adversarial rounds recorded, architect verdict `pass`, openspec strict-validate output captured.
2. Mine `RESTRUCTURE_PLAN.md` + `movements.json` to MemPalace per `mempalace-integration` (orchestrator-serialized mining).
3. Best-effort notify per `common-pipeline-conventions` `## Notifications wiring convention` (`pipeline_complete` event; offline/no-config = silent no-op).
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

## What this skill is NOT

- **Not an executor** — it produces the verified plan + OpenSpec change; it never runs a `git mv`, never edits a source file, never "just applies the small ones." Execution is `/architect-team` driving the produced change (or the user, by hand, batch by batch).
- Not a code-quality reviewer — it optimizes placement and boundaries; the only refactors it plans are those movements force (import rewrites, path constants, barrels) plus boundary extractions that make a movement clean. Feature work and implementation cleanups route through the normal pipelines.
- Not a maps producer — it consumes `cartographer-team` / `intake-and-mapping` output and triggers freshness-checked re-mapping; it never re-implements mapping.
- Not a fix loop — adversarial findings route to the producing role inside the run; it files no SRs of its own. Post-execution drift is the implementing pipeline's territory.
- Not bounded — there is no "good enough after N rounds." The exit conditions are evidence (partition green, two consecutive clean adversarial rounds, architect pass, strict validate), nothing else.
