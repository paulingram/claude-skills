# Multi-persona path-coverage discipline (v2.11.0)

Features that serve more than one user persona (a client receiving an email invite; an attorney monitoring a dashboard; a title-agency assistant entering intake data on behalf of a client; a family member completing their own intake; etc.) MUST be tested from EVERY persona's path before any fix on the feature is claimed complete. Testing one persona's golden path and declaring the fix shipped — when the OTHER personas' views still don't render, still don't persist, or still don't sync — is the failure mode this discipline closes.

**Failure shape** (verbatim heirship case in CHANGELOG v2.11.0): the agent claimed a fix on a multi-persona matter-intake feature but its verification covered exactly ONE persona's entry point and stopped. The user found four distinct breakages — client email-link data never showed on the **title side** / title agency view; **two matters were created** because the Create-Matter button had no loading state and **looked frozen** (double-submit); the **attorney view** was blank and didn't show all the roles; and title-agency intake (someone assisting the client) saved nothing — reproaching *"this is unacceptable that you would claim a fix and fail to test it"* (the agent must **claim a fix and fail to test** NO feature; test every persona's path). The other three personas were silently broken and the run was claimed complete.

### The rule (non-negotiable)

Every feature MUST carry a `persona-inventory.json` artifact at `<workspace>/.architect-team/persona-inventory/<feature-slug>.json` documenting EVERY user persona the feature serves. The artifact is produced at intake (Phase −1 or `bug-fix-pipeline` Phase B−1) and frozen before any implementer dispatch. Schema:

```json
{
  "feature_slug": "matter-intake-multi-persona",
  "personas": [
    {
      "persona_id": "client-email-link",
      "entry_point": "https://<dev-url>/invite/<token>",
      "expected_views": ["intake-form", "submission-confirmation"],
      "expected_data_visibility": ["matter.client_email", "matter.client_name"],
      "cross_persona_dependencies": [
        {"writes_data": "matter.client_email", "must_appear_in_persona": "title-agency-dashboard"},
        {"writes_data": "matter.client_name", "must_appear_in_persona": "attorney-dashboard"}
      ]
    },
    {
      "persona_id": "title-agency-intake",
      "entry_point": "https://<dev-url>/ta/new",
      "expected_views": ["matter-form", "client-detail-panel"],
      "expected_data_visibility": ["matter.client_email", "matter.attorney_assigned"],
      "cross_persona_dependencies": []
    },
    {
      "persona_id": "attorney-dashboard",
      "entry_point": "https://<dev-url>/atty/matters",
      "expected_views": ["matter-list", "matter-detail", "role-assignments"],
      "expected_data_visibility": ["matter.client_name", "matter.roles[]"],
      "cross_persona_dependencies": []
    },
    {
      "persona_id": "family-member-intake",
      "entry_point": "https://<dev-url>/family/invite/<token>",
      "expected_views": ["family-form", "submission-confirmation"],
      "expected_data_visibility": ["matter.family_members[]"],
      "cross_persona_dependencies": [
        {"writes_data": "matter.family_members[]", "must_appear_in_persona": "attorney-dashboard"},
        {"writes_data": "matter.family_members[]", "must_appear_in_persona": "title-agency-dashboard"}
      ]
    }
  ]
}
```

The implementer's slice-end report and the qa-replayer's post-fix verification MUST cite at least one Playwright test per persona that:

1. **Opens the persona's `entry_point` URL.** Not a localhost route, not a unit test, not a mocked render — the live dev URL.
2. **Executes the persona's user-flow against the live backend.** Per the v2.6.0 live-data wiring discipline.
3. **Asserts every entry in `expected_data_visibility[]` appears in the rendered DOM.** Per the v2.6.0 `live-response-not-rendered` rule.
4. **Asserts every `cross_persona_dependencies[]` entry holds.** A test creates data as persona A, then opens persona B's `entry_point`, then asserts the data appears.
5. **Asserts double-submit idempotency on every form-submit interaction.** Per the new v2.11.0 `double-submit-not-tested` severity.
6. **Asserts a loading-state UI surfaces on every backend-call interaction.** Per the new v2.11.0 `loading-state-not-asserted` severity.

### 4 named severities

| Severity | Trigger |
|---|---|
| `persona-path-not-tested` | `persona_inventory.personas[]` names a persona AND no `playwright_test_runs[]` entry has matching `persona_id` |
| `cross-persona-sync-not-asserted` | Persona A has a `cross_persona_dependencies[]` entry naming persona B AND no `playwright_test_runs[]` entry creates data as A and asserts it in B's view |
| `double-submit-not-tested` | A persona's flow has a submit-shaped interaction AND no `playwright_test_runs[].clicks_with_timing[]` shows two clicks within `_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS` (500ms) with a final-record-count assertion of 1 |
| `loading-state-not-asserted` | A persona's flow has a backend-call interaction AND no `playwright_test_runs[].ui_states_observed[]` contains a `_LOADING_STATE_UI_HINTS` value (`loading`, `spinner`, `skeleton`, `progress`, `wait`, `pending`, …) within 200ms of the click |

### Canonical UI hints for loading-state detection

| Hint class | Patterns |
|---|---|
| **Spinner** | `spinner`, `Loading...`, `Working...`, `Please wait`, `progress-circular`, `aria-busy="true"` |
| **Skeleton** | `skeleton`, `placeholder-shimmer`, `loading-skeleton`, `<Skeleton`, `bg-shimmer` |
| **Progress bar** | `progress-bar`, `<progress>`, `role="progressbar"`, `progress-linear` |
| **Disabled-button-with-spinner** | button `disabled` attribute set + inline spinner SVG / spinner class |
| **Status text** | `Submitting...`, `Creating matter...`, `Saving...`, `Processing...` |

### Why existing layers don't catch this

| Existing layer | What it catches | Why it missed multi-persona |
|---|---|---|
| `playwright-user-flows` | A flow is genuine (real click, real backend) | The flow IS genuine — for the ONE persona the agent tested |
| `interaction-completeness` | Every interactive element is wired | The elements ARE wired — for the ONE persona's view |
| `verify_live_data_wiring` (v2.6.0) | Mock state survived production code | Mock state didn't survive — but only one persona's path was checked |
| `dev-api-integration-testing` | Tests exercise real backend | They do — for one persona's HTTP requests |
| `interaction-completeness` 3-reviewer swarm | 3 reviewers converge on element classification | They classify for ONE persona's view, not across personas |

v2.11.0 is the first layer that asks: **"given this feature serves N personas, did the verification exercise EVERY persona's entry point AND assert cross-persona data sync?"**

### Cross-references

- `hooks/vao_tools.py::verify_per_persona_path_coverage` — the 12th Layer 3 tool.
- `hooks/vao_tools.py::_LOADING_STATE_UI_HINTS` + `_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS` — the canonical detection constants.
- `agents/qa-replayer.md` `## Multi-persona path-coverage discipline (v2.11.0)` — post-fix per-persona re-replay gate.
- `agents/frontend.md` `## Multi-persona path-coverage discipline (v2.11.0)` — implementer's per-persona test mandate.
- `agents/interaction-reviewer.md` `## Multi-persona path-coverage discipline (v2.11.0)` — 3-reviewer swarm extension.
- `agents/bug-replicator.md` `## Multi-persona path-coverage discipline (v2.11.0)` — cross-persona repro test mandate.
- `tests/fixtures/vao/multi-persona-path-coverage-gap.json` — verbatim heirship canonical case (4 personas; only 1 tested; cross-persona sync broken; double-submit caused duplicate matters).
- `tests/test_vao_per_persona_path_coverage.py` + `tests/test_multi_persona_path_coverage_discipline.py` — structural tests.
- Companion to v2.6.0 live-data wiring (catches mock-state survival on the one tested path) + v2.7.0 pattern propagation (catches partial sweep within ONE persona's path) — different axis, same root principle: ship the COMPLETE verification the feature requires, not the persona-narrow slice of it.
