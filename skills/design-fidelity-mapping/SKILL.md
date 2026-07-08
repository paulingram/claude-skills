---
name: design-fidelity-mapping
description: Use when authoring or refreshing a frontend codebase's UX mapping AND any design artifacts are available — Figma exports, screenshot/mockup images (PNG/JPG/SVG), design tokens files, Storybook configs, brand guidelines, or a codebase `assets/` directory. Triggers - a `designs/` / `screens/` / `mockups/` folder in `$REQ_DIR`, a Figma URL referenced in proposal/design.md, a `tokens.json` / `tailwind.config.{js,ts}` / `theme.ts` / `.storybook/main.{js,ts}` in the codebase, an `assets/` or `public/images/` directory with non-trivial content, OR you are about to author Playwright tests for a UI that has a visual contract that needs codification. Skipped when no design inputs exist — the absence of a DESIGN_MAP.md is not a gap if there are no design inputs.
---

# Design-Fidelity Mapping — Capture the Visual Contract

Without a structured visual contract, "the page renders correctly" is a judgment call by whoever is looking. Design drift accumulates silently as developers freelance on spacing, colors, font weights, and asset placement. This skill makes the visual contract auditable: capture every design token, every static asset, and every per-screen visual spec in a single `<codebase>/docs/DESIGN_MAP.md`. The subsequent Playwright tests (per `playwright-user-flows`) then verify the running UI matches the contract by asserting computed styles, bounding boxes, asset references, and (optionally) pixel snapshots.

This skill is the conditional sibling of `frontend-route-mapping`. `ROUTE_MAP.md` captures structural and behavioral surface (routes, navigation, API calls); `DESIGN_MAP.md` captures visual surface (tokens, assets, per-screen specs). Both are produced by the same `route-mapper` agent, in the same Phase −1B mapping pass — but `DESIGN_MAP.md` only when design inputs exist.

## When to apply (conditional)

Run this skill if AT LEAST ONE of these is present:

1. Image files (PNG / JPG / SVG) in `$REQ_DIR/designs/`, `$REQ_DIR/screens/`, or `$REQ_DIR/mockups/`.
2. A Figma export folder in `$REQ_DIR/figma/` OR a Figma URL referenced in `$REQ_DIR/proposal.md` or `$REQ_DIR/design.md`.
3. A design tokens file in the codebase: `tokens.json`, `design-tokens.json`, `tailwind.config.{js,ts}`, `theme.ts`, `themes/*.ts`, `styles/tokens.css`, `theme.scss`.
4. A Storybook config: `.storybook/main.{js,ts}` in the codebase.
5. A brand guidelines doc: `BRAND.md`, `brand-guide.pdf`, links to a brand site in proposal/design.
6. An `assets/`, `public/images/`, `public/assets/`, or `static/images/` directory in the codebase with at least one non-trivial logo, illustration, or icon asset.
7. A materialized Claude Design project directory at `<workspace>/.architect-team/claude-design/<project-id>/` — produced by `claude-design-import` from a `claude.ai/design/p/<id>` offer (per `intake-and-mapping`). This is a first-class design-input source alongside the local/zip inputs above.

If none of the above exist, this skill is skipped. The codebase-map-reviewer must NOT flag a missing `DESIGN_MAP.md` as a deficiency in that case.

## File location and format

- Path: `<codebase>/docs/DESIGN_MAP.md`.
- YAML frontmatter (required):
  ```yaml
  ---
  last_designed: 2026-05-18T10:30:00Z
  design_baseline: V2   # label/version of the design GENERATION this map encodes
                        # (a redesign codename, a design-system version, a Figma
                        # file version). When this changes, the design Oracle
                        # itself moved — see Freshness → baseline migration.
  codebase: /abs/path/to/frontend
  framework: nextjs-15-app-router
  design_sources:
    - kind: screenshots
      path: $REQ_DIR/designs/
      count: 12
    - kind: tokens-file
      path: tailwind.config.ts
    - kind: storybook
      path: .storybook/
  viewport_default: { width: 1440, height: 900 }
  viewports_responsive: [{ width: 375, height: 667 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]
  color_format: oklch  # or hex, rgb — pick one and use it consistently in the body
  ---
  ```

## Schema (every applicable section required)

