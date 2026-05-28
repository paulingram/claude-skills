# Tasks: verified-agent-output (v2.0.0)

Six implementer slices, dispatched in two waves. Wave 1 is foundational (the new skill + the new agents + the schema bump + the vao_tools module). Wave 2 wires the framework into the pipeline bodies + adds the structural tests + bumps versions + updates docs. Wave 1 is sequenced before Wave 2 because the pipeline bodies (Wave 2) reference the agents + tools created in Wave 1.

## Files owned per slice

### Wave 1 slice 1: vao-skill — the canonical home

- Create: `skills/verified-agent-output/SKILL.md`

### Wave 1 slice 2: vao-agents — the two new agents

- Create: `agents/oracle-deriver.md`
- Create: `agents/adversarial-reviewer.md`

### Wave 1 slice 3: vao-tools — deterministic verification tools + schema bump

- Create: `hooks/vao_tools.py` (+ `__main__` CLI)
- Modify: `hooks/review_evidence_schema.py` (v6 → v7)
- Modify: `hooks/pipeline-completion-audit.py` (extended Stop hook)
- Modify: `hooks/review-gate-task.py` (uses v7 schema)
- Modify: `hooks/teammate-idle-check.py` (uses v7 schema)

### Wave 2 slice 4: pipeline-integration — wire Layer 1 + 2 + 4 into the 3 pipeline bodies

- Modify: `skills/architect-team-pipeline/SKILL.md` (Phase 0.5 + Layer 2 spawn brief + Layer 4 Phase −2 step)
- Modify: `skills/bug-fix-pipeline/SKILL.md` (analogous insertions at Phase B0.5 + B3 + B−1)
- Modify: `skills/mini-architect-team-pipeline/SKILL.md` (analogous insertions at Phase M0.5 + M5 + M0)
- Modify: `skills/team-spawning-and-review-gates/SKILL.md` (manifest v2 + adversarial-pairing)
- Modify: `skills/common-pipeline-conventions/SKILL.md` (Layer 4 section)

### Wave 2 slice 5: command-integration — opt-out + auto-cleanup paths

- Modify: `commands/architect-team.md` (`--no-vao` flag)
- Modify: `commands/bug-fix.md` (`--no-vao` flag)
- Modify: `commands/mini.md` (`--no-vao` flag)

### Wave 2 slice 6: tests + version + docs

- Create: `tests/test_verified_agent_output.py` (≥ 40 tests)
- Create: `tests/fixtures/vao/scope-narrowing.json`
- Create: `tests/fixtures/vao/git-stash-clobber.json`
- Create: `tests/fixtures/vao/frontend-fake-data.json`
- Create: `tests/fixtures/vao/oracle-structure-mismatch.json`
- Modify: `.claude-plugin/plugin.json` (2.0.0)
- Modify: `.claude-plugin/marketplace.json` (2.0.0)
- Modify: `CHANGELOG.md` (prepend v2.0.0 entry with breaking-change call-out + migration guide)
- Modify: `CLAUDE.md` (replace v1.7.0 lead with v2.0.0 lead; bump test count)
- Modify: `README.md` (banner v2.0.0, badges, "NEW IN v2.0.0" row)
- Modify: `docs/CODEBASE_MAP.md` (last_mapped bump; add new files to inventory; bump test count)
- Modify: `docs/INTEGRATION_MAP.md` (last_synthesized bump; note the discipline addition)

## Tasks

### Wave 1 (sequenced — foundational)

- [TASK-1] Author `skills/verified-agent-output/SKILL.md`. Cover the five layers in their own H2 sections; the failure-shape taxonomy; the per-shape adversarial-reviewer pairings; the four vao_tools verdicts; the run-history shape-detection mechanism (Layer 4); the composition rules with existing Phase 3 / Phase 5 reviewers (the picture: v2.0.0 = early nets BEFORE Phase 5, late nets unchanged AT Phase 5); the migration guide (v6 → v7 schema break); the explicit `--no-vao` escape-hatch trade-off. Target: ~600-800 lines.

- [TASK-2] Author `agents/oracle-deriver.md`. Frontmatter: `name: oracle-deriver`, `model: opus`, `description: "<one-line>"`, `tools: Bash Read Glob Grep TodoWrite Write` (Write restricted by body to the oracle-spec path). Body covers: when invoked (Phase 0.5 trigger conditions), how it walks each oracle shape (component-tree / design-map / api-contract / data-model / hybrid), the JSON schema it produces, the `_human_review_required` gate, the bounded-3-cycle convergence loop on user rejection. ~200-300 lines.

