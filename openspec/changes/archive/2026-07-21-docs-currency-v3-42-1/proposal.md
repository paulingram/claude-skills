# docs-currency-v3-42-1 — widened documentation-currency sweep (docs-only PATCH v3.42.1)

## Why

v3.42.0 shipped with its five-doc inventory audited current, but the repo's WIDER documentation surface — 207 walked tracked markdown files outside the frozen zones — was last swept as a whole at v3.31.1. A deterministic scan finds 11 candidate files carrying potential stale current-state patterns (old versions/counts asserted as current), concentrated in the living openspec specs (6 files with authoring-era claims) plus adjudication-needed hits in README/CLAUDE/maps/`commands/architect-team-setup.md`; dead pointers (paths that no longer resolve) have no standing check outside the instruction-compliance lint's in-scope set. The owner directive: bring everything current, remove expired details, preserve all historical narrative, frozen zones stay frozen.

## What Changes

- Sweep all 207 walked docs in three parallel non-overlapping groups: (1) core + docs/ current set + commands hit; (2) the 68 living openspec specs + any openspec project doc; (3) phenotypes/, services/, skills references, and the instruction-surface bodies (grep-driven).
- Fix every stale CURRENT-STATE assertion to the v3.42.0→v3.42.1 reality; remove or fix every dead pointer/expired reference; per-hit adjudication distinguishes current-state (fix) from historical narrative (preserve, disposition it).
- Record an explicit disposition (current / updated / frozen-historical / out-of-scope) for every walked doc; refresh the doc-disposition ledger.
- Frozen zones (archived openspec changes, docs/superpowers/, docs/archive/) untouched except broken cross-references.
- Release as docs-only PATCH v3.42.1: version manifests, a rubric-conforming CHANGELOG entry, suite + lint + doc checks green, independent doc-currency audit over the WIDENED surface.

## Capabilities

### Modified Capabilities

- `documentation-currency-refresh` — widened from the five-doc inventory to the full walked tracked-markdown surface, with dead-pointer verification and per-doc dispositions.
