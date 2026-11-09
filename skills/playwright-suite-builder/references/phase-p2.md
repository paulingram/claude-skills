# Phase P2 — Intuition-map freshness

Compare the map's `last_intuited` frontmatter timestamp against the most recent
commit touching frontend paths. **Reuse the existing detection in
`hooks/frontend_impact.py`** — the same classifier the pipeline already uses to
decide whether a change is frontend-impacting. Do not re-derive "what counts as a
frontend file" here; a second definition is a second thing to drift.

- **Map absent** — call the `intuition-map-lifecycle` `ensure` verb. Authoring
  against a missing map is forbidden.
- **Map stale** (`last_intuited` older than the most recent frontend-touching
  commit) — route the refresh through `intuition-map-lifecycle` `ensure` /
  re-intuit. Never hand-patch the map here.
- **New `low` / `unknown` items produced by the refresh** — these go to the
  bulk-verify gate BEFORE any authoring proceeds. The gate is a domain gate and
  fires regardless of `--proposal-first`, per
  `skills/interaction-intuition` `## Domain-gate carve-out`.
- **Map current** — proceed.

`playwright-user-flows`' standing rule holds unchanged here: tests are never
built on a stale map. Once the map is current, rebuild the project homepage so
its Maps panel never shows a pre-refresh verdict (v4.0.0, best-effort, never
blocking — `project-homepage` `## Rebuild moments`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```
