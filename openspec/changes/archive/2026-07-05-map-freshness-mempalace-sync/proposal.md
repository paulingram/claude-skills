## Why

"Review this codebase and update mempalce" — refined (proposal-refiner, grade A/92) to: re-validate the two codebase maps against the actual v3.31.1 code across the WHOLE repository, then bring the MemPalace palace current. The repo just fast-forwarded `320a69a → ff47a50` (v3.29.0 librarian-installable, v3.30.0 run-continuity enforcement, v3.31.0/.1 instruction-compliance standard + doc-currency refresh), while the workspace palace at `.mempalace/palace` last synced 2026-06-18 — its wake-up tops out at v3.28.0 content, so every future run starts blind to three releases. Additionally the wing-scoped wake-up (`--wing claude-skills`) returns "No memories yet" while the unscoped wake-up has content — a wing-tagging discrepancy that undermines the Phase −1A scoped-wake-up contract and needs diagnosis during the sync.

Honest context: the maps were re-verified by three independent reviewers YESTERDAY (2026-07-04, the doc-currency-refresh run — one cross-doc defect found and fixed, stamps bumped). The user knows this and explicitly chose a fresh whole-codebase re-validation anyway; this change independently re-validates rather than assuming the prior evidence.

## What Changes

- **Re-validate `docs/CODEBASE_MAP.md`** against the actual code across the whole repository (`skills/`, `agents/`, `commands/`, `hooks/`, `scripts/`, `services/`, `tests/`, `docs/`, `.claude-plugin/`) via 3 independent codebase-map-reviewer agents; aggregate deficiencies; fix any stale/missing/incorrect entry in place. (REQ-001)
- **Re-validate `docs/INTEGRATION_MAP.md`** on the same terms via 3 independent integration-explorer reviewers (hook wiring, command→skill→agent flows, services adapters, cross-surface counts). (REQ-002)
- **NEW run artifact** — a persisted map-review report at `<main-checkout>/.architect-team/map-review/report-<ts>.md` enumerating, per map, every checked section and every deficiency found (or an explicit clean verdict). Written to the MAIN checkout's `.architect-team/` (shared state) so it survives run-worktree pruning. (REQ-003)
- **MemPalace sync** — orchestrator-serialized `mempalace mine` of the v3.29.0–v3.31.1 CHANGELOG content, the re-validated maps, and this run's triage/findings artifacts into the shared palace; diagnose the wing-tagging discrepancy; post-update wake-up must surface v3.29.0–v3.31.1 content. (REQ-004)
- **File the review findings into the palace** — the map-review report is itself mined so future runs can recall it semantically. (REQ-005)
- **Green suite invariant** — `python -m pytest` from the worktree stays at the documented 5159 passed + 5 skipped; this change touches only the two map docs plus gitignored run artifacts. (REQ-006)

## Capabilities

### New Capabilities

- `map-freshness-mempalace-sync`: an independent whole-repo freshness re-validation of the two codebase maps (3-reviewer convergence per map, deficiencies fixed in place, a persisted review artifact in shared state) plus a MemPalace currency sync (palace surfaces the latest release content post-update, review findings filed, wing-tagging diagnosed) under a green-suite invariant.

### Modified Capabilities

None. No code capability changes behavior — the deliverables are two re-validated docs, a review artifact, and palace state.

## Impact

**Affected files:**
- `docs/CODEBASE_MAP.md` / `docs/INTEGRATION_MAP.md` — RE-VALIDATED; edited in place ONLY on found deficiencies.
- `<main-checkout>/.architect-team/map-review/report-<ts>.md` — NEW (run artifact, shared state, gitignored).
- `<main-checkout>/.mempalace/palace` — UPDATED (mined content; shared state, gitignored).
- `openspec/changes/map-freshness-mempalace-sync/**` — this change's artifacts.
- Source code, tests, hooks, `skills/`/`agents/`/`commands/`, `.claude-plugin/plugin.json` + `marketplace.json`, `CHANGELOG.md`, `README.md`, `CLAUDE.md` — UNTOUCHED (scope-out per the refined prompt: no version bump, nothing ships beyond the two map docs).
