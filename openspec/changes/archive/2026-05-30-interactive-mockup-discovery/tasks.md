# Tasks: interactive-mockup-discovery (v2.1.0)

Six implementer slices. Sequenced for the plugin self-development case (single author, single repo, pytest as the structural reviewer).

## Tasks

- [TASK-1] Author `skills/interactive-mockup-discovery/SKILL.md` as the canonical home. Document the two-pass mechanism, the 7 action_kind values, the interactions[] schema, the interaction_intent_gap surfacing protocol, the verify-interactions-honored verdict contract, the relationship to oracle-deriver / interaction-intuiter / Phase −1D bulk-verify. Cross-references to verified-agent-output, vao_tools.py, schema v7.

- [TASK-2] Author `agents/interaction-observer.md`. Frontmatter: name, description, model: opus, tools: Read/Edit/Write/Glob/Grep/LS/Bash/TodoWrite/NotebookRead/NotebookEdit, color: green. Carry the uniform `## Operating context`, `## Forbidden git operations`, `## Checkpoint discipline` sections. Body documents the 4-step protocol (run mockup → enumerate → simulate → record) and the bounded Write to .architect-team/oracle-spec/<change>/interaction-evidence/.

- [TASK-3] Extend `agents/oracle-deriver.md` to name `interactive-mockup` as a 6th spec_shape value, and add a short paragraph documenting the dispatch contract for interaction-observer.

- [TASK-4] Extend `agents/interaction-intuiter.md` with a new INTENT-INFERENCE mode section. Document the mismatch matrix, the interaction_intent_gap entry shape, the Phase −1D bulk-verify integration.

- [TASK-5] Extend `hooks/vao_tools.py` with `verify_interactions_honored(built_components, oracle_spec, out_path=None) -> dict` AND a `verify-interactions-honored` CLI subcommand. Return shape: `{tool, matched, gaps, honored_count, total_count, verdict_at}`. Deterministic / bit-stable (sorted keys, indent=2). Stdlib only.

- [TASK-6] Extend `hooks/review_evidence_schema.py` to add `interactions_honored_review` as an OPTIONAL field (not in REQUIRED_EVIDENCE_FIELDS). Add `VALID_INTERACTIONS_HONORED_VALUES = {"pass", "n/a", "fail"}` and a guarded validator that only fires when the field is present.

- [TASK-7] Create `tests/fixtures/vao/interactive-mockup-logout-misroute.json` — the canonical synthetic fixture per the design's failure-mode mapping.

- [TASK-8] Author `tests/test_vao_interactions_honored.py` (≥ 20 tests) — positive/negative/determinism for the 6th tool + the fixture round-trip + the optional schema field semantics.

- [TASK-9] Author `tests/test_interactive_mockup_discovery.py` (≥ 20 tests) — skill body assertions + agent frontmatter + oracle-deriver/interaction-intuiter extension assertions.

- [TASK-10] Update `tests/test_skills.py` `EXPECTED_SKILLS` (add `interactive-mockup-discovery`). Update `tests/test_agents.py` `EXPECTED_AGENTS` (add `interaction-observer`).

- [TASK-11] Version bump: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` to `2.1.0`. Update `tests/test_dispatch_banner.py` `test_plugin_metadata_at_1_5_0` assertion to `2.1.0`.

- [TASK-12] Docs:
  - **CHANGELOG.md** — prepend v2.1.0 entry (additive, backwards-compatible, names the two-pass mechanism and the new file inventory).
  - **CLAUDE.md** — refresh the lead paragraph with v2.1.0 framing.
  - **README.md** — banner v 2 . 1 . 0; inventory grid 28 → 29 skills, 29 → 30 agents.

- [TASK-13] OpenSpec archive: `openspec archive interactive-mockup-discovery --yes`. Update `tests/test_verified_agent_output.py` if needed (it shouldn't be — those tests resolve the v2.0.0 archive via glob).

- [TASK-14] Final regression: `python3 -m pytest -q` → expected ~2300 PASS + 1 SKIPPED.

- [TASK-15] Default-branch guard: commit to `architect-team/interactive-mockup-discovery` feature branch. Push with `git push -u origin`.

## Acceptance

All 12 acceptance criteria from `proposal.md`'s QA Guidance. Pytest suite passes at ~2300 / 1 skipped.
