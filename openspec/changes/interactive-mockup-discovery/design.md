# Design: interactive-mockup-discovery (v2.1.0)

## Reference

Full WHY + WHAT + ACs in `proposal.md`. This file is the architectural deep-dive.

## Why this is a v2.1.0, not a v2.0.x patch or a v3.0.0

- **MINOR (additive)** — the new skill, new agent, new tool, new optional schema field, and the agent extensions are purely additive. v2.0.0 evidence files validate unchanged against v7 (the new `interactions_honored_review` field is optional).
- **No schema break** — schema v7 is unchanged in its required-field set; the new field is OPTIONAL.
- **No phase reordering** — the observer is dispatched FROM oracle-deriver at Phase 0.5 (a sub-agent, not a new pipeline phase). Phase −1D's bulk-verify already handles the user-confirmation surface; no new phase.

## Reuse Decision Log

### RD-1: NEW `skills/interactive-mockup-discovery/SKILL.md`

**Decision:** Build new.
**Justification:** The two-pass mechanism (observation + intent inference) is a distinct cross-cutting discipline. Adding it to `interaction-intuition` (the existing intuition skill) would conflate code-side intuition with oracle-side observation. Adding it to `verified-agent-output` would bloat that skill past tractability.

### RD-2: NEW `agents/interaction-observer.md`

**Decision:** Build new.
**Justification:** No existing agent has the headless-execution observation role. The closest analogs are `visual-capture` (renders and screenshots; does NOT simulate interactions) and `flow-executor` (runs Playwright flows against a live app; does NOT enumerate-and-simulate every interactive element). The observer is structurally distinct.

### RD-3: EXTEND `agents/oracle-deriver.md`

**Decision:** Extend.
**Justification:** Adding a 6th spec_shape follows the established pattern (the existing 5 spec_shape categories are documented in one section). Refactoring to a sub-spec architecture would be a v2.0.0-scale change; for v2.1.0 a single new value + dispatch contract is the minimal correct extension.

### RD-4: EXTEND `agents/interaction-intuiter.md`

