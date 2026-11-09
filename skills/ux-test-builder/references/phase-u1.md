# Phase U1 — Site mapping (reuses `intake-and-mapping`)

Phase U1 reuses the `intake-and-mapping` discipline VERBATIM. The orchestrator runs the per-codebase freshness check on `CODEBASE_MAP.md` / `ROUTE_MAP.md` / `DESIGN_MAP.md` / `INTERACTION_INTUITION_MAP.md`. If any is stale (doc older than the most recent commit OR `map_invalidated` flagged), re-derive via `cartographer` (or the native mapping form in `skills/common-pipeline-conventions/references/native-methodology.md` when that CONDITIONAL plugin is absent) + `route-mapper` + `interaction-intuiter` per the standard tier-3 `ct6-converge` map convergence — the `codebase-map` preset (`reviewers: 3`, promise `CODEBASE MAP COMPLETE`), declared before the workflow runs and recorded after it (`skills/common-pipeline-conventions/references/converge-workflows.md`). If the maps are current, short-circuit.

**Project principles at intake (v4.0.0, per `project-principles`).** Once per project: when `<workspace>/.architect-team/principles.json` is absent, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" default-set --workspace <ws>` (proposed never binds); when the user provided a document, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" extract-candidates <file>`, `Read` it, and confirm the drafted statements in ONE `AskUserQuestion` (a domain gate; nothing becomes confirmed silently). Every explorer and executor brief carries the output of `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace <ws>` exactly as the intake record is carried.

**Homepage rebuild once the maps are current (v4.0.0, best-effort, never blocking).** After the freshness check (and any re-derive) has left the maps current (`project-homepage` `## Rebuild moments`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```

The Phase −1D bulk-verify gate still fires when low-confidence interaction-intuition items surface (per the v0.9.21 domain-gate rule). The user resolves them BEFORE U3 expansion begins — the explorers need confirmed intuitions to propose accurate flows.

**For `--dev` targets:** the site is the project's dev environment; the maps are the project's `<codebase>/docs/` maps.
**For URL targets:** the maps describe the WORKSPACE codebase (which models the target site); the target's URL is just the execution destination. When the URL points at a site the workspace doesn't model, the orchestrator escalates — the literal flow can be authored from the prose alone, but explorer expansion needs map-based context.
