# Proposal: mini-architect-team-pipeline (v0.10.0)

## Why

The full `/architect-team` pipeline is correct-by-construction at 8 phases, 26 agents, and ×3 reviewer convergence at multiple points. For small-to-medium feature changes on familiar codebases, this is overkill — the wall clock and token cost dominate the actual work. A faster sibling pipeline with a single architect, a single QA agent, and auto-merge to `main` on green QA lets the user do many rapid small mostly-accurate changes and call for a batched heavyweight review later.

## What changes

1. New skill `mini-architect-team-pipeline` (M0–M8 phases, single-architect + dev cross-review + single mini-qa).
2. New agent `mini-qa` (unit + integration + ≤3 Playwright flows against live dev URL).
3. New command `/architect-team:mini` (entry point).
4. New command `/architect-team:mini-review-sweep` (batched heavyweight review by `Mini-Run:` trailer).
5. New required `## QA Guidance` contract in every mini proposal.md (and matching `qa_guidance` block in coverage-map.json).
6. Auto-merge to `main` on green QA (with `--no-merge` opt-out, conflict + pre-push-hook safety rails).
7. `Mini-Run: <slug>` commit trailer on every commit produced by a mini run.
8. Cycle cap = 3 on M8 architect re-eval; on cycle 4 escalate to `/architect-team` via the existing folder-as-REQ_DIR pattern.

## QA Guidance

### Acceptance Criteria
- [AC-1] `/architect-team:mini` is invocable and accepts both input forms (folder or prose).
- [AC-2] A well-formed mini proposal.md with `## QA Guidance` passes the contract validator; a malformed one fails with specific error messages.
- [AC-3] The `Mini-Run: <slug>` trailer extractor returns the slug for tagged commits and `None` for untagged ones.
- [AC-4] The full test suite (`python -m pytest -v`) passes after the change, with the new ~50 tests added.

### Unit Test Targets
- `tests/helpers/qa_guidance.py:validate_markdown`: rejects every malformed permutation enumerated in `test_qa_guidance_contract.py`.
- `tests/helpers/qa_guidance.py:validate_json`: rejects the same malformed permutations in JSON form.
- `tests/helpers/mini_run_trailer.py:extract`: returns the slug for tagged commits, `None` for untagged, ignores prose mentions.
- `tests/helpers/mini_run_trailer.py:group_by_slug`: groups multi-commit slugs correctly.

### Integration Test Targets
- N/A — this change is plugin metadata + tests; there is no live dev API to integration-test against. The plugin's pytest suite IS the integration test.

### Playwright Flows
- N/A — this change ships no UI surface in any target project; the mini pipeline EXECUTES Playwright flows on behalf of target projects but does not bundle UI of its own.

### Out of Scope
- The full sweep orchestrator (parallel slug processing, finding de-dup, batched email-testing capture) — deferred to v0.10.1.
- Cross-language polyglot test-runner discovery — uses the existing single-language-friendly heuristic from the `integration` agent.

## Impact

- New: 1 skill, 1 agent, 2 commands, 2 test helpers, 7 test files, 5 OpenSpec artifacts (self-referential).
- Modified: 3 test-set definitions (test_skills.py / test_agents.py / test_commands.py), 1 skill (coverage-mapping), 2 doc maps (CODEBASE_MAP.md / INTEGRATION_MAP.md), 3 root docs (CLAUDE.md / README.md / CHANGELOG.md), 2 plugin metadata files (plugin.json / marketplace.json). 0–2 hooks (only if Task 14 / Task 15's tests reveal a gap).
- Version: v0.9.35 → v0.10.0.
- Test count: ~1300 → ~1350 PASS.
