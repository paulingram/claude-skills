# Tasks

## 1. Engine + tests (REQ-001, REQ-002, REQ-004, REQ-006)
- [x] 1.1 NEW `scripts/claude_design/claude_design_import.py` — `detect_claude_design_offer`, `parse_design_url`, `ClaudeDesignSource` + `FakeClaudeDesignSource`, `materialize_project` (+ `_safe_relpath`), `import_claude_design`, `plan_when_unavailable`, `main` CLI. Stdlib-only, no import-time side effects, `from __future__ import annotations`. TDD — failing tests first. (REQ-001, REQ-002, REQ-004)
- [x] 1.2 NEW `tests/test_claude_design_import.py` — detection (URL form, MCP-mention form, `?file=`/`Implement:` parse, no-offer); `parse_design_url` decode edges (`%2F`, `+`); fetch-orchestration vs `FakeClaudeDesignSource`; `materialize_project` writes all files + records focus; path-traversal + absolute-path rejection; `plan_when_unavailable` instruct-then-fallback / instruct-then-halt. Offline; green under cp1252 + `PYTHONUTF8=1`. (REQ-006)

## 2. Skill + wiring (REQ-003, REQ-005, REQ-007)
- [x] 2.1 NEW `skills/claude-design-import/SKILL.md` — the contract (frontmatter no `': '`/no `' #'`, description ≤ 1024; `# H1` + `## When this skill runs` + `## Two first-class input sources` + `## Workflow` + `## Honest boundary` + `## Cross-references`). (REQ-002, REQ-003, REQ-004, REQ-005)
- [x] 2.2 EDIT `skills/intake-and-mapping/SKILL.md` — additive input-discovery subsection invoking `claude-design-import`. (REQ-003, REQ-005)
- [x] 2.3 EDIT `agents/oracle-deriver.md` — body note: a Claude Design link materialized by `claude-design-import` is walked as an `interactive-mockup` oracle (frontmatter untouched). (REQ-003)
- [x] 2.4 EDIT `skills/design-fidelity-mapping/SKILL.md` — add the materialized Claude Design dir to the design-input source list. (REQ-003)
- [x] 2.5 EDIT `commands/architect-team.md` + `commands/visual-to-api.md` + `commands/ux-test.md` — one-line note that these design-consuming commands detect a Claude Design link and route it through `claude-design-import`. (REQ-007)
- [x] 2.6 Count-pins: `tests/test_skills.py` `EXPECTED_SKILLS` gains `claude-design-import` + count 47 → 48; `tests/test_instruction_compliance.py` in-scope skill count 47 → 48 (112 → 113 files). (REQ-006, REQ-007)

## 3. Gates (all REQs)
- [x] 3.1 Instruction-compliance lint clean over the in-scope set incl. the new/edited files (`scripts/compliance/instruction_compliance.py`). (REQ-007)
- [x] 3.2 Independent review — `task-reviewer` (pass) + `adversarial-reviewer` (producer != checker) on the diff; remediate findings. (all REQs)
- [x] 3.3 Full `python -m pytest` green under cp1252 + `PYTHONUTF8=1` (baseline 5212 passing + 5 skipped + this change's new tests). (REQ-006)
- [x] 3.4 `openspec validate --all --strict` clean. (all REQs)

## 4. Master review + ship (REQ-008)
- [x] 4.1 Phase 7: master-review audit `overall: pass`; `openspec archive claude-design-mcp-import`.
- [x] 4.2 Phase 8: version 3.33.0 (plugin.json + marketplace.json); doc-updater + doc-currency audit pass (README, CHANGELOG, CLAUDE.md, both maps, rubric count table — 47 → 48 skills); commit + push + merge --no-ff to main.
