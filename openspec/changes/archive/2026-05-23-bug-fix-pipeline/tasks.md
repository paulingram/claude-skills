## 1. REQ-001: bug-fix-pipeline skill

- [ ] 1.1 Create `skills/bug-fix-pipeline/SKILL.md` with valid frontmatter (`name: bug-fix-pipeline`, quoted `description`).
- [ ] 1.2 Author the ten phase sections — `## Phase B−1 — Intake & Mapping`, `## Phase B0 — Detection & Normalization`, `## Phase B1 — Bug Replication`, `## Phase B2 — Reproduction-artifact promotion + backend diagnostic`, `## Phase B3 — OpenSpec proposal authoring`, `## Phase B4 — Bug-Fix Generalization Audit`, `## Phase B5 — Implement + deploy to dev`, `## Phase B6 — QA replay against live dev`, `## Phase B7 — Archive + Report`, `## Phase B8 — Commit + push`.
- [ ] 1.3 Author the `## Five non-negotiable disciplines` section naming each of replicate-first / reproduction-is-regression / generalized-fix / QA-replay-against-live-dev / live-dev-by-default.
- [ ] 1.4 Author the `## Inputs` and `## Same input forms as architect-team-pipeline` sections.
- [ ] 1.5 Author the `## Operating rules (non-negotiable)` section — reuse the rules from architect-team-pipeline by reference + add the bug-fix-specific 10-iteration local ceiling.
- [ ] 1.6 Author the `## Default mode of operation` section referencing the v0.9.20 process-vs-domain-gate carve-out (the B1 ambiguity-escalation question is a domain gate; fires regardless of `--proposal-first`).

## 2. REQ-002: same-input-forms guarantee

- [ ] 2.1 In `skills/bug-fix-pipeline/SKILL.md` Phase B0, document BOTH input forms (folder OR plain-language prose) explicitly and reference v0.9.17 argument-parsing rules.
- [ ] 2.2 In `commands/bug-fix.md`, mirror `/architect-team`'s argument-parsing block verbatim — never refuse prose; never path-treat the first word; ask only when input is empty.

## 3. REQ-003: freshness pre-scan reuses intake-and-mapping

- [ ] 3.1 In `skills/bug-fix-pipeline/SKILL.md` Phase B−1, reuse `intake-and-mapping` verbatim — cite the skill name + the same freshness rules.
- [ ] 3.2 In `skills/intake-and-mapping/SKILL.md`, add a note that `bug-fix-pipeline` reuses this skill in its Phase B−1.

## 4. REQ-004: bug-replication discipline

- [ ] 4.1 Author Phase B1 in `skills/bug-fix-pipeline/SKILL.md` — Playwright for frontend (cite `playwright-user-flows`), backend script for backend (cite `dev-api-integration-testing`), ambiguity-escalation question for unclear bugs.
- [ ] 4.2 Document the three exit verdicts (`reproduced`, `could-not-reproduce`, `needs-clarification`) and their downstream behavior (proceed / escalate / pause).
- [ ] 4.3 Document the canonical ambiguity-escalation question phrasing ("How did you experience the bug? What did you click? What did you expect to see vs. what you saw?").

## 5. REQ-005: reproduction-artifact promotion + backend diagnostic

- [ ] 5.1 Author Phase B2 — promote the replication artifact into the target codebase's test directory.
- [ ] 5.2 State the rule: for frontend bugs the agent ALSO writes a backend diagnostic test.
- [ ] 5.3 State the rule: for backend-only bugs the script alone suffices.

## 6. REQ-006: OpenSpec proposal authoring for the fix

- [ ] 6.1 Author Phase B3 — slim OpenSpec change with the same artifact chain.
- [ ] 6.2 Mandate that the proposal cites the replication evidence verbatim.
- [ ] 6.3 Mandate that the Phase 1 planning-validation gate runs against the proposal.

## 7. REQ-007: generalized-fix architect review

- [ ] 7.1 Author Phase B4 in `skills/bug-fix-pipeline/SKILL.md` — dispatch the `system-architect` agent in `Bug-Fix Generalization Audit` mode.
- [ ] 7.2 Document the three verdicts (`pass`, `needs-generalization`, `needs-replacement`) and the user-override exception.
- [ ] 7.3 Edit `agents/system-architect.md` — add a `## Bug-Fix Generalization Audit` section documenting the mode alongside its existing audit modes.

## 8. REQ-008: QA-replay loop

- [ ] 8.1 Author Phase B6 — dispatch the `qa-replayer` agent on the reproduction artifact.
- [ ] 8.2 State the pass criterion: "the originating symptom is gone end-to-end" (NOT "the test passes").
- [ ] 8.3 Document the on-fail behavior: fresh OpenSpec proposal at B3 (not amended); loop bounded at 10 bug-fix iterations; global 20-step ceiling caps absolutely.

## 9. REQ-009: live-dev-environment-by-default

- [ ] 9.1 Author Phase B5 — deploy to the dev environment before Phase B6 testing; confirm builds green.
- [ ] 9.2 Document the `--environment production` exception (production deploy escalates to user).
- [ ] 9.3 State the build-failure routing (build failure → implementing team, NOT the QA-replay loop).

## 10. REQ-010: `/architect-team:bug-fix` command

