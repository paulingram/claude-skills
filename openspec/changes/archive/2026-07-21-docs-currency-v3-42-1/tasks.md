# tasks — docs-currency-v3-42-1

## 1. Sweep (3 parallel teams)

- [x] 1.1 S1 core-docs: adjudicate + fix scan hits in README/CLAUDE/CHANGELOG-top/docs-current-set/architect-team-setup.md; dead-pointer verification; per-doc dispositions.
- [x] 1.2 S2 living-specs: adjudicate + fix authoring-era current-state claims + dead pointers across all 68 living specs (+ openspec/project.md, openspec/AGENTS.md if present); openspec validate strict green after edits; per-doc dispositions.
- [x] 1.3 S3 wider-surface: phenotypes/, services/, skills references, instruction-surface bodies (grep-driven), tests/**/*.md, remaining walked docs; dead-pointer verification; per-doc dispositions.

## 2. Merge + verify (orchestrator)

- [x] 2.1 Merge disposition reports → refreshed ledger covering all walked docs.
- [x] 2.2 Verification battery: full suite (both encodings), instruction-compliance lint, changelog_check, capability_index --check, openspec validate strict.

## 3. Audit + release

- [x] 3.1 Independent widened-surface doc-currency audit → overall pass.
- [ ] 3.2 Version → 3.42.1; CHANGELOG entry (rubric-conforming); archive change; completion audit; commit/push/auto-merge; mark complete.
