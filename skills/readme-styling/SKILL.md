---
name: readme-styling
description: Use when creating or updating a README or any top-level project document and you want the house "bitmap" aesthetic — ASCII block-letter banner, gradient section dividers, box-drawing panels and inventory grids, ASCII flowcharts, logic maps that show routing and gates, a status timeline, colored badges, and a per-project color theme. Triggers — authoring or refreshing a README, the user asks for "flair" / "colorful" / "centered" / "bitmap" / "make it look good" styling, a new plugin or project needs its README, a version bump needs the README brought current, or a project has non-trivial control flow that the README must make legible. Reference guide — provides the canvas + centering rules, the pipe-table / ASCII-graph alignment rules, the banner / divider / panel / flowchart / logic-map / timeline patterns, the GitHub-safe + ANSI color model, the preset theme palettes, the interactive theme picker, and the consistency rules.
---

# Readme Styling — The Bitmap House Style

A README is the first thing anyone sees. The house style treats it as a piece of **retro-terminal bitmap art**: ASCII block-letter banners, dithered gradient dividers, box-drawing panels, ASCII flowcharts, and — for any system with non-trivial control flow — **logic maps that show exactly how requests route and where the gates are.** The result reads like an 8-bit manual: dense, scannable, confident, and impossible to mistake for a generic auto-generated README.

This is a reference skill. Apply the patterns below; the plugin's own [`README.md`](../../README.md) is the canonical reference implementation.

## The canvas — one width, everything centered to it

The single most common amateur tell is elements of different widths stacked left-aligned, so the page lists to one side like crooked shelves. The house style fixes a **canvas width** for the whole document and centers everything to it.

1. **Pick ONE canvas width** at the top of the job and hold it for the entire document. Default **74 columns**; widen only if a dense inventory grid genuinely needs it (then *every* full-width rule matches the wider number). Never let two widths coexist.
2. **Full-width elements are built to exactly the canvas width** — every `░` divider row, the `▰` timeline track, a panel's outer border. Count the columns; they must all end in the same column.
3. **Narrower elements are centered within the canvas** — the banner, flowcharts, logic maps, the footer plate. The leading indent is `floor((CANVAS − element_width) / 2)`. Compute it; do not eyeball it. That indent is the document's **visual spine** — every centered block shares it.
4. **The spine is consistent.** If the banner is centered with a 9-space indent, the flowchart and the timeline content sit on a compatible indent. A reader's eye should never have to re-find the center.

A README whose elements are all the same width or all centered to one spine reads as *deliberate*. That is the whole effect.

## What "colorful" means — GitHub-safe color and the ANSI variant

Color renders in two completely different worlds. The house style serves both, and never confuses them.

**On GitHub (the committed `README.md`)** — GitHub-rendered Markdown will NOT render ANSI escapes or HTML `<font color>`. Real color comes from exactly three places:

1. **Badges** — shields.io badges render as real colored pills. The literal-color layer; their hex values come from the active theme palette.
2. **Mermaid diagrams** — a ` ```mermaid ` fence renders on GitHub as a real diagram, and `classDef` / `style` give it **real fill and stroke color**. This is the way to get a *colored* diagram on GitHub. Use Mermaid for the headline architecture diagram when color matters; keep ASCII for the bitmap-charm logic maps.
3. **The glyph palette** — `█▓▒░`, `◆◇▸▌▰`, box-drawing — monochrome, but they make the page feel rich and deliberate.

**In a terminal (the optional ANSI variant)** — a terminal renders ANSI SGR color in full. The house style defines an **ANSI-colored variant** — the same banner / dividers / panels, wrapped in ANSI escapes from the active theme's ANSI palette — for display via `cat`, a TUI, or an agent session. **The ANSI variant is a SEPARATE artifact** (`README.ansi`, or emitted on demand) — it is NEVER the committed `README.md`, because raw ANSI renders as escape-code garbage on GitHub. Committed `.md` = GitHub-safe; ANSI = a separate terminal rendering.

## The theming engine — a per-project color identity

Every project gets a **theme** so its README has a consistent, distinct color identity instead of the same default blue everywhere.

A theme is four palettes that move together:

| Theme | Badge hex | Accent | ANSI fg | Mermaid fill | Vibe |
|---|---|---|---|---|---|
| `midnight` | `2563EB` | indigo `◆` | bright blue (`94`) | `#1e3a8a` | deep-blue terminal (default) |
| `phosphor` | `3FB950` | green `◆` | bright green (`92`) | `#14532d` | green-CRT / matrix |
| `amber` | `D97706` | amber `◆` | yellow (`93`) | `#78350f` | amber-CRT / vintage |
| `synthwave` | `C026D3` | magenta `◆` | bright magenta (`95`) | `#701a75` | magenta + cyan, neon |
| `crimson` | `DC2626` | red `◆` | bright red (`91`) | `#7f1d1d` | high-contrast alert red |
| `mono` | `6B7280` | grey `◆` | white (`97`) | `#374151` | pure greyscale, no hue |