- [ ] 10.1 Create `commands/bug-fix.md` with valid frontmatter (`description`, `argument-hint`).
- [ ] 10.2 Author the argument-parsing block mirroring `/architect-team` exactly (folder OR plain-language prose; flags `--no-commit` / `--no-push` / `--no-compact` / `--allow-push-to-default` / `--environment production` / `--force-bug` / `--no-deploy`).
- [ ] 10.3 Author the invocation block (Skill tool with `architect-team:bug-fix-pipeline`).
- [ ] 10.4 Author the auto-commit and auto-compact-prompt blocks mirroring `/architect-team`.

## 11. REQ-011: bug-replicator agent

- [ ] 11.1 Create `agents/bug-replicator.md` with valid frontmatter (5 keys; `model: opus`; color).
- [ ] 11.2 Set the tools allowlist: Read, Glob, Grep, LS, Bash, Write, TodoWrite (NO Edit).
- [ ] 11.3 Author `## Inputs`, `## Process`, `## Exit verdicts`, `## What this agent does NOT do`, `## Hard rules` sections.

## 12. REQ-012: qa-replayer agent

- [ ] 12.1 Create `agents/qa-replayer.md` with valid frontmatter.
- [ ] 12.2 Set the tools allowlist: Read, Glob, Grep, LS, Bash, TodoWrite (NO Edit, NO Write).
- [ ] 12.3 Author `## Inputs`, `## Process`, `## Exit verdicts`, `## What this agent does NOT do`, `## Hard rules` sections including the symptom-gone-end-to-end pass criterion.

## 13. REQ-013: bug-classifier agent + main-pipeline triage dispatch

- [ ] 13.1 Create `agents/bug-classifier.md` with valid frontmatter (`model: sonnet`; color).
- [ ] 13.2 Set the tools allowlist: Read, Glob, Grep, TodoWrite (NO Bash, NO Edit, NO Write).
- [ ] 13.3 Author the agent body documenting the verdict schema (kind / bug_portion / feature_portion / confidence / reasoning) and the lex-pass-then-structural-read method.
- [ ] 13.4 Edit `skills/architect-team-pipeline/SKILL.md` — add a `## Phase −2 — Triage & Routing` section BEFORE `## Phase −1 Prelude`. Document all four routing branches + the parallel-spawn pattern for `mixed` + the `triage_done: true` recursion-prevention flag.
- [ ] 13.5 Edit `commands/architect-team.md` — add `--bug-fix` and `--feature-only` opt-in flags (with natural-language phrasings); flags-intro extended.

## 14. REQ-014: pytest structural coverage

- [ ] 14.1 Create `tests/test_bug_fix_pipeline_skill.py` — frontmatter; all 10 phase sections; the five non-negotiable disciplines named; same-input-forms enforced; iteration ceiling mentioned.
- [ ] 14.2 Create `tests/test_bug_replicator_agent.py` — frontmatter; `model: opus`; tools allowlist correct (Edit NOT present; Write present); body sections.
- [ ] 14.3 Create `tests/test_qa_replayer_agent.py` — frontmatter; `model: opus`; tools allowlist correct (neither Edit nor Write present); three exit verdicts; on-fail routing rules.
- [ ] 14.4 Create `tests/test_bug_classifier_agent.py` — frontmatter; `model: sonnet`; tools allowlist exact (Read/Glob/Grep/TodoWrite); verdict schema fields all named in body.
- [ ] 14.5 Create `tests/test_triage_dispatch_wiring.py` — Phase −2 in pipeline skill names classifier + all four branches + parallel-spawn + triage_done; commands/architect-team.md documents both new flags; commands/bug-fix.md documents both input forms.
- [ ] 14.6 Update `tests/test_skills.py` `EXPECTED_SKILLS` — append `bug-fix-pipeline`.
- [ ] 14.7 Update `tests/test_agents.py` `EXPECTED_AGENTS` — append `bug-replicator`, `qa-replayer`, `bug-classifier`.
- [ ] 14.8 Update `tests/test_commands.py` `EXPECTED_COMMANDS` — append `bug-fix`.
- [ ] 14.9 Run `python -m pytest -q` — all pass, no regression against v0.9.21 baseline of 730.

## 15. REQ-015: documentation + release v0.9.22

- [ ] 15.1 Update README banner (`v 0 . 9 . 22`), version badge (`0.9.22`), tests badge.
- [ ] 15.2 Update NEW IN panel header to `v0.9.22`; add a v0.9.22 row at the top of the table covering the bug-fix-pipeline + triage layer.
- [ ] 15.3 Update README timeline — move `(current)` from v0.9.21 to a new v0.9.22 entry.
- [ ] 15.4 Update README inventory grid — SKILLS (21 → 22), AGENTS (18 → 21), COMMANDS (6 → 7); add the new rows.
- [ ] 15.5 Prepend `## [0.9.22] — 2026-05-23` to `CHANGELOG.md` covering REQ-001..015 with the user's verbatim directive as the WHY.
- [ ] 15.6 Update `docs/CODEBASE_MAP.md` — `last_mapped`, counts (22 / 21 / 7), §1 references v0.9.22, new sections for the new skill/agents/command.
- [ ] 15.7 Update `docs/INTEGRATION_MAP.md` — `last_synthesized`; note that bug-fix-pipeline reuses all existing integrations (no new ones).
- [ ] 15.8 Update `CLAUDE.md` — counts (22 skills, 21 agents); brief mention of bug-fix-pipeline + Phase −2 triage.
- [ ] 15.9 Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to `0.9.22`.
- [ ] 15.10 Run full pytest one final time — confirm all pass.

## 16. Archive

- [ ] 16.1 After every requirement is verified, run `openspec archive bug-fix-pipeline` to merge the spec deltas into `openspec/specs/`.
