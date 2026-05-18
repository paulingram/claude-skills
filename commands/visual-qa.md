---
description: Run a pixel-perfect post-development visual-QA reconciliation against DESIGN_MAP.md for one or all frontend codebases. Refreshes the design map if stale, runs code-first static analysis, then Playwright runtime verification with per-state screenshots, and produces a reconciliation report. Drift / gaps escalate to the architect-team via handoff — never inline-patched.
argument-hint: [codebase-path]
---

# /architect-team:visual-qa — On-Demand Visual Fidelity Reconciliation

You are running the visual-QA pipeline against one or all frontend codebases. The user invoked this with optional `$ARGUMENTS = <codebase-path>`. If empty, you reconcile every frontend codebase tracked in the workspace.

## Step 1 — Discover frontend codebases in scope

1. If `$ARGUMENTS` is provided AND is a valid path → that single codebase is in scope. Resolve to absolute. Assert `git -C <path> rev-parse --is-inside-work-tree`.
2. If `$ARGUMENTS` is empty:
   - Read `<workspace>/.architect-team/intake-state.json` (produced by `intake-and-mapping` in Phase −1). Enumerate every codebase classified as `frontend` or `fullstack`. Each is in scope.
   - If no intake state exists, ask the user: "I cannot find an intake-state.json. Which codebase(s) should I reconcile? Provide a path or run the architect-team pipeline first."
