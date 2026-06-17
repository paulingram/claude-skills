# closeout Specification

## Purpose
TBD - created by archiving change closeout-capability. Update Purpose after archive.
## Requirements
### Requirement: REQ-001 — Fire-before-compact trigger + deterministic staleness engine (CO-1)

The plugin SHALL wire a `PreCompact` hook (`hooks/precompact-closeout.py`) in `hooks/hooks.json` that runs a stdlib-only staleness engine (`hooks/closeout_check.py`) against the git working tree before context is compacted. The engine SHALL classify a session's changed files (currency-docs / code / version-source / new-surfaces) and emit advisory staleness signals; the hook SHALL surface a closeout reminder when the docs appear stale.

#### Scenario: a code change with no doc update is flagged before compaction

- **WHEN** the working tree has a source change and no documentation-currency doc changed, and the PreCompact hook fires
- **THEN** the hook emits a closeout reminder (on `systemMessage` and `hookSpecificOutput.additionalContext`) naming the staleness signals

#### Scenario: a new surface with only a CHANGELOG touch is still flagged

- **WHEN** a new skill/agent/command is added and only `CHANGELOG.md` (not README / CLAUDE.md / CODEBASE_MAP) was updated
- **THEN** the engine still emits `new-surface-undocumented` (it keys off the specific inventory-count docs, not any currency doc)

### Requirement: REQ-002 — Review-and-update contract (CO-2/CO-3)

The plugin SHALL provide a `closeout` skill (`skills/closeout/SKILL.md`) and a `closeout-agent` (`agents/closeout-agent.md`) that review the session's changes against the requirement (not only structural staleness), confirm every affected doc in the documentation-currency inventory, and — when a doc is lax — PERFORM the update itself rather than merely flagging it, reusing the `documentation-currency` discipline + the `doc-updater` whole-file-rewrite pattern. The agent SHALL operate from the working-tree diff (no coverage-map / run-ledger required), and its Write scope SHALL be bounded to the currency inventory.

#### Scenario: the contract documents review + self-update + the boundary

- **WHEN** the skill + agent bodies are read
- **THEN** the skill names CO-1…CO-3, the engine, and the documentation-currency reuse; the agent is Write-only (no Edit), bounded to the inventory, and states it works outside a pipeline run

### Requirement: REQ-003 — Non-blocking, fail-open safety + honest heuristics

The PreCompact hook SHALL NEVER block or delay compaction (it always exits 0) and SHALL fail open on any error (unreadable payload, git failure, import failure) by emitting nothing. The engine's signals SHALL be documented as advisory heuristics — a clean result does not prove semantic currency, and a signal is never silenced by editing a doc that did not need changing.

#### Scenario: bad input never wedges the session

- **WHEN** the PreCompact hook receives malformed or empty stdin, or git is unavailable
- **THEN** it exits 0 and writes nothing

### Requirement: REQ-004 — Reuse-first, the new command, and currency

The capability SHALL be built reuse-first (no duplication of the `documentation-currency` rules; the engine's inventory mirrors that skill, pinned by a test against drift), Python SHALL stay stdlib-only, the manual trigger SHALL be the 21st command `/architect-team:closeout`, and the release SHALL bump the version to 3.18.0 and bring the inventory counts current (43 skills / 38 agents / 21 commands).

#### Scenario: counts + version current

- **WHEN** the version files + README + CLAUDE.md + CODEBASE_MAP are read
- **THEN** the version is 3.18.0 and the inventories say 43 skills, 38 agents, 21 commands with closeout entries

### Requirement: REQ-005 — Tests green both encodings

A new test file SHALL cover the engine units, the staleness signals (including the new-surface-with-only-CHANGELOG regression), the working-tree collector against a real temp git repo (rename / staged-add / spaced-path), and the PreCompact hook as a subprocess (reminder-on-stale, silent-on-current, fail-open); the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_closeout.py` present
- **THEN** there are zero failures

