# Per-codebase mapping (one ct6-converge workflow per codebase, dispatched in parallel across codebases)

Each codebase's mapping work is independent of every other codebase's mapping work — only the later integration mapping depends on all per-codebase maps being done. So all per-codebase mapping ct6-converge workflow runs are dispatched in PARALLEL via a single Agent-tool batch — one teammate per codebase. For a 1-codebase workspace this is a no-op; for a multi-codebase workspace it cuts wall-clock by a factor of the codebase count. Within each codebase's ct6-converge workflow:

### Step 1: Freshness check (short-circuit if current)

- Read `<codebase>/docs/CODEBASE_MAP.md` `last_mapped` (YAML frontmatter).
- Run `git -C <codebase> log -1 --format=%cI` (most recent commit ISO time).
- Read `intake-state.json`'s `map_invalidated` array (codebases flagged as having a known-wrong map).
- Mark `CURRENT` and skip remap ONLY if all three hold: the doc exists, doc-timestamp ≥ latest-commit-timestamp, AND this codebase is NOT in `map_invalidated`.
- Else → remap. Cartographer auto-selects full vs update mode based on the change scope it detects.

**Map invalidation (closes the wrong-but-fresh-map hole).** A timestamp newer than the last commit only proves the map is *recent* — not *correct*. If any agent later in the run discovers the map is materially wrong — a teammate finds a module the map never listed, the integration agent finds an integration the map missed, a diagnostic-researcher traces a path the map mis-described — that agent records the codebase in `intake-state.json`'s `map_invalidated` array. That flag forces the NEXT run's Step 1 to re-derive + re-review the map regardless of timestamps, so a wrong map can never silently survive on freshness alone. The flag is cleared for a codebase once its re-derived map passes the Step 4 tier-3 convergence (three reviewers, recorded).

### Step 2: Run cartographer-team (v3.4.0 — delegates to the new skill)

As of v3.4.0, the cartographer (or native map) + tier-3 3-reviewer convergence flow is encapsulated in the `cartographer-team` skill (`skills/cartographer-team/SKILL.md`). Steps 2 + 3 + the 3-reviewer loop in Step 4 are now ONE dispatch to that skill.

Invoke `cartographer-team` (use the Skill tool with `skill: cartographer-team`) with:

```json
{
  "codebase_path": "<absolute-path>",
  "classification": "<frontend|backend|fullstack|library|infra|data-pipeline>",
  "output_path": "<codebase>/docs/CODEBASE_MAP.md",
  "produce_route_map": true,  // or false for non-frontend classifications
  "route_map_output_path": "<codebase>/docs/ROUTE_MAP.md",
  "frontend_read_only": false,  // intake-and-mapping callers always work on the project's actual codebase
  "freshness_check": true,
  "completion_promise": "CODEBASE MAP COMPLETE"
}
```

The skill body documents the full 5-phase flow internally (C1 freshness pre-check / C2 cartographer / C3 3-reviewer convergence / C4 MemPalace mine / C5 return verdict). Behavior is preserved bit-for-bit; only the implementation location moved from inline-in-this-skill-body to dispatch-the-skill.

**Why delegate:** the `architect-team-pipeline` Phase 0b Branch B (greenfield API + frontend reference) needs the same cartographer + 3-reviewer pattern but with `frontend_read_only: true` and an alternate output path. Sharing one skill body means both pipelines run identical code paths.

### Step 3: If frontend, route-mapper runs inside cartographer-team

`cartographer-team` produces `ROUTE_MAP.md` for frontend / fullstack classifications when `produce_route_map: true`. Same skill, same convergence pattern, same output location.

The route-mapper additionally produces `<codebase>/docs/DESIGN_MAP.md` per the `design-fidelity-mapping` skill IF AND ONLY IF design inputs exist (screenshots/Figma in `$REQ_DIR`, design tokens / Storybook / assets in the codebase). The codebase-map-reviewers MUST NOT flag the absence of DESIGN_MAP.md when no design inputs exist — it is intentionally conditional. When design inputs DO exist, all three docs (CODEBASE_MAP, ROUTE_MAP, DESIGN_MAP) are reviewed together by the tier-3 (3-reviewer) `ct6-converge` workflow.

### Step 4: Review convergence — tier 3, declare → ct6-converge workflow → record (label "CODEBASE MAP COMPLETE")

Map convergence is a tier-3 gate (three independent reviewers — `skills/team-spawning-and-review-gates/references/review-tiers.md`) and runs under the declare → run → record protocol of `skills/common-pipeline-conventions/references/converge-workflows.md`:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" declare --workspace <ws> --kind codebase-map --promise "CODEBASE MAP COMPLETE" --reviewers 3
#   Workflow({ name: "ct6-converge", args: { kind: "codebase-map", promise: "CODEBASE MAP COMPLETE", reviewers: 3, reviewerAgent: "architect-team:codebase-map-reviewer", fixerAgent: "architect-team:route-mapper", artifacts: ["<codebase>/docs/CODEBASE_MAP.md", "<codebase>/docs/ROUTE_MAP.md"] } })
python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" record --workspace <ws> --kind codebase-map --result '<the workflow JSON>'
```

This is the `ct6-converge` workflow with completion promise "CODEBASE MAP COMPLETE" — the promise is the declared gate's label, and the record (all 3 reviewers `ok` in the final round) is what satisfies it. No iteration cap (per `common-pipeline-conventions` `## Unbounded solving discipline`); a human `maxRounds` pauses the gate, it never passes it.

Inside the workflow, each round:

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
3. If all 3 return `status == "ok"` → the workflow returns `converged: true`; the orchestrator records it (`record.py record`), which satisfies the gate labelled `CODEBASE MAP COMPLETE`. Typing the label changes nothing — the record is the exit.
4. Otherwise: aggregate the deficiencies (deduplicate, sort by `map` then `section`), dispatch a targeted update request:
   - For `map: codebase` deficiencies → re-trigger cartographer in update mode, naming the deficient sections.
   - For `map: route` deficiencies → re-trigger route-mapper with the deficient routes/sections.
5. Loop until the record says converged. There is no iteration cap — the loop drives on recorded convergence (all 3 reviewers `ok`), not a count and not a typed string.

If the map genuinely cannot converge because a required input only the owner can supply is missing (e.g. an inaccessible private dependency the reviewers cannot read), surface that specific required input to the owner — loudly, while continuing all other work — and resume once it is provided. The loop never halts on iteration count.
