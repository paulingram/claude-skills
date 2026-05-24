## 1. REQ-001: ux-test-builder skill

- [ ] 1.1 Create `skills/ux-test-builder/SKILL.md` with valid frontmatter (`name: ux-test-builder`, quoted `description`).
- [ ] 1.2 Author the ten phase sections — `## Phase U0` (Intake), `## Phase U1` (Site mapping), `## Phase U2` (Literal flow), `## Phase U3` (Flow expansion), `## Phase U4` (Distillation), `## Phase U5` (Playwright authoring), `## Phase U6` (Parallel execution), `## Phase U7` (Consensus on disagreements), `## Phase U8` (Bug routing), `## Phase U9` (Final report).
- [ ] 1.3 Author the `## Five non-negotiable disciplines` section.
- [ ] 1.4 Author the `## Inputs`, `## Default mode of operation` sections.
- [ ] 1.5 Author the `## Operating rules (non-negotiable)` section + the `## Relationship to other skills` section.

## 2. REQ-002: `/architect-team:ux-test` command

- [ ] 2.1 Create `commands/ux-test.md` with valid frontmatter (`description`, `argument-hint`).
- [ ] 2.2 Author argument-parsing block mirroring `/architect-team` (folder OR plain-language prose; v0.9.17 anti-patterns forbidden).
- [ ] 2.3 Author the new flags: `--site <URL>`, `--dev`, `--credentials <env-var>`, `--persona <description>`, `--objectives <text>`.
- [ ] 2.4 Author the invocation block (Skill tool with `architect-team:ux-test-builder`).
- [ ] 2.5 Author the auto-commit + auto-compact-prompt blocks mirroring `/architect-team:bug-fix`.

## 3. REQ-003: U0 intake schema

- [ ] 3.1 In the skill body's Phase U0 section, document the intake schema (every required field).
- [ ] 3.2 State the rule: raw credential secrets are NEVER persisted; only env-var NAMES are recorded.
- [ ] 3.3 Document the U0 escalation when persona/objectives are too vague (domain gate).

## 4. REQ-004: U1 site mapping (reuse intake-and-mapping)

- [ ] 4.1 Document Phase U1 reuses `intake-and-mapping` verbatim.
- [ ] 4.2 Document Phase −1D bulk-verify gate still fires when low-confidence intuition items surface.

## 5. REQ-005: U2 literal flow

- [ ] 5.1 Document Phase U2's authoring of one literal Playwright flow.
- [ ] 5.2 State the literal flow becomes flow #1 in the eventual distilled set.
- [ ] 5.3 Reference `playwright-user-flows` for the authoring discipline.

## 6. REQ-006: U3 flow expansion via 3 explorer agents

- [ ] 6.1 Document Phase U3's 3-explorer parallel dispatch.
- [ ] 6.2 State each explorer proposes 10-15 ADDITIONAL flows (NOT rephrasing the literal).
- [ ] 6.3 State the explorers do NOT consult each other during U3.
- [ ] 6.4 Document the proposal-file path pattern.

## 7. REQ-007: U4 distillation

- [ ] 7.1 Document Phase U4's orchestrator-serialized distillation step.
- [ ] 7.2 State the dedup is semantic (not string-match).
- [ ] 7.3 Document the `source_explorers` attribution field.

## 8. REQ-008: U5 Playwright authoring per distilled flow

- [ ] 8.1 Document Phase U5's one-spec-per-flow authoring.
- [ ] 8.2 Reference `playwright-user-flows` + `root-cause-test-failures`.

## 9. REQ-009: U6 parallel execution via 3 executor agents

- [ ] 9.1 Document Phase U6's 3-executor parallel dispatch.
- [ ] 9.2 State each executor runs EVERY distilled flow (the redundancy is the consensus mechanism).
- [ ] 9.3 Document the per-flow result schema (verdict + trace + screenshots + expectation deltas + duration + notes).
- [ ] 9.4 Document the four verdict values.

## 10. REQ-010: U7 consensus on disagreements