The theme drives: the badge `color` segments, the Mermaid `classDef` fill/stroke, the ANSI variant's escape codes, and (optionally) the accent-glyph tint description. The glyph SHAPES never change — a theme tints, it does not restyle.

### The interactive picker — choose the theme at first setup

The chosen theme is recorded in a marker comment at the very top of the README (right after the `# H1`):

```markdown
<!-- architect-team:readme-theme=midnight -->
```

**When an agent authors or refreshes a project's README:**

- **Marker present** → read the theme name from it; apply that theme; do NOT prompt. The look stays stable across every future refresh.
- **Marker absent (first setup)** → run the picker: present the six preset themes (the table above — name + vibe) to the user and ask which they want. Use a structured choice prompt (e.g., `AskUserQuestion`). Write the chosen `<!-- architect-team:readme-theme=<name> -->` marker, then style the README with that theme.

This is the "small theming engine": a fixed palette set + a one-time pick + a recorded marker. No new tooling, no config files — the marker travels inside the README it themes.

## Anatomy of a styled README (in order)

1. `# H1` — the real project name (screen-readable).
2. **Theme marker** — `<!-- architect-team:readme-theme=... -->`.
3. **Banner** — ASCII block-letter name, centered on the canvas.
4. **Tagline** — a `>` blockquote, one tight paragraph, bold accents on the differentiators.
5. **Badge row** — themed shields.io badges.
6. **NEW IN** — what changed in the current version.
7. **WHAT YOU GET** — the inventory grid (boxed, canvas width).
8. **INSTALL / USAGE** — fenced command blocks.
9. **Diagrams** — the flowchart AND the logic maps (routing + gates).
10. **Detail sections** — loops, conventions, development.
11. **STATUS** — the version timeline.
12. **LICENSE + footer plate.**

Every major section is introduced by a gradient divider.

## 1. The banner

ASCII block letters spelling the project name, in a **bare** fenced code block, **centered on the canvas**, followed by a spaced subtitle + version line:

```
        █████  ██████   ██████ ██   ██
        ██   ██ ██   ██ ██      ██   ██
        ███████ ██████  ██      ███████
        ██   ██ ██   ██ ██      ██   ██
        ██   ██ ██   ██  ██████ ██   ██

            ─── S U B T I T L E ───   v X . Y . Z
```

- Each letter is a 5-row grid of `█` and spaces. Hand-assemble or use a figlet-style block font (`ANSI Regular`, `ANSI Shadow`, `Banner`).
- Keep the banner glyph-width **≤ canvas − 4** so the centering indent is positive; never let it scroll on mobile.
- Indent every banner row by the SAME computed centering indent — the rows stay a rigid block.
- The subtitle is letter-spaced (`T E A M`), em-dash framed; the version uses spaced digits (`v 0 . 9 . 16`).

## 2. Tagline + badges

The tagline is a single `>` blockquote — 3-5 lines, differentiators in **bold**. The themed badge row sits right after it:

```markdown
![version](https://img.shields.io/badge/version-0.9.16-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-NNN%20passing-3FB950?style=flat-square)
```

- The version badge's color is the **theme badge hex** (`2563EB` for `midnight`). License + a green pass-status badge stay green (`3FB950`) — green reads as "good" universally.
- Use `style=flat-square` — squared corners harmonize with the bitmap art; rounded badges fight it.
- 3-5 badges max: version, license, test status, one project-specific badge.

## 3. Section dividers (the gradient motif)

Every major section opens with a two-part divider in a **bare** fence — a row of `░` at the **full canvas width**, then a centered title flanked by the dither gradient:

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  SECTION TITLE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

`█▓▒░` (full → dark → medium → light) on the left, mirrored `░▒▓█` on the right. **Every `░` row in the document is exactly the canvas width** — identical, no exceptions.

## 4. Boxed panels & inventory grids

