# documentation-currency-refresh — delta (docs-currency-v3-42-1)

## ADDED Requirements

### Requirement: Widened-surface currency sweep with dispositions

A documentation-currency sweep SHALL cover every tracked markdown file outside the frozen zones (archived changes, historical records, the archive index), fixing every stale current-state assertion and every dead pointer while preserving historical narrative verbatim, and SHALL record an explicit per-doc disposition (current / updated / frozen-historical / out-of-scope) in a refreshed disposition ledger.

#### Scenario: stale current-state fixed, history preserved

- **WHEN** a walked doc asserts a prior release's fact as current
- **THEN** the assertion is brought current with the shipped release's verified facts
- **AND** historical narrative (append-only changelog entries, timeline rows, release digests, frozen docs) is byte-preserved

#### Scenario: dead pointers resolved

- **WHEN** a walked doc cites a repo path that no longer resolves
- **THEN** the citation is fixed to the current path or removed with the surrounding text corrected
- **AND** a post-sweep verification confirms every cited repo path in walked docs resolves

#### Scenario: every walked doc dispositioned

- **WHEN** the sweep completes
- **THEN** every walked doc carries an explicit disposition in the refreshed ledger
- **AND** an independent audit over the widened surface passes before the release commits