- [TASK-3] Author `agents/adversarial-reviewer.md`. Frontmatter: `name: adversarial-reviewer`, `model: opus`, `description: "<one-line>"`, `tools: Bash Read Glob Grep TodoWrite Write` (Write restricted to its `adversarial_review` block in the shared evidence file). Body covers: which shape it was paired for (passed in the spawn brief), which `vao_tools` tool it invokes, how it polls the teammate's tool-call log, the `adversarial_review` block schema it writes, the verdict semantics. ~150-200 lines.

- [TASK-4] Author `hooks/vao_tools.py`. Four deterministic tool functions: `verify_oracle_match(built_path, oracle_spec) -> dict`, `verify_baseline_clean(tool_call_log_path, baseline_sha=None) -> dict`, `verify_no_fake_data(diff_files, oracle_spec) -> dict`, `verify_every_element(component_paths, oracle_spec) -> dict`. Each writes a verdict JSON to `<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json`. Module also exposes a `__main__` CLI dispatching by subcommand (`vao verify-oracle-match ...`). All stdlib only. Deterministic / bit-stable output for given inputs. ~400-500 lines.

- [TASK-5] Bump `hooks/review_evidence_schema.py` to schema v7. Update `SCHEMA_VERSION = 7`. Extend `REQUIRED_EVIDENCE_FIELDS` with `oracle_match_review`, `baseline_clean_review`, `no_fake_data_review`, `adversarial_review`. Add a new `_validate_adversarial_review()` helper mirroring `_validate_independent_review()`. Add allowed-value sets for the three new `*_review` fields (`pass` / `n/a` / `fail`). The hook BLOCKS `fail` on each. Add the new fields to `validate_evidence()`. Update the docstring to v7 and note the BREAKING migration.

- [TASK-6] Extend `hooks/pipeline-completion-audit.py` to walk the coverage map and, for every entry, assert that the matching VAO verdict files exist at `<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json` with positive verdicts. A missing verdict OR a negative verdict is a blocking finding. Use the same exit-2 semantics as the existing audit failures.

- [TASK-7] Extend `hooks/review-gate-task.py` and `hooks/teammate-idle-check.py` to use the v7 schema (these already import from `review_evidence_schema.py`, so the change should be a single-line schema-version assertion + the existing v6 → v7 import). Verify each by running the existing 2056-test baseline against the v7 hooks; the baseline must remain green.

### Wave 2 (sequenced after Wave 1 — wires the framework in)

- [TASK-8] Modify `skills/architect-team-pipeline/SKILL.md` to insert the new Phase 0.5 (oracle-derivation gate) between the existing Phase 0 and Phase 1. Document the trigger conditions, the `oracle-deriver` dispatch, the user-confirmation gate, the bounded-3-cycle convergence loop, the frozen-spec path. ALSO extend Phase 2's spawn-brief documentation to include `vao_task_shape` and `vao_adversarial_role`. ALSO extend Phase −2 to invoke `vao detect-shape` at the end of triage and surface the shape-detection question when prior runs match. ALSO extend Phase 7's master-review audit to walk VAO verdicts.

