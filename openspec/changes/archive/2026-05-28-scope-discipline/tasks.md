# Tasks: scope-discipline

Single implementer slice. Documentation + structural-test change; no Python helpers, no behavior-runtime change.

## Files owned

- Modify: `skills/common-pipeline-conventions/SKILL.md` (NEW `## Scope discipline` section)
- Modify: `skills/architect-team-pipeline/SKILL.md` (anti-pattern entry referring to canonical section)
- Modify: `skills/bug-fix-pipeline/SKILL.md` (same)
- Modify: `skills/mini-architect-team-pipeline/SKILL.md` (same)
- Modify: `agents/prompt-refiner.md` (add scope-fidelity axis)
- Modify: `skills/proposal-refiner/SKILL.md` (axis in grade schema)
- Modify: `agents/bug-classifier.md` (action-verb interpretation section)
- Modify: `agents/system-architect.md` (Master Review Audit + Phase 2 architect brief get scope-narrowing check)
- Create: `tests/test_scope_discipline.py` (≥ 8 grep-audit tests)
- Modify: `.claude-plugin/plugin.json` (1.4.0)
- Modify: `.claude-plugin/marketplace.json` (1.4.0)
- Modify: `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`

## Tasks

- [TASK-1] Author the `## Scope discipline` section in `skills/common-pipeline-conventions/SKILL.md`. Cover: the anti-pattern (silently narrowing), comparison to v0.9.36 anti-deferral, the 6 parity-implying verbs (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`), what each implies (visual + structural + behavioral parity), domain-gate rule, surfacing pattern (`AskUserQuestion` BEFORE starting with an example wording), explicit forbidden patterns. ~50-70 lines.

- [TASK-2] In each of the 3 pipeline SKILL.md bodies (architect-team-pipeline, bug-fix-pipeline, mini-architect-team-pipeline), find the anti-patterns / operating-rules section and ADD a one-line entry: *"Don't silently narrow the prompt's scope. If the agent's interpretation is materially narrower than the prompt's literal meaning, surface the scope decision via `AskUserQuestion` before starting. Per `common-pipeline-conventions` `## Scope discipline`."*

- [TASK-3] Update `agents/prompt-refiner.md`:
  - Add `scope-fidelity` to the grading-axis table (currently 5 axes; making 6)
  - Update the grade-schema JSON example to include `scope-fidelity`
  - Add a section after the axis table describing what `scope-fidelity` measures and that a flagged value is a domain gate

- [TASK-4] Update `skills/proposal-refiner/SKILL.md`:
  - Find the `### Phase R2 — Initial clarity audit + grade` section
  - Update the grade-schema JSON to include `scope-fidelity`
  - Update the weighted-overall formula description (the 5 weights need to add a 6th; suggested: Clarity 0.20 + Scope 0.18 + Acceptance 0.20 + Grounding 0.17 + Conflict 0.08 + ScopeFidelity 0.17 — adjust as needed to sum to 1.0)

- [TASK-5] Update `agents/bug-classifier.md`:
  - Add a section `## Action-verb interpretation (v1.4.0)` documenting the 6 parity-implying verbs + the rule that the classifier MUST NOT scope narrower than the verb implies
  - State that a parity-verb prompt with a narrower-than-literal interpretation should trigger the `unclear` verdict with a scope-clarifying question (not the `feature` or `bug` verdict with a silently narrowed interpretation)

- [TASK-6] Update `agents/system-architect.md`:
  - In the Master Review Audit mode section, add a scope-narrowing check: the audit MUST verify the run's scope matches the original prompt's literal meaning OR there is explicit user authorization for any narrowing (recorded in the change folder, e.g., in `proposal.md`'s "Out of scope" section with prose from the user). Silent narrowings are a verdict-failure condition.
  - In the Phase 2 architect brief section, add scope-narrowing detection: when drafting the plan, the architect MUST confirm the proposed scope matches the original prompt's literal meaning; if not, surface a scope-clarification question before completing the draft.

- [TASK-7] Author `tests/test_scope_discipline.py` with ≥ 8 grep-audit tests:
  - common-pipeline-conventions has `## Scope discipline` exactly once
  - common-pipeline-conventions section contains all 6 verbs
  - common-pipeline-conventions section contains the `AskUserQuestion` surfacing pattern
  - each of the 3 pipeline bodies references `common-pipeline-conventions` `## Scope discipline`
  - `agents/prompt-refiner.md` contains `scope-fidelity`
  - `agents/bug-classifier.md` contains the action-verb section
  - `agents/system-architect.md` Master Review Audit mode references the scope-narrowing check
  - `skills/proposal-refiner/SKILL.md` Phase R2 grade schema contains `scope-fidelity`

- [TASK-8] Version bumps: `plugin.json` + `marketplace.json` → `1.4.0`.

- [TASK-9] Docs:
  - CHANGELOG: prepend v1.4.0 entry (Added: scope-discipline section + 6th refiner axis + tests; Changed: 3 pipeline bodies + prompt-refiner + bug-classifier + system-architect updated for scope-narrowing detection; Migration: backwards-compatible discipline change)
  - CLAUDE.md: replace v1.3.0 lead with v1.4.0 lead naming the scope discipline; bump test count to ~1720
  - README: banner v1.4.0, badges, NEW IN v1.4.0 row, status timeline
  - CODEBASE_MAP: last_mapped 2026-05-28T05:00:00Z; tests count ~1720 / 76; mention the new test file in inventory
  - INTEGRATION_MAP: last_synthesized 2026-05-28T05:00:00Z; note the discipline addition

- [TASK-10] Commits (4 logical groups):
  1. common-pipeline-conventions Scope discipline section + tests/test_scope_discipline.py
  2. 3 pipeline body anti-pattern entries + bug-classifier + system-architect
  3. proposal-refiner skill + prompt-refiner agent (the 6th axis)
  4. Version bump + docs

- [TASK-11] Phase 3 review-evidence at `.architect-team/reviews/v1.4.0-scope-discipline.json` per v6. teammate = "v1.4.0-implementer", task_id = "v1.4.0-scope-discipline". DO NOT write `independent_review`.

- [TASK-12] Final test run:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: ~1720 passed / 1 skipped (the +N is the new test file; exact count depends on parametrize expansions).

## Acceptance

All 9 acceptance criteria from `proposal.md` `## QA Guidance`.
