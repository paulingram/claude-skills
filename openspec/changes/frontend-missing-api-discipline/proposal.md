# Proposal: frontend-missing-api-discipline (v1.7.0)

## Why

When the frontend agent builds a UI element (button, form field, list, status display) that needs a backend API which **does not yet exist**, the current discipline doesn't tell it what to do. Options the agent might take silently:

- **Fake the data** — render hardcoded sample values (caught by `dynamic-value-discovery` but only at review time)
- **Mock the endpoint** — wire `page.route` mocks and call it "done" (caught by `playwright-user-flows` Real backend by default, but only at Phase 5)
- **Stub the UI** — render `<button disabled>` or `// TODO: wire when API ready` (caught by `interaction-completeness` `confirmed-stub` but only if explicitly user-confirmed)
- **Skip the element** — silently leave the element off the page (caught by `interaction-completeness` if the requirement is explicit, otherwise drift)

All four are downstream catches. The CLEAN move is: at the moment the frontend agent discovers the API is missing, surface that as a **backend requirement** via an SR, pause work on that element, and return to wire it up after the backend ships the API.

v1.7.0 makes this explicit in the frontend agent's body + introduces a new SR `origin.kind: "missing-api-for-frontend-element"` that the existing v0.7.0 dev-loop auto-spawn routes to the backend.

## What changes

1. **`agents/frontend.md`** body update — new `## Missing-API discipline` section. When you encounter a UI element that needs a backend API which doesn't exist yet:
   - Do NOT fake / mock / hardcode / stub
   - Write an SR at `.architect-team/solution-requirements/SR-missing-api-<element>-<ts>.json` with `origin.kind: "missing-api-for-frontend-element"` describing the required endpoint (method, path, request shape, response shape, error cases)
   - Pause that element's work
   - When the backend ships the API (orchestrator re-dispatches you with the SR resolved), return and wire up
2. **`agents/backend.md`** companion update — new `## Missing-API SR intake` section. When you receive an SR with `origin.kind: "missing-api-for-frontend-element"`, treat the frontend's specified shape as the contract and implement the endpoint per it. Surface the backend's actual shape in your dispatch report so the frontend agent can confirm before wiring.
3. **`agents/system-architect.md`** Phase 2 architect brief update — when planning a `both`-layer feature, the architect MUST identify backend-vs-frontend ordering dependencies upfront. If the frontend slice can't be fully implemented without backend APIs, the architect either: (a) dispatches backend FIRST and frontend after, OR (b) explicitly authorizes the frontend to surface missing-API SRs (the default — and most common).
4. **`skills/interaction-completeness/SKILL.md`** — recognize a new element classification: `pending-backend` (UI exists, awaiting an SR-tracked backend endpoint). The `interaction-reviewer` agents accept `pending-backend` only when there's a corresponding open SR with `origin.kind: "missing-api-for-frontend-element"`. Without the SR, the element is a gap (the existing rule).
5. **`skills/team-spawning-and-review-gates/SKILL.md`** — add `missing-api-for-frontend-element` to the recognized SR origin-kinds list + document the routing (backend gets dispatched; frontend gets re-dispatched after backend resolves the SR).
6. **`skills/common-pipeline-conventions/SKILL.md`** — new sub-section under existing `## Scope discipline` (v1.4.0) or as its own section: documenting the four anti-patterns above as forbidden, naming the missing-API SR as the right pattern.
7. **`tests/test_frontend_missing_api_discipline.py`** — grep audits asserting the disciplines are documented.
8. **Version bump v1.7.0** in plugin.json + marketplace.json + CHANGELOG + CLAUDE.md + README + maps.

## QA Guidance

### Acceptance Criteria

- [AC-1] `agents/frontend.md` has a `## Missing-API discipline` section naming the 4 forbidden anti-patterns, the right pattern (SR + pause + return), and the SR origin-kind verbatim.
- [AC-2] `agents/backend.md` has a `## Missing-API SR intake` section documenting the response pattern + shape-surfacing.
- [AC-3] `agents/system-architect.md` Phase 2 architect brief documents the ordering-dependency check for `both`-layer features.
- [AC-4] `skills/interaction-completeness/SKILL.md` documents the `pending-backend` classification + the SR linkage rule.
- [AC-5] `skills/team-spawning-and-review-gates/SKILL.md` lists `missing-api-for-frontend-element` as a recognized SR origin-kind + documents the routing.
- [AC-6] `skills/common-pipeline-conventions/SKILL.md` documents the anti-patterns + right pattern.
- [AC-7] `tests/test_frontend_missing_api_discipline.py` exists with ≥ 8 tests asserting the disciplines are documented.
- [AC-8] All existing tests pass (2030 baseline) + new tests. Target: ~2040+ / 1 skipped.
- [AC-9] Version `1.7.0` consistent across plugin.json, marketplace.json, CHANGELOG, README, CLAUDE.md.

### Unit Test Targets

- Grep audits on the 5 affected files for the required substrings
- `tests/test_team_spawning_and_review_gates.py` (or equivalent) updated if it tests the SR origin-kinds list

### Integration Test Targets

- N/A — discipline change is documentation + structural; pytest suite IS the integration test.

### Playwright Flows

- N/A.

### Out of Scope

- **Automated detection at runtime** — a hook that scans frontend diffs for `page.route` mocks / hardcoded data and flags missing-API. Future v1.x.
- **Backend changes to pre-emptively expose APIs** — out; the discipline assumes the backend may not yet have shipped. The pattern handles that case.
- **A `frontend-missing-api-pending` lifecycle UI** — the SR file IS the lifecycle marker; no separate UI needed in v1.7.0.

## Impact

- **Modified:** `agents/frontend.md`, `agents/backend.md`, `agents/system-architect.md`, `skills/interaction-completeness/SKILL.md`, `skills/team-spawning-and-review-gates/SKILL.md`, `skills/common-pipeline-conventions/SKILL.md`, CHANGELOG, CLAUDE.md, README, CODEBASE_MAP, INTEGRATION_MAP, plugin.json, marketplace.json.
- **New:** `tests/test_frontend_missing_api_discipline.py`, 1 openspec change folder.
- **Test count:** 2030 → ~2040+.
- **Version:** v1.6.0 → **v1.7.0**.
- **Backwards-compatible:** purely additive discipline. Well-behaved frontend runs (those that didn't fake / mock / hardcode / stub when an API was missing) see no change.
