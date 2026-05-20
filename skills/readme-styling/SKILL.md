---
name: readme-styling
description: Use when creating or updating a README or any top-level project document and you want the house "bitmap" aesthetic — ASCII block-letter banner, gradient section dividers, box-drawing panels and inventory grids, ASCII flowcharts, logic maps that show routing and gates, a status timeline, and colored badges. Triggers — authoring or refreshing a README, the user asks for "flair" / "colorful" / "bitmap" / "make it look good" styling, a new plugin or project needs its README, a version bump needs the README brought current, or a project has non-trivial control flow / gates that the README must make legible. Reference guide — provides the glyph palette, the banner / divider / panel / flowchart / logic-map / timeline patterns, the badge conventions, and the consistency rules.
---

# Readme Styling — The Bitmap House Style

A README is the first thing anyone sees. The house style treats it as a piece of **retro-terminal bitmap art**: ASCII block-letter banners, dithered gradient dividers, box-drawing panels, ASCII flowcharts, and — for any system with non-trivial control flow — **logic maps that show exactly how requests route and where the gates are.** The result reads like an 8-bit manual: dense, scannable, confident, and impossible to mistake for a generic auto-generated README.

This is a reference skill. Apply the patterns below; the plugin's own [`README.md`](../../README.md) is the canonical reference implementation.

## What "colorful" means on GitHub

GitHub-rendered Markdown does **not** render ANSI color codes — you cannot get terminal color in a README. "Colorful" is achieved three ways, and only three:

1. **Badges** — shields.io badges render as real colored pills. This is the literal-color layer.
2. **Syntax-highlighted code fences** — a fence with a language tag (` ```bash `) is colorized by GitHub's highlighter. (Art fences stay BARE — see the consistency rules.)
3. **The glyph palette + gradient motifs** — `█▓▒░`, `◆◇▸▌▰`, box-drawing — these are monochrome but they make the page feel rich and deliberate.

Do not try to embed ANSI escapes or HTML `<font color>` — the former does not render, the latter is stripped.

## Anatomy of a styled README (in order)

1. **Banner** — ASCII block-letter name.
2. **Tagline** — a `>` blockquote, one tight paragraph, bold accents on the differentiators.
3. **Badge row** — colored shields.io badges.
4. **NEW IN** — what changed in the current version.
5. **WHAT YOU GET** — the inventory grid (boxed).
6. **INSTALL / USAGE** — fenced command blocks.
7. **Diagrams** — the flowchart AND the logic maps (routing + gates).
8. **Detail sections** — loops, conventions, development.
9. **STATUS** — the version timeline.
10. **LICENSE + footer plate.**

Every major section is introduced by a gradient divider (pattern below).

## 1. The banner

ASCII block letters spelling the project name, in a **bare** fenced code block, followed by a spaced subtitle + version line:

```
 █████  ██████   ██████ ██   ██
██   ██ ██   ██ ██      ██   ██
███████ ██████  ██      ███████
██   ██ ██   ██ ██      ██   ██
██   ██ ██   ██  ██████ ██   ██

        ─── S U B T I T L E ───   v X . Y . Z
```

- Each letter is a 5-row grid of `█` and spaces. Hand-assemble, or generate with a figlet-style block font (`ANSI Regular`, `ANSI Shadow`, `Banner`).
- Keep the banner **≤ 72 columns** so it never horizontally scrolls on GitHub or mobile.
- The subtitle is letter-spaced (`T E A M`) and framed with em-dashes; the version uses spaced digits (`v 0 . 9 . 8`).
- The banner is decoration. The real project name MUST also appear as the Markdown `# H1` immediately above it (screen readers cannot read art).

## 2. Tagline + badges

The tagline is a single `>` blockquote — 3-5 lines, the differentiators in **bold**. The badge row sits right after it:

```markdown
![version](https://img.shields.io/badge/version-0.9.8-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-256%20passing-3FB950?style=flat-square)
```

Use `style=flat-square` — squared corners harmonize with the bitmap art; the default rounded badges fight it. 3-5 badges max: version, license, test status, and one project-specific badge.

## 3. Section dividers (the gradient motif)

Every major section is introduced by a two-part divider in a **bare** fenced block — a row of `░`, then a centered title flanked by the dither gradient:

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  SECTION TITLE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

`█▓▒░` (full → dark → medium → light shade) on the left, mirrored `░▒▓█` on the right — the signature dithering. The `░` rows are a fixed width (68-70 cols); keep it identical for every divider in the document.

## 4. Boxed panels & inventory grids

Box-drawing characters build titled panels and multi-column grids:

```
┌─ TITLE (n) ─────────────────┬─ TITLE (n) ───────────────────┐
│ ◇ item                      │ ◆ item               (tag)    │
├─ SUBSECTION ────────────────┴───────────────────────────────┤
│ ▸ full-width row                                            │
└──────────────────────────────────────────────────────────────┘
```

Rules:
- Pick **one box weight** for the document — light (`┌─┐│├┤┬┴┼└┘`) or heavy (`┏━┓┃┣┫┳┻╋┗┛`). Never mix weights.
- Pad every cell to an identical width so the right border is a straight vertical line. Misaligned borders read as broken.
- Titles live in the top/joint border: `┌─ SKILLS (16) ─...─┬`.
- A `┬` opens a column spine; the matching `┴` closes it; a full-width row below the spine starts with `├─...─┴─...─┤`.

## 5. ASCII flowcharts

A flowchart shows **linear progression** — phases or stages in sequence. Equal-width boxes, terse labels, directional connectors:

```
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │   STAGE A   │───▶│   STAGE B   │───▶│   STAGE C   │
   │  · detail   │    │  · detail   │    │  · detail   │
   └─────────────┘    └─────────────┘    └─────────────┘
```

Connectors: `───▶` `◀───` `▼` `▲` `│`. Keep boxes the same width; align them on a grid.

## 6. Logic maps — show the routing and the gates (REQUIRED for systems with control flow)

A flowchart shows *what happens next*. A **logic map** shows *how flow is decided* — the **decision points**, the **gates** (where flow is blocked or allowed), and the **routing** (where flow goes depending on a condition). Any project with non-trivial control flow — review gates, conditional routing, validation that can reject, retry/escalation loops — **MUST** include at least one logic map. A README that hides the gates behind prose is a README nobody can reason about.

A logic map uses a distinct vocabulary on top of the flowchart connectors:

- **Decision node** — a condition with labeled outgoing edges. Label every branch (`yes` / `no` / the condition value).
- **Gate node** — a point that blocks or allows. Render it unmistakably: a `▣ GATE` marker, with the pass edge continuing forward and the fail edge looping back or escalating.
- **Verdict / terminal node** — mark allow with `✓`, block with `✗`, and state the concrete effect (`exit 0`, `exit 2`, `SR written`).
- **Loop-back / route-back edge** — a dashed edge `◀┄┄┄` showing flow returning to an earlier actor.

Pattern — a gate:

```
              TaskUpdate(status = completed)
                          │
                          ▼
              ┌───────────────────────┐
              │  ▣  REVIEW GATE       │
              │  evidence valid?      │
              └───────────┬───────────┘
                  ┌───── no ────┐ ───── yes ─────┐
                  ▼                              ▼
            ✗  BLOCK  (exit 2)            ✓  ALLOW  (exit 0)
                  ┊                       task marked complete
                  └┄┄▶ back to author, fix the gap, retry
```

Pattern — conditional routing (a router that sends flow to different destinations by a condition value):

```
        issue surfaces ──▶ ◆ classify origin.kind
                                   │
              ┌──── test-failure ──┴── editability-gap ────┐
              ▼                                            ▼
     diagnostic research                            fix team (direct)
     (3 researchers + review)                              │
              └───────────────▶ fix team ◀─────────────────┘
```

Give every logic map a one-line caption stating what decision it documents. When a system has several independent gates or routers, draw a separate map for each — one map per decision domain, not one tangled mega-map.

## 7. The status timeline

A version history bracketed by `▰` track lines, `◆` marking the current release:

```
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
           v0.1.0 ─ initial release
           v0.9.7 ─ editability-completeness review
   ◆       v0.9.8 ─ readme-styling skill (current)
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
```

## The glyph palette (one glyph, one meaning)

Assign each glyph a single meaning and hold it for the whole document:

| Glyph | Meaning |
|---|---|
| `█▓▒░` / `░▒▓█` | gradient / dither — divider flanks |
| `◆` | filled diamond — agents, primary bullets, divider markers |
| `◇` | hollow diamond — skills |
| `▸` | triangle — commands, sub-bullets, steps |
| `▌` | half-block — subsection / loop headers |
| `▣` | framed square — a GATE node in a logic map |
| `✓` / `✗` | verdict — allow / block in a logic map |
| `▰` `▱` | filled / empty track — the status timeline |
| `▄` `▀` | upper / lower half-block — the footer plate |
| `───▶` `◀───` `▼` `▲` | flow connectors |
| `◀┄┄┄` | dashed — a route-back / loop edge |
| `─── X ───` | em-dash framing for a subtitle |

Box-drawing reference — light: `┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ─ │` · heavy: `┏ ┓ ┗ ┛ ┣ ┫ ┳ ┻ ╋ ━ ┃` · double: `╔ ╗ ╚ ╝ ═ ║`.

## Consistency rules (non-negotiable)

- **ASCII art goes in a BARE fenced code block** — ` ``` ` with NO language tag. A language tag invokes a syntax highlighter that recolors and can mangle box-drawing and shade characters; a bare fence renders plain monospace so the alignment holds. Command examples DO get a language tag (` ```bash `) — the highlighter colors real code, which is the point.
- **One box weight per document.** One divider width per document. One glyph-meaning map per document.
- **Pad for alignment.** Every box border must be a straight line. Count columns.
- **Banner ≤ 72 columns.** Dividers a fixed 68-70.
- **Decoration never carries content alone.** Every art block is mirrored by real Markdown (an `# H1`, a heading, a table, prose) that conveys the same information — screen readers see only the Markdown, not the art.
- **Keep it current.** On every version bump, update the banner version, the badges, the inventory counts, the NEW IN section, and the timeline. A stale styled README looks worse than a plain one.

## Anti-patterns

| Rationalization | Rebuttal |
|---|---|
| "I'll tag the art fence `text` / `bash` so it looks intentional." | The highlighter mangles box-drawing and shade glyphs. Art fences are bare. Always. |
| "Mixing light and heavy box lines adds variety." | It reads as broken rendering. One weight per document. |
| "The borders are roughly aligned, close enough." | A crooked border is the single most amateur tell. Count columns; pad exactly. |
| "Prose explains the gates fine; a diagram is extra work." | Prose hides branches. A logic map makes every gate and route legible at a glance — it is required, not decorative. |
| "One big diagram covers all the routing." | A tangled mega-map teaches nothing. One map per decision domain, each with a caption. |
| "Emoji everywhere makes it lively." | The bitmap glyph palette does the accenting. Emoji are optional and sparing; a flood cheapens the retro aesthetic. |
| "The README still says the old version / old counts." | A stale styled README signals neglect louder than a plain one would. Refresh it on every bump. |

## Reference implementation

This plugin's [`README.md`](../../README.md) applies every pattern here — banner, badges, gradient dividers, the boxed inventory grid, the pipeline flowchart, the routing/gate logic maps, the status timeline, the footer plate. Read it as the worked example before styling a new README.
