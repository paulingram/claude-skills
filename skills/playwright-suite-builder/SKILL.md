---
name: playwright-suite-builder
description: Callable orchestrator that builds and maintains a durable, persona-grouped Playwright suite for a target frontend codebase, reached via /architect-team:playwright-suite. Ten phases — P0 target and e2e-dir resolution following the repo's own convention, P1 inventory reconciled against the suite manifest, P2 intuition-map freshness, P3 review of the existing tests by dispatching the existing checkers, P4 suite-wide gap analysis, P5 gap-fill authoring per the full playwright-user-flows discipline, P6 debug-flow registration, P7 persona grouping, P8 dev-versus-prod safety classification, P9 engine-validated manifest write plus report. Triggers — "build the Playwright suite", a project with no durable test registry, the merge-boundary full run (`select --phase 8`) that needs the entire dev suite enumerated. Adds no new agents.
user-invocable: false
---

# playwright-suite-builder

Every piece needed to answer *"is this frontend properly tested?"* already exists
in CT6, and none of them add up to an answer. `test-completeness-verifier` checks
one slice. `interaction-completeness` audits one slice's element wiring.
`playwright-user-flows` authors one feature's flows. `interaction-intuition`
knows what every control is supposed to do. `test-prod-safety-classifier` knows
which tests are safe against production. `hooks/frontend_impact.py` knows when
the frontend last changed. What has been missing is the thing that composes them
into a SUITE — a durable registry of which tests exist, which map elements they
cover, who each one is for, and which of them may ever touch production.

This skill is that composition, and nothing more. Every verification stage it
runs is an existing checker it dispatches by name. It introduces **no new
agents** — reuse-first is the operating principle, and the gap here was never a
missing reviewer, it was a missing orchestrator and a missing registry.

You are the orchestrator for a ten-phase run (P0 → P9) reached via
`/architect-team:playwright-suite`. Standard flags `--no-commit` / `--no-push` /
`--no-compact` apply as they do in every pipeline.

<!-- ct6:block:principles:begin -->
## Operating principles

CT6 work is governed by eight load-bearing principles. The full statements — each with its named anti-pattern — live in `docs/ETHOS.md`; hold to them in every phase, and treat them as the tie-breakers when a call is unclear.

- **Reuse before build.** Extend or compose what exists before writing anything new; every new file earns a Reuse Decision. Anti-pattern: the greenfield reflex.
- **The producer is never its own checker.** Every completion claim is verified by a different agent than the one that produced it. Anti-pattern: self-attestation.
- **Honest boundary.** Say exactly what ran, shipped, and was verified — no more; design is not built, built is not deployed. Anti-pattern: the overclaim.
- **Unbounded solving.** Loop until the gate is green; never hand back a half-finished run on an iteration count. Anti-pattern: the arbitrary stop.
- **Default to action.** Gates are opt-in; on reversible work, pick the sensible default and proceed. Anti-pattern: permission-seeking.
- **Documentation currency.** Docs ship current or the run does not ship. Anti-pattern: the stale grid.
- **Evidence before assertion.** State a result only after running the check and reading its output. Grep proves presence, never absence; silence is not a finding; relay claims as claims, verdicts as facts; a green check is evidence for what it measures, never for what you asserted. Anti-pattern: the unverified "should work".
- **Understand before acting.** Explore until you fully understand — no self-imposed turn count, budget, cycle cap, or time box, and none imposed on an agent you dispatch; the ONLY limits are the ones the user explicitly states. Anti-pattern: the self-rationed investigation.

See `docs/ETHOS.md` for the full text.
<!-- ct6:block:principles:end -->

