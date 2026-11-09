# Solution Requirements — auto-spawn the dev loop on any surfaced issue

Whenever an agent surfaces an issue during testing — a Playwright failure, an integration test failure, a live-dev-API regression, a visual-fidelity drift, an RCA product-bug verdict — the agent does NOT just write a handoff and wait. It ALSO writes a structured **solution requirement** that the orchestrator automatically picks up and feeds back into Phase 2 of the dev loop. The loop is closed: issue → solution requirement → fix team spawned → fix flows through Phase 2 → Phase 5 → original test re-runs → verdict pass → originating teammate's task unblocks.

This converts "alert the user" into "fix the system." Alerts that don't trigger remediation are process failures; the discipline is to spawn the remediation, not log the alert.

### File location

```
<cwd>/.architect-team/solution-requirements/SR-<short-id>-<ISO-8601-UTC>.json
```

where `<short-id>` is derived from the originating test ID, drifted screen+element, or affected requirement. Use `_safe_id()`-compatible characters only (no `/`, `\`, leading `.`, or `..`).

### Schema

```json
{
  "schema_version": 1,
  "solution_id": "SR-test_user_completes_first_login-2026-05-18T15:00:00Z",
  "created_at": "<ISO 8601 UTC>",
  "origin": {
    "kind": "playwright-failure" | "integration-test-failure" | "live-dev-regression" | "visual-fidelity-drift" | "rca-product-bug" | "visual-qa-audit" | "test-completeness-failure" | "integration-testing-failure" | "editability-gap" | "unwired-control" | "placeholder-page" | "hardcoded-dynamic-value" | "missing-api-for-frontend-element" | "security-finding" | "a11y-gap" | "spec-drift" | "cross-layer-backend-required" | "cross-layer-frontend-required" | "incomplete-implementation-scope-required" | "live-data-wiring-gap" | "affordance-coverage-gap",
    "discovered_in": "Phase 3" | "Phase 5" | "/architect-team:visual-qa" | "ad-hoc",
    "discovered_by": "<teammate-name or 'integration' or 'visual-qa'>",
    "test_id": "<failing test ID, if applicable>",
    "rca_artifact": "<path to rca/<test-id>-<ts>.json, if applicable>",
    "reconciliation_artifact": "<path to visual-fidelity/<screen>-<viewport>-<ts>.json, if applicable>",
    "handoff_artifact": "<path to .architect-team/handoffs/<from>-to-<to>-<ts>.md if also written>"
  },
  "problem_summary": "<one-paragraph user-facing description: what the user sees that they should not, in product terms not implementation terms>",
  "expected_behavior": "<one-paragraph spec citation: what DESIGN_MAP / coverage-map / proposal.md says SHOULD happen>",
  "evidence": [
    "<path to log excerpt / screenshot / captured payload>",
    "<file:line citation>",
    "..."
  ],
  "affected_requirements": ["REQ-012", "REQ-019"],
  "affected_screens": ["/login", "/dashboard"],
  "scope": {
    "files_to_change": ["src/auth/login.py", "src/auth/__init__.py"],
    "files_to_test": ["tests/integration/test_login_dev_api.py", "tests/playwright/test_login.spec.ts"]
  },
  "acceptance_criteria": [
    "POST /api/auth/login with a soft-deleted account returns 410 Gone with body {error: 'account_deactivated'}",
    "POST /api/auth/login with a valid account returns 200 with body.user.name as a non-null string matching the DB row's name column",
    "Existing test_user_completes_first_login passes against the live dev API",
    "Visual-fidelity reconciliation for /dashboard's user-name banner reaches verdict perfect"
  ],
  "suggested_team": "backend-auth",
  "blast_radius": "single endpoint; no schema changes; safe to deploy with the existing release window",
  "priority": "critical" | "high" | "medium" | "low",
  "status": "open"
}
```

### Required field validity

- `solution_id` must be unique and `_safe_id()`-compatible.
- `origin.kind` must be one of the **canonical catalog** values. This is the OPEN canonical catalog (an `origin.kind` is added here when a new discipline introduces one — agents do NOT invent ad-hoc kinds, but the catalog itself grows with the framework):
  - **Test-failure origins** (route through `diagnostic-research-team` first): `playwright-failure`, `integration-test-failure`, `integration-testing-failure`, `live-dev-regression`, `visual-fidelity-drift`, `rca-product-bug`, `visual-qa-audit`, `test-completeness-failure`.
  - **Converged-map / known-shape origins** (spawn a fix team DIRECTLY): `editability-gap`, `unwired-control`, `placeholder-page`, `hardcoded-dynamic-value`, `missing-api-for-frontend-element`, `live-data-wiring-gap`, `affordance-coverage-gap`, `a11y-gap`, `security-finding`, `spec-drift`.
  - **Cross-layer / scope origins** (dispatched to the named layer/team): `cross-layer-backend-required`, `cross-layer-frontend-required`, `incomplete-implementation-scope-required`.
  - **`security-finding` (v3.10.0)** is produced by the `security-hunter` adversarial shape (NOT a Layer 3 `verify_*` severity — it is a code-review finding routed as an SR). It spawns the owning team (backend for an authz / injection / deserialization / secret finding; the dependency-adding team for an unjustified dependency) DIRECTLY; the diagnosis is already complete in the finding's `{class, file, line, evidence, remediation}`.
  - **`spec-drift`** is written when implementations disagree because the SPEC they read differed — one teammate briefed before an amendment and one after — or when code and spec disagree at review time. It spawns a fix team **DIRECTLY**: the diagnosis ("the spec line changed, and here is which fingerprint each side was briefed against") is already complete, so there is nothing for `diagnostic-research-team` to research. `spec-drift` is deliberately **NOT** a member of `TEST_FAILURE_ORIGINS` (`hooks/shared_rule_constants.py`) — adding it would attach a diagnostic-plan requirement to a diagnosis that is already written, and dilute the test-failure taxonomy with a non-test-failure. The SR's `evidence` cites both manifests' `spec_fingerprint` values and the amended artifact; its `acceptance_criteria` name the reading that wins. Where code and spec disagree, the code wins and the spec is amended in the same phase, per `common-pipeline-conventions` `## Spec currency discipline (mid-run) (v3.47.0)` — never "the readers misread".
  - **`a11y-gap` (v3.10.0)** is produced by the `interaction-completeness` accessibility axis (sub-kinds `keyboard-unreachable` / `missing-accessible-name` / `axe-violation`); it spawns the owning frontend team DIRECTLY.
- `editability-gap` SRs — and the three interaction-gap kinds (`unwired-control`, `placeholder-page`, `hardcoded-dynamic-value`) — spawn a fix team DIRECTLY; they do NOT route through `diagnostic-research-team`. The `editability-completeness` team's converged editable-surface map, and the `interaction-completeness` team's converged interaction map, each already name the exact attribute / control / page / value, the exact trace stage or gap kind, and the exact file; the diagnosis is complete, so no diagnostic research is needed. (The test-failure origins — `rca-product-bug`, `playwright-failure`, `integration-test-failure`, `integration-testing-failure`, `test-completeness-failure`, `visual-fidelity-drift` — DO route through `diagnostic-research-team` first; the converged-map-origin kinds do not. These spellings are canonical across the catalog, the runtime constant `hooks/shared_rule_constants.py::TEST_FAILURE_ORIGINS`, and the pipeline routing lists.)
- **`missing-api-for-frontend-element` SRs (v1.7.0)** also spawn a fix team DIRECTLY — they do NOT route through `diagnostic-research-team` because this is not a test failure; it is a known-shape backend requirement. The frontend agent that authored the SR has already named the endpoint contract (method, path, request shape, response shape, error responses) in the `acceptance_criteria`. Routing: **the orchestrator dispatches the BACKEND agent FIRST** with the SR as input — the backend implements the endpoint per the SR's `acceptance_criteria`, surfaces the actual endpoint shape in its dispatch report, and marks the SR `resolved`. On backend completion, the orchestrator **re-dispatches the FRONTEND agent** with the SR marked `resolved` so the frontend can read the backend's dispatch report, confirm the shape matches its SR (or reconcile against a documented schema diff), and wire up the originally-paused UI element. The element's `interaction-completeness` classification flips from `pending-backend` to `endpoint-backed` once the wire-up lands. The pause-and-return cycle is the v1.7.0 alternative to faking / mocking / hardcoding / silently stubbing — see `common-pipeline-conventions` `## Frontend missing-API discipline` for the canonical rule.
- `problem_summary` and `expected_behavior` are non-empty strings.
- `evidence` is a non-empty array; an SR without evidence is an alert dressed as a requirement.
- `affected_requirements` may be empty if the problem is in territory not yet covered by the coverage map — but then `affected_screens` (for visual) or `scope.files_to_change` MUST be non-empty so the orchestrator can attribute the fix.
- `acceptance_criteria` MUST include the original failing test as one of its criteria. The fix is only complete when the test that surfaced the issue passes.
- `suggested_team` is a hint; the orchestrator may route differently based on file ownership.
- `priority` defaults to `"high"` for any RCA product-bug, `"critical"` for any visual-fidelity drift blocking a designed user journey, and per-case judgment otherwise.

### Orchestrator pickup (architect-team-pipeline behavior)

When the orchestrator resumes (after any subagent signals idle), it MUST:

1. Walk `.architect-team/solution-requirements/*.json`.
2. For each SR with `status: "open"`:
   - If `affected_requirements` is non-empty → append entries to the active change's `coverage-map.json` referencing the SR ID; mark each entry `status: "in_progress"` once the fix team is spawned.
   - If `affected_requirements` is empty → write a new coverage-map entry derived from `acceptance_criteria` + `affected_screens` + `scope`.
   - Spawn a Phase 2 team per `team-spawning-and-review-gates` rules. The teammate's brief includes the SR ID, the SR file path, the acceptance criteria copied verbatim, the files_owned from `scope.files_to_change`, and a pointer to the original failing test that becomes the team's review-gate verification.
   - Update SR `status: "in_progress"` and record the spawned teammate name in a new `spawned_teammate` field.
3. The fix team works through Phase 3 (review gate) → Phase 4 (reconciliation if shared boundary) → Phase 5 (the original failing test re-runs as part of integration).
4. When the originating test reaches verdict `pass`, the orchestrator marks the SR `status: "resolved"` with a `resolved_at` timestamp and a `resolved_by` commit SHA, then unblocks the ORIGINATING teammate's task. The originating teammate re-runs whatever they were waiting on (visual-fidelity reconciliation, RCA, etc.) and that loop now converges to pass.
5. Master review (Phase 7) walks every SR and confirms each is `resolved` AND its acceptance criteria are reflected in a passing test in the coverage map.

### What this prevents

- Alerts that sit in a handoff file forever until someone manually triages them.
- Failures that surface, get logged, and don't translate into a code change.
- Teammates that mark their task `visual_fidelity_review: "fail"` and leave the fix to the user.
- Phase 5 failures that route back to a team in name only, with no concrete acceptance criteria attached.
- Process drift where "we'll fix it next sprint" silently re-enters the backlog instead of the active loop.

### Mandatory consumers (these skills write SRs on every applicable trigger)

- `root-cause-test-failures` Phase C — every `product-bug` RCA verdict writes an SR alongside the handoff. The handoff is for human readability; the SR is for orchestrator action.
- `visual-fidelity-reconciliation` Phase E — every escalation (out-of-scope file, implementation-extras, spec-ambiguity, cascade-blast-radius) writes an SR. Drift that gets autonomously fixed-to-spec does NOT need an SR (the fix happened in-loop).
- `playwright-user-flows` — when a Playwright test fails AND the RCA verdict is product-bug, the SR is written by RCA (don't duplicate). When a test reveals a UI contract that the implementation never honored (gap in the original spec), write an SR with `origin.kind: "playwright-failure"`.
- `dev-api-integration-testing` — when an integration test fails against the live dev API with a backend regression (RCA verdict product-bug), the SR is written by RCA. When the failure is in test-author error or env / fixture / race, fix in-loop without an SR (per root-cause-test-failures Phase C).
- `test-completeness-verifier` agent — every `overall: fail` writes an SR with `origin.kind: "test-completeness-failure"` so the orchestrator re-spawns the originating team with concrete missing-test acceptance criteria. The originating team re-enters Phase 2 to author the missing tests, passes Phase 3, and the verifier re-runs in Phase 5 to confirm. When the failure is specifically a `both`-layer feature whose happy-path user-flow tests ran against a mocked / fake backend (the `backend_integration_audit` is `mock_backed` with no explicit requirements authorization), the verifier instead uses `origin.kind: "integration-testing-failure"` — the orchestrator routes this through `diagnostic-research-team` (it is a test-failure origin) before spawning the fix team, and the `acceptance_criteria` mandate re-authoring the happy path against the real running backend.
- `editability-completeness` team — every gap in the converged editable-surface map (an attribute a user should be able to control whose end-to-end trace breaks: a `missing-control`, `dead-control`, `orphan-field`, `no-readback`, or `schema-mismatch`) becomes an SR with `origin.kind: "editability-gap"`. The `acceptance_criteria` are end-to-end and concrete: the create/edit flow has a working control for the attribute, the value reaches the database, the read-back returns it, and a real-backend integration test covers the round-trip. The fix team is spawned directly. After the fixes land, the three `editability-reviewer` agents re-spawn and re-review until the converged map has zero gaps.
- `interaction-completeness` team — every gap in the converged interaction map becomes an SR whose `origin.kind` is the gap kind: an `unwired-control` (an interactive element that drives no endpoint and no client behavior, with no user confirmation it is an intentional stub — also the kind for a correctly-wired control whose only break is a missing or vacuous user-flow test), a `placeholder-page` (a route wired to a placeholder / "coming soon" / skeleton / mock page where a live page is specified, unconfirmed), or a `hardcoded-dynamic-value` (a value hardcoded as the design's sample literal where the context shows it should be dynamically bound). The `acceptance_criteria` are precise: an `unwired-control` is wired end-to-end (or confirmed as a stub); a `placeholder-page` is replaced by the real live page the design specifies (or confirmed); a `hardcoded-dynamic-value` is bound to its named data source per `dynamic-value-discovery`; and in every case a genuine user-driven Playwright test (real `page.click` / `page.fill`, real UI path, real backend) covers the fix. The fix team is spawned directly. After the fixes land, the three `interaction-reviewer` agents re-spawn and re-review until the converged map has zero gaps. These gaps surface through the `ui_interaction_review` review-gate evidence field.
- `visual-verification-team` (the `system-architect` Visual Gap Synthesis role) — spawned in Phase 5 (and by `/architect-team:visual-qa`). After the team's `visual-capture` agents render the LIVE app and its `visual-analyzer` agents produce per-screen gap lists, the synthesis clusters the gaps into root causes and writes one SR per gap cluster with `origin.kind: "visual-fidelity-drift"`. The `acceptance_criteria` mandate that the live app match the DESIGN_MAP Oracle for every screen in the cluster, re-verified by the team against the running app. A team `blocked` verdict (the live app would not run) or `incomplete` (the sweep did not cover every screen) escalates to the human, not a fix team — an unrunnable app or an incomplete sweep is a prerequisite defect, not a fix-team task.

### Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "The handoff is enough — the orchestrator can read it" | The handoff is markdown for humans. The SR is JSON for machine action. Without the SR, the orchestrator has nothing structured to spawn a team from. |
| "I'll write a brief SR and let the fix team figure out the details" | Then the fix team negotiates the spec instead of executing it, and the acceptance criteria drift. Write the full SR with concrete acceptance criteria — the originating test MUST be among them. |
| "I'll skip the SR if the fix is obvious" | "Obvious" fixes still need acceptance criteria, evidence, and a loop entry. Otherwise the master review (Phase 7) has nothing to walk. |
| "I'll wait for the orchestrator to ask before writing the SR" | The orchestrator picks up SRs from disk; it does not poll teammates for status. If you don't write the SR, the loop does not re-enter. |
| "The fix touches files outside my scope; I'll let the user spawn the next team" | That is the scope-out-of-bounds escalation — write the SR with `suggested_team` set to the owning team. The orchestrator routes; the user does not need to be in the loop unless the SR has a spec-ambiguity. |
| "I'll set priority to medium to be neutral" | RCA product-bugs blocking a documented user journey are critical or high. The priority drives queue ordering at Phase 2 spawn time. Be honest, not modest. |