Box-drawing builds titled panels and multi-column grids, the outer border at **canvas width**:

```
┌─ TITLE (n) ─────────────────────────┬─ TITLE (n) ───────────────────────┐
│ ◇ item                              │ ◆ item                  (tag)     │
├─ SUBSECTION ────────────────────────┴───────────────────────────────────┤
│ ▸ full-width row                                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

Rules:
- Pick **one box weight** for the document — light (`┌─┐│├┤┬┴┼└┘`) or heavy (`┏━┓┃┣┫┳┻╋┗┛`). Never mix.
- Pad every cell to an identical width so the right border is a straight vertical line. Misaligned borders read as broken.
- The outer border spans exactly the canvas width; every row is therefore the same length.
- Titles live in the top/joint border. A `┬` opens a column spine; the matching `┴` closes it.

## 5. Pipe tables & ASCII graphs — alignment is centering

Any structure built from `│` / `|` and text — an ASCII table, a flowchart, a logic map — must have its **columns aligned** and the **whole structure centered** on the canvas. Crooked is the amateur tell; this section is how you avoid it.

**ASCII tables (inside a bare fence):**

1. For each column, find the widest cell (including the header). That is the column width.
2. Pad every cell in that column to that width — left-pad numbers, left-align text — so every `│` separator lands in the same column on every row.
3. Sum the column widths + separators = the table width. Center the whole table on the canvas with the computed indent.

```
        ┌──────────────┬─────────┬──────────┐
        │ Phase        │  Gate   │  Verdict │
        ├──────────────┼─────────┼──────────┤
        │ review-gate  │  hook   │  exit 2  │
        │ completion   │  Stop   │  exit 0  │
        └──────────────┴─────────┴──────────┘
```

(Markdown pipe tables — `| col | col |` rendered by GitHub — are a different thing: GitHub lays them out; you cannot center them with text, and that is fine. These rules are for ASCII tables in code fences.)

**ASCII graphs (flowcharts / logic maps):**

- Every box on a row is the **same width**; the row of boxes is centered on the canvas as one unit.
- Connectors (`───▶`, `│`, `▼`, `▲`) land on consistent columns — a `▼` sits directly under the `│` that feeds it.
- Multi-row graphs share one left spine; a box in row 2 aligns under its parent in row 1.

## 6. ASCII flowcharts

A flowchart shows **linear progression** — phases in sequence. Equal-width boxes, terse labels, directional connectors, centered on the canvas:

```
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │   STAGE A   │───▶│   STAGE B   │───▶│   STAGE C   │
   │  · detail   │    │  · detail   │    │  · detail   │
   └─────────────┘    └─────────────┘    └─────────────┘
```

For a *colored* flowchart on GitHub, author it as Mermaid instead — see §9.

## 7. Logic maps — show the routing and the gates (REQUIRED for systems with control flow)

A flowchart shows *what happens next*. A **logic map** shows *how flow is decided* — the **decision points**, the **gates**, the **routing**. Any project with non-trivial control flow — review gates, conditional routing, validation that rejects, retry/escalation loops — **MUST** include at least one logic map.

Vocabulary on top of the flowchart connectors:

- **Decision node** — a condition with labeled outgoing edges. Label every branch (`yes` / `no` / the value).
- **Gate node** — a point that blocks or allows. Render it unmistakably: a `▣ GATE` marker, pass edge forward, fail edge looping back / escalating.
- **Verdict node** — `✓` allow, `✗` block, with the concrete effect (`exit 0`, `exit 2`, `SR written`).
- **Route-back edge** — a dashed `◀┄┄┄` returning flow to an earlier actor.

```
              TaskUpdate(status = completed)
                          │
                          ▼
              ┌───────────────────────┐
              │  ▣  REVIEW GATE       │
              │  evidence valid?      │
              └───────────┬───────────┘
                  ┌──── no ────┐──── yes ────┐
                  ▼                          ▼
            ✗  BLOCK  (exit 2)        ✓  ALLOW  (exit 0)
                  ┊                  task marked complete
                  └┄┄▶ back to author, fix the gap, retry