## The suite manifest — the durable registry

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/suite-manifest.md` and execute it in full. Do not work from memory.

One `<e2e-dir>/suite-manifest.json` per frontend codebase, committed in the target repo, binds every test to a persona, the intuition-map elements it covers and its dev / prod safety verdict; `scripts/playwright_suite/manifest.py` validates it.

## The migration boundary

**Absent a manifest, every consuming surface behaves exactly as today.** A
project that has never run this skill has no `suite-manifest.json`, and every
wired surface — `playwright-user-flows` Phase C, the pipeline's Phase 5
full-integration run, `dev-api-integration-testing`, `mini-review-sweep`,
`test-run-monitor` — takes its pre-existing path unchanged. The wiring activates
only where a manifest exists. This is the named migration boundary of this
change, and it mirrors the v3.62.0 unbound-legacy convention — a new capability
that governs where it is present, and is invisible where it is not. There is no
migration step and no flag day; the first `/architect-team:playwright-suite` run
in a project is what creates its manifest.

## Phase P0 — Target + e2e-dir resolution

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p0.md` and execute it in full. Do not work from memory.

Resolve `<e2e-dir>` by the ladder (the Playwright config's `testDir`, then an existing conventional e2e directory, then `e2e/` only when none exists) and confirm the project principles once per project.

## Phase P1 — Inventory

Glob every spec under `<e2e-dir>` (and any additional `testDir` the config
declares), parse the test titles out of each file, and reconcile the result
against `<e2e-dir>/suite-manifest.json`:

- **On disk, not in the manifest** — a test the builder did not author. It is
  inventoried with `source` `pre-existing`; its `persona`, `covers_elements[]`,
  and `covers_routes[]` are derived at P4 and its `safety` at P8. Pre-existing
  tests are first-class suite members, never second-class.
- **In the manifest, not on disk** — the file was deleted or renamed. A rename is
  detected by matching test titles; an unmatched entry is removed and named in
  the P9 report, never silently dropped.
- **Both** — reconcile the entry's `test_names[]` against the file.

Absent a manifest, this phase creates one in memory; the write happens at P9.

## Phase P2 — Intuition-map freshness

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p2.md` and execute it in full. Do not work from memory.

Compare the map's `last_intuited` against the latest frontend-touching commit via `hooks/frontend_impact.py`; an absent or stale map goes through `intuition-map-lifecycle` `ensure`, and new `low` / `unknown` items hit the bulk-verify gate before any authoring.

## Phase P3 — Review the existing tests

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p3.md` and execute it in full. Do not work from memory.

Dispatch the existing checkers suite-wide -- `interaction-completeness` as a declared and recorded tier-3 `ct6-converge` workflow, `test-completeness-verifier` as the single mechanical verifier -- and never duplicate either rubric.

## Phase P4 — Gap analysis

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p4.md` and execute it in full. Do not work from memory.

Coverage is measured suite-wide against the CONFIRMED intuition map and the user-intent maps with `playwright-user-flows` Phase C's math.

## Phase P5 — Gap-fill authoring

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p5.md` and execute it in full. Do not work from memory.

`PROPOSAL_FIRST` pauses here; otherwise author every gap-fill test per the full `playwright-user-flows` discipline and run the selected set.

## Phase P6 — Debug-flow registration

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p6.md` and execute it in full. Do not work from memory.

Sweep the resolved bug artifacts the workspace carries and register each bug path as a `debug-flow` with a live `origin_ref`.

## Phase P7 — Persona grouping

Organize the suite on disk, inside `<e2e-dir>`:

- `<e2e-dir>/personas/<persona-slug>/` — the journey tests, grouped by who they
  are for.
- `<e2e-dir>/debug-flows/` — the registered regression flows.
- `<e2e-dir>/prod-checks/` — the read-only production checks.

Then define two Playwright projects in the target's config: `dev` (the full
suite) and `prod` (the prod-checks only). Extend the config's existing
`projects[]` rather than replacing it — a project that already defines browser
matrix projects keeps them.

Moving a file updates its manifest `file` field in the same phase. A move that
leaves the manifest pointing at the old path is exactly the drift
`verify-suite-manifest`'s disk reconciliation catches, and catching your own
drift after the fact is not a substitute for not creating it.

## Phase P8 — Dev/prod classification

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p8.md` and execute it in full. Do not work from memory.

Invoke `test-prod-safety-classifier` per test and bind `safety` and `mutates_data` into the manifest; the prod project is default-deny.

## Phase P9 — Manifest write + report

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/phase-p9.md` and execute it in full. Do not work from memory.

Validate the assembled manifest with the engine, write `<e2e-dir>/suite-manifest.json` only when valid, run the full suite once, and emit the run report.

## Running the suite

> **STOP.** Before acting under this section, Read `skills/playwright-suite-builder/references/running-the-suite.md` and execute it in full. Do not work from memory.

The `dev` project is what the merge-boundary full run (`select --phase 8`) enumerates in its entirety; the `prod` project is a read-only smoke suite that `test-run-monitor` spawns through its `LocalAdapter` path.

## Operating rules (non-negotiable)

- **No new agents.** Every verification stage dispatches an existing agent. A new
  agent requires a proven gap plus a Reuse Decision, per
  `skills/reuse-first-design`.
- **Never duplicate a checker.** P3 dispatches `test-completeness-verifier` and
  `interaction-completeness`; it does not re-implement either one's rubric.
- **Never author against a missing or stale map.** P2 gates P4 and P5.
- **Never guess a persona.** Unknown personas escalate per Step 0.
- **Never promote an unclassified test to prod.** Default-deny is structural.
- **Never write an invalid manifest.** The engine gates the write.
- **The manifest lives in the target repo, committed.** It is not run state; it
  survives the run, the worktree, and the session, and CI can run from it.
- **Absent a manifest, change nothing.** The migration boundary is a promise
  every wired surface keeps.

## Relationship to other skills

- `skills/intuition-map-lifecycle` — `ensure` at P2, `bug-path-upsert` at P6.
- `skills/interaction-intuition` — the map this suite is measured against, and
  the bulk-verify gate P2 routes new uncertainty through.
- `skills/playwright-user-flows` — Phase C's coverage math at P4 and the full
  authoring discipline at P5.
- `agents/test-completeness-verifier.md` is dispatched at P3 alongside the
  `agents/interaction-reviewer.md` team that `skills/interaction-completeness`
  defines.
- `skills/test-prod-safety-classifier` — the P8 verdict source; the manifest is
  where its classification becomes binding per test.
- `skills/dev-api-integration-testing` — the `it-<prefix>` test-only data
  convention P8's exceptions require, and the full-integration path that
  enumerates this manifest.
- `skills/test-run-monitor` — spawns the prod project as an ordinary test command
  via its `LocalAdapter` source path; it never gates, it watches and reports.
- `skills/ux-test-builder` and `skills/bug-fix-pipeline` — the two lanes that
  feed the suite between builder runs, via the lifecycle verbs and manifest
  registration.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `Phase P4 — Gap analysis` | `skills/playwright-suite-builder/references/phase-p4.md` | on demand |
| `Phase P5 — Gap-fill authoring` | `skills/playwright-suite-builder/references/phase-p5.md` | on demand |
| `Phase P6 — Debug-flow registration` | `skills/playwright-suite-builder/references/phase-p6.md` | on demand |
| `Phase P8 — Dev/prod classification` | `skills/playwright-suite-builder/references/phase-p8.md` | on demand |
| `Phase P9 — Manifest write + report` | `skills/playwright-suite-builder/references/phase-p9.md` | on demand |
| `Running the suite` | `skills/playwright-suite-builder/references/running-the-suite.md` | on demand |
| `The suite manifest — the durable registry` | `skills/playwright-suite-builder/references/suite-manifest.md` | on demand |
| `Phase P0 — Target + e2e-dir resolution` | `skills/playwright-suite-builder/references/phase-p0.md` | on demand |
| `Phase P2 — Intuition-map freshness` | `skills/playwright-suite-builder/references/phase-p2.md` | on demand |
| `Phase P3 — Review the existing tests` | `skills/playwright-suite-builder/references/phase-p3.md` | on demand |
