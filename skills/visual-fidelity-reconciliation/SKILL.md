---
name: visual-fidelity-reconciliation
description: Use when QA-reviewing frontend work post-development — every commit that touches .tsx / .jsx / .vue / .svelte / .astro / .css / .scss / .less / .module.css / Tailwind config / theme tokens / Storybook stories / asset files in a codebase that has a DESIGN_MAP.md MUST produce a reconciliation report verifying every (screen, element, state) tuple in scope matches the design contract PERFECTLY. Also use in Phase 5 integration to regression-check that downstream changes have not drifted the visual contract. Triggers — any frontend file change + DESIGN_MAP.md exists, OR an on-demand audit via the /architect-team:visual-qa command, OR the Phase 3 review-gate hook rejects an evidence file whose visual_fidelity_review value is fail. Mandates zero-tolerance defaults (0px / exact color / exact font / exact spacing / exact shadow), exhaustive per-state walks (default / hover / focus / active / disabled / loading / error / empty + every responsive breakpoint), fix-to-spec by default when drift is found (DESIGN_MAP.md is the agreed contract; AI fixes the implementation to match), and escalation reserved for four narrow exceptions (out-of-scope file, implementation-has-element-not-in-spec, spec-ambiguity, cascade-blast-radius).
---

# Visual-Fidelity Reconciliation — Pixel-Perfect QA Against the Design Contract

"It looks fine" is a judgment call. This skill makes the look-and-feel of every shipped frontend change auditable against `DESIGN_MAP.md`. Every (screen, element, state) tuple in scope gets a verdict — **perfect**, **drift**, or **gap** — with evidence at every node. Drift is never patched inline; it is escalated to the architect-team for a fix routed through the standard dev loops with proper spec attribution.

This skill is the dual of `design-fidelity-mapping`:
- `design-fidelity-mapping` **captures** the contract (`DESIGN_MAP.md`).
- `visual-fidelity-reconciliation` **verifies** the implementation honors the contract.

Without this skill, design drift accumulates one PR at a time — each one too small to flag, the cumulative effect too large to ignore.

Three disciplines:

1. **Zero-tolerance defaults.** Bounding boxes match to the pixel. Colors match to the exact computed value. Typography matches family-AND-weight-AND-size-AND-line-height. Border radii, shadows, padding, and margins match exactly. Tolerances are explicit per-element overrides with recorded rationale — never silent global slop.
2. **Exhaustive state walks.** Every state listed in DESIGN_MAP.md OR implied by the component code gets verified: default, hover, focus, active, disabled, loading, error, empty, plus every responsive breakpoint declared in DESIGN_MAP.md's `viewports_responsive` frontmatter. Missing a state is a gap.
3. **Fix drift to align to the spec; escalate only for genuine ambiguity or scope barriers.** `DESIGN_MAP.md` is the agreed contract. When reconciliation finds drift, the default action is to CHANGE THE IMPLEMENTATION to match the spec, re-run reconciliation, and verify `perfect`. Escalation is the exception — reserved for cases where (a) the fix requires editing files outside the agent's scope, (b) the spec itself is ambiguous / internally inconsistent / references tokens that don't exist, or (c) the implementation has an element NOT in the spec and the architect-team must decide whether to add to spec or remove from implementation. Alerting the user without fixing is a process failure: the discipline converges to the spec, autonomously, every time.

## When to run

- **Phase 3 — Team review gate (automatic).** When a frontend teammate marks any task complete and `files_changed` includes a frontend file AND DESIGN_MAP.md exists for the touched codebase, the teammate MUST produce a reconciliation report covering every (screen, element, state) tuple their change touched. The review-gate hook enforces this via the `visual_fidelity_review` evidence field (must be `"pass"` or `"n/a"`; `"fail"` blocks completion).
- **Phase 5 — Cross-layer integration (automatic).** The integration agent runs reconciliation across ALL screens (not just changed ones) as a regression check that upstream / sibling changes have not drifted the contract.
- **On-demand audit via `/architect-team:visual-qa` (manual).** Operator invokes the command at any point; the command refreshes DESIGN_MAP.md if stale, then runs reconciliation across all designed screens.

## Phase A — Scope identification

