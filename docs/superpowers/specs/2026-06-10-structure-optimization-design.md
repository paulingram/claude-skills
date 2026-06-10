# v3.11.0 — Structure Optimization Pipeline

**Date:** 2026-06-10
**Author:** Paul Ingram + Claude Fable 5

## Summary

A new CT6 capability that optimizes a codebase's **structure** (directory layout, module placement, file organization) end-to-end at the *planning* layer: it analyzes the code and the codebase maps (producing them via the existing `cartographer-team` machinery when missing or stale), drafts a restructure proposal through three independent analysts, closes the **reference-impact** set for every proposed file movement (every import, config glob, build script, docs link, and string path that must change), subjects the whole proposal to a **multi-agent adversarial review** that loops until two consecutive all-clean rounds, has the architect evaluate and assemble the **full plan** (target structure + every movement + every reference change + every refactoring step, in ordered, verifiable migration batches), and authors the result as an OpenSpec change via `openspec-propose` so the existing `/architect-team` pipeline can execute it.

Backbone per the user mandate: **ralph-loop** (every convergence loop uses the canonical `--completion-promise` form, no iteration cap), **openspec** (the plan ships as a strict-validating change), and **superpowers** (brainstorming discipline at draft time, `writing-plans` conventions for the plan document, `verification-before-completion` before any done-claim) — all wired per `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)`.

## Theory of operation

> A restructure proposal is only as good as its reference closure. The failure mode of every "move these files" plan is the reference nobody greps for — the dynamic import, the CI glob, the tsconfig path alias, the docs link. So the plan is not done when the target tree looks right; it is done when (1) every tracked file is provably accounted for (a deterministic partition check), (2) every movement carries its full reference-impact list with `file:line` evidence, and (3) three adversaries whose only job is to refute the plan have failed to find a missed reference for two consecutive rounds.

Producer-cannot-be-its-own-checker (v0.9.13) applies at pipeline scale: the analysts who design the structure never verify their own reference closure; the tracers who crawl references never judge the structure; the adversaries who refute never author.

## Approaches considered

1. **CHOSEN — new exploration-pipeline skill + 3 new agents + reuse of cartographer-team / ralph-loop / openspec-propose / superpowers.** Matches the house shape (`data-engineering-exploration` is the named precedent: a staged exploration pipeline with per-stage ralph-loop convergence ending in openspec authoring) and the explicit user instruction to create a new callable skill that leverages the existing backbone skills.
2. **Extend `visual-to-api-design`'s Exploration Pipeline with new stages.** Rejected: that pipeline's domain is UI→API design; structure optimization is an orthogonal concern and would muddy the five standardized `*_MAP.md` docs (v3.2.0 standard).
3. **Command-only flow driving existing agents (`system-architect` ×3).** Rejected: fails the explicit "create a new skill" instruction, and the existing agent mandates (`codebase-map-reviewer` audits maps, not movement plans; `system-architect` is a single evaluator, not a ×3 adversarial shape) do not cover movement/reference-closure accuracy.

## Architecture

- **One new skill** — `skills/structure-optimization/SKILL.md`: the orchestrator playbook, stages S0–S8.
- **One new command** — `commands/optimize-structure.md` → `/architect-team:optimize-structure`: the explicit entry point (dispatch-mode banner, argument parsing, git behavior, /compact prompt).
- **Three new agents**:
  - `structure-analyst` (opus, blue, ×3) — independently drafts a complete restructure proposal: structural problems found, target tree, a **full file partition** (every tracked file either appears in the movement table or in the explicit stays-in-place list), per-movement rationale, anticipated refactors. Analysis-only on source; bounded Write to its own draft directory.
  - `reference-tracer` (sonnet, orange, ×N sharded) — mechanically closes the reference-impact set for an assigned shard of the converged movement table: inbound references (imports/requires/includes, config globs, build scripts, CI paths, docs links, string-literal paths, test paths), outbound relative imports that break on move, and the refactoring steps each movement forces. Every entry carries `file:line` evidence. Bounded Write to its shard file.
  - `structure-adversary` (opus, red, ×3) — refutation-only: hunts for missed references via search modalities the tracers did NOT use (basename grep, extensionless module-path grep, string-literal scan, config/glob scan, git log rename history), re-runs the partition check, attacks migration-order hazards (cyclic imports, broken intermediate states), tooling breakage (lint/test/build configs), and runtime-only references (reflection, dynamic import, route-by-convention). A clean verdict is only credible because the adversary's mandate is to find a problem.
- **One extended agent** — `agents/system-architect.md` gains a **Restructure Plan Audit** mode (+ index entry): the Phase S6 independent evaluation of the converged, adversarially-verified proposal before plan assembly and OpenSpec authoring.
- **No new hooks, no new Layer 3 VAO tools, no schema change.** The accuracy guarantees live in the skill's deterministic partition check + the adversarial convergence loop. (Deferred candidate for a future release: a deterministic `verify-restructure-partition` Layer 3 tool.)

