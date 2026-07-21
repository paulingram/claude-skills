# installer-guidance-blocks Specification

## Purpose
TBD - created by archiving change quality-upgrades-v3-42. Update Purpose after archive.
## Requirements
### Requirement: Capability-gated self-removing guidance blocks

The MemPalace, Librarian, and gateway installers SHALL manage a marker-fenced guidance block in a target project's CLAUDE.md named via the opt-in `--claude-md <path>` flag: added (idempotently) on verified install, removed exactly (fences included, nothing outside them) on failed capability check or uninstall. The flag is the sanctioned mechanism — these are per-user tools with no single implied target project, and the house norm is that installers never silently mutate a user's environment (boot descriptors are printed, never auto-loaded; guidance follows the same rule). Concurrent multi-installer writes to one CLAUDE.md are outside the supported envelope (each write is atomic; cross-installer serialization is the caller's responsibility).

#### Scenario: install adds the block once

- **WHEN** an installer completes a verified install with `--claude-md` supplied and runs again afterward
- **THEN** the guidance block is present exactly once (idempotent re-run)

#### Scenario: no flag means no CLAUDE.md side effect

- **WHEN** any installer path runs without `--claude-md`
- **THEN** no CLAUDE.md is created or modified

#### Scenario: uninstall or failed check removes exactly the block

- **WHEN** the capability check fails or the uninstall path runs
- **THEN** exactly the fenced block is removed and all other CLAUDE.md content is byte-preserved

#### Scenario: degrade path is honest

- **WHEN** the capability is provisioned-but-disabled
- **THEN** the block either states the disabled state with the enable remediation, or is absent — never stale enabled-state guidance

