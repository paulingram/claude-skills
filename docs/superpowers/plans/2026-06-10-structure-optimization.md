# Structure Optimization Pipeline (v3.11.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `structure-optimization` skill (+ `/architect-team:optimize-structure` command, 3 new agents, a `system-architect` Restructure Plan Audit mode) that produces an adversarially-verified, reference-closed codebase-restructure plan as an OpenSpec change.

**Architecture:** Exploration-pipeline shape (S0–S8) per `docs/superpowers/specs/2026-06-10-structure-optimization-design.md` — cartographer-team for maps, ×3 structure-analyst drafts → ralph-loop convergence with a deterministic partition check, reference-tracer shards for reference closure, ×3 structure-adversary refutation rounds (two consecutive clean rounds to exit), system-architect audit, plan assembly per superpowers:writing-plans conventions, openspec-propose authoring + strict validation.

**Tech Stack:** Markdown (skill/command/agents), Python stdlib (tests only — no new runtime code), pytest structural tests (ASCII-only test modules, `encoding="utf-8"` reads, ASCII prefix+tail heading matching per the cp1252 rule).

**Repo-convention override:** this repo releases as a single version-bump commit on an `architect-team/<slug>` branch merged `--no-ff` into main (see v3.10.0 / `95b13fd`). Per-task commits are therefore replaced by one release commit at the end; the design doc + plan commit lands on the branch first.

---

### Task 0: Branch

- [ ] **Step 0.1:** `git checkout -b architect-team/structure-optimization` (from `main`, clean tree).
- [ ] **Step 0.2:** Commit the design doc + this plan: `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "docs: structure-optimization design + plan (v3.11.0 prelude)"` after `git add docs/superpowers/specs/2026-06-10-structure-optimization-design.md docs/superpowers/plans/2026-06-10-structure-optimization.md`.

### Task 1: Agents (TDD — structural test first)

**Files:**
- Test: `tests/test_structure_optimization_agents.py` (new)
- Create: `agents/structure-analyst.md`, `agents/reference-tracer.md`, `agents/structure-adversary.md`
- Modify: `agents/system-architect.md` (add `## Restructure Plan Audit (structure-optimization Phase S6)` H2 + a row in `## Audit modes (index)`)
- Modify: `tests/test_agents.py` (EXPECTED_AGENTS += the 3 names)

- [ ] **Step 1.1: Write the failing test** — full content below (key assertions): the 3 agent files exist; frontmatter name/tools/model/color valid per house palettes; each carries the 3 canonical boilerplate H2s (`## Operating context (v1.0.0)`, `## Forbidden git operations`, `## Checkpoint discipline`); mandate keywords — analyst: `partition` + `stays` + independence ("do NOT consult"); tracer: `file:line` + `shard` + the `references_in` / `references_out_relative` field names + at least 4 search-surface kinds (`config`, `ci`, `docs`, `string-path`); adversary: `refute` + `modalities` + `two consecutive` + partition re-run + `git log --follow`; producer/checker separation sentences; `system-architect.md` contains the new H2 + index row + verdict JSON keys (`partition_check_confirmed`, `reference_closure_spot_check`, `migration_order_sound`).
- [ ] **Step 1.2:** `python -m pytest tests/test_structure_optimization_agents.py -q` → FAIL (files missing).
- [ ] **Step 1.3:** Author the 3 agent files (frontmatter: analyst opus/blue, tracer sonnet/orange, adversary opus/red; tools — analyst: Read, Glob, Grep, Bash, Write, TodoWrite; tracer: Read, Glob, Grep, Bash, Write, TodoWrite; adversary: Read, Glob, Grep, Bash, Write, TodoWrite; all bounded-Write to their run-artifact paths only). Copy the 3 boilerplate blocks verbatim from `agents/endpoint-tracer.md`, then run `python scripts/setup/sync_agent_boilerplate.py` and confirm `--check` exits 0.
- [ ] **Step 1.4:** Extend `agents/system-architect.md` with the Restructure Plan Audit mode + index row.
- [ ] **Step 1.5:** Add the 3 names to `EXPECTED_AGENTS` in `tests/test_agents.py`.
- [ ] **Step 1.6:** `python -m pytest tests/test_structure_optimization_agents.py tests/test_agents.py tests/test_agent_boilerplate_sync.py tests/test_cross_consistency.py -q` → PASS.

### Task 2: Skill (TDD)

**Files:**
- Test: `tests/test_structure_optimization_skill.py` (new)
- Create: `skills/structure-optimization/SKILL.md`
- Modify: `tests/test_skills.py` (EXPECTED_SKILLS += `structure-optimization`)