For Phase 3 (per-team), the scope is the set of (screen, element, state) tuples touched by the teammate's diff:

1. Read `files_changed` from the review evidence.
2. For each changed file, identify which screens / components it affects:
   - Component file (`Button.tsx`) → every screen that imports it (`grep -r "from.*Button" --include="*.tsx" --include="*.jsx"`).
   - Token file (`tailwind.config.{js,ts}` / `theme.ts` / `tokens.json` / `styles/tokens.css`) → every screen (it cascades).
   - Asset file (`logo.svg`) → every screen referencing it (`grep -r "logo.svg"`).
   - Stylesheet (`globals.css` / `app.css`) → every screen that loads it (cascades).
   - Storybook story (`*.stories.tsx`) → the component the story covers.
3. For each affected screen, the relevant rows from DESIGN_MAP.md's `## Per-Screen Visual Specs` table become the in-scope reconciliation checklist. Plus every state listed for those elements + every responsive viewport from the frontmatter.

For Phase 5 (integration regression) and `/architect-team:visual-qa`, the scope is **every screen with a per-screen visual spec in DESIGN_MAP.md**. No exceptions; this is the regression net.

## Phase B — Code-first static analysis (mandatory, BEFORE running the browser)

Before launching Playwright, read the component code that renders each in-scope element and statically confirm the values resolve to the DESIGN_MAP spec. Static analysis catches drift even when runtime tests pass (because someone updated the tests to match the drift).

For each in-scope element:

1. **Locate the component source** — grep for the testid or role-name in the codebase to find the JSX/template that renders the element. Identify every styling layer that affects it:
   - Inline styles (`style={{ ... }}`).
   - Tailwind classes (`className="bg-brand-500 text-white px-4 py-2 ..."`) — resolve each class to its token value via the `tailwind.config.{js,ts}` and confirm against the DESIGN_MAP token.
   - CSS / SCSS module classes — find the source `.module.css` / `.module.scss` and resolve.
   - Styled-components / Emotion / Vanilla Extract / Stitches CSS-in-JS — read the `styled.div\`...\`` block.
   - Global CSS / theme variables — trace `var(--brand-primary)` to its declaration in `:root` / `[data-theme=...]`.
   - Inherited styles — check the parent chain for cascade.
2. **Compare each style property to the DESIGN_MAP spec** — for every property listed in the per-element row:
   - Code value resolves to spec value → tentative `perfect` (runtime will confirm).
   - Code value resolves to a different value → static drift, capture both with file:line citation.
   - Code value is dynamic (depends on a prop / theme / feature flag) → record the dependency and resolve at runtime in Phase C.
3. **Check asset references statically** — for every `<img src=...>` / `<svg use href=...>` / `background-image: url(...)`, verify the path resolves to an entry in DESIGN_MAP's Asset Registry, and the file at that path matches the registered SHA-256 (compute via `sha256sum` / `certutil`).
4. **Check link targets** — for every element with a `target_link` in DESIGN_MAP, locate the click handler / `href` / `to` prop / `router.push(...)` / `navigate(...)` call in the source. Compare:
   - `source: "explicit"` → match REQUIRED. Mismatch is drift; fix the implementation to match the explicit target.
   - `source: "inferred"`, `confidence: "high"` → match expected. Mismatch is drift, but with a note: the inference may have been wrong (the implementation is the more recent intent) OR the implementation drifted from intent. The fix-or-escalate decision uses the standard Phase E matrix; in practice, high-confidence inferences that match a coherent navigation web should be honored as the contract, and mismatches fix the implementation.
   - `source: "inferred"`, `confidence: "medium"` or `"low"` → match is informational only. Mismatch escalates to clarify (`awaiting_confirmation: true` items become escalations naturally; the user confirms the target, which becomes `explicit` on the next DESIGN_MAP refresh).
   - `source: "unknown"` (target is `"?"`) → cannot reconcile; record the implementation's actual link target as evidence and escalate so the user can promote it to `explicit` or correct it.

The static analysis output is a per-element `static_verdict` field captured into the reconciliation JSON before runtime. The runtime in Phase C either confirms it or contradicts it (which itself is a finding — usually means a cascade or runtime computation the static pass missed).