- [TASK-9] Modify `skills/bug-fix-pipeline/SKILL.md` with the analogous insertions at Phase B0.5 (oracle-derivation for the bug's affected surface), Phase B3's spawn brief (manifest v2 fields), Phase B−1 (run-history shape detection), Phase B8's master audit (VAO verdicts).

- [TASK-10] Modify `skills/mini-architect-team-pipeline/SKILL.md` with the analogous insertions at Phase M0.5 (oracle-derivation), Phase M5's mini-qa dispatch (manifest v2 fields — note: mini ships a single qa-reviewer, so the adversarial-reviewer pairing collapses to one-paired-with-mini-qa), Phase M0 (run-history shape detection).

- [TASK-11] Modify `skills/team-spawning-and-review-gates/SKILL.md` to add a `## VAO task-shape pairing (v2.0.0)` section. Document the five shapes, the per-shape adversarial-reviewer assignment, the manifest v2 schema bump (adding `vao_task_shape` and `vao_adversarial_role` fields), the concurrent-dispatch rule (teammate + adversarial-reviewer in the same Phase 2 batch). Update the existing manifest schema example JSON to include the two new fields.

- [TASK-12] Modify `skills/common-pipeline-conventions/SKILL.md` to add a `## Run-history shape detection (v2.0.0)` section. Document the `.architect-team/run-history/` JSON schema, the `vao detect-shape` tool, the Phase −2 invocation point in all three pipelines, the user-confirmation surface wording.

- [TASK-13] Add the `--no-vao` flag to each of `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`. Document the flag in the help section + the explicit trade-off (the v1.x failure modes re-open when VAO is disabled).

- [TASK-14] Author `tests/test_verified_agent_output.py`. Target ≥ 40 tests, parametrized where natural:
  - Skill body assertions (5 layers + 5 shapes + 5 pairings + 4 tools = ~20 parametrized assertions)
  - Agent frontmatter + body assertions (oracle-deriver + adversarial-reviewer = ~6 assertions × 2 agents)
  - `vao_tools.py` unit tests (each of 4 tools × positive + negative fixture = 8 assertions)
  - Schema v7 validation (positive + negative for each of the 4 new fields = 8 assertions)
  - Pipeline integration (Phase 0.5 / 0 / M0.5 presence × 3 pipelines = 3 assertions)
  - Manifest v2 schema bump (1-2 assertions)
  - Layer 4 section in common-pipeline-conventions (3-4 assertions)
  - `--no-vao` flag in each command body (3 assertions)
  - End-to-end synthetic-fixture replay (4 fixtures × end-to-end audit assertion = 4 assertions)

- [TASK-15] Create the four synthetic-fixture files under `tests/fixtures/vao/`. Each is a minimal JSON capturing the failure shape: `scope-narrowing.json` is a synthetic Phase 0 state where the user's prompt contained a parity verb and the agent's narrower interpretation is recorded; `git-stash-clobber.json` is a synthetic teammate tool-call log with a `git stash` line; `frontend-fake-data.json` is a synthetic diff with `"John Smith"` literal + an oracle spec naming `"John Smith"` as a dynamic value; `oracle-structure-mismatch.json` is a synthetic built-tree + frozen oracle spec with one divergence.

- [TASK-16] Version bumps in `plugin.json` and `marketplace.json` → `2.0.0`.

- [TASK-17] Docs:
  - **CHANGELOG.md:** prepend v2.0.0 entry. Lead with `BREAKING: review-evidence schema v6 → v7`. Document the migration path. Document the five layers. Document the `--no-vao` escape hatch. Acknowledge the cost trade-offs honestly (~15-25% wall-clock, ~2× tokens).
  - **CLAUDE.md:** replace the v1.7.0 lead with a v2.0.0 lead. Bump test counts. Add the four new files to the inventory section.
  - **README.md:** banner v2.0.0, badges, NEW IN v2.0.0 row naming the five layers + the breaking schema change + the `--no-vao` escape hatch.
  - **CODEBASE_MAP.md:** `last_mapped: 2026-05-28T<ts>Z`; bump test counts (2056 → ~2110); add `skills/verified-agent-output/`, `agents/oracle-deriver.md`, `agents/adversarial-reviewer.md`, `hooks/vao_tools.py`, `tests/test_verified_agent_output.py`, `tests/fixtures/vao/` to the inventory; bump file/skill counts (26 skills → 27; 27 agents → 29; etc.).
  - **INTEGRATION_MAP.md:** `last_synthesized: 2026-05-28T<ts>Z`; note the v2.0.0 framework addition.

- [TASK-18] Commits (6 logical groups, matching the slices):
  1. `verified-agent-output skill (canonical home of the VAO framework)` — slice 1
  2. `oracle-deriver + adversarial-reviewer agents` — slice 2
  3. `vao_tools.py + schema v7 + hook extensions (BREAKING)` — slice 3
  4. `Phase 0.5 oracle-derivation + Layer 2 + Layer 4 in 3 pipelines` — slice 4
  5. `--no-vao flag in pipeline-driving commands` — slice 5
  6. `tests + fixtures + version bump + docs` — slice 6

- [TASK-19] Phase 3 review-evidence at `.architect-team/reviews/v2.0.0-verified-agent-output.json` per v7. teammate = "v2.0.0-implementer", task_id = "v2.0.0-verified-agent-output". Now requires `oracle_match_review` / `baseline_clean_review` / `no_fake_data_review` / `adversarial_review` fields — populate per the v7 schema; for a documentation-only slice these are `n/a` with appropriate notes.

- [TASK-20] Final regression:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: 2110 (+ 1 skipped) — the existing 2056 + the ~54 new from TASK-14.

- [TASK-21] OpenSpec validation:
  ```bash
  cd /Users/paulingram/Documents/code/claude-skills && openspec validate verified-agent-output --strict --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('valid:', d['summary']['totals']['passed']==1)"
  ```
  Expected: `valid: True`.

## Acceptance

All 14 acceptance criteria from `proposal.md` `## QA Guidance`. The proposal-first gate hands this proposal back to the user for review before Wave 1 starts.