```

Give every logic map a one-line caption. One map per decision domain — never a tangled mega-map.

## 8. The status timeline

A version history bracketed by `▰` track lines at canvas width, `◆` marking the current release:

```
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
           v0.1.0 ─ initial release
           v0.9.15 ─ documentation-currency gate
   ◆       v0.9.16 ─ readme-styling: centering + color + themes (current)
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
```

## 9. Colored diagrams with Mermaid (GitHub color)

When a diagram should be *colored* on GitHub, author it as Mermaid and color it with `classDef` from the theme's Mermaid fill:

````
```mermaid
flowchart LR
    A[Intake] --> B[Plan] --> C[Build] --> D[Review] --> E[Ship]
    classDef themed fill:#1e3a8a,stroke:#2563EB,color:#fff
    class A,B,C,D,E themed
```
````

Swap the `fill` / `stroke` for the active theme's Mermaid colors. Keep Mermaid for the one headline architecture diagram; the bitmap logic maps stay ASCII (their charm is the monospace grid).

## The glyph palette (one glyph, one meaning)

| Glyph | Meaning |
|---|---|
| `█▓▒░` / `░▒▓█` | gradient / dither — divider flanks |
| `◆` | filled diamond — agents, primary bullets, divider markers, the theme accent |
| `◇` | hollow diamond — skills |
| `▸` | triangle — commands, sub-bullets, steps |
| `▌` | half-block — subsection / loop headers |
| `▣` | framed square — a GATE node in a logic map |
| `✓` / `✗` | verdict — allow / block |
| `▰` `▱` | filled / empty track — the status timeline |
| `▄` `▀` | upper / lower half-block — the footer plate |
| `───▶` `◀───` `▼` `▲` `│` | flow connectors |
| `◀┄┄┄` | dashed — a route-back / loop edge |

Box-drawing — light: `┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ─ │` · heavy: `┏ ┓ ┗ ┛ ┣ ┫ ┳ ┻ ╋ ━ ┃` · double: `╔ ╗ ╚ ╝ ═ ║`.

## Consistency rules (non-negotiable)

- **One canvas width.** Every full-width element is exactly it; every narrower element is centered to it with a computed indent. No eyeballing.
- **ASCII art goes in a BARE fence** — ` ``` ` with NO language tag. A language tag invokes a highlighter that recolors and mangles box-drawing and shade glyphs. Command examples DO get a tag (` ```bash `); Mermaid diagrams get ` ```mermaid `.
- **One box weight, one divider width, one glyph-meaning map** per document.
- **Pad for alignment.** Every box border and every `│` separator is a straight vertical line. Count columns.
- **The committed `README.md` is GitHub-safe.** No raw ANSI, no HTML color. The ANSI-colored rendering is a separate variant artifact.
- **One theme per project**, recorded in the `<!-- architect-team:readme-theme=... -->` marker. Read the marker; do not re-prompt or silently re-theme.
- **Decoration never carries content alone.** Every art block is mirrored by real Markdown (an `# H1`, a heading, a table, prose) — screen readers see only the Markdown.
- **Keep it current.** On every version bump, update the banner version, badges, inventory counts, NEW IN, and timeline.

## Anti-patterns

| Rationalization | Rebuttal |
|---|---|
| "I'll center elements by eye — close enough." | "Close" lists to one side. Compute `floor((CANVAS − width) / 2)` and indent every row by exactly that. |
| "The dividers can be one width and the grid another." | Two widths = a crooked page. One canvas width; everything matches or centers to it. |
| "I'll tag the art fence `text` so it looks intentional." | The highlighter mangles box-drawing and shade glyphs. Art fences are bare. Always. |
| "I'll put ANSI color in the README so it pops." | Raw ANSI renders as escape-code junk on GitHub. The committed `.md` is GitHub-safe; ANSI is a separate variant. |
| "Mixing light and heavy box lines adds variety." | It reads as broken rendering. One weight per document. |
| "The borders are roughly aligned, close enough." | A crooked border is the single most amateur tell. Count columns; pad exactly. |
| "Every project can just use the default blue." | A theme gives each project a color identity. Run the picker once; record the marker. |
| "Prose explains the gates fine; a diagram is extra work." | Prose hides branches. A logic map makes every gate and route legible — required, not decorative. |
| "Emoji everywhere makes it lively." | The bitmap glyph palette does the accenting. Emoji are optional and sparing; a flood cheapens the aesthetic. |

## Reference implementation

This plugin's [`README.md`](../../README.md) applies every pattern here — the theme marker, the centered banner, canvas-width gradient dividers, the boxed inventory grid, aligned ASCII tables and flowcharts, the routing/gate logic maps, the status timeline, the footer plate. Read it as the worked example before styling a new README.
