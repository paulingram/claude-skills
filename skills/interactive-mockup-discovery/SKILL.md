---
name: interactive-mockup-discovery
description: Two-pass discovery of interactive HTML mockups as oracle artifacts. Pass 1 (observation) runs the mockup in headless Chrome and records every interactive element's observed behavior; Pass 2 (intent inference) flags semantic-vs-observed mismatches (e.g., "Logout" button routing to /dashboard) and surfaces them at the existing Phase −1D bulk-verify gate so the user-resolved intent — not the mockup's literal behavior — becomes the binding contract. Adds a 6th spec_shape to oracle-deriver, a new interaction-observer agent, an INTENT-INFERENCE mode to interaction-intuiter, a new Layer 3 tool (verify-interactions-honored), and an OPTIONAL schema v7 field.
---

# interactive-mockup-discovery — v2.1.0 extension to the VAO framework

This skill closes two gaps the v2.0.0 oracle-deriver had:

1. **Interaction blindness on interactive oracles.** The existing 5 spec_shape categories (`component-tree`, `design-map`, `api-contract`, `data-model`, `hybrid`) all walk SOURCE artifacts deterministically. When the oracle artifact is an **interactive HTML mockup** — the artifact-style mockups Claude Code produces — a static source walk captures the DOM structure but misses every observable behavior: which buttons navigate where, which open drawers, which have JS handlers that silently no-op.