## The pipeline (stages)

| Stage | Name | Mechanism |
|---|---|---|
| S0 | Initialization | Resolve workspace; slug `structure-optimization-<ts>-<rand>`; persist `scope.json`; MemPalace wake-up precondition (per CPC); superpowers pre-flight (per `## Uniform plugin usage (v3.9.0)`). |
| S1 | Maps current | Per codebase in scope: `cartographer-team` with `freshness_check: true` (produces/refreshes `CODEBASE_MAP.md`; `ROUTE_MAP.md` for frontends). Multi-codebase workspaces: `INTEGRATION_MAP.md` freshness per `intake-and-mapping`. This is the "use our codemaps skill, produce them if they don't exist" mandate. |
| S2 | Independent drafts | ×3 `structure-analyst` in parallel (single Agent-tool batch in subagents mode OR three Lead-owned tasks in teams mode). Each consults `superpowers:brainstorming` discipline before committing to an approach; each draft contains the full file partition. |
| S3 | Convergence | Round-robin argue-to-convergence on ONE proposal; the deterministic **partition check** must pass before the promise may be emitted. Ralph-loop, completion-promise `"STRUCTURE PROPOSAL CONVERGED"`. |
| S4 | Reference closure | Movement table sharded across `reference-tracer` agents (non-overlapping shards); per-movement reference lists + forced refactors assembled into `movements.json`. |
| S5 | Adversarial verification | ×3 `structure-adversary` per round; every finding routes back into the S3/S4 artifacts (revise, re-trace); loop until **two consecutive all-clean rounds**. Ralph-loop, completion-promise `"RESTRUCTURE PLAN VERIFIED"`. |
| S6 | Architect evaluation + plan assembly | `system-architect` in Restructure Plan Audit mode independently evaluates (verdict JSON; a fail loops back to S3/S4/S5). On pass the orchestrator assembles `RESTRUCTURE_PLAN.md` per `superpowers:writing-plans` conventions: ordered migration batches, per-batch `git mv` set + reference edits + refactors + verification commands, risk register, rollback note. |
| S7 | OpenSpec authoring | Via `openspec-propose` (SKILL authoring path; NEVER hand-written), then `openspec validate --all --strict --json`. Every movement → a task; every reference closure → an acceptance criterion. Ralph-loop, completion-promise `"OPENSPEC AUTHORING COMPLETE"`. |
| S8 | Return + handoff | Verdict JSON to caller; `verification-before-completion` before any done-claim; mine plan artifacts to MemPalace; best-effort notify; execution handoff (default: tell the user to run `/architect-team` on the change; `--execute`: invoke `architect-team-pipeline` immediately with the change as input). |

## The deterministic partition check (the 100%-coverage mechanism)

Over each in-scope codebase: `git ls-files` (the tracked-file inventory) must equal, exactly, the union of (a) every `from` path in the movement table and (b) the expanded stays-in-place list (explicit paths or directory prefixes) — no orphans (tracked file in neither), no duplicates (file in both, or in two movements). The orchestrator runs this check itself with a stdlib-Python snippet (polyglot invocation per CPC) at S3 (gate on the convergence promise), again at S5 (every adversarial round re-runs it), and at S6 (the architect re-confirms). This is the countable artifact that converts "we crawled the codebase" from a claim into a checkable fact.

## Artifacts

All run-scoped, under `<workspace>/.architect-team/structure-optimization/<slug>/`:

- `scope.json` — verbatim inputs (codebases, objective prose, flags).
- `drafts/analyst-<N>.json` — S2 independent drafts.
- `converged-proposal.json` — S3 output (movement table + stays list + rationale + partition-check block).
- `reference-closure/shard-<N>.json` — S4 tracer shards.
- `movements.json` — the assembled machine sidecar (schema below).
- `adversarial/round-<N>/adversary-<M>.json` — S5 verdicts.
- `architect-verdict.json` — S6 audit verdict.
- `RESTRUCTURE_PLAN.md` — the human deliverable (S6).
- plus the OpenSpec change at `<workspace>/openspec/changes/<slug>/` (S7).

### `movements.json` schema (v1.0)

