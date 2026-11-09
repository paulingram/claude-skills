# Codebase discipline registry (v2.18.0)

CT6 disciplines that mutate the target codebase (annotation insertion, fixture authoring, mock removal, persona inventory build) need a per-codebase **discipline registry** so the orchestrator knows whether each discipline has already been applied. When the orchestrator detects an un-applied discipline at pipeline start, the registry mechanism **auto-executes** the discipline's update routine before the user's actual run continues.

**Failure shape** (verbatim case in CHANGELOG v2.18.0): the user needs to *"know if our system is already running / updated or if we need to execute an update, such as the classifier, and then … do this automatically when detected"*. Concretely: shipping the classifier as a CT6 plugin update does NOT add `@prod-safe` / `@not-prod-safe` annotations to a user's existing test files; without v2.18.0 the user must remember to run the classifier per codebase. v2.18.0 detects the unapplied discipline at pipeline start and applies it automatically.

### Per-workspace registry artifact

Path: `<workspace>/.architect-team/discipline-registry.json` (gitignored — runtime state, not source).

```json
{
  "schema_version": "1.0",
  "ct6_version_last_seen": "2.18.0",
  "disciplines_applied": [
    {
      "discipline": "prod-safe-test-classification",
      "ct6_version": "2.17.0",
      "applied_at": "2026-06-04T15:00:00Z",
      "applied_by_run_id": "<uuid>",
      "artifact_path": ".architect-team/test-prod-safety/classification-report-2026-06-04T15-00-00.json",
      "summary": {"prod_safe": 12, "not_prod_safe": 4, "ambiguous": 1, "unclassified": 0}
    }
  ],
  "last_freshness_check": "2026-06-04T15:30:00Z"
}
```

`disciplines_applied` is a flat list. A discipline is "applied" iff an entry exists AND its `applied_at` is newer than the latest `mtime` of the codebase surface the discipline covers (e.g., for v2.17.0 — the newest test file's mtime). When the surface advances past the applied timestamp, the discipline becomes "stale" and must be re-applied.

### Canonical discipline catalog (initial v1 entries)

| `discipline` | CT6 version | Detect (what counts as "applied") | Auto-update routine |
|---|---|---|---|
| `prod-safe-test-classification` | v2.17.0 | A `discipline-registry.json` entry exists OR every test file in the codebase carries `@prod-safe` or `@not-prod-safe` in its first 20 lines | Run the `test-prod-safety-classifier` skill in mass-classify mode with `--write-annotations` |
| `live-data-wiring` | v2.6.0 | A `discipline-registry.json` entry exists OR no `_MOCK_STATE_SIGNATURES` pattern survives in the codebase | Surface gaps via SR; do NOT auto-edit production code (mock removal can change semantics) |
| `multi-persona-path-coverage` | v2.11.0 | `<workspace>/.architect-team/persona-inventory.json` exists AND is non-empty | Spawn the system-architect agent to author the persona inventory; do NOT auto-execute (requires user confirmation of personas) |
| `affordance-coverage` | v2.13.0 | A scan of the codebase for `_FILE_UPLOAD_AFFORDANCE_SIGNATURES` returns either no matches OR a matching registry entry exists | Surface gaps via SR; do NOT auto-edit (UX decision, not mechanical) |

The catalog distinguishes **auto-apply-safe** disciplines (annotation insertion, classification metadata — mechanical, reversible, low-risk) from **SR-route-only** disciplines (mock removal, persona inventory, UX-decision affordances — require human judgment). Only auto-apply-safe disciplines fire the auto-update routine; the rest surface an SR and let the existing fix loop handle them.

### 3 named severities

| Severity | Trigger |
|---|---|
| `discipline-registry-missing` | `<workspace>/.architect-team/discipline-registry.json` does not exist (first-time setup; create with one entry per applied discipline OR an empty list if none have been applied) |
| `discipline-not-applied` | Catalog discipline has NO entry in `disciplines_applied` AND the codebase contains surface the discipline covers |
| `discipline-stale` | Catalog discipline has an entry BUT the relevant codebase surface has been modified since `applied_at` (e.g., new test files added since the classifier last ran) |

### Phase 0.1 auto-update protocol

When `Phase 0.1 — Discipline freshness check` (NEW pipeline phase between MemPalace wake-up and Phase −1) detects an un-applied **auto-apply-safe** discipline:

1. The orchestrator prints a one-line banner: `▸ CT6 v2.18.0: applying <discipline> (auto-update — discipline-registry was missing or stale)`
2. Invokes the auto-update routine for that discipline (e.g., for v2.17.0: the `test-prod-safety-classifier` skill in `mass-classify` mode with `--write-annotations`)
3. On success, records the application in `<workspace>/.architect-team/discipline-registry.json` (creating the file if missing)
4. Proceeds to Phase −1 with the discipline now applied

For an **SR-route-only** discipline, Phase 0.1 emits a `discipline-not-applied` SR with origin kind `discipline-not-applied` and routes it through the existing fix loop — the user (not the orchestrator) decides whether to apply it now or defer.

### New SR origin kind

`discipline-not-applied` — fires from Phase 0.1's freshness check when a catalog discipline is detected as un-applied AND not auto-apply-safe.

### Cross-references

- `hooks/discipline_registry.py` — the canonical catalog + helper module (`read_registry`, `freshness_check`, `record_application`).
- `hooks/vao_tools.py::verify_discipline_registry_current` — the 16th Layer 3 tool.
- `commands/discipline-status.md` — the 17th slash command (`/architect-team:discipline-status` + optional `--apply` flag).
- `architect-team-pipeline/SKILL.md` `## Phase 0.1 — Discipline freshness check` — the orchestrator-side wiring.
- `bug-fix-pipeline/SKILL.md` `## Phase 0.1 — Discipline freshness check` — bug-fix pipeline gets the same auto-update.
- `mini-architect-team-pipeline/SKILL.md` `## Phase 0.1 — Discipline freshness check` — mini-pipeline likewise.
- `tests/fixtures/vao/discipline-registry-not-applied.json` — canonical case (v2.17.0 classifier un-applied; expected auto-execute).
- Companion to v2.17.0 prod-safe test classification (its applied artifact is the FIRST registry entry) — different layer: v2.17.0 says "every test must be classified"; v2.18.0 says "and the orchestrator knows whether that's been done yet, and does it automatically if not."