**Decision:** Extend.
**Justification:** The intuiter already owns the per-element intuition + ambiguity-question surfacing pattern. Intent inference is a NEW input dimension (the oracle spec's interactions[]) processed through the SAME surfacing pattern (Phase −1D bulk-verify). Reusing the agent avoids duplicating the bulk-verify surface; the alternative (a separate agent) would re-implement the same protocol.

### RD-5: EXTEND `hooks/vao_tools.py`

**Decision:** Extend.
**Justification:** The 5 existing tools live in this module; the 6th is the same module-not-hook pattern.

### RD-6: EXTEND `hooks/review_evidence_schema.py`

**Decision:** Extend.
**Justification:** A new OPTIONAL field follows the established pattern for v7's dict-shape validators. The optional-ness is the v2.1.0 backward-compatibility guarantee — v2.0.0 evidence files continue to validate.

### RD-7: NEW `tests/test_vao_interactions_honored.py` + `tests/test_interactive_mockup_discovery.py`

**Decision:** Build new.
**Justification:** Each new layer needs structural tests. The synthetic fixture is the test-suite-enforced layer the v2.0.0 framework established.

### RD-8: NEW `tests/fixtures/vao/interactive-mockup-logout-misroute.json`

**Decision:** Build new.
**Justification:** Canonical synthetic fixture for the canonical failure shape. No existing fixture covers the mockup-lies pattern.

### RD-9: DEFERRED — live headless Chrome wiring

**Decision:** Deferred to v2.1.x.
**Justification:** The observer's contract is documented; the runtime sub-script that actually launches Playwright against an arbitrary user-supplied mockup is a follow-on. For v2.1.0 the observer reads pre-captured DOM-interaction snapshots so the plugin's own test suite stays stdlib-only. Live runtime wiring is straightforward (Playwright is already a plugin dep) but adds runtime risk that benefits from real-mockup feedback first.

### RD-10: DEFERRED — multi-mockup oracle synthesis

**Decision:** Deferred to v2.1.x+.
**Justification:** Same shape as v2.0.0's deferred multi-codebase oracle synthesis. One mockup per requirement is sufficient for the canonical case.

## Action_kind taxonomy — why these seven

Each value maps to a concrete DOM/runtime observable. The list is closed by design — adding an 8th value would imply a new observable shape that the observer cannot detect.

| Value | Observable | Example |
|---|---|---|
| `navigate` | URL changes (or History API call) | Clicking a button changes `window.location` |
| `open-drawer` | A `[role="complementary"]` / `[data-drawer]` / a sliding panel becomes visible | Hamburger button slides nav out |
| `open-modal` | A `[role="dialog"]` becomes visible | Confirm-delete button opens a modal |
| `submit` | A `<form>` submit event fires (and is not prevented-default into a fetch) | "Sign In" button submits a form |
| `input-text` | The element accepts focus and keyboard text | Email field accepts typing |
| `reveal` | An existing DOM node toggles `hidden` / `display: none` (without a drawer/modal role) | "Show password" toggle |
| `no-op` | No observable effect after simulation | A decorative button with no handler |

## Intent inference — the mismatch matrix

The intuiter's intent-inference pass uses a documented matrix of `semantic_label` patterns and the `action_kind` + `target_url_or_state` that "match" the expected intent. Mismatches become `interaction_intent_gap` entries.

The matrix lives in the `interaction-intuiter` agent body's new section (so the rules are auditable). Initial entries:

| Semantic pattern (case-insensitive) | Expected intent | Mismatch examples |
|---|---|---|
| `Logout` / `Log Out` / `Sign Out` | `navigate` to `/sign-in` / `/login` / `/logout` | Routes to `/dashboard`, no-op, opens a modal |
| `Sign In` / `Log In` / `Login` | `submit` form OR `navigate` to OAuth flow | No-op, routes to `/dashboard` without auth |
| `Save Draft` / `Save` | `submit` or `input-text` followed by an autosave fetch | Navigates away, opens unrelated modal |
| `Delete` / `Remove` | `open-modal` (confirmation) OR `submit` | Navigates without confirmation (destructive without guard) |
| `Cancel` / `Close` / `Dismiss` | `reveal` (close modal/drawer) OR `navigate` back | Submits, navigates forward |
| `Next` / `Continue` / `Proceed` | `navigate` forward OR `submit` step | No-op, navigates back |
| `Back` / `Previous` | `navigate` back | Navigates forward (or no-op) |

When the intuiter detects a mismatch, the `interaction_intent_gap` entry contains the trigger_selector, the semantic_label, the observed action_kind + target_url_or_state, the expected pattern, and a precise ambiguity question for the Phase −1D bulk-verify gate.

## Failure-mode mapping

| Failure | Caught at | How |
|---|---|---|
| Oracle is interactive mockup; source-walk misses behaviors | Pass 1 observation | interaction-observer enumerates + simulates every element |
| Mockup's Logout routes to /dashboard | Pass 2 intent inference | Mismatch matrix flags; Phase −1D bulk-verify surfaces; user confirms /sign-in |
| Built code routes Logout to /dashboard (treating mockup as binding) | Layer 3 verify-interactions-honored | Tool compares resolved_intent against built handler |
| Built code lacks an interactive element the mockup has | Layer 3 verify-every-element (existing v2.0.0) | Coverage check + the new interactions_honored_review catches the missing handler |
| Built code's drawer button doesn't actually open a drawer | Layer 3 verify-interactions-honored | Observed action_kind in oracle is `open-drawer`; tool asserts the built code's handler triggers a drawer |

## Costs accepted

1. **One additional agent dispatch per interactive-mockup oracle** — modest token cost when interactive mockups are in scope. Zero cost when no mockup is named (the spec_shape isn't triggered).
2. **Phase −1D bulk-verify gains items** — when intent gaps are detected, the user has more items to confirm. Mitigated by the existing single-list batched-prompt surface.
3. **The pre-captured-snapshot artifact** — the observer's stdlib-only test path reads a pre-captured JSON, which the live runtime would generate via Playwright. The test suite never executes a real browser, so the wiring shipped in v2.1.0 is contract-only; the runtime script is v2.1.x.

## Migration / backwards compatibility

- **v2.0.0 → v2.1.0:** ADDITIVE. No schema break.
- **Migration path.** Runs not in flight: no action needed. Runs in flight: the new optional field defaults to n/a unless the oracle spec carries interactions[].
- **Tests.** Existing 2255 tests pass. New ~45 tests assert the v2.1.0 structure.

## Version

**v2.1.0** — MINOR bump. Purely additive; backwards-compatible.
