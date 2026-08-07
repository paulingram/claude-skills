# compact-readme-status-timeline

## ADDED Requirements

### Requirement: The README carries no accumulated release timeline

`README.md` SHALL NOT embed a one-line-per-release timeline spanning the whole release history. The README's `STATUS` section SHALL name only the CURRENT release and SHALL carry a house-style pointer to `docs/RELEASE_HISTORY.md` for the full timeline. The README SHALL continue to carry exactly one `NEW IN` release spotlight (the current release) and the existing `RELEASE HISTORY` pointer block, and SHALL preserve the house aesthetic (block-letter banner, gradient dividers, the boxed inventory grid, the logic maps with the gate glyph, and the theme marker).

#### Scenario: The full release timeline is not in the README

- **WHEN** the README is read
- **THEN** it does not contain a `v0.1.0`-through-current one-line release timeline, and its `STATUS` section names only the current release plus a pointer to `docs/RELEASE_HISTORY.md`

#### Scenario: The README keeps exactly one spotlight and the pointer block

- **WHEN** the README is scanned for `NEW IN vX.Y.Z` spotlight dividers
- **THEN** exactly one is present, it names the current release (the `plugin.json` version), and a structure-anchored `RELEASE HISTORY` pointer block to `docs/RELEASE_HISTORY.md` sits above it

### Requirement: The full release timeline lives in the docs history file

`docs/RELEASE_HISTORY.md` SHALL carry the one-line release timeline (relocated from the README) as a compact index, in addition to the complete per-release narrative. It SHALL remain the complete history — carrying the current release, reaching the earliest retained release, and naming at least the recorded move-set of release identities — so no release content is lost by the README compaction.

#### Scenario: The relocated timeline is preserved in docs

- **WHEN** `docs/RELEASE_HISTORY.md` is read after the compaction
- **THEN** it contains the one-line release timeline index AND the complete per-release narrative, and every release the README previously listed in its timeline is still named there