Sections are required only if their underlying data exists. Missing data is declared in `## Coverage & Gaps` with the reason.

### `## Design Tokens`

Every design primitive expressible as a value. Use markdown tables. Cite the source for every row — either a screenshot frame, a Figma node, or a codebase file:line.

#### Color palette

| Name | Value | Semantic role | Source | Codebase reference |
|---|---|---|---|---|
| `brand.primary.500` | `#2563EB` / `oklch(0.55 0.22 256)` | primary action / CTA | `designs/login.png` (button bg) | `tailwind.config.ts:18` (`colors.brand.500`) |
| `brand.primary.600` | `#1D4ED8` | primary action hover | `designs/login.png` (hover state from Figma) | `tailwind.config.ts:19` |
| `surface.default` | `#FFFFFF` | page background | `designs/login.png` | `tailwind.config.ts:42` |
| `surface.muted` | `#F9FAFB` | secondary surfaces | `designs/dashboard.png` | `tailwind.config.ts:43` |
| `text.primary` | `#111827` | body text | `designs/login.png` | `tailwind.config.ts:55` |
| `text.muted` | `#6B7280` | help text, captions | `designs/login.png` | `tailwind.config.ts:56` |
| `feedback.error` | `#DC2626` | error states | `designs/login-error.png` | `tailwind.config.ts:71` |
| `feedback.success` | `#059669` | success toasts | `designs/dashboard-toast.png` | — (NEW, missing from codebase) |

Detected drift: every row where the design source disagrees with the codebase reference is captured in `## Detected Drift`.

#### Typography

| Token | Family | Size | Weight | Line-height | Letter-spacing | Use cases | Source |
|---|---|---|---|---|---|---|---|
| `display.lg` | `Inter, system-ui` | 36px | 700 | 44px | -0.5px | page titles | `designs/login.png` |
| `heading.md` | `Inter, system-ui` | 24px | 600 | 32px | -0.25px | section headings | `designs/dashboard.png` |
| `body.md` | `Inter, system-ui` | 14px | 400 | 20px | 0 | default body | all screens |
| `body.sm` | `Inter, system-ui` | 12px | 400 | 16px | 0 | help text | `designs/login.png` |
| `mono.md` | `JetBrains Mono` | 13px | 400 | 20px | 0 | code snippets | `designs/dashboard.png` |

Include every family with its fallback chain. Note any web-font hosting strategy (self-hosted vs CDN) if discoverable from the codebase.

#### Spacing scale

| Token | Value | Codebase reference |
|---|---|---|
| `space.1` | 4px | `tailwind.config.ts:91` |
| `space.2` | 8px | `tailwind.config.ts:92` |
| `space.3` | 12px | — (used in `designs/`, NOT in tokens) |
| `space.4` | 16px | `tailwind.config.ts:93` |
| `space.6` | 24px | `tailwind.config.ts:94` |
| `space.8` | 32px | `tailwind.config.ts:95` |

#### Radii, shadows, borders, breakpoints, z-index, motion

Each in its own subsection if the codebase or design defines them. Same table-with-citation format. Examples:

| Radius token | Value | Source |
|---|---|---|
| `radius.sm` | 4px | `designs/login.png` (input fields) |
| `radius.md` | 8px | `designs/login.png` (buttons) |
| `radius.full` | 9999px | `designs/dashboard.png` (avatar) |

| Shadow token | Value | Source |
|---|---|---|
| `shadow.sm` | `0 1px 2px rgb(0 0 0 / 0.05)` | `designs/dashboard-card.png` |
| `shadow.lg` | `0 10px 15px rgb(0 0 0 / 0.10)` | `designs/dashboard-modal.png` |

### `## Asset Registry`

Every static image, icon, illustration, or font file the UI ships:

| Asset ID | Path | Purpose | Dimensions | Size | SHA-256 | Variants | Referenced from |
|---|---|---|---|---|---|---|---|
| `logo-primary` | `public/images/logo.svg` | brand logo | 144 × 32 | 2.4 KB | `a3f1...` | `logo-dark.svg`, `logo-mark-only.svg` | `Header.tsx:8`, `LoginPage.tsx:14` |
| `hero-illustration` | `public/images/hero.png` | landing hero | 1200 × 800 | 84 KB | `7c2e...` | `hero@2x.png`, `hero-mobile.png` | `LandingPage.tsx:22` |
| `icon-set` | `public/icons/*.svg` | UI icons | 24 × 24 | per file | per file | — | `<Icon name="..." />` (resolves dynamically) |
| `favicon` | `public/favicon.ico` | tab icon | 32 × 32 | 1.1 KB | `4b8d...` | `favicon@2x.png`, `apple-touch-icon.png` | `<head>` |
| `font-inter` | `public/fonts/Inter-*.woff2` | web font | — | varies | per file | `Inter-Variable.woff2` | `@font-face` in `globals.css:3` |

Compute SHA-256 hashes via `sha256sum` (Unix) or `certutil -hashfile <path> SHA256` (Windows). Hashes go into the registry so test verification can detect tampering / accidental overwrites.

For each asset, also capture:
- **Alt text** (if `<img>`, captured from the JSX or noted "decorative — alt=''")
- **Variants** by viewport / theme / locale (light vs dark logo, mobile vs desktop hero)
- **Format constraints** (transparent PNG vs JPG, vector vs raster)

### `## Per-Screen Visual Specs`

For every screen / route that has a corresponding design artifact, the expected visual contract. One subsection per screen.

```markdown
### Screen: `/login` (logged-out state)

- **Source design:** `designs/login.png` (1440 × 900 viewport, light theme)
- **Figma frame:** "Auth / Login / Default" (if applicable)
- **Layout:**
  - Logo top-left at (40px, 40px), size 144 × 32, asset `logo-primary`.
  - Form container centered horizontally, max-width 400px, top offset 200px.
  - Form fields stacked, 16px gap between fields.
  - Submit button full-width within the form container.
  - Footer links bottom of viewport, centered.

- **Per-element specs:**

  | Element (inventory_id) | Selector | font-family | font-size | font-weight | color | bg-color | padding | border-radius | box-shadow | width | height |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | page-heading | `role=heading[name="Sign in"]` | Inter | 24px | 600 | `#111827` | — | — | — | — | auto | 32px |
  | email-label | `text="Email"` | Inter | 14px | 500 | `#374151` | — | — | — | — | auto | 20px |
  | email-input | `role=textbox[name="Email"]` | Inter | 14px | 400 | `#111827` | `#FFFFFF` | 8px 12px | 6px | inset-1px-solid-#E5E7EB | 100% | 40px |
  | password-input | `role=textbox[name="Password"]` | Inter | 14px | 400 | `#111827` | `#FFFFFF` | 8px 12px | 6px | inset-1px-solid-#E5E7EB | 100% | 40px |
  | submit-button | `role=button[name="Sign in"]` | Inter | 14px | 600 | `#FFFFFF` | `#2563EB` | 10px 16px | 6px | `shadow.sm` | 100% | 40px |
  | submit-button-disabled | `role=button[name="Sign in"][disabled]` | Inter | 14px | 600 | `#FFFFFF` | `#93C5FD` | 10px 16px | 6px | none | 100% | 40px |
  | forgot-password-link | `role=link[name="Forgot password?"]` | Inter | 12px | 400 | `#2563EB` | — | — | — | — | auto | 16px |

- **Asset placement:**
  - `logo-primary` at viewport position (40, 40).

- **Conditional states:**
  - Loading state — submit button shows a spinner (`role=progressbar`) at center, button text replaced.
  - Error state (401) — error-banner appears above the form, color `feedback.error`, padding 12px 16px, border-radius `radius.md`.

- **Responsive breakpoints:**
  - At `width=375px` (mobile): form container takes 100% width with 20px horizontal padding; logo centers; footer wraps.
  - At `width=768px` (tablet): same as desktop but with reduced top offset (120px).
  - At `width=1440px+` (desktop): as specified above.
```

For every interactive element listed in the ROUTE_MAP.md and corresponding `playwright-user-flows` interactivity inventory, this section MUST define its computed-style spec. An element in the inventory without a row in this table is a gap (declared in `## Coverage & Gaps`).

#### Static-vs-dynamic value classification (apply `dynamic-value-discovery`)

