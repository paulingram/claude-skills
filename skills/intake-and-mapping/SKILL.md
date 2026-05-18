---
name: intake-and-mapping
description: Use when entering Phase −1 of the architect-team pipeline, when any agent needs to consult codebase or integration maps, or when checking whether existing maps need refresh. Defines codebase discovery rules, the per-codebase ralph-loop with 3 reviewers (exit string "CODEBASE MAP COMPLETE"), frontend detection that triggers the route-mapper, and the integration ralph-loop with 3 explorers + master-synthesizer (exit string "INTEGRATION MAP COMPLETE"). Handles re-entry freshness checks against git commit timestamps.
---

# Intake & Mapping

The pipeline cannot reason about a codebase it has not mapped. This skill defines how the orchestrator builds, validates, and refreshes the structural knowledge it needs before any planning or implementation work begins.

## Codebase discovery

Resolve the set of codebases the work will touch, in priority order:

1. `$REQ_DIR/codebases.json` — shape: `{ "codebases": [ { "name": "...", "path": "<absolute or relative>" } ] }`.
2. `codebases:` key in the YAML frontmatter of `$REQ_DIR/proposal.md` or `$REQ_DIR/design.md`.
3. Current working directory as a single codebase.
4. Ask the user.

Resolve every path to an absolute path. Assert each is a git repo (`git -C <path> rev-parse --is-inside-work-tree`). Classify each:

- **frontend** — see frontend detection markers below.
- **backend** — has `pyproject.toml` / `setup.py` / `requirements.txt` / `go.mod` / `pom.xml` / `Cargo.toml` / equivalent.
- **fullstack** — both sets of markers in one repo (e.g., Next.js full-stack monorepo). Runs cartographer + route-mapper.
- **library** — package manifest but no obvious app entry.
- **infra** — Terraform / Pulumi / Helm / Kubernetes manifests as the dominant content.

## Frontend detection markers (any one is sufficient)

- `package.json` with a frontend framework dep: react, vue, svelte, angular, next, nuxt, remix, solid, qwik, astro, sveltekit, gatsby, preact, expo, lit, alpinejs, htmx.
- HTML files in `src/`, `public/`, or `app/`.
- A routing config: `pages/`, `app/router/`, `src/routes/`, `react-router`, `vue-router`, `@angular/router`, `expo-router`, `tanstack/router`.
- `index.html` as the entry.

## Per-codebase mapping (one ralph loop per codebase)

For each codebase:

### Step 1: Freshness check (short-circuit if current)

- Read `<codebase>/docs/CODEBASE_MAP.md` `last_mapped` (YAML frontmatter).
- Run `git -C <codebase> log -1 --format=%cI` (most recent commit ISO time).
- If doc exists AND doc-timestamp ≥ latest-commit-timestamp → mark `CURRENT`; skip remap.
- Else → remap. Cartographer auto-selects full vs update mode based on the change scope it detects.

### Step 2: Run cartographer

Trigger the `cartographer` plugin's own flow against the codebase. It produces `<codebase>/docs/CODEBASE_MAP.md` with `last_mapped` frontmatter.

### Step 3: If frontend, run route-mapper

For codebases classified as frontend or fullstack, additionally spawn the `route-mapper` agent. It produces `<codebase>/docs/ROUTE_MAP.md` with `last_routed` frontmatter per the `frontend-route-mapping` skill's schema.

The route-mapper additionally produces `<codebase>/docs/DESIGN_MAP.md` per the `design-fidelity-mapping` skill IF AND ONLY IF design inputs exist (screenshots/Figma in `$REQ_DIR`, design tokens / Storybook / assets in the codebase). The codebase-map-reviewers MUST NOT flag the absence of DESIGN_MAP.md when no design inputs exist — it is intentionally conditional. When design inputs DO exist, all three docs (CODEBASE_MAP, ROUTE_MAP, DESIGN_MAP) are reviewed together by the 3-reviewer ralph loop.

### Step 4: Review ralph loop (exit string "CODEBASE MAP COMPLETE")

Wrap the review in:

```
/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE" --max-iterations 10
```

Where the review prompt instructs the orchestrator to:

1. Spawn 3 `codebase-map-reviewer` agents IN PARALLEL (single message, multiple Task tool calls). Each receives:
   - The codebase root path.
   - `CODEBASE_MAP.md` (and `ROUTE_MAP.md` if present).
   - The minimum-completeness rubric (every directory ≥1 doc line; every entry point named; every public API of every top-level module covered; for ROUTE_MAP: every route, every dynamic param, every navigation edge, every API endpoint).
