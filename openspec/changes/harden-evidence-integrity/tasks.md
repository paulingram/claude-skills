# Tasks: harden-evidence-integrity

Groups 1–4 are parallelizable with non-overlapping file scope (see design Reuse Decisions).
Group 5 is the orchestrator/integration close-out. TDD throughout: the red run comes first —
and per this change's own check-falsifiability rule, every new test's red output is captured.

## 1. verify-check-can-fail tool (owner: hooks-tool teammate)

- [ ] 1.1 Write failing tests + fixtures for the zero-work signature registry (pytest `collected 0 items` / `no tests ran`, Playwright `no tests found` / 0-total, jest/vitest `No test files found`, tsc solution-shape predicate) — capture the red run
- [ ] 1.2 Write failing tests for red-run enforcement: `new-guard-never-shown-red`, `red-run-not-red`, missing/empty cited output as failure, clean-artifact pass
- [ ] 1.3 Implement `hooks/vao/check_integrity.py`: artifact contract `{checks: [{command, output_path, exit_code?}], new_test_files: [...], red_runs: {path: {command, output_path, observed_failure_excerpt, red_source}}}`, data-driven signature registry (substring + predicate kinds), `_detect_missing_evidence_artifact`-bar output validation, verdict JSON with the three severities
- [ ] 1.4 Wire the facade: `hooks/vao_tools.py` `_REEXPORT_MAP` + `verify-check-can-fail` argparse subcommand + dispatch, byte-consistent with the other 20
- [ ] 1.5 All group-1 tests green; run the tool's CLI against both a failing and a passing fixture artifact and capture outputs as demo artifacts

## 2. Schema, hooks, audits, fingerprint (owner: hooks-gates teammate)

- [ ] 2.1 Write failing tests: optional `check_integrity_review` (absent-valid / present-validated / fail-blocks), the unmanifested-task gate (block + all four fail-open directions + kill-switch `CT6_TASK_GATE_DISABLED`), marker `session_id` recording at engagement
- [ ] 2.2 Implement the schema optional field in `hooks/review_evidence_schema.py` (validated-when-present pattern) + the active-run unmanifested-task gate in `hooks/review-gate-task.py` + `session_id` population in `hooks/run_continuity.py` engagement path
- [ ] 2.3 Write failing tests for the three audit arms: `_audit_check_integrity` (diff-adds-tests ⇒ verdict exists+passes; fail-open no-diff/no-tests), `_audit_declared_gates` (unsatisfied blocks quoting declaration_text; absent registry fail-open; satisfied passes), `_audit_spec_currency` (stale in-flight manifest blocks; re-brief record clears; pre-upgrade fail-open)
- [ ] 2.4 Implement `hooks/spec_fingerprint.py` (SHA-256 over sorted posix-relpath+content pairs; stability + sensitivity tests) and the three audit arms in `hooks/pipeline-completion-audit.py` (worklist + `--check` parity)
- [ ] 2.5 All group-2 tests green; existing review-gate/audit test families still green (fail-open regression sweep)

## 3. Claims citation: deferral + delivery manifest (owner: claims teammate)

- [ ] 3.1 Write failing tests + fixtures (passing AND failing per severity): `uncited-completion-claim`, `uncited-deploy-claim`, `absence-claim-uncited`, `stalled-agent-claim-uncited`, `undeclared-gate-language`, extended citation tokens, optional `progress_reports[]` input
- [ ] 3.2 Implement the marker families + citation-token extension in `hooks/vao/deferral.py` (additive; existing severities and passing inputs unchanged — regression-covered)
- [ ] 3.3 Write failing tests for delivery-manifest citation errors (uncited verified-claim step blocks; cited manifests pass; existing valid manifests unchanged)
- [ ] 3.4 Implement the error-severity citation findings in `scripts/delivery/delivery_manifest.py` validate
- [ ] 3.5 All group-3 tests green; deferral + delivery-manifest existing families green

## 4. Instruction surfaces + compiled tiers (owner: instruction teammate)

- [ ] 4.1 `skills/dev-api-integration-testing/SKILL.md`: assertion-layer reorder (write-echo → API read-back chain → DB necessary-not-sufficient → audit) + rationalization row
- [ ] 4.2 `skills/playwright-user-flows/SKILL.md`: `### Shared-state hygiene` (unique-or-restore, runnable-twice, never assert a literal you wrote) + rationalization row
- [ ] 4.3 `agents/test-completeness-verifier.md`: readback_audit step + fixture-hygiene step (verdict fields additive, schema_version bump) + captured-output rule; `agents/task-reviewer.md`: capture-and-scan rule
- [ ] 4.4 `skills/team-spawning-and-review-gates/SKILL.md`: manifest `spec_fingerprint` field, SR catalog `spec-drift` entry, red-first three-sources section, `## Reading teammate state`; `skills/verified-agent-output/SKILL.md`: 21st tool table row + `check_integrity_review` citation contract + red-first cross-reference
- [ ] 4.5 `skills/common-pipeline-conventions/SKILL.md`: declared-gates discipline + spec-currency discipline (+ pipeline skills' Phase-8 declared-gates reference); `skills/delivery-manifest/SKILL.md`: citation bar + honest boundary
- [ ] 4.6 `docs/ETHOS.md`: new `## Evidence integrity (v3.47.0)` section (three rules, named anti-patterns); `scripts/setup/agent_boilerplate_blocks.py::PRINCIPLES`: one-clause principle-7 extension; run `sync_agent_boilerplate.py` + `compile_skills.py`; both `--check` modes byte-stable green
- [ ] 4.7 Structural/consistency tests for the new text surfaces green (ethos-injection, boilerplate-sync, instruction-compliance lint, doc pins)

## 5. Integration, pins, and release (orchestrator + reviewers)

- [ ] 5.1 Repo-wide count-pin sweep 20→21 (CLAUDE.md, docs/CODEBASE_MAP.md, README.md, skill bodies enumerating tools, consistency tests) — grep-verified zero stale pins
- [ ] 5.2 Full suite green: zero NEW failures vs the recorded Windows baseline (5979 passed / 5 skipped / 2 known pre-existing); PYTHONUTF8=1 parity spot-check
- [ ] 5.3 Version bump 3.46.0 → 3.47.0 (plugin.json + marketplace.json); CHANGELOG entry per docs/CHANGELOG_RUBRIC.md (top version == plugin.json; suite-total line)
- [ ] 5.4 Documentation currency: CODEBASE_MAP + INTEGRATION_MAP notes, README, CLAUDE.md counts/narratives (doc-updater + independent audit per pipeline Phase 8)
- [ ] 5.5 This change's own evidence: verify-check-can-fail run against THIS run's added tests (dogfood — red runs captured in group 1-3 TDD); declared-gates registry satisfied; final report claims cited
