# Design: frontend-missing-api-discipline

## Reference

Full ACs + WHY + WHAT in `proposal.md`. This file holds the architectural anchors.

## The discipline (canonical statement)

When the frontend agent encounters a UI element that needs a backend API and that API does not yet exist:

**Forbidden** (4 anti-patterns):
1. **Fake the data** — render hardcoded sample values pretending they're dynamic
2. **Mock the endpoint** — wire `page.route` mocks and call it "done"
3. **Hardcode the response** — embed the JSON response shape inline
4. **Silently stub the UI** — render `<button disabled>` or skip the element with a `// TODO: wire when API ready` comment

**Right pattern** (4 steps):
1. **Author an SR** at `.architect-team/solution-requirements/SR-missing-api-<element>-<ts>.json` with:
   - `origin.kind: "missing-api-for-frontend-element"`
   - `description`: which UI element needs which API
   - `acceptance_criteria`: the endpoint contract (method, path, request shape, response shape, error cases)
   - `scope.files_to_change`: the backend files where the endpoint should land
2. **Pause work** on that specific UI element; continue work on other elements that don't have the gap
3. **Return your slice with the SR noted**; let the orchestrator dispatch the backend
4. **Wire up** when the orchestrator re-dispatches you with the SR marked `resolved`

## Why the SR-and-pause pattern (not fake/mock/hardcode/stub)

| Anti-pattern | Why it fails |
|---|---|
| Fake the data | Caught by `dynamic-value-discovery` review — but only after frontend shipped. Wastes the round trip. |
| Mock the endpoint | Caught by `playwright-user-flows` Real-backend-by-default — but only at Phase 5 integration. Wastes the round trip and adds technical debt. |
| Hardcode the response | Same as Fake-the-data. |
| Silently stub the UI | Caught by `interaction-completeness` `confirmed-stub` rule — but only if the user can explicitly confirm. Without the SR, the stub is a gap, not an authorized placeholder. |

The SR pattern is the only one that closes the loop cleanly: the gap becomes an explicit backend requirement that the v0.7.0 dev-loop auto-spawn picks up, and the frontend returns to wire up the real thing.

## The `pending-backend` element classification

`skills/interaction-completeness/SKILL.md` currently recognizes 4 element classifications:
- `endpoint-backed` — UI element is wired to a real endpoint
- `client-only` — element does client-side work (form validation, navigation)
- `confirmed-stub` — intentional placeholder, user-confirmed
- `ambiguous` — needs the user's input to classify

v1.7.0 adds a 5th: **`pending-backend`** — UI element exists, awaiting an SR-tracked backend endpoint. Distinct from `confirmed-stub` because:
- `confirmed-stub`: intentional, user-authorized, no plan to wire
- `pending-backend`: temporary, SR-authorized, will be wired once backend ships the endpoint

The `interaction-reviewer` agents accept `pending-backend` ONLY when:
1. The element has an associated open SR with `origin.kind: "missing-api-for-frontend-element"`
2. The SR specifies the endpoint contract (the eventual wire-up target)

Without the SR, the element is a gap (existing rule).

## Routing — how the orchestrator handles a missing-API SR

The v0.7.0 dev-loop auto-spawn already handles SR intake (Phase 3b). The new origin-kind routes specially:

```
Frontend agent surfaces SR-missing-api-foo-<ts>.json (status: open, origin.kind: missing-api-for-frontend-element)
    ↓
Phase 3b SR walker picks it up
    ↓
NEW v1.7.0 routing: dispatch backend agent FIRST with the SR as input
                    (NOT through diagnostic-research-team — this isn't a test failure,
                     it's a known-shape backend requirement)
    ↓
Backend implements the endpoint per the SR's acceptance_criteria
    ↓
Backend marks SR resolved: true; surfaces actual endpoint shape in report
    ↓
Orchestrator re-dispatches frontend with SR marked resolved + the actual shape
    ↓
Frontend wires up the element (the originally-paused work)
    ↓
Standard Phase 3 review-gate verification
```

The routing diverges from the standard SR flow (no `diagnostic-research-team` — that's for test failures) but reuses the existing fix-team-spawn machinery.

## Reuse Decision Log

### RD-1: Extend `agents/frontend.md`

**Decision:** Extend in place.
**Anchor:** Discipline lives in the agent's own body. The forbidden-patterns-and-right-pattern shape mirrors the v1.6.0 `## Forbidden git operations` pattern (which is in every agent including frontend).

### RD-2: Extend `agents/backend.md`

**Decision:** Extend in place.
**Anchor:** Backend needs to know how to receive + respond to the SR.

### RD-3: Extend `agents/system-architect.md` Phase 2 brief

**Decision:** Extend.
**Anchor:** Phase 2 architect brief already handles cross-layer planning; this is an additive concern.

### RD-4: Extend `skills/interaction-completeness/SKILL.md` with `pending-backend` classification

**Decision:** Extend the existing classification list.
**Anchor:** v0.9.X added the 4-classification system; v1.7.0 adds the 5th. Same structural pattern.

### RD-5: Extend `skills/team-spawning-and-review-gates/SKILL.md` with the new SR origin-kind

**Decision:** Extend the existing origin-kinds list.

### RD-6: Extend `skills/common-pipeline-conventions/SKILL.md` with the discipline section

**Decision:** Extend.
**Anchor:** Cross-cutting discipline; lives in the canonical home (v1.0.0 / v1.4.0 / v1.5.0 / v1.6.0 precedent).

### RD-7: NEW `tests/test_frontend_missing_api_discipline.py`

**Decision:** New file.

## Migration / backwards compatibility

- **v1.6.0 → v1.7.0:** Purely additive discipline. Well-behaved frontend runs (which didn't fake / mock / hardcode / stub before) see no change. New runs that would have done one of the anti-patterns now have an explicit alternative.
- **No flag.**
- **No behavior change for the runtime** beyond the new SR origin-kind.

## Trade-offs accepted

- **Documentation-only discipline.** No automated runtime detector (would require parsing the frontend agent's output for `page.route` mocks / hardcoded data). Mitigated by structural tests asserting the discipline is documented.
- **The pause-and-return cycle adds wall-clock time.** Worth it — the alternative is faking data that gets ripped out at Phase 5.
- **SR payload schema is informal in v1.7.0.** Tightening to a strict schema (validated by a hook) is a future v1.x.

## Version

v1.7.0 — minor bump (additive discipline + 1 new classification + 1 new SR origin-kind, no breaking change).
