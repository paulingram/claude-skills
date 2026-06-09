---
name: cartographer-team
description: CT6's multi-agent wrapper around the external cartographer plugin call. One cartographer run produces CODEBASE_MAP.md; 3× codebase-map-reviewer agents independently audit the result and confirm 100% coverage in parallel; targeted re-mapping iterates until all 3 reviewers return ok. Wrapped in a ralph-loop with completion-promise "CODEBASE MAP COMPLETE". Caller-configurable output path so frontend-read-only mode (Phase 0b) can route output to .architect-team/frontend-reference/<codebase-slug>/ instead of <codebase>/docs/. v3.4.0.
---

# Cartographer Team

You are the **Cartographer Team orchestrator**. Drive one cartographer-plugin run + 3× `codebase-map-reviewer` agents in parallel, aggregate their deficiencies, re-trigger targeted cartographer updates, and loop until all 3 reviewers return `ok`. Caller-configurable output path.

## When this skill runs

Three callers as of v3.4.0:

1. **`intake-and-mapping` step B** — produces `<codebase>/docs/CODEBASE_MAP.md` per codebase in scope. The block that was inline (cartographer + 3 reviewers + targeted re-trigger) now delegates to this skill.

2. **`architect-team-pipeline` Phase 0b (greenfield + frontend reference branch)** — produces a reference `CODEBASE_MAP.md` (+ `ROUTE_MAP.md` for frontends) at `<workspace>/.architect-team/frontend-reference/<codebase-slug>/` with `frontend_read_only: true`. The frontend codebase is read as evidence; no file under the frontend codebase is modified.

3. **`bug-fix-pipeline` Phase B−1** — same as caller (1); the bug-fix pipeline reuses `intake-and-mapping` verbatim.

## Inputs

The caller passes a structured `inputs` object:

```json
{
  "codebase_path": "<absolute-path>",
  "classification": "frontend" | "backend" | "fullstack" | "library" | "infra" | "data-pipeline",
  "output_path": "<absolute-path-to-CODEBASE_MAP.md>",
  "produce_route_map": true | false,
  "route_map_output_path": "<absolute-path-or-null>",
  "frontend_read_only": true | false,
  "freshness_check": true | false,
  "completion_promise": "CODEBASE MAP COMPLETE"
}
```

When `freshness_check: true`, the skill first reads the existing map's `last_mapped` frontmatter and compares against `git log -1 --format=%cI` of the codebase root. If the map is newer AND no `map_invalidated` flag is set in `intake-state.json`, the skill short-circuits and returns the existing map verbatim.

## Phase C1 — Freshness pre-check (when requested)

If `freshness_check: true` AND a map already exists at `output_path`:

1. Read the map's `last_mapped` frontmatter.
2. Run `git -C <codebase_path> log -1 --format=%cI` to get the latest commit timestamp.
3. If `last_mapped >= latest-commit` AND `intake-state.json::map_invalidated` does NOT include this `codebase_path` → return the existing map; emit completion promise; exit.

Else proceed to C2.

## Phase C2 — Run cartographer

Trigger the external `cartographer` plugin's own flow against `codebase_path` (per `intake-and-mapping/SKILL.md` step 2). The plugin produces a draft `CODEBASE_MAP.md` at the codebase's standard location.

When `frontend_read_only: true`, after the cartographer plugin returns:

- **Move** the produced `CODEBASE_MAP.md` from `<codebase>/docs/CODEBASE_MAP.md` to the caller-configured `output_path` (which will be under `<workspace>/.architect-team/frontend-reference/<codebase-slug>/`).
- **Delete** the temporary file at `<codebase>/docs/CODEBASE_MAP.md` so the frontend codebase's working tree is left untouched.

When the `classification` is `frontend` or `fullstack` AND `produce_route_map: true`, additionally dispatch the existing `route-mapper` agent (and the existing `design-fidelity-mapping` skill when design inputs are present) to produce `ROUTE_MAP.md` at the caller-configured `route_map_output_path`. Same read-only treatment applies in `frontend_read_only` mode.

