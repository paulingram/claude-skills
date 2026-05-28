# Tasks: frontend-missing-api-discipline

Single implementer slice.

## Files owned

- Modify: `agents/frontend.md` (new `## Missing-API discipline` section)
- Modify: `agents/backend.md` (new `## Missing-API SR intake` section)
- Modify: `agents/system-architect.md` (Phase 2 ordering-dependency check)
- Modify: `skills/interaction-completeness/SKILL.md` (new `pending-backend` classification)
- Modify: `skills/team-spawning-and-review-gates/SKILL.md` (new SR origin-kind + routing)
- Modify: `skills/common-pipeline-conventions/SKILL.md` (discipline section)
- Create: `tests/test_frontend_missing_api_discipline.py`
- Modify: `.claude-plugin/plugin.json` (1.7.0)
- Modify: `.claude-plugin/marketplace.json` (1.7.0)
- Modify: `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`

## Tasks

- [TASK-1] Author `## Missing-API discipline` section in `agents/frontend.md`:
  - One-paragraph framing: "When you encounter a UI element that needs a backend API which does not yet exist..."
  - The 4 forbidden anti-patterns (faking / mocking / hardcoding / silently stubbing) — explicit "MUST NOT"
  - The right pattern (SR + pause + return) — 4 numbered steps
  - The SR payload shape (origin.kind, description, acceptance_criteria, scope.files_to_change)
  - Cross-reference to `common-pipeline-conventions ## Frontend missing-API discipline` (or wherever the canonical section lands)
  ~30-45 lines.

- [TASK-2] Author `## Missing-API SR intake` section in `agents/backend.md`:
  - When you receive an SR with `origin.kind: "missing-api-for-frontend-element"` ...
  - Treat the frontend's specified shape as the contract
  - Implement the endpoint per the SR's acceptance_criteria
  - Surface the actual endpoint shape in your dispatch report (path, methods, request/response schemas, status codes, error cases)
  - The frontend will confirm before wiring; if your shape differs from what the frontend specified, the diff is in your report
  ~15-25 lines.

- [TASK-3] Update `agents/system-architect.md` Phase 2 architect brief:
  - Add a checklist item: "For each `both`-layer requirement, identify backend-vs-frontend ordering dependencies. Decide: sequence backend-first OR authorize frontend to surface missing-API SRs (default)."
  - Document that the missing-API SR pattern is the default for `both`-layer features (rather than enforcing strict backend-first sequencing)
  ~10-15 lines.

- [TASK-4] Update `skills/interaction-completeness/SKILL.md`:
  - Find the existing element classification list (currently 4: endpoint-backed / client-only / confirmed-stub / ambiguous)
  - Add the 5th: `pending-backend` (UI exists, awaiting SR-tracked backend endpoint)
  - Document the SR-linkage rule (must have a matching open SR with `origin.kind: "missing-api-for-frontend-element"`)
  - Document the verification rule (interaction-reviewer accepts `pending-backend` only with the SR; without, it's a gap)
  ~20-30 lines added.

- [TASK-5] Update `skills/team-spawning-and-review-gates/SKILL.md`:
  - Find the existing SR origin-kinds list (rca-product-bug / playwright-failure / integration-failure / etc.)
  - Add `missing-api-for-frontend-element` to the list
  - Document the routing (backend dispatched FIRST with the SR; on backend completion, frontend re-dispatched with SR resolved)
  - Note the divergence from standard SR flow: does NOT route through `diagnostic-research-team` (this isn't a test failure)
  ~15-25 lines added.

- [TASK-6] Update `skills/common-pipeline-conventions/SKILL.md`:
  - Add a new `## Frontend missing-API discipline` section (NOT under Scope discipline; this is its own concern)
  - Cover: 4 anti-patterns, right pattern (SR + pause + return), cross-references to frontend.md + backend.md + team-spawning-and-review-gates
  ~30-40 lines.

- [TASK-7] Author `tests/test_frontend_missing_api_discipline.py` with ≥ 8 tests:
  - `agents/frontend.md` has `## Missing-API discipline` exactly once
  - `agents/frontend.md` names the 4 anti-patterns (parametrize over 4)
  - `agents/frontend.md` names the SR origin-kind verbatim
  - `agents/backend.md` has `## Missing-API SR intake`
  - `agents/backend.md` names the SR origin-kind verbatim
  - `agents/system-architect.md` Phase 2 brief documents ordering check
  - `skills/interaction-completeness/SKILL.md` has `pending-backend` classification
  - `skills/team-spawning-and-review-gates/SKILL.md` lists the new SR origin-kind
  - `skills/common-pipeline-conventions/SKILL.md` has the discipline section
  - All 3 affected agents reference each other consistently (verb: `pending-backend`, kind: `missing-api-for-frontend-element`)

- [TASK-8] Version bumps: `plugin.json` + `marketplace.json` → `1.7.0`.

- [TASK-9] Docs:
  - CHANGELOG: prepend v1.7.0 entry (Added: missing-API discipline + pending-backend classification + new SR origin-kind + tests)
  - CLAUDE.md: v1.7.0 lead naming the discipline; bump test count
  - README: banner v1.7.0, badges, NEW IN row, status timeline
  - CODEBASE_MAP: last_mapped 2026-05-28T08:00:00Z; new test file; bump test count
  - INTEGRATION_MAP: last_synthesized 2026-05-28T08:00:00Z; note the discipline + new origin-kind

- [TASK-10] Commits (4 logical groups):
  1. `common-pipeline-conventions` discipline section + `tests/test_frontend_missing_api_discipline.py`
  2. 3 agents updated (frontend + backend + system-architect)
  3. `interaction-completeness` + `team-spawning-and-review-gates`
  4. Version bump + docs

- [TASK-11] Phase 3 review-evidence at `.architect-team/reviews/v1.7.0-frontend-missing-api-discipline.json` per v6. teammate = "v1.7.0-implementer". No `independent_review`.

- [TASK-12] Final test run:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: 2030 baseline + ~10-20 new = ~2040-2050 / 1 skipped.

## Acceptance

All 9 acceptance criteria from `proposal.md` `## QA Guidance`.
