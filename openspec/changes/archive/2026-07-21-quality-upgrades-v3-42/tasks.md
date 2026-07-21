# tasks — quality-upgrades-v3-42

## A. Instruction-surface team (REQ-001, REQ-005, REQ-007)

- [ ] A.1 `docs/ETHOS.md` — 5-7 load-bearing principles, each with statement + anti-pattern; add to documentation-currency inventory awareness.
- [ ] A.2 `scripts/setup/compile_skills.py` — marker-block compile (canonical sources in-script; BEGIN/END fences; byte-stable; `--check`); wire a suite pin test.
- [ ] A.3 Principles block into all 39 `agents/*.md` (extend `sync_agent_boilerplate.py`) + the 5 pipeline-driving skills (via compile) — drift-pinned.
- [ ] A.4 `references/` extraction for the largest skills — heavy rarely-fired blocks → `skills/<name>/references/<id>.md` + STOP-Read pointers + index table; record before/after bytes.
- [ ] A.5 Tests: `test_ethos_injection.py`, `test_compile_skills.py`, `test_skill_references.py`; instruction-compliance lint green; full-suite impact clean.
- [ ] A.6 Review evidence (schema v7) + independent task-reviewer pass.

## B. Memory-hygiene team (REQ-002, REQ-010, REQ-011)

- [ ] B.1 `scripts/memory/recall_hygiene.py` — envelope(), allowlist filter, TTL digest cache (byte caps, injection budget, invalidate-on-mine, stale-fallback fail-open, degraded marker).
- [ ] B.2 Wire envelope into the `mempalace-integration` skill contract (render-path directives) + `hooks/sessionstart-run-continuity.py` injected-recall path.
- [ ] B.3 Tests: `test_recall_hygiene.py` (engine incl. cache/TTL/budget/invalidation/degraded), `test_sessionstart_recall_envelope.py` (hook path pin).
- [ ] B.4 Review evidence (schema v7) + independent task-reviewer pass.

## C. Doc-tooling team (REQ-003, REQ-004, REQ-006)

- [ ] C.1 `scripts/docs_tooling/capability_index.py` — deterministic generator; emit `docs/CAPABILITY_INDEX.md`; freshness test (regenerate-and-diff); CLAUDE.md pointer line.
- [ ] C.2 `docs/CODEBASE_MAP.md` `## What's intentionally NOT here` — ≥4 entries (single-harness, no usage telemetry, stdlib-only core, no embedded browser runtime) each with rationale + revisit-trigger.
- [ ] C.3 `docs/CHANGELOG_RUBRIC.md` + `scripts/docs_tooling/changelog_check.py` (top-entry version == plugin.json; suite-total line present) + suite wiring.
- [ ] C.4 Tests: `test_capability_index.py`, `test_changelog_rubric.py`.
- [ ] C.5 Review evidence (schema v7) + independent task-reviewer pass.

## D. Installer team (REQ-008)

- [ ] D.1 `scripts/setup/guidance_blocks.py` — `upsert_block` / `remove_block` with `<!-- ct6:<capability>:begin/end -->` fences; byte-preserving outside fences; idempotent.
- [ ] D.2 Wire into `install_mempalace.py`, `install_librarian.py`, `install_gateway.py` — add on verified install; remove on failed check/uninstall; honest disabled-state text.
- [ ] D.3 Tests: `test_installer_guidance_blocks.py` (add/idempotent/remove/degrade per installer).
- [ ] D.4 Review evidence (schema v7) + independent task-reviewer pass.

## E. Evals team (REQ-012, REQ-009)

- [ ] E.1 `scripts/evals/runner.py` (claude -p subprocess, stream-json parse, max-turns bound) + `judge.py` (bounded judge call; deterministic thresholds in fixtures) + `collector.py` (verdict/turns/tools/cost JSON; prior-run delta) + `budget.py` (ratio gate, noise floors, warn-first).
- [ ] E.2 `tests/evals/` — routing evals (prose → expected Skill invocation) + one planted-defect outcome eval (fixture repo + ground-truth JSON + thresholds); env-flag gating; default-suite exclusion wiring (conftest/pytest.ini).
- [ ] E.3 `tests/test_evals_offline.py` — deterministic engine tests IN the default suite (parser, collector math, budget gate, fixture integrity, gating logic).
- [ ] E.4 Review evidence (schema v7) + independent task-reviewer pass.

## F. Integration + release (orchestrator)

- [ ] F.1 Phase 4 reconciliation: A×C (lint over compiled files), E×suite (collection boundaries), cross-team suite run.
- [ ] F.2 Phase 5: full suite green (cp1252 + PYTHONUTF8=1); instruction-compliance lint green; LIVE eval smoke (routing + outcome) executed once — verdict + cost recorded.
- [ ] F.3 Phase 7: coverage walk + independent master-review audit `overall: pass`; archive change.
- [ ] F.4 Phase 8: version → 3.42.0; doc-updater + independent doc-currency audit pass; completion audit exit 0; commit/push/auto-merge; mark complete.
