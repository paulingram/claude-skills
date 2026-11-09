# Re-entry state

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
2. For each codebase: compare current `git log -1 --format=%cI` against the persisted `head_commit_time`. If unchanged → use existing maps. If changed → re-run mapping per the per-codebase ct6-converge workflow above.
3. If any codebase map regenerated → re-run integration mapping. Else use existing `INTEGRATION_MAP.md`.
4. Update `intake-state.json` at the end.
