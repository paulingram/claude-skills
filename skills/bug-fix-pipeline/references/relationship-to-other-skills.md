# Relationship to other skills

- `architect-team-pipeline` (sibling) — same orchestration discipline, different shape. Bug-fix pipeline is reached via `/architect-team:bug-fix` (explicit) or via the main pipeline's Phase −2 triage when the classifier returns `bug` (or in parallel for `mixed`).
- `intake-and-mapping` (Phase B−1) — reused verbatim. Same maps, same freshness rules.
- `playwright-user-flows` (Phase B1 frontend, B6 QA replay) — the bug-replicator drives Playwright per this skill; the QA replayer re-runs it the same way.
- `dev-api-integration-testing` (Phase B1 backend, B2 backend diagnostic, B6 QA replay) — same.
- `root-cause-test-failures` — applies when B1 returns `could-not-reproduce` or when B6 returns an unclear `bug-still-present` (the diagnostic loop runs through the orchestrator's normal channels).
- `coverage-mapping` + `reuse-first-design` (Phase B3) — same authoring disciplines as a feature proposal.
- `documentation-currency` (Phase B8) — the doc-currency gate runs before the auto-commit, same as the main pipeline. v0.9.23 promoted the update step to the dedicated `doc-updater` agent; the audit (system-architect Documentation Currency Audit mode) and the commit-blocking enforcement are unchanged.
