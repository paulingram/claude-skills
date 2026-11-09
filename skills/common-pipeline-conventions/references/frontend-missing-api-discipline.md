# Frontend missing-API discipline

When the frontend agent builds a UI element (a button, a form field, a list, a status display, an avatar) that needs a backend API which **does not yet exist** and no contract-first protocol is running for it, the agent must NOT improvise. The four improvisations are all defects in the costume of progress — each ships visibly-broken work that downstream gates catch only after wasted round trips. v1.7.0 names the explicit alternative: surface the missing API as a structured solution requirement, pause that element's work, continue on other elements, and return to wire up when the backend ships the endpoint.

### Forbidden (4 anti-patterns)

The frontend agent MUST NOT do any of the following when an API needed by a UI element does not yet exist:

1. **Fake the data** — render the design mockup's hardcoded sample literal (`"John Smith"`, `"$1,234.00"`, `"Shipped"`) as if it were the dynamic value. This is the exact defect `dynamic-value-discovery` catches at review — but only AFTER the frontend slice ships; the round trip is wasted.
2. **Mock the endpoint** — wire `page.route('**/api/users/me', ...)` returning a canned 2xx response and call it "tested." This is the exact defect `playwright-user-flows`'s "Real backend by default" discipline catches at Phase 5 integration — but only after the slice is at the integration gate; the round trip is wasted AND the mock becomes technical debt the next teammate must rip out.
3. **Hardcode the response shape** — inline the JSON shape into the component (or a helper) where a fetched response should sit. Same review-time defect as faking the data, one layer deeper.
4. **Silently stub the UI** — render `<button disabled>`, ship a placeholder page, or leave the element off the page with a `// TODO: wire when API ready` comment. `interaction-completeness`'s `confirmed-stub` rule catches this — but only when the user has explicitly confirmed the stub. Without the SR, an unconfirmed stub IS a gap, and the orchestrator has nothing structured to route a fix from.

All four are downstream catches. The clean move is to surface the missing API as a backend requirement at the moment the gap is discovered.

### Right pattern (SR + pause + return)

1. **Author a solution requirement** at `<cwd>/.architect-team/solution-requirements/SR-missing-api-<element>-<ts>.json` per `team-spawning-and-review-gates`'s `## Solution Requirements` schema with `origin.kind: "missing-api-for-frontend-element"`. The payload documents the required endpoint: method, path, request shape, response shape, error responses, the UI element that needs it, and the file the frontend will wire on backend completion. `scope.files_to_change` lists the backend files where the endpoint should land (best-effort; the backend agent confirms or revises).
2. **Pause work on that specific UI element.** Do not render fake data, do not wire a mock, do not ship a placeholder. Continue work on the OTHER elements in your slice that do not depend on this missing API — that part of the slice ships normally.
3. **Return your slice with the SR noted in your review-gate evidence.** Note in the `notes` field of your `independent_review` block (or as a top-level escalation) which element is paused pending the SR. The orchestrator's Phase 3b SR walker picks up the SR and dispatches the backend agent against it directly (no `diagnostic-research-team` routing — this isn't a test failure; it's a known-shape backend requirement).
4. **Wire up when the orchestrator re-dispatches you with the SR marked `resolved`.** The backend's dispatch report carries the actual endpoint shape — confirm the shape matches what you specified in the SR (the backend may surface a schema diff if the contract had to change), then wire the element to the now-live endpoint per `dynamic-value-discovery` (bind every dynamic value to its named data source). The `pending-backend` classification on this element flips to `endpoint-backed` once wired.

### Cross-references

- `agents/frontend.md` `## Missing-API discipline` is the per-agent statement of the rule (the frontend is where the discipline fires).
- `agents/backend.md` `## Missing-API SR intake` documents the backend response: implement per the SR's `acceptance_criteria`, surface the actual endpoint shape in the dispatch report, flag any schema diff for the frontend to confirm before wiring.
- `skills/team-spawning-and-review-gates/SKILL.md` lists `missing-api-for-frontend-element` as a recognized SR `origin.kind` AND documents the routing (backend dispatched FIRST; frontend re-dispatched on backend completion).
- `skills/interaction-completeness/SKILL.md` recognizes the `pending-backend` element classification — a UI element WITH a matching open SR is `pending-backend`; without the SR, it is an `unwired-control` gap.

### Why the SR-and-pause pattern, not fake/mock/hardcode/stub

| Anti-pattern | Where it gets caught | Cost |
|---|---|---|
| Fake the data | `dynamic-value-discovery` review (Phase 3 / Phase 5) | Round trip wasted; reviewer has to chase the fake literal across the diff. |
| Mock the endpoint | `playwright-user-flows` Real-backend-by-default audit (Phase 5) | Round trip wasted; the mock becomes technical debt the next teammate rips out. |
| Hardcode the response | `dynamic-value-discovery` (same as Fake-the-data) | Same as Fake-the-data, one layer deeper. |
| Silently stub the UI | `interaction-completeness` `unwired-control` / `placeholder-page` gap | Without the SR the stub is a gap; with no user confirmation it routes through a remediation loop anyway. |
| **SR + pause + return** | Caught immediately at the frontend agent's authoring step | Loop closes cleanly: missing API → SR → backend dispatched → endpoint ships → frontend wires it. Zero technical debt. |