## Phase C — Runtime verification with Playwright

After the static pass, run a fresh Playwright session per viewport declared in DESIGN_MAP.md and verify the rendered values for every in-scope tuple.

### Setup per viewport

```typescript
await page.setViewportSize({ width: 1440, height: 900 }); // EXACT viewport from DESIGN_MAP
await page.goto(screenUrl);
await page.waitForLoadState('networkidle');
```

### Induce each state explicitly

| State | How to induce |
|---|---|
| default | navigate to the screen, no interactions |
| hover | `await element.hover()` |
| focus | `await element.focus()` (or `page.keyboard.press('Tab')` to traverse) |
| active | `await page.mouse.down()` while element is hovered |
| disabled | navigate with the form in a state that triggers disabled (empty fields, etc.) |
| loading | intercept the relevant network call with `page.route` and delay the response |
| error | force a 4xx/5xx via `page.route` and trigger the action |
| empty | seed the dev API with an empty dataset OR force an empty response via `page.route` |

After inducing, wait for the state-defining element / class to be present before measuring (e.g., `await element.waitFor({ state: 'visible' })`, or wait for a CSS class change indicating the state).

### Measure every property

```typescript
const styles = await element.evaluate((el) => {
  const cs = window.getComputedStyle(el);
  return {
    fontFamily: cs.fontFamily,
    fontSize: cs.fontSize,
    fontWeight: cs.fontWeight,
    fontStyle: cs.fontStyle,
    lineHeight: cs.lineHeight,
    letterSpacing: cs.letterSpacing,
    textTransform: cs.textTransform,
    textDecoration: cs.textDecorationLine,
    color: cs.color,
    backgroundColor: cs.backgroundColor,
    backgroundImage: cs.backgroundImage,
    paddingTop: cs.paddingTop, paddingRight: cs.paddingRight, paddingBottom: cs.paddingBottom, paddingLeft: cs.paddingLeft,
    marginTop: cs.marginTop, marginRight: cs.marginRight, marginBottom: cs.marginBottom, marginLeft: cs.marginLeft,
    borderTopWidth: cs.borderTopWidth, borderRightWidth: cs.borderRightWidth, borderBottomWidth: cs.borderBottomWidth, borderLeftWidth: cs.borderLeftWidth,
    borderTopColor: cs.borderTopColor, borderRightColor: cs.borderRightColor, borderBottomColor: cs.borderBottomColor, borderLeftColor: cs.borderLeftColor,
    borderTopStyle: cs.borderTopStyle,
    borderTopLeftRadius: cs.borderTopLeftRadius, borderTopRightRadius: cs.borderTopRightRadius, borderBottomRightRadius: cs.borderBottomRightRadius, borderBottomLeftRadius: cs.borderBottomLeftRadius,
    boxShadow: cs.boxShadow,
    outline: cs.outline, outlineColor: cs.outlineColor, outlineWidth: cs.outlineWidth, outlineOffset: cs.outlineOffset,
    cursor: cs.cursor,
    opacity: cs.opacity,
    transform: cs.transform,
    zIndex: cs.zIndex,
  };
});
const box = await element.boundingBox();
```

Plus take a **per-state screenshot** at the element scope:

```typescript
await element.screenshot({ path: `<test-output-dir>/visual-fidelity/screenshots/<screen>-<element>-<state>-<viewport>.png` });
```

And a full-page screenshot at the viewport scope:

```typescript
await page.screenshot({ path: `<test-output-dir>/visual-fidelity/screenshots/<screen>-<state>-<viewport>-page.png`, fullPage: true });
```

Screenshots are evidence; they go into the reconciliation JSON's per-tuple `evidence[]` array.

### Compare with zero-tolerance defaults