## Phase C3 — 3-reviewer convergence (wrapped in a ralph-loop)

Wrap the entire convergence in `/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE"` — the loop runs until the completion-promise is satisfied (all 3 reviewers return `ok`); no iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`):

1. The orchestrator dispatches 3 `codebase-map-reviewer` agents in parallel via a single Agent-tool batch (subagents mode) OR creates 3 reviewer tasks in the shared list (teams mode). Each reviewer receives:
   - The current `CODEBASE_MAP.md` (and `ROUTE_MAP.md` when applicable) from `output_path`
   - The `codebase_path` for cross-checking against the actual code
   - The `classification`

2. Each reviewer returns:

   ```json
   {
     "reviewer_id": "<N>",
     "status": "ok" | "deficient",
     "deficiencies": [
       {
         "kind": "missing-module" | "missing-route" | "missing-api-entry" | "stale-entry" | "incorrect-classification",
         "evidence": "<file:line | route definition | etc.>",
         "remediation_hint": "<one-line suggestion for the cartographer>"
       }
     ]
   }
   ```

3. **All 3 ok** → emit `"CODEBASE MAP COMPLETE"`; exit the ralph-loop.

4. **Any deficient** → aggregate the deficiencies; re-trigger the cartographer plugin in update mode (or `route-mapper` for route-specific deficiencies) naming the deficient sections; loop.

The `frontend_read_only` flag continues to apply during every iteration — re-triggered cartographer runs MUST output to the alternate path, and any auto-generated file in `<codebase>/docs/` MUST be moved + deleted.

## Phase C4 — Mine to MemPalace (when not in read-only mode)

When `frontend_read_only: false`, mine the final `CODEBASE_MAP.md` (and `ROUTE_MAP.md` / `DESIGN_MAP.md` when produced) to MemPalace per `mempalace-integration`:

```bash
mempalace --palace <palace> mine "<output_path>" --wing <wing>
```

When `frontend_read_only: true`, SKIP the MemPalace mining — the reference maps are run-scoped, not project-history. The orchestrator can choose to mine them under a dedicated `reference` wing if it wants cross-run persistence, but the default is don't-mine.

## Phase C5 — Return verdict

Return to the caller:

```json
{
  "codebase_path": "<...>",
  "output_path": "<CODEBASE_MAP.md path>",
  "route_map_output_path": "<ROUTE_MAP.md path or null>",
  "freshness_short_circuited": true | false,
  "reviewer_iterations": N,
  "final_status": "complete"
}
```

## Frontend-read-only enforcement (hard rule)

When `frontend_read_only: true`:

- NO file under `codebase_path` may be created, modified, or deleted (except for the temporary cartographer-plugin output that the orchestrator moves + cleans).
- ALL final analysis output (CODEBASE_MAP.md / ROUTE_MAP.md / DESIGN_MAP.md if applicable) lands at the caller-configured paths, which the caller is responsible for setting to a location outside the frontend codebase.
- The v3.0.0 PreToolUse guardrail's `.architect-team/` allow-prefix already covers the canonical alternate paths under `.architect-team/frontend-reference/`. The skill body cannot bypass that guardrail; the orchestrator at every dispatch is also responsible.

A violation (write inside the frontend codebase during `frontend_read_only: true` mode) is a verdict-failure condition the caller should treat as a `pipeline-bypassed-needs-rerun` SR.

## Disciplines this skill respects

- v3.0.0 unilateral-override — the cartographer cannot decide to skip the 3-reviewer convergence.
- v1.6.0 teammate-git-discipline — no destructive git ops; teammates use `git diff <BASELINE_SHA>` for verification only.
- v0.9.19 3-reviewer convergence — the canonical pattern this skill implements.
- v3.3.0 test-run monitor — N/A (this is an analysis skill, not a test runner).

## What this skill is NOT

- Not a code generator. It produces structural maps, not code.
- Not the cartographer plugin itself. It WRAPS the external cartographer plugin call with CT6's multi-agent audit pattern.
- Not a fix loop. Persistent deficiencies (10+ iterations without convergence) become a caller-side escalation; this skill does not file them itself.
