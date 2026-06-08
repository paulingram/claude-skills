# Tasks

## 1. README.md (REQ-001)

- [x] 1.1 Bump version to 3.7.0 (banner ASCII token, badges, prose).
- [x] 1.2 Correct counts: 38 skills / 33 agents / 19 commands / 3673 tests (+5 skipped).
- [x] 1.3 Add v3.3–3.7 capabilities to inventory/prose (cartographer-team, data-engineering-exploration, domain-research-team, test-run-monitor, api-design-from-frontend, monitor-tests; worktree merge-check + hidden container; auto-merge-to-main + startup reconcile).
- [x] 1.4 Redraw the Phase 8 git-behavior ASCII logic-map: auto-merge-to-main → push → prune branch+worktree + `--no-auto-merge` opt-out. Preserve house style; GitHub-safe.

## 2. phenotypes/README.md (REQ-002)

- [x] 2.1 Correct any stale version/count references; phenotype inventory accurate.

## 3. CLAUDE.md (REQ-003)

- [x] 3.1 Headline + `## Structure` counts → 38/33/19 at v3.7.0; add v3.3–3.7 summary sentence; preserve historical prose.

## 4. Verify (REQ-001..003)

- [x] 4.1 Full `python -m pytest` green (test_readme_styling, test_skills, test_agents, test_commands, test_plugin_metadata pass with corrected figures); Windows cp1252 + PYTHONUTF8=1.