- [ ] 10.1 Document Phase U7's verdict pooling.
- [ ] 10.2 Document the re-examination loop (each executor re-runs the disputed flow with OTHER executors' verdicts as context).
- [ ] 10.3 State the 3-cycle bounded convergence.
- [ ] 10.4 State the post-bound escalation is a domain gate (regardless of `--proposal-first`).

## 11. REQ-011: U8 bug routing to bug-fix-pipeline

- [ ] 11.1 Document Phase U8's bug-artifact persistence.
- [ ] 11.2 Document the SR creation with `origin.kind: "ux-flow-failure"`.
- [ ] 11.3 State bugs auto-route through `bug-fix-pipeline`.
- [ ] 11.4 State the UX test builder does NOT block on bug fixes; bugs are queued.

## 12. REQ-012: U9 final report

- [ ] 12.1 Document Phase U9's final-report fields.
- [ ] 12.2 Reference the Phase 8 default-branch-guard discipline for the auto-commit + push.

## 13. REQ-013: flow-explorer agent

- [ ] 13.1 Create `agents/flow-explorer.md` with valid frontmatter (5 keys; `model: opus`; color).
- [ ] 13.2 Set the tools allowlist: `Read, Glob, Grep, LS, Bash, Write, TodoWrite`. NO `Edit`.
- [ ] 13.3 Author `## Inputs`, `## Process`, `## Output schema`, `## Bounded Write scope`, `## What this agent does NOT do`, `## Hard rules` sections.
- [ ] 13.4 In the body, state the do-not-rephrase-literal rule + the 10-15-additional-flows directive + the adjacent-capability discovery focus (e.g., "the user said 'upload files' but the site has 3 upload paths").

## 14. REQ-014: flow-executor agent

- [ ] 14.1 Create `agents/flow-executor.md` with valid frontmatter.
- [ ] 14.2 Set the tools allowlist: `Read, Glob, Grep, LS, Bash, Write, TodoWrite`. NO `Edit`.
- [ ] 14.3 Author body sections.
- [ ] 14.4 Document the four verdict values + the per-flow result schema + the per-flow trace/screenshot capture.
- [ ] 14.5 State the redundancy rationale (3 executors per flow surfaces flakiness as disagreement).

## 15. REQ-016: bug-fix-pipeline Phase B6b — Logical Sensibility Check

- [ ] 15.1 Edit `skills/bug-fix-pipeline/SKILL.md` — insert a new `## Phase B6b — Logical Sensibility Check` section between `## Phase B6` and `## Phase B7`.
- [ ] 15.2 Document the rationale (the user's auth-unavailable case verbatim — B6's QA-replay is too narrow).
- [ ] 15.3 Document the impact-set computation steps (changed files + importers + nav destinations + endpoints).
- [ ] 15.4 Document the `fix-sensibility-checker` agent dispatch.
- [ ] 15.5 Document the four verdict values (`sensible`, `nonsensical`, `env-failure`, `not-reachable`).
- [ ] 15.6 Document the `nonsensical` → fresh SR with `origin.kind: "fix-regression"` → recursive routing through bug-fix-pipeline.
- [ ] 15.7 Document the `--no-deploy` skip-with-note behavior.
- [ ] 15.8 Document the bounded-recursion rule (3 consecutive fix-regression bugs → escalate).
- [ ] 15.9 State the current fix is NOT marked complete until B6b returns clean.

## 16. REQ-017: fix-sensibility-checker agent

- [ ] 16.1 Create `agents/fix-sensibility-checker.md` with valid frontmatter (5 keys; `model: opus`; color).
- [ ] 16.2 Set the tools allowlist: `Read, Glob, Grep, LS, Bash, Write, TodoWrite`. NO `Edit`.
- [ ] 16.3 Author `## Inputs`, `## Process`, `## Output schema`, `## Bounded Write scope`, `## Impact-set computation`, `## What this agent does NOT do`, `## Hard rules` sections.
- [ ] 16.4 In the `## Impact-set computation` section, exhaustively document the git-grep heuristics for finding importers + nav destinations + endpoints.
- [ ] 16.5 Document the four verdict values + the verdict-file path.

## 17. REQ-015: pytest structural coverage

- [ ] 17.1 Create `tests/test_ux_test_builder_skill.py` — frontmatter; all 10 phase sections (U0-U9); the five disciplines; intake-schema fields; literal-flow-as-flow-1; 3-explorer + 3-executor; 3-cycle bounded convergence; ux-flow-failure routing.
- [ ] 17.2 Create `tests/test_flow_explorer_agent.py` — frontmatter; opus; tools (no Edit, Write present); 10-15-additional-flows directive; do-not-rephrase-literal rule.
- [ ] 17.3 Create `tests/test_flow_executor_agent.py` — frontmatter; opus; tools; four verdict values; per-flow-result path; redundancy rationale.
- [ ] 17.4 Create `tests/test_fix_sensibility_checker_agent.py` — frontmatter; opus; tools; impact-set computation section; four verdict values.
- [ ] 17.5 Create `tests/test_ux_test_builder_wiring.py` — cross-cutting wiring tests for the ux-test orchestrator.
- [ ] 17.6 Create `tests/test_bug_fix_phase_b6b_sensibility.py` — cross-cutting wiring tests for the bug-fix Phase B6b sensibility check.
- [ ] 17.7 Update `tests/test_skills.py` `EXPECTED_SKILLS` — append `ux-test-builder`.
- [ ] 17.8 Update `tests/test_agents.py` `EXPECTED_AGENTS` — append `flow-explorer`, `flow-executor`, `fix-sensibility-checker`.
- [ ] 17.9 Update `tests/test_commands.py` `EXPECTED_COMMANDS` — append `ux-test`.
- [ ] 17.10 Run `python -m pytest -q` from the repo root — all pass, no regression against the v0.9.28 baseline of 924.

## 18. REQ-018: documentation + release v0.9.29

- [ ] 18.1 Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to `0.9.29`.
- [ ] 18.2 Update README banner (`v 0 . 9 . 29`), version badge, tests badge.
- [ ] 18.3 Update NEW IN panel header to `v0.9.29`; add a v0.9.29 row covering both the ux-test-builder + the bug-fix Phase B6b sensibility check.
- [ ] 18.4 Update README timeline — move `(current)` to v0.9.29.
- [ ] 18.5 Update README inventory grid — SKILLS (22→23), AGENTS (22→25), COMMANDS (7→8); add the new entries.
- [ ] 18.6 Prepend `## [0.9.29] — 2026-05-23` entry in CHANGELOG.md.
- [ ] 18.7 Update `docs/CODEBASE_MAP.md` — `last_mapped` timestamp; counts (23 / 25 / 8); new sections in §3/§4.
- [ ] 18.8 Update `docs/INTEGRATION_MAP.md` — `last_synthesized`; note no new external integration.
- [ ] 18.9 Update `CLAUDE.md` — frontmatter counts (23 skills, 25 agents, 8 commands); brief mention of both new capabilities.
- [ ] 18.10 Run full pytest one final time — confirm all pass.

## 19. Archive

- [ ] 19.1 After every requirement is verified, run `openspec archive ux-test-builder` and merge the spec into `openspec/specs/ux-test-builder/`.
