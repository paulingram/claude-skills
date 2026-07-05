# Design — map-freshness-mempalace-sync

## Context

A docs+memory maintenance run, not new machinery. The deliverable is (1) an independently re-validated pair of maps with any drift fixed in place, (2) a persisted review artifact, and (3) a current palace whose wake-up surfaces v3.29.0–v3.31.1. The refined prompt (grade A/92) is the contract; its scope-out (no source changes, no version bump, no CHANGELOG edit, no L0 identity) is binding.

## Reuse Decision Log

Per `reuse-first-design` (extend > compose > reuse > build-new). This change adds NO new Python and NO new instruction files.

| Need | Decision | Reuse target (exists in repo) | New code justification |
|---|---|---|---|
| CODEBASE_MAP re-validation ×3 | **REUSE** | `agents/codebase-map-reviewer.md` (the Phase −1B 3-reviewer convergence role) | none |
| INTEGRATION_MAP re-validation ×3 | **REUSE** | `agents/integration-explorer.md` (the map's producer role, reviewing per `intake-and-mapping` Phase C) | none |
| Map fix-in-place on deficiencies | **REUSE** | one doc-scope teammate per `team-spawning-and-review-gates` (bounded to the two map files) + independent `task-reviewer` | none |
| Palace mine/sync + wake-up verification | **REUSE** | `mempalace-integration` skill flow; `mempalace mine/wake-up/search` CLI; orchestrator-serialized per the shared-state concurrency model | none |
| Review artifact | **BUILD-NEW (run artifact)** | none — no existing per-run map-review report | `.architect-team/map-review/report-<ts>.md` in the MAIN checkout's shared state — a markdown data artifact, not a module |

## Key decisions

- **The review artifact lives in the MAIN checkout's `.architect-team/`, not the worktree's.** Run worktrees are pruned after auto-merge; the acceptance criterion says "persisted". Shared-state placement (`shared_state_dir()` semantics, same as `run-history/`) survives the prune.
- **Palace writes are orchestrator-only.** Per the pipeline's shared-state concurrency model, `mempalace mine` is orchestrator-serialized; no teammate touches the palace. The MemPalace tasks (REQ-004/005) are Lead work, not teammate work.
- **Both timestamps say current; we re-validate anyway.** `last_mapped: 2026-07-04` post-dates the last content commit, and yesterday's doc-currency run already 3-reviewer-verified both maps. The user explicitly chose a fresh independent pass; a clean verdict with evidence is a legitimate outcome (the review is the deliverable, not the edits).
- **Wing-tagging diagnosis is in scope for REQ-004.** The scoped wake-up (`--wing claude-skills`) is empty while unscoped has content. Diagnose (wrong wing name in prior mines vs. wing filter semantics) and mine this run's content so the scoped wake-up works — or record the honest boundary if the CLI's wing semantics differ from the skill's assumption.
- **Zero-deficiency path.** If all 6 reviewers return clean, no fix teammate spawns; the review evidence records the clean verdicts and REQ-001/002 are satisfied by the review artifact alone.

## Parallelization (disjoint scopes)

- **Group A (REQ-001):** 3 × `codebase-map-reviewer` over `docs/CODEBASE_MAP.md` — read-only, parallel.
- **Group B (REQ-002):** 3 × `integration-explorer` reviewing `docs/INTEGRATION_MAP.md` — read-only, parallel with Group A (6 concurrent read-only agents).
- **Fix teammate (conditional):** owns exactly `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md`; runs only if deficiencies aggregate to a non-empty set; gated by schema-v7 evidence + independent task-reviewer.
- **Group C/D (REQ-003/004/005):** orchestrator work (artifact authoring + palace mines) — sequenced after A/B converge.
- **Group E (REQ-006):** full pytest suite — after any map edits land.

## Risks / boundaries

- **Reviewer false positives.** A "missing entry" claim must cite the actual file/symbol; the aggregation step discards claims that don't verify against the tree (the Lead spot-checks each cited path before briefing the fix teammate).
- **Palace mine `database is locked`.** Retry with tight bounded in-turn backoff; mining is idempotent.
- **Wake-up acceptance is semantic, not exact-string.** "Surfaces v3.29.0–v3.31.1 content" = a post-sync `wake-up` (or `search "run-continuity"` / `search "instruction compliance"`) returns chunks referencing the new releases; the exact L1 selection is the CLI's ranking, not ours.
- **Scope fences.** No source/test/hook edits; no version bump; no CHANGELOG/README/CLAUDE.md edits; L0 identity untouched; frontend maps N/A.
