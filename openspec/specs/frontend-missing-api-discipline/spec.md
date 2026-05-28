# frontend-missing-api-discipline Specification

## Purpose
TBD - created by archiving change frontend-missing-api-discipline. Update Purpose after archive.
## Requirements
### Requirement: frontend agent documents the missing-API discipline

`agents/frontend.md` SHALL gain a `## Missing-API discipline` section documenting: the 4 forbidden anti-patterns (faking data, mocking endpoints, hardcoding values, silently stubbing UI), the right pattern (write an SR + pause + return after backend resolves), and the SR origin-kind `missing-api-for-frontend-element` verbatim.

#### Scenario: section exists exactly once

- **WHEN** `agents/frontend.md` is parsed
- **THEN** it contains `## Missing-API discipline` exactly once

#### Scenario: section names the 4 forbidden anti-patterns

- **WHEN** the section is read
- **THEN** it names "faking" / "mocking" / "hardcoding" / "silently stubbing" (or equivalent prose for each) as forbidden patterns

#### Scenario: section documents the right pattern

- **WHEN** the section is read
- **THEN** it names writing an SR at `.architect-team/solution-requirements/` with `origin.kind: "missing-api-for-frontend-element"`
- **AND** it instructs the agent to PAUSE work on the element after writing the SR
- **AND** it instructs the agent to RETURN and wire when the orchestrator re-dispatches with the SR resolved

#### Scenario: section enumerates the SR payload shape

- **WHEN** the section is read
- **THEN** it documents that the SR's payload describes the required endpoint (method, path, request shape, response shape, error cases)

### Requirement: backend agent documents the missing-API SR intake

`agents/backend.md` SHALL gain a `## Missing-API SR intake` section documenting the response pattern: when receiving an SR with `origin.kind: "missing-api-for-frontend-element"`, implement the endpoint per the SR's described shape, surface the actual shape in the dispatch report so the frontend agent can confirm before wiring.

#### Scenario: section exists exactly once

- **WHEN** `agents/backend.md` is parsed
- **THEN** it contains `## Missing-API SR intake` exactly once

#### Scenario: section names the SR origin-kind verbatim

- **WHEN** the section is read
- **THEN** it contains `missing-api-for-frontend-element` (the same string used by frontend agent)

### Requirement: system-architect Phase 2 documents ordering-dependency check

`agents/system-architect.md` Phase 2 architect brief section SHALL document checking backend-vs-frontend ordering dependencies for `both`-layer features. The architect identifies whether frontend can be implemented without missing-API SRs, and either sequences backend-first OR authorizes frontend to surface missing-API SRs (default).

#### Scenario: Phase 2 brief documents the ordering check

- **WHEN** the Phase 2 architect brief section in `agents/system-architect.md` is parsed
- **THEN** it documents identifying backend-vs-frontend ordering dependencies for `both`-layer features
- **AND** it mentions the missing-API SR as the default mechanism

### Requirement: interaction-completeness recognizes pending-backend classification

`skills/interaction-completeness/SKILL.md` SHALL be updated to recognize a new element classification `pending-backend` (UI exists, awaiting an SR-tracked backend endpoint). The skill SHALL document that `interaction-reviewer` accepts `pending-backend` only when a corresponding open SR with `origin.kind: "missing-api-for-frontend-element"` exists; without the SR, the element is a gap.

#### Scenario: pending-backend classification documented

- **WHEN** the skill body is parsed
- **THEN** it contains `pending-backend` as a recognized element classification
- **AND** it states the SR-linkage rule (must have a matching open SR with `origin.kind: "missing-api-for-frontend-element"`)
- **AND** it states that without the SR, `pending-backend` is a gap (not a confirmed-stub)

### Requirement: team-spawning lists the new SR origin-kind

`skills/team-spawning-and-review-gates/SKILL.md` SHALL list `missing-api-for-frontend-element` in its recognized SR origin-kinds list and document the routing: the orchestrator dispatches the backend agent with the SR as input; on backend completion, the orchestrator re-dispatches the frontend agent with the SR marked `resolved` so the frontend can wire up.

#### Scenario: SR origin-kind enumerated

- **WHEN** the skill body is parsed
- **THEN** it contains `missing-api-for-frontend-element` in the recognized SR origin-kinds list
- **AND** it documents the routing (backend dispatched first; frontend re-dispatched after)

### Requirement: common-pipeline-conventions documents the discipline

`skills/common-pipeline-conventions/SKILL.md` SHALL document the 4 anti-patterns + the right pattern in a dedicated sub-section. May be a new `## Frontend missing-API discipline` section OR a sub-section under the existing `## Scope discipline` (v1.4.0).

#### Scenario: section documents the discipline

- **WHEN** the skill body is parsed
- **THEN** there exists a heading (level 2 or 3) explicitly naming missing-API or frontend-API discipline
- **AND** the section body names the 4 anti-patterns
- **AND** the section body names the SR + pause + return right pattern

### Requirement: Structural tests assert the discipline is documented

The plugin SHALL ship `tests/test_frontend_missing_api_discipline.py` with ≥ 8 tests covering the discipline assertions above.

#### Scenario: ≥ 8 tests collected and passing

- **WHEN** `python3 -m pytest tests/test_frontend_missing_api_discipline.py --collect-only` runs
- **THEN** it collects ≥ 8 tests
- **AND** all collected tests pass

### Requirement: Version bumped to 1.7.0

`1.7.0` SHALL be consistent across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, top of `CHANGELOG.md`, README banner + version badge, CLAUDE.md overview paragraph.

#### Scenario: plugin metadata at 1.7.0

- **WHEN** `plugin.json` and `marketplace.json` are read
- **THEN** both have `"version": "1.7.0"`