2. **Mockup lies.** Claude Code mockups frequently include buttons whose authored behavior makes no semantic sense — a "Logout" button that routes to `/dashboard` (the mockup author wasn't building real auth; they wanted the demo to feel continuous), or a "Save Draft" button with no handler at all. An agent that treats the mockup's literal behavior as binding will faithfully reproduce a broken Logout. The framework needs to detect semantic-vs-observed mismatches and surface them as ambiguities for user resolution BEFORE Phase 2 implementation.

## The two passes

### Pass 1 — Observation (the `interaction-observer` agent)

When `oracle-deriver` classifies an oracle artifact as `spec_shape: interactive-mockup`, it dispatches the new `interaction-observer` agent BEFORE writing its frozen spec. The observer:

1. **Runs the mockup** in headless Chrome via Playwright. (For the v2.1.0 plugin self-test suite — and any environment where Playwright isn't available — the observer reads a pre-captured DOM-interaction-snapshot JSON from disk. Live-execution wiring is v2.1.x.)
2. **Enumerates every interactive element** — every `button`, `a[href]`, `input`, `textarea`, `select`, `[role="button"]`, `[role="link"]`, `[onclick]`, `[data-action]`.
3. **Simulates each interaction** — `click` for buttons/links/role=button; `focus + type` for inputs; `change` for selects; `mouseover` for hover-revealed elements.
4. **Records the observed effect** into a structured `interactions[]` array on the frozen oracle spec.

Each interactions[] entry has the shape:

```json
{
  "interaction_id": "int-001",
  "trigger_selector": "button[data-testid='logout-btn']",
  "semantic_label": "Logout",
  "action_kind": "navigate",
  "observed_effect": "url-changed",
  "target_url_or_state": "/dashboard",
  "evidence_path": ".architect-team/oracle-spec/<change>/interaction-evidence/int-001.json"
}
```

#### The seven action_kind values

The vocabulary is closed by design. Each value maps to a concrete DOM/runtime observable:

| Value | Observable | Example |
|---|---|---|
| `navigate` | URL changes (or History API push) | Clicking changes `window.location` |
| `open-drawer` | A `[role="complementary"]` / `[data-drawer]` slides into view | Hamburger button slides nav out |
| `open-modal` | A `[role="dialog"]` becomes visible | Confirm-delete opens a modal |
| `submit` | A `<form>` submit event fires | "Sign In" submits a form |
| `input-text` | The element accepts focus and keyboard text | Email field accepts typing |
| `reveal` | An existing DOM node toggles `hidden` / `display` (no drawer/modal role) | "Show password" toggle |
| `no-op` | No observable effect after simulation | A decorative button with no handler |

If an element exhibits multiple observable effects (a button both submits AND opens a confirmation modal), the observer records the PRIMARY effect (the first runtime change after the interaction) as `action_kind` and notes the secondary effects in the `evidence_path` JSON.

### Pass 2 — Intent inference (extension to `interaction-intuiter`)

The existing `interaction-intuiter` agent already owns the per-element-with-ambiguity-question surfacing pattern that drives Phase −1D bulk-verify. When the oracle spec's `interactions[]` is populated, the intuiter runs an additional **INTENT-INFERENCE** pass:

1. Walks every interactions[] entry.
2. Compares the `semantic_label` against the `observed_effect` + `target_url_or_state` using a documented **mismatch matrix** (lives in the `agents/interaction-intuiter.md` body, so the rules are auditable).
3. For every mismatch, emits an `interaction_intent_gap` entry.

The mismatch matrix (initial entries — extensible as failure shapes emerge):

| Semantic pattern (case-insensitive) | Expected intent | Mismatch examples |
|---|---|---|
| `Logout` / `Log Out` / `Sign Out` | `navigate` to `/sign-in` / `/login` / `/logout` | Routes to `/dashboard`, no-op, opens unrelated modal |
| `Sign In` / `Log In` / `Login` | `submit` form OR `navigate` to OAuth flow | No-op, routes to `/dashboard` without auth |
| `Save Draft` / `Save` | `submit` or `input-text` + autosave fetch | Navigates away, opens unrelated modal |
| `Delete` / `Remove` | `open-modal` (confirmation) OR `submit` | Navigates without confirmation (destructive without guard) |
| `Cancel` / `Close` / `Dismiss` | `reveal` (close drawer/modal) OR `navigate` back | Submits, navigates forward |
| `Next` / `Continue` / `Proceed` | `navigate` forward OR `submit` step | No-op, navigates back |
| `Back` / `Previous` | `navigate` back | Navigates forward (or no-op) |

The `interaction_intent_gap` entry shape:

```json
{
  "gap_id": "iig-001",
  "interaction_id": "int-001",
  "trigger_selector": "button[data-testid='logout-btn']",
  "semantic_label": "Logout",
  "observed_action_kind": "navigate",
  "observed_target": "/dashboard",
  "expected_pattern": "navigate to /sign-in / /login / /logout",
  "ambiguity_question": "The Logout button in the mockup routes to /dashboard. Should the built work route to /sign-in (canonical logout), /login, or honor the mockup's literal /dashboard?",
  "user_verdict": null,
  "resolved_intent": null
}
```

## Phase −1D bulk-verify integration

`interaction_intent_gap` entries flow through the EXISTING Phase −1D bulk-verify gate alongside the existing `confidence ∈ {low, unknown, medium-with-ambiguity}` intuition entries. The user sees ONE unified numbered list; the same `all correct` / `<comma-separated numbers>` / `all incorrect` response format applies; the drill-down round uses `AskUserQuestion` with the candidate intents as options.

After the user resolves every intent gap:
- `user_verdict` is set to `confirmed | corrected | confirmed-stub | deferred`.
- `resolved_intent` is set to the canonical action_kind + target_url_or_state (e.g., `navigate:/sign-in`).
- The intuiter writes `resolved_intent` BACK to the corresponding interactions[] entry on the frozen oracle spec.
- The orchestrator flips the spec's `_human_review_required` to `false`.

## Layer 3 verification: `verify-interactions-honored`

`hooks/vao_tools.py` exposes a 6th deterministic tool. Inputs:

- `built_components` — list of `{path, handlers: [{trigger_selector, action_kind, target_url_or_state}]}` dicts.
- `oracle_spec` — the frozen spec carrying `interactions[]` (with `resolved_intent` populated for any user-resolved gap).

Output verdict JSON:

```json
{
  "tool": "verify-interactions-honored",
  "matched": true|false,
  "gaps": [
    {
      "trigger_selector": "button[data-testid='logout-btn']",
      "expected_action_kind": "navigate",
      "expected_target": "/sign-in",
      "actual_action_kind": "navigate",
      "actual_target": "/dashboard",
      "severity": "intent-violated"
    }
  ],
  "honored_count": 12,
  "total_count": 13,
  "verdict_at": "<ISO 8601 UTC>"
}
```

The tool walks every interactions[] entry. For each, it determines the **target intent**:
- If `resolved_intent` is populated → that's the target (user-confirmed canonical intent).
- Else if `action_kind != "no-op"` → the observed action is the target (the mockup's literal behavior is binding).
- Else → skip (no-op elements are not verified — the mockup intentionally has no handler).

Then for each target, it asserts a matching `built_components[*].handlers[]` entry exists whose `action_kind` + `target_url_or_state` match. Mismatches become `gaps[]` entries with one of three severities:
- `intent-violated` — the resolved intent says X, the built code does Y
- `missing-handler` — the oracle says this trigger has an effect, the built code has no handler at all
- `action-kind-mismatch` — the action_kind differs (oracle says open-modal, built code navigates)

The output is bit-stable (sorted keys, indent=2) — the determinism contract from v2.0.0 applies.

## Schema v7: optional `interactions_honored_review` field

`hooks/review_evidence_schema.py` schema v7 gains an OPTIONAL field `interactions_honored_review`. The field is REQUIRED only when the run's oracle spec carries a non-empty `interactions[]` array; n/a in all other cases.

The validator accepts the same shapes as the other v7 fields:
- String: `pass` / `n/a` / `fail`
- Dict: `{verdict, verdict_path}` citing the on-disk tool verdict.

v2.0.0 evidence files (which lack this field) continue to validate — the field's optionality is the v2.1.0 backward-compatibility guarantee.

## How this composes with v2.0.0

| v2.0.0 layer | What it caught | v2.1.0 changes |
|---|---|---|
| Layer 1 (`oracle-deriver`) | Frozen structural spec for 5 spec_shape categories | EXTENDED — 6th spec_shape `interactive-mockup` dispatches `interaction-observer` |
| Layer 2 (`adversarial-reviewer`) | 5 role-paired shape audits | Unchanged — the existing `oracle-divergence-hunter` shape now also covers interactions[] divergence via verify-interactions-honored |
| Layer 3 (`vao_tools.py`) | 5 deterministic verification tools | EXTENDED — 6th tool `verify-interactions-honored` |
| Layer 5 (structural tests) | Pytest suite asserting each layer is wired | EXTENDED — ~45 new tests asserting v2.1.0's wiring |
| Layer 6 (skill-invocation audit) | Stop-hook catches "applied methodology by hand" | Unchanged |
| Schema v7 | 5 new required VAO fields | EXTENDED — 1 new OPTIONAL field; required fields unchanged |

## Failure-mode mapping (the audit trail)

| Failure | Caught at | How |
|---|---|---|
| Oracle is interactive mockup; source-walk misses observable behaviors | Pass 1 observation | interaction-observer enumerates + simulates every interactive element |
| Mockup's "Logout" routes to /dashboard | Pass 2 intent inference | Mismatch matrix flags; Phase −1D bulk-verify surfaces; user confirms /sign-in |
| Built code treats mockup's broken Logout as binding | Layer 3 verify-interactions-honored | Tool compares resolved_intent against built handler; gap with severity `intent-violated` |
| Built code lacks an interactive element the mockup has | Layer 3 verify-every-element (existing) + verify-interactions-honored | Coverage gap + a `missing-handler` severity entry |
| Built code's "drawer" button actually navigates instead | Layer 3 verify-interactions-honored | action_kind mismatch — observed `open-drawer` vs built `navigate` |

## Cross-references

- `agents/oracle-deriver.md` — Phase 0.5 agent; extended for `interactive-mockup` spec_shape.
- `agents/interaction-observer.md` — NEW Pass 1 agent.
- `agents/interaction-intuiter.md` — Phase −1D intuiter; extended for INTENT-INFERENCE mode.
- `skills/interaction-intuition/SKILL.md` — the intuiter's existing home; this skill cross-references but does NOT duplicate the bulk-verify protocol.
- `skills/verified-agent-output/SKILL.md` — v2.0.0 canonical home of the 6 VAO layers; this skill is the v2.1.0 extension to Layer 1 + Layer 3.
- `hooks/vao_tools.py` — module hosting the 6 Layer-3 verification tools.
- `hooks/review_evidence_schema.py` — schema v7 with the new OPTIONAL field.
- `tests/test_vao_interactions_honored.py` — structural tests for the 6th tool.
- `tests/test_interactive_mockup_discovery.py` — structural tests for the skill body + agent frontmatter + extensions.
- `tests/fixtures/vao/interactive-mockup-logout-misroute.json` — the canonical synthetic fixture.

## Operating rules (non-negotiable)

- A change to the two-pass mechanism edits this skill ONCE. The agent bodies' extension sections cross-reference but do not duplicate.
- The action_kind vocabulary is closed at seven values. Adding an 8th value MUST extend this skill and the schema; ad-hoc values are forbidden.
- The mismatch matrix lives in the `interaction-intuiter` agent body (so the rules are auditable from a single source). Edits to the matrix happen there.
- The `verify-interactions-honored` verdict file is the source of truth at the hook layer — agent prose claiming "interactions honored" while citing a verdict with non-empty gaps is hook-blocked, same discipline as the other Layer 3 tools.
- The schema v7 field `interactions_honored_review` is OPTIONAL — v2.0.0 evidence files MUST continue to validate. Making it required would be a v3.0.0-scale break.
