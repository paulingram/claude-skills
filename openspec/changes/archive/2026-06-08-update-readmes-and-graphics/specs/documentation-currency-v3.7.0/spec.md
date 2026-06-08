## ADDED Requirements

### Requirement: README.md reflects the v3.7.0 inventory

`README.md` SHALL show version `3.7.0` (banner, badges, prose), the correct counts (38 skills, 33 agents, 19 commands, and the current test total), the v3.3.0–v3.7.0 capabilities in its inventory/prose, and an ASCII git-behavior logic-map reflecting the auto-merge-to-main + prune flow with the `--no-auto-merge` opt-out. The house bitmap aesthetic SHALL be preserved and the document SHALL render correctly on GitHub.

#### Scenario: counts and version are correct

- **WHEN** `README.md` is read
- **THEN** it shows `3.7.0` as the current version with no `3.5.0`/`3.6.0` shown as current
- **AND** its skill/agent/command counts match a programmatic count of `skills/*/SKILL.md` (38), `agents/*.md` (33), `commands/*.md` (19)
- **AND** the test total matches the measured `3673 passed / 5 skipped`

#### Scenario: new features and graphics present

- **WHEN** `README.md` is read
- **THEN** the v3.6.0 worktree end-of-run merge check + hidden container and the v3.7.0 auto-merge-to-main + startup reconcile are described
- **AND** the git-behavior ASCII logic-map shows the auto-merge → push → prune flow and the `--no-auto-merge` opt-out

### Requirement: phenotypes/README.md carries no stale references

`phenotypes/README.md` SHALL carry no stale version or count references inconsistent with the v3.7.0 state.

#### Scenario: phenotypes README is current

- **WHEN** `phenotypes/README.md` is read
- **THEN** any version/count reference it contains is consistent with v3.7.0 and the actual phenotype inventory

### Requirement: CLAUDE.md headline and structure counts are current

`CLAUDE.md` SHALL show v3.7.0 with 38 skills / 33 agents / 19 commands in its headline and `## Structure` counts, and SHALL carry a concise v3.3–3.7 summary; the historical version prose SHALL remain intact.

#### Scenario: CLAUDE.md headline is current

- **WHEN** `CLAUDE.md` is read
- **THEN** the headline names v3.7.0 (not v2.19.0) with the correct 38/33/19 counts
- **AND** a v3.3–3.7 summary sentence is present
- **AND** the prior version-history prose is preserved