| Property | Default tolerance |
|---|---|
| any color (color / background-color / border-color / outline-color / box-shadow color) | EXACT — rgb / rgba must match byte-for-byte |
| font-family | EXACT match — `Inter, system-ui, sans-serif` is NOT the same as `Inter, sans-serif`; whitespace/comma normalization is allowed |
| font-size | EXACT — `14px` not `13.99px` |
| font-weight | EXACT — `600` not `500` |
| font-style, text-transform, text-decoration | EXACT |
| line-height | EXACT — `20px` (or unitless `1.4` if specified that way, must match) |
| letter-spacing | EXACT |
| bounding-box x / y / width / height | 0px (EXACT) |
| padding / margin (each side) | 0px (EXACT) |
| border-radius (each corner) | 0px (EXACT) |
| border-width / style / color (each side) | EXACT |
| box-shadow | EXACT — offset / blur / spread / color all match |
| outline (focus state) | EXACT |
| opacity | EXACT (3 decimal places) |
| cursor | EXACT |
| asset src | EXACT path |
| asset SHA-256 | EXACT hash |
| z-index | EXACT |

**Per-element tolerance overrides** are allowed only when DESIGN_MAP.md has an explicit `tolerance:` clause for that element with a recorded rationale (e.g., `tolerance: { width: 1px, rationale: "sub-pixel rounding observed across browser engines; not user-perceivable" }`). Silent slop is forbidden.

## Phase D — Reconciliation report

For each screen reconciled, persist `<test-output-dir>/visual-fidelity/<screen>-<viewport>-<timestamp>.json`:

```json
{
  "schema_version": 1,
  "screen": "/login",
  "reconciled_at": "<ISO 8601 UTC>",
  "design_map_version": "<DESIGN_MAP.md last_designed timestamp>",
  "design_map_sha": "<git blob SHA of DESIGN_MAP.md at reconciliation time>",
  "viewport": { "width": 1440, "height": 900 },
  "engine": "chromium",
  "tuples": [
    {
      "element_id": "submit-button",
      "state": "default",
      "verdict": "perfect",
      "static_verdict": "perfect",
      "runtime_verdict": "perfect",
      "captured": { "font-family": "Inter, system-ui, sans-serif", "color": "rgb(255, 255, 255)", "background-color": "rgb(37, 99, 235)", "padding-top": "10px", "padding-right": "16px", "padding-bottom": "10px", "padding-left": "16px", "border-radius": "6px", "box-shadow": "0 1px 2px rgba(0, 0, 0, 0.05)", "width": 240, "height": 40 },
      "spec": { "font-family": "Inter, system-ui, sans-serif", "color": "#FFFFFF", "background-color": "#2563EB", "padding": "10px 16px", "border-radius": "6px", "box-shadow": "shadow.sm", "width": 240, "height": 40 },
      "delta": [],
      "evidence": ["screenshots/login-submit-button-default-1440.png", "screenshots/login-default-1440-page.png"]
    },
    {
      "element_id": "submit-button",
      "state": "hover",
      "verdict": "drift",
      "static_verdict": "drift",
      "runtime_verdict": "drift",
      "captured": { "background-color": "rgb(37, 99, 235)" },
      "spec": { "background-color": "#1D4ED8" },
      "delta": [
        {
          "property": "background-color",
          "captured": "rgb(37, 99, 235)",
          "spec": "rgb(29, 78, 216)",
          "severity": "high",
          "user_perceivable": true,
          "note": "hover state not implemented — element retains default background on :hover",
          "static_evidence": "Button.tsx:24 has no :hover styling for variant=primary",
          "runtime_evidence": "screenshots/login-submit-button-hover-1440.png"
        }
      ],
      "evidence": ["screenshots/login-submit-button-hover-1440.png"]
    },
    {
      "element_id": "remember-me-checkbox",
      "state": "default",
      "verdict": "gap",
      "captured": { "rendered": false },
      "spec": { "expected": "16x16 checkbox inline-flex with 'Remember me' label, 8px gap" },
      "delta": [
        {
          "property": "exists",
          "captured": "not rendered",
          "spec": "rendered",
          "severity": "high",
          "user_perceivable": true,
          "note": "checkbox component absent from JSX; spec calls for it",
          "static_evidence": "LoginForm.tsx — no <input type=\"checkbox\" /> nor RememberMe component referenced",
          "runtime_evidence": "screenshots/login-default-1440-page.png"
        }
      ],
      "evidence": ["screenshots/login-default-1440-page.png"]
    }
  ],
  "summary": {
    "tuples_reconciled": 24,
    "perfect": 22,
    "drift": 1,
    "gap": 1,
    "perfect_percentage": 91.67,
    "screens_in_scope": ["/login"],
    "viewports_in_scope": [{ "width": 1440, "height": 900 }],
    "states_in_scope": ["default", "hover", "focus", "disabled", "loading", "error"]
  }
}
```