A design mockup is full of sample data — `"John Smith"`, `"$1,234.00"`, `"2 hours ago"`, `"Welcome back, Sarah"`, `"3 items"`, `"Shipped"`. A per-screen visual spec that simply records the mockup's literal lets a literal implementation ship that one sample datum to every user — the UI then shows one person's data to everyone. So the per-screen visual specs do not just capture how a value LOOKS; they classify, for **every displayed value on the screen**, what KIND of value it is, by applying the `dynamic-value-discovery` skill — read it before authoring this section.

For each displayed value, add a `value_class` field — `static` or `dynamic` — classified FROM CONTEXT (the value's position, its nature, and the requirements / design language) and NEVER from the literal itself, since the same string is `static` in one place and `dynamic` in another (a `"Dashboard"` page heading is `static`; `"Dashboard"` as one row in a list of the user's saved report names is `dynamic`). Per the `dynamic-value-discovery` rubrics: person names, dates, currency amounts, counts, statuses, IDs, a greeting with a name, and any value in a record-detail view or a repeating list row are `dynamic`; nav labels, button text, section headings, fixed helper text, and brand strings are `static`.

For every value classified `dynamic`, the spec MUST also record a `data_source` — the named source the value binds to (`session.user.name`, `order.total` from `GET /orders/:id`, a route parameter, a store/context value, a derived computation). "It comes from the backend" is not a named source. A value table row for a screen looks like:

| Value (on screen) | value_class | data_source |
|---|---|---|
| user-name in header | `dynamic` | `session.user.name` (auth session) |
| page heading "Reports" | `static` | — |
| order total | `dynamic` | `order.total` from `GET /api/orders/:id` |
| "Save" button label | `static` | — |
| order status badge | `dynamic` | `order.status` from `GET /api/orders/:id` |

When a value's static-vs-dynamic classification genuinely cannot be determined from the requirements, design, or code, do NOT default-guess — record it in `## Coverage & Gaps` with `escalate: true` and the structured question from `dynamic-value-discovery`. The Phase 1 spec's acceptance criteria then REQUIRE the binding for every `dynamic` value — so "render the user's name from the session", not "render John Smith", is in the spec from the start, and the `interaction-completeness` evaluator can later flag any `dynamic` value shipped as the hardcoded sample literal as a `hardcoded-dynamic-value` gap.

### `## Link Inference for Un-Annotated Interactive Elements`

Designers often skip explicit link annotations on obvious buttons — "Sign in" rarely gets an arrow because everyone "knows" where it goes. The route-mapper agent is EMPOWERED to INFER the most likely link target when a design artifact lacks an explicit annotation. Inference is bounded: only when no explicit annotation exists, and only when a confident candidate can be identified from context. Silent "blank link" is forbidden.

The same principle generalizes to requirements interpretation: when `proposal.md` / `design.md` describe a flow without naming the precise destination ("users can navigate to their account"), the AI infers from available routes and the design page set, records the inference with reasoning, and surfaces low / medium confidence inferences for confirmation. The design audit is the most common application but not the only one.

#### Inference precedence (top wins)

1. **Explicit annotation in the design** — a Figma prototype connector, an arrow drawn on the mockup, a `"→ /dashboard"` label on the screenshot, text in the design's exported metadata, OR an explicit page link in the requirements doc. Always follow explicit; never override.
2. **Existing route in ROUTE_MAP.md whose name semantically matches the button text** — "Sign in" button + `/signin` route exists → high confidence; "Account" button + `/account` route exists → high confidence; "Pricing" button + `/pricing` route exists → high confidence.
3. **Existing page in the design set whose title semantically matches** — "Account" button + a screen titled "Account Settings" in `$REQ_DIR/designs/` → medium confidence.
4. **UX conventions when nothing else applies** — logo / wordmark → `/` (homepage); "Cancel" inside a form → previous route or close modal; "Save" → stay on current route with toast; "Submit" in a wizard → next step in the flow; "Back" → previous route; breadcrumb segment → that segment's route; tab → URL fragment or query param.
5. **No good candidate** → record as `target: "?"` with `inferred_reason: "no matching route or page; awaiting user confirmation"` and add to `## Coverage & Gaps` with `escalate: true`.

#### Schema addition

Every interactive element in `## Per-Screen Visual Specs` that has (or should have) a click handler gets a `target_link` field. For single-target links:

```json
{
  "element_id": "signin-button",
  "target_link": {
    "target": "/signin",
    "source": "inferred",
    "confidence": "high",
    "reasoning": "Button text 'Sign in' + route /signin exists in ROUTE_MAP.md; no other 'sign in' targets in the design set",
    "alternatives": ["/login (not in routes)", "/auth (route exists but is API namespace, not a page)"],
    "awaiting_confirmation": false
  }
}
```

For state-conditional links (button targets different pages based on app state — e.g., "Get started" → `/onboarding` for new users, `/dashboard` for returning users), use an array:

```json
{
  "element_id": "cta-button",
  "target_link": [
    { "target": "/onboarding", "source": "explicit", "condition": "user.is_first_login === true" },
    { "target": "/dashboard", "source": "inferred", "confidence": "high", "reasoning": "returning-user CTA pattern in the design set's other flows", "condition": "user.is_first_login === false", "awaiting_confirmation": false }
  ]
}
```

#### Field definitions

- `target` — page identifier (path, screen ID, modal ID, or `"?"` if unknown).
- `source` — `"explicit"` (from design annotation OR explicit requirements doc) | `"inferred"` (this skill's inference) | `"unknown"` (no annotation, no good candidate; user must confirm).
- `confidence` (required when `source: "inferred"`) — `"high"` | `"medium"` | `"low"`.
- `reasoning` (required when `source: "inferred"`) — one-sentence justification citing the precedence-rule level that produced the inference.
- `alternatives` (required when `source: "inferred"`) — other candidates considered, each with a one-line reason for rejection.
- `condition` (optional) — when the target is state-conditional, the predicate that selects this branch.
- `awaiting_confirmation` (required boolean) — `true` for `unknown`, `low`, `medium`; `false` for `high` and `explicit`. The orchestrator surfaces every `awaiting_confirmation: true` entry to the user at audit time.

#### Confidence levels (precise definitions)

- **high** — button text closely matches the name of an existing route in ROUTE_MAP.md AND no other route is a plausible target. The inference is recorded and used downstream; no escalation. Examples: "Sign in" → `/signin`, "Settings" → `/settings`, "Logout" → `/logout`.
- **medium** — multiple routes are plausible OR the button text only loosely matches OR the match comes from the design page set rather than ROUTE_MAP.md. Recorded with `awaiting_confirmation: true`; escalated via `## Coverage & Gaps` for user confirmation. Examples: "Account" → `/profile` / `/settings` / `/account` (3 plausible); "Help" → `/help` / `/support` / `/docs`.
- **low** — generic button text with no semantic anchor: "Continue", "Next", "Go", "OK". Multiple plausible targets, no UX-convention disambiguation. Best-guess recorded with `awaiting_confirmation: true` and explicit alternatives listed. Always escalated.

#### Coverage & Gaps integration

Every `target_link` with `awaiting_confirmation: true` becomes an entry in `## Coverage & Gaps`:

```yaml
gaps:
  - kind: link_inference_low_confidence
    screen: /pricing
    element: cta-button
    inferred_target: /signup
    alternatives: [/contact, /trial]
    reason: button text 'Get started' is generic; multiple plausible targets in routes
    escalate: true
```

The orchestrator surfaces these to the user at audit time (e.g., as part of `/architect-team:visual-qa` output or at Phase 1 spec validation). The user confirms or corrects; the corrected target is then `source: "explicit"` on the next DESIGN_MAP refresh.

#### Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "I'll leave the link blank — the design did not show one" | No. Leaving it blank means future agents do not know where the button goes; the visual-fidelity reconciliation cannot verify the implementation's link target; the user does not know what to confirm. Either infer with reasoning, or escalate via Coverage & Gaps. |
| "I'll guess all the links to be thorough" | No. Inference is CONDITIONAL on no explicit annotation. If the design has an arrow, follow it — never override with a guess. Inference is for the silent buttons, not the labeled ones. |
| "Every 'Sign in' button goes to /login — I'll mark it explicit" | No. If the design did not annotate it, mark it `inferred` with `high` confidence and the reasoning. The `source` distinction matters: `inferred` flags it for the audit log and future re-checks; `explicit` hides the inference under a claim of certainty. |
| "Low-confidence inferences slow things down" | Then mark them `awaiting_confirmation: true` and proceed; surface them in the Coverage & Gaps section. The user makes the call at audit time. The discipline is to not silently guess. |
| "The implementation already has the link wired correctly, so the inference is fine" | The DESIGN_MAP captures the design intent, not the current implementation. If implementation says `/dashboard` and inference says `/home`, `visual-fidelity-reconciliation` will surface the disagreement — that is intentional. The inference may have been wrong (and the implementation right) OR the implementation may have drifted from intent. Both are findings worth surfacing. |
| "I'll infer with 'medium' for everything to be safe" | Then the user has to confirm every link, which trains them to rubber-stamp the audit. Use the precise confidence definitions; reserve `medium` for genuine ambiguity. |
| "State-conditional links are too complex — I'll just pick one variant" | No. State-conditional behavior is part of the contract. Capture all branches as an array; if one branch is genuinely unknown, mark THAT branch `awaiting_confirmation`, not the whole element. |

### `## Asset Placement Diagram`

A textual or ASCII diagram per screen showing where assets render. Useful for asymmetric layouts:

```
/login (1440 × 900):
+------------------------------------------+
| [logo-primary]                           |  ← (40, 40)
|                                          |
|                                          |
|             +----------------+           |
|             | Sign in        |           |  ← form, centered
|             | [email-input]  |           |
|             | [password]     |           |
|             | [submit-btn]   |           |
|             +----------------+           |
|                                          |
|         Forgot password? · Privacy       |  ← footer, centered
+------------------------------------------+
```

### `## Theme Variants`

If the app supports light/dark or other theme variants, document them. Each variant gets its own design tokens delta (only the values that differ) and per-screen visual specs delta (only the elements whose values change).

### `## Detected Drift`

When the route-mapper detects the current implementation deviates from the design source, record the deviation explicitly. Both values, with citations.

| Token / element | Design source value | Implementation value | Source / file:line | Severity |
|---|---|---|---|---|
| `brand.primary.500` | `#2563EB` (`designs/login.png` Figma export) | `#3B82F6` (`tailwind.config.ts:18`) | both cited | high (off by ~10% perceived blue) |
| `submit-button height` | 44px (`designs/login.png`) | 40px (`Button.tsx:24`) | both cited | medium |
| `font.body.md` line-height | 22px (Figma) | 20px (`tailwind.config.ts:108`) | both cited | low |

The drift list is the input to the Phase 1 planning validation (the spec must decide for each row: fix the implementation, fix the design, or accept the deviation with rationale).

### `## Coverage & Gaps`

Where the design map is incomplete and why:

```yaml
gaps:
  - kind: missing_screen_spec
    screen: /dashboard
    reason: no design artifact provided in $REQ_DIR; left untouched
  - kind: missing_element_spec
    screen: /login
    element: remember-me-checkbox
    reason: checkbox not visible in the provided screenshot; awaiting design
    escalate: true
  - kind: missing_responsive_spec
    screen: /login
    breakpoint: mobile
    reason: only desktop screenshot provided
    escalate: true
```

Any `escalate: true` gap is a question to surface to the user before authoring tests.

## Capturing from each input type

### From screenshot/mockup images

Use the `Read` tool to load each PNG/JPG/SVG. For each image:
1. Identify which route/screen it represents (from filename, surrounding context, or by matching layout against ROUTE_MAP.md).
2. Extract colors (sample directly from the image): for each named element, name the rendered color. If the colors don't match a known token, propose a new token name and flag in `## Detected Drift` against any existing token approximations.
3. Estimate typography from visual scale (you may not be able to read font family names from a screenshot — note `inferred-from-visual`).
4. Estimate spacing and sizing.
5. Locate assets in the image (logos, illustrations, icons) and propose Asset Registry entries.

When in doubt about a value from a screenshot, mark it `~approximate from screenshot` and flag in `## Coverage & Gaps` with `escalate: true`. Do NOT invent precise values that aren't observable.

### From Figma exports

If a JSON export is provided (e.g., from the Figma REST API), parse it for: frames, styles, components, exported assets. Map each frame name to a screen identifier. Pull fills, strokes, text styles, effects directly — those are precise values.

### From a design tokens file in the codebase

`tokens.json` / `tailwind.config.{js,ts}` / `theme.ts` / `styles/tokens.css` — read each and extract every named token. The codebase tokens are precise values; populate the tables from them. Then compare to any provided design source — disagreements go in `## Detected Drift`.

### From Storybook

If `.storybook/main.{js,ts}` is present, identify story files (`*.stories.tsx`). Each story is a documented variant of a component, often with theme-aware controls. Use story files to enumerate component states (default, hover, focus, disabled, loading, error) — these become rows in the per-element table.

### From brand guidelines docs

`BRAND.md` or referenced brand sites typically specify primary colors, fonts, logo usage rules, and minimum sizes / clear-space rules for assets. Extract these into the tokens tables and the asset registry's notes column.

### From the codebase's assets directory

Walk every file in `public/images/`, `public/assets/`, `assets/`, `static/images/`. For each asset, run `sha256sum` (Unix) or `certutil -hashfile <path> SHA256` (Windows), record dimensions via `file` / `identify` if available, and grep the codebase for references (`<img src=`, `import logo from`, `url(...)` in CSS).

### From a materialized Claude Design project

When `intake-and-mapping` detected a Claude Design offer and `claude-design-import` materialized the project to `<workspace>/.architect-team/claude-design/<project-id>/`, treat that directory as a design-input source. It holds the whole project's HTML screens + assets. Walk each screen's markup + inline styles for the per-screen visual specs (colors, typography, spacing read from the rendered markup rather than estimated from a screenshot), register every asset under `## Asset Registry`, and use the offer's focus (`?file=` selector + `Implement:` target) to prioritize which screen's spec drives the Phase 1 build. The materialized project is an ordinary directory input — nothing about the capture changes because it arrived through the `claude_design` MCP.

## What "complete" means (for the codebase-map-reviewer)

A `DESIGN_MAP.md` is incomplete if ANY of the following:

- A design token in `tailwind.config.{js,ts}` / `theme.ts` / `tokens.json` is not in the appropriate Design Tokens table.
- An asset file in `public/images/` / `assets/` / `public/assets/` is not in the Asset Registry.
- A screen has a corresponding design artifact (screenshot, Figma frame) but no `## Per-Screen Visual Specs` subsection.
- An interactive element listed in `playwright-user-flows`'s interactivity inventory for a screen lacks a row in that screen's per-element table.
- The codebase clearly disagrees with the design source (e.g., button heights differ) but `## Detected Drift` has no entry.
- A gap exists but `## Coverage & Gaps` is missing or empty.

If the design source IS incomplete (only one screen provided, only desktop viewport, etc.), the map IS complete as long as `## Coverage & Gaps` explicitly declares the missing portions with `escalate: true`. Silent incompleteness is the failure mode.

## Verification — Playwright visual-fidelity tests

`DESIGN_MAP.md` is consumed by `playwright-user-flows` Phase B, which authors a layer of **visual-fidelity tests** alongside the user-journey tests. These tests assert:

1. **Computed styles match** the per-element specs (font-family, font-size, font-weight, color, background-color, padding, border-radius, box-shadow, width, height) using `element.evaluate(el => window.getComputedStyle(el))`.
2. **Bounding boxes match** (within tolerance, default ±2px) using `element.boundingBox()`.
3. **Asset references resolve** to the registered paths; optionally verify the served asset's SHA-256 matches the registry.
4. **Snapshot regression** (optional but recommended) at the primary viewport, with explicit masks for time-sensitive UI.

Test naming follows the user-intent convention from `playwright-user-flows` — name visual-fidelity tests after what the user perceives, not after the assertion mechanic. Example:

- **Yes:** `test_user_sees_brand_primary_button_on_login_page`
- **No:** `test_submit_button_has_correct_background_color`

See `playwright-user-flows` "Visual-fidelity tests" subsection in Phase B for the full test patterns and tolerance defaults.

## Downstream consumer: interaction-intuition (Phase −1D)

DESIGN_MAP.md is a Phase −1B output and a Phase −1D input. At Phase −1D the `interaction-intuiter` agent reads DESIGN_MAP.md (alongside ROUTE_MAP.md and INTEGRATION_MAP.md) per the `interaction-intuition` skill and produces `<codebase>/docs/INTERACTION_INTUITION_MAP.md` — a per-element intuition of "what action does this control take and which endpoint does it call" with confidence high / medium / low / unknown. The per-screen specs in this map drive the intuiter's enumeration order and the surrounding-controls reasoning; the per-screen `value_class` classifications (static / dynamic from `dynamic-value-discovery`) inform the intuiter's evidence trail when reasoning about which displayed values back which endpoints. When DESIGN_MAP.md is absent (no design inputs detected), the intuiter falls back to enumerating from the route table — and the resulting intuition map will be `medium`/`low`-heavy at the Phase −1D bulk-verify gate.

## Freshness

- `last_designed` set by route-mapper at write time, ISO 8601 UTC. `design_baseline` is the label/version of the design generation the map encodes.
- Stale checks: compare `last_designed` against the most recent modification time of any file in `$REQ_DIR/designs/`, the codebase's tokens file, and any asset under `public/images/`. If any is newer → re-run.
- **Incremental re-run vs. baseline migration — decide which you are doing BEFORE touching the map. This distinction is load-bearing.**
  - **Incremental re-run** — the design *generation* is the SAME (`design_baseline` unchanged); a few screens / tokens / assets were tweaked. Scope the diff and update ONLY the affected sections. Recompute SHA-256 for changed assets.
  - **Baseline migration** — the design generation itself changed: a redesign, a design-system version bump (e.g. Full → V2), a new Figma file. The incoming `design_baseline` differs from what the map currently records. An incremental update here is WRONG twice over: it produces a half-old / half-new map, AND it lets screens that look "unchanged" pass as current when their spec is actually still the OLD generation. On a baseline migration you MUST: (1) re-derive EVERY screen's spec against the new design generation — not just the screens whose source files happened to change; (2) set the new `design_baseline`; (3) bump `last_designed`. Then every screen is in scope for `visual-fidelity-reconciliation`, where — critically — an implementation that has NOT changed since the migration began is **drifted by definition** (it was never migrated). "Unchanged" after a baseline migration is unfinished work, never a clean bill of health.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "The implementation is the design — we don't need a separate spec" | No. Without an explicit spec, design drift accumulates silently as developers freelance on spacing, weights, and colors. Codify the contract or lose it. |
| "I'll just check it looks right" | "Looks right" is unauditable and unactionable. A PM cannot read your eyes; future tests cannot regress on your opinion. Codify the contract. |
| "Figma is the source — we don't need a copy in the repo" | Figma drifts between exports; the design file changes upstream and Playwright doesn't notice. `DESIGN_MAP.md` is the captured snapshot at a known commit; the tests assert against it. |
| "Visual regression is too brittle" | Pixel snapshots are brittle; computed-style assertions are not. Use both: snapshots only at the route's primary viewport with explicit masks; computed styles for typography and color where the contract is exact. |
| "I'll add the design spec later" | "Later" never happens. The route-mapper runs once per refresh — that is when the spec lands. |
| "Estimating values from a screenshot is too imprecise" | Then mark them `~approximate` and flag in `## Coverage & Gaps` with `escalate: true`. Escalating is correct; inventing precise values is not; skipping the map is worst. |
| "Drift is fine — the design was old anyway" | Then update the design and document the decision in `## Detected Drift`. Silent drift is a process failure even if the new value is "better". |
| "We don't use design tokens, we hard-code values" | Then the Design Tokens table is built from grep-ing the hard-coded values into a normalized set, and `## Detected Drift` will be a long list — that is information the team needs. |
| "The asset has no integrity hash because it's served from a CDN" | Hash the served bytes, then. Pin the URL or the asset version. Without a hash, the contract has a hole an attacker (or a wrong S3 bucket) walks through. |
| "I'll mark it complete without filling in the per-element specs" | Then `playwright-user-flows` has no contract to assert against. Visual-fidelity tests need every interactive element in the table. |

## Red flags — STOP and re-think

- You estimated values from a screenshot but did NOT flag them as approximate.
- An asset is in `public/images/` but has no row in the Asset Registry.
- An interactive element from `playwright-user-flows`'s inventory has no row in any `## Per-Screen Visual Specs` table.
- `## Detected Drift` is empty but the implementation values and design values are clearly disagreeing (you found one such pair; assume there are more).
- `## Coverage & Gaps` is empty and you provided a design artifact for only one screen out of three.
- You proposed values you "think look right" instead of citing a source.
