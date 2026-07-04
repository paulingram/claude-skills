# Tasks — consolidate-duplicated-rules

## Slice A — shared rule-constants + consumers + scope-discipline single-source

- [ ] A1. Create `hooks/shared_rule_constants.py` exporting `FORBIDDEN_GIT_OPERATIONS`, `ACTION_KIND_VALUES`, `TEST_FAILURE_ORIGINS`, `PARITY_VERBS` (stdlib-only, no side effects). (REQ-001)
- [ ] A2. Modify `hooks/vao_tools.py` to source its forbidden-git operation set from `shared_rule_constants.FORBIDDEN_GIT_OPERATIONS` (keep the regex/pattern derivation; remove the independently-maintained list). Behavior identical. (REQ-002)
- [ ] A3. Modify `hooks/pipeline-completion-audit.py` to import `TEST_FAILURE_ORIGINS` from the shared module. (REQ-002)
- [ ] A4. Add a source-of-truth header comment to `agents/prompt-refiner.md`, `agents/bug-classifier.md`, `agents/system-architect.md`, `agents/oracle-deriver.md` above the parity-verb restatement (text otherwise unchanged). (REQ-003)
- [ ] A5. Update `tests/test_cross_consistency.py` to assert the hook/skill test-failure-origin agreement against `shared_rule_constants.TEST_FAILURE_ORIGINS`. (REQ-002)
- [ ] A6. Add `tests/test_shared_rule_constants.py` — module surface + values + the parity-verb consistency check across the 4 agent files. (REQ-001, REQ-003)

## Slice B — canonical agent-boilerplate + sync script + drift guard

- [ ] B1. Define the canonical text of the three blocks (`## Forbidden git operations`, `## Checkpoint discipline`, `## Operating context (v1.0.0)`) in one place, with the allowlisted role-specific variants for `adversarial-reviewer`, `oracle-deriver`, `interaction-observer`. (REQ-004)
- [ ] B2. Add `scripts/setup/sync_agent_boilerplate.py` — idempotent regenerator; running against a synced tree makes no changes. (REQ-004)
- [ ] B3. Add `tests/test_agent_boilerplate_sync.py` — byte-identity drift guard across the standard agents, variants allowlisted. (REQ-005)

## Phase gates

- [ ] G1. `openspec validate --all --strict` passes. (REQ-006)
- [ ] G2. Full pytest suite green from repo root — ≥ 2394 passed + 1 skipped + new tests, zero failures. (REQ-006)
- [ ] G3. Independent task-review per slice (no behavior change, reuse-first honored, no stubs). (REQ-006)
- [ ] G4. Independent master-review audit `overall: pass`. (REQ-006)

## Release

- [ ] R1. Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to `3.1.0`. (REQ-007)
- [ ] R2. CHANGELOG `## [3.1.0]` entry; README + CLAUDE.md + CODEBASE_MAP currency. (REQ-007)
- [ ] R3. `openspec archive consolidate-duplicated-rules`. (REQ-007)
- [ ] R4. Commit to `architect-team/consolidate-duplicated-rules`; push; recommend PR.
