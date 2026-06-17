## Why

CT6-6 §2 asks for a **closeout agent** (CO-1…CO-3): one that fires before any suggestion to compact context, reviews the documentation and the changes made against the requirements, and — if the documentation looks lax — suggests continuing the update and then performs the update itself. The repo already has the `documentation-currency` discipline, the `doc-updater` agent, and the `system-architect` currency audit — but all of those run only inside a full pipeline's Phase 8. The missing piece is a session-end double-check that fires at ANY work boundary (especially before compaction) and works from the git working tree alone. This is component 2 of the in-repo CT6-6 tier.

## What Changes

- **New `PreCompact` hook + deterministic engine (CO-1)** — `hooks/precompact-closeout.py` (the first `PreCompact` wiring in `hooks/hooks.json`) runs `hooks/closeout_check.py` (stdlib-only) against the working tree and, when the documentation-currency inventory looks stale, injects a closeout reminder before compaction. Non-blocking + fail-open. (REQ-001)
- **New skill + agent contract (CO-2/CO-3)** — `skills/closeout/SKILL.md` (review the changes against the requirement, confirm every affected doc, update any that are stale) + `agents/closeout-agent.md` (the spawnable worker: Write-only, bounded to the currency inventory, operates from the working-tree diff so it runs OUTSIDE a pipeline run). Reuses `documentation-currency` + the `doc-updater` whole-file pattern. (REQ-002)
- **Safety + honesty** — the hook never blocks/delays compaction and fails open on any error; the engine's signals are heuristics (a clean result does not prove semantic currency); the `new-surface-undocumented` signal keys off the specific inventory-count docs so a lone CHANGELOG touch can't mask a stale grid. (REQ-003)
- **Reuse-first + currency + the new command** — the 21st command `/architect-team:closeout`; the count ripple (skills 42→43, agents 37→38, commands 20→21) + version bump to 3.18.0; Python stays stdlib-only. (REQ-004)
- **Tests** — `tests/test_closeout.py` (engine units + the staleness signals + the working-tree collector + the PreCompact hook subprocess); suite green both encodings. (REQ-005)

## Capabilities

### New Capabilities

- `closeout` — a session-end documentation-currency double-check that fires before compaction, reviews changes against the requirement, and updates stale docs itself.

### Modified Capabilities

- None removed. The skill/agent/command inventory grows by one each; the documentation-currency discipline gains a session-end counterpart (the Phase-8 gate is unchanged).
