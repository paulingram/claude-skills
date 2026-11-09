# Phase M1 — Maps freshness check

The mini variant uses **cached maps** wherever possible. Per `intake-and-mapping`, for each codebase the requirement touches:

1. Locate `<codebase>/docs/CODEBASE_MAP.md` and `<codebase>/docs/ROUTE_MAP.md` and the root `docs/INTEGRATION_MAP.md`.
2. Compare each map's `last_mapped` (or equivalent timestamp in its frontmatter) to the newest mtime of source files in its scope.
3. **Map fresh** (`last_mapped` ≥ newest src mtime) → use it as-is.
4. **Map stale or missing** → refresh **only the affected codebase**. Single-pass: dispatch `cartographer` for `CODEBASE_MAP.md` (or, when that CONDITIONAL plugin is absent, produce it in the house shape per `skills/common-pipeline-conventions/references/native-methodology.md`) and `route-mapper` for `ROUTE_MAP.md`. **Do NOT** run a tier-3 reviewer convergence on the refreshed map; do NOT regenerate `INTEGRATION_MAP.md` unless the change crosses codebases. Single-pass refresh is the mini variant's whole-pipeline shape; trust the cartographer's first pass.

A stale `INTEGRATION_MAP.md` is the one case worth a tier-3 escalation (map convergence, per `skills/team-spawning-and-review-gates/references/review-tiers.md`) — but only when the change crosses codebases: the Lead runs the `ct6-converge` workflow with the `integration-map` preset (`kind: "integration-map"`, `promise: "INTEGRATION MAP COMPLETE"`, `reviewerAgent: "architect-team:integration-explorer"`, `fixerAgent: "architect-team:master-synthesizer"`, `reviewers: 3`), declared before the workflow runs and recorded after it (`skills/common-pipeline-conventions/references/converge-workflows.md`). For an in-codebase change, ignore stale integration-map sections.

**Homepage rebuild once the maps are current (v4.0.0, best-effort, never blocking).** After the freshness check (and any refresh) has left the maps current, rebuild the project homepage so its Maps panel never shows a pre-remap verdict (`project-homepage` `## Rebuild moments`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```

Persist the maps (fresh or refreshed) into the working context for M2.