3. For each in-scope codebase, confirm `<codebase>/docs/DESIGN_MAP.md` exists. If it does NOT exist for a codebase, check whether design inputs exist (per `design-fidelity-mapping`'s trigger list — `designs/` / `screens/` / `mockups/` in `$REQ_DIR`, `tailwind.config` / `theme.ts` / `tokens.json` / `.storybook/` / `assets/` in the codebase). If design inputs exist but DESIGN_MAP.md does not, this is the first gap — emit a structured message asking the user whether to generate DESIGN_MAP.md first via the `route-mapper` agent. If design inputs do NOT exist for the codebase, skip it with a one-line explanation in the report.

## Step 2 — Freshness check on DESIGN_MAP.md (refresh if stale)

For each in-scope codebase:

1. Read DESIGN_MAP.md's YAML frontmatter and extract `last_designed` (ISO 8601 UTC).
2. Run `git -C <codebase> log -1 --format=%cI -- <codebase-frontend-paths>` where `<codebase-frontend-paths>` is the union of frontend-related paths: every component dir, the tokens file, the assets dir, Storybook config. (A coarse approximation is `git -C <codebase> log -1 --format=%cI`, but prefer the scoped form if you can list the paths from CODEBASE_MAP.md and DESIGN_MAP.md.)
3. Also stat the modification times of:
   - Every file in `$REQ_DIR/designs/` (if present).
   - The codebase's tokens file (`tailwind.config.{js,ts}` / `theme.ts` / `tokens.json` / `styles/tokens.css`).
   - Every file in the codebase's `assets/` / `public/images/` / `public/assets/` / `static/images/` dir.
4. If the most-recent of (commit time, design input mtimes, tokens mtime, asset mtimes) is NEWER than `last_designed`, DESIGN_MAP.md is STALE. Refresh it by spawning the `route-mapper` agent against the codebase per the `design-fidelity-mapping` skill's update-mode rules. Do NOT proceed to Step 3 until the refresh has completed and `last_designed` has been updated.
5. If DESIGN_MAP.md is current, proceed directly to Step 3.

State the freshness result explicitly to the user: "DESIGN_MAP.md for <codebase> is current as of <last_designed>" OR "DESIGN_MAP.md for <codebase> was stale (commit on <ts>, last_designed <ts>); refreshed before running reconciliation."

## Step 3 — Apply `visual-fidelity-reconciliation`

For each in-scope codebase:

1. **Phase A — Scope identification.** All screens with a per-screen visual spec in DESIGN_MAP.md are in scope (this is an audit, not a per-team gate). All states listed for each element are in scope. All viewports in `viewports_responsive` are in scope.

2. **Phase B — Code-first static analysis.** For every in-scope element:
   - Locate the component source (`grep` the testid / role-name).
   - Trace every styling layer (inline styles, Tailwind classes resolved via the config, CSS modules, CSS-in-JS, theme variables, cascade from parents).
   - Compare each resolved style to the DESIGN_MAP spec.
   - Verify asset references resolve to entries in the Asset Registry AND the file's SHA-256 matches the registered hash (compute via `sha256sum` / `certutil`).
   - Record `static_verdict` per element per state.

3. **Phase C — Runtime verification with Playwright.** Start a dev server if not running (use the codebase's documented dev command from CODEBASE_MAP.md, e.g., `npm run dev`, `pnpm dev`, `yarn dev`, `next dev`). Wait for it to be ready (poll the dev URL until 200). Then for every (screen, viewport) pair:
   - Set viewport EXACTLY to the spec.
   - Navigate to the screen.
   - For every (element, state) tuple:
     - Induce the state (hover / focus / active / disabled / loading / error / empty per the table in the skill).
     - Capture computed styles + bounding box.
     - Take an element screenshot to `<test-output-dir>/visual-fidelity/screenshots/<screen>-<element>-<state>-<viewport>.png`.
     - Take a page screenshot to `<test-output-dir>/visual-fidelity/screenshots/<screen>-<state>-<viewport>-page.png`.
   - Compare every captured value to DESIGN_MAP using zero-tolerance defaults (per the skill's tolerance table).
   - Record `runtime_verdict` per tuple.

4. **Phase D — Reconciliation report.** Persist `<test-output-dir>/visual-fidelity/<screen>-<viewport>-<timestamp>.json` per (screen, viewport). Persist a single aggregated `<cwd>/.architect-team/visual-fidelity-summary-<ts>.md` for the run.

5. **Phase E — Remediation (fix to spec by default).** For each tuple with verdict `drift` or `gap`, consult `visual-fidelity-reconciliation`'s decision matrix:
   - **Drift in any frontend file** → fix the implementation (className / inline style / token / asset reference) to produce the spec value. Re-run Phase B + Phase C for the affected tuples. Loop until `perfect`. The reconciliation JSON records every iteration in `passes_after_fix`.
   - **Gap: element specified but not rendered** → add the JSX / binding to render per spec; re-run.
   - **Gap: element rendered but not in spec** → escalate (user decision required: add to spec or remove from implementation).
   - **Spec ambiguity** (token referenced but undefined, contradictory specs) → escalate to fix the spec first via `design-fidelity-mapping`, then re-reconcile.
   - **Cascade blast radius** (the fix introduces drift in dependent screens) → escalate to the architect-team to plan the cascade.
6. **Escalation handoffs** (only for the four named cases above): write `<cwd>/.architect-team/handoffs/visual-qa-to-architect-<reason>-<screen>-<ts>.md` containing: DESIGN_MAP version reconciled against, summary of the drift/gap, the specific decision-matrix case that triggered escalation, links to JSON + screenshots. Identify the team that likely introduced the upstream issue via `git log -p --since=<last_designed> -- <files-involved>` and include `to: <team>` in the frontmatter.
7. **When a fix is applied**, also write an informational handoff to the team that introduced the drift (`visual-qa-to-<team>-fixed-<screen>-<ts>.md`) — not blocking, just heads-up so their next change matches the corrected spec.

## Step 4 — Report to the user

Emit a structured summary:

```
visual-qa run complete @ <ISO 8601 UTC>
codebases reconciled: <N>

per-codebase results:
  <codebase-name>:
    DESIGN_MAP.md status: current | refreshed
    screens reconciled: <N>
    tuples reconciled: <N>
    verdicts: perfect=<N>, drift=<N>, gap=<N>
    perfect_percentage: <N.NN>%
    handoffs written: <list of paths if any>
    summary: <path to .architect-team/visual-fidelity-summary-<ts>.md>

overall: PASS | DRIFT_DETECTED | GAPS_DETECTED
```

If `overall != PASS`, also list the top 5 highest-severity findings in the terminal output. Direct the user to the summary file and the handoffs for the full evidence.

## Operating rules (non-negotiable)

- Always refresh DESIGN_MAP.md if stale BEFORE running reconciliation. A reconciliation against a stale contract is worse than no reconciliation.
- Always run BOTH Phase B (code-first) AND Phase C (runtime). Skipping either is forbidden — they catch different drift classes.
- **Fix drift to align to the spec by default.** Alerting the user without fixing is a process failure. The discipline CONVERGES to the spec; only escalate when one of the four named cases applies (out-of-scope, implementation-extras, spec-ambiguity, cascade-blast-radius).
- Always re-run reconciliation after any fix; record each iteration in the reconciliation JSON's `passes_after_fix`. A claim of `pass` without the corresponding iteration record is invalid.
- After fixing a token-level cascade, re-run reconciliation on EVERY screen that depends on that token, not just the screen that surfaced the drift. Convergence across all dependent screens is the bar.
- Always produce screenshots as evidence. A reconciliation report with no screenshots is invalid.
- Match the viewport(s) declared in DESIGN_MAP.md exactly. Different viewport → different verdict; mixing them invalidates the report.
- If the dev server cannot be started (build failure, port conflict, missing env), report the failure clearly and STOP. Do not approximate runtime results from static analysis alone.
- Every escalation handoff names the specific decision-matrix case that triggered it. A handoff without that name is an alert, not an escalation.
