# Proposal: interactive-mockup-discovery (v2.1.0)

## Why

The v2.0.0 VAO framework introduced `oracle-deriver` (Layer 1) producing a frozen oracle spec the rest of the pipeline measures against, and 5 verification tools (Layer 3) including `verify-rendered-parity` for rendered-DOM checks. The deriver's existing 5 `spec_shape` categories (`component-tree`, `design-map`, `api-contract`, `data-model`, `hybrid`) walk SOURCE artifacts deterministically — they can name the elements that exist but they cannot record what those elements actually DO.

This gap is critical when the oracle artifact is an **interactive HTML mockup** — the artifact-style mockups Claude Code produces, where buttons click, drawers slide out, modals open, inputs accept text, fetches fire. A static walk of such a mockup captures the DOM structure but misses every observable behavior: which buttons navigate where, which open drawers, which have JS event listeners that no-op, which trigger fetch calls. Worse, the v1.4 scope-discipline assumed `match the oracle` meant matching the structure; matching an INTERACTIVE oracle requires matching its observable interactions too.

A second gap: **mockups lie**. A "Logout" button in a Claude Code mockup may have been authored to route to `/dashboard` (the mockup author wasn't building real auth; they wanted the demo to feel continuous). The agent that walks this mockup and treats its literal behavior as binding will faithfully reproduce a broken Logout. The framework needs to detect semantic-vs-observed-effect mismatches and surface them as ambiguities the user resolves BEFORE Phase 2 implementation.

### The two failure modes this proposal closes

| Failure | What goes wrong | Where it should be caught |
|---|---|---|
| **Interaction blindness** | Source-walk oracle spec names a "Save Draft" button. Built work renders a "Save Draft" button. Source-tree audit (`verify-oracle-match`) says matched. But the oracle's button opens a confirmation drawer + autosaves to local storage; the built button does neither. | New Layer 3 tool `verify-interactions-honored` checks every recorded interactions[] entry against the built code's wiring. |
| **Mockup lies** | Mockup's "Logout" button routes to `/dashboard` (or is a no-op). Agent treats observed behavior as binding. Built work faithfully reproduces broken Logout. | Pass 2 intent inference flags semantic_label ↔ observed_effect mismatches as `interaction_intent_gap` ambiguities at the existing Phase −1D bulk-verify gate. User confirms canonical intent; resolved intent (NOT mockup's literal behavior) becomes the binding contract. |

The shape of the fix matches v2.0.0's pattern: the `oracle-deriver` extends to recognize a 6th `spec_shape` (`interactive-mockup`), a new `interaction-observer` agent does the headless observation pass, the existing `interaction-intuiter` agent (already responsible for the Phase −1D bulk-verify dimension) gains an intent-inference mode, and a new Layer 3 tool verifies the resolved intent is honored in the built work.

## What changes

### A new spec_shape on oracle-deriver: `interactive-mockup`

When the oracle artifact is an HTML file (or a directory containing an `index.html` + assets) AND the artifact carries `<script>` tags / event handlers / inline JS, the oracle-deriver classifies `spec_shape: interactive-mockup` and dispatches the new `interaction-observer` agent BEFORE writing its frozen spec. The observer's output (the `interactions[]` array) is folded into the spec.

### Pass 1 — Observation (the new `interaction-observer` agent)

A new opus agent dispatched by oracle-deriver when `spec_shape: interactive-mockup` triggers. The observer:

1. **Runs the mockup** in headless Chrome via Playwright (already a plugin dependency for `playwright-user-flows`). For stdlib-only tests, the observer reads a pre-captured DOM-interaction-snapshot JSON from disk.
2. **Enumerates every interactive element** — every `button`, `a[href]`, `input`, `textarea`, `select`, `[role="button"]`, `[role="link"]`, `[onclick]`, `[data-action]`.
3. **Simulates each interaction** — click for buttons/links/role=button, focus + type for inputs, change for selects.
4. **Records the observed effect** — URL navigation, DOM-tree change (drawer slides in: a new `[data-component]` parent path appears), modal open (a new `[role="dialog"]` appears), focus moves, fetch fired (intercepted via Playwright's request interception), nothing observable (no-op).

The output is an `interactions[]` array on the frozen oracle spec:

```json
{
  "interactions": [
    {
      "interaction_id": "int-001",
      "trigger_selector": "button[data-testid='logout-btn']",
      "semantic_label": "Logout",
      "action_kind": "navigate",
      "observed_effect": "url-changed",
      "target_url_or_state": "/dashboard",
      "evidence_path": ".architect-team/oracle-spec/<change>/interaction-evidence/int-001.json"
    }
  ]
}
```

`action_kind` values: `navigate` / `open-drawer` / `open-modal` / `submit` / `input-text` / `reveal` / `no-op`.

### Pass 2 — Intent inference (extension to existing `interaction-intuiter`)

The existing `interaction-intuiter` agent (which already produces `INTERACTION_INTUITION_MAP.md` for code-side intuition) gains a new INTENT-INFERENCE mode. When the oracle spec's `interactions[]` is populated, the intuiter:

1. Walks every entry.
2. Compares `semantic_label` against `observed_effect` using a documented mismatch matrix (e.g., `Logout` + `navigate to /dashboard` → MISMATCH; `Logout` + `navigate to /sign-in` → MATCH; `Logout` + `no-op` → MISMATCH).
3. For every mismatch, emits an `interaction_intent_gap` entry to be surfaced at the existing Phase −1D bulk-verify gate (which already takes a user-confirmation list of one-line ambiguities).
4. The user confirms canonical intent ("Logout SHOULD route to /sign-in"). The `resolved_intent` field is written back to the interactions[] entry.

### Layer 3 tool: `verify-interactions-honored`

A new 6th Layer 3 tool extending `hooks/vao_tools.py`. Input: built components + frozen oracle spec. For every interactions[] entry whose `resolved_intent` is populated (the user confirmed an intent gap) OR whose `action_kind` is non-trivial (not `no-op`), asserts the built code's handler matches the resolved intent. Output verdict JSON matching the other tools' shape.

### Schema v7 — optional `interactions_honored_review` field

`hooks/review_evidence_schema.py` schema v7 gains a new OPTIONAL field `interactions_honored_review`. The field is OPTIONAL because not every requirement names an interactive-mockup oracle; the field is REQUIRED only when the run's oracle spec carries an `interactions[]` array. The validation logic checks the same pass/n/a/fail / dict-shape contract as the other v7 fields.

### Synthetic fixture: `interactive-mockup-logout-misroute.json`

Reproducing the canonical case: a mockup whose "Logout" button observes a navigate-to-/dashboard, the oracle spec captures it, the intent inference flags the mismatch, the user confirms /sign-in as the canonical intent, and `verify-interactions-honored` asserts the built code routes to /sign-in (not /dashboard).

## QA Guidance

### Acceptance Criteria

- [AC-1] `skills/interactive-mockup-discovery/SKILL.md` exists as the canonical home documenting the two-pass mechanism (observation + intent inference), the interactions[] schema, the action_kind taxonomy (7 values), the interaction_intent_gap surfacing protocol, the verify-interactions-honored verdict contract, and the relationship to oracle-deriver + interaction-intuiter + Phase −1D bulk-verify.
- [AC-2] `agents/interaction-observer.md` exists with the right frontmatter (name, description, model: opus, tools allowlist including Bash + Read + Write + Glob + Grep + LS + TodoWrite, color), the uniform `## Operating context` + `## Forbidden git operations` + `## Checkpoint discipline` sections, and a body documenting the 4-step observe protocol (run mockup → enumerate elements → simulate interactions → record observed effects), the interactions[] schema it writes, and the bounded Write to .architect-team/oracle-spec/<change>/interaction-evidence/.
- [AC-3] `agents/oracle-deriver.md` extends to name `interactive-mockup` as a 6th `spec_shape` value and documents the dispatch contract for `interaction-observer`.
- [AC-4] `agents/interaction-intuiter.md` gains a documented INTENT-INFERENCE mode that reads the oracle spec's `interactions[]`, compares semantic_label vs observed_effect, and emits `interaction_intent_gap` entries for the Phase −1D bulk-verify gate.
- [AC-5] `hooks/vao_tools.py` ships a 6th function `verify_interactions_honored(built_components, oracle_spec) -> dict` AND a `verify-interactions-honored` CLI subcommand. Output JSON: `{tool, matched: bool, gaps: [...], honored_count: int, total_count: int, verdict_at}`. Deterministic / bit-stable.
- [AC-6] `hooks/review_evidence_schema.py` schema v7 gains optional `interactions_honored_review` field. Required only when the run's oracle spec carries a non-empty `interactions[]` array; n/a otherwise.
- [AC-7] `tests/fixtures/vao/interactive-mockup-logout-misroute.json` exists with the canonical case (Logout → /dashboard observed, intent inference flags, resolved_intent: /sign-in, verify-interactions-honored verdict shows gap on a built tree that still routes to /dashboard).
- [AC-8] `tests/test_vao_interactions_honored.py` (≥ 20 tests) pinning the 6th tool's positive + negative + determinism contract, the synthetic fixture round-trip, the schema v7 optional-field semantics.
- [AC-9] `tests/test_interactive_mockup_discovery.py` (≥ 20 tests) pinning the skill body assertions (canonical home, 7 action_kind values, two-pass documentation), the agent frontmatter assertions, the oracle-deriver / interaction-intuiter extensions.
- [AC-10] `tests/test_skills.py` `EXPECTED_SKILLS` adds `interactive-mockup-discovery`. `tests/test_agents.py` `EXPECTED_AGENTS` adds `interaction-observer`.
- [AC-11] Version `2.1.0` consistent across plugin.json, marketplace.json, CHANGELOG, README banner, CLAUDE.md.
- [AC-12] All existing tests still pass + new tests. Target: 2255 → ~2300 (+ ~45 new).

### Out of Scope

- **Live Playwright execution against arbitrary user-supplied mockups** — v2.1.0 ships the agent contract + the verify-interactions-honored tool + the synthetic-fixture round-trip. Wiring the observer to an actual headless Chrome browser instance is a follow-on (v2.1.x) — the agent body documents the contract; a future runtime sub-script will execute it. For v2.1.0 the observer reads pre-captured DOM-interaction snapshots so the tests are stdlib-only.
- **Full Phase 0.5 inline-dispatch wiring in the 3 pipeline SKILL.md bodies** — same deferral as v2.0.0; the canonical home documents the dispatch contract.
- **Multi-mockup oracle synthesis** — one mockup per requirement; multi-mockup is v2.1.x+.

## Impact

- **New skill:** `skills/interactive-mockup-discovery/SKILL.md`.
- **New agent:** `agents/interaction-observer.md`.
- **Modified agents:** `agents/oracle-deriver.md` (adds `interactive-mockup` spec_shape), `agents/interaction-intuiter.md` (adds INTENT-INFERENCE mode).
- **Modified hooks:** `hooks/vao_tools.py` (+ `verify_interactions_honored`), `hooks/review_evidence_schema.py` (+ optional `interactions_honored_review`).
- **New tests:** `tests/test_vao_interactions_honored.py`, `tests/test_interactive_mockup_discovery.py`.
- **New fixture:** `tests/fixtures/vao/interactive-mockup-logout-misroute.json`.
- **Modified:** `tests/test_skills.py`, `tests/test_agents.py`, CHANGELOG.md, CLAUDE.md, README.md, plugin.json, marketplace.json.
- **Test count:** 2255 → ~2300.
- **Version:** v2.0.0 → **v2.1.0** (MINOR — additive; schema v7 field is OPTIONAL so v2.0.0 evidence files still validate).
- **Backwards-compatible:** YES. Schema v7 field is optional; the new tool is additive; the new skill is additive; new agent is additive; existing agent extensions are additive sections.
