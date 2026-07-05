## ADDED Requirements

### Requirement: CODEBASE_MAP whole-repo re-validation

`docs/CODEBASE_MAP.md` SHALL be independently re-validated against the actual code at HEAD across the whole repository (`skills/`, `agents/`, `commands/`, `hooks/`, `scripts/`, `services/`, `tests/`, `docs/`, `.claude-plugin/`) by three independent reviewers, with every found stale, missing, or incorrect entry fixed in place, or an explicit evidence-backed clean verdict recorded.

#### Scenario: three reviewers each return a structured verdict

- **WHEN** the three codebase-map-reviewer dispatches complete
- **THEN** each has returned a structured verdict (`ok` or `deficient` with a deficiency list citing file/section evidence)
- **AND** the aggregation discards any claimed deficiency that does not verify against the actual tree

#### Scenario: verified deficiencies are fixed in place

- **WHEN** the aggregated deficiency set is non-empty
- **THEN** each verified deficiency is fixed in `docs/CODEBASE_MAP.md` by a bounded doc-scope teammate whose completion is gated by schema-v7 review evidence plus an independent task-reviewer pass verdict
- **AND** when the aggregated set is empty, no fix teammate spawns and the clean verdict is recorded with evidence

### Requirement: INTEGRATION_MAP re-validation

`docs/INTEGRATION_MAP.md` SHALL be independently re-validated against the actual v3.31.1 integration surface (hook wiring, command→skill→agent flows, service adapters, cross-surface counts) by three independent reviewers, with every found deficiency fixed in place under the same gating as the CODEBASE_MAP fixes, or an explicit clean verdict recorded.

#### Scenario: three reviewers each return a structured verdict

- **WHEN** the three integration-map reviewer dispatches complete
- **THEN** each has returned a structured verdict (`ok` or `deficient` with cited evidence)
- **AND** verified deficiencies are fixed in place; unverified claims are discarded with the discard reason recorded

### Requirement: Persisted map-review artifact

The run SHALL persist a map-review report under the MAIN checkout's `.architect-team/map-review/` enumerating, per map, the sections checked, every deficiency found with its resolution (or the explicit clean verdict), and the reviewer verdicts it aggregates.

#### Scenario: the artifact survives the run worktree

- **WHEN** the report is written
- **THEN** its path is under `/Users/paulingram/Documents/code/claude-skills/.architect-team/map-review/` (shared state, not the prunable run worktree)
- **AND** it names both maps, the three-per-map reviewer verdicts, and each deficiency's disposition

### Requirement: MemPalace currency sync

The shared palace at the main checkout's `.mempalace/palace` SHALL be brought current: the v3.29.0–v3.31.1 release content, the re-validated maps, and this run's artifacts mined in (orchestrator-serialized), and the wing-tagging discrepancy (scoped wake-up empty while unscoped has content) diagnosed with the outcome recorded.

#### Scenario: post-update wake-up surfaces the new releases

- **WHEN** `mempalace wake-up` (or a targeted `mempalace search`) runs after the sync
- **THEN** the returned content references v3.29.0–v3.31.1 material (librarian-installable / run-continuity / instruction-compliance) and no longer tops out at v3.28.0

#### Scenario: wing discrepancy is diagnosed

- **WHEN** the sync completes
- **THEN** the review artifact records why `wake-up --wing claude-skills` was empty and what the sync did about it (correct wing tagging, or the honest boundary if the CLI's wing semantics differ)

### Requirement: Review findings filed into the palace

The map-review report SHALL itself be mined into the palace so future runs can recall this run's findings semantically.

#### Scenario: the findings are searchable

- **WHEN** `mempalace search "map freshness review"` (or equivalent) runs after filing
- **THEN** the results include content from this run's map-review report

### Requirement: Green suite invariant

The full pytest suite SHALL remain green (zero failures, 5164 collected) after all map edits land, since this change touches only the two map docs plus gitignored run artifacts. The documented canonical count 5159 passed + 5 skipped holds on Windows-with-PyYAML; on this run's macOS-without-PyYAML environment the equivalent green state is 5160 passed + 4 skipped (the 2 Unix-symlink tests run and pass; the 1 PyYAML-dependent test skips) — verified mechanism, recorded mid-run when the reviewer wave surfaced the environment dependence.

#### Scenario: suite unchanged after the run

- **WHEN** `python -m pytest` runs from the worktree root after all edits
- **THEN** it reports zero failures with 5164 tests collected
- **AND** the pass/skip split matches the environment's explained split (5160 + 4 here; canonical 5159 + 5 on Windows-with-PyYAML), with no drift beyond the 3 known environment-conditional tests
