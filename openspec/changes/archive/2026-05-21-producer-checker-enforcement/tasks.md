# Tasks — producer-checker-enforcement

## REQ-1 — Independent Phase 3 review

- [ ] **T-1** — `agents/task-reviewer.md`: NEW agent. opus; read-only on source (`Read, Glob, Grep, LS, Bash, Write, TodoWrite` — NO `Edit`). Independently reviews one completed teammate task's diff against the coverage-map acceptance criteria → `spec_review`; runs linters/type-checkers + inspects → `quality_review`; greps the diff for stubs/TODO/`NotImplementedError`/placeholder → `real_not_stubbed`; checks new files vs `design.md` Reuse Decisions → `reuse_compliance`. Writes the `independent_review` block into the task's evidence file. Never edits source; a `fail` verdict sends the task back.
- [ ] **T-2** — `hooks/review_evidence_schema.py`: schema **v5**. Add a required `independent_review` object — `{ reviewer, verdict, spec_review, quality_review, real_not_stubbed, reuse_compliance, reviewed_at }`. `validate_evidence()` must reject evidence when `independent_review` is absent, when `independent_review.reviewer` is empty or equals the top-level `teammate`, or when `independent_review.verdict != "pass"`. The teammate's own block is kept as `self_review` (informational, not gating).
- [ ] **T-3** — `skills/team-spawning-and-review-gates/SKILL.md`: document evidence schema v5 + the `independent_review` block; add the `task-reviewer` dispatch to the review-gate flow; **replace** the line "The hook does shape validation; honesty is enforced by the teammate's own discipline" with the independent-reviewer mechanism. Add a hard rule + an anti-pattern row.
- [ ] **T-4** — `skills/architect-team-pipeline/SKILL.md`: Phase 3 — after a teammate writes its `self_review` and signals task-complete, the orchestrator spawns a `task-reviewer` against that task; the reviewer's verdict populates the gate. The hook now enforces `reviewer != teammate`.

## REQ-2 — Independent Phase 7 master-review audit

- [ ] **T-5** — `agents/system-architect.md`: NEW "Master Review Audit" mode — independently re-verify every coverage-map entry (commit + tests + demo) and every SR (`resolved`), confirm `openspec validate`, write a verdict JSON to `.architect-team/master-review/audit-<ts>.json`.
- [ ] **T-6** — `skills/architect-team-pipeline/SKILL.md`: Phase 7 — after the orchestrator's walk, dispatch the independent system-architect audit; Phase 8 — the auto-commit is gated on the audit verdict `overall: pass`.
- [ ] **T-7** — `hooks/pipeline-completion-audit.py`: new `_audit_master_review` — if a run produced coverage-map progress, a passing master-review audit verdict must exist; block the `Stop` otherwise. Wire into `audit()`.

## Tests, docs, release

- [ ] **T-8** — Tests: `test_agents.py` `EXPECTED_AGENTS` += `task-reviewer`; v5-schema cases in `test_review_gate_task.py` + `test_teammate_idle_check.py`; NEW `test_independent_review.py` (the producer≠checker enforcement); `test_pipeline_completion_audit.py` master-review cases; `test_cross_consistency.py` updates. Full suite green.
- [ ] **T-9** — Docs + release: `README.md` (NEW IN, inventory AGENTS count, loops, timeline, badge, banner), `CHANGELOG.md` v0.9.13 entry, `.claude-plugin/plugin.json` + `marketplace.json` → `0.9.13`, `docs/CODEBASE_MAP.md` agent count + module guide.
