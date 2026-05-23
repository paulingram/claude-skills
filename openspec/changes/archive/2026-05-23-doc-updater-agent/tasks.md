## 1. REQ-001: doc-updater agent

- [ ] 1.1 Create `agents/doc-updater.md` with valid frontmatter (`name: doc-updater`, `model: opus`, `color: orange`).
- [ ] 1.2 Set the tools allowlist exactly: `Read, Glob, Grep, LS, Bash, Write, TodoWrite`. NO `Edit`.
- [ ] 1.3 Author `## Inputs`, `## Process`, `## Output schema`, `## Bounded Write scope`, `## What this agent does NOT do`, `## Hard rules` sections.

## 2. REQ-002: agent process documented

- [ ] 2.1 In `## Process`, name the five steps explicitly: (1) inventory walk, (2) diff scan, (3) staleness identification, (4) update in place, (5) report.
- [ ] 2.2 Document the stale-section entry schema fields: `doc_path`, `section_anchor`, `current_value`, `expected_value`, `justification`.
- [ ] 2.3 Document the report path pattern: `<cwd>/.architect-team/documentation-currency/updates-<ts>.json`.
- [ ] 2.4 State the whole-file-rewrite strategy and its rationale (avoids partial-update inconsistency).

## 3. REQ-003: documentation-currency skill references doc-updater

- [ ] 3.1 Edit `skills/documentation-currency/SKILL.md` — add a `## Update mechanism — the doc-updater agent` section (or update the existing update-step language) that names the agent.
- [ ] 3.2 Document the producer/checker pairing: doc-updater produces; system-architect Documentation Currency Audit verifies.
- [ ] 3.3 Cite v0.9.15 (the gate's introduction) and v0.9.13 (the producer/checker discipline).

## 4. REQ-004: architect-team-pipeline Phase 8 dispatches doc-updater

- [ ] 4.1 Edit `skills/architect-team-pipeline/SKILL.md` — modify the Phase 8 `### Documentation-currency gate` block: step 1 (Update) dispatches `doc-updater` (replaces "the orchestrator performs the updates").
- [ ] 4.2 Leave step 2 (Audit) and step 3 (Gate) structurally unchanged.

## 5. REQ-005: bug-fix-pipeline Phase B8 dispatches doc-updater

- [ ] 5.1 Edit `skills/bug-fix-pipeline/SKILL.md` — modify Phase B8 (or its documentation-currency reference) to name the `doc-updater` agent dispatch.
- [ ] 5.2 State the parity: same dispatch, same audit, same gate as the main pipeline.

## 6. REQ-006: pytest structural coverage

- [ ] 6.1 Create `tests/test_doc_updater_agent.py` — frontmatter; `model: opus`; tools allowlist (Read/Glob/Grep/LS/Bash/Write/TodoWrite present; Edit absent); body sections present; bounded Write scope documented; forbidden-writes section forbids source / tests / openspec / version-json.
- [ ] 6.2 Create `tests/test_doc_updater_wiring.py` — cross-cutting wiring test: documentation-currency skill names the agent; architect-team-pipeline Phase 8 dispatches; bug-fix-pipeline Phase B8 dispatches.
- [ ] 6.3 Update `tests/test_agents.py` `EXPECTED_AGENTS` — append `doc-updater`.
- [ ] 6.4 Run `python -m pytest -q` — all pass, no regression against v0.9.22 baseline of 824.

## 7. REQ-007: documentation + release v0.9.23

- [ ] 7.1 Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to `0.9.23`.
- [ ] 7.2 Update README banner (`v 0 . 9 . 23`), version badge, tests badge.
- [ ] 7.3 Update NEW IN panel header to `v0.9.23`; add a v0.9.23 row at the top.
- [ ] 7.4 Update README timeline — move `(current)` to v0.9.23.
- [ ] 7.5 Update README inventory grid — AGENTS (21 → 22); add `doc-updater (opus)` row.
- [ ] 7.6 Prepend `## [0.9.23] — 2026-05-23` entry in CHANGELOG.md.
- [ ] 7.7 Update `docs/CODEBASE_MAP.md` — `last_mapped` timestamp; agent count 21 → 22; new entry for `agents/doc-updater.md` in §4; §1 references v0.9.23.
- [ ] 7.8 Update `docs/INTEGRATION_MAP.md` — `last_synthesized`; note the doc-updater dispatch (no new external integration).
- [ ] 7.9 Update `CLAUDE.md` — frontmatter counts (22 agents); brief mention of doc-updater + dispatch in both pipelines.
- [ ] 7.10 Run full pytest one final time — confirm all pass.

## 8. Archive

- [ ] 8.1 After every requirement is verified, run `openspec archive doc-updater-agent`.