- [ ] **Step 2.1: Write the failing test** asserting: frontmatter (`name: structure-optimization`, description 20..1024 chars naming the triggers); the 9 stage H2s via ASCII prefix+tail (`("## Stage S0 ", "Initialization")` … `("## Stage S8 ", "Return")`); the 3 ralph-loop canonical invocations `/ralph-loop "` + `--completion-promise "STRUCTURE PROPOSAL CONVERGED"` / `"RESTRUCTURE PLAN VERIFIED"` / `"OPENSPEC AUTHORING COMPLETE"`; NO `--max-iterations` anywhere; cartographer-team reuse (`skill: cartographer-team` + `freshness_check`); the deterministic partition check (mentions `git ls-files`, `orphans`, `duplicates`, "exactly one", and that it gates S3 AND re-runs every S5 round AND at S6); `movements.json` schema fields (`schema_version`, `movement_id`, `references_in`, `references_out_relative`, `refactors`, `stays`, `partition_check`, `batches`, `adversarial_rounds`, `delete-dead`); the two-consecutive-clean-rounds exit rule; openspec authoring via `openspec-propose` + the `openspec validate --all --strict --json` gate; superpowers invocations (`superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:verification-before-completion`); CPC references (`## Uniform plugin usage (v3.9.0)`, `## Unbounded solving discipline (v3.8.0)`, `## Scope discipline`, `## MemPalace wake-up precondition`); Lead-owned dispatch phrasing ("single Agent-tool batch" + "tasks in the shared list"); `RESTRUCTURE_PLAN.md` + run-artifact paths under `.architect-team/structure-optimization/`; the "What this skill is NOT" section incl. "Not an executor"; producer/checker separation named.
- [ ] **Step 2.2:** Run → FAIL. **Step 2.3:** Author `skills/structure-optimization/SKILL.md` per the design (stages S0–S8, inputs JSON, partition-check snippet in polyglot form, movements.json schema, per-stage checklists + promises, Disciplines respected, What this skill is NOT). **Step 2.4:** Register in `EXPECTED_SKILLS`. **Step 2.5:** targeted pytest → PASS.

### Task 3: Command (TDD)

**Files:**
- Test: `tests/test_optimize_structure_command.py` (new)
- Create: `commands/optimize-structure.md`
- Modify: `tests/test_commands.py` (EXPECTED_COMMANDS += `optimize-structure`), `hooks/skill_invocation_audit.py` (frozen fallback tuple += `optimize-structure`; comment "19"→"20")

- [ ] **Step 3.1: Write the failing test** asserting: frontmatter description + argument-hint; dispatch-mode banner block FIRST (`teams_mode.py" --banner --command "/architect-team:optimize-structure"`); flag table (`--objective`, `--execute` default OFF, `--no-commit`, `--no-push`, `--no-compact`, `--all`); binds the skill (`skill: structure-optimization`); plan-producer rule ("never moves a single source file"); default-branch guard (`architect-team/optimize-structure-`); safety rules (`NEVER force-push`, no arbitrary wall-clock wakeups); the /compact box; `$ARGUMENTS` parsing section; cross-references section.
- [ ] **Step 3.2:** Run → FAIL. **Step 3.3:** Author `commands/optimize-structure.md` (mirror `visual-to-api.md` shape; banner; argument parsing; invoke skill via Skill tool; git behavior incl. never `git add -A`; `--execute` handoff to `architect-team-pipeline`; compact box). **Step 3.4:** Register in `EXPECTED_COMMANDS` + update the frozen fallback. **Step 3.5:** `python -m pytest tests/test_optimize_structure_command.py tests/test_commands.py tests/test_skill_invocation_audit_canonical.py tests/test_vao_glue_execution.py -q` → PASS.

### Task 4: Docs + version bump

**Files:** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (3.10.0→3.11.0); `CHANGELOG.md` (new `## [3.11.0] — 2026-06-10 — Structure Optimization Pipeline` entry: what shipped, counts 41/37/20, test delta, MINOR rationale); `CLAUDE.md` (counts line, skills/agents/commands bullets, Recent releases top entry — drop the oldest of the three); `docs/CODEBASE_MAP.md` (prepend a v3.11.0 paragraph to the frontmatter `note:` ledger); `README.md` (badge `tests-NNNN`, the "19 slash commands" line, inventory-grid counts — grep `40`, `34`, `19`, `4268` and sweep); `docs/INTEGRATION_MAP.md` (one entry: the new skill's touchpoints reuse the already-integrated cartographer / ralph-loop / openspec / superpowers plugins).

- [ ] **Step 4.1:** Apply all edits. **Step 4.2:** `python -m pytest tests/test_plugin_metadata.py tests/test_readme_styling.py tests/test_documentation_currency.py -q` → PASS.

### Task 5: Full suite + adversarial review

- [ ] **Step 5.1:** `python -m pytest -q` from repo root → expect previous 4268+5 plus the new tests, zero failures.
- [ ] **Step 5.2:** `$env:PYTHONUTF8 = "1"; python -m pytest -q` → same result (both-encodings rule).
- [ ] **Step 5.3:** Dispatch 2 read-only review subagents (house-conformance + reference-accuracy adversary) over the 6 new/changed markdown artifacts; fix every verified finding; re-run affected tests.

### Task 6: Release commit + merge

- [ ] **Step 6.1:** `git add` the explicit file list (never `-A`); commit on the branch: `v3.11.0: structure-optimization — adversarially-verified codebase-restructure planning pipeline (skill + command + 3 agents + system-architect audit mode)` with the `-c user.name="Paul Ingram"` override + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.
- [ ] **Step 6.2:** `git checkout main && git merge --no-ff architect-team/structure-optimization`. No push (not requested).

## Self-review

Spec coverage: maps→Task 2 (S1 + cartographer-team reuse assertions); adversarial→Tasks 1+2 (adversary agent + S5 rules); file movements + references + refactors→movements.json schema assertions (Task 2); architect full plan→Task 1 (audit mode) + Task 2 (S6); ralph/openspec/superpowers backbone→Task 2 assertions; reuse-existing-skills→cartographer-team/intake-and-mapping/CPC references. Placeholders: none — exact strings are pinned in the test assertions, which are the contract the markdown must satisfy. Type consistency: promise strings, schema field names, agent names, and section titles are spelled identically across Tasks 1–4.
