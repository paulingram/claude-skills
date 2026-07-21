# design — gstack-profile-comparison

## Approach

Analysis-only run in subagents dispatch mode. Four parallel profiler subagents (one per gstack tier) produce per-tier findings JSON/markdown with file citations into the run worktree's `.architect-team/gstack-comparison/findings/`. A CT6-side grounding pack (the existing `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md`, `CLAUDE.md`) supplies the our-side citations — no re-mapping needed (maps verified CURRENT at Phase −1). The orchestrator synthesizes the matrix + report + backlog; an independent adversarial reviewer (producer ≠ checker) verifies every citation resolves and attacks weak/overreaching claims before the report is final; the Phase 7 master-review audit independently re-verifies coverage.

## Static-read boundary (non-negotiable)

No gstack code is executed — no `bin/` tools, no `dev-setup`, no CI workflows, no `bun install`. Profilers read files only. The 912 KB `CHANGELOG.md` and 144 KB `TODOS.md` are skimmed for recency/direction signals only (head/tail + grep), never read in full.

## Artifact placement

- Per-tier findings + working state: `<worktree>/.architect-team/gstack-comparison/findings/` (per-run state).
- Final report + backlog: `/Users/paulingram/Documents/code/claude-skills/.architect-team/gstack-comparison/` (MAIN checkout — durable across worktree cleanup, gitignored). Deviation from per-run-state convention is deliberate: the deliverable must outlive the run worktree; recorded here per the refined brief's acceptance criterion 2.
- Tracked footprint: ONLY `openspec/changes/gstack-profile-comparison/` (this change), archived at Phase 7.

## Reuse Decision Log

| Proposed new thing | Ladder verdict | Decision |
|---|---|---|
| New source module for comparison | REJECTED — build-new unneeded | No source code is written this run; the analysis is agent work + markdown artifacts. |
| New comparison-report format | REUSE | Mirrors the run-report conventions already used under `.architect-team/runs/` (per `architect-team-pipeline` Phase 8) + the matrix style of `docs/INTEGRATION_MAP.md` tables. |
| New backlog schema | REUSE (extend) | Items follow the solution-requirement fields (`team-spawning-and-review-gates` `## Solution Requirements`: title, why, acceptance_criteria, scope, suggested_team) with `status: proposed` + `value`/`effort`/`ratio` fields added — consumable by future runs as prose or SR seeds. Cited: CODEBASE_MAP §hooks (SR schema consumers). |
| New OpenSpec capability `gstack-comparative-analysis` | BUILD-NEW (sanctioned) | An analysis-record capability; precedent `documentation-currency-refresh` created by the `2026-07-16-docs-currency-v3-39-1` archived change. No existing capability covers external-package comparative analysis. |
| Re-mapping CT6 (cartographer) | REJECTED — reuse existing maps | `docs/CODEBASE_MAP.md` verified CURRENT at Phase −1 (its currency note describes the post-stamp commits' change); read-only run, drift risk nil. |

## Third-party dependencies

None added. Profilers use Read/Glob/Grep/Bash(read-only) only.

## Producer/checker seams

1. Profilers produce findings → the synthesis consumes but the adversarial reviewer independently re-resolves every citation against both trees.
2. Orchestrator produces the report/backlog → the adversarial reviewer verdict gates finalization.
3. Orchestrator walks coverage at Phase 7 → the `system-architect` master-review audit independently re-verifies; its verdict gates the commit.