2. Each reviewer returns:
   ```json
   { "status": "ok" | "deficient",
     "deficiencies": [
       { "map": "codebase" | "route", "section": "<heading>", "gap": "<what's missing>",
         "evidence": "<file:line or symbol the reviewer found that isn't reflected>" }
     ] }
   ```
3. If all 3 return `status == "ok"` → emit the exact line `CODEBASE MAP COMPLETE` (this triggers the ralph-loop completion promise and exits).
4. Otherwise: aggregate the deficiencies (deduplicate, sort by `map` then `section`), dispatch a targeted update request:
   - For `map: codebase` deficiencies → re-trigger cartographer in update mode, naming the deficient sections.
   - For `map: route` deficiencies → re-trigger route-mapper with the deficient routes/sections.
5. Loop. The ralph-loop's `--max-iterations 10` cap prevents runaway.

If the loop hits the iteration cap without "CODEBASE MAP COMPLETE", surface this to the user as a blocker — do not proceed silently.

## Integration mapping (one ralph loop, all codebases)

After every codebase has a complete map:

```
/ralph-loop "<synthesis prompt>" --completion-promise "INTEGRATION MAP COMPLETE" --max-iterations 8
```

Synthesis prompt:

1. Spawn 3 `integration-explorer` agents IN PARALLEL. Each receives:
   - Every `<codebase>/docs/CODEBASE_MAP.md`.
   - Every `<codebase>/docs/ROUTE_MAP.md` where present.
   - Read access to boundary code: HTTP clients (`requests`, `httpx`, `axios`, `fetch`), queue consumers/producers, shared schemas (protobuf, OpenAPI, GraphQL SDL), deployment configs (compose files, k8s manifests, Terraform), env files, contract files.
2. Each agent independently writes its own synthesis to `<workspace>/.architect-team/integration-drafts/<agent-N>.md`.
3. **Round-robin convergence:** each agent reads the other 2's drafts, flags gaps, revises its own. Iterate until each agent confirms the other two's drafts each cover 100% of what their own draft covers.
4. Spawn `master-synthesizer`. It reads all 3 drafts; produces `<workspace>/docs/INTEGRATION_MAP.md` with:
   - YAML frontmatter: `last_synthesized: <ISO 8601 UTC>`, `codebases: [<names>]`, `source_drafts: [<paths>]`.
   - Sections: Overview, Per-Pair Integration table, Contracts/Schemas catalog, Deployment topology, Known failure modes, Open questions.
5. **Confirmation pass:** present the master doc to each of the 3 original explorers; each must reply with `confirms: true` or list discrepancies. Master-synthesizer revises until all 3 confirm.
6. When all 3 confirm → emit `INTEGRATION MAP COMPLETE`.

## Re-entry state

After Phase −1 completes (or short-circuits), persist:

`<workspace>/.architect-team/intake-state.json`:
```json
{
  "schema_version": 1,
  "completed_at": "<ISO 8601 UTC>",
  "codebases": [
    {
      "name": "api",
      "path": "/abs/path/to/api",
      "head_sha": "<git rev-parse HEAD>",
      "head_commit_time": "<git log -1 --format=%cI>",
      "codebase_map_last_mapped": "<from frontmatter>",
      "route_map_last_routed": "<from frontmatter or null>"
    }
  ],
  "integration_map_last_synthesized": "<from frontmatter>"
}
```

On the NEXT invocation of `/architect-team`:

1. Re-run discovery (the codebase set may have changed).
2. For each codebase: compare current `git log -1 --format=%cI` against the persisted `head_commit_time`. If unchanged → use existing maps. If changed → re-run mapping per the per-codebase ralph loop above.
3. If any codebase map regenerated → re-run integration mapping. Else use existing `INTEGRATION_MAP.md`.
4. Update `intake-state.json` at the end.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "The map is mostly right, I'll just proceed" | Mostly-right plus undetected gaps is how parallel teams produce conflicting code. The 3-reviewer ralph loop is cheap insurance. |
| "Cartographer already handles freshness, we don't need our own check" | Cartographer's check is per-doc. Ours covers integration-map freshness across codebases. Both run. |
| "Just one reviewer is enough" | Single reviewers miss things consistently. The 3-agent independent verdict is the whole point. |
| "Skip integration mapping for single-codebase work" | Run it anyway — it generates the INTEGRATION_MAP.md the reuse-first-design skill consults. The doc may be short, but the file must exist. |
