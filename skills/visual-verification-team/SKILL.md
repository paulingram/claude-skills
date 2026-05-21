---
name: visual-verification-team
description: Use when visual-fidelity reconciliation needs to be independently verified against the live running app — at Phase 5, or via the visual-qa command. Spawns a three-role team — visual-capture agents start the live app and capture screenshots plus computed-style DATA for every DESIGN_MAP screen (countable, hard-to-fake artifacts); visual-analyzer agents perform objective structural analysis (a deterministic data diff of the captured values against the design spec, a pixel diff against the design reference image, and a code cross-check); then the system-architect synthesizes the per-screen gap lists holistically, clustering them into root causes and routing fixes. Replaces the single-agent verifier — capture, analysis, and synthesis are separate roles so no one agent can cut a step inside itself.
---

# Visual Verification Team — Capture, Analyze, Synthesize

The recurring failure of visual QA is an agent that reads the code, reasons about the styles, writes "perfect," and never renders the running app — or renders some of it, cuts the rest, and apologizes. A single agent doing capture + analysis + verdict can cut a corner *inside itself* invisibly. This skill removes that possibility by splitting the work into three roles with a hard artifact boundary between them:

1. **Capture** — `visual-capture` agents start the **live running app** and produce, per screen, a *capture set*: screenshots + a computed-style DATA dump from the real DOM + the design-side reference. Capture is mechanical and its output is **countable** — if DESIGN_MAP has N screens, there are N capture sets, or capture is incomplete and it is visible immediately.
2. **Analyze** — `visual-analyzer` agents perform **objective structural analysis** of the capture sets: a deterministic diff of the captured data against the design spec, a pixel diff against the design reference image, a code cross-check. They produce per-screen gap lists.
3. **Synthesize** — the `system-architect` agent reads every per-screen gap list and synthesizes them **holistically** — clustering individual gaps into root causes, deciding routing, producing the consolidated verdict and the SRs.

Analysis cannot begin until the capture artifacts exist on disk. Synthesis cannot begin until every screen has an analysis. The boundaries are the enforcement.

## The objective layer is DATA — not an agent eyeballing images

This is the load-bearing rule. The verdict "this screen matches the design at 100%" is established by **measured data**: computed styles (`font-size`, `font-weight`, `color`, `line-height`, `padding`, ...), bounding boxes, hex / rgb values, asset SHA-256 hashes. `38px ≠ 26px` is arithmetic, not an opinion — it is auditable, reproducible, and impossible to hand-wave.

Screenshots are captured and they matter, but in **two secondary roles** — never as the primary verdict:

- **Pixel diff against a design reference image** — when the design Oracle includes a reference image for a screen at the matching viewport, the analyzer runs a mechanical pixel diff (a `pixelmatch`-style comparison, or Playwright's `toHaveScreenshot`). This catches what computed styles cannot: actual rendered text content, image/icon content, overflow and clipping, z-order stacking, font rendering.
- **Gross-break inspection** — the analyzer visually inspects each screenshot for rendering that is *visibly broken* in a way no single computed-style property captures (an element rendered off-screen, text overlapping, a broken-image placeholder). This is a bounded use of vision: it catches breaks; it does NOT certify matches.

An agent looking at two images and declaring "they match" is NOT a verdict. That is the unauditable eyeballing this whole discipline exists to eliminate. Data certifies the match; images catch the breaks data misses.

## Role 1 — Capture (`visual-capture` agents, spawned in parallel)

The orchestrator partitions the screens in `DESIGN_MAP.md` into groups (5–8 screens per group) and spawns one `visual-capture` agent per group, in parallel.

Each capture agent:

1. **Starts the live app** — the real application, run against the **real backend** (real dev API, real dev data — per `dev-api-integration-testing` and the v0.9.5 real-backend discipline), using the documented dev/serve command from CODEBASE_MAP.md. Confirms it serves (HTTP 200, real app — not a 404 / error overlay). **If the app cannot be made to run, the capture agent reports `blocked` and stops** — it never substitutes anything for the live app.
2. **Captures every tuple** for its assigned screens — every (screen, element, state, viewport): navigate the live app, induce the state, set the viewport, then capture BOTH:
   - a **screenshot** (per-state element + per-viewport full-page) to `<cwd>/.architect-team/visual-fidelity/capture/<screen>-<state>-<viewport>.png`;
   - a **computed-style + bounding-box DATA dump** from the real DOM to `<cwd>/.architect-team/visual-fidelity/capture/<screen>-<state>-<viewport>.json` (every property in `visual-fidelity-reconciliation`'s measurement list).
3. **Assembles the design-side reference** for each screen — the design image from `$REQ_DIR/designs/` (or equivalent) if one exists; OR a screenshot of a renderable design prototype / reference deploy if the requirements provide one; OR, if neither exists, records `reference: spec-only` (the DESIGN_MAP spec values are the only reference). Records which.
4. Capture is **mechanical — no verdicts.** A capture agent never decides "this looks right." It renders, it screenshots, it measures, it records. Judgment is Role 2's job.

Capture agents are read-only on source code; they write only capture artifacts.

## Role 2 — Analyze (`visual-analyzer` agents, spawned in parallel)

The orchestrator spawns `visual-analyzer` agents, partitioned by screen-group, once the capture sets exist. Each analyzer, for its assigned screens:

1. **Data diff (the verdict).** For every captured tuple, diff the captured computed-style/box DATA against the DESIGN_MAP spec, zero-tolerance per the skill's tolerance table. Every property that is not an exact match is a gap, recorded with the measured value, the spec value, and the delta. This diff is deterministic — it does not depend on the analyzer's perception.
2. **Pixel diff (when a reference image exists).** Run a mechanical pixel diff of the captured live screenshot against the design reference image at the matching viewport. Record the diff ratio and the diff-overlay image. A non-trivial diff in a region the data diff reported clean is a finding — usually content (text/icon) the computed styles do not cover.
3. **Code cross-check.** Read the component source for each gap and confirm the captured value traces to a real code value (catches a runtime cascade, and catches a test that was updated to match the drift).
4. **Gross-break inspection.** Inspect each screenshot for visibly broken rendering (overflow, clipping, off-screen elements, z-order glitches, broken-image placeholders). Record any as gaps even if the data diff was clean.
5. **Spec-completeness check.** If a captured screen / element / state has no spec row in DESIGN_MAP, the analyzer cannot certify it 100% — it flags `spec-incomplete` (you cannot verify against a partial contract; this routes to a `design-fidelity-mapping` refresh).

Output: a per-screen **gap list** at `<cwd>/.architect-team/visual-fidelity/analysis/<screen>-<ts>.json` — every gap with `kind` (`data-drift` / `pixel-drift` / `gross-break` / `missing-element` / `spec-incomplete`), measured-vs-spec values, severity, and evidence paths (the capture screenshot, the data dump, the pixel-diff overlay). A screen with zero gaps is recorded explicitly as `verified-perfect` — the absence of a gap entry is not the same as a verified screen.

## Role 3 — Synthesize (the `system-architect`, "Visual Gap Synthesis" mode)

The orchestrator dispatches the `system-architect` agent with every per-screen gap list. It does NOT just concatenate them — it synthesizes:

1. **Completeness check first.** Confirm a capture set exists for every DESIGN_MAP screen and a gap list exists for every capture set. `screens_captured == screens_analyzed == design_map_screen_count`. If any screen was not captured or not analyzed, the verification is incomplete — verdict `incomplete`, send the missing screens back to capture/analysis. A team cannot pass on a partial sweep.
2. **Cluster the gaps into root causes.** Twelve `data-drift` gaps that are all "heading uses the wrong type token" is ONE systemic issue (a token regression), not twelve. Three screens that are 100% the *previous* design generation is "those three were never migrated" (the design-baseline-migration case from `visual-fidelity-reconciliation`). Cluster by: shared token, shared component, shared screen-set, shared design-baseline. The cluster — not the individual gap — is the unit of the fix.
3. **Route.** A systemic token cluster → one fix at the token, re-verify all dependent screens. Per-screen clusters → per-screen fixes. Spec-incomplete → a `design-fidelity-mapping` refresh first.
4. **Consolidated verdict.** Write `<cwd>/.architect-team/visual-fidelity/verification-verdict-<codebase>-<ts>.json` with: `overall` (`pass` / `fail` / `incomplete` / `blocked`), `screens_captured`, `screens_analyzed`, `design_map_screen_count`, the gap clusters, and the routing. `overall: pass` ONLY when every screen was captured + analyzed and every gap list is `verified-perfect`.
5. **SRs.** Each gap cluster becomes a solution requirement (`origin.kind: "visual-fidelity-drift"`) so the fix routes through the normal dev loop. `blocked` (the live app would not run) escalates to the human, not to a fix team.

## Anti-cheat: the artifact boundary

The reason this works where a single self-reporting agent did not:

- **Capture sets are countable.** `design_map_screen_count` × states × viewports = the expected capture count. The synthesizer checks it. A capture agent that cut screens is caught by arithmetic, not by trust.
- **Analysis cannot precede capture.** The analyzer's input is the capture artifacts on disk. It cannot "analyze" a screen that was never captured — there is nothing to read.
- **The verdict is data.** The analyzer's data diff is deterministic; a reviewer can re-run it against the same capture JSON and get the same answer. It is not "the analyzer thought it looked fine."
- **Synthesis is independent of both.** The `system-architect` did not capture and did not analyze; it checks the counts and clusters the findings — it cannot inherit a capture/analysis agent's blind spot.

## When this fires

- **Phase 5 — Cross-Layer Integration.** After the integration agent's `visual-fidelity-reconciliation` sweep, the orchestrator runs this team to independently verify it against the live app. The team's consolidated verdict — not the reconciliation report — gates Phase 5.
- **`/architect-team:visual-qa`.** The on-demand audit runs this team as its verification gate.
- This skill replaces the single-agent `visual-fidelity-verifier`: the same independent-verification job, decomposed into capture / analyze / synthesize so no one role can cut a step inside itself.

## Hard rules (non-negotiable)

- **Live app or nothing.** Capture renders the real running app against the real backend. No live app → `blocked` → escalate. Never substitute static analysis, mockups, or Storybook-in-isolation.
- **Every screen. No sampling.** `screens_captured == screens_analyzed == design_map_screen_count` for a `pass`. The synthesizer enforces it.
- **The verdict is measured data.** An agent eyeballing two images is never the verdict. Data certifies the match; pixel-diff and gross-break inspection are the secondary nets.
- **Capture is mechanical; analysis is the judgment; synthesis is holistic.** A capture agent does not verdict. An analyzer does not cluster. The synthesizer does not re-measure. Keep the roles separate — that separation is the anti-cheat.
- **Clusters, not tuples, are the fix unit.** Report twelve token-drift gaps as one systemic cluster, not twelve isolated drifts.