Then aggregate all per-screen JSONs into a single `<cwd>/.architect-team/visual-fidelity-summary-<ts>.md` for the orchestrator and architect-team to read. The summary lists every drift and gap with screen + element + state + delta + severity.

## Phase E — Drift / gap remediation (fix to spec by default; escalate only on the narrow exceptions)

When Phase D produces any tuple with verdict `drift` or `gap`, the discipline is to FIX the implementation to align with the spec. The hook will eventually block `visual_fidelity_review: "fail"` — but the goal is to never need that branch. The reconciliation loop is fix → re-run Phase B (static) and Phase C (runtime) → verify `perfect` → set `"pass"`.

### The fix-or-escalate decision matrix

For each `drift` / `gap` row in the reconciliation JSON, decide:

| Finding | Default action |
|---|---|
| Drift in a file in your `files_owned` (Phase 3) OR any frontend file under reconciliation (Phase 5 / on-demand) | **Fix to spec.** Change the className / inline style / token / asset reference to produce the spec value. Re-run Phase B + Phase C for the affected tuples. Loop until `perfect`. |
| Gap: spec describes an element that is NOT rendered (e.g., "Remember me" checkbox missing from JSX) | **Implement to spec.** Add the JSX / component import / state binding so the element renders per the spec. Re-run reconciliation. |
| Gap: implementation has an element that is NOT in the spec (extra widget, leftover from a previous build) | **Escalate** (this is the user-input branch). Write the handoff per "Escalation" below — the user / architect-team must decide whether to add the element to DESIGN_MAP via `design-fidelity-mapping` or remove it from the implementation. Don't unilaterally delete. |
| Drift in a file OUTSIDE your scope (Phase 3 only — teammate's `files_owned` excludes the file) | **Escalate** to the team that owns the file. The orchestrator routes a focused task to them. |
| Drift where fixing affects MANY screens via cascade (e.g., a token in `tailwind.config.ts` is wrong, used by 14 screens) | **Fix the cascade** if it converges every dependent screen to its own spec values — that is the right fix because the token IS the spec primitive. Re-reconcile EVERY affected screen, not just the one that surfaced the drift. If the fix would convert one drift into 14 drifts (because some dependent screens were relying on the wrong value), escalate to the architect-team. |
| Spec ambiguity: DESIGN_MAP says `color: brand.primary.500` but no `brand.primary.500` token exists in the codebase, OR the per-screen spec contradicts the design tokens table | **Escalate.** The spec itself needs fixing first; only the architect-team or the user can decide which value is canonical. Trigger `design-fidelity-mapping` refresh after the decision lands, then re-reconcile. |
| Tolerance ambiguity: spec says `width: 240px` but the rendered width is 239px and no `tolerance` clause exists | **Fix to spec** (the default tolerance is 0px). If the 1px diff is structural (e.g., a fractional border-radius rendering artifact unavoidable across browsers), then escalate to ADD a tolerance to DESIGN_MAP — but the default is fix, not escalate. |

### How to fix (concrete)

1. **Identify the styling layer** carrying the drifted value (inline / Tailwind class / CSS module / CSS-in-JS / theme variable / cascading parent).
2. **Change the value at its source** — prefer fixing the token (in `tailwind.config.{js,ts}` / `theme.ts` / `tokens.json` / `:root` CSS variables) over fixing the call-site if the spec value matches an existing token name. Prefer fixing the call-site over inventing new tokens when the spec value is one-off.
3. **Never bandage** — adding a class that overrides a wrong inherited value is a bandage; fix the inheritance.
4. **Asset fixes** — if `src` is wrong, point it to the registered asset. If the file's SHA-256 has drifted, the asset bytes were modified; restore from the registry or escalate if the modification was intentional.
5. **State-induction fixes** — if `:hover` styles are missing (the drift is "default and hover have the same bg"), add the `:hover` (or `data-state=hover` / `&:hover` in CSS-in-JS) rule producing the spec value.
6. **Responsive fixes** — if a breakpoint diverges, add or correct the `@media` / Tailwind breakpoint variant (e.g., `md:px-6`) for that viewport.
7. **Re-run reconciliation** on the tuples you fixed before claiming verdict `pass`. The reconciliation JSON's `passes_after_fix` field should record how many iterations the convergence took (1 ideally; more than 3 is a smell — escalate).

### Escalation (only for the narrow exceptions above)

When escalating:

1. Write the reconciliation JSON(s) and the summary as evidence (these already exist from Phase D).
2. Set `visual_fidelity_review: "fail"` in the review evidence — the hook will block the TaskUpdate, which is correct: a teammate cannot mark complete with unresolved drift.
3. Write the handoff to `<cwd>/.architect-team/handoffs/<self>-to-architect-visual-<reason>-<screen>-<ts>.md` where `<reason>` is one of: `out-of-scope`, `implementation-extras`, `spec-ambiguity`, `cascade-blast-radius`. The handoff contains:
   - DESIGN_MAP.md version reconciled against (timestamp + blob SHA).
   - The summary of every drift / gap with severity.
   - The link(s) to the reconciliation JSON(s) and the per-state screenshots.
   - **Crucially: WHY this isn't being fixed autonomously** — name the specific decision matrix row that triggered escalation. Without this, the handoff is just an alert (which the user said is insufficient).
   - For scope-out-of-bounds escalations, identify the team that owns the file (`git log` ownership) so the orchestrator can route directly.
4. Signal idle.

The hook value `"fail"` is the SAFETY NET, not the default workflow. The default workflow is: drift found → fix → re-run → `"pass"`. If you find yourself reaching for `"fail"`, you have either (a) hit one of the four escalation cases above and the handoff is the right action, or (b) you're avoiding a fix that you should be making. Choose carefully.

**Allowed verdict values for `visual_fidelity_review` in review-gate evidence:**

- `"pass"` — reconciliation ran, every tuple is `perfect` (after all fix-and-re-run iterations). Required when frontend was touched AND DESIGN_MAP.md exists. THIS IS THE STEADY STATE.
- `"n/a"` — either no frontend was touched OR DESIGN_MAP.md does not exist for this codebase. MUST also include `visual_fidelity_review_note` with a one-sentence justification of which branch applies.
- `"fail"` — reconciliation ran, at least one tuple was `drift` or `gap` AND the discipline could not converge to `pass` autonomously (one of the four escalation cases applies). The hook BLOCKS this value — the teammate has escalated and is waiting for the architect-routed clarification, after which they re-run reconciliation and only mark complete when verdict is `"pass"`.

## Hard rules — non-negotiable

- **Zero-tolerance defaults.** No silent slop. Per-element tolerance overrides go in DESIGN_MAP.md with a written rationale, not in test code.
- **Exhaustive states.** Every state listed or implied must be reconciled. A spec that only covers `default` while the component has hover / focus / disabled is itself a gap (escalate to update DESIGN_MAP first, then re-reconcile).
- **Exhaustive viewports.** Reconciliation runs at every viewport declared in DESIGN_MAP.md's `viewports_responsive` frontmatter. Different viewport → different verdict.
- **Code-first BEFORE runtime.** Skipping the static analysis means missing the cases where Playwright happens to pass but the underlying code is wrong (e.g., theme variable was changed and so was the test).
- **Screenshots are mandatory evidence.** Every tuple's `evidence[]` array includes at minimum one per-state element screenshot AND one per-viewport full-page screenshot. They go into the review-gate evidence as artifact paths.
- **Fix to spec is the default.** When the file is in scope and the spec is unambiguous, the agent CHANGES the implementation to match DESIGN_MAP, re-runs reconciliation, and verifies `perfect`. Alerting without fixing is a process failure.
- **Escalation is for the narrow exceptions only.** Out-of-scope files, implementation-has-extras-not-in-spec, spec-ambiguity, cross-screen cascade blast radius. Every escalation handoff names which case triggered it.
- **Asset SHA-256 always verified at runtime.** A `src` match without a hash match is incomplete — the served bytes are what the user actually sees.
- **The spec is the contract, not a suggestion.** DESIGN_MAP.md is what was agreed. Implementation drift is a code defect; the fix is code, not negotiation. If the spec is wrong, fix the spec via `design-fidelity-mapping` FIRST (with user / architect-team input), then re-reconcile against the corrected spec.

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "1px off is not user-perceivable" | Maybe — but it's the slippery slope of all design drift. Either update DESIGN_MAP with a stated `tolerance` for THIS element with rationale, or fix to spec. Default is zero. |
| "The hover state is not critical" | Then it should not be in DESIGN_MAP — and the reconciliation will not check it. If it IS in DESIGN_MAP, it is a tuple that must verdict. |
| "I'll just alert the user about this drift; they can decide" | No. Alerting without fixing is the failure mode this skill exists to prevent. DESIGN_MAP.md is the agreed contract; the discipline converges to it. Fix when you can; escalate only on the four named exceptions (out-of-scope, implementation-extras, spec-ambiguity, cascade-blast-radius). |
| "The design changed; the implementation is right" | Then update DESIGN_MAP first via `design-fidelity-mapping` to capture the new design, then re-reconcile. Order matters: design → map → implement → reconcile. NEVER assume the implementation is right when it disagrees with the captured spec. |
| "Snapshot regression is enough; we do not need per-element comparisons" | Snapshots regress on overall pixel diff but mask many computed-style drifts (a wrong font-weight that is within tolerance pixel-wise still ships the wrong contract). Both layers are required. |
| "Cross-browser differences make 0px impossible" | Run reconciliation in the SAME browser engine as DESIGN_MAP was captured against. If multiple engines are in scope, DESIGN_MAP must declare per-engine variants. |
| "I will just mark visual_fidelity_review n/a — designs were not provided" | If DESIGN_MAP.md does not exist for the codebase, n/a is correct AND the note must say so explicitly. If it DOES exist, n/a is the wrong call — fix to spec or escalate per the matrix. |
| "Static analysis is redundant with runtime" | Static analysis catches drift the runtime can mask (the test was updated to match the wrong value). Both are required. |
| "I'll escalate this — the user can decide" | Re-read the decision matrix. Most drift is fixable autonomously: change a Tailwind class, change a token, add a missing state rule, add a missing element to JSX, fix an asset path. Only escalate when the matrix says to (out-of-scope, implementation-extras, spec-ambiguity, cascade-blast-radius). Escalation-by-default is what the user explicitly rejected. |
| "Fix-and-re-run might mask the original problem" | The reconciliation JSON records every iteration in `passes_after_fix`. The audit trail captures both the original drift and the fix. Convergence to `perfect` IS the outcome the discipline targets. |
| "Screenshots are just for snapshots, not per-state" | Per-state element screenshots are EVIDENCE the reconciliation actually ran the state. Without them, you can claim any verdict; with them, the verdict is auditable. |
| "The fix touches 14 files via the token cascade — that's too many to do autonomously" | If all 14 dependent screens converge to their own spec values after the fix, that is the correct fix and you SHOULD do it. If the fix would convert one drift into many drifts (some screens were relying on the wrong value), THEN escalate via the cascade-blast-radius branch. Count of files is not the test; convergence-to-spec is. |

## Red flags — STOP and re-run

- You ran reconciliation with a global `tolerance: > 0` instead of per-element.
- You declared `visual_fidelity_review: "pass"` without producing the reconciliation JSON(s).
- You skipped a state ("the disabled state is rare").
- You escalated a drift that the decision matrix says to fix autonomously.
- You alerted the user about a drift without first attempting (or completing) the fix per the decision matrix.
- You ran reconciliation at the wrong viewport because "1440 vs 1366 doesn't matter".
- The reconciliation JSON has fewer tuples than `screens_in_scope × elements_per_screen × states_per_element × viewports`.
- The `evidence[]` array for any tuple is empty.
- Static analysis was skipped because "the runtime would catch it anyway".
- The DESIGN_MAP.md was stale (`last_designed` < latest codebase commit on frontend files) and you proceeded without refreshing it.
- An escalation handoff is missing the named decision-matrix case that triggered it — without that, it's an alert, not an escalation.
