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

If none of the above exist, this skill is skipped. The codebase-map-reviewer must NOT flag a missing `DESIGN_MAP.md` as a deficiency in that case.

## File location and format

- Path: `<codebase>/docs/DESIGN_MAP.md`.
- YAML frontmatter (required):
  ```yaml
  ---
  last_designed: 2026-05-18T10:30:00Z
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

## Freshness

- `last_designed` set by route-mapper at write time, ISO 8601 UTC.
- Stale checks: compare `last_designed` against the most recent modification time of any file in `$REQ_DIR/designs/`, the codebase's tokens file, and any asset under `public/images/`. If any is newer → re-run.
- On re-run, scope the diff (which screens changed, which tokens changed, which assets changed) and update only the affected sections. Recompute SHA-256 for changed assets.

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
