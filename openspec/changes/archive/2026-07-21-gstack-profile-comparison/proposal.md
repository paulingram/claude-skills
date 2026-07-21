# gstack-profile-comparison — profile the gstack skills package + cited comparison vs the CT6 skills engine (analysis-only)

## Why

The owner downloaded gstack (`~/Downloads/gstack-main.zip` — 1337 files, ~56 MB unpacked), a large agentic-skills stack with a per-skill `SKILL.md` + `SKILL.md.tmpl` template system, a `bin/` tool tier (`gstack-brain-*`, `gstack-analytics`, `gstack-artifacts-*`), an evals CI tier (`evals.yml`, `evals-periodic.yml`, `version-gate.yml`, `skill-docs.yml`), and heavyweight architecture/ethos docs. CT6 is itself a skills engine (48 skills / 39 agents / 23 commands / hook-enforced discipline stack / 5689-test suite). A structured, cited comparison surfaces (a) what gstack does better, (b) where CT6 is better (moats to preserve), and (c) which gstack ideas CT6 should abstract and adopt — feeding a prioritized adoption backlog for future runs. The refined brief (`.architect-team/refined-prompts/gstack-profile-comparison-20260721T162549Z.md`, grade A/93) locked: report + matrix deliverable; ideas + backlog stop-point (NO implementation this run); full 4-tier STATIC profile (never execute gstack code); gstack unpacked outside the repo.

## What Changes

- Profile gstack across four tiers (static read only): (a) skill format (`SKILL.md` + `.tmpl` system), (b) `bin/` tool tier, (c) evals CI tier, (d) architecture/ethos docs — per-tier findings artifacts with file citations under the run's `.architect-team/` state.
- Produce the comparison report — surface-by-surface matrix + narrative answers to the three questions, every material claim carrying file citations from both sides — persisted under `.architect-team/gstack-comparison/` in the main checkout (durable, gitignored) and presented in full in-chat.
- Produce the adoption backlog — solution-requirement-style items prioritized by value-vs-effort, each actionable as a future `/architect-team` input — alongside the report, its path recorded in the report.
- This OpenSpec change itself is the run's only tracked-file footprint (analysis record; precedent: `archive/2026-07-16-docs-currency-v3-39-1`). NO source, test, doc, or version-machinery changes; NO gstack content committed.

## Capabilities

### New Capabilities

- `gstack-comparative-analysis` — the deliverable contract for this analysis run (profile completeness, two-sided citation discipline, backlog actionability, repo hygiene).