```json
{
  "schema_version": "1.0",
  "generated_at": "<ISO-8601 UTC>",
  "objective": "<verbatim user objective prose or null>",
  "codebases": [{"path": "<abs>", "baseline_sha": "<sha>"}],
  "movements": [
    {
      "movement_id": "mv-<NNN>",
      "kind": "move" | "rename" | "split" | "merge" | "delete-dead",
      "from": ["<repo-relative path>", "..."],
      "to": ["<repo-relative path>", "..."],
      "rationale": "<one-line>",
      "references_in": [
        {"file": "<repo-relative>", "line": 0, "kind": "import" | "require" | "include" | "config" | "build" | "ci" | "docs" | "string-path" | "test",
         "current": "<verbatim snippet>", "required_change": "<verbatim snippet>"}
      ],
      "references_out_relative": [
        {"line": 0, "current": "<verbatim snippet>", "required_change": "<verbatim snippet>"}
      ],
      "refactors": [
        {"refactor_id": "rf-<NNN>", "kind": "mechanical" | "semantic", "description": "<one-line>", "evidence": "<file:line>"}
      ],
      "batch": 1
    }
  ],
  "stays": ["<repo-relative path or directory-prefix ending '/'>"],
  "partition_check": {"tracked_files": 0, "moved": 0, "stayed": 0, "orphans": [], "duplicates": [], "passed": true},
  "batches": [
    {"batch": 1, "movements": ["mv-001"], "verification": ["<command>"], "parallel_safe": true}
  ],
  "adversarial_rounds": [{"round": 1, "findings_count": 0, "clean": true}]
}
```

`kind` semantics: `move`/`rename` are 1→1; `split` is 1→N; `merge` is N→1; `delete-dead` is 1→0 and is permitted ONLY with adversary-confirmed zero inbound references and an explicit rationale (dead code), and is always surfaced to the user in the final report.

## Command surface

`/architect-team:optimize-structure [codebase-path | --all] [--objective "<prose>"] [--execute] [--no-commit] [--no-push] [--no-compact]`

- Dispatch-mode banner first (the run dispatches multi-agent convergence teams).
- First non-flag token = codebase path (default: workspace root; `--all` = every codebase in `intake-state.json`).
- `--objective` — optimization goals/constraints prose, folded verbatim into every analyst/adversary brief and `scope.json` (scope discipline per CPC `## Scope discipline`: the skill never narrows the stated objective without a user gate).
- `--execute` — after S7 validates, invoke `architect-team-pipeline` with the produced change as the requirements input. Default OFF: the deliverable is the verified plan; execution is an explicit second step.
- Git behavior mirrors `/architect-team:visual-to-api`: commit produced artifacts (never `git add -A`), default-branch guard (`architect-team/optimize-structure-<slug>` branch when on main), `--no-commit` / `--no-push` opt-outs, /compact prompt at end unless `--no-compact`.
- The command is the *plan producer*; it never moves a single source file. File movement is execution and belongs to `/architect-team` driving the produced change.

## What this skill is NOT

- Not an executor — it produces the verified plan + OpenSpec change; Phase 2-8 of `architect-team-pipeline` implements it (or the user does).
- Not a code-quality reviewer — it optimizes *structure* (placement, layout, boundaries), not implementations. Refactors it lists are those *forced by movements* (import rewrites, path constants, barrel files) plus boundary-level extractions needed to make a movement clean — never feature work.
- Not a maps producer — it *consumes* `cartographer-team` / `intake-and-mapping` for maps (and triggers them when missing/stale), it does not re-implement mapping.
- Not bounded — every loop runs to its completion promise per `## Unbounded solving discipline (v3.8.0)`.

## Test plan

- `tests/test_structure_optimization_skill.py` — stage headings (ASCII prefix+tail pattern per the cp1252 rule); the three ralph-loop canonical invocations + exact promise strings; `openspec-propose` binding + strict-validate gate; `cartographer-team` reuse with `freshness_check`; the partition check documented at S3/S5/S6; `movements.json` schema fields; the two-consecutive-clean-rounds rule; CPC references (uniform plugin usage, unbounded solving, scope discipline, MemPalace wake-up); Lead-owned dispatch phrasing (no nested teams).
- `tests/test_optimize_structure_command.py` — frontmatter; banner-first; flag table incl. `--execute` default-off; plan-producer-never-moves-files rule; no-force-push safety; /compact block.
- `tests/test_structure_optimization_agents.py` — the 3 new agents: frontmatter validity (tools/model/color from the documented palettes), canonical boilerplate blocks present (operating context / forbidden git ops / checkpoint), mandate keywords (analyst: partition; tracer: file:line evidence + shard; adversary: refute + modalities + consecutive clean rounds), producer/checker separation statements.
- Registry updates: `EXPECTED_SKILLS` (+1), `EXPECTED_AGENTS` (+3), `EXPECTED_COMMANDS` (+1) — the cross-consistency bidirectional check enforces both directions. `CANONICAL_COMMANDS` auto-derives from `commands/*.md`; its frozen fallback gains the new basename.
- Boilerplate: `python scripts/setup/sync_agent_boilerplate.py --check` green after authoring the 3 agents.

## Documentation + version

`plugin.json` + `marketplace.json` → **3.11.0**; CHANGELOG entry (MINOR — new capability); CLAUDE.md (counts 41 skills / 37 agents / 20 commands + Recent releases paragraph); `docs/CODEBASE_MAP.md` frontmatter `note:` ledger paragraph; README inventory counts; `docs/INTEGRATION_MAP.md` line for the new skill's external-plugin touchpoints (cartographer, ralph-loop, openspec, superpowers — all already-integrated plugins, newly referenced by this skill).
