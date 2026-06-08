## Why

The reader-facing documentation has drifted badly from the actual v3.7.0 state. `README.md` claims 26 skills / 27 agents / 12 commands; the repo actually ships **38 skills / 33 agents / 19 commands**. `CLAUDE.md`'s headline still says "As of **v2.19.0**" while the repo is at **v3.7.0**. The v3.3.0–v3.7.0 capabilities (cartographer-team, data-engineering-exploration, domain-research-team, test-run-monitor, api-design-from-frontend, the worktree end-of-run merge check, the auto-merge-to-main default + startup branch reconciliation) are absent from the README inventory and graphics. A stale README ships a lie; a stale CLAUDE.md misinforms every future run.

## What Changes

- **Update** `README.md` to v3.7.0: correct counts (38 skills / 33 agents / 19 commands / 3673 tests + 5 skipped), bump the ASCII banner + badges, refresh the inventory grid with the v3.3–3.7 skills/commands/agents, and redraw the Phase 8 git-behavior logic-map to show the auto-merge-to-main → push → prune flow + the `--no-auto-merge` opt-out. House aesthetic preserved (no full restyle). (REQ-001)
- **Update** `phenotypes/README.md` — correct any stale version/count references; phenotype inventory accurate. (REQ-002)
- **Update** `CLAUDE.md` — headline + `## Structure` counts to 38/33/19 at v3.7.0; add a concise v3.3–3.7 summary sentence; leave the historical version prose intact. (REQ-003)

Documentation-only. No source, test, skill-body, command-body, or agent-body changes. No version bump (ships no code; stays at 3.7.0). No CHANGELOG edit (already current).

## Capabilities

### New Capabilities

- `documentation-currency-v3.7.0`: a guarantee that `README.md`, `phenotypes/README.md`, and `CLAUDE.md` reflect the actual v3.7.0 inventory — correct skill/agent/command/test counts, current version, the v3.3–3.7 feature set, and graphics that match the real flow.

### Modified Capabilities

None.

## Impact

**Affected files:** `README.md`, `phenotypes/README.md`, `CLAUDE.md`. No code, no version-source-of-truth, no CHANGELOG.
